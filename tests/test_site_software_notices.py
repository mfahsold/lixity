"""Reading websites retain notices from the loaded package's installation."""

import pytest

from lixity import site_export
from lixity.research.repository import ResearchError

pytestmark = pytest.mark.portability


def installed_distribution(root, license_member):
    metadata = root / 'lixity-0.7.4.dist-info'
    metadata.mkdir(parents=True)
    (metadata / 'METADATA').write_text('Metadata-Version: 2.4\nName: lixity\nVersion: 0.7.4\n')
    members = [metadata.relative_to(root) / 'METADATA', metadata.relative_to(root) / 'RECORD']
    if license_member is not None:
        license_path = metadata / license_member
        license_path.parent.mkdir(parents=True, exist_ok=True)
        license_path.write_bytes(b'SYNTHETIC_INSTALLED_LICENSE')
        members.append(license_path.relative_to(root))
    (metadata / 'RECORD').write_text(''.join(f'{member.as_posix()},,\n' for member in members))


@pytest.mark.parametrize('license_member', ['licenses/LICENSE', 'LICENSE'])
def test_notices_use_loaded_installation_when_checkout_metadata_shadows_it(tmp_path, monkeypatch, license_member):
    installed = tmp_path / 'environment' / 'site-packages'
    installed_distribution(installed, license_member)
    checkout = tmp_path / 'checkout' / 'src'
    metadata = checkout / 'lixity.egg-info'
    metadata.mkdir(parents=True)
    (metadata / 'PKG-INFO').write_text('Metadata-Version: 2.4\nName: lixity\nVersion: 0.7.4\n')
    (metadata / 'SOURCES.txt').write_text('LICENSE\n')
    monkeypatch.syspath_prepend(str(installed))
    monkeypatch.syspath_prepend(str(checkout))
    monkeypatch.setattr(site_export, '__file__', str(installed / 'lixity' / 'site_export.py'))

    notices = site_export._software_notices()

    assert notices['licenses/Lixity-LICENSE'] == b'SYNTHETIC_INSTALLED_LICENSE'


@pytest.mark.parametrize('own_metadata', [False, True])
def test_notices_fail_closed_without_loaded_installation_license(tmp_path, monkeypatch, own_metadata):
    installed = tmp_path / 'environment' / 'site-packages'
    if own_metadata:
        installed_distribution(installed, None)
    elsewhere = tmp_path / 'other-environment' / 'site-packages'
    installed_distribution(elsewhere, 'licenses/LICENSE')
    monkeypatch.syspath_prepend(str(elsewhere))
    monkeypatch.setattr(site_export, '__file__', str(installed / 'lixity' / 'site_export.py'))

    with pytest.raises(ResearchError, match='installed Lixity license is unavailable'):
        site_export._software_notices()
