"""Promote verified immutable GitHub release bytes without rebuilding them.

Only a confirmed HTTP 404 represents absence. Authentication, transport, schema,
identity and digest failures stop publication; no response bodies or tokens are
included in diagnostics. All network operations here are read-only.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import check_release
from build_public_site import LANGUAGES, page_path
from make_videos import PUBLIC_VIDEO_FILES

# Direct script calls in Actions start with scripts/ on the import path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop.scripts.qualify_desktop_release import QUALIFICATION_FILE, load_qualified_artifacts
from desktop.scripts.verify_desktop_artifacts import (
    DESKTOP_CHECKSUMS,
    PUBLIC_INSTALLER_MANIFESTS,
    public_installer_inventory,
    sha256_file,
)
from desktop.scripts.windows_artifact_signing import AZURE_CREDENTIALS, AZURE_FIELDS
from scripts import desktop_downloads

JSON_LIMIT = 2 * 1024 * 1024
ASSET_LIMIT = 256 * 1024 * 1024
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")
RELEASE_TAG = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
RC_WORKFLOW = "rc.yml"
RC_ARTIFACT = "verified-release-candidate"
DEFAULT_PAGES_URL = "https://mfahsold.github.io/lixity/"
PAGES_VERIFY_FILES = (
    *(page_path(language) for language in LANGUAGES),
    *(f"guides/metrics/{language}.html" for language in LANGUAGES),
    "guides/first-look.html",
    "guides/first-look-de.html",
    "guides/installation.html",
    "robots.txt",
    "sitemap.xml",
    "sitemap-alt.xml",
    "desktop-downloads.json",
    "llms.txt",
    "assets/analytics.js",
    "assets/analytics.json",
    "assets/design-tokens.css",
    "assets/components.css",
    "assets/home.css",
    "assets/product-tour.js",
    "screenshots/dashboard-light.png",
    "screenshots/dashboard-measurement-focus.png",
    *(f"videos/{name}" for name in sorted(PUBLIC_VIDEO_FILES) if name != "README.md"),
    "sandbox/index.html",
    "demo/report.html",
    "demo/manifest.json",
    "demo/reader/manifest.json",
    "demo/companion/manifest.json",
)
_ASKPASS_ENV_VARS = (
    "GIT_ASKPASS",
    "SSH_ASKPASS",
    "VSCODE_GIT_ASKPASS_NODE",
    "VSCODE_GIT_ASKPASS_MAIN",
    "VSCODE_GIT_ASKPASS_EXTRA_ARGS",
    "VSCODE_GIT_IPC_HANDLE",
)
_ATTESTATION_FLAGS = (
    "--source-digest",
    "--signer-digest",
    "--cert-identity",
    "--deny-self-hosted-runners",
)
_BASE_HOSTS = frozenset({
    "api.github.com", "github.com", "pypi.org", "files.pythonhosted.org", "zenodo.org",
})
DESKTOP_METADATA = PUBLIC_INSTALLER_MANIFESTS | {DESKTOP_CHECKSUMS, QUALIFICATION_FILE}
_APPLE_SIGNING_SECRETS = {
    "APPLE_DEVELOPER_ID_P12_BASE64",
    "APPLE_DEVELOPER_ID_P12_PASSWORD",
    "APPLE_NOTARY_KEY_P8_BASE64",
    "APPLE_NOTARY_KEY_ID",
    "APPLE_NOTARY_ISSUER_ID",
}


def resolve_gh_binary():
    """Prefer explicit GH_BIN, then ~/.local/bin/gh, then PATH."""
    explicit = os.environ.get("GH_BIN", "").strip()
    if explicit:
        return explicit
    local_gh = Path.home() / ".local" / "bin" / "gh"
    if local_gh.is_file() and os.access(local_gh, os.X_OK):
        return str(local_gh)
    return shutil.which("gh") or "gh"


def github_subprocess_env(base_env=None, *, unset_env_tokens=False):
    """Strip broken editor askpass hooks; optionally fall back to the OS keyring."""
    env = dict(os.environ if base_env is None else base_env)
    for key in _ASKPASS_ENV_VARS:
        env.pop(key, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    if unset_env_tokens:
        env.pop("GH_TOKEN", None)
        env.pop("GITHUB_TOKEN", None)
    return env


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Allow public asset redirects, without forwarding API credentials."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if (req.has_header("Authorization") or target.scheme != "https"
                or target.username is not None or target.password is not None
                or target.hostname not in {"github.com", "release-assets.githubusercontent.com",
                                           "objects.githubusercontent.com",
                                           "files.pythonhosted.org"}):
            raise ValueError("unexpected HTTP redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HttpClient:
    """Bounded HTTPS access; only the GitHub API receives the GitHub token."""

    def __init__(self, token=None, opener=None, extra_hosts=()):
        self.token = token
        self.opener = opener or urllib.request.build_opener(SafeRedirect())
        self.allowed_hosts = _BASE_HOSTS | {
            urllib.parse.urlsplit(DEFAULT_PAGES_URL).hostname,
            *{host for host in extra_hosts if host},
        }

    def request(self, url, *, accept="application/json", headers=None):
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != "https" or parsed.username is not None or parsed.password is not None
                or parsed.hostname not in self.allowed_hosts):
            raise ValueError("unexpected channel URL")
        req_headers = {"User-Agent": "lixity-release-check", "Accept": accept}
        if headers:
            req_headers.update(headers)
        if parsed.hostname == "api.github.com":
            req_headers["Accept"] = "application/vnd.github+json"
            req_headers["X-GitHub-Api-Version"] = "2022-11-28"
            if self.token:
                req_headers["Authorization"] = f"Bearer {self.token}"
        return urllib.request.Request(url, headers=req_headers)  # noqa: S310 - HTTPS and hosts checked above

    def bytes(self, url, *, limit=ASSET_LIMIT, missing=False, accept="*/*", headers=None):
        try:
            with self.opener.open(self.request(url, accept=accept, headers=headers), timeout=30) as response:
                raw = response.read(limit + 1)
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            if missing and status == 404:
                return None
            raise ValueError(f"channel query failed: HTTP {status}") from None
        except (urllib.error.URLError, OSError, TimeoutError):
            raise ValueError("channel query failed: transport state is unknown") from None
        if len(raw) > limit:
            raise ValueError("channel response exceeds the allowed byte limit")
        return raw

    def json(self, url, *, missing=False, array=False, headers=None):
        raw = self.bytes(url, limit=JSON_LIMIT, missing=missing, accept="application/json",
                         headers=headers)
        if raw is None:
            return None
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ValueError("channel response is not valid JSON") from None
        if not isinstance(value, list if array else dict):
            raise ValueError("channel JSON has an unexpected structure")
        return value

    def download(self, url, destination, size):
        if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= ASSET_LIMIT:
            raise ValueError("release asset has an invalid or excessive size")
        try:
            with self.opener.open(self.request(url), timeout=30) as response, destination.open("xb") as output:
                received = 0
                while chunk := response.read(min(1024 * 1024, size + 1 - received)):
                    received += len(chunk)
                    if received > size:
                        raise ValueError("release asset exceeds its declared size")
                    output.write(chunk)
                if received != size:
                    raise ValueError("release asset differs from its declared size")
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            raise ValueError(f"release asset download failed: HTTP {status}") from None
        except (urllib.error.URLError, OSError, TimeoutError):
            raise ValueError("release asset download failed: transport state is unknown") from None


def _check_checkout_commit(root, expected_commit):
    if not SHA.fullmatch(expected_commit):
        raise ValueError("expected commit must be a full lowercase Git SHA")
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607 - git is a required runner tool
            cwd=root, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("could not determine the checked-out source commit") from None
    if result.returncode or result.stdout.strip() != expected_commit:
        raise ValueError("checked-out source commit differs from expected commit")


def identities(root, tag, expected_commit, repo, client):
    """Bind checked-out source, peeled remote tag and expected commit together."""
    if not REPOSITORY.fullmatch(repo):
        raise ValueError("repository must be owner/name")
    if not RELEASE_TAG.fullmatch(tag):
        raise ValueError("release tag must have the form vX.Y.Z")
    version = check_release.source_version(root, tag)
    _check_checkout_commit(root, expected_commit)
    base = f"https://api.github.com/repos/{repo}"
    ref = client.json(f"{base}/git/ref/tags/{tag}")
    for _ in range(10):
        obj = ref.get("object")
        if (not isinstance(obj, dict) or not isinstance(obj.get("sha"), str)
                or not SHA.fullmatch(obj["sha"])):
            raise ValueError("remote tag identity is malformed")
        if obj.get("type") == "commit":
            if obj["sha"] != expected_commit:
                raise ValueError("remote tag commit differs from expected commit")
            return version
        if obj.get("type") != "tag":
            raise ValueError("remote tag does not identify a commit")
        ref = client.json(f"{base}/git/tags/{obj['sha']}")
    raise ValueError("remote tag nesting exceeds the identity limit")


def release_metadata(repo, tag, client, *, include_drafts=False):
    base = f"https://api.github.com/repos/{repo}"
    value = client.json(f"{base}/releases/tags/{tag}", missing=True)
    if value is None and include_drafts:
        # The by-tag endpoint is documented for published releases. Drafts need
        # an authenticated listing; stop rather than guess beyond this bound.
        for page in range(1, 11):
            releases = client.json(f"{base}/releases?per_page=100&page={page}", array=True)
            if any(not isinstance(item, dict) or not isinstance(item.get("tag_name"), str)
                   or not item["tag_name"] for item in releases):
                raise ValueError("GitHub release listing is malformed")
            matches = [item for item in releases if item.get("tag_name") == tag]
            if len(matches) > 1:
                raise ValueError("GitHub release listing contains duplicate tags")
            if matches:
                value = matches[0]
                break
            if len(releases) < 100:
                break
        else:
            raise ValueError("GitHub draft lookup exceeds the release listing limit")
    if value is None:
        return None
    if value.get("tag_name") != tag:
        raise ValueError("GitHub release tag differs from the requested tag")
    if not isinstance(value.get("draft"), bool) or not isinstance(value.get("immutable"), bool):
        raise ValueError("GitHub release publication state is unknown")
    return value


def inspect(root, tag, expected_commit, repo, client):
    identities(root, tag, expected_commit, repo, client)
    release = release_metadata(repo, tag, client, include_drafts=True)
    state = "missing" if release is None else "draft" if release["draft"] else "published"
    return {"state": state, "tag": tag, "source_sha": expected_commit}


def verify_rc(root, tag, expected_commit, repo, client):
    """Find a successful main-branch qualification with a retained artifact."""
    if not REPOSITORY.fullmatch(repo):
        raise ValueError("repository must be owner/name")
    if not RELEASE_TAG.fullmatch(tag):
        raise ValueError("release tag must have the form vX.Y.Z")
    check_release.source_version(root, tag)
    _check_checkout_commit(root, expected_commit)
    base = f"https://api.github.com/repos/{repo}/actions"
    listing = client.json(f"{base}/workflows/{RC_WORKFLOW}/runs?branch=main&event=workflow_dispatch"
                          f"&status=success&head_sha={expected_commit}&per_page=30")
    runs = listing.get("workflow_runs")
    if not isinstance(runs, list):
        raise ValueError("GitHub release-candidate runs are unknown")
    for run in runs:
        head_repo = run.get("head_repository") if isinstance(run, dict) else None
        if (not isinstance(head_repo, dict) or head_repo.get("full_name") != repo
                or run.get("path") != f".github/workflows/{RC_WORKFLOW}"
                or run.get("head_branch") != "main" or run.get("head_sha") != expected_commit
                or run.get("event") != "workflow_dispatch" or run.get("status") != "completed"
                or run.get("conclusion") != "success"):
            raise ValueError("GitHub returned a release-candidate run with unexpected identity or state")
        run_id = run.get("id")
        if type(run_id) is not int or run_id <= 0:
            raise ValueError("GitHub release-candidate run ID is invalid")
        listing = client.json(f"{base}/runs/{run_id}/artifacts?name={RC_ARTIFACT}")
        artifacts = listing.get("artifacts")
        if (not isinstance(artifacts, list) or listing.get("total_count") != len(artifacts)
                or any(not isinstance(item, dict) or item.get("name") != RC_ARTIFACT
                       or not isinstance(item.get("expired"), bool) for item in artifacts)):
            raise ValueError("GitHub release-candidate artifact listing is incomplete or malformed")
        retained = [item for item in artifacts if not item["expired"]]
        if not retained:
            continue
        if len(retained) != 1:
            raise ValueError("GitHub run must retain exactly one release-candidate artifact")
        artifact = retained[0]
        artifact_id, digest = artifact.get("id"), artifact.get("digest")
        origin = artifact.get("workflow_run")
        if (type(artifact_id) is not int or artifact_id <= 0 or not isinstance(digest, str)
                or not digest.startswith("sha256:") or not DIGEST.fullmatch(digest[7:])
                or not isinstance(origin, dict) or origin.get("id") != run_id
                or origin.get("head_branch") != "main" or origin.get("head_sha") != expected_commit):
            raise ValueError("GitHub release-candidate artifact has an invalid identity or SHA-256 digest")
        return {"tag": tag, "source_sha": expected_commit, "run_id": run_id,
                "artifact_id": artifact_id, "artifact_digest": digest}
    raise ValueError(f"no successful rc.yml run retains a candidate for {expected_commit}; "
                     f"run make rc-gate RELEASE_TAG={tag} and wait for qualification")


def published(release):
    if release is None or release["draft"] or not release.get("published_at"):
        raise ValueError("GitHub release must already be published")
    if not release["immutable"]:
        raise ValueError("GitHub release must be immutable")


def assets(release, repo, tag, *, draft=False, require_desktop=False):
    python_names = _pypi_filenames(tag) | {"SHA256SUMS"}
    actual = release.get("assets")
    if not isinstance(actual, list):
        raise ValueError("GitHub release asset list is unknown")
    desktop = any(isinstance(asset, dict) and asset.get("name") == QUALIFICATION_FILE for asset in actual)
    if require_desktop and not desktop:
        raise ValueError("This release requires the qualified desktop installer set")
    if desktop and release.get("prerelease") is not False:
        raise ValueError("The qualified desktop installer set requires a stable release")
    if not desktop and len(actual) != len(python_names):
        raise ValueError("GitHub release must contain exactly the wheel, sdist and SHA256SUMS")
    required = python_names | (DESKTOP_METADATA | public_installer_inventory(tag).keys() if desktop else set())
    result = {}
    for asset in actual:
        name = asset.get("name") if isinstance(asset, dict) else None
        if not isinstance(name, str) or name not in required:
            raise ValueError("GitHub release has an unexpected asset")
        digest = asset.get("digest")
        if name in result or asset.get("state") != "uploaded":
            raise ValueError("GitHub release has duplicate or incomplete assets")
        if not isinstance(digest, str) or not digest.startswith("sha256:") or not DIGEST.fullmatch(digest[7:]):
            raise ValueError("GitHub release asset SHA256 digest is unknown")
        size = asset.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= ASSET_LIMIT:
            raise ValueError("GitHub release asset has an invalid or excessive size")
        url = asset.get("browser_download_url")
        expected_url = f"https://github.com/{repo}/releases/download/{tag}/{name}"
        draft_pattern = re.compile(
            rf"https://github\.com/{re.escape(repo)}/releases/download/untagged-[0-9a-f]+/{re.escape(name)}",
        )
        if url != expected_url and not (draft and isinstance(url, str) and draft_pattern.fullmatch(url)):
            raise ValueError("GitHub release asset URL differs from the selected release")
        result[name] = asset
    if not required <= result.keys():
        raise ValueError("GitHub release asset set is incomplete: " + ", ".join(sorted(required - result.keys())))
    return result


def verify_attestations(paths, repo, tag, expected_commit, *, workflow="release.yml"):
    """Require GitHub's signed workflow identity, source ref/SHA and hosted runner."""
    gh_bin = resolve_gh_binary()
    sub_env = github_subprocess_env()
    source_ref = f"refs/tags/{tag}" if workflow == "release.yml" else "refs/heads/main"
    for path in paths:
        command = [
            gh_bin, "attestation", "verify", str(path), "--repo", repo,
            "--source-digest", expected_commit, "--source-ref", source_ref,
            "--signer-digest", expected_commit,
            "--cert-identity", f"https://github.com/{repo}/.github/workflows/{workflow}@{source_ref}",
            "--deny-self-hosted-runners",
        ]
        try:
            result = subprocess.run(  # noqa: S603 - fixed gh command, argv only
                command, check=False, env=sub_env, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError(f"attestation verification unavailable for {path.name}") from None
        if result.returncode:
            raise ValueError(f"attestation verification failed for {path.name}; a current gh CLI is required")


def verify_rc_artifacts(root, tag, expected_commit, repo, dist):
    """Compare the candidate with the tagged source and verify its build provenance."""
    if not REPOSITORY.fullmatch(repo):
        raise ValueError("repository must be owner/name")
    _check_checkout_commit(root, expected_commit)
    version = check_release.validate(root, dist, tag)
    check_release.verify_checksums(dist, version)
    verify_attestations(sorted(dist.iterdir()), repo, tag, expected_commit, workflow=RC_WORKFLOW)
    return {"tag": tag, "source_sha": expected_commit, "state": "qualified"}


def _qualified_desktop_names(directory, qualification, tag, expected_commit):
    installers = load_qualified_artifacts(directory, qualification, tag=tag, source_sha=expected_commit)
    return DESKTOP_METADATA | {asset.filename for asset in installers}


def stage_desktop(root, tag, expected_commit, repo, artifacts_dir, qualification, destination):
    """Stage only reviewed, attested files for the common GitHub Release draft."""
    if not REPOSITORY.fullmatch(repo):
        raise ValueError("repository must be owner/name")
    check_release.source_version(root, tag)
    _check_checkout_commit(root, expected_commit)
    names = _qualified_desktop_names(artifacts_dir, qualification, tag, expected_commit)
    empty_destination(destination)
    with tempfile.TemporaryDirectory(prefix=".lixity-desktop-", dir=destination.parent) as scratch:
        fresh = Path(scratch) / "desktop"
        fresh.mkdir()
        for name in sorted(names):
            source = qualification if name == QUALIFICATION_FILE else artifacts_dir / name
            shutil.copyfile(source, fresh / name)
        _qualified_desktop_names(fresh, fresh / QUALIFICATION_FILE, tag, expected_commit)
        verify_attestations([fresh / name for name in sorted(names - {QUALIFICATION_FILE})],
                            repo, tag, expected_commit, workflow="desktop-release.yml")
        if destination.exists():
            destination.rmdir()
        os.replace(fresh, destination)
    return {"state": "qualified", "installer_count": len(names - DESKTOP_METADATA),
            "source_sha": expected_commit, "tag": tag}


def _verify_asset_file(path, asset):
    if (path.is_symlink() or not path.is_file() or path.stat().st_size != asset["size"]
            or "sha256:" + sha256_file(path) != asset["digest"]):
        raise ValueError(f"GitHub release digest differs for {path.name}")


def _verify_desktop_files(directory, expected, tag, repo, expected_commit):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Desktop installer directory must be a regular directory")
    for name, asset in expected.items():
        _verify_asset_file(directory / name, asset)
    installers = load_qualified_artifacts(directory, directory / QUALIFICATION_FILE, tag=tag,
                                         source_sha=expected_commit)
    names = DESKTOP_METADATA | {asset.filename for asset in installers}
    if names != expected.keys():
        raise ValueError("Desktop release listings and qualified files differ")
    verify_attestations([directory / name for name in sorted(names - {QUALIFICATION_FILE})],
                        repo, tag, expected_commit, workflow="desktop-release.yml")
    return installers


def _download_desktop_files(directory, expected, tag, repo, expected_commit, client):
    for name, asset in sorted(expected.items()):
        client.download(asset["browser_download_url"], directory / name, asset["size"])
    return _verify_desktop_files(directory, expected, tag, repo, expected_commit)


def record_desktop_catalog(root, tag, expected_commit, repo, output, client):
    """Record the installer links from a verified immutable desktop release."""
    identities(root, tag, expected_commit, repo, client)
    release = release_metadata(repo, tag, client)
    published(release)
    expected = assets(release, repo, tag, require_desktop=True)
    desktop = {name: expected[name] for name in DESKTOP_METADATA | public_installer_inventory(tag).keys()}
    with tempfile.TemporaryDirectory(prefix="lixity-desktop-readback-") as scratch:
        directory = Path(scratch)
        installers = _download_desktop_files(directory, desktop, tag, repo, expected_commit, client)
        catalog = desktop_downloads.record_catalog(release, installers, (directory / DESKTOP_CHECKSUMS).read_bytes(),
                                                   (directory / QUALIFICATION_FILE).read_bytes())
        desktop_downloads.write_catalog(catalog, output)
    return {"state": "catalog-recorded", "tag": tag, "source_sha": expected_commit,
            "installer_count": len(installers)}


def verify_files(root, dist, tag, repo, expected_commit, release, *, draft=False,
                 require_desktop=False, desktop_dist=None, client=None, python_only=False):
    expected = assets(release, repo, tag, draft=draft, require_desktop=require_desktop)
    python_names = _pypi_filenames(tag) | {"SHA256SUMS"}
    check_release.verify_checksums(dist, tag[1:])
    for name in python_names:
        _verify_asset_file(dist / name, expected[name])
    verify_attestations([dist / name for name in sorted(python_names)], repo, tag, expected_commit)
    check_release.validate(root, dist, tag)
    desktop_assets = {name: expected[name] for name in expected.keys() - python_names}
    if desktop_assets and not python_only:
        if desktop_dist is not None:
            _verify_desktop_files(desktop_dist, desktop_assets, tag, repo, expected_commit)
        elif draft or client is None:
            raise ValueError("Desktop draft verification requires the staged installer directory")
        else:
            with tempfile.TemporaryDirectory(prefix="lixity-desktop-readback-") as scratch:
                _download_desktop_files(Path(scratch), desktop_assets, tag, repo, expected_commit, client)
    return {name: asset["digest"].removeprefix("sha256:") for name, asset in expected.items()}


def verify_github(root, tag, expected_commit, repo, dist, client, *,
                  draft=False, include_digests=False, require_desktop=False,
                  desktop_dist=None, python_only=False):
    identities(root, tag, expected_commit, repo, client)
    release = release_metadata(repo, tag, client, include_drafts=draft)
    if draft:
        if release is None or not release["draft"] or release["immutable"]:
            raise ValueError("GitHub release must be an unpublished draft")
    else:
        published(release)
    digests = verify_files(root, dist, tag, repo, expected_commit, release, draft=draft,
                           require_desktop=require_desktop, desktop_dist=desktop_dist,
                           client=client, python_only=python_only)
    return {"state": "draft" if draft else "published", "source_sha": expected_commit, "tag": tag,
            **({"digests": digests} if include_digests else {})}


def empty_destination(path):
    if path.is_symlink() or (path.exists() and (not path.is_dir() or any(path.iterdir()))):
        raise ValueError("output directory must be absent or empty; existing files are preserved")
    path.parent.mkdir(parents=True, exist_ok=True)


def recover(root, tag, expected_commit, repo, dist, client, *, include_digests=False,
            require_desktop=False, python_only=False):
    identities(root, tag, expected_commit, repo, client)
    release = release_metadata(repo, tag, client)
    published(release)
    expected = assets(release, repo, tag, require_desktop=require_desktop)
    python_names = _pypi_filenames(tag) | {"SHA256SUMS"}
    empty_destination(dist)
    with tempfile.TemporaryDirectory(prefix=".lixity-release-", dir=dist.parent) as scratch:
        fresh = Path(scratch) / "dist"
        fresh.mkdir()
        for name in sorted(python_names):
            asset = expected[name]
            client.download(asset["browser_download_url"], fresh / name, asset["size"])
        digests = verify_files(root, fresh, tag, repo, expected_commit, release, client=client,
                               require_desktop=require_desktop, python_only=python_only)
        if dist.exists():
            dist.rmdir()
        os.replace(fresh, dist)
    return {"state": "published", "source_sha": expected_commit, "tag": tag,
            **({"digests": digests} if include_digests else {})}


def _pypi_filenames(tag):
    return {f"lixity-{tag[1:]}-py3-none-any.whl", f"lixity-{tag[1:]}.tar.gz"}


def _pypi_release_files(dist, tag, client):
    names = _pypi_filenames(tag)
    value = client.json(f"https://pypi.org/pypi/lixity/{tag[1:]}/json", missing=True)
    if value is None:
        return {}
    if not isinstance(value.get("info"), dict) or value["info"].get("version") != tag[1:]:
        raise ValueError("PyPI release version is unknown or differs from the requested version")
    files = value.get("urls")
    if not isinstance(files, list):
        raise ValueError("PyPI file state is unknown")
    found = {}
    for file in files:
        name = file.get("filename") if isinstance(file, dict) else None
        if not isinstance(name, str) or name not in names:
            raise ValueError("PyPI has an unexpected distribution filename")
        if name in found or file.get("yanked") is not False:
            raise ValueError("PyPI has a duplicate or yanked distribution")
        digests = file.get("digests")
        actual = digests.get("sha256") if isinstance(digests, dict) else None
        expected = hashlib.sha256((dist / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"PyPI SHA256 digest differs or is unknown for {name}")
        found[name] = file
    return found


def stage_pypi(root, tag, expected_commit, repo, dist, upload, client):
    github = verify_github(root, tag, expected_commit, repo, dist, client, include_digests=True, python_only=True)
    published_files = _pypi_release_files(dist, tag, client)
    missing = sorted(_pypi_filenames(tag) - published_files.keys())
    empty_destination(upload)
    with tempfile.TemporaryDirectory(prefix=".lixity-pypi-", dir=upload.parent) as scratch:
        fresh = Path(scratch) / "upload"
        fresh.mkdir()
        for name in missing:
            target = fresh / name
            shutil.copyfile(dist / name, target)
            if sha256_file(target) != github["digests"][name]:
                raise ValueError(f"Staged PyPI distribution differs from the verified GitHub asset for {name}")
        if upload.exists():
            upload.rmdir()
        os.replace(fresh, upload)
    return {"upload_count": len(missing), "state": "pending" if missing else "complete"}


def _wait_for_pypi(dist, tag, client):
    # Newly uploaded files can take up to ~60s to appear on PyPI CDN. Retry only
    # missing visibility, never digest/auth/transport failures and never the upload.
    expected = _pypi_filenames(tag)
    for attempt in range(12):
        files = _pypi_release_files(dist, tag, client)
        missing = sorted(expected - files.keys())
        if not missing:
            return files
        if attempt < 11:
            time.sleep(5)
    raise ValueError("PyPI publication is incomplete: " + ", ".join(missing))


def verify_pypi(root, tag, expected_commit, repo, dist, client):
    result = verify_github(root, tag, expected_commit, repo, dist, client, python_only=True)
    _wait_for_pypi(dist, tag, client)
    return {**result, "state": "complete"}


def _parse_worktrees(porcelain):
    entries = []
    current = {}
    for line in porcelain.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            current["path"] = line.split(" ", 1)[1]
        elif line.startswith("HEAD "):
            current["head"] = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            current["branch"] = line.split(" ", 1)[1].removeprefix("refs/heads/")
        elif line == "prunable" or line.startswith("prunable "):
            current["prunable"] = True
    if current:
        entries.append(current)
    for item in entries:
        item.setdefault("prunable", False)
    return entries


def _desktop_signing_status(run_cmd, gh_bin, repo):
    def list_names(command):
        result = run_cmd([gh_bin, *command, "--repo", repo, "--json", "name"])
        if result is None or result.returncode != 0:
            return None
        try:
            rows = json.loads(result.stdout)
        except (TypeError, ValueError):
            return None
        if not isinstance(rows, list) or any(
            not isinstance(row, dict) or not isinstance(row.get("name"), str) for row in rows
        ):
            return None
        return {row["name"] for row in rows}

    secrets = list_names(["secret", "list", "--app", "actions"])
    variables = list_names(["variable", "list"])
    return {
        "macos": {
            "missing_secrets": sorted(_APPLE_SIGNING_SECRETS - secrets) if secrets is not None else None,
        },
        "windows": {
            "missing_secrets": sorted(set(AZURE_CREDENTIALS) - secrets) if secrets is not None else None,
            "missing_variables": sorted(AZURE_FIELDS.keys() - variables) if variables is not None else None,
        },
    }


def doctor(root, repo, client, *, tag=None, unset_env_tokens=False, desktop_signing=False):
    """Inspect local Git/worktree state, gh CLI readiness and optional release channels."""
    if not REPOSITORY.fullmatch(repo):
        raise ValueError("repository must be owner/name")
    gh_bin = resolve_gh_binary()
    sub_env = github_subprocess_env(unset_env_tokens=unset_env_tokens)

    def run_cmd(argv, cwd=None):
        try:
            return subprocess.run(  # noqa: S603 - fixed local git/gh command
                argv, cwd=cwd, env=sub_env, text=True, capture_output=True, timeout=30, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

    gh_ver = run_cmd([gh_bin, "--version"])
    if gh_ver is None or gh_ver.returncode != 0:
        raise ValueError("gh CLI is unavailable")
    gh_version = (gh_ver.stdout or "").splitlines()[0].strip() if gh_ver.stdout else "unknown"

    attest_help = run_cmd([gh_bin, "attestation", "verify", "--help"])
    help_text = ((attest_help.stdout or "") + (attest_help.stderr or "")) if attest_help else ""
    if attest_help is None or attest_help.returncode != 0 or any(flag not in help_text for flag in _ATTESTATION_FLAGS):
        raise ValueError("installed gh CLI lacks required attestation verification flags")

    auth_res = run_cmd([gh_bin, "auth", "status"])
    auth_text = ((auth_res.stdout or "") + (auth_res.stderr or "")) if auth_res else ""
    auth_ok = bool(auth_res is not None and auth_res.returncode == 0)
    workflow_scope = bool(re.search(r"Token scopes:.*\bworkflow\b", auth_text))

    head_res = run_cmd(["git", "rev-parse", "HEAD"], cwd=root)
    branch_res = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
    status_res = run_cmd(["git", "status", "--porcelain"], cwd=root)
    wt_res = run_cmd(["git", "worktree", "list", "--porcelain"], cwd=root)
    if (head_res is None or head_res.returncode != 0 or branch_res is None or branch_res.returncode != 0
            or status_res is None or status_res.returncode != 0):
        raise ValueError("could not inspect local Git repository state")
    worktrees = _parse_worktrees(wt_res.stdout) if wt_res and wt_res.returncode == 0 else []

    report = {
        "ok": True,
        "gh_binary": gh_bin,
        "gh_version": gh_version,
        "attestation_flags_supported": True,
        "auth_ok": auth_ok,
        "workflow_scope": workflow_scope,
        "git": {
            "head": head_res.stdout.strip(),
            "branch": branch_res.stdout.strip(),
            "clean": not bool(status_res.stdout.strip()),
            "worktrees": worktrees,
            "prunable_worktrees": sum(1 for item in worktrees if item.get("prunable")),
        },
    }
    if desktop_signing:
        report["desktop_signing"] = _desktop_signing_status(run_cmd, gh_bin, repo)
    if tag is not None:
        version = check_release.source_version(root, tag)
        check_release.verify_release_notes(root, tag)
        release = release_metadata(repo, tag, client, include_drafts=True)
        github_state = "missing" if release is None else "draft" if release["draft"] else "published"
        pypi_value = client.json(f"https://pypi.org/pypi/lixity/{version}/json", missing=True)
        pypi_present = []
        if pypi_value is not None:
            if not isinstance(pypi_value.get("urls"), list):
                raise ValueError("PyPI file state is unknown")
            pypi_present = sorted(
                item["filename"] for item in pypi_value["urls"]
                if isinstance(item, dict) and isinstance(item.get("filename"), str)
            )
        expected_dists = {f"lixity-{version}-py3-none-any.whl", f"lixity-{version}.tar.gz"}
        report.update(
            tag=tag,
            version=version,
            release_notes_ready=True,
            github_state=github_state,
            pypi_present=pypi_present,
            pypi_missing=sorted(expected_dists - set(pypi_present)),
        )
    return report


def _stage_pages_module():
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import stage_pages
    return stage_pages


def _normalize_pages_base(base_url):
    parsed = urllib.parse.urlsplit(base_url)
    if (parsed.scheme != "https" or not parsed.hostname
            or parsed.username is not None or parsed.password is not None):
        raise ValueError("Pages base URL must be a plain HTTPS URL")
    normalized = base_url if base_url.endswith("/") else base_url + "/"
    return normalized, parsed.hostname


def verify_pages(root, tag, expected_commit, client, *, base_url=DEFAULT_PAGES_URL):
    """Verify live Pages deployment metadata and staged public resources."""
    _check_checkout_commit(root, expected_commit)
    if tag is not None:
        check_release.source_version(root, tag)
    normalized_base, host = _normalize_pages_base(base_url)
    if host not in client.allowed_hosts:
        raise ValueError("Pages host is not allowed by the verification client")

    headers = {"Cache-Control": "no-cache", "Accept-Encoding": "identity"}
    deployment_url = urllib.parse.urljoin(normalized_base, "deployment.json")
    deployment = client.json(deployment_url, headers=headers)
    if deployment.get("schema_version") != 1 or deployment.get("source_sha") != expected_commit:
        raise ValueError("Pages deployment.json source_sha differs from expected commit")

    stage_pages = _stage_pages_module()
    with tempfile.TemporaryDirectory(prefix="lixity-pages-verify-") as temp_dir:
        staged = Path(temp_dir) / "public"
        stage_pages.stage(root / "docs", staged)
        root_bytes = client.bytes(normalized_base, headers=headers)
        if root_bytes != (staged / "index.html").read_bytes():
            raise ValueError("public Pages canonical root differs from staged index.html")
        for rel_path in PAGES_VERIFY_FILES:
            expected_bytes = (staged / rel_path).read_bytes()
            actual_bytes = client.bytes(urllib.parse.urljoin(normalized_base, rel_path), headers=headers)
            if actual_bytes != expected_bytes:
                raise ValueError(f"public Pages resource differs from staged build: {rel_path}")
    if client.json(deployment_url, headers=headers) != deployment:
        raise ValueError("Pages deployment changed during verification")
    return {
        "state": "verified",
        **({"tag": tag} if tag is not None else {}),
        "source_sha": expected_commit,
        "base_url": normalized_base,
        "verified_paths": len(PAGES_VERIFY_FILES) + 2,
    }


def zenodo_status(repo, tag, client):
    """Query Zenodo asynchronously without blocking release publication on archival lag."""
    if not REPOSITORY.fullmatch(repo):
        raise ValueError("repository must be owner/name")
    if not RELEASE_TAG.fullmatch(tag):
        raise ValueError("release tag must have the form vX.Y.Z")
    repository = f"https://github.com/{repo}"
    identifiers = (repository, f"{repository}/tree/{tag}", f"{repository}/releases/tag/{tag}")
    related = " OR ".join(f'"{identifier}"' for identifier in identifiers)
    query = urllib.parse.urlencode({
        "q": f'metadata.related_identifiers.identifier:({related}) AND metadata.version:("{tag}" OR "{tag[1:]}")',
        "size": 10,
        "all_versions": 1,
    })
    unknown = {"zenodo_status": "unknown", "zenodo_doi": None, "zenodo_url": None}
    try:
        payload = client.json(f"https://zenodo.org/api/records?{query}")
    except ValueError:
        return unknown
    hits = payload.get("hits", {}).get("hits") if isinstance(payload.get("hits"), dict) else None
    if not isinstance(hits, list):
        return unknown
    matches = []
    for hit in hits:
        metadata = hit.get("metadata") if isinstance(hit, dict) else None
        relations = metadata.get("related_identifiers") if isinstance(metadata, dict) else None
        if not isinstance(relations, list):
            return unknown
        if metadata.get("version") in (tag, tag[1:]) and any(
            isinstance(item, dict) and isinstance(item.get("identifier"), str)
            and item["identifier"].rstrip("/") in identifiers for item in relations
        ):
            matches.append(hit)
    if not matches:
        return {**unknown, "zenodo_status": "pending"}
    if len(matches) != 1:
        return unknown
    record = matches[0]
    doi = record.get("doi") if isinstance(record.get("doi"), str) else None
    links = record.get("links") if isinstance(record.get("links"), dict) else {}
    self_html = links.get("self_html") if isinstance(links.get("self_html"), str) else None
    return {"zenodo_status": "minted" if doi else "pending", "zenodo_doi": doi, "zenodo_url": self_html}


def verify_release(
    root, tag, expected_commit, repo, dist, client, *,
    base_url=DEFAULT_PAGES_URL, check_zenodo=False, skip_pypi=False, skip_pages=False,
    require_desktop=False,
):
    """Verify a GitHub release and its selected publication channels."""
    if not dist.exists() or not any(dist.iterdir()):
        github = recover(root, tag, expected_commit, repo, dist, client, include_digests=True,
                         require_desktop=require_desktop)
    else:
        github = verify_github(root, tag, expected_commit, repo, dist, client, include_digests=True,
                               require_desktop=require_desktop)
    result = {
        "state": "verified",
        "tag": tag,
        "source_sha": expected_commit,
        "channels": ["github"],
    }
    if not skip_pypi:
        for name, entry in _wait_for_pypi(dist, tag, client).items():
            url = entry.get("url")
            if not isinstance(url, str):
                raise ValueError(f"PyPI distribution URL missing for {name}")
            data = client.bytes(url)
            if hashlib.sha256(data).hexdigest() != github["digests"][name] or data != (dist / name).read_bytes():
                raise ValueError(f"downloaded PyPI distribution differs from GitHub asset for {name}")
        result["channels"].append("pypi")
        result["github_pypi_bytes_identical"] = True
    if not skip_pages:
        pages = verify_pages(root, tag, expected_commit, client, base_url=base_url)
        result["channels"].append("pages")
        result["pages_verified_paths"] = pages["verified_paths"]
    if check_zenodo:
        result.update(zenodo_status(repo, tag, client))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("inspect", "recover", "verify-github", "verify-draft", "stage-pypi",
                 "verify-pypi", "doctor", "verify-pages", "verify-zenodo", "verify-release",
                 "stage-desktop", "record-desktop-catalog", "verify-rc", "verify-rc-artifacts"),
    )
    parser.add_argument("--root", type=Path, help="Source checkout for local verification")
    parser.add_argument("--tag")
    parser.add_argument("--expected-commit")
    parser.add_argument("--repo", help="GitHub repository as owner/name")
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--desktop-dist", type=Path, help="Separate directory for the reviewed desktop asset set")
    parser.add_argument("--require-desktop", action="store_true", help="Reject a Python-only release")
    parser.add_argument("--desktop-signing", action="store_true",
                        help="Report missing repository-level desktop signing names with doctor")
    parser.add_argument("--python-only", action="store_true", help="Recover only the artifacts required by PyPI")
    parser.add_argument("--artifacts-dir", type=Path, help="Unpacked desktop release workflow bundle")
    parser.add_argument("--qualification", type=Path, help="Reviewed desktop qualification receipt")
    parser.add_argument("--catalog-output", type=Path, help="Write the reviewed desktop download catalog here")
    parser.add_argument("--upload", type=Path, default=Path("upload"))
    parser.add_argument("--base-url", default=DEFAULT_PAGES_URL)
    parser.add_argument("--use-keyring", action="store_true",
                        help="Unset GH_TOKEN/GITHUB_TOKEN for gh subprocesses so OS keyring is used")
    parser.add_argument("--check-zenodo", action="store_true",
                        help="Include the asynchronous Zenodo status in verify-release")
    parser.add_argument("--skip-pypi", action="store_true",
                        help="Omit PyPI from verify-release when it was intentionally skipped")
    parser.add_argument("--skip-pages", action="store_true",
                        help="Omit live Pages from verify-release for a historical tag")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    if args.command != "verify-zenodo" and args.root is None:
        parser.error(f"--root is required for {args.command}")
    if args.command != "verify-pages" and not args.repo:
        parser.error(f"--repo is required for {args.command}")
    if args.command not in {"doctor", "verify-pages"} and not args.tag:
        parser.error(f"--tag is required for {args.command}")
    if args.command not in {"doctor", "verify-zenodo"} and not args.expected_commit:
        parser.error(f"--expected-commit is required for {args.command}")
    if args.command != "verify-release" and (args.skip_pypi or args.skip_pages):
        parser.error("--skip-pypi and --skip-pages apply only to verify-release")
    if args.command == "stage-desktop" and not (args.artifacts_dir and args.qualification and args.desktop_dist):
        parser.error("stage-desktop requires --artifacts-dir, --qualification and --desktop-dist")
    if (args.command == "record-desktop-catalog") != bool(args.catalog_output):
        parser.error("--catalog-output is required for record-desktop-catalog and applies only to that command")
    if args.desktop_dist and args.command not in {"stage-desktop", "verify-draft", "verify-github"}:
        parser.error("--desktop-dist applies to staging or checking GitHub desktop assets")
    if args.require_desktop and args.command not in {"recover", "verify-draft", "verify-github", "verify-release"}:
        parser.error("--require-desktop applies to GitHub release verification")
    if args.desktop_signing and args.command != "doctor":
        parser.error("--desktop-signing applies only to doctor")
    if args.python_only and (args.command != "recover" or args.require_desktop):
        parser.error("--python-only is only for Python artifact recovery")
    if args.use_keyring:
        os.environ.pop("GH_TOKEN", None)
        os.environ.pop("GITHUB_TOKEN", None)
    token = None if args.use_keyring else (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    try:
        pages_hosts = ()
        if args.command == "verify-pages" or (args.command == "verify-release" and not args.skip_pages):
            pages_hosts = (_normalize_pages_base(args.base_url)[1],)
        client = HttpClient(token=token, extra_hosts=pages_hosts)
        if args.command == "doctor":
            result = doctor(
                args.root, args.repo, client, tag=args.tag, unset_env_tokens=args.use_keyring,
                desktop_signing=args.desktop_signing,
            )
        elif args.command == "verify-pages":
            result = verify_pages(args.root, args.tag, args.expected_commit, client, base_url=args.base_url)
        elif args.command == "verify-zenodo":
            result = {"tag": args.tag, **zenodo_status(args.repo, args.tag, client)}
        elif args.command == "verify-release":
            result = verify_release(
                args.root, args.tag, args.expected_commit, args.repo, args.dist, client,
                base_url=args.base_url, check_zenodo=args.check_zenodo,
                skip_pypi=args.skip_pypi, skip_pages=args.skip_pages,
                require_desktop=args.require_desktop,
            )
        else:
            common = (args.root, args.tag, args.expected_commit, args.repo)
            if args.command == "inspect":
                result = inspect(*common, client)
            elif args.command == "verify-rc":
                result = verify_rc(*common, client)
            elif args.command == "verify-rc-artifacts":
                result = verify_rc_artifacts(*common, args.dist)
            elif args.command == "recover":
                result = recover(*common, args.dist, client, require_desktop=args.require_desktop,
                                 python_only=args.python_only)
            elif args.command == "stage-desktop":
                result = stage_desktop(*common, args.artifacts_dir, args.qualification, args.desktop_dist)
            elif args.command == "record-desktop-catalog":
                result = record_desktop_catalog(*common, args.catalog_output, client)
            elif args.command == "stage-pypi":
                result = stage_pypi(*common, args.dist, args.upload, client)
            elif args.command == "verify-pypi":
                result = verify_pypi(*common, args.dist, client)
            else:
                result = verify_github(
                    *common, args.dist, client, draft=args.command == "verify-draft",
                    desktop_dist=args.desktop_dist, require_desktop=args.require_desktop,
                )
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as output:
                for key, value in result.items():
                    output.write(f"{key}={value}\n")
    except (ValueError, OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"release channel check failed: {exc}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
