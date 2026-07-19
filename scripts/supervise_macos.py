#!/usr/bin/env python3
"""Local-only supervisor for an unattended HIWM demo macOS run."""

from __future__ import annotations

import collections
import fcntl
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "logs" / "watchdog.log"
LOCK_PATH = ROOT / "temp" / "hiwm-supervisor.lock"
HEALTH_URLS = (
    "http://127.0.0.1:8283/liveness",
    "http://127.0.0.1:8283/readiness",
)
CHECK_INTERVAL_SECONDS = 60
STARTUP_GRACE_SECONDS = 180
FAILURE_THRESHOLD = 3
RESTART_WINDOW_SECONDS = 30 * 60
MAX_RESTARTS_PER_WINDOW = 5
COOLDOWN_SECONDS = 15 * 60
BACKOFF_SECONDS = (10, 20, 40, 60)


class SafeLog:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > 1_000_000:
            rotated = path.with_suffix(path.suffix + ".1")
            os.replace(path, rotated)
            os.chmod(rotated, 0o600)
        self._file = path.open("a", encoding="utf-8")
        os.chmod(path, 0o600)

    def write(self, *, event: str, **fields: object) -> None:
        allowed = {
            "pid",
            "live_code",
            "ready_code",
            "failure_streak",
            "exit_code",
            "backoff_seconds",
            "cooldown_seconds",
            "restart_count",
        }
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
        }
        record.update({key: value for key, value in fields.items() if key in allowed})
        self._file.write(json.dumps(record, separators=(",", ":")) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def _probe(url: str) -> tuple[bool, int]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=5) as response:
            code = int(response.status)
            body = json.loads(response.read(256).decode("utf-8"))
            return code == 200 and body == {"status": "ok"}, code
    except Exception:
        return False, 0


def _start_child(log: SafeLog) -> subprocess.Popen[bytes]:
    child = subprocess.Popen(
        ["/bin/bash", "scripts/start_macos.sh"],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    log.write(event="child_started", pid=child.pid)
    return child


def _stop_child(child: subprocess.Popen[bytes], log: SafeLog) -> None:
    if child.poll() is not None:
        return
    log.write(event="child_stopping", pid=child.pid)
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        child.wait(timeout=20)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait(timeout=5)
        log.write(event="child_killed", pid=child.pid)


def main() -> int:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_file = LOCK_PATH.open("a+")
    os.chmod(LOCK_PATH, 0o600)
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 2

    log = SafeLog(LOG_PATH)
    stop_event = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    restart_times: collections.deque[float] = collections.deque()
    restart_index = 0
    child = _start_child(log)
    child_started_at = time.monotonic()
    failure_streak = 0
    try:
        while not stop_event.wait(CHECK_INTERVAL_SECONDS):
            now = time.monotonic()
            if child.poll() is not None:
                log.write(event="child_exited", exit_code=child.returncode)
                needs_restart = True
            else:
                live_ok, live_code = _probe(HEALTH_URLS[0])
                ready_ok, ready_code = _probe(HEALTH_URLS[1])
                if live_ok and ready_ok:
                    log.write(
                        event="health_ok",
                        live_code=live_code,
                        ready_code=ready_code,
                        failure_streak=failure_streak,
                    )
                    if failure_streak:
                        log.write(
                            event="health_recovered",
                            live_code=live_code,
                            ready_code=ready_code,
                            failure_streak=failure_streak,
                        )
                    failure_streak = 0
                    if now - child_started_at >= RESTART_WINDOW_SECONDS:
                        restart_index = 0
                    needs_restart = False
                elif now - child_started_at < STARTUP_GRACE_SECONDS:
                    log.write(
                        event="startup_wait",
                        live_code=live_code,
                        ready_code=ready_code,
                    )
                    needs_restart = False
                else:
                    failure_streak += 1
                    log.write(
                        event="health_failed",
                        live_code=live_code,
                        ready_code=ready_code,
                        failure_streak=failure_streak,
                    )
                    needs_restart = failure_streak >= FAILURE_THRESHOLD

            if not needs_restart:
                continue

            _stop_child(child, log)
            restart_times.append(now)
            while restart_times and now - restart_times[0] > RESTART_WINDOW_SECONDS:
                restart_times.popleft()
            if len(restart_times) >= MAX_RESTARTS_PER_WINDOW:
                log.write(
                    event="restart_cooldown",
                    restart_count=len(restart_times),
                    cooldown_seconds=COOLDOWN_SECONDS,
                )
                if stop_event.wait(COOLDOWN_SECONDS):
                    break
                restart_times.clear()
                restart_index = 0
            else:
                backoff = BACKOFF_SECONDS[min(restart_index, len(BACKOFF_SECONDS) - 1)]
                restart_index += 1
                log.write(event="restart_backoff", backoff_seconds=backoff)
                if stop_event.wait(backoff):
                    break

            child = _start_child(log)
            child_started_at = time.monotonic()
            failure_streak = 0
    finally:
        _stop_child(child, log)
        log.write(event="supervisor_stopped")
        log.close()
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
