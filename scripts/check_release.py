"""Build and verify release archives without importing the source package."""

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from email.parser import Parser
from pathlib import Path

PENDING_RELEASE = "Pending release"
RELEASE_HEADING = re.compile(
    rf"(?m)^## \[(\d+\.\d+\.\d+)\] [-–] ({PENDING_RELEASE}|\d{{4}}-\d{{2}}-\d{{2}})$"
)


def source_version(root: Path, tag: str | None = None) -> str:
    module = ast.parse((root / "src/lixity/_version.py").read_text(encoding="utf-8"))
    values = [
        node.value.value for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__version__"
                for target in node.targets)
        and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
    ]
    if len(values) != 1:
        raise ValueError("source must declare exactly one literal __version__")
    version = values[0]
    if tag is not None and tag != f"v{version}":
        raise ValueError(f"tag {tag!r} does not match source version {version}")
    return version


def verify_release_notes(root: Path, tag: str) -> None:
    """Require the release notes for the matching source version to be reviewed."""
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("release notes require a stable vX.Y.Z tag")
    notes = root / "docs" / "releases" / f"{tag}.md"
    if not notes.is_file():
        raise ValueError(f"missing release notes for {tag}")
    text = notes.read_text(encoding="utf-8")
    if not text.strip() or "(pending)" in text or "Pending release." in text:
        raise ValueError(f"release notes for {tag} still contain pending placeholders")


