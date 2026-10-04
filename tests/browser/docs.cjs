const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
// Validate the public static site without contacting production or loading private data.
const fs = require('node:fs');
const path = require('node:path');
const {expect} = require(path.join(playwrightModule, 'test'));
const os = require('node:os');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../docs');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-public-docs-'));
const routes = ['', 'guides/installation.html', 'guides/interpretation.html', 'guides/research-pdf.html'];

(async () => {
  const browser = await launchChromium();
  try {
    for (const [javaScriptEnabled, colorScheme] of [[true, 'light'], [false, 'light'], [true, 'dark']]) {
      const context = await browser.newContext({javaScriptEnabled, colorScheme});
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
      await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        assert.equal(url.origin, 'http://lixity.test', 'Public pages must not require external requests');
        const relative = decodeURIComponent(url.pathname).replace(/^\/lixity\//, '') || 'index.html';
        const file = path.resolve(root, relative);
        assert.ok(file.startsWith(root + path.sep));
        assert.ok(fs.existsSync(file), `Missing public asset ${relative}`);
        const contentType = {'.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.png': 'image/png', '.svg': 'image/svg+xml'}[path.extname(file)];
        await route.fulfill({contentType, body: fs.readFileSync(file)});
      });
      for (const width of [1440, 390, 320]) {
        await page.setViewportSize({width, height: 900});
        for (const route of routes) {
          await page.goto('http://lixity.test/lixity/' + route);
          assert.equal(await page.locator('h1').count(), 1);
          const headings = await page.locator('h1,h2,h3,h4,h5,h6').evaluateAll(nodes => nodes.map(node => Number(node.tagName[1])));
          headings.forEach((level, index) => {
            if (index) assert.ok(level <= headings[index - 1] + 1, `${route} skips a heading level`);
          });
          assert.deepEqual(await page.locator('main img').evaluateAll(nodes => nodes
            .filter(node => !(Number(node.getAttribute('width')) > 0 && Number(node.getAttribute('height')) > 0))
            .map(node => node.getAttribute('src'))), [], `${route} has images without dimensions`);
          assert.ok((await page.title()).length > 10);
          assert.ok((await page.locator('main').innerText()).length > 1000);
          assert.equal(await page.locator('link[rel=canonical]').getAttribute('href'), 'https://mfahsold.github.io/lixity/' + route);
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${route} overflows at ${width}px`);
          if (width === 320 && ['guides/interpretation.html', 'guides/research-pdf.html'].includes(route)) {
            for (const table of await page.locator('.feature-table-wrapper').all()) {
              assert.ok(await table.evaluate(element => element.scrollWidth > element.clientWidth), 'Wide reference tables scroll inside the page');
              assert.ok(await table.locator('th').first().evaluate(element => element.getBoundingClientRect().width >= 120), 'Table columns remain readable on mobile');
              await table.scrollIntoViewIfNeeded();
              await table.focus();
              await page.keyboard.press('ArrowRight');
              await expect.poll(() => table.evaluate(element => element.scrollLeft), {
                message: 'Focused tables scroll with the keyboard even when page scripts are disabled',
              }).toBeGreaterThan(0);
            }
            await page.locator('h1').scrollIntoViewIfNeeded();
          }
          if (!route) {
            for (const image of await page.locator('.feature .shot img').all()) {
              await image.scrollIntoViewIfNeeded();
              await image.evaluate(element => element.decode());
              assert.equal(await image.evaluate(element => element.parentElement.getAttribute('href')), await image.getAttribute('src'), 'Feature images open their original PNG without JavaScript');
              assert.ok(await image.evaluate(element => {
                const feature = element.closest('article');
                return feature.querySelector('h2') && feature.querySelector('p').textContent.length > 50;
              }), 'Each image belongs to an explained feature');
              assert.deepEqual(await image.evaluate(element => [element.naturalWidth, element.naturalHeight]),
                [Number(await image.getAttribute('width')), Number(await image.getAttribute('height'))]);
            }
            await page.locator('h1').scrollIntoViewIfNeeded();
          }
          if (javaScriptEnabled) {
            await page.screenshot({path: path.join(artifacts, `${route ? path.basename(route, '.html') : 'home'}-${width}-${colorScheme}.png`)});
          }
        }
        await page.goto('http://lixity.test/lixity/');
        if (javaScriptEnabled) {
          await page.locator('#themeToggle').click();
          assert.equal(await page.locator('html').getAttribute('data-theme'), 'light');
        }
        await page.locator('#guides a[href="guides/research-pdf.html"]').click();
        assert.ok(page.url().endsWith('/guides/research-pdf.html'));
        if (javaScriptEnabled) {
          assert.equal(await page.locator('html').getAttribute('data-theme'), 'light', 'Guides keep the chosen theme');
          await page.reload();
          assert.equal(await page.locator('html').getAttribute('data-theme'), 'light', 'Reload keeps the chosen theme');
        }
        await page.locator('nav a[href="interpretation.html"]').click();
        assert.ok(page.url().endsWith('/guides/interpretation.html'));
        if (javaScriptEnabled) {
          assert.equal(await page.locator('html').getAttribute('data-theme'), 'light');
          await page.goto('http://lixity.test/lixity/');
          await page.locator('#themeToggle').click();
          assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
          await page.locator('#themeToggle').click();
          assert.equal(await page.locator('html').getAttribute('data-theme'), 'auto');
          await page.evaluate(() => localStorage.removeItem('lixity-theme'));
        }
      }
      assert.deepEqual(errors, []);
      await context.close();
    }
    console.log(`Public docs: four pages, desktop/390/320, JS on/off, assets, navigation and console passed. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
