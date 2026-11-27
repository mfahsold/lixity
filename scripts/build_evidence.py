"""Identify a local build's inputs and retain its evidence outside disposable checkouts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def source_state(root: Path) -> dict:
    """Identify HEAD, tracked changes and the contents of untracked source files."""
    git = shutil.which("git")
    if git is None:
        raise ValueError("Git is required to identify the local build source")

    def read_git(*args: str) -> bytes:
        return subprocess.check_output([git, *args], cwd=root)  # noqa: S603 - fixed Git queries

    revision = read_git("rev-parse", "--verify", "HEAD").decode("ascii").strip()
    changes = read_git("status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none")
    if not changes:
        return {"commit": revision, "dirty": False}

    tracked = read_git("diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--")
    untracked = hashlib.sha256()
    names = read_git("ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    for name in sorted(filter(None, names)):
        path = root / os.fsdecode(name)
        mode = path.lstat().st_mode
        contents = hashlib.sha256()
        if stat.S_ISLNK(mode):
            contents.update(os.fsencode(os.readlink(path)))
        elif stat.S_ISREG(mode):
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    contents.update(chunk)
        else:
            raise ValueError(f"Expected a regular file or symlink in the build source: {path}")
        untracked.update(name + b"\0" + str(mode).encode("ascii") + b"\0" + contents.digest())

    return {
        "commit": revision,
        "dirty": True,
        "tracked_diff_sha256": hashlib.sha256(tracked).hexdigest(),
        "status_sha256": hashlib.sha256(changes).hexdigest(),
        "untracked_files_sha256": untracked.hexdigest(),
    }


def build_output_parent(checkout: Path, default: Path, output_root: Path | None) -> Path:
    """Use one optional evidence root with a subdirectory per build type."""
    configured_root = os.environ.get("LIXITY_BUILD_OUTPUT_ROOT")
    if output_root is None and configured_root:
        output_root = Path(configured_root)
    parent = default if output_root is None else output_root.expanduser() / default.name
    parent = parent.resolve()
    if parent.is_relative_to(checkout.resolve()):
        relative = parent.relative_to(checkout.resolve()).as_posix()
        git = shutil.which("git")
        if git is None:
            raise ValueError("Git is required to check the build output location")
        # The output must stay out of the source snapshot on both sides of a build.
        result = subprocess.run(  # noqa: S603 - fixed Git check for the chosen directory
            [git, "check-ignore", "-q", "--", relative + "/"], cwd=checkout, check=False,
        )
        if result.returncode != 0:
            raise ValueError(f"Choose a Git-ignored build output directory or one outside the checkout: {parent}")
    return parent


def write_build_receipt(path: Path, data: dict) -> None:
    """Replace the receipt atomically within its private build directory."""
    pending = path.with_suffix(path.suffix + ".tmp")
    pending.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    pending.replace(path)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
