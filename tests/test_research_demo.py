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
from urllib.parse import quote, urlencode

import pytest

from lixity import __version__
from lixity.research import api

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import make_screenshots  # noqa: E402


def site_data(document):
    match = re.search(r'<script[^>]*id="lixity-site-data"[^>]*>(.*?)</script>', document, re.DOTALL)
    assert match, "The demo must use the production website's frozen read provider"
    return json.loads(match[1])


@pytest.fixture
def research_fixture(tmp_path):
    return make_screenshots.build_research_fixture(tmp_path)


@pytest.fixture
def public_demo(tmp_path, research_fixture, monkeypatch):
    """Exercise demo publication without requiring native PDF fonts.

    PDF composition is covered by the font-guarded pipeline/export suites. These
    synthetic attachments expose the exact inputs passed through the generator.
    """
    from lixity import pdf_export, pdf_layouts

    monkeypatch.setattr(pdf_layouts, "_installed_fonts", dict)
    for role in ("TEXT", "HEADING", "MONO", "SANS", "SANS_BOLD", "ITALIC", "BOLD_ITALIC"):
        monkeypatch.delenv("LIXITY_PDF_FONT_" + role, raising=False)

    def synthetic_pdf(text, **options):
        return b"%PDF-synthetic-demo\n" + json.dumps({"text": text, **options}).encode("utf-8")

    monkeypatch.setattr(pdf_export, "compose_pdf", synthetic_pdf)
    project = tmp_path / "research-demo"
    before = {path.relative_to(project): path.read_bytes() for path in project.rglob("*") if path.is_file()}
    target = make_screenshots.build_research_demo(tmp_path, project)
    assert {path.relative_to(project): path.read_bytes() for path in project.rglob("*") if path.is_file()} == before
    return target


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
    manifest = json.loads((ROOT / "docs/assets/research/sources.json").read_text(encoding="utf-8"))
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
    assert len(links["links"]) == 5
    link = next(item for item in links["links"] if item["anchor"]["quote"] ==
                "Someone had tried the eastern gate of Warehouse 4.")
    assert link["anchor"]["source_path"] == "harbour-manuscript.md"
    assert link["anchor"]["quote"] == "Someone had tried the eastern gate of Warehouse 4."
    assert link["claim_title"] == "Attempted warehouse entry"
    assert link["claim_revision"] == 1
    assert link["state"] == "active"
    manuscript_bytes = (ROOT / "samples/first-look.md").read_bytes()
    assert (project / "harbour-manuscript.md").read_bytes() == manuscript_bytes
    assert api.list_manuscript_links(project) == {key: value for key, value in links.items() if key != "ok"}
    evidence = api.list_evidence_links(project, claim_id=link["claim_id"])["evidence_links"]
    assert {item["relation"] for item in evidence} == {"supports", "qualifies"}
    source = next(source for source in api.list_sources(project)["sources"]
                  if source["title"] == "Port Authority Customs Log (synthetic)")
    assert source["context"]["external_reference"]["server_id"] == "synthetic-offline-example"
    assert "No live Zotero connection" in source["context"]["provenance_note"]
    assert all(source["title"] != "harbour-manuscript.md" for source in api.list_sources(project)["sources"])
    review = research_fixture["/api/research/manuscript-review?project_token=synthetic-harbour-manuscript"]
    assert all(item["anchor_state"] == "resolved" for item in review["links"])
    assert review["review_needed_count"] == 2
    assert all(item["flags"] == ["claim_changed"] for item in review["links"]
               if item["review_needed"])
    assert review["current_source_sha256"] == hashlib.sha256((project / "harbour-manuscript.md").read_bytes()).hexdigest()
    assert api.audit(project)["ok"]


def test_demo_records_source_disagreement_and_preserves_the_earlier_interpretation(tmp_path, research_fixture):
    project = tmp_path / "research-demo"
    claims = api.list_claims(project)["claims"]
    assert len(claims) == 6
    inspection = next(item for item in claims if item["title"] == "Where the crate was opened")
    before = api.get_record(project, "claim", inspection["id"], revision=1)
    current = api.get_record(project, "claim", inspection["id"])
    assert "opened the crate on the quay" in before["record"]["statement"]
    assert "customs station" in current["record"]["statement"]
    assert current["record"]["revision"] == 2
    evidence = api.list_evidence_links(project, claim_id=inspection["id"])["evidence_links"]
    assert {(item["claim_revision"], item["relation"]) for item in evidence} == {
        (1, "supports"), (1, "contradicts"), (2, "supports")}
    quoted = {item["relation"]: item["citation"]["verbatim"] for item in evidence if item["claim_revision"] == 1}
    assert "opened the crate beside the gate" in quoted["supports"]
    assert "crate was first opened at the customs station" in quoted["contradicts"]
    assert len(current["citations"]) == 1
    assert "first opened at the customs station" in current["citations"][0]["verbatim"]
    relations = api.list_claim_relations(project)["relations"]
    assert len(relations) == 1
    assert relations[0]["to_claim"]["claim_id"] == inspection["id"]
    assert relations[0]["to_claim"]["revision"] == 2
    assert not relations[0]["review_needed"]
    assert api.audit(project)["ok"]


