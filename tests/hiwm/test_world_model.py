from __future__ import annotations

import hashlib
import json
import time
from types import SimpleNamespace

import pytest

from chat_engine.data_models.chat_data_type import ChatDataType
from chat_engine.data_models.client_profile import (
    ClientSessionProfilePayload,
    LatestClientSessionProfile,
)
from handlers.hiwm.hiwm_handler import (
    CapturedCameraFrame,
    HIWMConfig,
    HIWMContext,
    HandlerHIWM,
)
from handlers.hiwm.ledger import ImmutableJSONLLedger
from handlers.hiwm.models import (
    EvidenceReference,
    HIWMModelInference,
    ObservationSnapshot,
    PreviousTurnFeedback,
)
from handlers.hiwm.world_model import (
    HIWMResponseValidationError,
    OpenAICompatibleWorldModel,
)
from tests.hiwm.fixtures import (
    make_actions,
    make_beliefs,
    make_content_signals,
    make_observation,
    make_payload,
)


class _FakeCompletions:
    def __init__(self, contents: list[str]):
        self.contents = contents
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.contents[min(len(self.calls) - 1, len(self.contents) - 1)]
        return SimpleNamespace(
            id="response-test",
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        )


def _world_model(
    *contents: str, max_attempts: int = 2
) -> tuple[OpenAICompatibleWorldModel, _FakeCompletions]:
    completions = _FakeCompletions(list(contents))
    model = object.__new__(OpenAICompatibleWorldModel)
    model.api_url = "https://example.invalid/v1"
    model.model_name = "qwen3.5-omni-flash"
    model.temperature = 0.2
    model.input_modalities = frozenset({"text"})
    model.structured_output = True
    model.enable_thinking = False
    model.max_output_tokens = 4096
    model.max_attempts = max_attempts
    model._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return model, completions


def test_request_is_text_only_json_mode_with_thinking_disabled():
    observation = make_observation()
    inference = HIWMModelInference(
        content_signals=make_content_signals(),
        beliefs=make_beliefs(),
        actions=make_actions(),
        feedback=None,
    )
    model, completions = _world_model(inference.model_dump_json())

    result = model.infer(
        objective="测试目标",
        observation=observation,
        historical_beliefs=[],
        previous_locked_prediction=None,
        camera_data_url="data:image/jpeg;base64,not-transmitted",
    )

    assert result.inference == inference
    request = completions.calls[0]
    assert request["stream"] is False
    assert request["response_format"] == {"type": "json_object"}
    assert request["extra_body"] == {"enable_thinking": False}
    assert request["max_tokens"] == 4096
    user_content = request["messages"][1]["content"]
    assert isinstance(user_content, str)
    assert "image_url" not in user_content
    payload = json.loads(user_content)
    assert payload["required_response_schema"] == HIWMModelInference.model_json_schema()


def test_invalid_json_is_retried_once_then_rejected():
    model, completions = _world_model('{"actions":[]}', '{"beliefs":[]}')

    with pytest.raises(HIWMResponseValidationError, match="after 2 attempt"):
        model.infer(
            objective="测试目标",
            observation=make_observation(),
            historical_beliefs=[],
            previous_locked_prediction=None,
            camera_data_url=None,
        )

    assert len(completions.calls) == 2


def test_second_valid_response_succeeds_after_validation_retry():
    inference = HIWMModelInference(
        content_signals=make_content_signals(),
        beliefs=make_beliefs(),
        actions=make_actions(),
        feedback=None,
    )
    model, completions = _world_model('{"actions":[]}', inference.model_dump_json())

    result = model.infer(
        objective="测试目标",
        observation=make_observation(),
        historical_beliefs=[],
        previous_locked_prediction=None,
        camera_data_url=None,
    )

    assert result.inference == inference
    assert len(completions.calls) == 2
    retry_messages = completions.calls[1]["messages"]
    assert len(retry_messages) == 3
    repair = json.loads(retry_messages[2]["content"])
    assert repair["request_type"] == "schema_validation_retry"
    assert repair["validation_issues"] == ["content_signals:array_type"]
    assert '{"actions":[]}' not in retry_messages[2]["content"]


def test_prohibited_generated_claim_rejects_whole_response_and_retries():
    inference = HIWMModelInference(
        content_signals=make_content_signals(),
        beliefs=make_beliefs(),
        actions=make_actions(),
        feedback=None,
    )
    unsafe_payload = inference.model_dump(mode="json")
    unsafe_payload["actions"][0]["utterance"] = "The user is lying."
    model, completions = _world_model(
        json.dumps(unsafe_payload), inference.model_dump_json()
    )

    result = model.infer(
        objective="测试目标",
        observation=make_observation(),
        historical_beliefs=[],
        previous_locked_prediction=None,
        camera_data_url=None,
    )

    assert result.inference == inference
    assert len(completions.calls) == 2


