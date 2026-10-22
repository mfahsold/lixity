// Real exported synthetic archives retain native reads on file:// and static HTTP.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const {pythonFixture} = require('./support/python-fixture.cjs');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-read-only-site-data-'));
const fixture = pythonFixture(String.raw`
import hashlib, json
from pathlib import Path
from lixity.research import api
from lixity.research.repository import Repository
from lixity.site_export import prepare_site
from tests.test_research_images import png
from tests.test_research_geography import geography
root = Path(ARTIFACTS)
project = root / 'synthetic-project'
api.init(project, title='Synthetic reading website')
manuscript = project / 'manuscript.md'
manuscript.write_text('# Synthetic website\n\n## Arrival\n\nThe eastern gate was open. I could hear the rain.\n\n## Return\n\nThe keeper returned before dawn.\n')
source = root / 'synthetic-evidence.txt'
source.write_text('The register records an open gate.\n\nUncited synthetic source paragraph.\n')
capture = api.ingest(project, source, title='Synthetic register', allow_retention=True)
passage = api.get_source(project, capture['source_id'])['passages'][0]
dossier = api.create_dossier(project, 'Synthetic gate notes', '## Register\n\nEarlier interpretation.\n\n' +
    chr(96)*3 + 'mermaid\ngraph LR\n A[Gate] --> B[Arrival]\n' + chr(96)*3 + '\n',
    evidence_ids=[passage['id']], geography=geography())['dossier_id']
claim = api.create_claim(project, title='Earlier claim title', statement='The earlier claim interpretation.', dossier_id=dossier)['claim_id']
api.link_evidence(project, claim_id=claim, passage_id=passage['id'])
api.revise_record(project, 'claim', claim, changes={'title':'Current claim title', 'statement':'The current claim interpretation.'},
    expected_revision=1, change_kind='correction', reason='Synthetic reviewed wording.')
image = api.attach_dossier_image(project, dossier, png(), filename='synthetic.png', alt='Synthetic retained pixel',
    allow_retention=True, expected_snapshot=Repository(project).snapshot().digest, expected_revision=1)
api.record_decision(project, title='Synthetic plot choice', rationale='Keep the gate open.',
    claim_id=claim, dossier_ids=[dossier])
def digest():
    return {str(p.relative_to(project)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in project.rglob('*') if p.is_file()}
before = digest()
for name, research, files in [('full', True, True), ('excerpts', True, False), ('analysis', False, False)]:
    bundle = prepare_site(project, manuscript=manuscript, include_research=research, include_source_files=files)
    destination = root / name
    for name, content in bundle.files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
assert digest() == before
print(json.dumps({'claim':claim, 'dossier':dossier, 'source':capture['source_id'],
    'project':str(project), 'before':before}))
`.replace('ARTIFACTS', JSON.stringify(artifacts)));

function projectBytes() {
  const result = {};
  function visit(dir) {
    for (const item of fs.readdirSync(dir, {withFileTypes:true})) {
      const file = path.join(dir, item.name);
      if (item.isDirectory()) visit(file);
      else result[path.relative(fixture.project, file).split(path.sep).join('/')] = require('node:crypto').createHash('sha256').update(fs.readFileSync(file)).digest('hex');
    }
  }
  visit(fixture.project); return result;
}

