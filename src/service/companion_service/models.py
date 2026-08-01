from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


Identifier = str


class AccessLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)


class ChatRequest(BaseModel):
    user_id: Identifier = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_.-]+$")
    session_id: Identifier = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_.-]+$")
    turn_id: Identifier = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_.-]+$")
    message: str = Field(min_length=1, max_length=4_000)
    profile_enabled: bool = True
    frontend_context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def non_blank_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("message must not be blank")
        return normalized


class ResetRequest(BaseModel):
    confirm: Literal[True]


class MessageView(BaseModel):
    session_id: str
    user_id: str
    turn_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    model: str | None = None
    profile_version: int | None = None
    request_id: str


class ProfileUpdateView(BaseModel):
    status: Literal["updated", "unchanged", "failed", "skipped"]
    profile_version: int | None = None
    summary: list[str] = Field(default_factory=list)
    retryable: bool = False
    error: str | None = None


class ChatResponse(BaseModel):
    request_id: str
    turn_id: str
    session_id: str
    user_id: str
    reply: str
    model: str
    profile_used: bool
    profile_version_used: int | None = None
    profile_update: ProfileUpdateView
    latency_ms: dict[str, float]
    cached: bool = False
