from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from handlers.hiwm.ledger import (
    ImmutableJSONLLedger,
    canonical_json_bytes,
    prediction_sha256,
)
from handlers.hiwm.models import LockedPredictionRecord, SafetyFallbackPayload
from tests.hiwm.fixtures import make_payload


class LedgerTests(unittest.TestCase):
    def test_ledger_appends_fsync_record_and_verifies_hash(self):
        payload = make_payload()
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = ImmutableJSONLLedger(Path(temp_dir), payload.session_id)
            record = ledger.append(payload)

            self.assertTrue(ledger.path.exists())
            self.assertTrue(ledger.verify(record))
            self.assertEqual(record.locked_prediction.prediction_id, payload.turn_id)
            self.assertEqual(
                record.locked_prediction.action_id, payload.selected_action_id
            )
            self.assertEqual(ledger.read_last(), record)
            self.assertEqual(
                len(ledger.path.read_text(encoding="utf-8").splitlines()), 1
            )

    def test_ledger_hash_detects_post_lock_mutation(self):
        payload = make_payload()
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = ImmutableJSONLLedger(Path(temp_dir), payload.session_id)
            record = ledger.append(payload)
            tampered = record.model_dump(mode="json")
            tampered["actions"][0]["utterance"] = "被事后改写的测试文本"
            tampered_record = LockedPredictionRecord.model_validate(tampered)

            self.assertFalse(ledger.verify(tampered_record))

    def test_legacy_v1_record_without_information_gain_still_verifies(self):
        payload = make_payload()
        legacy_payload = payload.model_dump(mode="json")
        for action in legacy_payload["actions"]:
            action.pop("information_gain")
        legacy_payload["planner"]["formula"] = "goal-risk-uncertainty-v1"
        legacy_payload["planner"]["weights"].pop("information_gain")
        for score in legacy_payload["planner"]["scores"]:
            score.pop("information_gain_component")
        digest = prediction_sha256(legacy_payload)
        locked = {
            **legacy_payload,
            "locked_prediction": {
                "algorithm": "sha256",
                "prediction_id": payload.turn_id,
                "action_id": payload.selected_action_id,
                "sha256": digest,
                "locked_at": payload.locked_at,
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = ImmutableJSONLLedger(Path(temp_dir), payload.session_id)
            ledger.root_dir.mkdir(parents=True, exist_ok=True)
            ledger.path.write_bytes(canonical_json_bytes(locked) + b"\n")

            record = ledger.read_last()

            self.assertIsNotNone(record)
            assert record is not None
            self.assertTrue(ledger.verify(record))
            self.assertEqual(record.planner.formula, "goal-risk-uncertainty-v1")
            self.assertEqual(record.planner.weights.information_gain, 0.35)
            self.assertTrue(
                all(
                    score.information_gain_component == 0
                    for score in record.planner.scores
                )
            )

    def test_probability_free_safe_fallback_is_locked_before_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = ImmutableJSONLLedger(Path(temp_dir), "fallback-session")
            payload = SafetyFallbackPayload(
                session_id="fallback-session",
                turn_id="turn-fallback",
                stage="api",
                action_id="clarify",
                utterance="请你换一种说法可以吗？",
                reason="本轮预测不可用",
                locked_at=time.time(),
            )

            record = ledger.append_fallback(payload)

            self.assertTrue(ledger.verify_fallback(record))
            self.assertEqual(record.probability_kind, "unavailable")
            self.assertNotIn("goal_probability", record.model_dump())
            self.assertEqual(record.locked_prediction.action_id, "clarify")


if __name__ == "__main__":
    unittest.main()
