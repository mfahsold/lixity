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
const routes = htmlRoutes(root).filter(route => route !== 'demo/research.html').sort();
// Every content page gets all widths. Shared surface types cover theme/JS variants.
const fullMatrixRoutes = new Set(['', 'guides/first-look.html', 'guides/research-pdf.html', 'demo/report.html',
  'examples/effi-briest.html', 'blog/index.html', 'blog/whats-new-lixity.html']);
const returnJourneyRoutes = new Set(['', 'guides/first-look.html', 'blog/index.html',
  'blog/whats-new-lixity.html', 'demo/report.html', 'examples/effi-briest.html']);
const demoTitle = 'The Crate at Warehouse 4';
const demoQuote = 'Someone had tried the eastern gate of Warehouse 4.';

async function withoutRequests(page, description, exercise) {
  const requests = [];
  const record = request => requests.push({url: request.url(), method: request.method()});
  page.on('request', record);
  try {
    await exercise();
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.deepEqual(requests, [], description);
  } finally {
    page.off('request', record);
  }
}

async function returnToTop(page, route) {
  const backTop = page.locator('a.site-back-top[href="#top"]');
  await backTop.focus();
  await expect(backTop).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/#top$/);
  await expect(page.locator('body#top')).toBeFocused();
  await expect.poll(() => page.evaluate(() => scrollY), {
    message: `${route || 'home'} returns to the document top after keyboard activation`,
  }).toBeLessThan(2);
}

async function checkReturnNavigation(page, route, exercise) {
  const top = page.locator('body#top.site-page');
  await expect(top).toHaveAttribute('tabindex', '-1');
  const navigation = page.locator('nav.site-return[aria-label="Lixity navigation"]');
  await expect(navigation).toBeVisible();
  const home = navigation.locator(`a[href="${route ? '../' : './'}"]`);
  await expect(home).toBeVisible();
  const demo = navigation.getByRole('link', {name: 'Demo', exact: true});
  await expect(demo).toHaveAttribute('href', route ? '../demo/report.html' : 'demo/report.html');
  if (route.startsWith('examples/')) await expect(demo).not.toHaveAttribute('aria-current', /.+/);
  const breadcrumbs = page.locator('.site-breadcrumbs');
  if (!route) {
    await expect(home).toHaveAttribute('aria-current', 'page');
  } else {
    await expect(breadcrumbs).toBeVisible();
    await expect(breadcrumbs.locator('[aria-current=page]')).toHaveCount(1);
    const parent = route.startsWith('guides/') ? '../#guides'
      : route === 'blog/index.html' ? '../'
        : route.startsWith('blog/') ? 'index.html'
          : route === 'demo/report.html' ? '../#examples' : '../';
    await expect(breadcrumbs.locator('a').last()).toHaveAttribute('href', parent);
  }
  const backTop = page.locator('a.site-back-top[href="#top"]');
  await expect(backTop).toBeVisible();
  if (!exercise) return;
  const menuBefore = await navigation.boundingBox();
  const disclosure = page.locator('details:visible').filter({has: page.locator('summary:visible')}).first();
  const hasDisclosure = await disclosure.count();
  const initiallyOpen = hasDisclosure ? await disclosure.getAttribute('open') !== null : false;
  if (hasDisclosure) await disclosure.locator('summary').first().click();
  await page.evaluate(() => window.scrollTo({top: document.scrollingElement.scrollHeight, behavior: 'instant'}));
  const maxScroll = await page.evaluate(() => document.documentElement.scrollHeight - innerHeight);
  if (maxScroll > 50) await expect.poll(() => page.evaluate(() => scrollY), {
    message: `${route || 'home'} leaves the document top before returning`,
  }).toBeGreaterThan(50);
  await returnToTop(page, route);
  const headingView = await page.locator('h1').evaluate(heading => {
    const box = heading.getBoundingClientRect();
    const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    const shell = heading.closest('.workspace-shell');
    return {visible: box.top >= 0 && box.bottom <= innerHeight && heading.contains(hit),
      top: box.top, bottom: box.bottom, width: innerWidth, height: innerHeight,
      shellScroll: shell && shell.scrollTop, hit: hit && hit.outerHTML.slice(0, 150)};
  });
  assert.equal(headingView.visible, true, `${route} returns to an unobscured heading: ${JSON.stringify(headingView)}`);
  const menuAfter = await navigation.boundingBox();
  for (const dimension of ['x', 'y', 'width', 'height']) {
    assert.ok(Math.abs(menuBefore[dimension] - menuAfter[dimension]) < 1, `${route} keeps its navigation geometry after returning`);
  }
  if (hasDisclosure) {
    assert.equal(await disclosure.getAttribute('open') !== null, !initiallyOpen,
      `${route} keeps the user's native disclosure state when returning to the top`);
    await disclosure.locator('summary').first().click();
    await returnToTop(page, route);
  }
}

