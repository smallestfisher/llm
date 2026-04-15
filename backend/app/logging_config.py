from __future__ import annotations

import logging
import os
import sys
from typing import Any

from loguru import logger


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_JSON = os.getenv("LOG_JSON", "0") == "1"
LOG_BACKTRACE = os.getenv("LOG_BACKTRACE", "0") == "1"
LOG_DIAGNOSE = os.getenv("LOG_DIAGNOSE", "0") == "1"


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except Exception:
            level = record.levelno

        frame = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        extra: dict[str, Any] = {"logger_name": record.name}
        if record.threadName:
            extra["thread_name"] = record.threadName
        if record.processName:
            extra["process_name"] = record.processName

        logger.bind(**extra).opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logging() -> None:
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(logging.NOTSET)

    for name in list(logging.root.manager.loggerDict.keys()):
        target = logging.getLogger(name)
        target.handlers = []
        target.propagate = True

    logger.remove()
    logger.add(
        sys.stderr,
        level=LOG_LEVEL,
        serialize=LOG_JSON,
        backtrace=LOG_BACKTRACE,
        diagnose=LOG_DIAGNOSE,
        enqueue=True,
        colorize=not LOG_JSON,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[logger_name]}</cyan> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ) if not LOG_JSON else None,
    )


def get_logger(name: str):
    return logger.bind(logger_name=name)
