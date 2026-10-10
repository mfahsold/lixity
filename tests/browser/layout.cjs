const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '../..');
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
import runpy
render = runpy.run_path('tests/test_ui_contract.py')['_full_dashboard']
render.__globals__['SAMPLE'] += '\\n\\n## Dialog\\n\\n»Ich gehe zum Haus und sehe den Regen«, sagte sie.\\n' + '\\n\\nIch gehe zum Haus.\\n' * 100
print(render())
`],
  {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8', maxBuffer: 8*1024*1024});
assert.equal(fixture.status, 0, fixture.error ? fixture.error.message : fixture.stderr);

(async () => {
  const browser = await launchChromium();
  try {
    const page = await browser.newPage({hasTouch: true});
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
      await page.locator('#tab-view-project').click();
      assert.equal(await page.locator('#nda-manager, #nda-table, #nda-passphrase').count(), 0);
      assert.equal(await page.locator('#nda-draft-form').count(), 0, 'No implicit NDA capability in an embedding fixture');
      await page.locator('#tab-view-analysis').click();
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
      await page.mouse.move(0, 0);
      const headings = page.locator('#matrix th');
      assert.equal(await headings.locator('.help[data-help]').count(), await headings.count());
      const sentenceHelp = headings.locator('.help').nth(3);
      await sentenceHelp.evaluate(element => element.setAttribute('aria-describedby', 'microhint'));
      await sentenceHelp.focus();
      await page.waitForFunction(() => document.querySelector('#lixity-tooltip').classList.contains('visible'));
      assert.equal(await page.locator('#lixity-tooltip').textContent(), await sentenceHelp.getAttribute('data-help'));
      assert.equal(await sentenceHelp.getAttribute('aria-describedby'), 'microhint lixity-tooltip');
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#lixity-tooltip').getAttribute('aria-hidden'), 'true');
      assert.equal(await sentenceHelp.getAttribute('aria-describedby'), 'microhint');
      if (width === 1440) {
        await sentenceHelp.hover();
        await page.locator('#lixity-tooltip').hover();
        assert.equal(await page.locator('#lixity-tooltip').getAttribute('aria-hidden'), 'false', 'Hovering an explanation keeps it readable');
        await page.keyboard.press('Escape');
      }
      if (width === 320) {
        await sentenceHelp.tap();
        assert.equal(await page.locator('#lixity-tooltip').getAttribute('aria-hidden'), 'false');
        assert.ok(await page.locator('#lixity-tooltip').evaluate(element => {
          const box = element.getBoundingClientRect();
          return box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight;
        }), 'Touch help stays inside the viewport');
        await sentenceHelp.tap();
        assert.equal(await page.locator('#lixity-tooltip').getAttribute('aria-hidden'), 'true');
      }
      if (width <= 390) {
        await page.locator('#style-tab-bands').click();
        assert.ok(await page.locator('#matrix table').evaluate(table => table.getBoundingClientRect().width >= 700));
        assert.ok(await page.locator('#dialogue .dist .label').first().evaluate(label => label.getBoundingClientRect().width >= 200));
        assert.ok(await page.locator('.band').first().evaluate(band => band.getBoundingClientRect().width >= 150));
      }
      await page.locator('#tab-view-project').click();
      await page.locator('.settings-form .settings-advanced > summary').click();
      await page.locator('#tab-view-analysis').click();
      await page.locator('#ch-1 .chip').first().click();
      assert.equal(await page.locator('#ch-1 .ptext.open').count(), 1);
      await sentenceHelp.focus();
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#ch-1 .ptext.open').count(), 1, 'Dismissing help must not close an unrelated paragraph');
      for (const selector of ['#flags', '#dist', '#dialogue', '#characters', '#pacing', '#motifs', '#showing', '#heatmap', '#bands', '#dimensions', '#markers', '#matrix', '#controls', '#ch-1']) {
        await page.locator(selector === '#controls' ? '#tab-view-project' : '#tab-view-analysis').click();
        if (['#heatmap', '#bands', '#dimensions'].includes(selector)) {
          await page.locator('#style-tab-' + selector.slice(1)).click();
        }
        await page.mouse.move(0, 0);
        await page.evaluate(() => document.activeElement.blur());
        await page.locator(selector).screenshot({path: `/tmp/lixity-layout-${width}-${selector.slice(1)}.png`});
      }
    }
    assert.deepEqual(errors, []);
    console.log('Layout: desktop/tablet/mobile spacing, readable charts and tables, matrix tooltips, settings and chapter expansion passed');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
