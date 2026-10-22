const {selectMetric} = require('./support/analysis-controls.cjs');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
// Validate the public static site without contacting production or loading private data.
const fs = require('node:fs');
const path = require('node:path');
const {expect} = require(path.join(playwrightModule, 'test'));
const os = require('node:os');
const http = require('node:http');
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
const publicationRoutes = new Set(['demo/reader/index.html', 'demo/companion/index.html']);
for (const route of publicationRoutes) assert.ok(routes.includes(route), `Missing curated public example: ${route}`);
// Every content page gets all widths. Shared surface types cover theme/JS variants.
const fullMatrixRoutes = new Set(['', 'guides/first-look.html', 'guides/interpretation.html', 'guides/research-pdf.html', 'demo/report.html',
  'examples/effi-briest.html', 'blog/index.html', 'blog/whats-new-lixity.html', 'blog/manuscript-reading-workbench.html', ...publicationRoutes]);
const returnJourneyRoutes = new Set(['', 'guides/first-look.html', 'blog/index.html',
  'blog/whats-new-lixity.html', 'demo/report.html', 'examples/effi-briest.html', ...publicationRoutes]);
let origin;
const demoTitle = 'The Crate at Warehouse 4';
const demoQuote = 'Someone had tried the eastern gate of Warehouse 4.';
const demoSecondQuote = 'Fresh scratches crossed the lock';

function manuscriptReviewItem(page, quote = demoQuote) {
  return page.locator('#research-manuscript-review .manuscript-link-review-item')
    .filter({has: page.getByText(quote, {exact: true})});
}

async function openResearchVersions(page) {
  const versions = page.locator('#research-revision-versions');
  await expect(versions).toBeVisible();
  if (!await versions.evaluate(details => details.open)) await versions.locator(':scope > summary').click();
}

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

async function checkLazyPreviewStability(page) {
  let release;
  const held = new Promise(resolve => { release = resolve; });
  const imagePath = '**/screenshots/dashboard-dossier-image.png';
  const holdImage = async route => { await held; await route.fallback(); };
  await page.route(imagePath, holdImage);
  try {
    await page.goto(origin + '/lixity/guides/research-pdf.html', {waitUntil: 'domcontentloaded'});
    const image = page.locator('img[src="../screenshots/dashboard-dossier-image.png"]');
    await image.scrollIntoViewIfNeeded();
    const before = await image.boundingBox();
    assert.ok(before.height > 100, 'A lazy screenshot reserves its bounded preview before its bytes arrive');
    const followingTop = () => page.locator('#search').evaluate(node => node.getBoundingClientRect().top + scrollY);
    const beforeTop = await followingTop();
    release();
    await image.evaluate(node => node.decode());
    assert.ok(Math.abs(await followingTop() - beforeTop) <= 1,
      'Loading screenshot bytes must not move the following content');
  } finally {
    release();
    await page.unroute(imagePath, holdImage);
  }
}

async function showOverview(page) {
  const open = page.locator('#workbench-overview-open');
  if (await open.isVisible()) await open.click();
  await expect(page.locator('#workbench-overview-back')).toBeVisible();
  await expect(page.locator('#manuscript-analysis-panels')).toBeVisible();
}

async function openValues(page, passage) {
  const analysis = page.locator('#manuscript-analysis-toggle');
  const priorAnalysis = await analysis.getAttribute('aria-pressed');
  await passage.locator('.reader-paragraph-actions').click();
  await page.locator('#manuscript-context-menu [data-reader-action=values]').click();
  await expect(page.locator('#reader-inspector')).toBeVisible();
  await expect(analysis).toHaveAttribute('aria-pressed', priorAnalysis);
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
  const breadcrumbs = page.locator('.site-breadcrumbs');
  if (!route) {
    await expect(page.locator('.brand[href="./"]')).toHaveAttribute('aria-current', 'page');
    await expect(navigation.getByRole('link', {name: 'Home', exact: true})).toHaveCount(0);
    await expect(navigation.getByRole('link', {name: 'Demo', exact: true})).toHaveCount(0);
  } else if (route === 'demo/report.html') {
    await expect(navigation.getByRole('link', {name: 'About Lixity', exact: true})).toHaveAttribute('href', '../');
    await expect(navigation.locator('a')).toHaveCount(1);
    await expect(navigation).toContainText('Read-only demo');
    await expect(breadcrumbs).toHaveCount(0);
  } else if (publicationRoutes.has(route)) {
    await expect(navigation.locator('a')).toHaveCount(4);
    await expect(navigation.getByRole('link', {name:'Author workspace', exact:true})).toHaveAttribute('href', '../report.html');
    await expect(navigation.getByRole('link', {name:'Short tour', exact:true})).toHaveAttribute('href', '../../guides/first-look.html');
    await expect(breadcrumbs).toHaveCount(0);
  } else {
    if (route.startsWith('examples/')) {
      await expect(navigation.locator('a[href="../"]')).toBeVisible();
      const demo = navigation.getByRole('link', {name: 'Demo', exact: true});
      await expect(demo).toHaveAttribute('href', '../demo/report.html');
      await expect(demo).not.toHaveAttribute('aria-current', /.+/);
    } else {
      await expect(page.locator('.site-header .brand')).toHaveAttribute('href', '../');
      await expect(navigation.getByRole('link', {name: 'Guides', exact: true})).toHaveAttribute('href', '../#guides');
      await expect(navigation.getByRole('link', {name: 'Install', exact: true})).toHaveAttribute('href', route.startsWith('blog/') ? '../guides/installation.html' : 'installation.html');
      await expect(navigation.getByRole('link', {name: 'Demo', exact: true})).toHaveCount(0);
      await expect(page.locator('.guide-nav')).toHaveCount(0);
    }
    await expect(breadcrumbs).toBeVisible();
    await expect(breadcrumbs.locator('[aria-current=page]')).toHaveCount(1);
    const parent = route.startsWith('guides/') ? '../#guides'
      : route === 'blog/index.html' ? '../'
        : route.startsWith('blog/') ? 'index.html' : '../';
    await expect(breadcrumbs.locator('a').last()).toHaveAttribute('href', parent);
  }
  const backTop = page.locator('a.site-back-top[href="#top"]');
  await expect(backTop).toBeVisible();
  if (page.viewportSize().width <= 700 && await page.locator('body > main').count()) {
    const contentBottom = await page.locator('body > main').evaluate(node => node.getBoundingClientRect().bottom);
    const returnTop = await backTop.evaluate(node => node.getBoundingClientRect().top);
    assert.ok(returnTop >= contentBottom,
      `${route || 'home'} keeps mobile return navigation after the text instead of covering it`);
  }
  if (!exercise) return;
  const menuBefore = await navigation.boundingBox();
  // The Reading menu intentionally closes on focus leaving it. The public
  // provenance disclosure keeps the persistent native state checked here.
  const disclosure = route === 'demo/report.html' ? page.locator('#example-context')
    : page.locator('details:visible').filter({has: page.locator('summary:visible')}).first();
  const hasDisclosure = await disclosure.count();
  const initiallyOpen = hasDisclosure ? await disclosure.getAttribute('open') !== null : false;
  if (hasDisclosure) await disclosure.locator('summary').first().click();
  await page.evaluate(() => window.scrollTo({top: document.scrollingElement.scrollHeight, behavior: 'instant'}));
  const maxScroll = await page.evaluate(() => document.documentElement.scrollHeight - innerHeight);
  if (maxScroll > 50) await expect.poll(() => page.evaluate(() => scrollY), {
    message: `${route || 'home'} leaves the document top before returning`,
  }).toBeGreaterThan(50);
  await returnToTop(page, route);
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
  // Expanded native controls can move the authored heading below the fold.
  // Check the normal document after restoring the original disclosure state.
  const headingView = await page.locator('h1').evaluate(generated => {
    let heading = generated;
    if (document.body.matches('.has-source-title.manuscript-reading[data-workspace-view="analysis"]:not(.workbench-overview)')) {
      heading = document.querySelector('.reader-preface > .reader-heading');
      if (!heading) throw new Error('The matching authored reader heading is missing');
    }
    const box = heading.getBoundingClientRect();
    const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    const shell = heading.closest('.workspace-shell');
    return {visible: box.top >= 0 && box.bottom <= innerHeight && heading.contains(hit),
      top: box.top, bottom: box.bottom, width: innerWidth, height: innerHeight,
      shellScroll: shell && shell.scrollTop, hit: hit && hit.outerHTML.slice(0, 150)};
  });
  assert.equal(headingView.visible, true, `${route} returns to an unobscured heading: ${JSON.stringify(headingView)}`);
}

