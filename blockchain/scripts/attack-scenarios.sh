#!/usr/bin/env bash
# Demonstrates that the live chaincode refuses forged and replayed audit
# submissions. Takes an existing VERIFIED record sent by OrgA and tries:
#   1. replay   - same signed manifest under a new transactionId
#   2. tamper   - lower the QBER (and change the session) without re-signing
#   3. wrong MSP - OrgB's Fabric identity submits OrgA's transfer
# Every attempt must fail endorsement; the ledger must stay unchanged.
#
#   ./scripts/attack-scenarios.sh qfabric-tx-001
set -euo pipefail
source "$(dirname "$0")/common.sh"

TX="${1:?usage: attack-scenarios.sh <transactionId of a VERIFIED OrgA record>}"
require jq
cd "$TEST_NETWORK_DIR"
export PATH="$FABRIC_SAMPLES_DIR/bin:$PATH" FABRIC_CFG_PATH="$FABRIC_SAMPLES_DIR/config" VERBOSE=false
set +u  # fabric-samples envVar.sh is not nounset-safe
# shellcheck disable=SC1091
. scripts/envVar.sh

ORDERER=(-o localhost:7050 --ordererTLSHostnameOverride orderer.example.com --tls --cafile "$ORDERER_CA")
PEERS=(--peerAddresses localhost:7051 --tlsRootCertFiles "$PEER0_ORG1_CA"
       --peerAddresses localhost:9051 --tlsRootCertFiles "$PEER0_ORG2_CA")

query() { peer chaincode query -C "$CHANNEL_NAME" -n "$CHAINCODE_NAME" -c "$1"; }

# expect_refused <org number> <label> <expected error substring> <tx id> <manifest json> <signature>
expect_refused() {
  local org="$1" label="$2" want="$3" args out
  setGlobals "$org"
  args=$(jq -nc --arg t "$4" --arg m "$5" --arg s "$6" '{function:"RecordSecureTransaction",Args:[$t,$m,$s]}')
  if out=$(peer chaincode invoke "${ORDERER[@]}" -C "$CHANNEL_NAME" -n "$CHAINCODE_NAME" "${PEERS[@]}" -c "$args" 2>&1); then
    die "$label: ACCEPTED (expected refusal)"
  elif grep -q "$want" <<<"$out"; then
    log "$label: refused ✔  ($want)"
  else
    die "$label: refused for an unexpected reason: $(grep -o 'message:.*' <<<"$out" | head -1)"
  fi
}

setGlobals 1
RECORD=$(query "$(jq -nc --arg t "$TX" '{function:"GetTransaction",Args:[$t]}')")
[ "$(jq -r .securityStatus <<<"$RECORD")" = VERIFIED ] || die "$TX is not a VERIFIED record"
[ "$(jq -r .manifest.sender <<<"$RECORD")" = OrgA ] || die "$TX must be sent by OrgA"
MANIFEST=$(jq -c .manifest <<<"$RECORD")
SIG=$(jq -r .signature <<<"$RECORD")
BEFORE=$(query '{"function":"GetAllTransactions","Args":[]}' | jq length)
SUFFIX=$(date +%s)

expect_refused 1 "replay"    "already recorded" \
  "attack-replay-$SUFFIX" "$MANIFEST" "$SIG"
expect_refused 1 "tamper"    "signature verification failed" \
  "attack-tamper-$SUFFIX" "$(jq -c '.qberPpm=0 | .sessionId+="-forged"' <<<"$MANIFEST")" "$SIG"
expect_refused 2 "wrong MSP" "submitter MSP Org2MSP" \
  "attack-msp-$SUFFIX" "$(jq -c '.sessionId+="-msp"' <<<"$MANIFEST")" "$SIG"

setGlobals 1
AFTER=$(query '{"function":"GetAllTransactions","Args":[]}' | jq length)
[ "$BEFORE" = "$AFTER" ] || die "ledger changed: $BEFORE -> $AFTER records"
log "all attacks refused; ledger unchanged ($AFTER records)"
