// Empty evidence guides an existing claim into the retained-passage workflow.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-claim-evidence-actions-'));

async function openClaims(page) {
  await page.locator('[data-rtab=claims]').click();
  // Startup's overview has no archive snapshot; wait for the first versioned
  // catalogue before testing reads that must survive unchanged refreshes.
  await expect.poll(() => page.evaluate(() => researchClaimsSnapshot)).toMatch(/^[0-9a-f]{64}$/);
}

(async () => {
  const server = await startNativeServer(`
import json, re, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
from lixity.workspace_labels import WORKSPACE_LABELS
base = Path(sys.argv[1]); project = base / 'synthetic-project'
api.init(project, title='Synthetic claim evidence actions')
dossier = api.create_dossier(project, title='Synthetic dossier', body='Synthetic dossier notes.')
empty_dossier = api.create_dossier(project, title='Synthetic empty dossier', body='No claim association.')
ids = {'empty': api.create_claim(project, title='Synthetic claim without evidence', statement='The gate opened.',
    confidence='evidenced', dossier_id=dossier['dossier_id'])['claim_id']}
for state in ('retained', 'withdrawn', 'unavailable', 'historical'):
    source = base / (state + '.txt')
    source.write_text('Synthetic ' + state + ' source paragraph about a quiet garden.', encoding='utf-8')
    captured = api.ingest(project, source, allow_retention=True)
    passage = api.get_source(project, captured['source_id'])['passages'][0]['id']
    claim = api.create_claim(project, title='Synthetic ' + state + ' claim', statement='An authored interpretation.')['claim_id']
    ids[state] = claim
    api.link_evidence(project, claim_id=claim, passage_id=passage)
    if state == 'withdrawn': api.withdraw(project, captured['source_id'], reason='Synthetic withdrawal')
    if state == 'unavailable': api.purge(project, captured['source_id'], reason='Synthetic purge')
    if state == 'historical':
        current = api.get_record(project, 'claim', claim)
        api.revise_record(project, 'claim', claim, changes={'statement': 'A changed interpretation.'},
            expected_snapshot=current['snapshot'], expected_revision=1, change_kind='correction', reason='Synthetic revision')
api.record_decision(project, title='Synthetic decision without claim', rationale='An authored choice.')
manuscript = project / 'manuscript.md'
manuscript.write_text('# Synthetic manuscript\\n\\nA bird crosses the quiet garden. Rain begins.\\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.research_dir = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.exports_dir = str(base / 'exports')
labels = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    LixityServerHandler.language = locale
    LixityServerHandler.refresh()
    (base / (locale + '.html')).write_text(LixityServerHandler.dashboard_html, encoding='utf-8')
    labels[locale] = {key: WORKSPACE_LABELS[locale][key] for key in (
        'research_link_heading', 'research_no_linked_evidence',
        'research_loading_evidence', 'research_evidence_withdrawn_context', 'research_evidence_unavailable',
        'research_dossier_claims_empty')}
# Locale shells share this server's final manuscript context, as do embedding
# hosts; presentation language does not request another project or analysis.
token = re.search(r'data-manuscript-project-token="([^"]+)"', LixityServerHandler.dashboard_html).group(1)
for locale in labels:
    shell = base / (locale + '.html')
    text = shell.read_text(encoding='utf-8')
    old_token = re.search(r'data-manuscript-project-token="([^"]+)"', text).group(1)
    shell.write_text(text.replace(old_token, token), encoding='utf-8')
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'ids': ids,
    'dossier': dossier['dossier_id'], 'empty_dossier': empty_dossier['dossier_id'], 'labels': labels}), flush=True)
server.serve_forever()
`, artifacts);
  let browser;
  try {
    browser = await launchChromium();
    for (const [locale, labels] of Object.entries(server.fixture.labels)) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 1000}});
      page.setDefaultTimeout(10000);
      const errors = [], writes = [], external = [];
      let evidenceRead = 'native', held, release;
      let holdCatalogue = locale === 'en', catalogueHeld, releaseCatalogue, catalogueSnapshot = 'native';
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => {if (['error', 'warning'].includes(message.type())) errors.push(message.text());});
      await page.route('**/*', async route => {
        const request = route.request(), url = new URL(request.url());
        if (url.origin !== server.fixture.url) {external.push(request.url()); return route.abort();}
        if (request.method() !== 'GET') {writes.push(url.pathname); return route.abort();}
        if (url.pathname === '/') return route.fulfill({contentType: 'text/html', body: fs.readFileSync(path.join(artifacts, locale + '.html'), 'utf8')});
        if (url.pathname === '/api/research/claims' && !url.searchParams.has('claim_id') && !url.searchParams.has('dossier_id')) {
          const response = await route.fetch(), data = await response.json();
          if (catalogueSnapshot === 'changed') data.snapshot = 'f'.repeat(64);
          if (catalogueSnapshot === 'missing') delete data.snapshot;
          if (holdCatalogue) {
            catalogueHeld = true;
            await new Promise(resolve => {releaseCatalogue = resolve;});
          }
          return route.fulfill({json: data});
        }
        if (url.pathname === '/api/research/claims' && url.searchParams.get('claim_id') === server.fixture.ids.empty) {
          if (evidenceRead === 'held') {
            held = true;
            await new Promise(resolve => {release = resolve;});
          }
          if (evidenceRead === 'failed') return route.fulfill({json: {ok: false, message: 'Synthetic evidence read unavailable'}});
          if (evidenceRead === 'malformed') return route.fulfill({json: {ok: true}});
          const malformedRows = {
            'null-row': null,
            'primitive-row': 'Invalid evidence row',
            'array-row': [],
            'object-quote': {citation: {availability: 'available', verbatim: {toString: null}}},
            'object-revision': {claim_revision: {toString: null}, claim_latest_revision: 2},
          };
          if (Object.hasOwn(malformedRows, evidenceRead)) return route.fulfill({json: {ok: true, evidence_links: [malformedRows[evidenceRead]]}});
        }
        return route.continue();
      });
      await page.goto(server.fixture.url);
      assert.match(await page.title(), /Synthetic manuscript/);
      await expect(page.locator('#chapters')).toContainText('A bird crosses the quiet garden.');
      if (locale === 'en') {
        await expect(page.locator('[data-research-detail=dossier]')).toHaveCount(2);
        await expect(page.locator('#research-claims-list [data-load-evidence]')).toHaveCount(0);
        await expect.poll(() => catalogueHeld).toBe(true);
        holdCatalogue = false; releaseCatalogue();
        await expect(page.locator('#research-claims-list [data-load-evidence]')).toHaveCount(5);
      }
      await page.locator('#tab-view-research').click();
      await page.locator('[data-rtab=dossiers]').click();
      const dossier = page.locator('[data-research-detail=dossier][data-record-id="' + server.fixture.dossier + '"]');
      await dossier.click();
      const claims = dossier.locator('..').locator('.research-dossier-claims');
      await claims.locator('[data-research-history=claim]').click();
      await expect(page.locator('#research-revision-history-detail')).toContainText('The gate opened.');
      await page.keyboard.press('Escape');
      await expect(page.locator('#modal-research-revision')).not.toBeVisible();
      const noClaim = page.locator('[data-research-detail=dossier][data-record-id="' + server.fixture.empty_dossier + '"]');
      await noClaim.click();
      await expect(noClaim.locator('..').locator('.research-dossier-claims')).toContainText(labels.research_dossier_claims_empty);
      await expect(noClaim.locator('..').locator('.research-dossier-claims [data-research-history=claim]')).toHaveCount(0);
      await openClaims(page);
      const empty = page.locator('[id="claim-evidence-' + server.fixture.ids.empty + '"]');
      await empty.locator('[data-load-evidence]').click();
      await expect(empty).toContainText(labels.research_no_linked_evidence);
      // Removing the empty-state route would leave the reader at a dead end.
      const action = empty.getByRole('button', {name: labels.research_link_heading, exact: true});
      await expect(action).toBeVisible();
      await expect(empty.locator('button')).toHaveCount(1);
      await empty.locator('..').screenshot({path: path.join(artifacts, `empty-${locale}-${width}.png`)});
      await action.click();
      await expect(page.locator('#r-link-composer')).toHaveAttribute('open', '');
      await expect(page.locator('#r-link-claim-select')).toHaveValue(server.fixture.ids.empty);
      await expect(page.locator('#r-find-passage')).toBeFocused();
      await page.locator('#r-find-passage').click();
      await expect(page.locator('#r-search-scope')).toHaveValue('sources');
      await expect(page.locator('#r-search-query')).toBeFocused();
      await openClaims(page);
      await expect(page.locator('#r-link-claim-select')).toHaveValue(server.fixture.ids.empty);
      await page.locator('#r-link-claim-select').selectOption(server.fixture.ids.retained);
      await page.locator('#r-link-composer .selection-technical > summary').click();
      await page.locator('#r-link-passage-id').fill('Retained draft passage');
      await page.locator('#r-link-rationale').fill('Retained draft rationale');
      await page.locator('#r-link-relation').selectOption('qualifies');
      if (await empty.locator('[data-load-evidence]').count()) await empty.locator('[data-load-evidence]').click();
      await action.click();
      await expect(page.locator('#r-link-claim-select')).toHaveValue(server.fixture.ids.retained);
      await expect(page.locator('#r-link-passage-id')).toHaveValue('Retained draft passage');
      await expect(page.locator('#r-link-rationale')).toHaveValue('Retained draft rationale');
      await expect(page.locator('#r-link-relation')).toHaveValue('qualifies');
      await expect(page.locator('#r-link-claim-select')).toBeFocused();
      if (locale === 'en') {
        for (const state of ['withdrawn', 'unavailable', 'historical']) {
          const panel = page.locator('[id="claim-evidence-' + server.fixture.ids[state] + '"]');
          await panel.locator('[data-load-evidence]').click();
          await expect(panel).not.toContainText(labels.research_loading_evidence);
          await expect(panel).not.toContainText(labels.research_no_linked_evidence);
          await expect(panel.locator('[data-link-claim-evidence]')).toHaveCount(0);
          if (state !== 'historical') await expect(panel).toContainText(labels[state === 'withdrawn' ? 'research_evidence_withdrawn_context' : 'research_evidence_unavailable']);
          else await expect(panel).toContainText('Linked to earlier claim version 1');
        }
        for (const failure of ['failed', 'malformed', 'null-row', 'primitive-row', 'array-row', 'object-quote', 'object-revision']) {
          await page.reload();
          await page.locator('#tab-view-research').click(); await openClaims(page);
          evidenceRead = 'held'; held = false;
          await empty.locator('[data-load-evidence]').click();
          await expect.poll(() => held).toBe(true);
          await expect(empty).toContainText(labels.research_loading_evidence);
          await expect(empty).not.toContainText(labels.research_no_linked_evidence);
          evidenceRead = failure; release();
          await expect(empty).not.toContainText(labels.research_loading_evidence);
          await expect(empty).not.toContainText(labels.research_no_linked_evidence);
          await expect(empty.locator('[data-load-evidence]')).toBeVisible();
          evidenceRead = 'native';
          await empty.locator('[data-load-evidence]').click();
          await expect(action).toBeVisible();
        }
        // A visible evidence read survives an unchanged accepted catalogue.
        await page.reload();
        await page.locator('#tab-view-research').click(); await openClaims(page);
        await page.evaluate(id => {
          window.claimActionPreviousItem = researchClaimCardItems.find(item => item.id === id);
          window.claimActionRenders = 0;
          const render = renderResearchClaimCards;
          renderResearchClaimCards = function() {++window.claimActionRenders; return render();};
        }, server.fixture.ids.empty);
        await page.locator('[data-rtab=dossiers]').click();
        holdCatalogue = true; catalogueHeld = false;
        await page.locator('[data-rtab=claims]').click();
        await expect.poll(() => catalogueHeld).toBe(true);
        evidenceRead = 'held'; held = false;
        await empty.locator('[data-load-evidence]').click();
        await expect.poll(() => held).toBe(true);
        const beforeCatalogue = await page.evaluate(() => window.claimActionRenders);
        holdCatalogue = false; releaseCatalogue();
        await expect.poll(() => page.evaluate(() => window.claimActionRenders)).toBeGreaterThan(beforeCatalogue);
        await expect(empty).toContainText(labels.research_loading_evidence);
        assert.equal(await page.evaluate(id => researchClaimCardItems.find(item => item.id === id) === window.claimActionPreviousItem,
          server.fixture.ids.empty), true, 'Unchanged accepted catalogue keeps the evidence read owner');
        evidenceRead = 'native'; release();
        await expect(action).toBeVisible();
        await page.locator('[data-rtab=dossiers]').click(); await openClaims(page);
        await expect(action).toBeVisible();
        // Any changed archive snapshot invalidates evidence, even if the claim
        // bytes match: source lifecycle and evidence links can change separately.
        catalogueSnapshot = 'changed';
        await page.locator('[data-rtab=dossiers]').click(); await openClaims(page);
        await expect(empty.locator('[data-load-evidence]')).toBeVisible();
        evidenceRead = 'held'; held = false;
        await empty.locator('[data-load-evidence]').click();
        await expect.poll(() => held).toBe(true);
        catalogueSnapshot = 'native';
        await page.locator('[data-rtab=dossiers]').click(); await openClaims(page);
        await expect(empty.locator('[data-load-evidence]')).toBeVisible();
        const releasedRead = page.waitForResponse(response => new URL(response.url()).searchParams.get('claim_id') === server.fixture.ids.empty);
        evidenceRead = 'native'; release(); await releasedRead;
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
        await expect(empty.locator('[data-load-evidence]')).toBeVisible();
        await expect(action).toHaveCount(0);
        await empty.locator('[data-load-evidence]').click();
        await expect(action).toBeVisible();
        catalogueSnapshot = 'missing';
        await page.locator('[data-rtab=dossiers]').click(); await page.locator('[data-rtab=claims]').click();
        await expect.poll(() => page.evaluate(() => researchClaimsSnapshot)).toBe(null);
        await expect(empty.locator('[data-load-evidence]')).toBeVisible();
        await empty.locator('[data-load-evidence]').click(); await expect(action).toBeVisible();
        const beforeMissingRefresh = await page.evaluate(() => window.claimActionRenders);
        await page.locator('[data-rtab=dossiers]').click(); await page.locator('[data-rtab=claims]').click();
        await expect.poll(() => page.evaluate(() => window.claimActionRenders)).toBeGreaterThan(beforeMissingRefresh);
        await expect(empty.locator('[data-load-evidence]')).toBeVisible();
        catalogueSnapshot = 'native';
        // A read-only embedding can inspect evidence without advertising a save flow.
        await page.route(server.fixture.url + '/', route => route.fulfill({contentType: 'text/html',
          body: fs.readFileSync(path.join(artifacts, locale + '.html'), 'utf8').replace(/data-research-token="[^"]+"/, 'data-research-token=""')}));
        await page.reload(); await page.locator('#tab-view-research').click(); await openClaims(page);
        await empty.locator('[data-load-evidence]').click();
        await expect(empty).toContainText(labels.research_no_linked_evidence);
        await expect(empty.locator('button')).toHaveCount(0);
      }
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${locale}/${width}: no page overflow`);
      assert.deepEqual(errors, []); assert.deepEqual(writes, []); assert.deepEqual(external, []);
      await page.close();
    }
    console.log('Claim evidence actions: native empty guidance, claim navigation, drafts, seven locales, desktop/mobile, read-only, loading/error retry and historical evidence passed. Screenshots: ' + artifacts);
  } finally {
    if (browser) await browser.close();
    await server.close();
    for (const locale of ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl']) {
      fs.rmSync(path.join(artifacts, locale + '.html'), {force: true});
    }
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