async function assertDemoReadOnly(page) {
  const writers = 'input[type=file], textarea, [data-research-revise], [data-dossier-add-image], ' +
    '[data-dossier-claim], [data-dossier-decision], [data-use-passage], ' +
    '[data-geo-add], [data-geo-remove], [data-action], [data-manuscript-link-selection], ' +
    '[data-manuscript-link-accept], #research-revision-edit-tab, #research-revision-save, ' +
    '#research-revision-batch-add, #r-dos-create-btn, #r-claim-create-btn, #r-decision-create-btn, ' +
    '#r-ingest-btn, #r-zotero-browse';
  await expect(page.locator(`:is(${writers}):visible:not(:disabled)`)).toHaveCount(0);
  await expect(page.locator('a[href^="zotero:"]')).toHaveCount(0);
  for (const control of await page.locator('[data-demo-local]').all()) await expect(control).toBeDisabled();
  await expect(page.locator('[contenteditable=true]:visible')).toHaveCount(0);
}

async function checkDemoLocalControl(control) {
  // Native authoring sections may start compact, but remain inspectable.
  for (let depth = 0; depth < 8; depth++) {
    const closed = control.locator('xpath=ancestor::details[not(@open)][last()]');
    if (!await closed.count()) break;
    await closed.locator(':scope > summary').click();
  }
  await expect(control).toBeVisible();
  await expect(control).toBeDisabled();
  await expect(control).toHaveAttribute('data-demo-local', 'true');
  const note = control.locator('xpath=ancestor::*[.//*[contains(concat(" ",normalize-space(@class)," ")," demo-local-note ")]][1]')
    .locator('.demo-local-note').first();
  await expect(note).toBeVisible();
  await expect(note).toContainText(/Local app/i);
  const installation = note.locator('a[href="../guides/installation.html"]');
  await expect(installation).toBeVisible();
  assert.ok((await installation.innerText()).trim(), 'Local-only guidance includes a named installation link');
  await installation.focus();
  await expect(installation).toBeFocused();
  const description = await control.getAttribute('aria-describedby');
  assert.ok(description && description.split(/\s+/).includes(await note.getAttribute('id')),
    'The unavailable control is associated with its visible explanation');
}

async function checkGeographyInsights(page, geography) {
  await expect(geography).toContainText("Night watchman's walk");
  await expect(geography).toContainText("Customs officer's drive");
  const map = geography.locator('.geography-map.leaflet-container');
  await geography.scrollIntoViewIfNeeded();
  await expect(map).toBeVisible();
  await map.scrollIntoViewIfNeeded();
  await expect(geography.locator('[data-geo-basemap]')).toBeChecked();
  await expect(map.locator('.leaflet-tile-loaded').first()).toBeVisible();
  await expect(map.locator('.leaflet-control-attribution')).toContainText('OpenStreetMap');
  // Offline interactions remain independently testable after the default
  // background has been explicitly disabled, without changing the map view.
  await geography.locator('[data-geo-basemap]').uncheck();
  await expect(geography.locator('li')).toHaveCount(5);
  await expect(geography.locator('.geography-overview')).toContainText('5 located');
  await expect(geography.locator('.geography-overview')).toContainText('0 unplaced');
  await expect(geography.locator('.geography-legend')).toContainText('Route');
  const labels = await geography.locator('.geography-sketch text').evaluateAll(nodes => nodes.map(node => [node.getAttribute('x'), node.getAttribute('y')].join(',')));
  assert.equal(new Set(labels).size, labels.length, 'Canonical point and route number markers use distinct anchors');
  await withoutRequests(page, 'Map selection, context and framing stay local without tiles or writes', async () => {
    for (let index = 0; index < 5; index++) {
      await map.scrollIntoViewIfNeeded();
      const number = map.locator('.geography-map-number button[data-geo-select="' + index + '"]');
      if (await page.evaluate(() => navigator.maxTouchPoints > 0)) await number.tap();
      else await number.click();
      await expect(geography.locator('li').nth(index)).toHaveClass(/is-selected/);
    }
    for (const index of [0, 1]) {
      await map.scrollIntoViewIfNeeded();
      const point = map.locator('svg [data-geo-select="' + index + '"]');
      if (await page.evaluate(() => navigator.maxTouchPoints > 0)) await point.tap();
      else await point.click();
      await expect(geography.locator('li').nth(index)).toHaveClass(/is-selected/);
    }
    const route = geography.locator('.geography-feature-list [data-geo-feature-index="2"]');
    await route.locator('button[data-geo-select]').click();
    const selected = geography.locator('.geography-selected');
    await expect(selected).toContainText("Night watchman's walk");
    await expect(selected).toContainText('Night watchman');
    await expect(selected).toContainText(await route.locator('.geography-route-facts').innerText());
    await expect(geography.locator('[data-geo-frame]')).toBeEnabled();
    await geography.locator('[data-geo-frame]').click();
    await expect(map).toBeVisible();
    await expect(map.locator('svg [data-geo-select="2"]')).toHaveAttribute('aria-pressed', 'true');
    const focusedZoom = await map.evaluate(element => element._geographyMap.getZoom());
    await geography.locator('[data-geo-fit]').click();
    assert.ok(await map.evaluate(element => element._geographyMap.getZoom()) <= focusedZoom,
      'Fit all restores the full authored extent after framing one route');
    const method = geography.locator('.geography-method');
    await method.locator('summary').click();
    for (const paragraph of await method.locator('p').all()) await expect(paragraph).toBeVisible();
    await expect(method).toContainText('great-circle');
    await expect(method).toContainText('travel time');
    await method.locator('summary').click();
    await geography.locator('[data-geo-details]').click();
    await expect(route.locator('button[data-geo-select]')).toBeFocused();
    await geography.locator('[data-geo-clear]').click();
    await expect(geography.locator('[data-geo-frame]')).toBeDisabled();
    await expect(geography.locator('[data-geo-select][aria-pressed=true]')).toHaveCount(0);
    await route.locator('button[data-geo-select]').click();
    await expect(selected).toContainText("Night watchman's walk");
    await expect(geography.locator('[data-geo-basemap]')).not.toBeChecked();
  });
}

