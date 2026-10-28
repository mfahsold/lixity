// Declared chapter groups change comparison display, never the measured book.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), os = require('node:os');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-analysis-scope-'));
const fixtures = pythonFixture(`
import json
from lixity.api import dashboard
from lixity.language import get_language_profile
from tests.locales import LOCALES
text = "\\n\\n".join(f"## Chapter {n}\\n\\n" + (("moss " * length).strip() + ". ") * 20
                       for n, length in enumerate((8, 9, 10, 11, 70), 1))
settings = {"register_profiles": {'Letters <img src=x onerror="window.scopeInjected=true">': {}},
            "chapter_registers": {"2": 'Letters <img src=x onerror="window.scopeInjected=true">',
                                   "4": 'Letters <img src=x onerror="window.scopeInjected=true">'},
            "characters": {'Alex <script>': {"pov_in_chapters": [1, 3]},
                           "Robin": {"pov_in_chapters": [3, 5]}, "Mention only": {"aliases": ["moss"]}}}
print(json.dumps({locale: {"html": dashboard(text, language=locale, title="Synthetic chapter groups", project_config=settings),
                         "status": get_language_profile(locale).labels["analysis_scope_status"]}
                  for locale in LOCALES}))
`, {root});

(async () => {
  const browser = await launchChromium();
  try {
    for (const [locale, fixture] of Object.entries(fixtures)) {
      for (const width of [1440, 320]) {
        const page = await browser.newPage({viewport: {width, height: width === 320 ? 480 : 1000},
          reducedMotion: width === 320 ? 'reduce' : 'no-preference',
          colorScheme: width === 320 ? 'dark' : 'light', hasTouch: width === 320});
        page.setDefaultTimeout(7000);
        const errors = [], writes = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('console', message => {if (['error', 'warning'].includes(message.type())) errors.push(message.text());});
        await page.route('http://lixity.test/**', route => {
          if (route.request().method() !== 'GET') writes.push(route.request().method());
          return route.fulfill({contentType: 'text/html', body: fixture.html});
        });
        await page.goto('http://lixity.test/?scope=synthetic');
        assert.match(await page.title(), /^Synthetic chapter groups/);
        await page.locator('#style-tab-heatmap').click();
        assert.equal(await page.locator('#analysis-scope').isVisible(), true);
        const register = page.locator('#analysis-scope-register'), pov = page.locator('#analysis-scope-pov');
        const fdr = page.locator('#heatmap-fdr-only');
        const rows = page.locator('#heatmap tbody tr[data-chapter-num]');
        const visible = () => rows.evaluateAll(nodes => nodes.filter(node => !node.hidden).map(node => Number(node.dataset.chapterNum)));
        const measured = () => page.evaluate(() => ({
          rows: Array.from(document.querySelectorAll('#heatmap tbody tr')).map(row => ({
            chapter: row.dataset.chapterNum, fdr: row.dataset.fdrCount,
            cells: Array.from(row.cells).map(cell => ({text: cell.textContent, title: cell.title,
              chapter: cell.dataset.chapter, layer: cell.dataset.layer})),
          })),
          bands: document.querySelector('#bands').innerHTML,
          globalCounts: document.querySelector('#heatmap > .hint').textContent,
          prose: paragraphContent,
        }));
        const before = await measured();
        assert.deepEqual(await visible(), [1, 2, 3, 4, 5]);
        assert.equal(await register.locator('option').count(), 3);
        assert.equal(await pov.locator('option').count(), 3, 'Name mentions create no inferred POV group');
        await register.selectOption('r-0');
        assert.deepEqual(await visible(), [2, 4]);
        await pov.selectOption('p-0');
        assert.deepEqual(await visible(), [], 'Independent declarations combine by intersection');
        assert.equal(await page.locator('#heatmap-empty').isVisible(), true);
        const expectedEmpty = fixture.status.replace('{shown}', '0').replace('{total}', '5');
        assert.equal(await page.locator('#analysis-scope-status').textContent(), expectedEmpty);
        await register.selectOption('');
        assert.deepEqual(await visible(), [1, 3]);
        await pov.selectOption('p-1');
        assert.deepEqual(await visible(), [3, 5]);
        await fdr.check();
        assert.deepEqual(await visible(), [5]);
        await register.selectOption('r-0');
        assert.deepEqual(await visible(), []);
        await fdr.uncheck();
        assert.deepEqual(await visible(), [], 'Changing FDR cannot overwrite the group intersection');
        await pov.selectOption('');
        assert.deepEqual(await visible(), [2, 4]);
        await fdr.check();
        assert.deepEqual(await visible(), [], 'Registered chapter exemption remains in effect');
        await page.locator('#analysis-scope-reset').click();
        assert.deepEqual(await visible(), [1, 2, 3, 4, 5]);
        assert.equal(await fdr.isChecked(), false);
        assert.equal(await register.inputValue(), '');
        assert.equal(await pov.inputValue(), '');
        await register.selectOption('unassigned');
        assert.deepEqual(await visible(), [1, 3, 5]);
        await page.evaluate(() => {location.hash = 'heatmap-ch-2';});
        await page.waitForFunction(() => !document.querySelector('#heatmap-ch-2').hidden);
        assert.equal(await register.inputValue(), '', 'A genuine fragment reveals a filtered-out comparison row');
        assert.equal(await page.evaluate(() => location.hash), '#heatmap-ch-2');
        await pov.selectOption('p-0');
        await page.evaluate(() => scrollAndFlash(document.getElementById('heatmap-ch-4'), {behavior: 'auto'}));
        assert.equal(await pov.inputValue(), '', 'Existing programmatic jumps use the same reveal owner');
        assert.deepEqual(await measured(), before, 'Display filters preserve all measured content and book-reference rendering');
        assert.equal(await page.locator('#chapters .chapter[hidden]').count(), 0, 'The continuous manuscript is not filtered');
        assert.equal(await page.evaluate(() => Boolean(window.scopeInjected)), false);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
        assert.deepEqual(errors, []);
        assert.deepEqual(writes, []);
        if (locale === 'de') {
          await page.locator('#analysis-scope').scrollIntoViewIfNeeded();
          await page.screenshot({path: path.join(artifacts, `scope-${width}.png`), animations: 'disabled'});
        }
        await page.close();
      }
    }
    console.log(`Analysis scope: ${Object.keys(fixtures).length} locales × desktop/short mobile, declared groups/FDR/reset/fragment/jump/source/reference checks passed; ${artifacts}`);
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
