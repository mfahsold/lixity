"""Recovery promotes verified published bytes and fails on unknown channel state."""

import copy
import hashlib
import importlib.util
import io
import json
import subprocess
import tarfile
import urllib.error
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TAG = "v0.3.0"
SHA = "a" * 40
REPO = "example/lixity"
API = f"https://api.github.com/repos/{REPO}"


@pytest.fixture
def channels(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("release_channels", ROOT / "scripts/release_channels.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def candidate(tmp_path):
    source = tmp_path / "source"
    package = source / "src/lixity"
    package.mkdir(parents=True)
    (package / "_version.py").write_text('__version__ = "0.3.0"\n')
    (package / "py.typed").write_bytes(b"")
    dist = tmp_path / "original"
    dist.mkdir()
    files = {"_version.py": b'__version__ = "0.3.0"\n', "py.typed": b""}
    wheel = dist / "lixity-0.3.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, contents in files.items():
            archive.writestr(f"lixity/{name}", contents)
        archive.writestr("lixity-0.3.0.dist-info/METADATA", "Name: lixity\nVersion: 0.3.0\n")
    with tarfile.open(dist / "lixity-0.3.0.tar.gz", "w:gz") as archive:
        for name, contents in {**{f"src/lixity/{k}": v for k, v in files.items()},
                               "PKG-INFO": b"Name: lixity\nVersion: 0.3.0\n"}.items():
            member = tarfile.TarInfo(f"lixity-0.3.0/{name}")
            member.size = len(contents)
            archive.addfile(member, io.BytesIO(contents))
    sums = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
                   for p in sorted(dist.iterdir()))
    (dist / "SHA256SUMS").write_text(sums)
    return source, dist


def metadata(dist):
    return {"id": 12, "tag_name": TAG, "draft": False, "immutable": True,
            "published_at": "2026-11-16T12:00:00Z", "assets": [
                {"id": i, "name": path.name, "state": "uploaded", "size": path.stat().st_size,
                 "digest": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
                 "browser_download_url": f"https://github.com/{REPO}/releases/download/{TAG}/{path.name}"}
                for i, path in enumerate(sorted(dist.iterdir()), 1)]}


class Responses:
    """Exercise HTTP classification and byte limits without external requests."""

    def __init__(self, values):
        self.values = values
        self.requests = []

    def open(self, request, *, timeout):
        self.requests.append(request)
        value = self.values[request.full_url]
        if callable(value):
            value = value()
        if isinstance(value, Exception):
            raise value
        return io.BytesIO(value if isinstance(value, bytes) else json.dumps(value).encode())


def client_for(channels, dist, *, release=None, pypi=None):
    values = {
        API + f"/git/ref/tags/{TAG}": {"object": {"type": "commit", "sha": SHA}},
        API + f"/releases/tags/{TAG}": release or metadata(dist),
        API + "/releases?per_page=100&page=1": [],
        f"https://pypi.org/pypi/lixity/{TAG[1:]}/json": pypi,
    }
    values.update({f"https://github.com/{REPO}/releases/download/{TAG}/{path.name}": path.read_bytes()
                   for path in dist.iterdir()})
    opener = Responses(values)
    return channels.HttpClient(token="secret",  # noqa: S106 - synthetic test credential
                                opener=opener), opener


def fake_git(monkeypatch, channels, sha=SHA):
    original = channels.subprocess.run

    def run(argv, **kwargs):
        if argv[:2] == ["git", "rev-parse"]:
            assert kwargs.get("cwd") is not None
            assert kwargs.get("text") is True and kwargs.get("stdout") == subprocess.PIPE
            return subprocess.CompletedProcess(argv, 0, sha + "\n", "")
        return original(argv, **kwargs)

    monkeypatch.setattr(channels.subprocess, "run", run)


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_only_confirmed_404_is_absent(channels, status):
    url = API + f"/releases/tags/{TAG}"
    failure = urllib.error.HTTPError(url, status, "credentials must stay private", {}, io.BytesIO())
    client = channels.HttpClient(opener=Responses({url: failure}))
    with pytest.raises(ValueError, match=f"HTTP {status}"):
        client.json(url, missing=True)
    absent = urllib.error.HTTPError(url, 404, "not found", {}, io.BytesIO())
    assert channels.HttpClient(opener=Responses({url: absent})).json(url, missing=True) is None
    with pytest.raises(ValueError, match="HTTP 404"):
        channels.HttpClient(opener=Responses({url: absent})).json(url)


def test_network_and_malformed_responses_are_unknown(channels):
    url = API + "/releases"
    for value in (urllib.error.URLError("private proxy"), b"not json", [], b"x" * (2 * 1024 * 1024 + 1)):
        client = channels.HttpClient(opener=Responses({url: value}))
        with pytest.raises(ValueError):
            client.json(url, missing=True)


def test_authentication_is_never_sent_to_asset_or_pypi_hosts(channels):
    url = "https://pypi.org/pypi/lixity/0.3.0/json"
    opener = Responses({url: {"urls": []}, API + "/releases": {}})
    client = channels.HttpClient(token="secret",  # noqa: S106 - synthetic test credential
                                opener=opener)
    client.json(url)
    client.json(API + "/releases")
    assert opener.requests[0].get_header("Authorization") is None
    assert opener.requests[1].get_header("Authorization") == "Bearer secret"


@pytest.mark.parametrize("mutate, message", [
    ({"draft": True, "immutable": False}, "published"),
    ({"immutable": False}, "immutable"),
    ({"tag_name": "v0.3.1"}, "tag"),
    ({"published_at": None}, "published"),
])
def test_recovery_rejects_unpublished_or_wrong_release(channels, candidate, monkeypatch, mutate, message):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    release = metadata(dist)
    release.update(mutate)
    client, _ = client_for(channels, dist, release=release)
    with pytest.raises(ValueError, match=message):
        channels.recover(source, TAG, SHA, REPO, dist.parent / "recovered", client)


def test_inspect_distinguishes_missing_draft_published(channels, candidate, monkeypatch):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    for release, expected in [(metadata(dist), "published"),
                              ({**metadata(dist), "draft": True, "immutable": False}, "draft"),
                              (urllib.error.HTTPError(API, 404, "missing", {}, io.BytesIO()), "missing")]:
        client, _ = client_for(channels, dist, release=release)
        assert channels.inspect(source, TAG, SHA, REPO, client)["state"] == expected


def test_source_and_remote_annotated_tag_must_match_expected_commit(channels, candidate, monkeypatch):
    source, dist = candidate
    fake_git(monkeypatch, channels, sha="b" * 40)
    client, opener = client_for(channels, dist)
    with pytest.raises(ValueError, match="source commit"):
        channels.inspect(source, TAG, SHA, REPO, client)
    fake_git(monkeypatch, channels)
    opener.values[API + f"/git/ref/tags/{TAG}"] = {"object": {"type": "tag", "sha": "c" * 40}}
    opener.values[API + "/git/tags/" + "c" * 40] = {"object": {"type": "commit", "sha": "b" * 40}}
    with pytest.raises(ValueError, match="tag commit"):
        channels.inspect(source, TAG, SHA, REPO, client)
    opener.values[API + "/git/tags/" + "c" * 40] = {"object": {"type": "commit", "sha": SHA}}
    assert channels.inspect(source, TAG, SHA, REPO, client)["source_sha"] == SHA


def test_recovery_keeps_exact_bytes_and_verifies_each_attestation(channels, candidate, monkeypatch):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    client, _ = client_for(channels, dist)
    commands = []
    monkeypatch.setattr(channels, "verify_attestations", lambda paths, repo, tag, sha: commands.append(
        (sorted(p.name for p in paths), repo, tag, sha)))
    recovered = dist.parent / "recovered"
    channels.recover(source, TAG, SHA, REPO, recovered, client)
    assert {p.name: p.read_bytes() for p in recovered.iterdir()} == {
        p.name: p.read_bytes() for p in dist.iterdir()}
    assert commands == [(["SHA256SUMS", "lixity-0.3.0-py3-none-any.whl", "lixity-0.3.0.tar.gz"],
                         REPO, TAG, SHA)]


@pytest.mark.parametrize("failure", ["metadata_digest", "download_digest", "missing_asset", "extra_asset", "attestation"])
def test_recovery_never_promotes_unverified_or_partial_files(channels, candidate, monkeypatch, failure):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    release = copy.deepcopy(metadata(dist))
    if failure == "metadata_digest":
        release["assets"][0]["digest"] = "sha256:" + "0" * 64
    elif failure == "missing_asset":
        release["assets"].pop()
    elif failure == "extra_asset":
        release["assets"].append({**release["assets"][0], "name": "other.whl"})
    client, opener = client_for(channels, dist, release=release)
    if failure == "download_digest":
        opener.values[release["assets"][0]["browser_download_url"]] = b"corrupt"
    def attest(*args):
        if failure == "attestation":
            raise ValueError("attestation failed")
    monkeypatch.setattr(channels, "verify_attestations", attest)
    recovered = dist.parent / "recovered"
    with pytest.raises(ValueError):
        channels.recover(source, TAG, SHA, REPO, recovered, client)
    assert not recovered.exists()
    assert len(list(dist.iterdir())) == 3


@pytest.mark.parametrize("existing, expected", [((), 2), (("wheel",), 1), (("wheel", "sdist"), 0)])
def test_pypi_reconciliation_stages_only_missing_identical_files(channels, candidate, monkeypatch, existing, expected):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    names = {"wheel": "lixity-0.3.0-py3-none-any.whl", "sdist": "lixity-0.3.0.tar.gz"}
    files = [{"filename": names[k], "digests": {"sha256": hashlib.sha256((dist / names[k]).read_bytes()).hexdigest()},
              "yanked": False} for k in existing]
    client, _ = client_for(channels, dist, pypi={"info": {"version": "0.3.0"}, "urls": files})
    monkeypatch.setattr(channels, "verify_attestations", lambda *args: None)
    upload = dist.parent / "upload"
    result = channels.stage_pypi(source, TAG, SHA, REPO, dist, upload, client)
    assert result["upload_count"] == expected
    assert {p.name for p in upload.iterdir()} == set(names.values()) - {names[k] for k in existing}
    assert all(p.read_bytes() == (dist / p.name).read_bytes() for p in upload.iterdir())


@pytest.mark.parametrize("files", [
    [{"filename": "lixity-0.3.0-py3-none-any.whl", "digests": {"sha256": "0" * 64}, "yanked": False}],
    [{"filename": "other.whl", "digests": {"sha256": "0" * 64}, "yanked": False}],
    [{"filename": "lixity-0.3.0-py3-none-any.whl", "digests": {}, "yanked": False}],
])
def test_pypi_mismatch_is_never_silently_skipped(channels, candidate, monkeypatch, files):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    client, _ = client_for(channels, dist, pypi={"info": {"version": "0.3.0"}, "urls": files})
    monkeypatch.setattr(channels, "verify_attestations", lambda *args: None)
    upload = dist.parent / "upload"
    with pytest.raises(ValueError, match="PyPI"):
        channels.stage_pypi(source, TAG, SHA, REPO, dist, upload, client)
    assert not upload.exists()


def test_attestation_policy_pins_repository_workflow_source_tag_and_hosted_runner(channels, candidate, monkeypatch):
    _, dist = candidate
    commands = []
    def run(argv, **kwargs):
        commands.append(argv)
        return subprocess.CompletedProcess(argv, 0)
    monkeypatch.setattr(channels.subprocess, "run", run)
    channels.verify_attestations(sorted(dist.iterdir()), REPO, TAG, SHA)
    assert len(commands) == 3
    for command in commands:
        assert command[:3] == ["gh", "attestation", "verify"]
        assert command[command.index("--repo") + 1] == REPO
        assert command[command.index("--source-digest") + 1] == SHA
        assert command[command.index("--source-ref") + 1] == "refs/tags/v0.3.0"
        assert command[command.index("--cert-identity") + 1] == (
            "https://github.com/example/lixity/.github/workflows/release.yml@refs/tags/v0.3.0")
        assert "--deny-self-hosted-runners" in command
    monkeypatch.setattr(channels.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a[0], 1))
    with pytest.raises(ValueError, match="attestation"):
        channels.verify_attestations(sorted(dist.iterdir()), REPO, TAG, SHA)


