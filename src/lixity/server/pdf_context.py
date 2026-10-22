"""Opaque metadata tokens for selected manuscript and research contexts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from ..config import project_config_snapshot
from ..style_fingerprint import FingerprintThresholds


def _project_config_context(
    root: Path, config_bytes: bytes | None = None, *, maximum_bytes: int | None = None,
) -> dict[str, str]:
    """Include selected-root metadata without returning file content or paths."""
    def digest(name: str) -> str:
        try:
            if name == "lixity.toml" and config_bytes is not None:
                content = config_bytes
                if maximum_bytes is not None and len(content) > maximum_bytes:
                    return "unsupported"
            else:
                identity, content = project_config_snapshot(root / name, maximum_bytes=maximum_bytes)
                if identity is None:
                    return "absent"
            return hashlib.sha256(content).hexdigest()
        except ValueError:
            return "unsupported"
        except OSError:
            return "unreadable"
    return {name: digest(name) for name in ("lixity.toml", "pyproject.toml")}


def project_settings_token(
    project_root: str | Path | None, source_input: str | None,
    *, config_bytes: bytes | None = None, maximum_config_bytes: int | None = None,
) -> str:
    """Bind metadata saves to the selected root and its observed configuration."""
    if project_root is None:
        return ""
    root = Path(project_root).resolve()
    context = {
        "root": str(root), "source": str(Path(source_input).resolve()) if source_input else None,
        "configuration": _project_config_context(root, config_bytes, maximum_bytes=maximum_config_bytes),
    }
    return hashlib.sha256(json.dumps(context, sort_keys=True).encode("utf-8")).hexdigest()


def research_context_token(project_root: str | Path | None) -> str:
    """Identify the selected archive root, including research-only workspaces.

    This is a context guard, not an authentication credential or content digest.
    Restored copies can share a project ID and snapshot while having different
    selected roots; a stale tab must not write to a different selected copy.
    """
    if project_root is None:
        return ""
    context = {"research_root": str(Path(project_root).resolve())}
    return hashlib.sha256(json.dumps(context, sort_keys=True).encode("utf-8")).hexdigest()


def manuscript_pdf_token(
    source_input: str | None, *, project_root: str | Path | None,
    language: str, title: str | None, thresholds: FingerprintThresholds,
    config_bytes: bytes | None = None,
) -> str:
    """Bind a download to selected server metadata without exposing local paths.

    This identifies the selection, not manuscript content. The download reads
    the selected file when requested instead of retaining a rendered text copy.
    """
    if not source_input:
        return ""
    source = Path(source_input).resolve()
    root = Path(project_root).resolve() if project_root is not None else source.parent
    context = {
        "source": str(source), "root": str(root), "language": language,
        "title": title, "thresholds": asdict(thresholds),
        "configuration": _project_config_context(root, config_bytes),
    }
    encoded = json.dumps(context, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
