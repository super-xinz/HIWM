"""HIWM handler that replaces direct LLM replies in the inherited media pipeline."""

from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional, Set, cast
from uuid import uuid4

import numpy as np
from loguru import logger
from pydantic import Field, field_validator

from chat_engine.common.handler_base import (
    HandlerBase,
    HandlerBaseInfo,
    HandlerDataInfo,
    HandlerDetail,
)
from chat_engine.contexts.handler_context import HandlerContext
from chat_engine.contexts.session_context import SessionContext
from chat_engine.data_models.chat_data.chat_data_model import ChatData
from chat_engine.data_models.chat_data_type import ChatDataType
from chat_engine.data_models.client_perception import (
    LatestClientPerception,
    bind_latest_client_perception,
)
from chat_engine.data_models.client_profile import (
    LatestClientSessionProfile,
    bind_latest_client_session_profile,
)
from chat_engine.data_models.chat_engine_config_data import (
    ChatEngineConfigModel,
    HandlerBaseConfigModel,
)
from chat_engine.data_models.chat_signal import ChatSignal, SignalFilterRule
from chat_engine.data_models.chat_signal_type import ChatSignalType
from chat_engine.data_models.chat_stream import ChatStreamIdentity
from chat_engine.data_models.chat_stream_config import ChatStreamConfig
from chat_engine.data_models.runtime_data.data_bundle import (
    DataBundle,
    DataBundleDefinition,
    DataBundleEntry,
)
from engine_utils.directory_info import DirectoryInfo

from .camera import encode_bgr_frame_as_jpeg
from .execution import submit_locked_sequence
from .ledger import ImmutableJSONLLedger
from .models import (
    BeliefItem,
    EvidenceReference,
    HIWMError,
    LockedPredictionRecord,
    ObservationSnapshot,
    PlannerSafetyPolicy,
    PlannerWeights,
    PredictionPayload,
    SafetyFallbackPayload,
)
from .planner import HIWMPlanner
from .playback import PlaybackFeedbackTracker
from .world_model import (
    HIWMAPIError,
    HIWMResponseValidationError,
    OpenAICompatibleWorldModel,
)


class HIWMConfig(HandlerBaseConfigModel):
    model_name: str = Field(default="deepseek-v4-flash", min_length=1)
    api_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        min_length=1,
    )
    api_key_env: str = Field(default="DASHSCOPE_API_KEY", min_length=1)
    objective: str = Field(min_length=1)
    request_timeout_seconds: float = Field(default=30.0, gt=0.0)
    max_output_tokens: int = Field(default=4096, ge=512, le=8192)
    max_attempts: int = Field(default=2, ge=1, le=2)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    input_modalities: List[Literal["text", "image"]] = Field(
        default_factory=lambda: ["text"], min_length=1
    )
    structured_output: bool = Field(default=True)
    enable_thinking: bool = Field(default=False)
    history_max_events: int = Field(default=20, ge=0, le=100)
    ledger_dir: str = Field(default="temp/hiwm_ledger", min_length=1)
    require_asr_audio_ancestry: bool = Field(default=True)
    camera_max_age_seconds: float = Field(default=5.0, gt=0.0)
    camera_capture_interval_ms: int = Field(default=250, ge=0)
    perception_max_age_seconds: float = Field(default=5.0, gt=0.0, le=30.0)
    planner: PlannerWeights = Field(default_factory=PlannerWeights)
    safety_policy: PlannerSafetyPolicy = Field(default_factory=PlannerSafetyPolicy)
    fallback_action: Literal["clarify", "wait"] = "clarify"
    fallback_utterance: str = Field(
        default="我暂时无法可靠地生成下一步预测。可以请你换一种说法，或稍后再试吗？",
        min_length=1,
        max_length=200,
    )

    @field_validator("input_modalities")
    @classmethod
    def _validate_input_modalities(
        cls, value: List[Literal["text", "image"]]
    ) -> List[Literal["text", "image"]]:
        if "text" not in value:
            raise ValueError("HIWM input_modalities must include 'text'")
        if len(value) != len(set(value)):
            raise ValueError("HIWM input_modalities must be unique")
        return value

@dataclass(frozen=True)
class CapturedCameraFrame:
    evidence: EvidenceReference
    data_url: str


