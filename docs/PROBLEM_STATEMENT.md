# Problem Statement

## Context

Permissioned blockchains such as Hyperledger Fabric underpin supply-chain, trade-finance and healthcare consortia. Their trust model relies on classical public-key cryptography:

- **ECDSA (P-256)** signs every transaction proposal, endorsement and block.
- **X.509 certificates** issued by Fabric CAs bind identities to ECDSA keys (MSP).
- **TLS** with ECDHE/RSA protects peer-to-peer and client-to-peer traffic.

## The quantum threat

A cryptographically relevant quantum computer running **Shor's algorithm** solves the elliptic-curve discrete logarithm and integer factorization problems in polynomial time. That would let an attacker:

1. **Forge signatures:** derive an organization's ECDSA private key from its public certificate and impersonate it.
2. **Decrypt recorded traffic** ("harvest now, decrypt later"): key exchanges recorded today can be broken later. Ledger data is long-lived, which makes it an attractive target.
3. **Undermine audit trails:** if signatures become forgeable, the provenance guarantees of historic records weaken.

**Grover's algorithm** only halves symmetric security, so AES-256 stays adequate (~128-bit post-quantum security).

NIST finalized its first post-quantum standards in August 2024: **FIPS 203 (ML-KEM)**, **FIPS 204 (ML-DSA)** and **FIPS 205 (SLH-DSA)**. Migration is under way, but blockchain platforms such as Fabric have not adopted them yet.

## The gap QFabric addresses

Organizations exchanging confidential documents over a Fabric consortium need:

| Need | Classical status | QFabric approach |
|---|---|---|
| Quantum-resistant authentication of who sent what | ECDSA only | ML-DSA-65 signatures verified on-chain |
| Key establishment that does not rely on public-key exchange | ECDHE | BB84 QKD (simulated) + HKDF |
| Detection of key-exchange eavesdropping | None at the protocol level | BB84 QBER check with abort |
| Confidential, tamper-evident document transfer | Off-chain, ad hoc | AES-256-GCM + hashes anchored on the ledger |
| Auditable evidence of the security conditions of each transfer | None | Signed manifest + chaincode policy → `VERIFIED` / `REJECTED` records |

## Scope

In scope: a working prototype on the Fabric 2.5 test network with two organizations, simulated BB84 on Qiskit Aer, ML-DSA-65 through liboqs, and a measurable comparison with the classical baseline.

Out of scope: replacing Fabric's internal ECDSA (core-platform change), physical QKD hardware, production key management.
