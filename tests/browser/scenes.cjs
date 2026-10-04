const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '../..');
const fixtures = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
import json
from lixity import api
text = '## Sample <svg onload="window.injected=1">\\n\\nA door shuts.\\n\\n---\\n\\n' + 'A report was recorded. ' * 30
settings = {'scene_analysis': {'assignments': {'1:1': '<b>close</b>', '1:2': 'formal'},
    'groups': {'<b>close</b>': {'targets': {'asl': [2, 6]}}, 'formal': {'targets': {'hd_d': [0.2, 0.8]}}}}}
print(json.dumps({language: api.dashboard(text, language=language, project_config=settings)
    for language in ('de', 'en', 'fr', 'es', 'it', 'pt', 'nl')}))
`], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8', maxBuffer: 12*1024*1024});
assert.equal(fixtures.status, 0, fixtures.stderr);
const documents = JSON.parse(fixtures.stdout);
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-scenes-ui-'));

(async () => {
  const browser = await launchChromium();
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let document;
    await page.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: document}));
    for (const [language, html] of Object.entries(documents)) {
      document = html;
      for (const width of [1440, 320]) {
        await page.setViewportSize({width, height: 900});
        await page.goto('http://lixity.test/');
        assert.equal(await page.locator('#scenes details').count(), 2);
        assert.equal(await page.locator('#scenes svg, #scenes b').count(), 0);
        assert.equal(await page.evaluate(() => window.injected), undefined);
        const summary = page.locator('#scenes summary').first();
        await summary.focus();
        await page.keyboard.press('Enter');
        assert.equal(await page.locator('#scenes details[open]').count(), 1);
        assert.equal(await page.locator('#scenes details[open] tbody tr').count(), 16);
        for (const cell of await page.locator('#scenes details[open] td, #scenes details[open] thead th:not(:first-child)').all()) {
          assert.equal(await cell.evaluate(element => {
            const range = document.createRange();
            range.selectNodeContents(element);
            return range.getClientRects().length;
          }), 1, 'Values and comparison headers stay on one readable line');
        }
        const wrap = page.locator('#scenes details[open] .table-wrap');
        assert.equal(await wrap.getAttribute('tabindex'), '0');
        await wrap.focus();
        if (width === 320) {
          assert.ok(await wrap.evaluate(el => el.scrollWidth > el.clientWidth));
          await page.keyboard.press('ArrowRight');
          await page.waitForFunction(() => document.querySelector('#scenes details[open] .table-wrap').scrollLeft > 0);
        }
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), language + ' ' + width);
        assert.ok(!await page.locator('#scenes').textContent().then(text => /scene_(support|value|range|guidance)|panel_scenes|\{min_tokens\}/.test(text)));
        await page.locator('#scenes').screenshot({path: path.join(artifacts, `${language}-${width}.png`)});
      }
    }
    assert.deepEqual(errors, []);
    console.log('Scenes: real values, inert labels, keyboard details, scrolling tables, seven locales and desktop/mobile passed. ' + artifacts);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