async function assertDemoReadOnly(page) {
  const writers = 'input[type=file], textarea, [data-research-revise], [data-dossier-add-image], ' +
    '[data-dossier-claim], [data-dossier-decision], [data-use-passage], [data-link-claim-evidence], ' +
    '[data-geo-add], [data-geo-remove], [data-action], [data-manuscript-link-selection], ' +
    '[data-manuscript-link-accept], #research-revision-edit-tab, #research-revision-save, ' +
    '#research-revision-batch-add, #r-dos-create-btn, #r-claim-create-btn, #r-decision-create-btn, ' +
    '#r-ingest-btn, #r-zotero-browse';
  await expect(page.locator(`:is(${writers}):visible:not(:disabled)`)).toHaveCount(0);
  await expect(page.locator('a[href^="zotero:"]')).toHaveCount(0);
  await expect(page.locator('body')).toHaveAttribute('data-read-only', 'true');
  await expect(page.locator('[data-requires-write]:visible, [data-requires-live]:visible')).toHaveCount(0);
  await expect(page.locator('.demo-local-note, [data-demo-local]')).toHaveCount(0);
  await expect(page.locator('[contenteditable=true]:visible')).toHaveCount(0);
}

async function checkPublicationExample(page, route, javaScriptEnabled, width, colorScheme) {
  const reader = route === 'demo/reader/index.html';
  await assertDemoReadOnly(page);
  await expect(page.locator('#research-manager, #manuscript-analysis-panels')).toHaveCount(0);
  await expect(page.locator('.publication-introduction')).toContainText('Keep this context beside the story');
  if (reader) {
    await expect(page.locator('.publication-novel .chapter')).toHaveCount(6);
    await expect(page.locator('.publication-novel')).toContainText(demoQuote);
  } else {
    await expect(page.locator('.publication-novel, #chapters')).toHaveCount(0);
    assert.ok(!(await page.content()).includes('A blank signature is an absence, not a name.'),
      'The chapter-three companion cap removes the late note from every byte');
  }
  if (!javaScriptEnabled) {
    await expect(page.locator('#publication-context noscript')).toBeVisible();
    await expect(page.locator('#publication-entries article')).toHaveCount(0);
    return;
  }
  await page.locator('#publication-progress-reset').click();
  const entries = page.locator('#publication-entries'), contents = page.locator('#publication-contents');
  await expect(entries.locator('article')).toHaveCount(3);
  await expect(contents).not.toContainText('Light and sound');
  await expect(contents).not.toContainText('The receiving signature');
  const images = await entries.locator('.dossier-image img').all();
  assert.equal(images.length, 2);
  await Promise.all(images.map(image => image.evaluate(element => {element.loading='eager';return element.decode();})));
  assert.ok(await images[0].evaluate(element => element.naturalWidth > 1000));
  await withoutRequests(page, 'Published progress, search and preview never call an API or load hidden assets', async () => {
    await page.locator('#publication-progress').selectOption('3');
    await expect(entries.locator('article')).toHaveCount(3);
    await page.locator('#publication-progress-apply').click();
    await expect(entries.locator('article')).toHaveCount(5);
    await page.locator('#publication-context-search').fill('The receiving signature');
    await expect(entries.locator('article')).toHaveCount(0);
    await page.locator('#publication-context-search').fill('');
    await expect(entries.locator('article')).toHaveCount(5);
    if (reader) {
      await page.locator('#publication-preview-open').click();
      await page.locator('#publication-preview-progress').selectOption('6');
      await page.locator('#publication-preview-form button[type=submit]').click();
      await expect(entries).toContainText('A blank signature is an absence, not a name.');
      await expect(page.locator('#publication-progress')).toHaveValue('3');
      await page.locator('#publication-preview-close').click();
      await expect(entries).not.toContainText('The receiving signature');
    } else {
      await expect(page.locator('#publication-progress option[value="6"]')).toHaveCount(0);
    }
    await contents.getByRole('link', {name:'Light and sound', exact:true}).click();
    await expect(entries.getByRole('heading', {name:'Light and sound', exact:true})).toBeFocused();
  });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.locator('#publication-progress-reset').click();
  await page.locator('#publication-context').evaluate(context => context.scrollTo({top:0, behavior:'instant'}));
  await page.evaluate(() => window.scrollTo({top:0, behavior:'instant'}));
  await page.screenshot({path:path.join(artifacts, `publication-${reader?'reader':'companion'}-${width}-${colorScheme}.png`)});
}

