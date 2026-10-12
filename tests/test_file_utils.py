"""Atomic file failures must preserve the original bytes and permissions."""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from lixity.io import FileUtils


def _write(target: Path, content: bytes, binary: bool) -> bool:
    if binary:
        return FileUtils.atomic_write_bytes_if_changed(str(target), content)
    return FileUtils.atomic_write_if_changed(str(target), content.decode("utf-8"))


@pytest.mark.parametrize("binary", [False, True])
@pytest.mark.parametrize("operation", ["mkstemp", "fdopen", "chmod", "fsync", "replace"])
def test_atomic_failure_preserves_original_and_cleans_staging(tmp_path, binary, operation):
    target = tmp_path / "manuscript.md"
    original = b"Original synthetic manuscript.\n"
    target.write_bytes(original)
    target.chmod(0o640)
    mode = stat.S_IMODE(target.stat().st_mode)
    namespace = "tempfile" if operation == "mkstemp" else "os"
    with (
        patch(f"lixity.io.{namespace}.{operation}", side_effect=OSError("injected failure")),
        pytest.raises(OSError, match="injected failure"),
    ):
        _write(target, b"Updated synthetic manuscript.\n", binary)
    assert target.read_bytes() == original
    assert stat.S_IMODE(target.stat().st_mode) == mode
    assert sorted(path.name for path in tmp_path.iterdir()) == ["manuscript.md"]


@pytest.mark.parametrize("binary", [False, True])
def test_partial_staged_write_never_falls_back_to_original(tmp_path, binary):
    target = tmp_path / "manuscript.md"
    target.write_bytes(b"Original synthetic manuscript.\n")
    real_fdopen = os.fdopen

    class PartialWriter:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def write(self, content):
            self.stream.write(content[:3])
            raise OSError("partial staged write")

    def partial_fdopen(*args, **kwargs):
        stream = real_fdopen(*args, **kwargs)
        return PartialWriter(stream) if args[1] == "wb" else stream

    with (
        patch("lixity.io.os.fdopen", side_effect=partial_fdopen),
        pytest.raises(OSError, match="partial staged write"),
    ):
        _write(target, b"Updated synthetic manuscript.\n", binary)
    assert target.read_bytes() == b"Original synthetic manuscript.\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["manuscript.md"]


@pytest.mark.parametrize("binary", [False, True])
@pytest.mark.parametrize("permissions", [0o640, 0o4750])
def test_changed_write_preserves_mode_and_repeat_does_not_stage(tmp_path, binary, permissions):
    target = tmp_path / "manuscript.md"
    target.write_bytes(b"Original.\n")
    target.chmod(permissions)
    mode = stat.S_IMODE(target.stat().st_mode)
    content = "Synthetic résumé.\n".encode()
    assert _write(target, content, binary) is True
    assert target.read_bytes() == content
    assert stat.S_IMODE(target.stat().st_mode) == mode
    with patch("lixity.io.tempfile.mkstemp", side_effect=OSError("must not stage")):
        assert _write(target, content, binary) is False
    assert sorted(path.name for path in tmp_path.iterdir()) == ["manuscript.md"]


def test_before_replace_guard_can_reject_without_changing_original(tmp_path):
    target = tmp_path / "settings.toml"
    target.write_bytes(b"original = true\n")

    def reject():
        assert target.read_bytes() == b"original = true\n"
        staged = list(tmp_path.glob("sync_tmp_*.tmp"))
        assert len(staged) == 1
        assert staged[0].read_bytes() == b"updated = true\n"
        raise OSError("project changed")

    with pytest.raises(OSError, match="project changed"):
        FileUtils.atomic_write_bytes_if_changed(
            str(target), b"updated = true\n", before_replace=reject,
        )
    assert target.read_bytes() == b"original = true\n"
    assert list(tmp_path.glob("sync_tmp_*.tmp")) == []