def test_inspect_and_draft_verification_find_drafts_hidden_from_by_tag_endpoint(channels, candidate, monkeypatch):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    client, opener = client_for(channels, dist)
    opener.values[API + f"/releases/tags/{TAG}"] = urllib.error.HTTPError(API, 404, "not published", {}, io.BytesIO())
    draft = {**metadata(dist), "draft": True, "immutable": False, "published_at": None}
    opener.values[API + "/releases?per_page=100&page=1"] = [draft]
    monkeypatch.setattr(channels, "verify_attestations", lambda *args: None)
    assert channels.inspect(source, TAG, SHA, REPO, client)["state"] == "draft"
    assert channels.verify_github(source, TAG, SHA, REPO, dist, client, draft=True)["state"] == "draft"


def test_failed_draft_listing_cannot_turn_404_into_missing(channels, candidate, monkeypatch):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    client, opener = client_for(channels, dist)
    opener.values[API + f"/releases/tags/{TAG}"] = urllib.error.HTTPError(API, 404, "missing", {}, io.BytesIO())
    opener.values[API + "/releases?per_page=100&page=1"] = urllib.error.HTTPError(API, 403, "denied", {}, io.BytesIO())
    with pytest.raises(ValueError, match="HTTP 403"):
        channels.inspect(source, TAG, SHA, REPO, client)


