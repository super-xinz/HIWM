"""Small, dependency-free execution primitive for locked utterances."""

from __future__ import annotations

from typing import Callable


def submit_locked_sequence(
    *,
    is_cancelled: Callable[[], bool],
    submit_spoken: Callable[[], None],
    cancel_current: Callable[[], None],
    submit_final: Callable[[], None],
    on_final_error: Callable[[Exception], None],
) -> bool:
    """Submit one locked utterance and report whether it remains pending.

    Cancellation immediately after the non-final spoken bundle is submitted is
    *not* execution. The stream is cancelled, its empty final bundle is skipped,
    and ``False`` is returned so callers cannot promote a feedback baseline.

    A failure to close the stream is different: the spoken bundle has entered
    the pipeline and may still reach playback, so it remains pending for a real
    CLIENT_PLAYBACK terminal signal.
    """

    if is_cancelled():
        return False
    submit_spoken()
    if is_cancelled():
        cancel_current()
        return False
    try:
        submit_final()
    except Exception as exc:
        on_final_error(exc)
    return not is_cancelled()
