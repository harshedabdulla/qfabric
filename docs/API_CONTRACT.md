# QFabric API Contract (v1)

**Status:** draft v1.0, needs sign-off from both developers (see [integration/API_CONTRACT.md](../integration/API_CONTRACT.md)).
**Provider:** Quantum/PQC service (`quantum-pqc/`, FastAPI).
**Consumers:** Blockchain client (`blockchain/client`, `blockchain/integration`) and the `qfabric-audit` chaincode (via the signed audit manifest).

This document is the source of truth. The executable versions are:

| Artifact | Location |
|---|---|
| Pydantic schemas | `quantum-pqc/api/schemas.py` |
| Go mirrors | `blockchain/integration/metadata.go` |
| Canonical manifest (Go) | `blockchain/chaincode/qfabric-audit/transaction.go`, `CanonicalBytes` |
| Canonical manifest (Python) | `quantum-pqc/mldsa/manifest.py` |
| Sample request/response | `integration/sample_request.json`, `integration/sample_response.json` |
| ML-DSA-65 interop vector | `integration/test_vectors/mldsa65_audit_manifest.json` |

Contract tests on both sides decode the samples strictly (unknown fields are errors), so drift breaks the build.

---

## 1. Conventions

| Topic | Rule |
|---|---|
| Base URL | `http://localhost:8000/api/v1` |
| Content type | `application/json; charset=utf-8` |
| Field names | camelCase |
| Unknown request fields | rejected with `422 VALIDATION_ERROR` |
| Binary data | standard base64 with padding (RFC 4648 §4) |
| Hashes | SHA-256, lowercase hex, 64 characters |
| Timestamps | UTC, second precision, `YYYY-MM-DDTHH:MM:SSZ` |
| Organization IDs | `^[A-Za-z0-9_-]{1,64}$` (demo uses `OrgA`, `OrgB`) |
| Session / transaction IDs | `^[A-Za-z0-9._:-]{1,128}$` |
| Rates | floats in `[0, 1]` in the API; integer parts-per-million (`*Ppm`) inside the signed manifest |
| Secrets | **No endpoint ever returns or logs** a BB84 shared secret, an AES key or an ML-DSA secret key |

### Organization mapping (Fabric test network)

| QFabric org | Role | Fabric MSP | Peer |
|---|---|---|---|
| `OrgA` | `MANUFACTURER` | `Org1MSP` | `peer0.org1.example.com:7051` |
| `OrgB` | `SUPPLIER` | `Org2MSP` | `peer0.org2.example.com:9051` |

### Cryptographic parameters

| Item | Value |
|---|---|
| Signature | ML-DSA-65 (FIPS 204), **pure mode, empty context string**. Public key 1952 B, signature 3309 B |
| Key fingerprint (`publicKeyId`) | `sha256(rawPublicKey)` hex |
| KDF | HKDF-SHA-256, IKM = BB84 secret, salt = UTF-8 `sessionId`, info = `qfabric/v1/aes-256-gcm|<sender>|<receiver>`, L = 32 |
| AEAD | AES-256-GCM, 12-byte random nonce, 16-byte tag appended to ciphertext |
| AAD | `qfabric/v1|<sessionId>|<sender>|<receiver>` |
| `documentHash` | `sha256(original plaintext)` |
| `encryptedDocumentHash` | `sha256(nonce || ciphertext)` |
| `transcriptHash` | `sha256(canonical BB84 classical transcript)` |
| QBER abort threshold | default 0.11, maximum 0.11 |

---

## 2. Errors

Every non-2xx response uses one envelope:

