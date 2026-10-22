"""Export destinations must never replace the selected manuscript or its aliases."""

from pathlib import Path

import pytest

from lixity.cli import main
from lixity.io import FileUtils

pytestmark = pytest.mark.portability


@pytest.mark.parametrize('command', ['pdf', 'dashboard'])
@pytest.mark.parametrize('alias', ['same', 'symlink', 'hardlink'])
def test_cli_exports_reject_manuscript_aliases(tmp_path: Path, monkeypatch, capsys, command, alias):
    source = tmp_path / 'manuscript.md'
    original = b'# Synthetic source\n\n## One\n\nA door opens beside the quay.\n'
    source.write_bytes(original)
    target = source if alias == 'same' else tmp_path / 'output'
    if alias == 'symlink':
        target.symlink_to(source)
    elif alias == 'hardlink':
        target.hardlink_to(source)
    import lixity.pdf_export as pdf
    monkeypatch.setattr(pdf, 'compose_pdf', lambda *_args, **_kwargs: b'%PDF-synthetic')
    status = main([command, str(source), '-o', str(target)])
    assert status == 1
    assert source.read_bytes() == original
    assert target.read_bytes() == original
    assert 'manuscript' in capsys.readouterr().err.lower()


def test_text_writer_preserves_target_when_guard_fails_after_staging(tmp_path: Path):
    target = tmp_path / 'reading.html'
    target.write_text('Previous reviewed copy')
    def reject():
        raise ValueError('Source relationship changed')
    with pytest.raises(ValueError, match='relationship changed'):
        FileUtils.atomic_write_if_changed(str(target), 'New copy', before_replace=reject)
    assert target.read_text() == 'Previous reviewed copy'
    assert sorted(p.name for p in tmp_path.iterdir()) == ['reading.html']


def test_distinct_output_can_be_new_without_creating_it(tmp_path: Path):
    source = tmp_path / 'manuscript.md'
    source.write_text('Synthetic prose.')
    target = tmp_path / 'absent' / 'copy.pdf'
    FileUtils.require_distinct_output(str(source), str(target))
    assert not target.parent.exists()
