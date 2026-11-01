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
