// Command qfabric-audit is the QFabric security-audit chaincode for
// Hyperledger Fabric 2.5.
//
// It records tamper-evident audit records for secure document transfers
// between organizations. Every record is backed by an application-level
// ML-DSA-65 (FIPS 204) signature that the chaincode verifies itself against
// the sender's registered public key. It never trusts a "verified" boolean
// supplied by the client or by the Quantum/PQC service.
//
// See docs/API_CONTRACT.md §4 (canonical audit manifest) and
// docs/SECURITY_MODEL.md for the rules this chaincode enforces.
package main

import (
	"log"

	"github.com/hyperledger/fabric-contract-api-go/v2/contractapi"
)

func main() {
	chaincode, err := contractapi.NewChaincode(&AuditContract{})
	if err != nil {
		log.Panicf("error creating qfabric-audit chaincode: %v", err)
	}
	chaincode.Info.Title = "qfabric-audit"
	chaincode.Info.Version = "0.1.0"

	if err := chaincode.Start(); err != nil {
		log.Panicf("error starting qfabric-audit chaincode: %v", err)
	}
}
