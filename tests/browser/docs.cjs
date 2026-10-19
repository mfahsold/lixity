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
function htmlRoutes(directory, prefix = '') {
  return fs.readdirSync(directory, {withFileTypes: true}).flatMap(entry => {
    const relative = prefix + entry.name;
    return entry.isDirectory() ? htmlRoutes(path.join(directory, entry.name), relative + '/')
      : entry.name.endsWith('.html') ? [relative === 'index.html' ? '' : relative] : [];
  });
}
const routes = htmlRoutes(root).sort();
// Every content page gets all widths. Shared surface types cover theme/JS variants.
const fullMatrixRoutes = new Set(['', 'guides/research-pdf.html', 'demo/report.html',
  'demo/research.html', 'examples/effi-briest.html', 'blog/whats-new-lixity.html']);

async function checkResearchDemo(page, javaScriptEnabled, width, colorScheme) {
  const notice = page.locator('#example-context');
  const credits = page.locator('#research-source-credits');
  await expect(notice).toContainText('read-only research example');
  await expect(notice).toContainText('Current main (unreleased)');
  await expect(notice).toContainText('Generated with Lixity');
  await expect(notice).toContainText('fictional');
  await expect(notice).toContainText('no live Zotero connection');
  await expect(notice).toContainText('retained passage, authored claim and manuscript quote are separate records');
  await expect(notice).toContainText('cannot import, edit or save');
  await expect(credits).toContainText('Richard Krause');
  await expect(credits).toContainText('Library of Congress');
  await expect(credits.locator('a[href="../assets/research/sources.json"]')).toBeVisible();
  function assertReadOnly() {
    return expect(page.locator('input[type=file], textarea, [data-research-revise], [data-dossier-add-image], [data-geo-add], [data-geo-remove], [data-action], [data-manuscript-link-selection], [data-manuscript-link-accept], a[href^="zotero:"], #research-revision-edit-tab, #research-revision-save, #research-revision-batch-add, #r-dos-create-btn, #r-claim-create-btn, #r-decision-create-btn, #r-ingest-btn, #r-zotero-browse, .view-navigation, #project-controls')
      .locator('visible=true')).toHaveCount(0);
  }
  await assertReadOnly();
  if (!javaScriptEnabled) {
    await expect(page.getByText('This interactive read-only example requires JavaScript. Source credits remain available below.', {exact: true})).toBeVisible();
    await notice.locator('a[href="#research-source-credits"]').click();
    await expect(page).toHaveURL(/#research-source-credits$/);
    await expect(credits.locator('h2')).toBeInViewport();
    return;
  }
  await expect(page.locator('[data-rtab=dossiers]')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#research-dossiers-list .research-card')).toHaveCount(2);
  await page.locator('[data-rtab=sources]').click();
  await expect(page.locator('#research-sources-list .research-card')).toHaveCount(4);
  await expect(page.locator('#zotero-box')).not.toHaveAttribute('open', '');
  const zoteroReturn = page.locator('#research-sources-list a[href^="zotero:"]');
  await expect(zoteroReturn).toHaveCount(1);
  assert.equal(await zoteroReturn.evaluate(link =>
    link.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}))), false,
  'Offline fixture source-return links cannot activate the Zotero protocol');
  await page.locator('#r-filter-sources').fill('Hamburg free-port');
  await expect(page.locator('#research-sources-list .research-card').locator('visible=true')).toHaveCount(1);
  const source = page.locator('#research-sources-list .research-card').filter({hasText: 'Hamburg free-port area, circa 1900'});
  await source.locator('[data-research-detail=source]').click();
  await expect(source.locator('.research-details-body')).toContainText('image/jpeg');
  await expect(source.locator('.research-details-body')).toContainText('circa-1900');
  await page.locator('#r-filter-sources').fill('');
  await page.locator('[data-rtab=dossiers]').click();
  await expect(page.locator('#research-dossiers-list .research-card')).toHaveCount(2);
  const dossier = page.locator('#research-dossiers-list .research-card').filter({hasText: 'Warehouse 4 case notes'});
  await dossier.locator('[data-research-detail=dossier]').click();
  const detail = dossier.locator('.research-details-body');
  const authoredClaim = detail.locator('.research-dossier-claims-list li').filter({hasText: 'Attempted warehouse entry'});
  await expect(authoredClaim.locator('[data-manuscript-link-count="1"]')).toBeVisible();
  await expect(authoredClaim.locator('[data-claim-revision="1"]')).toBeVisible();
  await expect(detail.locator('.dossier-image img')).toHaveCount(2);
  const dossierImages = await detail.locator('.dossier-image img').all();
  await Promise.all(dossierImages.map(image => image.evaluate(element => { element.loading = 'eager'; return element.decode(); })));
  let imageIndex = 0;
  for (const image of dossierImages) {
    await image.evaluate(element => { element.loading = 'eager'; return element.decode(); });
    assert.ok(await image.evaluate(element => element.naturalWidth > 1000 && element.naturalHeight > 1000), 'Reviewed public images decode at their original resolution');
    assert.match(await image.getAttribute('src'), /\.\.\/assets\/research\/hamburg-.+\.jpg$/);
    await image.locator('..').click();
    const enlarged = page.locator('#modal-dossier-image-enlarge');
    await expect(enlarged).toBeVisible();
    await expect(enlarged.locator('.pswp__item[aria-hidden=false] img.pswp__img')).toHaveAttribute('src', await image.evaluate(element => element.currentSrc));
    await expect(enlarged.locator('.pswp__counter')).toHaveText(`${imageIndex + 1} / 2`);
    await enlarged.locator('.pswp__button--zoom').click();
    await expect(enlarged.locator('.pswp')).toHaveClass(/pswp--zoomed-in/);
    await page.screenshot({path: path.join(artifacts, `research-image-viewer-${imageIndex}-${width}-${colorScheme}.png`)});
    await page.keyboard.press('Escape');
    await expect(enlarged).not.toBeVisible();
    imageIndex++;
  }
  const sourceContext = detail.locator('.dossier-image figcaption details').first();
  await sourceContext.locator('summary').click();
  await expect(sourceContext).toContainText('Richard Krause');
  await expect(sourceContext.locator('a[href^="https://commons.wikimedia.org/"]')).toBeVisible();
  await sourceContext.locator('summary').click();
  const geography = detail.locator('.dossier-geography');
  await expect(geography).toContainText("Night watchman's walk");
  await expect(geography).toContainText("Customs officer's drive");
  await expect(geography.locator('svg')).toBeVisible();
  await expect(geography.locator('li')).toHaveCount(5);
  const labels = await geography.locator('svg text').evaluateAll(nodes => nodes.map(node => [node.getAttribute('x'), node.getAttribute('y')].join(',')));
  assert.equal(new Set(labels).size, labels.length, 'Canonical point and route number markers use distinct anchors');
  await geography.locator('[data-geo-map]').click();
  await expect(geography.locator('.geography-map.leaflet-container')).toBeVisible();
  await expect(geography.locator('[data-geo-basemap]')).not.toBeChecked();
  await geography.locator('[data-geo-fit]').click();
  const diagram = detail.locator('[data-research-diagram]').first();
  await diagram.scrollIntoViewIfNeeded();
  await expect(diagram).toHaveAttribute('data-diagram-state', 'ready');
  await diagram.locator('[data-diagram-enlarge]').click();
  await expect(page.locator('#modal-dossier-image-enlarge img.pswp__img')).toBeVisible();
  await expect.poll(() => page.locator('#modal-dossier-image-enlarge img.pswp__img').evaluate(image => image.naturalWidth)).toBeGreaterThan(0);
  await page.keyboard.press('Escape');
  await assertReadOnly();
  await geography.scrollIntoViewIfNeeded();
  await page.screenshot({path: path.join(artifacts, `research-geography-${width}-${colorScheme}.png`)});
  await dossier.locator('[data-research-history=dossier]').click();
  const history = page.locator('#research-revision-history-detail');
  await expect(history.locator('.dossier-image img')).toHaveCount(2);
  await expect(history.locator('.dossier-geography')).toContainText("Night watchman's walk");
  await assertReadOnly();
  await page.locator('#research-revision-history-list [data-research-revision="1"]').click();
  await expect(history.locator('.dossier-image img')).toHaveCount(0);
  await expect(history.locator('.dossier-geography')).toContainText("Night watchman's walk");
  await page.keyboard.press('Escape');
  await page.locator('[data-rtab=claims]').click();
  await expect(page.locator('#research-claims-list .research-card')).toHaveCount(3);
  const claim = page.locator('#research-claims-list .research-card').filter({hasText: 'Attempted warehouse entry'});
  await claim.locator('[data-load-evidence]').click();
  await expect(claim.locator('.claim-evidence-subpanel')).toContainText('synthetic');
  await page.locator('#r-open-timeline').click();
  await expect(page.locator('#research-claims-timeline .research-timeline-strip-row')).toHaveCount(2);
  await expect(page.locator('#research-claims-timeline')).toContainText('present day');
  await assertReadOnly();
  await page.locator('[data-rtab=decisions]').click();
  await expect(page.locator('#research-decisions-list .research-card')).toHaveCount(2);
  await page.locator('[data-rtab=review]').click();
  await expect(page.locator('#research-editorial-review')).not.toContainText('Loading');
  await expect(page.locator('#research-editorial-review')).toContainText('Warehouse 4 case notes');
  const manuscriptReview = page.locator('#research-manuscript-review');
  await expect(manuscriptReview.locator('.manuscript-link-review-item')).toHaveCount(1);
  await expect(manuscriptReview).toContainText('Attempted warehouse entry');
  await expect(manuscriptReview.locator('blockquote')).toHaveText('Someone had tried the eastern gate of Warehouse 4.');
  await expect(manuscriptReview).toContainText('Exact passage');
  await expect(manuscriptReview).toContainText('Saved version 1');
  await manuscriptReview.locator('[data-research-history=claim]').click();
  await expect(history).toContainText('The customs log describes an attempted entry');
  await page.keyboard.press('Escape');
  await manuscriptReview.scrollIntoViewIfNeeded();
  await page.screenshot({path: path.join(artifacts, `research-manuscript-review-${width}-${colorScheme}.png`)});
  await assertReadOnly();
}

