from __future__ import annotations

import re
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

    async def require_profile(self, user_id: str) -> dict:
        current = await self.get_profile(user_id)
        if current is None:
            raise ProfileEngineError(
                "示例画像尚未准备好", status=404, retryable=False
            )
        return current

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


_TRAIT_LABELS = {
    "extroversion": "互动活跃度",
    "social_warmth": "社交温度",
    "assertiveness": "表达坚定度",
    "impulsivity": "行动即时性",
    "openness": "开放程度",
    "creativity": "创造倾向",
    "depth_of_thought": "思考深度",
    "thinking_ratio": "分析决策倾向",
    "empathy": "共情能力",
    "risk_tolerance": "风险接受度",
    "structure_pref": "结构化偏好",
    "discipline": "自律程度",
    "adaptability": "适应能力",
    "persistence": "持续投入度",
    "confidence": "自信程度",
    "optimism": "积极预期",
    "romantic_orientation": "关系投入度",
}

_GROUP_LABELS = {
    "energy_mode": "互动节奏",
    "cognition_mode": "信息处理",
    "decision_mode": "决策方式",
    "action_mode": "行动方式",
    "self_system": "自我调节",
    "emotion_relation_mode": "情绪与关系",
}

_PREFERENCE_LABELS = {
    "response_length": "回复长度",
    "directness": "表达直接度",
    "empathy_first": "共情优先",
    "question_load": "提问密度",
    "humor_level": "幽默程度",
}

_STATE_LABELS = {
    "emotion": "当前情绪",
    "stress_level": "压力水平",
    "energy_level": "精力水平",
}

_VALUE_LABELS = {
    "short": "简短",
    "long": "详细",
    "low": "较低",
    "medium": "适中",
    "high": "较高",
    "true": "是",
    "false": "否",
}


def _presentation_text(value: object) -> object:
    """Remove internal methodology labels from browser-facing profile content."""
    if isinstance(value, str):
        text = re.sub(r"数字(?:密码|学)(?:\s*[0-9]{4})?", "初始画像线索", value, flags=re.IGNORECASE)
        text = re.sub(r"生命灵数|生命数|生日数|天赋数", "初始画像线索", text)
        text = re.sub(r"(?<!\d)(?:19|20)\d{2}-\d{2}-\d{2}(?!\d)", "出生信息线索", text)
        text = re.sub(r"(?<!\d)\d{4}(?!\d)", "初始画像线索", text)
        text = re.sub(r"MBTI|荣格八维", "偏好倾向", text, flags=re.IGNORECASE)
        text = re.sub(
            r"(?<![A-Za-z])[IE][NS][FT][JP](?:-[AT])?(?:型)?(?![A-Za-z])",
            "偏好倾向",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"(?<![A-Za-z])[IE]\s+[NS]\s+[FT]\s+[JP](?![A-Za-z])",
            "偏好倾向",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"(?<![A-Za-z])(?:Ni|Ne|Si|Se|Ti|Te|Fi|Fe)(?![A-Za-z])",
            "偏好维度",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\b(?:I/E|S/N|T/F|J/P)\b", "偏好维度", text, flags=re.IGNORECASE)
        text = re.sub(r"九型(?:人格|互动画像|画像|互动)?", "互动风格", text)
        text = re.sub(r"\b[1-9]w[1-9]\b", "互动风格", text, flags=re.IGNORECASE)
        text = re.sub(r"[1-9](?:号|型)(?:人格)?", "互动风格", text)
        text = re.sub(r"(?<![A-Za-z])Type\s*[1-9](?!\d)", "互动风格", text, flags=re.IGNORECASE)
        text = re.sub(
            r"完美型|助人型|成就型|自我型|理智型|忠诚型|活跃型|领袖型|和平型",
            "互动风格",
            text,
        )
        text = re.sub(
            r"\b(?:SX|SP|SO)/(?:SX|SP|SO)\b",
            "关注组合",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"(?<![A-Za-z])(?:SX|SP|SO)(?:优先)?(?![A-Za-z])",
            "关注倾向",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\b(?:social|self-preservation|sexual)(?:\s+instinct)?\b",
            "关注倾向",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"八字|命理|紫微(?:斗数)?|生辰", "出生信息线索", text)
        text = re.sub(
            r"偏财格|七杀格|伤官格|正官格|正财格|食神格|正印格|偏印格|建禄格|羊刃格",
            "出生信息线索",
            text,
        )
        text = re.sub(
            r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]"
            r"(?:\s+[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]){2,3}",
            "出生信息线索",
            text,
        )
        text = re.sub(
            r"[甲乙丙丁戊己庚辛壬癸]?[木火土金水]?日主|身强|身弱|四柱|天干|地支|五行|命盘",
            "出生信息线索",
            text,
        )
        text = re.sub(r"[^\s，。；：、]+\.xlsx", "内部资料", text, flags=re.IGNORECASE)
        text = re.sub(r"enneagram", "interaction-style", text, flags=re.IGNORECASE)
        text = re.sub(r"numerology", "initial-signal", text, flags=re.IGNORECASE)
        return _VALUE_LABELS.get(text.lower(), text)
    if isinstance(value, dict):
        return {key: _presentation_text(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_presentation_text(item) for item in value]
    return value


def _public_preferences(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    return {
        label: _presentation_text(value[key])
        for key, label in _PREFERENCE_LABELS.items()
        if key in value
    }


def _public_state(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, label in _STATE_LABELS.items():
        if key not in value:
            continue
        item = value[key]
        if isinstance(item, dict):
            item = item.get("value")
        result[label] = _presentation_text(item)
    return result


def _public_trait_level(value: float) -> str:
    if value >= 0.7:
        return "突出"
    if value <= 0.35:
        return "相对克制"
    return "均衡"


def public_profile(data: dict | None) -> dict | None:
    if not data or not isinstance(data.get("profile"), dict):
        return None
    profile = data["profile"]
    meta = profile.get("meta", {})
    portrait = profile.get("portrait", {})
    runtime = profile.get("runtime", {})
    traits: list[dict] = []
    for group_name, group in profile.get("core_traits", {}).items():
        if not isinstance(group, dict):
            continue
        for name, value in group.items():
            if isinstance(value, dict) and isinstance(value.get("value"), (int, float)):
                traits.append({
                    "group": _GROUP_LABELS.get(group_name, "综合特征"),
                    "name": _TRAIT_LABELS.get(name, "画像特征"),
                    "level": _public_trait_level(value["value"]),
                    "_rank": value.get("confidence") or 0,
                })
    traits.sort(key=lambda item: item["_rank"], reverse=True)
    for item in traits:
        item.pop("_rank", None)
    return {
        "updated_at": meta.get("updated_at"),
        "portrait": {
            key: _presentation_text(value.get("content") if isinstance(value, dict) else value)
            for key, value in portrait.items()
            if key in {"essence", "strengths", "core_tension"}
        },
        "top_traits": traits[:6],
        "interaction_preferences": _public_preferences(runtime.get("interaction_preferences", {})),
        "current_state": _public_state(runtime.get("current_state", {})),
    }
