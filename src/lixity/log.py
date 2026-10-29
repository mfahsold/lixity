"""Central logging for Lixity: one logger tree, one line format, one policy.

- Modules log through :func:`get_logger` under the ``lixity`` tree.
- The CLI keeps stdout as its result channel (tables, JSON, reports); every
  diagnostic goes through logging to stderr.
- The managed service captures the child's stderr into its log file, so the
  logging layer needs no file handler of its own; :func:`rotate_service_log`
  bounds that file at service start.
- Request logs never contain query strings: context tokens and selectors
  travel there. That discipline lives in the call sites and is covered by
  the server tests.
- The level comes from an explicit argument, else ``LIXITY_LOG_LEVEL``, else
  DEBUG while ``LIXITY_DEBUG``/``--debug`` is active, else INFO.
- ``LIXITY_SPEECH_LOG_LEVEL=DEBUG`` separately enables speech diagnostics,
  without enabling debug logging for the rest of the application.

Individual call sites must avoid logging manuscript text or credentials. Other
stderr output and existing debug errors can contain contextual details.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from secrets import token_hex
from threading import RLock
from typing import IO, Any

NAME = "lixity"
FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S UTC"
_TRUE_VALUES = {"1", "true", "yes", "on"}
_SPEECH_DIAGNOSTIC_ID: ContextVar[str | None] = ContextVar("lixity_speech_diagnostic_id", default=None)
_CONFIGURE_LOCK = RLock()
_SPEECH_PREVIOUS_LEVEL: list[int] = []


def new_speech_diagnostic_id() -> str:
    """Create a random operational ID unrelated to project and job tokens."""
    return token_hex(8)


def speech_diagnostic_id() -> str | None:
    """Return the diagnostic ID for this context, if one has been entered."""
    return _SPEECH_DIAGNOSTIC_ID.get()


@contextmanager
def speech_diagnostic_scope(identifier: str | None = None) -> Iterator[str]:
    """Correlate nested speech work without leaking state across threads."""
    selected = identifier or speech_diagnostic_id() or new_speech_diagnostic_id()
    if len(selected) != 16 or any(char not in "0123456789abcdef" for char in selected):
        raise ValueError("Invalid speech diagnostic identifier")
    reset = _SPEECH_DIAGNOSTIC_ID.set(selected)
    try:
        yield selected
    finally:
        _SPEECH_DIAGNOSTIC_ID.reset(reset)


class _UtcFormatter(logging.Formatter):
    """Timestamps stay in UTC so service logs line up across machines."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return time.strftime(datefmt or DATEFMT, time.gmtime(record.created))


class _StderrHandler(logging.StreamHandler[Any]):
    """Writes to whatever ``sys.stderr`` is at emit time.

    The service captures the process' stderr file descriptor and tests use
    ``redirect_stderr``; binding the stream once at import time would bypass
    both.
    """

    def __init__(self) -> None:
        super().__init__(sys.stderr)

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stderr
        super().emit(record)


def _requested_level() -> int:
    name = os.environ.get("LIXITY_LOG_LEVEL", "").strip().upper()
    if name:
        value = getattr(logging, name, None)
        if isinstance(value, int):
            return value
    if os.environ.get("LIXITY_DEBUG", "").strip().lower() in _TRUE_VALUES:
        return logging.DEBUG
    return logging.INFO


def resolve_level(level: int | str | None = None) -> int:
    """Resolve the effective level for the ``lixity`` tree."""
    if isinstance(level, str):
        value = getattr(logging, level.strip().upper(), None)
        return value if isinstance(value, int) else logging.INFO
    if isinstance(level, int):
        return level
    return _requested_level()


def configure(
    *, level: int | str | None = None, stream: IO[str] | None = None, force: bool = False
) -> logging.Logger:
    """Configure the ``lixity`` logger tree once and return its root logger."""
    with _CONFIGURE_LOCK:
        logger = logging.getLogger(NAME)
        logger.propagate = False
        if force:
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
        if not logger.handlers:
            stream_handler: logging.Handler = (
                _StderrHandler() if stream is None else logging.StreamHandler(stream)
            )
            stream_handler.setFormatter(_UtcFormatter(FORMAT, datefmt=DATEFMT))
            logger.addHandler(stream_handler)
        logger.setLevel(resolve_level(level))
        speech = logging.getLogger(f"{NAME}.speech")
        if os.environ.get("LIXITY_SPEECH_LOG_LEVEL", "").strip().upper() == "DEBUG":
            if not _SPEECH_PREVIOUS_LEVEL:
                _SPEECH_PREVIOUS_LEVEL.append(speech.level)
            speech.setLevel(logging.DEBUG)
        elif _SPEECH_PREVIOUS_LEVEL:
            speech.setLevel(_SPEECH_PREVIOUS_LEVEL.pop())
        return logger


def get_logger(suffix: str | None = None) -> logging.Logger:
    """Return a logger below ``lixity``, configuring the tree on first use."""
    if not logging.getLogger(NAME).handlers:
        configure()
    return logging.getLogger(NAME if not suffix else f"{NAME}.{suffix}")


def rotate_service_log(path: Path, *, max_bytes: int = 2_000_000, backups: int = 3) -> list[Path]:
    """Rotate an oversized captured service log at service start.

    The service appends the child's output to ``path``; rotating here (and
    not from a logging handler) keeps one writer per file. Returns the
    rotated files for tests and diagnostics.
    """
    try:
        if path.stat().st_size <= max_bytes:
            return []
    except OSError:
        return []
    moved: list[Path] = []
    oldest = path.with_name(f"{path.name}.{backups}")
    if oldest.exists():
        oldest.unlink()
    for index in range(backups - 1, 0, -1):
        source = path.with_name(f"{path.name}.{index}")
        if source.exists():
            source.rename(path.with_name(f"{path.name}.{index + 1}"))
            moved.append(path.with_name(f"{path.name}.{index + 1}"))
    path.rename(path.with_name(f"{path.name}.1"))
    moved.append(path.with_name(f"{path.name}.1"))
    return moved
