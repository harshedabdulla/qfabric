# QFabric Security Model

## 1. Classification of mechanisms

| Mechanism | Category | Security basis | Role in QFabric |
|---|---|---|---|
| ML-DSA-65 | **Post-quantum cryptography** (classical algorithm, FIPS 204) | Hardness of Module-LWE / Module-SIS lattice problems | Organization authentication, transcript and manifest signatures |
| BB84 | **Quantum cryptography** (QKD), *not* PQC | Measurement disturbance / no-cloning; needs an authenticated classical channel | Shared-secret establishment, eavesdropping detection |
| AES-256-GCM | Symmetric AEAD | Grover reduces it to ~128-bit security, still adequate | Document confidentiality and integrity |
| HKDF-SHA-256 | KDF | Hash security | Bind key to session and direction |
| ECDSA (Fabric MSP) | Classical (**quantum-vulnerable**) | ECDLP | Fabric membership, endorsement, block signatures |

### Why there is no ML-KEM (FIPS 203) in v1

ML-KEM is a post-quantum **key-encapsulation** mechanism. In QFabric, BB84 already fills the key-establishment role, so v1 does not use ML-KEM. A natural extension, worth doing if time allows, is a **hybrid key**: run ML-KEM-768 between the orgs as well, and derive the AES key with `HKDF(IKM = BB84_secret || ML-KEM_shared_secret, ...)`. The derived key then stays secure if either mechanism holds. That matters because BB84 here is only simulated. The change would add `mlkem` fields to the manifest (a `V2` header) and is a contract change.

## 2. Assets

1. Confidential documents exchanged between OrgA and OrgB.
2. BB84 shared secrets and derived AES keys.
3. ML-DSA-65 secret keys of each organization.
4. Integrity of the audit history (who sent what, when, and under which security conditions).

## 3. Adversaries and assumptions

| Adversary | Capabilities | Mitigation |
|---|---|---|
| **Eve on the quantum channel** | Intercept-resend on any fraction of qubits | QBER estimation. Abort above 11%. Expected QBER from full intercept-resend is 25% |
| **Active attacker on the classical channel** | Read, modify or inject reconciliation messages (man-in-the-middle on BB84) | Every classical message goes into a transcript signed with ML-DSA-65 by both parties. Signature failure aborts |
| **Network attacker between client and crypto service** | Alter API responses (QBER, hashes, "verified" flags) | Ledger ignores service booleans. Chaincode verifies the ML-DSA signature over the canonical manifest with the ledger-registered key. Any alteration breaks the signature |
| **Malicious / buggy Fabric client** | Submit forged or replayed manifests, submit on behalf of another org | Signature verification, `senderKeyId` binding, submitter MSP == sender MSP, `sessionId` replay index |
| **Ciphertext tamperer** | Flip bits, swap nonces, replay ciphertext across sessions | AES-GCM tag over ciphertext. AAD binds session + direction. HKDF salt/info binds key to session + direction |
| **Store-now-decrypt-later quantum adversary** | Records traffic today, runs Shor later | Signatures are ML-DSA. Confidentiality key never travels over a public-key exchange (BB84 + HKDF) |
| **Ledger tamperer** | Rewrite past audit records | Fabric hash-chained blocks, endorsement by both orgs, `VerifyTransactionRecord` re-verification |

Assumptions:

- A1. Each organization's crypto-service host and key store are not compromised.
- A2. The initial ML-DSA public-key registration is honest. The Fabric MSP identity of the registering org authenticates it (trust-on-first-registration, bootstrapped by classical PKI).
- A3. The quantum channel is **simulated** (Qiskit Aer). Its security argument holds only for the modelled attack (intercept-resend) and noise model.
- A4. Random numbers come from NumPy generators seeded per run for reproducibility. **This is a simulation, not a QRNG/CSPRNG-grade source.** ML-DSA keys, AES nonces and HKDF use OS randomness through liboqs and `cryptography`.

## 4. Authentication

