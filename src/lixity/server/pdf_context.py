"""Opaque metadata tokens for selected manuscript and research contexts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from ..style_fingerprint import FingerprintThresholds


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
    }
    encoded = json.dumps(context, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
