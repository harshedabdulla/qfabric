#!/usr/bin/env bash
# Package, install, approve and commit the qfabric-audit Go chaincode.
#   ./scripts/deploy-chaincode.sh                 # version 1.0, sequence 1
#   ./scripts/deploy-chaincode.sh 1.1 2           # upgrade: bump version AND sequence
# Default endorsement policy: majority of channel members, i.e. both OrgA and
# OrgB peers execute the chaincode and both independently verify ML-DSA.
set -euo pipefail
source "$(dirname "$0")/common.sh"

CC_VERSION="${1:-1.0}"
CC_SEQUENCE="${2:-1}"

require go
[ -x "$TEST_NETWORK_DIR/network.sh" ] || die "test network not installed; run ./scripts/start-network.sh"

log "Running chaincode unit tests before deploy"
(cd "$CHAINCODE_PATH" && go test ./...)

cd "$TEST_NETWORK_DIR"
log "Deploying $CHAINCODE_NAME v$CC_VERSION (sequence $CC_SEQUENCE) to $CHANNEL_NAME"
./network.sh deployCC -c "$CHANNEL_NAME" -ccn "$CHAINCODE_NAME" -ccp "$CHAINCODE_PATH" \
  -ccl go -ccv "$CC_VERSION" -ccs "$CC_SEQUENCE"
