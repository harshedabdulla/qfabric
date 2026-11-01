package main

// `client serve` runs the QFabric demo dashboard: a single-page UI plus a
// small JSON API that drives the same flows as the CLI subcommands.
//
// The server holds Fabric Gateway connections for both OrgA and OrgB
// (each with its own User1 MSP identity), so the UI can act as either
// organization. It binds to localhost only: it signs Fabric transactions
// with the test network's user keys.
//
// Nothing secret crosses this API. The crypto service never returns
// ML-DSA secret keys or BB84 keys, and the ciphertext is not requested.

import (
	"context"
	"embed"
	"encoding/base64"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"log"
	"mime"
	"net"
	"net/http"
	"strings"
	"time"

	"github.com/hyperledger/fabric-gateway/pkg/client"
	"google.golang.org/grpc"

	"qfabric/blockchain/integration"
)

//go:embed web
var webFS embed.FS

const maxDocumentBytes = 1 << 20 // 1 MiB, matches the demo's purpose

type orgSession struct {
	cfg      *Config
	gw       *client.Gateway
	conn     *grpc.ClientConn
	contract *client.Contract
}

type server struct {
	crypto *integration.CryptoClient
	orgs   map[string]*orgSession
}

func cmdServe(args []string) error {
	flags := flag.NewFlagSet("serve", flag.ContinueOnError)
	addr := flags.String("addr", "127.0.0.1:8080", "listen address (keep it on localhost)")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if host, _, err := net.SplitHostPort(*addr); err != nil || !isLoopback(host) {
		return fmt.Errorf("refusing to listen on %q: the dashboard signs with Fabric user keys, use a loopback address", *addr)
	}

	base, err := loadConfig()
	if err != nil {
		return err
	}
	s := &server{crypto: integration.NewCryptoClient(base.CryptoAPIURL), orgs: map[string]*orgSession{}}
	for _, id := range []string{"OrgA", "OrgB"} {
		cfg := *base
		cfg.Org = orgProfiles[id]
		gw, conn, err := connect(&cfg)
		if err != nil {
			return fmt.Errorf("%s gateway: %w", id, err)
		}
		defer conn.Close()
		defer gw.Close()
		s.orgs[id] = &orgSession{&cfg, gw, conn, gw.GetNetwork(cfg.ChannelName).GetContract(cfg.ChaincodeName)}
	}

	static, _ := fs.Sub(webFS, "web")
	mux := http.NewServeMux()
	mux.Handle("GET /", http.FileServerFS(static))
	mux.HandleFunc("GET /api/status", s.handleStatus)
	mux.HandleFunc("POST /api/register", s.handleRegister)
	mux.HandleFunc("POST /api/transfer", s.handleTransfer)
	mux.HandleFunc("GET /api/transactions", s.handleList)
	mux.HandleFunc("GET /api/transactions/{id}/verify", s.handleVerify)
	mux.HandleFunc("POST /api/transactions/{id}/attacks", s.handleAttacks)

	srv := &http.Server{Addr: *addr, Handler: guard(mux), ReadHeaderTimeout: 10 * time.Second}
	log.Printf("QFabric dashboard on http://%s (crypto service %s, channel %s)", *addr, base.CryptoAPIURL, base.ChannelName)
	return srv.ListenAndServe()
}

func isLoopback(host string) bool {
	if host == "localhost" {
		return true
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.IsLoopback()
}

// guard blocks cross-site use of the local API: state-changing requests
// must be JSON (forcing a CORS preflight, which is never answered), and
// the Host header must be local (DNS rebinding).
func guard(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		host, _, err := net.SplitHostPort(r.Host)
		if err != nil {
			host = r.Host
		}
		if !isLoopback(host) {
			http.Error(w, "forbidden host", http.StatusForbidden)
			return
		}
		if r.Method == http.MethodPost {
			if ct, _, _ := mime.ParseMediaType(r.Header.Get("Content-Type")); ct != "application/json" {
				http.Error(w, "content type must be application/json", http.StatusUnsupportedMediaType)
				return
			}
		}
		next.ServeHTTP(w, r)
	})
}

func (s *server) org(id string) (*orgSession, error) {
	o, ok := s.orgs[id]
	if !ok {
		return nil, fmt.Errorf("unknown organization %q (use OrgA or OrgB)", id)
	}
	return o, nil
}

// --- handlers --------------------------------------------------------------