def test_before_replace_guard_runs_after_fsync_and_not_for_unchanged_bytes(tmp_path):
    target = tmp_path / "settings.toml"
    target.write_bytes(b"original = true\n")
    events = []
    real_fsync = os.fsync

    def synced(fd):
        real_fsync(fd)
        events.append("synced")

    def guard():
        assert events == ["synced"]
        assert target.read_bytes() == b"original = true\n"
        events.append("guarded")

    with patch("lixity.io.os.fsync", side_effect=synced):
        assert FileUtils.atomic_write_bytes_if_changed(
            str(target), b"updated = true\n", before_replace=guard,
        ) is True
    assert events == ["synced", "guarded"]
    assert target.read_bytes() == b"updated = true\n"
    assert FileUtils.atomic_write_bytes_if_changed(
        str(target), b"updated = true\n", before_replace=guard,
    ) is False


def test_decode_failure_is_a_read_error_without_changing_bytes(tmp_path):
    target = tmp_path / "manuscript.md"
    target.write_bytes(b"Synthetic invalid UTF-8: \xff\n")
    with pytest.raises(OSError, match="utf-8"):
        FileUtils.read_file(str(target))
    assert target.read_bytes() == b"Synthetic invalid UTF-8: \xff\n"


def test_source_snapshot_hash_and_normalized_text_use_the_same_read(tmp_path):
    target = tmp_path / "manuscript.md"
    original = "Synthetic résumé.\r\nAnother line.\r".encode()
    target.write_bytes(original)
    real_fdopen = os.fdopen

    class ChangingReader:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def read(self):
            content = self.stream.read()
            target.write_bytes(b"Changed after the snapshot read.\n")
            return content

    def changing_open(*args, **kwargs):
        return ChangingReader(real_fdopen(*args, **kwargs))

    with patch("lixity.io.os.fdopen", side_effect=changing_open) as opened:
        text, digest = FileUtils.read_source_snapshot(str(target))
    assert opened.call_count == 1
    assert text == "Synthetic résumé.\nAnother line.\n"
    assert digest == hashlib.sha256(original).hexdigest()
    assert digest != hashlib.sha256(target.read_bytes()).hexdigest()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO required")
def test_source_snapshot_refuses_fifo_without_waiting_for_a_writer(tmp_path):
    target = tmp_path / "manuscript.md"
    os.mkfifo(target)
    code = (
        "import sys; from lixity.io import FileUtils\n"
        "try: FileUtils.read_source_snapshot(sys.argv[1])\n"
        "except OSError: print('refused')\n"
    )
    result = subprocess.run([sys.executable, "-c", code, str(target)],  # noqa: S603 - synthetic local file
                            capture_output=True, text=True, timeout=2, check=True)
    assert result.stdout.strip() == "refused"


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO required")
def test_snapshot_refuses_node_replaced_after_regular_file_check(tmp_path):
    target = tmp_path / "manuscript.md"
    target.write_text("Synthetic manuscript.\n", encoding="utf-8")
    real_open = os.open

    def changed_open(path, flags, *args, **kwargs):
        target.unlink()
        os.mkfifo(target)
        return real_open(path, flags, *args, **kwargs)

    with patch("lixity.io.os.open", side_effect=changed_open), pytest.raises(OSError, match="regular"):
        FileUtils.read_source_snapshot(str(target))


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO required")
@pytest.mark.parametrize("binary", [False, True])
def test_atomic_writer_refuses_special_nodes_without_replacing_them(tmp_path, binary):
    target = tmp_path / "output.txt"
    os.mkfifo(target)
    with pytest.raises(OSError, match="regular"):
        _write(target, b"Synthetic output.\n", binary)
    assert stat.S_ISFIFO(target.stat().st_mode)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["output.txt"]


def test_text_writer_honors_explicit_encoding(tmp_path):
    target = tmp_path / "manuscript.txt"
    assert FileUtils.atomic_write_if_changed(str(target), "résumé\n", "utf-16") is True
    assert target.read_bytes() == "résumé\n".encode("utf-16")
    assert FileUtils.atomic_write_if_changed(str(target), "résumé\n", "utf-16") is False


def test_unchanged_text_does_not_rewrite_existing_crlf_newlines(tmp_path):
    target = tmp_path / "manuscript.md"
    target.write_bytes(b"Synthetic text.\r\n")
    with patch("lixity.io.tempfile.mkstemp", side_effect=OSError("must not stage")):
        assert FileUtils.atomic_write_if_changed(str(target), "Synthetic text.\n") is False
    assert target.read_bytes() == b"Synthetic text.\r\n"
