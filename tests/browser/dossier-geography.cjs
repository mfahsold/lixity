// Editable geography round-trips through native dossier revisions; synthetic data only.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const {createInterface} = require('node:readline');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-dossier-geography-'));

(async () => {
  const server = spawn(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-u', '-c', `
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
base = Path(sys.argv[1]); project = base / 'synthetic-project'
api.init(project, title='Synthetic geography')
manuscript = project / 'manuscript.md'
manuscript.write_text('# Synthetic manuscript\\n\\nA traveller crosses the invented harbour.\\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.research_dir = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.language = 'en'; LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}'}), flush=True)
server.serve_forever()
`, artifacts], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, stdio: ['ignore', 'pipe', 'pipe']});
  const lines = createInterface({input: server.stdout});
  let stderr = '', browser;
  server.stderr.on('data', data => { stderr = (stderr + data).slice(-5000); });
  try {
    const fixture = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Synthetic server startup timed out: ' + stderr)), 15000);
      lines.once('line', line => { clearTimeout(timer); resolve(JSON.parse(line)); });
      server.once('error', reject);
      server.once('exit', code => reject(new Error(`Synthetic server exited ${code}: ${stderr}`)));
    });
    browser = await launchChromium();
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}, hasTouch: true});
    page.setDefaultTimeout(10000);
    const errors = [], external = [], writes = [], requests = [], tileRequests = [];
    let failTiles = false;
    await page.route('https://tile.openstreetmap.org/**', route => route.fulfill(failTiles ? {status: 503, body: 'Synthetic provider unavailable'} :
      {contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#edf2ef"/></svg>'}));
    async function showSketch(view) {
      await view.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      if (await view.locator('[data-geo-map]').getAttribute('aria-expanded') === 'true') {
        await view.locator('[data-geo-basemap]').uncheck();
        await view.locator('[data-geo-map]').click();
      }
      await expect(view.locator('.geography-sketch')).toBeVisible();
    }
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      requests.push(request.url());
      if (request.url().startsWith('https://tile.openstreetmap.org/')) {
        tileRequests.push({url: request.url(), referer: request.headers().referer});
      } else if (!request.url().startsWith(fixture.url) && !request.url().startsWith('blob:')) external.push(request.url());
      if (request.method() === 'POST') writes.push(request.postDataJSON());
    });
    await page.goto(fixture.url);
    assert.equal(new URL(page.url()).origin, fixture.url);
    assert.match(await page.title(), /Synthetic manuscript/);
    assert.equal(await page.evaluate(() => window.L && window.L.version), '1.9.4', 'The interactive renderer is pinned and bundled offline');
    await page.locator('#tab-view-research').click();
    await page.locator('[data-rtab=dossiers]').click();
    const collision = await page.evaluate(() => {
      const literal = '@@@LIXITYINLINE0END0@@@ @@@LIXITYINLINE1END0@@@ @@@LIXITYINLINE' + 'X'.repeat(32768);
      const code = '@@@LIXITYINLINE2END0@@@ code_*_ $&';
      const host = document.createElement('div');
      host.innerHTML = renderSafeMarkdown(literal + ' `' + code + '` [**token label**](https://example.org/token_suffix)');
      return {preserved: host.textContent === literal + ' ' + code + ' token label',
        code: host.querySelector('code').textContent, href: host.querySelector('a').getAttribute('href'),
        label: host.querySelector('a strong').textContent};
    });
    assert.equal(collision.preserved, true, 'Authored token-like text and long literal prefix runs remain exact data');
    assert.equal(collision.code, '@@@LIXITYINLINE2END0@@@ code_*_ $&');
    assert.equal(collision.href, 'https://example.org/token_suffix');
    assert.equal(collision.label, 'token label');
    // Inline formatting must not cross generated link attributes or leak into
    // the following geography, where it can reparent the SVG fallback.
    for (const width of [1440, 320]) {
      await page.setViewportSize({width, height: 1000});
      await page.evaluate(() => {
        const host = document.createElement('div'); host.id = 'markdown-geography-boundary';
        const body = 'Prefix_name [Link](https://example.org/target_suffix)\n\n' +
          '[Suffix link](https://example.org/prefix_target) suffix_name.\n\n' +
          '*Intended emphasis* and [**bold link**](https://example.org/a_b).\n\n' +
          '`code_*_ $&` and $x_y$ and [internal_label](lixity:dossier/id_suffix).\n\n' +
          '![Image_name](lixity:image/urn:uuid:11111111-1111-4111-8111-111111111111/urn:uuid:22222222-2222-4222-8222-222222222222)';
        host.innerHTML = researchDossierBodyHtml(body, {project_id: 'synthetic', images: []}) +
          LixityDossierGeography.html({type: 'FeatureCollection', features: [
            {type: 'Feature', geometry: {type: 'Point', coordinates: [10, 46]}, properties: {label: 'Synthetic place'}},
          ]});
        document.body.appendChild(host);
      });
      const boundary = page.locator('#markdown-geography-boundary');
      const mapBoundary = boundary.locator('.dossier-geography');
      await mapBoundary.scrollIntoViewIfNeeded();
      await expect(mapBoundary.locator('.geography-map')).toBeVisible();
      await expect(mapBoundary.locator('[data-geo-basemap]')).toBeChecked();
      await expect(mapBoundary.locator('.geography-sketch')).toBeHidden();
      assert.equal(await mapBoundary.locator('em').count(), 0, 'Prose emphasis must not wrap geographic controls');
      assert.equal(await mapBoundary.locator('h4').evaluate(node => getComputedStyle(node).fontStyle), 'normal');
      await expect(boundary.getByRole('link', {name: 'Link', exact: true})).toHaveAttribute('href', 'https://example.org/target_suffix');
      await expect(boundary.getByRole('link', {name: 'Suffix link', exact: true})).toHaveAttribute('href', 'https://example.org/prefix_target');
      await expect(boundary.locator('a strong')).toHaveText('bold link');
      await expect(boundary.locator('a:has(strong)')).toHaveAttribute('href', 'https://example.org/a_b');
      await expect(boundary.locator('p > em')).toHaveText('Intended emphasis');
      await expect(boundary.locator('code:not(.lixity-ref)')).toHaveText('code_*_ $&');
      await expect(boundary.locator('.math-inline')).toHaveText('x_y');
      await expect(boundary.locator('.lixity-ref')).toHaveText('internal_label (dossier/id_suffix)');
      await expect(boundary.locator('.dossier-image-unavailable strong')).toHaveText('Image_name');
      assert.equal(await boundary.locator('.research-dossier-body-rendered').evaluate(node =>
        node.querySelectorAll('p a em').length), 0, 'URL data must never become link-label emphasis');
      await boundary.screenshot({path: path.join(artifacts, `markdown-geography-boundary-${width}.png`)});
      await boundary.evaluate(node => node.remove());
    }
    await page.setViewportSize({width: 1440, height: 1000});
    await page.evaluate(() => {
      const host = document.createElement('div'); host.id = 'geo-default-lifecycle'; host.hidden = true;
      host.style.marginTop = '200vh';
      host.innerHTML = LixityDossierGeography.html({type: 'FeatureCollection', features: [
        {type: 'Feature', geometry: {type: 'Point', coordinates: [11, 47]}, properties: {label: 'Synthetic lifecycle place'}},
      ]});
      document.body.appendChild(host);
    });
    const lifecycle = page.locator('#geo-default-lifecycle .dossier-geography');
    const lifecycleMap = lifecycle.locator('.geography-map');
    const beforeHidden = tileRequests.length;
    await page.locator('#geo-default-lifecycle').evaluate(node => { node.hidden = false; });
    await lifecycle.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await expect(lifecycle.locator('[data-geo-map]')).toHaveAttribute('aria-expanded', 'false');
    assert.equal(tileRequests.length, beforeHidden, 'An offscreen saved reader never requests tiles');
    await lifecycle.scrollIntoViewIfNeeded();
    await expect(lifecycleMap).toBeVisible();
    await lifecycleMap.scrollIntoViewIfNeeded();
    await expect(lifecycle.locator('[data-geo-basemap]')).toBeChecked();
    await expect(lifecycleMap.locator('.leaflet-tile-loaded')).not.toHaveCount(0);
    await page.evaluate(() => scrollTo(0, 0));
    await expect(lifecycleMap.locator('.leaflet-tile')).toHaveCount(0);
    const beforeOffscreenResize = tileRequests.length;
    await page.setViewportSize({width: 1420, height: 1000});
    assert.equal(tileRequests.length, beforeOffscreenResize, 'Offscreen map resizing cannot request tiles');
    await lifecycleMap.scrollIntoViewIfNeeded();
    await expect(lifecycleMap.locator('.leaflet-tile-loaded')).not.toHaveCount(0);
    await lifecycle.locator('[data-geo-basemap]').uncheck();
    const beforeOff = tileRequests.length;
    await lifecycle.evaluate(node => { node.classList.add('synthetic-mutation'); });
    await page.evaluate(() => scrollTo(0, 0));
    await lifecycle.scrollIntoViewIfNeeded();
    await expect(lifecycle.locator('[data-geo-basemap]')).not.toBeChecked();
    await expect(lifecycleMap.locator('.leaflet-tile')).toHaveCount(0);
    assert.equal(tileRequests.length, beforeOff, 'Explicit tiles off survives mutations and viewport changes');
    await lifecycle.locator('[data-geo-basemap]').check();
    await lifecycleMap.scrollIntoViewIfNeeded();
    await expect(lifecycleMap.locator('.leaflet-tile-loaded')).not.toHaveCount(0);
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', {configurable: true, value: true});
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await expect(lifecycleMap.locator('.leaflet-tile')).toHaveCount(0);
    const beforeBackground = tileRequests.length;
    await lifecycleMap.locator('.leaflet-control-zoom-in').click();
    assert.equal(tileRequests.length, beforeBackground, 'A background document cannot request tiles');
    await page.evaluate(() => { delete document.hidden; document.dispatchEvent(new Event('visibilitychange')); });
    await expect(lifecycleMap.locator('.leaflet-tile-loaded')).not.toHaveCount(0);
    await page.evaluate(() => window.dispatchEvent(new Event('pagehide')));
    await expect(lifecycleMap.locator('.leaflet-map-pane')).toHaveCount(0);
    await lifecycle.evaluate(node => { node.classList.add('after-pagehide'); });
    await expect(lifecycleMap).toBeHidden();
    await page.evaluate(() => window.dispatchEvent(new Event('pageshow')));
    await expect(lifecycleMap).toBeVisible();
    await showSketch(lifecycle);
    await lifecycle.evaluate(node => { node.classList.add('after-explicit-sketch'); });
    await expect(lifecycleMap).toBeHidden();
    const beforeStale = tileRequests.length;
    const lifecycleToken = await lifecycle.evaluate(root => {
      const panel = document.getElementById('research-manager'), token = panel.dataset.researchToken;
      const savedHTML = root.outerHTML;
      panel.dataset.researchToken = 'synthetic-delayed-geography-context';
      const host = document.createElement('div'); host.id = 'geo-stale-render'; host.innerHTML = savedHTML;
      document.body.appendChild(host);
      return token;
    });
    const stale = page.locator('#geo-stale-render .dossier-geography');
    await stale.scrollIntoViewIfNeeded();
    await stale.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await expect(stale.locator('[data-geo-map]')).toHaveAttribute('aria-expanded', 'false');
    await expect(stale.locator('.leaflet-map-pane')).toHaveCount(0);
    assert.equal(tileRequests.length, beforeStale, 'Delayed HTML keeps its original project context and never requests tiles');
    await page.evaluate(token => {
      document.getElementById('geo-stale-render').remove();
      document.getElementById('research-manager').dataset.researchToken = token;
    }, lifecycleToken);
    const beforeUnplaced = tileRequests.length;
    await lifecycle.evaluate(root => {
      root.parentElement.innerHTML = LixityDossierGeography.html({type: 'FeatureCollection', features: [
        {type: 'Feature', geometry: null, properties: {label: 'Synthetic unplaced record'}},
      ]});
    });
    await lifecycle.scrollIntoViewIfNeeded();
    await expect(lifecycleMap).toHaveCount(0);
    assert.equal(tileRequests.length, beforeUnplaced, 'Unknown geometry never invents a map or requests tiles');
    await page.locator('#geo-default-lifecycle').evaluate(node => node.remove());
    // Number labels are controls, not transparent decorations over another
    // feature. Exercise actual pointer hits with overlapping points/line/area.
    await page.evaluate(() => {
      const host = document.createElement('div'); host.id = 'geo-pointer-regression';
      host.innerHTML = LixityDossierGeography.html({type: 'FeatureCollection', features: [
        {type: 'Feature', geometry: {type: 'Point', coordinates: [11, 46]}, properties: {label: 'Synthetic point'}},
        {type: 'Feature', geometry: {type: 'LineString', coordinates: [[11, 46], [11.002, 46.002], [11.004, 46.002]]}, properties: {label: 'Synthetic route'}},
        {type: 'Feature', geometry: {type: 'Polygon', coordinates: [[[10.999, 45.999], [11.005, 45.999], [11.005, 46.003], [10.999, 46.003], [10.999, 45.999]]]}, properties: {label: 'Synthetic area'}},
      ]});
      document.getElementById('research-manager').appendChild(host);
    });
    const pointerView = page.locator('#geo-pointer-regression .dossier-geography');
    const pointerMap = pointerView.locator('.geography-map');
    const beforePointerWrites = writes.length;
    for (const width of [1440, 320]) {
      await page.setViewportSize({width, height: 1000});
      await pointerView.scrollIntoViewIfNeeded();
      await expect(pointerMap.locator('svg .leaflet-interactive').first()).toBeVisible();
      await pointerView.locator('[data-geo-basemap]').uncheck();
      await pointerView.locator('[data-geo-fit]').click();
      const selectionZoom = await pointerMap.evaluate(node => node._geographyMap.getZoom());
      for (const index of [0, 1, 2]) {
        await pointerMap.scrollIntoViewIfNeeded();
        const number = pointerMap.locator('.geography-map-number').filter({hasText: new RegExp('^' + (index + 1) + '$')});
        const box = await number.boundingBox();
        const hit = await page.evaluate(box => {
          const node = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
          return node && {tag: node.tagName, class: node.getAttribute('class'), feature: node.dataset.geoSelect};
        }, box);
        if (width === 320) await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);
        else await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
        await expect(pointerView.locator('li').nth(index), JSON.stringify({width, index, box, hit})).toHaveClass(/is-selected/);
        assert.equal(await pointerMap.evaluate(node => node._geographyMap.getZoom()), selectionZoom,
          'Rapid number taps select features without becoming a map double-tap zoom gesture');
      }
      // The area's fill must not intercept the point or route beneath a label.
      for (const index of [0, 1]) {
        await pointerMap.scrollIntoViewIfNeeded();
        const hit = await pointerMap.locator('svg [data-geo-select="' + index + '"]').evaluate(node => {
          const point = node.getPointAtLength(node.getTotalLength() * .25);
          const screen = new DOMPoint(point.x, point.y).matrixTransform(node.getScreenCTM());
          return {x: screen.x, y: screen.y};
        });
        await page.mouse.click(hit.x, hit.y);
        await expect(pointerView.locator('li').nth(index)).toHaveClass(/is-selected/);
      }
      const firstNumber = pointerMap.locator('.geography-map-number').getByRole('button', {name: '1. Synthetic point', exact: true});
      await firstNumber.focus(); await page.keyboard.press('Enter');
      await expect(pointerView.locator('li').nth(0)).toHaveClass(/is-selected/);
      await pointerView.locator('[data-geo-clear]').click();
      await firstNumber.focus(); await page.keyboard.press('Space');
      await expect(firstNumber).toHaveAttribute('aria-pressed', 'true');
      await pointerMap.screenshot({path: path.join(artifacts, `number-controls-${width}.png`)});
    }
    assert.equal(writes.length, beforePointerWrites, 'Map pointer and keyboard selection never writes research records');
    await page.locator('#geo-pointer-regression').evaluate(node => node.remove());
    await page.setViewportSize({width: 1440, height: 1000});
    if (!await page.locator('#r-dos-composer').evaluate(node => node.open)) await page.locator('#r-dos-composer > summary').click();
    await page.locator('#r-dos-title').fill('Synthetic harbour journey');
    await page.locator('#r-dos-body').fill('# Context\n\nSynthetic route notes.');
    const create = page.locator('#r-dos-geography-editor');
    await create.locator('summary').first().click();
    await create.locator('[data-geo-add]').click();
    let feature = create.locator('[data-geo-feature]').first();
    await feature.locator('[data-geo-field=label]').fill('Harbour <img src=x onerror=window.geoInjected=true>');
    await feature.locator('[data-geo-field=coordinates]').fill('999, 52.5');
    await page.locator('#r-dos-create-btn').click();
    await expect(page.locator('#r-dos-create-btn-status')).not.toBeEmpty();
    assert.equal(writes.filter(write => write.title === 'Synthetic harbour journey').length, 0, 'Invalid coordinates are rejected before a write');
    await feature.locator('[data-geo-field=coordinates]').fill('13.4, 52.5');
    assert.ok(!(await create.locator('.geography-sketch').innerHTML()).match(/NaN|Infinity/), 'Single-point sketch has finite degenerate bounds');
    await create.locator('[data-geo-add]').click();
    feature = create.locator('[data-geo-feature]').nth(1);
    await feature.locator('[data-geo-field=label]').fill('Mira’s journey');
    await feature.locator('[data-geo-field=type]').selectOption('LineString');
    await feature.locator('[data-geo-field=coordinates]').fill('13.4, 52.5\n13.6, 52.7');
    await feature.locator('summary').click();
    await feature.locator('[data-geo-field=actors]').fill('Mira\nEmil');
    await feature.locator('[data-geo-field=transport]').selectOption('rail');
    await feature.locator('[data-geo-field=time_period]').fill('1902');
    await feature.locator('[data-geo-field=waypoint_labels]').fill('Harbour\nStation');
    let releaseCreate, startedCreate;
    const createGate = new Promise(resolve => { releaseCreate = resolve; });
    const createReady = new Promise(resolve => { startedCreate = resolve; });
    await page.route('**/api/research-dossier', async route => {
      const response = await route.fetch(); startedCreate(); await createGate; await route.fulfill({response});
    });
    await page.locator('#r-dos-create-btn').click();
    await createReady;
    await expect(page.locator('#r-dos-create-btn')).toBeDisabled();
    await page.evaluate(() => {
      window.geoOriginalFileText = File.prototype.text;
      File.prototype.text = function() {
        return window.geoOriginalFileText.call(this).then(text => new Promise(resolve => { window.geoImportRelease = () => resolve(text); }));
      };
    });
    const newerImport = {type: 'FeatureCollection', features: [{type: 'Feature', geometry: null, properties: {label: 'Newer imported geography'}}]};
    await create.locator('[data-geo-import]').setInputFiles({name: 'newer.geojson', mimeType: 'application/geo+json', buffer: Buffer.from(JSON.stringify(newerImport))});
    await page.waitForFunction(() => Boolean(window.geoImportRelease));
    releaseCreate();
    await expect(page.locator('#r-dos-create-btn')).toBeEnabled();
    await page.unroute('**/api/research-dossier');
    await expect(page.locator('#r-dos-title')).toHaveValue('Synthetic harbour journey');
    await expect(create.locator('[data-geo-feature]')).toHaveCount(2, 'A pending import prevents an older save from clearing the draft');
    const writesBeforePendingSave = writes.filter(write => write.title === 'Synthetic harbour journey').length;
    await page.locator('#r-dos-create-btn').click();
    assert.equal(writes.filter(write => write.title === 'Synthetic harbour journey').length, writesBeforePendingSave, 'Save waits for the selected file to finish importing');
    await page.evaluate(() => { window.geoImportRelease(); File.prototype.text = window.geoOriginalFileText; delete window.geoImportRelease; });
    await expect(create.locator('[data-geo-field=label]')).toHaveValue('Newer imported geography');
    let listed = await (await page.request.get(fixture.url + '/api/research/dossiers')).json();
    const id = listed.dossiers.find(item => item.title === 'Synthetic harbour journey').id;
    const recordURL = fixture.url + '/api/research/record?kind=dossier&id=' + id;
    const detailURL = fixture.url + '/api/research/dossiers?id=' + id;
    let saved = await (await page.request.get(recordURL)).json();
    assert.deepEqual(saved.record.geography.features[0].geometry, {type: 'Point', coordinates: [13.4, 52.5]});
    assert.deepEqual(saved.record.geography.features[1].properties.actors, ['Mira', 'Emil']);
    assert.equal(saved.record.geography.features[1].properties.transport, 'rail');
    assert.deepEqual(saved.record.geography.features[1].properties.waypoint_labels, ['Harbour', 'Station']);
    assert.equal(saved.record.geography.features[0].properties.label, 'Harbour <img src=x onerror=window.geoInjected=true>');
    await create.locator('[data-geo-remove]').first().click();
    await expect(create.locator('[data-geo-feature]')).toHaveCount(0);
    if (!await page.locator('#r-dos-composer').evaluate(node => node.open)) await page.locator('#r-dos-composer > summary').click();
    await page.locator('#r-dos-title').fill('');
    await page.locator('#r-dos-body').fill('');
    async function openDetails() {
      const summary = page.locator(`[data-research-detail=dossier][data-record-id="${id}"]`);
      if (await summary.evaluate(node => node.parentElement.open)) await summary.click();
      await summary.click();
      await expect(page.locator('.research-details-body .dossier-geography')).toBeVisible();
    }
    await openDetails();
    await expect(page.locator('.research-details-body .dossier-geography')).toContainText('Mira’s journey');
    await expect(page.locator('.research-details-body .dossier-geography')).toContainText('1902');
    assert.equal(await page.locator('.geography-feature-list img').count(), 0, 'Feature metadata is inert text');
    assert.equal(await page.evaluate(() => Boolean(window.geoInjected)), false);
    const geography = page.locator('.research-details-body .dossier-geography');
    await geography.scrollIntoViewIfNeeded();
    await expect(geography.locator('[data-geo-map]')).toHaveAttribute('aria-expanded', 'true');
    await expect(geography.locator('[data-geo-basemap]')).toBeChecked();
    await expect(geography.locator('.leaflet-control-attribution')).toContainText('OpenStreetMap');
    await showSketch(geography);
    await expect(geography.locator('.geography-overview')).toContainText('2 located');
    await expect(geography.locator('.geography-legend')).toContainText(/point/i);
    await expect(geography.locator('.geography-method')).toContainText('spherical');
    await expect(geography.locator('li').nth(1).locator('.geography-route-facts')).toContainText('km');
    await expect(geography.locator('[data-geo-frame]')).toBeDisabled();
    assert.equal(await geography.locator('svg [data-geo-select]').count(), 2,
      'Each saved point and route is a keyboard-reachable feature control');
    await expect(geography.locator('svg')).toHaveAttribute('role', 'group');
    await expect(geography.locator('svg [data-geo-select="0"]')).toHaveAttribute('role', 'button');
    await expect(geography.locator('svg [data-geo-select="0"]')).toHaveAttribute('aria-label', /Harbour <img/);
    const listButton = index => geography.locator(`.geography-feature-list button[data-geo-select="${index}"]`);
    await geography.locator('.geography-sketch').scrollIntoViewIfNeeded();
    await geography.locator('svg [data-geo-select="0"] circle').click();
    await expect(listButton(0)).not.toBeFocused();
    await expect(geography.locator('.geography-selected')).toBeInViewport();
    await expect(geography.locator('.geography-sketch')).toBeInViewport();
    await expect(listButton(0)).toHaveAttribute('aria-pressed', 'true');
    await expect(geography.locator('li').nth(0).locator('details')).toHaveAttribute('open', '');
    await expect(geography.locator('li').nth(0).locator('pre')).toHaveText('13.4, 52.5');
    await expect(geography.locator('.geography-selected')).toContainText('Longitude');
    await expect(geography.locator('.geography-selected')).toContainText('Latitude');
    await geography.locator('[data-geo-details]').click();
    await expect(listButton(0)).toBeFocused();
    await geography.locator('svg [data-geo-select="1"]').focus();
    assert.notEqual(await geography.locator('svg [data-geo-select="1"]').evaluate(node => getComputedStyle(node).outlineStyle), 'none',
      'Keyboard focus on a route remains visible');
    await page.keyboard.press('Space');
    await expect(listButton(1)).toBeFocused();
    await expect(geography.locator('.geography-selected')).toContainText('Mira’s journey');
    await expect(geography.locator('.geography-selected')).toContainText('1902');
    await expect(geography.locator('.geography-selected')).toContainText('Harbour → Station');
    await expect(geography.locator('[data-geo-frame]')).toBeEnabled();
    await geography.locator('[data-geo-frame]').click();
    await geography.locator('.geography-method > summary').click();
    await expect(geography.locator('.geography-method')).toContainText('6,371.0088');
    for (const width of [1440, 320]) {
      await page.setViewportSize({width, height: 1000});
      await geography.screenshot({path: path.join(artifacts, `route-information-${width}.png`)});
    }
    await page.setViewportSize({width: 1440, height: 1000});
    await geography.locator('[data-geo-map]').click();
    await expect(geography.locator('svg [data-geo-select="1"]')).toHaveClass(/is-selected/);
    await expect(listButton(0)).toHaveAttribute('aria-pressed', 'false');
    await listButton(0).focus();
    await page.keyboard.press('Enter');
    await expect(geography.locator('svg [data-geo-select="0"]')).toHaveClass(/is-selected/);
    await expect(geography.locator('svg [data-geo-select="1"]')).not.toHaveClass(/is-selected/);
    await page.evaluate(value => {
      const copy = document.createElement('div'); copy.id = 'geo-navigation-copy';
      copy.innerHTML = window.LixityDossierGeography.html(value); document.getElementById('research-manager').appendChild(copy);
    }, saved.record.geography);
    const secondGeography = page.locator('#geo-navigation-copy .dossier-geography');
    await secondGeography.scrollIntoViewIfNeeded();
    await showSketch(secondGeography);
    const requestCount = requests.length, writeCount = writes.length;
    await secondGeography.locator('svg [data-geo-select="1"]').focus();
    await page.keyboard.press('Enter');
    await expect(secondGeography.locator('li').nth(1)).toHaveClass(/is-selected/);
    await expect(geography.locator('li').nth(0)).toHaveClass(/is-selected/);
    await expect(geography.locator('li').nth(1)).not.toHaveClass(/is-selected/);
    await page.evaluate(value => {
      document.getElementById('geo-navigation-copy').innerHTML = window.LixityDossierGeography.html(value);
    }, saved.record.geography);
    await showSketch(secondGeography);
    await expect(secondGeography.locator('[aria-pressed="true"]')).toHaveCount(0);
    await secondGeography.locator('.geography-feature-list button[data-geo-select="0"]').click();
    await expect(secondGeography.locator('svg [data-geo-select="0"]')).toHaveAttribute('aria-pressed', 'true');
    await secondGeography.locator('[data-geo-map]').click();
    await geography.locator('[data-geo-map]').click();
    await expect(page.locator('.geography-map .leaflet-map-pane')).toHaveCount(2);
    await expect(geography.locator('.geography-map-number')).toHaveCount(2);
    await expect(geography.locator('.leaflet-control-scale')).toBeVisible();
    await geography.locator('[data-geo-frame]').click();
    assert.ok(await geography.locator('.geography-map').evaluate(node => node._geographyMap.getBounds().contains(window.L.latLng(52.5, 13.4))),
      'The selected point can be framed independently of the other rendered map');
    await secondGeography.locator('[data-geo-fit]').click();
    await expect(geography.locator('.geography-feature-list button[data-geo-select="0"]')).toHaveAttribute('aria-pressed', 'true');
    await geography.locator('[data-geo-map]').click();
    assert.equal(requests.length, requestCount, 'Feature navigation and rerendering never request data');
    assert.equal(writes.length, writeCount, 'Feature navigation never writes');
    assert.equal((await (await page.request.get(recordURL)).json()).snapshot, saved.snapshot, 'Feature selection is not stored');
    await page.locator('#geo-navigation-copy').evaluate(node => node.remove());
    await page.evaluate(() => {
      const host = document.createElement('div'); host.id = 'geo-polar-copy';
      host.innerHTML = window.LixityDossierGeography.html({type: 'FeatureCollection', features: [{type: 'Feature',
        geometry: {type: 'Point', coordinates: [25, 90]}, properties: {label: 'Synthetic pole'}}]});
      document.getElementById('research-manager').appendChild(host);
    });
    const polar = page.locator('#geo-polar-copy .dossier-geography');
    await polar.scrollIntoViewIfNeeded();
    await expect(polar.locator('.geography-map')).toBeVisible();
    await expect(polar.locator('.geography-projection-hint')).toContainText('85.05');
    await polar.locator('.geography-feature-list button[data-geo-select="0"]').click();
    await expect(polar.locator('pre')).toHaveText('25, 90');
    await polar.locator('[data-geo-clear]').click();
    await expect(polar.locator('[aria-pressed="true"]')).toHaveCount(0);
    await expect(polar.locator('[data-geo-frame]')).toBeDisabled();
    await page.locator('#geo-polar-copy').evaluate(node => node.remove());
    const mapToggle = geography.locator('[data-geo-map]'), map = geography.locator('.geography-map');
    await mapToggle.click();
    await expect(map).toBeVisible();
    await expect(map.locator('svg .leaflet-interactive')).toHaveCount(2);
    await expect(map.locator('.leaflet-overlay-pane > svg')).toHaveAttribute('role', 'group');
    await expect(geography.locator('[data-geo-basemap]')).not.toBeChecked();
    const offlineTiles = tileRequests.length;
    const initialMap = await map.evaluate(node => ({zoom: node._geographyMap.getZoom(), center: node._geographyMap.getCenter()}));
    await map.locator('.leaflet-control-zoom-in').click();
    await expect.poll(() => map.evaluate(node => node._geographyMap.getZoom())).toBeGreaterThan(initialMap.zoom);
    const box = await map.boundingBox();
    await page.mouse.move(box.x + box.width * .7, box.y + box.height * .7);
    await page.mouse.down(); await page.mouse.move(box.x + box.width * .7 + 70, box.y + box.height * .7 + 30, {steps: 5}); await page.mouse.up();
    await expect.poll(() => map.evaluate(node => node._geographyMap.getCenter().lng)).not.toBe(initialMap.center.lng);
    await geography.locator('[data-geo-fit]').click();
    assert.ok(await map.evaluate(node => node._geographyMap.getBounds().contains(window.L.latLng(52.5, 13.4))), 'Fit restores the authored feature bounds');
    await map.locator('svg [data-geo-select="0"]').click();
    await expect(listButton(0)).not.toBeFocused();
    await map.locator('svg [data-geo-select="1"]').click();
    await expect(listButton(1)).not.toBeFocused();
    await expect(map).toBeInViewport();
    await expect(geography.locator('.geography-selected')).toBeInViewport();
    await expect(map.locator('svg [data-geo-select="1"]')).toHaveAttribute('aria-pressed', 'true');
    await map.locator('svg [data-geo-select="0"]').focus();
    await page.keyboard.press('Enter');
    await expect(listButton(0)).toBeFocused();
    await listButton(0).click();
    await expect(map.locator('svg [data-geo-select="0"]')).toHaveAttribute('aria-pressed', 'true');
    assert.equal(tileRequests.length, offlineTiles, 'Explicit offline vector navigation never restarts tiles');
    await expect(geography.locator('.geography-basemap-hint')).toContainText('OpenStreetMap');
    await geography.locator('[data-geo-basemap]').check();
    await map.scrollIntoViewIfNeeded();
    await expect(map.locator('.leaflet-tile-loaded')).not.toHaveCount(0);
    await expect(map.locator('.leaflet-control-attribution')).toContainText('OpenStreetMap');
    assert.ok(tileRequests.every(request => new URL(request.url).hostname === 'tile.openstreetmap.org' &&
      /^\/\d+\/\d+\/\d+\.png$/.test(new URL(request.url).pathname)), 'Only standard current-viewport tile URLs are permitted');
    assert.ok(tileRequests.every(request => request.referer === fixture.url + '/'), 'Tile referrers contain only the local origin');
    await page.locator('[data-rtab=sources]').click();
    const hiddenTiles = tileRequests.length;
    await page.setViewportSize({width: 1380, height: 980});
    assert.equal(tileRequests.length, hiddenTiles, 'Hidden readers issue no tile requests when resized');
    await page.locator('[data-rtab=dossiers]').click();
    await geography.scrollIntoViewIfNeeded();
    await expect(map).toBeVisible();
    await map.scrollIntoViewIfNeeded();
    await expect(mapToggle).toHaveAttribute('aria-expanded', 'true');
    await expect(geography.locator('[data-geo-basemap]')).toBeChecked();
    await expect(map).toBeVisible();
    await expect(map.locator('.leaflet-tile-loaded')).not.toHaveCount(0);
    const originalToken = await page.evaluate(() => {
      const host = document.getElementById('research-manager'), token = host.dataset.researchToken;
      host.dataset.researchToken = 'synthetic-context-change'; return token;
    });
    await expect(mapToggle).toHaveAttribute('aria-expanded', 'false');
    await expect(geography.locator('[data-geo-basemap]')).not.toBeChecked();
    await page.evaluate(token => { document.getElementById('research-manager').dataset.researchToken = token; }, originalToken);
    await map.scrollIntoViewIfNeeded();
    await expect(map).toBeVisible();
    failTiles = true;
    // Use a new zoom level so previously decoded successful tiles cannot mask
    // a real provider failure. Fast failure may disable tiles before click ends.
    await map.locator('.leaflet-control-zoom-in').click();
    await map.locator('.leaflet-control-zoom-in').click();
    await map.locator('.leaflet-control-zoom-in').click();
    await expect.poll(async () => ({message: await geography.locator('.geography-map-status').textContent(),
      errors, tileCount: tileRequests.length})).toMatchObject({message: expect.stringContaining('could not be loaded')});
    await expect(geography.locator('[data-geo-basemap]')).not.toBeChecked();
    await expect(map.locator('.leaflet-tile')).toHaveCount(0);
    await expect(map.locator('svg .leaflet-interactive')).toHaveCount(2);
    const failedTiles = tileRequests.length;
    await map.locator('.leaflet-control-zoom-in').click();
    await expect(geography.locator('[data-geo-basemap]')).not.toBeChecked();
    assert.equal(tileRequests.length, failedTiles, 'Provider failure stays offline until an explicit retry');
    failTiles = false;
    await geography.locator('[data-geo-basemap]').check();
    await expect.poll(() => tileRequests.length).toBeGreaterThan(failedTiles);
    await expect(geography.locator('.geography-map-status')).toBeEmpty();
    await geography.locator('[data-geo-basemap]').uncheck();
    await mapToggle.click();
    assert.equal((await (await page.request.get(recordURL)).json()).snapshot, saved.snapshot, 'Provider failure preserves the archive');
    await page.locator(`[data-research-revise=dossier][data-record-id="${id}"]:not([data-dossier-section])`).click();
    const editor = page.locator('#research-revision-field-geography-editor');
    await editor.locator('summary').first().click();
    await expect(editor.locator('[data-geo-feature]')).toHaveCount(2);
    const importFile = editor.locator('[data-geo-import]');
    const unknownFeature = {type: 'Feature', geometry: null, properties: {label: 'Unknown'}};
    const invalidProperties = [{actors: null}, {waypoint_labels: null}, {description: ' '}, {time_period: ''}, {feature_type: '\n'}];
    const invalidImports = ['{bad', 'null', JSON.stringify({type: 'FeatureCollection', features: [], bbox: [0, 0, 1, 1]})].concat(
      invalidProperties.map(properties => JSON.stringify({type: 'FeatureCollection', features: [{...unknownFeature, properties: {...unknownFeature.properties, ...properties}}]})));
    for (const invalid of invalidImports) {
      await importFile.setInputFiles({name: 'invalid.geojson', mimeType: 'application/json', buffer: Buffer.from(invalid)});
      await expect(editor.locator('[data-geo-status]')).not.toBeEmpty();
      await expect(editor.locator('[data-geo-feature]')).toHaveCount(2);
    }
    const unicodeProperties = {label: '😀'.repeat(300) + '\r\nNorth', description: '😀'.repeat(2001) + '\r\nNote', time_period: '😀'.repeat(300) + '\nPeriod',
      feature_type: '😀'.repeat(300) + '\rCategory', actors: ['😀'.repeat(100), 'Name\r\nwith newline', ' '], waypoint_labels: ['North\r\nGate', '😀'.repeat(300)]};
    const unicode = {type: 'FeatureCollection', features: [{type: 'Feature', geometry: {type: 'LineString', coordinates: [[1, 2], [3, 4]]}, properties: unicodeProperties}]};
    await importFile.setInputFiles({name: 'unicode.geojson', mimeType: 'application/geo+json', buffer: Buffer.from(JSON.stringify(unicode))});
    await expect(editor.locator('[data-geo-feature]')).toHaveCount(1);
    await expect(editor.locator('[data-geo-field=label]')).toHaveValue('😀'.repeat(300) + 'North');
    assert.deepEqual(await page.evaluate(() => document.getElementById('research-revision-field-geography')._geographyEditor.read()), unicode,
      'Accepted Unicode and embedded-newline list values survive an unchanged editor roundtrip');
    await editor.locator('[data-geo-field=label]').fill('Edited Unicode route');
    const editedUnicode = await page.evaluate(() => document.getElementById('research-revision-field-geography')._geographyEditor.read());
    assert.deepEqual(editedUnicode.features[0].properties.actors, unicodeProperties.actors, 'Editing another field preserves embedded newlines in actor names');
    assert.deepEqual(editedUnicode.features[0].properties.waypoint_labels, unicodeProperties.waypoint_labels, 'Editing another field preserves embedded newlines in waypoint names');
    for (const key of ['description', 'time_period', 'feature_type']) assert.equal(editedUnicode.features[0].properties[key], unicodeProperties[key], `Editing another field preserves ${key} line endings`);
    assert.ok((await page.evaluate(value => window.LixityDossierGeography.html(value), unicode)).includes('dossier-geography'), 'Saved Unicode data remains viewable');
    const overlong = structuredClone(unicode);
    overlong.features[0].properties.actors[0] += 'x';
    await importFile.setInputFiles({name: 'overlong.geojson', mimeType: 'application/geo+json', buffer: Buffer.from(JSON.stringify(overlong))});
    await expect(editor.locator('[data-geo-status]')).not.toBeEmpty();
    await expect(editor.locator('[data-geo-field=label]')).toHaveValue('Edited Unicode route');
    const imported = {type: 'FeatureCollection', features: [
      {type: 'Feature', geometry: {type: 'Polygon', coordinates: [[[179, 1], [-179, 1], [-179, 3], [179, 1]], [[179.6, 1.2], [179.8, 1.2], [179.7, 1.4], [179.6, 1.2]]]}, properties: {label: 'Dateline area', description: 'Synthetic polygon with a hole.', actors: ['Mira, narrator', 'Emil']}},
      {type: 'Feature', geometry: null, properties: {label: 'Unknown destination'}}
    ]};
    await page.evaluate(() => {
      window.geoOriginalFileText = File.prototype.text;
      File.prototype.text = function() {
        return window.geoOriginalFileText.call(this).then(text => new Promise(resolve => { window.geoImportRelease = () => resolve(text); }));
      };
    });
    const importPayload = {name: 'synthetic.geojson', mimeType: 'application/geo+json', buffer: Buffer.from(JSON.stringify(imported))};
    await page.locator('input[name=research_revision_change_kind][value=correction]').check();
    await page.locator('#research-revision-reason').fill('Wait for the selected import.');
    await importFile.setInputFiles(importPayload);
    await page.waitForFunction(() => Boolean(window.geoImportRelease));
    const writesBeforeRevisionImport = writes.filter(write => write.kind === 'dossier').length;
    await page.locator('#research-revision-save').click();
    await expect(page.locator('#research-revision-status')).toContainText('finish importing');
    assert.equal(writes.filter(write => write.kind === 'dossier').length, writesBeforeRevisionImport, 'Revision Save also waits for the selected import');
    await editor.locator('[data-geo-field=label]').first().fill('Draft entered after import began');
    await page.evaluate(() => { window.geoImportRelease(); File.prototype.text = window.geoOriginalFileText; });
    await expect(editor.locator('[data-geo-field=label]').first()).toHaveValue('Draft entered after import began');
    await importFile.setInputFiles(importPayload);
    await expect(editor.locator('[data-geo-field=label]').first()).toHaveValue('Dateline area');
    await editor.locator('[data-geo-field=label]').first().fill('Reviewed dateline area');
    await page.locator('input[name=research_revision_change_kind][value=correction]').check();
    await page.locator('#research-revision-reason').fill('Synthetic geography revision.');
    // A stale saved-version guard must retain this structured draft and require review.
    saved = await (await page.request.get(recordURL)).json();
    const concurrent = await page.request.post(fixture.url + '/api/research-record-revise', {data: {
      kind: 'dossier', id, expected_snapshot: saved.snapshot, expected_revision: saved.record.revision,
      changes: {body: '# Context\n\nConcurrent source notes.'}, change_kind: 'correction', reason: 'Synthetic concurrent body.'
    }});
    assert.equal(concurrent.ok(), true);
    await page.locator('#research-revision-save').click();
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    await expect(editor.locator('[data-geo-field=label]').first()).toHaveValue('Reviewed dateline area');
    await page.locator('#research-revision-merge-apply').click();
    await expect(page.locator('#research-revision-merge')).not.toBeVisible();
    await page.locator('#research-revision-save').click();
    await expect(page.locator('#modal-research-revision')).not.toBeVisible();
    saved = await (await page.request.get(recordURL)).json();
    assert.equal(saved.record.geography.features[0].properties.label, 'Reviewed dateline area');
    assert.equal(saved.record.geography.features[0].geometry.coordinates.length, 2, 'Polygon holes survive editing');
    assert.deepEqual(saved.record.geography.features[0].properties.actors, ['Mira, narrator', 'Emil'], 'Imported actor names remain intact when editing another field');
    assert.equal(saved.record.geography.features[1].geometry, null);
    assert.equal(saved.record.body, '# Context\n\nConcurrent source notes.');
    await page.locator(`[data-research-revise=dossier][data-record-id="${id}"]:not([data-dossier-section])`).click();
    await editor.locator('summary').first().click();
    await editor.locator('[data-geo-feature]').first().locator('summary').click();
    await editor.locator('[data-geo-field=time_period]').first().fill('1903');
    await page.locator('input[name=research_revision_change_kind][value=correction]').check();
    await page.locator('#research-revision-reason').fill('Synthetic overlapping geography review.');
    const theirGeography = structuredClone(saved.record.geography);
    theirGeography.features[0].properties.time_period = '1904';
    assert.equal((await page.request.post(fixture.url + '/api/research-record-revise', {data: {
      kind: 'dossier', id, expected_snapshot: saved.snapshot, expected_revision: saved.record.revision,
      changes: {geography: theirGeography}, change_kind: 'correction', reason: 'Synthetic concurrent geography.'
    }})).ok(), true);
    await page.locator('#research-revision-save').click();
    await expect(page.locator('#research-revision-merge')).toBeVisible();
    await expect(editor.locator('[data-geo-field=time_period]').first()).toHaveValue('1903');
    await page.locator('#research-revision-merge input[value=mine]').check();
    await page.locator('#research-revision-merge-apply').click();
    await expect(page.locator('#research-revision-merge')).not.toBeVisible();
    await page.locator('#research-revision-save').click();
    await expect(page.locator('#modal-research-revision')).not.toBeVisible();
    saved = await (await page.request.get(recordURL)).json();
    assert.equal(saved.record.geography.features[0].properties.time_period, '1903');
    await openDetails();
    await expect(page.locator('.research-details-body .dossier-geography')).toContainText('Unknown destination');
    await expect(page.locator('.research-details-body .dossier-geography')).toContainText('Location unknown');
    await geography.scrollIntoViewIfNeeded();
    await showSketch(geography);
    assert.ok(!(await page.locator('.research-details-body .dossier-geography .geography-sketch').innerHTML()).match(/NaN|Infinity/));
    assert.ok(await page.locator('.research-details-body .geography-sketch path').evaluate(node => node.getBBox().height > 100), 'Dateline area stays local instead of flattening across 358 degrees');
    await page.locator('[data-dossier-section=Context]').click();
    await expect(page.locator('#research-revision-field-geography')).toHaveCount(0, 'Section editor changes only body');
    await page.keyboard.press('Escape');
    await page.locator(`[data-research-history=dossier][data-record-id="${id}"]`).click();
    await expect(page.locator('#research-revision-history-detail .dossier-geography')).toContainText('Reviewed dateline area');
    await page.locator('#research-revision-versions > summary').click();
    await page.locator('[data-research-revision="1"]').click();
    await expect(page.locator('#research-revision-history-detail .dossier-geography')).toContainText('Mira’s journey');
    await expect(page.locator('#research-revision-history-detail .geography-route-facts')).toContainText('km');
    await expect(page.locator('#research-revision-history-detail .dossier-geography')).not.toContainText('Reviewed dateline');
    await page.keyboard.press('Escape');
    await page.locator('#tab-view-analysis').click();
    await page.locator('#workspace-reader-toggle').click();
    await page.waitForFunction(() => !document.querySelector('#workspace-reader-dossier').disabled);
    await page.locator('#workspace-reader-dossier').selectOption(id);
    await expect(page.locator('#workspace-reader-body .dossier-geography')).toContainText('Reviewed dateline area');
    assert.equal(await page.locator('#workspace-reader-body [data-geo-add]').count(), 0);
    for (const language of ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl']) {
      assert.equal((await page.request.post(fixture.url + '/api/settings', {data: {language}})).ok(), true);
      await page.reload();
      await page.locator('#tab-view-research').click();
      await page.locator('[data-rtab=dossiers]').click();
      await openDetails();
      for (const width of [1440, 320]) {
        await page.setViewportSize({width, height: 950});
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${language}/${width}: dossier fits viewport`);
        const view = page.locator('.research-details-body .dossier-geography');
        await view.scrollIntoViewIfNeeded();
        await showSketch(view);
        assert.ok(!(await view.locator('.geography-overview').textContent()).includes('geography_'), `${language}: overview translated`);
        assert.ok(!(await view.locator('.geography-navigation-hint').textContent()).includes('geography_'), `${language}: navigation guidance translated`);
        const beforeNavigation = requests.length;
        await view.locator('svg [data-geo-select="0"]').focus();
        await page.keyboard.press('Enter');
        await expect(view.locator('li').nth(0).locator('pre')).toBeVisible();
        await view.locator('.geography-feature-list button[data-geo-select="1"]').focus();
        await page.keyboard.press('Space');
        await expect(view.locator('li').nth(1)).toHaveClass(/is-selected/);
        await expect(view.locator('.geography-selected')).toContainText('Unknown destination');
        await expect(view.locator('[data-geo-frame]')).toBeDisabled();
        await expect(view.locator('svg .is-selected')).toHaveCount(0, 'Unknown locations have list details without an invented shape');
        assert.equal(requests.length, beforeNavigation, `${language}/${width}: navigation stays offline`);
        await view.locator('[data-geo-map]').click();
        await expect(view.locator('.geography-map')).toBeVisible();
        await expect(view.locator('.leaflet-control-scale')).toBeVisible();
        assert.ok(!(await view.locator('.geography-map-tools').textContent()).includes('geography_'), `${language}: map controls translated`);
        await view.locator('[data-geo-fit]').click();
        assert.ok(await view.locator('.geography-map').evaluate(node => Number.isFinite(node._geographyMap.getCenter().lng)), 'Dateline map has a finite center');
        assert.ok(await view.locator('.geography-map').evaluate(node => node._geographyMap.getBounds().getEast() - node._geographyMap.getBounds().getWest() < 20), 'Dateline geometry stays local on the map');
        if (language === 'en') {
          await view.screenshot({path: path.join(artifacts, `interactive-map-${width}.png`)});
          await page.emulateMedia({colorScheme: 'dark'});
          await view.screenshot({path: path.join(artifacts, `interactive-map-${width}-dark.png`)});
          await page.emulateMedia({colorScheme: 'light'});
        }
        await view.locator('[data-geo-map]').click();
        await page.locator(`[data-research-revise=dossier][data-record-id="${id}"]:not([data-dossier-section])`).click();
        await page.locator('#research-revision-field-geography-editor > summary').click();
        assert.ok(!(await editor.textContent()).includes('geography_'), `${language}: geography labels translated`);
        assert.ok(await page.locator('#modal-research-revision').evaluate(node => node.scrollWidth <= node.clientWidth), `${language}/${width}: editor fits viewport`);
        if (language === 'en') await page.locator('#modal-research-revision').screenshot({path: path.join(artifacts, `editor-${width}.png`)});
        await editor.locator('[data-geo-feature]').first().locator('summary').click();
        await editor.locator('[data-geo-field=transport]').first().scrollIntoViewIfNeeded();
        await expect(editor.locator('[data-geo-field=transport]').first()).toBeVisible();
        await page.locator('#research-revision-save').scrollIntoViewIfNeeded();
        await expect(page.locator('#research-revision-save')).toBeVisible();
        if (language === 'en') await page.locator('#modal-research-revision').screenshot({path: path.join(artifacts, `editor-bottom-${width}.png`)});
        await page.keyboard.press('Escape');
        if (language === 'en') await page.locator('.research-details-body .dossier-geography').screenshot({path: path.join(artifacts, `sketch-${width}.png`)});
      }
    }
    const staticDocument = await page.evaluate(([value, summary]) => '<!doctype html><html><head>' +
      Array.from(document.querySelectorAll('style')).map(node => node.outerHTML).join('') +
      '</head><body>' + window.LixityDossierGeography.html(value, summary) + '</body></html>', [saved.record.geography, saved.geography_summary]);
    const staticPage = await browser.newPage({javaScriptEnabled: false});
    await staticPage.setContent(staticDocument);
    for (const width of [1440, 320]) {
      await staticPage.setViewportSize({width, height: 950});
      await expect(staticPage.locator('li')).toHaveCount(2);
      await expect(staticPage.locator('.geography-overview')).toHaveText(/^1 .+ · 1 .+ · 2 .+$/);
      await expect(staticPage.locator('li').nth(0)).toContainText('Reviewed dateline area');
      await expect(staticPage.locator('li').nth(1)).toContainText('Unknown destination');
      const coordinates = staticPage.locator('li').nth(0).locator('details');
      if (!(await coordinates.evaluate(node => node.open))) await coordinates.locator('summary').click();
      await expect(coordinates.locator('pre')).toBeVisible();
      assert.ok(await staticPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `Static geography fits ${width}px`);
      await staticPage.screenshot({path: path.join(artifacts, `static-${width}.png`), fullPage: true});
    }
    await staticPage.close();
    assert.ok(writes.some(write => write.geography && write.research_token), 'Create uses selected research context');
    assert.deepEqual(errors, []);
    assert.deepEqual(external, [], 'Geography only requests the standard intercepted tile endpoint');
    console.log(`Dossier geography: native create/edit/import/CAS/history/companion, local pointer/keyboard selection, independent hosts, static fallback and seven languages at 1440/320 passed. Screenshots: ${artifacts}`);
  } finally {
    if (stderr.includes('Traceback')) console.error(stderr);
    if (browser) await browser.close();
    lines.close();
    if (server.exitCode === null) { const exited = once(server, 'exit'); server.kill(); await exited; }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
