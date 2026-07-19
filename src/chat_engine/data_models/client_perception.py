"""Bounded, consent-gated client perception side-channel contracts.

Only derived, observable features are accepted. Raw audio, images, landmarks,
embeddings, free-form labels, and arbitrary metadata are deliberately absent
from these models and are rejected by ``extra="forbid"``.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Probability = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
HeadAngle = Annotated[float, Field(ge=-90.0, le=90.0, allow_inf_nan=False)]
PitchHz = Annotated[float, Field(ge=0.0, le=2_000.0, allow_inf_nan=False)]
PitchDeltaHz = Annotated[
    float, Field(ge=-2_000.0, le=2_000.0, allow_inf_nan=False)
]
EnergyDelta = Annotated[float, Field(ge=-1.0, le=1.0, allow_inf_nan=False)]
SpeechRate = Annotated[float, Field(ge=0.0, le=20.0, allow_inf_nan=False)]

ObservableFeatureName = Literal[
    "browInnerUp",
    "browDownLeft",
    "browDownRight",
    "eyeBlinkLeft",
    "eyeBlinkRight",
    "eyeWideLeft",
    "eyeWideRight",
    "jawOpen",
    "mouthPucker",
    "mouthSmileLeft",
    "mouthSmileRight",
    "mouthFrownLeft",
    "mouthFrownRight",
    "gazeLeft",
    "gazeRight",
    "gazeUp",
    "gazeDown",
]


class StrictPerceptionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class FaceDerivedFeatures(StrictPerceptionModel):
    """Visible face tracking output, never an inferred emotion or identity."""

    face_present: bool
    yaw: Optional[HeadAngle] = None
    pitch: Optional[HeadAngle] = None
    tracking_quality: Probability
    observable_features: list[ObservableFeatureName] = Field(
        default_factory=list,
        max_length=16,
    )

    @field_validator("observable_features")
    @classmethod
    def _unique_observable_features(
        cls, value: list[ObservableFeatureName]
    ) -> list[ObservableFeatureName]:
        if len(value) != len(set(value)):
            raise ValueError("observable_features must be unique")
        return value

    @model_validator(mode="after")
    def _no_face_has_no_face_measurements(self) -> "FaceDerivedFeatures":
        if not self.face_present and (
            self.yaw is not None
            or self.pitch is not None
            or self.observable_features
            or self.tracking_quality != 0.0
        ):
            raise ValueError(
                "face measurements must be empty when face_present is false"
            )
        return self


class SpeechDerivedFeatures(StrictPerceptionModel):
    """Bounded acoustic/prosodic measurements relative to the current speaker."""

    speech_active: bool
    rms: Probability
    pitch_hz: Optional[PitchHz] = None
    pitch_delta: Optional[PitchDeltaHz] = None
    energy_delta: Optional[EnergyDelta] = None
    pause_ms: Annotated[int, Field(ge=0, le=60_000)] = 0
    speech_rate: Optional[SpeechRate] = None


class ClientObservationPayload(StrictPerceptionModel):
    """Wire payload for ``SendClientObservation``.

    ``consent=false`` is a revocation command and must contain no features.
    Consent-bearing updates must contain at least one derived modality.
    """

    consent: bool
    face: Optional[FaceDerivedFeatures] = None
    speech: Optional[SpeechDerivedFeatures] = None

    @model_validator(mode="after")
    def _validate_consent_contract(self) -> "ClientObservationPayload":
        if not self.consent:
            if self.face is not None or self.speech is not None:
                raise ValueError("revocation payload must not contain features")
            return self
        if self.face is None and self.speech is None:
            raise ValueError("consented observation requires face or speech features")
        return self


class ClientPerceptionSnapshot(StrictPerceptionModel):
    """Server-timestamped snapshot safe to place in HIWM evidence metadata."""

    observed_at: Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
    face: Optional[FaceDerivedFeatures] = None
    speech: Optional[SpeechDerivedFeatures] = None


@dataclass(frozen=True)
class _StoredSnapshot:
    snapshot: ClientPerceptionSnapshot
    received_monotonic: float


class LatestClientPerception:
    """Thread-safe single-slot storage; updates replace rather than accumulate."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: Optional[_StoredSnapshot] = None

    def apply(
        self,
        payload: ClientObservationPayload,
        *,
        wall_time: Optional[float] = None,
        monotonic_time: Optional[float] = None,
    ) -> None:
        if not payload.consent:
            self.clear()
            return
        now_wall = time.time() if wall_time is None else wall_time
        now_monotonic = time.monotonic() if monotonic_time is None else monotonic_time
        snapshot = ClientPerceptionSnapshot(
            observed_at=now_wall,
            face=payload.face,
            speech=payload.speech,
        )
        with self._lock:
            self._latest = _StoredSnapshot(
                snapshot=snapshot,
                received_monotonic=now_monotonic,
            )

    def clear(self) -> None:
        with self._lock:
            self._latest = None

    def get_fresh(
        self,
        max_age_seconds: float,
        *,
        monotonic_time: Optional[float] = None,
    ) -> Optional[ClientPerceptionSnapshot]:
        if max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive")
        now = time.monotonic() if monotonic_time is None else monotonic_time
        with self._lock:
            stored = self._latest
            if stored is None:
                return None
            age = now - stored.received_monotonic
            if age < 0 or age > max_age_seconds:
                self._latest = None
                return None
            return stored.snapshot.model_copy(deep=True)


_SHARED_STATE_ATTRIBUTE = "_hiwm_latest_client_perception"
_SHARED_STATE_BIND_LOCK = threading.Lock()


def bind_latest_client_perception(shared_states: object) -> LatestClientPerception:
    """Attach one perception slot to the existing per-session shared state."""

    with _SHARED_STATE_BIND_LOCK:
        state = getattr(shared_states, _SHARED_STATE_ATTRIBUTE, None)
        if isinstance(state, LatestClientPerception):
            return state
        state = LatestClientPerception()
        setattr(shared_states, _SHARED_STATE_ATTRIBUTE, state)
        return state
