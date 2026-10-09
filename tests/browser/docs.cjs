const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
// Validate the public static site without contacting production or loading private data.
const fs = require('node:fs');
const path = require('node:path');
const {expect} = require(path.join(playwrightModule, 'test'));
const os = require('node:os');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const repository = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-public-docs-'));
const root = path.join(artifacts, 'site');
const python = process.env.PYTHON_BIN || path.join(repository, '.venv/bin/python');
const staged = spawnSync(python, ['scripts/stage_pages.py', '--output', root], {cwd: repository, encoding: 'utf8'});
assert.equal(staged.status, 0, staged.stderr);
const routes = ['', 'guides/installation.html', 'guides/interpretation.html', 'guides/research-pdf.html', 'guides/first-look.html', 'demo/report.html'];

async function checkReport(page, javaScriptEnabled, width, colorScheme) {
  assert.equal(await page.locator('.page').count(), 1, 'The example uses the generated report layout');
  assert.ok((await page.locator('.page').innerText()).length > 1000);
  assert.equal(await page.locator('form, input[type=file], textarea, [contenteditable=true], #controls, #nda-draft, #view-pane-project, #view-pane-research, [data-marker-kind]').count(), 0, 'The example has no upload, writer, settings, NDA or editing controls');
  assert.equal(await page.locator('.chapter').count(), 6);
  assert.ok(await page.locator('.chip').count() > 6, 'The report exposes actual paragraph blocks');
  const chapterLink = page.locator('#dim-scores a[href="#ch-2"]');
  assert.equal(await chapterLink.count(), 1, 'The style view has a semantic chapter link');
  await chapterLink.focus();
  await page.keyboard.press('Enter');
  if (!javaScriptEnabled) {
    assert.ok(page.url().endsWith('#ch-2'), 'Chapter anchors work without JavaScript');
    return;
  }
  assert.equal(await page.locator('#ch-2').evaluate(element => element.classList.contains('flash')), true, 'The chapter link navigates to its actual text section');
  const chip = page.locator('#ch-2 .chip').first();
  const target = await chip.getAttribute('data-target');
  const passage = page.locator('#' + target);
  assert.equal(await chip.getAttribute('aria-expanded'), 'false');
  await chip.focus();
  await page.keyboard.press('Enter');
  assert.equal(await chip.getAttribute('aria-expanded'), 'true');
  await expect(passage).toBeVisible();
  await expect(passage).toHaveCSS('opacity', '1');
  assert.ok((await passage.locator('p').innerText()).length > 50, 'Opening a block exposes the synthetic source paragraph');
  assert.ok((await passage.locator('.anchor').innerText()).length > 5, 'The passage includes source lines');
  await passage.locator('p').click();
  await page.screenshot({path: path.join(artifacts, `report-passage-${width}-${colorScheme}.png`)});
  await chip.focus();
  await page.keyboard.press('Space');
  assert.equal(await chip.getAttribute('aria-expanded'), 'false');
  assert.equal(await passage.evaluate(element => element.classList.contains('open')), false);
  const countVisible = () => page.locator('.chip:visible').count();
  const allVisible = await countVisible();
  await page.locator('#filter-flags').check();
  assert.equal(await page.locator('body').evaluate(element => element.classList.contains('only-flags')), true);
  const flaggedVisible = await countVisible();
  assert.ok(flaggedVisible < allVisible, 'The flag filter changes the visible paragraph blocks');
  await page.locator('#paragraph-filter-reset').click();
  assert.equal(await page.locator('#filter-flags').isChecked(), false);
  assert.equal(await countVisible(), allVisible, 'Reset restores the paragraph map');
  await page.locator('#style-layer').selectOption('asl');
  assert.equal(await page.locator('#layer-legend').isVisible(), true);
  assert.ok(await page.locator('.chip.has-layer').count() > 0, 'Selecting a layer changes actual paragraph data');
  await page.locator('#paragraph-filter-reset').click();
  assert.equal(await page.locator('#style-layer').inputValue(), '');
  assert.equal(await page.locator('#layer-legend').isVisible(), false);
  const canvas = page.locator('#dim-3d-canvas');
  await canvas.scrollIntoViewIfNeeded();
  const initial = await canvas.screenshot();
  await page.locator('#dim-ctl-left').focus();
  await page.keyboard.press('Enter');
  assert.notDeepEqual(await canvas.screenshot(), initial, 'A keyboard control rotates the real chapter chart');
  await page.locator('#dim-ctl-reset').click();
  assert.deepEqual(await canvas.screenshot(), initial, 'Reset restores the chapter chart');
  await page.mouse.move(0, 0);
  await page.keyboard.press('Escape');
  await page.locator('#dimensions').screenshot({path: path.join(artifacts, `report-style-${width}-${colorScheme}.png`)});
}

(async () => {
  const browser = await launchChromium();
  try {
    for (const [javaScriptEnabled, colorScheme] of [[true, 'light'], [false, 'light'], [true, 'dark'], [false, 'dark']]) {
      const context = await browser.newContext({javaScriptEnabled, colorScheme});
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
      await context.route('**/*', async route => {
        const request = route.request();
        const url = new URL(request.url());
        assert.equal(request.method(), 'GET', 'The public journey must make only static GET requests');
        assert.equal(url.origin, 'http://lixity.test', 'Public pages must not require external requests');
        assert.ok(url.pathname.startsWith('/lixity/'), 'The public journey must not call an API');
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
          if (route !== 'demo/report.html') {
            assert.ok((await page.locator('main').innerText()).length > 1000);
          }
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
          await page.screenshot({path: path.join(artifacts, `${route ? path.basename(route, '.html') : 'home'}-${width}-${colorScheme}${javaScriptEnabled ? '' : '-js-off'}.png`), fullPage: route === 'guides/first-look.html'});
          if (route === 'demo/report.html') await checkReport(page, javaScriptEnabled, width, colorScheme);
        }
        await page.goto('http://lixity.test/lixity/');
        await page.locator('.hero-cta a[href="guides/first-look.html"]').click();
        assert.ok(page.url().endsWith('/guides/first-look.html'));
        await page.locator('.btn[href="../demo/report.html"]').click();
        assert.ok(page.url().endsWith('/demo/report.html'));
        await page.locator('a[href="../guides/first-look.html"]').first().click();
        assert.ok(page.url().endsWith('/guides/first-look.html'), 'The report returns to the walkthrough');
        await page.goto('http://lixity.test/lixity/');
        await page.locator('.hero-cta a.primary[href="demo/report.html"]').click();
        assert.ok(page.url().endsWith('/demo/report.html'), 'The primary CTA opens the report directly');
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
    console.log(`Public docs: six staged pages, desktop/390/320, light/dark, JS on/off, static GET-only journey, report keyboard/filter/chart controls, assets, overflow and console passed. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
