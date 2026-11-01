#!/usr/bin/env bash
# Reset QFabric to a clean demo state: destroys the ledger AND the crypto
# service's ML-DSA keys together (they must always be reset as a pair), then
# starts everything again with the chaincode deployed and nothing registered.
# Afterwards, start the walkthrough at docs/DEMO.md step 2.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Stopping Fabric network (ledger destroyed) and crypto service (keys destroyed)"
./blockchain/scripts/stop-network.sh >/dev/null 2>&1 || true
docker compose down -v >/dev/null 2>&1 || true

echo "==> Starting crypto service"
docker compose up -d crypto
echo "==> Starting Fabric network and deploying chaincode"
./blockchain/scripts/start-network.sh
./blockchain/scripts/deploy-chaincode.sh

for _ in $(seq 1 60); do curl -sf localhost:8000/api/v1/health >/dev/null && break; sleep 1; done
curl -sf localhost:8000/api/v1/health >/dev/null || { echo "crypto service not healthy" >&2; exit 1; }
echo "==> Clean demo state ready. Continue with docs/DEMO.md step 2."
