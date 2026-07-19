#!/bin/sh
set -eu

PORT="${PORT:-8080}"
CONFIG_FILE="${HIWM_CONFIG:-config/chat_with_hiwm_zeabur.yaml}"

# The cloud handlers require a non-empty value while loading. This sentinel
# starts the UI without granting provider access; the real key is supplied by
# the user from the one-step setup page and remains process-memory only.
if [ -z "${DASHSCOPE_API_KEY:-}" ]; then
  export DASHSCOPE_API_KEY="NOT_CONFIGURED_YET"
fi

exec python src/demo.py \
  --config "$CONFIG_FILE" \
  --host 0.0.0.0 \
  --port "$PORT"
