"""lixity.config – project and user configuration files ([tool.lixity] / lixity.toml).

Resolution order (first match wins per key):
  CLI flag / API kwarg  >  UI server session  >  project pyproject.toml
  >  ~/.config/lixity.toml  >  code defaults.

Known settings use their owning component's validation. Unknown keys are ignored
so forward-compatible configs stay loadable.
"""

from __future__ import annotations

import json
import math
import os
import re
import stat
import warnings
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .io import FileUtils
from .models import CorpusConfig
from .publication import (
    PublicationSettings,
    publication_configuration_schema,
    validate_metadata_text,
)

if TYPE_CHECKING:
    from .style_fingerprint import FingerprintThresholds

#: Default loopback endpoint of the local dashboard service. Shared by the
#: ``serve``/``service`` CLI entry points and the server package; it lives in
#: this light module because the CLI must not import the server package just
#: to know its own default.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

UNINTERPRETED_KEYS = frozenset({"phrases", "capabilities"})
PROJECT_ONLY_KEYS = ("author_name", "draft_notice", "publication", "register_profiles", "chapter_registers", "characters", "manuscript")
PERSISTED_SETTINGS_KEYS = ("title", "author_name", "publication", "register_profiles", "chapter_registers")

# Keys that may appear in [tool.lixity] (documented schema).
TOOL_KEYS = frozenset(
    {
        "title",
        "author_name",
        "draft_notice",
        "publication",
        "z_mild",
        "z_strong",
        "fdr_q",
        "fdr_method",
        "dim_score_threshold",
        "flag_min_severity",
        "min_chapters",
        "names",
        "characters",
        "motifs",
        "nda",
        "scene_analysis",
        "manuscript",
    }
) | frozenset(CorpusConfig.model_fields) | UNINTERPRETED_KEYS


MAX_AUTHOR_NAME_CHARS = 500
MAX_PROJECT_TITLE_CHARS = 500
MAX_DRAFT_NOTICE_CHARS = 500


def validate_author_name(value: object) -> str:
    """Validate explicit author data without changing spelling or inner spacing."""
    return validate_metadata_text(value, "Author name", MAX_AUTHOR_NAME_CHARS)


def validate_project_title(value: object) -> str:
    """Validate the same bounded title used by UI and PDF metadata."""
    return validate_metadata_text(value, "Title", MAX_PROJECT_TITLE_CHARS)


def validate_draft_notice(value: object) -> str:
    """Validate an optional running-header notice (e.g. 'Confidential draft')."""
    return validate_metadata_text(value, "Draft notice", MAX_DRAFT_NOTICE_CHARS)


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
            block = newline.join(f"{json.dumps(name, ensure_ascii=False)} = {_toml_literal(item)}" for name, item in value.items())
            candidate(content + (newline if content and not content.endswith("\n") else "")
                      + f"[{key}]" + newline + block + newline)
        else:
            candidate(f"{key} = {encoded}" + newline + content)
    else:
        scalar = (r'(?:"(?:[^"\\\r\n]|\\.)*"|\'[^\'\r\n]*\'|true|false|'
                  r'[+-]?(?:[\d_]+(?:\.[\d_]+)?(?:[eE][+-]?[\d_]+)?|inf|nan))')
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
                    block = newline.join(f"{json.dumps(name, ensure_ascii=False)} = {_toml_literal(item)}" for name, item in value.items())
                    comments = "".join(line for line in content[header.end():end].splitlines(keepends=True)
                                       if line.lstrip().startswith("#"))
                    candidate(content[:header.end()] + comments + block + newline + content[end:])
            # Nested project tables may omit the parent header entirely. Replace
            # only their own sections; parsed equality guards unrelated data and
            # header-like lines inside multiline strings.
            spans: list[tuple[int, int]] = []
            for index, header in enumerate(headers):
                try:
                    roots = _parse_project_toml(header[0])
                except ValueError:
                    continue
                if set(roots) == {key}:
                    spans.append((header.start(), headers[index + 1].start() if index + 1 < len(headers) else len(content)))
            if spans and not candidates:
                block = f"[{key}]" + newline + newline.join(
                    f"{json.dumps(name, ensure_ascii=False)} = {_toml_literal(item)}" for name, item in value.items()) + newline
                updated = content
                for index in range(len(spans) - 1, -1, -1):
                    start, end = spans[index]
                    comments = "".join(line for line in content[start:end].splitlines(keepends=True)
                                       if line.lstrip().startswith("#"))
                    updated = updated[:start] + (block if index == 0 else "") + comments + updated[end:]
                candidate(updated)
    if len(set(candidates)) != 1:
        raise ValueError(f"Project {key} assignment cannot be safely updated; nothing was changed")
    return candidates[0]