def test_provider_adapter_normalizes_non_evidence_transport_fields_without_retry():
    observation = make_observation()
    inference = HIWMModelInference(
        content_signals=make_content_signals(),
        beliefs=make_beliefs(),
        actions=make_actions(),
        feedback=None,
    )
    payload = inference.model_dump(mode="json")
    payload["unexpected_provider_field"] = "ignored"
    current_evidence = [observation.current_asr.evidence_id]
    for row in payload["content_signals"]:
        row["evidence_refs"] = current_evidence
        row["confidence"] = str(row["confidence"])
        row["provider_note"] = "ignored"
    for row in payload["beliefs"]:
        row["id"] = "duplicate-belief-id"
        row["evidence_refs"] = current_evidence
        row["confidence"] = str(row["confidence"])
    for row in payload["actions"]:
        row["action_id"] = "duplicate-action-id"
        row["evidence_refs"] = current_evidence
        row.pop("information_gain")
        row["goal_probability"] = str(row["goal_probability"])
        row["risk_probability"] = str(row["risk_probability"])
        row["uncertainty"] = str(row["uncertainty"])
    payload["feedback"] = {
        "previous_turn_id": "invented-turn",
        "actual_observation": "不应在首轮保留",
        "comparison": "matched",
        "explanation": "不应在首轮保留",
        "evidence_refs": ["invented-evidence"],
    }
    model, completions = _world_model(
        json.dumps({"result": payload}, ensure_ascii=False), max_attempts=1
    )

    result = model.infer(
        objective="测试目标",
        observation=observation,
        historical_beliefs=[],
        previous_locked_prediction=None,
        camera_data_url=None,
    )

    assert len(completions.calls) == 1
    assert result.inference.feedback is None
    assert len({item.id for item in result.inference.beliefs}) == len(
        result.inference.beliefs
    )
    assert len({item.action_id for item in result.inference.actions}) == 3
    for item in result.inference.content_signals:
        assert item.evidence_refs == [observation.current_asr.evidence_id]
    for item in result.inference.beliefs:
        assert item.evidence_refs == [observation.current_asr.evidence_id]
    for item in result.inference.actions:
        assert item.evidence_refs == [observation.current_asr.evidence_id]
        assert item.information_gain == 0.0


@pytest.mark.parametrize(
    ("section", "replacement"),
    [
        ("content_signals", ["invented-evidence"]),
        ("beliefs", ["invented-evidence"]),
        ("actions", ["invented-evidence"]),
        ("content_signals", []),
        ("actions", []),
    ],
)
def test_provider_adapter_rejects_unknown_or_missing_required_evidence_refs(
    section, replacement
):
    inference = HIWMModelInference(
        content_signals=make_content_signals(),
        beliefs=make_beliefs(),
        actions=make_actions(),
        feedback=None,
    )
    payload = inference.model_dump(mode="json")
    payload[section][0]["evidence_refs"] = replacement
    # Force provider normalization instead of the direct strict parse path.
    payload["actions"][1]["goal_probability"] = str(
        payload["actions"][1]["goal_probability"]
    )
    model, completions = _world_model(
        json.dumps(payload, ensure_ascii=False), max_attempts=1
    )

    with pytest.raises(HIWMResponseValidationError, match="strict validation"):
        model.infer(
            objective="测试目标",
            observation=make_observation(),
            historical_beliefs=[],
            previous_locked_prediction=None,
            camera_data_url=None,
        )

    assert len(completions.calls) == 1


def test_provider_adapter_rejects_allowed_history_ref_when_current_asr_is_required():
    observation = make_observation()
    history_text = "Earlier observable conversation text."
    history = EvidenceReference(
        evidence_id="history:earlier",
        modality="history",
        source="test_history",
        observed_at=observation.current_asr.observed_at - 1,
        content=history_text,
        sha256=hashlib.sha256(history_text.encode("utf-8")).hexdigest(),
    )
    observation = observation.model_copy(update={"history": [history]})
    inference = HIWMModelInference(
        content_signals=make_content_signals(),
        beliefs=make_beliefs(),
        actions=make_actions(),
        feedback=None,
    )
    payload = inference.model_dump(mode="json")
    payload["content_signals"][0]["evidence_refs"] = [history.evidence_id]
    payload["actions"][1]["goal_probability"] = str(
        payload["actions"][1]["goal_probability"]
    )
    model, _ = _world_model(json.dumps(payload), max_attempts=1)

    with pytest.raises(HIWMResponseValidationError, match="strict validation"):
        model.infer(
            objective="测试目标",
            observation=observation,
            historical_beliefs=[],
            previous_locked_prediction=None,
            camera_data_url=None,
        )


