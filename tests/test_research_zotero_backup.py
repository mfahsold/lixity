"""Paired backups retain external media and reject corrupted restoration inputs."""
import tempfile
import unittest
from pathlib import Path

from lixity.research import api, zotero_backup
from lixity.research.repository import ResearchError


class TestZoteroBackup(unittest.TestCase):
    def test_pair_roundtrip_and_corruption_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / 'project'
            data = root / 'data'
            data.mkdir()
            (data/'zotero.sqlite').write_bytes(b'Synthetic database fixture')
            (data/'storage').mkdir()
            (data/'storage'/'audio.wav').write_bytes(b'Synthetic media fixture')
            api.init(project, title='Paired backup test')
            with self.assertRaises(ResearchError):
                zotero_backup.backup(project, data, root/'denied')
            bundle = root/'bundle'
            zotero_backup.backup(project, data, bundle, confirm_closed=True)
            restored = root/'restored'
            zotero_backup.restore(bundle, restored)
            self.assertTrue(api.audit(restored/'project')['ok'])
            self.assertEqual((restored/'zotero/storage/audio.wav').read_bytes(), (data/'storage/audio.wav').read_bytes())
            (bundle/'zotero/storage/audio.wav').write_bytes(b'Tampered')
            with self.assertRaisesRegex(ResearchError, 'checksum'):
                zotero_backup.restore(bundle, root/'bad')
            self.assertFalse((root/'bad').exists())

    def test_symlinks_and_overwrite_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api.init(root/'project', title='Synthetic')
            (root/'data').mkdir()
            (root/'data/zotero.sqlite').write_bytes(b'Synthetic')
            (root/'data/link').symlink_to(root/'project', target_is_directory=True)
            with self.assertRaises(ResearchError):
                zotero_backup.backup(root/'project', root/'data', root/'bundle', confirm_closed=True)
            self.assertFalse((root/'bundle').exists())
            with self.assertRaises(ResearchError):
                zotero_backup.restore(root/'data', root/'project')
