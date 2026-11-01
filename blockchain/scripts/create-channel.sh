#!/usr/bin/env bash
# Create the application channel and join both orgs' peers.
set -euo pipefail
source "$(dirname "$0")/common.sh"

[ -x "$TEST_NETWORK_DIR/network.sh" ] || die "test network not installed; run ./scripts/start-network.sh"
cd "$TEST_NETWORK_DIR"
log "Creating channel $CHANNEL_NAME"
./network.sh createChannel -c "$CHANNEL_NAME"
