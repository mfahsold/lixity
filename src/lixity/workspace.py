"""lixity.workspace – Self-contained project workspace with idempotent artifacts.

Convention: a folder containing a manuscript is a workspace. Lixity discovers
the manuscript, creates ``exports/`` (artifacts plus ``exports/archive/``) and
``nda/`` (encrypted agreements) on demand, and publishes every artifact
idempotently:

- identical content causes **zero writes** (content hash comparison),
- changed content creates exactly one timestamped version,
- the stable file name is updated (symlink, file-copy fallback),
- older timestamped versions rotate into ``exports/archive/`` (last 10 kept).
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime

from .io import FileUtils
from .publishing import archive_timestamped, prune_archive, update_stable_link

EXPORTS_DIRNAME = "exports"
ARCHIVE_DIRNAME = "archive"
NDA_DIRNAME = "nda"
ARCHIVE_KEEP_LAST = 10
TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M"

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
    """A manuscript folder with its generated ``exports/`` and ``nda/`` subfolders."""

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

    @property
    def nda_dir(self) -> str:
        return os.path.join(self.root, NDA_DIRNAME)

    def ensure_layout(self) -> list[str]:
        """Creates ``exports/``, ``exports/archive/`` and ``nda/`` idempotently.

        Returns: list of directories that did not exist before.
        """
        created = []
        for path in (self.exports_dir, self.archive_dir, self.nda_dir):
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
        stamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        versioned_name = f"{stem}_{stamp}{ext}"
        versioned = self.artifact_path(versioned_name)
        FileUtils.atomic_write_if_changed(versioned, content)
        try:  # published artifacts are readable (mkstemp defaults to 0600)
            os.chmod(versioned, 0o644)
        except OSError:
            pass
        update_stable_link(stable, versioned)
        archive_timestamped(
            self.exports_dir,
            rf"{re.escape(stem)}_\d{{4}}-\d{{2}}-\d{{2}}_\d{{2}}-\d{{2}}{re.escape(ext)}$",
            keep_basenames=[versioned_name],
        )
        prune_archive(self.archive_dir, keep_last=ARCHIVE_KEEP_LAST)
        return True


def discover(root: str | None = None, explicit: str | None = None) -> Workspace:
    """Resolves the manuscript of a workspace.

    Order: explicit path, ``<foldername>.md``, ``manuscript.md``/``manuskript.md``,
    then the only remaining Markdown file. Raises ``FileNotFoundError`` when no
    manuscript exists and ``ValueError`` when the choice is ambiguous.
    """
    if explicit:
        path = os.path.abspath(explicit)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Manuscript not found: {path}")
        return Workspace(root=os.path.dirname(path), manuscript=path)

    base = os.path.abspath(root or os.getcwd())
    for candidate in (f"{os.path.basename(base)}.md", *MANUSCRIPT_FILENAMES):
        path = os.path.join(base, candidate)
        if os.path.isfile(path):
            return Workspace(root=base, manuscript=path)

    markdown = sorted(
        os.path.join(base, entry)
        for entry in os.listdir(base)
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
    raise ValueError(f"Multiple manuscripts in {base}: {names} – please specify explicitly.")
