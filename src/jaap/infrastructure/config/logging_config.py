"""Centralized logging configuration.

`configure_logging()` is called exactly once, at the composition root
(the future CLI entry point), and sets up the root logger with two
handlers: human-readable text to the console (for local development) and
structured JSON to a rotating log file (for anything that later wants to
parse or aggregate logs, e.g. Phase 5 monitoring).

This lives in infrastructure/config/, not utils/: it performs real I/O
(creating directories, opening file handles) and depends on Settings,
both of which are disqualifying for utils/ per that package's own rule
(dependency-free, no I/O). It was initially scaffolded under utils/ in
Milestone 1 before either constraint applied; moved here once this
module's actual responsibilities made the mismatch concrete.

Everywhere else in the codebase just does the standard:
    logger = logging.getLogger(__name__)
No module should configure its own handlers or call basicConfig() itself.
"""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler

from jaap.infrastructure.config.settings import Settings

_CONSOLE_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_CONSOLE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_LOG_FILE_NAME = "jaap.log"
_MAX_LOG_FILE_BYTES = 5_000_000  # 5 MB per file before rotating
_BACKUP_COUNT = 3  # keep this many rotated files in addition to the active one


class _JsonFormatter(logging.Formatter):
    """Formats each log record as a single-line JSON object.

    Kept intentionally minimal (no third-party JSON-logging dependency)
    -- just the fields worth having for a first pass at machine-readable
    logs: timestamp, level, logger name, message, and exception info when
    present.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, str] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(settings: Settings) -> None:
    """Configure the root logger with console (text) and file (JSON) handlers.

    Safe to call more than once (e.g. across multiple tests in the same
    process): any handlers from a previous call are removed first, so
    calling this repeatedly does not stack duplicate handlers or write
    each line multiple times.

    Args:
        settings: The application's Settings, providing the log level and
            the directory to write the JSON log file into.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT, datefmt=_CONSOLE_DATE_FORMAT))
    root_logger.addHandler(console_handler)

    settings.log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        settings.log_dir / _LOG_FILE_NAME,
        maxBytes=_MAX_LOG_FILE_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(_JsonFormatter())
    root_logger.addHandler(file_handler)
