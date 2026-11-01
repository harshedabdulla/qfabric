// Command client is the QFabric blockchain client. It bridges the
// Quantum/PQC service and the qfabric-audit chaincode.
//
// Usage (run from blockchain/):
//
//	go run ./client health
//	QFABRIC_ORG=OrgA go run ./client register
//	QFABRIC_ORG=OrgA go run ./client transfer -to OrgB -file doc.txt [-eve] [-tx qfabric-tx-001]
//	go run ./client get qfabric-tx-001
//	go run ./client list
//	go run ./client verify qfabric-tx-001
package main

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"time"

	"github.com/hyperledger/fabric-gateway/pkg/client"

	"qfabric/blockchain/integration"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	if err := run(os.Args[1], os.Args[2:]); err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: client <health|register|transfer|get|list|verify> [args]")
}

func run(cmd string, args []string) error {
	cfg, err := loadConfig()
	if err != nil {
		return err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()
	crypto := integration.NewCryptoClient(cfg.CryptoAPIURL)

	if cmd == "health" {
		h, err := crypto.Health(ctx)
		if err != nil {
			return err
		}
		return printJSON(h)
	}

	gw, conn, err := connect(cfg)
	if err != nil {
		return err
	}
	defer conn.Close()
	defer gw.Close()
	contract := gw.GetNetwork(cfg.ChannelName).GetContract(cfg.ChaincodeName)

	switch cmd {
	case "register":
		return cmdRegister(ctx, cfg, crypto, contract)
	case "transfer":
		return cmdTransfer(ctx, cfg, crypto, contract, args)
	case "get":
		return withID(args, func(id string) ([]byte, error) { return getTransaction(contract, id) })
	case "list":
		return printRaw(getAllTransactions(contract))
	case "verify":
		return withID(args, func(id string) ([]byte, error) { return verifyTransactionRecord(contract, id) })
	default:
		usage()
		return fmt.Errorf("unknown command %q", cmd)
	}
}

// cmdRegister creates (or fetches) the org's ML-DSA key in the crypto
// service, then anchors the public key on the ledger.
func cmdRegister(ctx context.Context, cfg *Config, crypto *integration.CryptoClient, contract *client.Contract) error {
	org, err := crypto.RegisterOrganization(ctx, integration.RegisterOrganizationRequest{
		OrgID: cfg.Org.OrgID, DisplayName: cfg.Org.DisplayName, MSPID: cfg.Org.MSPID, Role: cfg.Org.Role,
	})
	var apiErr *integration.APIError
	if errors.As(err, &apiErr) && apiErr.Code == "ORGANIZATION_EXISTS" {
		org, err = crypto.GetOrganization(ctx, cfg.Org.OrgID)
	}
	if err != nil {
		return err
	}
	return printRaw(registerOrganization(contract, cfg.Org, org.PublicKey))
}

func cmdTransfer(ctx context.Context, cfg *Config, crypto *integration.CryptoClient, contract *client.Contract, args []string) error {
	fs := flag.NewFlagSet("transfer", flag.ContinueOnError)
	to := fs.String("to", "OrgB", "receiver organization")
	file := fs.String("file", "", "document to send")
	eve := fs.Bool("eve", false, "simulate intercept-resend eavesdropper")
	txID := fs.String("tx", fmt.Sprintf("qfabric-tx-%d", time.Now().UnixNano()), "QFabric transaction id")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *file == "" {
		return errors.New("transfer requires -file")
	}
	doc, err := os.ReadFile(*file)
	if err != nil {
		return err
	}

	transfer, err := crypto.SecureTransfer(ctx, integration.SecureTransferRequest{
		Sender: cfg.Org.OrgID, Receiver: *to,
		Document:             base64.StdEncoding.EncodeToString(doc),
		SimulateEavesdropper: *eve,
	})
	if err != nil {
		return err
	}
	fmt.Fprintf(os.Stderr, "crypto service: session=%s bb84=%s qber=%.4f (service verdict %s; ledger will re-verify)\n",
		transfer.SessionID, transfer.BB84Status, transfer.QBER, transfer.SecurityStatus)
	return printRaw(recordSecureTransaction(contract, *txID, transfer))
}

func withID(args []string, fn func(string) ([]byte, error)) error {
	if len(args) != 1 {
		return errors.New("expected exactly one transaction id")
	}
	return printRaw(fn(args[0]))
}

func printRaw(data []byte, err error) error {
	if err != nil {
		return err
	}
	var out bytes.Buffer
	if json.Indent(&out, data, "", "  ") != nil {
		fmt.Println(string(data))
		return nil
	}
	fmt.Println(out.String())
	return nil
}

func printJSON(v any) error {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	fmt.Println(string(b))
	return nil
}
