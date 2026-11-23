#!/usr/bin/env python3
"""Preview or publish the Wiki Markdown pages in docs/wiki/."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = REPO_ROOT / "docs" / "wiki"
WIKI_REMOTE = "https://github.com/mfahsold/lixity.wiki.git"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true", help="Commit and push the reviewed changes")
    args = parser.parse_args(argv)

    pages = sorted(path for path in WIKI_DIR.glob("*.md") if path.is_file() and not path.is_symlink())
    names = [path.name for path in pages]
    if "Home.md" not in names:
        print(f"Error: a regular Home.md is required in {WIKI_DIR}.", file=sys.stderr)
        return 1

    git = shutil.which("git")
    if not git:
        print("Error: git is not installed.", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="lixity-wiki-sync-") as tmpdir:
        clone_dir = Path(tmpdir) / "repo"
        try:
            subprocess.run([git, "clone", "--quiet", WIKI_REMOTE, str(clone_dir)], check=True)  # noqa: S603
            branch = subprocess.check_output(  # noqa: S603
                [git, "symbolic-ref", "--short", "HEAD"], cwd=clone_dir, text=True,
            ).strip()
            revision = subprocess.check_output(  # noqa: S603
                [git, "rev-parse", "--short", "HEAD"], cwd=clone_dir, text=True,
            ).strip()
            print(f"Wiki default branch {branch} at {revision}", flush=True)
            wiki_only = sorted(path.name for path in clone_dir.glob("*.md") if path.name not in names)
            if wiki_only:
                print("Preserving wiki-only pages " + ", ".join(wiki_only), flush=True)
            for page in pages:
                target = clone_dir / page.name
                if target.is_symlink() or (target.exists() and not target.is_file()):
                    raise ValueError(f"Wiki page is not a regular file: {page.name}")
                shutil.copyfile(page, target)

            subprocess.run([git, "add", "--", *names], cwd=clone_dir, check=True)  # noqa: S603
            changes = subprocess.check_output(  # noqa: S603
                [git, "diff", "--cached", "--name-status"], cwd=clone_dir, text=True,
            )
            if not changes:
                print("Managed wiki pages are up to date.")
                return 0
            if not args.publish:
                subprocess.run(  # noqa: S603
                    [git, "--no-pager", "diff", "--cached", "--no-ext-diff", "--no-textconv"],
                    cwd=clone_dir, check=True,
                )
                print("Preview only. Use --publish to publish these pages.")
                return 0
            subprocess.run(  # noqa: S603
                [git, "commit", "-m", "docs(wiki): synchronize wiki documentation from docs/wiki"],
                cwd=clone_dir, check=True,
            )
            subprocess.run(  # noqa: S603
                [git, "push", "origin", f"HEAD:refs/heads/{branch}"], cwd=clone_dir, check=True,
            )
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            print(f"Could not synchronize the GitHub Wiki: {exc}", file=sys.stderr)
            return 1
        print("Wiki pages published.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
