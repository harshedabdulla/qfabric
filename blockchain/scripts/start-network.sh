#!/usr/bin/env bash
# Start the Fabric test network with two orgs (OrgA=Org1MSP Manufacturer,
# OrgB=Org2MSP Supplier), using Fabric CAs, then create the channel.
#   ./scripts/start-network.sh            # up + channel
#   ./scripts/start-network.sh --no-channel
set -euo pipefail
source "$(dirname "$0")/common.sh"

ensure_fabric_samples
cd "$TEST_NETWORK_DIR"
log "Starting test network (state DB: $STATE_DB)"
./network.sh up -ca -s "$STATE_DB"

if [ "${1:-}" != "--no-channel" ]; then
  "$BLOCKCHAIN_DIR/scripts/create-channel.sh"
fi
log "Network up. Next: ./scripts/deploy-chaincode.sh"
