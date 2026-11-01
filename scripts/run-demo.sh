#!/usr/bin/env bash
# End-to-end QFabric demo.
#
#   1. crypto service up and healthy (real Docker service, or the mock)
#   2. Fabric test network up, chaincode deployed
#   3. OrgA and OrgB register ML-DSA public keys on the ledger
#   4. Honest transfer       -> BB84 SUCCESS -> ledger VERIFIED
#   5. Eavesdropped transfer -> BB84 ABORTED -> ledger REJECTED
#   6. Audit history + independent re-verification
#   7. Replay / tamper / wrong-MSP attacks -> all refused
#
#   ./scripts/run-demo.sh [document]     (default: integration sample PO)
#   MOCK_CRYPTO=1 ./scripts/run-demo.sh  use blockchain/tools/mockcrypto (BB84 numbers simulated)
#   SKIP_INFRA=1 ./scripts/run-demo.sh   network, chaincode and crypto service already running
#
# Organizations can be registered only once per network. Re-running against
# the same network skips registration if the orgs already exist.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API="${QFABRIC_CRYPTO_API_URL:-http://localhost:8000/api/v1}"
DOC="${1:-}"
if [ -n "$DOC" ]; then
  [ -f "$DOC" ] || { echo "document not found: $DOC" >&2; exit 1; }
  DOC="$(cd "$(dirname "$DOC")" && pwd)/$(basename "$DOC")"   # script changes directory later
fi
MOCK_PID=""
step() { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

cleanup() {
  [ -n "$MOCK_PID" ] && kill "$MOCK_PID" 2>/dev/null || true
  [ -n "${TMP_DOC:-}" ] && rm -f "$TMP_DOC"
  [ -n "${REG_ERR:-}" ] && rm -f "$REG_ERR"
  return 0
}
trap cleanup EXIT

if [ -z "$DOC" ]; then
  TMP_DOC="$(mktemp -t qfabric-doc.XXXXXX)"
  DOC="$TMP_DOC"
  python3 -c "import json,base64,sys; sys.stdout.buffer.write(base64.b64decode(json.load(open('$ROOT/integration/sample_request.json'))['document']))" > "$DOC"
fi

if [ -n "${MOCK_CRYPTO:-}" ]; then
  if ! curl -sf "$API/health" >/dev/null; then
    step "Starting MOCK crypto service (real ML-DSA/AES-GCM, simulated BB84 statistics)"
    (cd "$ROOT/blockchain" && go build -o "${TMPDIR:-/tmp}/qfabric-mockcrypto" ./tools/mockcrypto)
    "${TMPDIR:-/tmp}/qfabric-mockcrypto" -addr 127.0.0.1:8000 >/dev/null 2>&1 &
    MOCK_PID=$!
  fi
elif [ -z "${SKIP_INFRA:-}" ]; then
  step "Starting crypto service"
  (cd "$ROOT" && docker compose up --build -d crypto)
fi

if [ -z "${SKIP_INFRA:-}" ]; then
  if docker ps --format '{{.Names}}' | grep -q '^peer0.org1.example.com$'; then
    step "Fabric network already running"
  else
    step "Starting Fabric network and deploying chaincode"
    "$ROOT/blockchain/scripts/start-network.sh"
    "$ROOT/blockchain/scripts/deploy-chaincode.sh"
  fi
fi

step "Waiting for crypto service at $API"
for _ in $(seq 1 30); do
  curl -sf "$API/health" >/dev/null && break
  sleep 1
done
curl -sf "$API/health" || { echo "crypto service not healthy" >&2; exit 1; }
echo

cd "$ROOT/blockchain"
go build -o "${TMPDIR:-/tmp}/qfabric-client" ./client
CLIENT="${TMPDIR:-/tmp}/qfabric-client"
RUN_ID="$(date +%s)"

step "Registering organizations (ML-DSA-65 public keys -> ledger)"
REG_ERR="$(mktemp -t qfabric-register.XXXXXX)"
for org in OrgA OrgB; do
  if QFABRIC_ORG=$org "$CLIENT" register 2>"$REG_ERR"; then :
  elif grep -q "already registered" "$REG_ERR"; then echo "$org already registered on the ledger"
  else cat "$REG_ERR" >&2; exit 1
  fi
done

step "Honest transfer OrgA -> OrgB (expect VERIFIED)"
QFABRIC_ORG=OrgA "$CLIENT" transfer -to OrgB -file "$DOC" -tx "qfabric-tx-$RUN_ID-ok"

step "Transfer with intercept-resend eavesdropper (expect REJECTED)"
QFABRIC_ORG=OrgA "$CLIENT" transfer -to OrgB -file "$DOC" -eve -tx "qfabric-tx-$RUN_ID-eve"

step "Audit history"
"$CLIENT" list

step "Independent re-verification of the honest transfer"
"$CLIENT" verify "qfabric-tx-$RUN_ID-ok"

step "Attack scenarios against the honest record"
"$ROOT/blockchain/scripts/attack-scenarios.sh" "qfabric-tx-$RUN_ID-ok"
