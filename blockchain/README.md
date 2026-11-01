# QFabric: Blockchain Module

**Owner:** Developer 1 (Blockchain / Hyperledger Fabric).

This module runs a Hyperledger Fabric 2.5 network with two organizations, the `qfabric-audit` Go chaincode that **independently verifies ML-DSA-65 signatures** and records security audit events, and a Go client that bridges the Quantum/PQC service and the ledger.

## Status

| Component | Status |
|---|---|
| Network scripts (fetch pinned Fabric 2.5.16, up, channel, deploy, down) | ✅ written, not yet run end to end |
| Chaincode: data model, canonical manifest, validation, policy, ML-DSA verify (CIRCL) | ✅ unit-tested against the shared vector |
| Chaincode: `RegisterOrganization`, `GetOrganization`, `RecordSecureTransaction`, `GetTransaction`, `GetAllTransactions`, `VerifyTransactionRecord` | ⏳ stubs with step-by-step TODOs |
| Client: gateway connection, chaincode wrappers, crypto API client, CLI | ✅ compiles. Untested against a live network |
| Contract test (samples ↔ Go structs) | ✅ passing |

## Layout

```
blockchain/
├── go.mod                    module qfabric/blockchain (client + integration + tests)
├── .env.example
├── network/                  Fabric test network lives here (downloaded, git-ignored)
├── chaincode/qfabric-audit/  separate Go module, deployed to Fabric
│   ├── main.go               contractapi bootstrap
│   ├── organization.go       Organization model, RegisterOrganization, GetOrganization
│   ├── transaction.go        AuditManifest (canonical bytes, Validate, PolicyViolations), AuditRecord
│   ├── audit.go              AuditContract functions, ML-DSA-65 verification (CIRCL)
│   └── audit_test.go         vector, tamper, validation and policy tests
├── client/                   CLI: health | register | transfer | get | list | verify
│   ├── config.go             env config, OrgA/OrgB → Org1MSP/Org2MSP mapping
│   ├── gateway.go            Fabric Gateway connection (X.509 identity, TLS)
│   ├── transaction.go        chaincode call wrappers
│   └── main.go
├── integration/              crypto-service HTTP client + JSON contract structs
├── scripts/                  common.sh, start-network.sh, create-channel.sh, deploy-chaincode.sh, stop-network.sh
└── tests/integration_test.go contract test (offline) + E2E (QFABRIC_E2E=1)
```

## Organizations

| QFabric | Role | Fabric MSP | Peer |
|---|---|---|---|
| OrgA | Manufacturer | Org1MSP | peer0.org1.example.com:7051 |
| OrgB | Supplier | Org2MSP | peer0.org2.example.com:9051 |

The test network's Org1 and Org2 are reused as-is. Renaming them would require custom `configtx.yaml` and crypto config, and buys nothing for the demo.

## Quick start

```bash
cd blockchain
cp .env.example .env
go test ./...                               # contract tests
(cd chaincode/qfabric-audit && go test ./...)

./scripts/start-network.sh                  # first run downloads Fabric 2.5.16 samples, binaries, images
./scripts/deploy-chaincode.sh               # v1.0, sequence 1 (runs unit tests first)
# upgrade after changes:
./scripts/deploy-chaincode.sh 1.1 2

./scripts/stop-network.sh                   # tear down (destroys ledger)
```

### Client

```bash
go run ./client health                                          # crypto service reachable?
QFABRIC_ORG=OrgA go run ./client register                       # ML-DSA key → ledger
QFABRIC_ORG=OrgB go run ./client register
QFABRIC_ORG=OrgA go run ./client transfer -to OrgB -file ../README.md -tx qfabric-tx-001
QFABRIC_ORG=OrgA go run ./client transfer -to OrgB -file ../README.md -eve -tx qfabric-tx-002
go run ./client list
go run ./client verify qfabric-tx-001
```

### Testing the chaincode without the crypto service

Use the shared vector `integration/test_vectors/mldsa65_audit_manifest.json`. It contains an ML-DSA-65 public key, a manifest and a valid signature. With the network up and the chaincode implemented:

```bash
cd network/fabric-samples/test-network
export PATH=$PWD/../bin:$PATH FABRIC_CFG_PATH=$PWD/../config
source scripts/envVar.sh && setGlobals 1        # act as Org1 (OrgA)
V=../../../../integration/test_vectors/mldsa65_audit_manifest.json
PK=$(jq -r .publicKey $V); MANIFEST=$(jq -c .manifest $V); SIG=$(jq -r .signature $V)
ORDERER="-o localhost:7050 --ordererTLSHostnameOverride orderer.example.com --tls --cafile $ORDERER_CA"
PEERS="--peerAddresses localhost:7051 --tlsRootCertFiles $PEER0_ORG1_CA --peerAddresses localhost:9051 --tlsRootCertFiles $PEER0_ORG2_CA"

peer chaincode invoke $ORDERER -C mychannel -n qfabric-audit $PEERS \
  -c "$(jq -nc --arg pk "$PK" '{function:"RegisterOrganization",Args:["OrgA","Manufacturer","MANUFACTURER",$pk]}')"
peer chaincode invoke $ORDERER -C mychannel -n qfabric-audit $PEERS \
  -c "$(jq -nc --arg m "$MANIFEST" --arg s "$SIG" '{function:"RecordSecureTransaction",Args:["qfabric-tx-001",$m,$s]}')"
peer chaincode query -C mychannel -n qfabric-audit -c '{"function":"GetAllTransactions","Args":[]}'
```

## Security rules the chaincode enforces

Full list: [docs/API_CONTRACT.md §5](../docs/API_CONTRACT.md#5-ledger-policy-chaincode-qfabric-audit).

- Verify ML-DSA-65 over the canonical manifest against the **ledger-registered** key. Never trust `mldsaVerified` or `securityStatus` from the service.
- The submitter's MSP must equal the sender org's MSP. MSP IDs come from the caller certificate, never from arguments.
- Replay guard: one record per `sessionId` and per `transactionId`.
- Deterministic: timestamps from `GetTxTimestamp()`, never `time.Now()`. No randomness, no map-iteration-order-dependent output.
- Store hashes and metadata only: no plaintext, no ciphertext, no private keys, no BB84 secrets.

## Toolchain notes

- The chaincode `go.mod` targets **Go 1.25** and pins `fabric-contract-api-go v2.2.2`, because newer releases require a Go version newer than the one in `fabric-ccenv:2.5`. Check before bumping: `docker run --rm hyperledger/fabric-ccenv:2.5 go version`.
- `deploy-chaincode.sh` uses the test network's `deployCC`, which runs `go mod vendor` in the chaincode directory. `vendor/` is git-ignored.
- On Apple Silicon, Fabric 2.5 publishes arm64 images, so no emulation is needed.
