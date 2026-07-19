from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from service.frontend_service.api_config import (
    build_public_api_config,
    configure_runtime_api_key,
)


def _manager_with_configs(secret: str):
    return SimpleNamespace(
        handler_registries={
            "BailianASR": SimpleNamespace(
                handler=SimpleNamespace(),
                handler_config=SimpleNamespace(
                    api_key=secret,
                    model_name="fun-asr-realtime",
                    base_websocket_url="wss://asr.example.invalid/inference",
                    sample_rate=16000,
                    format="pcm",
                )
            ),
            "HIWM": SimpleNamespace(
                handler=SimpleNamespace(_api_key=secret),
                handler_config=SimpleNamespace(
                    api_key_env="DASHSCOPE_API_KEY",
                    model_name="deepseek-v4-flash",
                    api_url="https://model.example.invalid/v1",
                    request_timeout_seconds=30,
                    temperature=0.2,
                    input_modalities=["text"],
                    structured_output=True,
                    enable_thinking=False,
                )
            ),
            "BailianTTS": SimpleNamespace(
                handler=SimpleNamespace(),
                handler_config=SimpleNamespace(
                    api_key=secret,
                    model_name="cosyvoice-v3-flash",
                    voice="longxing_v3",
                    sample_rate=24000,
                )
            ),
        }
    )


def test_public_api_config_has_fixed_secret_free_contract(monkeypatch):
    secret = "unit-test-secret-must-not-leak"
    monkeypatch.setenv("DASHSCOPE_API_KEY", secret)

    result = build_public_api_config(_manager_with_configs(secret))

    assert set(result) == {"schema_version", "asr", "hiwm", "tts"}
    assert set(result["asr"]) == {
        "provider",
        "model",
        "endpoint",
        "key_env",
        "configured",
        "sample_rate",
        "format",
    }
    assert set(result["hiwm"]) == {
        "provider",
        "model",
        "endpoint",
        "key_env",
        "configured",
        "timeout_seconds",
        "temperature",
        "streaming",
        "response_format",
        "input_modalities",
        "structured_output",
        "thinking_enabled",
    }
    assert set(result["tts"]) == {
        "provider",
        "model",
        "endpoint",
        "key_env",
        "configured",
        "voice",
        "sample_rate",
    }
    assert result["schema_version"] == "1.1"
    assert result["asr"]["configured"] is True
    assert result["hiwm"]["configured"] is True
    assert result["tts"]["configured"] is True
    assert result["hiwm"]["response_format"] == "json_object"
    assert result["hiwm"]["temperature"] == 0.2
    assert result["hiwm"]["streaming"] is False
    assert result["hiwm"]["input_modalities"] == ["text"]
    assert result["hiwm"]["structured_output"] is True
    assert result["hiwm"]["thinking_enabled"] is False
    assert result["tts"]["endpoint"] is None
    assert secret not in json.dumps(result, sort_keys=True)


def test_public_api_config_reports_absent_handlers_without_inventing_values(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    result = build_public_api_config(SimpleNamespace(handler_registries={}))

    for component in ("asr", "hiwm", "tts"):
        assert result[component]["provider"] is None
        assert result[component]["model"] is None
        assert result[component]["endpoint"] is None
        assert result[component]["configured"] is False


def test_public_api_config_does_not_report_ui_bootstrap_sentinel_as_a_key(monkeypatch):
    sentinel = "NOT_CONFIGURED_YET"
    monkeypatch.setenv("DASHSCOPE_API_KEY", sentinel)

    result = build_public_api_config(_manager_with_configs(sentinel))

    assert result["asr"]["configured"] is False
    assert result["hiwm"]["configured"] is False
    assert result["tts"]["configured"] is False


def test_runtime_api_key_updates_active_handlers_without_returning_secret(monkeypatch):
    sentinel = "NOT_CONFIGURED_YET"
    secret = "sk-runtime-unit-test-secret"
    monkeypatch.setenv("DASHSCOPE_API_KEY", sentinel)
    manager = _manager_with_configs(sentinel)

    result = configure_runtime_api_key(manager, f"  {secret}  ")

    assert result["asr"]["configured"] is True
    assert result["hiwm"]["configured"] is True
    assert result["tts"]["configured"] is True
    assert manager.handler_registries["BailianASR"].handler_config.api_key == secret
    assert manager.handler_registries["HIWM"].handler._api_key == secret
    assert manager.handler_registries["BailianTTS"].handler_config.api_key == secret
    assert secret not in json.dumps(result, sort_keys=True)


@pytest.mark.parametrize("value", ["", "short", "NOT_CONFIGURED_YET"])
def test_runtime_api_key_rejects_invalid_values_without_replacing_existing_key(
    monkeypatch, value
):
    existing = "sk-existing-unit-test-secret"
    monkeypatch.setenv("DASHSCOPE_API_KEY", existing)
    manager = _manager_with_configs(existing)

    with pytest.raises(ValueError):
        configure_runtime_api_key(manager, value)

    assert manager.handler_registries["HIWM"].handler._api_key == existing
    assert os.environ["DASHSCOPE_API_KEY"] == existing


def test_legacy_cosyvoice_registry_name_is_exposed_and_updated(monkeypatch):
    sentinel = "NOT_CONFIGURED_YET"
    secret = "sk-cosyvoice-runtime-test"
    monkeypatch.setenv("DASHSCOPE_API_KEY", sentinel)
    manager = SimpleNamespace(
        handler_registries={
            "CosyVoice": SimpleNamespace(
                handler=SimpleNamespace(),
                handler_config=SimpleNamespace(
                    api_key=sentinel,
                    model_name="cosyvoice-v1",
                    voice="longxiaochun",
                    sample_rate=24000,
                ),
            )
        }
    )

    before = build_public_api_config(manager)
    assert before["tts"]["provider"] == "dashscope"
    assert before["tts"]["configured"] is False

    after = configure_runtime_api_key(manager, secret)

    assert after["tts"]["configured"] is True
    assert manager.handler_registries["CosyVoice"].handler_config.api_key == secret
