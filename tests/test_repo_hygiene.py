"""Public-repository hygiene: planning notes, local state and secrets stay out.

The repository is public. Local planning lives in ignored directories such as
``.planning/`` and ``.artifacts/``; this test fails when such content, obvious
credentials or machine-local paths become tracked anyway. It intentionally
contains no private project names, so the guard itself is publishable.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PATHS = (".planning/", ".artifacts/", ".worktrees/", ".superpowers/")
FORBIDDEN_SUFFIXES = (".key", ".pem", ".p12", ".pfx", ".jks", ".keystore")
FORBIDDEN_NAMES = ("uv.lock",)
BINARY_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".webm", ".mp4", ".pdf",
                   ".woff2", ".whl", ".gz", ".tar", ".zip", ".so", ".dylib", ".bin")
SECRET_PATTERNS = (
    re.compile(r"hf_[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"glpat-[A-Za-z0-9_-]{20,}"),
)
#: Documented placeholders (``/home/demo``, ``/Users/you``, ``/Users/Shared``)
#: are allowed; any other machine-local home directory is not.
LOCAL_PATH_PATTERNS = (
    re.compile(r"/home/(?!demo\b)[A-Za-z0-9._-]+/"),
    re.compile(r"/Users/(?!you/|Shared/)[A-Za-z0-9._-]+/"),
)


def tracked_files() -> list[str]:
    git = shutil.which("git")
    assert git is not None, "git is required for the repository hygiene check"
    result = subprocess.run(  # noqa: S603 - resolved git executable
        [git, "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def test_no_planning_or_local_state_is_tracked() -> None:
    offenders = [name for name in tracked_files()
                 if name.startswith(FORBIDDEN_PATHS) or Path(name).name in FORBIDDEN_NAMES]
    assert offenders == [], f"Local planning or tool state must not be tracked: {offenders}"


def test_no_credentials_or_private_keys_are_tracked() -> None:
    offenders = []
    for name in tracked_files():
        path = Path(name)
        private_key = path.suffix in FORBIDDEN_SUFFIXES or path.name.startswith(("id_rsa", "id_ed25519", "id_ecdsa"))
        environment = path.name == ".env" or (
            path.name.startswith(".env.") and not path.name.endswith((".example", ".template"))
        )
        if private_key or environment:
            offenders.append(name)
    assert offenders == [], f"Credentials or private keys must not be tracked: {offenders}"


def test_tracked_text_files_carry_no_secrets_or_local_paths() -> None:
    offenders = []
    for name in tracked_files():
        path = Path(name)
        if path.suffix in BINARY_SUFFIXES:
            continue
        try:
            text = (ROOT / name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in (*SECRET_PATTERNS, *LOCAL_PATH_PATTERNS):
            match = pattern.search(text)
            if match:
                offenders.append(f"{name}: {pattern.pattern}")
    assert offenders == [], f"Secret-like values or machine-local paths found: {offenders}"
