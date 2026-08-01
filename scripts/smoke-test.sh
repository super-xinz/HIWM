#!/bin/sh
set -eu

BASE_URL="${1:-http://127.0.0.1:8283}"
BASE_URL="${BASE_URL%/}"
ACCESS_CODE="${DEMO_ACCESS_CODE:-}"
STAMP="$(date +%s)"
USER_ID="smoke-${STAMP}"
SESSION_ID="smoke-session-${STAMP}"
TURN_ID="smoke-turn-${STAMP}"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

echo "[1/5] aggregate health"
curl -fsS "$BASE_URL/api/health" | python -c 'import json,sys; d=json.load(sys.stdin); assert d["services"]["application"] == "ok"'

if [ -n "$ACCESS_CODE" ]; then
  echo "[2/5] server-side access login"
  LOGIN_BODY="$(python -c 'import json,os; print(json.dumps({"code":os.environ["DEMO_ACCESS_CODE"]}))')"
  curl -fsS -c "$COOKIE_JAR" -H 'Content-Type: application/json' -d "$LOGIN_BODY" "$BASE_URL/api/v1/access/login" >/dev/null
else
  echo "[2/5] access login skipped (DEMO_ACCESS_CODE empty)"
fi

echo "[3/5] read or initialize profile"
PROFILE_BEFORE="$(curl -fsS -b "$COOKIE_JAR" "$BASE_URL/api/v1/companion/profile/$USER_ID")"
BEFORE_VERSION="$(printf '%s' "$PROFILE_BEFORE" | python -c 'import json,sys; print(json.load(sys.stdin)["profile"]["profile_version"])')"

echo "[4/5] complete profile-aware chat"
CHAT_BODY="$(USER_ID="$USER_ID" SESSION_ID="$SESSION_ID" TURN_ID="$TURN_ID" python -c 'import json,os; print(json.dumps({"user_id":os.environ["USER_ID"],"session_id":os.environ["SESSION_ID"],"turn_id":os.environ["TURN_ID"],"message":"以后回答请简短一点，我最近在准备一个重要决定。","profile_enabled":True},ensure_ascii=False))')"
CHAT_RESPONSE="$(curl -fsS -b "$COOKIE_JAR" -H 'Content-Type: application/json' -d "$CHAT_BODY" "$BASE_URL/api/v1/companion/chat")"
printf '%s' "$CHAT_RESPONSE" | python -c 'import json,sys; d=json.load(sys.stdin); assert d["reply"] and d["turn_id"]; assert d["profile_update"]["status"] == "updated"'

echo "[5/5] verify persisted messages and refreshed profile"
curl -fsS -b "$COOKIE_JAR" "$BASE_URL/api/v1/companion/sessions/$SESSION_ID/messages" | python -c 'import json,sys; d=json.load(sys.stdin); assert len(d["messages"]) == 2'
curl -fsS -b "$COOKIE_JAR" "$BASE_URL/api/v1/companion/profile/$USER_ID" | python -c 'import json,sys; assert json.load(sys.stdin)["profile"]["profile_version"] > int(sys.argv[1])' "$BEFORE_VERSION"
echo "Smoke test passed: user=$USER_ID"
