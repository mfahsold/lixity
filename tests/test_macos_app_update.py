"""Exercise replacement and rollback in disposable app directories."""

import json
import os
import shutil
from pathlib import Path

import pytest

from desktop.scripts import macos_app_update as update

pytestmark = pytest.mark.skipif(os.name != "posix", reason="Local macOS updater uses POSIX file locks")


@pytest.fixture
def bundles(tmp_path, monkeypatch):
    installed = tmp_path / "Applications/Lixity.app"
    incoming = tmp_path / "build/Lixity.app"
    backups = tmp_path / "backups"
    for bundle, label in ((installed, "old"), (incoming, "new")):
        bundle.mkdir(parents=True)
        (bundle / "build").write_text(label, encoding="utf-8")

    def identity(bundle):
        return update.AppIdentity("0.9.1", (bundle / "build").read_text(encoding="utf-8"))

    def copy(command, **_):
        assert command[0] == "/usr/bin/ditto"
        shutil.copytree(command[1], command[2])

    monkeypatch.setattr(update, "_verified_identity", identity)
    monkeypatch.setattr(update, "_require_closed_app", lambda: None)
    monkeypatch.setattr(update.subprocess, "run", copy)
    return installed, incoming, backups, identity


def test_same_version_update_and_repeat_have_one_rollback_copy(bundles):
    installed, incoming, backups, identity = bundles
    result = update.update_installed_app(incoming, "revision", destination=installed, backup_root=backups)
    previous = Path(result["backup_app"])
    assert result["state"] == "updated"
    assert identity(installed).code_hash == "new"
    assert identity(previous).code_hash == "old"
    assert json.loads((previous.parent / "rollout.json").read_text(encoding="utf-8")) == result

    repeated = update.update_installed_app(incoming, "revision", destination=installed, backup_root=backups)
    assert repeated["state"] == "unchanged"
    assert list(backups.glob("before-desktop-update-*")) == [previous.parent]


def test_installed_signature_failure_restores_previous_bundle(bundles, monkeypatch):
    installed, incoming, backups, identity = bundles

    def fail_after_replacement(bundle):
        result = identity(bundle)
        if bundle == installed and result.code_hash == "new":
            raise ValueError("Synthetic invalid signature")
        return result

    monkeypatch.setattr(update, "_verified_identity", fail_after_replacement)
    with pytest.raises(ValueError, match="invalid signature"):
        update.update_installed_app(incoming, "revision", destination=installed, backup_root=backups)
    assert identity(installed).code_hash == "old"
    receipt, = backups.glob("*/rollout.json")
    assert json.loads(receipt.read_text(encoding="utf-8"))["state"] == "rolled_back"


def test_update_rechecks_for_a_launch_after_staging(bundles, monkeypatch):
    installed, incoming, backups, identity = bundles
    open_checks = iter((False, True))

    def reopen_during_copy():
        if next(open_checks):
            raise ValueError("Close Lixity")

    monkeypatch.setattr(update, "_require_closed_app", reopen_during_copy)
    with pytest.raises(ValueError, match="Close Lixity"):
        update.update_installed_app(incoming, "revision", destination=installed, backup_root=backups)
    assert identity(installed).code_hash == "old"
    assert not list(backups.glob("before-desktop-update-*"))


def test_update_rejects_a_downgrade(bundles, monkeypatch):
    installed, incoming, backups, identity = bundles
    monkeypatch.setattr(update, "_verified_identity", lambda bundle: (
        update.AppIdentity("0.10.0", "old") if bundle == installed else identity(bundle)
    ))
    with pytest.raises(ValueError, match="manual rollback"):
        update.update_installed_app(incoming, "revision", destination=installed, backup_root=backups)
    assert identity(installed).code_hash == "old"
    assert not list(backups.glob("before-desktop-update-*"))
