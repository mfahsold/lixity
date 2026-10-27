// Shared workbench journeys preserve document identity across optional tools.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-workbench-'));
const fixtures = pythonFixture(`
import json
from dashboard_fixtures import full_dashboard
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
original = full_dashboard.__globals__['render_dashboard']
full_dashboard.__globals__['SAMPLE'] += '\\n\\n## Reading continuity\\n\\n' + '\\n\\n'.join(
    'Synthetic paragraph %d. ' % number + 'A quiet garden gives this scene a place to continue. ' * 6
    for number in range(40))
result = {}
for locale in ('en', 'de'):
    def render(*args, **kwargs):
        return original(*args, **{**kwargs,
            'labels': {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]},
            'language_key': locale, 'enabled_actions': ['analyze', 'research-reader'],
            'manuscript_pdf_token': 'synthetic-project', 'research_context_token': 'synthetic-research',
            'manuscript_source_sha256': 'a' * 64})
    full_dashboard.__globals__['render_dashboard'] = render
    result[locale] = full_dashboard()
print(json.dumps(result))
`, {root});
const dossier = {id: 'garden', project_id: 'synthetic-project', title: 'Garden context',
  revision: 1, body: '## Garden\n\nA saved synthetic note.', sections: ['Garden'],
  citations: [], tags: [], claims: []};

async function createPage(browser, html, width) {
  const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion: 'reduce'});
  const errors = [], writes = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('http://lixity.test/**', route => {
    const url = new URL(route.request().url());
    if (route.request().method() !== 'GET') {
      writes.push(url.pathname);
      return route.fulfill({status: 400, json: {ok: false, message: 'No reading writes'}});
    }
    if (url.pathname === '/api/research/dossiers') return route.fulfill({json:
      url.searchParams.has('id') ? {ok: true, ...dossier}
        : {ok: true, project_id: dossier.project_id, dossiers: [dossier]}});
    if (url.pathname.startsWith('/api/')) return route.fulfill({json: {
      ok: true, initialized: true, project_id: dossier.project_id, snapshot: 'synthetic-snapshot',
      records: [], sources: [], dossiers: [dossier], claims: [], decisions: [], candidates: [], links: [],
    }});
    return route.fulfill({contentType: 'text/html', body: html});
  });
  await page.goto('http://lixity.test/');
  await page.locator('#tab-view-analysis').click();
  return {page, errors, writes};
}

async function settle(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}
async function documentState(page) {
  return page.locator('#chapters .ptext').evaluateAll(nodes => nodes.map(node => ({
    id: node.id, hash: node.dataset.paragraphSha256, start: node.dataset.start, end: node.dataset.end,
    text: node.querySelector('.ptext-inner > p')?.textContent,
  })));
}

