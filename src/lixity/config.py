"""lixity.config – project and user configuration files ([tool.lixity] / lixity.toml).

Resolution order (first match wins per key):
  CLI flag / API kwarg  >  UI server session  >  project pyproject.toml
  >  ~/.config/lixity.toml  >  code defaults.

Only scalar keys and simple lists/maps are read; unknown keys are ignored so
forward-compatible configs stay loadable.
"""

from __future__ import annotations

import json
import math
import os
import re
import stat
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .io import FileUtils
from .models import CorpusConfig
from .publication import PublicationSettings, validate_metadata_text

if TYPE_CHECKING:
    from .style_fingerprint import FingerprintThresholds

# Keys that may appear in [tool.lixity] (documented schema).
TOOL_KEYS = frozenset(
    {
        "title",
        "author_name",
        "publication",
        "z_mild",
        "z_strong",
        "fdr_q",
        "fdr_method",
        "dim_score_threshold",
        "flag_min_severity",
        "min_chapters",
        "names",
        "motifs",
        "phrases",
        "nda",
        "capabilities",
        "scene_analysis",
    }
) | frozenset(CorpusConfig.model_fields)


MAX_AUTHOR_NAME_CHARS = 500
MAX_PROJECT_TITLE_CHARS = 500


def validate_author_name(value: object) -> str:
    """Validate explicit author data without changing spelling or inner spacing."""
    return validate_metadata_text(value, "Author name", MAX_AUTHOR_NAME_CHARS)


def validate_project_title(value: object) -> str:
    """Validate the same bounded title used by UI and PDF metadata."""
    return validate_metadata_text(value, "Title", MAX_PROJECT_TITLE_CHARS)


def _same_toml(left: Any, right: Any) -> bool:
    """Compare parsed settings, including unchanged TOML NaN values."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same_toml(value, right[key]) for key, value in left.items())
    if isinstance(left, list):
        return len(left) == len(right) and all(_same_toml(a, b) for a, b in zip(left, right, strict=True))
    return (isinstance(left, float) and math.isnan(left) and math.isnan(right)) or bool(left == right)


def _parse_project_toml(content: str) -> dict[str, Any]:
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - Python 3.10
        import tomli as tomllib
    try:
        return dict(tomllib.loads(content))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError("Project config could not be parsed; nothing was changed") from exc


def project_config_snapshot(path: Path) -> tuple[tuple[int, ...] | None, bytes]:
    """Read only a regular root config, without blocking on special file nodes."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None, b""
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Project config must be a regular nonsymlink file")
    # NONBLOCK also protects a POSIX regular-file→FIFO race; NOFOLLOW refuses a
    # replacement symlink where supported. fstat checks the opened node again.
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError("Project config changed while reading; nothing was changed")
        content = stream.read()
    return (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns, info.st_size, info.st_mode), content


@dataclass(frozen=True)
class PreparedProjectSettings:
    """A validated candidate, committed only if both root configs are unchanged."""

    path: Path
    original: tuple[tuple[int, ...] | None, bytes]
    pyproject_original: tuple[tuple[int, ...] | None, bytes]
    content: bytes

    def commit(self) -> None:
        def unchanged() -> None:
            if (project_config_snapshot(self.path) != self.original
                    or project_config_snapshot(self.path.parent / "pyproject.toml") != self.pyproject_original):
                raise ValueError("Project config changed while saving; nothing was overwritten")
        unchanged()
        FileUtils.atomic_write_bytes_if_changed(str(self.path), self.content, before_replace=unchanged)


