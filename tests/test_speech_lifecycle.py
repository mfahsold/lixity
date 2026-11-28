"""Model residency uses real spawned processes without optional inference stacks."""
from __future__ import annotations

import json
import os
import time

import pytest

from lixity.speech import generate_silence_wav
from lixity.speech_lifecycle import ModelLifecycle


def load_fake():
    def render(request):
        if request.get("crash"):
            os._exit(7)
        if request.get("delay"):
            time.sleep(request["delay"])
        return generate_silence_wav(.01, 24000)
    return render


def test_cold_health_reuse_and_release():
    with ModelLifecycle(load_fake, idle_timeout_seconds=.15) as lifecycle:
        assert lifecycle.health() == {"model_state": "unloaded", "active": False, "idle_timeout_seconds": .15}
        assert lifecycle.child_pid is None
        assert lifecycle({})[:4] == b"RIFF"
        first = lifecycle.child_pid
        assert first and first != os.getpid()
        assert lifecycle.health()["model_state"] == "loaded"
        lifecycle({})
        assert lifecycle.child_pid == first
        deadline = time.monotonic() + 5
        while lifecycle.health()["model_state"] != "unloaded" and time.monotonic() < deadline:
            time.sleep(.02)
        assert lifecycle.child_pid is None
        lifecycle({})
        assert lifecycle.child_pid != first


def test_spawned_worker_accepts_a_bounded_toucan_reference_set():
    from lixity.speech_worker import MAX_BASE_REQUEST_BYTES, MAX_REFERENCE_SET_REQUEST_BYTES

    payload = {"reference_parts": ["x" * (MAX_BASE_REQUEST_BYTES + 1)]}
    assert len(json.dumps(payload).encode()) < MAX_REFERENCE_SET_REQUEST_BYTES
    with ModelLifecycle(load_fake) as lifecycle:
        assert lifecycle(payload)[:4] == b"RIFF"


def test_spawned_worker_rejects_an_oversized_request_before_loading():
    from lixity.speech_worker import MAX_REFERENCE_SET_REQUEST_BYTES

    with ModelLifecycle(load_fake) as lifecycle:
        with pytest.raises(ValueError, match="transport limit"):
            lifecycle({"reference_parts": ["x" * MAX_REFERENCE_SET_REQUEST_BYTES]})
        assert lifecycle.child_pid is None


def test_idle_interval_begins_after_completion():
    with ModelLifecycle(load_fake, idle_timeout_seconds=.1) as lifecycle:
        lifecycle({"delay": .2})
        assert lifecycle.health()["model_state"] == "loaded"
        assert lifecycle.child_pid is not None


def test_crashed_child_is_reaped_and_retry_works():
    with ModelLifecycle(load_fake) as lifecycle:
        with pytest.raises(RuntimeError, match="process"):
            lifecycle({"crash": True})
        assert lifecycle.health()["model_state"] == "failed"
        assert lifecycle.child_pid is None
        assert lifecycle({})[:4] == b"RIFF"


@pytest.mark.parametrize("timeout", [-1, float("inf"), float("nan"), 86401, True])
def test_invalid_idle_timeout(timeout):
    with pytest.raises(ValueError):
        ModelLifecycle(load_fake, idle_timeout_seconds=timeout)


def test_zero_idle_timeout_releases_child():
    with ModelLifecycle(load_fake, idle_timeout_seconds=0) as lifecycle:
        lifecycle({})
        deadline = time.monotonic() + 5
        while lifecycle.child_pid is not None and time.monotonic() < deadline:
            time.sleep(.01)
        assert lifecycle.health() == {"model_state": "unloaded", "active": False, "idle_timeout_seconds": 0}
        assert lifecycle.child_pid is None


def test_old_deadline_never_unloads_active_or_newly_completed_job(monkeypatch):
    import threading

    import lixity.speech_lifecycle as module

    timers = []

    class ManualTimer:
        def __init__(self, interval, callback, args):
            assert interval == 300
            self.callback = lambda: callback(*args)
            self.daemon = False
            self.cancelled = False
            timers.append(self)

        def start(self):
            pass

        def cancel(self):
            self.cancelled = True

    monkeypatch.setattr(module.threading, "Timer", ManualTimer)
    with ModelLifecycle(load_fake) as lifecycle:
        lifecycle({})
        first_pid = lifecycle.child_pid
        first_timer = timers[-1]
        responses = []
        job = threading.Thread(target=lambda: responses.append(lifecycle({"delay": .3})))
        job.start()
        deadline = time.monotonic() + 5
        while not lifecycle.health()["active"] and time.monotonic() < deadline:
            time.sleep(.01)
        expired = threading.Thread(target=first_timer.callback)
        expired.start()
        assert lifecycle.health() == {"model_state": "loaded", "active": True, "idle_timeout_seconds": 300}
        assert lifecycle.child_pid == first_pid
        job.join(5)
        expired.join(5)
        assert not job.is_alive() and not expired.is_alive()
        assert len(responses) == 1
        assert first_timer.cancelled
        assert lifecycle.child_pid == first_pid
        assert lifecycle.health()["model_state"] == "loaded"
        timers[-1].callback()
        assert lifecycle.child_pid is None


def load_with_runtime():
    from lixity.speech_qwen import LoadedRenderer, WorkerRuntime
    return LoadedRenderer(load_fake(), WorkerRuntime("cpu", "float32", 1, "eager", "cpu"))


