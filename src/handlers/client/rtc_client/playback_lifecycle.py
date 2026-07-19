from __future__ import annotations

import threading
from typing import Any, Optional

from chat_engine.data_models.chat_data_type import ChatDataType
from chat_engine.data_models.chat_stream import ChatStreamIdentity, StreamKey
from chat_engine.data_models.chat_stream_config import ChatStreamConfig


class RtcPlaybackLifecycle:
    """Track playback that has actually entered the RTC audio output path."""

    def __init__(self, producer_name: str = "RtcClient"):
        self._producer_name = producer_name
        self._stream_manager: Any = None
        self._streamer: Any = None
        self._source_stream: Optional[ChatStreamIdentity] = None
        self._playback_stream: Optional[ChatStreamIdentity] = None
        self._cancelled_source_keys: set[StreamKey] = set()
        self._lock = threading.RLock()

    def bind(self, stream_manager: Any, producer_name: Optional[str] = None) -> None:
        """Bind the per-session stream manager before RTC output starts."""
        with self._lock:
            if stream_manager is self._stream_manager:
                if producer_name:
                    self._producer_name = producer_name
                return
            if self._playback_stream is not None and stream_manager is not self._stream_manager:
                raise RuntimeError("cannot replace the stream manager during active RTC playback")
            self._stream_manager = stream_manager
            self._streamer = None
            if producer_name:
                self._producer_name = producer_name

    def _get_streamer_locked(self):
        if self._streamer is None and self._stream_manager is not None:
            self._streamer = self._stream_manager.create_lifecycle_streamer(
                data_type=ChatDataType.CLIENT_PLAYBACK,
                producer_name=self._producer_name,
                config=ChatStreamConfig(cancelable=False),
            )
        return self._streamer

    @staticmethod
    def _same_stream(
        left: Optional[ChatStreamIdentity],
        right: Optional[ChatStreamIdentity],
    ) -> bool:
        return left is not None and right is not None and left.key == right.key

    def _finish_locked(self) -> None:
        streamer = self._streamer
        self._source_stream = None
        self._playback_stream = None
        if streamer is not None:
            streamer.finish_current()

    def observe_audio_packet(
        self,
        source_stream: Optional[ChatStreamIdentity],
        is_last_data: bool,
    ) -> Optional[ChatStreamIdentity]:
        """
        Observe one valid AVATAR_AUDIO packet dequeued for WebRTC output.

        The first packet opens CLIENT_PLAYBACK. The last packet closes it. A
        source transition also closes the preceding contiguous playback before
        opening the new one, matching the order in the RTC output queue.
        """
        if source_stream is None or source_stream.key is None:
            return None

        with self._lock:
            if source_stream.key in self._cancelled_source_keys:
                return None

            if not self._same_stream(self._source_stream, source_stream):
                # BailianTTS uses a final-only zero-valued packet as a stream
                # sentinel when synthesis produced no playable audio. It must
                # not manufacture a BEGIN/END pair or mark an action executed.
                if is_last_data:
                    return None
                if self._playback_stream is not None:
                    self._finish_locked()

                streamer = self._get_streamer_locked()
                if streamer is None:
                    return None
                playback_stream = streamer.open_stream(
                    sources=[source_stream],
                    name=f"rtc-playback:{source_stream.stream_key_str}",
                )
                if playback_stream is None:
                    return None
                self._source_stream = source_stream
                self._playback_stream = playback_stream

            playback_stream = self._playback_stream
            if is_last_data:
                self._finish_locked()
            return playback_stream

    def should_emit_audio_packet(self, source_stream: Optional[ChatStreamIdentity]) -> bool:
        """Return False for late packets belonging to an already-cancelled source."""
        if source_stream is None or source_stream.key is None:
            return True
        with self._lock:
            return source_stream.key not in self._cancelled_source_keys

    def mark_source_cancelled(self, source_stream: Optional[ChatStreamIdentity]) -> None:
        """Prevent queued packets from reopening a cancelled AVATAR_AUDIO stream."""
        if source_stream is None or source_stream.key is None:
            return
        with self._lock:
            self._cancelled_source_keys.add(source_stream.key)
            if self._same_stream(self._source_stream, source_stream):
                # The stream graph already cancelled CLIENT_PLAYBACK through the
                # AVATAR_AUDIO referrer edge. Only local tracking is cleared here.
                self._source_stream = None
                self._playback_stream = None

    def mark_playback_cancelled(
        self,
        playback_stream: Optional[ChatStreamIdentity],
    ) -> Optional[ChatStreamIdentity]:
        """Clear local state for an engine-cancelled CLIENT_PLAYBACK stream."""
        if playback_stream is None or playback_stream.key is None:
            return None
        with self._lock:
            if not self._same_stream(self._playback_stream, playback_stream):
                return None
            source_stream = self._source_stream
            if source_stream is not None and source_stream.key is not None:
                self._cancelled_source_keys.add(source_stream.key)
            self._source_stream = None
            self._playback_stream = None
            return source_stream

    def reset(self) -> None:
        """Drop session-local tracking during teardown without inventing an END."""
        with self._lock:
            self._source_stream = None
            self._playback_stream = None
            self._cancelled_source_keys.clear()
            self._streamer = None
            self._stream_manager = None
