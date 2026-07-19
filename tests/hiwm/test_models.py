from __future__ import annotations

import unittest
from pydantic import ValidationError

from handlers.hiwm.models import HIWMModelInference, PreviousTurnFeedback
from tests.hiwm.fixtures import make_actions, make_beliefs, make_content_signals, make_observation


class ModelContractTests(unittest.TestCase):
    def setUp(self):
        self.observation = make_observation()
        self.beliefs = make_beliefs()
        self.actions = make_actions()
        self.content_signals = make_content_signals()

    def test_inference_requires_exactly_three_actions(self):
        valid = HIWMModelInference(
            content_signals=self.content_signals,
            beliefs=self.beliefs,
            actions=self.actions,
            feedback=None,
        )
        self.assertEqual(len(valid.actions), 3)

        with self.assertRaises(ValidationError):
            HIWMModelInference(
                content_signals=self.content_signals,
                beliefs=self.beliefs,
                actions=self.actions[:2],
                feedback=None,
            )

        fourth = self.actions[0].model_copy(
            update={
                "action_id": "action-four",
                "strategy": "ask_schedule",
                "utterance": "Which delivery date should we plan around?",
                "predicted_observation": "The user may provide a target date.",
                "risk": "The date may still be unknown.",
            }
        )
        with self.assertRaises(ValidationError):
            HIWMModelInference(
                content_signals=self.content_signals,
                beliefs=self.beliefs,
                actions=[*self.actions, fourth],
                feedback=None,
            )

    def test_probability_must_be_in_unit_interval(self):
        invalid = self.actions[0].model_dump()
        invalid["goal_probability"] = 1.01
        with self.assertRaises(ValidationError):
            HIWMModelInference(
                content_signals=self.content_signals,
                beliefs=self.beliefs,
                actions=[invalid, self.actions[1], self.actions[2]],
                feedback=None,
            )

    def test_information_gain_uses_probability_boundaries(self):
        lower = self.actions[0].model_copy(update={"information_gain": 0.0})
        upper = self.actions[1].model_copy(update={"information_gain": 1.0})
        valid = HIWMModelInference(
            content_signals=self.content_signals,
            beliefs=self.beliefs,
            actions=[lower, upper, self.actions[2]],
            feedback=None,
        )
        self.assertEqual(valid.actions[0].information_gain, 0.0)
        self.assertEqual(valid.actions[1].information_gain, 1.0)

        invalid = self.actions[0].model_dump()
        invalid["information_gain"] = 1.01
        with self.assertRaises(ValidationError):
            HIWMModelInference(
                content_signals=self.content_signals,
                beliefs=self.beliefs,
                actions=[invalid, self.actions[1], self.actions[2]],
                feedback=None,
            )

    def test_runtime_evidence_refs_cannot_be_invented(self):
        invalid = self.actions[0].model_copy(
            update={"evidence_refs": ["not-in-observation"]}
        )
        inference = HIWMModelInference(
            content_signals=self.content_signals,
            beliefs=self.beliefs,
            actions=[invalid, self.actions[1], self.actions[2]],
            feedback=None,
        )
        with self.assertRaisesRegex(ValueError, "unknown evidence"):
            inference.validate_against_observation(
                self.observation, previous_turn_id=None
            )

    def test_model_output_forbids_server_side_selection_field(self):
        value = {
            "content_signals": [item.model_dump() for item in self.content_signals],
            "beliefs": [item.model_dump() for item in self.beliefs],
            "actions": [item.model_dump() for item in self.actions],
            "feedback": None,
            "selected_action_id": self.actions[0].action_id,
        }
        with self.assertRaises(ValidationError):
            HIWMModelInference.model_validate(value)

    def test_second_turn_feedback_requires_matching_turn_and_current_evidence(self):
        evidence_id = self.observation.current_asr.evidence_id
        feedback = PreviousTurnFeedback(
            previous_turn_id="previous-turn",
            actual_observation="The user supplied a narrower requirement.",
            comparison="partial",
            explanation="The previous prediction was only partly observed.",
            evidence_refs=[evidence_id],
        )
        inference = HIWMModelInference(
            content_signals=self.content_signals,
            beliefs=self.beliefs,
            actions=self.actions,
            feedback=feedback,
        )

        inference.validate_against_observation(
            self.observation,
            previous_turn_id="previous-turn",
        )

        wrong_turn = inference.model_copy(
            update={
                "feedback": feedback.model_copy(
                    update={"previous_turn_id": "different-turn"}
                )
            }
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            wrong_turn.validate_against_observation(
                self.observation,
                previous_turn_id="previous-turn",
            )

        wrong_evidence = inference.model_copy(
            update={
                "feedback": feedback.model_copy(
                    update={"evidence_refs": ["invented-evidence"]}
                )
            }
        )
        with self.assertRaisesRegex(ValueError, "unknown evidence"):
            wrong_evidence.validate_against_observation(
                self.observation,
                previous_turn_id="previous-turn",
            )

        without_feedback = inference.model_copy(update={"feedback": None})
        with self.assertRaisesRegex(ValueError, "feedback is required"):
            without_feedback.validate_against_observation(
                self.observation,
                previous_turn_id="previous-turn",
            )


if __name__ == "__main__":
    unittest.main()
