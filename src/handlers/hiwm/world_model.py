"""OpenAI-compatible, non-streaming HIWM inference with strict validation."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

from loguru import logger
from pydantic import ValidationError

from .models import (
    BeliefItem,
    HIWMModelInference,
    LockedPredictionRecord,
    ModelInfo,
    ObservationSnapshot,
)


SYSTEM_PROMPT = """你是人际交互世界模型中的预测组件。
只能使用所提供的已定稿观察、历史信念和上一条已锁定预测。
维护与任务相关且可证伪的交互信念。绝不能把隐藏情绪、人格、欺骗行为、诊断结果或受保护特征断言为事实。
每条信念和每个动作只能引用所提供观察中存在的 evidence_id。

将与任务相关的语言内容提取到 content_signals。每一项的类型必须是以下之一：
need、concern、commitment、question 或 unknown。每一项都必须以当前已定稿的 ASR 证据为依据，
保留不确定性，不得把声学或视觉特征转化为内容层面的断言。

生成恰好三个实质不同且可立即执行的沟通动作。
其中恰好一个候选动作必须采用保守的澄清或等待策略，其 strategy 必须以 ASCII 标记 `clarify` 或 `wait` 开头。
当所有积极行动分支的风险或不确定性过高时，该动作将作为确定性服务端规划器的安全出口。
每个动作都要提供：准确话术、预测的下一个可观察回应、预测的任务状态变化、目标达成概率、风险概率、
简洁的风险说明、不确定性、information_gain 以及证据引用。information_gain 表示观察该动作对应回应后，
与任务相关的不确定性预计会减少多少（归一化值）：0 表示预计不会减少，1 表示在合理动作中预计减少最多。
这些数值是模型当前给出的、未经校准的 [0, 1] 区间估计，不代表实测准确率。
不要替用户选择动作；服务端规划器会在验证后进行选择。

这是实时对话，JSON 必须紧凑：content_signals 最多 4 项，beliefs 最多 6 项；
每个动作只给 1 项 predicted_state_delta，utterance 最多 80 个字符，
predicted_observation、risk 和 feedback 中的说明各用一个短句。不要重述输入或模式。

结构完整性要求：content_signals 和 beliefs 都必须至少包含 1 项；actions 必须恰好包含 3 项；
所有必填字符串都必须是非空白短文本，禁止使用空字符串或仅空格占位；所有必填概率都必须填写。
首轮 previous_locked_prediction 为 null 时，feedback 必须为 null。

