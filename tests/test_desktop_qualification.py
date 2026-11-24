"""Test the maintainer receipt against the same manifests used for CI builds."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from desktop.scripts import qualify_desktop_release as qualification
from desktop.scripts import verify_desktop_artifacts as verifier

TAG = "v0.10.0"
SOURCE = "1" * 40


@pytest.fixture
def candidate(tmp_path: Path) -> Path:
    directory = tmp_path / "candidate"
    prototypes = {
        "aarch64-apple-darwin": {"dmg/Lixity_0.10.0_aarch64.dmg": b"x\x01"},
        "x86_64-apple-darwin": {"dmg/Lixity_0.10.0_x64.dmg": b"x\x01"},
        "x86_64-pc-windows-msvc": {
            "msi/Lixity_0.10.0_x64_de-DE.msi": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
            "msi/Lixity_0.10.0_x64_en-US.msi": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
            "nsis/Lixity_0.10.0_x64-setup.exe": b"MZ",
        },
        "x86_64-unknown-linux-gnu": {
            "deb/Lixity_0.10.0_amd64.deb": b"!<arch>\n",
            "appimage/Lixity_0.10.0_amd64.AppImage": b"\x7fELF",
        },
    }
    for target, entries in prototypes.items():
        bundles = tmp_path / target
        for name, signature in entries.items():
            path = bundles / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(signature.ljust(512, b"\0"))
        assert verifier.main([
            str(bundles), "--target", target, "--out-dir", str(directory), "--copy-to", str(directory),
        ]) == 0
    artifacts = verifier.load_verified_artifacts(directory)
    (directory / verifier.DESKTOP_CHECKSUMS).write_bytes(verifier.desktop_checksums(artifacts))
    return directory


def _complete_receipt(candidate: Path) -> dict:
    receipt = qualification.qualification_template(candidate, tag=TAG, source_sha=SOURCE)
    receipt["reviewed_by"] = "Desktop reviewer"
    for entry in receipt["installers"].values():
        entry["os"] = "Synthetic OS version for the contract fixture"
        entry["evidence"] = "Synthetic record for the contract fixture"
        entry["checks"] = dict.fromkeys(entry["checks"], True)
    return receipt


def _write_receipt(candidate: Path, report: dict) -> Path:
    path = candidate / qualification.QUALIFICATION_FILE
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def test_qualification_loads_all_retained_installer_bytes(candidate):
    receipt = _write_receipt(candidate, _complete_receipt(candidate))
    artifacts = qualification.load_qualified_artifacts(candidate, receipt, tag=TAG, source_sha=SOURCE)
    assert artifacts == verifier.load_verified_artifacts(candidate)
    assert len(artifacts) == 7


def test_test_build_inventory_and_unreviewed_template_require_qualification(candidate):
    qualifications = candidate / qualification.QUALIFICATION_FILE
    with pytest.raises(ValueError, match="Missing regular file"):
        qualification.load_qualified_artifacts(candidate, qualifications, tag=TAG, source_sha=SOURCE)
    receipt = qualification.qualification_template(candidate, tag=TAG, source_sha=SOURCE)
    _write_receipt(candidate, receipt)
    with pytest.raises(ValueError, match="requires a recorded reviewer"):
        qualification.load_qualified_artifacts(candidate, qualifications, tag=TAG, source_sha=SOURCE)


def test_qualification_is_bound_to_one_source_commit(candidate):
    receipt = _write_receipt(candidate, _complete_receipt(candidate))
    with pytest.raises(ValueError, match="different release tag or source"):
        qualification.load_qualified_artifacts(candidate, receipt, tag=TAG, source_sha="2" * 40)


@pytest.mark.parametrize(("field", "value", "message"), (
    ("trust", "ad-hoc", "Wrong platform trust requirement"),
    ("checks", {"clean_install": True}, "Invalid desktop qualification checks"),
    ("upgrade", 1, "Incomplete desktop qualification"),
    ("platform_trust", False, "Incomplete desktop qualification"),
    ("sha256", "2" * 64, "Qualified installer SHA-256 differs"),
))
def test_qualification_checks_each_individual_file(candidate, field, value, message):
    report = _complete_receipt(candidate)
    item = report["installers"]["Lixity_0.10.0_aarch64.dmg"]
    if field in item["checks"]:
        item["checks"][field] = value
    else:
        item[field] = value
    receipt = _write_receipt(candidate, report)
    with pytest.raises(ValueError, match=message):
        qualification.load_qualified_artifacts(candidate, receipt, tag=TAG, source_sha=SOURCE)


def test_candidate_rechecks_combined_checksum_file(candidate):
    (candidate / verifier.DESKTOP_CHECKSUMS).write_bytes(b"not the verified checksums\n")
    with pytest.raises(ValueError, match="Combined desktop checksums differ"):
        qualification.qualification_template(candidate, tag=TAG, source_sha=SOURCE)


def test_candidate_rejects_incomplete_matrix_and_mixed_versions(candidate):
    with pytest.raises(ValueError, match="Installer filename does not match"):
        qualification.load_candidate_artifacts(candidate, tag="v0.10.1")
    (candidate / "desktop-artifacts-x86_64-apple-darwin.json").unlink()
    with pytest.raises(ValueError, match="exactly the four public targets"):
        qualification.load_candidate_artifacts(candidate, tag=TAG)
