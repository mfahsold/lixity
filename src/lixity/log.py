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

Log files and runtime records never contain manuscript text.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import IO, Any

NAME = "lixity"
FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S UTC"
_TRUE_VALUES = {"1", "true", "yes", "on"}


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
