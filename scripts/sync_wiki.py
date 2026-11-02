#!/usr/bin/env python3
"""Synchronize docs/wiki/ markdown pages to the GitHub Wiki repository."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = REPO_ROOT / "docs" / "wiki"
WIKI_REMOTE = "https://github.com/mfahsold/lixity.wiki.git"


def main() -> int:
    if not WIKI_DIR.is_dir():
        print(f"Error: {WIKI_DIR} does not exist.", file=sys.stderr)
        return 1

    git = shutil.which("git")
    if not git:
        print("Error: git is not installed.", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="lixity-wiki-sync-") as tmpdir:
        clone_dir = Path(tmpdir) / "repo"
        print(f"Cloning {WIKI_REMOTE}...")
        clone_res = subprocess.run(  # noqa: S603
            [git, "clone", WIKI_REMOTE, str(clone_dir)],
            check=False,
            capture_output=True,
            text=True,
        )
        if clone_res.returncode != 0:
            print("Note: GitHub Wiki repository is not yet initialized on GitHub servers.", file=sys.stderr)
            print("To initialize: visit https://github.com/mfahsold/lixity/wiki and click 'Save page' on Home.md once.", file=sys.stderr)
            return 2

        # Copy all files from docs/wiki to clone_dir
        for src_file in WIKI_DIR.iterdir():
            if src_file.is_file():
                shutil.copy2(src_file, clone_dir / src_file.name)

        # Commit and push
        subprocess.run([git, "add", "-A"], cwd=clone_dir, check=True)  # noqa: S603
        status_res = subprocess.run(  # noqa: S603
            [git, "status", "--porcelain"],
            check=False,
            cwd=clone_dir,
            capture_output=True,
            text=True,
        )
        if not status_res.stdout.strip():
            print("GitHub Wiki is already up to date.")
            return 0

        subprocess.run(  # noqa: S603
            [git, "commit", "-m", "docs(wiki): synchronize wiki documentation from docs/wiki"],
            cwd=clone_dir,
            check=True,
        )
        print("Pushing updates to GitHub Wiki...")
        subprocess.run([git, "push", "origin", "master"], cwd=clone_dir, check=True)  # noqa: S603
        print("Successfully synchronized docs/wiki to GitHub Wiki!")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
