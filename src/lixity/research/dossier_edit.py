"""Bounded, explicit Markdown drafts of authored dossiers; never a source store."""

import json
import math
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import Field, field_validator

from .limits import MAX_RESEARCH_OBJECT_BYTES
from .models import Dossier, Identifier, StrictModel
from .repository import Repository, ResearchError, sync_directory
from .revisions import _record, prepare_record_revision

_PREFIX = "<!-- lixity-dossier-edit/1\n"
_END = "\n-->\n"
_HEADER_START = re.compile(r"<!-- lixity-dossier-edit/1\r?\n")
_HEADER_END = re.compile(r"\r?\n-->\r?\n")
# The model's maximum is a codepoint limit; UTF-8 requires at most four bytes each.
_BODY_MAX_CHARS = next(item.max_length for item in Dossier.model_fields["body"].metadata
                       if hasattr(item, "max_length"))
_BODY_MAX_BYTES = 4 * _BODY_MAX_CHARS
_EDITABLE = frozenset({"title", "language", "tags", "geography", "evidence_ids"})


class _EditHeader(StrictModel):
    project_id: Identifier
    kind: Literal["dossier"]
    record_id: Identifier
    base_revision: Annotated[int, Field(ge=1)]
    fields: dict[str, Any]

    @field_validator("fields")
    @classmethod
    def exact_fields(cls, value: dict[str, Any]) -> dict[str, Any]:
        if set(value) != _EDITABLE:
            raise ValueError("Use exactly the exported dossier fields")
        return value


def _utf8(value: str, context: str) -> bytes:
    try:
        return value.encode("utf-8")
    except UnicodeError as exc:
        raise ResearchError(f"Dossier edit {context} must be valid UTF-8") from exc


def _body_bytes(body: str) -> bytes:
    if not 1 <= len(body) <= _BODY_MAX_CHARS:
        raise ResearchError("Dossier edit body exceeds its supported text size or is empty")
    content = _utf8(body, "body")
    if len(content) > _BODY_MAX_BYTES:
        raise ResearchError("Dossier edit body exceeds its supported byte size")
    return content


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate dossier edit header key")
        value[key] = item
    return value


def _finite_json(value: str) -> None:
    raise ValueError(f"Nonfinite dossier edit header value: {value}")


def _json_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Dossier edit header number exceeds finite range")
    return number


def encode_dossier_edit(record: Dossier) -> str:
    """Export identities and editable metadata, followed by the exact body."""
    _body_bytes(record.body)
    header = {
        "project_id": record.project_id, "kind": "dossier", "record_id": record.id,
        "base_revision": record.revision,
        "fields": {"title": record.title, "language": record.language, "tags": record.tags,
                   "geography": record.geography.model_dump(mode="json") if record.geography else None,
                   "evidence_ids": [ref.id for ref in record.evidence_refs]},
    }
    text = json.dumps(header, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    text = text.replace("<", "\\u003c").replace(">", "\\u003e")
    if len(_utf8(text, "header")) > MAX_RESEARCH_OBJECT_BYTES:
        raise ResearchError("Dossier edit header exceeds the supported structured-record size")
    return _PREFIX + text + _END + record.body


def decode_dossier_edit(text: str) -> dict[str, Any]:
    """Read only the explicit leading control comment; body content stays inert."""
    start = _HEADER_START.match(text)
    if start is None:
        raise ResearchError("Expected an exported lixity-dossier-edit/1 header")
    end = _HEADER_END.search(text, start.end())
    if end is None:
        raise ResearchError("Dossier edit header is incomplete")
    raw = text[start.end():end.start()]
    if len(_utf8(raw, "header")) > MAX_RESEARCH_OBJECT_BYTES:
        raise ResearchError("Dossier edit header exceeds the supported structured-record size")
    try:
        if "-->" in raw or "<!--" in raw:
            raise ValueError("Escape comment delimiters in dossier metadata")
        values = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_finite_json,
                            parse_float=_json_float)
        header = _EditHeader.model_validate(values)
    except (ValueError, RecursionError) as exc:
        raise ResearchError("Invalid dossier edit header; preserve exported identities and fields") from exc
    body = text[end.end():]
    _body_bytes(body)
    return {**header.model_dump(), "body": body}


