from __future__ import annotations

import os
from dataclasses import dataclass


def _integer(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _boolean(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class CompanionSettings:
    profile_engine_base_url: str
    profile_engine_api_key: str
    profile_engine_tenant_id: str
    profile_engine_timeout_seconds: float
    llm_api_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout_seconds: float
    default_user_id: str
    database_url: str
    access_code: str
    access_session_ttl_seconds: int
    access_cookie_secure: bool
    profile_context_max_chars: int
    git_commit_sha: str

    @classmethod
    def from_env(cls) -> "CompanionSettings":
        llm_key = os.getenv("LLM_API_KEY", "").strip()
        if not llm_key:
            candidate = os.getenv("DASHSCOPE_API_KEY", "").strip()
            if candidate != "NOT_CONFIGURED_YET":
                llm_key = candidate
        return cls(
            profile_engine_base_url=os.getenv(
                "PROFILE_ENGINE_BASE_URL", "http://127.0.0.1:8000"
            ).rstrip("/"),
            profile_engine_api_key=os.getenv("PROFILE_ENGINE_API_KEY", "").strip(),
            profile_engine_tenant_id=os.getenv(
                "PROFILE_ENGINE_TENANT_ID", "demo-tenant"
            ).strip(),
            profile_engine_timeout_seconds=_integer(
                "PROFILE_ENGINE_TIMEOUT_MS", 30_000
            ) / 1000,
            llm_api_base_url=os.getenv(
                "LLM_API_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ).rstrip("/"),
            llm_api_key=llm_key,
            llm_model=os.getenv("LLM_MODEL", "qwen-plus").strip(),
            llm_timeout_seconds=_integer("LLM_TIMEOUT_MS", 60_000) / 1000,
            default_user_id=os.getenv("DEMO_DEFAULT_USER_ID", "demo-xu").strip(),
            database_url=os.getenv(
                "COMPANION_DATABASE_URL", "sqlite:///./temp/companion-chat.db"
            ).strip(),
            access_code=os.getenv("DEMO_ACCESS_CODE", "").strip(),
            access_session_ttl_seconds=_integer(
                "DEMO_SESSION_TTL_SECONDS", 8 * 60 * 60, 300
            ),
            access_cookie_secure=_boolean("DEMO_COOKIE_SECURE", False),
            profile_context_max_chars=_integer(
                "PROFILE_CONTEXT_MAX_CHARS", 8_000, 1_000
            ),
            git_commit_sha=os.getenv("GIT_COMMIT_SHA", "unknown")[:64],
        )

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_model and self.llm_api_base_url)

    @property
    def profile_engine_configured(self) -> bool:
        return bool(
            self.profile_engine_base_url
            and self.profile_engine_api_key
            and self.profile_engine_tenant_id
        )
