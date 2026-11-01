# Contributing to QFabric

Two developers work in parallel on strictly separated modules. These rules keep them out of each other's way.

## Rules

1. **Each developer works on their own feature branch.** Branch from `dev` and open PRs into `dev`. `main` only receives demo-ready merges from `dev`.
2. **Quantum/PQC changes belong in `quantum-pqc/`.** Owner: Developer 2.
3. **Blockchain changes belong in `blockchain/`.** Owner: Developer 1.
4. **Don't modify the other developer's module**, except for integration fixes both developers agreed on. Note the agreement in the PR.
5. **Shared API changes must be discussed before merging.** That covers `docs/API_CONTRACT.md`, `integration/**`, `quantum-pqc/api/schemas.py`, `blockchain/integration/metadata.go`, the canonical manifest, and the chaincode ledger policy. Such PRs need **both** approvals (see [docs/INTEGRATION_GUIDE.md §5](docs/INTEGRATION_GUIDE.md#5-change-management)).
6. **No private keys or secrets in Git.** That includes `.env`, key stores, Fabric `msp/`/`tls/` material, `*.pem`/`*.key`, BB84 secrets, AES keys, and real documents. If something leaks, rotate it and rewrite history before pushing further.
7. **All modules must have their own tests.** `pytest` in `quantum-pqc/`. `go test ./...` in `blockchain/` and `blockchain/chaincode/qfabric-audit/`. PRs keep them green.
8. **Update documentation whenever an interface changes:** the module README, `docs/API_CONTRACT.md`, and the samples and test vector if affected.

## Branches

```
main
dev
feature/bb84
feature/mldsa
feature/secure-encryption
feature/fabric-network
feature/chaincode
feature/integration
```

## Workflow

```bash
git checkout dev && git pull
git checkout -b feature/<topic>
# work, commit often
git fetch origin && git rebase origin/dev
git push -u origin feature/<topic>      # open a PR into dev
```

Commit messages: `type(scope): summary`, for example `feat(bb84): intercept-resend eavesdropper`, `fix(chaincode): reject replayed sessionId`, `docs(contract): add abortReason`. Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `perf`.

## Pull request checklist

- [ ] Changes are confined to my module (or the contract change is agreed and flagged)
- [ ] Tests added or updated and passing locally
- [ ] Docs updated for any behaviour or interface change
- [ ] No secrets, generated artifacts (`vendor/`, `fabric-samples/`, `.venv/`) or real documents committed
- [ ] README status table updated only for features that actually work

## Code style

- Python: type hints, small pure functions, `ruff`/`black` defaults. Never log secrets.
- Go: `gofmt`, `go vet`. Chaincode must be deterministic: no `time.Now()`, no randomness, no output that depends on map iteration order.
