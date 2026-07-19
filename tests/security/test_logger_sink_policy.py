from __future__ import annotations

import sys

from service.service_data_models.logger_config_data import LoggerConfigData
from service.service_utils import logger_utils


class _RecordingLogger:
    def __init__(self):
        self.remove_calls = 0
        self.add_calls = []
        self.info_calls = []

    def remove(self):
        self.remove_calls += 1

    def add(self, sink, **kwargs):
        self.add_calls.append((sink, kwargs))
        return len(self.add_calls)

    def info(self, message, *args):
        self.info_calls.append((message, args))


def test_configured_level_and_privacy_defaults_apply_to_all_sinks(monkeypatch):
    recording_logger = _RecordingLogger()
    monkeypatch.setattr(logger_utils, "logger", recording_logger)

    logger_utils.config_loggers(LoggerConfigData(log_level="WARNING"))

    assert recording_logger.remove_calls == 1
    assert len(recording_logger.add_calls) == 2

    stdout_sink, stdout_options = recording_logger.add_calls[0]
    file_sink, file_options = recording_logger.add_calls[1]
    assert stdout_sink is sys.stdout
    assert file_sink == "logs/log.log"

    for options in (stdout_options, file_options):
        assert options["level"] == "WARNING"
        assert options["backtrace"] is False
        assert options["diagnose"] is False

    assert file_options["rotation"] == "10 MB"
    assert file_options["retention"] == "14 days"
    assert file_options["compression"] == "gz"
    assert file_options["encoding"] == "utf-8"
    assert file_options["enqueue"] is True