async function checkGeographyInsights(page, geography) {
  await expect(geography).toContainText("Night watchman's walk");
  await expect(geography).toContainText("Customs officer's drive");
  const map = geography.locator('.geography-map.leaflet-container');
  await geography.scrollIntoViewIfNeeded();
  await expect(map).toBeVisible();
  await map.scrollIntoViewIfNeeded();
  await expect(geography.locator('[data-geo-basemap]')).toBeHidden();
  await expect(geography.locator('[data-geo-basemap]')).not.toBeChecked();
  await expect(map.locator('.leaflet-tile')).toHaveCount(0);
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
    await expect(geography.locator('[data-geo-basemap]')).toBeHidden();
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
  await expect(zoteroReturn).toHaveCount(0);
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
  await expect(detail.locator('[data-dossier-claim], [data-dossier-decision]')).toHaveCount(0);
  const authoredClaim = detail.locator('.research-dossier-claims-list li').filter({hasText: 'Attempted warehouse entry'});
  await expect(authoredClaim.locator('[data-manuscript-link-count="2"]')).toBeVisible();
  await expect(authoredClaim.locator('[data-claim-revision="2"]')).toBeVisible();
  await expect(detail.locator('.dossier-image img')).toHaveCount(2);
  const dossierImages = await detail.locator('.dossier-image img').all();
  await Promise.all(dossierImages.map(image => image.evaluate(element => { element.loading = 'eager'; return element.decode(); })));
  let imageIndex = 0;
  for (const image of dossierImages) {
    await image.evaluate(element => { element.loading = 'eager'; return element.decode(); });
    assert.ok(await image.evaluate(element => element.naturalWidth > 1000 && element.naturalHeight > 1000), 'Reviewed public images decode at their original resolution');
    assert.match(await image.getAttribute('src'), /^assets\/sources\/[0-9a-f]{64}\.jpg$/);
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
  const versions = page.locator('#research-revision-versions');
  await expect(versions).toBeVisible();
  assert.equal(await versions.evaluate(details => details.open), false,
    'The public entry opens with its version list collapsed');
  await versions.locator(':scope > summary').click();
  await page.locator('#research-revision-history-list [data-research-revision="1"]').click();
  await expect(history.locator('.dossier-image img')).toHaveCount(0);
  await expect(history.locator('.dossier-geography')).toContainText("Night watchman's walk");
  await page.keyboard.press('Escape');
  await page.locator('[data-rtab=claims]').click();
  await expect(page.locator('#research-claims-list .research-card')).toHaveCount(6);
  const claim = page.locator('#research-claims-list .research-card').filter({hasText: 'Attempted warehouse entry'});
  await claim.locator('[data-load-evidence]').click();
  await expect(claim.locator('.claim-evidence-subpanel')).toContainText('synthetic');
  await expect(claim.locator('.claim-evidence-subpanel .research-passage-card')).toHaveCount(3);
  await expect(claim.locator('.claim-evidence-subpanel')).toContainText('Qualifies');
  const inspection = page.locator('#research-claims-list .research-card').filter({hasText: 'Where the crate was opened'});
  await inspection.locator('[data-load-evidence]').click();
  await expect(inspection.locator('.claim-evidence-subpanel .research-passage-card')).toHaveCount(3);
  const contradiction = inspection.locator('.research-passage-card').filter({has: page.getByText('Contradicts', {exact: true})});
  await expect(contradiction).toContainText('The signed correction explicitly places the first opening at the station.');
  await contradiction.locator('[data-research-history=evidence_link]').click();
  await expect(page.locator('#research-revision-kind')).toContainText('Evidence link · Version 1');
  await expect(history).toContainText('Contradicts');
  await expect(history).toContainText('the crate was first opened at the customs station at six ten');
  await assertReadOnly();
  await openResearchVersions(page);
  await expect(page.locator('#research-revision-history-list [data-research-revision]')).toHaveCount(1);
  await page.locator('#research-revision-history-list [data-research-revision="1"]').click();
  await expect(history).toContainText('The signed correction explicitly places the first opening at the station.');
  await page.keyboard.press('Escape');
  const emptyClaim = page.locator('#research-claims-list .research-card').filter({hasText: 'Harbour tour research notes'});
  await emptyClaim.locator('[data-load-evidence]').click();
  await expect(emptyClaim.locator('.claim-evidence-subpanel')).toContainText('No evidence linked to this claim.');
  await expect(emptyClaim.locator('[data-link-claim-evidence]')).toHaveCount(0);
  await expect(page.locator('#r-link-composer')).toBeHidden();
  await emptyClaim.screenshot({path: path.join(artifacts, `research-empty-evidence-${width}-${colorScheme}.png`)});
  await page.locator('#r-open-timeline').click();
  await expect(page.locator('#research-claims-timeline .research-timeline-strip-row')).toHaveCount(5);
  await expect(page.locator('#research-claims-timeline .research-timeline-unplaced > li')).toHaveCount(1);
  await expect(page.locator('#research-claims-timeline')).toContainText('present day');
  await page.locator('[data-claim-view=list]').click();
  const causalLink = page.locator('#research-claim-relations .research-relation-card');
  await expect(causalLink).toHaveCount(1);
  await expect(causalLink).toContainText('The cracked lid delayed inspection');
  await expect(causalLink).toContainText('Where the crate was opened');
  await expect(causalLink).toContainText('is proposed to cause');
  await causalLink.locator('[data-research-history=claim_relation]').click();
  await expect(page.locator('#research-revision-kind')).toContainText('Cause/effect link · Version 1');
  await expect(history).toContainText('The cracked lid delayed inspection');
  await expect(history).toContainText('Where the crate was opened');
  await expect(history).toContainText('This link does not verify causality.');
  await assertReadOnly();
  await openResearchVersions(page);
  await expect(page.locator('#research-revision-history-list [data-research-revision]')).toHaveCount(1);
  await page.locator('#research-revision-history-list [data-research-revision="1"]').click();
  await expect(history).toContainText('This link does not verify causality.');
  await page.keyboard.press('Escape');
  await assertReadOnly();
  await page.locator('[data-rtab=decisions]').click();
  await expect(page.locator('#research-decisions-list .research-card')).toHaveCount(3);
  await page.locator('[data-rtab=review]').click();
  await expect(page.locator('#research-editorial-review')).not.toContainText('Loading');
  await expect(page.locator('#research-editorial-review')).toContainText('Warehouse 4 case notes');
  const decisionComparison = page.locator('#research-editorial-review .research-card')
    .filter({has: page.getByText('Keep the inspection at dawn', {exact: true})})
    .locator('[data-decision-review]');
  await expect(decisionComparison).toHaveCount(1);
  await decisionComparison.locator(':scope > summary').click();
  await expect(decisionComparison.locator('.research-decision-review-grid')).toBeVisible();
  await expect(decisionComparison.locator('[data-decision-review-latest="decision"]')).toContainText('Latest decision · version');
  await expect(decisionComparison.locator('[data-decision-review-latest="dossier"]')).toContainText('Warehouse 4 case notes');
  await decisionComparison.locator('[data-decision-review-close]').click();
  await expect(decisionComparison).not.toHaveAttribute('open', '');
  await assertReadOnly();
  const manuscriptReview = page.locator('#research-manuscript-review');
  await expect(manuscriptReview.locator('.manuscript-link-review-item')).toHaveCount(5);
  await expect(manuscriptReview.locator('blockquote')).toHaveText([
    demoQuote, demoSecondQuote, 'One plank cracked.',
    'The crate was first opened at the customs station at six ten.',
    'Cart seventeen: returned, six forty in the evening.',
  ]);
  const originalReview = manuscriptReviewItem(page);
  await expect(originalReview).toHaveCount(1);
  await expect(originalReview).toContainText('Attempted warehouse entry');
  await expect(originalReview).toContainText('Exact passage');
  await expect(originalReview).toContainText('Claim has a newer version');
  await expect(originalReview.locator('[data-research-history=claim]')).toHaveAttribute('data-record-revision', '1');
  await expect(originalReview.locator('[data-research-history=claim]')).toHaveText('Linked version 1');
  await originalReview.locator('[data-research-history=claim]').click();
  await expect(history).toContainText('The customs log describes an attempted entry');
  await expect(history).not.toContainText('the implement, people and launch connection remain unconfirmed');
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
  assert.equal(await page.locator('.chapter[data-start]').count(), 6,
    'The report retains six profiled chapters alongside readable front matter');
  assert.ok(await page.locator('.chip').count() > 6, 'The report exposes actual paragraph blocks');
  if (javaScriptEnabled) {
    await expect(page.locator('#manuscript-analysis-toggle')).toHaveAttribute('aria-pressed', 'false');
    await expect(page.locator('#chapters .ptext-inner > p').first()).toBeVisible();
    await expect(page.locator('#reader-preface')).toBeVisible();
    await showOverview(page);
  }
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
  await expect(page.locator('#manuscript-analysis-toggle')).toHaveAttribute('aria-pressed', 'false');
  await page.locator('#manuscript-analysis-toggle').click();
  const chip = page.locator('#ch-2 .chip').first();
  await expect(chip).toBeVisible();
  const target = await chip.getAttribute('data-target');
  const passage = page.locator('#' + target);
  assert.equal(await chip.getAttribute('aria-expanded'), 'false');
  await chip.focus();
  await page.keyboard.press('Enter');
  assert.equal(await chip.getAttribute('aria-expanded'), 'true');
  await expect(passage).toBeVisible();
  await expect(passage).toHaveCSS('opacity', '1');
  assert.ok((await passage.locator('.ptext-inner > p').innerText()).length > 50, 'Opening a block exposes the synthetic source paragraph');
  await openValues(page, passage);
  assert.ok((await page.locator('#reader-inspector .anchor').innerText()).length > 5,
    'Passage values include the selected source lines');
  await passage.locator('.ptext-inner > p').click();
  await page.screenshot({path: path.join(artifacts, `report-passage-${width}-${colorScheme}.png`)});
  await page.locator('#reader-inspector-close').click();
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
  await selectMetric(page, 'asl');
  assert.equal(await page.locator('#layer-legend').isVisible(), true);
  assert.ok(await page.locator('.chip.has-layer').count() > 0, 'Selecting a layer changes actual paragraph data');
  await page.locator('#paragraph-filter-reset').click();
  assert.equal(await page.locator('#style-layer').inputValue(), '');
  assert.equal(await page.locator('#layer-legend').isVisible(), false);
  const canvas = page.locator('#dim-3d-canvas');
  await showOverview(page);
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

async function checkSavedPassageContext(page, width) {
  const overviewBack = page.locator('#workbench-overview-back');
  if (await overviewBack.isVisible()) await overviewBack.click();
  await expect(page.locator('#chapters')).toBeVisible();
  const passage = page.locator('#chapters .ptext').filter({hasText: demoQuote}).first();
  const prose = passage.locator('.ptext-inner > p');
  const original = await prose.textContent();
  await passage.locator('[data-reader-paragraph]').click();
  await page.locator('#manuscript-context-menu [data-reader-action=values]').click();
  await page.locator('#reader-inspector-body [data-reader-action=research]').click();
  const context = page.locator('#workspace-context-panel [data-passage-research]');
  await expect(context).toHaveAttribute('data-state', 'ready');
  await expect(context.locator('.passage-research-item')).toHaveCount(1);
  const associations = context.locator('[data-passage-research-associations]');
  await expect(associations).not.toHaveAttribute('open', '');
  await expect(associations.locator(':scope > summary')).toHaveText('Text associations (2)');
  await expect(associations.locator('blockquote')).toHaveCount(2);
  await expect(associations.locator('blockquote').first()).toBeHidden();
  await associations.locator(':scope > summary').click();
  await expect(associations.locator('blockquote')).toHaveText([demoQuote, demoSecondQuote]);
  await expect(context).toContainText('Attempted warehouse entry');
  await expect(context).toContainText('Warehouse 4 case notes');
  const decisions = context.locator('[data-passage-research-decisions]');
  await expect(decisions).not.toHaveAttribute('open', '');
  await expect(decisions.locator(':scope > summary')).toHaveText('3 decisions in current dossier');
  await decisions.locator(':scope > summary').click();
  await expect(decisions.locator('[data-research-history=decision]')).toHaveCount(3);
  await expect(decisions).toContainText('Keep the inspection at dawn');
  await expect(decisions).toContainText('Move the discovery scene');
  await expect(decisions).toContainText('Leave the receiving signature blank');
  await context.locator('.passage-record-title[data-research-history=claim]').click();
  await expect(page.locator('#research-revision-kind')).toContainText('Claim · Version 2');
  await expect(page.locator('#research-revision-history-detail')).toContainText('the implement, people and launch connection remain unconfirmed');
  await page.keyboard.press('Escape');
  await context.locator('.passage-record-pin[data-research-history=claim][data-record-revision="1"]').click();
  await expect(page.locator('#research-revision-kind')).toContainText('Claim · Version 1');
  await expect(page.locator('#research-revision-history-detail')).toContainText('The customs log describes an attempted entry');
  await page.keyboard.press('Escape');
  await expect(context).toBeVisible();
  await page.locator('#workspace-context-panel').screenshot({path: path.join(artifacts, `demo-passage-research-${width}.png`)});
  await context.locator('[data-passage-research-close]').click();
  await expect(context).toBeHidden();
  const back = page.locator('#workbench-return');
  if (await back.isVisible()) await back.click();
  await expect(prose).toHaveText(original);
  await assertDemoReadOnly(page);
}

async function checkDemoCapabilities(page, width) {
  for (const selector of ['#btn-modal-new-project', '#btn-modal-open-project', '#tab-view-project', '[data-action=settings]']) {
    await expect(page.locator(selector)).toBeHidden();
  }
  await withoutRequests(page, 'The production website transport rejects every mutation before network access', async () => {
    for (const endpoint of ['/api/research-dossier', '/api/manuscript-pdf']) {
      assert.equal(await page.evaluate(async endpoint => {
        try { await fetch(endpoint, {method: 'POST', body: '{}'}); return false; }
        catch (_) { return true; }
      }, endpoint), true);
    }
  });
  await page.locator('#tab-view-analysis').click();
  await checkSavedPassageContext(page, width);

  const pdfDownload = page.waitForEvent('download');
  await page.locator('#demo-downloads a[href="warehouse-4-book.pdf"]').click();
  const pdf = await pdfDownload;
  assert.equal(pdf.suggestedFilename(), 'warehouse-4-book.pdf');
  const pdfPath = path.join(artifacts, `demo-book-${width}.pdf`);
  await pdf.saveAs(pdfPath);
  assert.deepEqual(fs.readFileSync(pdfPath), fs.readFileSync(path.join(root, 'demo/warehouse-4-book.pdf')),
    'The website downloads the exact reviewed book PDF');

  await showOverview(page);
  for (const id of ['heatmap', 'bands', 'dimensions', 'structural']) {
    const tab = page.locator(`[data-style-view="${id}"]`);
    await tab.click();
    await expect(tab).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('#' + id)).toBeVisible();
    await expect(page.locator('#style-panels > .panel:visible')).toHaveCount(1);
  }
  const reviewLinks = page.locator('#analysis-review [data-jump]');
  await expect(reviewLinks).toHaveCount(2);
  for (const link of await reviewLinks.all()) {
    await link.click();
    const target = await link.getAttribute('data-jump');
    await expect(page).toHaveURL(new RegExp(target + '$'));
    await expect(page.locator(target)).toBeVisible();
    await expect(page.locator(target)).toBeInViewport();
  }

  await page.locator('[data-review-passage]').click();
  const passage = page.locator('#chapters .ptext.open').first();
  const passageId = await passage.getAttribute('id');
  const originalText = await passage.locator('p').first().innerText();
  await expect(passage.locator('[data-marker-kind]:visible')).toHaveCount(0);
  await passage.locator('.reader-paragraph-actions').click();
  await expect(page.locator('#manuscript-context-menu [data-reader-action=todo]')).toHaveCount(0);
  await page.keyboard.press('Escape');

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
  await expect(page.locator('#chapters')).toBeVisible();
  await expect(page.locator('#workbench-overview-open')).toBeVisible();
  await expect(page.locator('#manuscript-analysis-toggle')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#' + passageId + ' p').first()).toHaveText(originalText);

  await page.locator('#tab-view-research').click();
  await page.locator('[data-rtab=dossiers]').click();
  await expect(page.locator('#r-dos-composer')).toBeHidden();
  const dossier = page.locator('#research-dossiers-list .research-card').filter({hasText: 'Warehouse 4 case notes'});
  await expect(dossier.locator('[data-research-revise=dossier]')).toHaveCount(0);
  await dossier.locator('[data-workspace-dossier]').click();
  await expect(page.locator('#tab-view-analysis')).toHaveAttribute('aria-selected', 'true');
  await expect(reader.locator('h3').first()).toHaveText('Warehouse 4 case notes');
  const companionImage = reader.locator('[data-dossier-enlarge]').first();
  await companionImage.locator('..').scrollIntoViewIfNeeded();
  await companionImage.locator('img').evaluate(image => image.decode());
  await companionImage.click();
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
  await page.locator('#workspace-reader-close').click();
  await expect(page.locator('#workspace-reader-panel')).not.toBeVisible();
  await expect(toggle).toBeFocused();
  await expect(page.locator('#' + passageId + ' p').first()).toHaveText(originalText);

  await page.locator('#tab-view-research').click();
  for (const tab of ['search', 'grounding']) {
    await expect(page.locator(`[data-rtab=${tab}]`)).toBeHidden();
    await expect(page.locator('#rtab-' + tab)).toBeHidden();
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
  assert.match(markdown, /\*\*Total Evidence Citations:\*\* 8/);
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
  const context = page.locator('details#example-context');
  await expect(context).not.toHaveAttribute('open', '');
  await context.locator(':scope > summary').click();
  await expect(context).toContainText('cannot import, edit or save');
  await expect(context.locator('a[href="../guides/installation.html"]')).toBeVisible();
  await context.locator(':scope > summary').click();
  if (javaScriptEnabled && (width === 320 || width === 390)) {
    await page.locator('#tab-view-analysis').click();
    await expect(page.locator('#chapters')).toBeVisible();
    const firstProseY = await page.locator('#chapters .ptext-inner > p').first().evaluate(
      paragraph => paragraph.getBoundingClientRect().top + scrollY,
    );
    assert.ok(firstProseY < 1200, `The compact demo reaches prose within 1200px, got ${firstProseY}`);
  }
  if (javaScriptEnabled) {
    await expect(page.locator('#tab-view-project')).toBeHidden();
    await expect(page.locator('.site-read-only-notice')).toBeVisible();
  }
  for (const layout of ['editor', 'book', 'sheet', 'report', 'document']) {
    await expect(page.locator(`a[href="warehouse-4-${layout}.pdf"]`).first()).toBeVisible();
  }
  await checkReport(page, javaScriptEnabled, width, colorScheme);
  if (!javaScriptEnabled) {
    await checkResearchDemo(page, false, width, colorScheme);
    return;
  }
  await expect(page.locator('#tab-view-analysis')).toBeVisible();
  await expect(page.locator('#tab-view-research')).toBeVisible();
  await expect(page.locator('#tab-view-project')).toBeHidden();
  await expect(page.locator('body')).toHaveAttribute('data-manuscript-links', 'read');
  const quickStart = page.locator('#demo-quick-start');
  await expect(quickStart).toBeVisible();
  await quickStart.getByRole('button', {name: 'Read the manuscript'}).click();
  await expect(page.locator('#tab-view-analysis')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#view-pane-analysis')).toBeVisible();
  await quickStart.getByRole('button', {name: 'Explore research'}).click();
  await expect(page.locator('#tab-view-research')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#view-pane-research')).toBeVisible();
  await assertDemoReadOnly(page);
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
  await expect(passage.locator('mark.text-hit')).toHaveText(demoQuote);
  await expect(page.locator('#text-search-status')).toContainText('1 matching blocks');
  await expect.poll(() => passage.evaluate(node => node.classList.contains('flash')), {
    message: 'The manuscript search reaches its marked passage before opening Values',
  }).toBe(true);
  await openValues(page, passage);
  const inspectedValues = await page.locator('#reader-inspector-body').textContent();
  await selectMetric(page, 'asl');
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
  await expect(page.locator('#tab-view-research')).toBeFocused();
  await expect(page.locator('#tab-view-research')).toHaveAttribute('aria-selected', 'true');
  await page.keyboard.press(width >= 1100 ? 'ArrowUp' : 'ArrowLeft');
  await expect(page.locator('#tab-view-analysis')).toBeFocused();
  await page.keyboard.press(width >= 1100 ? 'ArrowDown' : 'ArrowRight');
  await expect(page.locator('#tab-view-research')).toBeFocused();
  await expect(page.locator('#tab-view-research')).toHaveAttribute('aria-selected', 'true');
  await checkResearchDemo(page, true, width, colorScheme);
  await page.locator('#tab-view-analysis').click();
  await expect(page.locator('#text-search')).toHaveValue(demoQuote);
  await expect(page.locator('#style-layer')).toHaveValue('asl');
  await expect(page.locator('#reader-inspector')).toBeVisible();
  await expect(page.locator('#reader-inspector .paragraph-values')).toHaveAttribute('open', '');
  assert.equal(await page.locator('#reader-inspector-body').textContent(), inspectedValues,
    'Returning from research preserves the selected passage values');
  await expect(page.locator('#' + passageId + ' p').first()).toHaveText(paragraphText);
  await expect(page.locator('#' + passageId + ' mark.manuscript-claim-hit')).toHaveText([demoQuote, demoSecondQuote]);
  await page.locator('#tab-view-research').click();
  await expect(page.locator('[data-rtab=review]')).toHaveAttribute('aria-selected', 'true');
  const originalReview = manuscriptReviewItem(page);
  await expect(originalReview.locator('blockquote')).toHaveText(demoQuote);
  await originalReview.locator('[data-manuscript-link-jump]').click();
  await expect(page.locator('#tab-view-analysis')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#' + passageId)).toBeFocused();
  await expect.poll(() => page.locator('#' + passageId).evaluate(panel => {
    const toolbar = document.querySelector('#manuscript-reader-controls');
    const top = panel.getBoundingClientRect().top;
    const boundary = getComputedStyle(toolbar).position === 'sticky'
      ? toolbar.getBoundingClientRect().bottom : 0;
    return top >= boundary && top < innerHeight;
  })).toBe(true);
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
  await page.goto(origin + '/lixity/demo/research.html');
  await expect(page).toHaveURL(origin + '/lixity/demo/report.html#research-manager');
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
  let browser;
  // Chromium's native download requests bypass Playwright routing. Serve only
  // the staged local files so a download cannot escape to a public hostname.
  const staticRequests = [];
  const server = http.createServer((request, response) => {
    staticRequests.push({method: request.method, path: request.url});
    const url = new URL(request.url, 'http://localhost');
    const relative = decodeURIComponent(url.pathname).replace(/^\/lixity\//, '');
    const file = path.resolve(root, relative);
    if (request.method !== 'GET' || !url.pathname.startsWith('/lixity/') ||
        !file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
      response.writeHead(404); response.end(); return;
    }
    response.writeHead(200, {'Content-Type': {'.pdf': 'application/pdf', '.txt': 'text/plain',
      '.jpg': 'image/jpeg', '.png': 'image/png'}[path.extname(file)] || 'application/octet-stream'});
    response.end(fs.readFileSync(file));
  });
  try {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    origin = 'http://127.0.0.1:' + server.address().port;
    browser = await launchChromium();
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
        assert.equal(url.origin, origin, 'The website never requests external map tiles or private APIs');
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
          if (!route && javaScriptEnabled && colorScheme === 'light' && !hasTouch && width !== 390) {
            await checkLazyPreviewStability(page);
          }
          await page.goto(origin + '/lixity/' + route);
          assert.equal(await page.locator('h1').count(), 1);
          const headings = await page.locator('h1,h2,h3,h4,h5,h6').evaluateAll(nodes => nodes.map(node => Number(node.tagName[1])));
          headings.forEach((level, index) => {
            if (index) assert.ok(level <= headings[index - 1] + 1, `${route} skips a heading level`);
          });
          assert.deepEqual(await page.locator('main img').evaluateAll(nodes => nodes
            .filter(node => !(Number(node.getAttribute('width')) > 0 && Number(node.getAttribute('height')) > 0))
            .map(node => node.getAttribute('src'))), [], `${route} has images without dimensions`);
          // Lazy images are measured after the user reaches them, not while
          // their intrinsic bytes are still unavailable below the viewport.
          for (const image of await page.locator('figure.frame img, figure.walkthrough img').all()) {
            if (!await image.evaluate(node => node.getClientRects().length > 0)) continue;
            await image.scrollIntoViewIfNeeded();
            await image.evaluate(node => node.decode());
          }
          const previews = await page.locator('figure.frame :is(img, video), figure.walkthrough :is(img, video)').evaluateAll(nodes =>
            nodes.filter(node => node.getClientRects().length > 0).map(node => {
              const box = node.getBoundingClientRect();
              return {source: node.getAttribute('src') || node.getAttribute('poster'),
                width: box.width, height: box.height,
                aspect: Number(node.getAttribute('width')) / Number(node.getAttribute('height')),
                fit: getComputedStyle(node).objectFit,
                fullSize: node.tagName !== 'IMG' || node.closest('a')?.getAttribute('href') === node.getAttribute('src')};
            }));
          for (const preview of previews) {
            assert.ok(preview.height <= Math.min(450, 900 * .7 + 2) && preview.width <= 706,
              `${route}: product preview stays bounded: ${JSON.stringify(preview)}`);
            assert.ok(Math.abs(preview.width / preview.height - preview.aspect) < .01 || preview.fit === 'contain',
              `${route}: the complete image fits without cropping or stretching: ${JSON.stringify(preview)}`);
            assert.equal(preview.fullSize, true, `${route}: screenshot keeps a native full-size link`);
          }
          if (previews.length) await page.evaluate(() => window.scrollTo({top: 0, behavior: 'instant'}));
          assert.ok((await page.title()).length > 10);
          // Plain reports retain lazy paragraph payloads; the interactive demo
          // mounts continuous prose. Content pages need a readable article.
          const dashboard = route === 'demo/report.html' || route.startsWith('examples/');
          const publication = publicationRoutes.has(route);
          if (!dashboard && !publication) {
            const themeControl = page.locator('#themeToggle');
            if (javaScriptEnabled) await expect(themeControl).toBeVisible();
            else await expect(themeControl).toBeHidden();
          }
          if (dashboard) {
            assert.ok(await page.locator('.chapter').count() > 0, `${route} renders chapters`);
            assert.ok(await page.locator('.chip').count() > 0, `${route} renders paragraph chips`);
          } else if (!publication) {
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
          if (route === 'guides/interpretation.html') {
            await page.locator('a[href="first-look.html#passage"]').click();
            await expect(page).toHaveURL(/first-look\.html#passage$/);
            await page.goto(origin + '/lixity/' + route);
          }
          if (route === 'guides/research-pdf.html') {
            await page.locator('.guide-toc a[href="#search"]').click();
            await expect(page).toHaveURL(/#search$/);
            await page.locator('h1').scrollIntoViewIfNeeded();
          }
          if (!route) {
            if (width === 1440) {
              const columns = await page.locator('.hero').evaluate(hero => {
                const copy = hero.querySelector('.hero-copy').getBoundingClientRect();
                const image = hero.querySelector('.frame').getBoundingClientRect();
                return {copyRight: copy.right, imageLeft: image.left};
              });
              assert.ok(columns.copyRight < columns.imageLeft, 'Desktop introduction and preview share one row');
            }
            await expect(page.locator('.hero-cta a.primary[href="demo/report.html"]')).toHaveAccessibleName('Open the example manuscript');
            await expect(page.locator('.hero-cta a[href="guides/first-look.html"]')).toHaveAccessibleName('Take the short tour');
            await expect(page.locator('.site-header a[href="#installation"]')).toBeVisible();
            const commandLink = page.locator('.site-header a[href="#command-line"]');
            await expect(commandLink).toBeVisible();
            await commandLink.focus();
            await page.keyboard.press('Enter');
            await expect(page).toHaveURL(/#command-line$/);
            const commands = page.locator('#command-line');
            await expect(commands).toBeInViewport();
            const commandColumns = await commands.locator('article').evaluateAll(nodes => nodes.map(node => {
              const box = node.getBoundingClientRect();
              return {left: box.left, right: box.right, top: box.top, bottom: box.bottom,
                codeTop: node.querySelector('pre').getBoundingClientRect().top};
            }));
            assert.equal(commandColumns.length, 2);
            if (width === 1440) assert.ok(commandColumns[0].right < commandColumns[1].left,
              'Desktop command examples share one row');
            if (width === 1440) assert.ok(Math.abs(commandColumns[0].codeTop - commandColumns[1].codeTop) < 1,
              'Desktop command examples align their code blocks despite different note lengths');
            if (width === 320) assert.ok(commandColumns[0].bottom < commandColumns[1].top,
              'Narrow command examples stack in reading order');
            await page.locator('h1').scrollIntoViewIfNeeded();
            await expect(page.locator('#installation')).toHaveCount(1);
            assert.equal(await page.locator('#installation').evaluate(node => node.tagName), 'SECTION',
              'The installation fragment opens its own author-facing section');
            await expect(page.locator('#installation a[href="guides/installation.html"]')).toBeVisible();
            for (const destination of ['demo/report.html', 'guides/installation.html', 'guides/first-look.html']) {
              await expect(page.locator(`#guides a[href="${destination}"]`)).toHaveCount(0);
            }
            await expect(page.locator('#guides > p a[href="guides/interpretation.html"]')).toBeVisible();
            await expect(page.locator('#features blockquote')).toHaveText(demoQuote);
            await expect(page.locator('#features a[href="demo/report.html#p-0"]')).toBeVisible();
            await expect(page.locator('#features a[href="demo/report.html#matrix"]')).toBeVisible();
            const reference = page.locator('#guides details');
            await expect(reference).toHaveCount(1);
            assert.equal(await reference.evaluate(node => node.open), false,
              'Technical references start behind one reversible disclosure');
            await expect(reference.locator('a[href="AGENTS.md"]')).toBeHidden();
            await reference.locator(':scope > summary').focus();
            await page.keyboard.press('Enter');
            await expect(reference.locator('a[href="AGENTS.md"]')).toBeVisible();
            await expect(reference.locator('#methods')).toHaveCount(1);
            await expect(reference.locator('#cli-api')).toHaveCount(1);
            await reference.locator(':scope > summary').press('Enter');
            await expect(reference.locator('a[href="AGENTS.md"]')).toBeHidden();
            await expect(reference.locator(':scope > summary')).toBeFocused();
            const image = page.locator('.hero .frame img');
            await expect(image).toHaveCount(1);
            await image.evaluate(element => element.decode());
            assert.equal(await image.evaluate(element => element.parentElement.getAttribute('href')),
              await image.getAttribute('src'), 'The product image opens at full size without JavaScript');
            assert.deepEqual(await image.evaluate(element => [element.naturalWidth, element.naturalHeight]),
              [Number(await image.getAttribute('width')), Number(await image.getAttribute('height'))]);
            assert.ok(await image.evaluate(element => {
              const box = element.getBoundingClientRect();
              return Math.abs(box.width / box.height - element.naturalWidth / element.naturalHeight) < .01;
            }), 'The homepage preserves the complete screenshot aspect ratio');
            await expect(page.locator('#impressum > summary')).toBeVisible();
            await page.locator('#impressum > summary').click();
            await expect(page.locator('#impressum address')).toBeVisible();
            await expect(page.locator('#impressum address')).toContainText('ROST Services GmbH');
            await page.locator('#impressum > summary').click();
            await page.locator('h1').scrollIntoViewIfNeeded();
          }
          await page.screenshot({path: path.join(artifacts, `${route ? path.basename(route, '.html') : 'home'}-${width}-${colorScheme}${javaScriptEnabled ? '' : '-js-off'}.png`), fullPage: route === '' || route === 'guides/first-look.html'});
          if (route === 'demo/report.html') await checkDemoWorkspace(page, javaScriptEnabled, width, colorScheme);
          if (publication) await checkPublicationExample(page, route, javaScriptEnabled, width, colorScheme);
        }
        await page.goto(origin + '/lixity/');
        await page.locator('.site-header a[href="#installation"]').focus();
        await page.keyboard.press('Enter');
        await expect(page).toHaveURL(origin + '/lixity/#installation');
        await expect(page.locator('#installation h2')).toBeInViewport();
        await page.locator('#installation a[href="guides/installation.html"]').click();
        assert.ok(page.url().endsWith('/guides/installation.html'), 'An eager visitor can reach installation through the header and its dedicated section');
        await page.goto(origin + '/lixity/');
        await page.locator('.hero-cta a[href="guides/first-look.html"]').click();
        assert.ok(page.url().endsWith('/guides/first-look.html'), 'The secondary CTA offers a tour before installation');
        await page.locator('.ctl[href="../demo/report.html"]').click();
        assert.ok(page.url().endsWith('/demo/report.html'));
        await page.locator('#example-context > summary').click();
        await page.locator('#example-context a[href="../guides/first-look.html"]').click();
        assert.ok(page.url().endsWith('/guides/first-look.html'), 'The report returns to the walkthrough');
        await page.locator('.site-breadcrumbs a[href="../#guides"]').click();
        await expect(page).toHaveURL(origin + '/lixity/#guides');
        await expect(page.locator('#guides h2')).toBeInViewport();
        await returnToTop(page, 'Guides parent');
        await page.locator('.brand[href="./"]').click();
        await expect(page).toHaveURL(origin + '/lixity/');
        await page.locator('.hero-cta a.primary[href="demo/report.html"]').click();
        assert.ok(page.url().endsWith('/demo/report.html'), 'The primary CTA opens the one demo directly');
        await page.locator('.site-header .brand, .site-return a[href="../"]').first().click();
        await expect(page).toHaveURL(origin + '/lixity/');
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
        await page.locator('.site-header .site-return a[href="../#guides"]').click();
        await expect(page).toHaveURL(origin + '/lixity/#guides');
        await page.locator('#guides a[href="guides/interpretation.html"]').click();
        assert.ok(page.url().endsWith('/guides/interpretation.html'));
        if (javaScriptEnabled) {
          await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
          await page.locator('.site-header .brand, .site-return a[href="../"]').first().click();
          await expect(page).toHaveURL(origin + '/lixity/');
          await page.locator('#themeToggle').click();
          await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
          await page.locator('#themeToggle').click();
          await expect(page.locator('html')).toHaveAttribute('data-theme', 'auto');
          await page.evaluate(() => localStorage.removeItem('lixity-theme'));
        }
        // The blog index lists the newest article; its page renders standalone.
        await page.goto(origin + '/lixity/blog/');
        const newestArticle = page.locator('article h2 a').first();
        const articleURL = new URL(await newestArticle.getAttribute('href'), page.url());
        await newestArticle.click();
        assert.equal(page.url(), articleURL.href);
        assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'),
          'https://mfahsold.github.io' + articleURL.pathname, 'Canonical URL matches the published page');
        await page.locator('.site-breadcrumbs a[href="index.html"]').click();
        await expect(page).toHaveURL(origin + '/lixity/blog/index.html');
        await expect(page.locator('article h2 a').first()).toHaveAttribute('href', path.basename(articleURL.pathname));
        await page.locator('.site-header .brand, .site-return a[href="../"]').first().click();
        await expect(page).toHaveURL(origin + '/lixity/');
      }
      if (colorScheme === 'light') await checkLegacyResearchURL(page, javaScriptEnabled);
      assert.deepEqual(errors, []);
      assert.ok(staticRequests.every(request => request.method === 'GET' && request.path.startsWith('/lixity/')),
        'Native downloads use only the disposable local static server');
      await context.close();
    }
    console.log(`Public docs: ${routes.length} selected HTML pages at desktop/390/320, representative surfaces in light/dark and JS on/off, static GET-only navigation, one six-chapter demo Analysis/Research state roundtrip with evidence/quote and PDF links, legacy research redirect, case-study rendering, keyboard/focus/console passed. Screenshots: ${artifacts}`);
  } finally {
    try { if (browser) await browser.close(); }
    finally {
      await new Promise(resolve => server.close(resolve));
      fs.rmSync(root, {recursive: true, force: true});
    }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
