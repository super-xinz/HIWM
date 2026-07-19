from __future__ import annotations

from types import SimpleNamespace

from chat_engine.data_models.chat_data.chat_data_model import ChatData
from chat_engine.data_models.chat_data_type import ChatDataType
from chat_engine.data_models.chat_stream import ChatStreamIdentity
from chat_engine.data_models.runtime_data.data_bundle import (
    DataBundle,
    DataBundleDefinition,
    DataBundleEntry,
)
from handlers.tts.bailian_tts import tts_handler_cosyvoice_bailian as tts_module


def _text_packet(stream_id, text: str, *, final: bool) -> ChatData:
    definition = DataBundleDefinition()
    definition.add_entry(DataBundleEntry.create_text_entry("avatar_text"))
    bundle = DataBundle(definition)
    bundle.set_main_data(text)
    return ChatData(
        stream_id=stream_id,
        source="HIWM",
        type=ChatDataType.AVATAR_TEXT,
        timestamp=(1, 16000),
        data=bundle,
        is_first_data=not final,
        is_last_data=final,
    )


class _AudioStreamer:
    def __init__(self):
        self.new_stream_calls = 0
        self.cancel_calls = 0
        self.data_definition = DataBundleDefinition()
        self.data_definition.add_entry(
            DataBundleEntry.create_audio_entry("avatar_audio", 1, 24000)
        )

    def new_stream(self, *args, **kwargs):
        self.new_stream_calls += 1
        return ChatStreamIdentity(
            data_type=ChatDataType.AVATAR_AUDIO,
            builder_id=900,
            stream_id=self.new_stream_calls,
            producer_name="BailianTTS",
        )

    def cancel_current(self):
        self.cancel_calls += 1


class _Submitter:
    def __init__(self):
        self.streamer = _AudioStreamer()

    def get_streamer(self, _data_type):
        return self.streamer


def test_empty_final_completes_existing_synthesis_without_empty_streaming_call(monkeypatch):
    instances = []

    class _Synthesizer:
        def __init__(self, **_kwargs):
            self.calls = []
            self.complete_calls = 0
            self.cancel_calls = 0
            instances.append(self)

        def streaming_call(self, text):
            self.calls.append(text)

        def streaming_complete(self):
            self.complete_calls += 1

        def streaming_cancel(self):
            self.cancel_calls += 1

    monkeypatch.setattr(tts_module, "SpeechSynthesizer", _Synthesizer)
    context = tts_module.TTSContext("tts-session")
    context.data_submitter = _Submitter()
    handler = SimpleNamespace(model_name="test-model", voice="test-voice")
    stream_id = ChatStreamIdentity(
        data_type=ChatDataType.AVATAR_TEXT,
        builder_id=800,
        stream_id=1,
        producer_name="HIWM",
    )

    context.handle_text_stream(_text_packet(stream_id, "真实回复", final=False), handler)
    context.handle_text_stream(_text_packet(stream_id, "", final=True), handler)

    assert len(instances) == 1
    assert instances[0].calls == ["真实回复"]
    assert instances[0].complete_calls == 1
    assert context.data_submitter.streamer.new_stream_calls == 1
    assert context.data_submitter.streamer.cancel_calls == 0
    assert context.api_links == {}


def test_synthesis_exception_cancels_audio_output_stream(monkeypatch):
    class _FailingSynthesizer:
        def __init__(self, **_kwargs):
            self.cancel_calls = 0

        def streaming_call(self, _text):
            raise RuntimeError("test synthesis failure")

        def streaming_complete(self):
            raise AssertionError("failed synthesis must not complete")

        def streaming_cancel(self):
            self.cancel_calls += 1

    monkeypatch.setattr(tts_module, "SpeechSynthesizer", _FailingSynthesizer)
    context = tts_module.TTSContext("tts-session")
    context.data_submitter = _Submitter()
    handler = SimpleNamespace(model_name="test-model", voice="test-voice")
    stream_id = ChatStreamIdentity(
        data_type=ChatDataType.AVATAR_TEXT,
        builder_id=800,
        stream_id=2,
        producer_name="HIWM",
    )

    context.handle_text_stream(_text_packet(stream_id, "触发失败", final=False), handler)

    assert context.data_submitter.streamer.new_stream_calls == 1
    assert context.data_submitter.streamer.cancel_calls == 1
    assert context.api_links == {}
