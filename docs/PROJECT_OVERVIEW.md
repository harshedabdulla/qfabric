# Project Overview

**QFabric: Quantum-Assisted Post-Quantum Security for Hyperledger Fabric**
Qiskit IBM Quantum Hacks, Challenge 5: Post-Quantum Cryptography.

## Motivation

Fabric consortia authenticate members and transactions with ECDSA, which a large quantum computer could break (see [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md)). Waiting for platform-level migration leaves today's audit trails and confidential exchanges exposed. QFabric shows how a consortium can add quantum-era protections **at the application layer, now**, without forking Fabric.

## What QFabric does

Two organizations, **OrgA (Manufacturer)** and **OrgB (Supplier)**, exchange a confidential document:

1. **Authenticate** with ML-DSA-65 keys whose public halves are anchored on the ledger.
2. **Establish a key** with BB84, simulated on Qiskit Aer with real circuits. An optional intercept-resend eavesdropper is detected through QBER.
3. **Protect the document**: compress (zstd), then encrypt with AES-256-GCM under an HKDF-SHA-256 key derived from the BB84 secret.
4. **Audit**: the sender signs a canonical manifest of the security metadata. The Fabric chaincode verifies the signature itself and records a `VERIFIED` or `REJECTED` audit record. No plaintext, keys or secrets go on-chain.

## Goals

| # | Goal | Success criterion |
|---|---|---|
| G1 | Real BB84 simulation | Qiskit circuits, sifting, QBER, error correction, privacy amplification. QBER ≈ 0 without Eve, ≈ 25% with full intercept-resend |
| G2 | Post-quantum authentication | ML-DSA-65 sign/verify. Tampering detected. Cross-language (liboqs ↔ CIRCL) verification passes |
| G3 | Confidential transfer | Round-trip encrypt/decrypt. Tampered ciphertext rejected |
| G4 | Independent on-chain verification | Chaincode rejects forged, replayed or mis-attributed manifests. It never trusts service booleans |
| G5 | Auditability | Ledger shows both successful and eavesdropped sessions. `VerifyTransactionRecord` re-verifies |
| G6 | Measured trade-offs | Benchmarks per [BENCHMARKING.md](BENCHMARKING.md) |

## Expected outcome

An end-to-end demo (`scripts/run-demo.sh`) that:

1. registers both organizations,
2. performs an honest transfer recorded as `VERIFIED`,
3. performs an eavesdropped transfer recorded as `REJECTED` with reason `QBER_EXCEEDS_THRESHOLD`,
4. shows the audit history and re-verifies a record,

plus a benchmark report comparing ECDSA and ML-DSA and quantifying the BB84, encryption and Fabric overheads.

## Team

| Developer | Area | Directory |
|---|---|---|
| Dev 1 | Blockchain / Hyperledger Fabric, root docs, integration docs | `blockchain/`, root, `docs/`, `integration/` |
| Dev 2 | Quantum computing / PQC | `quantum-pqc/` |

## Phases

1. **Repository initialization** (this commit): structure, docs, contract, scaffolds.
2. **Independent development**: Fabric network + chaincode (Dev 1). BB84, ML-DSA, encryption, API (Dev 2).
3. **Integration**: client ↔ API ↔ chaincode. Accepted and rejected flows.
4. **Demo and benchmarks.**
