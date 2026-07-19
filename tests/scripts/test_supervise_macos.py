from __future__ import annotations

import importlib.util
import json
import stat
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "supervise_macos.py"
SPEC = importlib.util.spec_from_file_location("supervise_macos_under_test", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
supervisor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(supervisor)


class _Response:
    def __init__(self, *, status: int, body: bytes):
        self.status = status
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


class _Opener:
    def __init__(self, response: _Response):
        self.response = response
        self.calls = []

    def open(self, url: str, *, timeout: int):
        self.calls.append((url, timeout))
        return self.response


def test_probe_accepts_only_exact_local_health_contract(monkeypatch):
    healthy = _Opener(
        _Response(status=200, body=json.dumps({"status": "ok"}).encode())
    )
    monkeypatch.setattr(
        supervisor.urllib.request,
        "build_opener",
        lambda *_handlers: healthy,
    )

    assert supervisor._probe(supervisor.HEALTH_URLS[0]) == (True, 200)
    assert healthy.calls == [(supervisor.HEALTH_URLS[0], 5)]

    unhealthy = _Opener(
        _Response(status=200, body=json.dumps({"status": "starting"}).encode())
    )
    monkeypatch.setattr(
        supervisor.urllib.request,
        "build_opener",
        lambda *_handlers: unhealthy,
    )
    assert supervisor._probe(supervisor.HEALTH_URLS[1]) == (False, 200)

    invalid_json = _Opener(_Response(status=200, body=b"not-json"))
    monkeypatch.setattr(
        supervisor.urllib.request,
        "build_opener",
        lambda *_handlers: invalid_json,
    )
    assert supervisor._probe(supervisor.HEALTH_URLS[0]) == (False, 0)


def test_watchdog_policy_constants_are_bounded_and_consistent():
    assert supervisor.HEALTH_URLS == (
        "http://127.0.0.1:8283/liveness",
        "http://127.0.0.1:8283/readiness",
    )
    assert supervisor.CHECK_INTERVAL_SECONDS == 60
    assert supervisor.STARTUP_GRACE_SECONDS == 180
    assert supervisor.FAILURE_THRESHOLD == 3
    assert supervisor.RESTART_WINDOW_SECONDS == 30 * 60
    assert supervisor.MAX_RESTARTS_PER_WINDOW == 5
    assert supervisor.COOLDOWN_SECONDS == 15 * 60
    assert supervisor.BACKOFF_SECONDS == (10, 20, 40, 60)
    assert tuple(sorted(supervisor.BACKOFF_SECONDS)) == supervisor.BACKOFF_SECONDS


def test_safe_log_is_private_rotated_and_drops_unapproved_fields(tmp_path):
    path = tmp_path / "watchdog.log"
    path.write_bytes(b"x" * 1_000_001)

    log = supervisor.SafeLog(path)
    log.write(
        event="health_failed",
        live_code=0,
        ready_code=0,
        failure_streak=3,
        forbidden_payload="must-not-persist",
    )
    log.close()

    rotated = path.with_suffix(".log.1")
    assert rotated.exists()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(rotated.stat().st_mode) == 0o600

    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["event"] == "health_failed"
    assert record["failure_streak"] == 3
    assert "forbidden_payload" not in record
    assert "must-not-persist" not in path.read_text(encoding="utf-8")
