// Shared tools preserve author drafts, return context and pending source identity.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const {openSourceComparison} = require('./support/research-tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-research-tools-'));

(async () => {
  const server = await startNativeServer(`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
base = Path(sys.argv[1]); project = base / 'synthetic-project'
api.init(project, title='Synthetic workflow project')
sources = []
for name, text in [('Alpha', 'The archive garden contains amber lanterns.'), ('Beta', 'The keeper walks beside the quiet river.')]:
    source = base / (name + '.txt'); source.write_text(text, encoding='utf-8')
    sources.append(api.ingest(project, source, title=name + ' source', allow_retention=True)['source_id'])
claim = api.create_claim(project, title='Synthetic claim', statement='The garden contains lanterns.')['claim_id']
manuscript = project / 'manuscript.md'; manuscript.write_text('## Synthetic chapter\\n\\nThe archive keeper walks beside the garden and the quiet river.\\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project); LixityServerHandler.research_dir = str(project)
LixityServerHandler.source_input = str(manuscript); LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.language = 'en'; LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'sources': sources, 'claim': claim, 'project': str(project)}), flush=True)
server.serve_forever()
`, artifacts);
  let browser;
  const releases = [];
  const sourceReturns = [], expectedSourceReturns = [];
  try {
    browser = await launchChromium();
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport:{width,height:950}, reducedMotion:'reduce'});
      page.setDefaultTimeout(10000);
      const errors = [], comparisons = [], writes = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => {
        if (request.method() !== 'POST') return;
        const endpoint = new URL(request.url()).pathname;
        if (endpoint === '/api/research-compare') comparisons.push(request.postDataJSON());
        else if (!['/api/research-search'].includes(endpoint)) writes.push(endpoint);
      });
      await page.goto(server.fixture.url);
      await page.locator('[data-view=research]').click();
      await page.locator('[data-rtab=claims]').click();
      await page.locator('#r-claim-composer > summary').click();
      await page.locator('#r-claim-title').fill('Unsaved synthetic title');
      await page.locator('#r-claim-statement').fill('Unsaved synthetic statement');
      const origin = page.locator('[data-rtab=search]');
      await origin.click();
      await expect(origin).toHaveAttribute('aria-expanded', 'true');
      await expect(page.locator('[data-rtab=claims]')).toHaveAttribute('aria-selected', 'true');
      await expect(page.locator('#r-claim-title')).toBeVisible();
      await expect(page.locator('#r-search-scope option')).toHaveCount(5);
      await page.locator('#r-search-scope').selectOption('sources');
      await page.locator('#r-search-query').fill('garden');
      await page.locator('#r-search-btn').click();
      await expect(page.locator('#research-search-results')).toContainText('Alpha source');
      await page.screenshot({path:path.join(artifacts, `search-${width}.png`)});
      await page.keyboard.press('Escape');
      await expect(page.locator('#research-tool-host')).toBeHidden();
      await expect(origin).toBeFocused();
      await expect(page.locator('#r-claim-title')).toHaveValue('Unsaved synthetic title');
      await expect(page.locator('#r-claim-statement')).toHaveValue('Unsaved synthetic statement');
      await origin.click();
      await expect(page.locator('#r-search-query')).toHaveValue('garden');
      const readHit = page.locator('#research-search-results [data-research-search-passage]').first();
      await readHit.click();
      await expect(page.locator('#research-search-reader .research-passage-quote')).toBeVisible();
      await expect(page.locator('#research-search-reader')).toContainText('The archive garden contains amber lanterns.');
      const readCurrent = page.locator('#research-search-reader [data-research-detail=source]');
      await expect(readCurrent).toHaveText('Read current source');
      await readCurrent.click();
      await expect(page.locator('#research-search-reader .research-source-doc-rendered')).toContainText('The archive garden contains amber lanterns.');
      await page.screenshot({path:path.join(artifacts, `passage-source-${width}.png`)});
      const searchCompare = page.locator('#research-search-reader [data-research-source-compare]');
      await searchCompare.click();
      await expect(page.locator('#research-tool-host')).toHaveAttribute('data-tool', 'grounding');
      await page.locator('#research-tool-close').click();
      await expect(page.locator('#research-tool-host')).toHaveAttribute('data-tool', 'search');
      await expect(searchCompare).toBeFocused();
      await page.locator('#research-search-return').click();
      await expect(readHit).toBeFocused();

      await expect(page.locator('#r-search-scope')).toHaveValue('sources');
      await page.locator('#research-tool-close').click();

      await openSourceComparison(page, server.fixture.sources[0]);
      assert.deepEqual(comparisons, [], 'Opening the source and comparison entry never runs analysis');
      await expect(page.locator('#rtab-sources')).toBeVisible();
      await expect(page.locator('#research-tool-host')).toContainText('Alpha source');
      let release, ready;
      const gate = new Promise(resolve => { release = resolve; releases.push(resolve); });
      const started = new Promise(resolve => { ready = resolve; });
      await page.route('**/api/research-compare', async route => {
        const response = await route.fetch();
        ready();
        await gate;
        await route.fulfill({response});
      });
      await page.locator('#r-ground-btn').click();
      await started;
      assert.equal(comparisons[0].source_id, server.fixture.sources[0]);
      await page.locator(`#research-sources-list [data-research-detail=source][data-record-id="${server.fixture.sources[0]}"]`).click();
      await expect(page.locator('#research-tool-host')).toBeHidden();
      await expect(page.locator('#r-ground-btn')).toHaveAttribute('aria-busy', 'false');

      await openSourceComparison(page, server.fixture.sources[1]);
      await expect(page.locator('#research-tool-host')).toContainText('Beta source');
      const finished = page.waitForResponse(response => response.url().endsWith('/api/research-compare'));
      release();
      await finished;
      await expect(page.locator('#research-tool-host')).toContainText('Beta source');
      await expect(page.locator('#research-grounding-results')).not.toContainText('Alpha source');
      await expect(page.locator('#research-grounding-results [data-ground-tab=shared]')).toHaveCount(0);
      await page.unroute('**/api/research-compare');
      await page.locator('#r-ground-btn').click();
      await expect(page.locator('#research-grounding-results [data-ground-tab=shared]')).toBeVisible();
      assert.equal(comparisons.length, 2);
      assert.equal(comparisons[1].source_id, server.fixture.sources[1]);
      // A completed comparison also loses its owner when the source reader collapses.
      const betaSummary = page.locator(`#research-sources-list [data-research-detail=source][data-record-id="${server.fixture.sources[1]}"]`);
      await betaSummary.click();
      await expect(page.locator('#research-tool-host')).toBeHidden();
      assert.equal(comparisons.length, 2, 'Collapsing a completed comparison never starts another request');
      await openSourceComparison(page, server.fixture.sources[1]);
      await expect(page.locator('#r-ground-btn')).toBeEnabled();
      // Hold two successive requests: the abandoned reply must not settle its replacement.
      const pending = [];
      await page.route('**/api/research-compare', async route => {
        const response = await route.fetch();
        let releaseResponse;
        const held = new Promise(resolve => {releaseResponse = resolve; releases.push(resolve);});
        pending.push({release:releaseResponse, finished:false});
        const request = pending.at(-1);
        await held;
        await route.fulfill({response});
        request.finished = true;
      });
      await page.locator('#r-ground-btn').click();
      await expect.poll(() => pending.length).toBe(1);
      await betaSummary.click();
      await expect(page.locator('#research-tool-host')).toBeHidden();
      await expect(page.locator('#r-ground-btn')).toHaveAttribute('aria-busy', 'false');
      await openSourceComparison(page, server.fixture.sources[1]);
      await expect(page.locator('#r-ground-btn')).toBeEnabled();
      await page.locator('#r-ground-btn').click();
      await expect.poll(() => pending.length).toBe(2);
      pending[0].release();
      await expect.poll(() => pending[0].finished).toBe(true);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await expect(page.locator('#research-tool-host')).toBeVisible();
      await expect(page.locator('#r-ground-btn')).toBeDisabled();
      await expect(page.locator('#r-ground-btn')).toHaveAttribute('aria-busy', 'true');
      await expect(page.locator('#research-grounding-results [data-ground-tab=shared]')).toHaveCount(0);
      pending[1].release();
      await expect(page.locator('#r-ground-btn')).toHaveAttribute('aria-busy', 'false');
      await expect(page.locator('#r-ground-btn')).toBeEnabled();
      await expect(page.locator('#research-grounding-results [data-ground-tab=shared]')).toBeVisible();
      await page.unroute('**/api/research-compare');

      // The reader may still show an older retained version when the archive gains one.
      const previousVersion = await page.locator('#research-comparison-source').getAttribute('data-source-version');
      const refreshed = JSON.parse(execFileSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
import json, sys
from pathlib import Path
from lixity.research import api
project = Path(sys.argv[1]); source = project.parent / 'Beta.txt'
source.write_text('The keeper walks beside the quiet river. Latest synthetic capture ' + sys.argv[3] + '.', encoding='utf-8')
print(json.dumps(api.ingest(project, source, source_id=sys.argv[2], allow_retention=True)))
`, server.fixture.project, server.fixture.sources[1], String(width)], {cwd:root, env:{...process.env,PYTHONPATH:path.join(root,'src')}, encoding:'utf8'}));
      assert.ok(!previousVersion.includes(refreshed.source_version_id));
      await page.locator('#r-ground-btn').click();
      await expect(page.locator('#research-comparison-source')).toHaveAttribute('data-source-version', refreshed.source_version_id);
      await expect(page.locator('#research-grounding-results')).toContainText(refreshed.source_version_id);
      await page.screenshot({path:path.join(artifacts, `comparison-${width}.png`)});
      // Malformed/unavailable measurements must never become measured zeroes.
      await page.route('**/api/research-compare', async route => {
        const response = await route.fetch(), json = await response.json();
        json.summary = {jaccard_similarity:null, overlap_coefficient:null,
          shared_types:null, source_content_words:null, manuscript_content_words:null};
        await route.fulfill({response,json});
      });
      await page.locator('#r-ground-btn').click();
      const details = page.locator('#research-grounding-results > .research-card > details');
      await details.locator(':scope > summary').click();
      await expect(details.locator('[role=status]')).toBeVisible();
      await expect(details.locator('[data-comparison-version]')).toBeVisible();
      await expect(details.locator('[data-comparison-version]')).toContainText(refreshed.source_version_id);
      const values = await details.locator('.grounding-kpi-val').allTextContents();
      assert.equal(values.length, 4);
      assert.ok(values.every(value => !/[0-9]|NaN/.test(value)), 'Missing comparison measurements remain unknown');
      await page.unroute('**/api/research-compare');
      await page.locator('#research-tool-close').click();
      await page.locator('[data-rtab=claims]').click();
      await expect(page.locator('#r-claim-title')).toHaveValue('Unsaved synthetic title');
      await expect(page.locator('#r-claim-statement')).toHaveValue('Unsaved synthetic statement');
      await page.locator('[data-view=analysis]').click();
      await page.locator('#research-reader-terms').click();
      await expect(page.locator('#research-tool-host')).toBeVisible();
      await expect(page.locator('#research-manuscript-terms-section')).toHaveAttribute('open', '');
      await expect(page.locator('#r-terms-refresh')).toBeVisible();
      await page.locator('#research-tool-close').click();
      await expect(page.locator('[data-view=analysis]')).toHaveAttribute('aria-selected', 'true');
      await expect(page.locator('#research-reader-terms')).toBeFocused();
      // Return belongs to the clicked content reader, even when another utility was open.
      for (const entry of ['header-review', 'header-search', 'reader-terms']) {
        await page.locator('[data-view=research]').click();
        await openSourceComparison(page, server.fixture.sources[0]);
        await page.locator('#research-tool-close').click();
        const contentCompare = page.locator(`#research-sources-list [data-research-source-compare="${server.fixture.sources[0]}"]`);
        await expect(contentCompare).toBeFocused();
        if (entry === 'reader-terms') {
          await page.locator('[data-view=analysis]').click();
          await page.locator('#research-reader-terms').click();
        } else {
          await page.locator(`[data-rtab=${entry === 'header-review' ? 'review' : 'search'}]`).click();
        }
        await expect(page.locator('[data-rtab=sources]')).toHaveAttribute('aria-selected', 'true');
        await contentCompare.click();
        await expect(page.locator('#research-tool-host')).toHaveAttribute('data-tool', 'grounding');
        await page.locator('#research-tool-close').click();
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        sourceReturns.push({width, entry, ...await page.evaluate(() => ({
          source: document.activeElement.dataset.researchSourceCompare || null,
          view: window.LixityWorkbench.state().view,
          tool: window.LixityResearchTools.active(),
          sourcesSelected: document.querySelector('[data-rtab=sources]').getAttribute('aria-selected')
        }))});
        expectedSourceReturns.push({width, entry, source:server.fixture.sources[0], view:'research', tool:'', sourcesSelected:'true'});
        // Settle any restored utility before exercising the next independent entry.
        if (await page.locator('#research-tool-host').isVisible()) await page.locator('#research-tool-close').click();
      }
      assert.deepEqual(writes, [], 'Reading, searching, comparison and return never save records or settings');
      assert.deepEqual(errors, []);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({path:path.join(artifacts, `tools-${width}.png`)});
      // A surface teardown can replace the document while its observer is queued.
      await page.evaluate(() => {
        document.body.innerHTML = '<main><p id="replacement-surface">Synthetic replacement surface</p></main>';
      });
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await expect(page.locator('#replacement-surface')).toHaveText('Synthetic replacement surface');
      assert.deepEqual(errors, [], 'Removing the original research surface disconnects its observer without runtime errors');
      await page.close();
    }
    assert.deepEqual(sourceReturns, expectedSourceReturns, 'Source return restores the actual clicked reader instead of the previous utility origin');
    console.log('Research tools: retained drafts/query/scope, Escape return, explicit source comparison and late-response isolation passed at1440/320. '+artifacts);
  } finally {
    releases.forEach(release => release());
    if (browser) await browser.close();
    await server.close();
  }
})().catch(error => {console.error(error); process.exitCode=1;});
