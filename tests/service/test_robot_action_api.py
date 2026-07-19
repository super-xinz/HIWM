from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from handlers.hiwm.ledger import ImmutableJSONLLedger
from handlers.hiwm.models import SafetyFallbackPayload
from service.frontend_service.robot_action_api import register_robot_action_api
from tests.hiwm.fixtures import make_payload


def _robot_client(root: Path) -> TestClient:
    app = FastAPI()
    register_robot_action_api(
        app,
        SimpleNamespace(
            handler_registries={
                "HIWM": SimpleNamespace(
                    handler_config=SimpleNamespace(ledger_dir=str(root))
                )
            }
        ),
    )
    return TestClient(app)


def test_robot_capabilities_are_explicitly_speech_only(tmp_path: Path):
    with _robot_client(tmp_path) as client:
        response = client.get("/api/v1/robot/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["supported_commands"] == ["speak"]
    assert body["physical_motion_enabled"] is False
    assert body["raw_media_exposed"] is False
    assert body["exactly_once_delivery"] is False


def test_robot_commands_are_derived_from_verified_locked_records(tmp_path: Path):
    payload = make_payload()
    ledger = ImmutableJSONLLedger(tmp_path, payload.session_id)
    prediction = ledger.append(payload)
    fallback = ledger.append_fallback(
        SafetyFallbackPayload(
            session_id=payload.session_id,
            turn_id="fallback-turn",
            stage="api",
            action_id="clarify",
            utterance="请换一种说法。",
            reason="预测不可用",
            locked_at=payload.locked_at + 1,
        )
    )

    with _robot_client(tmp_path) as client:
        response = client.get(
            f"/api/v1/robot/sessions/{payload.session_id}/commands"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["delivery"] == "at_least_once"
    assert body["next_cursor"] == "fallback-turn"
    assert [item["turn_id"] for item in body["commands"]] == [
        payload.turn_id,
        "fallback-turn",
    ]
    first, second = body["commands"]
    selected = next(
        action
        for action in payload.actions
        if action.action_id == payload.selected_action_id
    )
    assert first["idempotency_key"] == f"{payload.session_id}:{payload.turn_id}"
    assert first["command"] == {
        "type": "speak",
        "strategy": selected.strategy,
        "text": selected.utterance,
        "fallback": False,
    }
    assert first["source_lock"]["sha256"] == prediction.locked_prediction.sha256
    assert second["command"]["fallback"] is True
    assert second["source_lock"]["sha256"] == fallback.locked_prediction.sha256


def test_robot_cursor_returns_only_newer_commands_and_rejects_unknown_cursor(
    tmp_path: Path,
):
    payload = make_payload()
    ledger = ImmutableJSONLLedger(tmp_path, payload.session_id)
    ledger.append(payload)
    ledger.append_fallback(
        SafetyFallbackPayload(
            session_id=payload.session_id,
            turn_id="next-turn",
            stage="api",
            action_id="wait",
            utterance="我们可以稍后继续。",
            reason="预测不可用",
            locked_at=payload.locked_at + 1,
        )
    )

    with _robot_client(tmp_path) as client:
        response = client.get(
            f"/api/v1/robot/sessions/{payload.session_id}/commands",
            params={"after_turn_id": payload.turn_id},
        )
        invalid = client.get(
            f"/api/v1/robot/sessions/{payload.session_id}/commands",
            params={"after_turn_id": "unknown-turn"},
        )

    assert [item["turn_id"] for item in response.json()["commands"]] == [
        "next-turn"
    ]
    assert invalid.status_code == 400
    assert "bounded ledger window" in invalid.json()["detail"]


def test_robot_api_uses_runtime_control_auth_when_enabled(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("HIWM_RUNTIME_CONTROL_TOKEN", "robot-access-token")

    with _robot_client(tmp_path) as client:
        denied = client.get("/api/v1/robot/capabilities")
        allowed = client.get(
            "/api/v1/robot/capabilities",
            headers={"Authorization": "Bearer robot-access-token"},
        )

    assert denied.status_code == 403
    assert allowed.status_code == 200
