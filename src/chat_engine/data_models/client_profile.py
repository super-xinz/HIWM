"""Consent-gated, session-local initial interaction profile contracts."""

from __future__ import annotations

import threading
import time
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictProfileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ClientSessionProfilePayload(StrictProfileModel):
    """A user-confirmed text profile or a consent revocation command."""

    consent: bool
    profile_id: Optional[Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{1,96}$")]] = None
    initial_information: Optional[Annotated[str, Field(min_length=1, max_length=4_000)]] = None

    @field_validator("initial_information")
    @classmethod
    def _strip_initial_information(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("initial_information must not be blank")
        return stripped

    @model_validator(mode="after")
    def _validate_consent_contract(self) -> "ClientSessionProfilePayload":
        if not self.consent:
            if self.profile_id is not None or self.initial_information is not None:
                raise ValueError("profile revocation must not contain profile data")
            return self
        if self.profile_id is None or self.initial_information is None:
            raise ValueError("consented profile requires id and initial information")
        return self


class ClientSessionProfileSnapshot(StrictProfileModel):
    profile_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{1,96}$")]
    initial_information: Annotated[str, Field(min_length=1, max_length=4_000)]
    observed_at: Annotated[float, Field(ge=0.0, allow_inf_nan=False)]


class LatestClientSessionProfile:
    """One thread-safe, session-local confirmed profile; no global identity store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: Optional[ClientSessionProfileSnapshot] = None

    def apply(
        self,
        payload: ClientSessionProfilePayload,
        *,
        wall_time: Optional[float] = None,
    ) -> None:
        if not payload.consent:
            self.clear()
            return
        snapshot = ClientSessionProfileSnapshot(
            profile_id=payload.profile_id,
            initial_information=payload.initial_information,
            observed_at=time.time() if wall_time is None else wall_time,
        )
        with self._lock:
            self._latest = snapshot

    def clear(self) -> None:
        with self._lock:
            self._latest = None

    def get(self) -> Optional[ClientSessionProfileSnapshot]:
        with self._lock:
            return self._latest.model_copy(deep=True) if self._latest is not None else None


_SHARED_STATE_ATTRIBUTE = "_hiwm_latest_client_session_profile"
_SHARED_STATE_BIND_LOCK = threading.Lock()


def bind_latest_client_session_profile(shared_states: object) -> LatestClientSessionProfile:
    with _SHARED_STATE_BIND_LOCK:
        state = getattr(shared_states, _SHARED_STATE_ATTRIBUTE, None)
        if isinstance(state, LatestClientSessionProfile):
            return state
        state = LatestClientSessionProfile()
        setattr(shared_states, _SHARED_STATE_ATTRIBUTE, state)
        return state
