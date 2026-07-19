from __future__ import annotations

import unittest

from pydantic import ValidationError

from handlers.hiwm.models import PlannerSafetyPolicy, PlannerWeights
from handlers.hiwm.planner import HIWMPlanner
from tests.hiwm.fixtures import make_actions


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.actions = make_actions()

    def test_planner_selects_by_goal_minus_risk_minus_uncertainty(self):
        planner = HIWMPlanner(
            PlannerWeights(goal=1.0, risk=1.0, uncertainty=0.5)
        )
        decision = planner.select(self.actions)

        # Fixture scores: A=.52, B=.395, C=.10. The server selects A even
        # though B has the largest raw goal probability.
        self.assertEqual(decision.selected_action_id, "action-a")
        self.assertEqual(
            [score.action_id for score in decision.scores],
            ["action-a", "action-b", "action-c"],
        )
        self.assertEqual(
            decision.formula,
            "goal-information-gain-risk-uncertainty-v2",
        )
        self.assertEqual(decision.weights.information_gain, 0.35)
        self.assertTrue(
            all(score.information_gain_component == 0 for score in decision.scores)
        )

    def test_information_gain_can_change_the_selected_action(self):
        actions = list(self.actions)
        actions[1] = actions[1].model_copy(update={"information_gain": 0.40})
        planner = HIWMPlanner(
            PlannerWeights(
                goal=1.0,
                risk=1.0,
                uncertainty=0.5,
                information_gain=0.35,
            )
        )

        decision = planner.select(actions)

        # Without information gain A=.52 and B=.395. B's explicit .14
        # information-gain component raises its auditable total to .535.
        self.assertEqual(decision.selected_action_id, "action-b")
        score_b = next(
            score for score in decision.scores if score.action_id == "action-b"
        )
        self.assertAlmostEqual(score_b.information_gain_component, 0.14)
        self.assertAlmostEqual(score_b.score, 0.535)

    def test_zero_information_gain_weight_preserves_v1_ranking(self):
        actions = list(self.actions)
        actions[1] = actions[1].model_copy(update={"information_gain": 1.0})
        planner = HIWMPlanner(
            PlannerWeights(
                goal=1.0,
                risk=1.0,
                uncertainty=0.5,
                information_gain=0.0,
            )
        )

        decision = planner.select(actions)

        self.assertEqual(decision.selected_action_id, "action-a")
        self.assertEqual(decision.formula, "goal-risk-uncertainty-v1")
        self.assertTrue(
            all(score.information_gain_component == 0 for score in decision.scores)
        )

    def test_information_gain_can_be_the_only_positive_weight(self):
        actions = [
            action.model_copy(update={"information_gain": gain})
            for action, gain in zip(self.actions, (0.0, 1.0, 0.5))
        ]
        planner = HIWMPlanner(
            PlannerWeights(
                goal=0.0,
                risk=0.0,
                uncertainty=0.0,
                information_gain=1.0,
            )
        )

        self.assertEqual(planner.select(actions).selected_action_id, "action-b")

    def test_all_zero_planner_weights_remain_invalid(self):
        with self.assertRaises(ValidationError):
            PlannerWeights(
                goal=0.0,
                risk=0.0,
                uncertainty=0.0,
                information_gain=0.0,
            )

    def test_planner_does_not_accept_non_three_action_sets(self):
        planner = HIWMPlanner(PlannerWeights())
        with self.assertRaisesRegex(ValueError, "exactly three"):
            planner.select(self.actions[:2])

    def test_all_unsafe_branches_force_explicit_clarification_exit(self):
        unsafe = [
            action.model_copy(
                update={
                    "risk_probability": 0.9,
                    "information_gain": 1.0 if action.action_id == "action-b" else 0.0,
                }
            )
            for action in self.actions
        ]
        planner = HIWMPlanner(
            PlannerWeights(),
            PlannerSafetyPolicy(max_risk_probability=0.7),
        )

        decision = planner.select(unsafe)

        self.assertEqual(decision.selected_action_id, "action-a")

    def test_all_unsafe_without_safe_exit_is_rejected(self):
        unsafe = [
            action.model_copy(
                update={"risk_probability": 0.9, "strategy": f"assert-{index}"}
            )
            for index, action in enumerate(self.actions)
        ]
        planner = HIWMPlanner(PlannerWeights())

        with self.assertRaisesRegex(ValueError, "clarify/wait"):
            planner.select(unsafe)


if __name__ == "__main__":
    unittest.main()
