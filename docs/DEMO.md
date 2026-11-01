# QFabric Demo Runbook

Every command below was run end to end on the `dev` branch. Run them from the **repo root** unless a step says `cd`. Each step lists what to say while it runs.

## 0. One-time setup (before the presentation)

```bash
./scripts/setup.sh                      # quantum-pqc/.venv, Qiskit built from third_party/qiskit, liboqs, Go deps
docker compose build crypto             # crypto service image (builds Qiskit from source: slow the first time)
mkdir -p demo-output && printf 'CONFIDENTIAL PURCHASE ORDER PO-2026-0042\nBuyer: OrgA (Manufacturer)\nSupplier: OrgB\nItem: Titanium fasteners, grade 5, qty 5000\nUnit price: 0.42 USD\n' > demo-output/po.txt
```

## Option A: one command, everything (about 3 minutes from cold)

```bash
./scripts/run-demo.sh demo-output/po.txt
```

This starts the crypto service and Fabric, deploys the chaincode, registers both orgs, runs an honest and an eavesdropped transfer, shows the audit history, re-verifies, and runs the attacks. Use it as a backup, or when time is short.

## Option B: step by step (recommended for presenting)

### 1. Start the infrastructure

Safe to re-run: if the network, channel or chaincode is already up, each script says so and skips. To start over from an empty ledger, run `./scripts/reset-demo.sh` instead and continue at step 2.

```bash
docker compose up -d crypto                        # Quantum/PQC service on :8000
./blockchain/scripts/start-network.sh              # Fabric 2.5.16: orderer + OrgA (Org1MSP) + OrgB (Org2MSP) + CAs
./blockchain/scripts/deploy-chaincode.sh           # qfabric-audit chaincode, endorsed by both orgs
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

> *"Two organizations, Manufacturer and Supplier, on a permissioned Hyperledger Fabric network. Next to it runs our quantum/PQC service."*

### 2. Qiskit really is in this repo

```bash
ls quantum-pqc/third_party/qiskit
quantum-pqc/.venv/bin/python -c "import qiskit; print('Qiskit', qiskit.__version__, 'loaded from', qiskit.__file__)"
curl -s localhost:8000/api/v1/health | jq .versions
```

> *"BB84 runs on Qiskit 2.6.1 built from source inside this repository, not a black-box package. The running service reports where its Qiskit comes from."*

### 3. BB84 quantum key distribution and eavesdropper detection

```bash
cd quantum-pqc
.venv/bin/python -m scripts.demo_bb84 --noise 0.02
cd ..
```

Expected: no eavesdropper gives `SUCCESS` (QBER ≈ 1.5%). Eve at 30% or 100% gives `ABORTED` (QBER ≈ 11–25%).

> *"Alice encodes random bits in random bases as Qiskit circuits, and Bob measures them on Aer. An intercept-resend eavesdropper has to measure the qubits, which disturbs them, so the error rate jumps to ≈25%. Above 11% we abort and no key is produced."*

The same exchange through the API, showing the authenticated transcript:

```bash
curl -s -X POST localhost:8000/api/v1/bb84/execute -H 'content-type: application/json' \
  -d '{"sender":"OrgA","receiver":"OrgB","channelErrorRate":0.02}' \
  | jq '{status, qber, siftedKeyLength, finalKeyLength, keyConfirmed, transcriptAuthenticated, backend}'
curl -s -X POST localhost:8000/api/v1/bb84/simulate-attack -H 'content-type: application/json' \
  -d '{"sender":"OrgA","receiver":"OrgB"}' \
  | jq '{status, abortReason, qber, expectedQberFromAttack, finalKeyLength}'
```

(These two calls need the orgs registered in the crypto service, so run them after step 5 on a fresh start.)

### 4. ML-DSA-65 post-quantum signatures

```bash
cd quantum-pqc
.venv/bin/python -m scripts.demo_mldsa
cd ..
```

> *"ML-DSA-65 is NIST FIPS 204, a lattice-based signature quantum computers can't forge. The public key is 1952 bytes and the signature 3309. A one-byte change fails verification."*

### 5. Register organizations: ML-DSA public keys anchored on the ledger

```bash
cd blockchain
QFABRIC_ORG=OrgA go run ./client register | jq '{orgId, mspId, algorithm, publicKeyId, registeredAt}'
QFABRIC_ORG=OrgB go run ./client register | jq '{orgId, mspId, algorithm, publicKeyId, registeredAt}'
go run ./client org OrgA | jq '{orgId, role, mspId, algorithm, publicKeyId, publicKey: (.publicKey[0:48] + "...")}'
```

> *"Each org's post-quantum public key now lives on the blockchain, bound to its Fabric identity. From here on the ledger trusts this key, not the service."*

### 6. Honest confidential transfer, recorded as VERIFIED

```bash
QFABRIC_ORG=OrgA go run ./client transfer -to OrgB -file ../demo-output/po.txt -tx demo-honest \
  | jq '{transactionId, securityStatus, mldsaVerified, qber, signatureAlgorithm, documentHash: .manifest.documentHash, fabricTxId}'