class HIWMContext(HandlerContext):
    def __init__(self, session_id: str):
        super().__init__(session_id)
        self.config: Optional[HIWMConfig] = None
        self.world_model: Optional[OpenAICompatibleWorldModel] = None
        self.planner: Optional[HIWMPlanner] = None
        self.ledger: Optional[ImmutableJSONLLedger] = None
        self.historical_beliefs: List[BeliefItem] = []
        self.previous_locked_prediction: Optional[LockedPredictionRecord] = None
        self.feedback_state_lock = threading.Lock()
        self.playback_feedback = PlaybackFeedbackTracker()
        self.latest_camera: Optional[CapturedCameraFrame] = None
        self.client_perception: Optional[LatestClientPerception] = None
        self.client_session_profile: Optional[LatestClientSessionProfile] = None
        self.last_camera_capture_monotonic: float = 0.0
        self.text_buffers: Dict[str, str] = {}
        self.cancel_event = threading.Event()
        self.cancellation_state_lock = threading.Lock()
        self.active_input_stream_key: Optional[str] = None
        self.active_input_audio_ancestor_keys: Set[str] = set()
        self.active_output_stream_key: Optional[str] = None


class HandlerHIWM(HandlerBase):
    """Observe, predict three actions, plan, lock, and then execute one utterance."""

    _AUDIO_ANCESTRY_TYPES = {
        ChatDataType.MIC_AUDIO,
        ChatDataType.HUMAN_AUDIO,
        ChatDataType.HUMAN_DUPLEX_AUDIO,
        ChatDataType.HUMAN_DUPLEX_AUDIO_PARTIAL,
    }

    def __init__(self):
        super().__init__()
        self.config: Optional[HIWMConfig] = None
        self._api_key: Optional[str] = None

    def get_handler_info(self) -> HandlerBaseInfo:
        return HandlerBaseInfo(config_model=HIWMConfig)

    def load(
        self,
        engine_config: ChatEngineConfigModel,
        handler_config: Optional[HandlerBaseConfigModel] = None,
    ):
        if not isinstance(handler_config, HIWMConfig):
            raise TypeError("HIWM handler requires a valid HIWMConfig")
        api_key = os.environ.get(handler_config.api_key_env)
        if not api_key:
            raise ValueError(
                f"HIWM API key is missing; set environment variable "
                f"{handler_config.api_key_env!r} before startup"
            )
        self.config = handler_config
        self._api_key = api_key
        logger.info(
            f"HIWM handler loaded with model={handler_config.model_name}, "
            f"probability_kind=uncalibrated_model_estimate"
        )

    def create_context(
        self,
        session_context: SessionContext,
        handler_config: Optional[HandlerBaseConfigModel] = None,
    ) -> HandlerContext:
        if not isinstance(handler_config, HIWMConfig):
            raise TypeError("HIWM handler requires a valid HIWMConfig")
        if not self._api_key:
            raise RuntimeError("HIWM handler was not loaded with an API key")

        context = HIWMContext(session_context.session_info.session_id)
        context.config = handler_config
        context.client_perception = bind_latest_client_perception(
            session_context.shared_states
        )
        context.client_session_profile = bind_latest_client_session_profile(
            session_context.shared_states
        )
        context.world_model = OpenAICompatibleWorldModel(
            api_key=self._api_key,
            api_url=handler_config.api_url,
            model_name=handler_config.model_name,
            timeout_seconds=handler_config.request_timeout_seconds,
            temperature=handler_config.temperature,
            input_modalities=handler_config.input_modalities,
            structured_output=handler_config.structured_output,
            enable_thinking=handler_config.enable_thinking,
            max_output_tokens=handler_config.max_output_tokens,
            max_attempts=handler_config.max_attempts,
        )
        context.planner = HIWMPlanner(
            handler_config.planner,
            safety_policy=handler_config.safety_policy,
        )

        ledger_root = Path(handler_config.ledger_dir)
        if not ledger_root.is_absolute():
            ledger_root = Path(DirectoryInfo.get_project_dir()) / ledger_root
        context.ledger = ImmutableJSONLLedger(ledger_root, context.session_id)
        return context

    def start_context(
        self, session_context: SessionContext, handler_context: HandlerContext
    ):
        pass

    def get_handler_detail(
        self, session_context: SessionContext, context: HandlerContext
    ) -> HandlerDetail:
        hiwm_context = cast(HIWMContext, context)
        output_definition = DataBundleDefinition()
        output_definition.add_entry(DataBundleEntry.create_text_entry("avatar_text"))
        inputs = {
            ChatDataType.HUMAN_TEXT: HandlerDataInfo(type=ChatDataType.HUMAN_TEXT)
        }
        if hiwm_context.config is not None and "image" in hiwm_context.config.input_modalities:
            inputs[ChatDataType.CAMERA_VIDEO] = HandlerDataInfo(
                type=ChatDataType.CAMERA_VIDEO
            )
        return HandlerDetail(
            inputs=inputs,
            outputs={
                ChatDataType.AVATAR_TEXT: HandlerDataInfo(
                    type=ChatDataType.AVATAR_TEXT,
                    definition=output_definition,
                    output_stream_config=ChatStreamConfig(cancelable=True),
                )
            },
            signal_filters=[
                SignalFilterRule(ChatSignalType.STREAM_CANCEL, None, None),
                SignalFilterRule(
                    ChatSignalType.STREAM_BEGIN, None, ChatDataType.CLIENT_PLAYBACK
                ),
                SignalFilterRule(
                    ChatSignalType.STREAM_END, None, ChatDataType.CLIENT_PLAYBACK
                ),
            ],
        )

    def handle(
        self,
        context: HandlerContext,
        inputs: ChatData,
        output_definitions: Dict[ChatDataType, HandlerDataInfo],
    ):
        hiwm_context = cast(HIWMContext, context)
        if inputs.type == ChatDataType.CAMERA_VIDEO:
            self._capture_camera_frame(hiwm_context, inputs)
            return None
        if inputs.type != ChatDataType.HUMAN_TEXT:
            return None
        self._handle_finalized_text(hiwm_context, inputs, output_definitions)
        return None

    def _capture_camera_frame(self, context: HIWMContext, inputs: ChatData) -> None:
        if (
            inputs.data is None
            or context.config is None
            or "image" not in context.config.input_modalities
        ):
            return
        now_monotonic = time.monotonic()
        min_interval = context.config.camera_capture_interval_ms / 1000.0
        if (
            context.latest_camera is not None
            and now_monotonic - context.last_camera_capture_monotonic < min_interval
        ):
            return
        raw_frame = inputs.data.get_main_data()
        if not isinstance(raw_frame, np.ndarray):
            return
        frame = self._normalize_camera_frame(raw_frame)
        if frame is None:
            return

        stream_key = inputs.stream_id.stream_key_str if inputs.stream_id else None
        observed_at = time.time()
        evidence_id = f"camera:{stream_key or 'unkeyed'}:{int(observed_at * 1000)}"
        encoded = encode_bgr_frame_as_jpeg(frame, quality=85)
        timestamp = list(inputs.timestamp) if inputs.timestamp else None
        evidence = EvidenceReference(
            evidence_id=evidence_id,
            modality="camera",
            source=inputs.source or "camera_video",
            observed_at=observed_at,
            stream_key=stream_key,
            content=None,
            sha256=encoded.sha256,
            metadata={
                "shape": list(frame.shape),
                "dtype": str(frame.dtype),
                "encoded_media_type": "image/jpeg",
                "encoded_bytes": len(encoded.jpeg_bytes),
                "session_timestamp": timestamp,
            },
        )
        context.latest_camera = CapturedCameraFrame(
            evidence=evidence, data_url=encoded.data_url
        )
        context.last_camera_capture_monotonic = now_monotonic

    @staticmethod
    def _normalize_camera_frame(raw_frame: np.ndarray) -> Optional[np.ndarray]:
        frame = np.asarray(raw_frame)
        while frame.ndim > 3:
            frame = frame[-1]
        if frame.ndim == 2:
            frame = np.repeat(frame[..., np.newaxis], 3, axis=2)
        if frame.ndim != 3 or frame.shape[2] not in (3, 4):
            return None
        if frame.shape[2] == 4:
            frame = frame[..., :3]
        if np.issubdtype(frame.dtype, np.floating):
            max_value = float(np.nanmax(frame)) if frame.size else 0.0
            if max_value <= 1.0:
                frame = frame * 255.0
        frame = np.nan_to_num(frame, nan=0.0, posinf=255.0, neginf=0.0)
        return np.ascontiguousarray(np.clip(frame, 0, 255).astype(np.uint8))

    def _handle_finalized_text(
        self,
        context: HIWMContext,
        inputs: ChatData,
        output_definitions: Dict[ChatDataType, HandlerDataInfo],
    ) -> None:
        stream_key = inputs.stream_id.stream_key_str if inputs.stream_id else "unkeyed"
        chunk = inputs.data.get_main_data() if inputs.data is not None else None
        if isinstance(chunk, str):
            context.text_buffers[stream_key] = context.text_buffers.get(stream_key, "") + chunk

        # This is the hard boundary: no model invocation for partial text.
        if not inputs.is_last_data:
            return

        text = context.text_buffers.pop(stream_key, "").strip()
        if not text:
            return

        turn_started = time.monotonic()
        turn_id = str(uuid4())
        input_stream_key = (
            inputs.stream_id.stream_key_str if inputs.stream_id else None
        )
        input_audio_ancestor_keys = self._audio_ancestry_keys(
            context, inputs.stream_id
        )
        with context.cancellation_state_lock:
            context.cancel_event.clear()
            context.active_input_stream_key = input_stream_key
            context.active_input_audio_ancestor_keys = input_audio_ancestor_keys
        input_lease = None
        stage = "input_validation"
        try:
            if inputs.stream_id is None or context.stream_manager is None:
                raise RuntimeError("HIWM finalized input has no retainable stream")
            input_lease = context.stream_manager.acquire_stream_lease(inputs.stream_id)
            if input_lease is None:
                raise RuntimeError("HIWM finalized input stream is no longer available")
            if context.config is None:
                raise RuntimeError("HIWM context has no configuration")
            if context.config.require_asr_audio_ancestry and not self._has_audio_ancestry(
                context, inputs.stream_id
            ):
                raise ValueError(
                    "finalized HUMAN_TEXT is not linked to a real microphone/audio ASR stream"
                )

            observation, camera_data_url = self._build_observation(
                context=context,
                inputs=inputs,
                text=text,
                turn_id=turn_id,
            )
            if context.cancel_event.is_set():
                logger.info(
                    "HIWM turn stage=input_validation state=cancelled"
                )
                return

            if context.world_model is None:
                raise RuntimeError("HIWM world model is not initialized")
            stage = "api"
            with context.feedback_state_lock:
                historical_beliefs = list(context.historical_beliefs)
                previous_locked_prediction = context.previous_locked_prediction
            api_started = time.monotonic()
            logger.info("HIWM turn stage=api state=started")
            result = context.world_model.infer(
                objective=context.config.objective,
                observation=observation,
                historical_beliefs=historical_beliefs,
                previous_locked_prediction=previous_locked_prediction,
                camera_data_url=camera_data_url,
            )
            logger.info(
                "HIWM turn stage=api state=completed duration_ms={}",
                round((time.monotonic() - api_started) * 1000),
            )
            if context.cancel_event.is_set():
                logger.info("HIWM turn stage=api state=cancelled")
                return

            stage = "planner"
            if context.planner is None:
                raise RuntimeError("HIWM planner is not initialized")
            decision = context.planner.select(result.inference.actions)
            selected_action = next(
                action
                for action in result.inference.actions
                if action.action_id == decision.selected_action_id
            )
            if context.cancel_event.is_set():
                return

            stage = "ledger"
            if context.ledger is None:
                raise RuntimeError("HIWM ledger is not initialized")
            locked_at = time.time()
            payload = PredictionPayload(
                session_id=context.session_id,
                turn_id=turn_id,
                objective=context.config.objective,
                observation=observation,
                content_signals=result.inference.content_signals,
                beliefs=result.inference.beliefs,
                actions=result.inference.actions,
                selected_action_id=decision.selected_action_id,
                planner=decision,
                feedback=result.inference.feedback,
                model=result.model_info,
                locked_at=locked_at,
            )
            locked_record = context.ledger.append(payload)
            if not context.ledger.verify(locked_record):
                raise RuntimeError("newly appended prediction failed ledger verification")
            logger.info(
                "HIWM turn stage=ledger state=locked pre_output_ms={}",
                round((time.monotonic() - turn_started) * 1000),
            )

            if context.cancel_event.is_set():
                logger.info("HIWM turn stage=ledger state=cancelled")
                return

            stage = "output"
            submitted = self._emit_locked_utterance(
                context=context,
                inputs=inputs,
                output_definitions=output_definitions,
                locked_record=locked_record,
                utterance=selected_action.utterance,
            )
            # AVATAR_TEXT submission is only pending execution. A correlated,
            # real CLIENT_PLAYBACK STREAM_END promotes the feedback baseline.
            # The bool is retained so cancellation/error behavior is explicit.
            if not submitted:
                context.playback_feedback.discard_record(locked_record)
                if not context.cancel_event.is_set():
                    raise RuntimeError(
                        "locked HIWM utterance could not enter the output stream"
                    )
            else:
                logger.info(
                    "HIWM turn stage=output state=submitted total_ms={}",
                    round((time.monotonic() - turn_started) * 1000),
                )
        except HIWMResponseValidationError as exc:
            self._emit_error(
                context,
                inputs,
                output_definitions,
                turn_id,
                "response_validation",
                exc,
            )
        except HIWMAPIError as exc:
            self._emit_error(
                context, inputs, output_definitions, turn_id, "api", exc
            )
        except Exception as exc:
            self._emit_error(
                context,
                inputs,
                output_definitions,
                turn_id,
                cast(str, stage),
                exc,
            )
        finally:
            if input_lease is not None:
                input_lease.release()
            with context.cancellation_state_lock:
                if context.active_input_stream_key == input_stream_key:
                    context.active_input_stream_key = None
                    context.active_input_audio_ancestor_keys.clear()

    def _build_observation(
        self,
        *,
        context: HIWMContext,
        inputs: ChatData,
        text: str,
        turn_id: str,
    ) -> tuple[ObservationSnapshot, Optional[str]]:
        stream_key = inputs.stream_id.stream_key_str if inputs.stream_id else None
        ancestry = self._ancestry_metadata(context, inputs.stream_id)
        asr_metadata = {
            "finalized": True,
            "source_chain": ancestry,
            "session_timestamp": list(inputs.timestamp) if inputs.timestamp else None,
        }
        if context.client_perception is not None and context.config is not None:
            perception = context.client_perception.get_fresh(
                context.config.perception_max_age_seconds
            )
            if perception is not None:
                asr_metadata["perception"] = perception.model_dump(mode="json")

        current_asr = EvidenceReference(
            evidence_id=f"asr:{turn_id}",
            modality="asr",
            source=inputs.source or "human_text",
            observed_at=time.time(),
            stream_key=stream_key,
            content=text,
            sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            metadata=asr_metadata,
        )

        camera = (
            context.latest_camera
            if context.config is not None
            and "image" in context.config.input_modalities
            else None
        )
        if camera is not None and context.config is not None:
            if time.time() - camera.evidence.observed_at > context.config.camera_max_age_seconds:
                camera = None

        history = self._history_evidence(context, exclude_stream_key=stream_key)
        observation = ObservationSnapshot(
            cutoff_at=time.time(),
            current_asr=current_asr,
            camera=camera.evidence if camera is not None else None,
            history=history,
        )
        return observation, camera.data_url if camera is not None else None

    def _history_evidence(
        self, context: HIWMContext, exclude_stream_key: Optional[str]
    ) -> List[EvidenceReference]:
        output: List[EvidenceReference] = []
        if context.client_session_profile is not None:
            profile = context.client_session_profile.get()
            if profile is not None:
                text = profile.initial_information
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                output.append(
                    EvidenceReference(
                        evidence_id=f"profile:{profile.profile_id}:{digest[:12]}",
                        modality="history",
                        source="client_confirmed_profile",
                        observed_at=profile.observed_at,
                        content=text,
                        sha256=digest,
                        metadata={
                            "role": "initial_profile",
                            "confirmed_by_user": True,
                        },
                    )
                )
        if context.session_history is None or context.config is None:
            return output
        if context.config.history_max_events == 0:
            return output
        events = context.session_history.get_recent_events(
            data_types=[ChatDataType.HUMAN_TEXT, ChatDataType.AVATAR_TEXT],
            signal_types=[ChatSignalType.STREAM_END],
            max_count=max(context.config.history_max_events * 4, 1),
        )
        conversation: List[EvidenceReference] = []
        seen: Set[tuple] = set()
        for event in events:
            if event.source_stream_key == exclude_stream_key:
                continue
            if not isinstance(event.data, str) or not event.data.strip():
                continue
            role = "human" if event.data_type == ChatDataType.HUMAN_TEXT else "assistant"
            dedupe_key = (role, event.source_stream_key, event.data)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            text = event.data.strip()
            conversation.append(
                EvidenceReference(
                    evidence_id=f"history:{event.event_id}",
                    modality="history",
                    source=event.owner or role,
                    observed_at=event.timestamp,
                    stream_key=event.source_stream_key,
                    content=text,
                    sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    metadata={"role": role, "clock": "session_monotonic"},
                )
            )
        return output + conversation[-context.config.history_max_events :]

    def _has_audio_ancestry(
        self, context: HIWMContext, stream_id: Optional[ChatStreamIdentity]
    ) -> bool:
        return bool(self._audio_ancestry_keys(context, stream_id))

    def _audio_ancestry_keys(
        self, context: HIWMContext, stream_id: Optional[ChatStreamIdentity]
    ) -> Set[str]:
        if stream_id is None or context.stream_manager is None:
            return set()
        ancestry = context.stream_manager.get_stream_ancestry(stream_id)
        related = list(ancestry.get("parents", [])) + list(
            ancestry.get("ancestors", [])
        )
        return {
            item.stream_key_str
            for item in related
            if item.data_type in self._AUDIO_ANCESTRY_TYPES
            and item.stream_key_str is not None
        }

    def _ancestry_metadata(
        self, context: HIWMContext, stream_id: Optional[ChatStreamIdentity]
    ) -> List[dict]:
        if stream_id is None or context.stream_manager is None:
            return []
        ancestry = context.stream_manager.get_stream_ancestry(stream_id)
        result = []
        seen = set()
        for relation in ("parents", "ancestors"):
            for item in ancestry.get(relation, []):
                key = item.stream_key_str
                if key in seen:
                    continue
                seen.add(key)
                result.append(
                    {
                        "relation": relation,
                        "stream_key": key,
                        "data_type": item.data_type.value,
                        "producer": item.producer_name,
                    }
                )
        return result

    def _emit_locked_utterance(
        self,
        *,
        context: HIWMContext,
        inputs: ChatData,
        output_definitions: Dict[ChatDataType, HandlerDataInfo],
        locked_record: LockedPredictionRecord,
        utterance: str,
    ) -> bool:
        if context.cancel_event.is_set():
            return False
        output_info = output_definitions.get(ChatDataType.AVATAR_TEXT)
        streamer = context.data_submitter.get_streamer(ChatDataType.AVATAR_TEXT)
        if output_info is None or output_info.definition is None or streamer is None:
            raise RuntimeError("AVATAR_TEXT output is not configured")
        sources = [inputs.stream_id] if inputs.stream_id is not None else []
        output_stream_id = streamer.new_stream(
            sources=sources,
            name="hiwm",
            config=ChatStreamConfig(cancelable=True),
        )
        if streamer.current_stream is None:
            return False
        output_stream_key = output_stream_id.stream_key_str
        with context.cancellation_state_lock:
            context.active_output_stream_key = output_stream_key

        # Register before distributing AVATAR_TEXT so a very fast downstream
        # playback BEGIN cannot race ahead of the pending state.
        context.playback_feedback.register(
            locked_record, output_stream_id.stream_key_str
        )

        spoken = DataBundle(output_info.definition)
        spoken.set_main_data(utterance)
        spoken.add_meta("hiwm", locked_record.model_dump(mode="json"))

        final = DataBundle(output_info.definition)
        final.set_main_data("")
        try:
            return submit_locked_sequence(
                is_cancelled=context.cancel_event.is_set,
                submit_spoken=lambda: streamer.stream_data(
                    spoken, finish_stream=False
                ),
                cancel_current=streamer.cancel_current,
                submit_final=lambda: streamer.stream_data(final, finish_stream=True),
                on_final_error=lambda exc: logger.error(
                    "HIWM utterance submitted but final bundle failed; "
                    "error_type={}",
                    type(exc).__name__,
                ),
            )
        except Exception:
            context.playback_feedback.discard_record(locked_record)
            raise
        finally:
            with context.cancellation_state_lock:
                if context.active_output_stream_key == output_stream_key:
                    context.active_output_stream_key = None

    @staticmethod
    def _playback_ancestry_keys(
        context: HIWMContext, related: Optional[ChatStreamIdentity]
    ) -> Set[str]:
        if related is None or context.stream_manager is None:
            return set()
        ancestry = context.stream_manager.get_stream_ancestry(related)
        return {
            item.stream_key_str
            for item in list(ancestry.get("parents", []))
            + list(ancestry.get("ancestors", []))
            if item.stream_key_str
        }

    def _set_cancel_if_correlated(
        self,
        context: HIWMContext,
        related: Optional[ChatStreamIdentity],
    ) -> Optional[str]:
        """Atomically cancel only the turn owning ``related``.

        Input cancellation is correlated to the finalized HUMAN_TEXT stream or
        one of its audio ancestors. Output cancellation is correlated to the
        AVATAR_TEXT currently being submitted or one of that stream's
        descendants. An unscoped cancellation remains a session-wide cancel,
        matching the pre-existing shutdown/interrupt behavior.
        """

        with context.cancellation_state_lock:
            if related is None:
                context.cancel_event.set()
                return "session"

            related_key = related.stream_key_str
            if related_key is None:
                return None

            if (
                related.data_type == ChatDataType.HUMAN_TEXT
                and related_key == context.active_input_stream_key
            ):
                context.cancel_event.set()
                return "active_input"

            if (
                related.data_type in self._AUDIO_ANCESTRY_TYPES
                and related_key in context.active_input_audio_ancestor_keys
            ):
                context.cancel_event.set()
                return "active_input_audio_ancestor"

            active_output_key = context.active_output_stream_key
            if (
                related.data_type == ChatDataType.AVATAR_TEXT
                and related_key == active_output_key
            ):
                context.cancel_event.set()
                return "active_output"

            if active_output_key is not None:
                ancestry_keys = self._playback_ancestry_keys(context, related)
                if active_output_key in ancestry_keys:
                    context.cancel_event.set()
                    return "active_output_descendant"

        return None

    def _handle_playback_lifecycle(
        self, context: HIWMContext, signal: ChatSignal
    ) -> None:
        related = signal.related_stream
        playback_key = related.stream_key_str if related is not None else None
        ancestry_keys = self._playback_ancestry_keys(context, related)
        if signal.type == ChatSignalType.STREAM_BEGIN:
            context.playback_feedback.bind_playback(playback_key, ancestry_keys)
            return
        if signal.type == ChatSignalType.STREAM_CANCEL:
            context.playback_feedback.cancel_playback(playback_key, ancestry_keys)
            return
        if signal.type != ChatSignalType.STREAM_END:
            return
        executed = context.playback_feedback.complete(playback_key, ancestry_keys)
        if executed is not None:
            with context.feedback_state_lock:
                context.previous_locked_prediction = executed
                context.historical_beliefs = list(executed.beliefs)

    def _emit_error(
        self,
        context: HIWMContext,
        inputs: ChatData,
        output_definitions: Dict[ChatDataType, HandlerDataInfo],
        turn_id: str,
        stage: str,
        exc: Exception,
    ) -> None:
        logger.error(
            "HIWM turn failed at stage={} error_type={}",
            stage,
            type(exc).__name__,
        )
        if context.cancel_event.is_set():
            return
        try:
            valid_stage = stage if stage in {
                "input_validation",
                "api",
                "response_validation",
                "planner",
                "ledger",
                "output",
            } else "output"
            error = HIWMError(
                session_id=context.session_id,
                turn_id=turn_id,
                stage=valid_stage,
                code=type(exc).__name__,
                message=(
                    "本轮预测不可用；系统已自动切换到安全的澄清/等待路径。"
                ),
                occurred_at=time.time(),
            )
            output_info = output_definitions.get(ChatDataType.AVATAR_TEXT)
            streamer = context.data_submitter.get_streamer(ChatDataType.AVATAR_TEXT)
            if output_info is None or output_info.definition is None or streamer is None:
                logger.error("Cannot emit HIWM error: AVATAR_TEXT output is unavailable")
                return
            if context.config is None or context.ledger is None:
                logger.error("Cannot lock HIWM fallback: runtime is unavailable")
                return
            locked_fallback = context.ledger.append_fallback(
                SafetyFallbackPayload(
                    session_id=context.session_id,
                    turn_id=turn_id,
                    stage=valid_stage,
                    action_id=context.config.fallback_action,
                    utterance=context.config.fallback_utterance,
                    reason=error.message,
                    locked_at=time.time(),
                )
            )
            if not context.ledger.verify_fallback(locked_fallback):
                logger.error("Newly appended HIWM fallback failed ledger verification")
                return
            sources = [inputs.stream_id] if inputs.stream_id is not None else []
            output_stream_id = streamer.new_stream(
                sources=sources,
                name="hiwm_safe_fallback",
                config=ChatStreamConfig(cancelable=True),
            )
            if streamer.current_stream is None:
                return
            output_stream_key = output_stream_id.stream_key_str
            with context.cancellation_state_lock:
                context.active_output_stream_key = output_stream_key
            try:
                spoken = DataBundle(output_info.definition)
                spoken.set_main_data(context.config.fallback_utterance)
                spoken.add_meta("hiwm_error", error.model_dump(mode="json"))
                spoken.add_meta(
                    "hiwm_fallback", locked_fallback.model_dump(mode="json")
                )
                final = DataBundle(output_info.definition)
                final.set_main_data("")
                submit_locked_sequence(
                    is_cancelled=context.cancel_event.is_set,
                    submit_spoken=lambda: streamer.stream_data(
                        spoken, finish_stream=False
                    ),
                    cancel_current=streamer.cancel_current,
                    submit_final=lambda: streamer.stream_data(
                        final, finish_stream=True
                    ),
                    on_final_error=lambda final_exc: logger.error(
                        "HIWM safe fallback final bundle failed; error_type={}",
                        type(final_exc).__name__,
                    ),
                )
            finally:
                with context.cancellation_state_lock:
                    if context.active_output_stream_key == output_stream_key:
                        context.active_output_stream_key = None
        except Exception as output_exc:
            logger.error(
                "Failed to emit safe HIWM fallback; error_type={}",
                type(output_exc).__name__,
            )

    def on_signal(self, context: HandlerContext, signal: ChatSignal):
        hiwm_context = cast(HIWMContext, context)
        related = signal.related_stream
        if related is not None and related.data_type == ChatDataType.CLIENT_PLAYBACK:
            self._handle_playback_lifecycle(hiwm_context, signal)
        if signal.type != ChatSignalType.STREAM_CANCEL:
            return
        if related is not None and related.data_type == ChatDataType.HUMAN_TEXT:
            if related.stream_key_str:
                hiwm_context.text_buffers.pop(related.stream_key_str, None)
        if related is None:
            hiwm_context.playback_feedback.clear()
        elif related.data_type == ChatDataType.AVATAR_TEXT:
            hiwm_context.playback_feedback.discard_avatar_text(
                related.stream_key_str
            )
        cancel_scope = self._set_cancel_if_correlated(hiwm_context, related)
        related_type = related.data_type.value if related is not None else "none"
        if cancel_scope is not None:
            logger.info(
                "HIWM cancellation accepted; scope={} related_type={}",
                cancel_scope,
                related_type,
            )
        else:
            logger.info(
                "HIWM cancellation ignored; reason=unrelated related_type={}",
                related_type,
            )

    def destroy_context(self, context: HandlerContext):
        hiwm_context = cast(HIWMContext, context)
        with hiwm_context.cancellation_state_lock:
            hiwm_context.cancel_event.set()
            hiwm_context.active_input_stream_key = None
            hiwm_context.active_input_audio_ancestor_keys.clear()
            hiwm_context.active_output_stream_key = None
        hiwm_context.text_buffers.clear()
        hiwm_context.latest_camera = None
        if hiwm_context.client_session_profile is not None:
            hiwm_context.client_session_profile.clear()
        hiwm_context.playback_feedback.clear()
        if hiwm_context.world_model is not None:
            try:
                hiwm_context.world_model.close()
            finally:
                hiwm_context.world_model = None
