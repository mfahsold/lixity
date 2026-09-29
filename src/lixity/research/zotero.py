"""Optional read-only Zotero Desktop bridge; no remote service or database access."""

import http.client
import json
import re
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

from . import api
from .models import Source, SourceContext, SourceVersion, Tombstone
from .repository import Repository, ResearchError, digest

MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def _request(path: str) -> tuple[bytes, str | None]:
    """Use only the fixed loopback service, without proxies or redirect following."""
    connection = http.client.HTTPConnection("127.0.0.1", 23119, timeout=10)
    try:
        connection.request("GET", "/api/" + path, headers={"Zotero-API-Version": "3"})
        response = connection.getresponse()
        if response.status == 403:
            raise ResearchError("Enable Zotero Settings > Advanced > Allow other applications on this computer")
        if response.status != 200:
            raise ResearchError(f"Zotero local API returned HTTP {response.status}; check the library and item key")
        content = response.read(MAX_RESPONSE_BYTES + 1)
        if len(content) > MAX_RESPONSE_BYTES:
            raise ResearchError("Zotero response exceeds 2 MiB; use a smaller page")
        return content, response.getheader("Zotero-Server-ID")
    except (OSError, http.client.HTTPException) as error:
        raise ResearchError("Cannot read Zotero Desktop at 127.0.0.1:23119; start Zotero and enable its local API") from error
    finally:
        connection.close()


def _library(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"(?:users/(?:0|[1-9][0-9]*)|groups/[1-9][0-9]*)", value):
        raise ResearchError("Explicit Zotero library must be users/0, users/<id> or groups/<id>")
    return value


def _library_identity(value: str) -> str:
    """Personal-library aliases identify the same library within one server."""
    return "users/0" if value.startswith("users/") else value


def _key(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z0-9]{8}", value):
        raise ResearchError("Zotero item key must contain eight uppercase letters or digits")
    return value


def _item(value: Any, expected_key: str | None = None) -> dict[str, Any]:
    if (not isinstance(value, dict) or not isinstance(value.get("data"), dict)
            or type(value.get("version")) is not int or value["version"] < 0):
        raise ResearchError("Invalid Zotero item response")
    key = _key(value.get("key"))
    if expected_key is not None and key != expected_key:
        raise ResearchError("Zotero returned a different item key")
    if not isinstance(value["data"].get("itemType"), str):
        raise ResearchError("Invalid Zotero item type")
    return value


class _Reader:
    def __init__(self) -> None:
        self.server_id: str | None = None
        self.started = False

    def read(self, path: str) -> bytes:
        content, server_id = _request(path)
        if self.started and server_id != self.server_id:
            raise ResearchError("Zotero instance changed during this operation; retry after checking Zotero")
        self.server_id = server_id
        self.started = True
        return content

    def json(self, path: str) -> Any:
        content = self.read(path)
        try:
            return json.loads(content)
        except (ValueError, UnicodeError) as error:
            raise ResearchError("Invalid JSON from Zotero local API") from error

    def item(self, library: str, key: str) -> dict[str, Any]:
        return _item(self.json(f"{library}/items/{_key(key)}"), key)


def browse(project: str | Path, *, library: str, query: str = "", item_key: str | None = None,
           limit: int = 20, start: int = 0, collection_key: str | None = None) -> dict[str, Any]:
    """Preview one explicit library page, or one item and a page of its attachments."""
    snapshot = Repository(project).snapshot()
    library = _library(library)
    if type(limit) is not int or not 1 <= limit <= 100 or type(start) is not int or start < 0:
        raise ResearchError("Zotero limit must be 1..100 and start must be nonnegative")
    if not isinstance(query, str) or len(query) > 1000:
        raise ResearchError("Zotero query must be at most 1000 characters")
    reader = _Reader()
    params: dict[str, str | int] = {"format": "json", "limit": limit, "start": start}
    parent = None
    if item_key is not None:
        if query:
            raise ResearchError("Choose either a Zotero query or an item key")
        parent = reader.item(library, item_key)
        path = f"{library}/items/{item_key}/children"
    else:
        params["q"] = query
        path = f"{library}/collections/{_key(collection_key)}/items/top" if collection_key else f"{library}/items/top"
    values = reader.json(path + "?" + urlencode(params))
    if not isinstance(values, list) or len(values) > limit:
        raise ResearchError("Invalid Zotero item page")
    items = [_item(value) for value in values]
    result: dict[str, Any] = {"schema_version": "research-zotero-local/1", "project_id": snapshot.project.id,
                              "library": library, "server_id": reader.server_id, "start": start,
                              "limit": limit, "next_start": start + len(items) if len(items) == limit else None,
                              "warnings": ["External metadata is unreviewed; no files have been retained."]}
    if parent is None:
        result["items"] = items
    else:
        result["item"] = parent
        result["attachments"] = [item for item in items if item["data"]["itemType"] == "attachment"]
    return result


