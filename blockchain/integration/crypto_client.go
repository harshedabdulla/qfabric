package integration

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// CryptoClient talks to the Quantum/PQC FastAPI service.
type CryptoClient struct {
	BaseURL string // e.g. http://localhost:8000/api/v1
	HTTP    *http.Client
}

// NewCryptoClient returns a client with a timeout long enough for BB84
// simulation of a few thousand qubits.
func NewCryptoClient(baseURL string) *CryptoClient {
	return &CryptoClient{
		BaseURL: strings.TrimRight(baseURL, "/"),
		HTTP:    &http.Client{Timeout: 120 * time.Second},
	}
}

func (c *CryptoClient) Health(ctx context.Context) (*HealthResponse, error) {
	var out HealthResponse
	return &out, c.do(ctx, http.MethodGet, "/health", nil, &out)
}

func (c *CryptoClient) RegisterOrganization(ctx context.Context, req RegisterOrganizationRequest) (*Organization, error) {
	var out Organization
	return &out, c.do(ctx, http.MethodPost, "/organizations/register", req, &out)
}

func (c *CryptoClient) GetOrganization(ctx context.Context, orgID string) (*Organization, error) {
	var out Organization
	return &out, c.do(ctx, http.MethodGet, "/organizations/"+orgID, nil, &out)
}

func (c *CryptoClient) SecureTransfer(ctx context.Context, req SecureTransferRequest) (*SecureTransferResponse, error) {
	var out SecureTransferResponse
	return &out, c.do(ctx, http.MethodPost, "/secure-transfer", req, &out)
}

func (c *CryptoClient) do(ctx context.Context, method, path string, body, out any) error {
	var reader io.Reader
	if body != nil {
		buf, err := json.Marshal(body)
		if err != nil {
			return err
		}
		reader = bytes.NewReader(buf)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.BaseURL+path, reader)
	if err != nil {
		return err
	}
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.HTTP.Do(req)
	if err != nil {
		return fmt.Errorf("crypto API %s %s: %w", method, path, err)
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 64<<20))
	if err != nil {
		return err
	}

	if resp.StatusCode >= 300 {
		var envelope struct {
			Error APIError `json:"error"`
		}
		if json.Unmarshal(raw, &envelope) != nil || envelope.Error.Code == "" {
			return &APIError{HTTPStatus: resp.StatusCode, Code: "HTTP_" + fmt.Sprint(resp.StatusCode), Message: resp.Status}
		}
		envelope.Error.HTTPStatus = resp.StatusCode
		return &envelope.Error
	}
	return json.Unmarshal(raw, out)
}
