"""Bounded, self-cleaning logging for aihsm.

Two rules govern everything in this module:

1. A secret value must never be written to the log. Callers pass only rule
   names, vault entry names, action names, error type names, and counts.
2. Logging must never break the tool. Every public function here is
   best-effort: if the log directory can't be created, or a write or
   rotation fails, the failure is silently swallowed.

Stdlib only: logging, logging.handlers, os, pathlib.
"""

import logging
import logging.handlers
import os
from pathlib import Path

DEFAULT_MAX_BYTES = 1_000_000
DEFAULT_BACKUPS = 4

_LOGGER_NAME = "aihsm"
_NO_LOG_ENV = "SECRET_HARNESS_NO_LOG"

_configured = False


def default_log_path():
    # type: () -> Path
    return Path.home() / ".claude" / "aihsm" / "logs" / "aihsm.log"


def _clear_handlers(logger):
    for handler in list(logger.handlers):
        try:
            handler.close()
        except Exception:
            pass
        try:
            logger.removeHandler(handler)
        except Exception:
            pass


def get_logger(log_path=None, max_bytes=DEFAULT_MAX_BYTES, backups=DEFAULT_BACKUPS, force=False):
    # type: (..., int, int, bool) -> logging.Logger
    """Return the shared aihsm logger, configured exactly once.

    Repeat calls with force=False return the already-configured logger
    without touching its handlers. Pass force=True (tests only, normally) to
    drop existing handlers and reconfigure from the given arguments.
    """
    global _configured

    logger = logging.getLogger(_LOGGER_NAME)

    if _configured and not force:
        return logger

    _clear_handlers(logger)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if os.environ.get(_NO_LOG_ENV):
        logger.addHandler(logging.NullHandler())
        _configured = True
        return logger

    try:
        path = Path(log_path) if log_path is not None else default_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            str(path),
            maxBytes=max_bytes,
            backupCount=backups,
            encoding="utf-8",
            delay=True,
        )
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    except Exception:
        _clear_handlers(logger)
        logger.addHandler(logging.NullHandler())

    _configured = True
    return logger


def info(message):
    # type: (str) -> None
    try:
        get_logger().log(logging.INFO, message)
    except Exception:
        pass


def error(message):
    # type: (str) -> None
    try:
        get_logger().log(logging.ERROR, message)
    except Exception:
        pass
