// Synthetic retained images exercise the native UI against its real HTTP API.
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn, execFileSync} = require('node:child_process');
const {once} = require('node:events');
const {createInterface} = require('node:readline');
const assert = require('node:assert/strict');
const {expect} = require(path.join(playwrightModule, 'test'));
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-dossier-images-'));
const python = process.env.PYTHON_BIN || path.join(root, '.venv/bin/python');

function waitForHeldResponse(promise, label) {
  let timer;
  return Promise.race([promise, new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`Timed out waiting for ${label}`)), 10000);
  })]).finally(() => clearTimeout(timer));
}

async function checkDiagramReadability(page) {
  const diagrams = [
    ['wide', 'flowchart LR\n A[Collect sources] --> B[Check provenance] --> C[Compare evidence] --> D[Record decision]'],
    ['vertical', 'flowchart TD\n A[Read] --> B[Review] --> C[Decide]'],
  ];
  await page.evaluate(diagrams => {
    const host = document.createElement('section'); host.id = 'diagram-readability';
    host.innerHTML = diagrams.map(([name, source]) => '<div data-diagram-fixture="' + name + '">' +
      renderSafeMarkdown('```mermaid\n' + source + '\n```') + '</div>').join('');
    document.querySelector('.research-dossier-body-rendered .research-prose').appendChild(host);
  }, diagrams);
  for (const width of [320, 1440]) {
    await page.setViewportSize({width, height: 1000});
    for (const theme of ['light', 'dark']) {
      await page.evaluate(theme => { document.documentElement.dataset.theme = theme; }, theme);
      for (const [name, source] of diagrams) {
        const figure = page.locator(`[data-diagram-fixture=${name}] [data-research-diagram]`);
        await figure.scrollIntoViewIfNeeded();
        await expect(figure).toHaveAttribute('data-diagram-state', 'ready');
        await expect(figure.locator('code')).toHaveText(source);
        await expect(figure.getByText('Diagram, scroll horizontally when needed', {exact: true})).toBeVisible();
        const metrics = await figure.evaluate(element => {
          const svg = element.querySelector('svg'), canvas = element.querySelector('.research-diagram-canvas');
          const bounds = svg.getBoundingClientRect(), outer = element.getBoundingClientRect(), viewport = canvas.getBoundingClientRect();
          const fonts = [...svg.querySelectorAll('text')].map(text => {
            const transform = text.getScreenCTM();
            return parseFloat(getComputedStyle(text).fontSize) * Math.hypot(transform.a, transform.b);
          });
          return {width: bounds.width, height: bounds.height, intrinsicWidth: svg.viewBox.baseVal.width,
            minimumFont: Math.min(...fonts), viewportWidth: canvas.clientWidth, contentWidth: canvas.scrollWidth,
            left: outer.left, right: outer.right, diagramStart: bounds.left - viewport.left,
            pageWidth: document.documentElement.scrollWidth};
        });
        await figure.screenshot({path: path.join(artifacts, `diagram-${name}-${theme}-${width}.png`)});
        assert.ok(Number.isFinite(metrics.minimumFont) && metrics.minimumFont >= 12, `${name} ${theme} ${width}px readable labels: ${JSON.stringify(metrics)}`);
        assert.ok(metrics.width >= metrics.intrinsicWidth * .98, `${name} retains Mermaid's intrinsic layout`);
        assert.ok(metrics.diagramStart >= 0, 'The start of an overflowing diagram remains reachable');
        if (name === 'vertical' && width === 1440) assert.ok(metrics.right - metrics.left < width / 2, 'A small diagram keeps a compact frame');
        assert.ok(metrics.left >= 0 && metrics.right <= width && metrics.pageWidth <= width, `${name} must not widen the page`);
        if (name === 'wide' && width === 320) {
          assert.ok(metrics.contentWidth > metrics.viewportWidth, 'Wide diagrams scroll within their own viewport');
          const canvas = figure.locator('.research-diagram-canvas');
          await expect(canvas).toHaveAccessibleName('Diagram, scroll horizontally when needed');
          await canvas.focus();
          await page.keyboard.press('ArrowRight');
          await expect.poll(() => canvas.evaluate(element => element.scrollLeft)).toBeGreaterThan(0);
          await page.keyboard.press('Tab');
          await expect(figure.locator('[data-diagram-enlarge]')).toBeFocused();
          await page.keyboard.press('Enter');
          const viewer = page.locator('#modal-dossier-image-enlarge');
          await expect(viewer.locator('img.pswp__img')).toBeVisible();
          await expect.poll(() => viewer.locator('img.pswp__img').evaluate(image => image.naturalWidth)).toBeGreaterThan(0);
          await page.keyboard.press('Escape');
          await expect(figure.locator('[data-diagram-enlarge]')).toBeFocused();
          await canvas.evaluate(element => { element.scrollLeft = 0; });
        }
        if (name === 'vertical' || width === 1440) assert.ok(metrics.contentWidth <= metrics.viewportWidth, `Fitting diagrams avoid unnecessary scrolling: ${JSON.stringify(metrics)}`);
      }
    }
  }
  await page.evaluate(() => { document.getElementById('diagram-readability').remove(); document.documentElement.dataset.theme = 'light'; });
  await page.setViewportSize({width: 1440, height: 1000});
}

