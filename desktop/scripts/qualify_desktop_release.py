"""Check a maintainer-reviewed qualification receipt against exact desktop installer bytes."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .verify_desktop_artifacts import (
    DESKTOP_CHECKSUMS,
    PUBLIC_INSTALLER_MANIFESTS,
    PUBLIC_RELEASE_TAG,
    DesktopArtifact,
    desktop_checksums,
    load_verified_artifacts,
    verify_public_installer_inventory,
)

QUALIFICATION_FILE = "desktop-qualification.json"
QUALIFICATION_SCHEMA = "lixity-desktop-qualification/1"
_SOURCE_SHA = re.compile(r"[0-9a-f]{40}")
_CHECKS = (
    "platform_trust",
    "clean_install",
    "upgrade",
    "rollback",
    "app_smoke",
    "project_data_retained",
)
_TRUST = {
    "macos-dmg": "developer-id-notarized",
    "windows-nsis": "authenticode",
    "windows-msi": "authenticode",
    "linux-deb": "sha256",
    "linux-appimage": "sha256",
}


def _check_identity(tag: str, source_sha: str) -> None:
    if not PUBLIC_RELEASE_TAG.fullmatch(tag):
        raise ValueError("Expected a stable desktop release tag such as v0.10.0")
    if not _SOURCE_SHA.fullmatch(source_sha):
        raise ValueError("Expected the full source commit SHA")


def _require_regular_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Missing regular file: {path.name}")


def load_candidate_artifacts(artifacts_dir: Path, *, tag: str) -> tuple[DesktopArtifact, ...]:
    """Load the complete public installer matrix and verify the combined checksums."""
    if not PUBLIC_RELEASE_TAG.fullmatch(tag):
        raise ValueError("Expected a stable desktop release tag such as v0.10.0")
    manifests = {path.name for path in artifacts_dir.glob("desktop-artifacts-*.json")}
    if manifests != PUBLIC_INSTALLER_MANIFESTS:
        raise ValueError("Desktop artifact manifests must cover exactly the four public targets")
    for name in sorted(PUBLIC_INSTALLER_MANIFESTS | {DESKTOP_CHECKSUMS}):
        _require_regular_file(artifacts_dir / name)
    artifacts = load_verified_artifacts(artifacts_dir)
    verify_public_installer_inventory(artifacts, tag=tag)
    if (artifacts_dir / DESKTOP_CHECKSUMS).read_bytes() != desktop_checksums(artifacts):
        raise ValueError("Combined desktop checksums differ from the verified installer inventory")
    return artifacts


def qualification_template(artifacts_dir: Path, *, tag: str, source_sha: str) -> dict[str, Any]:
    """Describe the exact candidate with its review fields awaiting evidence."""
    _check_identity(tag, source_sha)
    artifacts = load_candidate_artifacts(artifacts_dir, tag=tag)
    return {
        "schema_version": QUALIFICATION_SCHEMA,
        "tag": tag,
        "source_sha": source_sha,
        "reviewed_by": "",
        "installers": {
            item.filename: {
                "sha256": item.sha256,
                "os": "",
                "trust": _TRUST[item.kind],
                "checks": dict.fromkeys(_CHECKS, False),
                "evidence": "",
            }
            for item in artifacts
        },
    }


def _recorded_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_qualified_artifacts(
    artifacts_dir: Path, qualification_path: Path, *, tag: str, source_sha: str,
) -> tuple[DesktopArtifact, ...]:
    """Verify reviewed checks against the tag, source SHA and exact installer bytes.

    The receipt records maintainer verification performed on each platform.
    Verify build attestations and platform signatures separately.
    """
    _check_identity(tag, source_sha)
    _require_regular_file(qualification_path)
    receipt = json.loads(qualification_path.read_text(encoding="utf-8"))
    if (
        not isinstance(receipt, dict)
        or receipt.keys() != {"schema_version", "tag", "source_sha", "reviewed_by", "installers"}
        or receipt["schema_version"] != QUALIFICATION_SCHEMA
    ):
        raise ValueError("Invalid desktop qualification receipt")
    if (receipt["tag"], receipt["source_sha"]) != (tag, source_sha):
        raise ValueError("Desktop qualification belongs to a different release tag or source")
    if not _recorded_text(receipt["reviewed_by"]):
        raise ValueError("Desktop qualification requires a recorded reviewer")

    artifacts = load_candidate_artifacts(artifacts_dir, tag=tag)
    entries = receipt["installers"]
    if not isinstance(entries, dict) or entries.keys() != {item.filename for item in artifacts}:
        raise ValueError("Qualification must describe exactly the verified installer filenames")
    for item in artifacts:
        record = entries[item.filename]
        if not isinstance(record, dict) or record.keys() != {"sha256", "os", "trust", "checks", "evidence"}:
            raise ValueError(f"Invalid desktop qualification entry: {item.filename}")
        if record["sha256"] != item.sha256:
            raise ValueError(f"Qualified installer SHA-256 differs: {item.filename}")
        if record["trust"] != _TRUST[item.kind]:
            raise ValueError(f"Wrong platform trust requirement for {item.filename}. Expected {_TRUST[item.kind]}")
        if not _recorded_text(record["os"]) or not _recorded_text(record["evidence"]):
            raise ValueError(f"Record the clean OS version and verification evidence for {item.filename}")
        checks = record["checks"]
        if not isinstance(checks, dict) or checks.keys() != set(_CHECKS):
            raise ValueError(f"Invalid desktop qualification checks for {item.filename}")
        incomplete = [name for name in _CHECKS if checks[name] is not True]
        if incomplete:
            raise ValueError(f"Incomplete desktop qualification for {item.filename}: {', '.join(incomplete)}")
    return artifacts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, required=True, help="Flattened installer bundle")
    parser.add_argument("--tag", required=True, help="Expected public release tag")
    parser.add_argument("--source-sha", required=True, help="Expected full source commit SHA")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--template", action="store_true", help="Print a blank review receipt for the candidate")
    mode.add_argument("--qualification", type=Path, help="Verify this completed review receipt")
    args = parser.parse_args(argv)
    try:
        if args.template:
            print(json.dumps(qualification_template(args.artifacts_dir, tag=args.tag, source_sha=args.source_sha),
                             indent=2))
        else:
            artifacts = load_qualified_artifacts(args.artifacts_dir, args.qualification,
                                                 tag=args.tag, source_sha=args.source_sha)
            print(json.dumps({"state": "qualified", "tag": args.tag, "source_sha": args.source_sha,
                              "verified_installers": len(artifacts)}))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
