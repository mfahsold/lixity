"""Explicit, bounded snapshots of one project using the native read-only UI.

The result is a reading website, not a restorable research archive. Source
retention does not establish redistribution rights. Exporting never publishes
online or writes into the selected project.
"""

from __future__ import annotations

import ctypes
import errno
import hashlib
import io
import json
import os
import stat
import sys
import tempfile
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlencode

from ._version import __version__
from .characters import presence_report, resolve_character_settings
from .config import read_explicit_project_config, resolve_thresholds, validate_author_name
from .io import FileUtils
from .markdown_parser import _without_comments, split_chapters
from .markers import list_markers
from .pipeline import analyze_document, resolve_document_config, supplementary_reports
from .project_identity import manuscript_identity_check, project_title
from .research import api, editorial
from .research.images import IMAGE_TYPES, read_image, resolve_dossier_images, resolve_dossier_media
from .research.manuscript import (
    manuscript_links_data,
    manuscript_review_data,
    manuscript_terms_data,
)
from .research.media import MEDIA_TYPES, VIDEO_TYPES
from .research.models import (
    Dossier,
    EvidenceLink,
    Head,
    Manifest,
    Passage,
    SourceVersion,
    Tombstone,
)
from .research.repository import Repository, ResearchConflictError, ResearchError, Snapshot
from .research.revisions import (
    KINDS,
    _record,
    _record_history,
    _section_text,
    _view,
    dossier_withdrawal,
)
from .research.timeline import timeline_data
from .site_contracts import (
    DATA_SCHEMA,
    MAX_SITE_BYTES,
    MAX_SITE_DATA_BYTES,
    MAX_SITE_RESPONSES,
    MAX_SITE_REVISIONS,
    SITE_ANALYSIS_SCHEMA,
    SITE_SCHEMA,
    AnalysisSection,
    SiteData,
    SiteExportOptions,
    SiteManifest,
    SiteMode,
)
from .site_preflight import media_summary, preflight_report
from .site_publications import resolve_site_publication
from .style_fingerprint import FingerprintThresholds
from .ui import render_analysis
from .ui.dashboard import _script_json
from .ui.manuscript_document import ReaderBlock, reader_blocks
from .workspace import resolve_manuscript_target


def _json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def _checksum(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name and not path.is_absolute() and ".." not in path.parts
                and "\\" not in name and "\0" not in name and ":" not in name
                and path.as_posix() == name)


class SiteExportLimitError(ResearchError):
    """A first bounded preparation failure, not an estimate of a complete site."""

    def __init__(self, category: str, observed: int, limit: int, *, unit: str = "bytes",
                 context: dict[str, Any] | None = None) -> None:
        suggestions = ([] if category == "publication_bytes" else [
            "Use --mode review without --include-research for a manuscript-only copy."])
        if category != "research_record_bytes":
            suggestions.append(
                "Use --mode reader or --mode companion with --publication-profile NAME to select fewer or "
                "smaller dossier entries for the reading copy.")
        # Prepared responses include records and authored history even without
        # original assets. Only the separate bundle budget warrants this hint.
        if category == "bundle_bytes":
            suggestions.append(
                "If --include-source-files is enabled, omit it when original source assets are not needed; "
                "the remaining HTML and selected content must still fit the bundle limit.")
        location = ""
        if context:
            if context.get("response_route"):
                location = f" Response: {context['response_route']}"
                parameters = context.get("response_parameters", {})
                if parameters:
                    location += " (" + ", ".join(f"{key}={value}" for key, value in parameters.items()) + ")"
                location += "."
            elif context.get("asset"):
                location = f" Asset: {context['asset']}."
            elif context.get("record_id"):
                location = f" Record: {context['record_kind']} {context['record_id']}."
        message = (f"Website export limit {category}: observed {observed:,} {unit}; "
                   f"limit {limit:,}; overflow {observed - limit:,}.{location} "
                   "Preparation stopped at the first limit crossing; total package size is unknown; "
                   "no output written. " + " ".join(suggestions))
        self.diagnostic: dict[str, Any] = {
            "schema_version": "lixity-site-preflight-error/1", "ok": False,
            "complete": False, "measurement": "first_limit_crossing", "files_written": False,
            "limit": category, f"limit_{unit}": limit, f"observed_{unit}": observed,
            f"overflow_{unit}": observed - limit, "message": message,
            "suggestions": suggestions, **(context or {}),
        }
        super().__init__(message)


