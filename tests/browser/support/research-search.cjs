// Search interaction and literal result rendering against the generated UI.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium, playwrightModule} = require('../../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const {pythonFixture} = require('./python-fixture.cjs');

async function checkResearchSearch(browser, artifacts, mode = 'all') {
  const {html} = pythonFixture('import json\nfrom dashboard_fixtures import full_dashboard\nprint(json.dumps({"html": full_dashboard()}))');
  const quote = 'The lamp & <img src=x onerror=alert(1)> remains; café "quoted".';
  const excerpt = 'Ampersand & <draft> café; lamp &amp; text.';
  for (const width of [1440, 320]) for (const theme of ['light', 'dark']) {
    const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion: 'reduce', colorScheme: theme});
    const requests = [], errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => {if (message.type() === 'error') errors.push(message.text());});
    try {
      await page.route('http://localhost/**', route => {
        const pathname = new URL(route.request().url()).pathname;
        if (pathname.endsWith('/research-search')) {
          requests.push(route.request().postDataJSON());
          return route.fulfill({json: {ok: true, hits: [
            {kind: 'passage', passage_id: 'synthetic-passage', source_title: 'Synthetic source', verbatim: quote},
            {kind: 'dossier', record_id: 'synthetic-dossier', revision: 1, title: 'Synthetic dossier', excerpt},
          ]}});
        }
        if (pathname.includes('/api/')) return route.fulfill({json: {
          ok: true, initialized: true, project_title: 'Synthetic search archive',
          sources: [], dossiers: [], claims: [], decisions: [],
        }});
        return route.fulfill({contentType: 'text/html', body: html});
      });
      await page.goto('http://localhost/');
      await page.locator('[data-view="research"]').click();
      await expect(page.locator('#r-active-root')).toContainText('Synthetic search archive');
      await page.locator('[data-rtab="search"]').click();
      const query = page.locator('#r-search-query');
      const results = page.locator('#research-search-results');
      await query.fill('amp');
      if (mode !== 'highlight') {
        await query.press('Enter');
        await expect(results.locator('.research-passage-quote')).toHaveCount(2);
        assert.equal(requests.length, 1, 'Enter searches exactly once');
        assert.equal(requests[0].query, 'amp');
        await expect(query).toBeFocused();
        await expect(query).toHaveAccessibleName(/\S/);
      }
      const beforeClick = requests.length;
      await page.locator('#r-search-btn').click();
      await expect.poll(() => requests.length).toBe(beforeClick + 1);
      await expect(results.locator('.research-passage-quote')).toHaveCount(2);
      if (mode !== 'keyboard') {
        assert.equal(await results.locator('.research-passage-quote').nth(0).textContent(), '„' + quote + '“');
        assert.equal(await results.locator('.research-passage-quote').nth(1).textContent(), excerpt);
        assert.deepEqual(await results.locator('mark').allTextContents(), ['amp', 'Amp', 'amp', 'amp']);
        await query.fill('<img & café ;');
        await page.locator('#r-search-btn').click();
        await expect(results.locator('mark')).toContainText(['&', '<img', ';', 'café', '&', 'café', ';', '&']);
        assert.equal(await results.locator('.research-passage-quote').nth(0).textContent(), '„' + quote + '“');
        assert.equal(await results.locator('.research-passage-quote').nth(1).textContent(), excerpt);
        assert.equal(await results.locator('img, script').count(), 0, 'Source markup remains literal text');
      }
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.screenshot({path: path.join(artifacts, `research-search-${width}-${theme}.png`), fullPage: true});
      let axePath;
      try {axePath = require.resolve('axe-core');}
      catch (_) {axePath = path.join(os.homedir(), 'rosts_services/node_modules/axe-core/axe.js');}
      if (fs.existsSync(axePath)) {
        await page.evaluate(fs.readFileSync(axePath, 'utf8'));
        const audit = await page.evaluate(async () => axe.run(document.getElementById('rtab-search')));
        if (audit.violations.length) console.log(JSON.stringify(audit.violations.map(item => ({id: item.id, nodes: item.nodes.map(node => ({target: node.target, failureSummary: node.failureSummary}))}))));
        assert.deepEqual(audit.violations.map(item => item.id), [], `Search accessibility at ${width}px/${theme}`);
        console.log(`Search axe ${width}px/${theme}: ${audit.violations.length} violations, ${audit.incomplete.length} incomplete checks`);
      } else console.log('Search axe-core unavailable; automated accessibility audit skipped');
      assert.deepEqual(errors, [], 'Search renders without console or runtime errors');
    } finally {await page.close();}
  }
}

module.exports = {checkResearchSearch};

if (require.main === module) {
  (async () => {
    const artifacts = fs.mkdtempSync('/tmp/lixity-research-search-');
    const browser = await launchChromium();
    try {
      await checkResearchSearch(browser, artifacts, process.argv[2]);
      console.log('Research search checks passed; screenshots: ' + artifacts);
    } finally {await browser.close();}
  })().catch(error => {console.error(error); process.exitCode = 1;});
}
