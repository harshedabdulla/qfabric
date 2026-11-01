package main

import (
	"crypto/x509"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/hyperledger/fabric-gateway/pkg/client"
	"github.com/hyperledger/fabric-gateway/pkg/hash"
	"github.com/hyperledger/fabric-gateway/pkg/identity"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
)

// connect opens a Fabric Gateway connection as the org's User1 identity.
// This is Fabric MSP (X.509 / ECDSA) authentication: it proves which
// Fabric member submits a transaction. ML-DSA authentication of the
// transfer itself happens inside the chaincode.
func connect(cfg *Config) (*client.Gateway, *grpc.ClientConn, error) {
	conn, err := newGrpcConnection(cfg)
	if err != nil {
		return nil, nil, err
	}
	id, err := newIdentity(cfg)
	if err != nil {
		conn.Close()
		return nil, nil, err
	}
	sign, err := newSign(cfg)
	if err != nil {
		conn.Close()
		return nil, nil, err
	}

	gw, err := client.Connect(
		id,
		client.WithSign(sign),
		client.WithHash(hash.SHA256),
		client.WithClientConnection(conn),
		client.WithEvaluateTimeout(5*time.Second),
		client.WithEndorseTimeout(15*time.Second),
		client.WithSubmitTimeout(5*time.Second),
		client.WithCommitStatusTimeout(1*time.Minute),
	)
	if err != nil {
		conn.Close()
		return nil, nil, err
	}
	return gw, conn, nil
}

func newGrpcConnection(cfg *Config) (*grpc.ClientConn, error) {
	pem, err := os.ReadFile(cfg.tlsCertPath())
	if err != nil {
		return nil, fmt.Errorf("read peer TLS CA (is the test network up?): %w", err)
	}
	cert, err := identity.CertificateFromPEM(pem)
	if err != nil {
		return nil, err
	}
	pool := x509.NewCertPool()
	pool.AddCert(cert)
	creds := credentials.NewClientTLSFromCert(pool, cfg.Org.GatewayPeer)
	return grpc.NewClient(cfg.Org.PeerEndpoint, grpc.WithTransportCredentials(creds))
}

func newIdentity(cfg *Config) (*identity.X509Identity, error) {
	pem, err := readFirstFile(cfg.certDir())
	if err != nil {
		return nil, fmt.Errorf("read user certificate: %w", err)
	}
	cert, err := identity.CertificateFromPEM(pem)
	if err != nil {
		return nil, err
	}
	return identity.NewX509Identity(cfg.Org.MSPID, cert)
}

func newSign(cfg *Config) (identity.Sign, error) {
	pem, err := readFirstFile(cfg.keyDir())
	if err != nil {
		return nil, fmt.Errorf("read user private key: %w", err)
	}
	key, err := identity.PrivateKeyFromPEM(pem)
	if err != nil {
		return nil, err
	}
	return identity.NewPrivateKeySign(key)
}

// readFirstFile reads the single file in an MSP directory (file names
// differ between cryptogen and Fabric CA enrollment).
func readFirstFile(dir string) ([]byte, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	for _, e := range entries {
		if !e.IsDir() {
			return os.ReadFile(filepath.Join(dir, e.Name()))
		}
	}
	return nil, fmt.Errorf("no file in %s", dir)
}
