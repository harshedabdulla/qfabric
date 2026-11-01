#!/usr/bin/env bash
# End-to-end QFabric demo (Phase 3+). Requires both modules implemented.
#
#   1. crypto service up (Docker) and healthy
#   2. Fabric test network up, chaincode deployed
#   3. OrgA and OrgB register ML-DSA public keys on the ledger
#   4. Honest transfer      -> BB84 SUCCESS  -> ledger VERIFIED
#   5. Eavesdropped transfer -> BB84 ABORTED -> ledger REJECTED
#   6. Audit history + independent re-verification
#
#   ./scripts/run-demo.sh [document]     (default: integration sample PO)
#   SKIP_INFRA=1 ./scripts/run-demo.sh   (services already running)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API="${QFABRIC_CRYPTO_API_URL:-http://localhost:8000/api/v1}"
DOC="${1:-}"
step() { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

if [ -z "$DOC" ]; then
  DOC="$(mktemp -t qfabric-doc.XXXXXX)"
  trap 'rm -f "$DOC"' EXIT
  python3 -c "import json,base64,sys; sys.stdout.buffer.write(base64.b64decode(json.load(open('$ROOT/integration/sample_request.json'))['document']))" > "$DOC"
fi

if [ -z "${SKIP_INFRA:-}" ]; then
  step "Starting crypto service"
  (cd "$ROOT" && docker compose up --build -d crypto)
  step "Starting Fabric network and deploying chaincode"
  "$ROOT/blockchain/scripts/start-network.sh"
  "$ROOT/blockchain/scripts/deploy-chaincode.sh"
fi

step "Waiting for crypto service at $API"
for _ in $(seq 1 30); do
  curl -sf "$API/health" >/dev/null && break
  sleep 2
done
curl -sf "$API/health" >/dev/null || { echo "crypto service not healthy" >&2; exit 1; }

cd "$ROOT/blockchain"
RUN_ID="$(date +%s)"

step "Registering organizations (ML-DSA-65 public keys -> ledger)"
QFABRIC_ORG=OrgA go run ./client register
QFABRIC_ORG=OrgB go run ./client register

step "Honest transfer OrgA -> OrgB (expect VERIFIED)"
QFABRIC_ORG=OrgA go run ./client transfer -to OrgB -file "$DOC" -tx "qfabric-tx-$RUN_ID-ok"

step "Transfer with intercept-resend eavesdropper (expect REJECTED)"
QFABRIC_ORG=OrgA go run ./client transfer -to OrgB -file "$DOC" -eve -tx "qfabric-tx-$RUN_ID-eve"

step "Audit history"
go run ./client list

step "Independent re-verification of the honest transfer"
go run ./client verify "qfabric-tx-$RUN_ID-ok"
