package main

import (
	"encoding/json"
	"fmt"

	"github.com/hyperledger/fabric-gateway/pkg/client"

	"qfabric/blockchain/integration"
)

// Thin wrappers over the qfabric-audit chaincode functions. Results are
// returned as raw JSON so the CLI can print exactly what the ledger holds.

func registerOrganization(contract *client.Contract, profile OrgProfile, publicKeyB64 string) ([]byte, error) {
	return submit(contract, "RegisterOrganization", profile.OrgID, profile.DisplayName, profile.Role, publicKeyB64)
}

func getOrganization(contract *client.Contract, orgID string) ([]byte, error) {
	return contract.EvaluateTransaction("GetOrganization", orgID)
}

// recordSecureTransaction submits only the signed manifest and signature.
// The service's mldsaVerified / securityStatus are deliberately not sent.
func recordSecureTransaction(contract *client.Contract, transactionID string, transfer *integration.SecureTransferResponse) ([]byte, error) {
	manifest, err := json.Marshal(transfer.AuditManifest)
	if err != nil {
		return nil, err
	}
	return submit(contract, "RecordSecureTransaction", transactionID, string(manifest), transfer.Signature.Value)
}

func getTransaction(contract *client.Contract, transactionID string) ([]byte, error) {
	return contract.EvaluateTransaction("GetTransaction", transactionID)
}

func getAllTransactions(contract *client.Contract) ([]byte, error) {
	return contract.EvaluateTransaction("GetAllTransactions")
}

func verifyTransactionRecord(contract *client.Contract, transactionID string) ([]byte, error) {
	return contract.EvaluateTransaction("VerifyTransactionRecord", transactionID)
}

func submit(contract *client.Contract, fn string, args ...string) ([]byte, error) {
	result, err := contract.SubmitTransaction(fn, args...)
	if err != nil {
		return nil, fmt.Errorf("%s: %w", fn, describeGatewayError(err))
	}
	return result, nil
}

// describeGatewayError surfaces chaincode error messages from endorsement
// failures, which the Gateway otherwise wraps in gRPC status details.
func describeGatewayError(err error) error {
	if endorseErr, ok := err.(*client.EndorseError); ok {
		return fmt.Errorf("endorse failed for tx %s: %w", endorseErr.TransactionID, endorseErr)
	}
	return err
}
