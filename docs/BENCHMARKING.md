# Benchmarking Plan

Results go in `benchmarks/<area>/results/` (git-ignored raw output). Summary tables are copied into this file and the root README once measured. **No numbers are claimed until measured.**

## 1. Environment to record with every run

CPU model, cores, RAM, OS, Python/Go versions, liboqs version, Qiskit/Aer versions, Fabric version, state DB, and whether Docker runs natively or in a VM (Colima/Docker Desktop).

## 2. Cryptography (`benchmarks/cryptography/`, Python)

| ID | Metric | Method | Output |
|---|---|---|---|
| C1 | ECDSA P-256 vs ML-DSA-65: keygen / sign / verify latency | `cryptography` ECDSA vs liboqs ML-DSA-65. 1 000 iterations after 50 warm-up, 1 KiB message. `time.perf_counter_ns` | mean, p50, p95, ops/s |
| C2 | Key and signature sizes | Byte lengths (ECDSA DER signature varies, so report its range) | table: pk, sk, sig bytes |
| C3 | Ledger footprint per audit record | `len(json(AuditRecord))` with an ML-DSA signature vs a hypothetical ECDSA signature | bytes per record |
| C4 | BB84 QBER vs interception rate | `interception_rate ∈ {0, 0.1, …, 1.0}`, 20 seeds each, 2048 qubits | mean ± std QBER vs theoretical `0.25·r`. Abort rate |
| C5 | BB84 QBER vs channel noise | `channel_error_rate ∈ {0, 0.01, …, 0.15}`, no Eve | QBER, abort rate, final key length |
| C6 | BB84 key-generation overhead | wall time per stage (prepare, simulate, sift, EC, PA) for `num_qubits ∈ {512, 1024, 2048, 4096, 8192}` | ms per stage. Secure bits per second |
| C7 | Key efficiency | `final_key_length / num_qubits` vs QBER | ratio |
| C8 | Encryption / decryption latency | AES-256-GCM on documents of 1 KiB, 100 KiB, 1 MiB, 10 MiB (incl. HKDF) | MB/s, ms |
| C9 | Compression ratio | zstd (levels 3, 10, 19) and gzip on text, JSON, PDF and random data | ratio, compress ms. Effect on encryption time |

## 3. Blockchain (`benchmarks/blockchain/`, Go)

| ID | Metric | Method | Output |
|---|---|---|---|
| B1 | `RecordSecureTransaction` latency | Submit → commit status via Gateway. 200 sequential transactions with pre-signed manifests | mean, p50, p95 ms |
| B2 | Throughput | N concurrent submitters (1, 4, 8, 16), 60 s each | committed TPS, error rate |
| B3 | Cost of on-chain ML-DSA verification | Same transaction with verification vs a baseline function that skips verification (benchmark build only, never deployed) | Δ latency, Δ TPS |
| B4 | Query latency | `GetTransaction`, `GetAllTransactions` at 100 / 1 000 / 10 000 records | ms |
| B5 | Block/ledger growth | Ledger size delta per 1 000 records | MB |

Use [Hyperledger Caliper](https://hyperledger-caliper.github.io/caliper/) for B2 if time allows. Otherwise use a Go load generator built on `fabric-gateway`.

## 4. End-to-end

| ID | Metric | Method |
|---|---|---|
| E1 | Full secure transfer latency | `client transfer` wall time broken down into API (BB84, encrypt, sign) and Fabric (endorse, commit) |
| E2 | Eavesdropping detection rate | 100 runs with `simulateEavesdropper`. Fraction recorded `REJECTED` |

## 5. Reporting template

```
| Operation        | ECDSA P-256 | ML-DSA-65 | Ratio |
|------------------|-------------|-----------|-------|
| Keygen (µs)      |             |           |       |
| Sign (µs)        |             |           |       |
| Verify (µs)      |             |           |       |
| Public key (B)   | 65 / 91 DER | 1952      |       |
| Signature (B)    | ~70–72 DER  | 3309      |       |
```

The key and signature sizes above are fixed by the standards (FIPS 204 and SEC 1 / DER). Every timing cell must come from a measured run.