def verify_desktop_version(root: Path, version: str) -> None:
    """Check the version used by the Rust workspace and native installer builds."""
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10
        import tomli as tomllib

    desktop = root / "desktop"
    config = tomllib.loads((desktop / "Cargo.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((desktop / "Cargo.lock").read_text(encoding="utf-8"))
    tauri = json.loads((desktop / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    workspace = config.get("workspace")
    package = workspace.get("package") if isinstance(workspace, dict) else None
    locked_packages = lock.get("package")
    if not isinstance(locked_packages, list):
        raise ValueError("desktop/Cargo.lock does not declare a package list")
    versions = {
        "desktop/Cargo.toml": package.get("version") if isinstance(package, dict) else None,
        "desktop/Cargo.lock": next((item.get("version") for item in locked_packages
                                    if isinstance(item, dict) and item.get("name") == "lixity-desktop"), None),
        "desktop/src-tauri/tauri.conf.json": tauri.get("version") if isinstance(tauri, dict) else None,
    }
    for path, actual in versions.items():
        if actual != version:
            raise ValueError(f"{path} version {actual!r} does not match source version {version}")


def check_metadata(contents: bytes, version: str) -> None:
    metadata = Parser().parsestr(contents.decode("utf-8"))
    if metadata.get_all("Name") != ["lixity"] or metadata.get_all("Version") != [version]:
        raise ValueError(f"artifact metadata must declare Name: lixity and Version: {version}")


def _package_data_patterns(root: Path) -> tuple[str, ...]:
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            try:
                import tomllib
            except ModuleNotFoundError:  # Python 3.10
                import tomli as tomllib
            config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            patterns = config.get("tool", {}).get("setuptools", {}).get("package-data", {}).get("lixity")
            if isinstance(patterns, list) and all(isinstance(item, str) for item in patterns):
                return tuple(patterns)
        except ModuleNotFoundError:
            pass
    return ("py.typed", "locales/*.json", "ui/assets/*", "ui/assets/vendor/*")


def package_files(root: Path) -> dict[str, bytes]:
    source = root / "src/lixity"
    files = set(source.rglob("*.py")) | {source / "py.typed"}
    for pattern in _package_data_patterns(root):
        files.update(path for path in source.glob(pattern) if path.is_file())
    return {"lixity/" + path.relative_to(source).as_posix(): path.read_bytes() for path in files}


def check_package(actual: dict[str, bytes], expected: dict[str, bytes], label: str) -> None:
    missing = sorted(expected.keys() - actual.keys())
    extra = sorted(actual.keys() - expected.keys())
    changed = sorted(name for name in expected.keys() & actual.keys()
                     if expected[name] != actual[name])
    if missing or extra or changed:
        raise ValueError(f"{label} differs from source: missing={missing}, extra={extra}, "
                         f"changed={changed}")


def validate(root: Path, dist: Path, tag: str | None = None) -> str:
    """Validate the release artifacts against the source and optional tag."""
    version = source_version(root, tag)
    wheel = dist / f"lixity-{version}-py3-none-any.whl"
    sdist = dist / f"lixity-{version}.tar.gz"
    allowed = {wheel.name, sdist.name, "SHA256SUMS"}
    paths = list(dist.iterdir())
    if (not wheel.is_file() or not sdist.is_file()
            or any(path.name not in allowed or not path.is_file() or path.is_symlink()
                   for path in paths)):
        raise ValueError("artifacts must be exactly the current wheel and sdist, "
                         "with optional SHA256SUMS")
    expected = package_files(root)
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(names) != len(set(names)) or metadata != [f"lixity-{version}.dist-info/METADATA"]:
            raise ValueError("wheel has duplicate members or ambiguous metadata")
        check_metadata(archive.read(metadata[0]), version)
        check_package({name: archive.read(name) for name in names if name.startswith("lixity/")},
                      expected, "wheel")
    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        prefix = f"lixity-{version}/"
        if len(names) != len(set(names)) or any(
                not member.name.startswith(prefix)
                and not (member.name == prefix.rstrip("/") and member.isdir())
                for member in members):
            raise ValueError("sdist has duplicate members or unexpected root")
        metadata_file = archive.extractfile(prefix + "PKG-INFO")
        if metadata_file is None:
            raise ValueError("sdist is missing PKG-INFO")
        check_metadata(metadata_file.read(), version)
        actual = {}
        actual_tests = {}
        for member in members:
            if member.name.startswith(prefix + "src/lixity/") and not member.isdir():
                if not member.isfile():
                    raise ValueError("sdist package members must be regular files")
                contents = archive.extractfile(member)
                if contents is None:
                    raise ValueError(f"unreadable sdist member: {member.name}")
                actual[member.name.removeprefix(prefix + "src/")] = contents.read()
            elif member.name.startswith(prefix + "tests/") and member.name.endswith(".py"):
                if not member.isfile():
                    raise ValueError("sdist test modules must be regular files")
                contents = archive.extractfile(member)
                if contents is None:
                    raise ValueError(f"unreadable sdist member: {member.name}")
                actual_tests[member.name.removeprefix(prefix)] = contents.read()
        check_package(actual, expected, "sdist")
        expected_tests = {path.relative_to(root).as_posix(): path.read_bytes()
                          for path in (root / "tests").rglob("*.py")}
        check_package(actual_tests, expected_tests, "sdist tests")
    return version


def write_checksums(dist: Path) -> None:
    """Write artifact hashes after verification."""
    paths = sorted([*dist.glob("*.whl"), *dist.glob("*.tar.gz")])
    sums = "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
                   for path in paths)
    (dist / "SHA256SUMS").write_text(sums, encoding="utf-8")


def verify_checksums(dist: Path, version: str) -> None:
    """Read and verify declared hashes; never create or repair release evidence."""
    manifest = dist / "SHA256SUMS"
    if dist.is_symlink() or manifest.is_symlink() or not manifest.is_file():
        raise ValueError("SHA256SUMS must be a regular file in the artifact directory")
    expected = {f"lixity-{version}-py3-none-any.whl", f"lixity-{version}.tar.gz"}
    declared: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](.+)", line)
        if match is None:
            raise ValueError("malformed SHA256SUMS entry")
        digest, name = match.groups()
        if name not in expected or name in declared:
            raise ValueError("SHA256SUMS must declare each current artifact exactly once")
        declared[name] = digest.lower()
    if declared.keys() != expected:
        raise ValueError("SHA256SUMS must declare the current wheel and sdist")
    for name, digest in declared.items():
        path = dist / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"checksum artifact must be a regular file: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"checksum mismatch: {name}")


def promote_artifacts(root: Path, fresh: Path, dist: Path, tag: str | None) -> None:
    """Stage complete bytes locally, then replace with rollback on caught failures.

    The two directory renames are not one atomic operation. A process kill or
    power loss between them can leave the prior directory at the backup path.
    """
    dist.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{dist.name}-release-", dir=dist.parent))
    candidate = staging / "candidate"
    previous = staging / "previous"
    try:
        candidate.mkdir()
        for path in sorted(fresh.iterdir()):
            shutil.copy2(path, candidate / path.name)
        version = validate(root, candidate, tag)
        verify_checksums(candidate, version)
        try:
            if dist.exists():
                dist.rename(previous)
            candidate.rename(dist)
        except BaseException:
            if previous.exists():
                try:
                    previous.rename(dist)
                except OSError as exc:
                    raise OSError("artifact promotion and rollback failed; previous artifacts "
                                  f"retained at {previous}") from exc
            raise
        if previous.exists():
            try:
                shutil.rmtree(previous)
            except OSError as exc:
                raise OSError(f"artifacts promoted to {dist}, but previous artifacts could not "
                              f"be removed from {previous}") from exc
    finally:
        # Never clean away the only retained copy when rollback/cleanup failed.
        if not previous.exists():
            shutil.rmtree(staging)


def build(root: Path, dist: Path, tag: str | None = None, *, smoke_wheel: bool = False,
          install_report: Path | None = None) -> None:
    """Replace managed outputs only after candidate validation and requested smoke checks."""
    version = source_version(root, tag)
    if dist.is_symlink():
        raise ValueError("artifact output directory must not be a symlink")
    old = list(dist.iterdir()) if dist.exists() else []
    if any(not path.is_file() or path.is_symlink()
           or not (path.name == "SHA256SUMS"
                   or (path.name.startswith("lixity-")
                       and path.name.endswith((".whl", ".tar.gz"))))
           for path in old):
        raise ValueError("artifact output directory contains unmanaged files")
    if install_report is not None and (not smoke_wheel or install_report.resolve().is_relative_to(dist.resolve())):
        raise ValueError("install report requires a smoke check and an output path outside dist")
    with tempfile.TemporaryDirectory(prefix="lixity-build-") as directory:
        fresh = Path(directory) / "dist"
        staged_report = Path(directory) / "install-report.json" if install_report is not None else None
        subprocess.run(  # noqa: S603 - fixed interpreter/build module, no shell
            [sys.executable, "-m", "build", "--outdir", str(fresh)], cwd=root, check=True,
        )
        validate(root, fresh, tag)
        if smoke_wheel:
            smoke(fresh, version, install_report=staged_report)
        write_checksums(fresh)
        promote_artifacts(root, fresh, dist, tag)
        if install_report is not None and staged_report is not None:
            shutil.copyfile(staged_report, install_report)


def smoke(dist: Path, version: str, *, install_report: Path | None = None) -> None:
    """Verify a wheel installation outside the checkout in a disposable venv."""
    wheel = next(dist.glob("*.whl")).resolve()
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    with tempfile.TemporaryDirectory(prefix="lixity-release-smoke-") as directory:
        work = Path(directory)
        env["LIXITY_SERVICE_STATE_DIR"] = str(work / "service-state")
        env["LIXITY_SERVICE_RUNTIME_DIR"] = str(work / "service-runtime")
        subprocess.run(  # noqa: S603 - fixed interpreter and venv module
            [sys.executable, "-m", "venv", str(work / "venv")], check=True, env=env,
        )
        executable = work / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        cli = work / "venv" / ("Scripts/lixity.exe" if os.name == "nt" else "bin/lixity")

        def run(command: list[str], label: str) -> str:
            try:
                return subprocess.run(  # noqa: S603 - controlled venv interpreter, no shell
                    command, cwd=work, env=env, check=True,
                    capture_output=True, text=True,
                ).stdout
            except subprocess.CalledProcessError as exc:
                detail = (exc.stderr or exc.stdout or "no diagnostic output").strip()[-4000:]
                raise ValueError(f"installed wheel smoke failed ({label}, exit {exc.returncode}):"
                                 f"\n{detail}") from exc

        install = [str(executable), "-m", "pip", "install", str(wheel)]
        if install_report is not None:
            install.extend(("--report", str(install_report)))
        run(install, "install wheel")
        run([str(executable), "-m", "pip", "check"], "check dependencies")
        if run([str(cli), "--version"], "CLI version").strip() != f"lixity {version}":
            raise ValueError("installed CLI version differs from release version")
        about = json.loads(run([str(cli), "about", "--json"], "about metadata"))
        if about["meta"]["version"] != version:
            raise ValueError("installed about metadata differs from release version")
        status = json.loads(run([str(cli), "service", "status", "--port", "59973", "--json"],
                                "service status"))
        if status["schema_version"] != "lixity-service-status/1" or not status["ok"]:
            raise ValueError("installed service status did not return its inspection contract")
        diagnostics = json.loads(run([str(cli), "doctor", "--port", "59973", "--json"],
                                     "installation diagnostics"))
        if (diagnostics["schema_version"] != "lixity-doctor/1" or not diagnostics["ok"]
                or diagnostics["installation"]["distribution_version"] != version):
            raise ValueError("installed diagnostics disagree with the release installation")

        # Exercise package-data and license discovery from the installed wheel,
        # outside the source checkout, through all three publication formats.
        run([str(executable), "-c", """
from pathlib import Path
from lixity.config import prepare_project_settings
from lixity.research import api
from lixity.site_export import export_site
project = Path('synthetic-project')
project.mkdir()
(project / 'manuscript.md').write_text(chr(10).join([
    '## One', '', 'Synthetic opening.', '', '## Two', '', 'LATE_SMOKE_SENTINEL', '']), encoding='utf-8')
(project / 'lixity.toml').write_text('manuscript = "manuscript.md"' + chr(10), encoding='utf-8')
api.init(project, title='Synthetic reading project')
dossier = api.create_dossier(project, 'Public note', 'Approved synthetic background.')['dossier_id']
prepare_project_settings(project, {'site_publications': {'readers': {
    'title': 'Synthetic companion', 'entries': [{'dossier_id': dossier}]}}}).commit()
for mode in ('review', 'reader', 'companion'):
    options = {} if mode == 'review' else {'publication_profile': 'readers', 'max_chapter': 1}
    target = Path('website-' + mode)
    manifest = export_site(project, target, mode=mode, **options)
    assert manifest['mode'] == mode
    assert (target / 'licenses/Lixity-LICENSE').is_file()
    content = (target / 'index.html').read_text(encoding='utf-8')
    assert 'data-read-only="true"' in content
    if mode != 'review': assert 'LATE_SMOKE_SENTINEL' not in content
    if mode == 'companion': assert 'Synthetic opening.' not in content
"""], "reading website exports")
        run([str(cli), "pdf", str(work / "synthetic-project/manuscript.md"),
             "--layout", "document", "-o", str(work / "document.pdf")], "document PDF export")
        if not (work / "document.pdf").read_bytes().startswith(b"%PDF-"):
            raise ValueError("installed neutral document export did not produce a PDF")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--tag", help="Require the exact v<source-version> tag")
    parser.add_argument("--build", action="store_true", help="Build fresh verified archives")
    parser.add_argument("--smoke", action="store_true", help="Install and smoke-test the wheel")
    parser.add_argument("--install-report", type=Path,
                        help="Save pip's smoke-install report outside dist (requires --build --smoke)")
    parser.add_argument("--source-only", action="store_true",
                        help="Check source/tag identity without building or reading artifacts")
    parser.add_argument("--require-release-notes", action="store_true",
                        help="Check matching release notes for pending placeholders (requires --source-only)")
    parser.add_argument("--desktop-version", action="store_true",
                        help="Check native installer version pins (requires --source-only)")
    args = parser.parse_args()
    if args.source_only and (args.build or args.smoke):
        parser.error("--source-only cannot build or smoke-test artifacts")
    if (args.require_release_notes or args.desktop_version) and not args.source_only:
        parser.error("--require-release-notes and --desktop-version require --source-only")
    if args.install_report is not None and not (args.build and args.smoke):
        parser.error("--install-report requires --build --smoke")
    root = Path(__file__).resolve().parents[1]
    dist = args.dist.absolute()
    try:
        if args.source_only:
            version = source_version(root, args.tag)
            if args.require_release_notes:
                verify_release_notes(root, f"v{version}")
            if args.desktop_version:
                verify_desktop_version(root, version)
            print(f"release source verified: {version}")
            return
        if args.build:
            build(root, dist, args.tag, smoke_wheel=args.smoke, install_report=args.install_report)
        version = validate(root, dist, args.tag)
        verify_checksums(dist, version)
        if args.smoke and not args.build:
            smoke(dist, version)
    except (ValueError, OSError, tarfile.TarError, zipfile.BadZipFile,
            subprocess.CalledProcessError) as exc:
        parser.exit(1, f"release check failed: {exc}\n")
    print(f"release artifacts verified: {version}" + (" (installed wheel checked)" if args.smoke else ""))


if __name__ == "__main__":
    main()
