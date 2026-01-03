#!/usr/bin/env bash
set -euo pipefail

# SSH alias（~/.ssh/config の Host 名）
SSH_HOST="atm9"

# CC computer の保存先（現状は 1 固定でOK）
REMOTE_DIR="/opt/minecraft_atm9_server/world/computercraft/computer/1"

# ローカルの CC コード
LOCAL_CC_DIR="./cc"

echo "== Deploy CC code to ${SSH_HOST}:${REMOTE_DIR} =="

# cc/ 以下を同期（差分のみ）
rsync -az --delete --exclude 'startup.lua' \
  -e "ssh" \
  "${LOCAL_CC_DIR}/" \
  "${SSH_HOST}:${REMOTE_DIR}/cc/"

# startup.lua は computer 直下
if [ -f "${LOCAL_CC_DIR}/startup.lua" ]; then
  rsync -az -e "ssh" \
    "${LOCAL_CC_DIR}/startup.lua" \
    "${SSH_HOST}:${REMOTE_DIR}/startup.lua"
else
  echo "== startup.lua not found, skipped =="
fi

echo "== Done. In-game: reboot =="
