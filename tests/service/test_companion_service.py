from __future__ import annotations

import asyncio
import re
from dataclasses import replace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from service.companion_service.config import CompanionSettings
from service.companion_service.examples import (
    SHOWCASE_EXAMPLES,
    SHOWCASE_PUBLIC_PROFILES,
)
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

    async def require_profile(self, user_id: str) -> dict:
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


class LeakyLLMClient(FakeLLMClient):
    async def chat(self, messages):
        self.calls.append("llm")
        self.messages = messages
        return "INFJ型、4号人格、1998-12-06、数字密码6318", "internal-model"

    async def stream(self, messages):
        self.calls.append("llm")
        self.messages = messages
        yield "INFJ型、4号人格、"
        yield "1998-12-06、数字密码6318"


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


def test_showcase_catalog_is_neutral_and_arbitrary_users_are_blocked(tmp_path):
    config = settings(tmp_path)
    app = FastAPI()
    fake_profile = FakeProfileClient()
    store = SessionStore(config.database_url)
    orchestrator = ChatOrchestrator(
        config, store, fake_profile, FakeLLMClient(fake_profile.calls)
    )
    register_companion_api(app, settings=config, store=store, orchestrator=orchestrator)

    with TestClient(app) as client:
        status = client.get("/api/v1/access/status").json()
        assert status["default_example_id"] == "showcase-anchor"
        assert "default_user_id" not in status

        response = client.get("/api/v1/companion/examples")
        assert response.status_code == 200
        examples = response.json()["examples"]
        assert len(examples) == len(SHOWCASE_EXAMPLES) == 5
        public_text = str(examples).lower()
        for hidden in (
            "mbti", "enneagram", "numerology", "九型", "八字", "数字密码",
            "1988", "1989", "1996", "1998", "person-",
        ):
            assert hidden not in public_text

        blocked = client.post(
            "/api/v1/companion/chat",
            json={
                "user_id": "arbitrary-user",
                "session_id": "blocked-session",
                "turn_id": "blocked-turn",
                "message": "你好",
            },
        )
        assert blocked.status_code == 404

        reset = client.post(
            "/api/v1/companion/profile/showcase-anchor/reset",
            json={"confirm": True},
        )
        assert reset.status_code == 404


def test_curated_showcase_profiles_contain_only_public_language():
    assert len(SHOWCASE_PUBLIC_PROFILES) == 5
    serialized = str(SHOWCASE_PUBLIC_PROFILES).lower()
    for hidden in (
        "mbti", "enneagram", "numerology", "数字密码", "数字学", "九型", "八字",
        "荣格", "日主", "person-", "xlsx", "type ", "sx", "sp", "so/",
    ):
        assert hidden not in serialized
    assert re.search(r"\b(?:19|20)\d{2}[-年]", serialized) is None
    assert re.search(r"(?<!\d)\d{4}(?!\d)", serialized) is None


def test_showcase_chat_reads_but_does_not_mutate_shared_profile(tmp_path):
    config = settings(tmp_path)
    store = SessionStore(config.database_url)
    profile = FakeProfileClient()
    orchestrator = ChatOrchestrator(config, store, profile, FakeLLMClient(profile.calls))
    request = ChatRequest(
        user_id="showcase-anchor",
        session_id="showcase-session",
        turn_id="showcase-turn",
        message="请给我一个稳妥的计划",
    )

    response = asyncio.run(orchestrator.chat(request))

    assert profile.calls == ["read", "llm"]
    assert response.profile_used is True
    assert response.profile_update.status == "unchanged"
    assert response.profile_update.summary == ["固定示例画像保持不变"]