(async () => {
  const server = spawn(python, ['-u', '-c', `
import json, struct, sys, zlib
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
base = Path(sys.argv[1]); project = base / 'synthetic-project'
api.init(project, title='Synthetic image research')
def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
png = b'\\x89PNG\\r\\n\\x1a\\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 2, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b'\\0\\xff\\0\\0\\0\\xff\\0' * 2)) + chunk(b'IEND', b'')
(base / 'synthetic.png').write_bytes(png)
(base / 'synthetic-apng.png').write_bytes(png[:33] + chunk(b'acTL', struct.pack('>II', 1, 0)) + png[33:])
jpeg = bytes.fromhex('ffd8ffe000104a46494600010100000100010000ffdb004300' + '01' * 64 + 'ffc0000b080001000101011100ffc40014000100000000000000000000000000000000ffc40014100100000000000000000000000000000000ffda0008010100003f003fffd9')
(base / 'synthetic.jpg').write_bytes(jpeg)
dossier = api.create_dossier(project, title='Synthetic image dossier', body='# Notes\\n\\nRetained evidence.\\n\\n# Detail\\n\\nSecond section.')
other_dossier = api.create_dossier(project, title='Other synthetic dossier', body='Unrelated synthetic content.')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.language = 'en'; LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'project': str(project), 'dossier': dossier['dossier_id'], 'other_dossier': other_dossier['dossier_id']}), flush=True)
server.serve_forever()
`, artifacts], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, stdio: ['ignore', 'pipe', 'pipe']});
  let stderr = '';
  server.stderr.on('data', data => { stderr += data; });
  const lines = createInterface({input: server.stdout});
  let browser;
  const releaseHeldResponses = [];
  try {
    const fixture = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Fixture startup timed out: ' + stderr)), 15000);
      lines.once('line', line => { clearTimeout(timeout); resolve(JSON.parse(line)); });
      server.once('error', reject);
      server.once('exit', code => reject(new Error(`Fixture exited ${code}: ${stderr}`)));
    });
    const dossierListURL = url => url.origin === fixture.url &&
      url.pathname === '/api/research/dossiers' && !url.searchParams.has('id');
    const dossierDetailURL = url => url.origin === fixture.url &&
      url.pathname === '/api/research/dossiers' && url.searchParams.has('id');
    browser = await launchChromium();
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [], external = [], writes = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (!request.url().startsWith(fixture.url) && !request.url().startsWith('blob:')) external.push(request.url());
      if (request.method() === 'POST' && request.url().endsWith('/research-dossier-image')) writes.push(request.postDataJSON());
    });
    await page.addInitScript(() => {
      window.imageURLs = {created: [], revoked: []};
      const create = URL.createObjectURL.bind(URL), revoke = URL.revokeObjectURL.bind(URL);
      URL.createObjectURL = value => { const url = create(value); window.imageURLs.created.push(url); return url; };
      URL.revokeObjectURL = url => { window.imageURLs.revoked.push(url); revoke(url); };
    });
    await page.goto(fixture.url);
    assert.equal(new URL(page.url()).origin, fixture.url);
    assert.ok((await page.title()).includes('No Project Loaded'));
    assert.ok((await page.locator('body').textContent()).includes('Research'));
    const plainHTTP = await page.evaluate(() => {
      const randomUUID = crypto.randomUUID;
      Object.defineProperty(crypto, 'randomUUID', {configurable: true, value: undefined});
      try { return renderSafeMarkdown('Synthetic dossier text.', {project_id: 'synthetic', images: []}); }
      catch (error) { return {error: error.message}; }
      finally { Object.defineProperty(crypto, 'randomUUID', {configurable: true, value: randomUUID}); }
    });
    assert.equal(plainHTTP, '<p>Synthetic dossier text.</p>', 'Resolver also works when randomUUID is unavailable on an HTTP host');
    await page.locator('#tab-view-research').click();
    await page.locator('[data-rtab=dossiers]').click();
    await page.locator(`[data-research-detail=dossier][data-record-id="${fixture.dossier}"]`).click();
    await expect(page.locator('[data-dossier-add-image]')).toBeVisible();
    await checkDiagramReadability(page);
    await page.locator('[data-dossier-add-image]').click();
    const dialog = page.locator('#modal-dossier-image');
    const file = {name: 'synthetic.png', mimeType: 'image/png', buffer: fs.readFileSync(path.join(artifacts, 'synthetic.png'))};
    await page.locator('#dossier-image-file').setInputFiles(file);
    await expect(page.locator('#dossier-image-preview img')).toBeVisible();
    // Selection A completes after B; a late local read must not replace B.
    await page.evaluate(() => {
      window.readImageBuffer = File.prototype.arrayBuffer;
      File.prototype.arrayBuffer = function() {
        if (this.name === 'slow.png') return new Promise(resolve => { window.finishSlowImage = () => window.readImageBuffer.call(this).then(resolve); });
        return window.readImageBuffer.call(this);
      };
    });
    await page.locator('#dossier-image-file').setInputFiles({...file, name: 'slow.png'});
    await page.locator('#dossier-image-file').setInputFiles({...file, name: 'newest.png'});
    await expect(page.locator('#dossier-image-preview')).toContainText('newest.png');
    await page.evaluate(async () => { await window.finishSlowImage(); File.prototype.arrayBuffer = window.readImageBuffer; });
    await expect(page.locator('#dossier-image-preview')).toContainText('newest.png');
    await page.locator('#dossier-image-file').setInputFiles(file);
    await expect(page.locator('#dossier-image-preview img')).toBeVisible();
    assert.deepEqual(await page.locator('#dossier-image-preview img').evaluate(image => [image.naturalWidth, image.naturalHeight]), [2, 2]);
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();
    assert.equal(writes.length, 0, 'Preview and cancel must not retain source bytes');
    await expect(page.locator('[data-dossier-add-image]')).toBeFocused();
    await expect.poll(() => page.evaluate(() => window.imageURLs.created.length === window.imageURLs.revoked.length)).toBe(true);
    assert.deepEqual(await page.evaluate(() => window.imageURLs.created), await page.evaluate(() => window.imageURLs.revoked), 'Cancel revokes preview URLs');
    await page.locator('[data-dossier-add-image]').click();
    // Real JPEG decoding accompanies PNG; rejected SVG never reaches decoding.
    await page.locator('#dossier-image-file').setInputFiles({name: 'synthetic.jpg', mimeType: 'image/jpeg', buffer: fs.readFileSync(path.join(artifacts, 'synthetic.jpg'))});
    await expect(page.locator('#dossier-image-preview img')).toBeVisible();
    assert.deepEqual(await page.locator('#dossier-image-preview img').evaluate(image => [image.naturalWidth, image.naturalHeight]), [1, 1]);
    await page.locator('#dossier-image-file').setInputFiles({name: 'hostile.svg', mimeType: 'image/svg+xml', buffer: Buffer.from('<svg onload="alert(1)"></svg>')});
    await expect(page.locator('#dossier-image-status.err')).toBeVisible();
    assert.equal(await page.locator('#dossier-image-preview img').count(), 0);
    await page.evaluate(() => {
      window.imageDecodeCalls = 0; window.originalImageDecode = Image.prototype.decode;
      Image.prototype.decode = function() { window.imageDecodeCalls++; return window.originalImageDecode.call(this); };
    });
    await page.locator('#dossier-image-file').setInputFiles({name: 'synthetic-apng.png', mimeType: 'image/png', buffer: fs.readFileSync(path.join(artifacts, 'synthetic-apng.png'))});
    await expect.poll(() => page.evaluate(() => window.imageDecodeCalls > 0 || Boolean(document.querySelector('#dossier-image-status.err')))).toBe(true);
    assert.equal(await page.evaluate(() => window.imageDecodeCalls), 0, 'APNG chunks are rejected before native decoding');
    await page.evaluate(() => { Image.prototype.decode = window.originalImageDecode; });
    const hugeDimensions = Buffer.from(file.buffer); hugeDimensions.writeUInt32BE(65535, 16); hugeDimensions.writeUInt32BE(65535, 20);
    const urlCount = await page.evaluate(() => window.imageURLs.created.length);
    for (const invalid of [
      {...file, buffer: hugeDimensions},
      {...file, buffer: Buffer.alloc(16 * 1024 * 1024 + 1)},
      {...file, name: 'wrong-format.jpg'}
    ]) {
      await page.locator('#dossier-image-file').setInputFiles(invalid);
      await expect(page.locator('#dossier-image-status.err')).toBeVisible();
      assert.equal(await page.evaluate(() => window.imageURLs.created.length), urlCount, 'Bounds and signature preflight run before native decoding');
    }
    await page.locator('#dossier-image-file').setInputFiles(file);
    await page.locator('#dossier-image-alt').fill('Synthetic [red] and \\green squares " onload="alert(1) <img src=x onerror=alert(1)>');
    await page.locator('#dossier-image-options > summary').click();
    await page.locator('#dossier-image-caption').fill('A synthetic caption <script>alert(1)</script>.');
    await page.locator('#dossier-image-note').fill('Synthetic provenance <img src=x onerror=window.imageProvenanceInjected=true>');
    await page.locator('#dossier-image-origin').fill('https://example.org/synthetic-source');
    await page.locator('#dossier-image-section').selectOption('Notes');
    await page.locator('#dossier-image-retention').check();
    // A valid preview does not override authoritative server validation.
    const sourcesBeforeRejection = await (await page.request.get(fixture.url + '/api/research/sources')).json();
    await page.route('**/api/research-dossier-image', route => route.continue({postData: JSON.stringify({...route.request().postDataJSON(), content_base64: Buffer.from('invalid raster').toString('base64')})}));
    await page.locator('#dossier-image-save').click();
    await expect(page.locator('#dossier-image-status.err')).toBeVisible();
    await expect(page.locator('#dossier-image-alt')).toHaveValue('Synthetic [red] and \\green squares " onload="alert(1) <img src=x onerror=alert(1)>');
    await expect(page.locator('#dossier-image-preview img')).toBeVisible();
    assert.equal((await (await page.request.get(fixture.url + '/api/research/sources')).json()).sources.length, sourcesBeforeRejection.sources.length);
    await page.unroute('**/api/research-dossier-image');
    let finishSave, startedSave, acceptedEnvelope;
    const saveGate = new Promise(resolve => { finishSave = resolve; });
    releaseHeldResponses.push(finishSave);
    const saveReady = new Promise(resolve => { startedSave = resolve; });
    await page.route('**/api/research-dossier-image', async route => {
      const response = await route.fetch(); acceptedEnvelope = await response.json(); startedSave(); await saveGate; await route.fulfill({response});
    });
    let finishDetail, startedDetail;
    const detailGate = new Promise(resolve => { finishDetail = resolve; });
    releaseHeldResponses.push(finishDetail);
    const detailReady = new Promise(resolve => { startedDetail = resolve; });
    await page.route(dossierDetailURL, async route => {
      const response = await route.fetch(); startedDetail(); await detailGate; await route.fulfill({response});
    });
    await page.locator('#dossier-image-save').click();
    await waitForHeldResponse(saveReady, 'image save response');
    await expect(page.locator('#dossier-image-save')).toBeDisabled();
    await page.evaluate(() => document.getElementById('dossier-image-form').requestSubmit());
    await page.keyboard.press('Escape');
    await expect(dialog).toBeVisible();
    finishSave();
    await expect(dialog).not.toBeVisible();
    await waitForHeldResponse(detailReady, 'dossier detail response');
    await page.locator('#r-filter-dossiers').fill('Synthetic');
    await page.locator('#r-filter-dossiers').focus();
    finishDetail();
    await page.unroute('**/api/research-dossier-image');
    await expect(page.locator('.research-dossier-body-rendered .dossier-image img')).toBeVisible();
    await expect(page.locator('.research-dossier-body-rendered .dossier-image figcaption')).toContainText('Synthetic provenance <img src=x onerror=window.imageProvenanceInjected=true>');
    await expect(page.locator('.research-dossier-body-rendered .dossier-image figcaption a')).toHaveAttribute('href', 'https://example.org/synthetic-source');
    assert.equal(await page.evaluate(() => Boolean(window.imageProvenanceInjected)), false);
    await expect(page.locator('#r-filter-dossiers')).toBeFocused();
    await page.unroute(dossierDetailURL);
    // Clicking dossier content gives its labelled tabpanel focus. An accepted
    // save must respect that move when its delayed reconciliation completes.
    let finishMovedDetail, startedMovedDetail;
    const movedDetailGate = new Promise(resolve => { finishMovedDetail = resolve; });
    releaseHeldResponses.push(finishMovedDetail);
    const movedDetailReady = new Promise(resolve => { startedMovedDetail = resolve; });
    await page.route(dossierDetailURL, async route => {
      const response = await route.fetch(); startedMovedDetail(); await movedDetailGate; await route.fulfill({response});
    });
    await page.locator('[data-dossier-add-image]').focus();
    await page.evaluate(accepted => {
      document.getElementById('research-status-bar').textContent = '';
      document.dispatchEvent(new CustomEvent('lixity:dossier-image-saved', {detail: accepted}));
    }, acceptedEnvelope);
    await waitForHeldResponse(movedDetailReady, 'moved-focus dossier detail response');
    await page.locator('#r-filter-dossiers').fill('Synthetic');
    await page.locator('#r-filter-dossiers').focus();
    await page.locator('#research-dossiers-list .research-card-title').first().click();
    const dossierPane = page.locator('#rtab-dossiers');
    await expect(dossierPane).toBeVisible();
    await expect(dossierPane).toBeFocused();
    finishMovedDetail();
    await expect(page.locator('#research-status-bar')).toContainText('Image and dossier saved.');
    await expect(page.locator('.research-dossier-body-rendered .dossier-image img')).toBeVisible();
    await expect(page.locator('[data-dossier-add-image]')).not.toBeFocused();
    await expect(dossierPane).toBeFocused();
    await expect(page.locator('#r-filter-dossiers')).toHaveValue('Synthetic');
    await page.unroute(dossierDetailURL);
    // An unrelated dossier control selected while a list read is pending must
    // keep its focus even if the list refresh replaces its original DOM node.
    let finishList, startedList;
    const listGate = new Promise(resolve => { finishList = resolve; });
    releaseHeldResponses.push(finishList);
    const listReady = new Promise(resolve => { startedList = resolve; });
    await page.route(dossierListURL, async route => {
      const response = await route.fetch(); startedList(); await listGate; await route.fulfill({response});
    });
    await page.locator('[data-dossier-add-image]').focus();
    await page.evaluate(accepted => {
      document.getElementById('research-status-bar').textContent = '';
      document.dispatchEvent(new CustomEvent('lixity:dossier-image-saved', {detail: accepted}));
    }, acceptedEnvelope);
    await waitForHeldResponse(listReady, 'dossier list response');
    const otherSummary = page.locator(`[data-research-detail=dossier][data-record-id="${fixture.other_dossier}"]`);
    await otherSummary.focus();
    await expect(otherSummary).toBeFocused();
    finishList();
    await expect(page.locator('#research-status-bar')).toContainText('Image and dossier saved.');
    await expect(page.locator('.research-dossier-body-rendered .dossier-image img')).toBeVisible();
    await expect(otherSummary).toBeFocused();
    await page.unroute(dossierListURL);
    assert.equal(writes.length, 2, 'One rejected save plus one accepted save; busy resubmission sends no request');
    assert.equal(writes[1].allow_retention, true);
    assert.equal(writes[1].section, 'Notes');
    assert.ok(writes[1].expected_snapshot);
    assert.equal(writes[1].expected_revision, 1);
    const figure = page.locator('.research-dossier-body-rendered .dossier-image');
    await expect(page.locator('.research-dossier-body-rendered')).toContainText('A synthetic caption');
    assert.equal(await figure.locator('script').count(), 0);
    await figure.locator('[data-dossier-enlarge]').click();
    await expect(page.locator('#modal-dossier-image-enlarge')).toBeVisible();
    await expect(page.locator('#modal-dossier-image-enlarge .pswp__button--zoom')).toBeVisible();
    await expect(page.locator('#modal-dossier-image-enlarge .pswp__caption')).toContainText('synthetic.png');
    await expect(page.locator('#modal-dossier-image-enlarge .pswp__caption')).toContainText('Synthetic provenance');
    await expect(page.locator('#modal-dossier-image-enlarge .pswp__caption')).toContainText('Source context Synthetic provenance');
    await page.keyboard.press('Escape');
    await expect(figure.locator('[data-dossier-enlarge]')).toBeFocused();
    // Lazy images belong to the gallery before inline decode. A delayed image
    // that completes outside the visible slides must fit when revisited.
    const imageURL = await figure.locator('img').evaluate(image => image.src);
    const lazyURLs = [1, 2, 3].map(index => imageURL + '&gallery_fixture=held' + index);
    const lazyLoads = new Map();
    for (const url of lazyURLs) {
      await page.route(url, route => new Promise(resolve => {
        lazyLoads.set(url, async () => {
          await route.fulfill({contentType: 'image/png', body: file.buffer}); resolve();
        });
      }));
    }
    await figure.evaluate((element, urls) => {
      for (const src of urls) {
        const lazy = element.cloneNode(true);
        lazy.classList.add('offscreen-gallery-image');
        lazy.style.cssText = 'position:absolute;top:100000px;left:0';
        const image = document.createElement('img');
        image.loading = 'lazy'; image.src = src;
        lazy.querySelector('img').replaceWith(image);
        element.parentElement.appendChild(lazy);
      }
    }, lazyURLs);
    assert.deepEqual(await page.locator('.offscreen-gallery-image img')
      .evaluateAll(images => images.map(image => image.naturalWidth)), [0, 0, 0]);
    await figure.first().locator('[data-dossier-enlarge]').click();
    await expect(page.locator('#modal-dossier-image-enlarge .pswp__counter')).toHaveText('1 / 4');
    await expect.poll(() => lazyLoads.size).toBe(2);
    const next = page.locator('#modal-dossier-image-enlarge .pswp__button--arrow--next');
    const previous = page.locator('#modal-dossier-image-enlarge .pswp__button--arrow--prev');
    await next.click();
    await expect(page.locator('#modal-dossier-image-enlarge .pswp__counter')).toHaveText('2 / 4');
    const delayedImage = await page.locator('#modal-dossier-image-enlarge .pswp__item[aria-hidden=false] img.pswp__img').elementHandle();
    await expect.poll(() => lazyLoads.size).toBe(3);
    await Promise.all([...lazyLoads].filter(([url]) => url !== lazyURLs[0]).map(([, release]) => release()));
    await next.click();
    await next.click();
    await expect(page.locator('#modal-dossier-image-enlarge .pswp__counter')).toHaveText('4 / 4');
    await expect.poll(() => delayedImage.evaluate(image => image.isConnected)).toBe(false);
    await lazyLoads.get(lazyURLs[0])();
    await delayedImage.evaluate(image => image.decode());
    await previous.click();
    await previous.click();
    await expect(page.locator('#modal-dossier-image-enlarge .pswp__counter')).toHaveText('2 / 4');
    const currentImage = page.locator('#modal-dossier-image-enlarge .pswp__item[aria-hidden=false] img.pswp__img');
    await expect.poll(() => currentImage.evaluate(image => {
      const box = image.getBoundingClientRect();
      return image.naturalWidth && box.height && box.width
        ? Math.abs(box.width / box.height - image.naturalWidth / image.naturalHeight) : Infinity;
    })).toBeLessThan(.01);
    await page.keyboard.press('Escape');
    await page.locator('.offscreen-gallery-image').evaluateAll(elements => elements.forEach(element => element.remove()));
    for (const url of lazyURLs) await page.unroute(url);
    const detail = await (await page.request.get(fixture.url + '/api/research/dossiers?id=' + fixture.dossier)).json();
    assert.equal(detail.images.length, 1);
    const pin = detail.images[0];
    await expect(page.locator('#research-sources-list')).toContainText('image/png');
    assert.equal(await page.locator(`#r-ground-source-select option[value="${pin.source_id}"]`).count(), 0, 'Raster sources cannot enter textual comparison');
    await page.locator('[data-rtab=sources]').click();
    await page.locator(`[data-research-detail=source][data-record-id="${pin.source_id}"]`).click();
    await expect(page.locator('#research-sources-list')).toContainText('no text passages or textual comparison');
    assert.equal(await page.locator('#research-sources-list [data-source-view]').count(), 0, 'An image source has no fabricated text view');
    const dossierSummary = page.locator(`[data-research-detail=dossier][data-record-id="${fixture.dossier}"]`);
    await Promise.all([page.waitForResponse(response => dossierListURL(new URL(response.url())), {timeout: 10000}), page.locator('[data-rtab=dossiers]').click()]);
    // A refresh preserves an unchanged open detail, so close it first;
    // clicking blindly would toggle the preserved detail shut.
    if (await dossierSummary.evaluate(node => node.parentElement.open)) await dossierSummary.click();
    await dossierSummary.click();
    await expect(page.locator('[data-dossier-add-image]')).toBeVisible();
    const markdownChecks = await page.evaluate(({detail, pin}) => {
      const source = detail.body.match(/!\[[\s\S]+?\]\(lixity:image[^\n]+?\)/)[0];
      const host = document.createElement('div');
      const result = {};
      function count(text, context) { host.innerHTML = renderSafeMarkdown(text, context); return host.querySelectorAll('img').length; }
      result.available = count(source, detail);
      result.code = count('~~~\n' + source + '\n~~~\n\n`' + source + '`\n\n    ' + source + '\n\n\\' + source, detail);
      result.mixed = count(source + '\n\n```\n' + source + '\n```', detail);
      result.otherRecord = count(source);
      result.hostile = count('![x](https://example.org/image.png) ![x](data:image/svg+xml,x) ![x](javascript:alert(1)) <img src="https://example.org/x">', detail);
      result.onLoad = count(source, detail) && host.querySelector('img').getAttribute('onload');
      const badProject = {...detail, project_id: 'urn:uuid:11111111-1111-4111-8111-111111111111'};
      result.projectMismatch = count(source, badProject);
      for (const availability of ['missing', 'withdrawn', 'purged', 'unavailable']) {
        const context = {...detail, images: [{...pin, availability, url: 'https://example.org/never.png'}]};
        result[availability] = count(source, context);
        result[availability + 'Text'] = host.textContent;
      }
      const poison = {...detail, images: [{...pin, url: 'https://example.org/never.png'}]};
      count(source, poison); result.url = host.querySelector('img').getAttribute('src');
      return result;
    }, {detail, pin});
    assert.equal(markdownChecks.available, 1);
    assert.equal(markdownChecks.code, 0, 'Code and escaped literals never resolve images');
    assert.equal(markdownChecks.mixed, 1, 'A code duplicate must remain inert beside the same rendered pin');
    assert.equal(markdownChecks.otherRecord, 0);
    assert.equal(markdownChecks.hostile, 0);
    assert.equal(markdownChecks.onLoad, null, 'Hostile alt attributes remain text');
    assert.equal(markdownChecks.projectMismatch, 0);
    for (const availability of ['missing', 'withdrawn', 'purged', 'unavailable']) {
      assert.equal(markdownChecks[availability], 0);
      assert.ok(markdownChecks[availability + 'Text'].length > 20);
    }
    assert.ok(markdownChecks.url.startsWith('/api/research/image?'));
    const binary = await page.request.get(fixture.url + pin.url);
    assert.equal(binary.status(), 200);
    assert.deepEqual(await binary.body(), file.buffer);
    // A real concurrent publication rejects both image and revision, preserving
    // all local inputs until the author explicitly reviews a fresh read.
    await page.locator('[data-dossier-add-image]').click();
    await page.locator('#dossier-image-file').setInputFiles(file);
    await page.locator('#dossier-image-alt').fill('Second synthetic attachment');
    await page.locator('#dossier-image-retention').check();
    const before = await (await page.request.get(fixture.url + '/api/research/sources')).json();
    execFileSync(python, ['-c', 'import sys; from lixity.research import api; api.create_dossier(sys.argv[1], title="Concurrent synthetic dossier", body="Concurrent publication.")', fixture.project], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}});
    await page.locator('#dossier-image-save').click();
    await expect(page.locator('#dossier-image-conflict')).toBeVisible();
    await expect(page.locator('#dossier-image-alt')).toHaveValue('Second synthetic attachment');
    await expect(page.locator('#dossier-image-preview img')).toBeVisible();
    await expect(page.locator('#dossier-image-save')).toBeDisabled();
    const after = await (await page.request.get(fixture.url + '/api/research/sources')).json();
    assert.equal(after.sources.length, before.sources.length, 'A stale attachment leaves no orphan capture');
    await page.locator('#dossier-image-review').click();
    await expect(page.locator('#dossier-image-current')).toContainText('Version 2');
    await expect(page.locator('#dossier-image-save')).toBeDisabled();
    await page.locator('#dossier-image-accept-current').click();
    await expect(page.locator('#dossier-image-save')).toBeEnabled();
    await page.keyboard.press('Escape');
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({width, height: 900});
      await figure.scrollIntoViewIfNeeded();
      assert.ok(await figure.evaluate(element => element.getBoundingClientRect().right <= innerWidth));
      await page.screenshot({path: path.join(artifacts, `figure-${width}.png`)});
    }
    // A newer capture for the same source does not replace an accepted pin.
    execFileSync(python, ['-c', 'import sys; from lixity.research import api; api.ingest(sys.argv[1], sys.argv[2], source_id=sys.argv[3], allow_retention=True)', fixture.project, path.join(artifacts, 'synthetic.jpg'), pin.source_id], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}});
    const latestSources = await (await page.request.get(fixture.url + '/api/research/sources')).json();
    assert.ok(latestSources.sources[0].version_id);
    assert.notEqual(latestSources.sources[0].version_id, pin.source_version_id);
    const currentDossier = await (await page.request.get(fixture.url + '/api/research/dossiers?id=' + fixture.dossier)).json();
    assert.equal(currentDossier.images[0].source_version_id, pin.source_version_id);
    assert.deepEqual(await (await page.request.get(fixture.url + pin.url)).body(), file.buffer);
    await page.setViewportSize({width: 1440, height: 1000});
    await page.locator(`[data-research-history=dossier][data-record-id="${fixture.dossier}"]`).click();
    await expect(page.locator('#research-revision-history .dossier-image img')).toBeVisible();
    assert.ok((await page.locator('#research-revision-history .dossier-image img').getAttribute('src')).includes(encodeURIComponent(pin.source_version_id)));
    await page.keyboard.press('Escape');
    for (const operation of ['withdraw', 'purge']) {
      execFileSync(python, ['-c', 'import sys; from lixity.research import api; getattr(api, sys.argv[3])(sys.argv[1], source_id=sys.argv[2], reason="Synthetic image lifecycle test")', fixture.project, pin.source_id, operation], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}});
      await page.reload();
      await page.locator('#tab-view-research').click();
      await page.locator('[data-rtab=dossiers]').click();
      await page.locator(`[data-research-detail=dossier][data-record-id="${fixture.dossier}"]`).click();
      await expect(page.locator('.research-dossier-body-rendered .dossier-image-unavailable')).toBeVisible();
      assert.equal(await page.locator('.research-dossier-body-rendered .dossier-image img').count(), 0);
      await expect(page.locator('.research-dossier-body-rendered .dossier-image')).toContainText(operation === 'withdraw' ? 'Image withdrawn' : 'Image purged');
      await expect(page.locator('.research-dossier-body-rendered .dossier-image')).toContainText('Synthetic image lifecycle test');
    }
    for (const language of ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl']) {
      assert.equal((await page.request.post(fixture.url + '/api/settings', {data: {language}})).ok(), true);
      await page.reload();
      await expect(page.locator('html')).toHaveAttribute('lang', language);
      await page.locator('#tab-view-research').click();
      await page.locator('[data-rtab=dossiers]').click();
      await page.locator(`[data-research-detail=dossier][data-record-id="${fixture.dossier}"]`).click();
      await page.locator('[data-dossier-add-image]').click();
      await page.locator('#dossier-image-file').setInputFiles(file);
      await expect(page.locator('#dossier-image-preview img')).toBeVisible();
      await page.locator('#dossier-image-options > summary').click();
      assert.ok(!(await dialog.textContent()).includes('image_'), `${language} must have translated image labels`);
      for (const width of language === 'en' ? [1440, 390, 320] : [320]) {
        await page.setViewportSize({width, height: 900});
        assert.ok(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth), `${language} ${width}px dialog overflow`);
        await dialog.screenshot({path: path.join(artifacts, `dialog-${language}-${width}.png`)});
        await page.locator('#dossier-image-save').scrollIntoViewIfNeeded();
        await expect(page.locator('#dossier-image-retention')).toBeVisible();
        await dialog.screenshot({path: path.join(artifacts, `dialog-bottom-${language}-${width}.png`)});
      }
      await page.keyboard.press('Escape');
      await expect(dialog).not.toBeVisible();
    }
    assert.deepEqual(external, [], 'Images must not make external requests');
    assert.deepEqual(errors, []);
    console.log(`Dossier images: readable Mermaid viewport/keyboard enlargement at 1440/320 in light/dark; PNG/JPEG decoding; preview cancel/race/limits; atomic save busy/error/CAS recovery; exact old pins, full/section/history and lifecycle states; hostile data with no external requests; seven locales at 1440/390/320 passed. Screenshots: ${artifacts}`);
  } finally {
    releaseHeldResponses.forEach(release => release());
    if (stderr.includes('Traceback')) console.error(stderr);
    if (browser) await browser.close();
    lines.close();
    if (server.exitCode === null) { const exited = once(server, 'exit'); server.kill(); await exited; }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
