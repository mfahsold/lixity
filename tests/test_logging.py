"""Central logging behaviour: levels, format, idempotence and rotation."""

from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timezone
from unittest import mock

from lixity import log


def test_level_resolution_prefers_argument_then_env_then_debug_flag():
    with mock.patch.dict(
        os.environ, {"LIXITY_LOG_LEVEL": "warning", "LIXITY_DEBUG": "1"}, clear=False
    ):
        assert log.resolve_level() == logging.WARNING
        assert log.resolve_level("error") == logging.ERROR
        assert log.resolve_level(logging.CRITICAL) == logging.CRITICAL
    with mock.patch.dict(os.environ, {"LIXITY_DEBUG": "1"}, clear=False):
        os.environ.pop("LIXITY_LOG_LEVEL", None)
        assert log.resolve_level() == logging.DEBUG
    with mock.patch.dict(os.environ, {"LIXITY_LOG_LEVEL": "not-a-level"}, clear=False):
        os.environ.pop("LIXITY_DEBUG", None)
        assert log.resolve_level() == logging.INFO


def test_configure_is_idempotent_and_writes_utc_lines():
    stream = io.StringIO()
    first = log.configure(level="DEBUG", stream=stream, force=True)
    second = log.configure(level="DEBUG", stream=stream)
    assert first is second
    assert len(first.handlers) == 1
    log.get_logger("server").debug("synthetic detail")
    line = stream.getvalue().strip()
    assert line.endswith(" DEBUG lixity.server synthetic detail"), line
    parsed = datetime.strptime(line.split(" DEBUG ", 1)[0], log.DATEFMT).replace(
        tzinfo=timezone.utc
    )
    assert parsed.year >= 2026


def test_get_logger_configures_the_tree_on_first_use():
    log.configure(force=True)
    logger = log.get_logger("service")
    assert logger.name == "lixity.service"
    assert logger.getEffectiveLevel() == log.resolve_level()


def test_rotation_bounds_the_captured_service_log(tmp_path):
    path = tmp_path / "service-8765.log"
    path.write_text("x" * 10, encoding="utf-8")
    moved = log.rotate_service_log(path, max_bytes=5, backups=2)
    assert moved == [path.with_name("service-8765.log.1")]
    assert path.with_name("service-8765.log.1").read_text(encoding="utf-8") == "x" * 10
    path.write_text("y" * 10, encoding="utf-8")
    log.rotate_service_log(path, max_bytes=5, backups=2)
    assert path.with_name("service-8765.log.1").read_text(encoding="utf-8") == "y" * 10
    assert path.with_name("service-8765.log.2").read_text(encoding="utf-8") == "x" * 10
    path.write_text("z" * 10, encoding="utf-8")
    log.rotate_service_log(path, max_bytes=5, backups=2)
    assert path.with_name("service-8765.log.2").read_text(encoding="utf-8") == "y" * 10
    assert not path.with_name("service-8765.log.3").exists()
    assert log.rotate_service_log(path, max_bytes=1000, backups=2) == []


def test_rotation_ignores_a_missing_log_file(tmp_path):
    assert log.rotate_service_log(tmp_path / "absent.log") == []
