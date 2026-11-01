# Development Guide

## 1. Prerequisites

| Tool | Version | Needed by |
|---|---|---|
| git | any recent | both |
| Python | **3.12** (3.11–3.13 supported; Qiskit/Aer wheels lag the newest CPython) | Quantum/PQC |
| liboqs (C) | **0.16.x**, matching `liboqs-python~=0.16.0` | Quantum/PQC (or use Docker) |
| Go | 1.25+ | Blockchain |
| Docker + Compose v2 | recent | Blockchain (Fabric), crypto service container |
| jq, curl | any | Fabric test-network scripts |

Pinned platform versions: **Hyperledger Fabric 2.5.16**, **Fabric CA 1.5.22**, **fabric-contract-api-go v2.2.2**, **fabric-gateway v1.12.1**, **cloudflare/circl v1.6.5**.

## 2. First-time setup

```bash
git clone <repo-url> qfabric && cd qfabric
./scripts/setup.sh crypto        # Dev 2
./scripts/setup.sh blockchain    # Dev 1 (add --fabric to pre-download Fabric)
```

`setup.sh` creates `quantum-pqc/.venv`, installs requirements, runs `go mod download` for both Go modules, and copies `.env.example` → `.env` where missing.

### Installing liboqs (Quantum/PQC)

- **macOS:** `brew install liboqs`, then check the version with `brew info liboqs` (0.16.x).
- **Linux / exact version:**
  ```bash
  git clone --depth 1 --branch 0.16.0 https://github.com/open-quantum-safe/liboqs
  cmake -S liboqs -B liboqs/build -DBUILD_SHARED_LIBS=ON -DOQS_BUILD_ONLY_LIB=ON -DCMAKE_INSTALL_PREFIX="$HOME/_oqs"
  cmake --build liboqs/build --parallel && cmake --install liboqs/build
  export OQS_INSTALL_PATH="$HOME/_oqs"
  ```
- **No local install:** `docker compose up --build crypto` builds liboqs 0.16.0 inside the image.

## 3. Daily commands

```bash
# Quantum/PQC
cd quantum-pqc
source .venv/bin/activate
pytest                                   # stubs show as "skipped: not implemented yet"
uvicorn api.main:app --reload --port 8000   # docs at http://localhost:8000/docs
python -m scripts.demo_bb84

# Blockchain
cd blockchain
go test ./...                            # client + contract tests
(cd chaincode/qfabric-audit && go test ./...)
./scripts/start-network.sh               # Fabric up + channel
./scripts/deploy-chaincode.sh            # or: deploy-chaincode.sh 1.1 2 to upgrade
go run ./client list
./scripts/stop-network.sh
```

## 4. Branches

```
main                     demo-ready, protected
└── dev                  integration branch
    ├── feature/bb84               Dev 2
    ├── feature/mldsa              Dev 2
    ├── feature/secure-encryption  Dev 2
    ├── feature/fabric-network     Dev 1
    ├── feature/chaincode          Dev 1
    └── feature/integration        both
```

```bash
git checkout dev && git pull
git checkout -b feature/chaincode
# ... commit ...
git push -u origin feature/chaincode     # open PR into dev
```

- Branch from `dev` and open PRs into `dev`. `dev` → `main` only when the demo passes.
- Rebase or merge `dev` frequently. Keep PRs small.
- Commit style: `feat(chaincode): verify ML-DSA in RecordSecureTransaction`, `fix(bb84): ...`, `docs: ...`, `test: ...`.

## 5. Ownership

| Path | Owner | Others may |
|---|---|---|
| `quantum-pqc/**` | Dev 2 | open issues. Integration fixes only with Dev 2's agreement |
| `blockchain/**` | Dev 1 | open issues |
| `README.md`, `docs/**`, `integration/**`, `scripts/**`, `docker-compose.yml` | Dev 1 | PRs welcome, contract files need both approvals |

A `CODEOWNERS` file can enforce this on GitHub once the remote exists:

```
/quantum-pqc/   @<dev2-github-handle>
/blockchain/    @<dev1-github-handle>
/integration/   @<dev1-github-handle> @<dev2-github-handle>
/docs/API_CONTRACT.md @<dev1-github-handle> @<dev2-github-handle>
```

## 6. Dependency rules

- Python: add to `quantum-pqc/requirements.txt` with a lower bound (and an upper bound for Qiskit majors). No unpinned git dependencies.
- Go: `go get pkg@version && go mod tidy`. The **chaincode** `go.mod` must keep `go 1.25.0` or lower and only depend on modules that build with the Go toolchain inside `hyperledger/fabric-ccenv:2.5`. Check with `docker run --rm hyperledger/fabric-ccenv:2.5 go version`.
- Never vendor-commit `blockchain/chaincode/**/vendor/` (the deploy script generates it).

## 7. Secrets hygiene

- `.env`, key stores, `*.pem`, `msp/`, `tls/`, `keystore/` are git-ignored. Do not force-add them.
- Never print keys or secrets in logs, tests or demos. Use fingerprints (`publicKeyId`).
- The repository contains no private keys. The ML-DSA test vector deliberately publishes how its test-only key is derived, for reproducibility. Never reuse that key.

## 8. Definition of done (per PR)

- Tests for the change, and the module's whole test suite green.
- Docs updated when behaviour or interfaces change (module README, and the contract if shared).
- No secrets, no generated artifacts, no unrelated reformatting.
