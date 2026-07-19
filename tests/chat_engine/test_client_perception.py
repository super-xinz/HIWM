from __future__ import annotations

import pytest
from pydantic import ValidationError

from chat_engine.data_models.client_perception import (
    ClientObservationPayload,
    LatestClientPerception,
)


def _valid_payload() -> dict:
    return {
        "consent": True,
        "face": {
            "face_present": True,
            "yaw": -12.5,
            "pitch": 4.0,
            "tracking_quality": 0.91,
            "observable_features": ["browInnerUp", "jawOpen"],
        },
        "speech": {
            "speech_active": True,
            "rms": 0.31,
            "pitch_hz": 188.0,
            "pitch_delta": 14.0,
            "energy_delta": 0.12,
            "pause_ms": 240,
            "speech_rate": 4.2,
        },
    }


def test_contract_accepts_only_bounded_derived_features():
    observation = ClientObservationPayload.model_validate(_valid_payload())

    assert observation.consent is True
    assert observation.face is not None
    assert observation.face.observable_features == ["browInnerUp", "jawOpen"]
    assert observation.speech is not None
    assert observation.speech.pitch_hz == 188.0


@pytest.mark.parametrize(
    "path,value",
    [
        (("face", "raw_frame"), "data:image/jpeg;base64,forbidden"),
        (("face", "landmarks"), [[0.1, 0.2, 0.3]]),
        (("speech", "raw_audio"), "AAAA"),
        (("speech", "transcript"), "free-form content is not accepted here"),
    ],
)
def test_contract_rejects_raw_media_and_arbitrary_fields(path, value):
    payload = _valid_payload()
    payload[path[0]][path[1]] = value

    with pytest.raises(ValidationError):
        ClientObservationPayload.model_validate(payload)


def test_contract_rejects_unbounded_or_free_form_measurements():
    invalid_angle = _valid_payload()
    invalid_angle["face"]["yaw"] = 120.0
    with pytest.raises(ValidationError):
        ClientObservationPayload.model_validate(invalid_angle)

    invented_label = _valid_payload()
    invented_label["face"]["observable_features"] = ["user_is_angry"]
    with pytest.raises(ValidationError):
        ClientObservationPayload.model_validate(invented_label)

    duplicate_label = _valid_payload()
    duplicate_label["face"]["observable_features"] = ["jawOpen", "jawOpen"]
    with pytest.raises(ValidationError):
        ClientObservationPayload.model_validate(duplicate_label)


def test_revocation_must_not_carry_features():
    assert ClientObservationPayload.model_validate({"consent": False}).consent is False

    with pytest.raises(ValidationError):
        ClientObservationPayload.model_validate(
            {"consent": False, "face": _valid_payload()["face"]}
        )


def test_latest_slot_replaces_expires_and_revokes():
    state = LatestClientPerception()
    first = ClientObservationPayload.model_validate(_valid_payload())
    state.apply(first, wall_time=100.0, monotonic_time=10.0)
    assert state.get_fresh(5.0, monotonic_time=14.9).observed_at == 100.0
    assert state.get_fresh(5.0, monotonic_time=15.1) is None

    second_data = _valid_payload()
    second_data["face"]["yaw"] = 22.0
    second = ClientObservationPayload.model_validate(second_data)
    state.apply(second, wall_time=101.0, monotonic_time=20.0)
    latest = state.get_fresh(5.0, monotonic_time=20.1)
    assert latest is not None
    assert latest.face is not None
    assert latest.face.yaw == 22.0

    state.apply(ClientObservationPayload.model_validate({"consent": False}))
    assert state.get_fresh(5.0, monotonic_time=20.2) is None
