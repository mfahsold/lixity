const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
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
        const measurements = page.locator('#scenes > .scene-measurements');
        assert.equal(await measurements.getAttribute('open'), null);
        assert.equal(await page.locator('#scenes .scene-detail summary').first().isVisible(), false);
        const link = page.locator('#scenes .scene-overview a').first();
        await link.focus();
        await page.keyboard.press('Enter');
        assert.equal(await page.evaluate(() => document.activeElement.id), 'scene-metrics-1-1',
          'Opening scene measurements transfers keyboard focus to the destination');
        assert.equal(await measurements.getAttribute('open'), '');
        assert.equal(await page.locator('#scenes .scene-detail[open]').count(), 1);
        assert.equal(await page.locator('#scenes .scene-detail[open] tbody tr').count(), 16);
        for (const cell of await page.locator('#scenes .scene-detail[open] td, #scenes .scene-detail[open] thead th:not(:first-child)').all()) {
          assert.equal(await cell.evaluate(element => {
            const range = document.createRange();
            range.selectNodeContents(element);
            return range.getClientRects().length;
          }), 1, 'Values and comparison headers stay on one readable line');
        }
        const wrap = page.locator('#scenes .scene-detail[open] .table-wrap');
        assert.equal(await wrap.getAttribute('tabindex'), '0');
        if (width === 320) {
          assert.ok(await wrap.evaluate(el => el.scrollWidth > el.clientWidth));
          await page.keyboard.press('ArrowRight');
          await page.waitForFunction(() => document.querySelector('#scenes .scene-detail[open] .table-wrap').scrollLeft > 0);
        }
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), language + ' ' + width);
        assert.ok(!await page.locator('#scenes').textContent().then(text => /scene_(support|value|range|guidance)|panel_scenes|\{min_tokens\}/.test(text)));
        await page.locator('#scenes').screenshot({path: path.join(artifacts, `${language}-${width}.png`)});
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('#scenes .scene-detail[open]').count(), 0);
        assert.equal(await measurements.getAttribute('open'), '');
        assert.equal(await page.locator('#scenes .scene-detail summary').first().evaluate(el => el === document.activeElement), true);
        await page.keyboard.press('Escape');
        assert.equal(await measurements.getAttribute('open'), null);
        assert.equal(await measurements.locator(':scope > summary').evaluate(el => el === document.activeElement), true);
        await link.focus(); await page.keyboard.press('Enter');
        await page.keyboard.press('Tab');
        assert.equal(await page.locator('#scenes .scene-detail[data-scene="1:2"] > summary')
          .evaluate(el => el === document.activeElement), true,
        'Tab continues from the opened measurements to the next scene summary');
        await page.keyboard.press('Shift+Tab');
        assert.equal(await page.evaluate(() => document.activeElement.id), 'scene-metrics-1-1');
        await page.keyboard.press('Escape'); await page.keyboard.press('Escape');
        // The ordinary href reveals nested measurements without application JavaScript.
        const context = await browser.newContext({javaScriptEnabled: false, viewport: {width, height: 900}});
        try {
          const plain = await context.newPage();
          await plain.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: document}));
          await plain.goto('http://lixity.test/');
          await plain.locator('#scenes .scene-overview a').last().click();
          assert.equal(await plain.locator('#scenes > .scene-measurements').getAttribute('open'), '');
          assert.equal(await plain.locator('#scenes .scene-detail[data-scene="1:2"]').getAttribute('open'), '');
          assert.equal(await plain.locator('#scene-metrics-1-2 table').isVisible(), true);
        } finally { await context.close(); }
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
    await nativeLongScenes(browser);
    assert.deepEqual(errors, []);
    console.log('Scenes: real values and separate reversible plans, inert labels, keyboard details, scrolling tables, seven locales and desktop/mobile passed. ' + artifacts);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});

