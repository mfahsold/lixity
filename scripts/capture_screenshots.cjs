const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const assert = require('node:assert/strict');

async function main() {
  const captures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await chromium.launch({headless: true});
  const results = [];
  try {
    const page = await browser.newPage({deviceScaleFactor: 1, reducedMotion: 'reduce'});
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
      } else if (name === 'dashboard-layer.png') {
        await page.locator('#style-layer').selectOption('dialogue');
        for (let index = 0; index < 3; index++) await page.locator('#ch-1 .chip').nth(index).click();
        assert.equal(await page.locator('#ch-1 .ptext.open').count(), 3);
        await save(capture.target, '#ch-1');
      } else {
        await save(capture.target);
      }
    }
    const base = path.dirname(captures[0].source);
    const output = path.dirname(captures[0].target);
    await open(path.join(base, 'dashboard.html'), 390, 1000);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await save(path.join(output, 'dashboard-mobile.png'));
    await save(path.join(output, 'dashboard-dimensions-mobile.png'), '#dimensions');
    await open(path.join(base, 'dashboard-dark.html'), 1600, 1050, 'dark');
    await save(path.join(output, 'dashboard-dimensions-dark.png'), '#dimensions');
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(base, 'capture-results.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
