"""Bounded, read-only metadata inspection of an explicitly selected project.

``lixity-project-structure/1`` describes conventional roles, not new role bindings
or a verified archive. Role states are available, missing, unassigned, invalid,
ambiguous, unreadable, unsafe and unknown. Availability describes filesystem
metadata only. Existing artifacts always have unknown provenance: names, mtimes
and embedded claims do not establish their producing source or product version.

Issues contain only a stable code, severity and nullable project-relative path.
Codes cover config (invalid-config, unsafe-config, config-unreadable,
config-too-large), source selection (manuscript-missing, manuscript-unassigned,
manuscript-ambiguous, manuscript-invalid, manuscript-unreadable,
manuscript-unsafe, manuscript-selection-mismatch, manuscript-in-outputs), roles
(role-not-directory, role-symlink, role-unreadable), artifacts
(artifact-symlink-broken, artifact-path-escape, artifact-not-file,
artifact-unreadable, artifact-name-invalid, output-source-alias,
output-config-alias), and limits (inventory-truncated, discovery-truncated).

Inspection neither reads manuscript/artifact bytes nor opens Research snapshots.
Only bounded root-local configuration is parsed through the shared readers.
The metadata observations are not atomic and never authorize a later download:
transport handlers must recheck the selected context and file at use time.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ProjectConfigTooLargeError, read_explicit_project_config
from .workspace import (
    ARCHIVE_DIRNAME,
    EXPORTS_DIRNAME,
    MANUSCRIPT_FILENAMES,
    AmbiguousManuscriptError,
    configured_manuscript,
    discover,
)

PROJECT_STRUCTURE_SCHEMA = "lixity-project-structure/1"
MAX_CONFIG_BYTES = 1024 * 1024
MAX_ARTIFACTS = 200
MAX_SCANNED_ENTRIES = 2000
_CONFIG_FILES = ("pyproject.toml", "lixity.toml")
Issue = dict[str, Any]


def _issue(issues: list[Issue], code: str, path: str | None, severity: str = "error") -> None:
    item = {"code": code, "severity": severity, "path": path}
    if item not in issues:
        issues.append(item)


def _configuration(root: Path, issues: list[Issue]) -> tuple[dict[str, Any] | None, str, bool]:
    state = "available"
    truncated = False
    for name in _CONFIG_FILES:
        path = root / name
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            _issue(issues, "config-unreadable", name)
            state = "unreadable"
            continue
        if stat.S_ISLNK(info.st_mode):
            _issue(issues, "unsafe-config", name)
            state = "unsafe"
        elif not stat.S_ISREG(info.st_mode):
            _issue(issues, "invalid-config", name)
            state = "invalid"
        elif not os.access(path, os.R_OK):
            _issue(issues, "config-unreadable", name)
            state = "unreadable"
        elif info.st_size > MAX_CONFIG_BYTES:
            _issue(issues, "config-too-large", name, "warning")
            truncated = True
            if state == "available":
                state = "unknown"
    if state != "available":
        return None, state, truncated
    try:
        return read_explicit_project_config(root, maximum_bytes=MAX_CONFIG_BYTES), state, truncated
    except ProjectConfigTooLargeError:
        _issue(issues, "config-too-large", None, "warning")
        return None, "unknown", True
    except (OSError, ValueError):
        _issue(issues, "invalid-config", None)
        return None, "invalid", truncated


def _source_path(root: Path, value: str | Path) -> tuple[Path, str]:
    path = Path(value).expanduser()
    if ".." in path.parts or "\0" in os.fspath(path):
        raise ValueError("Unsafe manuscript path")
    path = path if path.is_absolute() else root / path
    relative = path.relative_to(root).as_posix()
    path.resolve().relative_to(root)
    if relative == ".":
        raise ValueError("A manuscript must be a file")
    relative.encode("utf-8")
    return path, relative


def _discover(root: Path, settings: dict[str, Any], issues: list[Issue]) -> tuple[str | None, str, bool]:
    try:
        conventional = any((root / name).is_file() for name in (f"{root.name}.md", *MANUSCRIPT_FILENAMES))
        names: list[str] = []
        if not conventional:
            with os.scandir(root) as entries:
                for number, entry in enumerate(entries, 1):
                    if number >= MAX_SCANNED_ENTRIES:
                        _issue(issues, "discovery-truncated", None, "warning")
                        return None, "unknown", True
                    names.append(entry.name)
        return discover(root=str(root), project_config=settings, entry_names=names).manuscript, "available", False
    except AmbiguousManuscriptError:
        _issue(issues, "manuscript-ambiguous", None)
        return None, "ambiguous", False
    except FileNotFoundError:
        _issue(issues, "manuscript-unassigned", None, "info")
        return None, "unassigned", False
    except OSError:
        _issue(issues, "manuscript-unreadable", None)
        return None, "unreadable", False
    except (RuntimeError, ValueError):
        _issue(issues, "manuscript-invalid", None)
        return None, "invalid", False


def _configured_source(root: Path, settings: dict[str, Any] | None,
                       issues: list[Issue]) -> tuple[Path | None, str | None, str]:
    if settings is None or "manuscript" not in settings:
        return None, None, "unassigned"
    value = settings["manuscript"]
    if not isinstance(value, str) or not value.strip():
        _issue(issues, "manuscript-invalid", None)
        return None, None, "invalid"
    try:
        configured = configured_manuscript(root, project_config=settings)
        if configured is None:
            raise ValueError("Configuration changed during inspection")
        path, relative = _source_path(root, configured)
        return path, relative, "available"
    except (OSError, RuntimeError, ValueError):
        _issue(issues, "manuscript-unsafe", None)
        return None, None, "unsafe"


def _source_state(path: Path, relative: str, issues: list[Issue]) -> str:
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            _issue(issues, "manuscript-invalid", relative)
            return "invalid"
        if not os.access(path, os.R_OK):
            _issue(issues, "manuscript-unreadable", relative)
            return "unreadable"
        return "available"
    except FileNotFoundError:
        _issue(issues, "manuscript-missing", relative)
        return "missing"
    except OSError:
        _issue(issues, "manuscript-unreadable", relative)
        return "unreadable"


def _manuscript(root: Path, selected: str | Path | None, settings: dict[str, Any] | None,
                config_state: str, issues: list[Issue]) -> tuple[dict[str, Any], list[Path], bool]:
    role: dict[str, Any] = {"role": "manuscript", "path": None, "state": config_state,
                            "selection": "none", "configured_path": None}
    configured, configured_relative, configured_state = _configured_source(root, settings, issues)
    sources = [configured] if configured is not None else []
    if settings is not None and "manuscript" in settings:
        role["state"] = configured_state
        role["configured_path"] = configured_relative
    truncated = False
    candidate: str | Path | None = selected if selected is not None else configured
    if selected is not None:
        role["selection"] = "selected"
    elif configured is not None:
        role["selection"] = "configured"
    elif settings is not None and "manuscript" not in settings:
        candidate, role["state"], truncated = _discover(root, settings, issues)
        if candidate is not None:
            role["selection"] = "discovered"
    if candidate is None:
        return role, sources, truncated
    try:
        path, relative = _source_path(root, candidate)
    except (OSError, RuntimeError, ValueError):
        role["state"] = "unsafe"
        _issue(issues, "manuscript-unsafe", None)
        return role, sources, truncated
    role["path"] = relative
    if selected is not None and configured is not None and path.resolve() != configured.resolve():
        _issue(issues, "manuscript-selection-mismatch", relative, "warning")
        if configured_relative is not None:
            _source_state(configured, configured_relative, issues)
    role["state"] = _source_state(path, relative, issues)
    if path not in sources:
        sources.append(path)
    if Path(relative).parts[0] == EXPORTS_DIRNAME:
        _issue(issues, "manuscript-in-outputs", relative, "warning")
    return role, sources, truncated


def _directory(root: Path, role: str, relative: str, issues: list[Issue]) -> dict[str, Any]:
    result = {"role": role, "path": relative, "state": "available"}
    current = root
    for part in Path(relative).parts:
        current /= part
        try:
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode):
                result["state"] = "unsafe"
                _issue(issues, "role-symlink", relative)
                break
            if not stat.S_ISDIR(info.st_mode):
                result["state"] = "invalid"
                _issue(issues, "role-not-directory", relative)
                break
            if not os.access(current, os.R_OK | os.X_OK):
                result["state"] = "unreadable"
                _issue(issues, "role-unreadable", relative)
                break
        except FileNotFoundError:
            result["state"] = "missing"
            break
        except OSError:
            result["state"] = "unreadable"
            _issue(issues, "role-unreadable", relative)
            break
    return result


def _identity(path: Path) -> tuple[int, int] | None:
    info = path.stat()
    return (info.st_dev, info.st_ino) if info.st_ino else None


@dataclass
class _Protection:
    paths: dict[Path, set[str]]
    identities: dict[tuple[int, int], set[str]]
    complete: bool


def _protection(root: Path, sources: list[Path], config_state: str, issues: list[Issue]) -> _Protection:
    """Collect protected identities once per operation, without directory scans."""
    result = _Protection({}, {}, config_state == "available")
    selected = [(source, "output-source-alias") for source in sources]
    selected.extend((root / name, "output-config-alias") for name in _CONFIG_FILES)
    for path, code in selected:
        relative = path.relative_to(root).as_posix()
        try:
            info = path.lstat()
            if code == "output-config-alias" and stat.S_ISLNK(info.st_mode):
                # Unsafe settings must never be followed while checking aliases.
                result.complete = False
                continue
            result.paths.setdefault(path.resolve(), set()).add(code)
            identity = _identity(path)
            if identity is None:
                result.complete = False
                _issue(issues, "artifact-unreadable", relative)
            else:
                result.identities.setdefault(identity, set()).add(code)
        except FileNotFoundError:
            result.paths.setdefault(path, set()).add(code)
        except (OSError, RuntimeError, ValueError):
            result.complete = False
            _issue(issues, "config-unreadable" if code == "output-config-alias" else "manuscript-unreadable", relative)
    return result


def _artifact(root: Path, path: Path, protected: _Protection,
              issues: list[Issue]) -> dict[str, Any] | None:
    relative = path.relative_to(root).as_posix()
    result: dict[str, Any] = {"name": path.name, "path": relative, "size_bytes": None,
                              "provenance": "unknown", "downloadable": False}
    try:
        relative.encode("utf-8")
    except UnicodeEncodeError:
        _issue(issues, "artifact-name-invalid", None, "warning")
        return None
    try:
        resolved = path.resolve()
        alias = False
        for code in sorted(protected.paths.get(resolved, set())):
            _issue(issues, code, relative)
            alias = True
        if not resolved.is_relative_to(root / EXPORTS_DIRNAME):
            _issue(issues, "artifact-path-escape", relative)
            return result
        info = path.stat()
        if stat.S_ISDIR(info.st_mode):
            return None  # The inventory is flat; it does not classify nested folders.
        if not stat.S_ISREG(info.st_mode):
            _issue(issues, "artifact-not-file", relative, "warning")
            return result
        result["size_bytes"] = info.st_size
        identity = (info.st_dev, info.st_ino)
        for code in sorted(protected.identities.get(identity, set())):
            _issue(issues, code, relative)
            alias = True
        if not os.access(path, os.R_OK):
            _issue(issues, "artifact-unreadable", relative)
        else:
            result["downloadable"] = not alias and protected.complete
    except FileNotFoundError:
        _issue(issues, "artifact-symlink-broken" if path.is_symlink() else "artifact-unreadable",
               relative, "warning")
    except (OSError, RuntimeError, ValueError):
        _issue(issues, "artifact-unreadable", relative)
    return result


def _artifacts(root: Path, role: dict[str, Any], protected: _Protection,
               issues: list[Issue]) -> tuple[list[dict[str, Any]], bool]:
    if role["state"] != "available":
        return [], False
    items = []
    truncated = False
    try:
        with os.scandir(root / EXPORTS_DIRNAME) as entries:
            for number, entry in enumerate(entries, 1):
                if entry.name != ARCHIVE_DIRNAME:
                    item = _artifact(root, Path(entry.path), protected, issues)
                    if item is not None:
                        items.append(item)
                if number >= MAX_SCANNED_ENTRIES:
                    truncated = True
                    break
    except OSError:
        role["state"] = "unreadable"
        _issue(issues, "role-unreadable", EXPORTS_DIRNAME)
    if len(items) > MAX_ARTIFACTS:
        truncated = True
    if truncated:
        _issue(issues, "inventory-truncated", EXPORTS_DIRNAME, "warning")
    items.sort(key=lambda item: (item["name"].casefold(), item["name"]))
    return items[:MAX_ARTIFACTS], truncated


def inspect_project(project: str | Path, *, selected_manuscript: str | Path | None = None) -> dict[str, Any]:
    """Inspect current metadata, preserving findings and unknown observations.

    The root must be an existing directory. Findings retain ``ok: true``;
    ``has_errors`` reflects error-severity issues rather than absence of optional
    roles. Config reads stop above 1 MiB per file. Root discovery and flat output
    scans stop at 2,000 entries, returning at most 200 output files. Reaching a
    scan boundary conservatively marks the inspection incomplete, even when the
    boundary could coincide with the end of that directory. No folders are made.
    """
    root = Path(project).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Project root must be an existing directory")
    issues: list[Issue] = []
    settings, config_state, truncated = _configuration(root, issues)
    manuscript, sources, source_truncated = _manuscript(root, selected_manuscript, settings, config_state, issues)
    outputs = _directory(root, "outputs", EXPORTS_DIRNAME, issues)
    roles = [manuscript, _directory(root, "research", "research", issues), outputs,
             _directory(root, "output_archive", f"{EXPORTS_DIRNAME}/{ARCHIVE_DIRNAME}", issues),
             {"role": "submissions", "path": None, "state": "unassigned"}]
    protected = _protection(root, sources, config_state, issues)
    if ((manuscript["path"] is None and manuscript["state"] != "unassigned")
            or (settings is not None and "manuscript" in settings and manuscript["configured_path"] is None)):
        protected.complete = False
    artifacts, output_truncated = _artifacts(root, outputs, protected, issues)
    return {"schema_version": PROJECT_STRUCTURE_SCHEMA, "ok": True,
            "has_errors": any(issue["severity"] == "error" for issue in issues),
            "root": str(root), "roles": roles, "artifacts": artifacts, "issues": issues,
            "truncated": truncated or source_truncated or output_truncated}


def project_artifact_path(project: str | Path, name: str, *,
                          selected_manuscript: str | Path | None = None) -> Path:
    """Resolve one eligible flat output without an output inventory.

    The name is already decoded by the transport. Source/configuration aliases,
    escaped or broken links, special nodes and unavailable identity checks fail.
    Without a selected or configured source, bounded shared discovery identifies
    the source to protect; ambiguous or incomplete discovery fails closed.
    The caller must still perform its bounded descriptor read and context checks;
    a returned pathname is not an atomic filesystem authorization.
    """
    if not name or name in {".", ".."} or any(part in name for part in ("/", "\\", "\0")):
        raise ValueError("Artifact name must be one filename")
    name.encode("utf-8")
    root = Path(project).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Project root must be an existing directory")
    issues: list[Issue] = []
    settings, config_state, _ = _configuration(root, issues)
    if settings is None:
        raise ValueError("Project configuration cannot be safely inspected")
    configured, _, configured_state = _configured_source(root, settings, issues)
    if configured_state not in {"available", "unassigned"}:
        raise ValueError("Configured manuscript cannot be safely inspected")
    sources = [configured] if configured is not None else []
    if selected_manuscript is not None:
        selected, _ = _source_path(root, selected_manuscript)
        if selected not in sources:
            sources.append(selected)
    elif configured is None:
        manuscript, sources, _ = _manuscript(root, None, settings, config_state, issues)
        if manuscript["path"] is None and manuscript["state"] != "unassigned":
            raise ValueError("Manuscript selection cannot be safely determined")
    role = _directory(root, "outputs", EXPORTS_DIRNAME, issues)
    if role["state"] != "available":
        raise ValueError("Output directory is unavailable")
    protected = _protection(root, sources, config_state, issues)
    item = _artifact(root, root / EXPORTS_DIRNAME / name, protected, issues)
    if item is None or not item["downloadable"]:
        raise ValueError("Artifact is not eligible for download")
    target = (root / EXPORTS_DIRNAME / name).resolve(strict=True)
    if not target.is_relative_to(root / EXPORTS_DIRNAME) or not target.is_file():
        raise ValueError("Artifact path changed during inspection")
    return target