def ingest(project: str | Path, *, library: str, attachment_key: str, allow_retention: bool = False,
           source_id: str | None = None, language: str | None = None, dry_run: bool = False,
           expected_server_id: str | None = None, expected_snapshot: str | None = None,
           progress_callback: Callable[[str, str], None] | None = None) -> dict[str, Any]:
    """Capture one selected local attachment through the existing evidence pipeline."""
    if allow_retention is not True:
        raise ResearchError("Explicit local retention permission is required (--allow-retention)")
    snapshot = Repository(project).snapshot()
    if expected_snapshot is not None and snapshot.digest != expected_snapshot:
        raise ResearchError("Research snapshot changed; reload the Zotero selection")
    library = _library(library)
    attachment_key = _key(attachment_key)
    if progress_callback:
        progress_callback("zotero-resolve", f"Resolving Zotero attachment {attachment_key}...")
    reader = _Reader()
    attachment = reader.item(library, attachment_key)
    if expected_server_id is not None and reader.server_id != expected_server_id:
        raise ResearchError("Zotero instance differs from the preview; reload the selection")
    data = attachment["data"]
    media_type = data.get("contentType")
    if (data["itemType"] != "attachment" or media_type not in ("application/pdf", "text/plain", "text/markdown")
            or data.get("linkMode") not in ("imported_file", "imported_url", "linked_file")):
        raise ResearchError("Select a locally available PDF or UTF-8 text attachment; other media stay in Zotero")
    parent_key = data.get("parentItem")
    parent = reader.item(library, parent_key) if parent_key else attachment
    metadata = parent["data"]
    title = metadata.get("title") or data.get("title")
    if not isinstance(title, str) or not 1 <= len(title) <= 500:
        raise ResearchError("Zotero item needs a title of 1..500 characters")
    capture_library = _library_identity(library)
    identity = f"Zotero local capture: {capture_library}/items/{attachment_key}; instance={reader.server_id or 'unavailable'}"
    creators = metadata.get("creators", [])
    if not isinstance(creators, list) or any(not isinstance(creator, dict) for creator in creators):
        raise ResearchError("Invalid Zotero creators")
    names = [" ".join(str(creator.get(field, "")) for field in ("name", "firstName", "lastName")).strip()
             for creator in creators]
    note = "\n".join((identity, f"Attachment version: {attachment['version']}",
                      f"Parent: {capture_library}/items/{parent['key']}; version={parent['version']}",
                      f"Title: {title}", f"Creators: {'; '.join(names)}", f"Date: {metadata.get('date', '')}"))
    external = ({"provider": "zotero", "server_id": reader.server_id, "library": capture_library,
                 "item_key": parent["key"], "attachment_key": attachment_key,
                 "item_version": parent["version"], "attachment_version": attachment["version"]}
                if reader.server_id else None)
    explicit_source = source_id is not None
    def matches(value: dict[str, Any] | None) -> bool:
        return bool(value and external
                    and _library_identity(value.get("library", "")) == external["library"]
                    and all(value.get(k) == external[k]
                            for k in ("provider", "server_id", "attachment_key")))
    active = api.list_sources(project)["sources"]
    linked = [source for source in active if matches(source["context"].get("external_reference"))]
    if len(linked) > 1 or (linked and source_id and linked[0]["id"] != source_id):
        raise ResearchError("Zotero attachment identity does not match a unique source")
    if linked and source_id is None:
        source_id = linked[0]["id"]
    context: dict[str, Any] = {}
    migration = False
    existing = None
    if source_id:
        if reader.server_id is None:
            raise ResearchError("Safe Zotero refresh requires a server identity (Zotero 10 or later)")
        existing = next((source for source in active if source["id"] == source_id), None)
        if existing is None:
            raise ResearchError("Zotero refresh requires an active source")
        context = dict(existing["context"])
        previous = context.get("external_reference")
        if previous and not matches(previous):
            raise ResearchError("Source refresh must match the previously captured Zotero attachment and instance")
        if previous and external:
            # Accepted records keep their original alias, so merely changing
            # API addressing does not create a new capture or rewrite history.
            prior_library = previous["library"]
            external["library"] = prior_library
            identity = identity.replace(capture_library + "/items/", prior_library + "/items/")
            note = note.replace(capture_library + "/items/", prior_library + "/items/", 2)
        if not previous and not (context.get("provenance_note") or "").startswith(identity + "\n"):
            tags = metadata.get("tags", [])
            migration = isinstance(tags, list) and any(isinstance(tag, dict) and
                tag.get("tag") == "lixity-source:" + source_id[9:] for tag in tags)
            if not migration:
                raise ResearchError("Source refresh must match its Zotero identity or migration source tag")
    prior_note = context.get("provenance_note")
    context.update(provenance_note=(prior_note if prior_note and not prior_note.startswith(identity + "\n") else note),
                   origin_url=metadata.get("url") or None)
    if external:
        context["external_reference"] = external
    SourceContext.model_validate(context)
    location = reader.read(f"{library}/items/{attachment_key}/file/view/url").decode("utf-8").strip()
    parsed = urlsplit(location)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost") or parsed.query or parsed.fragment:
        raise ResearchError("Zotero attachment must resolve to a local file URL")
    from urllib.request import url2pathname
    path = Path(url2pathname(parsed.path))
    if not path.is_absolute() or not path.is_file():
        raise ResearchError("Zotero attachment is not an available local regular file; download it in Zotero first")
    is_pdf = media_type == "application/pdf"
    maximum = api.MAX_PDF_BYTES if is_pdf else api.MAX_SOURCE_BYTES
    if progress_callback:
        progress_callback("zotero-read", f"Reading attachment {path.name}...")
    with path.open("rb") as stream:
        content = stream.read(maximum + 1)
    if not content or len(content) > maximum:
        raise ResearchError("Zotero attachment is empty or exceeds the PDF/text ingestion size limit")
    if migration and existing and digest(content) != existing["sha256"]:
        raise ResearchError("Migration binding requires exact original attachment bytes")
    # A stable temporary copy gives extraction and retained bytes the same input.
    with tempfile.TemporaryDirectory(prefix="lixity-zotero-") as directory:
        target = Path(directory) / ("attachment.pdf" if is_pdf else "attachment.txt")
        target.write_bytes(content)
        result = api.ingest(project, target, allow_retention=True, source_id=source_id,
                            title=None if source_id else title, language=language, context=context,
                            expected_snapshot=expected_snapshot or snapshot.digest,
                            dry_run=dry_run or (bool(linked) and not explicit_source),
                            progress_callback=progress_callback)
        if linked and not explicit_source:
            if not result["unchanged"]:
                raise ResearchError("Zotero capture changed; explicitly pass --source-id to refresh it")
            result["dry_run"] = dry_run
    return {**result, "zotero": {"library": library, "attachment_key": attachment_key,
                                "item_key": parent["key"], "server_id": reader.server_id},
            "warnings": ["Explicit capture only; Zotero changes are not synchronized automatically."]}


