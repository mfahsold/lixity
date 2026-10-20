"""The public research example retains reviewed visuals and permits fixture reads only."""

import base64
import hashlib
import html
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


def test_research_fixture_connects_retained_evidence_to_an_authored_claim_and_manuscript(tmp_path, research_fixture):
    project = tmp_path / "research-demo"
    links = research_fixture["/api/research/manuscript-links"]
    assert len(links["links"]) == 1
    link = links["links"][0]
    assert link["anchor"]["source_path"] == "harbour-manuscript.md"
    assert link["anchor"]["quote"] == "Someone had tried the eastern gate of Warehouse 4."
    assert link["claim_title"] == "Attempted warehouse entry"
    assert link["claim_revision"] == 1
    assert link["state"] == "active"
    manuscript_bytes = (ROOT / "samples/first-look.md").read_bytes()
    assert (project / "harbour-manuscript.md").read_bytes() == manuscript_bytes
    assert api.list_manuscript_links(project) == {key: value for key, value in links.items() if key != "ok"}
    evidence = api.list_evidence_links(project, claim_id=link["claim_id"])["evidence_links"]
    assert len(evidence) == 1
    assert evidence[0]["relation"] == "supports"
    source = next(source for source in api.list_sources(project)["sources"]
                  if source["title"] == "Port Authority Customs Log (synthetic)")
    assert source["context"]["external_reference"]["server_id"] == "synthetic-offline-example"
    assert "No live Zotero connection" in source["context"]["provenance_note"]
    assert all(source["title"] != "harbour-manuscript.md" for source in api.list_sources(project)["sources"])
    review = research_fixture["/api/research/manuscript-review?project_token=synthetic-harbour-manuscript"]
    assert review["links"][0]["anchor_state"] == "resolved"
    assert review["review_needed_count"] == 0
    assert review["current_source_sha256"] == hashlib.sha256((project / "harbour-manuscript.md").read_bytes()).hexdigest()
    assert api.audit(project)["ok"]


def test_public_demo_externalizes_image_bytes_and_preserves_source_records(tmp_path, research_fixture):
    target = make_screenshots.build_research_demo(tmp_path, research_fixture)
    assert target == tmp_path / "docs/demo/report.html"
    document = target.read_text()
    fixture_path = target.with_name("research-data.json")
    fixture = json.loads(fixture_path.read_text())
    assert '<span class="product-name">Lixity · read-only</span>' in document
    assert re.search(r'<p class="project-meta">[^<]*Fictional demo</p>', document)
    provenance = re.search(
        r'<details\b(?P<attributes>[^>]*\bid="example-context"[^>]*)>(?P<body>.*?)</details>',
        document, re.DOTALL,
    )
    assert provenance is not None
    assert not re.search(r'(?:^|\s)open(?:\s|=|$)', provenance["attributes"])
    assert '<summary id="example-heading">About this read-only demo</summary>' in provenance["body"]
    assert f"Generated with Lixity {__version__}." in provenance["body"]
    assert "cannot import, edit or save" in provenance["body"]
    assert "fictional demonstration records" in provenance["body"]
    assert "Hamburg free-port area, circa 1900" in document
    assert "Ships in the Harbor, Hamburg, Germany" in document
    assert "Zotero normally owns bibliography, reading and source notes" in document
    assert "no live Zotero connection" in document
    assert "saved manuscript quote" in document
    assert len(re.findall(r'<section class="chapter(?: [^\"]*)?" id="ch-\d+"', document)) == 6
    assert 'data-manuscript-links="read"' in document
    source = (ROOT / "samples/first-look.md").read_bytes()
    assert f'data-manuscript-source-sha256="{hashlib.sha256(source).hexdigest()}"' in document
    assert (tmp_path / "docs/research/examples/harbour-manuscript.md").read_bytes() == source
    assert (ROOT / "LICENSE").read_text().strip() in html.unescape(document)
    for layout in ("editor", "book", "sheet", "report"):
        filename = f"warehouse-4-{layout}.pdf"
        assert f'href="{filename}"' in document
        assert target.with_name(filename).read_bytes().startswith(b"%PDF-")
    legacy = target.with_name("research.html").read_text()
    assert 'http-equiv="refresh" content="0; url=report.html#research-manager"' in legacy
    assert 'href="report.html#research-manager"' in legacy
    assert 'rel="canonical" href="https://mfahsold.github.io/lixity/demo/report.html"' in legacy
    assert "research-demo-adapter" not in legacy
    assert "content_base64" not in fixture_path.read_text()
    assert "Mara stopped beneath the quay lamp" not in fixture_path.read_text()
    assert all(url.startswith("/api/research/") for url in fixture)
    assert not any(url.startswith("/api/research/image") for url in fixture)
    dossiers = fixture["/api/research/dossiers"]["dossiers"]
    dossier_id = next(dossier["id"] for dossier in dossiers if dossier["title"] == "Warehouse 4 case notes")
    details = fixture["/api/research/dossiers?id=" + dossier_id.replace(":", "%3A")]
    assert {image["url"] for image in details["images"]} == {
        "../assets/research/hamburg-free-port-1900.jpg", "../assets/research/hamburg-harbour-1890-1900.jpg"}
    for item in json.loads((ROOT / "docs/assets/research/sources.json").read_text())["sources"]:
        source_bytes = (ROOT / "docs/assets/research" / item["filename"]).read_bytes()
        assert base64.b64encode(source_bytes).decode("ascii") not in document
        assert hashlib.sha256(source_bytes).hexdigest() == item["sha256"]


