from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest

from service.companion_service.config import CompanionSettings
from service.companion_service.llm_client import LLMClient


def settings(tmp_path) -> CompanionSettings:
    return CompanionSettings(
        profile_engine_base_url="http://profile.test",
        profile_engine_api_key="profile-key",
        profile_engine_tenant_id="test-tenant",
        profile_engine_timeout_seconds=1,
        llm_api_base_url="https://api.deepseek.com/v1",
        llm_api_key="llm-key",
        llm_model="deepseek-v4-flash",
        llm_timeout_seconds=1,
        default_user_id="showcase-anchor",
        database_url=f"sqlite:///{tmp_path / 'chat.db'}",
        access_code="",
        access_session_ttl_seconds=3600,
        access_cookie_secure=False,
        profile_context_max_chars=4000,
        git_commit_sha="test-sha",
    )


class RecordingCompletions:
    def __init__(self):
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["stream"]:
            return self._stream()
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="正常回复"))],
            model=kwargs["model"],
        )

    async def _stream(self):
        yield SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="流式回复"))]
        )


class RecordingClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=RecordingCompletions())


def install_recording_client(monkeypatch, llm_client: LLMClient) -> RecordingClient:
    recording_client = RecordingClient()
    monkeypatch.setattr(llm_client, "_client", lambda: recording_client)
    return recording_client


def test_official_deepseek_v4_chat_disables_thinking(monkeypatch, tmp_path):
    llm_client = LLMClient(settings(tmp_path))
    recording_client = install_recording_client(monkeypatch, llm_client)

    reply, model = asyncio.run(llm_client.chat([{"role": "user", "content": "你好"}]))

    request = recording_client.chat.completions.calls[0]
    assert reply == "正常回复"
    assert model == "deepseek-v4-flash"
    assert request["stream"] is False
    assert request["extra_body"] == {"thinking": {"type": "disabled"}}


def test_official_deepseek_v4_stream_disables_thinking(monkeypatch, tmp_path):
    llm_client = LLMClient(settings(tmp_path))
    recording_client = install_recording_client(monkeypatch, llm_client)

    async def collect() -> list[str]:
        return [chunk async for chunk in llm_client.stream([])]

    assert asyncio.run(collect()) == ["流式回复"]
    request = recording_client.chat.completions.calls[0]
    assert request["stream"] is True
    assert request["extra_body"] == {"thinking": {"type": "disabled"}}


@pytest.mark.parametrize(
    ("base_url", "model"),
    [
        ("https://api.deepseek.com/v1", "deepseek-chat"),
        ("https://proxy.example.com/v1", "deepseek-v4-flash"),
        ("https://api.deepseek.com.example.com/v1", "deepseek-v4-flash"),
        ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    ],
)
def test_other_openai_compatible_requests_are_unchanged(
    monkeypatch, tmp_path, base_url, model
):
    config = replace(settings(tmp_path), llm_api_base_url=base_url, llm_model=model)
    llm_client = LLMClient(config)
    recording_client = install_recording_client(monkeypatch, llm_client)

    asyncio.run(llm_client.chat([]))

    request = recording_client.chat.completions.calls[0]
    assert "extra_body" not in request