def export_library(project: str | Path, output: str | Path, *, allow_retention: bool = False,
                   dry_run: bool = False) -> dict[str, Any]:
    """Export active captures as an additive RIS import bundle; never edit evidence."""
    if allow_retention is not True:
        raise ResearchError("Explicit local retention permission is required (--allow-retention)")
    repository = Repository(project)
    snapshot = repository.snapshot()
    target = Path(output).expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise ResearchError("Zotero export destination must not exist")
    withdrawn = {r.target_ref.id for r in snapshot.records.values() if isinstance(r, Tombstone)}
    sources = [r for r in snapshot.records.values() if isinstance(r, Source) and r.id not in withdrawn]
    entries: list[dict[str, Any]] = []
    payloads: dict[str, bytes] = {}
    lines: list[str] = []
    for source in sorted(sources, key=lambda r: r.id):
        versions = [r for r in snapshot.records.values() if isinstance(r, SourceVersion)
                    and r.source_ref.id == source.id and r.id not in withdrawn]
        if not versions:
            continue
        version = max(versions, key=lambda r: r.sequence)
        suffix = ".pdf" if version.blob.media_type == "application/pdf" else ".txt"
        relative = f"files/{source.id[9:]}{suffix}"
        content = repository.read_blob(version.blob)
        if not dry_run:
            payloads[relative] = content
        entries.append({"source_id": source.id, "version_id": version.id, "title": source.title,
                        "language": source.language, "sha256": version.blob.sha256,
                        "file": relative, "context": version.context.model_dump()})
        def line(field: str, value: str) -> None:
            lines.append(f"{field}  - {' '.join(value.split())}")
        line("TY", "GEN")
        line("TI", source.title)
        line("LA", source.language)
        line("KW", "lixity-source:" + source.id[9:])
        for tag in version.context.tags:
            line("KW", tag)
        if version.context.origin_url:
            line("UR", version.context.origin_url)
        line("N1", f"Lixity retained source {source.id}; capture {version.id}; SHA-256 {version.blob.sha256}")
        if version.context.provenance_note:
            line("N1", version.context.provenance_note)
        # Absolute file URIs allow the reviewed bundle to be imported by Zotero.
        line("L1" if suffix == ".pdf" else "L4", (target / relative).as_uri())
        lines.extend(("ER  -", ""))
    manifest = {"schema_version": "research-zotero-export-local/1", "project_id": snapshot.project.id,
                "snapshot": snapshot.digest, "sources": entries}
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".lixity-zotero-export-", dir=target.parent) as directory:
            stage = Path(directory) / "bundle"
            (stage / "files").mkdir(parents=True)
            for relative, content in payloads.items():
                (stage / relative).write_bytes(content)
            (stage / "library.ris").write_text("\n".join(lines), encoding="utf-8")
            (stage / "migration.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            if target.exists() or target.is_symlink():
                raise ResearchError("Zotero export destination appeared during export")
            stage.rename(target)
    return {"schema_version": "research-zotero-export-local/1", "sources": len(entries),
            "snapshot": snapshot.digest, "output": str(target), "dry_run": dry_run}


def collections(project: str | Path, *, library: str, start: int = 0) -> dict[str, Any]:
    """List one bounded page of local collections without changing project settings."""
    snapshot = Repository(project).snapshot()
    library = _library(library)
    if type(start) is not int or start < 0:
        raise ResearchError("Collection start must be nonnegative")
    reader = _Reader()
    values = reader.json(f"{library}/collections?format=json&limit=100&start={start}")
    if not isinstance(values, list) or len(values) > 100:
        raise ResearchError("Invalid Zotero collections page")
    for value in values:
        if not isinstance(value, dict) or not isinstance(value.get("data"), dict):
            raise ResearchError("Invalid Zotero collection")
        _key(value.get("key"))
        if not isinstance(value["data"].get("name"), str):
            raise ResearchError("Invalid Zotero collection name")
    return {"schema_version": "research-zotero-local/1", "project_id": snapshot.project.id,
            "library": library, "server_id": reader.server_id, "collections": values,
            "next_start": start + len(values) if len(values) == 100 else None}
