// The public Pages adapter uses only GoatCounter's documented pixel parameters.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-pages-analytics-'));
const runtime = fs.readFileSync(path.resolve(__dirname, '../../docs/assets/analytics.js'), 'utf8');
const publicOrigin = 'https://mfahsold.github.io';
const pixelOrigin = 'https://mfahsold.goatcounter.com';
const gif = Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64');
const fixture = `<!doctype html><title>Lixity public guide</title>
<main><h1>Public synthetic guide</h1><textarea>PRIVATE MANUSCRIPT DRAFT</textarea>
<a id="demo" href="/lixity/demo/report.html?private=SECRET#selection">Demo</a>
<a id="install" href="/lixity/guides/installation.html">Install</a>
<a id="install-reference" href="/lixity/INSTALLATION.md">Installation reference</a>
<a id="install-anchor" href="/lixity/#install">Install section</a>
<a id="repository" href="https://github.com/mfahsold/lixity">Repository</a>
<a id="pdf" href="/lixity/demo/warehouse-4-book.pdf?private=SECRET">PDF</a>
<a id="pdf-editor" href="/lixity/demo/warehouse-4-editor.pdf">Editorial PDF</a>
<a id="pdf-sheet" href="/lixity/demo/warehouse-4-sheet.pdf">Sheet PDF</a>
<a id="pdf-report" href="/lixity/demo/warehouse-4-report.pdf">Report PDF</a>
<a id="pdf-document" href="/lixity/demo/warehouse-4-document.pdf">Document PDF</a>
<a id="other-pdf" href="/lixity/private.pdf">Unreviewed PDF</a>
<a id="untracked" data-goatcounter-click="PRIVATE CUSTOM EVENT" href="https://example.test/private">Other destination</a>
<a id="spoof" href="https://github.com.evil.test/mfahsold/lixity">Other host</a></main>
<script defer src="/lixity/assets/analytics.js"></script>`;

