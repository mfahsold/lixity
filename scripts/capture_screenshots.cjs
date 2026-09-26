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
      const nativeFetch = window.fetch.bind(window);
      window.fetch = (input, options) => {
        const url = typeof input === 'string' ? input : input.url;
        if (location.pathname.endsWith('/dashboard-research-workspace.html') &&
            Object.prototype.hasOwnProperty.call(fixture, url)) {
          return Promise.resolve(new Response(JSON.stringify(fixture[url]), {
            status: 200,
            headers: {'Content-Type': 'application/json'},
          }));
        }
        return nativeFetch(input, options);
      };
    }, {fixture: researchFixture});
    page.setDefaultTimeout(10000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    async function open(source, width, height, colorScheme = 'light') {
      await page.setViewportSize({width, height});
      await page.emulateMedia({colorScheme});
      await page.goto(pathToFileURL(source).href);
      await page.evaluate(() => document.fonts.ready);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    }
    async function save(target, selector) {
      await page.mouse.move(0, 0);
      const options = {path: target, animations: 'disabled'};
      if (selector) await page.locator(selector).screenshot(options);
      else await page.screenshot(options);
      const bytes = fs.readFileSync(target);
      results.push({file: path.basename(target), width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20)});
    }
    for (const capture of captures) {
      const name = path.basename(capture.target);
      await open(capture.source, capture.width, capture.height, name.includes('dark') ? 'dark' : 'light');
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
        await save(capture.target, '#welcome-hero');
      } else if (name === 'dashboard-project-modal.png') {
        await page.evaluate(() => {
          const m = document.getElementById('modal-project-create');
          if (m) m.showModal();
        });
        await save(capture.target, '#modal-project-create .modal-card');
      } else if (name.startsWith('dashboard-research-claims')) {
        await page.locator('[data-rtab="claims"]').click();
        await page.locator('#research-claims-list .research-card').first().waitFor();
        await page.locator('[data-load-evidence]').first().click();
        await page.locator('.claim-evidence-subpanel .research-passage-quote').first().waitFor();
        if (name.includes('mobile')) {
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        }
        await save(capture.target, '#research-manager');
      } else if (name.startsWith('dashboard-research-decisions')) {
        await page.locator('[data-rtab="decisions"]').click();
        await page.locator('#research-decisions-list .research-card').first().waitFor();
        if (name.includes('mobile')) {
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        }
        await save(capture.target, '#research-manager');
      } else {
        await save(capture.target);
      }
    }
    const base = path.dirname(captures[0].source);
    const output = path.dirname(captures[0].target);
    await open(path.join(base, 'dashboard.html'), 390, 1028);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await save(path.join(output, 'dashboard-mobile.png'));
    await save(path.join(output, 'dashboard-dimensions-mobile.png'), '#dimensions');
    await open(path.join(base, 'dashboard-dark.html'), 1600, 1050, 'dark');
    await save(path.join(output, 'dashboard-dimensions-dark.png'), '#dimensions');
    await open(path.join(base, 'dashboard.html'), 1600, 1050);
    await save(path.join(output, 'dashboard-reference.png'), '#bands');
    await open(path.join(base, 'dashboard-settings.html'), 1600, 1050);
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
