from __future__ import annotations

import json
from types import SimpleNamespace

from loguru import logger

from chat_engine.data_models.client_perception import bind_latest_client_perception
from handlers.client.rtc_client.client_handler_rtc import RtcClientSessionDelegate
from service.rtc_service.rtc_stream import RtcStream


def _message(payload: dict) -> str:
    return json.dumps(
        {
            "header": {
                "name": "SendClientObservation",
                "request_id": "observation-test",
            },
            "payload": payload,
        }
    )


def _stream_and_state():
    shared_states = SimpleNamespace()
    state = bind_latest_client_perception(shared_states)
    delegate = RtcClientSessionDelegate()
    delegate.client_perception = state
    stream = object.__new__(RtcStream)
    stream.client_session_delegate = delegate
    stream.stream_start_delay = 0.5
    stream.chat_channel = None
    return stream, state


def test_rtc_side_channel_accepts_latest_consented_snapshot_and_revokes():
    stream, state = _stream_and_state()
    stream._handle_chat_datachannel_message(
        _message(
            {
                "consent": True,
                "face": {
                    "face_present": True,
                    "yaw": 8.0,
                    "pitch": -3.0,
                    "tracking_quality": 0.88,
                    "observable_features": ["eyeBlinkLeft"],
                },
                "speech": {
                    "speech_active": False,
                    "rms": 0.02,
                    "pitch_hz": None,
                    "pitch_delta": None,
                    "energy_delta": -0.1,
                    "pause_ms": 1300,
                    "speech_rate": None,
                },
            }
        )
    )

    latest = state.get_fresh(5.0)
    assert latest is not None
    assert latest.face is not None
    assert latest.face.yaw == 8.0

    # Revocation is fail-safe: even a buggy client carrying a forbidden field
    # cannot leave the previous consented snapshot resident.
    stream._handle_chat_datachannel_message(
        _message({"consent": False, "raw_frame": "must-not-be-stored"})
    )
    assert state.get_fresh(5.0) is None


def test_rtc_side_channel_rejects_raw_media_without_logging_payload():
    stream, state = _stream_and_state()
    sentinel = "forbidden-biometric-payload-sentinel"
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}", level="DEBUG")
    try:
        stream._handle_chat_datachannel_message(
            _message(
                {
                    "consent": True,
                    "face": {
                        "face_present": True,
                        "yaw": 0.0,
                        "pitch": 0.0,
                        "tracking_quality": 1.0,
                        "observable_features": [],
                        "raw_frame": sentinel,
                    },
                }
            )
        )
    finally:
        logger.remove(sink_id)

    assert state.get_fresh(5.0) is None
    assert sentinel not in "".join(messages)
