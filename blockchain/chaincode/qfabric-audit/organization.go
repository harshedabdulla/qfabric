package main

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"
	"unicode"

	"github.com/hyperledger/fabric-contract-api-go/v2/contractapi"
)

// Organization roles used by the demo network.
const (
	RoleManufacturer = "MANUFACTURER" // OrgA, Fabric Org1MSP
	RoleSupplier     = "SUPPLIER"     // OrgB, Fabric Org2MSP
)

// Organization binds a QFabric organization to its Fabric MSP identity and
// its trusted ML-DSA-65 public key.
//
// Two separate authentication layers meet here:
//   - MSPID: Fabric membership (X.509 / ECDSA). Proves who submitted a
//     Fabric transaction. Classical and not quantum-safe.
//   - PublicKey: application-level ML-DSA-65 key. Proves who signed the
//     audit manifest. Post-quantum.
type Organization struct {
	DocType      string `json:"docType"` // always "organization"
	OrgID        string `json:"orgId"`
	DisplayName  string `json:"displayName"`
	Role         string `json:"role"`
	MSPID        string `json:"mspId"`     // taken from the caller identity, never from arguments
	Algorithm    string `json:"algorithm"` // "ML-DSA-65"
	PublicKey    string `json:"publicKey"` // base64, 1952 bytes raw
	PublicKeyID  string `json:"publicKeyId"`
	RegisteredBy string `json:"registeredBy"` // Fabric client identity ID
	RegisteredAt string `json:"registeredAt"` // transaction timestamp
}

// PublicKeyID is the trusted fingerprint of an ML-DSA public key:
// lowercase hex SHA-256 of the raw public-key bytes.
func PublicKeyID(rawPublicKey []byte) string {
	sum := sha256.Sum256(rawPublicKey)
	return hex.EncodeToString(sum[:])
}

// RegisterOrganization anchors an organization's ML-DSA-65 public key on the
// ledger. The caller's Fabric MSP becomes the organization's MSP, so an org
// can only register itself. Each MSP may register exactly one organization
// and registrations are immutable (no silent key replacement).
func (c *AuditContract) RegisterOrganization(
	ctx contractapi.TransactionContextInterface,
	orgID, displayName, role, publicKeyB64 string,
) (*Organization, error) {
	if !reOrgID.MatchString(orgID) {
		return nil, fmt.Errorf("invalid orgId %q", orgID)
	}
	if err := validateDisplayName(displayName); err != nil {
		return nil, err
	}
	if role != RoleManufacturer && role != RoleSupplier {
		return nil, fmt.Errorf("invalid role %q (want %s or %s)", role, RoleManufacturer, RoleSupplier)
	}

	rawKey, err := base64.StdEncoding.DecodeString(publicKeyB64)
	if err != nil {
		return nil, fmt.Errorf("publicKey must be standard base64: %w", err)
	}
	if _, err := parseMLDSA65PublicKey(rawKey); err != nil {
		return nil, err
	}

	identity := ctx.GetClientIdentity()
	mspID, err := identity.GetMSPID()
	if err != nil {
		return nil, fmt.Errorf("read caller MSP: %w", err)
	}
	clientID, err := identity.GetID()
	if err != nil {
		return nil, fmt.Errorf("read caller identity: %w", err)
	}

	stub := ctx.GetStub()
	key, err := stub.CreateCompositeKey(keyOrganization, []string{orgID})
	if err != nil {
		return nil, err
	}
	if exists, err := stateExists(ctx, key); err != nil {
		return nil, err
	} else if exists {
		return nil, fmt.Errorf("organization %s is already registered", orgID)
	}
	mspKey, err := stub.CreateCompositeKey(keyMSP, []string{mspID})
	if err != nil {
		return nil, err
	}
	if existing, err := stub.GetState(mspKey); err != nil {
		return nil, err
	} else if existing != nil {
		return nil, fmt.Errorf("MSP %s already registered organization %s", mspID, existing)
	}

	registeredAt, err := txTimestamp(ctx)
	if err != nil {
		return nil, err
	}
	org := &Organization{
		DocType:      "organization",
		OrgID:        orgID,
		DisplayName:  displayName,
		Role:         role,
		MSPID:        mspID,
		Algorithm:    SignatureAlgorithm,
		PublicKey:    publicKeyB64,
		PublicKeyID:  PublicKeyID(rawKey),
		RegisteredBy: clientID,
		RegisteredAt: registeredAt,
	}
	if err := putJSON(ctx, key, org); err != nil {
		return nil, err
	}
	if err := stub.PutState(mspKey, []byte(orgID)); err != nil {
		return nil, err
	}
	event, _ := json.Marshal(map[string]string{"orgId": orgID, "mspId": mspID, "publicKeyId": org.PublicKeyID})
	if err := stub.SetEvent("OrganizationRegistered", event); err != nil {
		return nil, err
	}
	return org, nil
}

// GetOrganization returns a registered organization.
func (c *AuditContract) GetOrganization(
	ctx contractapi.TransactionContextInterface,
	orgID string,
) (*Organization, error) {
	if !reOrgID.MatchString(orgID) {
		return nil, fmt.Errorf("invalid orgId %q", orgID)
	}
	key, err := ctx.GetStub().CreateCompositeKey(keyOrganization, []string{orgID})
	if err != nil {
		return nil, err
	}
	var org Organization
	found, err := getJSON(ctx, key, &org)
	if err != nil {
		return nil, err
	}
	if !found {
		return nil, fmt.Errorf("organization %s is not registered", orgID)
	}
	return &org, nil
}

func validateDisplayName(name string) error {
	if strings.TrimSpace(name) == "" || len(name) > 128 {
		return fmt.Errorf("displayName must be 1-128 characters")
	}
	for _, r := range name {
		if unicode.IsControl(r) {
			return fmt.Errorf("displayName must not contain control characters")
		}
	}
	return nil
}
