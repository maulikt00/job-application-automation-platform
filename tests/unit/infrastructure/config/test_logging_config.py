"""Tests for configure_logging(): the console (text) + file (JSON)
handler setup, using tmp_path so no real log directory is touched.
"""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from jaap.infrastructure.config.logging_config import _JsonFormatter, configure_logging
from jaap.infrastructure.config.settings import Settings


@pytest.fixture(autouse=True)
def _reset_root_logger_handlers() -> None:
    """Ensure each test starts and ends with a clean root logger, so
    handlers configured by one test never leak into another."""
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    for handler in original_handlers:
        root.addHandler(handler)
    root.setLevel(original_level)


def _make_settings(tmp_path: Path, **overrides: object) -> Settings:
    kwargs: dict[str, object] = {"log_dir": tmp_path / "logs"}
    kwargs.update(overrides)
    return Settings(_env_file=None, **kwargs)  # type: ignore[arg-type]


def test_configure_logging_attaches_console_and_file_handlers(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)

    configure_logging(settings)

    root = logging.getLogger()
    stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)
                        and not isinstance(h, RotatingFileHandler)]
    file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]

    assert len(stream_handlers) == 1
    assert len(file_handlers) == 1


def test_configure_logging_creates_the_log_directory(tmp_path: Path) -> None:
    log_dir = tmp_path / "nested" / "logs"
    settings = _make_settings(tmp_path, log_dir=log_dir)

    configure_logging(settings)

    assert log_dir.is_dir()
    assert (log_dir / "jaap.log").exists()


def test_configure_logging_is_idempotent(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)

    configure_logging(settings)
    configure_logging(settings)

    root = logging.getLogger()
    file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
    assert len(file_handlers) == 1  # not 2 -- the second call must not stack a duplicate


def test_root_logger_level_matches_settings(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path, log_level="WARNING")

    configure_logging(settings)

    assert logging.getLogger().level == logging.WARNING


def test_log_file_contains_valid_json_lines(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    configure_logging(settings)

    logger = logging.getLogger("jaap.test")
    logger.info("hello from a test")

    log_file = settings.log_dir / "jaap.log"
    lines = [line for line in log_file.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["level"] == "INFO"
    assert record["logger"] == "jaap.test"
    assert record["message"] == "hello from a test"
    assert "timestamp" in record


def test_json_formatter_includes_exception_info_when_present() -> None:
    formatter = _JsonFormatter()
    logger = logging.getLogger("jaap.test.exceptions")

    try:
        raise ValueError("boom")
    except ValueError:
        record = logger.makeRecord(
            logger.name, logging.ERROR, __file__, 0, "something failed", (), True
        )
        # makeRecord's exc_info arg only accepts a bool via logger.error();
        # build the record directly with real exc_info for this unit test.
        import sys

        record.exc_info = sys.exc_info()

    formatted = json.loads(formatter.format(record))
    assert "exception" in formatted
    assert "ValueError: boom" in formatted["exception"]
