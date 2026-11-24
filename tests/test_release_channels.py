"""Recovery promotes verified published bytes and fails on unknown channel state."""

import copy
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import urllib.error
import zipfile
from pathlib import Path

import pytest

from desktop.scripts import qualify_desktop_release as qualification
from desktop.scripts import verify_desktop_artifacts as desktop

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


@pytest.fixture
def desktop_candidate(tmp_path):
    bundle = tmp_path / "installer-workflow"
    magic = {
        "macos-dmg": ("dmg", b"x\x01"),
        "windows-msi": ("msi", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
        "windows-nsis": ("nsis", b"MZ"),
        "linux-deb": ("deb", b"!<arch>\n"),
        "linux-appimage": ("appimage", b"\x7fELF"),
    }
    installers = desktop.public_installer_inventory(TAG)
    for target in sorted({target for target, _ in installers.values()}):
        base = tmp_path / target
        for filename, (owner, kind) in installers.items():
            if owner == target:
                directory, prefix = magic[kind]
                path = base / directory / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(prefix.ljust(512, b"\0"))
        assert desktop.main([str(base), "--target", target, "--out-dir", str(bundle),
                             "--copy-to", str(bundle)]) == 0
    (bundle / desktop.DESKTOP_CHECKSUMS).write_bytes(
        desktop.desktop_checksums(desktop.load_verified_artifacts(bundle)),
    )
    receipt = qualification.qualification_template(bundle, tag=TAG, source_sha=SHA)
    receipt["reviewed_by"] = "Synthetic reviewer"
    for entry in receipt["installers"].values():
        entry["checks"] = dict.fromkeys(entry["checks"], True)
        entry["os"] = "Synthetic clean VM"
        entry["evidence"] = "Synthetic fixture evidence"
    review = tmp_path / qualification.QUALIFICATION_FILE
    review.write_text(json.dumps(receipt))
    return bundle, review


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


def test_desktop_draft_and_public_recovery_use_the_same_qualified_bytes(
    channels, candidate, desktop_candidate, monkeypatch, tmp_path,
):
    root, dist = candidate
    installers, review = desktop_candidate
    fake_git(monkeypatch, channels)
    calls = []
    monkeypatch.setattr(
        channels, "verify_attestations",
        lambda paths, repo, tag, sha, **flags: calls.append(({p.name for p in paths}, flags)),
    )
    staged = tmp_path / "staged-desktop"
    receipt = json.loads(review.read_bytes())
    review.write_text(json.dumps({**receipt, "source_sha": "b" * 40}))
    with pytest.raises(ValueError, match="different release tag or source"):
        channels.stage_desktop(root, TAG, SHA, REPO, installers, review, staged)
    assert not staged.exists()
    review.write_text(json.dumps(receipt))
    assert channels.stage_desktop(root, TAG, SHA, REPO, installers, review, staged)["installer_count"] == 7
    assert calls[-1][1] == {"desktop": True}
    assert channels.QUALIFICATION_FILE not in calls[-1][0]

    release = metadata(dist)
    client, opener = client_for(channels, dist, release=release)
    with pytest.raises(ValueError, match="requires the qualified desktop installer set"):
        channels.verify_github(root, TAG, SHA, REPO, dist, client, require_desktop=True)
    release["prerelease"] = False
    release["assets"].extend(metadata(staged)["assets"])
    for path in staged.iterdir():
        opener.values[f"https://github.com/{REPO}/releases/download/{TAG}/{path.name}"] = path.read_bytes()

    release["draft"], release["immutable"] = True, False
    assert channels.verify_github(root, TAG, SHA, REPO, dist, client, draft=True,
                                  require_desktop=True, desktop_dist=staged)["state"] == "draft"
    release["draft"], release["immutable"] = False, True
    result = channels.recover(root, TAG, SHA, REPO, tmp_path / "recovered", client, include_digests=True)
    assert set(result["digests"]) == {path.name for path in (*dist.iterdir(), *staged.iterdir())}
    assert {path.name for path in (tmp_path / "recovered").iterdir()} == {path.name for path in dist.iterdir()}
    review_asset = next(item for item in release["assets"] if item["name"] == channels.QUALIFICATION_FILE)
    review_asset["digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match=r"digest differs for desktop-qualification\.json"):
        channels.verify_github(root, TAG, SHA, REPO, dist, client, desktop_dist=staged)


def test_catalog_records_attested_public_installer_bytes_atomically(
    channels, candidate, desktop_candidate, monkeypatch, tmp_path, capsys,
):
    root, dist = candidate
    installers, review = desktop_candidate
    fake_git(monkeypatch, channels)
    calls = []
    monkeypatch.setattr(channels, "verify_attestations",
                        lambda paths, *args, **flags: calls.append(({p.name for p in paths}, flags)))
    staged = tmp_path / "staged-desktop"
    channels.stage_desktop(root, TAG, SHA, REPO, installers, review, staged)
    base = f"https://github.com/{REPO}/releases"
    monkeypatch.setattr(channels.desktop_downloads, "RELEASES", base)
    release = {**metadata(dist), "prerelease": False, "html_url": f"{base}/tag/{TAG}"}
    release["assets"].extend(metadata(staged)["assets"])
    client, opener = client_for(channels, dist, release=release)
    for path in staged.iterdir():
        opener.values[f"{base}/download/{TAG}/{path.name}"] = path.read_bytes()
    output = tmp_path / "catalog.json"
    output.write_text("previous catalog")

    missing = next(asset for asset in release["assets"] if asset["name"].endswith("de-DE.msi"))
    release["assets"].remove(missing)
    with pytest.raises(ValueError, match=r"asset set is incomplete.*de-DE\.msi"):
        channels.record_desktop_catalog(root, TAG, SHA, REPO, output, client)
    assert output.read_text() == "previous catalog"
    assert len(opener.requests) == 2  # Tag identity and release metadata only.
    release["assets"].append(missing)

    url = missing["browser_download_url"]
    original = opener.values[url]
    opener.values[url] = b"\0" * len(original)
    with pytest.raises(ValueError, match=r"GitHub release digest differs.*de-DE\.msi"):
        channels.record_desktop_catalog(root, TAG, SHA, REPO, output, client)
    assert output.read_text() == "previous catalog"
    opener.values[url] = original

    monkeypatch.setattr(channels, "HttpClient", lambda **kwargs: client)
    monkeypatch.setattr(sys, "argv", ["release_channels", "record-desktop-catalog", "--root", str(root),
                                    "--tag", TAG, "--expected-commit", SHA, "--repo", REPO,
                                    "--catalog-output", str(output)])
    capsys.readouterr()
    channels.main()
    assert json.loads(capsys.readouterr().out)["installer_count"] == 7
    catalog = json.loads(output.read_bytes())
    assert catalog["tag"] == TAG
    assert {entry["filename"] for entry in catalog["installers"]} == desktop.public_installer_inventory(TAG).keys()
    assert calls[-1] == ({path.name for path in staged.iterdir()} - {channels.QUALIFICATION_FILE}, {"desktop": True})


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


@pytest.mark.parametrize("failure", ["interrupted", "wrong_bytes"])
def test_pypi_staging_keeps_previous_directory_intact_until_both_copies_verify(
    channels, candidate, monkeypatch, tmp_path, failure,
):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    client, _ = client_for(channels, dist, pypi={"info": {"version": TAG[1:]}, "urls": []})
    monkeypatch.setattr(channels, "verify_attestations", lambda *args: None)
    upload = tmp_path / "upload"
    upload.mkdir()
    copyfile = channels.shutil.copyfile

    def break_second_copy(src, dst):
        copyfile(src, dst)
        if src.name.endswith(".tar.gz"):
            if failure == "interrupted":
                raise OSError("synthetic copy interruption")
            dst.write_bytes(b"wrong distribution bytes")

    monkeypatch.setattr(channels.shutil, "copyfile", break_second_copy)
    expected = (OSError, "copy interruption") if failure == "interrupted" else (ValueError, "Staged PyPI distribution")
    with pytest.raises(expected[0], match=expected[1]):
        channels.stage_pypi(source, TAG, SHA, REPO, dist, upload, client)
    assert list(upload.iterdir()) == []
    assert not list(tmp_path.glob(".lixity-pypi-*"))

    monkeypatch.setattr(channels.shutil, "copyfile", copyfile)
    result = channels.stage_pypi(source, TAG, SHA, REPO, dist, upload, client)
    assert result == {"state": "pending", "upload_count": 2}
    assert {path.name: path.read_bytes() for path in upload.iterdir()} == {
        path.name: path.read_bytes() for path in dist.iterdir() if path.name != "SHA256SUMS"
    }


def test_attestation_policy_pins_repository_workflow_source_tag_and_hosted_runner(channels, candidate, monkeypatch):
    _, dist = candidate
    commands = []
    def run(argv, **kwargs):
        commands.append((argv, kwargs.get("env")))
        return subprocess.CompletedProcess(argv, 0)
    monkeypatch.setattr(channels.subprocess, "run", run)
    monkeypatch.setenv("GIT_ASKPASS", "/broken/askpass")
    channels.verify_attestations(sorted(dist.iterdir()), REPO, TAG, SHA)
    assert len(commands) == 3
    for command, env in commands:
        assert Path(command[0]).name == "gh"
        assert command[1:3] == ["attestation", "verify"]
        assert command[command.index("--repo") + 1] == REPO
        assert command[command.index("--source-digest") + 1] == SHA
        assert command[command.index("--source-ref") + 1] == "refs/tags/v0.3.0"
        assert command[command.index("--cert-identity") + 1] == (
            "https://github.com/example/lixity/.github/workflows/release.yml@refs/tags/v0.3.0")
        assert "--deny-self-hosted-runners" in command
        assert env is not None and "GIT_ASKPASS" not in env
        assert env["GIT_TERMINAL_PROMPT"] == "0"
    commands.clear()
    channels.verify_attestations([dist / "Lixity_0.3.0_aarch64.dmg"], REPO, TAG, SHA, desktop=True)
    command = commands[0][0]
    assert command[command.index("--source-ref") + 1] == "refs/heads/main"
    assert command[command.index("--cert-identity") + 1] == (
        "https://github.com/example/lixity/.github/workflows/desktop-release.yml@refs/heads/main")
    assert command[command.index("--source-digest") + 1] == SHA
    assert command[command.index("--signer-digest") + 1] == SHA
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
    draft["assets"] = [
        {**asset, "browser_download_url": f"https://github.com/{REPO}/releases/download/untagged-952a0a99dd3f413504a9/{asset['name']}"}
        for asset in draft["assets"]
    ]
    opener.values[API + "/releases?per_page=100&page=1"] = [draft]
    monkeypatch.setattr(channels, "verify_attestations", lambda *args: None)
    assert channels.inspect(source, TAG, SHA, REPO, client)["state"] == "draft"
    assert channels.verify_github(source, TAG, SHA, REPO, dist, client, draft=True)["state"] == "draft"
    # Published releases must still reject untagged draft URLs.
    published_untagged = {**draft, "draft": False, "immutable": True, "published_at": "2026-11-16T12:00:00Z"}
    opener.values[API + f"/releases/tags/{TAG}"] = published_untagged
    with pytest.raises(ValueError, match="URL"):
        channels.verify_github(source, TAG, SHA, REPO, dist, client, draft=False)


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
    assert delays == [5]
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
    assert len([r for r in opener.requests if r.full_url == url]) == 12
    assert delays == [5] * 11
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


def test_resolve_gh_binary_and_github_subprocess_env(channels, monkeypatch, tmp_path):
    fake_home = tmp_path / "home"
    local_gh = fake_home / ".local/bin/gh"
    local_gh.parent.mkdir(parents=True)
    local_gh.write_text("#!/bin/sh\n")
    local_gh.chmod(0o755)
    monkeypatch.setattr(channels.Path, "home", classmethod(lambda cls: fake_home))
    monkeypatch.delenv("GH_BIN", raising=False)
    assert channels.resolve_gh_binary() == str(local_gh)

    custom_gh = str(tmp_path / "custom-gh")
    monkeypatch.setenv("GH_BIN", custom_gh)
    assert channels.resolve_gh_binary() == custom_gh

    monkeypatch.delenv("GH_BIN", raising=False)
    local_gh.unlink()
    monkeypatch.setattr(channels.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    assert channels.resolve_gh_binary() == "/usr/bin/gh"

    base = {
        "PATH": "/usr/bin",
        "GH_TOKEN": "narrow-token",
        "GITHUB_TOKEN": "other-token",
        "GIT_ASKPASS": "/askpass",
        "SSH_ASKPASS": "/ssh-askpass",
        "VSCODE_GIT_ASKPASS_NODE": "/node",
        "VSCODE_GIT_ASKPASS_MAIN": "/main.js",
        "VSCODE_GIT_ASKPASS_EXTRA_ARGS": "--arg",
        "VSCODE_GIT_IPC_HANDLE": str(tmp_path / "ipc.sock"),
    }
    sanitized = channels.github_subprocess_env(base)
    assert sanitized == {"PATH": "/usr/bin", "GH_TOKEN": "narrow-token", "GITHUB_TOKEN": "other-token",
                         "GIT_TERMINAL_PROMPT": "0"}
    keyring_env = channels.github_subprocess_env(base, unset_env_tokens=True)
    assert keyring_env == {"PATH": "/usr/bin", "GIT_TERMINAL_PROMPT": "0"}


def _doctor_subprocess(channels, monkeypatch, *, flags="--source-digest --signer-digest --cert-identity --deny-self-hosted-runners",
                       auth_code=0, auth_out="Token scopes: 'gist', 'read:org', 'repo', 'workflow'\n",
                       signing_lists=None):
    def fake_run(argv, **kwargs):
        name = Path(argv[0]).name
        if name == "gh":
            if argv[1:] == ["--version"]:
                return subprocess.CompletedProcess(argv, 0, "gh version 2.104.0\n", "")
            if argv[1:] == ["attestation", "verify", "--help"]:
                return subprocess.CompletedProcess(argv, 0, flags, "")
            if argv[1:] == ["auth", "status"]:
                return subprocess.CompletedProcess(argv, auth_code, auth_out, "")
            if signing_lists is not None:
                for kind, command in (
                    ("secret", ["secret", "list", "--app", "actions"]),
                    ("variable", ["variable", "list"]),
                ):
                    if argv[1:] == [*command, "--repo", REPO, "--json", "name"]:
                        code, rows = signing_lists[kind]
                        return subprocess.CompletedProcess(argv, code, json.dumps(rows), "private diagnostic")
        if name == "git":
            if argv[1:] == ["rev-parse", "HEAD"]:
                return subprocess.CompletedProcess(argv, 0, SHA + "\n", "")
            if argv[1:] == ["rev-parse", "--abbrev-ref", "HEAD"]:
                return subprocess.CompletedProcess(argv, 0, "main\n", "")
            if argv[1:] == ["status", "--porcelain"]:
                return subprocess.CompletedProcess(argv, 0, "", "")
            if argv[1:] == ["worktree", "list", "--porcelain"]:
                return subprocess.CompletedProcess(
                    argv, 0,
                    f"worktree /repo\nHEAD {SHA}\nbranch refs/heads/main\n\n"
                    f"worktree /tmp/stale\nHEAD {SHA}\nbranch refs/heads/old\nprunable gitdir\n",
                    "",
                )
        raise AssertionError(f"Unexpected subprocess: {argv}")

    monkeypatch.setattr(channels.subprocess, "run", fake_run)


def test_doctor_reports_git_gh_and_channel_readiness(channels, candidate, monkeypatch):
    source, dist = candidate
    notes = source / "docs/releases" / f"{TAG}.md"
    notes.parent.mkdir(parents=True)
    notes.write_text("# Lixity v0.3.0\n\nVerified notes.\n", encoding="utf-8")
    _doctor_subprocess(channels, monkeypatch)
    client, opener = client_for(channels, dist)
    opener.values[API + f"/releases/tags/{TAG}"] = urllib.error.HTTPError(API, 404, "missing", {}, io.BytesIO())
    opener.values[f"https://pypi.org/pypi/lixity/{TAG[1:]}/json"] = urllib.error.HTTPError(
        "https://pypi.org", 404, "missing", {}, io.BytesIO(),
    )
    report = channels.doctor(source, REPO, client, tag=TAG)
    assert report["ok"] is True
    assert report["gh_version"] == "gh version 2.104.0"
    assert report["attestation_flags_supported"] is True
    assert report["auth_ok"] is True
    assert report["workflow_scope"] is True
    assert report["git"]["clean"] is True
    assert report["git"]["prunable_worktrees"] == 1
    assert report["github_state"] == "missing"
    assert report["pypi_missing"] == ["lixity-0.3.0-py3-none-any.whl", "lixity-0.3.0.tar.gz"]


def test_doctor_desktop_signing_reports_only_required_names(channels, candidate, monkeypatch):
    source, dist = candidate
    _doctor_subprocess(channels, monkeypatch, signing_lists={
        "secret": (0, [{"name": "APPLE_NOTARY_KEY_ID"}, {"name": "OTHER_SECRET"}]),
        "variable": (0, [{"name": name, "value": "private value"} for name in channels.AZURE_FIELDS]),
    })
    client, _ = client_for(channels, dist)
    report = channels.doctor(source, REPO, client, desktop_signing=True)["desktop_signing"]
    assert report == {
        "macos": {"missing_secrets": [
            "APPLE_DEVELOPER_ID_P12_BASE64", "APPLE_DEVELOPER_ID_P12_PASSWORD",
            "APPLE_NOTARY_ISSUER_ID", "APPLE_NOTARY_KEY_P8_BASE64",
        ]},
        "windows": {
            "missing_secrets": ["AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID"],
            "missing_variables": [],
        },
    }


@pytest.mark.parametrize("secret_response", [(1, []), (0, [{}])])
def test_doctor_desktop_signing_keeps_failed_queries_unknown(channels, candidate, monkeypatch, secret_response):
    source, dist = candidate
    _doctor_subprocess(channels, monkeypatch, signing_lists={
        "secret": secret_response,
        "variable": (0, []),
    })
    client, _ = client_for(channels, dist)
    report = channels.doctor(source, REPO, client, desktop_signing=True)["desktop_signing"]
    assert report["macos"]["missing_secrets"] is None
    assert report["windows"]["missing_secrets"] is None
    assert report["windows"]["missing_variables"] == sorted(channels.AZURE_FIELDS)


def test_doctor_rejects_old_gh_and_pending_release_notes(channels, candidate, monkeypatch):
    source, dist = candidate
    notes = source / "docs/releases" / f"{TAG}.md"
    notes.parent.mkdir(parents=True)
    notes.write_text("# Lixity v0.3.0\n\n## Verification (pending)\n", encoding="utf-8")
    _doctor_subprocess(channels, monkeypatch)
    client, _ = client_for(channels, dist)
    with pytest.raises(ValueError, match="pending"):
        channels.doctor(source, REPO, client, tag=TAG)

    notes.write_text("# Lixity v0.3.0\n\nVerified.\n", encoding="utf-8")
    _doctor_subprocess(channels, monkeypatch, flags="--repo --owner")
    with pytest.raises(ValueError, match="attestation"):
        channels.doctor(source, REPO, client, tag=TAG)


def _setup_pages_stub(channels, monkeypatch, source):
    pages = {rel: f"<html><body>{rel}</body></html>".encode() for rel in channels.PAGES_VERIFY_FILES}

    class FakeStagePages:
        @staticmethod
        def stage(docs_dir, output):
            assert docs_dir == source / "docs"
            for rel, body in pages.items():
                target = output / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(body)
            return len(pages)

    monkeypatch.setattr(channels, "_stage_pages_module", lambda: FakeStagePages)
    return pages


def test_verify_pages_validates_deployment_sha_and_staged_bytes(channels, candidate, monkeypatch):
    source, _dist = candidate
    fake_git(monkeypatch, channels)
    pages = _setup_pages_stub(channels, monkeypatch, source)
    base = "https://mfahsold.github.io/lixity/"
    values = {
        base + "deployment.json": {"schema_version": 1, "source_sha": SHA, "workflow_run_url": "https://example"},
        base: pages["index.html"],
        **{base + rel: body for rel, body in pages.items()},
    }
    opener = Responses(values)
    client = channels.HttpClient(opener=opener)
    result = channels.verify_pages(source, TAG, SHA, client, base_url=base)
    assert result["state"] == "verified"
    assert result["source_sha"] == SHA
    assert result["verified_paths"] == len(channels.PAGES_VERIFY_FILES) + 2
    deployment_requests = [request for request in opener.requests
                           if request.full_url == base + "deployment.json"]
    assert len(deployment_requests) == 2
    assert all(request.get_header("Cache-control") == "no-cache" for request in deployment_requests)

    values[base + "deployment.json"] = {"schema_version": 1, "source_sha": "b" * 40}
    with pytest.raises(ValueError, match="source_sha"):
        channels.verify_pages(source, TAG, SHA, client, base_url=base)

    values[base + "deployment.json"] = {"schema_version": 1, "source_sha": SHA}
    values[base + "index-de.html"] = b"stale german bytes"
    with pytest.raises(ValueError, match=r"index-de\.html"):
        channels.verify_pages(source, TAG, SHA, client, base_url=base)

    values[base + "index-de.html"] = pages["index-de.html"]
    values[base + "guides/metrics/de.html"] = b"stale german measurement reference"
    with pytest.raises(ValueError, match=r"guides/metrics/de\.html"):
        channels.verify_pages(source, TAG, SHA, client, base_url=base)

    values[base + "guides/metrics/de.html"] = pages["guides/metrics/de.html"]
    for path in ("sitemap.xml", "assets/analytics.json", "screenshots/dashboard-light.png",
                 "videos/social-hook-9x16.mp4", "demo/report.html"):
        values[base + path] = b"stale resource"
        with pytest.raises(ValueError, match=f"resource differs from staged build: {path}"):
            channels.verify_pages(source, TAG, SHA, client, base_url=base)
        values[base + path] = pages[path]

    deployments = iter([{"schema_version": 1, "source_sha": SHA},
                        {"schema_version": 1, "source_sha": "b" * 40}])
    values[base + "deployment.json"] = lambda: next(deployments)
    with pytest.raises(ValueError, match="deployment changed"):
        channels.verify_pages(source, TAG, SHA, client, base_url=base)


def test_verify_pages_command_accepts_deployed_commit_without_release_tag(channels, candidate,
                                                                    monkeypatch, capsys):
    source, _dist = candidate
    fake_git(monkeypatch, channels)
    pages = _setup_pages_stub(channels, monkeypatch, source)
    base = channels.DEFAULT_PAGES_URL
    opener = Responses({
        base + "deployment.json": {"schema_version": 1, "source_sha": SHA},
        base: pages["index.html"],
        **{base + rel: body for rel, body in pages.items()},
    })
    client = channels.HttpClient(opener=opener)
    monkeypatch.setattr(channels, "HttpClient", lambda **kwargs: client)
    monkeypatch.setattr(sys, "argv", [
        "release_channels.py", "verify-pages", "--root", str(source), "--expected-commit", SHA,
    ])
    channels.main()
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "verified" and result["source_sha"] == SHA
    assert "tag" not in result


def test_verify_release_checks_github_pypi_bytes_and_pages_end_to_end(channels, candidate, monkeypatch):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    attestation_checks = []
    monkeypatch.setattr(channels, "verify_attestations", lambda *args: attestation_checks.append(args))
    pages = _setup_pages_stub(channels, monkeypatch, source)
    base = "https://mfahsold.github.io/lixity/"
    pypi_urls = []
    extra = {
        base + "deployment.json": {"schema_version": 1, "source_sha": SHA},
        base: pages["index.html"],
        **{base + rel: body for rel, body in pages.items()},
    }
    for name in ("lixity-0.3.0-py3-none-any.whl", "lixity-0.3.0.tar.gz"):
        body = (dist / name).read_bytes()
        url = f"https://files.pythonhosted.org/packages/test/{name}"
        pypi_urls.append({
            "filename": name,
            "url": url,
            "yanked": False,
            "digests": {"sha256": hashlib.sha256(body).hexdigest()},
        })
        extra[url] = body
    client, opener = client_for(channels, dist, pypi={"info": {"version": "0.3.0"}, "urls": pypi_urls})
    opener.values.update(extra)
    recovered = dist.parent / "verified-dist"
    result = channels.verify_release(source, TAG, SHA, REPO, recovered, client, base_url=base)
    assert result["state"] == "verified"
    assert result["channels"] == ["github", "pypi", "pages"]
    assert result["github_pypi_bytes_identical"] is True
    assert len(attestation_checks) == 1
    assert sum(request.full_url == f"https://pypi.org/pypi/lixity/{TAG[1:]}/json"
               for request in opener.requests) == 1

    corrupted_url = pypi_urls[0]["url"]
    opener.values[corrupted_url] = b"corrupted pypi bytes"
    with pytest.raises(ValueError, match=r"differ|PyPI"):
        channels.verify_release(source, TAG, SHA, REPO, recovered, client, base_url=base)

    def change_files_after_github_verification():
        replacement = b"different local and PyPI distribution"
        (recovered / pypi_urls[0]["filename"]).write_bytes(replacement)
        opener.values[corrupted_url] = replacement
        pypi_urls[0]["digests"]["sha256"] = hashlib.sha256(replacement).hexdigest()
        return {"info": {"version": TAG[1:]}, "urls": pypi_urls}

    opener.values[f"https://pypi.org/pypi/lixity/{TAG[1:]}/json"] = change_files_after_github_verification
    with pytest.raises(ValueError, match="differs from GitHub asset"):
        channels.verify_release(source, TAG, SHA, REPO, recovered, client, base_url=base)


def test_verify_release_can_omit_pypi_and_live_pages(channels, candidate, monkeypatch, capsys):
    source, dist = candidate
    fake_git(monkeypatch, channels)
    monkeypatch.setattr(channels, "verify_attestations", lambda *args: None)
    client, opener = client_for(channels, dist)
    pypi_url = f"https://pypi.org/pypi/lixity/{TAG[1:]}/json"
    del opener.values[pypi_url]
    monkeypatch.setattr(channels, "HttpClient", lambda **kwargs: client)
    monkeypatch.setattr(sys, "argv", [
        "release_channels.py", "verify-release", "--root", str(source), "--tag", TAG,
        "--expected-commit", SHA, "--repo", REPO, "--dist", str(dist), "--skip-pypi", "--skip-pages",
    ])
    channels.main()
    report = json.loads(capsys.readouterr().out)
    assert report == {"state": "verified", "tag": TAG, "source_sha": SHA, "channels": ["github"]}
    assert {request.host for request in opener.requests} == {"api.github.com"}


def zenodo_search_url(channels):
    base = f"https://github.com/{REPO}"
    query = channels.urllib.parse.urlencode({
        "q": (f'metadata.related_identifiers.identifier:("{base}" OR "{base}/tree/{TAG}" '
              f'OR "{base}/releases/tag/{TAG}") AND metadata.version:("{TAG}" OR "{TAG[1:]}")'),
        "size": 10,
        "all_versions": 1,
    })
    return f"https://zenodo.org/api/records?{query}"


def test_verify_zenodo_command_needs_no_checkout_or_other_channel(channels, monkeypatch, capsys):
    url = zenodo_search_url(channels)
    opener = Responses({url: {"hits": {"hits": []}}})
    client = channels.HttpClient(opener=opener)
    monkeypatch.setattr(channels, "HttpClient", lambda **kwargs: client)
    monkeypatch.setattr(sys, "argv", [
        "release_channels.py", "verify-zenodo", "--repo", REPO, "--tag", TAG,
    ])
    channels.main()
    assert [request.full_url for request in opener.requests] == [url]
    assert json.loads(capsys.readouterr().out) == {
        "tag": TAG, "zenodo_status": "pending", "zenodo_doi": None, "zenodo_url": None,
    }


def test_zenodo_status_classifies_minted_pending_and_unknown(channels):
    url = zenodo_search_url(channels)

    def result(*hits):
        return channels.zenodo_status(REPO, TAG, channels.HttpClient(opener=Responses({url: {"hits": {"hits": hits}}})))

    record = {
        "doi": "10.5281/zenodo.12345",
        "links": {"self_html": "https://zenodo.org/records/12345"},
        "metadata": {"version": TAG, "related_identifiers": [{"identifier": f"https://github.com/{REPO}"}]},
    }
    other_release = {**record, "metadata": {**record["metadata"], "version": "v0.8.0"}}
    other_project = {**record, "metadata": {**record["metadata"], "related_identifiers": [
        {"identifier": "https://github.com/example/different-project"},
    ]}}
    assert result(other_release, other_project, record) == {
        "zenodo_status": "minted",
        "zenodo_doi": "10.5281/zenodo.12345",
        "zenodo_url": "https://zenodo.org/records/12345",
    }
    assert result(other_release, other_project) == result() == {
        "zenodo_status": "pending",
        "zenodo_doi": None,
        "zenodo_url": None,
    }
    error = urllib.error.HTTPError(url, 503, "down", {}, io.BytesIO())
    assert result(record, {**record, "doi": "10.5281/zenodo.54321"}) == result({}) == (
        channels.zenodo_status(REPO, TAG, channels.HttpClient(opener=Responses({url: error})))
    ) == {
        "zenodo_status": "unknown",
        "zenodo_doi": None,
        "zenodo_url": None,
    }
