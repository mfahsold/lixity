#!/usr/bin/env python3
"""Prepare the pinned Azure signing client and sign Windows bundle files."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from collections.abc import Mapping
from pathlib import Path

CLIENT_VERSION = "1.0.146"
CLIENT_URL = (
    "https://api.nuget.org/v3-flatcontainer/microsoft.artifactsigning.client/"
    f"{CLIENT_VERSION}/microsoft.artifactsigning.client.{CLIENT_VERSION}.nupkg"
)
CLIENT_SHA256 = "7761e5d8f31e54b764da21d33cd8b0a2940e1b05526c7dfcb5e94b0431426f70"
SDK_VERSION = "10.0.26100.0"
TIMESTAMP_URL = "http://timestamp.acs.microsoft.com"
DLIB_LIBRARY = "Azure.CodeSigning.Dlib.dll"
AZURE_FIELDS = {
    "LIXITY_AZURE_SIGNING_ENDPOINT": "Endpoint",
    "LIXITY_AZURE_SIGNING_ACCOUNT": "CodeSigningAccountName",
    "LIXITY_AZURE_SIGNING_PROFILE": "CertificateProfileName",
}
AZURE_CREDENTIALS = ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")


def signing_metadata(env: Mapping[str, str]) -> dict[str, str | list[str]]:
    missing = [key for key in (*AZURE_FIELDS, *AZURE_CREDENTIALS) if not env.get(key, "").strip()]
    if missing:
        raise ValueError(f"Missing Azure Artifact Signing configuration: {', '.join(missing)}")

    metadata = {field: env[key].strip() for key, field in AZURE_FIELDS.items()}
    if not re.fullmatch(r"https://[a-z0-9]+\.codesigning\.azure\.net", metadata["Endpoint"]):
        raise ValueError("LIXITY_AZURE_SIGNING_ENDPOINT must be an HTTPS Azure signing region endpoint")
    return {
        **metadata,
        "ExcludeCredentials": [
            "ManagedIdentityCredential",
            "WorkloadIdentityCredential",
            "SharedTokenCacheCredential",
            "VisualStudioCredential",
            "VisualStudioCodeCredential",
            "AzureCliCredential",
            "AzurePowerShellCredential",
            "AzureDeveloperCliCredential",
            "InteractiveBrowserCredential",
        ],
    }


def extract_signing_client(package: bytes, destination: Path) -> Path:
    if hashlib.sha256(package).hexdigest() != CLIENT_SHA256:
        raise ValueError("Microsoft.ArtifactSigning.Client SHA-256 mismatch")

    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        for member in archive.infolist():
            if re.fullmatch(r"bin/x64/[A-Za-z0-9._-]+", member.filename):
                (destination / Path(member.filename).name).write_bytes(archive.read(member))
    library = destination / DLIB_LIBRARY
    if not library.is_file():
        raise FileNotFoundError(f"Expected the x64 signing library {DLIB_LIBRARY} in the package")
    return library


def prepare_signing() -> None:
    metadata = signing_metadata(os.environ)
    sdk_dir = Path(os.environ["PROGRAMFILES(X86)"]) / "Windows Kits" / "10" / "bin"
    signtool = sdk_dir / SDK_VERSION / "x64" / "signtool.exe"
    if not signtool.is_file():
        raise FileNotFoundError(f"Install the Windows SDK {SDK_VERSION} x64 signing tools")
    work_dir = Path(tempfile.mkdtemp(prefix="lixity-windows-signing-", dir=os.environ["RUNNER_TEMP"]))
    with urllib.request.urlopen(CLIENT_URL, timeout=60) as response:  # noqa: S310 - pinned HTTPS URL and digest
        library = extract_signing_client(response.read(), work_dir)
    metadata_file = work_dir / "azure-signing-metadata.json"
    metadata_file.write_text(json.dumps(metadata), encoding="utf-8")
    config = work_dir / "tauri-signing.json"
    sign_command = {
        "cmd": sys.executable,
        "args": [
            str(Path(__file__).resolve()), "sign",
            "--signtool", str(signtool), "--library", str(library), "--metadata", str(metadata_file), "%1",
        ],
    }
    config.write_text(json.dumps({"bundle": {"windows": {"signCommand": sign_command}}}), encoding="utf-8")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8", newline="\n") as output:
        output.write(f"config={config}\nsigntool={signtool}\n")


def verify_signature(signtool: Path, path: Path) -> None:
    """Check every embedded Authenticode signature, including timestamps."""
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError(f"Expected a regular Windows binary at {path}")
    try:
        subprocess.run(  # noqa: S603 - absolute SignTool executable and separate arguments
            [str(signtool.resolve()), "verify", "/pa", "/all", "/tw", str(path.resolve())],
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise ValueError(f"{path.name}: Authenticode signature or timestamp verification failed") from error


def sign_file(signtool: Path, library: Path, metadata: Path, path: Path) -> None:
    subprocess.run(  # noqa: S603 - absolute SignTool executable and separate arguments
        [
            str(signtool.resolve()), "sign", "/fd", "SHA256", "/tr", TIMESTAMP_URL, "/td", "SHA256",
            "/dlib", str(library), "/dmdf", str(metadata), str(path.resolve()),
        ],
        check=True,
    )
    # Tauri signs the patched app before embedding it and then restores the unsigned build executable.
    verify_signature(signtool, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("prepare", help="Prepare the signed GitHub Actions build")
    sign = subparsers.add_parser("sign", help="Sign and verify one file from the Tauri bundle")
    sign.add_argument("--signtool", required=True, type=Path)
    sign.add_argument("--library", required=True, type=Path)
    sign.add_argument("--metadata", required=True, type=Path)
    sign.add_argument("file", type=Path)
    verify = subparsers.add_parser("verify", help="Verify one Windows file, such as the installed app")
    verify.add_argument("--signtool", required=True, type=Path)
    verify.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare_signing()
        elif args.command == "sign":
            sign_file(args.signtool, args.library, args.metadata, args.file)
        else:
            verify_signature(args.signtool, args.file)
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
