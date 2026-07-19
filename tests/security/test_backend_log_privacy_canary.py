from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from loguru import logger

from chat_engine.data_models.chat_data.chat_data_model import ChatData
from chat_engine.data_models.chat_data_type import ChatDataType
from chat_engine.data_models.chat_stream import ChatStreamIdentity
from chat_engine.data_models.runtime_data.data_bundle import (
    DataBundle,
    DataBundleDefinition,
    DataBundleEntry,
)
from handlers.asr.bailian_asr import asr_handler_bailian as asr_module
from handlers.hiwm.hiwm_handler import HIWMContext, HandlerHIWM
from handlers.hiwm.world_model import HIWMResponseValidationError
from handlers.tts.bailian_tts import tts_handler_cosyvoice_bailian as tts_module


ASR_CANARY = "CANARY_ASR_TRANSCRIPT_6f892b"
TTS_CANARY = "CANARY_TTS_UTTERANCE_928d4e"
HIWM_CANARY = "CANARY_HIWM_PROVIDER_BODY_b301a7"


def _audio_packet(stream_id: ChatStreamIdentity) -> ChatData:
    definition = DataBundleDefinition()
    definition.add_entry(
        DataBundleEntry.create_audio_entry("human_audio", 1, 16000)
    )
    bundle = DataBundle(definition)
    bundle.set_main_data(np.zeros((1, 16000), dtype=np.float32))
    return ChatData(
        stream_id=stream_id,
        source="privacy-test",
        type=ChatDataType.HUMAN_AUDIO,
        timestamp=(1, 16000),
        data=bundle,
        is_first_data=True,
        is_last_data=True,
    )


def _text_packet(stream_id: ChatStreamIdentity, text: str) -> ChatData:
    definition = DataBundleDefinition()
    definition.add_entry(DataBundleEntry.create_text_entry("avatar_text"))
    bundle = DataBundle(definition)
    bundle.set_main_data(text)
    return ChatData(
        stream_id=stream_id,
        source="privacy-test",
        type=ChatDataType.AVATAR_TEXT,
        timestamp=(1, 16000),
        data=bundle,
        is_first_data=True,
        is_last_data=True,
    )


class _TextStreamer:
    def __init__(self):
        self.data_definition = DataBundleDefinition()
        self.data_definition.add_entry(
            DataBundleEntry.create_text_entry("human_text")
        )
        self.current_stream = None
        self.payloads = []

    def new_stream(self, _sources):
        self.current_stream = ChatStreamIdentity(
            data_type=ChatDataType.HUMAN_TEXT,
            builder_id=210,
            stream_id=1,
            producer_name="privacy-test-asr",
        )
        return self.current_stream

    def stream_data(self, data, *, finish_stream=False):
        self.payloads.append(data.get_main_data())
        if finish_stream:
            self.current_stream = None


class _AudioStreamer:
    def __init__(self):
        self.data_definition = DataBundleDefinition()
        self.data_definition.add_entry(
            DataBundleEntry.create_audio_entry("avatar_audio", 1, 24000)
        )
        self.new_stream_calls = 0

    def new_stream(self, *args, **kwargs):
        self.new_stream_calls += 1
        return ChatStreamIdentity(
            data_type=ChatDataType.AVATAR_AUDIO,
            builder_id=220,
            stream_id=self.new_stream_calls,
            producer_name="privacy-test-tts",
        )

    def cancel_current(self):
        raise AssertionError("the successful fake TTS path must not be cancelled")


class _Submitter:
    def __init__(self, streamer):
        self.streamer = streamer

    def get_streamer(self, _data_type):
        return self.streamer


def test_asr_tts_and_hiwm_logs_exclude_payload_canaries(monkeypatch):
    """Payloads must flow through handlers without appearing in backend logs."""

    class _RecognitionResult:
        message = ""
        request_id = "request-safe"

        def get_sentence(self):
            return {"text": ASR_CANARY, "end_time": 1000}

        def get_request_id(self):
            return self.request_id

    class _Recognition:
        def __init__(self, **kwargs):
            self.callback = kwargs["callback"]
            self.audio_frames = []

        def start(self):
            return None

        def send_audio_frame(self, frame):
            self.audio_frames.append(frame)

        def stop(self):
            self.callback.on_event(_RecognitionResult())
            self.callback.on_complete()

        def get_last_request_id(self):
            return "request-safe"

        def get_first_package_delay(self):
            return 1

        def get_last_package_delay(self):
            return 2

    synthesizers = []

    class _Synthesizer:
        def __init__(self, **_kwargs):
            self.calls = []
            self.complete_calls = 0
            synthesizers.append(self)

        def streaming_call(self, text):
            self.calls.append(text)

        def streaming_complete(self):
            self.complete_calls += 1

        def streaming_cancel(self):
            raise AssertionError("the successful fake TTS path must not be cancelled")

    monkeypatch.setattr(asr_module, "Recognition", _Recognition)
    monkeypatch.setattr(tts_module, "SpeechSynthesizer", _Synthesizer)

    captured_logs = []
    sink_id = logger.add(
        lambda message: captured_logs.append(str(message)),
        level="DEBUG",
        format="{message}\n{exception}",
    )
    try:
        text_streamer = _TextStreamer()
        asr_context = asr_module.BailianASRContext("privacy-asr")
        asr_context.data_submitter = _Submitter(text_streamer)
        asr_context.handle_audio_stream(
            _audio_packet(
                ChatStreamIdentity(
                    data_type=ChatDataType.HUMAN_AUDIO,
                    builder_id=200,
                    stream_id=1,
                    producer_name="privacy-test",
                )
            ),
            SimpleNamespace(
                model_name="fake-asr",
                audio_format="pcm",
                sample_rate=16000,
                semantic_punctuation_enabled=False,
                language_hints=None,
            ),
        )

        audio_streamer = _AudioStreamer()
        tts_context = tts_module.TTSContext("privacy-tts")
        tts_context.data_submitter = _Submitter(audio_streamer)
        tts_context.handle_text_stream(
            _text_packet(
                ChatStreamIdentity(
                    data_type=ChatDataType.AVATAR_TEXT,
                    builder_id=201,
                    stream_id=1,
                    producer_name="privacy-test",
                ),
                TTS_CANARY,
            ),
            SimpleNamespace(model_name="fake-tts", voice="fake-voice"),
        )

        hiwm_context = HIWMContext("privacy-hiwm")
        hiwm_context.cancel_event.set()
        try:
            raise ValueError(HIWM_CANARY)
        except ValueError as provider_error:
            try:
                raise HIWMResponseValidationError(
                    "provider response did not match the schema"
                ) from provider_error
            except HIWMResponseValidationError as validation_error:
                HandlerHIWM()._emit_error(
                    hiwm_context,
                    ChatData(),
                    {},
                    "privacy-turn",
                    "response_validation",
                    validation_error,
                )
    finally:
        logger.remove(sink_id)

    assert text_streamer.payloads == [ASR_CANARY]
    assert len(synthesizers) == 1
    assert synthesizers[0].calls == [TTS_CANARY]
    assert synthesizers[0].complete_calls == 1
    assert audio_streamer.new_stream_calls == 1

    rendered_logs = "".join(captured_logs)
    leaked_channels = [
        channel
        for channel, canary in (
            ("ASR", ASR_CANARY),
            ("TTS", TTS_CANARY),
            ("HIWM", HIWM_CANARY),
        )
        if canary in rendered_logs
    ]
    assert not leaked_channels, (
        "backend logs exposed synthetic payload canaries for: "
        + ", ".join(leaked_channels)
    )