def test_demo_serializes_every_rendered_record_kind_and_exact_version(tmp_path, research_fixture):
    project = tmp_path / "research-demo"
    groups = {
        "dossier": api.list_dossiers(project)["dossiers"],
        "claim": api.list_claims(project)["claims"],
        "decision": api.list_decisions(project)["decisions"],
        "evidence_link": api.list_evidence_links(project)["evidence_links"],
        "claim_relation": api.list_claim_relations(project)["relations"],
    }
    for kind, records in groups.items():
        assert records, kind
        for record in records:
            identifier = record["relation_id"] if kind == "claim_relation" else record["id"]
            endpoint = "?kind=" + kind + "&id=" + quote(identifier, safe="")
            assert research_fixture["/api/research/record" + endpoint] == {
                "ok": True, **api.get_record(project, kind, identifier)}
            history = api.record_history(project, kind, identifier)
            assert research_fixture["/api/research/history" + endpoint] == {"ok": True, **history}
            for version in history["revisions"]:
                key = "/api/research/record" + endpoint + "&revision=" + str(version["revision"])
                expected = {"ok": True, **api.get_record(project, kind, identifier, revision=version["revision"])}
                assert research_fixture[key] == expected
                assert research_fixture[key + "&research_token=synthetic-research-example"] == expected
            if kind in ("claim", "dossier"):
                context = urlencode({"project_token": "synthetic-harbour-manuscript", "id": identifier, "kind": kind})
                assert research_fixture["/api/research/record?" + context] == {
                    "ok": True, **api.get_record(project, kind, identifier)}


def test_public_demo_externalizes_image_bytes_and_preserves_source_records(tmp_path, public_demo):
    target = public_demo
    assert target == tmp_path / "docs/demo/report.html"
    document = target.read_text(encoding="utf-8")
    data = site_data(document)
    fixture = data["responses"]
    assert 'data-read-only="true"' in document
    assert "research-demo-adapter" not in document
    assert "research-demo-controls" not in document
    assert not target.with_name("research-data.json").exists()
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
    assert "exact manuscript quotations" in document
    assert "All PDFs use the same fictional manuscript" in document
    assert len(re.findall(r'<section class="chapter(?: [^\"]*)?" id="ch-\d+"', document)) == 6
    assert 'data-manuscript-links="read"' in document
    source = (ROOT / "samples/first-look.md").read_bytes()
    assert f'data-manuscript-source-sha256="{hashlib.sha256(source).hexdigest()}"' in document
    assert (tmp_path / "docs/research/examples/harbour-manuscript.md").read_bytes() == source
    assert (ROOT / "LICENSE").read_text(encoding="utf-8").strip() in html.unescape(document)
    for layout in ("editor", "book", "sheet", "report", "document"):
        filename = f"warehouse-4-{layout}.pdf"
        assert f'href="{filename}"' in document
        attachment = target.with_name(filename).read_bytes()
        assert attachment.startswith(b"%PDF-synthetic-demo\n")
        assert json.loads(attachment.split(b"\n", 1)[1]) == {
            "text": source.decode("utf-8"), "manuscript": "harbour-manuscript.md",
            "layout": layout, "language": "en", "title": "The Crate at Warehouse 4",
            "author": "Example Author", "project_config": {},
        }
    legacy = target.with_name("research.html").read_text(encoding="utf-8")
    assert 'http-equiv="refresh" content="0; url=report.html#research-manager"' in legacy
    assert 'href="report.html#research-manager"' in legacy
    assert 'rel="canonical" href="https://mfahsold.github.io/lixity/demo/report.html"' in legacy
    assert "research-demo-adapter" not in legacy
    assert "content_base64" not in json.dumps(data)
    assert all(url.startswith("/api/research/") for url in fixture)
    assert not any(url.startswith("/api/research/image") for url in fixture)
    dossiers = fixture["/api/research/dossiers"]["dossiers"]
    dossier_id = next(dossier["id"] for dossier in dossiers if dossier["title"] == "Warehouse 4 case notes")
    details = fixture["/api/research/dossiers?id=" + dossier_id.replace(":", "%3A")]
    assert len(details["images"]) == 2
    assert all(data["resources"][image["url"]].startswith("assets/sources/") for image in details["images"])
    for item in json.loads((ROOT / "docs/assets/research/sources.json").read_text(encoding="utf-8"))["sources"]:
        source_bytes = (ROOT / "docs/assets/research" / item["filename"]).read_bytes()
        assert base64.b64encode(source_bytes).decode("ascii") not in document
        assert hashlib.sha256(source_bytes).hexdigest() == item["sha256"]


