from __future__ import annotations

import json
import stat
import sys
import threading

import pytest

from scripts import smoke_cloud


def test_smoke_report_is_owner_only_even_when_file_already_exists(tmp_path, monkeypatch):
    marker = tmp_path / "cloud-smoke.json"
    marker.write_text("old", encoding="utf-8")
    marker.chmod(0o644)
    monkeypatch.setattr(smoke_cloud, "MARKER_PATH", marker)

    report = {
        "privacy": "no_audio_text_or_credentials_persisted",
        "components": {"asr": {"status": "ok"}},
    }
    smoke_cloud._write_private_report(report)

    assert stat.S_IMODE(marker.stat().st_mode) == 0o600
    assert json.loads(marker.read_text(encoding="utf-8")) == report


def _configure_attempt_paths(tmp_path, monkeypatch):
    marker = tmp_path / "cloud-smoke.json"
    attempt_dir = tmp_path / "attempts"
    monkeypatch.setattr(smoke_cloud, "MARKER_PATH", marker)
    monkeypatch.setattr(smoke_cloud, "ATTEMPT_LOCK_DIR", attempt_dir)
    return marker, attempt_dir


def test_attempt_lock_is_owner_only_fsynced_and_one_shot(tmp_path, monkeypatch):
    _marker, attempt_dir = _configure_attempt_paths(tmp_path, monkeypatch)
    real_fsync = smoke_cloud.os.fsync
    fsync_calls = []

    def recording_fsync(descriptor):
        fsync_calls.append(descriptor)
        return real_fsync(descriptor)

    monkeypatch.setattr(smoke_cloud.os, "fsync", recording_fsync)

    lock_path = smoke_cloud._claim_attempt("full")

    assert lock_path == attempt_dir / "full.lock"
    assert stat.S_IMODE(attempt_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(lock_path.stat().st_mode) == 0o600
    assert json.loads(lock_path.read_text(encoding="utf-8"))["mode"] == "full"
    # One fsync persists the file contents and one persists the directory entry.
    assert len(fsync_calls) >= 2
    with pytest.raises(FileExistsError):
        smoke_cloud._claim_attempt("full")


def test_concurrent_claim_allows_exactly_one_process_stage(tmp_path, monkeypatch):
    _configure_attempt_paths(tmp_path, monkeypatch)
    barrier = threading.Barrier(8)
    outcomes = []

    def claim():
        barrier.wait()
        try:
            smoke_cloud._claim_attempt("retry_failed_hiwm")
        except FileExistsError:
            outcomes.append("blocked")
        else:
            outcomes.append("claimed")

    threads = [threading.Thread(target=claim) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert outcomes.count("claimed") == 1
    assert outcomes.count("blocked") == 7


def _failed_hiwm_report(**flags):
    return {
        "attempted_at": 1.0,
        "privacy": "no_audio_text_or_credentials_persisted",
        "components": {"hiwm": {"status": "failed", "error_type": "UnitTest"}},
        **flags,
    }


@pytest.mark.parametrize(
    ("attempt_mode", "arguments", "existing_report", "expected_operations"),
    [
        (
            "full",
            ["--asr-wav", "synthetic.wav"],
            None,
            ["key", "hiwm", "tts", "asr"],
        ),
        (
            "retry_failed_hiwm",
            ["--retry-failed-hiwm-once"],
            _failed_hiwm_report(),
            ["key", "hiwm"],
        ),
        (
            "validate_hiwm_adapter",
            ["--validate-hiwm-adapter-once"],
            _failed_hiwm_report(hiwm_retry_used=True),
            ["key", "hiwm"],
        ),
        (
            "validate_json_envelope",
            ["--validate-json-envelope-once"],
            _failed_hiwm_report(
                hiwm_retry_used=True,
                hiwm_adapter_validation_used=True,
            ),
            ["key", "hiwm"],
        ),
        (
            "validate_schema_retry",
            ["--validate-schema-retry-once"],
            _failed_hiwm_report(
                hiwm_retry_used=True,
                hiwm_adapter_validation_used=True,
                hiwm_json_envelope_validation_used=True,
            ),
            ["key", "hiwm"],
        ),
    ],
)
def test_every_mode_claims_durable_lock_before_key_and_cloud_operations(
    tmp_path,
    monkeypatch,
    attempt_mode,
    arguments,
    existing_report,
    expected_operations,
):
    marker, _attempt_dir = _configure_attempt_paths(tmp_path, monkeypatch)
    if existing_report is not None:
        marker.write_text(json.dumps(existing_report), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["smoke_cloud.py", "--confirm-one-time-cloud-cost", *arguments],
    )
    operations = []

    def assert_locked(stage):
        lock_path = smoke_cloud._attempt_lock_path(attempt_mode)
        assert lock_path.exists()
        assert stat.S_IMODE(lock_path.stat().st_mode) == 0o600
        operations.append(stage)

    def load_key():
        assert_locked("key")
        return "unit-test-key"

    def run_hiwm(_key):
        assert_locked("hiwm")
        return {"status": "ok", "model": "offline-fake"}

    def run_tts(_key):
        assert_locked("tts")
        return {"status": "ok", "audio_bytes": 1}

    def run_asr(_key, _wav_path):
        assert_locked("asr")
        return {"status": "ok", "recognized_nonempty": True}

    monkeypatch.setattr(smoke_cloud, "_load_key", load_key)
    monkeypatch.setattr(smoke_cloud, "_run_hiwm", run_hiwm)
    monkeypatch.setattr(smoke_cloud, "_run_tts", run_tts)
    monkeypatch.setattr(smoke_cloud, "_run_asr", run_asr)

    assert smoke_cloud.main() == 0
    assert operations == expected_operations


def test_key_error_keeps_lock_and_blocks_repeat_before_key_access(tmp_path, monkeypatch):
    _marker, _attempt_dir = _configure_attempt_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "smoke_cloud.py",
            "--confirm-one-time-cloud-cost",
            "--asr-wav",
            "synthetic.wav",
        ],
    )
    key_calls = 0

    def failing_load_key():
        nonlocal key_calls
        key_calls += 1
        assert smoke_cloud._attempt_lock_path("full").exists()
        raise RuntimeError("offline key failure")

    monkeypatch.setattr(smoke_cloud, "_load_key", failing_load_key)

    with pytest.raises(RuntimeError, match="offline key failure"):
        smoke_cloud.main()

    lock_path = smoke_cloud._attempt_lock_path("full")
    assert lock_path.exists()
    assert stat.S_IMODE(lock_path.stat().st_mode) == 0o600
    assert smoke_cloud.main() == 2
    assert key_calls == 1


def test_post_provider_crash_keeps_lock_and_blocks_any_second_cloud_call(
    tmp_path, monkeypatch
):
    marker, _attempt_dir = _configure_attempt_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "smoke_cloud.py",
            "--confirm-one-time-cloud-cost",
            "--asr-wav",
            "synthetic.wav",
        ],
    )
    key_calls = 0
    provider_calls = 0

    def load_key():
        nonlocal key_calls
        key_calls += 1
        assert smoke_cloud._attempt_lock_path("full").exists()
        return "unit-test-key"

    def crash_after_provider_entry(_key):
        nonlocal provider_calls
        provider_calls += 1
        assert smoke_cloud._attempt_lock_path("full").exists()
        raise SystemExit(99)

    monkeypatch.setattr(smoke_cloud, "_load_key", load_key)
    monkeypatch.setattr(smoke_cloud, "_run_hiwm", crash_after_provider_entry)

    with pytest.raises(SystemExit, match="99"):
        smoke_cloud.main()

    assert not marker.exists()
    assert smoke_cloud._attempt_lock_path("full").exists()
    assert smoke_cloud.main() == 2
    assert key_calls == 1
    assert provider_calls == 1
