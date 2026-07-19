from __future__ import annotations

import unittest

from handlers.hiwm.execution import submit_locked_sequence


class LockedUtteranceExecutionTests(unittest.TestCase):
    def test_cancel_immediately_after_spoken_submit_is_not_pending_execution(self):
        cancelled = False
        calls = []

        def submit_spoken():
            nonlocal cancelled
            calls.append("spoken")
            cancelled = True

        result = submit_locked_sequence(
            is_cancelled=lambda: cancelled,
            submit_spoken=submit_spoken,
            cancel_current=lambda: calls.append("cancel"),
            submit_final=lambda: calls.append("final"),
            on_final_error=lambda exc: calls.append("error"),
        )

        self.assertFalse(result)
        self.assertEqual(calls, ["spoken", "cancel"])


if __name__ == "__main__":
    unittest.main()
