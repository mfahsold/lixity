"""lixity.workspace – Self-contained project workspace with idempotent artifacts.

Convention: a folder containing a manuscript is a workspace. Lixity discovers
the manuscript, creates ``exports/`` (artifacts plus ``exports/archive/``)
on demand, and publishes every artifact
idempotently:

- identical content causes **zero writes** (content hash comparison),
- changed content creates exactly one timestamped version,
- the stable file name is updated (symlink, file-copy fallback),
- older timestamped versions rotate into ``exports/archive/`` (last 10 kept).
"""

from __future__ import annotations

import contextlib
import os
import re
import stat
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import read_explicit_project_config
from .io import FileUtils
from .publishing import TIMESTAMP_PATTERN, archive_timestamped, prune_archive, update_stable_link

EXPORTS_DIRNAME = "exports"
ARCHIVE_DIRNAME = "archive"
ARCHIVE_KEEP_LAST = 10
TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S-%f"

MANUSCRIPT_FILENAMES = ("manuscript.md", "manuskript.md")
_IGNORED_STEMS = {"readme", "agents", "license", "changelog", "index", "nda"}

_UMLAUTS = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"}
)


def slugify(name: str) -> str:
    """Filesystem-safe artifact slug (umlauts transliterated, spaces -> ``_``)."""
    text = name.strip().translate(_UMLAUTS)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")
    return text or "manuskript"


@dataclass(frozen=True)
class Workspace:
    """A manuscript folder with its generated exports and artifact archive."""

    root: str
    manuscript: str

    @property
    def slug(self) -> str:
        return slugify(os.path.splitext(os.path.basename(self.manuscript))[0])

    @property
    def exports_dir(self) -> str:
        return os.path.join(self.root, EXPORTS_DIRNAME)

    @property
    def archive_dir(self) -> str:
        return os.path.join(self.exports_dir, ARCHIVE_DIRNAME)

    def ensure_layout(self) -> list[str]:
        """Create the analysis exports and archive directories idempotently.

        Returns: list of directories that did not exist before.
        """
        created = []
        for path in (self.exports_dir, self.archive_dir):
            if not os.path.isdir(path):
                created.append(path)
                FileUtils.ensure_dir(path)
        return created

    def read_manuscript(self) -> str:
        return FileUtils.read_file(self.manuscript)

    def artifact_path(self, filename: str) -> str:
        return os.path.join(self.exports_dir, filename)

    def publish(self, filename: str, content: str, dry_run: bool = False) -> bool:
        """Publishes a text artifact idempotently.

        Returns: ``True`` if the stable artifact changed (or would change in a
        dry run), ``False`` if the content is already identical.
        """
        stable = self.artifact_path(filename)
        try:
            unchanged = FileUtils.read_file(stable) == content
        except (OSError, UnicodeError):
            unchanged = False
        if unchanged:
            return False
        if dry_run:
            return True

        self.ensure_layout()
        stem, ext = os.path.splitext(filename)
        stamp = datetime.now().astimezone().strftime(TIMESTAMP_FORMAT)
        collision = 0
        same_stamp = re.compile(rf"{re.escape(stem)}_{stamp}(?:_(\d{{6,}}))?{re.escape(ext)}$")
        for directory in (self.exports_dir, self.archive_dir):
            for entry in os.listdir(directory):
                match = same_stamp.fullmatch(entry)
                if match is not None:
                    collision = max(collision, int(match.group(1) or 0) + 1)
        suffix = f"_{collision:06d}" if collision else ""
        versioned_name = f"{stem}_{stamp}{suffix}{ext}"
        versioned = self.artifact_path(versioned_name)
        FileUtils.atomic_write_if_changed(versioned, content)
        with contextlib.suppress(OSError):  # mkstemp defaults to 0600
            os.chmod(versioned, 0o644)
        if not update_stable_link(stable, versioned):
            raise OSError(f"Failed to publish stable artifact: {stable}")
        archive_timestamped(
            self.exports_dir,
            rf"{re.escape(stem)}{TIMESTAMP_PATTERN}{re.escape(ext)}$",
            keep_basenames=[versioned_name],
        )
        prune_archive(self.archive_dir, keep_last=ARCHIVE_KEEP_LAST)
        return True


class AmbiguousManuscriptError(ValueError):
    """A folder contains several possible manuscripts and needs a selector."""


def configured_manuscript(
    root: str | Path, *, project_config: Mapping[str, Any] | None = None,
) -> str | None:
    """Resolve one root-local manuscript setting without requiring source bytes.

    Missing/unreadable source state belongs to the caller (notably Research
    review). Invalid settings and paths escaping this project always fail.
    An explicit ``project_config`` mapping, including an empty one, reuses
    already inspected root-local settings without reopening their files.
    """
    base = Path(root).expanduser().resolve()
    settings = read_explicit_project_config(base) if project_config is None else project_config
    if "manuscript" not in settings:
        return None
    value = settings["manuscript"]
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Configured manuscript must be a nonblank relative path")
    relative = Path(value)
    if relative.is_absolute() or relative.anchor or ".." in relative.parts or relative == Path(".") or "\0" in value:
        raise ValueError("Configured manuscript must be a relative file path without parent traversal")
    try:
        path = base / relative
        path.resolve().relative_to(base)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f"Configured manuscript must remain inside the selected project: {exc}") from exc
    return str(path)


