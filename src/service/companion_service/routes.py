from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from .access import AccessManager
from .config import CompanionSettings
from .examples import (
    DEFAULT_EXAMPLE_ID,
    SHOWCASE_BY_ID,
    SHOWCASE_EXAMPLES,
    public_profile_for_example,
)
from .llm_client import LLMError
from .models import AccessLoginRequest, ChatRequest
from .orchestrator import ChatOrchestrator
from .profile_client import (
    ProfileEngineClient,
    ProfileEngineError,
    _presentation_text,
)
from .session_store import DuplicateTurnError, SessionAccessError, SessionStore


def register_companion_api(
    app: FastAPI,
    *,
    settings: CompanionSettings | None = None,
    store: SessionStore | None = None,
    orchestrator: ChatOrchestrator | None = None,
) -> None:
    """Register the server-side companion BFF once on an existing HIWM app."""

    if getattr(app.state, "companion_api_registered", False):
        return
    settings = settings or CompanionSettings.from_env()
    store = store or SessionStore(settings.database_url)
    profile_client = ProfileEngineClient(settings)
    orchestrator = orchestrator or ChatOrchestrator(
        settings, store, profile_client=profile_client
    )
    access = AccessManager(settings)
    default_example_id = (
        settings.default_user_id
        if settings.default_user_id in SHOWCASE_BY_ID
        else DEFAULT_EXAMPLE_ID
    )
    app.state.companion_api_registered = True
    app.state.companion_settings = settings
    app.state.companion_store = store

    protected_prefixes = (
        "/api/v1/companion",
        "/api/v1/runtime",
        "/webrtc",
    )
    no_store_prefixes = (*protected_prefixes, "/api/v1/access")

    def private_no_store(response: Response) -> Response:
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Pragma"] = "no-cache"
        vary = response.headers.get("Vary", "")
        values = {item.strip() for item in vary.split(",") if item.strip()}
        values.add("Cookie")
        response.headers["Vary"] = ", ".join(sorted(values))
        return response

    @app.middleware("http")
    async def companion_access_guard(request: Request, call_next):
        if request.url.path.startswith(protected_prefixes) and not access.authorized(request):
            return private_no_store(Response(
                content=json.dumps({"detail": "请先输入 Demo 访问口令"}, ensure_ascii=False),
                status_code=401,
                media_type="application/json",
            ))
        response = await call_next(request)
        if request.url.path.startswith(no_store_prefixes):
            return private_no_store(response)
        return response

    @app.get("/api/v1/access/status", tags=["access"])
    async def access_status(request: Request) -> dict:
        return {
            "authorized": access.authorized(request),
            "required": access.required,
            "default_example_id": default_example_id,
        }

    @app.post("/api/v1/access/login", tags=["access"])
    async def access_login(
        body: AccessLoginRequest, request: Request, response: Response
    ) -> dict:
        access.login(request, response, body.code)
        return {"authorized": True, "required": access.required}

    @app.post("/api/v1/access/logout", tags=["access"])
    async def access_logout(request: Request, response: Response) -> dict:
        if access.authorized(request):
            store.clear_owner(access.subject(request))
        access.logout(request, response)
        return {"authorized": False}

    async def health_payload() -> dict:
        profile_state = "not_configured"
        if settings.profile_engine_configured:
            profile_state = "ok" if await profile_client.health_check() else "unavailable"
        database_state = "ok" if store.health_check() else "unavailable"
        healthy = (
            profile_state == "ok"
            and settings.llm_configured
            and database_state == "ok"
            and (access.required or not settings.access_cookie_secure)
        )
        return {"status": "ok" if healthy else "degraded"}

    def public_chat_response(value: object) -> dict:
        raw = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
        if not isinstance(raw, dict):
            return {"reply": "", "cached": False}
        reply = _presentation_text(raw.get("reply", ""))
        return {
            "reply": reply if isinstance(reply, str) else "",
            "cached": raw.get("cached") is True,
        }

    def public_message(item: dict) -> dict:
        role = item.get("role")
        content = item.get("content", "")
        if role == "assistant":
            content = _presentation_text(content)
        return {
            "turn_id": item.get("turn_id"),
            "role": role,
            "content": content if isinstance(content, str) else "",
            "created_at": item.get("created_at"),
        }

    @app.get("/api/health", tags=["system"])
    async def web_health() -> dict:
        return await health_payload()

    @app.get("/api/v1/companion/health", tags=["companion"])
    async def companion_health() -> dict:
        return await health_payload()

    @app.get("/api/v1/companion/examples", tags=["companion"])
    async def companion_examples() -> dict:
        return {
            "default_example_id": default_example_id,
            "examples": [item.public_view() for item in SHOWCASE_EXAMPLES],
        }

    def require_showcase_example(user_id: str) -> None:
        if user_id not in SHOWCASE_BY_ID:
            raise HTTPException(status_code=404, detail="示例角色不存在")

    @app.post("/api/v1/companion/chat", tags=["companion"])
    async def companion_chat(body: ChatRequest, request: Request) -> dict:
        require_showcase_example(body.user_id)
        access.check_rate(request, "chat", settings.chat_rate_limit_per_minute)
        body = body.model_copy(update={"profile_enabled": True})
        try:
            store.bind_session(body.session_id, access.subject(request), body.user_id)
        except SessionAccessError as exc:
            raise HTTPException(status_code=404, detail="会话不存在") from exc
        try:
            return public_chat_response(await orchestrator.chat(body))
        except DuplicateTurnError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except LLMError as exc:
            raise HTTPException(status_code=502, detail="回复生成暂时不可用") from exc
        except ProfileEngineError as exc:
            status = 404 if exc.status == 404 else 503
            detail = "示例画像尚未准备好" if status == 404 else "示例画像暂时不可用"
            raise HTTPException(status_code=status, detail=detail) from exc

    @app.post("/api/v1/companion/chat/stream", tags=["companion"])
    async def companion_chat_stream(body: ChatRequest, request: Request) -> StreamingResponse:
        require_showcase_example(body.user_id)
        access.check_rate(request, "chat", settings.chat_rate_limit_per_minute)
        body = body.model_copy(update={"profile_enabled": True})
        try:
            store.bind_session(body.session_id, access.subject(request), body.user_id)
        except SessionAccessError as exc:
            raise HTTPException(status_code=404, detail="会话不存在") from exc

        async def events():
            try:
                async for event in orchestrator.stream_chat(body):
                    event_type = event.get("type")
                    if event_type == "meta":
                        safe_meta = {"type": "meta", "cached": event.get("cached") is True}
                        yield f"data: {json.dumps(safe_meta, ensure_ascii=False)}\n\n"
                    elif event_type == "delta":
                        continue
                    elif event_type == "final":
                        response = public_chat_response(event.get("response"))
                        safe_reply = response.get("reply", "")
                        if safe_reply:
                            yield f"data: {json.dumps({'type': 'delta', 'content': safe_reply}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'final', 'response': response}, ensure_ascii=False)}\n\n"
            except DuplicateTurnError as exc:
                yield f"data: {json.dumps({'type': 'error', 'code': 'duplicate_turn', 'message': str(exc)}, ensure_ascii=False)}\n\n"
            except LLMError:
                yield f"data: {json.dumps({'type': 'error', 'code': 'generation_unavailable', 'message': '回复生成暂时不可用'}, ensure_ascii=False)}\n\n"
            except ProfileEngineError as exc:
                message = "示例画像尚未准备好" if exc.status == 404 else "示例画像暂时不可用"
                yield f"data: {json.dumps({'type': 'error', 'code': 'example_unavailable', 'message': message}, ensure_ascii=False)}\n\n"
            except Exception:
                yield f"data: {json.dumps({'type': 'error', 'code': 'stream_interrupted', 'message': '流式连接意外中断，请重试'}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/v1/companion/profile/{user_id}", tags=["companion"])
    async def companion_profile(user_id: str) -> dict:
        require_showcase_example(user_id)
        if not settings.profile_engine_configured:
            raise HTTPException(status_code=503, detail="画像引擎尚未配置")
        try:
            await profile_client.require_profile(user_id)
            return {"profile": public_profile_for_example(user_id)}
        except ProfileEngineError as exc:
            status = exc.status if exc.status and 400 <= exc.status < 600 else 503
            detail = "示例画像尚未准备好" if status == 404 else "示例画像暂时不可用"
            raise HTTPException(status_code=status, detail=detail) from exc

    @app.get("/api/v1/companion/sessions/{session_id}/messages", tags=["companion"])
    async def session_messages(
        session_id: str,
        request: Request,
        limit: int = Query(default=100, ge=1, le=200),
    ) -> dict:
        try:
            authorized = store.authorize_session(session_id, access.subject(request))
        except SessionAccessError as exc:
            raise HTTPException(status_code=404, detail="会话不存在") from exc
        if not authorized:
            return {"session_id": session_id, "messages": []}
        return {
            "session_id": session_id,
            "messages": [public_message(item) for item in store.messages(session_id, limit)],
        }

    @app.delete("/api/v1/companion/sessions/{session_id}", tags=["companion"])
    async def clear_session(session_id: str, request: Request) -> dict:
        try:
            authorized = store.authorize_session(session_id, access.subject(request))
        except SessionAccessError as exc:
            raise HTTPException(status_code=404, detail="会话不存在") from exc
        if not authorized:
            return {"session_id": session_id, "cleared": False}
        store.clear_session(session_id)
        return {"session_id": session_id, "cleared": True}
