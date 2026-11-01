# Integration Contract: Quick Reference and Sign-off

The full specification is in [`docs/API_CONTRACT.md`](../docs/API_CONTRACT.md). This file is the one-page summary both developers check against while integrating, plus the sign-off record. Spec details are deliberately not duplicated here, so the two documents cannot drift apart.

## Files in this directory

| File | Purpose | Verified by |
|---|---|---|
| `sample_request.json` | Example `POST /api/v1/secure-transfer` body | `quantum-pqc/tests/test_integration.py`, `blockchain/tests/integration_test.go` |
| `sample_response.json` | Example response with a **real** ML-DSA-65 signature | same as above |
| `test_vectors/mldsa65_audit_manifest.json` | Cross-language ML-DSA-65 vector (CIRCL key + signature, canonical manifest) | `blockchain/chaincode/qfabric-audit/audit_test.go`, `quantum-pqc/tests/test_mldsa.py` |

The vector key is **test-only**. Its seed derivation is published in the file on purpose, for reproducibility.

## Endpoints

| Method | Path | Used by blockchain client |
|---|---|---|
| GET | `/api/v1/health` | yes (`client health`) |
| POST | `/api/v1/organizations/register` | yes (`client register`) |
| GET | `/api/v1/organizations/{orgId}` | yes (when the org already exists) |
| POST | `/api/v1/mldsa/sign` | no (demo/diagnostics) |
| POST | `/api/v1/mldsa/verify` | no (demo/diagnostics) |
| POST | `/api/v1/bb84/execute` | no (crypto demos) |
| POST | `/api/v1/bb84/simulate-attack` | no (crypto demos) |
| POST | `/api/v1/encryption/encrypt` | no |
| POST | `/api/v1/encryption/decrypt` | no |
| POST | `/api/v1/secure-transfer` | **yes (`client transfer`)** |

## The data path to the ledger

```
crypto service                      blockchain client                     chaincode
--------------                      -----------------                     ---------
POST /secure-transfer  ──────────►  response.auditManifest  ──json──►  RecordSecureTransaction(
                                    response.signature.value ─b64──►      transactionId,
                                                                          manifestJSON,
                                    (mldsaVerified, securityStatus        signatureB64)
                                     are NOT forwarded)                  - rebuilds canonical bytes
                                                                         - verifies ML-DSA-65 with the
                                                                           ledger-registered key
                                                                         - applies policy → VERIFIED/REJECTED
```

## Agreement checklist

Tick each item together before starting Phase 3 (integration):

- [ ] Field names, types and enums in `docs/API_CONTRACT.md` §3 agreed
- [ ] Canonical manifest format §4 agreed (line format, field order, ppm integers)
- [ ] ML-DSA-65 pure mode, empty context agreed. Python verifies the CIRCL vector with liboqs (`test_vector_signature_verifies_with_liboqs` passes)
- [ ] Ledger policy §5 agreed (QBER max 11%, ≥256-bit final key, rejection reasons)
- [ ] Error envelope and codes §2 agreed
- [ ] Org mapping OrgA→Org1MSP, OrgB→Org2MSP agreed

## Sign-off

| Version | Date | Blockchain (Dev 1) | Quantum/PQC (Dev 2) | Notes |
|---|---|---|---|---|
| v1.0 | | ☐ | ☐ | Initial contract |