@dataclass(frozen=True)
class SiteBundle:
    """A complete local candidate; names never address the source filesystem."""

    files: dict[str, bytes]
    manifest: dict[str, Any]
    media_summary: dict[str, int] = field(default_factory=dict)

    def preflight(self) -> dict[str, Any]:
        """Report actual package sizes without writing or downloading files."""
        return preflight_report(self)

    def _validate(self) -> None:
        SiteManifest.model_validate(self.manifest)
        if any(not _safe_member(name) or not isinstance(content, bytes) for name, content in self.files.items()):
            raise ResearchError("Website bundle has unsafe paths or non-byte file contents")
        size = sum(len(content) for content in self.files.values())
        if size > MAX_SITE_BYTES:
            raise SiteExportLimitError("bundle_bytes", size, MAX_SITE_BYTES)
        if (self.files.get("manifest.json") != _json(self.manifest)
                or set(self.files) != set(self.manifest["files"]) | {"manifest.json"}):
            raise ResearchError("Website manifest or file inventory changed after preparation")
        for name, item in self.manifest["files"].items():
            content = self.files.get(name)
            if content is None or len(content) != item["byte_length"] or _checksum(content) != item["sha256"]:
                raise ResearchError("Website bundle changed after preparation")

    def to_zip(self) -> bytes:
        """Return a portable ZIP of the same verified files as directory export."""
        self._validate()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(self.files):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, self.files[name])
        return buffer.getvalue()


def _public_data(value: Any) -> Any:
    """Omit local operational identities; never rewrite authored prose strings."""
    if isinstance(value, dict):
        return {key: _public_data(item) for key, item in value.items()
                if key not in {"project_root", "external_reference", "ocr", "output_path"}}
    if isinstance(value, list):
        return [_public_data(item) for item in value]
    return value


def _config_state(repository: Repository) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name in ("pyproject.toml", "lixity.toml"):
        path = repository.safe(repository.root / name)
        if not path.exists():
            result[name] = None
            continue
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_SITE_DATA_BYTES:
            raise ResearchError("Project settings must be bounded regular files")
        result[name] = _checksum(repository.read(path, maximum=MAX_SITE_DATA_BYTES))
    return result


def _snapshot(repository: Repository, *, include_history: bool) -> Snapshot:
    """Bound retained input bytes and the authored history actually being exported."""
    head = Head.model_validate_json(repository.read(repository.data / "HEAD.json", maximum=4096))
    manifest = Manifest.model_validate_json(repository.read_manifest(head.sha256))
    if include_history:
        authored_revisions = sum(entry.kind in KINDS for entry in manifest.entries)
        if authored_revisions > MAX_SITE_REVISIONS:
            raise SiteExportLimitError("research_authored_revision_count", authored_revisions,
                                       MAX_SITE_REVISIONS, unit="count")
    total = 0
    for entry in manifest.entries:
        path = repository.record_path(entry)
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise ResearchError("Research export requires regular record files")
        total += info.st_size
        if total > MAX_SITE_DATA_BYTES:
            raise SiteExportLimitError("research_record_bytes", total, MAX_SITE_DATA_BYTES,
                                       context={"record_kind": entry.kind, "record_id": entry.ref.id,
                                                "record_revision": entry.ref.revision})
    snapshot = repository.snapshot()
    if snapshot.digest != head.sha256:
        raise ResearchConflictError("Research changed during website preparation; retry the export")
    return snapshot


def _software_notices() -> dict[str, bytes]:
    files = {}
    package = Path(__file__).parent
    for path in (package / "ui/assets/vendor").glob("*.LICENSE"):
        files["licenses/" + path.name] = path.read_bytes()
    license_path = package.parents[1] / "LICENSE"
    if license_path.is_file():
        files["licenses/Lixity-LICENSE"] = license_path.read_bytes()
    else:
        # A checkout added to sys.path must not shadow the loaded installation.
        for distribution in metadata.distributions(name="lixity", path=[str(package.parent)]):
            for entry in distribution.files or ():
                if (entry.parts and entry.parts[0].endswith(".dist-info")
                        and entry.parts[1:] in (("LICENSE",), ("licenses", "LICENSE"))):
                    files["licenses/Lixity-LICENSE"] = Path(str(distribution.locate_file(entry))).read_bytes()
                    break
            if "licenses/Lixity-LICENSE" in files:
                break
    if "licenses/Lixity-LICENSE" not in files:
        raise ResearchError("The installed Lixity license is unavailable; repair the installation before exporting")
    return files


class _Reads:
    """Bounded exact native response routes for the frozen browser provider."""

    def __init__(self, token: str):
        self.token = token
        self.responses: dict[str, Any] = {}
        self.size = 0
        self.bytes_by_route: dict[str, int] = {}

    def add(self, route: str, payload: Any, *, companion: bool = False, **query: Any) -> None:
        public = _public_data(payload)
        parameters = {key: str(value) for key, value in query.items()}
        variants = [parameters, {**parameters, "research_token": self.token}]
        if companion:
            variants += [{**parameters, "project_token": self.token},
                         {**parameters, "project_token": self.token, "research_token": self.token}]
        payload_size = len(_json(public))
        for values in variants:
            path = "/api/research/" + route
            if values:
                path += "?" + urlencode(sorted(values.items()))
            if path in self.responses:
                continue
            response_bytes = payload_size + len(path)
            attempted = self.size + response_bytes
            context = {"response_route": "/api/research/" + route,
                       "response_parameters": {key: value for key, value in parameters.items()
                                               if key in {"id", "kind", "revision", "dossier_id", "claim_id"}},
                       "accepted_responses": len(self.responses), "accepted_bytes": self.size,
                       "response_bytes": response_bytes, "accepted_by_route_bytes": dict(self.bytes_by_route)}
            if len(self.responses) >= MAX_SITE_RESPONSES:
                raise SiteExportLimitError("research_response_count", len(self.responses) + 1,
                                           MAX_SITE_RESPONSES, unit="count", context=context)
            if attempted > MAX_SITE_DATA_BYTES:
                raise SiteExportLimitError("research_response_bytes", attempted, MAX_SITE_DATA_BYTES, context=context)
            self.size = attempted
            self.bytes_by_route[route] = self.bytes_by_route.get(route, 0) + response_bytes
            self.responses[path] = public


