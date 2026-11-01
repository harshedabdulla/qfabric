package main

import (
	"crypto/sha256"
	"encoding/hex"

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

// RegisterOrganization stores an organization's ML-DSA-65 public key.
//
// TODO(blockchain):
//  1. Validate orgID (reOrgID), displayName (non-empty, bounded), role.
//  2. mspID := ctx.GetClientIdentity().GetMSPID(); an org may only register
//     itself, so mspID comes from the caller, not from an argument.
//  3. Decode publicKeyB64; require len == mldsa65.PublicKeySize and that it
//     unmarshals (see parseMLDSA65PublicKey in audit.go).
//  4. Refuse if the orgID key already exists (no silent key replacement).
//  5. RegisteredAt from ctx.GetStub().GetTxTimestamp() (never time.Now()).
//  6. PutState(orgKey(orgID), json) and emit event "OrganizationRegistered".
func (c *AuditContract) RegisterOrganization(
	ctx contractapi.TransactionContextInterface,
	orgID, displayName, role, publicKeyB64 string,
) (*Organization, error) {
	return nil, errNotImplemented
}

// GetOrganization returns a registered organization.
//
// TODO(blockchain): GetState(orgKey(orgID)); error if missing; unmarshal.
func (c *AuditContract) GetOrganization(
	ctx contractapi.TransactionContextInterface,
	orgID string,
) (*Organization, error) {
	return nil, errNotImplemented
}
