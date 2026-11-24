"""Replace a closed, ad-hoc-signed Lixity development app with a verified build."""

from __future__ import annotations

import json
import plistlib
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

INSTALLATION = Path("/Applications/Lixity.app")
BACKUPS = Path("Library/Application Support/local-installation-backups/Lixity")
IDENTIFIER = "io.github.mfahsold.Lixity"
VERSION = re.compile(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){2}")


@dataclass(frozen=True)
class AppIdentity:
    version: str
    code_hash: str


def _verified_identity(app: Path) -> AppIdentity:
    if app.is_symlink() or not app.is_dir():
        raise ValueError(f"Expected a regular app bundle at {app}")
    with (app / "Contents/Info.plist").open("rb") as stream:
        info = plistlib.load(stream)
    version = info.get("CFBundleShortVersionString")
    if info.get("CFBundleIdentifier") != IDENTIFIER or not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ValueError(f"Expected a Lixity app with a stable version at {app}")
    subprocess.run(  # noqa: S603 - fixed macOS code-signing tool
        ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)], check=True,
    )
    result = subprocess.run(  # noqa: S603 - fixed macOS code-signing tool
        ["/usr/bin/codesign", "-d", "--verbose=4", str(app)],
        capture_output=True, text=True, check=True,
    )
    code_hash = re.search(r"^CDHash=([a-f0-9]{40})$", result.stderr, re.M)
    if "Signature=adhoc" not in result.stderr.splitlines() or code_hash is None:
        raise ValueError(f"Only ad-hoc-signed local test builds can use this update at {app}")
    return AppIdentity(version, code_hash.group(1))


def _require_closed_app() -> None:
    result = subprocess.run(
        ["/usr/bin/pgrep", "-f", r"(^|/)lixity-desktop( |$)|-m lixity serve --_desktop-mode"],
        capture_output=True, check=False,
    )
    if result.returncode != 1:
        raise ValueError("Close Lixity and its desktop engine before updating")


def _write_receipt(path: Path, result: dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def update_installed_app(
    candidate: Path, revision: str, *, destination: Path = INSTALLATION, backup_root: Path | None = None,
) -> dict[str, object]:
    """Install a staged local build while retaining the previous app in a private backup."""
    import fcntl

    backups = backup_root if backup_root is not None else Path.home() / BACKUPS
    if destination.resolve() == candidate.resolve():
        raise ValueError("Build the update in a separate location")
    backups.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (backups / "update.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _require_closed_app()
        installed = _verified_identity(destination)
        incoming = _verified_identity(candidate)
        if tuple(map(int, incoming.version.split("."))) < tuple(map(int, installed.version.split("."))):
            raise ValueError(f"Downgrade from {installed.version} to {incoming.version} requires manual rollback")
        result: dict[str, object] = {
            "state": "unchanged", "source_revision": revision, "installed_app": str(destination),
            "previous": asdict(installed), "candidate": asdict(incoming),
        }
        if installed == incoming:
            return result
        if destination.stat().st_dev != backups.stat().st_dev:
            raise ValueError("The app and backup folder must be on the same filesystem")

        with tempfile.TemporaryDirectory(prefix=".lixity-update-", dir=destination.parent) as staging:
            staged = Path(staging) / destination.name
            subprocess.run(  # noqa: S603 - fixed macOS bundle-preserving copy
                ["/usr/bin/ditto", str(candidate), str(staged)], check=True,
            )
            if _verified_identity(staged) != incoming:
                raise ValueError("The staged copy differs from the verified build")
            _require_closed_app()
            backup = Path(tempfile.mkdtemp(prefix="before-desktop-update-", dir=backups))
            previous = backup / destination.name
            receipt = backup / "rollout.json"
            result.update(state="prepared", backup_app=str(previous))
            _write_receipt(receipt, result)
            destination.rename(previous)
            try:
                staged.rename(destination)
                if _verified_identity(destination) != incoming:
                    raise ValueError("The installed app differs from the staged build")
                result["state"] = "updated"
                _write_receipt(receipt, result)
            except BaseException:
                if destination.exists():
                    destination.rename(staged)
                previous.rename(destination)
                result["state"] = "rolled_back"
                _write_receipt(receipt, result)
                raise
        return result
