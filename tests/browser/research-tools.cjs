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
manuscript = project / 'manuscript' / 'draft.md'; manuscript.parent.mkdir()
paragraph = 'The archive keeper walks beside the garden and the quiet river.\\n'
manuscript.write_text('## Synthetic chapter\\n\\n' + paragraph + '\\n## The bridge\\n\\nRain fell on the planks.\\n'
    '\\n## The landing\\n\\nThe boat waited.\\n\\n' + paragraph, encoding='utf-8')
dossier = api.create_dossier(project, title='Synthetic term dossier', body='## Notes\\n\\nA note about the river.')['dossier_id']
(project / 'lixity.toml').write_text(
    '[terms."quiet river"]\\naliases = ["archive keeper"]\\ndossier_id = ' + json.dumps(dossier)
    + '\\nclaim_id = ' + json.dumps(claim)
    + '\\nscoped_alternatives = [{term = "Signal 7", chapters = [1], note = "Keep the archival name"}, '
      '{term = "estuary: marker", chapters = [3, 9], note = "Retain the historical name"}]\\n'
    + '[terms.garden]\\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project); LixityServerHandler.research_dir = str(project)
LixityServerHandler.source_input = str(manuscript); LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.language = 'en'; LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'sources': sources, 'claim': claim, 'dossier': dossier, 'project': str(project)}), flush=True)
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
      const occurrences = ['archive keeper', 'garden', 'quiet river'];
      await expect(page.locator('#research-manuscript-terms blockquote')).toHaveText([...occurrences, ...occurrences]);
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
      await page.locator('[data-rtab=dossiers]').click();
      const dossier = page.locator(`#research-dossiers-list [data-research-detail=dossier][data-record-id="${server.fixture.dossier}"]`);
      await dossier.click();
      const terms = dossier.locator('..').locator('details[data-dossier-terms]');
      await expect(terms).toBeVisible();
      await expect(terms).not.toHaveAttribute('open', '');
      const scopedRead = page.waitForResponse(response => {
        const url = new URL(response.url());
        return url.pathname === '/api/research/manuscript-terms' && url.searchParams.get('dossier_id') === server.fixture.dossier;
      });
      await terms.locator(':scope > summary').press('Enter');
      const scopedTerms = await (await scopedRead).json();
      assert.equal(scopedTerms.dossier_id, server.fixture.dossier);
      assert.deepEqual(scopedTerms.terms.map(term => term.term), ['quiet river']);
      const linkedOccurrences = ['archive keeper', 'quiet river'];
      await expect(terms.locator('blockquote')).toHaveText([...linkedOccurrences, ...linkedOccurrences]);
      const firstMatch = scopedTerms.occurrences[0].anchor;
      const lastMatch = scopedTerms.occurrences.at(-1).anchor;
      assert.equal(firstMatch.paragraph_sha256, lastMatch.paragraph_sha256);
      assert.notEqual(firstMatch.start_line, lastMatch.start_line);
      await page.evaluate(() => {
        const bridge = window.LixityManuscriptLinks;
        const navigate = bridge.navigate;
        bridge.navigate = panel => {
          document.body.dataset.termJumpLine = panel.dataset.start;
          navigate(panel);
        };
      });
      await terms.getByRole('button', {name:'Go to manuscript passage'}).last().click();
      await expect(page.locator('body')).toHaveAttribute('data-term-jump-line', String(lastMatch.start_line));
      await expect(page.locator('[data-view=analysis]')).toHaveAttribute('aria-selected', 'true');
      assert.deepEqual(writes, [], 'Reading, searching, comparison and return never save records or settings');
      assert.deepEqual(errors, []);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({path:path.join(artifacts, `tools-${width}.png`)});
      if (width === 320) {
        await page.locator('#research-reader-terms').click();
        const catalogueRead = page.waitForRequest(request => {
          const url = new URL(request.url());
          return url.pathname === '/api/research/dossiers' && url.searchParams.has('project_token') && !url.searchParams.has('id');
        });
        await page.locator('#r-term-manage > summary').click();
        const catalogue = new URL((await catalogueRead).url());
        assert.equal(catalogue.searchParams.get('project_token'), await page.locator('body').getAttribute('data-manuscript-project-token'));
        const saveTerm = page.locator('#r-term-save-btn');
        const termStatus = page.locator('#r-term-status');
        const termDossier = page.getByRole('combobox', {name:'Linked dossier (optional)'});
        await expect(termDossier).toBeEnabled();
        await expect(termDossier).toHaveAccessibleDescription('The selected dossier will show where this term appears in the manuscript.');
        await expect(termDossier.locator('option').last()).toHaveText('Synthetic term dossier');
        const dossierField = termDossier.locator('..').locator('..');
        for (const viewport of [320, 1440, 2560]) {
          await page.setViewportSize({width:viewport, height:950});
          assert.ok(await dossierField.evaluate(node => node.scrollWidth <= node.clientWidth),
            `Linked dossier controls fit at ${viewport}px`);
        }
        await page.setViewportSize({width, height:950});
        await dossierField.screenshot({path:path.join(artifacts, 'term-dossier-320.png')});
        await expect(page.locator('#r-term-chips').getByRole('button', {name:'quiet river', exact:true})).toBeVisible();
        async function writeTerm() {
          const token = await page.locator('#settings-form').getAttribute('data-project-token');
          const manuscriptToken = await page.locator('body').getAttribute('data-manuscript-project-token');
          assert.notEqual(token, manuscriptToken);
          const written = page.waitForResponse(response => new URL(response.url()).pathname === '/api/settings');
          await saveTerm.click();
          const accepted = await written;
          assert.equal(accepted.status(), 200);
          const payload = accepted.request().postDataJSON();
          assert.equal(payload.project_token, token);
          await expect(termStatus).toContainText('Settings applied.');
          await expect(page.locator('#research-tool-host')).toBeVisible();
          await expect(saveTerm).toBeEnabled();
          return payload.terms;
        }
        await page.locator('#r-term-name').fill('walks beside');
        await termDossier.selectOption(server.fixture.dossier);
        const created = await writeTerm();
        assert.equal(created['walks beside'].dossier_id, server.fixture.dossier);
        const expandedOccurrences = ['archive keeper', 'walks beside', 'garden', 'quiet river'];
        await expect(page.locator('#research-manuscript-terms blockquote')).toHaveText([...expandedOccurrences, ...expandedOccurrences]);
        if (await dossier.locator('..').evaluate(node => node.open)) await dossier.click();
        await dossier.click();
        await terms.locator(':scope > summary').press('Enter');
        const expandedLinks = ['archive keeper', 'walks beside', 'quiet river'];
        await expect(terms.locator('blockquote')).toHaveText([...expandedLinks, ...expandedLinks]);

        await page.route(url => url.pathname === '/api/research/dossiers' && url.searchParams.has('project_token') && !url.searchParams.has('id'),
          route => route.fulfill({status:503, json:{ok:false}}), {times:1});
        await page.locator('#r-terms-refresh').press('Enter');
        await expect(page.locator('#r-term-dossier-status')).toContainText('Failed to load dossiers');
        await expect(termDossier).toBeDisabled();
        await page.locator('#r-term-chips').getByRole('button', {name:'quiet river', exact:true}).click();
        await expect(termDossier).toHaveValue(server.fixture.dossier);
        await page.locator('#r-term-aliases').fill('archive keeper, riverbank');
        const variants = page.locator('#r-term-variants');
        const wording = row => row.getByRole('textbox', {name:'Variant wording'});
        const chapterField = row => row.getByRole('textbox', {name:'Chapter numbers'});
        const first = variants.getByRole('group', {name:'Variant 1'});
        const second = variants.getByRole('group', {name:'Variant 2'});
        await expect(wording(first)).toHaveValue('Signal 7');
        await expect(wording(second)).toHaveValue('estuary: marker');
        await expect(second.getByRole('textbox', {name:'Note (optional)'})).toHaveValue('Retain the historical name');
        await expect(chapterField(second)).toHaveValue('3, 9');
        await second.getByText('Choose from manuscript chapters', {exact:true}).press('Enter');
        const chapterTwo = second.getByRole('button', {name:'Chapter 2', exact:true});
        await chapterTwo.press('Enter');
        await expect(chapterTwo).toHaveAttribute('aria-pressed', 'true');
        await expect(chapterField(first)).toHaveValue('1');
        await expect(chapterField(second)).toHaveValue('2, 3, 9');
        await page.locator('#r-term-add-variant').press('Enter');
        const temporary = variants.getByRole('group', {name:'Variant 3'});
        await expect(wording(temporary)).toBeFocused();
        await wording(temporary).fill('Planning variant');
        await chapterField(temporary).fill('2, 2');
        const beforeInvalid = writes.length;
        await saveTerm.press('Enter');
        await expect(chapterField(temporary)).toHaveJSProperty('validationMessage', 'Enter distinct positive chapter numbers separated by commas.');
        assert.equal(writes.length, beforeInvalid);
        await temporary.getByRole('button', {name:'Remove variant'}).press('Enter');
        await expect(wording(second)).toBeFocused();
        await expect(temporary).toHaveCount(0);
        for (const viewport of [320, 1440, 2560]) {
          await page.setViewportSize({width:viewport, height:950});
          assert.ok(await second.evaluate(row => row.scrollWidth <= row.clientWidth &&
            Number.parseFloat(getComputedStyle(row).paddingInlineStart) > 0), `Variant rows fit with interior spacing at ${viewport}px`);
        }
        await page.setViewportSize({width, height:950});
        await variants.screenshot({path:path.join(artifacts, 'term-variants-320.png')});
        const edited = await writeTerm();
        assert.equal(edited['quiet river'].dossier_id, server.fixture.dossier);
        assert.equal(edited['quiet river'].claim_id, server.fixture.claim);
        assert.equal(edited['quiet river'].strict_boundaries, null);
        const expectedVariants = [
          {term:'Signal 7', chapters:[1], note:'Keep the archival name'},
          {term:'estuary: marker', chapters:[2, 3, 9], note:'Retain the historical name'},
        ];
        assert.deepEqual(edited['quiet river'].scoped_alternatives, expectedVariants);
        await page.locator('#r-term-chips').getByRole('button', {name:'quiet river', exact:true}).click();
        await expect(chapterField(second)).toHaveValue('2, 3, 9');
        const removeVariants = variants.getByRole('button', {name:'Remove variant'});
        await removeVariants.first().press('Enter');
        await removeVariants.first().press('Enter');
        await expect(page.locator('#r-term-add-variant')).toBeFocused();
        const cleared = await writeTerm();
        assert.deepEqual(cleared['quiet river'].scoped_alternatives, []);
        assert.equal(cleared['quiet river'].dossier_id, server.fixture.dossier);
        await page.locator('#r-term-chips').getByRole('button', {name:'walks beside', exact:true}).click();
        await expect(termDossier).toBeEnabled();
        await expect(termDossier).toHaveValue(server.fixture.dossier);
        await termDossier.selectOption('');
        const unlinked = await writeTerm();
        assert.equal(unlinked['walks beside'].dossier_id, null);
        assert.equal(unlinked['quiet river'].dossier_id, server.fixture.dossier);
        assert.deepEqual(writes, ['/api/settings', '/api/settings', '/api/settings', '/api/settings']);
      }
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