def resolve_manuscript_target(
    explicit: str | None = None, *, project: str | Path | None = None,
    allow_discovery: bool = False,
) -> Workspace:
    """Select one CLI manuscript and root without searching for another project.

    Legacy explicit files retain their own directory as the workspace. An
    explicit project contains every selected file; omission uses its root-local
    setting, with conventional discovery available only to folder commands.
    """
    if explicit is not None and project is None:
        selected = os.path.abspath(explicit)
        base = Path(selected).parent
    else:
        base = Path(project if project is not None else os.getcwd()).expanduser().resolve()
        if not base.is_dir():
            raise ValueError("Project path must be a folder")
        if explicit is not None:
            path = Path(explicit).expanduser()
            if not path.is_absolute():
                path = base / path
            try:
                path.resolve().relative_to(base)
            except (OSError, RuntimeError, ValueError) as exc:
                raise ValueError("Manuscript must remain inside the selected project") from exc
            selected = str(path)
        elif allow_discovery:
            return discover(root=str(base))
        else:
            configured = configured_manuscript(base)
            if configured is None:
                raise ValueError("Supply a manuscript file or set manuscript in the selected project's root-local config (use --project PATH to select a root)")
            selected = configured
    try:
        info = os.stat(selected)
    except FileNotFoundError as exc:
        raise ValueError(f"Manuscript not found: {selected}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"Manuscript must be a regular file: {selected}")
    return Workspace(root=str(base), manuscript=selected)


def discover(
    root: str | None = None, explicit: str | None = None,
    *, project_config: Mapping[str, Any] | None = None, entry_names: Sequence[str] | None = None,
) -> Workspace:
    """Resolves the manuscript of a workspace.

    Order: explicit path, root-local configured manuscript, ``<foldername>.md``, ``manuscript.md``/``manuskript.md``,
    then the only remaining Markdown file. Raises ``FileNotFoundError`` when no
    manuscript exists and ``ValueError`` when the choice is ambiguous.
    ``project_config`` reuses an already read root-local mapping. ``entry_names``
    reuses captured names for the fallback instead of listing the folder again;
    bounded callers must report an incomplete capture before invoking discovery.
    Omitted arguments preserve ordinary filesystem/configuration discovery.
    """
    if explicit:
        path = os.path.abspath(explicit)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Manuscript not found: {path}")
        return Workspace(root=os.path.dirname(path), manuscript=path)

    base = os.path.abspath(root or os.getcwd())
    configured = configured_manuscript(base, project_config=project_config)
    if configured is not None:
        try:
            info = os.stat(configured)
        except FileNotFoundError as exc:
            raise ValueError(f"Configured manuscript not found: {configured}") from exc
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"Configured manuscript must be a regular file: {configured}")
        return Workspace(root=base, manuscript=configured)
    for candidate in (f"{os.path.basename(base)}.md", *MANUSCRIPT_FILENAMES):
        path = os.path.join(base, candidate)
        if os.path.isfile(path):
            return Workspace(root=base, manuscript=path)

    markdown = sorted(
        os.path.join(base, entry)
        for entry in (os.listdir(base) if entry_names is None else entry_names)
        if entry.lower().endswith(".md")
        and os.path.splitext(entry)[0].lower() not in _IGNORED_STEMS
        and os.path.isfile(os.path.join(base, entry))
    )
    if len(markdown) == 1:
        return Workspace(root=base, manuscript=markdown[0])
    if not markdown:
        raise FileNotFoundError(
            f"No manuscript found in {base} (expected: "
            f"{os.path.basename(base)}.md, manuscript.md or exactly one .md file)."
        )
    names = ", ".join(os.path.basename(path) for path in markdown)
    raise AmbiguousManuscriptError(f"Multiple manuscripts in {base}: {names} – please specify explicitly.")


@dataclass(frozen=True)
class ProjectTarget:
    """Resolved root and optional manuscript for one explicit selector."""

    root: str
    manuscript: str | None = None
    research_only: bool = False


def resolve_project_target(selector: str | Path, *, empty: str = "error") -> ProjectTarget:
    """Resolve one explicit file or folder selector without reading manuscript text.

    - A manuscript file selects its parent directory.
    - A folder uses the shared discovery rules (``<folder>.md``,
      ``manuscript.md`` and exactly one remaining Markdown file).
    - ``empty`` decides a folder without a manuscript: ``"error"`` re-raises
      discovery, ``"research"`` accepts only a folder containing ``research/``
      and marks it research-only, ``"allow"`` accepts any folder and also
      swallows ambiguous choices for neutral foreground starts.
    """
    if empty not in ("error", "research", "allow"):
        raise ValueError("Unknown empty-folder policy: " + empty)
    path = Path(selector).expanduser().resolve()
    if path.is_file():
        return ProjectTarget(root=str(path.parent), manuscript=str(path))
    if not path.is_dir():
        raise ValueError("Project path must be a folder or manuscript file")
    try:
        workspace = discover(root=str(path))
    except FileNotFoundError:
        if empty == "research" and (path / "research").is_dir():
            return ProjectTarget(root=str(path), research_only=True)
        if empty == "allow":
            return ProjectTarget(root=str(path))
        raise
    except AmbiguousManuscriptError:
        if empty == "allow":
            return ProjectTarget(root=str(path))
        raise
    return ProjectTarget(root=workspace.root, manuscript=workspace.manuscript)
