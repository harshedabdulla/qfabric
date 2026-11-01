# QFabric Frontend (optional, deferred)

**Do not start until both backend modules work end to end** (`scripts/run-demo.sh` passes).

Planned stack: Next.js + Tailwind CSS.

Planned views:

1. **Transfer**: pick sender/receiver, upload a document, toggle the eavesdropper, run `POST /api/v1/secure-transfer`.
2. **BB84 visualizer**: bases, sifting, QBER vs threshold, abort reason (from `/bb84/execute`).
3. **Audit ledger**: table of `GetAllTransactions` with `VERIFIED`/`REJECTED` badges, and a "re-verify" button calling `VerifyTransactionRecord`.
4. **Benchmarks**: charts from `benchmarks/*/results`.

The browser cannot talk to Fabric directly. A thin backend-for-frontend (the Go client exposed over HTTP, or a Next.js API route calling it) will relay ledger queries. Define that API in `docs/API_CONTRACT.md` before building it.
