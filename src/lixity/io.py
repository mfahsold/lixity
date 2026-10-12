"""lixity.io – Atomic, idempotent file operations with diff-suppression.

Ensures zero-diff idempotency via content equality checks,
with atomic replacement to prevent partial writes.
"""

import contextlib
import hashlib
import os
import stat
import tempfile
from collections.abc import Callable


class FileUtils:
    """
    Tools for reliable, atomic and idempotent filesystem operations.
    """

    @staticmethod
    def atomic_write_if_changed(filepath: str, content: str, encoding: str = "utf-8") -> bool:
        """
        Writes the passed content to disk only if it differs
        from the current file content.

        Parameters:
            filepath: Target path of the file to write.
            content: New file content as a string.
            encoding: Text encoding (default: 'utf-8').

        Returns:
            True: File was created or changed.
            False: File already exists with identical content; no write access.
        """
        try:
            if FileUtils.read_file(filepath, encoding) == content:
                return False
        except OSError:
            pass  # Missing, unreadable or incorrectly encoded target -> replace.
        return FileUtils.atomic_write_bytes_if_changed(filepath, content.encode(encoding))

    @staticmethod
    def atomic_write_bytes_if_changed(
        filepath: str,
        content: bytes,
        *,
        before_replace: Callable[[], None] | None = None,
    ) -> bool:
        """
        Writes binary content to disk only if it differs from the current file.

        Text and binary callers share a same-directory staged write. Existing
        permissions are preserved; staging or replacement errors propagate
        without an in-place overwrite fallback.

        Parameters:
            filepath: Target path to write to.
            content: New file content as bytes.
            before_replace: Optional guard called after staging and fsync,
                immediately before replacement. It is not called for unchanged
                bytes. A raised exception leaves the original file untouched.

        Returns:
            True: File was created or changed.
            False: File already exists with identical content; no write access.
        """
        filepath = os.path.abspath(filepath)
        try:
            unchanged = FileUtils._read_regular_bytes(filepath) == content
        except OSError:
            unchanged = False  # Missing or unreadable target -> rewrite
        if unchanged:
            return False

        out_dir = os.path.dirname(filepath)
        os.makedirs(out_dir, exist_ok=True)
        try:
            target_stat = os.stat(filepath)
            if not stat.S_ISREG(target_stat.st_mode):
                raise OSError("Atomic write target must be a regular file")
            mode = stat.S_IMODE(target_stat.st_mode)
        except FileNotFoundError:
            mode = None

        temp_fd: int | None = None
        temp_path: str | None = None
        try:
            temp_fd, temp_path = tempfile.mkstemp(dir=out_dir, prefix="sync_tmp_", suffix=".tmp")
            staged = os.fdopen(temp_fd, "wb")
            temp_fd = None  # The stream now owns the descriptor.
            with staged as f:
                if f.write(content) != len(content):
                    raise OSError("Incomplete staged file write")
                f.flush()
                if mode is not None:
                    os.chmod(temp_path, mode)
                os.fsync(f.fileno())
            if before_replace is not None:
                before_replace()
            os.replace(temp_path, filepath)
            return True
        finally:
            if temp_fd is not None:
                os.close(temp_fd)
            if temp_path is not None:
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(temp_path)

    @staticmethod
    def read_file(filepath: str, encoding: str = "utf-8") -> str:
        """
        Reads a text file in a standards-compliant way.

        Parameters:
            filepath: Path to the file to read.
            encoding: Text encoding (default: 'utf-8').

        Returns:
            Complete file content as a string.
        """
        return FileUtils.read_source_snapshot(filepath, encoding)[0]

    @staticmethod
    def read_source_snapshot(filepath: str, encoding: str = "utf-8") -> tuple[str, str]:
        """Return normalized text and its original-byte digest from one read."""
        content = FileUtils._read_regular_bytes(filepath)
        try:
            text = content.decode(encoding)
        except UnicodeDecodeError as exc:
            raise OSError(f"Cannot decode file {filepath!r} as {encoding}: {exc.reason}") from exc
        return text.replace("\r\n", "\n").replace("\r", "\n"), hashlib.sha256(content).hexdigest()

    @staticmethod
    def _read_regular_bytes(filepath: str) -> bytes:
        """Reject special nodes before and after opening, without blocking on a FIFO."""
        expected = os.stat(filepath)
        if not stat.S_ISREG(expected.st_mode):
            raise OSError("Text source must be a regular file")
        opened = os.open(filepath, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) |
                         getattr(os, "O_BINARY", 0))
        descriptor: int | None = opened
        try:
            actual = os.fstat(opened)
            if (not stat.S_ISREG(actual.st_mode)
                    or (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino)):
                raise OSError("Text source changed or is not a regular file")
            stream = os.fdopen(opened, "rb")
            descriptor = None
            with stream:
                content: bytes = stream.read()
                return content
        finally:
            if descriptor is not None:
                os.close(descriptor)

    @staticmethod
    def ensure_dir(dirpath: str) -> None:
        """
        Creates a directory recursively if it does not yet exist.

        Parameters:
            dirpath: Directory path to create.
        """
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
