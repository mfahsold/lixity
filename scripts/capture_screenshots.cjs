const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const assert = require('node:assert/strict');

let playwrightMod = process.env.PLAYWRIGHT_MODULE || 'playwright';
try {
  require.resolve(playwrightMod);
} catch {
  const fallback = '/home/codeai/.npm/_npx/b234c773f454f454/node_modules/playwright';
  if (fs.existsSync(fallback)) playwrightMod = fallback;
}
const { chromium } = require(playwrightMod);

async function main() {
  const captures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const launchOptions = {headless: true};
  const execPath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ||
    (fs.existsSync('/usr/bin/chromium-browser') ? '/usr/bin/chromium-browser' :
     fs.existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);
  if (execPath) {
    launchOptions.executablePath = execPath;
  }
  const browser = await chromium.launch(launchOptions);
  const results = [];
  try {
    const page = await browser.newPage({deviceScaleFactor: 1, reducedMotion: 'reduce'});
    const fixturePath = path.join(path.dirname(captures[0].source), 'research-workspace-fixture.json');
    const researchFixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
    await page.addInitScript(({fixture}) => {
      window.captureRequests = [];
      window.fetch = (input, options) => {
        const url = typeof input === 'string' ? input : input.url;
        const method = (options && options.method) || 'GET';
        window.captureRequests.push({url, method});
        if (!Object.prototype.hasOwnProperty.call(fixture, url)) {
          throw new Error('Missing screenshot API fixture: ' + url);
        }
        if (method !== 'GET' && !['/api/nda-list', '/api/research-search'].includes(url)) {
          throw new Error('Screenshot capture cannot mutate a project: ' + method + ' ' + url);
        }
        if (url === '/api/research-search') {
          const query = JSON.parse(options.body);
          if (query.query !== 'warehouse customs' || query.scope !== 'sources') {
            throw new Error('Screenshot search must match the generated API result');
          }
        }
        return Promise.resolve(new Response(JSON.stringify(fixture[url]), {
          status: 200,
          headers: {'Content-Type': 'application/json'},
        }));
      };
    }, {fixture: researchFixture});
    page.setDefaultTimeout(10000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    async function settle() {
      await page.evaluate(() => document.fonts.ready);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    }
    async function open(source, width, height, colorScheme = 'light') {
      await page.setViewportSize({width, height});
      await page.emulateMedia({colorScheme});
      await page.goto(pathToFileURL(source).href);
      await settle();
      assert.ok((await page.title()).length || await page.locator('body').innerText(), 'Capture document is not blank');
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Capture page must not overflow horizontally');
    }
    async function selectView(view) {
      const tab = page.locator(`[data-view="${view}"]`);
      if (await tab.count()) await tab.click();
    }
    async function selectManuscript() {
      const input = page.locator('#manuscript-import-file');
      await input.setInputFiles({
        name: 'harbour-story.md', mimeType: 'text/markdown',
        buffer: Buffer.from('# Harbour story\n\n## Arrival\n\nMara reached the harbour before dawn. The customs log lay open on the desk.\n\n## The ledger\n\nShe compared the entry with the night watchman\'s account.\n'),
      });
      assert.equal((await page.locator('#manuscript-file-name').textContent()).trim(), 'harbour-story.md');
      assert.equal(await page.locator('#manuscript-import-btn').isEnabled(), true);
    }
    async function save(target, selector) {
      await settle();
      await page.mouse.move(0, 0);
      if (await page.locator('#lixity-tooltip.visible').count()) await page.keyboard.press('Escape');
      if (await page.locator('#lixity-tooltip').count()) await page.locator('#lixity-tooltip').waitFor({state: 'hidden'});
      const options = {path: target, animations: 'disabled'};
      if (selector) await page.locator(selector).screenshot(options);
      else await page.screenshot(options);
      assert.deepEqual(errors, [], 'Screenshots must be free of runtime and console errors');
      const bytes = fs.readFileSync(target);
      results.push({file: path.basename(target), width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20)});
    }
    async function saveDialog(target, selector) {
      // Expand scroll containers only for complete documentation captures.
      await page.addStyleTag({content: 'dialog.lixity-modal[open], dialog.lixity-modal[open] .modal-card { max-height: none; overflow: visible; } dialog.lixity-modal[open] .modal-body { overflow: visible; flex-shrink: 0; }'});
      const dialog = page.locator('dialog[open]');
      const height = await dialog.evaluate(element => element.scrollHeight);
      const viewport = page.viewportSize();
      await page.setViewportSize({width: viewport.width, height: Math.max(viewport.height, height + 80)});
      assert.ok(await dialog.evaluate(element => element.scrollHeight <= element.clientHeight + 1), 'Complete dialog content must fit the capture');
      const buttons = dialog.locator('button:visible');
      assert.ok(await buttons.count() > 0);
      for (const button of await buttons.all()) {
        assert.ok(await button.evaluate(element => element.getBoundingClientRect().bottom <= element.closest('dialog').getBoundingClientRect().bottom), 'Dialog actions must not be clipped');
      }
      await save(target, selector);
    }
    for (const capture of captures) {
      const name = path.basename(capture.target);
      await open(capture.source, capture.width, capture.height, name.includes('dark') ? 'dark' : 'light');
      if (name === 'dashboard-light.png' || name === 'dashboard-dark.png') await selectView('analysis');
      if (name === 'dashboard-dimensions.png') {
        await save(capture.target, '#dimensions');
      } else if (name === 'dashboard-markers.png') {
        await save(capture.target, '#markers');
      } else if (name === 'dashboard-heatmap.png') {
        await page.evaluate(() => {
          const rows = document.querySelectorAll('table.heatmap tbody tr');
          for (let i = 20; i < rows.length; i++) rows[i].remove();
        });
        await save(capture.target, '#heatmap');
      } else if (name === 'dashboard-layer.png') {
        await page.locator('#style-layer').selectOption('dialogue');
        for (let index = 0; index < 3; index++) await page.locator('#ch-1 .chip').nth(index).click();
        assert.equal(await page.locator('#ch-1 .ptext.open').count(), 3);
        await save(capture.target, '#ch-1');
      } else if (name === 'dashboard-welcome.png') {
        await selectView('research');
        await save(capture.target);
      } else if (name === 'dashboard-project-modal.png') {
        await page.locator('#btn-modal-new-project').click();
        await page.locator('#tab-btn-scratch').click();
        await page.locator('#new-proj-title').fill('Harbour story');
        await saveDialog(capture.target, '#modal-project-create');
      } else if (name.startsWith('dashboard-project-settings')) {
        await selectView('project');
        await selectManuscript();
        assert.equal(await page.locator('#nda-manager').getAttribute('open'), null);
        await save(capture.target, '#view-pane-project');
      } else if (name.startsWith('dashboard-project-import')) {
        await selectView('project');
        await selectManuscript();
        await page.locator('#manuscript-import-btn').click();
        await page.locator('#import-preview-box').waitFor({state: 'visible'});
        assert.equal(await page.locator('#btn-submit-import-project').isEnabled(), true);
        await saveDialog(capture.target, '#modal-project-create');
      } else if (name.startsWith('dashboard-nda')) {
        await selectView('project');
        await page.locator('#nda-manager > summary').click();
        await page.locator('#nda-unlock-row').waitFor({state: 'visible'});
        assert.equal(await page.locator('#nda-add-row').isVisible(), false);
        await save(capture.target, '#nda-manager');
      } else if (name.startsWith('dashboard-project-open')) {
        await page.locator('#btn-modal-open-project').click();
        await page.locator('#open-proj-choose').click();
        await page.locator('#open-project-chooser-list button').first().waitFor();
        assert.ok(await page.locator('#modal-project-open').evaluate(element => element.scrollWidth <= element.clientWidth));
        await saveDialog(capture.target, '#modal-project-open');
      } else if (name.startsWith('dashboard-research-claims')) {
        await selectView('research');
        await page.locator('[data-rtab="claims"]').click();
        await page.locator('#research-claims-list .research-card').first().waitFor();
        await page.locator('[data-load-evidence]').first().click();
        await page.locator('.claim-evidence-subpanel .research-passage-quote').first().waitFor();
        if (name.includes('mobile')) {
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        }
        await save(capture.target, '#research-manager');
      } else if (name.startsWith('dashboard-research-decisions')) {
        await selectView('research');
        await page.locator('[data-rtab="decisions"]').click();
        await page.locator('#research-decisions-list .research-card').first().waitFor();
        if (name.includes('mobile')) {
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        }
        await save(capture.target, '#research-manager');
      } else if (name.startsWith('dashboard-research-sources') || name.startsWith('dashboard-research-dossiers')) {
        await selectView('research');
        const sources = name.startsWith('dashboard-research-sources');
        const kind = sources ? 'sources' : 'dossiers';
        await page.locator(`[data-rtab="${kind}"]`).click();
        await page.locator(`#research-${kind}-list .research-card`).first().waitFor();
        await settle();
        const before = await page.evaluate(() => captureRequests.length);
        await page.locator(`#r-filter-${kind}`).fill(sources ? 'customs' : 'warehouse');
        assert.equal(await page.evaluate(() => captureRequests.length), before, 'List filtering is local');
        const card = page.locator(`#research-${kind}-list .research-card:visible`).first();
        await card.locator('[data-research-detail]').click();
        await card.locator('.research-details-body .research-prose').first().waitFor();
        await save(capture.target, '#research-manager');
      } else if (name.startsWith('dashboard-research-search')) {
        await selectView('research');
        await page.locator('[data-rtab="search"]').click();
        await page.locator('#r-search-query').fill('warehouse customs');
        await page.locator('#r-search-scope').selectOption('sources');
        await page.locator('#r-search-btn').click();
        await page.locator('#research-search-results .research-passage-card').first().waitFor();
        await save(capture.target, '#research-manager');
      } else if (name === 'cli-research.png') {
        await save(capture.target, '.win');
      } else {
        await save(capture.target);
      }
    }
    const base = path.dirname(captures[0].source);
    const output = path.dirname(captures[0].target);
    await open(path.join(base, 'dashboard.html'), 390, 1028);
    await selectView('analysis');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await save(path.join(output, 'dashboard-mobile.png'));
    await save(path.join(output, 'dashboard-dimensions-mobile.png'), '#dimensions');
    await open(path.join(base, 'dashboard-dark.html'), 1600, 1050, 'dark');
    await selectView('analysis');
    await save(path.join(output, 'dashboard-dimensions-dark.png'), '#dimensions');
    await open(path.join(base, 'dashboard.html'), 1600, 1050);
    await selectView('analysis');
    await save(path.join(output, 'dashboard-reference.png'), '#bands');
    await open(path.join(base, 'dashboard-settings.html'), 1600, 1050);
    await selectView('project');
    await page.locator('.settings-advanced summary').click();
    await save(path.join(output, 'dashboard-settings.png'), '#settings-form');
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(base, 'capture-results.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
