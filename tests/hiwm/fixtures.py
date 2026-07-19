from __future__ import annotations

import hashlib
import time
from typing import List

from handlers.hiwm.models import (
    BeliefItem,
    CandidateAction,
    ContentSignal,
    EvidenceReference,
    ModelInfo,
    ObservationSnapshot,
    PlannerWeights,
    PredictionPayload,
    StateDelta,
)
from handlers.hiwm.planner import HIWMPlanner


def make_observation() -> ObservationSnapshot:
    text = "测试中的真实当前话语"
    return ObservationSnapshot(
        cutoff_at=time.time(),
        current_asr=EvidenceReference(
            evidence_id="asr:test-turn",
            modality="asr",
            source="test_asr",
            observed_at=time.time(),
            stream_key="stream_1_1",
            content=text,
            sha256=hashlib.sha256(text.encode()).hexdigest(),
            metadata={"finalized": True},
        ),
        history=[],
    )


def make_beliefs() -> List[BeliefItem]:
    return [
        BeliefItem(
            id="belief-1",
            statement="测试夹具中的当前话语包含一个待回应的问题",
            status="known",
            confidence=0.9,
            evidence_refs=["asr:test-turn"],
            change="new",
        )
    ]


def make_content_signals() -> List[ContentSignal]:
    return [
        ContentSignal(
            id="content-1",
            category="question",
            statement="测试夹具中的当前话语提出了一个问题",
            confidence=0.95,
            evidence_refs=["asr:test-turn"],
            change="new",
        )
    ]


def make_actions() -> List[CandidateAction]:
    return [
        CandidateAction(
            action_id="action-a",
            strategy="clarify",
            utterance="测试夹具动作甲",
            predicted_observation="测试夹具预测甲",
            predicted_state_delta=[
                StateDelta(target="shared_context", predicted_change="测试变化甲")
            ],
            goal_probability=0.72,
            risk_probability=0.10,
            risk="测试风险甲",
            uncertainty=0.20,
            evidence_refs=["asr:test-turn"],
        ),
        CandidateAction(
            action_id="action-b",
            strategy="explain",
            utterance="测试夹具动作乙",
            predicted_observation="测试夹具预测乙",
            predicted_state_delta=[
                StateDelta(target="shared_context", predicted_change="测试变化乙")
            ],
            goal_probability=0.82,
            risk_probability=0.35,
            risk="测试风险乙",
            uncertainty=0.15,
            evidence_refs=["asr:test-turn"],
        ),
        CandidateAction(
            action_id="action-c",
            strategy="summarize",
            utterance="测试夹具动作丙",
            predicted_observation="测试夹具预测丙",
            predicted_state_delta=[
                StateDelta(target="shared_context", predicted_change="测试变化丙")
            ],
            goal_probability=0.40,
            risk_probability=0.05,
            risk="测试风险丙",
            uncertainty=0.50,
            evidence_refs=["asr:test-turn"],
        ),
    ]


def make_payload() -> PredictionPayload:
    observation = make_observation()
    beliefs = make_beliefs()
    actions = make_actions()
    planner = HIWMPlanner(PlannerWeights(goal=1.0, risk=1.0, uncertainty=0.5))
    decision = planner.select(actions)
    now = time.time()
    return PredictionPayload(
        session_id="test-session",
        turn_id="test-turn",
        objective="测试目标",
        observation=observation,
        content_signals=make_content_signals(),
        beliefs=beliefs,
        actions=actions,
        selected_action_id=decision.selected_action_id,
        planner=decision,
        feedback=None,
        model=ModelInfo(
            model_name="test-model",
            api_url="https://example.invalid/v1",
            response_id="response-test",
            requested_at=now,
            completed_at=now,
        ),
        locked_at=now,
    )