def _edit_project_setting(content: str, key: str, value: Any) -> str:
    settings = _parse_project_toml(content)
    expected = {**settings, key: value}
    if key in settings and _same_toml(settings[key], value):
        return content
    newline = "\r\n" if "\r\n" in content else "\n"
    if isinstance(value, dict):
        encoded = "{ " + ", ".join(f"{name} = {_toml_literal(item)}" for name, item in value.items()) + " }"
    else:
        encoded = _toml_literal(value)
    candidates: list[str] = []

    def candidate(updated: str) -> None:
        try:
            if _same_toml(expected, _parse_project_toml(updated)):
                candidates.append(updated)
        except ValueError:
            pass

    if key not in settings:
        if isinstance(value, dict):
            block = newline.join(f"{name} = {_toml_literal(item)}" for name, item in value.items())
            candidate(content + (newline if content and not content.endswith("\n") else "")
                      + f"[{key}]" + newline + block + newline)
        else:
            candidate(f"{key} = {encoded}" + newline + content)
    else:
        scalar = r'(?:"(?:[^"\\\r\n]|\\.)*"|\'[^\'\r\n]*\'|true|false|[+-]?[\d_]+(?:\.[\d_]+)?)'
        value_pattern = r"\{[^\r\n]*\}" if isinstance(value, dict) else scalar
        assignments = re.compile(
            rf"^([ \t]*(?:{key}|\"{key}\"|'{key}')[ \t]*=[ \t]*){value_pattern}"
            r"([ \t]*(?:#[^\r\n]*)?)(\r?\n|$)", re.MULTILINE)
        for match in assignments.finditer(content):
            candidate(content[:match.start()] + match[1] + encoded + match[2] + match[3] + content[match.end():])
        if isinstance(value, dict):
            headers = list(re.finditer(r"^[ \t]*\[[^\r\n]+\][ \t]*(?:#[^\r\n]*)?(?:\r?\n|$)", content, re.MULTILINE))
            for header in headers:
                if not re.fullmatch(rf"[ \t]*\[(?:{key}|\"{key}\"|'{key}')\][ \t]*(?:#[^\r\n]*)?(?:\r?\n|$)", header[0]):
                    continue
                # Parsed equality identifies real boundaries even if a multiline
                # string elsewhere happens to contain something like a header.
                for end in [match.start() for match in headers if match.start() > header.start()] + [len(content)]:
                    block = newline.join(f"{name} = {_toml_literal(item)}" for name, item in value.items())
                    comments = "".join(line for line in content[header.end():end].splitlines(keepends=True)
                                       if line.lstrip().startswith("#"))
                    candidate(content[:header.end()] + comments + block + newline + content[end:])
    if len(set(candidates)) != 1:
        raise ValueError(f"Project {key} assignment cannot be safely updated; nothing was changed")
    return candidates[0]


def _toml_literal(value: Any) -> str:
    return ("true" if value else "false") if isinstance(value, bool) else json.dumps(value, ensure_ascii=False)


def prepare_project_settings(
    project_root: str | Path | None, changes: Mapping[str, Any],
) -> PreparedProjectSettings:
    """Prepare one root-only identity/publication update, preserving other data.

    Unsupported assignment syntax fails closed. Optimistic stat/byte checks are
    protection against observed external edits, not a cross-process file lock.
    """
    if project_root is None:
        raise ValueError("An explicit active project directory is required")
    root = Path(project_root).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("An existing nonsymlink project directory is required")
    path = root / "lixity.toml"
    original = project_config_snapshot(path)
    pyproject_original = project_config_snapshot(root / "pyproject.toml")
    try:
        content = original[1].decode("utf-8")
    except UnicodeError as exc:
        raise ValueError("Project config could not be parsed; nothing was changed") from exc
    _parse_project_toml(content)
    for key, raw in changes.items():
        if key == "author_name":
            value: Any = validate_author_name(raw)
        elif key == "title":
            value = validate_project_title(raw)
        elif key == "publication":
            value = PublicationSettings.model_validate(raw).model_dump()
        else:
            raise ValueError(f"Unsupported project metadata: {key}")
        content = _edit_project_setting(content, key, value)
    return PreparedProjectSettings(path, original, pyproject_original, content.encode("utf-8"))


def save_project_author(project_root: str | Path | None, author_name: object) -> None:
    """Persist author identity through the shared prepared metadata writer."""
    prepare_project_settings(project_root, {"author_name": author_name}).commit()


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10 in CI
        import tomli as tomllib
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except OSError as exc:
        warnings.warn(
            f"Could not read {path}: {exc}. Its settings are ignored.",
            stacklevel=2,
        )
        return {}
    except tomllib.TOMLDecodeError as exc:
        # A malformed config silently reverts language, thresholds and corpus
        # patterns to defaults, so the analysis runs and reports numbers that
        # do not match what the project asked for. Unreadable is not the same
        # as absent, and only one of the two may be quiet.
        warnings.warn(
            f"Could not parse {path}: {exc}. Its settings are ignored and code "
            f"defaults apply -- check the reported language and thresholds, they "
            f"are probably not the ones you configured.",
            stacklevel=2,
        )
        return {}
    if path.name == "pyproject.toml":
        tool = data.get("tool") or {}
        section = tool.get("lixity") or {}
        return dict(section) if isinstance(section, dict) else {}
    return dict(data) if isinstance(data, dict) else {}


