#!/usr/bin/env bash
# Stop the test network and remove its containers, volumes and generated
# crypto material. Ledger data is destroyed.
set -euo pipefail
source "$(dirname "$0")/common.sh"

[ -x "$TEST_NETWORK_DIR/network.sh" ] || die "test network not installed"
cd "$TEST_NETWORK_DIR"
log "Stopping test network"
./network.sh down
rm -rf "$CHAINCODE_PATH/vendor"