func (s *server) handleStatus(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()
	out := map[string]any{"organizations": map[string]any{}}
	if h, err := s.crypto.Health(ctx); err != nil {
		out["crypto"] = map[string]any{"status": "unreachable", "error": err.Error()}
	} else {
		out["crypto"] = h
	}
	orgs := out["organizations"].(map[string]any)
	for id, o := range s.orgs {
		entry := map[string]any{"orgId": id, "mspId": o.cfg.Org.MSPID, "displayName": o.cfg.Org.DisplayName, "registered": false}
		if raw, err := getOrganization(o.contract, id); err == nil {
			var rec map[string]any
			if json.Unmarshal(raw, &rec) == nil {
				delete(rec, "publicKey") // 1952-byte key; the fingerprint is enough for the UI
				entry["registered"] = true
				entry["ledger"] = rec
			}
		}
		orgs[id] = entry
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *server) handleRegister(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Org string `json:"org"`
	}
	if !readJSON(w, r, &req) {
		return
	}
	o, err := s.org(req.Org)
	if err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	p := o.cfg.Org
	keys, err := s.crypto.RegisterOrganization(r.Context(), integration.RegisterOrganizationRequest{
		OrgID: p.OrgID, DisplayName: p.DisplayName, MSPID: p.MSPID, Role: p.Role,
	})
	var apiErr *integration.APIError
	if errors.As(err, &apiErr) && apiErr.Code == "ORGANIZATION_EXISTS" {
		keys, err = s.crypto.GetOrganization(r.Context(), p.OrgID)
	}
	if err != nil {
		writeError(w, http.StatusBadGateway, err)
		return
	}
	raw, err := registerOrganization(o.contract, p, keys.PublicKey)
	if err != nil {
		writeError(w, http.StatusConflict, err)
		return
	}
	writeRaw(w, raw)
}

type transferRequest struct {
	From             string  `json:"from"`
	To               string  `json:"to"`
	Document         string  `json:"document"` // plain text from the UI
	TransactionID    string  `json:"transactionId"`
	Eavesdropper     bool    `json:"eavesdropper"`
	InterceptionRate float64 `json:"interceptionRate"`
	ChannelErrorRate float64 `json:"channelErrorRate"`
	NumQubits        int     `json:"numQubits"`
}

func (s *server) handleTransfer(w http.ResponseWriter, r *http.Request) {
	var req transferRequest
	if !readJSON(w, r, &req) {
		return
	}
	o, err := s.org(req.From)
	if err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	if req.Document == "" || len(req.Document) > maxDocumentBytes {
		writeError(w, http.StatusBadRequest, fmt.Errorf("document must be 1 byte to %d bytes", maxDocumentBytes))
		return
	}
	if req.TransactionID == "" {
		req.TransactionID = fmt.Sprintf("qfabric-tx-%d", time.Now().UnixNano())
	}
	if req.NumQubits == 0 {
		req.NumQubits = 2048
	}
	if req.InterceptionRate == 0 {
		req.InterceptionRate = 1.0
	}

	ctx, cancel := context.WithTimeout(r.Context(), 3*time.Minute)
	defer cancel()
	started := time.Now()
	transfer, err := s.crypto.SecureTransfer(ctx, integration.SecureTransferRequest{
		Sender: req.From, Receiver: req.To,
		Document:             base64.StdEncoding.EncodeToString([]byte(req.Document)),
		NumQubits:            &req.NumQubits,
		ChannelErrorRate:     &req.ChannelErrorRate,
		SimulateEavesdropper: req.Eavesdropper,
		InterceptionRate:     &req.InterceptionRate,
	})
	if err != nil {
		writeError(w, http.StatusBadGateway, err)
		return
	}
	cryptoMs := time.Since(started).Milliseconds()

	started = time.Now()
	raw, err := recordSecureTransaction(o.contract, req.TransactionID, transfer)
	if err != nil {
		writeError(w, http.StatusConflict, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"crypto": map[string]any{
			"sessionId":       transfer.SessionID,
			"bb84Status":      transfer.BB84Status,
			"abortReason":     transfer.AbortReason,
			"qber":            transfer.QBER,
			"qberThreshold":   transfer.QBERThreshold,
			"siftedKeyLength": transfer.AuditManifest.SiftedKeyLength,
			"finalKeyLength":  transfer.AuditManifest.FinalKeyLength,
			"originalSize":    transfer.OriginalSize,
			"compressedSize":  transfer.CompressedSize,
			"compression":     transfer.Compression,
			"encryption":      transfer.EncryptionAlgorithm,
			"transcriptHash":  transfer.TranscriptHash,
			"signatureBytes":  decodedLen(transfer.Signature.Value),
			"serviceVerdict":  transfer.SecurityStatus,
			"durationMs":      cryptoMs,
		},
		"ledger":           json.RawMessage(raw),
		"ledgerDurationMs": time.Since(started).Milliseconds(),
	})
}

func (s *server) handleList(w http.ResponseWriter, r *http.Request) {
	raw, err := getAllTransactions(s.orgs["OrgA"].contract)
	if err != nil {
		writeError(w, http.StatusBadGateway, err)
		return
	}
	writeRaw(w, raw)
}