当 previous_locked_prediction 存在时，将其与当前已定稿的 ASR 比较，并针对上一轮的对应预测提供反馈。
当该字段为 null 时，feedback 也必须为 null。
只返回符合响应模式的 JSON，不要添加 Markdown 或任何说明文字。
"""


class HIWMAPIError(RuntimeError):
    pass


class HIWMResponseValidationError(ValueError):
    def __init__(self, message: str, *, issues: Optional[list[str]] = None):
        super().__init__(message)
        self.issues = tuple(issues or ())


def _safe_validation_issues(exc: Exception) -> list[str]:
    if isinstance(exc, ValidationError):
        issues = []
        for item in exc.errors(
            include_url=False, include_context=False, include_input=False
        ):
            location = ".".join(str(part) for part in item.get("loc", ())) or "root"
            issues.append(f"{location}:{item.get('type', 'validation_error')}")
        return issues[:20]
    if isinstance(exc, json.JSONDecodeError):
        return ["response:invalid_json"]

    # Map known adapter failures to value-free codes. Never include the raw
    # provider response or exception message: both can contain user content.
    message = str(exc)
    known_messages = (
        ("model response has no choices", "response:no_choices"),
        ("model response content is empty", "response:empty_content"),
        ("HIWM response must be a JSON object", "response:not_json_object"),
        ("HIWM response must contain a JSON object", "response:not_json_object"),
        ("content_signals must be an array", "content_signals:array_type"),
        ("beliefs must be an array", "beliefs:array_type"),
        ("actions must be an array", "actions:array_type"),
        ("predicted_state_delta must be an array", "actions.predicted_state_delta:array_type"),
        ("evidence_refs must be a non-empty array", "evidence_refs:missing"),
        ("evidence_refs entries must be non-empty strings", "evidence_refs:string_type"),
        ("evidence_refs must be unique", "evidence_refs:duplicate"),
        ("evidence_refs contains unknown observation IDs", "evidence_refs:unknown"),
        (
            "evidence_refs must include finalized current ASR evidence",
            "evidence_refs:missing_current_asr",
        ),
        ("candidate set has no explicit conservative exit", "actions:missing_conservative_exit"),
    )
    for expected, code in known_messages:
        if expected in message:
            return [code]
    if "contains prohibited model-generated claim class" in message:
        return ["generated_text:prohibited_claim"]
    if "must be in [0, 1]" in message or "must be numeric" in message:
        return ["probability:number_out_of_range_or_type"]
    if "must be non-empty text" in message or "must not be blank" in message:
        return ["generated_text:blank"]
    return [f"response:{type(exc).__name__}"]


def _validation_repair_message(issues: Sequence[str]) -> str:
    """Build a value-free correction request for a validation retry."""

    return json.dumps(
        {
            "request_type": "schema_validation_retry",
            "instruction": (
                "上一份回答未通过验证。请针对原始请求重新生成一个全新的 JSON 对象，"
                "并严格符合 required_response_schema。返回恰好三个不同的动作，"
                "其中恰好一个是 clarify/wait 动作。content_signals 和 beliefs 都至少返回一项，"
                "所有必填字符串必须非空，所有必填概率必须填写。"
                "只能使用所提供观察中的 evidence_id。"
                "只返回 JSON。"
            ),
            "validation_issues": list(issues[:20]),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


@dataclass(frozen=True)
class WorldModelResult:
    inference: HIWMModelInference
    model_info: ModelInfo


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value.strip()


def _probability(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not 0.0 <= parsed <= 1.0:
        raise ValueError(f"{field} must be in [0, 1]")
    return parsed


def _enum_value(value: Any, allowed: set[str], fallback: str) -> str:
    normalized = str(value or "").strip().casefold()
    return normalized if normalized in allowed else fallback


def _rows(value: Any, field: str) -> list[dict[str, Any]]:
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        value = value["items"]
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{field} entries must be objects")
    return value


def _stable_id(value: Any, *, prefix: str, index: int, seen: set[str]) -> str:
    candidate = str(value or "").strip()[:128]
    if not candidate or candidate in seen:
        candidate = f"{prefix}-{index}"
    suffix = 2
    base = candidate
    while candidate in seen:
        candidate = f"{base}-{suffix}"
        suffix += 1
    seen.add(candidate)
    return candidate


def _evidence_refs(
    value: Any,
    *,
    allowed: set[str],
    current_asr_id: str,
    require_current: bool,
) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("evidence_refs must be a non-empty array")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError("evidence_refs entries must be non-empty strings")
    refs = [item.strip() for item in value]
    if len(refs) != len(set(refs)):
        raise ValueError("evidence_refs must be unique")
    unknown = set(refs) - allowed
    if unknown:
        raise ValueError("evidence_refs contains unknown observation IDs")
    if require_current and current_asr_id not in refs:
        raise ValueError("evidence_refs must include finalized current ASR evidence")
    return refs


def _normalize_provider_payload(
    content: str,
    *,
    observation: ObservationSnapshot,
    previous_turn_id: Optional[str],
) -> HIWMModelInference:
    """Normalize provider syntax without inventing audit evidence.

    JSON mode guarantees syntax, not exact schema adherence. Models should not
    be authoritative for local row IDs or previous-turn linkage, so the server
    can stabilize those transport details. Evidence references are different:
    unknown IDs and a missing required current-ASR ID are rejected rather than
    silently removed or replaced.
    """

    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("HIWM response must be a JSON object")
    if not {"content_signals", "beliefs", "actions"}.issubset(payload):
        for wrapper in ("inference", "result", "output"):
            nested = payload.get(wrapper)
            if isinstance(nested, dict):
                payload = nested
                break

    allowed_refs = observation.evidence_ids()
    current_asr_id = observation.current_asr.evidence_id

    content_ids: set[str] = set()
    content_signals = []
    for index, item in enumerate(
        _rows(payload.get("content_signals"), "content_signals"), 1
    ):
        content_signals.append(
            {
                "id": _stable_id(
                    item.get("id"), prefix="content", index=index, seen=content_ids
                ),
                "category": _enum_value(
                    item.get("category"),
                    {"need", "concern", "commitment", "question", "unknown"},
                    "unknown",
                ),
                "statement": _required_text(item.get("statement"), "statement"),
                "confidence": _probability(item.get("confidence"), "confidence"),
                "evidence_refs": _evidence_refs(
                    item.get("evidence_refs"),
                    allowed=allowed_refs,
                    current_asr_id=current_asr_id,
                    require_current=True,
                ),
                "change": _enum_value(
                    item.get("change"),
                    {"new", "updated", "unchanged", "retracted"},
                    "new",
                ),
            }
        )

    belief_ids: set[str] = set()
    beliefs = []
    for index, item in enumerate(_rows(payload.get("beliefs"), "beliefs"), 1):
        beliefs.append(
            {
                "id": _stable_id(
                    item.get("id"), prefix="belief", index=index, seen=belief_ids
                ),
                "statement": _required_text(item.get("statement"), "statement"),
                "status": _enum_value(
                    item.get("status"),
                    {"known", "working_hypothesis", "unknown"},
                    "working_hypothesis",
                ),
                "confidence": _probability(item.get("confidence"), "confidence"),
                "evidence_refs": _evidence_refs(
                    item.get("evidence_refs"),
                    allowed=allowed_refs,
                    current_asr_id=current_asr_id,
                    require_current=False,
                ),
                "change": _enum_value(
                    item.get("change"),
                    {"new", "updated", "unchanged", "retracted"},
                    "new",
                ),
            }
        )

    action_ids: set[str] = set()
    actions = []
    for index, item in enumerate(_rows(payload.get("actions"), "actions"), 1):
        delta_rows = _rows(item.get("predicted_state_delta"), "predicted_state_delta")
        actions.append(
            {
                "action_id": _stable_id(
                    item.get("action_id"),
                    prefix="action",
                    index=index,
                    seen=action_ids,
                ),
                "strategy": _required_text(item.get("strategy"), "strategy"),
                "utterance": _required_text(item.get("utterance"), "utterance"),
                "predicted_observation": _required_text(
                    item.get("predicted_observation"), "predicted_observation"
                ),
                "predicted_state_delta": [
                    {
                        "target": _required_text(delta.get("target"), "target"),
                        "predicted_change": _required_text(
                            delta.get("predicted_change"), "predicted_change"
                        ),
                    }
                    for delta in delta_rows
                ],
                "goal_probability": _probability(
                    item.get("goal_probability"), "goal_probability"
                ),
                "risk_probability": _probability(
                    item.get("risk_probability"), "risk_probability"
                ),
                "risk": _required_text(item.get("risk"), "risk"),
                "uncertainty": _probability(item.get("uncertainty"), "uncertainty"),
                # Older provider responses remain valid and contribute no
                # unsubstantiated information-gain bonus.
                "information_gain": _probability(
                    item.get("information_gain", 0.0), "information_gain"
                ),
                "evidence_refs": _evidence_refs(
                    item.get("evidence_refs"),
                    allowed=allowed_refs,
                    current_asr_id=current_asr_id,
                    require_current=True,
                ),
            }
        )

    feedback = None
    if previous_turn_id is not None:
        raw_feedback = payload.get("feedback")
        if isinstance(raw_feedback, dict):
            feedback = {
                "previous_turn_id": previous_turn_id,
                "actual_observation": _required_text(
                    raw_feedback.get("actual_observation"), "actual_observation"
                ),
                "comparison": _enum_value(
                    raw_feedback.get("comparison"),
                    {"matched", "partial", "miss", "indeterminate"},
                    "indeterminate",
                ),
                "explanation": _required_text(
                    raw_feedback.get("explanation"), "explanation"
                ),
                "evidence_refs": _evidence_refs(
                    raw_feedback.get("evidence_refs"),
                    allowed=allowed_refs,
                    current_asr_id=current_asr_id,
                    require_current=True,
                ),
            }

    return HIWMModelInference.model_validate(
        {
            "content_signals": content_signals,
            "beliefs": beliefs,
            "actions": actions,
            "feedback": feedback,
        }
    )


def _extract_json_object(content: str) -> str:
    """Extract one complete JSON object while rejecting non-object payloads."""

    stripped = content.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline >= 0:
            stripped = stripped[first_newline + 1 :]
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3].rstrip()
    start = stripped.find("{")
    if start < 0:
        raise json.JSONDecodeError("no JSON object found", stripped, 0)
    value, _end = json.JSONDecoder().raw_decode(stripped, start)
    if not isinstance(value, dict):
        raise ValueError("HIWM response must contain a JSON object")
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _canonicalize_conservative_exit(
    inference: HIWMModelInference,
) -> HIWMModelInference:
    """Canonicalize a localized clarify/wait label without changing semantics."""

    actions = list(inference.actions)
    explicit = [
        index
        for index, action in enumerate(actions)
        if action.strategy.strip().casefold().startswith(("clarify", "wait"))
    ]
    if not explicit:
        localized = [
            index
            for index, action in enumerate(actions)
            if any(
                marker in action.strategy.strip().casefold()
                for marker in ("clarification", "wait", "澄清", "等待")
            )
        ]
        if localized:
            chosen = localized[0]
            actions[chosen] = actions[chosen].model_copy(
                update={"strategy": f"clarify:{actions[chosen].strategy}"}
            )
            explicit = [chosen]
    if len(explicit) > 1:
        for index in explicit[1:]:
            actions[index] = actions[index].model_copy(
                update={"strategy": f"alternative:{actions[index].strategy}"}
            )
        explicit = explicit[:1]
    if len(explicit) != 1:
        raise ValueError("candidate set has no explicit conservative exit")
    return inference.model_copy(update={"actions": actions})


class OpenAICompatibleWorldModel:
    def __init__(
        self,
        *,
        api_key: str,
        api_url: str,
        model_name: str,
        timeout_seconds: float,
        temperature: float,
        input_modalities: Sequence[str],
        structured_output: bool,
        enable_thinking: bool,
        max_output_tokens: int = 4096,
        max_attempts: int = 2,
    ):
        from openai import OpenAI

        self.api_url = api_url
        self.model_name = model_name
        self.temperature = temperature
        self.input_modalities = frozenset(input_modalities)
        self.structured_output = structured_output
        self.enable_thinking = enable_thinking
        self.max_output_tokens = max_output_tokens
        self.max_attempts = max(1, max_attempts)
        self._client = OpenAI(
            api_key=api_key,
            base_url=api_url,
            timeout=timeout_seconds,
        )

    def close(self) -> None:
        self._client.close()

    def infer(
        self,
        *,
        objective: str,
        observation: ObservationSnapshot,
        historical_beliefs: Sequence[BeliefItem],
        previous_locked_prediction: Optional[LockedPredictionRecord],
        camera_data_url: Optional[str],
    ) -> WorldModelResult:
        request_body: Dict[str, Any] = {
            "objective": objective,
            "observation": observation.model_dump(mode="json"),
            "historical_beliefs": [
                item.model_dump(mode="json") for item in historical_beliefs
            ],
            "previous_locked_prediction": (
                previous_locked_prediction.model_dump(mode="json")
                if previous_locked_prediction is not None
                else None
            ),
            "required_response_schema": HIWMModelInference.model_json_schema(),
        }
        serialized_request = json.dumps(
            request_body, ensure_ascii=False, separators=(",", ":")
        )
        user_content: Any = serialized_request
        if camera_data_url is not None and "image" in self.input_modalities:
            user_content = [{"type": "text", "text": serialized_request}]
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": camera_data_url},
                }
            )

        validation_issues: list[str] = []
        for attempt in range(1, self.max_attempts + 1):
            requested_at = time.time()
            try:
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ]
                if validation_issues:
                    messages.append(
                        {
                            "role": "user",
                            "content": _validation_repair_message(validation_issues),
                        }
                    )
                completion_args: Dict[str, Any] = {
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_output_tokens,
                    "stream": False,
                    "extra_body": {"enable_thinking": self.enable_thinking},
                }
                if self.structured_output:
                    completion_args["response_format"] = {"type": "json_object"}
                response = self._client.chat.completions.create(**completion_args)
            except Exception as exc:
                if attempt < self.max_attempts:
                    continue
                # Provider messages can contain request details. Keep the
                # client-facing exception deliberately stable and value-free.
                raise HIWMAPIError(
                    f"HIWM provider request failed after {self.max_attempts} attempt(s)"
                ) from exc
            completed_at = time.time()

            try:
                if not response.choices:
                    raise ValueError("model response has no choices")
                content = response.choices[0].message.content
                if isinstance(content, list):
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict):
                            text_parts.append(str(item.get("text", "")))
                        else:
                            text_parts.append(str(getattr(item, "text", item)))
                    content = "".join(text_parts)
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("model response content is empty")
                json_content = _extract_json_object(content)
                try:
                    inference = HIWMModelInference.model_validate_json(json_content)
                except (ValidationError, ValueError, TypeError):
                    inference = _normalize_provider_payload(
                        json_content,
                        observation=observation,
                        previous_turn_id=(
                            previous_locked_prediction.turn_id
                            if previous_locked_prediction is not None
                            else None
                        ),
                    )
                inference = _canonicalize_conservative_exit(inference)
                inference.validate_against_observation(
                    observation,
                    previous_locked_prediction.turn_id
                    if previous_locked_prediction is not None
                    else None,
                )
            except (ValidationError, ValueError, TypeError) as exc:
                validation_issues = _safe_validation_issues(exc)
                logger.warning(
                    "HIWM response validation rejected attempt={}/{} issues={}",
                    attempt,
                    self.max_attempts,
                    validation_issues,
                )
                if attempt < self.max_attempts:
                    continue
                raise HIWMResponseValidationError(
                    f"HIWM response failed strict validation after "
                    f"{self.max_attempts} attempt(s)",
                    issues=validation_issues,
                ) from exc

            return WorldModelResult(
                inference=inference,
                model_info=ModelInfo(
                    model_name=self.model_name,
                    api_url=self.api_url,
                    response_id=getattr(response, "id", None),
                    requested_at=requested_at,
                    completed_at=completed_at,
                ),
            )

        raise AssertionError("unreachable HIWM retry state")
