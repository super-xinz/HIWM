import sys

from loguru import logger
from service.service_data_models.logger_config_data import LoggerConfigData


def config_loggers(in_logger_config: LoggerConfigData):
    logger.remove()
    sink_defaults = {
        "level": in_logger_config.log_level,
        "backtrace": False,
        "diagnose": False,
    }
    logger.add(sys.stdout, **sink_defaults)
    logger.add(
        "logs/log.log",
        rotation="10 MB",
        retention="14 days",
        compression="gz",
        encoding="utf-8",
        enqueue=True,
        **sink_defaults,
    )
    logger.info("Set log level to {}", in_logger_config.log_level)