def _retain_source(repository: Repository, snapshot: Snapshot, version: SourceVersion,
                   files: dict[str, bytes], resources: dict[str, str]) -> None:
    """Copy one exact approved blob and register only its safe static mappings."""
    extension = {"image/png": ".png", "image/jpeg": ".jpg", "application/pdf": ".pdf", "video/mp4": ".mp4", "video/webm": ".webm",
                 "text/plain": ".txt"}.get(version.blob.media_type)
    if extension is None:
        raise ResearchError("Unsupported retained source media type for website export")
    path = "assets/sources/" + version.blob.sha256 + extension
    if path not in files:
        if sum(map(len, files.values())) + version.blob.byte_length > MAX_SITE_BYTES:
            raise SiteExportLimitError("bundle_bytes", sum(map(len, files.values())) + version.blob.byte_length,
                                       MAX_SITE_BYTES, context={"asset": path})
        files[path] = (read_image(repository, snapshot, project_id=snapshot.project.id,
            source_id=version.source_ref.id, version_id=version.id, media=version.blob.media_type in VIDEO_TYPES)["content"]
            if version.blob.media_type in IMAGE_TYPES | VIDEO_TYPES else repository.read_blob(version.blob))
    resources["/api/site-resource?" + urlencode(sorted({
        "source_id": version.source_ref.id, "version_id": version.id}.items()))] = path
    if version.blob.media_type in IMAGE_TYPES:
        resources["/api/research/image?" + urlencode(sorted({"project_id": snapshot.project.id,
            "source_id": version.source_ref.id, "version_id": version.id}.items()))] = path
    elif version.blob.media_type in MEDIA_TYPES:
        resources["/api/research/media?" + urlencode(sorted({"project_id": snapshot.project.id,
            "source_id": version.source_ref.id, "version_id": version.id}.items()))] = path


def _publication(repository: Repository, snapshot: Snapshot, text: str, config: Any,
                 source_hash: str, settings: dict[str, Any], options: SiteExportOptions,
                 files: dict[str, bytes]) -> tuple[dict[str, Any], dict[str, str], list[ReaderBlock] | None]:
    """Project only explicit reader selections before any output is assembled."""
    chapters = split_chapters(text, config)
    profile, cap = resolve_site_publication(settings.get("site_publications", {}),
        str(options.publication_profile), chapter_count=len(chapters), max_chapter=options.max_chapter)
    entries: list[dict[str, Any]] = []
    resources: dict[str, str] = {}
    size = len(profile.introduction.encode("utf-8")) + len(profile.title.encode("utf-8"))
    for selected in profile.entries:
        if selected.reveal_after_chapter > cap:
            continue
        dossier = _record(snapshot, "dossier", selected.dossier_id, selected.revision)
        if not isinstance(dossier, Dossier):
            raise ResearchError("Publication selections must reference dossiers")
        body = _section_text(dossier.body, selected.section) if selected.section is not None else dossier.body
        images = [*resolve_dossier_images(snapshot, body), *resolve_dossier_media(snapshot, body)]
        public_images = []
        for image in images:
            if image["availability"] != "available":
                raise ResearchError("A selected publication image is missing, withdrawn or purged")
            public_images.append({key: image[key] for key in (
                "project_id", "source_id", "source_version_id", "alt", "url", "availability", "media_type")})
            if options.include_source_files:
                version = snapshot.records[image["source_version_id"]]
                if not isinstance(version, SourceVersion):
                    raise ResearchError("Publication image provenance is unavailable")
                _retain_source(repository, snapshot, version, files, resources)
        citations = []
        if selected.include_citations:
            # Dossier evidence has whole-record scope, including for a selected
            # section. The profile flag explicitly selects that exact ref list.
            for ref in dict.fromkeys(dossier.evidence_refs):
                passage = snapshot.get(ref, Passage)
                citation = repository.citation(snapshot, passage)
                if citation["availability"] != "available":
                    raise ResearchError("A selected publication citation has been withdrawn or purged")
                citations.append({key: citation[key] for key in (
                    "source_title", "source_id", "source_version_id", "passage_id", "revision",
                    "verbatim", "start", "end", "offset_unit", "language", "verification",
                    "redistribution", "availability")})
                if options.include_source_files:
                    version = snapshot.records[citation["source_version_id"]]
                    if not isinstance(version, SourceVersion):
                        raise ResearchError("Publication citation provenance is unavailable")
                    _retain_source(repository, snapshot, version, files, resources)
        entry = {"id": f"entry-{len(entries) + 1}", "dossier_id": dossier.id,
            "revision": dossier.revision, "section": selected.section,
            "title": selected.title or selected.section or dossier.title, "body": body,
            "reveal_after_chapter": selected.reveal_after_chapter, "citations": citations,
            "images": [item for item in public_images if item["media_type"] in IMAGE_TYPES],
            "media": [item for item in public_images if item["media_type"] in MEDIA_TYPES],
            "geography": (dossier.geography.model_dump(mode="json")
                          if selected.include_geography and dossier.geography else None)}
        size += len(_json(entry))
        if size > MAX_SITE_DATA_BYTES:
            raise SiteExportLimitError("publication_bytes", size, MAX_SITE_DATA_BYTES,
                                       context={"publication_entry": entry["id"]})
        entries.append(entry)
    data: dict[str, Any] = {"schema_version": "lixity-reader-publication/1", "mode": options.mode,
        "profile": options.publication_profile, "project_id": snapshot.project.id,
        "source_sha256": source_hash, "title": profile.title, "introduction": profile.introduction,
        "max_chapter": cap, "chapters": [{"number": number} for number, _title, _body in chapters[:cap]],
        "entries": entries}
    data["identity"] = _checksum(_json(data))
    data_size = len(_json(data))
    if data_size > MAX_SITE_DATA_BYTES:
        raise SiteExportLimitError("publication_bytes", data_size, MAX_SITE_DATA_BYTES)
    document: list[ReaderBlock] | None = None
    if options.mode == "reader":
        document = []
        line = 1
        for _number, title, body in chapters[:cap]:
            document.append(ReaderBlock("heading", title, line, line, level=2, is_chapter=True))
            line += 1
            for block in reader_blocks(body, config, []):
                document.append(ReaderBlock(block.kind, block.text, line + block.start_line - 1,
                    line + block.end_line - 1, level=block.level))
            line += len(body.splitlines()) + 1
    return data, resources, document


