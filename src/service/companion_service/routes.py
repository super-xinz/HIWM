from __future__ import annotations

import json
import uuid

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from .access import AccessManager
from .config import CompanionSettings
from .llm_client import LLMError
from .models import AccessLoginRequest, ChatRequest, ResetRequest
from .orchestrator import ChatOrchestrator
from .profile_client import ProfileEngineClient, ProfileEngineError, public_profile
from .session_store import DuplicateTurnError, SessionStore


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
    app.state.companion_api_registered = True
    app.state.companion_settings = settings
    app.state.companion_store = store

    protected_prefixes = (
        "/api/v1/companion",
        "/api/v1/runtime",
        "/webrtc",
    )

    @app.middleware("http")
    async def companion_access_guard(request: Request, call_next):
        if request.url.path.startswith(protected_prefixes) and not access.authorized(request):
            return Response(
                content=json.dumps({"detail": "请先输入 Demo 访问口令"}, ensure_ascii=False),
                status_code=401,
                media_type="application/json",
            )
        return await call_next(request)

    @app.get("/api/v1/access/status", tags=["access"])
    async def access_status(request: Request) -> dict:
        return {
            "authorized": access.authorized(request),
            "required": access.required,
            "default_user_id": settings.default_user_id,
        }

    @app.post("/api/v1/access/login", tags=["access"])
    async def access_login(
        body: AccessLoginRequest, request: Request, response: Response
    ) -> dict:
        access.login(request, response, body.code)
        return {"authorized": True, "required": access.required}

    @app.post("/api/v1/access/logout", tags=["access"])
    async def access_logout(request: Request, response: Response) -> dict:
        access.logout(request, response)
        return {"authorized": False}

    async def health_payload() -> dict:
        profile_state = "not_configured"
        if settings.profile_engine_configured:
            profile_state = "ok" if await profile_client.health_check() else "unavailable"
        database_state = "ok" if store.health_check() else "unavailable"
        services = {
            "application": "ok",
            "profile_engine": profile_state,
            "llm": "configured" if settings.llm_configured else "not_configured",
            "database": database_state,
        }
        healthy = (
            profile_state == "ok"
            and settings.llm_configured
            and database_state == "ok"
            and (access.required or not settings.access_cookie_secure)
        )
        return {
            "status": "ok" if healthy else "degraded",
            "services": services,
            "version": settings.git_commit_sha,
            "access_protection": "configured" if access.required else "disabled",
        }

    @app.get("/api/health", tags=["system"])
    async def web_health() -> dict:
        return await health_payload()

    @app.get("/api/v1/companion/health", tags=["companion"])
    async def companion_health() -> dict:
        return await health_payload()

    @app.post("/api/v1/companion/chat", tags=["companion"])
    async def companion_chat(body: ChatRequest) -> dict:
        try:
            return (await orchestrator.chat(body)).model_dump(mode="json")
        except DuplicateTurnError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except LLMError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/api/v1/companion/chat/stream", tags=["companion"])
    async def companion_chat_stream(body: ChatRequest) -> StreamingResponse:
        async def events():
            try:
                async for event in orchestrator.stream_chat(body):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except DuplicateTurnError as exc:
                yield f"data: {json.dumps({'type': 'error', 'code': 'duplicate_turn', 'message': str(exc)}, ensure_ascii=False)}\n\n"
            except LLMError as exc:
                yield f"data: {json.dumps({'type': 'error', 'code': 'llm_unavailable', 'message': str(exc)}, ensure_ascii=False)}\n\n"
            except Exception:
                yield f"data: {json.dumps({'type': 'error', 'code': 'stream_interrupted', 'message': '流式连接意外中断，请重试'}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/v1/companion/profile/{user_id}", tags=["companion"])
    async def companion_profile(user_id: str) -> dict:
        if not settings.profile_engine_configured:
            raise HTTPException(status_code=503, detail="画像引擎尚未配置")
        try:
            data = await profile_client.ensure_profile(user_id, uuid.uuid4().hex)
            return {"profile": public_profile(data)}
        except ProfileEngineError as exc:
            status = exc.status if exc.status and 400 <= exc.status < 600 else 503
            raise HTTPException(status_code=status, detail=str(exc)) from exc

    @app.post("/api/v1/companion/profile/{user_id}/reset", tags=["companion"])
    async def companion_reset_profile(user_id: str, body: ResetRequest) -> dict:
        try:
            result = await profile_client.reset_profile(user_id, uuid.uuid4().hex)
            store.clear_user(user_id)
            return {"reset": True, "profile": public_profile(result)}
        except ProfileEngineError as exc:
            status = exc.status if exc.status and 400 <= exc.status < 600 else 503
            raise HTTPException(status_code=status, detail=str(exc)) from exc

    @app.post(
        "/api/v1/companion/sessions/{session_id}/turns/{turn_id}/profile-update:retry",
        tags=["companion"],
    )
    async def retry_profile_update(session_id: str, turn_id: str) -> dict:
        try:
            return (
                await orchestrator.retry_profile_update(session_id, turn_id)
            ).model_dump(mode="json")
        except ProfileEngineError as exc:
            status = exc.status if exc.status and 400 <= exc.status < 600 else 503
            raise HTTPException(status_code=status, detail=str(exc)) from exc

    @app.get("/api/v1/companion/sessions/{session_id}/messages", tags=["companion"])
    async def session_messages(
        session_id: str, limit: int = Query(default=100, ge=1, le=200)
    ) -> dict:
        return {"session_id": session_id, "messages": store.messages(session_id, limit)}

    @app.delete("/api/v1/companion/sessions/{session_id}", tags=["companion"])
    async def clear_session(session_id: str) -> dict:
        store.clear_session(session_id)
        return {"session_id": session_id, "cleared": True}
