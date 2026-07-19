from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass

import pytest

from chat_engine.contexts.session_clock import SessionClock
from chat_engine.core.stream_manager import ChatDataSubmitter, StreamManager
from chat_engine.data_models.chat_data.chat_data_model import ChatData
from chat_engine.data_models.chat_data_type import ChatDataType
from chat_engine.data_models.chat_signal import ChatSignal
from chat_engine.data_models.chat_signal_type import ChatSignalType
from chat_engine.data_models.chat_stream import ChatStreamIdentity
from chat_engine.data_models.chat_stream_config import ChatStreamConfig
from chat_engine.data_models.internal.chat_data_endpoints import DataSink
from chat_engine.data_models.internal.handler_definition_data import HandlerDataInfo
from chat_engine.data_models.runtime_data.data_bundle import (
    DataBundle,
    DataBundleDefinition,
    DataBundleEntry,
)
from handlers.hiwm.hiwm_handler import HIWMConfig, HIWMContext, HandlerHIWM
from handlers.hiwm.ledger import ImmutableJSONLLedger
from handlers.hiwm.models import HIWMModelInference, ModelInfo, PlannerWeights
from handlers.hiwm.planner import HIWMPlanner
from handlers.hiwm.world_model import WorldModelResult

from .fixtures import make_actions, make_beliefs, make_content_signals


class _Emitter:
    def __init__(self, signals: list[ChatSignal]):
        self.signals = signals

    def emit(self, signal: ChatSignal) -> None:
        self.signals.append(signal)


class _SignalManager:
    def __init__(self):
        self.clock = SessionClock()
        self.clock.start()
        self.signals: list[ChatSignal] = []

    def get_clock(self) -> SessionClock:
        return self.clock

    def get_emitter(self, _source_name=None) -> _Emitter:
        return _Emitter(self.signals)


class _BlockingWorldModel:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()

    def infer(self, *, observation, **_kwargs) -> WorldModelResult:
        self.started.set()
        if not self.release.wait(timeout=2.0):
            raise AssertionError("test did not release the blocking world model")

        evidence_id = observation.current_asr.evidence_id
        beliefs = [
            item.model_copy(update={"evidence_refs": [evidence_id]})
            for item in make_beliefs()
        ]
        actions = [
            item.model_copy(update={"evidence_refs": [evidence_id]})
            for item in make_actions()
        ]
        content_signals = [
            item.model_copy(update={"evidence_refs": [evidence_id]})
            for item in make_content_signals()
        ]
        completed_at = time.time()
        return WorldModelResult(
            inference=HIWMModelInference(
                content_signals=content_signals,
                beliefs=beliefs,
                actions=actions,
                feedback=None,
            ),
            model_info=ModelInfo(
                model_name="blocking-test-model",
                api_url="https://example.invalid/v1",
                response_id="blocking-test-response",
                requested_at=completed_at - 0.01,
                completed_at=completed_at,
            ),
        )


def _text_definition(name: str) -> DataBundleDefinition:
    definition = DataBundleDefinition()
    definition.add_entry(DataBundleEntry.create_text_entry(name))
    return definition


def _audio_definition(name: str, sample_rate: int = 16000) -> DataBundleDefinition:
    definition = DataBundleDefinition()
    definition.add_entry(DataBundleEntry.create_audio_entry(name, 1, sample_rate))
    return definition


def _streamer(
    manager: StreamManager,
    *,
    data_type: ChatDataType,
    definition: DataBundleDefinition,
    producer_name: str,
    sinks=None,
):
    info = HandlerDataInfo(
        type=data_type,
        definition=definition,
        output_stream_config=ChatStreamConfig(cancelable=True),
    )
    return manager.create_streamer(
        data_info=info,
        data_sinks={} if sinks is None else sinks,
        producer_name=producer_name,
        config=info.output_stream_config,
    )


