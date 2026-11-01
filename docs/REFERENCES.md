# References

## Standards

- NIST FIPS 204, *Module-Lattice-Based Digital Signature Standard (ML-DSA)*, Aug 2024. https://csrc.nist.gov/pubs/fips/204/final
- NIST FIPS 203, *Module-Lattice-Based Key-Encapsulation Mechanism Standard (ML-KEM)*, Aug 2024. https://csrc.nist.gov/pubs/fips/203/final
- NIST SP 800-38D, *Galois/Counter Mode (GCM)*. https://csrc.nist.gov/pubs/sp/800/38/d/final
- RFC 5869, *HMAC-based Extract-and-Expand Key Derivation Function (HKDF)*. https://www.rfc-editor.org/rfc/rfc5869
- RFC 8878, *Zstandard Compression*. https://www.rfc-editor.org/rfc/rfc8878
- NIST IR 8547 (draft), *Transition to Post-Quantum Cryptography Standards*. https://csrc.nist.gov/pubs/ir/8547/ipd

## Quantum computing and QKD

- Qiskit: https://github.com/Qiskit/qiskit
- Qiskit Aer: https://github.com/Qiskit/qiskit-aer
- IBM Quantum documentation: https://quantum.cloud.ibm.com/docs/en
- C. H. Bennett, G. Brassard, *Quantum cryptography: Public key distribution and coin tossing*, Proc. IEEE ICCSSP 1984 (reprinted in Theoretical Computer Science 560, 2014). https://doi.org/10.1016/j.tcs.2014.05.025
- P. W. Shor, J. Preskill, *Simple Proof of Security of the BB84 Quantum Key Distribution Protocol*, PRL 85, 441 (2000). https://doi.org/10.1103/PhysRevLett.85.441 (source of the ~11% QBER bound)
- G. Brassard, L. Salvail, *Secret-Key Reconciliation by Public Discussion* (Cascade), EUROCRYPT '93. https://doi.org/10.1007/3-540-48285-7_35
- V. Scarani et al., *The security of practical quantum key distribution*, Rev. Mod. Phys. 81, 1301 (2009). https://doi.org/10.1103/RevModPhys.81.1301
- P. W. Shor, *Polynomial-Time Algorithms for Prime Factorization and Discrete Logarithms on a Quantum Computer*, SIAM J. Comput. 26 (1997). https://doi.org/10.1137/S0097539795293172

## Post-quantum cryptography libraries

- Open Quantum Safe liboqs: https://github.com/open-quantum-safe/liboqs
- liboqs-python: https://github.com/open-quantum-safe/liboqs-python
- Cloudflare CIRCL (Go ML-DSA, used in chaincode): https://github.com/cloudflare/circl
- CRYSTALS-Dilithium (ML-DSA predecessor): https://pq-crystals.org/dilithium/
- pyca/cryptography (AES-GCM, HKDF, ECDSA): https://cryptography.io/

## Hyperledger Fabric

- Fabric: https://github.com/hyperledger/fabric
- Fabric documentation: https://hyperledger-fabric.readthedocs.io/
- Fabric samples (test network): https://github.com/hyperledger/fabric-samples
- Fabric Gateway client API: https://github.com/hyperledger/fabric-gateway
- Fabric Contract API for Go: https://github.com/hyperledger/fabric-contract-api-go
- Fabric Chaincode Go shim: https://github.com/hyperledger/fabric-chaincode-go
- Hyperledger Caliper (benchmarking): https://hyperledger-caliper.github.io/caliper/
- E. Androulaki et al., *Hyperledger Fabric: A Distributed Operating System for Permissioned Blockchains*, EuroSys 2018. https://doi.org/10.1145/3190508.3190538

## Post-quantum blockchain research

- T. M. Fernández-Caramès, P. Fraga-Lamas, *Towards Post-Quantum Blockchain: A Review on Blockchain Cryptography Resistant to Quantum Computing Attacks*, IEEE Access 8 (2020). https://doi.org/10.1109/ACCESS.2020.2968985
- D. Aggarwal et al., *Quantum attacks on Bitcoin, and how to protect against them*, Ledger 3 (2018). https://doi.org/10.5195/ledger.2018.127

Add papers here as they are used. Note which claim each one supports.