def _reader_analysis(text: str, config: Any, language: str, cap: int, title: str,
                     sections: list[AnalysisSection]) -> tuple[bytes, dict[str, Any]]:
    """Build analysis from selected chapters only; no project metadata or comments."""
    from .ui.components import esc, label
    from .ui.dashboard import _CSS_FILES, _bundle
    from .workspace_labels import WORKSPACE_LABELS

    selected = split_chapters(text, config)[:cap]
    # Reconstruct the disclosed chapter bodies before analysis. Never derive a
    # book-wide metric and then merely hide its later chapter rows.
    # A reader chapter may contain ordinary headings matching the default
    # chapter or appendix patterns. Use a collision-free synthetic heading
    # prefix so those authored blocks cannot change the chosen scope.
    boundary = "#" * 128
    while any(line.startswith(boundary + " ") for _, chapter_title, body in selected
              for line in (chapter_title + "\n" + body).splitlines()):
        boundary += "#"
    appendix_guard = "LIXITYREADERAPPENDIXBOUNDARY"
    while any(appendix_guard in chapter_title or appendix_guard in body for _, chapter_title, body in selected):
        appendix_guard += "X"
    capped = "\n\n".join(f"{boundary} {_without_comments(chapter_title)}\n\n{_without_comments(body)}"
                         for _number, chapter_title, body in selected)
    analysis_config, resolved = resolve_document_config(capped, language, project_config={})
    analysis_config = analysis_config.model_copy(update={
        # The parser removes heading markup from an empty title's fallback.
        "chapter_regex": rf"(?m)^{boundary} ", "appendix_marker": appendix_guard,
    })
    thresholds = resolve_thresholds(project_config={})
    analysis = analyze_document(capped, analysis_config, thresholds, include_evidence=sections == ["full"])
    labels = {**WORKSPACE_LABELS.get(resolved.key, WORKSPACE_LABELS["en"]), **resolved.labels}
    def L(key: str) -> str:
        return esc(label(labels, key))
    if sections == ["full"]:
        page = render_analysis(analysis, resolved, title=title, flag_min_severity=thresholds.flag_min_severity,
            controls=True, read_only=True, enabled_actions=[], markers=[],
            reader_document=reader_blocks(capped, analysis_config, analysis.paragraphs),
            **supplementary_reports(capped, analysis_config, analysis))
        envelope = {"schema_version": DATA_SCHEMA, "responses": {}, "resources": {}}
        script = '<script type="application/json" id="lixity-site-data">' + _script_json(envelope) + '</script>\n'
        page = page.replace('<script>', script + '<script>', 1)
        link = f'<p class="ctl-note"><a href="index.html">{L("publication_analysis_back")}</a> · {L("publication_analysis_cap_note")}</p>'
        page = page.replace('<body ', '<body ', 1).replace('<div class="page"', link + '<div class="page"', 1)
    else:
        metrics = analysis.metrics
        def number(value: float | int, available: bool = True) -> str:
            return esc(f"{value:.2f}" if isinstance(value, float) else value) if available else "—"
        def percentage(value: float, available: bool) -> str:
            return number(value) + "%" if available else "—"
        page_parts = ['<!DOCTYPE html>', f'<html lang="{esc(resolved.key)}"><head><meta charset="utf-8"/>',
            '<meta name="viewport" content="width=device-width, initial-scale=1"/>',
            '<link rel="icon" href="data:,"/>',
            f'<title>{L("publication_analysis_title")} · {esc(title)}</title>',
            f'<style>{_bundle(_CSS_FILES)}\n.reader-analysis-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,12rem),1fr));gap:.5rem 1rem}} .reader-analysis-grid dt{{font-weight:600}} .reader-analysis-grid dd{{margin:0}} .reader-analysis-grid div{{min-width:0}} .reader-analysis-chapter h3{{overflow-wrap:anywhere}}</style></head>',
            '<body class="lixity-report" data-read-only="true"><main class="page">',
            f'<a href="index.html">{L("publication_analysis_back")}</a>',
            f'<h1>{L("publication_analysis_title")}</h1>', f'<p>{L("publication_analysis_cap_note")}</p>']
        if "language" in sections:
            valid = metrics.clean_words > 0 and metrics.total_sentences > 0
            page_parts.extend(['<section id="analysis-section-language">', f'<h2>{L("publication_analysis_language")}</h2>', '<dl>',
                f'<dt>{L("words")}</dt><dd>{number(metrics.clean_words)}</dd>',
                f'<dt>{L("sentences")}</dt><dd>{number(metrics.total_sentences)}</dd>',
                f'<dt>{L("layer_asl")}</dt><dd>{number(metrics.asl, valid)}</dd>',
                f'<dt>{L("dialogue")}</dt><dd>{percentage(metrics.dialog_ratio, metrics.clean_words > 0)}</dd>',
                f'<dt>LIX</dt><dd>{number(metrics.lix, valid)}</dd>',
                f'<dt>Flesch</dt><dd>{number(metrics.flesch_de, valid)}</dd>', '</dl></section>'])
        if "chapters" in sections:
            page_parts.extend(['<section id="analysis-section-chapters">', f'<h2>{L("publication_analysis_chapters")}</h2>'])
            page_parts.extend(f'<article class="reader-analysis-chapter"><h3>{chapter.num}. {esc(chapter.title)}</h3>'
                    f'<dl class="reader-analysis-grid"><div><dt>{L("words")}</dt><dd>{chapter.words}</dd></div>'
                    f'<div><dt>{L("sentences")}</dt><dd>{chapter.sentences}</dd></div>'
                    f'<div><dt>{L("layer_asl")}</dt><dd>{number(chapter.asl, chapter.sentences > 0)}</dd></div>'
                    f'<div><dt>{L("dialogue")}</dt><dd>{percentage(chapter.dialog_pct, chapter.words > 0)}</dd></div>'
                    '</dl></article>' for chapter in metrics.chapters)
            page_parts.append('</section>')
        page_parts.append('</main></body></html>')
        page = '\n'.join(page_parts)
    policy = ('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
              'script-src \'self\' \'unsafe-inline\'; style-src \'unsafe-inline\'; '
              'img-src \'self\' data: blob:; media-src \'self\' blob:; connect-src \'self\'; font-src data:; '
              'base-uri \'none\'; form-action \'none\'"/>')
    page = page.replace('<head>', '<head>\n' + policy, 1)
    return page.encode('utf-8'), {"language": resolved.key, "thresholds": asdict(thresholds)}