- **Organization identity:** `RegisterOrganization` stores `(orgId, mspId-from-caller-cert, ML-DSA public key, SHA-256 fingerprint)`. Re-registration is refused. Key rotation is future work (it would need a signed rotation record).
- **Transcript authentication:** BB84's classical messages are serialized into a transcript. Both Alice (OrgA key) and Bob (OrgB key) sign it. `transcriptAuthenticated` reports the result, and `transcriptHash` is part of the signed manifest.
- **Transfer authentication:** the sender signs the canonical audit manifest (`docs/API_CONTRACT.md` §4). The chaincode verifies it on **every endorsing peer**, against the key **on the ledger**, never against a key supplied in the request.
- **Fabric authentication:** the client signs Fabric proposals with an X.509/ECDSA identity. This proves Fabric membership only and is not quantum-safe.

## 5. Key management

| Key | Created | Stored | Lifetime | Exposure |
|---|---|---|---|---|
| ML-DSA-65 secret key | `POST /organizations/register` | Service key store, file mode 0600 (Docker: named volume) | Until rotated (future) | Never returned or logged. `repr` hidden |
| ML-DSA-65 public key | same | Service + ledger | same | Public |
| BB84 shared secret (256 bit) | `run_bb84` on SUCCESS | Process memory (session store) | Service process lifetime | Never returned, logged or written to disk or ledger |
| AES-256 key | HKDF on demand | Not stored | Per operation | Never returned |
| AES-GCM nonce | Random 96-bit per encryption | Sent with ciphertext | Single use | Public |

HKDF parameters: `IKM = secret`, `salt = sessionId`, `info = "qfabric/v1/aes-256-gcm|" + sender + "|" + receiver`, `L = 32`.

Error and log hygiene: validation errors report field paths only, not values. Unhandled exceptions return a generic `INTERNAL_ERROR`, and stack traces go only to the server log.

## 6. Ledger security policy

The chaincode accepts a manifest only if the signature verifies. It then records:

- `VERIFIED`: BB84 succeeded, QBER ≤ threshold ≤ 11%, final key ≥ 256 bits, document encrypted with AES-256-GCM.
- `REJECTED`: authenticated but failing policy (for example, eavesdropping detected). Rejections are audited, not dropped.

Malformed, replayed or unauthenticated submissions error out and are not recorded.

## 7. Limitations (state these honestly in the demo)

1. **Simulated QKD.** No photons, no fibre, no detectors. Real BB84 needs dedicated optical hardware and distance-limited links, and real deployments face side-channel attacks (detector blinding, photon-number splitting) that are not modelled here.
2. **Single-host simulation.** Alice and Bob run in one service process, so the shared secret exists in one place. In a real deployment each org runs its own endpoint.
3. **Asymptotic key-length estimate.** Privacy amplification uses `n(1 − h(Q)) − leak − margin` without finite-key corrections.
4. **Fabric itself is classical.** Fabric 2.5 signs proposals, endorsements and blocks with ECDSA. QFabric adds post-quantum authentication at the application layer. It does not make Fabric's consensus or membership quantum-safe.
5. **Trust bootstrap is classical.** The first registration of an ML-DSA key relies on Fabric MSP (ECDSA).
6. **No key rotation or revocation** in v1.
7. **`/mldsa/sign` is a signing oracle.** Demo only. Disable it in any shared environment.
8. **In-memory sessions.** A service restart loses BB84 sessions, which is intentional for a demo.
9. **Timestamps.** The manifest `timestamp` is the sender's claim. The ledger's `recordedAt` (transaction timestamp) is the authoritative time.
10. **Simulation details.** Photons are batched as 64 independent qubits per circuit on Aer's exact stabilizer simulator. Channel noise is a Pauli channel. Eve's intercept-resend is a real mid-circuit measurement.
11. **Transcript authentication happens once, at the end.** Both orgs sign the whole classical transcript before the key is accepted, rather than signing each message as it goes. Tampering is still detected before any key is used, but an active attacker can force an abort (denial of service), as in any QKD system.
12. **Cascade leakage accounting** counts every parity bit and each 64-bit confirmation tag as leaked. This is conservative but asymptotic (see item 3).
