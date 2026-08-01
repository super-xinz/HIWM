from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from .models import ChatRequest, ChatResponse


class DuplicateTurnError(ValueError):
    pass


def request_fingerprint(request: ChatRequest) -> str:
    payload = request.model_dump(mode="json", exclude={"frontend_context"})
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SessionStore:
    """Small SQLite session store; intentionally contains no credentials."""

    def __init__(self, database_url: str):
        parsed = urlparse(database_url)
        if parsed.scheme != "sqlite":
            raise ValueError("COMPANION_DATABASE_URL currently supports sqlite:// only")
        raw_path = unquote(parsed.path)
        if database_url.startswith("sqlite:///./"):
            path = Path(database_url.removeprefix("sqlite:///"))
        elif raw_path:
            path = Path(raw_path)
        else:
            raise ValueError("SQLite database path is missing")
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS companion_turns (
                    session_id TEXT NOT NULL,
                    turn_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    update_payload_json TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, turn_id)
                );
                CREATE TABLE IF NOT EXISTS companion_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    turn_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    model TEXT,
                    profile_version INTEGER,
                    request_id TEXT NOT NULL,
                    UNIQUE(session_id, turn_id, role)
                );
                CREATE INDEX IF NOT EXISTS idx_companion_messages_session
                    ON companion_messages(session_id, id);
                """
            )

    def health_check(self) -> bool:
        try:
            with self._lock, self._connect() as db:
                db.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False

    def cached_turn(self, request: ChatRequest) -> ChatResponse | None:
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT request_hash, response_json FROM companion_turns WHERE session_id=? AND turn_id=?",
                (request.session_id, request.turn_id),
            ).fetchone()
        if not row:
            return None
        if row["request_hash"] != request_fingerprint(request):
            raise DuplicateTurnError("同一 turn_id 不能用于不同消息")
        response = ChatResponse.model_validate_json(row["response_json"])
        return response.model_copy(update={"cached": True})

    def save_turn(
        self,
        request: ChatRequest,
        response: ChatResponse,
        update_payload: dict | None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT request_hash FROM companion_turns WHERE session_id=? AND turn_id=?",
                (request.session_id, request.turn_id),
            ).fetchone()
            fingerprint = request_fingerprint(request)
            if existing:
                if existing["request_hash"] != fingerprint:
                    raise DuplicateTurnError("同一 turn_id 不能用于不同消息")
                db.rollback()
                return
            db.execute(
                "INSERT INTO companion_turns VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    request.session_id,
                    request.turn_id,
                    request.user_id,
                    fingerprint,
                    response.model_dump_json(),
                    json.dumps(update_payload, ensure_ascii=False) if update_payload else None,
                    now,
                ),
            )
            rows = (
                ("user", request.message, None),
                ("assistant", response.reply, response.model),
            )
            for role, content, model in rows:
                db.execute(
                    """INSERT INTO companion_messages
                    (session_id,user_id,turn_id,role,content,created_at,model,profile_version,request_id)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        request.session_id,
                        request.user_id,
                        request.turn_id,
                        role,
                        content,
                        now,
                        model,
                        response.profile_update.profile_version,
                        response.request_id,
                    ),
                )
            db.commit()

    def messages(self, session_id: str, limit: int = 100) -> list[dict]:
        limit = max(1, min(limit, 200))
        with self._lock, self._connect() as db:
            rows = db.execute(
                """SELECT session_id,user_id,turn_id,role,content,created_at,model,
                          profile_version,request_id
                   FROM companion_messages WHERE session_id=? ORDER BY id DESC LIMIT ?""",
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def pending_update(self, session_id: str, turn_id: str) -> dict | None:
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT update_payload_json FROM companion_turns WHERE session_id=? AND turn_id=?",
                (session_id, turn_id),
            ).fetchone()
        return json.loads(row["update_payload_json"]) if row and row["update_payload_json"] else None

    def replace_response(self, response: ChatResponse) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE companion_turns SET response_json=? WHERE session_id=? AND turn_id=?",
                (response.model_dump_json(), response.session_id, response.turn_id),
            )
            db.execute(
                """UPDATE companion_messages SET profile_version=?
                   WHERE session_id=? AND turn_id=?""",
                (
                    response.profile_update.profile_version,
                    response.session_id,
                    response.turn_id,
                ),
            )
            db.commit()

    def clear_session(self, session_id: str) -> None:
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM companion_messages WHERE session_id=?", (session_id,))
            db.execute("DELETE FROM companion_turns WHERE session_id=?", (session_id,))
            db.commit()

    def clear_user(self, user_id: str) -> None:
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM companion_messages WHERE user_id=?", (user_id,))
            db.execute("DELETE FROM companion_turns WHERE user_id=?", (user_id,))
            db.commit()
