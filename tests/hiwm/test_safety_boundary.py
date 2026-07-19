from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from handlers.hiwm.models import HIWMModelInference, PreviousTurnFeedback
from tests.hiwm.fixtures import (
    make_actions,
    make_beliefs,
    make_content_signals,
    make_observation,
)


def _inference_payload(*, with_feedback: bool = False) -> dict[str, Any]:
    payload = HIWMModelInference(
        content_signals=make_content_signals(),
        beliefs=make_beliefs(),
        actions=make_actions(),
        feedback=None,
    ).model_dump(mode="python")
    if with_feedback:
        payload["feedback"] = {
            "previous_turn_id": "previous-turn",
            "actual_observation": "The user supplied a narrower requirement.",
            "comparison": "partial",
            "explanation": "The observed wording only partially matched the prediction.",
            "evidence_refs": ["asr:test-turn"],
        }
    return payload


def _replace(payload: dict[str, Any], path: tuple[Any, ...], value: str) -> None:
    target: Any = payload
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value


@pytest.mark.parametrize(
    ("path", "unsafe_text"),
    [
        (("content_signals", 0, "statement"), "用户的真实情绪是愤怒。"),
        (("content_signals", 0, "statement"), "用户现在很焦虑。"),
        (("beliefs", 0, "statement"), "The user is lying."),
        (("beliefs", 0, "statement"), "The user is gay."),
        (("actions", 0, "strategy"), "infer personality type"),
        (("actions", 0, "utterance"), "你的忠诚度很低。"),
        (("actions", 0, "utterance"), "Fire the employee."),
        (("actions", 0, "predicted_observation"), "The user has a mental illness."),
        (("actions", 0, "predicted_observation"), "She is dangerous."),
        (("actions", 0, "risk"), "这个员工应该被解雇。"),
        (("actions", 0, "risk"), "This candidate is suitable for promotion."),
        (
            ("actions", 0, "predicted_state_delta", 0, "target"),
            "political affiliation",
        ),
        (
            ("actions", 0, "predicted_state_delta", 0, "predicted_change"),
            "判断其性取向。",
        ),
        (("feedback", "explanation"), "The user is deceptive."),
    ],
)
def test_all_model_generated_claim_surfaces_reject_prohibited_inference(
    path, unsafe_text
):
    payload = _inference_payload(with_feedback=path[0] == "feedback")
    _replace(payload, path, unsafe_text)

    with pytest.raises(ValidationError, match="prohibited model-generated claim"):
        HIWMModelInference.model_validate(payload)


@pytest.mark.parametrize(
    ("path", "safe_text"),
    [
        (("content_signals", 0, "statement"), "不能判断真实情绪。"),
        (
            ("beliefs", 0, "statement"),
            "There is insufficient evidence to infer personality.",
        ),
        (("actions", 0, "strategy"), "avoid deception inference"),
        (("actions", 0, "utterance"), "我不能判断你是否在撒谎。"),
        (("actions", 0, "utterance"), "Do not fire the employee."),
        (
            ("actions", 0, "predicted_observation"),
            "A diagnosis cannot be made from these signals.",
        ),
        (("actions", 0, "risk"), "风险在于错误推断政治立场。"),
        (("actions", 0, "risk"), "The user is not dangerous."),
        (("actions", 0, "risk"), "这个员工不应该被解雇。"),
        (
            ("actions", 0, "predicted_state_delta", 0, "target"),
            "不推断性取向",
        ),
        (
            ("actions", 0, "predicted_state_delta", 0, "predicted_change"),
            "Personality cannot be inferred.",
        ),
        (("feedback", "explanation"), "不能据此判断忠诚度。"),
    ],
)
def test_explicit_refusal_or_safety_statement_is_allowed(path, safe_text):
    payload = _inference_payload(with_feedback=path[0] == "feedback")
    _replace(payload, path, safe_text)

    inference = HIWMModelInference.model_validate(payload)

    assert inference is not None


def test_user_actual_observation_is_not_scanned_as_a_model_claim():
    feedback = PreviousTurnFeedback(
        previous_turn_id="previous-turn",
        actual_observation=(
            "用户自述：我在撒谎，我的真实情绪很愤怒，我的政治立场也很明确。"
        ),
        comparison="indeterminate",
        explanation="The comparison records only the user's observable wording.",
        evidence_refs=["asr:test-turn"],
    )

    assert "真实情绪" in feedback.actual_observation


def test_safe_disclaimer_does_not_mask_a_later_prohibited_claim():
    payload = _inference_payload()
    payload["beliefs"][0]["statement"] = "不能判断真实情绪，但是用户在撒谎。"

    with pytest.raises(ValidationError, match="prohibited model-generated claim"):
        HIWMModelInference.model_validate(payload)


def test_normal_fixture_passes_claim_and_evidence_validation():
    inference = HIWMModelInference(
        content_signals=make_content_signals(),
        beliefs=make_beliefs(),
        actions=make_actions(),
        feedback=None,
    )

    inference.validate_against_observation(make_observation(), previous_turn_id=None)
