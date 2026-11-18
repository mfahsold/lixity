"""On-demand native speech models owned by disposable spawned processes.

Only the child imports inference dependencies. Exiting that child releases its
allocator and device context rather than relying on Python garbage collection.
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import os
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from multiprocessing.connection import Connection, wait
from multiprocessing.process import BaseProcess
from typing import Any

from .log import get_logger
from .speech_worker import (
    MAX_BASE_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    SAMPLE_RATE,
    SYNTHESIS_TIMEOUT_SECONDS,
)

DEFAULT_IDLE_TIMEOUT_SECONDS = 300.0
MAX_IDLE_TIMEOUT_SECONDS = 86400.0
Renderer = Callable[[dict[str, Any]], bytes]
Loader = Callable[[], Renderer]


def _idle_timeout(value: float) -> float:
    if isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= MAX_IDLE_TIMEOUT_SECONDS:
        raise ValueError(f"Idle timeout must be between 0 and {MAX_IDLE_TIMEOUT_SECONDS:g} seconds")
    return value


def add_lifecycle_arguments(parser: argparse.ArgumentParser) -> None:
    """Expose the shared residency policy on each native worker entrypoint."""
    def parse(value: str) -> float:
        try:
            return _idle_timeout(float(value))
        except ValueError as exc:
            raise argparse.ArgumentTypeError(str(exc)) from exc
    parser.add_argument("--idle-timeout-seconds", type=parse, default=DEFAULT_IDLE_TIMEOUT_SECONDS,
                        help=f"Release model after completed synthesis is idle (0..{MAX_IDLE_TIMEOUT_SECONDS:g}; default {DEFAULT_IDLE_TIMEOUT_SECONDS:g})")


def _exit_with_parent() -> None:
    parent = multiprocessing.parent_process()
    if parent is not None:
        wait([parent.sentinel])
        os._exit(1)


def _child(connection: Connection, loader: Loader) -> None:
    """Spawn-safe entrypoint; the pipe carries bounded JSON and PCM bytes only."""
    threading.Thread(target=_exit_with_parent, daemon=True).start()
    try:
        renderer = loader()
        runtime = getattr(renderer, "runtime_info", None)
        metadata = {"runtime": asdict(runtime)} if is_dataclass(runtime) and not isinstance(runtime, type) else {}
        connection.send_bytes(json.dumps(metadata).encode())
        while True:
            request = json.loads(connection.recv_bytes(MAX_BASE_REQUEST_BYTES))
            data = renderer(request)
            from .speech import _read_pcm
            if not isinstance(data, bytes) or len(data) > MAX_RESPONSE_BYTES or _read_pcm(data)[0] != (1, 2, SAMPLE_RATE):
                raise ValueError("Invalid generated PCM audio")
            connection.send_bytes(data)
    except (EOFError, BrokenPipeError):
        pass
    except Exception:  # noqa: BLE001, S110 - parent reports a bounded failure without source data
        # Closing the pipe makes loading and synthesis failure explicit. A retry
        # always starts a fresh process, including after optional adapter errors.
        pass
    finally:
        connection.close()


class ModelLifecycle:
    """Serialize synthesis and reclaim a model after the last completed job."""

    def __init__(self, loader: Loader, *, idle_timeout_seconds: float = DEFAULT_IDLE_TIMEOUT_SECONDS) -> None:
        self._loader = loader
        self._idle_timeout = _idle_timeout(idle_timeout_seconds)
        self._operation = threading.Lock()
        self._state_lock = threading.Lock()
        self._state = "unloaded"
        self._active = False
        self._runtime: dict[str, Any] = {}
        self._process: BaseProcess | None = None
        self._connection: Connection | None = None
        self._timer: threading.Timer | None = None
        self._completed: float | None = None
        self._closed = False
        self._logger = get_logger("speech.worker")

    @property
    def child_pid(self) -> int | None:
        with self._state_lock:
            return self._process.pid if self._process is not None else None

    def health(self) -> dict[str, Any]:
        """Report residency without loading a model or extending its lifetime."""
        with self._state_lock:
            process = self._process
            if (process is not None and process.pid is not None and not process.is_alive()
                    and self._state in ("loaded", "loading")):
                self._state = "failed"
                self._runtime = {}
            return {"model_state": self._state, "active": self._active,
                    "idle_timeout_seconds": self._idle_timeout, **self._runtime}

    def _receive(self, limit: int) -> bytes:
        connection = self._connection
        if connection is None or not connection.poll(SYNTHESIS_TIMEOUT_SECONDS):
            raise RuntimeError("Native model process timed out")
        return connection.recv_bytes(limit)

    def _dispose(self, state: str) -> None:
        # The operation lock protects process ownership; health stays responsive
        # while the child is joined and resources are being reclaimed.
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        process = self._process
        if process is not None and process.pid is not None:
            process.join(timeout=.2)
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join()
        with self._state_lock:
            self._process = None
            if process is not None:
                process.close()
            self._runtime = {}
            self._state = state
        if process is not None:
            self._logger.info("event=worker_model_release status=%s", state)

    def _expire(self, completed: float) -> None:
        with self._operation:
            if not self._closed and self._completed == completed:
                self._dispose("unloaded")

    def __call__(self, request: dict[str, Any]) -> bytes:
        from .speech import _read_pcm
        payload = json.dumps(request).encode()
        if len(payload) > MAX_BASE_REQUEST_BYTES:
            raise ValueError("Native model request exceeds transport limit")
        with self._operation:
            if self._closed:
                raise RuntimeError("Native model lifecycle is closed")
            if self._timer is not None:
                self._timer.cancel()
            with self._state_lock:
                self._active = True
            if self._process is not None and not self._process.is_alive():
                self._dispose("failed")
            loading = self._process is None
            started = time.monotonic()
            try:
                if loading:
                    self._logger.info("event=worker_model_load status=started")
                    with self._state_lock:
                        self._state = "loading"
                    context = multiprocessing.get_context("spawn")
                    parent, child = context.Pipe()
                    self._connection = parent
                    process = context.Process(target=_child, args=(child, self._loader), daemon=True)
                    with self._state_lock:
                        self._process = process
                    try:
                        process.start()
                    finally:
                        child.close()
                    metadata = json.loads(self._receive(4096))
                    if not isinstance(metadata, dict) or set(metadata) - {"runtime"}:
                        raise ValueError("Invalid native model runtime metadata")
                    with self._state_lock:
                        self._runtime = metadata
                        self._state = "loaded"
                    self._logger.info("event=worker_model_load status=ready duration_ms=%d",
                                      int((time.monotonic() - started) * 1000))
                if self._connection is None:
                    raise RuntimeError("Native model process is disconnected")
                self._connection.send_bytes(payload)
                data = self._receive(MAX_RESPONSE_BYTES)
                if _read_pcm(data)[0] != (1, 2, SAMPLE_RATE):
                    raise ValueError("Invalid native model PCM audio")
                return data
            except Exception as exc:
                if loading:
                    self._logger.warning("event=worker_model_load status=failed duration_ms=%d",
                                         int((time.monotonic() - started) * 1000))
                self._dispose("failed")
                raise RuntimeError("Native model process failed during loading or synthesis") from exc
            finally:
                with self._state_lock:
                    self._active = False
                self._completed = time.monotonic()
                if self._process is not None:
                    self._timer = threading.Timer(self._idle_timeout, self._expire, args=(self._completed,))
                    self._timer.daemon = True
                    self._timer.start()

    def close(self) -> None:
        """Wait for an active job before releasing its owned child."""
        with self._operation:
            self._closed = True
            if self._timer is not None:
                self._timer.cancel()
            self._dispose("unloaded")

    def __enter__(self) -> ModelLifecycle:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def serve_worker(loader: Loader, *, model: str, port: int,
                 idle_timeout_seconds: float = DEFAULT_IDLE_TIMEOUT_SECONDS) -> None:
    """Run the shared cold HTTP worker and close its model on every exit path."""
    from .speech_worker import worker_server
    with ModelLifecycle(loader, idle_timeout_seconds=idle_timeout_seconds) as lifecycle:
        server = worker_server(lifecycle, model=model, port=port, health_info=lifecycle.health)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
