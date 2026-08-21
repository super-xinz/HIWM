from __future__ import annotations

import hmac
import hashlib
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, Request, Response

from .config import CompanionSettings


COOKIE_NAME = "hiwm_demo_session"


@dataclass
class AccessSession:
    expires_at: float


class AccessManager:
    def __init__(self, settings: CompanionSettings):
        self.settings = settings
        self.sessions: dict[str, AccessSession] = {}
        self.failures: dict[str, deque[float]] = defaultdict(deque)
        self.actions: dict[str, deque[float]] = defaultdict(deque)

    @property
    def required(self) -> bool:
        return bool(self.settings.access_code)

    def _prune(self) -> None:
        now = time.time()
        self.sessions = {
            token: item for token, item in self.sessions.items() if item.expires_at > now
        }

    def authorized(self, request: Request) -> bool:
        if not self.required:
            return True
        self._prune()
        token = request.cookies.get(COOKIE_NAME, "")
        session = self.sessions.get(token)
        return bool(session and session.expires_at > time.time())

    def require(self, request: Request) -> None:
        if not self.authorized(request):
            raise HTTPException(status_code=401, detail="请先输入 Demo 访问口令")

    def subject(self, request: Request) -> str:
        """Return a non-secret, per-login owner id for isolating demo sessions."""
        if not self.required:
            return "unprotected-demo"
        self.require(request)
        token = request.cookies.get(COOKIE_NAME, "")
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def check_rate(self, request: Request, action: str, limit: int) -> None:
        now = time.time()
        key = f"{self.subject(request)}:{action}"
        events = self.actions[key]
        while events and events[0] < now - 60:
            events.popleft()
        if len(events) >= limit:
            raise HTTPException(status_code=429, detail="操作过于频繁，请稍后再试")
        events.append(now)

    def login(self, request: Request, response: Response, code: str) -> None:
        if not self.required:
            return
        host = request.client.host if request.client else "unknown"
        now = time.time()
        attempts = self.failures[host]
        while attempts and attempts[0] < now - 300:
            attempts.popleft()
        if len(attempts) >= 5:
            raise HTTPException(status_code=429, detail="尝试次数过多，请五分钟后再试")
        if not hmac.compare_digest(code, self.settings.access_code):
            attempts.append(now)
            raise HTTPException(status_code=401, detail="访问口令不正确")
        attempts.clear()
        token = secrets.token_urlsafe(32)
        self.sessions[token] = AccessSession(
            expires_at=now + self.settings.access_session_ttl_seconds
        )
        response.set_cookie(
            COOKIE_NAME,
            token,
            max_age=self.settings.access_session_ttl_seconds,
            httponly=True,
            secure=self.settings.access_cookie_secure,
            samesite="strict",
            path="/",
        )

    def logout(self, request: Request, response: Response) -> None:
        token = request.cookies.get(COOKIE_NAME, "")
        owner = hashlib.sha256(token.encode("utf-8")).hexdigest() if token else ""
        self.sessions.pop(token, None)
        for key in [key for key in self.actions if key.startswith(f"{owner}:")]:
            self.actions.pop(key, None)
        response.delete_cookie(COOKIE_NAME, path="/")
