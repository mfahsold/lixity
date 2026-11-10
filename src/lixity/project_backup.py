"""Explicit project bundles reusing the authoritative research archive transport."""

import hashlib
import json
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from .research import api
from .research.repository import ResearchError
from .site_export import _publish_new_directory

SCHEMA = 'lixity-project-backup/1'
MAX_BYTES = 10 * 1024 * 1024 * 1024
MAX_FILES = 10000
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
EXCLUSIONS = [
    'Unselected files and external linked attachments',
    'Hidden directories, credentials, browser drafts, recovery and undo history',
    'Application profiles, caches, generated exports and Zotero databases',
]


def _plain_path(path: Path) -> Path:
    path = path.expanduser().absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ResearchError('Symlink paths are not supported')
    return path.resolve()


def _destination(path: str | Path) -> Path:
    target = _plain_path(Path(path))
    if target.exists():
        raise ResearchError('Destination must not exist')
    return target


def _selection(name: str) -> str:
    path = PurePosixPath(name)
    if (not name or not path.parts or path.is_absolute() or str(path) != name or '\\' in name
            or ':' in name or any(p.startswith('.') for p in path.parts)
            or path.parts[0].lower() in {'research', 'exports', 'node_modules'}):
        raise ResearchError('Select a visible project-relative file outside managed directories')
    return name


def _digest(path: Path) -> dict[str, Any]:
    _plain_path(path)
    if not path.is_file():
        raise ResearchError('Backup input must be a regular file')
    size = 0
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(65536):
            size += len(chunk)
            if size > MAX_BYTES:
                raise ResearchError('Project backup exceeds size limit')
            digest.update(chunk)
    return {'sha256': digest.hexdigest(), 'bytes': size}


def _inventory(root: Path) -> dict[str, dict[str, Any]]:
    _plain_path(root)
    if not root.is_dir():
        raise ResearchError('Bundle must be a directory')
    result: dict[str, dict[str, Any]] = {}
    total = 0
    entries = 0
    for path in root.rglob('*'):
        entries += 1
        if entries > MAX_FILES * 2:
            raise ResearchError('Project backup exceeds entry limit')
        _plain_path(path)
        if path.is_dir():
            continue
        record = _digest(path)
        total += record['bytes']
        if total > MAX_BYTES or len(result) >= MAX_FILES:
            raise ResearchError('Project backup exceeds size or file limit')
        result[path.relative_to(root).as_posix()] = record
    return result


def backup(project: str | Path, output: str | Path, *, manuscript: str,
           settings: list[str] | None = None,
           attachments: list[str] | None = None) -> dict[str, Any]:
    """Capture selected files and research; require writers to be stopped by caller."""
    root = _plain_path(Path(project))
    target = _destination(output)
    if not root.is_dir() or target == root or root in target.parents:
        raise ResearchError('Backup output must be outside the existing project')
    selected = {'manuscript': [_selection(manuscript)],
                'settings': [_selection(n) for n in settings or []],
                'attachments': [_selection(n) for n in attachments or []]}
    if any(n not in {'lixity.toml', 'pyproject.toml'} for n in selected['settings']):
        raise ResearchError('Settings must be root-local lixity.toml or pyproject.toml')
    names = [n for group in selected.values() for n in group]
    if len(set(names)) != len(names) or len(names) >= MAX_FILES:
        raise ResearchError('Duplicate selections or file limit exceeded')
    before = {n: _digest(root / n) for n in names}
    if sum(item['bytes'] for item in before.values()) > MAX_BYTES:
        raise ResearchError('Project backup exceeds size limit')
    research = root / 'research'
    _plain_path(research)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.lixity-backup-', dir=target.parent) as directory:
        stage = Path(directory) / 'bundle'
        stage.mkdir()
        for name in names:
            dest = stage / 'files' / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, dest)
            if _digest(dest) != before[name] or _digest(root / name) != before[name]:
                raise ResearchError('Selected file changed during backup')
        research_info = None
        if research.exists():
            research_info = api.export_archive(root, stage / 'research.tar.gz', include_project_config=False)
            api.restore_archive(stage / 'research.tar.gz', Path(directory) / 'verified')
        if {n: _digest(root / n) for n in names} != before:
            raise ResearchError('Selected files changed during backup')
        manifest = {'schema_version': SCHEMA, 'selected': selected,
                    'research': research_info, 'exclusions': EXCLUSIONS,
                    'files': _inventory(stage)}
        content = json.dumps(manifest, indent=2).encode('utf-8')
        if len(content) > MAX_MANIFEST_BYTES:
            raise ResearchError('Project backup manifest exceeds limit')
        (stage / 'BACKUP.json').write_bytes(content)
        _inventory(stage)
        _destination(target)
        _publish_new_directory(stage, target)
    return {'schema_version': SCHEMA, 'ok': True, 'output': str(target),
            'selected': selected, 'research_included': research_info is not None,
            'exclusions': EXCLUSIONS}


def restore(bundle: str | Path, output: str | Path) -> dict[str, Any]:
    """Verify the complete bundle before publishing a newly restored project."""
    source = _plain_path(Path(bundle))
    target = _destination(output)
    marker = source / 'BACKUP.json'
    _plain_path(marker)
    if not marker.is_file() or marker.stat().st_size > MAX_MANIFEST_BYTES:
        raise ResearchError('Missing or oversized project backup manifest')
    try:
        manifest = json.loads(marker.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError) as exc:
        raise ResearchError('Invalid project backup manifest') from exc
    actual = _inventory(source)
    marker_digest = actual.pop('BACKUP.json', None)
    if (not isinstance(manifest, dict) or manifest.get('schema_version') != SCHEMA
            or manifest.get('files') != actual):
        raise ResearchError('Project backup checksum or inventory mismatch')
    selected = manifest.get('selected')
    if not isinstance(selected, dict) or set(selected) != {'manuscript', 'settings', 'attachments'}:
        raise ResearchError('Invalid project backup selection')
    names: list[str] = []
    for group in selected.values():
        if not isinstance(group, list) or any(not isinstance(n, str) for n in group):
            raise ResearchError('Invalid project backup selection')
        names.extend(_selection(n) for n in group)
    if (len(selected['manuscript']) != 1 or len(set(names)) != len(names)
            or any(n not in {'lixity.toml', 'pyproject.toml'} for n in selected['settings'])):
        raise ResearchError('Invalid manuscript or settings selection')
    has_research = manifest.get('research') is not None
    expected = {'files/' + n for n in names}
    if has_research:
        expected.add('research.tar.gz')
    if set(actual) != expected:
        raise ResearchError('Unexpected project backup file inventory')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.lixity-restore-', dir=target.parent) as directory:
        stage = Path(directory) / 'project'
        if has_research:
            api.restore_archive(source / 'research.tar.gz', stage)
            if (stage / 'lixity.toml').exists():
                raise ResearchError('Project bundle research archive must not include root settings')
        else:
            stage.mkdir()
        for name in names:
            dest = stage / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / 'files' / name, dest)
            if _digest(dest) != actual['files/' + name]:
                raise ResearchError('Project restore checksum mismatch')
        if _inventory(source) != {**actual, 'BACKUP.json': marker_digest}:
            raise ResearchError('Project bundle changed during restoration')
        if has_research and not api.audit(stage)['ok']:
            raise ResearchError('Restored research integrity audit failed')
        _destination(target)
        _publish_new_directory(stage, target)
    return {'schema_version': SCHEMA, 'ok': True, 'output': str(target),
            'research_included': has_research, 'exclusions': EXCLUSIONS}
