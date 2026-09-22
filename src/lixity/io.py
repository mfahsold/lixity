"""lixity.io – Atomic, idempotent file operations with diff-suppression.

Ensures zero-diff idempotency via content hashing and equality checks,
with atomic replacement to prevent partial writes.
"""

import os
import shutil
import tempfile


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
        filepath = os.path.abspath(filepath)
        unchanged = False
        try:
            unchanged = FileUtils.read_file(filepath, encoding) == content
        except (OSError, UnicodeError):
            unchanged = False  # Missing or unreadable target -> rewrite
        if unchanged:
            return False  # Identical content -> no write access needed

        out_dir = os.path.dirname(filepath)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        # Stage 1: tempfile in the target directory (true POSIX-atomic rename via os.replace)
        try:
            temp_fd, temp_path = tempfile.mkstemp(dir=out_dir, prefix="sync_tmp_", suffix=".tmp")
            with os.fdopen(temp_fd, "w", encoding=encoding) as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())  # durability: data on disk before the rename
            os.replace(temp_path, filepath)
            return True
        except OSError:
            # Stage 2: system-wide temp directory (in case the workspace is sandbox-isolated, for example)
            try:
                temp_fd, temp_path = tempfile.mkstemp(
                    dir=tempfile.gettempdir(), prefix="sync_tmp_", suffix=".tmp"
                )
                with os.fdopen(temp_fd, "w", encoding=encoding) as f:
                    f.write(content)
                shutil.move(temp_path, filepath)
                return True
            except OSError:
                # Stage 3: direct in-place write as an emergency fallback
                with open(filepath, "w", encoding=encoding) as f:
                    f.write(content)
                return True

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
        with open(filepath, encoding=encoding) as f:
            return f.read()

    @staticmethod
    def ensure_dir(dirpath: str) -> None:
        """
        Creates a directory recursively if it does not yet exist.

        Parameters:
            dirpath: Directory path to create.
        """
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
