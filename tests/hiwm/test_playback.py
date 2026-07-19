from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from handlers.hiwm.ledger import ImmutableJSONLLedger
from handlers.hiwm.playback import PlaybackFeedbackTracker
from tests.hiwm.fixtures import make_payload


def make_locked_record():
    payload = make_payload()
    temp_dir = tempfile.TemporaryDirectory()
    ledger = ImmutableJSONLLedger(Path(temp_dir.name), payload.session_id)
    return temp_dir, ledger.append(payload)


class PlaybackFeedbackTrackerTests(unittest.TestCase):
    def test_only_correlated_real_playback_end_promotes_pending_prediction(self):
        temp_dir, record = make_locked_record()
        self.addCleanup(temp_dir.cleanup)
        tracker = PlaybackFeedbackTracker()
        tracker.register(record, "avatar-text-1")

        self.assertIsNone(
            tracker.complete("playback-unrelated", {"other-avatar-text"})
        )
        self.assertIsNotNone(tracker.pending)

        tracker.bind_playback(
            "playback-1", {"avatar-audio-1", "avatar-text-1"}
        )
        self.assertEqual(tracker.complete("playback-1", set()), record)
        self.assertIsNone(tracker.pending)

    def test_correlated_playback_cancel_discards_without_promotion(self):
        temp_dir, record = make_locked_record()
        self.addCleanup(temp_dir.cleanup)
        tracker = PlaybackFeedbackTracker()
        tracker.register(record, "avatar-text-1")

        self.assertTrue(
            tracker.cancel_playback(
                "playback-1", {"avatar-audio-1", "avatar-text-1"}
            )
        )
        self.assertIsNone(tracker.pending)
        self.assertIsNone(
            tracker.complete("playback-1", {"avatar-text-1"})
        )

    def test_unrelated_playback_cancel_does_not_clear_unique_pending(self):
        """A unique pending item is insufficient without ancestry correlation."""

        temp_dir, record = make_locked_record()
        self.addCleanup(temp_dir.cleanup)
        tracker = PlaybackFeedbackTracker()
        tracker.register(record, "avatar-text-1")

        self.assertFalse(
            tracker.cancel_playback("playback-other", {"avatar-text-other"})
        )
        self.assertEqual(tracker.pending.record, record)


if __name__ == "__main__":
    unittest.main()
