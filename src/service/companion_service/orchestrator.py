from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from .config import CompanionSettings
from .examples import is_showcase_example
from .llm_client import LLMClient, LLMError
from .models import ChatRequest, ChatResponse, ProfileUpdateView
from .profile_client import ProfileEngineClient, ProfileEngineError
from .prompt_composer import compose_messages
from .session_store import SessionStore


logger = logging.getLogger("hiwm.companion")

_UPDATE_FIELD_LABELS = {
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

_OPERATION_LABELS = {
    "UPSERT_FACT": "已记录一项长期事实",
    "SET_INTERACTION_PREFERENCE": "已更新沟通偏好",
    "SET_STATE": "已更新当前状态",
    "UPSERT_MEMORY": "已记录一项重要信息",
}


def _history_for_model(items: list[dict]) -> list[dict[str, str]]:
    return [
        {"role": item["role"], "content": item["content"]}
        for item in items
        if item.get("role") in {"user", "assistant"}
    ]


def _update_summary(result: dict) -> list[str]:
    summary: list[str] = []
    for patch in result.get("profile_patch", [])[:5]:
        field = patch.get("field")
        if field:
            field_name = str(field).split(".")[-1]
            summary.append(f"已更新{_UPDATE_FIELD_LABELS.get(field_name, '一项互动特征')}")
    for operation in result.get("runtime_operations", [])[:5]:
        operation_name = operation.get("operation")
        if operation_name:
            summary.append(_OPERATION_LABELS.get(str(operation_name), "已更新一项个性化信息"))
    if not summary and result.get("no_profile_change"):
        summary.append("本轮未发现需要写入画像的新信息")
    return summary


class ChatOrchestrator:
    def __init__(
        self,
        settings: CompanionSettings,
        store: SessionStore,
        profile_client: ProfileEngineClient | None = None,
        llm_client: LLMClient | None = None,
    ):
        self.settings = settings
        self.store = store
        self.profile_client = profile_client or ProfileEngineClient(settings)
        self.llm_client = llm_client or LLMClient(settings)

    async def _prepare(self, request: ChatRequest, request_id: str) -> tuple[dict | None, list[dict], dict[str, float]]:
        timings: dict[str, float] = {}
        profile_data = None
        if request.profile_enabled and self.settings.profile_engine_configured:
            started = time.perf_counter()
            try:
                if is_showcase_example(request.user_id):
                    profile_data = await self.profile_client.require_profile(request.user_id)
                else:
                    profile_data = await self.profile_client.ensure_profile(request.user_id, request_id)
            except ProfileEngineError as exc:
                if is_showcase_example(request.user_id):
                    raise
                logger.warning("profile read degraded request_id={} error_type={}", request_id, type(exc).__name__)
            timings["profile_read"] = round((time.perf_counter() - started) * 1000, 2)
        history = self.store.messages(request.session_id, limit=24)
        messages = compose_messages(
            request.message,
            _history_for_model(history),
            profile_data,
            self.settings.profile_context_max_chars,
        )
        return profile_data, messages, timings

    def _update_payload(
        self,
        request: ChatRequest,
        profile_data: dict,
        history: list[dict],
    ) -> dict:
        recent = _history_for_model(history)[-12:]
        return {
            "user_id": request.user_id,
            "session_id": request.session_id,
            "turn_id": request.turn_id,
            "expected_profile_version": profile_data["profile_version"],
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "user_message": request.message,
            "previous_turn_count": len(history),
            "recent_turns": recent,
            "idempotency_key": f"companion-turn-{request.turn_id}",
        }

    async def _finalize(
        self,
        request: ChatRequest,
        request_id: str,
        reply: str,
        model: str,
        profile_data: dict | None,
        timings: dict[str, float],
        total_started: float,
    ) -> ChatResponse:
        history = self.store.messages(request.session_id, limit=24)
        update_payload = None
        if profile_data is None or not request.profile_enabled:
            update_view = ProfileUpdateView(status="skipped")
        elif is_showcase_example(request.user_id):
            update_view = ProfileUpdateView(
                status="unchanged",
                profile_version=profile_data.get("profile_version"),
                summary=["固定示例画像保持不变"],
            )
        else:
            update_payload = self._update_payload(request, profile_data, history)
            started = time.perf_counter()
            try:
                updated = await self.profile_client.update_from_conversation(update_payload)
                update_view = ProfileUpdateView(
                    status="unchanged" if updated.get("no_profile_change") else "updated",
                    profile_version=updated.get("profile_version"),
                    summary=_update_summary(updated),
                )
            except ProfileEngineError as exc:
                update_view = ProfileUpdateView(
                    status="failed",
                    profile_version=profile_data.get("profile_version"),
                    retryable=exc.retryable,
                    error="画像更新暂时不可用",
                )
            timings["profile_update"] = round((time.perf_counter() - started) * 1000, 2)
        timings["total"] = round((time.perf_counter() - total_started) * 1000, 2)
        response = ChatResponse(
            request_id=request_id,
            turn_id=request.turn_id,
            session_id=request.session_id,
            user_id=request.user_id,
            reply=reply,
            model=model,
            profile_used=profile_data is not None,
            profile_version_used=profile_data.get("profile_version") if profile_data else None,
            profile_update=update_view,
            latency_ms=timings,
        )
        self.store.save_turn(request, response, update_payload)
        logger.info(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "info",
            "service": "hiwm-companion-chat",
            "request_id": request_id,
            "session_id": request.session_id,
            "turn_id": request.turn_id,
            "status": "ok",
            "latency": timings,
            "profile_status": update_view.status,
        }, ensure_ascii=False, separators=(",", ":")))
        return response

    async def chat(self, request: ChatRequest) -> ChatResponse:
        cached = self.store.cached_turn(request)
        if cached:
            return cached
        request_id = uuid.uuid4().hex
        total_started = time.perf_counter()
        profile_data, messages, timings = await self._prepare(request, request_id)
        started = time.perf_counter()
        reply, model = await self.llm_client.chat(messages)
        timings["llm"] = round((time.perf_counter() - started) * 1000, 2)
        return await self._finalize(
            request, request_id, reply, model, profile_data, timings, total_started
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[dict]:
        cached = self.store.cached_turn(request)
        if cached:
            yield {"type": "meta", "request_id": cached.request_id, "cached": True}
            yield {"type": "delta", "content": cached.reply}
            yield {"type": "final", "response": cached.model_dump(mode="json")}
            return
        request_id = uuid.uuid4().hex
        total_started = time.perf_counter()
        profile_data, messages, timings = await self._prepare(request, request_id)
        yield {
            "type": "meta",
            "request_id": request_id,
            "profile_used": profile_data is not None,
        }
        chunks: list[str] = []
        started = time.perf_counter()
        async for content in self.llm_client.stream(messages):
            chunks.append(content)
            yield {"type": "delta", "content": content}
        timings["llm"] = round((time.perf_counter() - started) * 1000, 2)
        reply = "".join(chunks).strip()
        if not reply:
            raise LLMError("大模型返回了空内容")
        response = await self._finalize(
            request,
            request_id,
            reply,
            self.settings.llm_model,
            profile_data,
            timings,
            total_started,
        )
        yield {"type": "final", "response": response.model_dump(mode="json")}

    async def retry_profile_update(self, session_id: str, turn_id: str) -> ChatResponse:
        payload = self.store.pending_update(session_id, turn_id)
        if not payload:
            raise ProfileEngineError("没有可重试的画像更新", retryable=False)
        result = await self.profile_client.update_from_conversation(payload)
        request = ChatRequest(
            user_id=payload["user_id"],
            session_id=session_id,
            turn_id=turn_id,
            message=payload["user_message"],
        )
        response = self.store.cached_turn(request)
        if response is None:
            raise ProfileEngineError("找不到对应聊天结果", retryable=False)
        updated = response.model_copy(update={
            "cached": False,
            "profile_update": ProfileUpdateView(
                status="unchanged" if result.get("no_profile_change") else "updated",
                profile_version=result.get("profile_version"),
                summary=_update_summary(result),
            ),
        })
        self.store.replace_response(updated)
        return updated
