// Synthetic native chronology, authored causality and keyword citation workflows.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {createInterface} = require('node:readline');
const {once} = require('node:events');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-chronology-'));

(async () => {
  const server = spawn(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-u', '-c', `
import html, json, re, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
from lixity.ui import render_dashboard
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
base = Path(sys.argv[1]); project = base / 'project'
api.init(project, title='Synthetic chronology project')
claims = []
for title, period in [('Duplicate title', '1900'), ('Duplicate title', '1880'), ('Approximate', 'circa 1925'), ('No date', None), ('Invalid', '2024-02-30'), ('Duplicate title', '1900')]:
    claims.append(api.create_claim(project, title=title, statement='Synthetic claim <img src=x onerror=window.chronologyInjected=true>', time_period=period)['claim_id'])
source = base / 'source.txt'; source.write_text('The synthetic reading room opened in 1880. A second sentence supplies full context.\\n\\nThe garden stayed quiet.', encoding='utf-8')
capture = api.ingest(project, source, allow_retention=True)
passage = api.get_source(project, capture['source_id'])['passages'][0]['id']
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.research_dir = str(project)
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.refresh()
match = re.search(r'id="research-manager"[^>]*data-research-token="([^"]*)"', LixityServerHandler.dashboard_html)
token = html.unescape(match.group(1)) if match else ''
fixtures = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    fixtures[locale] = render_dashboard([], [], controls=True, labels=labels, language_key=locale, research_context_token=token)
(base / 'fixtures.json').write_text(json.dumps(fixtures), encoding='utf-8')
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'claims': claims, 'passage': passage, 'version': capture['source_version_id']}), flush=True)
server.serve_forever()
`, artifacts], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, stdio: ['ignore', 'pipe', 'pipe']});
  const lines = createInterface({input: server.stdout});
  let browser, stderr = '';
  server.stderr.on('data', data => {stderr = (stderr + data).slice(-5000);});
  try {
    const fixture = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Synthetic server startup timed out: ' + stderr)), 15000);
      lines.once('line', line => {clearTimeout(timer); resolve(JSON.parse(line));});
      server.once('error', reject);
    });
    const fixtures = JSON.parse(fs.readFileSync(path.join(artifacts, 'fixtures.json'), 'utf8'));
    browser = await launchChromium();
    for (const [locale, html] of Object.entries(fixtures)) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 950}});
      page.setDefaultTimeout(10000);
      const errors = [], writes = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => {
        if (request.method() === 'POST' && !request.url().endsWith('/api/research-search')) writes.push(request.postDataJSON());
      });
      await page.route(fixture.url + '/', route => route.fulfill({contentType: 'text/html', body: html}));
      await page.goto(fixture.url);
      await page.locator('[data-rtab=claims]').click();
      await page.locator('#r-open-timeline').click();
      assert.equal(await page.locator('#rtab-timeline').isVisible(), true, 'The claims entry opens the more prominent timeline tab');
      await page.locator('[data-claim-view=timeline]').hover();
      assert.equal(await page.locator('[data-claim-view=timeline]').evaluate(element => getComputedStyle(element).color), 'rgb(255, 255, 255)', 'Selected timeline view stays readable on hover');
      await page.waitForFunction(() => document.querySelectorAll('#research-claims-timeline .research-timeline-dated > li, #research-claims-timeline .research-timeline-unplaced > li').length === 6);
      assert.equal(await page.locator('#research-claims-timeline').isVisible(), true, 'Loaded timeline entries are visible');
      const dated = await page.locator('#research-claims-timeline .research-timeline-dated > li').first().getAttribute('data-claim-id');
      assert.equal(dated, fixture.claims[1], '1880 precedes 1900 rather than creation order');
      assert.equal(await page.locator('#research-claims-timeline .research-timeline-unplaced > li').count(), 3);
      const scale = await page.locator('#research-claims-timeline .research-timeline-dated > li').first().locator('.research-timeline-scale span').textContent();
      assert.equal(scale, '1880', 'A dated claim shows its placed calendar range');
      const headings = await page.locator('#research-claims-timeline h3').allTextContents();
      assert.ok(headings[0].includes('(3)') && headings[1].includes('(3)'), 'Both chronology sections carry a count');
      const placementHint = await page.evaluate(() => uiLabel('research_timeline_placement_hint'));
      assert.ok((await page.locator('#research-claims-timeline').textContent()).includes(placementHint), 'Unplaced periods explain how to place a claim');
      const stripRows = page.locator('#research-claims-timeline .research-timeline-strip-row');
      assert.equal(await stripRows.count(), 3, 'The chronology strip shows every dated claim');
      const stripHref = await stripRows.first().getAttribute('href');
      assert.equal(await page.locator('#' + stripHref.slice(1)).count(), 1, 'Strip rows link to their claim card');
      await stripRows.first().click();
      assert.equal(new URL(page.url()).hash, stripHref, 'Activating a strip row jumps to its card');
      assert.equal(writes.length, 0, 'Timeline navigation writes no authored records');
      const endpointLabels = await page.locator('#r-relation-from option').allTextContents();
      assert.equal(new Set(endpointLabels).size, endpointLabels.length, 'Duplicate titles and periods still have distinct selectable labels');
      await page.locator('[data-claim-view=list]').click();
      const evidenceLabels = await page.locator('#r-link-claim-select option').allTextContents();
      assert.equal(new Set(evidenceLabels).size, evidenceLabels.length, 'Keyword evidence choices distinguish duplicate claim titles, periods and versions');
      const decisionLabels = await page.locator('#r-decision-claim-select option').allTextContents();
      assert.equal(new Set(decisionLabels).size, decisionLabels.length, 'Decision choices distinguish duplicate claim titles, periods and versions');
      assert.deepEqual(decisionLabels.slice(1), evidenceLabels.slice(1), 'Decision and evidence pickers describe the same claim versions consistently');
      const reviewedClaimLabel = await page.locator(`#r-link-claim-select option[value="${fixture.claims[0]}"]`).textContent();
      assert.ok(reviewedClaimLabel.includes('1900'), 'The reviewed period is visible when choosing a claim');
      if (!await page.locator('#r-link-composer').evaluate(node => node.open)) await page.locator('#r-link-composer > summary').click();
      await page.locator('#r-link-claim-select').selectOption({label: reviewedClaimLabel});
      await page.locator('#r-find-passage').click();
      assert.equal(await page.locator('#r-search-scope').inputValue(), 'sources');
      assert.equal(await page.locator('#r-link-claim-select').inputValue(), fixture.claims[0]);
      await page.locator('#r-search-query').fill('reading room');
      await page.locator('#r-search-btn').click();
      await page.locator('#research-search-results [data-use-passage=claim]').click();
      assert.equal(await page.locator('#r-link-claim-select').inputValue(), fixture.claims[0]);
      assert.equal(await page.locator('#research-evidence-draft .selection-context').textContent(), 'The synthetic reading room opened in 1880. A second sentence supplies full context.');
      assert.equal(writes.length, 0, 'Keyword selection only prepares the existing draft');
      if (locale === 'en' && width === 1440) {
        await page.locator('#r-link-rationale').fill('Synthetic reviewer accepts this paragraph context.');
        await page.locator('#r-link-evidence-btn').click();
        await page.waitForFunction(() => document.querySelector('#r-link-passage-id').value === '');
        const evidence = await (await page.request.get(fixture.url + '/api/research/claims?claim_id=' + encodeURIComponent(fixture.claims[0]))).json();
        assert.equal(evidence.evidence_links[0].citation.source_version_id, fixture.version);
        assert.equal(evidence.evidence_links[0].citation.verbatim, 'The synthetic reading room opened in 1880. A second sentence supplies full context.');
        assert.ok(writes[0].expected_snapshot && writes[0].research_token && writes[0].expected_claim_revision === 1);
        if (!await page.locator('#r-relation-composer').evaluate(node => node.open)) await page.locator('#r-relation-composer > summary').click();
        await page.locator('#r-relation-from').selectOption(fixture.claims[1]);
        await page.locator('#r-relation-to').selectOption(fixture.claims[0]);
        assert.equal(await page.locator('#r-relation-compatibility').isVisible(), true);
        await page.locator('#r-relation-rationale').fill('Synthetic authored cause/effect interpretation.');
        await page.waitForFunction(() => !document.querySelector('#r-relation-save').disabled);
        let releaseRelation, relationAccepted;
        const accepted = new Promise(resolve => {relationAccepted = resolve;});
        await page.route('**/api/research-claim-relation', async route => {
          const response = await route.fetch(); relationAccepted();
          await new Promise(resolve => {releaseRelation = resolve;});
          await route.fulfill({response});
        });
        await page.locator('#r-relation-save').click();
        await accepted;
        await page.locator('#r-relation-rationale').fill('A newer unsaved synthetic interpretation.');
        releaseRelation();
        await page.waitForFunction(() => document.querySelector('.research-relation-card'));
        assert.equal(await page.locator('#r-relation-rationale').inputValue(), 'A newer unsaved synthetic interpretation.', 'Delayed acceptance preserves a newer draft');
        await page.unroute('**/api/research-claim-relation');
        const relationId = await page.locator('.research-relation-card').getAttribute('data-relation-id');
        assert.equal(await page.locator('#r-relation-compatibility').isVisible(), false);
        await page.locator(`#research-claims-list [data-research-revise=claim][data-record-id="${fixture.claims[0]}"]`).click();
        await page.locator('#research-revision-field-statement').fill('A newer synthetic statement.');
        await page.locator('input[name=research_revision_change_kind][value=correction]').check();
        await page.locator('#research-revision-reason').fill('Synthetic correction changes a reviewed endpoint.');
        await page.locator('#research-revision-save').click();
        await page.waitForFunction(() => !document.querySelector('#modal-research-revision').open);
        await page.waitForFunction(() => document.querySelector('.research-relation-card .ctl-status.err'));
        await page.locator(`.research-relation-card [data-research-revise=claim_relation]`).click();
        await page.locator('#research-revision-options').evaluate(element => {element.open = true;});
        assert.equal(await page.locator('#research-revision-field-from_claim_id').inputValue(), fixture.claims[1]);
        assert.equal(await page.locator('#research-revision-field-to_claim_revision').inputValue(), '1', 'The old reviewed pin survives endpoint revision');
        await page.locator('#research-revision-field-state').selectOption('retracted');
        await page.locator('input[name=research_revision_change_kind][value=correction]').check();
        await page.locator('#research-revision-reason').fill('Synthetic retraction preserves prior interpretation history.');
        await page.locator('#research-revision-save').click();
        await page.waitForFunction(() => !document.querySelector('#modal-research-revision').open);
        await page.waitForFunction(() => !document.querySelector('.research-relation-card'));
        await page.locator('#r-relation-retracted').check();
        await page.waitForFunction(() => document.querySelector('.research-relation-card'));
        const relation = await (await page.request.get(fixture.url + '/api/research/record?kind=claim_relation&id=' + encodeURIComponent(relationId))).json();
        assert.equal(relation.record.state, 'retracted');
        assert.equal(relation.record.revision, 2);
        assert.equal(relation.record.to_claim_ref.revision, 1);
        await page.locator('[data-rtab=search]').click();
        let releaseSearch, firstSearch;
        const held = new Promise(resolve => {firstSearch = resolve;});
        const researchToken = await page.locator('#research-manager').getAttribute('data-research-token');
        const oldResult = await (await page.request.post(fixture.url + '/api/research-search', {
          data: {query: 'reading', scope: 'sources', research_token: researchToken}})).json();
        await page.route('**/api/research-search', async route => {
          if (route.request().postDataJSON().query !== 'reading') return route.continue();
          firstSearch();
          await new Promise(resolve => {releaseSearch = resolve;});
          await route.fulfill({json: oldResult});
        });
        await page.locator('#r-search-query').fill('reading');
        await page.locator('#r-search-btn').click();
        await held;
        await page.locator('#r-search-query').fill('garden');
        await page.locator('#r-search-btn').click();
        await page.waitForFunction(() => document.querySelector('#research-search-results').textContent.includes('garden stayed quiet'));
        releaseSearch();
        await page.waitForTimeout(150);
        assert.ok((await page.locator('#research-search-results').textContent()).includes('garden stayed quiet'), 'A delayed old query cannot replace newer keyword results');
        await page.unroute('**/api/research-search');
        await page.locator('#research-search-results [data-use-passage=claim]').click();
        assert.equal(await page.locator('#research-evidence-draft .selection-context').textContent(), 'The garden stayed quiet.');
        await page.locator('[data-rtab=search]').click();
        const beforeForeign = writes.length;
        await page.route('**/api/research-search', route => route.fulfill({json: {
          ...oldResult, project_id: 'urn:uuid:00000000-0000-4000-8000-000000000099'}}));
        await page.locator('#r-search-query').fill('reading');
        const foreignResponse = page.waitForResponse(response => response.url().endsWith('/api/research-search'));
        await page.locator('#r-search-btn').click();
        await (await foreignResponse).finished();
        await page.evaluate(() => new Promise(resolve => setTimeout(resolve, 0)));
        assert.equal(await page.locator('#research-search-results [data-use-passage]').count(), 0, 'A response from another project cannot offer citation actions');
        assert.equal(await page.locator('#research-evidence-draft .selection-context').textContent(), 'The garden stayed quiet.', 'A rejected result preserves the newer citation draft');
        assert.equal(writes.length, beforeForeign);
        await page.unroute('**/api/research-search');
      }
      assert.equal(await page.locator('#research-evidence-draft img, #research-claims-timeline img').count(), 0);
      assert.equal(await page.evaluate(() => window.chronologyInjected), undefined);
      await page.locator('[data-rtab=claims]').click();
      await page.locator('#r-relation-retracted').check();
      await page.waitForFunction(() => document.querySelector('.research-relation-card'));
      await page.locator('.research-relation-card [data-research-history=claim_relation]').click();
      await page.waitForFunction(() => document.querySelector('#research-revision-history-detail dd'));
      const stateLabel = await page.evaluate(() => uiLabel('research_relation_retracted'));
      assert.ok((await page.locator('#research-revision-history-detail').textContent()).includes(stateLabel), 'Saved relationship state uses its localized meaning');
      await page.locator('#modal-research-revision [data-close-modal]').first().click();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.locator('#rtab-claims').screenshot({path: path.join(artifacts, `${locale}-${width}.png`)});
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log(JSON.stringify({passed: true, locales: 7, viewports: [1440, 320], artifacts}));
  } finally {
    if (browser) await browser.close();
    lines.close(); server.kill('SIGTERM'); await once(server, 'exit').catch(() => {});
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
