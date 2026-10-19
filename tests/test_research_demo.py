"""The public research example retains reviewed visuals and permits fixture reads only."""

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from lixity import __version__
from lixity.research import api

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import make_screenshots  # noqa: E402


@pytest.fixture
def research_fixture(tmp_path):
    return make_screenshots.build_research_fixture(tmp_path)


def test_visual_fixture_refuses_missing_or_changed_reviewed_assets(tmp_path):
    assets = tmp_path / "assets"
    shutil.copytree(ROOT / "docs/assets/research", assets)
    image = assets / "hamburg-free-port-1900.jpg"
    image.write_bytes(image.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="reviewed"):
        make_screenshots.reviewed_visual_sources(assets)
    image.unlink()
    with pytest.raises((OSError, ValueError)):
        make_screenshots.reviewed_visual_sources(assets)


def test_research_fixture_retains_reviewed_visuals_with_credit_and_fiction_boundaries(tmp_path, research_fixture):
    project = tmp_path / "research-demo"
    manifest = json.loads((ROOT / "docs/assets/research/sources.json").read_text())
    sources = api.list_sources(project)["sources"]
    images = [source for source in sources if source["media_type"] == "image/jpeg"]
    assert len(images) == 2
    for item in manifest["sources"]:
        image = next(source for source in images if source["title"] == item["title"])
        assert image["sha256"] == item["sha256"]
        assert image["context"]["origin_url"] == item["origin_url"]
        assert item["credit"] in image["context"]["provenance_note"]
        assert item["rights"] in image["context"]["provenance_note"]
        assert item["source_url"] in image["context"]["provenance_note"]
    dossiers = api.list_dossiers(project)["dossiers"]
    dossier = api.get_dossier(project, next(d["id"] for d in dossiers if d["title"] == "Warehouse 4 case notes"))
    assert len(dossier["images"]) == 2
    assert "not evidence of the invented 1923 incident" in dossier["body"]
    features = dossier["geography"]["features"]
    journeys = [feature for feature in features if feature["geometry"]["type"] == "LineString"]
    assert {feature["properties"]["transport"] for feature in journeys} == {"walking", "driving"}
    assert all("fictional" in feature["properties"]["label"].lower() for feature in journeys)
    for image in dossier["images"]:
        resource = research_fixture[image["url"]]
        assert resource["asset_path"].startswith("docs/assets/research/")
        assert "content_base64" not in resource
    assert api.audit(project)["ok"]


def test_public_demo_externalizes_image_bytes_and_preserves_source_records(tmp_path, research_fixture):
    target = make_screenshots.build_research_demo(tmp_path, research_fixture)
    assert target == tmp_path / "docs/demo/research.html"
    document = target.read_text()
    fixture_path = target.with_name("research-data.json")
    fixture = json.loads(fixture_path.read_text())
    assert f"Lixity {__version__} · read-only research example" in document
    assert "Hamburg free-port area, circa 1900" in document
    assert "Ships in the Harbor, Hamburg, Germany" in document
    assert "content_base64" not in fixture_path.read_text()
    assert "data:image" not in document
    assert all(url.startswith("/api/research/") for url in fixture)
    assert not any(url.startswith("/api/research/image") for url in fixture)
    dossiers = fixture["/api/research/dossiers"]["dossiers"]
    dossier_id = next(dossier["id"] for dossier in dossiers if dossier["title"] == "Warehouse 4 case notes")
    details = fixture["/api/research/dossiers?id=" + dossier_id.replace(":", "%3A")]
    assert {image["url"] for image in details["images"]} == {
        "../assets/research/hamburg-free-port-1900.jpg", "../assets/research/hamburg-harbour-1890-1900.jpg"}
    for item in json.loads((ROOT / "docs/assets/research/sources.json").read_text())["sources"]:
        assert hashlib.sha256((ROOT / "docs/assets/research" / item["filename"]).read_bytes()).hexdigest() == item["sha256"]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is needed to exercise the public read adapter")
def test_public_read_adapter_rejects_writes_external_urls_and_unknown_local_reads(tmp_path, research_fixture):
    target = make_screenshots.build_research_demo(tmp_path, research_fixture)
    adapter = re.search(r'<script id="research-demo-adapter">(.*?)</script>', target.read_text(), re.DOTALL)
    assert adapter is not None
    payload = {"adapter": adapter[1], "fixture": json.loads(target.with_name("research-data.json").read_text())}
    script = """
const assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs');
const {adapter, fixture} = JSON.parse(fs.readFileSync(0, 'utf8'));
const calls = [];
const window = {fetch: async url => {
  calls.push(String(url));
  if (String(url) !== 'https://demo.invalid/demo/research-data.json') throw Error('Unexpected native fetch');
  return new Response(JSON.stringify(fixture), {headers: {'Content-Type': 'application/json'}});
}};
vm.runInNewContext(adapter, {window, document: {baseURI: 'https://demo.invalid/demo/research.html'}, URL, Request, Response, Set});
(async () => {
  const response = await window.fetch('/api/research/sources');
  assert.equal((await response.json()).sources.length, 4);
  await assert.rejects(() => window.fetch('/api/research/sources', {method: 'POST'}), /read.only/i);
  await assert.rejects(() => window.fetch('https://example.org/api/research/sources'), /read.only/i);
  await assert.rejects(() => window.fetch('/api/project-paths'), /read.only/i);
  await assert.rejects(() => window.fetch('/api/research/unknown'), /read.only/i);
  assert.deepEqual(calls, ['https://demo.invalid/demo/research-data.json']);
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
    completed = subprocess.run([shutil.which("node"), "-e", script], input=json.dumps(payload),  # noqa: S603
                               text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
