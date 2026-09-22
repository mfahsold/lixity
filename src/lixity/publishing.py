"""
scripts/engine/publishing.py
============================
Generic, project-neutral helpers for idempotent publication artefacts.

This engine layer is free of project and renderer dependencies
(no PyCairo/Pango, no book-specific names) and is shared by
export_pdf.py, export_epub.py and create_excerpt.py.

Provides:
- ``update_stable_link``: maintains a stable symlink (with copy fallback
  for filesystems without symlink support).
- ``archive_timestamped``: moves older timestamped artefacts atomically
  into an archive subdirectory (idempotent, never overwrites fresh files).
- ``prune_archive``: trims an archive to the last N versions per
  artefact family (retention policy against unbounded growth).
"""

import os
import re
import shutil
from collections.abc import Iterable
from re import Pattern


def update_stable_link(link_path: str, source_file: str) -> bool:
    """Updates a stable symlink pointing to ``source_file``.

    Falls back to a real file copy if the filesystem does not support
    symlinks. Returns: ``True`` on success.
    """
    try:
        if os.path.lexists(link_path):
            os.remove(link_path)
        try:
            os.symlink(os.path.basename(source_file), link_path)
        except (OSError, NotImplementedError):
            shutil.copyfile(source_file, link_path)
        return True
    except OSError:
        return False


def archive_timestamped(
    export_dir: str,
    pattern: "str | Pattern[str]",
    keep_basenames: Iterable[str],
    archive_subdir: str = "archive",
) -> int:
    """Archives timestamped artefacts that are not listed in ``keep_basenames``.

    - Symlinks and non-files are never touched (stable references remain).
    - Archive files with the same name are replaced atomically.
    - Returns: number of archived files.
    """
    archive_dir = os.path.join(export_dir, archive_subdir)
    os.makedirs(archive_dir, exist_ok=True)

    compiled: Pattern[str] = re.compile(pattern) if isinstance(pattern, str) else pattern
    keep = set(keep_basenames)

    archived = 0
    for entry in sorted(os.listdir(export_dir)):
        entry_path = os.path.join(export_dir, entry)
        if os.path.islink(entry_path) or not os.path.isfile(entry_path):
            continue
        if entry in keep or not compiled.match(entry):
            continue
        target_path = os.path.join(archive_dir, entry)
        if os.path.exists(target_path):
            os.remove(target_path)
        shutil.move(entry_path, target_path)
        archived += 1
    return archived


def prune_archive(
    archive_dir: str,
    keep_last: int = 10,
    timestamp_pattern: str = r"_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}",
) -> int:
    """Trims an archive to the last ``keep_last`` versions per artefact family.

    The family results from the file name without timestamp (e.g. all
    ``Buch_taschenbuch_*.pdf``). Sorting is lexicographic – for
    ``YYYY-MM-DD_HH-MM`` timestamps this corresponds to chronological order.
    Returns: number of deleted old versions.
    """
    if not os.path.isdir(archive_dir):
        return 0

    families: dict[str, list[str]] = {}
    for entry in sorted(os.listdir(archive_dir)):
        entry_path = os.path.join(archive_dir, entry)
        if os.path.islink(entry_path) or not os.path.isfile(entry_path):
            continue
        family = re.sub(timestamp_pattern, "", entry)
        families.setdefault(family, []).append(entry)

    removed = 0
    for entries in families.values():
        if len(entries) <= keep_last:
            continue
        for entry in entries[: len(entries) - keep_last]:
            os.remove(os.path.join(archive_dir, entry))
            removed += 1
    return removed