(async () => {
  const browser = await launchChromium();
  async function open({url = publicOrigin + '/lixity/guides/first-look.html?private=SECRET#quote',
    config = {site_code: 'mfahsold'}, configStatus = 200, brokenJson = false,
    pixelFailure = false, holdPixels = false, holdConfig = false, privacy = {}, width = 1440} = {}) {
    const context = await browser.newContext({viewport: {width, height: 900}});
    await context.addInitScript(privacy => {
      for (const [key, value] of Object.entries(privacy)) {
        Object.defineProperty(navigator, key, {get: () => value});
      }
    }, privacy);
    const page = await context.newPage();
    const requests = [], pixels = [], unexpected = [], warnings = [], errors = [];
    let releasePixels, releaseConfig;
    const pixelGate = new Promise(resolve => {releasePixels = resolve;});
    const configGate = new Promise(resolve => {releaseConfig = resolve;});
    page.on('request', request => requests.push(request.url()));
    page.on('console', message => {
      if (message.type() === 'warning') warnings.push(message.text());
    });
    page.on('pageerror', error => errors.push(error.message));
    await context.route('**/*', async route => {
      const request = route.request(), requestUrl = new URL(request.url());
      if (requestUrl.origin === pixelOrigin && requestUrl.pathname === '/count') {
        pixels.push({url: requestUrl, headers: request.headers(), method: request.method()});
        if (pixelFailure) return route.abort();
        if (holdPixels) await pixelGate;
        return route.fulfill({contentType: 'image/gif', body: gif});
      }
      if (requestUrl.pathname === '/lixity/assets/analytics.js') {
        return route.fulfill({contentType: 'application/javascript', body: runtime});
      }
      if (requestUrl.pathname === '/lixity/assets/analytics.json') {
        if (holdConfig) await configGate;
        return route.fulfill({status: configStatus, contentType: 'application/json',
          body: brokenJson ? '{broken' : JSON.stringify(config)});
      }
      if (request.isNavigationRequest()) return route.fulfill({contentType: 'text/html', body: fixture});
      unexpected.push(request.url());
      return route.abort();
    });
    await page.goto(url, {referer: 'https://ref.example/private?secret=HIDDEN', waitUntil: 'domcontentloaded'});
    await expect(page.locator('h1')).toHaveText('Public synthetic guide');
    // Observe cancellation after the analytics listener, then retain this page
    // so several independent native CTA clicks can be inspected in one context.
    await page.evaluate(() => {
      window.__navigationPrevented = [];
      window.addEventListener('click', event => {
        window.__navigationPrevented.push(event.defaultPrevented);
        event.preventDefault();
      });
    });
    return {context, page, requests, pixels, unexpected, warnings, errors, releasePixels, releaseConfig};
  }
  function payloads(state) {
    return state.pixels.map(({url, headers, method}) => {
      assert.equal(method, 'GET');
      assert.equal(headers.referer, undefined, 'Pixels send no HTTP Referer header');
      assert.deepEqual([...url.searchParams.keys()].sort(), ['e', 'p', 'r', 'rnd', 't']);
      assert.match(url.searchParams.get('rnd'), /^[a-z0-9]+$/);
      assert.ok(!/SECRET|PRIVATE|HIDDEN|MANUSCRIPT|selection/.test(url.href));
      const {rnd, ...data} = Object.fromEntries(url.searchParams);
      return data;
    });
  }
  async function actualDemo(width) {
    const context = await browser.newContext({viewport: {width, height: 1000}, acceptDownloads: true});
    const page = await context.newPage();
    const pixels = [], requests = [], unexpected = [], errors = [], warnings = [];
    await context.addInitScript(() => {
      window.__cspViolations = [];
      document.addEventListener('securitypolicyviolation', event => {
        window.__cspViolations.push({directive: event.effectiveDirective, blocked: event.blockedURI});
      });
    });
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'warning') warnings.push(message.text()); });
    page.on('request', request => requests.push({url: request.url(), method: request.method()}));
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin === pixelOrigin && url.pathname === '/count') {
        pixels.push({url, headers: request.headers(), method: request.method()});
        return route.fulfill({contentType: 'image/gif', body: gif});
      }
      if (url.origin === publicOrigin && url.pathname.startsWith('/lixity/')) {
        const relative = decodeURIComponent(url.pathname.slice('/lixity/'.length)) || 'index.html';
        const docs = path.join(root, 'docs');
        let file = path.resolve(docs, relative);
        // Pages stages these canonical shared styles from the packaged UI.
        if (['assets/design-tokens.css', 'assets/components.css'].includes(relative)) {
          file = path.join(root, 'src/lixity/ui', relative);
        } else if (!file.startsWith(docs + path.sep)) return route.abort();
        if (fs.existsSync(file) && fs.statSync(file).isFile()) {
          // Simulate a slow public configuration response so the journey must
          // wait for the installation page's analytics before navigating away.
          if (relative === 'assets/analytics.json') await new Promise(resolve => setTimeout(resolve, 500));
          const contentType = {'.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
            '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png',
            '.jpg': 'image/jpeg', '.pdf': 'application/pdf', '.md': 'text/markdown'}[path.extname(file)];
          return route.fulfill({contentType: contentType || 'application/octet-stream', body: fs.readFileSync(file)});
        }
      }
      unexpected.push(request.url());
      return route.abort();
    });
    try {
      await page.goto(publicOrigin + '/lixity/demo/report.html?private=SECRET', {waitUntil: 'domcontentloaded'});
      await expect(page).toHaveTitle('Lixity project demo — The Crate at Warehouse 4');
      await expect(page.locator('.demo-context')).toContainText('Read-only demo');
      try { await expect.poll(() => pixels.length).toBe(1); }
      catch (error) {
        console.error('Actual generated demo CSP violations:', await page.evaluate(() => window.__cspViolations));
        console.error('Actual generated demo analytics warnings:', warnings);
        throw error;
      }
      assert.ok(requests.some(request => request.url.endsWith('/assets/analytics.js')),
        'The actual generated CSP permits the owned analytics runtime');
      assert.deepEqual(payloads({pixels}), [{p: '/lixity/demo/report.html',
        t: 'Lixity project demo — The Crate at Warehouse 4', r: '', e: 'false'}]);
      const sourceState = () => page.locator('#chapters .ptext').evaluateAll(panels => panels.map(panel => ({
        id: panel.id, start: panel.dataset.start, end: panel.dataset.end, hash: panel.dataset.paragraphSha256,
        text: panel.querySelector('.ptext-inner > p').textContent,
      })));
      const prose = await sourceState();
      await page.locator('#manuscript-analysis-toggle').click();
      await page.locator('#manuscript-analysis-toggle').click();
      assert.deepEqual(await sourceState(), prose, 'Analysis changes controls, never canonical prose or source anchors');
      await expect(page.locator('#r-claim-create-btn')).toBeHidden();
      await expect(page.locator('meta[http-equiv="Content-Security-Policy"]')).toHaveCount(1);
      assert.equal(requests.some(request => request.url.endsWith('/assets/analytics.json')), false,
        'The public website uses reviewed inline analytics configuration without opening its read-only transport');
      // Native anchor downloads bypass Playwright routing in Chromium. The
      // public-docs suite checks exact PDF bytes against its local HTTP server;
      // this public-origin fixture checks the CTA event without live traffic.
      for (const [index, layout] of ['book', 'document'].entries()) {
        const pdfLink = page.locator(`#demo-downloads a[href="warehouse-4-${layout}.pdf"]`);
        await expect(pdfLink).toHaveAttribute('download', '');
        await page.evaluate(() => document.addEventListener('click', event => {
          if (event.target.closest('#demo-downloads a')) event.preventDefault();
        }, {once: true}));
        await pdfLink.click();
        await expect.poll(() => pixels.filter(pixel => pixel.url.searchParams.get('p') === 'pdf-download').length).toBe(index + 1);
      }
      assert.deepEqual(await page.evaluate(() => window.__cspViolations), []);
      await page.screenshot({path: path.join(artifacts, `native-demo-${width}.png`), fullPage: false});
      await page.locator('#example-context > summary').click();
      await page.locator('#example-context a[href="../guides/installation.html"]').click();
      await page.waitForURL(publicOrigin + '/lixity/guides/installation.html');
      await expect.poll(() => pixels.filter(pixel => pixel.url.searchParams.get('p') === 'install-open').length).toBe(1);
      await expect.poll(() => pixels.filter(pixel => pixel.url.searchParams.get('p') === '/lixity/guides/installation.html').length,
        {message: 'The destination finishes loading its analytics configuration before the next navigation'}).toBe(1);
      assert.equal(pixels.filter(pixel => pixel.url.searchParams.get('p') === '/lixity/demo/report.html').length, 1);
      await page.goto(publicOrigin + '/lixity/', {waitUntil: 'domcontentloaded'});
      await expect.poll(() => pixels.filter(pixel => pixel.url.searchParams.get('p') === '/lixity/').length).toBe(1);
      await page.locator('.site-return a[href="#installation"]').click();
      await expect.poll(() => pixels.filter(pixel => pixel.url.searchParams.get('p') === 'install-open').length,
        {message: 'The current landing-page Install section link records one installation event'}).toBe(2);
      await expect(page.locator('#installation')).toBeInViewport();
      await page.screenshot({path: path.join(artifacts, `landing-install-${width}.png`), fullPage: false});
      payloads({pixels});
      assert.deepEqual(await page.evaluate(() => window.__cspViolations), []);
      assert.deepEqual(requests.filter(request => request.method !== 'GET'), [], 'Public demo interactions make no server writes');
      assert.deepEqual(unexpected, []);
      assert.deepEqual(errors, []);
      assert.deepEqual(warnings, []);
    } finally { await context.close(); }
  }
  async function settle(page) { await page.waitForTimeout(80); }
  try {
    for (const width of [1440, 320]) await actualDemo(width);
    for (const width of [1440, 320]) {
      const state = await open({width});
      const {page} = state;
      await expect.poll(() => state.pixels.length).toBe(1);
      assert.deepEqual(payloads(state), [{p: '/lixity/guides/first-look.html',
        t: 'Lixity public guide', r: 'https://ref.example', e: 'false'}]);
      await page.locator('textarea').fill('NEVER SEND THIS SELECTED MANUSCRIPT');
      await page.locator('textarea').press('ControlOrMeta+A');
      await page.evaluate(() => document.dispatchEvent(new CustomEvent('lixity:public-pdf-download', {
        detail: {filename: 'PRIVATE MANUSCRIPT', layout: 'SECRET'},
      })));
      await settle(page);
      assert.equal(state.pixels.length, 1, 'The public demo completion event is ignored on other pages');
      const clicks = ['demo', 'install', 'repository', 'pdf', 'untracked', 'spoof', 'demo',
        'install-reference', 'install-anchor', 'pdf-editor', 'pdf-sheet', 'pdf-report', 'pdf-document', 'other-pdf'];
      for (const id of clicks) await page.locator('#' + id).click();
      await expect.poll(() => state.pixels.length).toBe(12);
      assert.deepEqual(payloads(state).slice(1), [
        {p: 'demo-open', e: 'true', t: 'Open demo', r: ''},
        {p: 'install-open', e: 'true', t: 'Open installation', r: ''},
        {p: 'repository-open', e: 'true', t: 'Open repository', r: ''},
        {p: 'pdf-download', e: 'true', t: 'Download PDF', r: ''},
        {p: 'demo-open', e: 'true', t: 'Open demo', r: ''},
        {p: 'install-open', e: 'true', t: 'Open installation', r: ''},
        {p: 'install-open', e: 'true', t: 'Open installation', r: ''},
        ...Array.from({length: 4}, () => ({p: 'pdf-download', e: 'true', t: 'Download PDF', r: ''})),
      ]);
      assert.deepEqual(await page.evaluate(() => window.__navigationPrevented), Array(clicks.length).fill(false));
      await page.addScriptTag({url: publicOrigin + '/lixity/assets/analytics.js'});
      await settle(page);
      assert.equal(state.pixels.length, 12, 'Duplicate inclusion cannot add a pageview or event listener');
      assert.deepEqual(state.unexpected, []);
      assert.deepEqual(state.warnings, []);
      assert.deepEqual(state.errors, []);
      await state.context.close();
    }
    for (const options of [
      {config: {site_code: null}}, {url: 'http://127.0.0.1:8765/lixity/demo/report.html'},
      {url: 'https://example.test/lixity/demo/report.html'}, {url: publicOrigin + '/other/report.html'},
      {url: publicOrigin + '/lixity-other/report.html'}, {privacy: {doNotTrack: '1'}},
      {privacy: {doNotTrack: 'yes'}}, {privacy: {globalPrivacyControl: true}},
    ]) {
      const state = await open(options);
      await state.page.locator('#demo').click();
      await settle(state.page);
      assert.equal(state.pixels.length, 0);
      if (options.url || options.privacy) assert.equal(state.requests.some(url => url.endsWith('/analytics.json')), false);
      assert.deepEqual(state.unexpected, []);
      assert.deepEqual(state.warnings, []);
      assert.deepEqual(state.errors, []);
      await state.context.close();
    }
    for (const options of [
      {config: {site_code: 'bad.example/secret'}}, {config: {site_code: '-bad'}},
      {config: {site_code: 'A'.repeat(64)}}, {config: []}, {config: {}},
      {configStatus: 404}, {brokenJson: true}, {pixelFailure: true},
    ]) {
      const state = await open(options);
      await expect.poll(() => state.warnings.length).toBe(1);
      await state.page.locator('#demo').click();
      await state.page.locator('#install').click();
      await settle(state.page);
      assert.equal(state.pixels.length, options.pixelFailure ? 3 : 0);
      assert.equal(state.warnings.length, 1);
      assert.deepEqual(state.unexpected, []);
      assert.deepEqual(state.errors, []);
      assert.deepEqual(await state.page.evaluate(() => window.__navigationPrevented), [false, false]);
      await state.context.close();
    }
    const pending = await open({holdPixels: true});
    await expect.poll(() => pending.pixels.length).toBe(1);
    for (let index = 0; index < 25; index++) await pending.page.locator('#demo').click();
    assert.equal(pending.pixels.length, 20, 'Unsettled Image references are bounded');
    assert.equal(pending.warnings.length, 1);
    payloads(pending);
    pending.releasePixels();
    await pending.page.waitForLoadState('networkidle');
    await pending.page.locator('#demo').click();
    await expect.poll(() => pending.pixels.length).toBe(21);
    assert.deepEqual(pending.errors, []);
    await pending.context.close();
    const configuring = await open({holdConfig: true});
    await configuring.page.locator('#demo').click();
    assert.equal(configuring.pixels.length, 0, 'Unknown configuration collects nothing');
    configuring.releaseConfig();
    await expect.poll(() => configuring.pixels.length).toBe(1);
    await settle(configuring.page);
    assert.equal(configuring.pixels.length, 1, 'Clicks before activation are not queued or replayed');
    await configuring.context.close();
    assert.deepEqual(JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../docs/assets/analytics.json'), 'utf8')),
      {site_code: 'mfahsold'}, 'Only the explicitly selected hosted property is activated');
    console.log('Pages analytics: actual generated demo/CSP/PDF CTA and installation journeys; pixel payloads, gates, errors and bounded images passed. No backend hit sent. Screenshots: ' + artifacts);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