def export_dossier_edit(project: str | Path, record_id: str, *, revision: int | None = None) -> str:
    """Export one selected revision, without modifying the archive or its pins."""
    snapshot = Repository(project).snapshot()
    record = _record(snapshot, "dossier", record_id, revision)
    if not isinstance(record, Dossier):
        raise ResearchError("Edit export requires a dossier")
    return encode_dossier_edit(record)


def prepare_dossier_edit(
    project: str | Path, record_id: str, document: str, *,
    resolutions: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Reconcile an explicit external draft through the ordinary revision owner."""
    draft = decode_dossier_edit(document)
    if draft["record_id"] != record_id:
        raise ResearchError("Dossier edit identity differs from the selected record")
    preview = prepare_record_revision(
        project, "dossier", record_id, base_revision=draft["base_revision"],
        changes={**draft["fields"], "body": draft["body"]}, resolutions=resolutions,
    )
    if preview["current"]["project_id"] != draft["project_id"]:
        raise ResearchError("Dossier edit belongs to a different project")
    return preview


def prepare_dossier_edits(
    project: str | Path,
    paths: Sequence[str | Path],
    *,
    change_kind: Literal["correction", "supersession"] = "correction",
    reason: str | None = None,
    actor: str = "local-author",
) -> dict[str, Any]:
    """Reconcile multiple explicit external draft files against one current archive snapshot.

    Reads each file, validates unique dossier IDs within the selected project,
    computes per-file diff/reconciliation state, and prepares a ready
    research-revision-batch-local/1 packet when all drafts are conflict-free.
    """
    if not paths:
        raise ResearchError("Provide at least one dossier edit file to prepare")
    repository = Repository(project)
    snapshot = repository.snapshot()

    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    operations: list[Mapping[str, Any]] = []
    all_ready = True
    total_changed = 0

    for p in paths:
        path_obj = Path(p).expanduser().resolve()
        doc = read_dossier_edit(path_obj)
        draft = decode_dossier_edit(doc)
        rec_id = draft["record_id"]
        if rec_id in seen_ids:
            raise ResearchError(f"Duplicate dossier edit draft for record {rec_id}")
        seen_ids.add(rec_id)
        if draft["project_id"] != snapshot.project.id:
            raise ResearchError(f"Dossier edit file {path_obj.name} belongs to a different project")

        preview = prepare_dossier_edit(project, rec_id, doc)
        current = preview["current"]
        is_ready = bool(preview["ready"])
        has_changes = bool(preview["has_changes"])
        if not is_ready:
            all_ready = False
        if has_changes:
            total_changed += 1

        changed_fields = sorted(preview.get("changes", {}).keys())
        conflicting_fields = [c["field"] for c in preview.get("conflicts", [])]

        items.append({
            "path": str(path_obj),
            "record_id": rec_id,
            "title": draft["fields"].get("title") or current["record"].get("title", ""),
            "base_revision": draft["base_revision"],
            "current_revision": current["record"]["revision"],
            "ready": is_ready,
            "has_changes": has_changes,
            "changed_fields": changed_fields,
            "conflicts": preview.get("conflicts", []),
            "conflicting_fields": conflicting_fields,
        })

        if is_ready and has_changes:
            op_reason = reason.strip() if isinstance(reason, str) and reason.strip() else f"Reconcile dossier draft {path_obj.name}"
            operations.append({
                "kind": "dossier",
                "id": rec_id,
                "expected_revision": current["record"]["revision"],
                "changes": preview["changes"],
                "change_kind": change_kind,
                "reason": op_reason,
            })

    packet: dict[str, Any] | None = None
    if all_ready and operations:
        from .revisions import prepare_record_revisions

        packet = prepare_record_revisions(project, operations, actor=actor)

    return {
        "schema_version": "research-dossier-batch-preview-local/1",
        "project_id": snapshot.project.id,
        "snapshot": snapshot.digest,
        "ready": all_ready,
        "total_files": len(items),
        "changed_files": total_changed,
        "items": items,
        "batch_packet": packet,
    }



def read_dossier_edit(path: str | Path) -> str:
    """Read a bounded UTF-8 edit file without newline translation."""
    # The three envelope line endings may each contain an additional CR byte.
    maximum = MAX_RESEARCH_OBJECT_BYTES + _BODY_MAX_BYTES + len(_PREFIX) + len(_END) + 3
    try:
        with Path(path).expanduser().open("rb") as stream:
            content = stream.read(maximum + 1)
        if len(content) > maximum:
            raise ResearchError("Dossier edit file exceeds supported header and body sizes")
        return content.decode("utf-8")
    except UnicodeError as exc:
        raise ResearchError(f"Dossier edit file must be UTF-8: {path}") from exc
    except OSError as exc:
        raise ResearchError(f"Cannot read dossier edit file: {path} ({exc})") from exc


def write_dossier_edit(
    project: str | Path, record_id: str, path: str | Path, *, revision: int | None = None,
) -> None:
    """Publish a complete draft exclusively outside authoritative state paths."""
    document = export_dossier_edit(project, record_id, revision=revision)
    write_research_draft_file(project, path, document)


def write_research_draft_file(project: str | Path, path: str | Path, document: str) -> None:
    """Publish an explicit draft atomically and exclusively outside archive paths.

    POSIX operations and cleanup stay anchored to an opened parent directory.
    Windows retains exclusive hard-link publication and identity checks; its
    Python filesystem API cannot provide the same directory-relative race guard.
    """
    repository = Repository(project)
    target = Path(path).expanduser().absolute()
    resolved = target.resolve()
    protected_paths = (repository.data, repository.root / ".lixity")
    for protected in protected_paths:
        if resolved == protected or protected in resolved.parents:
            raise ResearchError("Dossier edit files must stay outside research/ and .lixity/")
    content = _utf8(document, "document")
    temporary: str | None = None
    directory: int | None = None
    published = complete = False
    staged_identity: tuple[int, int] | None = None
    parent: Path | None = None
    parent_identity: tuple[int, int] | None = None

    def same_parent() -> bool:
        try:
            current = target.parent.stat()
            return (target.parent.resolve(strict=True) == parent
                    and (current.st_dev, current.st_ino) == parent_identity)
        except OSError:
            return False

    def check_parent() -> None:
        if not same_parent():
            raise ResearchError("Dossier edit destination directory changed; export again")

    try:
        parent = target.parent.resolve(strict=True)
        for protected in protected_paths:
            if parent == protected or protected in parent.parents:
                raise ResearchError("Dossier edit files must stay outside research/ and .lixity/")
        info = parent.stat()
        parent_identity = (info.st_dev, info.st_ino)
        if os.name != "nt":
            directory = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                                | getattr(os, "O_NOFOLLOW", 0))
            opened = os.fstat(directory)
            if (opened.st_dev, opened.st_ino) != parent_identity:
                raise ResearchError("Dossier edit destination directory changed; export again")
        check_parent()
        if directory is not None:
            temporary = f".lixity-edit-{uuid4().hex}"
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory)
        else:
            descriptor, temporary = tempfile.mkstemp(dir=parent, prefix=".lixity-edit-")
        with os.fdopen(descriptor, "wb") as stream:
            staged = os.fstat(stream.fileno())
            staged_identity = (staged.st_dev, staged.st_ino)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        check_parent()
        if directory is not None:
            os.link(temporary, target.name, src_dir_fd=directory, dst_dir_fd=directory,
                    follow_symlinks=False)
        else:
            os.link(temporary, target)
        published = True
        check_parent()
        if directory is not None:
            os.fsync(directory)
        else:
            sync_directory(parent)
        complete = True
    except FileExistsError as exc:
        raise ResearchError(f"Dossier edit destination already exists: {target}") from exc
    except OSError as exc:
        raise ResearchError(f"Cannot export dossier edit file: {target} ({exc})") from exc
    finally:
        try:
            # A replaced path must never redirect cleanup to somebody else's
            # file. POSIX cleanup still reaches our original directory by fd.
            if temporary is not None and (directory is not None or same_parent()):
                relative = {"dir_fd": directory} if directory is not None else {}
                if published and not complete:
                    try:
                        linked = os.stat(target.name if directory is not None else target,
                                         follow_symlinks=False, **relative)
                        if (linked.st_dev, linked.st_ino) == staged_identity:
                            os.unlink(target.name if directory is not None else target, **relative)
                    except FileNotFoundError:
                        pass
                with suppress(FileNotFoundError):
                    os.unlink(temporary, **relative)
        finally:
            if directory is not None:
                os.close(directory)