def _walk_up(start: Path, name: str) -> Path | None:
    for directory in [start, *start.parents]:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def read_project_config(directory: str | Path) -> dict[str, Any]:
    """Read the ``lixity.toml`` beside ``directory`` without walking up.

    Read-only probes (the Open Project chooser) need exactly this folder's
    configuration; ancestor or user settings must not leak into that answer.
    Oversized files are ignored instead of parsed.
    """
    path = Path(directory) / "lixity.toml"
    try:
        if path.is_file() and path.stat().st_size <= 65536:
            return _load_toml(path)
    except OSError:
        pass
    return {}


def load_project_config(start: str | Path | None = None) -> dict[str, Any]:
    """
    Merge user config under project config under nothing else.
    Returns only known scalar/list keys present in either file. Author identity
    is project data: it is read only at an explicitly supplied project root,
    never inherited from user settings, ancestor folders or an implicit cwd.
    """
    here = Path(start).resolve() if start else Path.cwd()
    if here.is_file():
        here = here.parent

    merged: dict[str, Any] = {}

    user = Path(os.path.expanduser("~/.config/lixity.toml"))
    if user.is_file():
        merged.update(_load_toml(user))
        merged.pop("author_name", None)
        merged.pop("publication", None)

    project = _walk_up(here, "pyproject.toml")
    if project is not None:
        settings = _load_toml(project)
        if start is None or project.parent != here:
            settings.pop("author_name", None)
            settings.pop("publication", None)
        merged.update(settings)

    local = _walk_up(here, "lixity.toml")
    if local is not None and local != project:
        settings = _load_toml(local)
        if start is None or local.parent != here:
            settings.pop("author_name", None)
            settings.pop("publication", None)
        merged.update(settings)

    return {k: v for k, v in merged.items() if k in TOOL_KEYS}


def same_config_scope(project_root: str | Path | None, start: str | Path | None) -> bool:
    """True when two selectors resolve to the same project-local config scope.

    ``load_project_config`` keeps author and publication only for files directly
    in the requested directory. Two selectors in that directory therefore read
    identical configuration, and callers may reuse one result instead of two.
    """
    if project_root is None or start is None:
        return False
    try:
        root = Path(project_root).resolve()
        target = Path(start).resolve()
    except OSError:
        return False
    return (target if target.is_dir() else target.parent) == root


#: Threshold keys shared by config resolution and the research analysis.
THRESHOLD_KEYS: tuple[str, ...] = (
    "z_mild",
    "z_strong",
    "fdr_q",
    "fdr_method",
    "min_chapters",
    "dim_score_threshold",
    "flag_min_severity",
)


def apply_config_to_thresholds(config: dict[str, Any]) -> dict[str, Any]:
    """Extract threshold-related keys (for FingerprintThresholds builders)."""
    return {key: config[key] for key in THRESHOLD_KEYS if key in config}


def resolve_thresholds(
    z_mild: float | None = None,
    z_strong: float | None = None,
    fdr_q: float | None = None,
    fdr_method: str | None = None,
    dim_score_threshold: float | None = None,
    flag_min_severity: int | None = None,
    min_chapters: int | None = None,
    *,
    use_project_config: bool = True,
    project_config: Mapping[str, Any] | None = None,
) -> FingerprintThresholds:
    """Single threshold builder for CLI, API and embedders.

    Precedence (first wins per key): explicit non-``None`` argument →
    project/user config (``[tool.lixity]`` / ``lixity.toml`` /
    ``~/.config/lixity.toml``) → ``FingerprintThresholds`` code default.
    Local imports avoid a module-level cycle with ``style_fingerprint``.
    """
    from .style_fingerprint import FingerprintThresholds as _FT

    defaults = _FT()
    values: dict[str, Any] = {
        "z_mild": defaults.z_mild,
        "z_strong": defaults.z_strong,
        "fdr_q": defaults.fdr_q,
        "fdr_method": defaults.fdr_method,
        "min_chapters": defaults.min_chapters,
        "dim_score_threshold": defaults.dim_score_threshold,
        "flag_min_severity": defaults.flag_min_severity,
    }
    if project_config is not None:
        values.update(apply_config_to_thresholds(dict(project_config)))
    elif use_project_config:
        values.update(apply_config_to_thresholds(load_project_config()))
    overrides = {
        "z_mild": z_mild,
        "z_strong": z_strong,
        "fdr_q": fdr_q,
        "fdr_method": fdr_method,
        "dim_score_threshold": dim_score_threshold,
        "flag_min_severity": flag_min_severity,
        "min_chapters": min_chapters,
    }
    values.update({k: v for k, v in overrides.items() if v is not None})
    return _FT(**values)
