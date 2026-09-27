// Validate the public static site without contacting production or loading private data.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
let playwrightMod = process.env.PLAYWRIGHT_MODULE || 'playwright';
try { require.resolve(playwrightMod); } catch {
  const fallback = '/home/codeai/.npm/_npx/b234c773f454f454/node_modules/playwright';
  if (fs.existsSync(fallback)) playwrightMod = fallback;
}
const {chromium} = require(playwrightMod);
const root = path.resolve(__dirname, '../../docs');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-public-docs-'));
const routes = ['', 'guides/installation.html', 'guides/interpretation.html', 'guides/research-pdf.html'];

(async () => {
  const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ||
    (fs.existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' :
     fs.existsSync('/usr/bin/chromium-browser') ? '/usr/bin/chromium-browser' : undefined);
  const browser = await chromium.launch({headless: true, ...(executablePath ? {executablePath} : {})});
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
        const contentType = {'.html': 'text/html', '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml'}[path.extname(file)];
        await route.fulfill({contentType, body: fs.readFileSync(file)});
      });
      for (const width of [1440, 390, 320]) {
        await page.setViewportSize({width, height: 900});
        for (const route of routes) {
          await page.goto('http://lixity.test/lixity/' + route);
          assert.equal(await page.locator('h1').count(), 1);
          assert.ok((await page.title()).length > 10);
          assert.ok((await page.locator('main').innerText()).length > 1000);
          assert.equal(await page.locator('link[rel=canonical]').getAttribute('href'), 'https://mfahsold.github.io/lixity/' + route);
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${route} overflows at ${width}px`);
          if (javaScriptEnabled) {
            await page.screenshot({path: path.join(artifacts, `${route ? path.basename(route, '.html') : 'home'}-${width}-${colorScheme}.png`)});
          }
        }
        await page.goto('http://lixity.test/lixity/');
        await page.locator('#guides a[href="guides/research-pdf.html"]').click();
        assert.ok(page.url().endsWith('/guides/research-pdf.html'));
        await page.locator('nav a[href="interpretation.html"]').click();
        assert.ok(page.url().endsWith('/guides/interpretation.html'));
      }
      assert.deepEqual(errors, []);
      await context.close();
    }
    console.log(`Public docs: four pages, desktop/390/320, JS on/off, assets, navigation and console passed. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