(async () => {
  const serverReads = [];
  const server = http.createServer((request, response) => {
    serverReads.push(request.url);
    const name = decodeURIComponent(new URL(request.url, 'http://local').pathname).replace(/^\/nested\//, '');
    const file = path.resolve(artifacts, name);
    if (!file.startsWith(artifacts + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
      response.writeHead(404); response.end(); return;
    }
    response.setHeader('Content-Type', file.endsWith('.html') ? 'text/html; charset=utf-8' : file.endsWith('.png') ? 'image/png' : 'application/octet-stream');
    response.end(fs.readFileSync(file));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await launchChromium();
  const errors = [], requests = [];
  try {
    for (const scheme of ['file', 'http']) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 1000}, reducedMotion: 'reduce'});
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => { if (['warning', 'error'].includes(message.type())) errors.push(message.text()); });
      page.on('request', request => requests.push(request.url()));
      const url = scheme === 'file' ? pathToFileURL(path.join(artifacts, 'full/index.html')).href : origin + '/nested/full/index.html';
      await page.goto(url);
      await page.locator('#tab-view-research').click();
      const dossier = page.locator('#research-dossiers-list .research-card').filter({hasText: 'Synthetic gate notes'});
      await expect(dossier).toBeVisible();
      assert.ok(!(await page.locator('#r-active-root').getAttribute('class')).includes('loading'));
      await dossier.locator('[data-research-detail="dossier"]').click();
      const image = dossier.locator('img[alt="Synthetic retained pixel"]');
      await expect(image).toBeVisible();
      await expect(image).toHaveJSProperty('naturalWidth', 1);
      assert.match(await image.getAttribute('src'), /^assets\//);
      await image.click();
      await expect(page.locator('#modal-dossier-image-enlarge')).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(dossier.locator('.research-diagram-canvas svg')).toBeVisible();
      await dossier.locator('[data-diagram-enlarge]').click();
      await expect(page.locator('#modal-dossier-image-enlarge')).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(dossier.locator('[data-geo-basemap]')).toBeHidden();
      await dossier.locator('[data-geo-map]').scrollIntoViewIfNeeded();
      await expect(dossier.locator('.geography-map')).toBeVisible();
      await page.locator('#research-tab-claims').click();
      const claim = page.locator('#research-claims-list .research-card').filter({hasText:'Current claim title'});
      await expect(claim).toBeVisible();
      assert.equal(await claim.locator('[data-research-revise]').count(), 0);
      await claim.locator('[data-research-history="claim"]').click();
      const dialog = page.locator('#modal-research-revision');
      await expect(dialog.locator('#research-revision-history-detail')).toContainText('The current claim interpretation.');
      await expect(dialog.locator('#research-revision-edit-tab')).toBeHidden();
      await dialog.locator('#research-revision-history-tab').focus();
      await page.keyboard.press('End');
      await expect(dialog.locator('#research-revision-history-tab')).toBeFocused();
      await dialog.locator('#research-revision-versions > summary').click();
      await expect(dialog.locator('[data-research-revision="1"]')).toBeVisible();
      await dialog.locator('[data-research-revision="1"]').click();
      await expect(dialog.locator('#research-revision-history-detail')).toContainText('The earlier claim interpretation.');
      await page.keyboard.press('Escape');
      await page.locator('#research-tab-review').click();
      await expect(page.locator('#research-editorial-review')).toContainText('Synthetic plot choice');
      assert.equal(await page.locator('[data-decision-ack-status]').count(), 0);
      await page.locator('#research-tab-sources').click();
      const source = page.locator('#research-sources-list .research-card').filter({hasText:'Synthetic register'});
      await source.locator('[data-research-detail="source"]').click();
      await expect(source.locator('.research-source-doc-rendered')).toContainText('Uncited synthetic source paragraph.');
      await expect(source.locator('[data-site-original-source]')).toHaveAttribute('href', /^assets\/sources\//);
      assert.equal(await source.locator('.selection-toolbar').count(), 0);
      await page.locator('#tab-view-analysis').click();
      await page.locator('#workspace-reader-toggle').click();
      await expect(page.locator('#workspace-reader-panel')).toBeVisible();
      await expect(page.locator('#workspace-reader-dossier')).toContainText('Synthetic gate notes');
      await page.locator('#workspace-reader-dossier').selectOption(fixture.dossier);
      await expect(page.locator('#workspace-reader-body')).toContainText('Earlier interpretation.');
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      await page.screenshot({path:path.join(artifacts, `snapshot-${scheme}-${width}.png`)});
      await page.goto(scheme === 'file' ? pathToFileURL(path.join(artifacts, 'analysis/index.html')).href : origin + '/nested/analysis/index.html');
      await expect(page.locator('#tab-view-research')).toBeHidden();
      await expect(page.locator('#view-pane-analysis')).toBeVisible();
      await page.locator('#text-search').fill('keeper');
      await page.locator('#text-search').press('Enter');
      await expect(page.locator('#chapters mark.text-hit')).toHaveCount(1);
      await page.locator('#reader-chapter').selectOption('ch-2');
      await expect(page.locator('#ch-2')).toBeInViewport();
      await page.goto(scheme === 'file' ? pathToFileURL(path.join(artifacts, 'excerpts/index.html')).href : origin + '/nested/excerpts/index.html');
      await page.locator('#tab-view-research').click();
      await page.locator('#research-tab-sources').click();
      const excerpt = page.locator('#research-sources-list .research-card').filter({hasText:'Synthetic register'});
      await excerpt.locator('[data-research-detail="source"]').click();
      await expect(excerpt.locator('.site-source-excerpts')).toBeVisible();
      await expect(excerpt.locator('.research-source-doc-rendered')).toContainText('The register records an open gate.');
      await expect(excerpt.locator('.research-source-doc-rendered')).not.toContainText('Uncited synthetic');
      assert.equal(await excerpt.locator('[data-site-original-source]').count(), 0);
      await page.close();
    }
    assert.deepEqual(errors, []);
    assert.ok(!requests.some(url => /\/api\/|openstreetmap|https:\/\//.test(url)), requests.join('\n'));
    assert.ok(!serverReads.some(url => url.startsWith('/api/')));
    assert.deepEqual(projectBytes(), fixture.before);
    console.log('Real snapshot file/HTTP native reads and identity passed:', artifacts);
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => {console.error(error); process.exitCode = 1;});
