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
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import check_release

JSON_LIMIT = 2 * 1024 * 1024
ASSET_LIMIT = 256 * 1024 * 1024
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Allow public asset redirects, without forwarding API credentials."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if (req.has_header("Authorization") or target.scheme != "https"
                or target.username is not None or target.password is not None
                or target.hostname not in {"github.com", "release-assets.githubusercontent.com",
                                           "objects.githubusercontent.com"}):
            raise ValueError("unexpected HTTP redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HttpClient:
    """Bounded HTTPS access; only the GitHub API receives the GitHub token."""

    def __init__(self, token=None, opener=None):
        self.token = token
        self.opener = opener or urllib.request.build_opener(SafeRedirect())

    def request(self, url):
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != "https" or parsed.username is not None or parsed.password is not None
                or parsed.hostname not in {"api.github.com", "github.com", "pypi.org"}):
            raise ValueError("unexpected channel URL")
        headers = {"User-Agent": "lixity-release-check", "Accept": "application/json"}
        if parsed.hostname == "api.github.com":
            headers["Accept"] = "application/vnd.github+json"
            headers["X-GitHub-Api-Version"] = "2022-11-28"
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
        return urllib.request.Request(url, headers=headers)  # noqa: S310 - HTTPS and hosts checked above

    def json(self, url, *, missing=False, array=False):
        try:
            with self.opener.open(self.request(url), timeout=30) as response:
                raw = response.read(JSON_LIMIT + 1)
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            if missing and status == 404:
                return None
            raise ValueError(f"channel query failed: HTTP {status}") from None
        except (urllib.error.URLError, OSError, TimeoutError):
            raise ValueError("channel query failed: transport state is unknown") from None
        if len(raw) > JSON_LIMIT:
            raise ValueError("channel response exceeds the JSON limit")
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