def test_runtime_only_exists_while_model_is_resident():
    lifecycle = ModelLifecycle(load_with_runtime)
    assert "runtime" not in lifecycle.health()
    lifecycle({})
    assert lifecycle.health()["runtime"]["device"] == "cpu"
    lifecycle.close()
    lifecycle.close()
    assert lifecycle.child_pid is None
    assert "runtime" not in lifecycle.health()
    with pytest.raises(RuntimeError, match="closed"):
        lifecycle({})


def test_pipe_eof_exits_child_and_close_reaps_it():
    with ModelLifecycle(load_fake) as lifecycle:
        lifecycle({})
        process = lifecycle._process
        assert process is not None
        lifecycle._connection.close()
        process.join(timeout=5)
        assert not process.is_alive()


def load_failing():
    raise ValueError("Synthetic loading failure")


def test_loading_failure_is_explicit_and_reaped():
    with ModelLifecycle(load_failing) as lifecycle:
        with pytest.raises(RuntimeError, match="process"):
            lifecycle({})
        assert lifecycle.health() == {"model_state": "failed", "active": False, "idle_timeout_seconds": 300}
        assert lifecycle.child_pid is None


def load_invalid():
    return lambda request: b"invalid waveform"


def test_invalid_child_audio_is_rejected_and_reaped():
    with ModelLifecycle(load_invalid) as lifecycle:
        with pytest.raises(RuntimeError, match="process"):
            lifecycle({})
        assert lifecycle.health()["model_state"] == "failed"
        assert lifecycle.child_pid is None


def test_http_health_is_cold_and_residency_is_visible():
    import json
    import threading
    import urllib.request

    from lixity.speech_worker import worker_health, worker_server

    with ModelLifecycle(load_fake) as lifecycle:
        server = worker_server(lifecycle, port=0, health_info=lifecycle.health)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        endpoint = f"http://127.0.0.1:{server.server_port}"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(endpoint + "/health") as response:
                health = json.load(response)
            assert health["ready"] is True
            assert health["model_state"] == "unloaded"
            assert "runtime" not in health
            assert lifecycle.child_pid is None
            result = worker_health("local", endpoints={"local": endpoint + "/v1/audio/speech"})
            assert result["state"] == "ready"
            assert result["model_state"] == "unloaded"
            assert lifecycle.child_pid is None
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


def test_shared_cli_policy_is_configurable_and_bounded():
    import argparse

    from lixity.speech_lifecycle import add_lifecycle_arguments

    parser = argparse.ArgumentParser()
    add_lifecycle_arguments(parser)
    assert parser.parse_args([]).idle_timeout_seconds == 300
    assert parser.parse_args(["--idle-timeout-seconds", "12.5"]).idle_timeout_seconds == 12.5
    assert parser.parse_args(["--idle-timeout-seconds", "0"]).idle_timeout_seconds == 0
    for invalid in ("-1", "nan", "inf", "86401"):
        with pytest.raises(SystemExit):
            parser.parse_args(["--idle-timeout-seconds", invalid])


def test_idle_child_death_is_reported_and_next_request_reloads():
    with ModelLifecycle(load_with_runtime, idle_timeout_seconds=21) as lifecycle:
        lifecycle({})
        process = lifecycle._process
        first_pid = lifecycle.child_pid
        process.terminate()
        process.join(5)
        assert lifecycle.health() == {"model_state": "failed", "active": False, "idle_timeout_seconds": 21}
        lifecycle({})
        assert lifecycle.child_pid != first_pid
        assert lifecycle.health()["model_state"] == "loaded"


def test_model_child_exits_when_owning_parent_dies(tmp_path):
    """Even an active renderer cannot outlive its HTTP worker process."""
    import queue
    import signal
    import subprocess
    import sys
    import threading
    from contextlib import suppress
    from pathlib import Path

    driver = tmp_path / "owner.py"
    driver.write_text('''import time
from lixity.speech import generate_silence_wav
from lixity.speech_lifecycle import ModelLifecycle

def load():
    def render(request):
        if request.get("wait"):
            print("ACTIVE", flush=True)
            time.sleep(60)
        return generate_silence_wav(.01, 24000)
    return render

if __name__ == "__main__":
    lifecycle = ModelLifecycle(load)
    lifecycle({})
    print("RESIDENT " + str(lifecycle.child_pid), flush=True)
    lifecycle({"wait": True})
''', encoding="utf-8")
    environment = os.environ | {"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    messages = queue.Queue()
    child_pid = None
    child_exited = False
    with subprocess.Popen([sys.executable, str(driver)], stdout=subprocess.PIPE,  # noqa: S603 - synthetic local driver
                          stderr=subprocess.DEVNULL, text=True, env=environment) as owner:
        def read_output():
            for line in owner.stdout:
                messages.put(line.strip())
            messages.put(None)

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        try:
            resident = messages.get(timeout=10)
            assert resident.startswith("RESIDENT ")
            child_pid = int(resident.split()[1])
            assert messages.get(timeout=10) == "ACTIVE"
            owner.kill()
            owner.wait(timeout=5)
            # The child inherited stdout. EOF proves its OS process exited,
            # including during synthesis when it is not reading the IPC pipe.
            assert messages.get(timeout=5) is None
            child_exited = True
            reader.join(timeout=5)
        finally:
            if owner.poll() is None:
                owner.kill()
                owner.wait(timeout=5)
            if child_pid is not None and not child_exited:
                with suppress(ProcessLookupError):
                    os.kill(child_pid, signal.SIGTERM)