@dataclass
class _Harness:
    handler: HandlerHIWM
    context: HIWMContext
    input_data: ChatData
    outputs: dict[ChatDataType, HandlerDataInfo]
    world_model: _BlockingWorldModel
    output_queue: queue.Queue
    manager: StreamManager
    active_audio: ChatStreamIdentity
    unrelated_audio: ChatStreamIdentity

    def unrelated_stream(self, data_type: ChatDataType) -> ChatStreamIdentity:
        if data_type == ChatDataType.AVATAR_TEXT:
            definition = _text_definition("unrelated_avatar_text")
        elif data_type == ChatDataType.CLIENT_PLAYBACK:
            definition = DataBundleDefinition()
        else:
            definition = _audio_definition(
                "unrelated_avatar_audio", sample_rate=24000
            )
        streamer = _streamer(
            self.manager,
            data_type=data_type,
            definition=definition,
            producer_name=f"Unrelated{data_type.value}",
        )
        return streamer.new_stream([])


def _build_harness(tmp_path) -> _Harness:
    manager = StreamManager(_SignalManager(), recycle_ttl=10.0)

    audio_definition = _audio_definition("human_audio")
    audio_streamer = _streamer(
        manager,
        data_type=ChatDataType.HUMAN_AUDIO,
        definition=audio_definition,
        producer_name="SileroVad",
    )
    unrelated_audio = audio_streamer.new_stream([])
    active_audio = audio_streamer.new_stream([])

    human_definition = _text_definition("human_text")
    human_streamer = _streamer(
        manager,
        data_type=ChatDataType.HUMAN_TEXT,
        definition=human_definition,
        producer_name="BailianASR",
    )
    human_stream_id = human_streamer.new_stream([active_audio])
    human_bundle = DataBundle(human_definition)
    human_bundle.set_main_data("测试取消范围")
    human_streamer.stream_data(human_bundle, finish_stream=True)

    input_bundle = DataBundle(human_definition)
    input_bundle.set_main_data("测试取消范围")
    input_data = ChatData(
        stream_id=human_stream_id,
        source="BailianASR",
        type=ChatDataType.HUMAN_TEXT,
        timestamp=(1600, 16000),
        data=input_bundle,
        is_first_data=True,
        is_last_data=True,
    )

    handler = HandlerHIWM()
    context = HIWMContext("cancellation-scope-session")
    context.config = HIWMConfig(
        objective="测试 HIWM 取消范围",
        request_timeout_seconds=1.0,
        history_max_events=0,
        ledger_dir=str(tmp_path / "ledger"),
        require_asr_audio_ancestry=True,
        planner=PlannerWeights(goal=1.0, risk=1.0, uncertainty=0.5),
    )
    world_model = _BlockingWorldModel()
    context.world_model = world_model
    context.planner = HIWMPlanner(context.config.planner)
    context.ledger = ImmutableJSONLLedger(tmp_path / "ledger", context.session_id)
    context.stream_manager = manager

    output_definition = _text_definition("avatar_text")
    output_info = HandlerDataInfo(
        type=ChatDataType.AVATAR_TEXT,
        definition=output_definition,
        output_stream_config=ChatStreamConfig(cancelable=True),
    )
    output_queue: queue.Queue = queue.Queue()
    output_sink = DataSink(
        owner="RtcClient",
        sink_queue=output_queue,
        consume_info=HandlerDataInfo(type=ChatDataType.AVATAR_TEXT),
    )
    output_streamer = _streamer(
        manager,
        data_type=ChatDataType.AVATAR_TEXT,
        definition=output_definition,
        producer_name="HIWM",
        sinks={ChatDataType.AVATAR_TEXT: [output_sink]},
    )
    submitter = ChatDataSubmitter()
    submitter.register_streamer(output_streamer)
    context.data_submitter = submitter

    return _Harness(
        handler=handler,
        context=context,
        input_data=input_data,
        outputs={ChatDataType.AVATAR_TEXT: output_info},
        world_model=world_model,
        output_queue=output_queue,
        manager=manager,
        active_audio=active_audio,
        unrelated_audio=unrelated_audio,
    )


def _cancel_during_infer(
    harness: _Harness, related_stream: ChatStreamIdentity | None
) -> None:
    errors: queue.Queue[BaseException] = queue.Queue()

    def run_turn() -> None:
        try:
            harness.handler.handle(
                harness.context, harness.input_data, harness.outputs
            )
        except BaseException as exc:  # pragma: no cover - re-raised on test thread
            errors.put(exc)

    worker = threading.Thread(target=run_turn, daemon=True)
    worker.start()
    try:
        assert harness.world_model.started.wait(timeout=1.0)
        harness.handler.on_signal(
            harness.context,
            ChatSignal(
                type=ChatSignalType.STREAM_CANCEL,
                related_stream=related_stream,
            ),
        )
    finally:
        harness.world_model.release.set()
        worker.join(timeout=2.0)

    assert not worker.is_alive()
    if not errors.empty():
        raise errors.get_nowait()