(async () => {
  const browser = await launchChromium();
  try {
    for (const [locale, html] of Object.entries(fixtures)) for (const width of [1440, 320]) {
      const {page, errors, writes} = await createPage(browser, html, width);
      const toggle = page.locator('#manuscript-analysis-toggle');
      assert.equal(await toggle.count(), 1, 'Analysis has one explicit visible display control');
      assert.equal(await toggle.getAttribute('aria-pressed'), 'false');
      const name = await toggle.getAttribute('aria-label');
      assert.ok(name && (await toggle.textContent()).trim(), 'State is named in the interface');
      const original = await documentState(page);
      await page.locator('#workbench-overview-open').click();
      await page.locator('#workbench-overview-back').click();
      await settle(page);
      assert.equal(await toggle.getAttribute('aria-pressed'), 'false',
        'A temporary overview returns to the previous analysis-layer preference');
      await page.locator('#chapters .ptext').nth(25).scrollIntoViewIfNeeded();
      const currentPassage = await page.evaluate(() => LixityReader.capture().panel.id);
      const prose = page.locator('#' + currentPassage + ' .ptext-inner > p');
      const beforeAnalysis = await prose.boundingBox();
      const beforeToggle = await toggle.boundingBox();
      const beforeNavigation = await page.locator('#workspace-navigation-toggle').getAttribute('aria-expanded');
      await toggle.click();
      await settle(page);
      assert.equal(await page.locator('#workspace-context-panel').isVisible(), false,
        'The analysis layer does not implicitly open a context tool');
      const afterAnalysis = await prose.boundingBox();
      assert.ok(Math.abs((await toggle.boundingBox()).width - beforeToggle.width) <= 1,
        'The On/Off switch keeps its width across state labels and selected type weight');
      for (const key of ['x', 'y', 'width', 'height']) assert.ok(
        Math.abs(beforeAnalysis[key] - afterAnalysis[key]) <= 2,
        `Revealing analysis preserves prose ${key}, without rewrapping or moving its passage`);
      assert.equal(await page.locator('#workspace-navigation-toggle').getAttribute('aria-expanded'), beforeNavigation,
        'Revealing analysis preserves the navigation arrangement');
      assert.equal(await toggle.getAttribute('aria-pressed'), 'true');
      assert.equal(await toggle.getAttribute('aria-label'), name, 'A toggle keeps its accessible name');
      if (width === 320) {
        await page.locator('#' + currentPassage + ' [data-reader-paragraph]').click();
        await page.locator('[data-reader-action=values]').click();
        await settle(page);
        await toggle.focus();
        await toggle.press('Space'); await settle(page);
        assert.equal(await toggle.evaluate(node => document.activeElement === node), true,
          'Hiding analysis with its keyboard toggle retains that toggle focus');
        await toggle.press('Space');
        assert.equal(await toggle.getAttribute('aria-pressed'), 'true');
        assert.equal(await page.locator('#manuscript-context-menu').isVisible(), false,
          'A second Space reverses Analysis rather than opening paragraph actions');
      }
      await page.locator('#workspace-reader-toggle').click();
      await page.locator('#workspace-reader-dossier').selectOption('garden');
      await page.locator('#workspace-reader-body h3').waitFor();
      await toggle.click();
      assert.equal(await toggle.getAttribute('aria-pressed'), 'false');
      assert.equal(await page.locator('#workspace-reader-panel').isVisible(), true,
        'Hiding analysis preserves a separately selected dossier');
      await toggle.click();
      assert.equal(await page.locator('#workspace-reader-panel').isVisible(), true);
      // Return from a relation route requests the document even if it is already active.
      await page.locator('#tab-view-research').click();
      await page.locator('#tab-view-analysis').click();
      await page.evaluate(() => LixityWorkbench.dispatch({type: 'surface', value: 'document'}));
      assert.equal(await page.locator('#workspace-reader-panel').isVisible(), true,
        'Resuming an already active document preserves its dossier');
      await page.locator('#chapters .ptext').nth(25).scrollIntoViewIfNeeded();
      const passageOrigin = await page.evaluate(() => { const anchor = LixityReader.capture(); return {id: anchor.panel.id, top: anchor.top}; });
      await page.locator('#workbench-overview-open').click();
      assert.equal(await page.locator('#manuscript-analysis-panels').isVisible(), true);
      const overviewHeading = await page.locator('#analysis-review h2').boundingBox();
      assert.ok(overviewHeading.y >= 0 && overviewHeading.y + overviewHeading.height <= 900,
        'Opening the overview from a deep passage starts at its first review heading');
      assert.equal(await page.locator('#workbench-overview-back').isVisible(), true);
      await page.locator('#analysis-sections [data-section-link]').last().click();
      await page.locator('#workbench-overview-back').click();
      await settle(page);
      assert.ok(Math.abs(await page.locator('#' + passageOrigin.id).evaluate(node => node.getBoundingClientRect().top) - passageOrigin.top) <= 2,
        'Overview section navigation preserves the original passage return');
      assert.equal(await page.locator('#workspace-reader-panel').isVisible(), true,
        'Overview return restores the document context tool');
      await page.locator('#chapters .ptext').nth(25).scrollIntoViewIfNeeded();
      const offOrigin = await page.evaluate(() => { const anchor = LixityReader.capture(); return {id: anchor.panel.id, top: anchor.top}; });
      await page.locator('#workbench-overview-open').click();
      await page.locator('#analysis-sections [data-section-link]').last().click();
      assert.equal(await toggle.isVisible(), false, 'Analysis marks are controlled from the document surface');
      await page.locator('#workbench-overview-back').click();
      await toggle.click(); await settle(page);
      assert.ok(Math.abs(await page.locator('#' + offOrigin.id).evaluate(node => node.getBoundingClientRect().top) - offOrigin.top) <= 2,
        'Returning from overview and hiding analysis preserves the original passage');
      assert.equal(await page.locator('#workspace-reader-panel').isVisible(), true);
      await page.locator('#workspace-reader-close').click();

      const first = page.locator('#chapters .ptext').first();
      await first.locator('[data-reader-paragraph]').click();
      await page.locator('[data-reader-action=values]').click();
      await page.locator('#reader-settings > summary').click();
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#reader-settings').evaluate(node => node.open), false,
        'Escape closes appearance before the underlying context dock');
      assert.equal(await page.locator('#reader-inspector').isVisible(), true);
      await page.locator('#tab-view-research').click();
      await page.locator('[data-rtab=claims]').click();
      const composer = page.locator('#r-claim-composer');
      await composer.locator('summary').first().click();
      await composer.locator('[data-close-disclosure]').focus();
      await page.keyboard.press('Escape');
      assert.equal(await composer.evaluate(node => node.open), false,
        'One Escape closes the active disclosure, not a hidden manuscript tool');
      await page.locator('#tab-view-analysis').click();
      await page.locator('#reader-inspector-close').click();

      await page.locator('#chapters .ptext').nth(25).scrollIntoViewIfNeeded();
      await settle(page);
      assert.equal(await toggle.isVisible(), true);
      const rect = await toggle.boundingBox();
      assert.ok(rect.y >= 0 && rect.y + rect.height <= 900, 'Analysis reversal remains in the viewport');
      await toggle.click();
      assert.deepEqual(await documentState(page), original, 'Analysis and tools preserve exact source text/anchors');
      assert.deepEqual(writes, []); assert.deepEqual(errors, []);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      await page.screenshot({path: path.join(artifacts, `${locale}-${width}.png`)});
      await page.close();
    }
    console.log(`Workbench journeys passed; screenshots: ${artifacts}`);
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
