"""Deterministic planner for model-generated HIWM action predictions."""

from __future__ import annotations

from typing import Sequence

from .models import (
    ActionScore,
    CandidateAction,
    PlannerDecision,
    PlannerSafetyPolicy,
    PlannerWeights,
)


class HIWMPlanner:
    """Select an action without allowing the generative model to choose it."""

    def __init__(
        self,
        weights: PlannerWeights,
        safety_policy: PlannerSafetyPolicy | None = None,
    ):
        self.weights = weights
        self.safety_policy = safety_policy or PlannerSafetyPolicy()

    def select(self, actions: Sequence[CandidateAction]) -> PlannerDecision:
        if len(actions) != 3:
            raise ValueError("HIWM planner requires exactly three candidate actions")

        scores = []
        for action in actions:
            goal_component = self.weights.goal * action.goal_probability
            risk_component = self.weights.risk * action.risk_probability
            uncertainty_component = self.weights.uncertainty * action.uncertainty
            information_gain_component = (
                self.weights.information_gain * action.information_gain
            )
            score = (
                goal_component
                + information_gain_component
                - risk_component
                - uncertainty_component
            )
            scores.append(
                ActionScore(
                    action_id=action.action_id,
                    score=score,
                    goal_component=goal_component,
                    risk_component=risk_component,
                    uncertainty_component=uncertainty_component,
                    information_gain_component=information_gain_component,
                )
            )

        all_branches_unsafe = all(
            action.goal_probability < self.safety_policy.min_goal_probability
            or action.risk_probability > self.safety_policy.max_risk_probability
            or action.uncertainty > self.safety_policy.max_uncertainty
            for action in actions
        )
        if all_branches_unsafe:
            conservative_ids = {
                action.action_id
                for action in actions
                if action.strategy.strip().casefold().startswith(("clarify", "wait"))
            }
            if not conservative_ids:
                raise ValueError(
                    "unsafe candidate set has no explicit clarify/wait exit"
                )
            # The model cannot overrule this branch by inflating its goal
            # estimate: choose the conservative exit with the least combined
            # observable risk and uncertainty.
            conservative_actions = [
                action for action in actions if action.action_id in conservative_ids
            ]
            selected_action = min(
                conservative_actions,
                key=lambda action: (
                    action.risk_probability,
                    action.uncertainty,
                    -action.goal_probability,
                ),
            )
            selected = next(
                score for score in scores if score.action_id == selected_action.action_id
            )
        else:
            # max() is stable, so an exact tie follows declared candidate order.
            selected = max(scores, key=lambda item: item.score)
        return PlannerDecision(
            formula=(
                "goal-information-gain-risk-uncertainty-v2"
                if self.weights.information_gain > 0
                else "goal-risk-uncertainty-v1"
            ),
            weights=self.weights,
            scores=scores,
            selected_action_id=selected.action_id,
        )