def identities(root, tag, expected_commit, repo, client):
    """Bind checked-out source, peeled remote tag and expected commit together."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("repository must be owner/name")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("release tag must have the form vX.Y.Z")
    if not SHA.fullmatch(expected_commit):
        raise ValueError("expected commit must be a full lowercase Git SHA")
    version = check_release.source_version(root, tag)
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


def published(release):
    if release is None or release["draft"] or not release.get("published_at"):
        raise ValueError("GitHub release must already be published")
    if not release["immutable"]:
        raise ValueError("GitHub release must be immutable")


def assets(release, repo, tag):
    names = {f"lixity-{tag[1:]}-py3-none-any.whl", f"lixity-{tag[1:]}.tar.gz", "SHA256SUMS"}
    actual = release.get("assets")
    if not isinstance(actual, list) or len(actual) != 3:
        raise ValueError("GitHub release must contain exactly the wheel, sdist and SHA256SUMS")
    result = {}
    for asset in actual:
        if not isinstance(asset, dict) or asset.get("name") not in names:
            raise ValueError("GitHub release has an unexpected asset")
        name = asset["name"]
        digest = asset.get("digest")
        if name in result or asset.get("state") != "uploaded":
            raise ValueError("GitHub release has duplicate or incomplete assets")
        if not isinstance(digest, str) or not digest.startswith("sha256:") or not DIGEST.fullmatch(digest[7:]):
            raise ValueError("GitHub release asset SHA256 digest is unknown")
        size = asset.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= ASSET_LIMIT:
            raise ValueError("GitHub release asset has an invalid or excessive size")
        if asset.get("browser_download_url") != f"https://github.com/{repo}/releases/download/{tag}/{name}":
            raise ValueError("GitHub release asset URL differs from the selected release")
        result[name] = asset
    if set(result) != names:
        raise ValueError("GitHub release asset set is incomplete")
    return result


def verify_attestations(paths, repo, tag, expected_commit):
    """Require GitHub's signed workflow identity, tag/SHA and hosted runner."""
    for path in paths:
        command = [
            "gh", "attestation", "verify", str(path), "--repo", repo,
            "--source-digest", expected_commit, "--source-ref", f"refs/tags/{tag}",
            "--signer-digest", expected_commit,
            "--cert-identity", f"https://github.com/{repo}/.github/workflows/release.yml@refs/tags/{tag}",
            "--deny-self-hosted-runners",
        ]
        try:
            result = subprocess.run(  # noqa: S603 - fixed gh command, argv only
                command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError(f"attestation verification unavailable for {path.name}") from None
        if result.returncode:
            raise ValueError(f"attestation verification failed for {path.name}; a current gh CLI is required")


def verify_files(root, dist, tag, repo, expected_commit, release):
    expected = assets(release, repo, tag)
    check_release.verify_checksums(dist, tag[1:])
    for name, asset in expected.items():
        path = dist / name
        if (path.stat().st_size != asset["size"]
                or "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() != asset["digest"]):
            raise ValueError(f"GitHub release digest differs for {name}")
    verify_attestations([dist / name for name in sorted(expected)], repo, tag, expected_commit)
    check_release.validate(root, dist, tag)


def verify_github(root, tag, expected_commit, repo, dist, client, *, draft=False):
    identities(root, tag, expected_commit, repo, client)
    release = release_metadata(repo, tag, client, include_drafts=draft)
    if draft:
        if release is None or not release["draft"] or release["immutable"]:
            raise ValueError("GitHub release must be an unpublished draft")
    else:
        published(release)
    verify_files(root, dist, tag, repo, expected_commit, release)
    return {"state": "draft" if draft else "published", "source_sha": expected_commit, "tag": tag}


def empty_destination(path):
    if path.is_symlink() or (path.exists() and (not path.is_dir() or any(path.iterdir()))):
        raise ValueError("output directory must be absent or empty; existing files are preserved")
    path.parent.mkdir(parents=True, exist_ok=True)


def recover(root, tag, expected_commit, repo, dist, client):
    identities(root, tag, expected_commit, repo, client)
    release = release_metadata(repo, tag, client)
    published(release)
    expected = assets(release, repo, tag)
    empty_destination(dist)
    with tempfile.TemporaryDirectory(prefix=".lixity-release-", dir=dist.parent) as scratch:
        fresh = Path(scratch) / "dist"
        fresh.mkdir()
        for name, asset in sorted(expected.items()):
            client.download(asset["browser_download_url"], fresh / name, asset["size"])
        verify_files(root, fresh, tag, repo, expected_commit, release)
        if dist.exists():
            dist.rmdir()
        os.replace(fresh, dist)
    return {"state": "published", "source_sha": expected_commit, "tag": tag}


def pypi_missing(dist, tag, client):
    names = {f"lixity-{tag[1:]}-py3-none-any.whl", f"lixity-{tag[1:]}.tar.gz"}
    value = client.json(f"https://pypi.org/pypi/lixity/{tag[1:]}/json", missing=True)
    if value is None:
        return sorted(names)
    if not isinstance(value.get("info"), dict) or value["info"].get("version") != tag[1:]:
        raise ValueError("PyPI release version is unknown or differs from the requested version")
    files = value.get("urls")
    if not isinstance(files, list):
        raise ValueError("PyPI file state is unknown")
    found = set()
    for file in files:
        if not isinstance(file, dict) or file.get("filename") not in names:
            raise ValueError("PyPI has an unexpected distribution filename")
        name = file["filename"]
        if name in found or file.get("yanked") is not False:
            raise ValueError("PyPI has a duplicate or yanked distribution")
        digests = file.get("digests")
        actual = digests.get("sha256") if isinstance(digests, dict) else None
        expected = hashlib.sha256((dist / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"PyPI SHA256 digest differs or is unknown for {name}")
        found.add(name)
    return sorted(names - found)


def stage_pypi(root, tag, expected_commit, repo, dist, upload, client):
    verify_github(root, tag, expected_commit, repo, dist, client)
    missing = pypi_missing(dist, tag, client)
    empty_destination(upload)
    upload.mkdir(exist_ok=True)
    for name in missing:
        shutil.copyfile(dist / name, upload / name)
    return {"upload_count": len(missing), "state": "pending" if missing else "complete"}


def verify_pypi(root, tag, expected_commit, repo, dist, client):
    result = verify_github(root, tag, expected_commit, repo, dist, client)
    # Newly uploaded files can take a moment to appear. Retry only missing
    # visibility, never digest/auth/transport failures and never the upload.
    for attempt in range(3):
        missing = pypi_missing(dist, tag, client)
        if not missing:
            return {**result, "state": "complete"}
        if attempt < 2:
            time.sleep(2)
    raise ValueError("PyPI publication is incomplete: " + ", ".join(missing))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "recover", "verify-github", "verify-draft",
                                           "stage-pypi", "verify-pypi"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--upload", type=Path, default=Path("upload"))
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    client = HttpClient(token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    common = (args.root, args.tag, args.expected_commit, args.repo)
    try:
        if args.command == "inspect":
            result = inspect(*common, client)
        elif args.command == "recover":
            result = recover(*common, args.dist, client)
        elif args.command == "stage-pypi":
            result = stage_pypi(*common, args.dist, args.upload, client)
        elif args.command == "verify-pypi":
            result = verify_pypi(*common, args.dist, client)
        else:
            result = verify_github(*common, args.dist, client, draft=args.command == "verify-draft")
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as output:
                for key, value in result.items():
                    output.write(f"{key}={value}\n")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"release channel check failed: {exc}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
