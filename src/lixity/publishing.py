"""
scripts/engine/publishing.py
============================
Generische, projektneutrale Helfer für idempotente Publikationsartefakte.

Diese Engine-Schicht ist frei von Projekt- und Renderer-Abhängigkeiten
(kein PyCairo/Pango, keine Buch-spezifischen Namen) und wird von
export_pdf.py, export_epub.py und create_excerpt.py geteilt.

Bietet:
- ``update_stable_link``: Pflegt einen stabilen Symlink (mit Copy-Fallback
  für Dateisysteme ohne Symlink-Unterstützung).
- ``archive_timestamped``: Verschiebt ältere Zeitstempel-Artefakte atomar
  in ein Archiv-Unterverzeichnis (idempotent, überschreibt nie frische Dateien).
- ``prune_archive``: Kürzt ein Archiv auf die letzten N Versionen je
  Artefaktfamilie (Retention-Policy gegen unbegrenztes Wachstum).
"""

import os
import re
import shutil
from collections.abc import Iterable
from re import Pattern


def update_stable_link(link_path: str, source_file: str) -> bool:
    """Aktualisiert einen stabilen Symlink auf ``source_file``.

    Fällt auf eine echte Dateikopie zurück, wenn das Dateisystem keine
    Symlinks unterstützt. Rückgabe: ``True`` bei Erfolg.
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
    """Archiviert Zeitstempel-Artefakte, die nicht in ``keep_basenames`` stehen.

    - Symlinks und Nicht-Dateien werden nie angetastet (stabile Verweise bleiben).
    - Gleichnamige Archivdateien werden atomar ersetzt.
    - Rückgabe: Anzahl der archivierten Dateien.
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
    """Kürzt ein Archiv auf die letzten ``keep_last`` Versionen je Artefaktfamilie.

    Die Familie ergibt sich aus dem Dateinamen ohne Zeitstempel (z. B. alle
    ``Buch_taschenbuch_*.pdf``). Sortiert wird lexikografisch – das entspricht
    bei ``YYYY-MM-DD_HH-MM``-Zeitstempeln der chronologischen Reihenfolge.
    Rückgabe: Anzahl der gelöschten Altversionen.
    """
    if not os.path.isdir(archive_dir):
        return 0

    families: "dict[str, list[str]]" = {}
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
