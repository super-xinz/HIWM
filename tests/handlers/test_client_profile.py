from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from chat_engine.data_models.client_profile import (
    ClientSessionProfilePayload,
    LatestClientSessionProfile,
    bind_latest_client_session_profile,
)


def test_profile_is_trimmed_replaced_and_cleared_by_revocation():
    store = LatestClientSessionProfile()
    store.apply(
        ClientSessionProfilePayload(
            consent=True,
            profile_id="visitor-1",
            initial_information="  已确认：希望本周完成试点。  ",
        ),
        wall_time=10.0,
    )

    snapshot = store.get()
    assert snapshot is not None
    assert snapshot.initial_information == "已确认：希望本周完成试点。"
    assert snapshot.observed_at == 10.0

    store.apply(ClientSessionProfilePayload(consent=False))
    assert store.get() is None


def test_profile_rejects_extra_fields_and_data_on_revocation():
    with pytest.raises(ValidationError):
        ClientSessionProfilePayload.model_validate(
            {
                "consent": True,
                "profile_id": "visitor-1",
                "initial_information": "已确认信息",
                "personality": "禁止的自由标签",
            }
        )
    with pytest.raises(ValidationError):
        ClientSessionProfilePayload(
            consent=False,
            profile_id="visitor-1",
            initial_information="不应随撤权发送",
        )


def test_profile_slot_is_shared_per_session_state_object():
    shared = SimpleNamespace()
    first = bind_latest_client_session_profile(shared)
    second = bind_latest_client_session_profile(shared)
    assert first is second
