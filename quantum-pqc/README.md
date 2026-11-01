# QFabric: Quantum/PQC Module

**Owner:** Developer 2 (Quantum Computing / PQC). Blockchain-side changes here only by agreement.

This module implements BB84 quantum key distribution (simulated on Qiskit Aer), ML-DSA-65 post-quantum signatures (liboqs), and AES-256-GCM document protection with HKDF-SHA-256 and zstd compression. It exposes everything through a FastAPI service that the Fabric client consumes.

> BB84 is **quantum cryptography** (QKD). ML-DSA is **post-quantum cryptography** (a classical algorithm resistant to quantum attacks). Don't conflate them in docs or slides.

## Status

| Component | Status |
|---|---|
| API skeleton, Pydantic schemas, error envelope, `/health` | ✅ working |
| Contract tests (samples, schema, secret-field guard) | ✅ passing |
| Dockerfile (liboqs 0.16.0 build) | ✅ builds. CIRCL ↔ liboqs vector verified |
| BB84 (`bb84/`) | ⏳ stubs: implement |
| ML-DSA (`mldsa/`) | ⏳ stubs (`public_key_id` done): implement |
| Encryption (`encryption/`) | ⏳ stubs (`associated_data` done): implement |
| Service layer (`api/services.py`) | ⏳ stubs return `501 NOT_IMPLEMENTED` |

Update this table as pieces land. Don't mark ✅ until the tests pass.

## Layout

```
quantum-pqc/
├── bb84/                 BB84 protocol
│   ├── alice.py            random bits/bases, state preparation (Qiskit circuits)
│   ├── bob.py              random bases, measurement on AerSimulator
│   ├── quantum_channel.py  noise model / backend
│   ├── eavesdropper.py     intercept-resend Eve
│   ├── basis_reconciliation.py  sifting, sampling, QBER
│   ├── error_correction.py Cascade-style reconciliation (+ leakage count)
│   ├── privacy_amplification.py Toeplitz hashing, secure length
│   └── protocol.py         run_bb84(): orchestration, abort logic, transcript
├── mldsa/                ML-DSA-65 via liboqs
│   ├── keygen.py           key pairs, publicKeyId = sha256(pk)
│   ├── signing.py / verification.py
│   ├── identity.py         org identities + 0600 key store
│   └── manifest.py         canonical audit manifest (CONTRACT-CRITICAL)
├── encryption/           HKDF, compression, AES-256-GCM, tamper detection
├── api/                  FastAPI: main.py, routes.py, schemas.py (contract), services.py
├── scripts/              demo_bb84.py, demo_mldsa.py, demo_secure_transfer.py
├── tests/                pytest. NotImplementedError → reported as "skipped"
├── Dockerfile            Python 3.12 + liboqs 0.16.0
└── requirements.txt
```

## Setup

```bash
# from repo root
./scripts/setup.sh crypto
# or manually
cd quantum-pqc
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Installing liboqs

`liboqs-python` needs the liboqs C library, version **0.16.x**.

- macOS: `brew install liboqs`
- Exact version from source: see [docs/DEVELOPMENT_GUIDE.md](../docs/DEVELOPMENT_GUIDE.md#installing-liboqs-quantumpqc), then `export OQS_INSTALL_PATH=$HOME/_oqs`.
- No local install: run the service in Docker (`docker compose up --build crypto` from the repo root).

If liboqs is missing, `import oqs` tries to download and build it on the fly. Install it explicitly to avoid surprises. Modules import `oqs` lazily inside functions so the rest of the package works without it.

## Run

```bash
pytest                                       # all tests
pytest -k "vector or canonical"              # interop gate with the Go chaincode
uvicorn api.main:app --reload --port 8000    # http://localhost:8000/docs
python -m scripts.demo_bb84 --noise 0.02
python -m scripts.demo_mldsa
python -m scripts.demo_secure_transfer README.md          # needs the API running
python -m scripts.demo_secure_transfer README.md --eve
```

Docker:

```bash
docker compose up --build -d crypto          # from repo root
curl localhost:8000/api/v1/health
```

## Implementation notes and rules

**BB84**
- Use real Qiskit circuits: Alice prepares, Eve measures and re-prepares, Bob measures on `AerSimulator`. Never shortcut by copying Alice's bits.
- Batch the circuits (one job, `shots=1` per circuit) for speed. Seed `AerSimulator(seed_simulator=...)` and NumPy from `BB84Config.seed`.
- Basis convention: `0 = Z`, `1 = X`.
- Defaults: 2048 qubits, 25% of sifted bits sampled, abort if QBER > 0.11, error correction leakage counted, privacy amplification to 256 bits, abort if the secure length is < 256.
- Every classical message goes into the transcript. Both orgs sign it with ML-DSA. `transcriptHash = sha256(transcript)`.
- Expected values to validate against: QBER ≈ 0 with an ideal channel. ≈ 0.25 × interception rate with Eve.

**ML-DSA**
- `oqs.Signature("ML-DSA-65")`, pure mode, **empty context**. This must match the chaincode (CIRCL).
- `canonical_manifest()` must reproduce `integration/test_vectors/mldsa65_audit_manifest.json["canonicalManifest"]` byte for byte.

**Encryption**
- HKDF-SHA-256: `salt = sessionId`, `info = "qfabric/v1/aes-256-gcm|<sender>|<receiver>"`, 32 bytes.
- AES-256-GCM: fresh 12-byte nonce from `os.urandom` and AAD from `associated_data()`. `encryptedDocumentHash = sha256(nonce || ciphertext)`.
- Bound decompression by `QFABRIC_MAX_DOCUMENT_BYTES`.

**Never**
- return, log or persist BB84 secrets or AES keys
- return ML-DSA secret keys
- echo request bodies in errors

## API

Full contract: [docs/API_CONTRACT.md](../docs/API_CONTRACT.md). Schemas live in `api/schemas.py`. Changing them is a contract change (see [CONTRIBUTING.md](../CONTRIBUTING.md)).

| Method | Path |
|---|---|
| GET | `/api/v1/health` |
| POST | `/api/v1/organizations/register` |
| GET | `/api/v1/organizations/{orgId}` |
| POST | `/api/v1/mldsa/sign`, `/api/v1/mldsa/verify` |
| POST | `/api/v1/bb84/execute`, `/api/v1/bb84/simulate-attack` |
| POST | `/api/v1/encryption/encrypt`, `/api/v1/encryption/decrypt` |
| POST | `/api/v1/secure-transfer` |
