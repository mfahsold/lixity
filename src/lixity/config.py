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
import tempfile
import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .models import CorpusConfig

if TYPE_CHECKING:
    from .style_fingerprint import FingerprintThresholds

# Keys that may appear in [tool.lixity] (documented schema).
TOOL_KEYS = frozenset(
    {
        "title",
        "author_name",
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


def validate_author_name(value: object) -> str:
    """Validate explicit author data without changing spelling or inner spacing."""
    if not isinstance(value, str):
        raise ValueError("Author name must be a string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("Author name must contain valid Unicode characters") from exc
    if any(ord(char) < 32 or 127 <= ord(char) <= 159 or char in "\u2028\u2029" for char in value):
        raise ValueError("Author name must not contain controls or line separators")
    value = value.strip()
    if len(value) > MAX_AUTHOR_NAME_CHARS:
        raise ValueError(f"Author name must be at most {MAX_AUTHOR_NAME_CHARS} characters")
    return value


def _same_toml(left: Any, right: Any) -> bool:
    """Compare parsed settings, including unchanged TOML NaN values."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same_toml(value, right[key]) for key, value in left.items())
    if isinstance(left, list):
        return len(left) == len(right) and all(_same_toml(a, b) for a, b in zip(left, right, strict=True))
    return (isinstance(left, float) and math.isnan(left) and math.isnan(right)) or bool(left == right)


def save_project_author(project_root: str | Path | None, author_name: object) -> None:
    """Atomically update only an explicit project's root author setting.

    Other bytes and parsed settings are preserved. Unsupported author assignment
    syntax, malformed TOML and changed files fail rather than being rewritten.
    The final stat/byte check is optimistic protection, not an external lock.
    """
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - Python 3.10
        import tomli as tomllib
    author = validate_author_name(author_name)
    if project_root is None:
        raise ValueError("An explicit active project directory is required")
    root = Path(project_root).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("An existing nonsymlink project directory is required")
    path = root / "lixity.toml"
    try:
        before = path.lstat()
    except FileNotFoundError:
        before = None
    if before is not None and not stat.S_ISREG(before.st_mode):
        raise ValueError("Project config must be a regular nonsymlink file")
    original = path.read_bytes() if before else b""
    try:
        content = original.decode("utf-8")
        settings = tomllib.loads(content)
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError("Project config could not be parsed; nothing was changed") from exc
    expected = {**settings, "author_name": author}
    encoded = json.dumps(author, ensure_ascii=False)
    newline = "\r\n" if "\r\n" in content else "\n"
    if "author_name" not in settings:
        updated = "author_name = " + encoded + newline + content
    elif settings["author_name"] == author:
        updated = content
    else:
        assignments = re.compile(
            r"^([ \t]*(?:author_name|\"author_name\"|'author_name')[ \t]*=[ \t]*)"
            r"(?:\"(?:[^\"\\\r\n]|\\.)*\"|'[^'\r\n]*'|true|false|[+-]?[\d_]+(?:\.[\d_]+)?)"
            r"([ \t]*(?:#[^\r\n]*)?)(\r?\n|$)", re.MULTILINE)
        candidates = []
        for match in assignments.finditer(content):
            candidate = content[:match.start()] + match[1] + encoded + match[2] + match[3] + content[match.end():]
            try:
                if _same_toml(expected, tomllib.loads(candidate)):
                    candidates.append(candidate)
            except tomllib.TOMLDecodeError:
                continue
        if len(candidates) != 1:
            raise ValueError("Project author assignment cannot be safely updated; nothing was changed")
        updated = candidates[0]
    if not _same_toml(expected, tomllib.loads(updated)):
        raise ValueError("Project config update would alter unrelated settings")
    output = updated.encode("utf-8")
    if output == original:
        if not stat.S_ISREG(path.lstat().st_mode) or path.read_bytes() != original:
            raise ValueError("Project config changed while saving; nothing was overwritten")
        return
    descriptor, temporary = tempfile.mkstemp(prefix=".lixity-author-", suffix=".tmp", dir=root)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            if before is not None:
                os.chmod(temporary, stat.S_IMODE(before.st_mode))
            stream.write(output)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            current = path.lstat()
        except FileNotFoundError:
            current = None
        def identity(info: os.stat_result | None) -> tuple[int, ...] | None:
            return ((info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns, info.st_size, info.st_mode)
                    if info is not None else None)
        if identity(current) != identity(before) or (current is not None and path.read_bytes() != original):
            raise ValueError("Project config changed while saving; nothing was overwritten")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


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

    project = _walk_up(here, "pyproject.toml")
    if project is not None:
        settings = _load_toml(project)
        if start is None or project.parent != here:
            settings.pop("author_name", None)
        merged.update(settings)

    local = _walk_up(here, "lixity.toml")
    if local is not None and local != project:
        settings = _load_toml(local)
        if start is None or local.parent != here:
            settings.pop("author_name", None)
        merged.update(settings)

    return {k: v for k, v in merged.items() if k in TOOL_KEYS}


def apply_config_to_thresholds(config: dict[str, Any]) -> dict[str, Any]:
    """Extract threshold-related keys (for FingerprintThresholds builders)."""
    out: dict[str, Any] = {}
    for key in (
        "z_mild",
        "z_strong",
        "fdr_q",
        "fdr_method",
        "min_chapters",
        "dim_score_threshold",
        "flag_min_severity",
    ):
        if key in config:
            out[key] = config[key]
    return out


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