async function checkReport(page, javaScriptEnabled, width, colorScheme) {
  assert.equal(await page.locator('.page').count(), 1, 'The example uses the generated report layout');
  assert.ok((await page.locator('.page').innerText()).length > 1000);
  assert.equal(await page.locator('form, input[type=file], textarea, [contenteditable=true], #controls, #nda-draft, #view-pane-project, #view-pane-research, [data-marker-kind]').count(), 0, 'The example has no upload, writer, settings, NDA or editing controls');
  assert.equal(await page.locator('.chapter').count(), 6);
  assert.ok(await page.locator('.chip').count() > 6, 'The report exposes actual paragraph blocks');
  if (javaScriptEnabled) await page.locator('#style-tab-dimensions').click();
  else {
    assert.equal(await page.locator('#style-panels > .panel:visible').count(), 4);
    assert.equal(await page.locator('#chapters .ptext p:visible').count(), await page.locator('#chapters .ptext').count(),
      'The offline fallback keeps the complete manuscript readable without JavaScript');
  }
  const chapterLink = page.locator('#dim-scores a[href="#ch-2"]');
  assert.equal(await chapterLink.count(), 1, 'The style view has a semantic chapter link');
  await chapterLink.focus();
  await page.keyboard.press('Enter');
  if (!javaScriptEnabled) {
    await expect(page, 'Chapter anchors work without JavaScript').toHaveURL(/#ch-2$/);
    return;
  }
  // The flash lands after the smooth scroll settles (see flashOnArrival).
  await page.waitForFunction(selector => document.querySelector(selector).classList.contains('flash'),
    '#ch-2', {timeout: 2500});
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
  await passage.locator('.paragraph-values > summary').click();
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
  await page.locator('#style-tab-dimensions').click();
  await canvas.scrollIntoViewIfNeeded();
  await page.mouse.move(0, 0);
  // Compare the rendered canvas bitmap. A locator screenshot at a fractional
  // scroll position can include one extra row of the surrounding background.
  const initial = await canvas.evaluate(element => element.toDataURL());
  await page.locator('#dim-ctl-left').focus();
  await page.keyboard.press('Enter');
  assert.notEqual(await canvas.evaluate(element => element.toDataURL()), initial, 'A keyboard control rotates the real chapter chart');
  await page.locator('#dim-ctl-reset').click();
  const reset = await canvas.evaluate(element => element.toDataURL());
  if (reset !== initial) {
    fs.writeFileSync(path.join(artifacts, `canvas-initial-${width}-${colorScheme}.png`), Buffer.from(initial.split(',')[1], 'base64'));
    fs.writeFileSync(path.join(artifacts, `canvas-reset-${width}-${colorScheme}.png`), Buffer.from(reset.split(',')[1], 'base64'));
    console.error(`Canvas reset mismatch: ${artifacts}, ${width}px, ${colorScheme}`);
  }
  assert.equal(reset, initial, 'Reset restores the chapter chart');
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
        let file = path.resolve(root, relative);
        if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
        assert.ok(file.startsWith(root + path.sep));
        assert.ok(fs.existsSync(file), `Missing public asset ${relative}`);
        const contentType = {'.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml'}[path.extname(file)];
        await route.fulfill({contentType, body: fs.readFileSync(file)});
      });
      for (const width of [1440, 390, 320]) {
        await page.setViewportSize({width, height: 900});
        for (const route of routes) {
          if (!(javaScriptEnabled && colorScheme === 'light') && !fullMatrixRoutes.has(route)) continue;
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
          // Dashboards keep their paragraph text in lazy payloads, so their
          // substance is checked structurally; content pages need an article.
          const dashboard = route === 'demo/report.html' || route.startsWith('examples/');
          if (dashboard) {
            assert.ok(await page.locator('.chapter').count() > 0, `${route} renders chapters`);
            assert.ok(await page.locator('.chip').count() > 0, `${route} renders paragraph chips`);
          } else if (route === 'demo/research.html') {
            assert.ok((await page.locator('#research-source-credits').innerText()).length > 1000, 'The research example has readable source credits without scripting');
          } else {
            assert.ok((await page.locator('main').innerText()).length > 1000,
              `${route} has too little visible text`);
          }
          assert.equal(await page.locator('link[rel=canonical]').getAttribute('href'), 'https://mfahsold.github.io/lixity/' + route);
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${route} overflows at ${width}px`);
          if (width === 320 && ['guides/interpretation.html', 'guides/research-pdf.html', 'guides/manuscript-analysis-tools.html'].includes(route)) {
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
            const reducedMotion = await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
            for (const feature of await page.locator('.feature').all()) {
              const video = feature.locator('.frame video');
              if (await video.count()) {
                assert.ok(await video.evaluate(element => ['autoplay', 'muted', 'loop', 'playsinline'].every(name => element.hasAttribute(name))), 'Feature walkthroughs loop muted and inline');
                assert.ok(await video.getAttribute('poster'), 'Feature walkthroughs carry a poster');
                assert.equal(await video.locator('source[type="video/mp4"]').count(), 1, 'Feature walkthroughs carry one MP4 source');
                if (!reducedMotion) await video.scrollIntoViewIfNeeded();
              }
              for (const image of await feature.locator('.frame img').all()) {
                await image.evaluate(element => { element.loading = 'eager'; return element.decode().catch(() => {}); });
                if (await image.isVisible()) await image.scrollIntoViewIfNeeded();
                assert.equal(await image.evaluate(element => element.parentElement.getAttribute('href')), await image.getAttribute('src'), 'Feature images open their original PNG without JavaScript');
                assert.ok(await image.evaluate(element => {
                  const feature = element.closest('article');
                  return feature.querySelector('h2') && feature.querySelector('p').textContent.length > 50;
                }), 'Each image belongs to an explained feature');
                assert.deepEqual(await image.evaluate(element => [element.naturalWidth, element.naturalHeight]),
                  [Number(await image.getAttribute('width')), Number(await image.getAttribute('height'))]);
              }
            }
            await page.locator('h1').scrollIntoViewIfNeeded();
          }
          await page.screenshot({path: path.join(artifacts, `${route ? path.basename(route, '.html') : 'home'}-${width}-${colorScheme}${javaScriptEnabled ? '' : '-js-off'}.png`), fullPage: route === '' || route === 'guides/first-look.html'});
          if (route === 'demo/report.html') await checkReport(page, javaScriptEnabled, width, colorScheme);
          if (route === 'demo/research.html') await checkResearchDemo(page, javaScriptEnabled, width, colorScheme);
        }
        await page.goto('http://lixity.test/lixity/');
        await page.locator('.hero-cta a[href="guides/first-look.html"]').click();
        assert.ok(page.url().endsWith('/guides/first-look.html'));
        await page.locator('.ctl[href="../demo/report.html"]').click();
        assert.ok(page.url().endsWith('/demo/report.html'));
        await page.locator('a[href="../guides/first-look.html"]').first().click();
        assert.ok(page.url().endsWith('/guides/first-look.html'), 'The report returns to the walkthrough');
        await page.goto('http://lixity.test/lixity/');
        await page.locator('.hero-cta a.primary[href="demo/report.html"]').click();
        assert.ok(page.url().endsWith('/demo/report.html'), 'The primary CTA opens the report directly');
        await page.goto('http://lixity.test/lixity/');
        if (javaScriptEnabled) {
          await page.locator('#themeToggle').click();
          await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
        }
        await page.locator('#guides a[href="guides/research-pdf.html"]').click();
        assert.ok(page.url().endsWith('/guides/research-pdf.html'));
        if (javaScriptEnabled) {
          await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
          await page.reload();
          await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
        }
        await page.locator('nav a[href="interpretation.html"]').click();
        assert.ok(page.url().endsWith('/guides/interpretation.html'));
        if (javaScriptEnabled) {
          await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
          await page.goto('http://lixity.test/lixity/');
          await page.locator('#themeToggle').click();
          await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
          await page.locator('#themeToggle').click();
          await expect(page.locator('html')).toHaveAttribute('data-theme', 'auto');
          await page.evaluate(() => localStorage.removeItem('lixity-theme'));
        }
        // The blog index lists the newest article; its page renders standalone.
        await page.goto('http://lixity.test/lixity/blog/');
        const newestArticle = page.locator('article h2 a').first();
        const articleURL = new URL(await newestArticle.getAttribute('href'), page.url());
        await newestArticle.click();
        assert.equal(page.url(), articleURL.href);
        assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'),
          'https://mfahsold.github.io' + articleURL.pathname, 'Canonical URL matches the published page');
      }
      assert.deepEqual(errors, []);
      await context.close();
    }
    console.log(`Public docs: ${routes.length} selected HTML pages at desktop/390/320, representative surfaces in light/dark and JS on/off, static GET-only journey, report keyboard/filter/chart controls, read-only research source/image/geography/history/timeline/manuscript-quote journey, assets, overflow and console passed. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