func (s *server) handleVerify(w http.ResponseWriter, r *http.Request) {
	as := r.URL.Query().Get("as")
	if as == "" {
		as = "OrgB"
	}
	o, err := s.org(as)
	if err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	raw, err := verifyTransactionRecord(o.contract, r.PathValue("id"))
	if err != nil {
		writeError(w, http.StatusNotFound, err)
		return
	}
	writeRaw(w, raw)
}

type attackResult struct {
	Name        string `json:"name"`
	Description string `json:"description"`
	Refused     bool   `json:"refused"`
	Message     string `json:"message"`
}

// handleAttacks replays the attack-scenarios.sh checks against a stored
// record: each submission must be refused by the chaincode.
func (s *server) handleAttacks(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	raw, err := getTransaction(s.orgs["OrgA"].contract, id)
	if err != nil {
		writeError(w, http.StatusNotFound, err)
		return
	}
	var rec struct {
		Manifest  map[string]any `json:"manifest"`
		Signature string         `json:"signature"`
	}
	if err := json.Unmarshal(raw, &rec); err != nil {
		writeError(w, http.StatusInternalServerError, err)
		return
	}
	sender, _ := rec.Manifest["sender"].(string)
	senderOrg, err := s.org(sender)
	if err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	other := s.orgs["OrgB"]
	if sender == "OrgB" {
		other = s.orgs["OrgA"]
	}
	suffix := fmt.Sprintf("-%d", time.Now().UnixNano())
	manifestJSON := func(m map[string]any) string { b, _ := json.Marshal(m); return string(b) }

	tampered := map[string]any{}
	for k, v := range rec.Manifest {
		tampered[k] = v
	}
	tampered["qberPpm"] = 1000
	tampered["sessionId"] = fmt.Sprint(rec.Manifest["sessionId"]) + suffix

	// Fresh session id so the replay guard does not fire first: the MSP
	// check runs before signature verification.
	foreign := map[string]any{}
	for k, v := range rec.Manifest {
		foreign[k] = v
	}
	foreign["sessionId"] = fmt.Sprint(rec.Manifest["sessionId"]) + "-msp" + suffix

	results := []attackResult{
		attempt("Replay", "Resubmit the same transaction id with the original signed manifest",
			senderOrg.contract, id, manifestJSON(rec.Manifest), rec.Signature),
		attempt("Tamper", "Rewrite qberPpm to 0.1% under a fresh id, keeping the original ML-DSA signature",
			senderOrg.contract, id+"-tampered"+suffix, manifestJSON(tampered), rec.Signature),
		attempt("Wrong MSP", fmt.Sprintf("Submit %s's manifest from %s's Fabric identity (%s)", sender, other.cfg.Org.OrgID, other.cfg.Org.MSPID),
			other.contract, id+"-wrongmsp"+suffix, manifestJSON(foreign), rec.Signature),
	}
	writeJSON(w, http.StatusOK, results)
}

func attempt(name, description string, contract *client.Contract, txID, manifest, signature string) attackResult {
	_, err := submit(contract, "RecordSecureTransaction", txID, manifest, signature)
	if err == nil {
		return attackResult{name, description, false, "ACCEPTED: the ledger did not refuse this"}
	}
	return attackResult{name, description, true, chaincodeMessage(err)}
}

// chaincodeMessage extracts the chaincode's own error text from the
// gateway's wrapped gRPC error.
func chaincodeMessage(err error) string {
	msg := err.Error()
	var endorseErr *client.EndorseError
	if errors.As(err, &endorseErr) {
		for _, d := range endorseErr.Details() {
			if m := d.GetMessage(); m != "" {
				msg = m
				break
			}
		}
	}
	if i := strings.LastIndex(msg, "message="); i >= 0 {
		msg = msg[i+len("message="):]
	}
	return strings.TrimPrefix(msg, "chaincode response 500, ")
}

func decodedLen(b64 string) int {
	raw, err := base64.StdEncoding.DecodeString(b64)
	if err != nil {
		return 0
	}
	return len(raw)
}

// --- JSON helpers ----------------------------------------------------------

func readJSON(w http.ResponseWriter, r *http.Request, v any) bool {
	dec := json.NewDecoder(io.LimitReader(r.Body, 2*maxDocumentBytes))
	dec.DisallowUnknownFields()
	if err := dec.Decode(v); err != nil {
		writeError(w, http.StatusBadRequest, fmt.Errorf("invalid JSON body: %w", err))
		return false
	}
	return true
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeRaw(w http.ResponseWriter, raw []byte) {
	w.Header().Set("Content-Type", "application/json")
	_, _ = w.Write(raw)
}

func writeError(w http.ResponseWriter, status int, err error) {
	writeJSON(w, status, map[string]string{"error": chaincodeMessage(err)})
}