async function checkResearchDemo(page, javaScriptEnabled, width, colorScheme) {
  const notice = page.locator('#example-context');
  const credits = page.locator('#research-source-credits');
  await expect(notice).toContainText('read-only');
  await expect(notice).toContainText('Generated with Lixity');
  await expect(notice).toContainText('fictional');
  await expect(notice).toContainText('no live Zotero connection');
  await expect(notice).toContainText('retained passage, authored claim and manuscript quote are separate records');
  await expect(notice).toContainText('cannot import, edit or save');
  await expect(credits).toContainText('Richard Krause');
  await expect(credits).toContainText('Library of Congress');
  await expect(credits.locator('a[href="../assets/research/sources.json"]')).toBeVisible();
  function assertReadOnly() {
    return assertDemoReadOnly(page);
  }
  await assertReadOnly();
  if (!javaScriptEnabled) {
    await credits.locator('h2').scrollIntoViewIfNeeded();
    await expect(credits.locator('h2')).toBeInViewport();
    return;
  }
  await expect(page.locator('[data-rtab=dossiers]')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#research-dossiers-list .research-card')).toHaveCount(2);
  await page.locator('[data-rtab=sources]').click();
  await expect(page.locator('#research-sources-list .research-card')).toHaveCount(4);
  await expect(page.locator('#zotero-box')).not.toHaveAttribute('open', '');
  const zoteroReturn = page.locator('#research-sources-list .research-zotero-link');
  await expect(zoteroReturn).toHaveCount(1);
  await expect(zoteroReturn).toHaveAttribute('aria-disabled', 'true');
  await expect(zoteroReturn).not.toHaveAttribute('href', /.+/);
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
  await checkDemoLocalControl(detail.locator('[data-dossier-claim]'));
  await checkDemoLocalControl(detail.locator('[data-dossier-decision]'));
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
  await checkGeographyInsights(page, geography);
  const diagram = detail.locator('[data-research-diagram]').first();
  await diagram.scrollIntoViewIfNeeded();
  await expect(diagram).toHaveAttribute('data-diagram-state', 'ready');
  await expect(diagram.locator('.research-diagram-canvas')).toHaveAccessibleName('Diagram, scroll horizontally when needed');
  assert.ok(await diagram.locator('svg').evaluate(svg => [...svg.querySelectorAll('text')].every(text => {
    const transform = text.getScreenCTM();
    return parseFloat(getComputedStyle(text).fontSize) * Math.hypot(transform.a, transform.b) >= 12;
  })), 'Public research diagrams keep readable labels at every tested width');
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
  await expect(manuscriptReview.locator('blockquote')).toHaveText(demoQuote);
  await expect(manuscriptReview).toContainText('Exact passage');
  await expect(manuscriptReview).toContainText('Saved version 1');
  await manuscriptReview.locator('[data-research-history=claim]').click();
  await expect(history).toContainText('The customs log describes an attempted entry');
  await page.keyboard.press('Escape');
  await manuscriptReview.scrollIntoViewIfNeeded();
  await page.screenshot({path: path.join(artifacts, `research-manuscript-review-${width}-${colorScheme}.png`)});
  await assertReadOnly();
}

async function checkStyleInsights(page, javaScriptEnabled, width, colorScheme) {
  const dimensions = page.locator('#dimensions');
  if (javaScriptEnabled) await page.locator('#style-tab-dimensions').click();
  await expect(dimensions.locator('.dim-guide')).toContainText('chapter order');
  await expect(dimensions.locator('.dim-coverage')).toContainText('6 / 6');
  const cutoff = dimensions.locator('.dim-cutoff');
  await cutoff.locator('summary').click();
  await expect(cutoff.locator('p')).toBeVisible();
  await expect(cutoff).toContainText('not a confidence region');
  await cutoff.locator('summary').click();
  const expert = dimensions.locator('#dim-expert');
  await expert.locator('summary').click();
  await expect(expert.locator('p').first()).toBeVisible();
  await expect(expert).toContainText('standardized low-to-high feature ranks');
  await expect(expert.locator('table')).toHaveCount(3);
  await expert.locator('summary').click();
  const select = dimensions.locator('#dim-chapter-select');
  const projection = dimensions.locator('#dim-projection');
  if (!javaScriptEnabled) {
    await expect(select).toBeDisabled();
    await expect(projection).toBeDisabled();
    await expect(dimensions.locator('#dim-scores tbody tr')).toHaveCount(6);
    return;
  }
  await withoutRequests(page, 'Style selection and planar views require no requests or writes', async () => {
    await select.selectOption('2');
    const selected = dimensions.locator('#dim-selection');
    await expect(selected).toHaveAttribute('data-chapter', '2');
    const row = dimensions.locator('#dim-scores tbody tr').filter({has: page.locator('a[href="#ch-2"]')});
    assert.deepEqual(await selected.locator('dd').allTextContents(), await row.locator('td.num').allTextContents(),
      'Persistent scores match the public semantic score table');
    await expect(selected).toContainText(await row.locator('td').last().innerText());
    await expect(dimensions.locator('#dim-read-chapter')).toHaveAttribute('href', '#ch-2');
    const canvas = dimensions.locator('#dim-3d-canvas');
    const spatial = await canvas.evaluate(element => element.toDataURL());
    await projection.selectOption('d1-d2');
    await expect(canvas).toHaveAttribute('data-projection', 'd1-d2');
    assert.notEqual(await canvas.evaluate(element => element.toDataURL()), spatial,
      'The public planar control changes the rendered chapter plot');
    await page.mouse.move(0, 0);
    await expect(selected).toHaveAttribute('data-chapter', '2');
    await dimensions.screenshot({path: path.join(artifacts, `report-style-selected-${width}-${colorScheme}.png`)});
    await projection.selectOption('3d');
  });
}

async function checkReport(page, javaScriptEnabled, width, colorScheme) {
  assert.equal(await page.locator('.page').count(), 1, 'The example uses the generated report layout');
  assert.ok((await page.locator('.page').innerText()).length > 1000);
  await assertDemoReadOnly(page);
  assert.equal(await page.locator('.chapter').count(), 6);
  assert.ok(await page.locator('.chip').count() > 6, 'The report exposes actual paragraph blocks');
  await checkStyleInsights(page, javaScriptEnabled, width, colorScheme);
  if (javaScriptEnabled && (colorScheme !== 'light' || width === 390)) return;
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
  assert.ok((await passage.locator('.ptext-inner > p').innerText()).length > 50, 'Opening a block exposes the synthetic source paragraph');
  await passage.locator('.paragraph-values > summary').click();
  assert.ok((await passage.locator('.anchor').innerText()).length > 5, 'The passage includes source lines');
  await passage.locator('.ptext-inner > p').click();
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

async function checkDemoCapabilities(page, width) {
  for (const id of ['btn-modal-new-project', 'btn-modal-open-project']) {
    await checkDemoLocalControl(page.locator('#' + id));
  }
  await page.locator('#btn-modal-new-project').evaluate(control => {
    control.disabled = false;
    control.click();
  });
  await expect(page.locator('#modal-project-create')).not.toBeVisible();
  await expect(page.locator('#btn-modal-new-project')).toBeDisabled();
  assert.equal(await page.evaluate(async () => {
    try {
      await fetch('/api/research-dossier', {method: 'POST', body: '{}'});
      return false;
    } catch (_) { return true; }
  }), true, 'The public adapter rejects a write even when called outside a disabled form');
  await page.locator('#tab-view-project').click();
  await expect(page.locator('#view-pane-project')).toBeVisible();
  await checkDemoLocalControl(page.locator('[data-action=settings]'));
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    `Inspectable local settings stay within ${width}px`);
  await expect(page.locator('#view-pane-project')).toHaveCSS('opacity', '1');
  await page.locator('#controls').scrollIntoViewIfNeeded();
  await page.screenshot({path: path.join(artifacts, `demo-local-settings-${width}.png`)});
  await page.locator('#tab-view-analysis').click();

  // The native form downloads a reviewed copy without running PDF generation.
  await page.locator('#manuscript-pdf-title').click();
  await expect(page.locator('#manuscript-pdf')).toContainText(/prepared copies/i);
  await page.locator('#manuscript-pdf-layout').selectOption('book');
  const pdfDownload = page.waitForEvent('download');
  await page.locator('#manuscript-pdf-download').click();
  const pdf = await pdfDownload;
  assert.equal(pdf.suggestedFilename(), 'manuscript-book.pdf');
  const pdfPath = path.join(artifacts, `demo-book-${width}.pdf`);
  await pdf.saveAs(pdfPath);
  assert.deepEqual(fs.readFileSync(pdfPath), fs.readFileSync(path.join(root, 'demo/warehouse-4-book.pdf')),
    'The native PDF picker downloads the exact prepared book PDF');
  await expect(page.locator('#manuscript-pdf-layout')).toHaveValue('book');
  await page.locator('#manuscript-pdf-title').click();

  for (const id of ['heatmap', 'bands', 'dimensions', 'structural']) {
    const tab = page.locator(`[data-style-view="${id}"]`);
    await tab.click();
    await expect(tab).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('#' + id)).toBeVisible();
    await expect(page.locator('#style-panels > .panel:visible')).toHaveCount(1);
  }
  for (const link of await page.locator('#analysis-sections [data-section-link]').all()) {
    await link.click();
    const target = await link.getAttribute('data-section-link');
    await expect(page).toHaveURL(new RegExp('#' + target + '$'));
    await expect(page.locator('#' + target)).toBeVisible();
    await expect(page.locator('#' + target)).toBeInViewport();
  }

  await page.locator('[data-review-passage]').click();
  const passage = page.locator('#chapters .ptext.open').first();
  const passageId = await passage.getAttribute('id');
  const originalText = await passage.locator('p').first().innerText();
  await expect(passage.locator('[data-marker-kind]')).toHaveCount(4);
  await checkDemoLocalControl(passage.locator('[data-marker-kind]').first());

  const toggle = page.locator('#workspace-reader-toggle');
  await expect(toggle).toBeVisible();
  await toggle.click();
  await expect(page.locator('#workspace-reader-panel')).toBeVisible();
  const select = page.locator('#workspace-reader-dossier');
  await expect(select).toBeEnabled();
  await select.selectOption({label: 'Warehouse 4 case notes'});
  const reader = page.locator('#workspace-reader-body');
  await expect(reader.locator('h3').first()).toHaveText('Warehouse 4 case notes');
  await expect(reader.locator('.dossier-image img')).toHaveCount(2);
  await expect(reader.locator('[data-research-revise], [data-dossier-add-image], [data-use-passage]')).toHaveCount(0);
  await page.locator('#workspace-reader-close').click();
  await expect(page.locator('#workspace-reader-panel')).not.toBeVisible();
  await expect(toggle).toBeFocused();
  await expect(page.locator('#analysis-review')).toBeVisible();
  await expect(page.locator('#' + passageId + ' p').first()).toHaveText(originalText);

  await page.locator('#tab-view-research').click();
  await page.locator('[data-rtab=dossiers]').click();
  await checkDemoLocalControl(page.locator('#r-dos-create-btn'));
  const collapse = page.locator('[data-close-disclosure=r-dos-composer]');
  await expect(collapse).toBeEnabled();
  await collapse.click();
  await expect(page.locator('#r-dos-create-btn')).toBeHidden();
  await expect(page.locator('#r-dos-composer > summary')).toBeFocused();
  const dossier = page.locator('#research-dossiers-list .research-card').filter({hasText: 'Warehouse 4 case notes'});
  await checkDemoLocalControl(dossier.locator('[data-research-revise=dossier]'));
  await dossier.locator('[data-workspace-dossier]').click();
  await expect(page.locator('#tab-view-analysis')).toHaveAttribute('aria-selected', 'true');
  await expect(reader.locator('h3').first()).toHaveText('Warehouse 4 case notes');
  await reader.locator('[data-dossier-enlarge]').first().click();
  const enlarged = page.locator('#modal-dossier-image-enlarge');
  await expect(enlarged).toBeVisible();
  const enlargedImage = enlarged.locator('.pswp__item[aria-hidden=false] img.pswp__img');
  await expect(enlargedImage).toBeVisible();
  await expect.poll(() => enlargedImage.evaluate(image => image.naturalWidth)).toBeGreaterThan(0);
  await page.keyboard.press('Escape');
  await expect(enlarged).not.toBeVisible();
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    `The native companion reader stays within ${width}px`);
  await page.locator('#workspace-reader').scrollIntoViewIfNeeded();
  await page.screenshot({path: path.join(artifacts, `demo-companion-${width}.png`)});
  await select.press('Escape');
  await expect(page.locator('#workspace-reader-panel')).not.toBeVisible();
  await expect(toggle).toBeFocused();
  await expect(page.locator('#' + passageId + ' p').first()).toHaveText(originalText);

  await page.locator('#tab-view-research').click();
  for (const [tab, submit] of [['search', 'r-search-btn'], ['grounding', 'r-ground-btn']]) {
    await page.locator(`[data-rtab=${tab}]`).click();
    await expect(page.locator('#rtab-' + tab)).toBeVisible();
    await checkDemoLocalControl(page.locator('#' + submit));
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      `Local-only ${tab} guidance stays within ${width}px`);
  }
  await page.locator('[data-rtab=claims]').click();
  const matrixButton = page.locator('#r-claim-matrix-btn');
  await expect(matrixButton).toBeVisible();
  await expect(matrixButton).toBeEnabled();
  const matrixDownload = page.waitForEvent('download');
  await matrixButton.click();
  const matrix = await matrixDownload;
  assert.equal(matrix.suggestedFilename(), 'claim-evidence-matrix.md');
  const matrixPath = path.join(artifacts, `demo-claim-matrix-${width}.md`);
  await matrix.saveAs(matrixPath);
  const markdown = fs.readFileSync(matrixPath, 'utf8');
  assert.match(markdown, /^# Research Claim-Evidence Matrix: The Crate at Warehouse 4/m);
  assert.match(markdown, /Attempted warehouse entry/);
  assert.match(markdown, /\*\*Total Evidence Citations:\*\* 1/);
  assert.match(markdown, /Warehouse 4 case notes/);
  await expect(matrixButton).toBeEnabled();
  await assertDemoReadOnly(page);
  await page.locator('[data-rtab=dossiers]').click();
  await page.locator('#tab-view-analysis').click();
}

