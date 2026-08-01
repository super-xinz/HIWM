from __future__ import annotations

import hmac
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
        self.sessions.pop(token, None)
        response.delete_cookie(COOKIE_NAME, path="/")
