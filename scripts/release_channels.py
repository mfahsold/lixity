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
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import check_release
from build_public_site import LANGUAGES, page_path

JSON_LIMIT = 2 * 1024 * 1024
ASSET_LIMIT = 256 * 1024 * 1024
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")
RELEASE_TAG = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
DEFAULT_PAGES_URL = "https://mfahsold.github.io/lixity/"
PAGES_VERIFY_FILES = (
    *(page_path(language) for language in LANGUAGES),
    *(f"guides/metrics/{language}.html" for language in LANGUAGES),
    "guides/installation.html",
    "desktop-downloads.json",
    "llms.txt",
    "sandbox/index.html",
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


def published(release):
    if release is None or release["draft"] or not release.get("published_at"):
        raise ValueError("GitHub release must already be published")
    if not release["immutable"]:
        raise ValueError("GitHub release must be immutable")


def assets(release, repo, tag, *, draft=False):
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
        url = asset.get("browser_download_url")
        expected_url = f"https://github.com/{repo}/releases/download/{tag}/{name}"
        draft_pattern = re.compile(
            rf"https://github\.com/{re.escape(repo)}/releases/download/untagged-[0-9a-f]+/{re.escape(name)}",
        )
        if url != expected_url and not (draft and isinstance(url, str) and draft_pattern.fullmatch(url)):
            raise ValueError("GitHub release asset URL differs from the selected release")
        result[name] = asset
    if set(result) != names:
        raise ValueError("GitHub release asset set is incomplete")
    return result


def verify_attestations(paths, repo, tag, expected_commit):
    """Require GitHub's signed workflow identity, tag/SHA and hosted runner."""
    gh_bin = resolve_gh_binary()
    sub_env = github_subprocess_env()
    for path in paths:
        command = [
            gh_bin, "attestation", "verify", str(path), "--repo", repo,
            "--source-digest", expected_commit, "--source-ref", f"refs/tags/{tag}",
            "--signer-digest", expected_commit,
            "--cert-identity", f"https://github.com/{repo}/.github/workflows/release.yml@refs/tags/{tag}",
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


def verify_files(root, dist, tag, repo, expected_commit, release, *, draft=False):
    expected = assets(release, repo, tag, draft=draft)
    check_release.verify_checksums(dist, tag[1:])
    for name, asset in expected.items():
        path = dist / name
        if (path.stat().st_size != asset["size"]
                or "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() != asset["digest"]):
            raise ValueError(f"GitHub release digest differs for {name}")
    verify_attestations([dist / name for name in sorted(expected)], repo, tag, expected_commit)
    check_release.validate(root, dist, tag)
    return {name: asset["digest"].removeprefix("sha256:") for name, asset in expected.items()}


def verify_github(root, tag, expected_commit, repo, dist, client, *,
                  draft=False, include_digests=False):
    identities(root, tag, expected_commit, repo, client)
    release = release_metadata(repo, tag, client, include_drafts=draft)
    if draft:
        if release is None or not release["draft"] or release["immutable"]:
            raise ValueError("GitHub release must be an unpublished draft")
    else:
        published(release)
    digests = verify_files(root, dist, tag, repo, expected_commit, release, draft=draft)
    return {"state": "draft" if draft else "published", "source_sha": expected_commit, "tag": tag,
            **({"digests": digests} if include_digests else {})}


def empty_destination(path):
    if path.is_symlink() or (path.exists() and (not path.is_dir() or any(path.iterdir()))):
        raise ValueError("output directory must be absent or empty; existing files are preserved")
    path.parent.mkdir(parents=True, exist_ok=True)


def recover(root, tag, expected_commit, repo, dist, client, *, include_digests=False):
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
        digests = verify_files(root, fresh, tag, repo, expected_commit, release)
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
    verify_github(root, tag, expected_commit, repo, dist, client)
    published_files = _pypi_release_files(dist, tag, client)
    missing = sorted(_pypi_filenames(tag) - published_files.keys())
    empty_destination(upload)
    upload.mkdir(exist_ok=True)
    for name in missing:
        shutil.copyfile(dist / name, upload / name)
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
    result = verify_github(root, tag, expected_commit, repo, dist, client)
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


def doctor(root, repo, client, *, tag=None, unset_env_tokens=False):
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
    if tag is not None:
        version = check_release.source_version(root, tag)
        notes = root / "docs" / "releases" / f"{tag}.md"
        if not notes.is_file():
            raise ValueError(f"missing release notes for {tag}")
        notes_text = notes.read_text(encoding="utf-8")
        if not notes_text.strip() or "(pending)" in notes_text or "Pending release." in notes_text:
            raise ValueError(f"release notes for {tag} still contain pending placeholders")
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
    query = urllib.parse.urlencode({
        "q": f'metadata.related_identifiers.identifier:"https://github.com/{repo}/tree/{tag}"',
        "size": 1,
    })
    try:
        payload = client.json(f"https://zenodo.org/api/records?{query}")
    except ValueError:
        return {"zenodo_status": "unknown", "zenodo_doi": None, "zenodo_url": None}
    hits = payload.get("hits", {}).get("hits") if isinstance(payload.get("hits"), dict) else None
    if not isinstance(hits, list):
        return {"zenodo_status": "unknown", "zenodo_doi": None, "zenodo_url": None}
    if not hits:
        return {"zenodo_status": "pending", "zenodo_doi": None, "zenodo_url": None}
    record = hits[0] if isinstance(hits[0], dict) else {}
    doi = record.get("doi") if isinstance(record.get("doi"), str) else None
    links = record.get("links") if isinstance(record.get("links"), dict) else {}
    self_html = links.get("self_html") if isinstance(links.get("self_html"), str) else None
    return {"zenodo_status": "minted" if doi else "pending", "zenodo_doi": doi, "zenodo_url": self_html}


def verify_release(
    root, tag, expected_commit, repo, dist, client, *,
    base_url=DEFAULT_PAGES_URL, check_zenodo=False, skip_pypi=False, skip_pages=False,
):
    """Verify a GitHub release and its selected publication channels."""
    if not dist.exists() or not any(dist.iterdir()):
        github = recover(root, tag, expected_commit, repo, dist, client, include_digests=True)
    else:
        github = verify_github(root, tag, expected_commit, repo, dist, client, include_digests=True)
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
                 "verify-pypi", "doctor", "verify-pages", "verify-zenodo", "verify-release"),
    )
    parser.add_argument("--root", type=Path, help="Source checkout for local verification")
    parser.add_argument("--tag")
    parser.add_argument("--expected-commit")
    parser.add_argument("--repo", help="GitHub repository as owner/name")
    parser.add_argument("--dist", type=Path, default=Path("dist"))
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
            result = doctor(args.root, args.repo, client, tag=args.tag, unset_env_tokens=args.use_keyring)
        elif args.command == "verify-pages":
            result = verify_pages(args.root, args.tag, args.expected_commit, client, base_url=args.base_url)
        elif args.command == "verify-zenodo":
            result = {"tag": args.tag, **zenodo_status(args.repo, args.tag, client)}
        elif args.command == "verify-release":
            result = verify_release(
                args.root, args.tag, args.expected_commit, args.repo, args.dist, client,
                base_url=args.base_url, check_zenodo=args.check_zenodo,
                skip_pypi=args.skip_pypi, skip_pages=args.skip_pages,
            )
        else:
            common = (args.root, args.tag, args.expected_commit, args.repo)
            if args.command == "inspect":
                result = inspect(*common, client)
            elif args.command == "recover":
                result = recover(*common, args.dist, client)
            elif args.command == "stage-pypi":
                result = stage_pypi(*common, args.dist, args.upload, client)
            elif args.command == "verify-pypi":
                result = verify_pypi(*common, args.dist, client)
            else:
                result = verify_github(
                    *common, args.dist, client, draft=args.command == "verify-draft",
                )
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as output:
                for key, value in result.items():
                    output.write(f"{key}={value}\n")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"release channel check failed: {exc}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
