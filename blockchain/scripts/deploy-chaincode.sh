#!/usr/bin/env bash
# Package, install, approve and commit the qfabric-audit Go chaincode.
#   ./scripts/deploy-chaincode.sh             # first deploy (v1.0, seq 1); no-op if already deployed
#   ./scripts/deploy-chaincode.sh upgrade     # redeploy current code as the next sequence
#   ./scripts/deploy-chaincode.sh 1.3 3       # explicit version and sequence
# Default endorsement policy: majority of channel members, i.e. both OrgA and
# OrgB peers execute the chaincode and both independently verify ML-DSA.
set -euo pipefail
source "$(dirname "$0")/common.sh"

require go
[ -x "$TEST_NETWORK_DIR/network.sh" ] || die "test network not installed; run ./scripts/start-network.sh"
network_running || die "network is not running; run ./scripts/start-network.sh"

CURRENT_SEQ="$(committed_sequence || true)"
case "${1:-}" in
  "")
    if [ -n "$CURRENT_SEQ" ]; then
      log "$CHAINCODE_NAME already deployed (version $(committed_version), sequence $CURRENT_SEQ). Nothing to do."
      log "After changing chaincode code, run: ./scripts/deploy-chaincode.sh upgrade"
      exit 0
    fi
    CC_VERSION="1.0"; CC_SEQUENCE=1 ;;
  upgrade)
    [ -n "$CURRENT_SEQ" ] || die "nothing deployed yet; run ./scripts/deploy-chaincode.sh"
    CC_SEQUENCE=$((CURRENT_SEQ + 1)); CC_VERSION="1.$((CURRENT_SEQ))" ;;
  *)
    CC_VERSION="$1"; CC_SEQUENCE="${2:?usage: deploy-chaincode.sh <version> <sequence>}"
    if [ -n "$CURRENT_SEQ" ] && [ "$CC_SEQUENCE" -le "$CURRENT_SEQ" ]; then
      die "sequence must be > committed sequence $CURRENT_SEQ (try: ./scripts/deploy-chaincode.sh upgrade)"
    fi ;;
esac

log "Running chaincode unit tests before deploy"
(cd "$CHAINCODE_PATH" && go test ./...)

cd "$TEST_NETWORK_DIR"
log "Deploying $CHAINCODE_NAME v$CC_VERSION (sequence $CC_SEQUENCE) to $CHANNEL_NAME"
./network.sh deployCC -c "$CHANNEL_NAME" -ccn "$CHAINCODE_NAME" -ccp "$CHAINCODE_PATH" \
  -ccl go -ccv "$CC_VERSION" -ccs "$CC_SEQUENCE"
