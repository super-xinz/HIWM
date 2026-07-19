#!/usr/bin/env python3
"""One-shot, privacy-preserving smoke checks for the configured cloud services.

The script intentionally keeps audio and text in memory, prints only aggregate
validation facts, and records a marker so an unattended monitor cannot repeat
billable calls by accident.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import threading
import time
import wave
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dotenv import load_dotenv  # noqa: E402


MARKER_PATH = ROOT / "temp" / "cloud_smoke_result.json"
ATTEMPT_LOCK_DIR = ROOT / "temp" / "cloud_smoke_attempts"
_ATTEMPT_MODES = frozenset(
    {
        "full",
        "retry_failed_hiwm",
        "validate_hiwm_adapter",
        "validate_json_envelope",
        "validate_schema_retry",
    }
)


def _fsync_directory(path: Path) -> None:
    """Persist a newly created attempt entry in its containing directory."""

    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _attempt_lock_path(mode: str) -> Path:
    if mode not in _ATTEMPT_MODES:
        raise ValueError(f"unsupported cloud smoke attempt mode: {mode}")
    return ATTEMPT_LOCK_DIR / f"{mode}.lock"


def _claim_attempt(mode: str) -> Path:
    """Atomically and durably consume one billable attempt before key access.

    The lock is deliberately never removed by this script.  Keeping it after a
    normal return, an exception, or a process crash closes the interval where a
    completed provider call could otherwise be repeated before the result marker
    was written.  Each explicitly supported recovery mode has its own one-shot
    lock so the existing full -> retry -> adapter -> envelope sequence remains
    available without allowing the same stage to run twice.
    """

    lock_path = _attempt_lock_path(mode)
    ATTEMPT_LOCK_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(ATTEMPT_LOCK_DIR, 0o700)
    payload = (
        json.dumps(
            {
                "schema_version": "1.0",
                "mode": mode,
                "claimed_at": time.time(),
                "pid": os.getpid(),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    descriptor = os.open(lock_path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=False) as lock_file:
            lock_file.write(payload)
            lock_file.flush()
            os.fsync(lock_file.fileno())
    finally:
        os.close(descriptor)
    _fsync_directory(ATTEMPT_LOCK_DIR)
    return lock_path


def _write_private_report(report: dict[str, Any]) -> None:
    """Persist only aggregate smoke facts with owner-only permissions."""

    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    descriptor = os.open(
        MARKER_PATH,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as marker_file:
        # os.open's mode is ignored for an existing file, so enforce it on the
        # live descriptor before writing any aggregate result.
        os.fchmod(marker_file.fileno(), 0o600)
        marker_file.write(payload)
        marker_file.flush()
        os.fsync(marker_file.fileno())


def _load_key() -> str:
    load_dotenv(ROOT / ".env", override=False)
    key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not key or key == "NOT_CONFIGURED_YET":
        raise RuntimeError("DASHSCOPE_API_KEY is not configured")
    return key


def _run_hiwm(key: str) -> dict[str, Any]:
    from handlers.hiwm.models import EvidenceReference, ObservationSnapshot
    from handlers.hiwm.world_model import OpenAICompatibleWorldModel

    text = "我想确认系统是否已经准备好，请给出一个清晰的下一步。"
    now = time.time()
    evidence = EvidenceReference(
        evidence_id="cloud-smoke-asr-1",
        modality="asr",
        source="synthetic_cloud_smoke",
        observed_at=now,
        stream_key="cloud-smoke",
        content=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        metadata={"synthetic": True},
    )
    observation = ObservationSnapshot(
        cutoff_at=now,
        current_asr=evidence,
        camera=None,
        history=[],
    )
    model = OpenAICompatibleWorldModel(
        api_key=key,
        api_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen3-vl-flash",
        timeout_seconds=30,
        temperature=0.2,
        input_modalities=["text", "image"],
        structured_output=True,
        enable_thinking=False,
        max_output_tokens=2048,
        max_attempts=2,
    )
    started = time.monotonic()
    try:
        result = model.infer(
            objective="准确回应当前问题并推进一个可验证的下一步。",
            observation=observation,
            historical_beliefs=[],
            previous_locked_prediction=None,
            camera_data_url=None,
        )
    finally:
        model.close()
    inference = result.inference
    conservative = sum(
        action.strategy.casefold().startswith(("clarify", "wait"))
        for action in inference.actions
    )
    if len(inference.actions) != 3 or conservative != 1:
        raise RuntimeError("HIWM strict action contract was not satisfied")
    if not inference.content_signals or not inference.beliefs:
        raise RuntimeError("HIWM structured evidence fields were empty")
    return {
        "status": "ok",
        "model": result.model_info.model_name,
        "latency_ms": round((time.monotonic() - started) * 1000),
        "action_count": len(inference.actions),
        "content_signal_count": len(inference.content_signals),
        "belief_count": len(inference.beliefs),
        "conservative_exit_count": conservative,
    }


def _run_tts(key: str) -> dict[str, Any]:
    import dashscope
    from dashscope.audio.tts_v2 import AudioFormat, ResultCallback, SpeechSynthesizer

    class ProbeCallback(ResultCallback):
        def __init__(self) -> None:
            self.audio_bytes = 0
            self.completed = False
            self.failed = False

        def on_data(self, data: bytes) -> None:
            self.audio_bytes += len(data)

        def on_complete(self) -> None:
            self.completed = True

        def on_error(self, _message: Any) -> None:
            self.failed = True

    dashscope.api_key = key
    callback = ProbeCallback()
    synthesizer = SpeechSynthesizer(
        model="cosyvoice-v3-flash",
        voice="longxing_v3",
        callback=callback,
        format=AudioFormat.PCM_24000HZ_MONO_16BIT,
    )
    started = time.monotonic()
    synthesizer.streaming_call("系统语音合成测试完成。")
    synthesizer.streaming_complete(complete_timeout_millis=30_000)
    if callback.failed or not callback.completed or callback.audio_bytes <= 0:
        raise RuntimeError("TTS returned no completed audio")
    return {
        "status": "ok",
        "model": "cosyvoice-v3-flash",
        "latency_ms": round((time.monotonic() - started) * 1000),
        "audio_bytes": callback.audio_bytes,
    }


def _run_asr(key: str, wav_path: Path) -> dict[str, Any]:
    import dashscope
    from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult

    class ProbeCallback(RecognitionCallback):
        def __init__(self) -> None:
            super().__init__()
            self.parts: list[str] = []
            self.failed = False
            self.completed = threading.Event()

        def on_event(self, result: RecognitionResult) -> None:
            sentence = result.get_sentence()
            if sentence.get("text") and RecognitionResult.is_sentence_end(sentence):
                self.parts.append(str(sentence["text"]))

        def on_complete(self) -> None:
            self.completed.set()

        def on_error(self, _result: RecognitionResult) -> None:
            self.failed = True
            self.completed.set()

        def on_close(self) -> None:
            self.completed.set()

    with wave.open(str(wav_path), "rb") as wav_file:
        if (
            wav_file.getnchannels() != 1
            or wav_file.getsampwidth() != 2
            or wav_file.getframerate() != 16_000
        ):
            raise RuntimeError("ASR smoke WAV must be mono 16-bit 16 kHz PCM")
        audio = wav_file.readframes(wav_file.getnframes())
        duration_ms = round(wav_file.getnframes() / 16_000 * 1000)

    dashscope.api_key = key
    dashscope.base_websocket_api_url = (
        "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
    )
    callback = ProbeCallback()
    recognition = Recognition(
        model="fun-asr-realtime",
        format="pcm",
        sample_rate=16_000,
        semantic_punctuation_enabled=True,
        language_hints=["zh"],
        callback=callback,
    )
    started = time.monotonic()
    recognition.start()
    for offset in range(0, len(audio), 3_200):
        recognition.send_audio_frame(audio[offset : offset + 3_200])
    recognition.stop()
    callback.completed.wait(timeout=30)
    recognized = "".join(callback.parts).strip()
    if callback.failed or not recognized:
        raise RuntimeError("ASR returned no finalized text")
    return {
        "status": "ok",
        "model": "fun-asr-realtime",
        "latency_ms": round((time.monotonic() - started) * 1000),
        "input_duration_ms": duration_ms,
        "recognized_nonempty": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm-one-time-cloud-cost",
        action="store_true",
        help="required acknowledgement that this command makes billable calls",
    )
    parser.add_argument("--asr-wav", type=Path)
    retry_group = parser.add_mutually_exclusive_group()
    retry_group.add_argument(
        "--retry-failed-hiwm-once",
        action="store_true",
        help="retry only a previously failed HIWM check; never repeats ASR/TTS",
    )
    retry_group.add_argument(
        "--validate-hiwm-adapter-once",
        action="store_true",
        help="one final HIWM-only validation after a local adapter fix",
    )
    retry_group.add_argument(
        "--validate-json-envelope-once",
        action="store_true",
        help="one capped HIWM-only validation after JSON envelope handling",
    )
    retry_group.add_argument(
        "--validate-schema-retry-once",
        action="store_true",
        help="one capped HIWM-only validation after schema-aware retry handling",
    )
    args = parser.parse_args()
    if not args.confirm_one_time_cloud_cost:
        parser.error("--confirm-one-time-cloud-cost is required")
    if args.retry_failed_hiwm_once:
        attempt_mode = "retry_failed_hiwm"
    elif args.validate_hiwm_adapter_once:
        attempt_mode = "validate_hiwm_adapter"
    elif args.validate_json_envelope_once:
        attempt_mode = "validate_json_envelope"
    elif args.validate_schema_retry_once:
        attempt_mode = "validate_schema_retry"
    else:
        attempt_mode = "full"
    existing_report: dict[str, Any] | None = None
    if MARKER_PATH.exists():
        existing_report = json.loads(MARKER_PATH.read_text(encoding="utf-8"))
        failed_hiwm = (
            existing_report.get("components", {}).get("hiwm", {}).get("status")
            == "failed"
        )
        retry_used = bool(existing_report.get("hiwm_retry_used"))
        adapter_used = bool(existing_report.get("hiwm_adapter_validation_used"))
        envelope_used = bool(existing_report.get("hiwm_json_envelope_validation_used"))
        schema_retry_used = bool(existing_report.get("hiwm_schema_retry_validation_used"))
        retry_allowed = args.retry_failed_hiwm_once and failed_hiwm and not retry_used
        adapter_allowed = (
            args.validate_hiwm_adapter_once
            and failed_hiwm
            and retry_used
            and not adapter_used
        )
        envelope_allowed = (
            args.validate_json_envelope_once
            and failed_hiwm
            and adapter_used
            and not envelope_used
        )
        schema_retry_allowed = (
            args.validate_schema_retry_once
            and failed_hiwm
            and envelope_used
            and not schema_retry_used
        )
        if not (
            retry_allowed
            or adapter_allowed
            or envelope_allowed
            or schema_retry_allowed
        ):
            print(json.dumps({"status": "skipped", "reason": "already_attempted"}))
            return 2
    elif (
        args.retry_failed_hiwm_once
        or args.validate_hiwm_adapter_once
        or args.validate_json_envelope_once
        or args.validate_schema_retry_once
    ):
        parser.error("there is no failed HIWM marker to retry")
    elif args.asr_wav is None:
        parser.error("--asr-wav is required for the initial three-component check")

    try:
        _claim_attempt(attempt_mode)
    except FileExistsError:
        print(
            json.dumps(
                {
                    "status": "skipped",
                    "reason": "already_attempted",
                    "mode": attempt_mode,
                }
            )
        )
        return 2

    # The durable O_EXCL attempt lock above must exist before this function can
    # read the credential or any provider SDK can be invoked.
    logging.getLogger("dashscope").setLevel(logging.WARNING)
    key = _load_key()
    MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = existing_report or {
        "attempted_at": time.time(),
        "privacy": "no_audio_text_or_credentials_persisted",
        "components": {},
    }
    exit_code = 0
    if args.retry_failed_hiwm_once:
        report["hiwm_retry_used"] = True
        report["hiwm_retry_attempted_at"] = time.time()
        operations = (("hiwm", lambda: _run_hiwm(key)),)
    elif args.validate_hiwm_adapter_once:
        report["hiwm_adapter_validation_used"] = True
        report["hiwm_adapter_validation_attempted_at"] = time.time()
        operations = (("hiwm", lambda: _run_hiwm(key)),)
    elif args.validate_json_envelope_once:
        report["hiwm_json_envelope_validation_used"] = True
        report["hiwm_json_envelope_validation_attempted_at"] = time.time()
        operations = (("hiwm", lambda: _run_hiwm(key)),)
    elif args.validate_schema_retry_once:
        report["hiwm_schema_retry_validation_used"] = True
        report["hiwm_schema_retry_validation_attempted_at"] = time.time()
        operations = (("hiwm", lambda: _run_hiwm(key)),)
    else:
        operations = (
            ("hiwm", lambda: _run_hiwm(key)),
            ("tts", lambda: _run_tts(key)),
            ("asr", lambda: _run_asr(key, args.asr_wav)),
        )
    for name, operation in operations:
        try:
            report["components"][name] = operation()
        except Exception as exc:  # Provider messages are deliberately not persisted.
            report["components"][name] = {
                "status": "failed",
                "error_type": type(exc).__name__,
            }
            safe_issues = getattr(exc, "issues", ())
            if safe_issues:
                report["components"][name]["validation_issues"] = list(safe_issues)
            exit_code = 1
    _write_private_report(report)
    print(json.dumps(report, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