def test_public_demo_manifest_covers_the_wrapped_production_site(tmp_path, public_demo):
    directory = public_demo.parent
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "lixity-read-only-site/1"
    assert manifest["entrypoint"] == "report.html"
    assert manifest["capabilities"]["research"] is True
    assert manifest["capabilities"]["source_files"] is True
    assert manifest["capabilities"]["automatic_external_requests"] is False
    document = public_demo.read_text(encoding="utf-8")
    assert document.count('http-equiv="Content-Security-Policy"') == 1
    assert 'data-site-code="null"' in document
    assert "external_reference" not in json.dumps(site_data(document))
    for name, item in manifest["files"].items():
        content = (directory / name).read_bytes()
        assert item == {"sha256": hashlib.sha256(content).hexdigest(), "byte_length": len(content)}
    assert "report.html" in manifest["files"]
    assert "index.html" not in manifest["files"]
    assert all(f"warehouse-4-{layout}.pdf" in manifest["files"] for layout in ("editor", "book", "sheet", "report", "document"))


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


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is needed to exercise the production read provider")
def test_public_demo_uses_production_transport_without_pdf_write_exceptions(public_demo):
    document = public_demo.read_text(encoding="utf-8")
    runtime = (ROOT / "src/lixity/ui/assets/read-only-site.js").read_text(encoding="utf-8")
    payload = {"runtime": runtime, "data": site_data(document)}
    script = """
const assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs');
const {runtime, data} = JSON.parse(fs.readFileSync(0, 'utf8'));
const calls = [];
const window = {fetch: async input => {calls.push(String(input)); return new Response('prepared resource');}};
const document = {baseURI: 'https://demo.invalid/demo/report.html', body: {dataset: {readOnly: 'true'}},
  getElementById(id) {assert.equal(id, 'lixity-site-data'); return {textContent: JSON.stringify(data)};}};
vm.runInNewContext(runtime, {window, document, URL, Request, Response, Map, Set});
(async () => {
  const sources = await (await window.fetch('/api/research/sources')).json();
  assert.equal(sources.sources.length, 4);
  const links = await (await window.fetch('/api/research/manuscript-links')).json();
  assert.equal(links.links.length, 5);
  const reviewKey = Object.keys(data.responses).find(key => key.startsWith('/api/research/manuscript-review?'));
  const review = await (await window.fetch(reviewKey)).json();
  assert.ok(review.links.some(link => link.anchor.quote === 'Someone had tried the eastern gate of Warehouse 4.'));
  const matrixKey = Object.keys(data.responses).find(key => key.startsWith('/api/research/matrix?') && key.includes('format=md'));
  const matrix = await window.fetch(matrixKey);
  assert.ok(matrix.headers.get('Content-Type').startsWith('text/markdown'));
  assert.match(await matrix.text(), /Attempted warehouse entry/);
  assert.deepEqual(calls, [], 'Reading prepared research never falls back to the network');
  for (const method of ['POST', 'PUT', 'PATCH', 'DELETE']) {
    for (const route of ['/api/manuscript-pdf', '/api/research-dossier', '/api/research-manuscript-link']) {
      await assert.rejects(() => window.fetch(route, {method, body: '{}'}), /read.only/i);
    }
  }
  for (const route of ['/api/project-paths', '/api/research/unknown',
    '/api/research/sources?research_token=unrecognized', 'https://example.org/api/research/sources',
    'zotero://select/library/items/DEMOLOG1']) {
    await assert.rejects(() => window.fetch(route), /not included/i);
  }
  assert.deepEqual(calls, []);
  const image = Object.entries(data.resources).find(([, path]) => path.endsWith('.jpg'));
  assert.ok(image, 'The production export includes the reviewed image resource');
  assert.equal(window.LixitySite.resourceUrl(image[0]), image[1]);
  assert.equal(await (await window.fetch(image[0])).text(), 'prepared resource');
  assert.deepEqual(calls, [new URL(image[1], document.baseURI).href]);
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
    completed = subprocess.run([shutil.which("node"), "-e", script], input=json.dumps(payload),  # noqa: S603
                               text=True, encoding="utf-8", capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr


@pytest.fixture
def public_publications(tmp_path, research_fixture):
    builder = getattr(make_screenshots, 'build_publication_examples', None)
    assert callable(builder), 'The public reader and companion examples are missing'
    return builder(tmp_path, tmp_path / 'research-demo')


def test_public_reader_and_companion_use_the_production_scope_and_assets(tmp_path, public_publications):
    from lixity.site_export import prepare_site
    from lixity.ui.dashboard import _CSS_FILES, _JS_FILES

    project = tmp_path / 'research-demo'
    for mode, target in public_publications.items():
        page = target.read_text()
        cap = 3 if mode == 'companion' else None
        native = prepare_site(project, manuscript='harbour-manuscript.md', mode=mode,
            publication_profile='readers', max_chapter=cap, include_source_files=True)
        assert site_data(page) == site_data(native.files['index.html'].decode())
        assert 'src="../assets/analytics.js"' not in page
        assert 'src="../../assets/analytics.js"' not in page
        assert f'rel="canonical" href="https://mfahsold.github.io/lixity/demo/{mode}/index.html"' in page
        assert 'href="../report.html"' in page
        assert 'href="../../guides/first-look.html"' in page
        assert 'href="../../assets/research/sources.json"' in page
        assert site_data(page)['responses'] == {}
        for asset in (*_CSS_FILES, *_JS_FILES):
            assert page.count((ROOT / 'src/lixity/ui/assets' / asset).read_text().strip()) == 1, asset
        manifest = json.loads(target.with_name('manifest.json').read_text())
        assert manifest['mode'] == mode
        assert manifest['capabilities']['automatic_external_requests'] is False
        assert manifest['capabilities']['analysis'] is False
        assert manifest['research']['included'] is False
        for name, item in manifest['files'].items():
            content = (target.parent / name).read_bytes()
            assert item == {'sha256': hashlib.sha256(content).hexdigest(), 'byte_length': len(content)}


def test_public_companion_contains_no_novel_and_actual_cap_omits_late_content(tmp_path, public_publications):
    from lixity.site_export import prepare_site

    companion = public_publications['companion'].read_text()
    source = (ROOT / 'samples/first-look.md').read_text()
    data = site_data(companion)['publication']
    assert data['max_chapter'] == 3
    assert data['chapters'] == [{'number': 1}, {'number': 2}, {'number': 3}]
    for paragraph in (part.strip() for part in source.split('\n\n') if len(part.strip()) > 60):
        assert paragraph not in companion
    assert 'The receiving signature' not in companion
    assert 'A blank signature is an absence, not a name.' not in companion
    assert 'No receiving signature had yet been identified' not in companion
    capped = prepare_site(tmp_path / 'research-demo', manuscript='harbour-manuscript.md',
        mode='reader', publication_profile='readers', max_chapter=3, include_source_files=True)
    public = b'\n'.join(capped.files.values())
    assert b'Someone had tried the eastern gate of Warehouse 4.' in public
    assert b'The Customs Note' not in public
    assert b'A blank signature is an absence, not a name.' not in public
    assert b'No receiving signature had yet been identified' not in public


def test_pages_stages_only_two_approved_publication_manifest_inventories(tmp_path, public_publications):
    from scripts.stage_pages import stage

    docs = tmp_path / 'docs'
    unapproved = ('demo/reader/local-notes.txt', 'demo/companion/extra.html',
                  'demo/other/index.html', 'demo/other/manifest.json')
    for name in unapproved:
        path = docs / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('UNREVIEWED_LOCAL_MATERIAL')
    destination = tmp_path / 'published'
    stage(docs, destination)
    expected = set()
    for mode, target in public_publications.items():
        manifest = json.loads(target.with_name('manifest.json').read_text())
        expected.update('demo/' + mode + '/' + name for name in [*manifest['files'], 'manifest.json'])
    actual = {path.relative_to(destination).as_posix() for path in (destination / 'demo').rglob('*') if path.is_file()}
    assert actual == expected
    assert not any((destination / name).exists() for name in unapproved)
    public_publications['reader'].write_text('Changed after review')
    with pytest.raises(ValueError, match=r'changed|checksum'):
        stage(docs, tmp_path / 'changed-output')
