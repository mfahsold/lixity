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

import orjson

NAME = "lixity"
FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S UTC"
_TRUE_VALUES = {"1", "true", "yes", "on"}
_DIAGNOSTIC_ID: ContextVar[str | None] = ContextVar("lixity_diagnostic_id", default=None)
_SPEECH_DIAGNOSTIC_ID: ContextVar[str | None] = ContextVar("lixity_speech_diagnostic_id", default=None)
_CONFIGURE_LOCK = RLock()
_SPEECH_PREVIOUS_LEVEL: list[int] = []


def new_diagnostic_id() -> str:
    """Create a random operational correlation ID unrelated to project tokens."""
    return token_hex(8)


new_speech_diagnostic_id = new_diagnostic_id


def diagnostic_id() -> str | None:
    """Return the active diagnostic ID for this context, if one has been entered."""
    return _DIAGNOSTIC_ID.get() or _SPEECH_DIAGNOSTIC_ID.get()


def speech_diagnostic_id() -> str | None:
    """Return the diagnostic ID for this context, if one has been entered."""
    return diagnostic_id()


@contextmanager
def diagnostic_scope(identifier: str | None = None) -> Iterator[str]:
    """Correlate nested workflow stages across pipeline, speech, and server without leaking state."""
    selected = identifier or diagnostic_id() or new_diagnostic_id()
    if len(selected) != 16 or any(char not in "0123456789abcdef" for char in selected):
        raise ValueError("Invalid diagnostic identifier")
    reset_general = _DIAGNOSTIC_ID.set(selected)
    reset_speech = _SPEECH_DIAGNOSTIC_ID.set(selected)
    try:
        yield selected
    finally:
        _DIAGNOSTIC_ID.reset(reset_general)
        _SPEECH_DIAGNOSTIC_ID.reset(reset_speech)


@contextmanager
def speech_diagnostic_scope(identifier: str | None = None) -> Iterator[str]:
    """Correlate nested speech work without leaking state across threads."""
    with diagnostic_scope(identifier) as scope_id:
        yield scope_id


def format_event(event: str, **fields: Any) -> str:
    """Format structured key-value diagnostic event according to Lixity standards.

    Fields are formatted as key=value without leaking private manuscript bytes.
    """
    pairs: list[str] = [f"event={event}"]
    diag_id = fields.pop("id", None) or diagnostic_id()
    if diag_id:
        pairs.append(f"id={diag_id}")
    for key, value in sorted(fields.items()):
        if value is None:
            continue
        if isinstance(value, bool):
            pairs.append(f"{key}={'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            pairs.append(f"{key}={value}")
        else:
            s_val = str(value)
            if " " in s_val or "=" in s_val or '"' in s_val:
                s_val = '"' + s_val.replace('"', '\\"') + '"'
            pairs.append(f"{key}={s_val}")
    return " ".join(pairs)


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Emit a structured diagnostic event on the given logger."""
    if logger.isEnabledFor(level):
        logger.log(level, format_event(event, **fields))


def is_json_logging() -> bool:
    """Return whether structured JSON logging format is requested."""
    fmt = os.environ.get("LIXITY_LOG_FORMAT", "").strip().lower()
    return fmt == "json" or os.environ.get("LIXITY_LOG_JSON", "").strip().lower() in _TRUE_VALUES


class _JsonFormatter(logging.Formatter):
    """Emit one-line NDJSON records for structured machine observability."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created))
        msg = record.getMessage()
        entry: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": msg,
        }
        diag_id = getattr(record, "diagnostic_id", None) or diagnostic_id()
        if diag_id:
            entry["id"] = diag_id
        if msg.startswith("event="):
            for part in msg.split(" "):
                if "=" in part:
                    k, v = part.split("=", 1)
                    v_clean = v.strip('"')
                    if k == "event":
                        entry["event"] = v_clean
                    elif v_clean == "true":
                        entry[k] = True
                    elif v_clean == "false":
                        entry[k] = False
                    elif v_clean.isdigit():
                        entry[k] = int(v_clean)
                    else:
                        try:
                            entry[k] = float(v_clean)
                        except ValueError:
                            entry[k] = v_clean
        if record.exc_info and record.exc_text:
            entry["exception"] = record.exc_text
        return orjson.dumps(entry).decode("utf-8")


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
    *, level: int | str | None = None, stream: IO[str] | None = None, force: bool = False,
    json_format: bool | None = None,
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
            use_json = json_format if json_format is not None else is_json_logging()
            formatter: logging.Formatter = _JsonFormatter() if use_json else _UtcFormatter(FORMAT, datefmt=DATEFMT)
            stream_handler.setFormatter(formatter)
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