def _toml_literal(value: Any) -> str:
    if isinstance(value, Mapping):
        return "{ " + ", ".join(f"{json.dumps(name, ensure_ascii=False)} = {_toml_literal(item)}"
                                 for name, item in value.items()) + " }"
    if isinstance(value, list):
        return "[" + ", ".join(_toml_literal(item) for item in value) + "]"
    return ("true" if value else "false") if isinstance(value, bool) else json.dumps(value, ensure_ascii=False)


def prepare_project_settings(
    project_root: str | Path | None, changes: Mapping[str, Any],
) -> PreparedProjectSettings:
    """Prepare one root-only project update, preserving other data.

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
    analysis_changes = {key: raw for key, raw in changes.items() if key in ANALYSIS_SETTINGS_KEYS}
    if "language" in analysis_changes:
        from .language import LANGUAGE_CHOICES

        if analysis_changes["language"] not in LANGUAGE_CHOICES:
            raise ValueError(f"Unknown language: {analysis_changes['language']}")
    candidate_thresholds = (resolve_thresholds(project_config={**load_project_config(root), **analysis_changes})
                            if any(key in analysis_changes for key in THRESHOLD_KEYS) else None)
    for key, raw in changes.items():
        if key == "author_name":
            value: Any = validate_author_name(raw)
        elif key == "title":
            value = validate_project_title(raw)
        elif key == "publication":
            value = PublicationSettings.model_validate(raw).model_dump()
        elif key == "language":
            value = raw
        elif key in THRESHOLD_KEYS:
            value = getattr(candidate_thresholds, key)
        elif key in {"register_profiles", "chapter_registers"}:
            from .registers import validate_register_settings

            current = load_project_config(root)
            profiles, assignments = validate_register_settings(
                changes.get("register_profiles", current.get("register_profiles", {})),
                changes.get("chapter_registers", current.get("chapter_registers", {})),
            )
            value = ({name: {feature: {bound: number for bound, number in zip(("lower", "upper"), bounds, strict=True)
                                      if number is not None} for feature, bounds in targets.items()}
                      for name, targets in profiles.items()} if key == "register_profiles" else assignments)
        else:
            raise ValueError(f"Unsupported project metadata: {key}")
        content = _edit_project_setting(content, key, value)
    return PreparedProjectSettings(path, original, pyproject_original, content.encode("utf-8"))


def save_project_author(project_root: str | Path | None, author_name: object) -> None:
    """Persist author identity through the shared prepared metadata writer."""
    prepare_project_settings(project_root, {"author_name": author_name}).commit()


def _load_toml(path: Path, *, text: str | None = None) -> dict[str, Any]:
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10 in CI
        import tomli as tomllib
    try:
        if text is None:
            with path.open("rb") as fh:
                data = tomllib.load(fh)
        else:
            data = tomllib.loads(text)
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
        section = data
        for key in ("tool", "lixity"):
            section = section.get(key, {})
            if not isinstance(section, dict):
                name = "tool" if key == "tool" else "tool.lixity"
                warnings.warn(
                    f"Could not read {path}: {name} must be a table. Its settings "
                    "are ignored and code defaults apply.",
                    stacklevel=2,
                )
                return {}
        return dict(section)
    return dict(data) if isinstance(data, dict) else {}


def _config_file_stat(path: Path) -> os.stat_result | None:
    """Probe configuration files without treating failed metadata reads as absence."""
    try:
        info = path.stat()
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as exc:
        warnings.warn(
            f"Could not read {path}: {exc}. Its settings are ignored.",
            stacklevel=2,
        )
        return None
    return info if stat.S_ISREG(info.st_mode) else None


def _walk_up(start: Path, name: str) -> Path | None:
    for directory in [start, *start.parents]:
        candidate = directory / name
        if _config_file_stat(candidate) is not None:
            return candidate
    return None


def read_project_config(directory: str | Path) -> dict[str, Any]:
    """Read the ``lixity.toml`` beside ``directory`` without walking up.

    Read-only probes (the Open Project chooser) need exactly this folder's
    configuration; ancestor or user settings must not leak into that answer.
    Oversized files are ignored instead of parsed.
    """
    path = Path(directory) / "lixity.toml"
    info = _config_file_stat(path)
    if info is not None and info.st_size <= 65536:
        return _load_toml(path)
    return {}


def read_explicit_project_config(directory: str | Path) -> dict[str, Any]:
    """Read only this root's settings; selection must not ignore invalid config.

    Unlike ordinary analysis loading, this strict read never consults user or
    ancestor files. Existing TOML/stat warnings become actionable errors.
    """
    settings: dict[str, Any] = {}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            for name in ("pyproject.toml", "lixity.toml"):
                path = Path(directory) / name
                try:
                    info = path.lstat()
                except FileNotFoundError:
                    continue
                if stat.S_ISLNK(info.st_mode):
                    info = path.stat()
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError(f"Project configuration must be a regular file: {path}")
                settings.update(_load_toml(path, text=FileUtils.read_file(str(path))))
    except (UserWarning, OSError) as exc:
        raise ValueError(f"Could not resolve project configuration: {exc}") from exc
    return {key: value for key, value in settings.items() if key in TOOL_KEYS}


def load_project_config(start: str | Path | None = None) -> dict[str, Any]:
    """
    Merge user config under project config under nothing else.
    Returns only known keys present in either file. Identity, publication and
    chapter registers and character profiles are explicit project data, never inherited from user
    settings, ancestor folders or an implicit cwd.
    """
    here = Path(start).resolve() if start else Path.cwd()
    if here.is_file():
        here = here.parent

    merged: dict[str, Any] = {}
    user = Path(os.path.expanduser("~/.config/lixity.toml"))
    if _config_file_stat(user) is not None:
        merged.update(_load_toml(user))
        for key in PROJECT_ONLY_KEYS:
            merged.pop(key, None)

    project = _walk_up(here, "pyproject.toml")
    if project is not None:
        settings = _load_toml(project)
        if start is None or project.parent != here:
            for key in PROJECT_ONLY_KEYS:
                settings.pop(key, None)
        merged.update(settings)

    local = _walk_up(here, "lixity.toml")
    if local is not None and local != project:
        settings = _load_toml(local)
        if start is None or local.parent != here:
            for key in PROJECT_ONLY_KEYS:
                settings.pop(key, None)
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

ANALYSIS_SETTINGS_KEYS = ("language", *THRESHOLD_KEYS)


def configuration_metadata() -> dict[str, Any]:
    """Describe installed configuration without discovering any project values.

    The component schemas expose defaults and local field constraints. They do
    not replace the existing validators or model the entire project file.
    """
    from .characters import character_configuration_schema
    from .style_fingerprint import FingerprintThresholds

    corpus_schema = CorpusConfig.model_json_schema()
    for key, value in CorpusConfig().model_dump().items():
        corpus_schema["properties"][key].setdefault("default", value)
    properties: dict[str, dict[str, Any]] = {}
    defaults = asdict(FingerprintThresholds())
    for key in THRESHOLD_KEYS:
        value = defaults[key]
        kind = "number" if key in FingerprintThresholds.numeric_inputs else "integer" if isinstance(value, int) else "string"
        field: dict[str, Any] = {"type": kind, "default": value}
        if key in FingerprintThresholds.numeric_inputs:
            policy = FingerprintThresholds.numeric_inputs[key]
            field["exclusiveMinimum" if policy.minimum_exclusive else "minimum"] = policy.minimum
            if policy.maximum is not None:
                field["exclusiveMaximum" if policy.maximum_exclusive else "maximum"] = policy.maximum
        properties[key] = field
    properties["min_chapters"]["minimum"] = FingerprintThresholds.minimum_chapters
    properties["flag_min_severity"]["enum"] = list(FingerprintThresholds.flag_severities)
    properties["fdr_method"]["enum"] = list(FingerprintThresholds.fdr_methods)
    return {
        "schema_version": "lixity-configuration/1",
        "accepted_keys": sorted(TOOL_KEYS),
        "uninterpreted_keys": sorted(UNINTERPRETED_KEYS),
        "project_only_keys": list(PROJECT_ONLY_KEYS),
        "scope": (
            "Accepted keys describe the project loader, not one validation schema. "
            "The component schemas cover CorpusConfig, FingerprintThresholds, PublicationSettings and character profiles; "
            "component validators also enforce rules such as valid register assignments. "
            "Other keys use their owning component's validation. Defaults are annotations, "
            "not effective project or server-session values. Project-only keys require an "
            "explicit root selection and exclude user or ancestor defaults."
        ),
        "corpus_schema": corpus_schema,
        "publication_schema": publication_configuration_schema(),
        "characters_schema": character_configuration_schema(),
        "threshold_schema": {
            "type": "object", "properties": properties, "additionalProperties": False,
            "$comment": (
                "Numeric thresholds must be finite. Defaults are annotations. "
                "FingerprintThresholds also validates z_mild <= z_strong after applying "
                "defaults; this cross-field rule is not encoded in JSON Schema."
            ),
        },
        "native_settings": {
            "persisted_keys": list(PERSISTED_SETTINGS_KEYS),
            "session_keys": list(ANALYSIS_SETTINGS_KEYS),
            "optional_persistence": {
                "flag": "save_analysis_defaults", "default": False,
                "keys": list(ANALYSIS_SETTINGS_KEYS), "requires_project_token": True,
                "scope": (
                    "When explicitly true, saves only posted language and threshold fields "
                    "to the selected project's lixity.toml in the existing settings transaction. "
                    "Requires an explicit project and its current project_token; absent or "
                    "false preserves session-only analysis settings."
                ),
            },
            "scope": (
                "Editable POST /api/settings fields, not a list of rendered controls. "
                "Persistence requires the selected project; publication and chapter registers "
                "also require its current project token. Language and thresholds remain in the "
                "session unless optional persistence is explicitly requested."
            ),
        },
    }


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
