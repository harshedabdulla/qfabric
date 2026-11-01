#!/usr/bin/env bash
# Shared settings for blockchain/scripts/*. Source, do not execute.
# Override any value via environment or blockchain/.env.

BLOCKCHAIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$BLOCKCHAIN_DIR/.env" ] && set -a && . "$BLOCKCHAIN_DIR/.env" && set +a

FABRIC_VERSION="${FABRIC_VERSION:-2.5.16}"
FABRIC_CA_VERSION="${FABRIC_CA_VERSION:-1.5.22}"
NETWORK_DIR="$BLOCKCHAIN_DIR/network"
FABRIC_SAMPLES_DIR="${FABRIC_SAMPLES_DIR:-$NETWORK_DIR/fabric-samples}"
TEST_NETWORK_DIR="${QFABRIC_TEST_NETWORK_DIR:-$FABRIC_SAMPLES_DIR/test-network}"
CHANNEL_NAME="${QFABRIC_CHANNEL:-mychannel}"
CHAINCODE_NAME="${QFABRIC_CHAINCODE:-qfabric-audit}"
CHAINCODE_PATH="$BLOCKCHAIN_DIR/chaincode/qfabric-audit"
STATE_DB="${FABRIC_STATE_DB:-leveldb}"   # leveldb | couchdb

log() { printf '\033[1;34m[qfabric]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[qfabric]\033[0m %s\n' "$*" >&2; exit 1; }

require() {
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || die "missing prerequisite: $cmd"
  done
}

# Download fabric-samples, Fabric binaries and Docker images (pinned) into
# blockchain/network/fabric-samples (git-ignored) if not present yet.
ensure_fabric_samples() {
  require docker curl git
  docker info >/dev/null 2>&1 || die "Docker daemon is not running"
  if [ -x "$TEST_NETWORK_DIR/network.sh" ] && [ -x "$FABRIC_SAMPLES_DIR/bin/peer" ]; then
    return
  fi
  log "Installing Fabric $FABRIC_VERSION / CA $FABRIC_CA_VERSION samples, binaries and images"
  mkdir -p "$NETWORK_DIR"
  (
    cd "$NETWORK_DIR"
    curl -sSfL -o install-fabric.sh \
      "https://raw.githubusercontent.com/hyperledger/fabric/v${FABRIC_VERSION}/scripts/install-fabric.sh"
    chmod +x install-fabric.sh
    ./install-fabric.sh --fabric-version "$FABRIC_VERSION" --ca-version "$FABRIC_CA_VERSION" docker samples binary
  )
}

network_running() {
  docker ps --format '{{.Names}}' | grep -q '^peer0.org1.example.com$'
}

# Run a `peer` CLI command as org 1 or 2 (subshell: does not leak env).
# Usage: as_peer 1 peer channel list
as_peer() {
  local org="$1"; shift
  (
    cd "$TEST_NETWORK_DIR"
    export PATH="$FABRIC_SAMPLES_DIR/bin:$PATH" FABRIC_CFG_PATH="$FABRIC_SAMPLES_DIR/config" VERBOSE=false
    set +u  # fabric-samples envVar.sh is not nounset-safe
    # shellcheck disable=SC1091
    . scripts/envVar.sh >/dev/null 2>&1
    setGlobals "$org" >/dev/null 2>&1
    "$@"
  )
}

channel_joined() {
  as_peer 1 peer channel list 2>/dev/null | grep -qx "$CHANNEL_NAME"
}

# Prints the committed chaincode sequence, or nothing if not committed.
committed_sequence() {
  as_peer 1 peer lifecycle chaincode querycommitted -C "$CHANNEL_NAME" -n "$CHAINCODE_NAME" 2>/dev/null \
    | sed -n 's/.*Sequence: \([0-9]*\),.*/\1/p'
}

committed_version() {
  as_peer 1 peer lifecycle chaincode querycommitted -C "$CHANNEL_NAME" -n "$CHAINCODE_NAME" 2>/dev/null \
    | sed -n 's/.*Version: \([^,]*\),.*/\1/p'
}
