"""Tests for the logging setup (console + rotating file)."""

import logging

import pytest

from backend.config import BACKEND_DIR, Settings
from backend.logging_config import configure_logging


@pytest.fixture(autouse=True)
def restore_logging():
    """Leave global logging as we found it for the rest of the suite."""
    root = logging.getLogger()
    saved = root.handlers[:], root.level
    yield
    for handler in root.handlers:
        if handler not in saved[0]:
            handler.close()
    root.handlers, root.level = saved
    logging.getLogger("backend").setLevel(logging.NOTSET)


def _flush():
    for handler in logging.getLogger().handlers:
        handler.flush()


def test_writes_backend_records_to_file(tmp_path):
    log_file = tmp_path / "nested" / "solon.log"
    configure_logging("INFO", log_file=log_file)

    logging.getLogger("backend.workflows").info("batch planned")
    logging.getLogger("backend.workflows").debug("too detailed")
    logging.getLogger("httpx").info("HTTP request noise")
    _flush()

    text = log_file.read_text()
    assert "batch planned" in text
    assert "backend.workflows" in text
    assert "too detailed" not in text
    assert "HTTP request noise" not in text


def test_rotates_when_file_is_full(tmp_path):
    log_file = tmp_path / "solon.log"
    configure_logging("INFO", log_file=log_file, max_bytes=500, backup_count=2)

    for i in range(50):
        logging.getLogger("backend").info("line %d %s", i, "x" * 40)
    _flush()

    assert log_file.exists()
    assert (tmp_path / "solon.log.1").exists()
    assert (tmp_path / "solon.log.2").exists()
    assert not (tmp_path / "solon.log.3").exists()


def test_console_only_when_no_file(tmp_path):
    configure_logging("INFO", log_file=None)
    handler_types = {type(h).__name__ for h in logging.getLogger().handlers}
    assert "RotatingFileHandler" not in handler_types


def test_log_file_path_resolves_against_backend_dir():
    assert Settings(_env_file=None).log_file_path == BACKEND_DIR / "logs/solon.log"
    assert Settings(_env_file=None, log_file="").log_file_path is None
