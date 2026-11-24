"""Offline tests for the official Windows desktop signing configuration and gate."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import zipfile

import pytest

from desktop.scripts import verify_desktop_artifacts
from desktop.scripts import windows_artifact_signing as signing


def test_prepare_signing_pins_client_and_keeps_credentials_out_of_outputs(tmp_path, monkeypatch):
    env = {
        **dict.fromkeys(signing.AZURE_CREDENTIALS, "synthetic-credential"),
        "LIXITY_AZURE_SIGNING_ENDPOINT": "https://weu.codesigning.azure.net",
        "LIXITY_AZURE_SIGNING_ACCOUNT": "example-signing-account",
        "LIXITY_AZURE_SIGNING_PROFILE": "ExampleProfile",
        "PROGRAMFILES(X86)": str(tmp_path / "Program Files (x86)"),
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_OUTPUT": str(tmp_path / "output"),
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("AZURE_CLIENT_SECRET")
    with pytest.raises(ValueError, match="Missing Azure Artifact Signing configuration: AZURE_CLIENT_SECRET"):
        signing.prepare_signing()
    monkeypatch.setenv("AZURE_CLIENT_SECRET", env["AZURE_CLIENT_SECRET"])

    signtool = (
        tmp_path / "Program Files (x86)" / "Windows Kits" / "10" / "bin"
        / signing.SDK_VERSION / "x64" / "signtool.exe"
    )
    signtool.parent.mkdir(parents=True)
    signtool.touch()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr(f"bin/x64/{signing.DLIB_LIBRARY}", b"x64 signing fixture")
        package.writestr(f"bin/x86/{signing.DLIB_LIBRARY}", b"x86 signing fixture")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        signing.extract_signing_client(archive.getvalue(), tmp_path)
    monkeypatch.setattr(signing, "CLIENT_SHA256", hashlib.sha256(archive.getvalue()).hexdigest())
    monkeypatch.setattr(signing.urllib.request, "urlopen", lambda *_args, **_kwargs: io.BytesIO(archive.getvalue()))

    signing.prepare_signing()
    config = next(tmp_path.glob("lixity-windows-signing-*/tauri-signing.json"))
    library = config.with_name(signing.DLIB_LIBRARY)
    metadata_file = config.with_name("azure-signing-metadata.json")
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert metadata["Endpoint"] == env["LIXITY_AZURE_SIGNING_ENDPOINT"]
    assert metadata["CodeSigningAccountName"] == env["LIXITY_AZURE_SIGNING_ACCOUNT"]
    assert metadata["CertificateProfileName"] == env["LIXITY_AZURE_SIGNING_PROFILE"]
    assert "AzureCliCredential" in metadata["ExcludeCredentials"]
    assert library.read_bytes() == b"x64 signing fixture"
    sign_command = json.loads(config.read_text(encoding="utf-8"))["bundle"]["windows"]["signCommand"]
    assert sign_command["args"][1:] == [
        "sign", "--signtool", str(signtool), "--library", str(library), "--metadata", str(metadata_file), "%1",
    ]
    assert "synthetic-credential" not in "".join(
        file.read_text(encoding="utf-8") for file in (config, metadata_file, tmp_path / "output")
    )


def test_sign_callback_requires_timestamped_authenticode_for_embedded_app(tmp_path, monkeypatch):
    commands = []
    app = tmp_path / "Lixity.exe"
    app.touch()
    signtool = tmp_path / "sdk" / "signtool.exe"
    library = tmp_path / signing.DLIB_LIBRARY
    metadata = tmp_path / "metadata.json"

    def run(command, *, check):
        assert check
        commands.append(command)
        if command[1] == "verify":
            raise subprocess.CalledProcessError(2, command)

    monkeypatch.setattr(signing.subprocess, "run", run)
    with pytest.raises(ValueError, match=r"Lixity\.exe: Authenticode signature or timestamp verification failed"):
        signing.sign_file(signtool, library, metadata, app)
    assert commands == [
        [
            str(signtool.resolve()), "sign", "/fd", "SHA256", "/tr", signing.TIMESTAMP_URL,
            "/td", "SHA256", "/dlib", str(library), "/dmdf", str(metadata), str(app.resolve()),
        ],
        [str(signtool.resolve()), "verify", "/pa", "/all", "/tw", str(app.resolve())],
    ]


def test_every_windows_installer_must_pass_signature_verification_before_hashing(tmp_path, monkeypatch):
    msi = tmp_path / "msi" / "Lixity.msi"
    exe = tmp_path / "nsis" / "Lixity.exe"
    msi.parent.mkdir()
    exe.parent.mkdir()
    msi.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(512))
    exe.write_bytes(b"MZ" + bytes(512))
    events = []
    signtool = tmp_path / "signtool.exe"

    def verify(tool, file):
        assert tool == signtool
        events.append(("verify", file.name))
        if file == exe:
            raise ValueError("Unsigned test installer")

    def sha256(file):
        events.append(("sha256", file.name))
        return ""

    monkeypatch.setattr(verify_desktop_artifacts, "verify_signature", verify)
    monkeypatch.setattr(verify_desktop_artifacts, "sha256_file", sha256)
    with pytest.raises(ValueError, match="Unsigned test installer"):
        verify_desktop_artifacts.collect_artifacts(tmp_path, windows_signtool=signtool)
    assert events == [("verify", "Lixity.msi"), ("verify", "Lixity.exe")]
    events.clear()
    verify_desktop_artifacts.collect_artifacts(tmp_path)
    assert events == [("sha256", "Lixity.msi"), ("sha256", "Lixity.exe")]
