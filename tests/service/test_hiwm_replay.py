from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from handlers.hiwm.ledger import ImmutableJSONLLedger
from handlers.hiwm.models import SafetyFallbackPayload
from service.frontend_service.hiwm_replay import (
    load_verified_timeline,
    register_hiwm_replay,
    resolve_session_ledger,
)
from tests.hiwm.fixtures import make_payload


def test_verified_replay_reads_predictions_and_probability_free_fallback(tmp_path: Path):
    payload = make_payload()
    ledger = ImmutableJSONLLedger(tmp_path, payload.session_id)
    normal = ledger.append(payload)
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

    events = load_verified_timeline(tmp_path, payload.session_id)

    assert [event["event_type"] for event in events] == [
        "prediction",
        "safe_fallback",
    ]
    assert events[0]["record"]["locked_prediction"]["sha256"] == (
        normal.locked_prediction.sha256
    )
    assert events[1]["record"]["probability_kind"] == "unavailable"
    assert events[1]["record"]["locked_prediction"]["sha256"] == (
        fallback.locked_prediction.sha256
    )


def test_replay_rejects_tampering(tmp_path: Path):
    payload = make_payload()
    ledger = ImmutableJSONLLedger(tmp_path, payload.session_id)
    record = ledger.append(payload).model_dump(mode="json")
    record["actions"][0]["utterance"] = "tampered"
    ledger.path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="verification"):
        load_verified_timeline(tmp_path, payload.session_id)


@pytest.mark.parametrize("session_id", ["../secret", "a/b", "", "🙂"])
def test_session_path_rejects_traversal(tmp_path: Path, session_id: str):
    with pytest.raises(ValueError, match="invalid session"):
        resolve_session_ledger(tmp_path, session_id)


def _replay_client(root: Path, *, enabled: bool = True) -> TestClient:
    registries = {}
    if enabled:
        registries["HIWM"] = SimpleNamespace(
            handler_config=SimpleNamespace(ledger_dir=str(root))
        )
    app = FastAPI()
    register_hiwm_replay(
        app,
        SimpleNamespace(handler_registries=registries),
    )
    return TestClient(app)


def test_get_timeline_returns_empty_bounded_envelope(tmp_path: Path):
    with _replay_client(tmp_path) as client:
        response = client.get(
            "/api/v1/sessions/empty-session/timeline"
        )

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "session_id": "empty-session",
        "raw_media_persisted": False,
        "events": [],
    }


def test_get_timeline_returns_verified_prediction_and_fallback(tmp_path: Path):
    payload = make_payload()
    ledger = ImmutableJSONLLedger(tmp_path, payload.session_id)
    normal = ledger.append(payload)
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

    with _replay_client(tmp_path) as client:
        response = client.get(
            f"/api/v1/sessions/{payload.session_id}/timeline"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["raw_media_persisted"] is False
    assert [event["event_type"] for event in body["events"]] == [
        "prediction",
        "safe_fallback",
    ]
    assert body["events"][0]["record"]["locked_prediction"]["sha256"] == (
        normal.locked_prediction.sha256
    )
    assert body["events"][1]["record"]["locked_prediction"]["sha256"] == (
        fallback.locked_prediction.sha256
    )


def test_get_timeline_rejects_invalid_id_and_disabled_hiwm(tmp_path: Path):
    with _replay_client(tmp_path) as client:
        invalid = client.get(
            "/api/v1/sessions/invalid%21session/timeline"
        )
    assert invalid.status_code == 400
    assert invalid.json() == {"detail": "invalid session id"}

    with _replay_client(tmp_path, enabled=False) as client:
        disabled = client.get(
            "/api/v1/sessions/valid-session/timeline"
        )
    assert disabled.status_code == 404
    assert disabled.json() == {"detail": "HIWM is not enabled"}


def test_delete_session_removes_existing_ledger_and_is_idempotent(tmp_path: Path):
    session_id = "delete-session"
    ledger_path = resolve_session_ledger(tmp_path, session_id)
    ledger_path.write_text("local-test-record\n", encoding="utf-8")

    with _replay_client(tmp_path) as client:
        first = client.delete(f"/api/v1/sessions/{session_id}")
        second = client.delete(f"/api/v1/sessions/{session_id}")

    assert first.status_code == 200
    assert first.json() == {"session_id": session_id, "deleted": True}
    assert not ledger_path.exists()
    assert second.status_code == 200
    assert second.json() == {"session_id": session_id, "deleted": False}


def test_delete_session_rejects_invalid_id_and_disabled_hiwm(tmp_path: Path):
    with _replay_client(tmp_path) as client:
        invalid = client.delete(
            "/api/v1/sessions/invalid%21session"
        )
    assert invalid.status_code == 400
    assert invalid.json() == {"detail": "invalid session id"}

    with _replay_client(tmp_path, enabled=False) as client:
        disabled = client.delete(
            "/api/v1/sessions/valid-session"
        )
    assert disabled.status_code == 404
    assert disabled.json() == {"detail": "HIWM is not enabled"}


def test_replay_requires_bearer_token_when_cloud_access_is_enabled(
    tmp_path: Path, monkeypatch
):
    token = "deployment-access-token"
    monkeypatch.setenv("HIWM_RUNTIME_CONTROL_TOKEN", token)

    with _replay_client(tmp_path) as client:
        denied = client.get(
            "/api/v1/sessions/cloud-session/timeline"
        )
        allowed = client.get(
            "/api/v1/sessions/cloud-session/timeline",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert denied.status_code == 403
    assert allowed.status_code == 200


def test_legacy_replay_route_remains_available_during_namespace_migration(
    tmp_path: Path,
):
    with _replay_client(tmp_path) as client:
        response = client.get(
            "/openavatarchat/hiwm/sessions/legacy-session/timeline"
        )

    assert response.status_code == 200
    assert response.json()["session_id"] == "legacy-session"
