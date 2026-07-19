#!/usr/bin/env bash
set -euo pipefail

# Prevent a newly-created credential file from being briefly world/group
# readable; an existing file is tightened explicitly after the copy guard.
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
CONFIG_FILE="${HIWM_CONFIG:-${OPEN_AVATAR_CHAT_CONFIG:-config/chat_with_hiwm_mac.yaml}}"
HOST="${HIWM_HOST:-${OPEN_AVATAR_CHAT_HOST:-127.0.0.1}}"
PORT="${HIWM_PORT:-${OPEN_AVATAR_CHAT_PORT:-8283}}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python environment missing. Run: bash scripts/setup_macos.sh" >&2
  exit 1
fi

cd "$ROOT_DIR"
if [[ ! -f .env ]]; then
  cp .env.example .env
fi
chmod 600 .env

# Cloud handlers validate that a key is non-empty at boot. A local sentinel
# lets the UI, local perception, and health endpoints start before the user
# adds a real key. It cannot authorize an API request and is never persisted.
if ! grep -Eq '^DASHSCOPE_API_KEY=.+$' .env; then
  export DASHSCOPE_API_KEY="NOT_CONFIGURED_YET"
  echo "Warning: DASHSCOPE_API_KEY is blank; UI-only bootstrap mode." >&2
fi

exec "$PYTHON_BIN" src/demo.py \
  --config "$CONFIG_FILE" \
  --host "$HOST" \
  --port "$PORT"
