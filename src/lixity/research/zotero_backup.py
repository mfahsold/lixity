"""Paired research/Zotero data backups with verified, non-overwriting restoration."""

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from . import api
from .archive import MAX_UNCOMPRESSED_BYTES, _file_digest_and_size
from .repository import ResearchError

SCHEMA = "research-zotero-backup-local/1"


def _inventory(root: Path) -> dict[str, dict[str, Any]]:
    if root.is_symlink() or not root.is_dir():
        raise ResearchError("Backup input must be a real directory")
    result: dict[str, dict[str, Any]] = {}
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ResearchError("Backup refuses symlinks and special files; use Zotero stored attachments")
        if path.is_file():
            total += path.stat().st_size
            if total > MAX_UNCOMPRESSED_BYTES:
                raise ResearchError("Paired backup exceeds the 10 GiB limit")
            checksum, size = _file_digest_and_size(path)
            result[path.relative_to(root).as_posix()] = {"sha256": checksum, "bytes": size}
    return result


def _destination(output: str | Path) -> Path:
    target = Path(output).expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise ResearchError("Backup/restore destination must not exist")
    return target


def backup(project: str | Path, data_dir: str | Path, output: str | Path, *,
           confirm_closed: bool = False) -> dict[str, Any]:
    """Copy an explicitly closed Zotero data directory alongside the research archive.

    The caller must close Zotero first. This is an operational precondition, not
    inferred from a process name. Linked files outside the data directory and
    manuscript/application-profile files are not included.
    """
    if confirm_closed is not True:
        raise ResearchError("Close Zotero and confirm with --confirm-zotero-closed before backing up")
    target = _destination(output)
    data = Path(data_dir).expanduser().absolute()
    if data == target or data in target.parents:
        raise ResearchError("Backup output must be outside the Zotero data directory")
    if not (data / "zotero.sqlite").is_file():
        raise ResearchError("Explicit Zotero data directory must contain zotero.sqlite")
    before = _inventory(data)
    if not api.audit(project)["ok"]:
        raise ResearchError("Research integrity audit failed; refusing backup")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".lixity-paired-", dir=target.parent) as directory:
        stage = Path(directory) / "bundle"
        stage.mkdir()
        archived = api.export_archive(project, stage / "research.tar.gz")
        shutil.copytree(data, stage / "zotero", symlinks=True)
        copied = _inventory(stage / "zotero")
        if copied != before or _inventory(data) != before:
            raise ResearchError("Zotero files changed during backup; close Zotero and retry")
        manifest = {"schema_version": SCHEMA, "files": _inventory(stage), "research": archived,
                    "scope": "Research archive and Zotero data directory; excludes manuscripts, profiles and external linked files"}
        (stage / "BACKUP.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if target.exists() or target.is_symlink():
            raise ResearchError("Backup destination appeared during capture")
        stage.rename(target)
    return {"schema_version": SCHEMA, "output": str(target), "files": len(manifest["files"]), "ok": True}


def restore(bundle: str | Path, output: str | Path) -> dict[str, Any]:
    """Verify every file, then restore into a new project/zotero directory pair."""
    target = _destination(output)
    source = Path(bundle).expanduser().absolute()
    inventory = _inventory(source)
    marker = source / "BACKUP.json"
    if not marker.is_file() or marker.stat().st_size > 4 * 1024 * 1024:
        raise ResearchError("Missing or oversized paired backup manifest")
    try:
        manifest = json.loads(marker.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as error:
        raise ResearchError("Invalid paired backup manifest") from error
    inventory.pop("BACKUP.json", None)
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA
            or manifest.get("files") != inventory):
        raise ResearchError("Paired backup checksum or file inventory mismatch")
    if "research.tar.gz" not in inventory or "zotero/zotero.sqlite" not in inventory:
        raise ResearchError("Incomplete paired backup")
    if any(path != "research.tar.gz" and not path.startswith("zotero/") for path in inventory):
        raise ResearchError("Unexpected paired backup file")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".lixity-paired-restore-", dir=target.parent) as directory:
        stage = Path(directory) / "restored"
        stage.mkdir()
        api.restore_archive(source / "research.tar.gz", stage / "project")
        shutil.copytree(source / "zotero", stage / "zotero", symlinks=True)
        copied = _inventory(stage / "zotero")
        expected = {name[7:]: record for name, record in inventory.items() if name.startswith("zotero/")}
        if copied != expected:
            raise ResearchError("Zotero restore checksum mismatch")
        if target.exists() or target.is_symlink():
            raise ResearchError("Restore destination appeared during verification")
        stage.rename(target)
    return {"schema_version": SCHEMA, "output": str(target), "ok": True,
            "project": str(target / "project"), "zotero_data": str(target / "zotero")}
