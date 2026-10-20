// Structural reading remains searchable without acquiring analysis/claim anchors.
const assert = require('node:assert/strict');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const root = path.resolve(__dirname, '../..');
const html = pythonFixture(`
import json
from dashboard_fixtures import full_dashboard
from lixity.models import CorpusConfig
from lixity.ui.manuscript_document import reader_blocks
full_dashboard.__globals__['SAMPLE'] = '''# A voyage

Preface unique.

## Departure

A quiet garden gives this sentence a place to begin.

### At the quay

> İ A quotation unique.

[^n]: A note unique.

## Empty

## Anmerkungen und Literaturverzeichnis

Appendix unique.

~~~
<img src=https://example.test/never>
~~~
'''
original = full_dashboard.__globals__['render_dashboard']
def render(*args, **kwargs):
    return original(*args, **{**kwargs, 'reader_document': reader_blocks(full_dashboard.__globals__['SAMPLE'], CorpusConfig(), args[1])})
full_dashboard.__globals__['render_dashboard'] = render
print(json.dumps(full_dashboard()))
`, {root});
(async () => {
  const browser = await launchChromium();
  try {
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion: 'reduce'});
      const requests = [], errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: html}));
      page.on('request', request => {if (request.url().includes('example.test')) requests.push(request.url());});
      await page.goto('http://lixity.test/');
      await page.locator('#tab-view-analysis').click();
      const main = page.locator('#chapters');
      assert.match(await main.innerText(), /Preface unique/);
      assert.match(await main.innerText(), /quotation unique/);
      assert.match(await main.innerText(), /note unique/);
      assert.match(await main.innerText(), /Appendix unique/);
      assert.equal(await main.locator('.ptext').count(), 1);
      assert.equal(await main.locator('img, script').count(), 0);
      assert.equal(await main.locator('.reader-structural [data-reader-paragraph]').count(), 0);
      const original = await main.locator('.ptext p').textContent();
      const field = page.locator('#text-search');
      for (const query of ['Preface unique', 'quotation unique', 'note unique', 'Appendix unique']) {
        await field.fill(query); await field.press('Enter');
        assert.equal(await main.locator('.reader-structural:not(.text-miss)').count(), 1);
        assert.equal(await main.locator('.reader-structural:not(.text-miss)').isVisible(), true);
        assert.equal(await main.locator('.reader-structural:not(.text-miss) mark').textContent(), query,
          'Structural search marks the original substring after case-fold-expanding characters');
        await field.press('Escape');
      }
      await page.locator('#reader-chapter').selectOption({label: 'Empty'});
      assert.equal(await main.locator('h2').filter({hasText: 'Empty'}).isVisible(), true);
      assert.equal(await main.locator('.ptext p').textContent(), original);
      assert.deepEqual(requests, []); assert.deepEqual(errors, []);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.close();
    }
    console.log('Source-order structural reader/search/coverage passed at1440/320.');
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