def test_pypi_transport_failure_prevents_upload_staging(channels, candidate, monkeypatch):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    client, opener = client_for(channels, dist)
    url = f"https://pypi.org/pypi/lixity/{TAG[1:]}/json"
    monkeypatch.setattr(channels, "verify_attestations", lambda *args: None)
    for failure in (urllib.error.HTTPError(url, 503, "unavailable", {}, io.BytesIO()),
                    urllib.error.URLError("no route")):
        opener.values[url] = failure
        with pytest.raises(ValueError):
            channels.stage_pypi(source, TAG, SHA, REPO, dist, dist.parent / "upload", client)
        assert not (dist.parent / "upload").exists()


def test_recovery_preserves_existing_files_on_failure(channels, candidate, monkeypatch):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    client, _ = client_for(channels, dist)
    recovered = dist.parent / "recovered"
    recovered.mkdir()
    (recovered / "keep.txt").write_bytes(b"previous candidate")
    with pytest.raises(ValueError, match="preserved"):
        channels.recover(source, TAG, SHA, REPO, recovered, client)
    assert (recovered / "keep.txt").read_bytes() == b"previous candidate"


def test_redirects_reject_credentials_and_untrusted_hosts(channels):
    policy = channels.SafeRedirect()
    request = channels.urllib.request.Request("https://api.github.com/repos/example/lixity", headers={"Authorization": "Bearer private"})
    with pytest.raises(ValueError, match="redirect"):
        policy.redirect_request(request, None, 302, "found", {}, "https://github.com/file")
    public = channels.urllib.request.Request("https://github.com/example/lixity/releases/download/v0.3.0/file")
    for target in ("http://release-assets.githubusercontent.com/file", "https://example.org/file", "https://user:secret@github.com/file"):
        with pytest.raises(ValueError, match="redirect"):
            policy.redirect_request(public, None, 302, "found", {}, target)
    redirected = policy.redirect_request(public, None, 302, "found", {}, "https://release-assets.githubusercontent.com/file")
    assert redirected.get_header("Authorization") is None


