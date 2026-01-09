#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
WORLD_ID="${WORLD_ID:-atm9}"
TS="${TS:-1767859999.0}"
RAW_NAME="${RAW_NAME:-minecraft:stone}"
AMOUNT="${AMOUNT:-999}"

echo "POST $BASE_URL/ingest (world_id=$WORLD_ID ts=$TS $RAW_NAME=$AMOUNT)"
curl -sS -X POST "$BASE_URL/ingest" \
  -H 'content-type: application/json' \
  -d "$(cat <<JSON
{
  "ts": $TS,
  "world_id": "$WORLD_ID",
  "entries": [
    {"kind":"item","raw_name":"$RAW_NAME","amount": $AMOUNT}
  ]
}
JSON
)" | jq .