```json
{
  "error": {
    "code": "ORGANIZATION_NOT_FOUND",
    "message": "unknown organization OrgC",
    "details": {}
  }
}
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `BAD_REQUEST` | Semantically invalid request that passed schema validation |
| 404 | `ORGANIZATION_NOT_FOUND` | Org not registered |
| 404 | `SESSION_NOT_FOUND` | Unknown `sessionId` |
| 409 | `ORGANIZATION_EXISTS` | Registering an existing org (fetch it with `GET /organizations/{orgId}`) |
| 409 | `SESSION_NOT_ESTABLISHED` | Encrypting/decrypting with an `ABORTED` BB84 session |
| 413 | `DOCUMENT_TOO_LARGE` | Document exceeds `QFABRIC_MAX_DOCUMENT_BYTES` |
| 422 | `VALIDATION_ERROR` | Schema validation failed. `details.fields` lists locations and messages, never input values |
| 422 | `DECRYPTION_FAILED` | AES-GCM authentication failed (tampering, wrong session, wrong AAD) |
| 500 | `INTERNAL_ERROR` | Unexpected failure. Details go to the server log only |
| 501 | `NOT_IMPLEMENTED` | Endpoint scaffolded but not built yet |

**A detected eavesdropper is not an error.** BB84 `ABORTED` returns `200` with `status`/`bb84Status = "ABORTED"`. It is a valid security outcome and gets audited on the ledger as `REJECTED`.

---

## 3. Endpoints

### 3.1 `GET /health`

```json
{
  "status": "ok",
  "service": "qfabric-quantum-pqc",
  "version": "0.1.0",
  "components": { "qiskit": "available", "qiskitAer": "available", "liboqs": "available" }
}
```

`status` is `degraded` when any component is unavailable.

### 3.2 `POST /organizations/register` → `201`

Generates an ML-DSA-65 key pair for the org. The secret key stays in the service key store.

Request:
```json
{ "orgId": "OrgA", "displayName": "Manufacturer", "mspId": "Org1MSP", "role": "MANUFACTURER" }
```

Response (`OrganizationResponse`):
```json
{
  "orgId": "OrgA",
  "displayName": "Manufacturer",
  "mspId": "Org1MSP",
  "role": "MANUFACTURER",
  "algorithm": "ML-DSA-65",
  "publicKey": "<base64, 1952 bytes>",
  "publicKeyId": "9f52c938...b49f",
  "createdAt": "2026-11-01T09:55:00Z"
}
```

The blockchain client then anchors `publicKey` on the ledger with `RegisterOrganization`. **From then on, the ledger's copy is the trusted key**, not the service's.

### 3.3 `GET /organizations/{orgId}` → `200`

Returns the same `OrganizationResponse`. `404 ORGANIZATION_NOT_FOUND` if unknown.

### 3.4 `POST /mldsa/sign`

Demo and diagnostics endpoint: it signs arbitrary bytes with an org's key, so it acts as a signing oracle. Disable it outside local demos.

Request: `{ "orgId": "OrgA", "message": "<base64>" }`

Response: `{ "orgId", "algorithm": "ML-DSA-65", "publicKeyId", "messageHash", "signature": "<base64, 3309 bytes>" }`

### 3.5 `POST /mldsa/verify`

Request: `{ "message", "signature", "publicKey" }` **or** `{ "message", "signature", "orgId" }` (exactly one key source).

Response: `{ "valid": true, "algorithm": "ML-DSA-65", "publicKeyId": "..." }`. An invalid signature returns `200` with `valid: false`.

### 3.6 `POST /bb84/execute`

Request (`BB84ExecuteRequest`, all optional except parties):

| Field | Type | Default | Range |
|---|---|---|---|
| `sender`, `receiver` | OrgId | (required) | must differ, both registered |
| `numQubits` | int | 2048 | 256–16384 |
| `sampleFraction` | float | 0.25 | 0.05–0.5 (sifted bits disclosed for QBER) |
| `qberThreshold` | float | 0.11 | (0, 0.11] |
| `channelErrorRate` | float | 0.0 | 0–0.25 (simulated physical noise) |
| `eavesdropper` | bool | false | |
| `interceptionRate` | float | 1.0 | 0–1 (used when `eavesdropper` is true) |
| `seed` | int or null | null | reproducible simulator/RNG |

Response (`BB84Response`):
```json
{
  "sessionId": "qfabric-session-001",
  "sender": "OrgA",
  "receiver": "OrgB",
  "status": "SUCCESS",
  "abortReason": null,
  "numQubits": 2048,
  "siftedKeyLength": 1024,
  "sampleSize": 256,
  "qber": 0.0195,
  "qberThreshold": 0.11,
  "errorCorrection": { "method": "cascade", "bitsLeaked": 131 },
  "finalKeyLength": 256,
  "keyConfirmed": true,
  "transcriptHash": "0b4335...ed1e",
  "transcriptAuthenticated": true,
  "eavesdropperEnabled": false,
  "interceptionRate": 0.0,
  "expectedQberFromAttack": null,
  "backend": "aer_simulator",
  "durationMs": 840.2
}
```

`abortReason` ∈ `QBER_THRESHOLD_EXCEEDED`, `KEY_CONFIRMATION_FAILED`, `INSUFFICIENT_KEY_MATERIAL`. On abort, `finalKeyLength` = 0 and no key is stored.

### 3.7 `POST /bb84/simulate-attack`

Same as `/bb84/execute` with the intercept-resend eavesdropper forced on. The request has no `eavesdropper` field. The response sets `expectedQberFromAttack = 0.25 × interceptionRate`.

### 3.8 `POST /encryption/encrypt`

Request: `{ "sessionId", "document": "<base64>", "compression": "zstd" | "gzip" | "none" }`

Response (`EncryptResponse`):
```json
{
  "sessionId": "qfabric-session-001",
  "algorithm": "AES-256-GCM",
  "compression": "zstd",
  "nonce": "<base64, 12 bytes>",
  "ciphertext": "<base64, includes 16-byte tag>",
  "originalSize": 156,
  "compressedSize": 146,
  "compressionRatio": 1.0685,
  "documentHash": "485e3d...de24",
  "encryptedDocumentHash": "2b2849...7836"
}
```

The session must be `SUCCESS`, otherwise `409 SESSION_NOT_ESTABLISHED`.

### 3.9 `POST /encryption/decrypt`

Request: `{ "sessionId", "nonce", "ciphertext", "compression", "expectedDocumentHash"? }`

Response: `{ "sessionId", "document": "<base64>", "documentHash", "integrityVerified": true, "hashMatched": true | null }`

A tag failure returns `422 DECRYPTION_FAILED`, which is the tamper-detection outcome.

### 3.10 `POST /secure-transfer` (the blockchain client calls this)

Runs the whole flow: BB84 → (on success) HKDF → compress → AES-256-GCM → receiver-side decrypt check → signed audit manifest.

Request (`SecureTransferRequest`): see [`integration/sample_request.json`](../integration/sample_request.json).

| Field | Type | Default |
|---|---|---|
| `sender`, `receiver` | OrgId | (required) |
| `document` | base64 | (required) |
| `filename` | string or null | null (not hashed or signed; logging only) |
| `compression` | enum | `zstd` |
| `numQubits`, `sampleFraction`, `channelErrorRate`, `seed` | as in 3.6 | |
| `simulateEavesdropper` | bool | false |
| `interceptionRate` | float | 1.0 |
| `includeCiphertext` | bool | false (set true to get `encryptedPayload` back) |

Response (`SecureTransferResponse`): see [`integration/sample_response.json`](../integration/sample_response.json).

| Field | Meaning |
|---|---|
| `sessionId`, `sender`, `receiver` | Session identity |
| `mldsaVerified` | The service verified its own signature. **Informational. The ledger ignores it.** |
| `bb84Status`, `abortReason`, `qber`, `qberThreshold` | BB84 outcome |
| `encryptionAlgorithm` | `AES-256-GCM`, or `NONE` when BB84 aborted |
| `compression`, `originalSize`, `compressedSize`, `compressionRatio` | Compression stats (`null` sizes when aborted) |
| `documentHash`, `encryptedDocumentHash`, `transcriptHash` | Hashes (`encryptedDocumentHash` null when aborted) |
| `securityStatus` | Service-side verdict using the ledger policy (§5). **Informational.** |
| `timestamp` | Manifest creation time |
| `auditManifest` | **The signed fields** (§4). Submitted to the chaincode |
| `signature` | `{ algorithm, signer, publicKeyId, value }`. `value` is submitted to the chaincode |
| `encryptedPayload` | `{ nonce, ciphertext }` only when `includeCiphertext` is true |

What gets submitted to the chaincode: `RecordSecureTransaction(transactionId, json(auditManifest), signature.value)`. Nothing else.

---

## 4. Canonical audit manifest (signed bytes)

The sender signs, and the chaincode verifies, **exactly** these bytes:

```
QFABRIC-AUDIT-MANIFEST-V1
sessionId=<sessionId>
sender=<orgId>
receiver=<orgId>
senderKeyId=<64 hex>
bb84Status=<SUCCESS|ABORTED>
qberPpm=<int>
qberThresholdPpm=<int>
siftedKeyLength=<int>
finalKeyLength=<int>
transcriptHash=<64 hex>
encryptionAlgorithm=<AES-256-GCM|NONE>
compression=<zstd|gzip|none>
documentHash=<64 hex>
encryptedDocumentHash=<64 hex, or empty when ABORTED>
timestamp=<YYYY-MM-DDTHH:MM:SSZ>
```

Rules:

1. Lines are joined with a single `\n` (0x0A). No trailing newline. UTF-8. The fields are restricted to ASCII.
2. Field order is fixed as shown. All 15 fields are always present.
3. Integers are base-10 with no sign, padding or exponent. `qberPpm = round(qber × 1 000 000)`.
4. Field formats (§1) exclude `\n` and `=`, so no field can inject another line.
5. Signature: ML-DSA-65, pure, **empty context**. Signing may be randomized (hedged); verification does not care.
6. The header line provides domain separation: the same key can never produce a valid audit manifest by signing something else.

Why not JSON? Canonical JSON across Python and Go is fragile (float formatting, key order, HTML escaping in Go's `encoding/json`). A fixed line format with integer-only numbers is unambiguous in both languages.

**Interop gate:** `integration/test_vectors/mldsa65_audit_manifest.json` holds a manifest, its canonical form, a CIRCL-generated public key, and signature. Go (`audit_test.go`) and Python (`tests/test_mldsa.py`) must both reproduce the canonical bytes and verify the signature.

---

## 5. Ledger policy (chaincode `qfabric-audit`)

`RecordSecureTransaction` processes a manifest as follows:

| Check | Failure result |
|---|---|
| Strict JSON decode, `Validate()` field formats | **error**, nothing written |
| `ABORTED` with ciphertext or `encryptionAlgorithm != NONE` | **error**, protocol violation |
| `transactionId` or `sessionId` already recorded | **error**, replay |
| Sender org registered, `senderKeyId == registered publicKeyId` | **error** |
| Submitter's Fabric MSP == sender org's MSP | **error** |
| ML-DSA-65 signature verifies against the **ledger-registered** key | **error**, unauthenticated data is never stored |
| `bb84Status == SUCCESS` | record `REJECTED` (`BB84_NOT_SUCCESSFUL`) |
| `qberThresholdPpm <= 110000` | record `REJECTED` (`QBER_THRESHOLD_ABOVE_POLICY`) |
| `qberPpm <= qberThresholdPpm` | record `REJECTED` (`QBER_EXCEEDS_THRESHOLD`) |
| `finalKeyLength >= 256` on success | record `REJECTED` (`INSUFFICIENT_KEY_MATERIAL`) |
| `AES-256-GCM` + `encryptedDocumentHash` present on success | record `REJECTED` (`DOCUMENT_NOT_ENCRYPTED`) |
| All pass | record `VERIFIED` |

Chaincode functions:

| Function | Type | Args | Returns |
|---|---|---|---|
| `RegisterOrganization` | submit | `orgId, displayName, role, publicKeyB64` (MSP taken from caller) | `Organization` |
| `GetOrganization` | evaluate | `orgId` | `Organization` |
| `RecordSecureTransaction` | submit | `transactionId, manifestJSON, signatureB64` | `AuditRecord` |
| `GetTransaction` | evaluate | `transactionId` | `AuditRecord` |
| `GetAllTransactions` | evaluate | none | `AuditRecord[]` |
| `VerifyTransactionRecord` | evaluate | `transactionId` | `VerificationResult` |

Stored `AuditRecord` (no plaintext, no keys, no secrets):

```json
{
  "docType": "auditRecord",
  "transactionId": "qfabric-tx-001",
  "manifest": { "...": "the 15 signed fields" },
  "qber": 0.02,
  "mldsaVerified": true,
  "signatureAlgorithm": "ML-DSA-65",
  "signature": "<base64>",
  "securityStatus": "VERIFIED",
  "rejectionReasons": [],
  "senderMspId": "Org1MSP",
  "submitterMspId": "Org1MSP",
  "fabricTxId": "<Fabric tx id>",
  "recordedAt": "2026-11-01T10:00:03Z"
}
```

---

## 6. Versioning and change process

- The path prefix `/api/v1` and the manifest header `QFABRIC-AUDIT-MANIFEST-V1` are versioned independently. A change to the signed fields means a `V2` header. Chaincode accepts only the versions it knows.
- Adding an **optional response** field is non-breaking, but update the Go structs as well, because the Go contract test rejects unknown fields.
- Everything else is breaking: discuss, update this file + both code mirrors + samples in **one PR**, and get both developers' approval (see `CONTRIBUTING.md`).