async function checkDemoWorkspace(page, javaScriptEnabled, width, colorScheme) {
  if (width >= 1100 && javaScriptEnabled) {
    const sidebar = await page.locator('.workspace-shell').boundingBox();
    const work = await page.locator('.view-pane.active').boundingBox();
    assert.ok(sidebar.x + sidebar.width <= work.x, 'The public demo retains the native desktop sidebar');
  }
  await expect(page.locator('h1')).toHaveText(demoTitle);
  if (javaScriptEnabled) {
    await expect(page.locator('#tab-view-project'), 'The public demo keeps the native Project & Settings workspace discoverable').toBeVisible();
  }
  for (const layout of ['editor', 'book', 'sheet', 'report']) {
    await expect(page.locator(`a[href="warehouse-4-${layout}.pdf"]`).first()).toBeVisible();
  }
  await checkReport(page, javaScriptEnabled, width, colorScheme);
  if (!javaScriptEnabled) {
    await checkResearchDemo(page, false, width, colorScheme);
    return;
  }
  await expect(page.locator('#tab-view-analysis')).toBeVisible();
  await expect(page.locator('#tab-view-research')).toBeVisible();
  await expect(page.locator('#tab-view-project')).toBeEnabled();
  await expect(page.locator('body')).toHaveAttribute('data-manuscript-links', 'read');
  if (colorScheme !== 'light' || width === 390) {
    await page.locator('#tab-view-research').click();
    await page.locator('[data-rtab=dossiers]').click();
    const dossier = page.locator('#research-dossiers-list .research-card').filter({hasText: 'Warehouse 4 case notes'});
    await dossier.locator('[data-research-detail=dossier]').click();
    const detail = dossier.locator('.research-details-body');
    await expect(detail.locator('.dossier-geography')).toBeVisible();
    await Promise.all((await detail.locator('.dossier-image img').all()).map(image =>
      image.evaluate(element => { element.loading = 'eager'; return element.decode(); })));
    await checkGeographyInsights(page, detail.locator('.dossier-geography'));
    await assertDemoReadOnly(page);
    await detail.locator('.dossier-geography').screenshot({path: path.join(artifacts, `research-geography-${width}-${colorScheme}.png`)});
    return;
  }
  await checkDemoCapabilities(page, width);
  // The saved research quotation belongs to the very manuscript being analysed.
  await page.locator('#text-search').fill(demoQuote);
  const passage = page.locator('#chapters .ptext.open').filter({hasText: demoQuote}).first();
  await expect(passage.locator('p').first()).toContainText(demoQuote);
  await passage.locator('.paragraph-values > summary').click();
  await page.locator('#style-layer').selectOption('asl');
  const passageId = await passage.getAttribute('id');
  const paragraphText = await passage.locator('p').first().innerText();
  await passage.locator('p').first().evaluate(node => {
    const range = document.createRange(); range.selectNodeContents(node);
    getSelection().removeAllRanges(); getSelection().addRange(range);
    document.dispatchEvent(new Event('selectionchange'));
  });
  await page.keyboard.press('Alt+l');
  await expect(page.locator('#manuscript-link-dialog, [data-manuscript-link-selection]')).toHaveCount(0);
  await page.evaluate(() => getSelection().removeAllRanges());
  await page.locator('#tab-view-analysis').focus();
  await page.keyboard.press('End');
  await expect(page.locator('#tab-view-project')).toBeFocused();
  await expect(page.locator('#tab-view-project')).toHaveAttribute('aria-selected', 'true');
  await page.keyboard.press(width >= 1100 ? 'ArrowUp' : 'ArrowLeft');
  await expect(page.locator('#tab-view-research')).toBeFocused();
  await expect(page.locator('#tab-view-research')).toHaveAttribute('aria-selected', 'true');
  await checkResearchDemo(page, true, width, colorScheme);
  await page.locator('#tab-view-analysis').click();
  await expect(page.locator('#text-search')).toHaveValue(demoQuote);
  await expect(page.locator('#style-layer')).toHaveValue('asl');
  await expect(page.locator('#' + passageId + ' .paragraph-values')).toHaveAttribute('open', '');
  await expect(page.locator('#' + passageId + ' p').first()).toHaveText(paragraphText);
  await expect(page.locator('#' + passageId + ' mark.manuscript-claim-hit')).toHaveText(demoQuote);
  await page.locator('#tab-view-research').click();
  await expect(page.locator('[data-rtab=review]')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#research-manuscript-review blockquote')).toHaveText(demoQuote);
  await page.locator('#research-manuscript-review [data-manuscript-link-jump]').click();
  await expect(page.locator('#tab-view-analysis')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#' + passageId)).toBeFocused();
  await page.locator('#view-pane-analysis, .view-nav-tab').evaluateAll(async nodes => {
    await Promise.all(nodes.flatMap(node => node.getAnimations().map(animation => animation.finished.catch(() => {}))));
  });
  await expect(page.locator('#view-pane-analysis')).toHaveCSS('opacity', '1');
  await expect(page.locator('#tab-view-analysis')).toBeEnabled();
  await expect(page.locator('#tab-view-research')).toBeEnabled();
  await page.locator('#' + passageId + ' p').first().scrollIntoViewIfNeeded();
  await expect(page.locator('#' + passageId + ' p').first()).toBeInViewport();
  await page.screenshot({path: path.join(artifacts, `demo-roundtrip-${width}.png`)});
}

async function checkLegacyResearchURL(page, javaScriptEnabled) {
  await page.goto('http://lixity.test/lixity/demo/research.html');
  await expect(page).toHaveURL('http://lixity.test/lixity/demo/report.html#research-manager');
  await expect(page.locator('h1')).toHaveText(demoTitle);
  await expect(page.locator('link[rel=canonical]')).toHaveAttribute('href', 'https://mfahsold.github.io/lixity/demo/report.html');
  if (javaScriptEnabled) {
    await expect(page.locator('#tab-view-research')).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('#research-manager')).toBeVisible();
  } else {
    await expect(page.locator('#chapters .ptext p').first()).toBeVisible();
    await expect(page.locator('#research-source-credits')).toContainText('Library of Congress');
  }
}

(async () => {
  const browser = await launchChromium();
  try {
    for (const [javaScriptEnabled, colorScheme, hasTouch = false] of [[true, 'light'], [false, 'light'], [true, 'dark'], [false, 'dark'], [true, 'light', true]]) {
      const context = await browser.newContext({javaScriptEnabled, colorScheme, hasTouch});
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
      await context.route('**/*', async route => {
        const request = route.request();
        const url = new URL(request.url());
        assert.equal(request.method(), 'GET', 'The public journey must make only static GET requests');
        if (url.origin === 'https://tile.openstreetmap.org' && /^\/\d+\/\d+\/\d+\.png$/.test(url.pathname) && !url.search) {
          // Synthetic tile bytes keep the default map journey deterministic;
          // published captures use normal current-viewport OSM requests.
          await route.fulfill({contentType: 'image/png', body: Buffer.from(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jC1sAAAAASUVORK5CYII=', 'base64')});
          return;
        }
        assert.equal(url.origin, 'http://lixity.test', 'Only the visible OSM map may request an external resource');
        assert.ok(url.pathname.startsWith('/lixity/'), 'The public journey must not call an API');
        const relative = decodeURIComponent(url.pathname).replace(/^\/lixity\//, '') || 'index.html';
        let file = path.resolve(root, relative);
        if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
        assert.ok(file.startsWith(root + path.sep));
        assert.ok(fs.existsSync(file), `Missing public asset ${relative}`);
        const contentType = {'.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.pdf': 'application/pdf'}[path.extname(file)];
        await route.fulfill({contentType, body: fs.readFileSync(file)});
      });
      for (const width of hasTouch ? [320] : [1440, 390, 320]) {
        await page.setViewportSize({width, height: 900});
        for (const route of routes) {
          if (hasTouch && route !== 'demo/report.html') continue;
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
          } else {
            assert.ok((await page.locator('main').innerText()).length > 1000,
              `${route} has too little visible text`);
          }
          assert.equal(await page.locator('link[rel=canonical]').getAttribute('href'), 'https://mfahsold.github.io/lixity/' + route);
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${route} overflows at ${width}px`);
          await checkReturnNavigation(page, route,
            colorScheme === 'light' && width !== 390 && returnJourneyRoutes.has(route));
          if (javaScriptEnabled && colorScheme === 'light' && width !== 390 &&
              (route === '' || route === 'guides/first-look.html' || (route === 'demo/report.html' && width === 320))) {
            await page.screenshot({path: path.join(artifacts, `navigation-${route ? path.basename(route, '.html') : 'home'}-${width}-light.png`)});
          }
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
          if (route === 'demo/report.html') await checkDemoWorkspace(page, javaScriptEnabled, width, colorScheme);
        }
        await page.goto('http://lixity.test/lixity/');
        await page.locator('.hero-cta a[href="guides/installation.html"]').click();
        assert.ok(page.url().endsWith('/guides/installation.html'), 'The secondary CTA opens local installation');
        await page.goto('http://lixity.test/lixity/');
        await page.locator('.release-note a[href="guides/first-look.html"]').click();
        assert.ok(page.url().endsWith('/guides/first-look.html'));
        await page.locator('.ctl[href="../demo/report.html"]').click();
        assert.ok(page.url().endsWith('/demo/report.html'));
        await page.locator('a[href="../guides/first-look.html"]').first().click();
        assert.ok(page.url().endsWith('/guides/first-look.html'), 'The report returns to the walkthrough');
        await page.locator('.site-breadcrumbs a[href="../#guides"]').click();
        await expect(page).toHaveURL('http://lixity.test/lixity/#guides');
        await expect(page.locator('#guides h2')).toBeInViewport();
        await returnToTop(page, 'Guides parent');
        await page.locator('.site-return a[href="./"]').click();
        await expect(page).toHaveURL('http://lixity.test/lixity/');
        await page.locator('.hero-cta a.primary[href="demo/report.html"]').click();
        assert.ok(page.url().endsWith('/demo/report.html'), 'The primary CTA opens the one demo directly');
        await page.locator('.site-return a').filter({hasText: /^Demo$/}).click();
        await expect(page).toHaveURL('http://lixity.test/lixity/demo/report.html');
        await page.locator('.site-breadcrumbs a[href="../"]').click();
        await expect(page).toHaveURL('http://lixity.test/lixity/');
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
          await page.locator('.site-return a[href="../"]').click();
          await expect(page).toHaveURL('http://lixity.test/lixity/');
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
        await page.locator('.site-breadcrumbs a[href="index.html"]').click();
        await expect(page).toHaveURL('http://lixity.test/lixity/blog/index.html');
        await expect(page.locator('article h2 a').first()).toHaveAttribute('href', path.basename(articleURL.pathname));
        await page.locator('.site-return a[href="../"]').click();
        await expect(page).toHaveURL('http://lixity.test/lixity/');
      }
      if (colorScheme === 'light') await checkLegacyResearchURL(page, javaScriptEnabled);
      assert.deepEqual(errors, []);
      await context.close();
    }
    console.log(`Public docs: ${routes.length} selected HTML pages at desktop/390/320, representative surfaces in light/dark and JS on/off, static GET-only navigation, one six-chapter demo Analysis/Research state roundtrip with evidence/quote and PDF links, legacy research redirect, case-study rendering, keyboard/focus/console passed. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
