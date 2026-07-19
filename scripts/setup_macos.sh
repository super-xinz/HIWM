#!/usr/bin/env bash
set -euo pipefail

# Keep any credential-bearing files created by this script private from the
# moment they are created. Existing .env files are tightened explicitly below.
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="$ROOT_DIR/.tools"
UV_BIN="$TOOLS_DIR/bin/uv"

mkdir -p "$TOOLS_DIR/bin" "$TOOLS_DIR/cache" "$TOOLS_DIR/python"

if [[ ! -x "$UV_BIN" ]]; then
  INSTALLER="$TOOLS_DIR/uv-install.sh"
  curl -LsSf https://astral.sh/uv/install.sh -o "$INSTALLER"
  env UV_INSTALL_DIR="$TOOLS_DIR/bin" sh "$INSTALLER"
fi

export UV_CACHE_DIR="$TOOLS_DIR/cache"
export UV_PYTHON_INSTALL_DIR="$TOOLS_DIR/python"
export PATH="$TOOLS_DIR/bin:$PATH"

cd "$ROOT_DIR"
"$UV_BIN" python install 3.11
"$UV_BIN" sync --locked --python 3.11
"$UV_BIN" run --locked install.py --config config/chat_with_hiwm_mac.yaml

FRONTEND_DIR="$ROOT_DIR/frontend"
if command -v pnpm >/dev/null 2>&1; then
  (
    cd "$FRONTEND_DIR"
    pnpm install --frozen-lockfile
    pnpm run build
  )
elif command -v corepack >/dev/null 2>&1; then
  (
    cd "$FRONTEND_DIR"
    corepack pnpm install --frozen-lockfile
    corepack pnpm run build
  )
else
  echo "Warning: Node.js/pnpm not found; frontend source was not rebuilt." >&2
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
fi
chmod 600 .env

echo "macOS setup complete. Start the service and enter your API Key on the setup page."