def test_post_upload_verification_waits_only_for_missing_visibility(channels, candidate, monkeypatch):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    client, opener = client_for(channels, dist)
    monkeypatch.setattr(channels, "verify_attestations", lambda *args: None)
    complete = {"info": {"version": "0.3.0"}, "urls": [
        {"filename": p.name, "yanked": False,
         "digests": {"sha256": hashlib.sha256(p.read_bytes()).hexdigest()}}
        for p in dist.iterdir() if p.name != "SHA256SUMS"]}
    url = f"https://pypi.org/pypi/lixity/{TAG[1:]}/json"
    observed = iter([{"info": {"version": "0.3.0"}, "urls": []}, complete])
    opener.values[url] = lambda: next(observed)
    delays = []
    monkeypatch.setattr(channels.time, "sleep", delays.append)
    assert channels.verify_pypi(source, TAG, SHA, REPO, dist, client)["state"] == "complete"
    assert delays == [2]
    assert len([r for r in opener.requests if r.full_url == url]) == 2
    assert not (dist.parent / "upload").exists()


def test_post_upload_verification_is_bounded_and_never_reuploads(channels, candidate, monkeypatch):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    client, opener = client_for(channels, dist, pypi={"info": {"version": "0.3.0"}, "urls": []})
    monkeypatch.setattr(channels, "verify_attestations", lambda *args: None)
    delays = []
    monkeypatch.setattr(channels.time, "sleep", delays.append)
    with pytest.raises(ValueError, match="incomplete"):
        channels.verify_pypi(source, TAG, SHA, REPO, dist, client)
    url = f"https://pypi.org/pypi/lixity/{TAG[1:]}/json"
    assert len([r for r in opener.requests if r.full_url == url]) == 3
    assert delays == [2, 2]
    assert not (dist.parent / "upload").exists()


