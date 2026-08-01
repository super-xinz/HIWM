from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import aiohttp

from .config import CompanionSettings


class ProfileEngineError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, retryable: bool = True):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class ProfileEngineClient:
    def __init__(self, settings: CompanionSettings):
        self.settings = settings

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {
            "X-API-Key": self.settings.profile_engine_api_key,
            "X-Tenant-ID": self.settings.profile_engine_tenant_id,
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key[:256]
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
        idempotency_key: str | None = None,
        allow_not_found: bool = False,
    ) -> dict | None:
        timeout = aiohttp.ClientTimeout(total=self.settings.profile_engine_timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method,
                    f"{self.settings.profile_engine_base_url}{path}",
                    headers=self._headers(idempotency_key),
                    json=payload,
                ) as response:
                    if allow_not_found and response.status == 404:
                        return None
                    try:
                        body: Any = await response.json()
                    except (aiohttp.ContentTypeError, ValueError) as exc:
                        raise ProfileEngineError(
                            "画像引擎返回了无法解析的响应", status=response.status
                        ) from exc
                    if response.status >= 400:
                        message = (
                            body.get("message")
                            or body.get("detail")
                            or f"画像引擎返回 HTTP {response.status}"
                        ) if isinstance(body, dict) else f"画像引擎返回 HTTP {response.status}"
                        raise ProfileEngineError(
                            str(message),
                            status=response.status,
                            retryable=response.status >= 500 or response.status in {408, 409, 429},
                        )
                    if not isinstance(body, dict):
                        raise ProfileEngineError("画像引擎响应不是 JSON 对象", retryable=False)
                    return body
        except ProfileEngineError:
            raise
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise ProfileEngineError("画像引擎暂时不可用") from exc

    async def health_check(self) -> bool:
        timeout = aiohttp.ClientTimeout(total=min(self.settings.profile_engine_timeout_seconds, 5))
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{self.settings.profile_engine_base_url}/health"
                ) as response:
                    body = await response.json()
                    return response.status == 200 and body.get("status") in {"ok", "degraded"}
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return False

    async def get_profile(self, user_id: str) -> dict | None:
        return await self._request(
            "GET", f"/v1/profiles/{user_id}", allow_not_found=True
        )

    async def ensure_profile(self, user_id: str, request_id: str) -> dict:
        current = await self.get_profile(user_id)
        if current is not None:
            return current
        created = await self._request(
            "POST",
            "/v1/profiles:init",
            payload={
                "tenant_user_id": user_id,
                "display_name": user_id,
                "consent": {"profile": True, "sensitive_inference": False},
            },
            idempotency_key=f"companion-init-{user_id}-{request_id}",
        )
        return {
            "profile_version": created["profile_version"],
            "profile": created["profile"],
            "rule_pack_versions": {
                "cold_start": created.get("rule_pack", {}).get("version"),
                "dialogue": created.get("rule_pack", {}).get("version"),
            },
        }

    async def update_from_conversation(self, payload: dict) -> dict:
        return await self._request(
            "POST",
            f"/v1/profiles/{payload['user_id']}/messages:ingest",
            payload={
                "conversation_id": payload["session_id"],
                "message_id": payload["turn_id"],
                "expected_profile_version": payload["expected_profile_version"],
                "occurred_at": payload.get("occurred_at")
                or datetime.now(timezone.utc).isoformat(),
                "text": payload["user_message"],
                "context": {
                    "previous_turn_count": payload.get("previous_turn_count", 0),
                    "recent_turns": payload.get("recent_turns", [])[-12:],
                },
            },
            idempotency_key=payload["idempotency_key"],
        )

    async def reset_profile(self, user_id: str, request_id: str) -> dict:
        return await self._request(
            "POST",
            f"/v1/profiles/{user_id}:reset",
            payload={"confirm": True, "display_name": user_id},
            idempotency_key=f"companion-reset-{user_id}-{request_id}",
        )


def public_profile(data: dict | None) -> dict | None:
    if not data or not isinstance(data.get("profile"), dict):
        return None
    profile = data["profile"]
    meta = profile.get("meta", {})
    portrait = profile.get("portrait", {})
    runtime = profile.get("runtime", {})
    enneagram = profile.get("enneagram_profile", {})
    traits: list[dict] = []
    for group_name, group in profile.get("core_traits", {}).items():
        if not isinstance(group, dict):
            continue
        for name, value in group.items():
            if isinstance(value, dict) and isinstance(value.get("value"), (int, float)):
                traits.append({
                    "group": group_name,
                    "name": name,
                    "value": value["value"],
                    "confidence": value.get("confidence"),
                })
    traits.sort(key=lambda item: item.get("confidence") or 0, reverse=True)
    return {
        "profile_version": data.get("profile_version"),
        "updated_at": meta.get("updated_at"),
        "overall_confidence": meta.get("overall_confidence"),
        "mbti": profile.get("mbti_dimensions", {}).get("type_label"),
        "portrait": {
            key: value.get("content") if isinstance(value, dict) else value
            for key, value in portrait.items()
            if key in {"essence", "strengths", "core_tension"}
        },
        "top_traits": traits[:6],
        "interaction_preferences": runtime.get("interaction_preferences", {}),
        "current_state": runtime.get("current_state", {}),
        "memories": runtime.get("memories", [])[-8:],
        "enneagram": enneagram.get("identity", {}),
    }