def _research(repository: Repository, snapshot: Snapshot, text: str, source: Path,
              source_hash: str, analysis: Any, token: str, include_files: bool,
              files: dict[str, bytes], *, settings: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    reads = _Reads(token)
    overview = api._project_overview(snapshot, root=repository.root)
    reads.add("status", {"ok": True, "initialized": True, **overview})
    for route, value in (("sources", api._list_sources(snapshot)), ("dossiers", api._list_dossiers(snapshot, root=repository.root)),
                         ("claims", api._list_claims(snapshot)), ("decisions", api._list_decisions(snapshot))):
        reads.add(route, {"ok": True, **value}, companion=route == "dossiers")
    cited: set[str] = set()
    for record in snapshot.revisions.values():
        if isinstance(record, Dossier):
            cited.update(ref.id for ref in record.evidence_refs)
        elif isinstance(record, EvidenceLink):
            cited.add(record.passage_ref.id)
    for item in overview["sources"]:
        detail = api._get_source(repository, snapshot, item["id"], include_text=include_files,
                                 passage_ids=None if include_files else cited, strict_text=include_files)
        reads.add("sources", {"ok": True, **detail}, id=item["id"])
    for item in overview["dossiers"]:
        reads.add("dossiers", {"ok": True, **api._get_dossier(repository, snapshot, item["id"])},
                  companion=True, id=item["id"])
        reads.add("claims", {"ok": True, **api._list_claims(snapshot, dossier_id=item["id"])}, dossier_id=item["id"])
    unavailable = {record.target_ref.id for record in snapshot.records.values() if isinstance(record, Tombstone)}
    for record in snapshot.records.values():
        if record.kind not in KINDS:
            continue
        if record.id in unavailable and not (isinstance(record, Dossier) and dossier_withdrawal(snapshot, record.id)):
            # Match the native viewer's explicit lifecycle boundary. Other
            # history/validation failures must abort rather than look absent.
            continue
        history = _record_history(snapshot, record.kind, record.id)
        reads.add("history", {"ok": True, **history}, kind=record.kind, id=record.id)
        for revision in history["revisions"]:
            pinned = _record(snapshot, record.kind, record.id, revision["revision"], include_withdrawn=True)
            value = {"ok": True, **_view(repository, snapshot, pinned)}
            reads.add("record", value, companion=record.kind in {"claim", "dossier"},
                      kind=record.kind, id=record.id, revision=pinned.revision)
            if pinned.revision == record.revision and record.id not in unavailable:
                reads.add("record", value, companion=record.kind in {"claim", "dossier"},
                          kind=record.kind, id=record.id)
        if record.kind == "claim":
            reads.add("claims", {"ok": True, **api._list_evidence_links(repository, snapshot, claim_id=record.id)},
                      claim_id=record.id)
        elif record.kind == "decision":
            reads.add("decision-impact", {"ok": True, **editorial.decision_impact_data(
                snapshot, record.id, outline=lambda body: list(api.extract_sections(body)))}, id=record.id)
    reads.add("review", {"ok": True, **editorial.editorial_review_data(
        snapshot, outline=lambda body: list(api.extract_sections(body)))})
    reads.add("manuscript-links", {"ok": True, **manuscript_links_data(snapshot)})
    reads.add("manuscript-review", {"ok": True, **manuscript_review_data(snapshot,
        source_path=source.relative_to(repository.root).as_posix(), source_sha256=source_hash,
        paragraphs=analysis.paragraphs, include_context=True)}, companion=True)
    reads.add("manuscript-terms", {"ok": True, **manuscript_terms_data(snapshot,
        source_path=source.relative_to(repository.root).as_posix(), source_sha256=source_hash,
        paragraphs=analysis.paragraphs, terms=(settings or {}).get("terms"))}, companion=True)
    reads.add("timeline", {"ok": True, **timeline_data(snapshot)})
    for include in (False, True):
        reads.add("claim-relations", {"ok": True, **api._list_claim_relations(snapshot, include_retracted=include)},
                  include_retracted=str(include).lower())
    reads.add("matrix", {"text": api.render_claim_matrix(api._claim_matrix_data(repository, snapshot), format="md")}, format="md")
    resources: dict[str, str] = {}
    if include_files:
        for version in snapshot.records.values():
            if not isinstance(version, SourceVersion) or version.id in unavailable or version.source_ref.id in unavailable:
                continue
            _retain_source(repository, snapshot, version, files, resources)
    return reads.responses, resources


def prepare_site(project: str | Path, *, manuscript: str | Path | None = None,
                 language: str | None = None, title: str | None = None,
                 thresholds: FingerprintThresholds | None = None,
                 include_research: bool = False, include_source_files: bool = False,
                 mode: SiteMode = "review", publication_profile: str | None = None,
                 max_chapter: int | None = None, analysis_sections: list[AnalysisSection] | None = None,
                 tense_model: str | None = None,
                 tense_scope: str | None = None) -> SiteBundle:
    """Prepare one explicit project website without writing source files or caches.

    Research includes authored versions and cited excerpts. Original retained
    files and full extracted text require both explicit inclusion options.
    The caller decides whether/how to share the resulting files.
    """
    options = SiteExportOptions(include_research=include_research,
        include_source_files=include_source_files, mode=mode,
        publication_profile=publication_profile, max_chapter=max_chapter,
        analysis_sections=[] if analysis_sections is None else analysis_sections)
    include_research, include_source_files = options.include_research, options.include_source_files
    repository = Repository(project)
    if not repository.root.is_dir():
        raise ResearchError("Select an existing project directory")
    settings_state = _config_state(repository)
    settings = read_explicit_project_config(repository.root)
    workspace = resolve_manuscript_target(str(manuscript) if manuscript is not None else None,
                                          project=repository.root)
    source = repository.safe(Path(workspace.manuscript))
    source_info = source.stat()
    if not stat.S_ISREG(source_info.st_mode):
        raise ResearchError("Website manuscript must be a regular file")
    if source_info.st_size > MAX_SITE_DATA_BYTES:
        raise ResearchError("Manuscript exceeds the 64 MiB website input limit")
    text, source_hash = FileUtils.read_source_snapshot(str(source))
    analysis_overrides = {key: value for key, value in (("tense_model", tense_model), ("tense_scope", tense_scope))
                          if value is not None}
    config, resolved = resolve_document_config(text, language or settings.get("language", "en"),
                                               project_config=settings, **analysis_overrides)
    effective_thresholds = thresholds or resolve_thresholds(project_config=settings)
    display_title = project_title(str(source), text, settings, title)
    snapshot = (_snapshot(repository, include_history=include_research)
                if include_research or mode != "review" else None)
    token = _checksum(_json({"source": source_hash, "research": snapshot.digest if snapshot else None,
                             "language": resolved.key, "thresholds": asdict(effective_thresholds), "title": display_title}))
    files = _software_notices()
    publication = None
    publication_analysis = None
    if mode == "review":
        analysis = analyze_document(text, config, effective_thresholds, include_evidence=True)
        responses, resources = (_research(repository, snapshot, text, source, source_hash, analysis, token,
                                          include_source_files, files, settings=settings) if snapshot else ({}, {}))
        selection = resolve_character_settings(None, settings)
        author = validate_author_name(settings.get("author_name", ""))
        document = render_analysis(analysis, resolved, title=display_title,
            flag_min_severity=effective_thresholds.flag_min_severity, controls=True, read_only=True,
            reader_document=reader_blocks(text, config, analysis.paragraphs),
            markers=list_markers(text), manuscript_name=source.name, current_language=resolved.key,
            project_author=author, identity_check=manuscript_identity_check(text, display_title, author),
            enabled_actions=["research-reader", "research-manuscript-review"] if snapshot else [],
            research_context_token=token if snapshot else "", manuscript_pdf_token=token,
            manuscript_source_sha256=source_hash, project_token=token,
            characters=presence_report(text, selection.names, config, declared_pov=selection.declared_pov) if selection.names else None,
            **supplementary_reports(text, config, analysis, scene_settings=settings.get("scene_analysis")))
    else:
        from .ui.publication import render_publication

        if snapshot is None:
            raise ResearchError("A curated publication requires an initialized research project")
        publication, resources, reading = _publication(repository, snapshot, text, config, source_hash,
                                                      settings, options, files)
        responses = {}
        display_title = publication["title"]
        if options.analysis_sections:
            files["analysis.html"], publication_analysis = _reader_analysis(
                text, config, resolved.key, publication["max_chapter"], display_title, options.analysis_sections)
        document = render_publication(publication, reader_document=reading, labels=resolved.labels,
                                      language_key=resolved.key, resources=resources,
                                      analysis_available=bool(options.analysis_sections))
    envelope = {"schema_version": DATA_SCHEMA, "responses": responses, "resources": resources,
                **({"publication": publication} if publication is not None else {})}
    envelope_size = len(_json(envelope))
    if envelope_size > MAX_SITE_DATA_BYTES:
        raise SiteExportLimitError("prepared_data_bytes", envelope_size, MAX_SITE_DATA_BYTES)
    SiteData.model_validate(envelope)
    script = '<script type="application/json" id="lixity-site-data">' + _script_json(envelope) + '</script>\n'
    # The provider is the first bundled asset and must see its data at load time.
    document = document.replace('<script>', script + '<script>', 1)
    policy = ('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
              'script-src \'self\' \'unsafe-inline\'; style-src \'unsafe-inline\'; '
              'img-src \'self\' data: blob:; media-src \'self\' blob:; connect-src \'self\'; font-src data:; '
              'base-uri \'none\'; form-action \'none\'"/>')
    document = document.replace("<head>", "<head>\n" + policy, 1)
    files["index.html"] = document.encode("utf-8")
    if FileUtils.read_source_snapshot(str(repository.safe(source)))[1] != source_hash:
        raise ResearchConflictError("Manuscript changed during website preparation; retry the export")
    if _config_state(repository) != settings_state:
        raise ResearchConflictError("Project settings changed during website preparation; retry the export")
    if snapshot and Head.model_validate_json(repository.read(repository.data / "HEAD.json", maximum=4096)).sha256 != snapshot.digest:
        raise ResearchConflictError("Research changed during website preparation; retry the export")
    manifest: dict[str, Any] = {"schema_version": SITE_ANALYSIS_SCHEMA if publication_analysis is not None else SITE_SCHEMA, "product_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(), "entrypoint": "index.html",
        "mode": mode,
        "project": {"title": display_title, "language": resolved.key,
                    **({"id": snapshot.project.id} if snapshot else {})},
        "manuscript": {**({"name": source.name} if mode == "review" else {}), "source_sha256": source_hash},
        "analysis": ({"language": resolved.key, "thresholds": asdict(effective_thresholds)} if mode == "review" else publication_analysis),
        "research": {"included": include_research, "snapshot": snapshot.digest if include_research and snapshot else None,
                     "revision_count": len(snapshot.revisions) if include_research and snapshot else 0},
        **({"publication": {"profile": publication["profile"], "identity": publication["identity"],
            "max_chapter": publication["max_chapter"], "entry_count": len(publication["entries"]),
            **({"analysis_sections": options.analysis_sections} if options.analysis_sections else {})}} if publication else {}),
        "capabilities": {"read_only": True, "analysis": mode == "review" or publication_analysis is not None, "research": include_research,
                         "source_files": include_source_files, "automatic_external_requests": False},
        "disclosures": [*( ["Contains manuscript prose, analysis and work-marker notes."] if mode == "review" else [
            "Contains only the selected publication profile, approved dossier content and explicitly selected citations/maps.",
            "Reading progress hides content already included in this file; it is not access control.",
            "The export chapter cap removes later publication entries and resources before assembly.",
            "Contains manuscript reading text only through the export cap." if mode == "reader" else "Contains no manuscript prose or analysis.",
            *(["Contains explicitly selected analysis computed only from the exported chapters with default settings; no work-marker notes."] if publication_analysis is not None else [])]),
            *( ["Contains accessible authored research history, notes, source metadata and cited excerpts; local Zotero identities are omitted."] if include_research else []),
            *( ["Includes original source bytes and images; retention does not grant redistribution rights." +
                (" Review mode also includes full extracted text." if mode == "review" else " Only selected publication dependencies are copied.")] if include_source_files else []),
            "A local reading snapshot, not a research backup or access-control system. No automatic publishing.",
            "Saved prose and source URLs can contain personal information; review before sharing."],
        "files": {name: {"sha256": _checksum(content), "byte_length": len(content)} for name, content in sorted(files.items())}}
    files["manifest.json"] = _json(manifest)
    bodies = ([entry["body"] for entry in publication["entries"]] if publication else
              [record.body for record in snapshot.revisions.values() if isinstance(record, Dossier)] if snapshot else [])
    bundle = SiteBundle(files, manifest, media_summary(snapshot, bodies, resources))
    bundle._validate()
    return bundle


def _publish_new_directory(stage: Path, target: Path) -> None:
    """Atomically publish without replacing even a concurrently created empty folder.

    Ordinary POSIX rename overwrites empty directories. The platform's
    no-replace primitive is required; unsupported filesystems fail explicitly.
    """
    if os.name == "nt":
        os.rename(stage, target)  # Windows rename refuses an existing target.
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith("linux"):
        rename = getattr(libc, "renameat2", None)
        if rename is None:
            raise ResearchError("Atomic no-replace website publication is unsupported; download a ZIP instead")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(-100, os.fsencode(stage), -100, os.fsencode(target), 1)  # AT_FDCWD, RENAME_NOREPLACE
    elif sys.platform == "darwin":
        rename = getattr(libc, "renamex_np", None)
        if rename is None:
            raise ResearchError("Atomic no-replace website publication is unsupported; download a ZIP instead")
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(os.fsencode(stage), os.fsencode(target), 4)  # RENAME_EXCL
    else:
        raise ResearchError("Atomic no-replace website publication is unsupported; download a ZIP instead")
    if result != 0:
        error = ctypes.get_errno()
        if error in (errno.EEXIST, errno.ENOTEMPTY):
            raise ResearchConflictError("Website destination already exists; nothing was replaced")
        raise OSError(error, "Could not atomically publish the website; no destination was replaced")


def export_site(project: str | Path, output: str | Path, *, manuscript: str | Path | None = None,
                language: str | None = None, title: str | None = None,
                thresholds: FingerprintThresholds | None = None,
                include_research: bool = False, include_source_files: bool = False,
                mode: SiteMode = "review", publication_profile: str | None = None,
                max_chapter: int | None = None, analysis_sections: list[AnalysisSection] | None = None) -> dict[str, Any]:
    """Publish a complete new local folder; never replace an existing target."""
    root = Path(project).expanduser().resolve()
    target = Path(output).expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise ResearchError("Website destination must not exist or be a symlink")
    for parent in target.parents:
        if parent.is_symlink():
            raise ResearchError("Website output must not traverse a symlink")
    target = target.resolve()
    if target.exists() or target.is_symlink():
        raise ResearchError("Website destination must not exist")
    for protected in (root / "research", root / ".lixity", root / ".git"):
        if target.is_relative_to(protected):
            raise ResearchError("Website output must remain outside protected project data")
    bundle = prepare_site(project, manuscript=manuscript, language=language, title=title,
                          thresholds=thresholds, include_research=include_research,
                          include_source_files=include_source_files, mode=mode,
                          publication_profile=publication_profile, max_chapter=max_chapter,
                          analysis_sections=analysis_sections)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".lixity-site-", dir=target.parent) as directory:
        stage = Path(directory) / "site"
        stage.mkdir()
        for name, content in bundle.files.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        if target.exists() or target.is_symlink():
            raise ResearchConflictError("Website destination appeared during export")
        _publish_new_directory(stage, target)
    return bundle.manifest