def test_pypi_404_stages_both_files_and_digest_conflicts_do_not_retry(channels, candidate, monkeypatch):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    client, opener = client_for(channels, dist)
    monkeypatch.setattr(channels, "verify_attestations", lambda *args: None)
    url = f"https://pypi.org/pypi/lixity/{TAG[1:]}/json"
    opener.values[url] = urllib.error.HTTPError(url, 404, "not published", {}, io.BytesIO())
    upload = dist.parent / "upload"
    assert channels.stage_pypi(source, TAG, SHA, REPO, dist, upload, client)["upload_count"] == 2
    opener.requests.clear()
    opener.values[url] = {"info": {"version": "0.3.0"}, "urls": [
        {"filename": "lixity-0.3.0.tar.gz", "yanked": False, "digests": {"sha256": "0" * 64}}]}
    delays = []
    monkeypatch.setattr(channels.time, "sleep", delays.append)
    with pytest.raises(ValueError, match="PyPI SHA256"):
        channels.verify_pypi(source, TAG, SHA, REPO, dist, client)
    assert delays == []
    assert len([r for r in opener.requests if r.full_url == url]) == 1


def test_published_checksum_manifest_is_evidence_never_rewritten(channels, candidate, monkeypatch):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    (dist / "SHA256SUMS").write_bytes(b"malformed evidence\n")
    client, _ = client_for(channels, dist)
    monkeypatch.setattr(channels, "verify_attestations", lambda *args: None)
    with pytest.raises(ValueError):
        channels.verify_github(source, TAG, SHA, REPO, dist, client)
    assert (dist / "SHA256SUMS").read_bytes() == b"malformed evidence\n"


def test_identity_uses_selected_source_checkout_with_real_git(channels, candidate, monkeypatch, tmp_path):
    source, _ = candidate
    subprocess.run(  # noqa: S603 - synthetic temporary repository
        ["git", "init", "-q", str(source)], check=True,  # noqa: S607 - git is a test prerequisite
    )
    subprocess.run(["git", "-c", "user.name=Synthetic Test", "-c", "user.email=test@example.invalid",  # noqa: S607
                    "commit", "--allow-empty", "-q", "-m", "Synthetic release identity"],
                   cwd=source, check=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source, check=True,  # noqa: S607
                            text=True, stdout=subprocess.PIPE).stdout.strip()
    client = channels.HttpClient(opener=Responses({
        API + f"/git/ref/tags/{TAG}": {"object": {"type": "commit", "sha": commit}}}))
    monkeypatch.chdir(tmp_path)
    assert channels.identities(source, TAG, commit, REPO, client) == "0.3.0"


@pytest.mark.parametrize("entry", [{}, {"tag_name": None}, {"tag_name": [TAG]}, {"tag_name": ""}])
def test_malformed_release_listing_cannot_establish_absence(channels, candidate, monkeypatch, entry):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    client, opener = client_for(channels, dist)
    opener.values[API + f"/releases/tags/{TAG}"] = urllib.error.HTTPError(API, 404, "missing", {}, io.BytesIO())
    opener.values[API + "/releases?per_page=100&page=1"] = [entry]
    with pytest.raises(ValueError, match="listing"):
        channels.inspect(source, TAG, SHA, REPO, client)
