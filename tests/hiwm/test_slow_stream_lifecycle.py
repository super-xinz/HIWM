from __future__ import annotations

import queue
import time

from chat_engine.contexts.session_clock import SessionClock
from chat_engine.core.stream_manager import ChatDataSubmitter, StreamManager
from chat_engine.data_models.chat_data.chat_data_model import ChatData
from chat_engine.data_models.chat_data_type import ChatDataType
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
from handlers.hiwm.world_model import HIWMAPIError, WorldModelResult

from .fixtures import make_actions, make_beliefs, make_content_signals


class _Emitter:
    def __init__(self, signals):
        self.signals = signals

    def emit(self, signal):
        self.signals.append(signal)


class _SignalManager:
    def __init__(self):
        self.clock = SessionClock()
        self.clock.start()
        self.signals = []

    def get_clock(self):
        return self.clock

    def get_emitter(self, _source_name=None):
        return _Emitter(self.signals)


class _SlowWorldModel:
    def __init__(self, manager, source_stream_id, *, fail: bool):
        self.manager = manager
        self.source_stream_id = source_stream_id
        self.fail = fail
        self.parent_survived = False

    def infer(self, *, observation, **_kwargs):
        # Deliberately exceed the test stream TTL and trigger a cleanup lookup.
        time.sleep(0.03)
        self.parent_survived = self.manager.find_stream(self.source_stream_id) is not None
        if self.fail:
            raise HIWMAPIError("test upstream failure")

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
        now = time.time()
        return WorldModelResult(
            inference=HIWMModelInference(
                content_signals=content_signals,
                beliefs=beliefs,
                actions=actions,
                feedback=None,
            ),
            model_info=ModelInfo(
                model_name="test-model",
                api_url="https://example.invalid/v1",
                response_id="slow-test",
                requested_at=now - 0.03,
                completed_at=now,
            ),
        )


def _text_definition(name: str) -> DataBundleDefinition:
    definition = DataBundleDefinition()
    definition.add_entry(DataBundleEntry.create_text_entry(name))
    return definition


def _build_harness(tmp_path, *, fail: bool):
    signal_manager = _SignalManager()
    manager = StreamManager(
        signal_manager,
        recycle_ttl=0.005,
        cleanup_interval=0.0,
    )

    human_definition = _text_definition("human_text")
    human_streamer = manager.create_streamer(
        data_info=HandlerDataInfo(
            type=ChatDataType.HUMAN_TEXT,
            definition=human_definition,
        ),
        data_sinks={},
        producer_name="BailianASR",
        config=ChatStreamConfig(cancelable=True),
    )
    source_stream_id = human_streamer.new_stream([])
    human_bundle = DataBundle(human_definition)
    human_bundle.set_main_data("测试慢推理")
    human_streamer.stream_data(human_bundle, finish_stream=True)

    input_bundle = DataBundle(human_definition)
    input_bundle.set_main_data("测试慢推理")
    input_data = ChatData(
        stream_id=source_stream_id,
        source="BailianASR",
        type=ChatDataType.HUMAN_TEXT,
        timestamp=(1600, 16000),
        data=input_bundle,
        is_first_data=True,
        is_last_data=True,
    )

    handler = HandlerHIWM()
    context = HIWMContext("slow-session")
    context.config = HIWMConfig(
        objective="测试真实慢推理回复链路",
        request_timeout_seconds=1.0,
        history_max_events=0,
        ledger_dir=str(tmp_path / "ledger"),
        require_asr_audio_ancestry=False,
        planner=PlannerWeights(goal=1.0, risk=1.0, uncertainty=0.5),
    )
    world_model = _SlowWorldModel(manager, source_stream_id, fail=fail)
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
    rtc_text_queue = queue.Queue()
    rtc_sink = DataSink(
        owner="RtcClient",
        sink_queue=rtc_text_queue,
        consume_info=HandlerDataInfo(type=ChatDataType.AVATAR_TEXT),
    )
    output_streamer = manager.create_streamer(
        data_info=output_info,
        data_sinks={ChatDataType.AVATAR_TEXT: [rtc_sink]},
        producer_name="HIWM",
        config=output_info.output_stream_config,
    )
    submitter = ChatDataSubmitter()
    submitter.register_streamer(output_streamer)
    context.data_submitter = submitter

    return (
        handler,
        context,
        input_data,
        {ChatDataType.AVATAR_TEXT: output_info},
        world_model,
        rtc_text_queue,
    )


def test_slow_success_keeps_parent_until_locked_reply_is_emitted(tmp_path):
    handler, context, input_data, outputs, world_model, rtc_queue = _build_harness(
        tmp_path, fail=False
    )

    handler.handle(context, input_data, outputs)

    assert world_model.parent_survived is True
    assert world_model.manager._stream_storage._retention_counts == {}
    spoken = rtc_queue.get_nowait()
    final = rtc_queue.get_nowait()
    assert spoken.data.get_main_data() == "测试夹具动作甲"
    assert spoken.is_last_data is False
    assert spoken.data.metadata["hiwm"]["selected_action_id"] == "action-a"
    assert final.data.get_main_data() == ""
    assert final.is_last_data is True
    assert rtc_queue.empty()


def test_slow_failure_locks_safe_fallback_before_rtc_output(tmp_path):
    handler, context, input_data, outputs, world_model, rtc_queue = _build_harness(
        tmp_path, fail=True
    )

    handler.handle(context, input_data, outputs)

    assert world_model.parent_survived is True
    assert world_model.manager._stream_storage._retention_counts == {}
    fallback_packet = rtc_queue.get_nowait()
    final_packet = rtc_queue.get_nowait()
    assert fallback_packet.is_last_data is False
    assert "无法可靠地生成" in fallback_packet.data.get_main_data()
    assert fallback_packet.data.metadata["hiwm_error"]["stage"] == "api"
    fallback = fallback_packet.data.metadata["hiwm_fallback"]
    assert fallback["probability_kind"] == "unavailable"
    assert fallback["locked_prediction"]["action_id"] == "clarify"
    assert final_packet.is_last_data is True
    assert final_packet.data.get_main_data() == ""
    assert rtc_queue.empty()

    # Verify the exact packet remains observable on the RTC text protocol.
    from handlers.client.rtc_client.client_handler_rtc import (
        ClientHandlerRtc,
        ClientRtcContext,
    )
    from handlers.client.ws_client.ws_message_protocol import serialize_message

    sent_messages = []
    rtc_handler = ClientHandlerRtc()
    rtc_handler._send_message_to_chat_channel = (
        lambda session_id, message: sent_messages.append((session_id, message)) or True
    )
    assert rtc_handler._send_text_to_chat_channel(
        ClientRtcContext("slow-session"), fallback_packet
    )
    wire_message = serialize_message(sent_messages[0][1])
    assert wire_message["payload"]["metadata"]["hiwm_error"]["stage"] == "api"
