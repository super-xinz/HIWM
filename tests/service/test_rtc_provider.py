from __future__ import annotations

from service.rtc_service.rtc_provider import RTCProvider


def test_runtime_turn_config_is_absent_without_urls(monkeypatch):
    monkeypatch.delenv("HIWM_TURN_URLS", raising=False)
    monkeypatch.setenv("HIWM_TURN_USERNAME", "ignored")
    monkeypatch.setenv("HIWM_TURN_CREDENTIAL", "ignored")

    assert RTCProvider._runtime_turn_config() is None


def test_runtime_turn_config_parses_comma_separated_urls(monkeypatch):
    monkeypatch.setenv(
        "HIWM_TURN_URLS",
        "turn:turn.example.com:3478, turns:turn.example.com:5349 ",
    )
    monkeypatch.setenv("HIWM_TURN_USERNAME", "hiwm-user")
    monkeypatch.setenv("HIWM_TURN_CREDENTIAL", "hiwm-secret")

    assert RTCProvider._runtime_turn_config() == {
        "turn_provider": "turn_server",
        "urls": [
            "turn:turn.example.com:3478",
            "turns:turn.example.com:5349",
        ],
        "username": "hiwm-user",
        "credential": "hiwm-secret",
    }