```

> *"BB84 makes a 256-bit key. HKDF derives an AES-256-GCM key, and the purchase order is compressed and encrypted. OrgA signs an audit manifest with ML-DSA. The chaincode on both peers verifies that signature itself and records only hashes and metadata, never the document or keys."*

### 7. Eavesdropper detected, recorded as REJECTED

```bash
QFABRIC_ORG=OrgA go run ./client transfer -to OrgB -file ../demo-output/po.txt -eve -tx demo-eve \
  | jq '{transactionId, securityStatus, qber, rejectionReasons}'
```

A stealthier Eve stays under the 11% threshold and is still rejected, because privacy amplification finds no secure key:

```bash
QFABRIC_ORG=OrgA go run ./client transfer -to OrgB -file ../demo-output/po.txt -eve -intercept 0.3 -noise 0 -tx demo-stealthy-eve \
  | jq '{transactionId, securityStatus, qber, rejectionReasons}'
```

> *"The attack itself becomes tamper-evident audit evidence on the ledger."*

### 8. Audit history

```bash
go run ./client list | jq -r '["TX","STATUS","QBER","FROM→TO"], (.[] | [.transactionId, .securityStatus, (.qber|tostring), "\(.manifest.sender)→\(.manifest.receiver)"]) | @tsv' | column -t
```

### 9. Independent re-verification, by the other organization

```bash
QFABRIC_ORG=OrgB go run ./client verify demo-honest | jq .
```

> *"Any member can re-check the stored ML-DSA signature against the registered key and recompute the verdict."*

### 10. Attacks on the ledger are refused

```bash
./scripts/attack-scenarios.sh demo-honest
cd ..
```

Expected: replay, tampered QBER and submission under the wrong org are all refused, and the ledger is unchanged.

> *"Changing one number in a signed manifest breaks the post-quantum signature, and the chaincode refuses it."*

### 11. Encryption tamper detection (optional)

```bash
A=localhost:8000/api/v1
SID=$(curl -s -X POST $A/bb84/execute -H 'content-type: application/json' -d '{"sender":"OrgA","receiver":"OrgB"}' | jq -r .sessionId)
ENC=$(jq -n --arg s "$SID" --arg d "$(base64 < demo-output/po.txt)" '{sessionId:$s, document:$d, compression:"zstd"}' \
      | curl -s -X POST $A/encryption/encrypt -H 'content-type: application/json' -d @-)
echo "$ENC" | jq '{algorithm, originalSize, compressedSize, ciphertext: (.ciphertext[0:40] + "..."), documentHash}'
# genuine ciphertext decrypts
echo "$ENC" | jq '{sessionId, nonce, ciphertext, compression, expectedDocumentHash: .documentHash}' \
  | curl -s -X POST $A/encryption/decrypt -H 'content-type: application/json' -d @- | jq -r '.hashMatched, (.document|@base64d)'
# flip one bit, and AES-GCM rejects it
echo "$ENC" | python3 -c "import sys,json,base64; e=json.load(sys.stdin); c=bytearray(base64.b64decode(e['ciphertext'])); c[0]^=1; print(json.dumps({'sessionId':e['sessionId'],'nonce':e['nonce'],'ciphertext':base64.b64encode(c).decode(),'compression':'zstd'}))" \
  | curl -s -X POST $A/encryption/decrypt -H 'content-type: application/json' -d @- | jq .
```

### 12. Tests (if asked "how do you know it works?")

```bash
(cd quantum-pqc && .venv/bin/python -m pytest -q)                  # 60 tests: BB84, ML-DSA, AES-GCM, API
(cd blockchain/chaincode/qfabric-audit && go test ./...)          # chaincode: signatures, replay, policy
(cd blockchain && go test ./...)                                   # contract tests
```

## Reset and teardown

```bash
./scripts/reset-demo.sh                  # clean slate between rehearsals: empty ledger, new keys, chaincode deployed
# or tear everything down:
./blockchain/scripts/stop-network.sh     # destroys the ledger
docker compose down -v                   # stops the crypto service AND deletes its ML-DSA keys
```

Always reset **both** together. The ledger refuses re-registration, so new service keys on an old ledger, or old keys on a new ledger, will not match.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `organization OrgA is already registered` | Normal on a re-run. Skip step 5 |
| `senderKeyId does not match` | The service keys and the ledger are out of sync. Run the full reset above |
| `transaction demo-honest already recorded` | Use a new `-tx` id, e.g. `-tx demo-honest-2` |
| `cannot join: channel already exists` / `ENDORSEMENT_POLICY_FAILURE` while deploying | You re-ran step 1 with old scripts on a running network. Pull the latest `dev`: the scripts now skip what already exists |
| Changed the chaincode code | `./blockchain/scripts/deploy-chaincode.sh upgrade` |
| Port 8000 busy | `lsof -iTCP:8000 -sTCP:LISTEN`, then stop that process |
| Crypto service not ready | `docker compose logs crypto` |

## What is not shown (be upfront)

- BB84 runs on a **simulator** (Qiskit Aer). There is no quantum hardware or optical link.
- Fabric's own transaction signatures are still classical ECDSA. QFabric adds post-quantum authentication at the application layer.
- ML-KEM is not used yet (see `docs/SECURITY_MODEL.md`). Benchmarks are pending (`docs/BENCHMARKING.md`).