def test_second_turn_request_carries_locked_prediction_and_valid_feedback(tmp_path):
    previous = ImmutableJSONLLedger(tmp_path, "two-turn-session").append(make_payload())
    text = "第二轮用户补充了更具体的需求。"
    observed_at = time.time()
    current_asr = make_observation().current_asr.model_copy(
        update={
            "evidence_id": "asr:second-turn",
            "observed_at": observed_at,
            "content": text,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }
    )
    observation = ObservationSnapshot(
        cutoff_at=observed_at,
        current_asr=current_asr,
    )
    evidence_refs = [current_asr.evidence_id]
    inference = HIWMModelInference(
        content_signals=[
            item.model_copy(update={"evidence_refs": evidence_refs})
            for item in make_content_signals()
        ],
        beliefs=[
            item.model_copy(update={"evidence_refs": evidence_refs})
            for item in make_beliefs()
        ],
        actions=[
            item.model_copy(update={"evidence_refs": evidence_refs})
            for item in make_actions()
        ],
        feedback=PreviousTurnFeedback(
            previous_turn_id=previous.turn_id,
            actual_observation="The user narrowed the requested outcome.",
            comparison="partial",
            explanation="The prior prediction was only partially observed.",
            evidence_refs=evidence_refs,
        ),
    )
    model, completions = _world_model(
        inference.model_dump_json(),
        max_attempts=1,
    )

    result = model.infer(
        objective="测试目标",
        observation=observation,
        historical_beliefs=previous.beliefs,
        previous_locked_prediction=previous,
        camera_data_url=None,
    )

    assert result.inference.feedback == inference.feedback
    request_payload = json.loads(completions.calls[0]["messages"][1]["content"])
    assert request_payload["previous_locked_prediction"]["turn_id"] == (
        previous.turn_id
    )
    assert request_payload["previous_locked_prediction"]["locked_prediction"] == (
        previous.locked_prediction.model_dump(mode="json")
    )
    assert len(request_payload["historical_beliefs"]) == len(previous.beliefs)


def test_json_object_is_extracted_from_provider_fence_without_retry():
    inference = HIWMModelInference(
        content_signals=make_content_signals(),
        beliefs=make_beliefs(),
        actions=make_actions(),
        feedback=None,
    )
    content = (
        "Here is the requested JSON object:\n```json\n"
        + inference.model_dump_json()
        + "\n```\n"
    )
    model, completions = _world_model(content, max_attempts=1)

    result = model.infer(
        objective="测试目标",
        observation=make_observation(),
        historical_beliefs=[],
        previous_locked_prediction=None,
        camera_data_url=None,
    )

    assert result.inference == inference
    assert len(completions.calls) == 1


def test_localized_clarification_strategy_is_canonicalized_without_retry():
    actions = make_actions()
    conservative = next(
        index
        for index, action in enumerate(actions)
        if action.strategy.casefold().startswith(("clarify", "wait"))
    )
    actions[conservative] = actions[conservative].model_copy(
        update={"strategy": "澄清当前需求"}
    )
    inference = HIWMModelInference(
        content_signals=make_content_signals(),
        beliefs=make_beliefs(),
        actions=actions,
        feedback=None,
    )
    model, completions = _world_model(inference.model_dump_json(), max_attempts=1)

    result = model.infer(
        objective="测试目标",
        observation=make_observation(),
        historical_beliefs=[],
        previous_locked_prediction=None,
        camera_data_url=None,
    )

    assert len(completions.calls) == 1
    assert (
        sum(
            action.strategy.casefold().startswith(("clarify", "wait"))
            for action in result.inference.actions
        )
        == 1
    )


def test_text_only_observation_drops_fresh_camera_evidence():
    context = HIWMContext("text-only-session")
    context.config = HIWMConfig(objective="测试目标", input_modalities=["text"])
    context.latest_camera = CapturedCameraFrame(
        evidence=EvidenceReference(
            evidence_id="camera:test",
            modality="camera",
            source="camera_video",
            observed_at=time.time(),
            sha256="0" * 64,
        ),
        data_url="data:image/jpeg;base64,not-transmitted",
    )
    handler = HandlerHIWM()

    detail = handler.get_handler_detail(None, context)
    observation, camera_data_url = handler._build_observation(
        context=context,
        inputs=SimpleNamespace(stream_id=None, source="BailianASR", timestamp=None),
        text="真实文本输入",
        turn_id="turn-test",
    )

    assert ChatDataType.CAMERA_VIDEO not in detail.inputs
    assert observation.camera is None
    assert camera_data_url is None


def test_confirmed_initial_profile_is_added_as_history_evidence():
    context = HIWMContext("profile-session")
    context.config = HIWMConfig(
        objective="测试目标",
        input_modalities=["text"],
        history_max_events=0,
    )
    context.client_session_profile = LatestClientSessionProfile()
    context.client_session_profile.apply(
        ClientSessionProfilePayload(
            consent=True,
            profile_id="visitor-1",
            initial_information="已确认：希望本周完成一个小型试点。",
        ),
        wall_time=123.0,
    )

    observation, _ = HandlerHIWM()._build_observation(
        context=context,
        inputs=SimpleNamespace(stream_id=None, source="BailianASR", timestamp=None),
        text="请先说说实施周期。",
        turn_id="turn-profile",
    )

    assert len(observation.history) == 1
    assert observation.history[0].source == "client_confirmed_profile"
    assert observation.history[0].metadata["confirmed_by_user"] is True


def test_hiwm_config_requires_text_and_unique_modalities():
    with pytest.raises(ValueError):
        HIWMConfig(objective="测试目标", input_modalities=["image"])
    with pytest.raises(ValueError):
        HIWMConfig(objective="测试目标", input_modalities=["text", "text"])
