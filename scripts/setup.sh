#!/usr/bin/env bash
# QFabric developer setup.
#   ./scripts/setup.sh              # check prerequisites, set up both modules
#   ./scripts/setup.sh crypto       # Quantum/PQC developer only
#   ./scripts/setup.sh blockchain   # Blockchain developer only
#   ./scripts/setup.sh blockchain --fabric   # also download Fabric samples/binaries/images
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-all}"
FETCH_FABRIC="${2:-}"

log()  { printf '\033[1;34m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[setup]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[setup]\033[0m %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

copy_env() {
  local dir="$1"
  if [ -f "$dir/.env.example" ] && [ ! -f "$dir/.env" ]; then
    cp "$dir/.env.example" "$dir/.env"
    log "created ${dir#"$ROOT"/}/.env from .env.example"
  fi
}

setup_crypto() {
  log "Quantum/PQC module"
  local py=""
  for candidate in python3.12 python3.13 python3.11; do
    if have "$candidate"; then py="$candidate"; break; fi
  done
  [ -n "$py" ] || die "Python 3.11-3.13 required (3.12 recommended); Qiskit wheels may not exist for newer versions"
  cd "$ROOT/quantum-pqc"
  if [ ! -d .venv ]; then
    log "creating quantum-pqc/.venv with $py"
    "$py" -m venv .venv
  fi
  .venv/bin/python -m pip install --quiet --upgrade pip

  # Qiskit is built from the vendored source in third_party/qiskit (2.6.1), not PyPI.
  [ -f third_party/qiskit/pyproject.toml ] || die "quantum-pqc/third_party/qiskit is missing"
  have cargo || die "Rust toolchain required to build Qiskit from source: https://rustup.rs"
  if ! .venv/bin/python -c "import qiskit, sys; sys.exit(0 if 'third_party' in qiskit.__file__ else 1)" 2>/dev/null; then
    log "building Qiskit from third_party/qiskit (Rust, takes a few minutes)"
    .venv/bin/python -m pip uninstall --quiet --yes qiskit 2>/dev/null || true
    .venv/bin/python -m pip install --quiet -e third_party/qiskit
  fi
  .venv/bin/python -m pip install --quiet -r requirements.txt
  copy_env "$ROOT/quantum-pqc"

  # liboqs 0.16.0 (C library for ML-DSA) is built into quantum-pqc/.oqs
  # (git-ignored) unless one is already available. mldsa/__init__.py finds it.
  if [ ! -e .oqs/lib/liboqs.dylib ] && [ ! -e .oqs/lib/liboqs.so ] && [ -z "${OQS_INSTALL_PATH:-}" ]; then
    log "building liboqs 0.16.0 into quantum-pqc/.oqs"
    .venv/bin/python -m pip install --quiet cmake ninja
    local src
    src="$(mktemp -d)"
    git clone --quiet --depth 1 --branch 0.16.0 https://github.com/open-quantum-safe/liboqs "$src/liboqs"
    .venv/bin/cmake -S "$src/liboqs" -B "$src/build" -GNinja -DCMAKE_MAKE_PROGRAM="$PWD/.venv/bin/ninja" \
      -DBUILD_SHARED_LIBS=ON -DOQS_BUILD_ONLY_LIB=ON -DCMAKE_INSTALL_PREFIX="$PWD/.oqs" >/dev/null
    .venv/bin/cmake --build "$src/build" >/dev/null
    .venv/bin/cmake --install "$src/build" >/dev/null
    rm -rf "$src"
  fi
  log "run tests: cd quantum-pqc && .venv/bin/python -m pytest"
}

setup_blockchain() {
  log "Blockchain module"
  have go || die "Go 1.25+ required"
  have docker || warn "Docker not found: required for the Fabric network"
  have jq || warn "jq not found: required by the Fabric test-network scripts (brew install jq)"
  (cd "$ROOT/blockchain" && go mod download)
  (cd "$ROOT/blockchain/chaincode/qfabric-audit" && go mod download)
  copy_env "$ROOT/blockchain"
  if [ "$FETCH_FABRIC" = "--fabric" ]; then
    # shellcheck source=../blockchain/scripts/common.sh
    source "$ROOT/blockchain/scripts/common.sh"
    ensure_fabric_samples
  else
    log "Fabric samples/binaries are downloaded on first ./blockchain/scripts/start-network.sh"
  fi
  log "run tests: cd blockchain && go test ./... && (cd chaincode/qfabric-audit && go test ./...)"
}

have git || die "git required"
copy_env "$ROOT"
case "$TARGET" in
  crypto)     setup_crypto ;;
  blockchain) setup_blockchain ;;
  all)        setup_crypto; setup_blockchain ;;
  *)          die "unknown target '$TARGET' (crypto | blockchain | all)" ;;
esac
log "done"