def test_demo_read_fixtures_match_native_companion_and_matrix(tmp_path, research_fixture):
    project = tmp_path / "research-demo"
    reader = "/api/research/dossiers?project_token=synthetic-harbour-manuscript"
    assert research_fixture[reader] == {"ok": True, **api.list_dossiers(project)}
    for dossier in api.list_dossiers(project)["dossiers"]:
        endpoint = reader + "&id=" + dossier["id"].replace(":", "%3A")
        assert research_fixture[endpoint] == {"ok": True, **api.get_dossier(project, dossier["id"])}
        assert research_fixture[endpoint + "&research_token=synthetic-research-example"] == research_fixture[endpoint]
    matrix = api.render_claim_matrix(api.claim_matrix_data(project), format="md")
    assert research_fixture["/api/research/matrix?format=md"] == {"text": matrix}


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
const preparedFiles = ['https://demo.invalid/demo/warehouse-4-editor.pdf',
  'https://demo.invalid/demo/warehouse-4-book.pdf', 'https://demo.invalid/demo/warehouse-4-sheet.pdf',
  'https://demo.invalid/demo/warehouse-4-report.pdf'];
const window = {fetch: async url => {
  calls.push(String(url));
  if (preparedFiles.includes(String(url))) {
    return new Response('%PDF-synthetic-transport-check', {headers: {'Content-Type': 'application/pdf'}});
  }
  if (String(url) !== 'https://demo.invalid/demo/research-data.json') throw Error('Unexpected native fetch');
  return new Response(JSON.stringify(fixture), {headers: {'Content-Type': 'application/json'}});
}};
vm.runInNewContext(adapter, {window, document: {baseURI: 'https://demo.invalid/demo/research.html'}, URL, Request, Response, Set});
(async () => {
  const response = await window.fetch('/api/research/sources');
  assert.equal((await response.json()).sources.length, 4);
  const links = await (await window.fetch('/api/research/manuscript-links')).json();
  assert.equal(links.links.length, 1);
  const review = await (await window.fetch('/api/research/manuscript-review?project_token=synthetic-harbour-manuscript&research_token=synthetic-research-example')).json();
  assert.equal(review.links[0].anchor.quote, 'Someone had tried the eastern gate of Warehouse 4.');
  const reader = await (await window.fetch('/api/research/dossiers?project_token=synthetic-harbour-manuscript&research_token=synthetic-research-example')).json();
  assert.equal(reader.dossiers.length, 2);
  const matrix = await window.fetch('/api/research/matrix?format=md&research_token=synthetic-research-example');
  assert.ok(matrix.headers.get('Content-Type').startsWith('text/markdown'));
  assert.match(await matrix.text(), /Attempted warehouse entry/);
  for (const layout of ['editor', 'book', 'sheet', 'report']) {
    const prepared = await window.fetch('/api/manuscript-pdf', {method: 'POST', body: JSON.stringify({
      layout, project_token: 'synthetic-harbour-manuscript'})});
    assert.equal(prepared.headers.get('Content-Type'), 'application/pdf');
    assert.equal(await prepared.text(), '%PDF-synthetic-transport-check');
  }
  for (const body of [{layout: '../secret', project_token: 'synthetic-harbour-manuscript'},
    {layout: 'book', project_token: 'another-project'},
    {layout: 'book', project_token: 'synthetic-harbour-manuscript', manuscript: 'private bytes'}]) {
    await assert.rejects(() => window.fetch('/api/manuscript-pdf', {method: 'POST', body: JSON.stringify(body)}), /read.only/i);
  }
  await assert.rejects(() => window.fetch('/api/research/sources', {method: 'POST'}), /read.only/i);
  await assert.rejects(() => window.fetch('/api/research-manuscript-link', {method: 'POST'}), /read.only/i);
  await assert.rejects(() => window.fetch('zotero://select/library/items/DEMOLOG1'), /read.only/i);
  await assert.rejects(() => window.fetch('https://example.org/api/research/sources'), /read.only/i);
  await assert.rejects(() => window.fetch('/api/project-paths'), /read.only/i);
  await assert.rejects(() => window.fetch('/api/research/unknown'), /read.only/i);
  await assert.rejects(() => window.fetch('/api/research/manuscript-links?research_token=unrecognized'), /read.only/i);
  await assert.rejects(() => window.fetch('/api/research/dossiers?project_token=unrecognized&research_token=synthetic-research-example'), /read.only/i);
  assert.deepEqual(calls, ['https://demo.invalid/demo/research-data.json', ...preparedFiles]);
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
    completed = subprocess.run([shutil.which("node"), "-e", script], input=json.dumps(payload),  # noqa: S603
                               text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
