const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-scenes-ui-'));
const fixtures = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
import json, sys
from pathlib import Path
from lixity import api
text = '## Sample <svg onload="window.injected=1">\\n\\nA door shuts.\\n\\n---\\n\\n' + 'A report was recorded. ' * 30
settings = {'scene_analysis': {'assignments': {'1:1': '<b>close</b>', '1:2': 'formal', '3:1': 'formal'},
    'planned': ['3:1'],
    'groups': {'<b>close</b>': {'targets': {'asl': [2, 6]}}, 'formal': {'targets': {'hd_d': [0.2, 0.8]}}}}}
languages = ('de', 'en', 'fr', 'es', 'it', 'pt', 'nl')
pending = {'scene_analysis': {'assignments': {'2:1': '<b>planned</b>'},
    'planned': ['2:1'], 'groups': {'<b>planned</b>': {}}}}
documents = {}
for kind, source, config in (('measured', text, settings),
                             ('planned', '## Draft\\n\\nA quiet draft starts here.', pending)):
    documents[kind] = {}
    for language in languages:
        target = Path(sys.argv[1]) / f'{kind}-{language}.html'
        target.write_text(api.dashboard(source, language=language, project_config=config), encoding='utf-8')
        documents[kind][language] = str(target)
print(json.dumps(documents))
`, artifacts], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8', maxBuffer: 1024*1024});
assert.equal(fixtures.status, 0, fixtures.error || fixtures.stderr);
const documents = JSON.parse(fixtures.stdout);

(async () => {
  const browser = await launchChromium();
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let document;
    await page.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: document}));
    for (const [language, filename] of Object.entries(documents.measured)) {
      document = fs.readFileSync(filename, 'utf8');
      for (const width of [1440, 320]) {
        await page.setViewportSize({width, height: 900});
        await page.goto('http://lixity.test/');
        assert.equal(await page.locator('#scenes .scene-detail').count(), 2);
        assert.equal(await page.locator('#scenes .scene-planned').count(), 1);
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
    for (const [language, filename] of Object.entries(documents.planned)) {
      document = fs.readFileSync(filename, 'utf8');
      for (const width of [1440, 320]) for (const theme of ['light', 'dark']) {
        await page.setViewportSize({width, height: 900});
        await page.emulateMedia({colorScheme: theme, reducedMotion: 'reduce'});
        await page.goto('http://lixity.test/');
        const plans = page.locator('#scenes .scene-planned');
        const summary = plans.locator('summary');
        assert.equal(await plans.locator('table, [data-jump], b').count(), 0,
          'Plans have no fabricated measurements or nonexistent chapter links');
        await summary.focus();
        await page.keyboard.press('Enter');
        assert.equal(await plans.getAttribute('open'), '');
        assert.equal(await plans.locator('li').textContent(), '2:1 · <b>planned</b>');
        assert.equal(await plans.locator('p').isVisible(), true);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        const bounds = await plans.boundingBox();
        assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= width + 1);
        await page.locator('#scenes').screenshot({path: path.join(artifacts, `planned-${language}-${width}-${theme}.png`)});
        await page.keyboard.press('Enter');
        assert.equal(await plans.getAttribute('open'), null, 'The same control collapses plans');
        assert.equal(await summary.evaluate(element => element === document.activeElement), true);
      }
    }
    assert.deepEqual(errors, []);
    console.log('Scenes: real values and separate reversible plans, inert labels, keyboard details, scrolling tables, seven locales and desktop/mobile passed. ' + artifacts);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
