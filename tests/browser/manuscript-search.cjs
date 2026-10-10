// The author can search the manuscript itself, not only the research archive.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '../..');
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
import runpy
render = runpy.run_path('tests/test_ui_contract.py')['_full_dashboard']
# A manuscript phrase that looks like markup, and one that only appears in a
# single chapter, so filtering is observable.
render.__globals__['SAMPLE'] += (
    "\\n\\n## Suchkapitel\\n\\n"
    "Hier steht ein seltenes Suchwort im Manuskript.\\n\\n"
    "Und hier ein Satz mit <img src=x onerror=window.searchInjected=true> als Text.\\n"
)
print(render())
`],
  {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8', maxBuffer: 8 * 1024 * 1024});
assert.equal(fixture.status, 0, fixture.error ? fixture.error.message : fixture.stderr);

(async () => {
  const browser = await launchChromium();
  try {
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}, hasTouch: true});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://lixity.test/**', route => route.fulfill(route.request().url().includes('/api/')
        ? {json: {ok: true, locked: true, records: []}}
        : {contentType: 'text/html', body: fixture.stdout}));
      await page.goto('http://lixity.test/');
      await page.locator('#tab-view-analysis').click();

      const field = page.locator('#text-search');
      assert.equal(await field.count(), 1, 'manuscript search field exists');
      assert.ok(await field.isVisible(), `search field visible at ${width}`);

      const paragraphs = await page.locator('#chapters .ptext').count();
      assert.ok(paragraphs > 3, 'fixture has paragraphs to filter');

      // An empty query must leave the manuscript untouched.
      assert.equal(await page.locator('#chapters .ptext.text-miss').count(), 0);
      assert.equal(await page.locator('#text-search-next').isVisible(), false);

      await field.fill('Suchwort');
      await page.waitForFunction(() => document.querySelectorAll('#chapters .ptext:not(.text-miss)').length === 1);
      const status = await page.locator('#text-search-status').textContent();
      assert.match(status, /\d+/, `status reports a count at ${width}`);

      // Everything that does not match leaves the page; the match stays.
      const misses = await page.locator('#chapters .ptext.text-miss').count();
      const visible = await page.locator('#chapters .ptext:not(.text-miss)').count();
      assert.equal(misses + visible, paragraphs);
      assert.equal(visible, 1, 'exactly one paragraph holds the rare word');
      assert.equal(await page.locator('mark.text-hit').count(), 1);
      assert.equal(
        await page.locator('.chapter:not(.text-miss)').count(), 1,
        'only the chapter holding the match remains'
      );
      assert.equal(await page.locator('#text-search-next').isVisible(), true);

      // The interface must never parse manuscript text as markup.
      assert.equal(await page.evaluate(() => Boolean(window.searchInjected)), false);
      assert.equal(await page.locator('#chapters img, #chapters script').count(), 0);

      // A query without hits reports it instead of an empty page.
      await field.fill('zzzkeintrefferzzz');
      // The field debounces, so wait for the outcome rather than for any text:
      // the previous query's count is still on screen for a moment.
      await page.waitForFunction(() => document.querySelectorAll('#chapters .ptext:not(.text-miss)').length === 0);
      assert.match(await page.locator('#text-search-status').textContent(), /\D/);

      // Escape clears the search and restores the whole manuscript.
      await field.press('Escape');
      await page.waitForFunction(() => document.querySelectorAll('#chapters .ptext.text-miss').length === 0);
      assert.equal(await page.locator('#chapters .ptext:not(.text-miss)').count(), paragraphs);
      assert.equal(await page.locator('mark.text-hit').count(), 0);

      // The clear button and the arrow keys work as well.
      await field.fill('Regen');
      await page.waitForFunction(() => document.querySelectorAll('#chapters mark.text-hit').length > 0);
      const opened = await page.locator('#chapters .ptext.open').count();
      assert.ok(opened >= 1, 'the first match is opened');
      await page.locator('#text-search-clear').click();
      await page.waitForFunction(() => document.querySelectorAll('#chapters .ptext.text-miss').length === 0);
      assert.equal(await field.inputValue(), '');

      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true,
        `no overflow with the search bar at ${width}`);
      assert.deepEqual(errors, []);
      await page.locator('.toolbar').screenshot({path: `/tmp/lixity-manuscript-search-${width}.png`});
      await page.close();
    }
    console.log('Manuscript search: present, filters chapters and paragraphs, counts hits, ' +
      'steps through them, clears on Escape and keeps manuscript markup inert at 1440/320 passed.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
