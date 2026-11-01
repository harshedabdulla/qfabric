# Integration Guide

How the Quantum/PQC module (Dev 2) and the Blockchain module (Dev 1) connect, and how each developer can work **without waiting for the other**.

## 1. The seam

There is exactly one runtime seam: **HTTP/JSON `/api/v1`**, specified in [API_CONTRACT.md](API_CONTRACT.md). Neither module imports the other's code.

The security-critical part of the seam is the **canonical audit manifest** (§4 of the contract). It is implemented twice, independently:

- Python: `quantum-pqc/mldsa/manifest.py` (`canonical_manifest`)
- Go: `blockchain/chaincode/qfabric-audit/transaction.go` (`CanonicalBytes`)

The shared test vector `integration/test_vectors/mldsa65_audit_manifest.json` keeps the two implementations identical.

## 2. Working independently (Phase 2)

### Blockchain developer: no crypto service needed

- **Chaincode unit tests** use the test vector: a real ML-DSA-65 public key, manifest and signature. Register that public key for `OrgA` in your mock ledger, feed the manifest and signature to `RecordSecureTransaction`, and expect `VERIFIED`. Mutate any field and expect an error.
- **More signed manifests** (for example an aborted one): generate them in Go tests with `mldsa65.GenerateKey` + `mldsa65.SignTo(sk, m.CanonicalBytes(), nil, false, sig)`.
- **Client contract test**: `go test ./tests/...` strict-decodes the sample JSON into the Go structs.
- **On a live network** before the API exists: `peer chaincode invoke` with the vector's values (see `blockchain/README.md`).

### Quantum/PQC developer: no Fabric needed

- `pytest` covers BB84, ML-DSA, encryption and the API. Stubs are reported as *skipped* until implemented.
- `test_canonical_manifest_matches_go_chaincode` and `test_vector_signature_verifies_with_liboqs` prove compatibility with the chaincode without running it.
- The service must reproduce `sample_response.json`'s **shape** (values differ per run). `test_sample_response_matches_schema` guards this.

## 3. Integration steps (Phase 3)

| Step | Owner | Done when |
|---|---|---|
| 1. Sign off contract v1 | both | `integration/API_CONTRACT.md` table signed |
| 2. Interop gate | Dev 2 | `pytest -k "vector or canonical"` passes with liboqs installed |
| 3. Service up in Docker | Dev 2 | `docker compose up --build -d crypto` and `go run ./client health` returns `ok` |
| 4. Chaincode deployed | Dev 1 | `./scripts/deploy-chaincode.sh` succeeds, `GetAllTransactions` returns `[]` |
| 5. Register orgs | Dev 1 | `QFABRIC_ORG=OrgA go run ./client register` (then OrgB) |
| 6. Honest transfer | both | `client transfer -file doc.txt` gives a `VERIFIED` record |
| 7. Eavesdropped transfer | both | `client transfer -file doc.txt -eve` gives a `REJECTED` record with reasons |
| 8. Negative tests | Dev 1 | Tampered manifest, wrong org, replayed session are all refused by the chaincode |
| 9. Full demo | both | `./scripts/run-demo.sh` runs clean |

## 4. Debugging mismatches

| Symptom | Likely cause |
|---|---|
| Chaincode `ML-DSA-65 signature verification failed` on a fresh manifest | Canonical bytes differ. Diff Python `canonical_manifest(...)` against Go `CanonicalBytes()` for the same JSON. Check float→ppm rounding, field order and trailing newline |
| Signature verifies in Python but not Go | Non-empty context string, or HashML-DSA (pre-hash) mode used. Both sides must use pure ML-DSA-65 with an empty context |
| `senderKeyId` mismatch | The org was re-registered in the service (new key) but the ledger still holds the old key. Re-registration on the ledger is refused by design, so restart the network or implement key rotation |
| Go contract test: `unknown field` | The service added a field. Update `metadata.go` and the samples in the same PR |
| `submitter MSP` error | `QFABRIC_ORG` doesn't match the manifest sender. Run the client as the sender org |
| liboqs warning about version mismatch | The liboqs C library differs from liboqs-python 0.16.x. Install liboqs 0.16.0 or use Docker |

## 5. Change management

Any change to `quantum-pqc/api/schemas.py`, `blockchain/integration/metadata.go`, the manifest format or the ledger policy:

1. Open an issue or PR tagged `contract-change` and describe the change.
2. Update `docs/API_CONTRACT.md`, both code mirrors, `integration/*.json`, and the test vector if the manifest changed.
3. Get approval from **both** developers.
4. Bump the version row in `integration/API_CONTRACT.md`.
