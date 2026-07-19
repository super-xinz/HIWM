"""Thread-safe pending-to-executed correlation for real client playback."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Iterable, Optional

from .models import LockedPredictionRecord


@dataclass(frozen=True)
class PendingLockedPrediction:
    record: LockedPredictionRecord
    avatar_text_stream_key: str


class PlaybackFeedbackTracker:
    """Track one pending utterance until its descendant playback terminates.

    The HIWM handler is sequential, so only the newest response can be pending.
    Playback signals can arrive on another thread; all transitions are guarded.
    A playback key is accepted only when its ancestry contains the registered
    AVATAR_TEXT stream key. This prevents an unrelated playback END from
    promoting a prediction.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: Optional[PendingLockedPrediction] = None
        self._bound_playback_keys: set[str] = set()

    @property
    def pending(self) -> Optional[PendingLockedPrediction]:
        with self._lock:
            return self._pending

    def register(
        self, record: LockedPredictionRecord, avatar_text_stream_key: str
    ) -> None:
        if not avatar_text_stream_key:
            raise ValueError("avatar_text_stream_key must not be blank")
        with self._lock:
            self._pending = PendingLockedPrediction(
                record=record,
                avatar_text_stream_key=avatar_text_stream_key,
            )
            self._bound_playback_keys.clear()

    def bind_playback(
        self, playback_stream_key: Optional[str], ancestry_keys: Iterable[str]
    ) -> bool:
        with self._lock:
            if self._pending is None or not playback_stream_key:
                return False
            if self._pending.avatar_text_stream_key not in set(ancestry_keys):
                return False
            self._bound_playback_keys.add(playback_stream_key)
            return True

    def complete(
        self, playback_stream_key: Optional[str], ancestry_keys: Iterable[str]
    ) -> Optional[LockedPredictionRecord]:
        """Promote only a playback END correlated to the pending AVATAR_TEXT."""

        with self._lock:
            if not self._matches_locked(playback_stream_key, ancestry_keys):
                return None
            record = self._pending.record if self._pending is not None else None
            self._clear_locked()
            return record

    def cancel_playback(
        self, playback_stream_key: Optional[str], ancestry_keys: Iterable[str]
    ) -> bool:
        """Discard a correlated playback without promoting it."""

        with self._lock:
            if not self._matches_locked(playback_stream_key, ancestry_keys):
                return False
            self._clear_locked()
            return True

    def discard_avatar_text(self, avatar_text_stream_key: Optional[str]) -> bool:
        with self._lock:
            if (
                self._pending is None
                or not avatar_text_stream_key
                or self._pending.avatar_text_stream_key != avatar_text_stream_key
            ):
                return False
            self._clear_locked()
            return True

    def discard_record(self, record: LockedPredictionRecord) -> bool:
        """Discard only the supplied record, leaving a newer pending one intact."""

        with self._lock:
            if (
                self._pending is None
                or self._pending.record.turn_id != record.turn_id
            ):
                return False
            self._clear_locked()
            return True

    def clear(self) -> None:
        with self._lock:
            self._clear_locked()

    def _matches_locked(
        self, playback_stream_key: Optional[str], ancestry_keys: Iterable[str]
    ) -> bool:
        if self._pending is None:
            return False
        return (
            bool(playback_stream_key)
            and playback_stream_key in self._bound_playback_keys
        ) or self._pending.avatar_text_stream_key in set(ancestry_keys)

    def _clear_locked(self) -> None:
        self._pending = None
        self._bound_playback_keys.clear()