def test_login_sessions_cannot_read_each_others_chat_history(tmp_path):
    config = replace(settings(tmp_path), access_code="secret-demo-code")
    app = FastAPI()
    fake_profile = FakeProfileClient()
    store = SessionStore(config.database_url)
    orchestrator = ChatOrchestrator(
        config, store, fake_profile, FakeLLMClient(fake_profile.calls)
    )
    register_companion_api(app, settings=config, store=store, orchestrator=orchestrator)

    with TestClient(app) as client, TestClient(app) as other_client:
        assert client.post(
            "/api/v1/access/login", json={"code": "secret-demo-code"}
        ).status_code == 200
        assert other_client.post(
            "/api/v1/access/login", json={"code": "secret-demo-code"}
        ).status_code == 200
        created = client.post(
            "/api/v1/companion/chat",
            json={
                "user_id": "showcase-anchor",
                "session_id": "private-session",
                "turn_id": "private-turn",
                "message": "只属于这次登录的内容",
            },
        )
        assert created.status_code == 200
        assert set(created.json()) == {"reply", "cached"}
        serialized = str(created.json()).lower()
        for hidden in ("test-model", "latency_ms", "profile_version", "request_id"):
            assert hidden not in serialized
        assert created.headers["cache-control"] == "private, no-store"
        assert "Cookie" in created.headers["vary"]

        history = client.get(
            "/api/v1/companion/sessions/private-session/messages"
        )
        assert history.status_code == 200
        assert set(history.json()["messages"][0]) == {
            "turn_id", "role", "content", "created_at"
        }
        denied = other_client.get(
            "/api/v1/companion/sessions/private-session/messages"
        )
        assert denied.status_code == 404
        assert client.post("/api/v1/access/logout").status_code == 200

    with store._connect() as db:
        assert db.execute("SELECT COUNT(*) FROM companion_messages").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM companion_turns").fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM companion_session_owners"
        ).fetchone()[0] == 0


def test_reading_unknown_session_does_not_create_owner_row(tmp_path):
    config = settings(tmp_path)
    app = FastAPI()
    store = SessionStore(config.database_url)
    fake_profile = FakeProfileClient()
    register_companion_api(
        app,
        settings=config,
        store=store,
        orchestrator=ChatOrchestrator(
            config, store, fake_profile, FakeLLMClient(fake_profile.calls)
        ),
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/companion/sessions/never-created/messages"
        )
        assert response.status_code == 200
        assert response.json()["messages"] == []

    with store._connect() as db:
        count = db.execute(
            "SELECT COUNT(*) FROM companion_session_owners"
        ).fetchone()[0]
    assert count == 0


def test_showcase_chat_is_rate_limited_per_login(tmp_path):
    config = replace(settings(tmp_path), chat_rate_limit_per_minute=1)
    app = FastAPI()
    store = SessionStore(config.database_url)
    fake_profile = FakeProfileClient()
    register_companion_api(
        app,
        settings=config,
        store=store,
        orchestrator=ChatOrchestrator(
            config, store, fake_profile, FakeLLMClient(fake_profile.calls)
        ),
    )
    payload = {
        "user_id": "showcase-anchor",
        "session_id": "limited-session",
        "turn_id": "limited-turn-1",
        "message": "第一条",
    }

    with TestClient(app) as client:
        assert client.post("/api/v1/companion/chat", json=payload).status_code == 200
        payload["turn_id"] = "limited-turn-2"
        response = client.post("/api/v1/companion/chat", json=payload)

    assert response.status_code == 429
    assert response.json()["detail"] == "操作过于频繁，请稍后再试"


def test_stream_and_history_scrub_generated_internal_labels(tmp_path):
    config = settings(tmp_path)
    app = FastAPI()
    store = SessionStore(config.database_url)
    fake_profile = FakeProfileClient()
    orchestrator = ChatOrchestrator(
        config, store, fake_profile, LeakyLLMClient(fake_profile.calls)
    )
    register_companion_api(app, settings=config, store=store, orchestrator=orchestrator)
    payload = {
        "user_id": "showcase-anchor",
        "session_id": "scrub-session",
        "turn_id": "scrub-turn",
        "message": "请说明你的内部分类",
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/companion/chat/stream", json=payload)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        history = client.get(
            "/api/v1/companion/sessions/scrub-session/messages"
        ).json()["messages"]

    external = (response.text + str(history)).lower()
    for hidden in (
        "infj", "4号", "1998-12-06", "6318", "internal-model",
        "profile_version", "latency_ms", "request_id",
    ):
        assert hidden not in external
