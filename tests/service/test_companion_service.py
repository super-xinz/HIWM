from __future__ import annotations

import asyncio
from dataclasses import replace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from service.companion_service.config import CompanionSettings
from service.companion_service.models import ChatRequest
from service.companion_service.orchestrator import ChatOrchestrator
from service.companion_service.profile_client import ProfileEngineError
from service.companion_service.routes import register_companion_api
from service.companion_service.session_store import DuplicateTurnError, SessionStore


def settings(tmp_path) -> CompanionSettings:
    return CompanionSettings(
        profile_engine_base_url="http://profile.test",
        profile_engine_api_key="profile-key",
        profile_engine_tenant_id="test-tenant",
        profile_engine_timeout_seconds=1,
        llm_api_base_url="http://llm.test/v1",
        llm_api_key="llm-key",
        llm_model="test-model",
        llm_timeout_seconds=1,
        default_user_id="demo-xu",
        database_url=f"sqlite:///{tmp_path / 'chat.db'}",
        access_code="",
        access_session_ttl_seconds=3600,
        access_cookie_secure=False,
        profile_context_max_chars=4000,
        git_commit_sha="test-sha",
    )


class FakeProfileClient:
    def __init__(self, *, fail_update: bool = False):
        self.calls: list[str] = []
        self.fail_update = fail_update
        self.profile = {
            "profile_version": 2,
            "profile": {
                "portrait": {"essence": {"content": "偏好清晰而温和的沟通"}},
                "runtime": {
                    "current_state": {},
                    "interaction_preferences": {"response_length": "short"},
                    "memories": [],
                },
                "meta": {"overall_confidence": 0.4},
            },
        }

    async def ensure_profile(self, user_id: str, request_id: str) -> dict:
        self.calls.append("read")
        return self.profile

    async def update_from_conversation(self, payload: dict) -> dict:
        self.calls.append("update")
        if self.fail_update:
            raise ProfileEngineError("temporary profile failure")
        return {
            "profile_version": 3,
            "profile_patch": [{"field": "core_traits.energy_mode.extroversion"}],
            "runtime_operations": [],
            "no_profile_change": False,
        }


class FakeLLMClient:
    def __init__(self, calls: list[str]):
        self.calls = calls
        self.messages = []

    async def chat(self, messages):
        self.calls.append("llm")
        self.messages = messages
        return "我会用更简短的方式回应你。", "test-model"

    async def stream(self, messages):
        self.calls.append("llm")
        self.messages = messages
        yield "我会用"
        yield "更简短的方式回应你。"


def test_orchestrator_reads_profile_before_llm_and_updates_after(tmp_path):
    config = settings(tmp_path)
    store = SessionStore(config.database_url)
    profile = FakeProfileClient()
    llm = FakeLLMClient(profile.calls)
    orchestrator = ChatOrchestrator(config, store, profile, llm)
    request = ChatRequest(
        user_id="demo-xu", session_id="session-1", turn_id="turn-1", message="请说短一点"
    )

    response = asyncio.run(orchestrator.chat(request))

    assert profile.calls == ["read", "llm", "update"]
    assert response.profile_used is True
    assert response.profile_update.status == "updated"
    assert response.profile_update.profile_version == 3
    assert "偏好清晰而温和的沟通" in llm.messages[0]["content"]
    assert [item["role"] for item in store.messages("session-1")] == ["user", "assistant"]


def test_profile_update_failure_keeps_reply_and_can_be_cached(tmp_path):
    config = settings(tmp_path)
    store = SessionStore(config.database_url)
    profile = FakeProfileClient(fail_update=True)
    orchestrator = ChatOrchestrator(config, store, profile, FakeLLMClient(profile.calls))
    request = ChatRequest(
        user_id="demo-xu", session_id="session-2", turn_id="turn-2", message="今天有点累"
    )

    response = asyncio.run(orchestrator.chat(request))
    cached = asyncio.run(orchestrator.chat(request))

    assert response.reply
    assert response.profile_update.status == "failed"
    assert response.profile_update.retryable is True
    assert cached.cached is True
    assert profile.calls == ["read", "llm", "update"]


def test_duplicate_turn_rejects_different_message(tmp_path):
    config = settings(tmp_path)
    store = SessionStore(config.database_url)
    profile = FakeProfileClient()
    orchestrator = ChatOrchestrator(config, store, profile, FakeLLMClient(profile.calls))
    original = ChatRequest(
        user_id="demo-xu", session_id="session-3", turn_id="turn-3", message="第一条"
    )
    asyncio.run(orchestrator.chat(original))

    try:
        asyncio.run(orchestrator.chat(original.model_copy(update={"message": "不同的第二条"})))
    except DuplicateTurnError:
        pass
    else:
        raise AssertionError("duplicate turn with a different message must be rejected")


def test_access_code_is_server_verified_and_sets_http_only_cookie(tmp_path):
    config = replace(settings(tmp_path), access_code="secret-demo-code")
    app = FastAPI()
    fake_profile = FakeProfileClient()
    store = SessionStore(config.database_url)
    orchestrator = ChatOrchestrator(
        config, store, fake_profile, FakeLLMClient(fake_profile.calls)
    )
    register_companion_api(app, settings=config, store=store, orchestrator=orchestrator)

    with TestClient(app) as client:
        blocked = client.get("/api/v1/companion/sessions/session/messages")
        assert blocked.status_code == 401
        wrong = client.post("/api/v1/access/login", json={"code": "wrong"})
        assert wrong.status_code == 401
        login = client.post("/api/v1/access/login", json={"code": "secret-demo-code"})
        assert login.status_code == 200
        cookie = login.headers["set-cookie"]
        assert "HttpOnly" in cookie
        assert "secret-demo-code" not in cookie
        allowed = client.get("/api/v1/companion/sessions/session/messages")
        assert allowed.status_code == 200
