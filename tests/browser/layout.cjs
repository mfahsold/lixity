let playwrightMod = process.env.PLAYWRIGHT_MODULE || 'playwright';
const fs = require('node:fs');
try {
  require.resolve(playwrightMod);
} catch {
  const fallback = '/home/codeai/.npm/_npx/b234c773f454f454/node_modules/playwright';
  if (fs.existsSync(fallback)) playwrightMod = fallback;
}
const {chromium} = require(playwrightMod);
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '../..');
const fixture = spawnSync(path.join(root, '.venv/bin/python'), ['-c', `
import runpy
render = runpy.run_path('tests/test_ui_contract.py')['_full_dashboard']
render.__globals__['SAMPLE'] += '\\n\\n## Dialog\\n\\n»Ich gehe zum Haus und sehe den Regen«, sagte sie.\\n' + '\\n\\nIch gehe zum Haus.\\n' * 100
print(render())
`],
  {cwd: root, encoding: 'utf8', maxBuffer: 8*1024*1024});
assert.equal(fixture.status, 0, fixture.stderr);

(async () => {
  const launchOptions = {headless: true};
  const execPath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ||
    (fs.existsSync('/usr/bin/chromium-browser') ? '/usr/bin/chromium-browser' :
     fs.existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);
  if (execPath) launchOptions.executablePath = execPath;
  const browser = await chromium.launch(launchOptions);
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://lixity.test/**', route => route.fulfill(route.request().url().includes('/api/')
      ? {json: {ok: true, locked: true, records: []}} : {contentType: 'text/html', body: fixture.stdout}));
    for (const width of [1440, 768, 390, 320]) {
      await page.setViewportSize({width, height: 900});
      await page.goto('http://lixity.test/');
      assert.ok(await page.locator('#license-terms').isVisible());
      assert.ok((await page.locator('#license-terms').textContent()).includes('self-publishing'));
      await page.locator('.license-badge').focus();
      await page.keyboard.press('Enter');
      assert.ok(page.url().endsWith('#license-terms'));
      assert.equal(await page.locator('.license-links a').count(), 2);
      await page.locator('.project-header').screenshot({path: `/tmp/lixity-license-${width}.png`});
      await page.evaluate(() => ndaRender([{id: '" data-injected="yes', name: '<img src=x onerror="window.ndaInjected=1">', contact: '<script>bad()</script>', pdf: '<svg onload="window.ndaInjected=1">', status: 'draft'}]));
      assert.equal(await page.locator('#nda-table img, #nda-table script, #nda-table svg, #nda-table [data-injected]').count(), 0);
      assert.equal(await page.locator('#nda-table [data-nda-export]').getAttribute('data-nda-export'), '" data-injected="yes');
      assert.ok(await page.locator('#nda-table').textContent().then(text => text.includes('<img src=x')));
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `page overflow at ${width}`);
      assert.equal(await page.locator('.panel > table').count(), 0);
      const panelGaps = await page.locator('.panel').evaluateAll(panels => panels.flatMap(panel => {
        const boxes = Array.from(panel.children).map(child => child.getBoundingClientRect()).filter(box => box.height > 0);
        return boxes.slice(1).map((box, index) => ({panel: panel.id, gap: box.top - boxes[index].bottom}));
      }));
      assert.ok(panelGaps.every(item => Math.abs(item.gap - 16) < 1), JSON.stringify({width, panelGaps}));
      const gap = await page.locator('#dialogue').evaluate(panel => {
        const tiles = panel.querySelector('.kpi-row').getBoundingClientRect();
        return panel.querySelector('.dist').getBoundingClientRect().top - tiles.bottom;
      });
      assert.ok(gap >= 12 && gap <= 24, `KPI/chart gap ${gap} at ${width}`);
      const headings = page.locator('#matrix th');
      assert.equal(await headings.locator('.help[data-help]').count(), await headings.count());
      await headings.locator('.help').nth(3).focus();
      await page.waitForFunction(() => document.querySelector('#lixity-tooltip').classList.contains('visible'));
      assert.match(await page.locator('#lixity-tooltip').textContent(), /sentence length/i);
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#lixity-tooltip').getAttribute('aria-hidden'), 'true');
      if (width <= 390) {
        assert.ok(await page.locator('#matrix table').evaluate(table => table.getBoundingClientRect().width >= 700));
        assert.ok(await page.locator('#dialogue .dist .label').first().evaluate(label => label.getBoundingClientRect().width >= 200));
        assert.ok(await page.locator('.band').first().evaluate(band => band.getBoundingClientRect().width >= 150));
      }
      await page.locator('.settings-advanced summary').click();
      await page.locator('#ch-1 .chip').first().click();
      assert.equal(await page.locator('#ch-1 .ptext.open').count(), 1);
      for (const selector of ['#flags', '#dist', '#dialogue', '#characters', '#pacing', '#motifs', '#showing', '#heatmap', '#bands', '#dimensions', '#markers', '#matrix', '#controls', '#ch-1']) {
        await page.mouse.move(0, 0);
        await page.evaluate(() => document.activeElement.blur());
        await page.locator(selector).screenshot({path: `/tmp/lixity-layout-${width}-${selector.slice(1)}.png`});
      }
    }
    assert.deepEqual(errors, []);
    console.log('Layout: desktop/tablet/mobile spacing, readable charts and tables, matrix tooltips, settings and chapter expansion passed');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
