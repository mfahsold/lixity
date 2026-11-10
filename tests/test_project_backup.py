"""Synthetic project backups preserve bytes and fail closed on damaged inputs."""
import json
from pathlib import Path

import pytest

from lixity import project_backup
from lixity.cli import main
from lixity.research import api
from lixity.research.repository import ResearchError


def test_roundtrip(tmp_path: Path) -> None:
    project = tmp_path / 'project'
    api.init(project, title='Synthetic project')
    (project / 'novel.md').write_bytes('Synthetic prose. ä\r\n'.encode())
    (project / 'lixity.toml').write_text('language = "de"\n')
    (project / 'image.png').write_bytes(b'Synthetic image')
    (project / '.env').write_text('EXCLUDED=synthetic')
    bundle = tmp_path / 'bundle'
    result = project_backup.backup(project, bundle, manuscript='novel.md',
                                   settings=['lixity.toml'], attachments=['image.png'])
    assert result['ok']
    restored = tmp_path / 'restored'
    assert project_backup.restore(bundle, restored)['ok']
    assert api.audit(restored)['ok']
    for name in ['novel.md', 'lixity.toml', 'image.png']:
        assert (restored / name).read_bytes() == (project / name).read_bytes()
    assert not (restored / '.env').exists()
    (bundle / 'files/novel.md').write_bytes(b'Tampered')
    with pytest.raises(ResearchError, match='checksum'):
        project_backup.restore(bundle, tmp_path / 'bad')
    assert not (tmp_path / 'bad').exists()


@pytest.mark.parametrize('name', ['../outside.md', '.env', 'research/source.md', 'link.md'])
def test_unsafe_selection(tmp_path: Path, name: str) -> None:
    project = tmp_path / 'project'
    project.mkdir()
    (tmp_path / 'outside.md').write_text('Synthetic')
    (project / 'link.md').symlink_to(tmp_path / 'outside.md')
    with pytest.raises(ResearchError):
        project_backup.backup(project, tmp_path / 'bundle', manuscript=name)
    assert not (tmp_path / 'bundle').exists()


def test_restore_inventory_and_limits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'novel.md').write_text('Synthetic prose')
    bundle = tmp_path / 'bundle'
    project_backup.backup(project, bundle, manuscript='novel.md')
    with pytest.raises(ResearchError):
        project_backup.restore(bundle, project)
    marker = bundle / 'BACKUP.json'
    manifest = json.loads(marker.read_text())
    manifest['files']['../escape'] = manifest['files']['files/novel.md']
    marker.write_text(json.dumps(manifest))
    with pytest.raises(ResearchError):
        project_backup.restore(bundle, tmp_path / 'bad')
    assert not (tmp_path / 'bad').exists()
    monkeypatch.setattr(project_backup, 'MAX_BYTES', 2)
    with pytest.raises(ResearchError, match='limit'):
        project_backup.backup(project, tmp_path / 'large', manuscript='novel.md')


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'novel.md').write_text('Synthetic prose')
    bundle = tmp_path / 'bundle'
    assert main(['project-backup', '--project', str(project), '--manuscript', 'novel.md',
                 '--output', str(bundle)]) == 0
    assert json.loads(capsys.readouterr().out)['ok']
    assert main(['project-restore', '--from', str(bundle), '--to', str(tmp_path / 'new')]) == 0
    assert json.loads(capsys.readouterr().out)['ok']


def test_nested_research_verification(tmp_path: Path) -> None:
    import hashlib

    project = tmp_path / 'project'
    api.init(project, title='Synthetic')
    (project / 'novel.md').write_text('Synthetic prose')
    bundle = tmp_path / 'bundle'
    project_backup.backup(project, bundle, manuscript='novel.md')
    damaged = b'Not a research archive'
    (bundle / 'research.tar.gz').write_bytes(damaged)
    marker = bundle / 'BACKUP.json'
    manifest = json.loads(marker.read_text())
    manifest['files']['research.tar.gz'] = {
        'sha256': hashlib.sha256(damaged).hexdigest(), 'bytes': len(damaged)}
    marker.write_text(json.dumps(manifest))
    with pytest.raises(ResearchError, match='archive'):
        project_backup.restore(bundle, tmp_path / 'bad')
    assert not (tmp_path / 'bad').exists()


