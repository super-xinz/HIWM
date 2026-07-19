from __future__ import annotations

import time
from types import SimpleNamespace

from chat_engine.data_models.client_perception import (
    ClientObservationPayload,
    LatestClientPerception,
)
from handlers.hiwm.hiwm_handler import HIWMConfig, HIWMContext, HandlerHIWM


def _payload(consent: bool = True) -> ClientObservationPayload:
    if not consent:
        return ClientObservationPayload.model_validate({"consent": False})
    return ClientObservationPayload.model_validate(
        {
            "consent": True,
            "face": {
                "face_present": True,
                "yaw": 11.0,
                "pitch": -2.0,
                "tracking_quality": 0.93,
                "observable_features": ["browInnerUp"],
            },
            "speech": {
                "speech_active": True,
                "rms": 0.22,
                "pitch_hz": 172.0,
                "pitch_delta": 9.0,
                "energy_delta": 0.08,
                "pause_ms": 100,
                "speech_rate": 3.7,
            },
        }
    )


def _observation(context: HIWMContext):
    return HandlerHIWM()._build_observation(
        context=context,
        inputs=SimpleNamespace(stream_id=None, source="test_asr", timestamp=(1, 1)),
        text="这是最终转写文本",
        turn_id="turn-perception",
    )[0]


def test_fresh_consented_snapshot_is_attached_to_current_asr_metadata():
    context = HIWMContext("perception-session")
    context.config = HIWMConfig(
        objective="测试派生感知证据",
        perception_max_age_seconds=5.0,
    )
    context.client_perception = LatestClientPerception()
    context.client_perception.apply(_payload())

    perception = _observation(context).current_asr.metadata["perception"]
    assert set(perception) == {"observed_at", "face", "speech"}
    assert perception["face"]["observable_features"] == ["browInnerUp"]
    assert perception["speech"]["pitch_hz"] == 172.0
    assert "consent" not in perception


def test_stale_or_revoked_snapshot_is_not_attached():
    context = HIWMContext("perception-session")
    context.config = HIWMConfig(
        objective="测试派生感知证据",
        perception_max_age_seconds=1.0,
    )
    context.client_perception = LatestClientPerception()
    context.client_perception.apply(
        _payload(),
        monotonic_time=time.monotonic() - 2.0,
    )
    assert "perception" not in _observation(context).current_asr.metadata

    context.client_perception.apply(_payload())
    context.client_perception.apply(_payload(consent=False))
    assert "perception" not in _observation(context).current_asr.metadata