def _assert_spoken_and_final(harness: _Harness) -> None:
    spoken = harness.output_queue.get_nowait()
    final = harness.output_queue.get_nowait()
    assert spoken.data.get_main_data() == "测试夹具动作甲"
    assert spoken.is_last_data is False
    assert final.data.get_main_data() == ""
    assert final.is_last_data is True
    assert harness.output_queue.empty()


def test_unrelated_human_audio_cancel_during_infer_keeps_reply(tmp_path):
    harness = _build_harness(tmp_path)

    _cancel_during_infer(harness, harness.unrelated_audio)

    assert harness.context.cancel_event.is_set() is False
    _assert_spoken_and_final(harness)
    assert harness.context.ledger.read_last() is not None


def test_active_input_audio_ancestor_cancel_during_infer_suppresses_reply(tmp_path):
    harness = _build_harness(tmp_path)

    ancestry = harness.manager.get_stream_ancestry(harness.input_data.stream_id)
    ancestry_keys = {
        stream.stream_key_str
        for stream in ancestry["parents"] + ancestry["ancestors"]
    }
    assert harness.active_audio.stream_key_str in ancestry_keys

    _cancel_during_infer(harness, harness.active_audio)

    assert harness.context.cancel_event.is_set() is True
    assert harness.output_queue.empty()
    assert harness.context.ledger.read_last() is None


def test_active_input_text_cancel_during_infer_suppresses_reply(tmp_path):
    harness = _build_harness(tmp_path)

    _cancel_during_infer(harness, harness.input_data.stream_id)

    assert harness.context.cancel_event.is_set() is True
    assert harness.output_queue.empty()
    assert harness.context.ledger.read_last() is None


@pytest.mark.parametrize(
    "data_type",
    [
        ChatDataType.AVATAR_TEXT,
        ChatDataType.AVATAR_AUDIO,
        ChatDataType.CLIENT_PLAYBACK,
    ],
)
def test_unrelated_avatar_or_playback_cancel_during_infer_keeps_reply(
    tmp_path, data_type: ChatDataType
):
    harness = _build_harness(tmp_path)
    unrelated_stream = harness.unrelated_stream(data_type)

    _cancel_during_infer(harness, unrelated_stream)

    assert harness.context.cancel_event.is_set() is False
    _assert_spoken_and_final(harness)
    assert harness.context.ledger.read_last() is not None


def test_global_cancel_during_infer_preserves_teardown_behavior(tmp_path):
    harness = _build_harness(tmp_path)

    _cancel_during_infer(harness, None)

    assert harness.context.cancel_event.is_set() is True
    assert harness.output_queue.empty()
    assert harness.context.ledger.read_last() is None


def test_active_output_descendant_cancel_is_relevant(tmp_path):
    harness = _build_harness(tmp_path)
    avatar_text = harness.unrelated_stream(ChatDataType.AVATAR_TEXT)
    avatar_audio_definition = _audio_definition("avatar_audio", sample_rate=24000)
    avatar_audio_streamer = _streamer(
        harness.manager,
        data_type=ChatDataType.AVATAR_AUDIO,
        definition=avatar_audio_definition,
        producer_name="BailianTTS",
    )
    avatar_audio = avatar_audio_streamer.new_stream([avatar_text])
    harness.context.active_output_stream_key = avatar_text.stream_key_str

    harness.handler.on_signal(
        harness.context,
        ChatSignal(
            type=ChatSignalType.STREAM_CANCEL,
            related_stream=avatar_audio,
        ),
    )

    assert harness.context.cancel_event.is_set() is True


def test_active_output_cancel_is_relevant(tmp_path):
    harness = _build_harness(tmp_path)
    avatar_text = harness.unrelated_stream(ChatDataType.AVATAR_TEXT)
    harness.context.active_output_stream_key = avatar_text.stream_key_str

    harness.handler.on_signal(
        harness.context,
        ChatSignal(
            type=ChatSignalType.STREAM_CANCEL,
            related_stream=avatar_text,
        ),
    )

    assert harness.context.cancel_event.is_set() is True