def test_bundle_symlink_and_unlisted_files(tmp_path: Path) -> None:
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'novel.md').write_text('Synthetic prose')
    bundle = tmp_path / 'bundle'
    project_backup.backup(project, bundle, manuscript='novel.md')
    extra = bundle / 'extra'
    extra.symlink_to(project / 'novel.md')
    with pytest.raises(ResearchError, match='Symlink'):
        project_backup.restore(bundle, tmp_path / 'bad')
    extra.unlink()
    extra.write_text('Unlisted synthetic file')
    with pytest.raises(ResearchError, match='inventory'):
        project_backup.restore(bundle, tmp_path / 'bad')
    assert not (tmp_path / 'bad').exists()


def test_cli_failure_is_not_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(['project-restore', '--from', str(tmp_path / 'missing'),
                 '--to', str(tmp_path / 'new')]) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert 'failed' in captured.err
    assert not (tmp_path / 'new').exists()


def test_unselected_settings_not_in_research_archive(tmp_path: Path) -> None:
    import tarfile

    project = tmp_path / 'project'
    api.init(project, title='Synthetic')
    (project / 'novel.md').write_text('Synthetic prose')
    (project / 'lixity.toml').write_text('language = "de"\n')
    bundle = tmp_path / 'bundle'
    project_backup.backup(project, bundle, manuscript='novel.md')
    with tarfile.open(bundle / 'research.tar.gz') as archive:
        assert 'lixity.toml' not in archive.getnames()
    project_backup.restore(bundle, tmp_path / 'restored')
    assert not (tmp_path / 'restored/lixity.toml').exists()
    api.export_archive(project, tmp_path / 'standalone.tar.gz')
    with tarfile.open(tmp_path / 'standalone.tar.gz') as archive:
        assert 'lixity.toml' in archive.getnames()


def test_dot_selection_and_normalized_output(tmp_path: Path) -> None:
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'novel.md').write_text('Synthetic prose')
    with pytest.raises(ResearchError):
        project_backup.backup(project, tmp_path / 'bundle', manuscript='.')
    alias = project / '..' / 'project' / 'bundle'
    with pytest.raises(ResearchError, match='outside'):
        project_backup.backup(project, alias, manuscript='novel.md')
    assert not (project / 'bundle').exists()


def test_concurrent_destination_is_not_replaced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'novel.md').write_text('Synthetic prose')
    bundle = tmp_path / 'bundle'
    original = project_backup._destination
    calls = 0

    def race(path: str | Path) -> Path:
        nonlocal calls
        result = original(path)
        calls += 1
        if calls == 2:
            result.mkdir()
        return result

    monkeypatch.setattr(project_backup, '_destination', race)
    with pytest.raises(ResearchError, match='destination'):
        project_backup.backup(project, bundle, manuscript='novel.md')
    assert bundle.is_dir()
    assert list(bundle.iterdir()) == []


def test_restore_rejects_nested_unselected_settings(tmp_path: Path) -> None:
    import hashlib

    project = tmp_path / 'project'
    api.init(project, title='Synthetic')
    (project / 'novel.md').write_text('Synthetic prose')
    (project / 'lixity.toml').write_text('language = "de"\n')
    bundle = tmp_path / 'bundle'
    project_backup.backup(project, bundle, manuscript='novel.md')
    api.export_archive(project, bundle / 'research.tar.gz')
    payload = (bundle / 'research.tar.gz').read_bytes()
    marker = bundle / 'BACKUP.json'
    manifest = json.loads(marker.read_text())
    manifest['files']['research.tar.gz'] = {
        'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)}
    marker.write_text(json.dumps(manifest))
    with pytest.raises(ResearchError, match='settings'):
        project_backup.restore(bundle, tmp_path / 'bad')
    assert not (tmp_path / 'bad').exists()
