from __future__ import annotations

import unittest

from chat_engine.data_models.chat_data_type import ChatDataType
from chat_engine.data_models.chat_stream import ChatStreamIdentity
from handlers.client.rtc_client.playback_lifecycle import RtcPlaybackLifecycle


def stream(data_type: ChatDataType, builder_id: int, stream_id: int) -> ChatStreamIdentity:
    return ChatStreamIdentity(
        data_type=data_type,
        builder_id=builder_id,
        stream_id=stream_id,
        producer_name="test",
    )


class FakeLifecycleStreamer:
    def __init__(self):
        self.opened = []
        self.finished = 0
        self._next_stream_id = 0

    def open_stream(self, sources, name):
        playback = stream(ChatDataType.CLIENT_PLAYBACK, 99, self._next_stream_id)
        self._next_stream_id += 1
        self.opened.append((list(sources), name, playback))
        return playback

    def finish_current(self):
        self.finished += 1


class FakeStreamManager:
    def __init__(self):
        self.streamer = FakeLifecycleStreamer()
        self.created = []

    def create_lifecycle_streamer(self, data_type, producer_name, config):
        self.created.append((data_type, producer_name, config))
        return self.streamer


class RtcPlaybackLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.manager = FakeStreamManager()
        self.lifecycle = RtcPlaybackLifecycle()
        self.lifecycle.bind(self.manager, producer_name="RtcClient")

    def test_first_real_packet_begins_and_last_real_packet_ends(self):
        audio = stream(ChatDataType.AVATAR_AUDIO, 10, 1)

        playback = self.lifecycle.observe_audio_packet(audio, is_last_data=False)
        same_playback = self.lifecycle.observe_audio_packet(audio, is_last_data=False)

        self.assertEqual(playback, same_playback)
        self.assertEqual(len(self.manager.created), 1)
        data_type, producer_name, config = self.manager.created[0]
        self.assertEqual(data_type, ChatDataType.CLIENT_PLAYBACK)
        self.assertEqual(producer_name, "RtcClient")
        self.assertFalse(config.cancelable)
        self.assertEqual(self.manager.streamer.opened[0][0], [audio])
        self.assertEqual(self.manager.streamer.finished, 0)

        ended_playback = self.lifecycle.observe_audio_packet(audio, is_last_data=True)

        self.assertEqual(ended_playback, playback)
        self.assertEqual(self.manager.streamer.finished, 1)

    def test_cancel_does_not_invent_end_and_blocks_queued_packets(self):
        audio = stream(ChatDataType.AVATAR_AUDIO, 10, 2)
        playback = self.lifecycle.observe_audio_packet(audio, is_last_data=False)

        source = self.lifecycle.mark_playback_cancelled(playback)
        ignored = self.lifecycle.observe_audio_packet(audio, is_last_data=True)

        self.assertEqual(source, audio)
        self.assertFalse(self.lifecycle.should_emit_audio_packet(audio))
        self.assertIsNone(ignored)
        self.assertEqual(self.manager.streamer.finished, 0)

    def test_late_packet_after_cancel_is_rejected_from_rtc_output(self):
        audio = stream(ChatDataType.AVATAR_AUDIO, 10, 7)
        playback = self.lifecycle.observe_audio_packet(audio, is_last_data=False)

        self.lifecycle.mark_playback_cancelled(playback)

        self.assertFalse(self.lifecycle.should_emit_audio_packet(audio))
        self.assertIsNone(self.lifecycle.observe_audio_packet(audio, is_last_data=False))
        self.assertEqual(len(self.manager.streamer.opened), 1)

    def test_source_cancel_before_dequeue_never_opens_playback(self):
        audio = stream(ChatDataType.AVATAR_AUDIO, 10, 3)

        self.lifecycle.mark_source_cancelled(audio)
        playback = self.lifecycle.observe_audio_packet(audio, is_last_data=False)

        self.assertIsNone(playback)
        self.assertEqual(self.manager.created, [])
        self.assertEqual(self.manager.streamer.opened, [])

    def test_final_only_sentinel_does_not_create_playback(self):
        audio = stream(ChatDataType.AVATAR_AUDIO, 10, 6)

        playback = self.lifecycle.observe_audio_packet(audio, is_last_data=True)

        self.assertIsNone(playback)
        self.assertEqual(self.manager.created, [])
        self.assertEqual(self.manager.streamer.opened, [])
        self.assertEqual(self.manager.streamer.finished, 0)

    def test_actual_source_transition_closes_previous_contiguous_playback(self):
        first_audio = stream(ChatDataType.AVATAR_AUDIO, 10, 4)
        second_audio = stream(ChatDataType.AVATAR_AUDIO, 10, 5)

        first_playback = self.lifecycle.observe_audio_packet(first_audio, is_last_data=False)
        second_playback = self.lifecycle.observe_audio_packet(second_audio, is_last_data=False)

        self.assertNotEqual(first_playback, second_playback)
        self.assertEqual(self.manager.streamer.finished, 1)
        self.assertEqual(len(self.manager.streamer.opened), 2)
        self.assertEqual(self.manager.streamer.opened[1][0], [second_audio])


if __name__ == "__main__":
    unittest.main()