async function nativeLongScenes(browser) {
  const directory = path.join(artifacts, 'native-project');
  fs.mkdirSync(directory);
  const server = await startNativeServer(String.raw`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
project = Path(sys.argv[1])
manuscript = project / 'manuscript.md'
chapters = []
for number in range(1, 15):
    scenes = ['A door closed. The garden waited in the rain. ' * 25
              for _ in range(2 if number <= 5 else 1)]
    chapters.append(f'## Synthetic chapter {number}: The river garden\n\n' + '\n\n---\n\n'.join(scenes))
manuscript.write_text('\n\n'.join(chapters), encoding='utf-8')
(project / 'lixity.toml').write_text('title = "Synthetic scene navigation"\nlanguage = "en"\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}'}), flush=True)
server.serve_forever()
`, directory);
  const original = fs.readFileSync(path.join(directory, 'manuscript.md'));
  const page = await browser.newPage({reducedMotion: 'reduce'});
  const errors = [], writes = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (!['GET', 'HEAD'].includes(request.method())) writes.push(request.method()); });
  try {
    for (const width of [1440, 320]) {
      await page.setViewportSize({width, height: 900});
      await page.goto(server.fixture.url);
      assert.match(await page.title(), /Synthetic scene navigation/);
      await page.locator('#workbench-overview-open').click();
      const catalogue = page.locator('#scenes > .scene-measurements');
      assert.equal(await catalogue.getAttribute('open'), null);
      assert.equal(await page.locator('#scenes .scene-overview tbody tr').count(), 19);
      assert.equal(await catalogue.locator('.scene-detail').count(), 19);
      assert.equal(await catalogue.locator('.scene-detail summary').first().isVisible(), false);
      const overview = page.locator('#scenes .scene-overview');
      assert.equal(await overview.evaluate(element => element.clientHeight <= 416), true,
        'The complete scene overview stays inside the shared bounded table region');
      await overview.focus();
      let pageDowns = 0;
      while (pageDowns < 12 && !await overview.evaluate(element =>
        element.scrollTop + element.clientHeight >= element.scrollHeight - 1)) {
        await overview.evaluate(element => {
          element.dataset.testScrollEnded = 'false';
          element.addEventListener('scrollend', () => { element.dataset.testScrollEnded = 'true'; }, {once: true});
        });
        await page.keyboard.press('PageDown');
        await page.waitForFunction(() => document.querySelector('#scenes .scene-overview').dataset.testScrollEnded === 'true');
        pageDowns++;
      }
      assert.ok(pageDowns > 0, 'Keyboard PageDown scrolls the scene overview itself');
      assert.equal(await overview.evaluate(element => {
        const box = element.getBoundingClientRect(), last = element.querySelector('tbody tr:last-child').getBoundingClientRect();
        return last.bottom <= box.bottom + 1 && last.top >= box.top - 1;
      }), true, 'Keyboard scrolling reaches the complete final scene row');
      await overview.evaluate(element => { element.scrollTop = 0; element.scrollLeft = element.scrollWidth; });
      assert.equal(await overview.evaluate(element => {
        const box = element.getBoundingClientRect(), identity = element.querySelector('tbody th').getBoundingClientRect();
        return identity.left >= box.left - 1 && identity.right <= box.right + 1 &&
          identity.top >= box.top - 1 && identity.bottom <= box.bottom + 1;
      }), true, 'The scene identity remains fully visible after horizontal scrolling');
      const identityWidth = await overview.locator('tbody th').first().evaluate(element => element.getBoundingClientRect().width);
      assert.ok(identityWidth <= (width === 320 ? 160 : 240),
        `The identity column leaves space for measured values (${width}px viewport, ${identityWidth}px identity)`);
      assert.equal(await overview.locator('tbody tr').count(), 19, 'Scrolling preserves every scene row');
      await page.locator('#scenes').screenshot({path: path.join(artifacts, `native-${width}-closed.png`)});
      const firstLink = page.locator('#scenes .scene-overview a').first();
      await firstLink.focus(); await page.keyboard.press('Enter');
      assert.equal(await catalogue.getAttribute('open'), '');
      assert.equal(await page.locator('#scene-metrics-1-1 table').isVisible(), true);
      assert.equal(await page.evaluate(() => document.activeElement.id), 'scene-metrics-1-1',
        'Native scene navigation keeps keyboard focus at the visible measurements');
      await page.keyboard.press('Escape');
      assert.equal(await catalogue.locator('.scene-detail[open]').count(), 0);
      assert.equal(await catalogue.locator('.scene-detail[data-scene="1:1"] > summary')
        .evaluate(el => el === document.activeElement), true);
      await page.keyboard.press('Escape');
      assert.equal(await catalogue.getAttribute('open'), null);
      assert.equal(await catalogue.locator(':scope > summary').evaluate(el => el === document.activeElement), true);
      await page.locator('#scenes .scene-overview a').last().click();
      assert.equal(await page.locator('#scene-metrics-14-1 table').isVisible(), true);
      await page.locator('#scene-metrics-14-1').scrollIntoViewIfNeeded();
      await page.locator('#scene-metrics-14-1').screenshot({path: path.join(artifacts, `native-${width}-last-scene.png`)});
      // Every scene has real measurements, and opening one never closes another.
      for (const detail of await catalogue.locator('.scene-detail').all()) {
        await detail.locator('summary').focus(); await page.keyboard.press('Enter');
        if (await detail.getAttribute('open') === null) await page.keyboard.press('Enter');
        assert.equal(await detail.locator('tbody tr').count(), 16);
      }
      assert.equal(await catalogue.locator('.scene-detail[open]').count(), 19);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      const context = await browser.newContext({javaScriptEnabled: false, viewport: {width, height: 900}});
      try {
        const plain = await context.newPage();
        await plain.goto(server.fixture.url + '/#scene-metrics-14-1');
        assert.equal(await plain.locator('#scenes > .scene-measurements').getAttribute('open'), '');
        assert.equal(await plain.locator('#scenes .scene-detail[data-scene="14:1"]').getAttribute('open'), '');
        assert.equal(await plain.locator('#scene-metrics-14-1 table').isVisible(), true);
      } finally { await context.close(); }
    }
    assert.deepEqual(fs.readFileSync(path.join(directory, 'manuscript.md')), original);
    assert.deepEqual(errors, []);
    assert.deepEqual(writes, []);
  } finally { await page.close(); await server.close(); }
}
