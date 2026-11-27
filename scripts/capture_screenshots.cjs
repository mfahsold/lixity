const {selectMetric} = require('../tests/browser/support/analysis-controls.cjs');
const {launchChromium, playwrightModule} = require('./browser_tools.cjs');
const {anchoredFrames, digest, recordProductTour, shotAnchor} = require('./product_tour_capture.cjs');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
// Loopback is a trustworthy context for Web Crypto, just like the native app.
// Every request to this synthetic origin is intercepted; no server is contacted.
const CAPTURE_ORIGIN = 'http://localhost:41737';

async function main() {
  const captures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await launchChromium();
  let guideBrowser = null;
  const results = [];
  try {
    const fixturePath = path.join(path.dirname(captures[0].source), 'research-workspace-fixture.json');
    const researchFixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
    // Intercept a synthetic origin so embedded exact-version images use the same
    // resource URLs as the native app without contacting a running server.
    async function prepareWorkspacePage(target, {cursor = false, fixtures = true} = {}) {
    if (fixtures) {
    // Published map captures show real OSM tiles, with their native attribution.
    // Load only the normal visible viewport; regression suites stub tile bytes.
    await target.route('https://tile.openstreetmap.org/**', async route => {
      const url = new URL(route.request().url());
      assert.equal(route.request().method(), 'GET');
      assert.match(url.pathname, /^\/\d+\/\d+\/\d+\.png$/);
      assert.equal(url.search, '');
      await route.continue();
    });
    await target.route(CAPTURE_ORIGIN + '/**', async route => {
      const url = new URL(route.request().url());
      if (['/assets/design-tokens.css', '/assets/components.css'].includes(url.pathname)) {
        const asset = path.join(__dirname, '..', 'src', 'lixity', 'ui', 'assets', path.basename(url.pathname));
        await route.fulfill({status: 200, contentType: 'text/css; charset=utf-8', body: fs.readFileSync(asset)});
        return;
      }
      const resource = researchFixture[url.pathname + url.search];
      if (['/api/research/image', '/api/research/media'].includes(url.pathname) && resource && resource.asset_path) {
        assert.equal(route.request().method(), 'GET');
        assert.ok(['docs/assets/research/hamburg-free-port-1900.jpg',
          'docs/assets/research/hamburg-harbour-1890-1900.jpg',
          'docs/assets/research/warehouse-4-receipt.png',
          'docs/assets/research/warehouse-4-ledger.png',
          'docs/assets/research/warehouse-4-watchman.mp4'].includes(resource.asset_path));
        await route.fulfill({status: 200, contentType: resource.media_type,
          body: fs.readFileSync(path.join(__dirname, '..', resource.asset_path))});
        return;
      }
      if (url.pathname === '/api/manuscript-delta') {
        await route.fulfill({status: 200, contentType: 'application/json',
          body: JSON.stringify({ok: true, available: false, snapshot: null, delta: null})});
        return;
      }
      if (url.pathname === '/api/manuscript-timeline') {
        await route.fulfill({status: 200, contentType: 'application/json',
          body: JSON.stringify({ok: true, snapshots: [], items: []})});
        return;
      }
      const matchedSource = captures.map(item => item.source).find(src => '/' + path.basename(src) === url.pathname);
      assert.ok(matchedSource, 'Unknown screenshot resource: ' + url.pathname);
      await route.fulfill({status: 200, contentType: 'text/html; charset=utf-8',
        body: fs.readFileSync(matchedSource)});
    });
    await target.addInitScript(({fixture}) => {
      const origFetch = window.fetch.bind(window);
      window.captureRequests = [];
      window.fetch = (input, options) => {
        const url = typeof input === 'string' ? input : input.url;
        if (url.includes('/api/manuscript')) return origFetch(input, options);
        const method = (options && options.method) || 'GET';
        window.captureRequests.push({url, method});
        if (!Object.prototype.hasOwnProperty.call(fixture, url)) {
          throw new Error('Missing screenshot API fixture: ' + url);
        }
        if (method !== 'GET' && url !== '/api/research-search') {
          throw new Error('Screenshot capture cannot mutate a project: ' + method + ' ' + url);
        }
        if (url === '/api/research-search') {
          const query = JSON.parse(options.body);
          if (query.query !== 'warehouse customs' || query.scope !== 'sources') {
            throw new Error('Screenshot search must match the generated API result');
          }
        }
        const result = fixture[url];
        if (new URL(url, location.href).pathname === '/api/analysis-review') {
          const query = new URL(url, location.href).searchParams;
          if ([...query.keys()].length !== 1 || query.get('project_token') !== document.body.dataset.manuscriptProjectToken ||
              result.source_sha256 !== document.body.dataset.manuscriptSourceSha256) {
            throw new Error('Capture review fixture must match the displayed manuscript context');
          }
        }
        return Promise.resolve(new Response(JSON.stringify(result), {
          status: 200,
          headers: {'Content-Type': 'application/json'},
        }));
      };
    }, {fixture: researchFixture});
    }
    if (cursor) {
      await target.addInitScript(() => {
        const attach = () => {
          const dot = document.createElement('div');
          dot.id = 'walkthrough-cursor';
          dot.style.cssText = 'position:fixed;left:-40px;top:-40px;width:22px;height:22px;margin:-11px 0 0 -11px;' +
            'border-radius:50%;background:rgba(37,99,235,.30);border:2px solid rgba(37,99,235,.85);' +
            'box-shadow:0 0 0 3px rgba(37,99,235,.15);z-index:2147483647;pointer-events:none;opacity:0;';
          document.body.appendChild(dot);
          window.addEventListener('mousemove', event => {
            dot.style.opacity = '1';
            dot.style.left = event.clientX + 'px';
            dot.style.top = event.clientY + 'px';
          }, {passive: true});
          window.addEventListener('mousedown', () => { dot.style.transform = 'scale(.72)'; }, {passive: true});
          window.addEventListener('mouseup', () => { dot.style.transform = 'scale(1)'; }, {passive: true});
          const caption = document.createElement('div');
          caption.id = 'walkthrough-caption';
          caption.style.cssText = 'position:fixed;left:50%;bottom:32px;transform:translateX(-50%);max-width:82%;' +
            'padding:12px 24px;border-radius:12px;background:rgba(15,23,42,.92);color:#f8fafc;' +
            'font:600 16px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;letter-spacing:.015em;text-align:center;' +
            'border:1px solid rgba(255,255,255,.15);box-shadow:0 12px 32px rgba(0,0,0,.35);' +
            'backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);' +
            'z-index:2147483647;pointer-events:none;opacity:0;transition:opacity .25s ease,transform .25s ease;';
          document.body.appendChild(caption);
          let hideTimer = null;
          window.setWalkthroughCaption = text => {
            if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
            if (text) {
              caption.textContent = text;
              caption.style.opacity = '1';
            } else {
              caption.style.opacity = '0';
              hideTimer = setTimeout(() => {
                if (caption.style.opacity === '0') caption.textContent = '';
                hideTimer = null;
              }, 280);
            }
          };
        };
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', attach);
        else attach();
      });
    }
    }
    const page = await browser.newPage({deviceScaleFactor: 2, reducedMotion: 'reduce'});
    await prepareWorkspacePage(page);
    page.setDefaultTimeout(10000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    async function settle() {
      await page.evaluate(() => document.fonts.ready);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    }
    async function open(source, width, height, colorScheme = 'light') {
      if (page.url().startsWith(CAPTURE_ORIGIN)) await page.evaluate(() => localStorage.clear());
      await page.setViewportSize({width, height});
      await page.emulateMedia({colorScheme});
      await page.goto(CAPTURE_ORIGIN + '/' + path.basename(source));
      assert.ok(await page.evaluate(() => isSecureContext && !!globalThis.crypto?.subtle),
        'Screenshot origin must support native text-identity verification');
      await settle();
      assert.ok((await page.title()).length || await page.locator('body').innerText(), 'Capture document is not blank');
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Capture page must not overflow horizontally');
    }
    async function selectView(view) {
      const tab = page.locator(`[data-view="${view}"]`);
      if (await tab.count()) await tab.click();
    }
    async function openProjectActions() {
      const disclosure = page.locator('#project-actions');
      if (await disclosure.count() && !await disclosure.evaluate(node => node.open)) {
        await disclosure.locator(':scope > summary').click();
      }
    }
    async function selectManuscript() {
      await openProjectActions();
      await page.locator('#btn-modal-new-project').click();
      await page.locator('#modal-project-create').waitFor({state: 'visible'});
      await page.locator('#import-file-input').setInputFiles({
        name: 'warehouse-4.md', mimeType: 'text/markdown',
        buffer: fs.readFileSync(path.join(__dirname, '..', 'samples', 'first-look.md')),
      });
      await page.locator('#import-preview-box').waitFor({state: 'visible'});
      assert.equal(await page.locator('#btn-submit-import-project').isEnabled(), true);
    }
    async function captureThrough(capture, selector, lastSelector, {firstSelector = null} = {}) {
      const last = typeof lastSelector === 'string' ? page.locator(lastSelector) : lastSelector;
      await last.waitFor({state: 'visible'});
      await settle();
      const bounds = await last.evaluate((last, options) => {
        const {selector, firstSelector} = options;
        const target = document.querySelector(selector);
        const targetBox = target.getBoundingClientRect();
        const first = firstSelector ? document.querySelector(firstSelector) : null;
        const top = first ? Math.max(0, first.getBoundingClientRect().top - targetBox.top - 12) : 0;
        const lastBox = last.getBoundingClientRect();
        // End in the space after this task, never through the next item.
        let bottom = lastBox.bottom + 16;
        let next = last.nextElementSibling;
        while (next && !next.getClientRects().length) next = next.nextElementSibling;
        if (next) bottom = Math.min(bottom, (lastBox.bottom + next.getBoundingClientRect().top) / 2);
        return {top, height: bottom - targetBox.top - top,
          lastBottom: lastBox.bottom - targetBox.top, targetHeight: targetBox.height};
      }, {selector, firstSelector});
      assert.ok(bounds.top + bounds.height >= bounds.lastBottom && bounds.targetHeight >= bounds.lastBottom,
        'Capture must retain the complete final task element');
      capture.topOffset = Math.floor(bounds.top);
      capture.maxHeight = Math.ceil(bounds.height);
    }
    async function save(target, selector, {visibleMap = false} = {}) {
      await settle();
      await page.mouse.move(0, 0);
      if (await page.locator('#lixity-tooltip.visible').count()) await page.keyboard.press('Escape');
      if (await page.locator('#lixity-tooltip').count()) await page.locator('#lixity-tooltip').waitFor({state: 'hidden'});
      // Start component framing from the document origin so a toolbar made
      // sticky by an earlier interaction cannot float over the clipped task.
      if (visibleMap) {
        await page.locator(selector).evaluate(node => {
          const toolbar = document.querySelector('.toolbar');
          const inset = toolbar ? toolbar.getBoundingClientRect().height : 0;
          window.scrollTo({top: scrollY + node.getBoundingClientRect().top - inset - 16, behavior: 'instant'});
        });
      } else await page.evaluate(() => window.scrollTo({top: 0, behavior: 'instant'}));
      await settle();
      const job = captures.find(item => item.target === target) || {};
      const options = {path: target, animations: 'disabled'};
      if (selector) {
        const element = page.locator(selector);
        const clip = await element.evaluate(node => {
          const rect = node.getBoundingClientRect();
          return {x: rect.x + scrollX, y: rect.y + scrollY, width: rect.width, height: rect.height};
        });
        if (job.topOffset) {
          clip.y += job.topOffset;
          clip.height -= job.topOffset;
        }
        // Explicit excerpts end at a complete task boundary supplied by the
        // capture definition. Do not reshape native widgets to fit a camera.
        if (job.maxHeight) clip.height = Math.min(clip.height, job.maxHeight);
        assert.ok(clip.width > 0 && clip.height > 0, `Capture target ${selector} must have a visible task boundary`);
        if (visibleMap) {
          const map = element.locator('.geography-map.leaflet-container');
          assert.ok(await map.evaluate(node => {
            const rect = node.getBoundingClientRect();
            return rect.top < innerHeight && rect.bottom > 0;
          }), 'The native map must remain in the visible viewport during capture');
          await map.locator('.leaflet-tile-loaded').first().waitFor();
          await map.locator('.leaflet-tile-container img').evaluateAll(images => Promise.all(images.map(image => image.decode())));
          assert.match(await map.locator('.leaflet-control-attribution').innerText(), /OpenStreetMap/,
            'The final map frame must preserve native basemap attribution');
        }
        await page.screenshot({...options, fullPage: true, clip});
      } else await page.screenshot(options);
      assert.deepEqual(errors, [], 'Screenshots must be free of runtime and console errors');
      const bytes = fs.readFileSync(target);
      results.push({file: path.basename(target), width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20)});
    }
    async function alignHeatmapExcerpt() {
      // Keep the real horizontal scrollport and all measurements intact. Size
      // the browser window so this excerpt ends at a complete feature column.
      const geometry = () => page.locator('#heatmap').evaluate(panel => {
        const wrapper = panel.querySelector('.heatmap-wrap');
        const bounds = wrapper.getBoundingClientRect();
        const columns = Array.from(wrapper.querySelectorAll('thead th')).map(cell => {
          const rect = cell.getBoundingClientRect();
          return {left: rect.left - bounds.left, right: rect.right - bounds.left};
        });
        const visible = columns.filter(column => column.right <= bounds.width - 2);
        return {width: bounds.width, last: visible.at(-1), next: columns[visible.length]};
      });
      const before = await geometry();
      assert.ok(before.last && before.next, 'Heatmap capture must show a meaningful horizontal excerpt');
      const excess = Math.max(0, Math.floor(before.width - before.last.right - 2));
      if (excess) {
        const size = page.viewportSize();
        await page.setViewportSize({width: size.width - excess, height: size.height});
        await settle();
      }
      const after = await geometry();
      assert.ok(after.last && after.next && after.last.right <= after.width - 1 &&
        after.next.left >= after.width - 2,
      `Heatmap excerpt must end at a full column boundary: ${JSON.stringify(after)}`);
    }
    async function saveDialog(target, selector) {
      const dialog = page.locator(selector);
      // Keep the real modal's bounded scrolling and show its confirmation
      // state, with the native header and Close control still reachable.
      const footer = dialog.locator('.modal-footer:visible').last();
      if (await footer.count()) await footer.scrollIntoViewIfNeeded();
      const close = dialog.locator('.modal-close');
      assert.ok(await close.isVisible(), 'Native dialog Close control must remain visible');
      const bounds = await dialog.boundingBox();
      for (const control of [close, ...(await footer.count() ? await footer.locator('button:visible').all() : [])]) {
        const button = await control.boundingBox();
        assert.ok(button && button.y >= bounds.y && button.y + button.height <= bounds.y + bounds.height + 1,
          'Native dialog header and confirmation actions must fit the capture');
      }
      await save(target, selector);
    }
    for (const capture of captures.filter(item => !item.video)) {
      const name = path.basename(capture.target);
      await open(capture.source, capture.width, capture.height, name.includes('dark') ? 'dark' : 'light');
      if (await page.locator('#manuscript-analysis-toggle').count()) {
        await selectView('analysis');
        if (name === 'dashboard-heatmap.png') await page.locator('#workbench-overview-open').click();
        else if (name === 'dashboard-editorial.png') await page.locator('#manuscript-analysis-toggle').click();
      }
      if (name.startsWith('dashboard-reader-focus')) {
        await selectView('analysis');
        assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'false');
        await page.locator('#reader-settings > summary').click();
        await page.locator('#reader-text-larger').click();
        await page.locator('#reader-settings > summary').click();
        await captureThrough(capture, '#workspace-reader', page.locator('#ch-1 .ptext').nth(1));
        await save(capture.target, '#workspace-reader');
      } else if (name.startsWith('dashboard-measurement-focus')) {
        await selectView('analysis');
        await page.locator('#manuscript-analysis-toggle').click();
        await selectMetric(page, 'asl');
        const paragraph = page.locator('#ch-2 .ptext').first();
        await paragraph.scrollIntoViewIfNeeded();
        await paragraph.locator('[data-reader-paragraph]').click();
        await page.locator('[data-reader-action=values]').click();
        await page.locator('#reader-inspector [data-reader-evidence-paragraph]').click();
        const card = page.locator('#analysis-evidence-card');
        await card.waitFor({state: 'visible'});
        await page.mouse.move(0, 0);
        // Opening the card focuses Close and can show its shortcut tooltip.
        await card.locator('.analysis-evidence-close').blur();
        await page.locator('#lixity-tooltip.visible').waitFor({state: 'hidden'});
        await settle();
        await card.screenshot({path: capture.target, animations: 'disabled'});
        assert.deepEqual(errors, [], 'Screenshots must be free of runtime and console errors');
        const bytes = fs.readFileSync(capture.target);
        results.push({file:name,width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20)});
      } else if (name === 'dashboard-mobile.png') {
        // Finish after the first complete paragraph instead of cutting a line
        // of the next paragraph at an arbitrary viewport height.
        const paragraphs = page.locator('#ch-1 .ptext');
        const end = await paragraphs.nth(0).evaluate(first => {
          const second = first.nextElementSibling;
          const bottom = first.getBoundingClientRect().bottom + scrollY;
          return Math.floor(second ? Math.min(bottom + 20, (bottom + second.getBoundingClientRect().top + scrollY) / 2) : bottom + 20);
        });
        await page.setViewportSize({width: capture.width, height: end});
        assert.ok(await paragraphs.first().evaluate(node => node.getBoundingClientRect().bottom <= innerHeight),
          'Mobile capture must contain the complete first paragraph');
        if (await paragraphs.count() > 1) {
          assert.ok(await paragraphs.nth(1).evaluate(node => node.getBoundingClientRect().top >= innerHeight),
            'Mobile capture must not clip the next paragraph');
        }
        await save(capture.target);
      } else if (name === 'dashboard-light.png' || name === 'dashboard-dark.png') {
        // A complete opening chapter makes the entrance image a coherent
        // reading task. Use a real viewport; preserve the native shell.
        const bottom = await page.locator('#ch-1 .ptext').last().evaluate(node => node.getBoundingClientRect().bottom + scrollY);
        assert.ok(bottom < 1400, 'Reader entrance must remain a compact opening chapter');
        await page.setViewportSize({width: capture.width, height: Math.ceil(bottom + 32)});
        await save(capture.target);
      } else if (name === 'dashboard-editorial.png') {
        await selectView('analysis');
        const paragraph = page.locator('#ch-1 .ptext').first();
        await paragraph.locator('[data-reader-paragraph]').click();
        await page.locator('[data-reader-action=values]').click();
        await paragraph.locator('[data-reader-paragraph]').click();
        await page.locator('[data-reader-action=todo]').click();
        await paragraph.locator('.marker-note').fill('Check the gate observation');
        await captureThrough(capture, '#ch-1', paragraph);
        await save(capture.target, '#ch-1');
      } else if (name.startsWith('dashboard-heatmap')) {
        await page.locator('[data-analysis-workflow=compare]').click();
        await page.locator('[data-analysis-section-target=style]').click();
        await page.evaluate(() => {
          const rows = document.querySelectorAll('table.heatmap tbody tr');
          for (let i = 20; i < rows.length; i++) rows[i].remove();
        });
        await alignHeatmapExcerpt();
        await save(capture.target, '#heatmap');
      } else if (name.startsWith('dashboard-project-settings')) {
        await selectView('project');
        await selectManuscript();
        await page.locator('#modal-project-create').waitFor({state: 'visible'});
        await page.locator('#modal-project-create .modal-close').click();
        await page.locator('#modal-project-create').waitFor({state: 'hidden'});
        assert.equal(await page.locator('#set-author-name').isVisible(), true);
        assert.equal(await page.locator('#nda-draft-form input, #nda-draft-form textarea').count(), 5);
        await page.locator('#settings-registers > summary').click();
        // Show a real unsaved example through the same editor authors use.
        const requestsBeforeDraft = await page.evaluate(() => captureRequests.length);
        await page.locator('[data-register-add-profile]').click();
        const profile = page.locator('[data-register-profile]').last();
        await profile.locator('[data-register-field=register_name]').fill('Chapter contrast');
        await profile.locator('[data-register-add-target]').click();
        await profile.locator('[data-register-field=register_target]').selectOption('asl');
        await profile.locator('[data-register-field=register_lower]').fill('8');
        await profile.locator('[data-register-field=register_upper]').fill('15');
        await page.locator('[data-register-add-assignment]').click();
        const assignment = page.locator('[data-register-assignment]').last();
        await assignment.locator('[data-register-field=register_selector]').fill('2');
        await assignment.locator('[data-register-field=register_name]').fill('Chapter contrast');
        assert.equal(await page.evaluate(() => captureRequests.length), requestsBeforeDraft,
          'Framing a register draft must not save project settings');
        await captureThrough(capture, '#controls', '#settings-form > .settings-actions',
          {firstSelector: '#settings-registers'});
        await save(capture.target, '#controls');
      } else if (name.startsWith('dashboard-project-import')) {
        await selectView('project');
        await selectManuscript();
        await page.locator('#import-preview-box').waitFor({state: 'visible'});
        assert.equal(await page.locator('#btn-submit-import-project').isEnabled(), true);
        await saveDialog(capture.target, '#modal-project-create');
      } else if (name.startsWith('dashboard-research-review')) {
        await selectView('research');
        await page.locator('[data-rtab="review"]').click();
        await page.locator('#research-editorial-review .research-card').first().waitFor();
        await page.locator('#research-manuscript-review .manuscript-link-review-item').first().waitFor();
        await save(capture.target, '#research-manuscript-review-section');
      } else if (name.startsWith('dashboard-research-timeline')) {
        await selectView('research');
        await page.locator('[data-rtab="claims"]').click();
        await page.locator('#r-open-timeline').click();
        await page.waitForFunction(() => document.querySelector('#research-claims-timeline .research-timeline-strip-row'));
        await save(capture.target, '#research-claims-timeline');
      } else if (name.startsWith('dashboard-research-claims')) {
        await selectView('research');
        await page.locator('[data-rtab="claims"]').click();
        await page.locator('#research-claims-list .research-card').first().waitFor();
        await page.locator('[data-load-evidence]').first().click();
        await page.locator('.claim-evidence-subpanel .research-passage-quote').first().waitFor();
        await captureThrough(capture, '#research-manager', '#research-claims-list .research-card:first-child');
        await save(capture.target, '#research-manager');
      } else if (name.startsWith('dashboard-research-decisions')) {
        await selectView('research');
        await page.locator('[data-rtab="decisions"]').click();
        await page.locator('#research-decisions-list .research-card').first().waitFor();
        await captureThrough(capture, '#research-manager', '#research-decisions-list .research-card:first-child');
        await save(capture.target, '#research-manager');
      } else if (name.startsWith('dashboard-research-dossiers') || name.startsWith('dashboard-dossier-')) {
        await selectView('research');
        await page.locator('[data-rtab="dossiers"]').click();
        await page.locator('#research-dossiers-list .research-card').first().waitFor();
        await settle();
        const before = await page.evaluate(() => captureRequests.length);
        await page.locator('#r-filter-dossiers').fill('warehouse');
        assert.equal(await page.evaluate(() => captureRequests.length), before, 'List filtering is local');
        const card = page.locator('#research-dossiers-list .research-card:visible').filter({hasText: 'Warehouse 4 case notes'});
        await card.locator('[data-research-detail]').click();
        await card.locator('.research-details-body .research-prose').first().waitFor();
        for (const image of await card.locator('.dossier-image img').all()) {
          await image.scrollIntoViewIfNeeded();
          // A lazy image can change its active request when it enters the viewport.
          await page.waitForFunction(element => element.complete && element.naturalWidth > 0,
            await image.elementHandle());
          await image.evaluate(element => element.decode());
        }
        if (name.startsWith('dashboard-dossier-geography')) {
          const map = card.locator('.geography-map.leaflet-container');
          await map.waitFor();
          const before = await page.evaluate(() => captureRequests.length);
          await card.locator('.geography-feature-list button[data-geo-select="2"]').click();
          await card.locator('[data-geo-frame]').click();
          await card.locator('.geography-map.leaflet-container').waitFor();
          await card.locator('[data-geo-fit]').click();
          assert.match(await card.locator('.geography-selected').innerText(), /Night watchman/);
          await map.scrollIntoViewIfNeeded();
          assert.equal(await card.locator('[data-geo-basemap]').isChecked(), true);
          await map.locator('.leaflet-tile-loaded').first().waitFor();
          await map.locator('.leaflet-tile-container img').evaluateAll(images => Promise.all(images.map(image => image.decode())));
          assert.match(await map.locator('.leaflet-control-attribution').innerText(), /OpenStreetMap/);
          assert.equal(await page.evaluate(() => captureRequests.length), before,
            'Authored route selection and map framing require no further requests');
          await captureThrough(capture, '.research-details-body .dossier-geography', '.research-details-body .geography-method');
          await save(capture.target, '.research-details-body .dossier-geography', {visibleMap: true});
        } else if (name.startsWith('dashboard-dossier-diagram')) {
          const diagram = card.locator('[data-research-diagram]').first();
          await diagram.scrollIntoViewIfNeeded();
          await diagram.locator('svg.research-diagram').waitFor();
          await save(capture.target, '[data-research-diagram]');
        } else if (name.startsWith('dashboard-dossier-image-zoom')) {
          await card.locator('[data-dossier-enlarge]').first().click();
          await page.locator('#modal-dossier-image-enlarge .pswp__item[aria-hidden=false] img.pswp__img').waitFor();
          await save(capture.target, '#modal-dossier-image-enlarge');
        } else if (name.startsWith('dashboard-dossier-image') || name.startsWith('dashboard-dossier-photo')) {
          const alt = name.startsWith('dashboard-dossier-photo') ? "Hamburg's Hansahafen" : 'Historical coloured plan';
          const figure = card.locator('.dossier-image').filter({has: page.locator('img[alt*="' + alt + '"]')});
          await figure.scrollIntoViewIfNeeded();
          const provenance = figure.locator('.dossier-image-source-context');
          if (await provenance.count()) await provenance.locator('summary').click();
          await save(capture.target, '.dossier-image:has(img[alt*="' + alt + '"])');
        } else {
          await card.locator('[data-research-detail]').click();
          await captureThrough(capture, '#research-manager', card);
          await save(capture.target, '#research-manager');
        }
      } else if (name.startsWith('dashboard-research-search')) {
        await selectView('research');
        await page.locator('[data-rtab="search"]').click();
        await page.locator('#r-search-query').fill('warehouse customs');
        await page.locator('#r-search-scope').selectOption('sources');
        await page.locator('#r-search-btn').click();
        await page.locator('#research-search-results .research-passage-card').first().waitFor();
        await captureThrough(capture, '#research-manager', '#research-search-results .research-passage-card:first-child');
        await save(capture.target, '#research-manager');
      } else {
        await save(capture.target);
      }
    }
    const videoCaptures = captures.filter(item => item.video);
    if (videoCaptures.some(item => path.basename(item.videoTarget, '.webm') !== 'product-tour')) {
      const {chromium} = require(playwrightModule);
      guideBrowser = await chromium.launch({
        headless: true,
        args: ['--force-device-scale-factor=2', '--mute-audio'],
      });
    }
    await Promise.all(videoCaptures.map(async capture => {
      const flow = path.basename(capture.videoTarget, '.webm');
      if (flow === 'product-tour') {
        results.push(...await recordProductTour({browser, capture, prepareWorkspacePage}));
        return;
      }
      const videoScale = 2;
      const context = await guideBrowser.newContext({
        viewport: {width: capture.width, height: capture.height},
        recordVideo: {
          dir: path.dirname(capture.videoTarget),
          size: {width: capture.width * videoScale, height: capture.height * videoScale},
        },
        deviceScaleFactor: videoScale,
      });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
      await prepareWorkspacePage(page, {cursor: true});
      page.setDefaultTimeout(15000);
      let pointer = {x: Math.round(capture.width * 0.5), y: Math.round(capture.height * 0.45)};
      const settleFrame = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const readyCursor = async () => {
        await page.locator('#walkthrough-cursor').waitFor({state: 'attached'});
        await page.evaluate(() => {
          const cursor = document.getElementById('walkthrough-cursor');
          if (!cursor) return;
          cursor.style.transition = 'transform .12s ease, opacity .18s ease';
          if (typeof cursor.showPopover === 'function') {
            cursor.setAttribute('popover', 'manual');
            Object.assign(cursor.style, {right: 'auto', bottom: 'auto', padding: '0', overflow: 'visible'});
            if (!cursor.matches(':popover-open')) cursor.showPopover();
          }
        });
      };
      const moveTo = async (locator, {duration = null, point = null} = {}) => {
        await locator.scrollIntoViewIfNeeded();
        await settleFrame();
        const box = await locator.boundingBox();
        assert.ok(box && box.width && box.height, 'Walkthrough target must be visible before pointer movement');
        const destination = point || {x: box.x + box.width / 2, y: box.y + box.height / 2};
        await readyCursor();
        const dist = Math.hypot(destination.x - pointer.x, destination.y - pointer.y);
        const travelMs = duration ?? Math.min(520, Math.max(240, 220 + dist * 0.25));
        const started = Date.now();
        while (true) {
          const progress = Math.min(1, (Date.now() - started) / travelMs);
          const eased = (1 - Math.cos(Math.PI * progress)) / 2;
          await page.mouse.move(
            pointer.x + (destination.x - pointer.x) * eased,
            pointer.y + (destination.y - pointer.y) * eased,
          );
          if (progress >= 1) break;
          await page.waitForTimeout(16);
        }
        pointer = destination;
      };
      const smoothClick = async (locator, options = {}) => {
        await moveTo(locator, options);
        await page.waitForTimeout(80);
        await page.mouse.down();
        await page.waitForTimeout(110);
        await page.mouse.up();
      };
      const smoothHover = async (locator, holdMs = 550) => {
        await moveTo(locator);
        await page.waitForTimeout(holdMs);
      };
      const smoothSelect = async (locator, value) => {
        await moveTo(locator);
        await locator.focus();
        await page.evaluate(() => {
          const cursor = document.getElementById('walkthrough-cursor');
          if (cursor) cursor.style.transform = 'scale(.72)';
        });
        await page.waitForTimeout(110);
        await locator.selectOption(value);
        await page.evaluate(() => {
          const cursor = document.getElementById('walkthrough-cursor');
          if (cursor) cursor.style.transform = 'scale(1)';
        });
      };
      const smoothScrollBy = async (deltaY, steps = 10, totalMs = 400) => {
        const stepDelay = Math.max(16, Math.round(totalMs / steps));
        let applied = 0;
        for (let i = 1; i <= steps; i++) {
          const eased = (1 - Math.cos(Math.PI * (i / steps))) / 2;
          const target = deltaY * eased;
          await page.mouse.wheel(0, target - applied);
          applied = target;
          await page.waitForTimeout(stepDelay);
        }
      };
      const setCaption = async text => {
        await page.evaluate(value => {
          const caption = document.getElementById('walkthrough-caption');
          if (caption && value) {
            Object.assign(caption.style, {
              left: '50%', right: 'auto', top: 'auto', bottom: '28px', transform: 'translateX(-50%)',
            });
          }
          if (window.setWalkthroughCaption) window.setWalkthroughCaption(value);
        }, text);
      };
      const placeCaptionClear = async selector => {
        await page.locator(selector).evaluateAll(controls => {
          const caption = document.getElementById('walkthrough-caption');
          if (!caption) return;
          const visible = controls
            .map(control => control.getBoundingClientRect())
            .filter(rect => rect.width && rect.height);
          if (!visible.length) return;
          const candidates = [
            {left: '50%', right: 'auto', top: 'auto', bottom: '28px', transform: 'translateX(-50%)'},
            {left: '50%', right: 'auto', top: '12px', bottom: 'auto', transform: 'translateX(-50%)'},
            {left: '24px', right: 'auto', top: 'auto', bottom: '28px', transform: 'none'},
            {left: 'auto', right: '24px', top: 'auto', bottom: '28px', transform: 'none'},
            {left: 'auto', right: '24px', top: '12px', bottom: 'auto', transform: 'none'},
          ];
          const prevTransition = caption.style.transition;
          caption.style.transition = 'none';
          for (const candidate of candidates) {
            Object.assign(caption.style, candidate);
            const overlay = caption.getBoundingClientRect();
            const clear = visible.every(rect =>
              rect.right <= overlay.left || rect.left >= overlay.right ||
              rect.bottom <= overlay.top || rect.top >= overlay.bottom
            );
            if (clear) break;
          }
          void caption.offsetHeight;
          caption.style.transition = prevTransition;
        });
      };
      const withCaption = async (text, action, {leadMs = 420, holdMs = 1500, keep = false} = {}) => {
        await setCaption(text);
        await page.waitForTimeout(leadMs);
        await action();
        if (holdMs > 0) await page.waitForTimeout(holdMs);
        if (!keep) {
          await setCaption('');
          await page.waitForTimeout(280);
        }
      };
      const assertCaptionClear = async selector => {
        assert.ok(await page.locator(selector).evaluateAll(controls => {
          controls = controls.filter(control => { const rect = control.getBoundingClientRect(); return rect.width && rect.height; });
          if (!controls.length) return false;
          const caption = document.querySelector('#walkthrough-caption');
          if (!caption || getComputedStyle(caption).opacity === '0') return true;
          const overlay = caption.getBoundingClientRect();
          return controls.every(control => {
            const rect = control.getBoundingClientRect();
            return !rect.width || !rect.height || rect.right <= overlay.left || rect.left >= overlay.right ||
              rect.bottom <= overlay.top || rect.top >= overlay.bottom;
          });
        }), 'Walkthrough captions must not obscure task actions during interaction');
      };
      const assertReviewConfirmed = async () => {
        const total = await page.locator('#flags .flag-row').count();
        await page.waitForFunction(total => {
          const reload = document.getElementById('triage-reload');
          const status = document.getElementById('triage-save-status');
          const progress = document.getElementById('triage-progress');
          const rows = Array.from(document.querySelectorAll('#flags .flag-row'));
          return reload && reload.hidden && status && status.textContent === '' && progress &&
            progress.textContent.includes(uiFormat('triage_completed', {completed: 0, total})) &&
            rows.every(row => row.dataset.reviewState === 'unreviewed');
        }, total);
      };
      await page.goto(CAPTURE_ORIGIN + '/' + path.basename(capture.source));
      if (flow !== 'research-timeline' && await page.locator('#workbench-overview-open').count()) {
        await page.locator('#tab-view-analysis').click();
        if (flow === 'editorial-loop') await page.locator('#workbench-overview-open').click();
      }
      if (flow === 'editorial-loop') await assertReviewConfirmed();
      else await page.locator('#chapters .ptext').first().waitFor({state: 'visible'});
      await page.evaluate(async () => {
        await document.fonts.ready;
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      });
      await shotAnchor(page);
      if (flow === 'editorial-loop') {
        await page.waitForTimeout(350);
        await withCaption('Start with the manuscript review overview.', async () => {
          await smoothClick(page.locator('[data-analysis-workflow=review]'));
          await page.locator('#flags').scrollIntoViewIfNeeded();
          await page.waitForTimeout(450);
          const flagRow = page.locator('#flags .flag-row button[data-target]').first();
          if (await flagRow.count()) await smoothHover(flagRow, 700);
        }, {leadMs: 450, holdMs: 900});
        const paragraph = page.locator('#ch-1 .ptext').nth(2);
        await withCaption('Open a passage for closer inspection.', async () => {
          await smoothClick(page.locator('#workbench-overview-back'));
          await smoothClick(paragraph.locator('[data-reader-paragraph]'));
          await smoothClick(page.locator('[data-reader-action=values]'));
          assert.equal(await page.locator('#reader-inspector').isVisible(), true);
          assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'false',
            'Local paragraph Values leave global Analysis Off');
        }, {leadMs: 400, holdMs: 1450});
        await withCaption('Draft a review note beside the selected passage.', async () => {
          await smoothClick(paragraph.locator('[data-reader-paragraph]'));
          await smoothClick(page.locator('[data-reader-action=todo]'));
          await placeCaptionClear('.marker-note, [data-marker-save], [data-marker-cancel], #reader-inspector button');
          await moveTo(paragraph.locator('.marker-note'));
          await paragraph.locator('.marker-note').pressSequentially('Check the closing cadence here', {delay: 55});
          await assertCaptionClear('.marker-note, [data-marker-save], [data-marker-cancel], #reader-inspector button');
        }, {leadMs: 400, holdMs: 1500});
        await withCaption('Return to the overview to find passage markers.', async () => {
          await smoothClick(page.locator('#workbench-overview-open'));
          await smoothClick(page.locator('[data-analysis-workflow=review]'));
          await smoothClick(page.locator('[data-analysis-section-target=markers]'));
          await page.locator('#markers').scrollIntoViewIfNeeded();
        }, {leadMs: 400, holdMs: 2800, keep: true});
      } else if (flow === 'analysis-review') {
        await page.waitForTimeout(350);
        const paragraph = page.locator('#chapters .ptext').first();
        await withCaption('Read with manuscript analysis switched off.', async () => {
          await paragraph.scrollIntoViewIfNeeded();
          await moveTo(paragraph);
          assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'false');
        }, {leadMs: 400, holdMs: 1500});
        await withCaption('Open a passage for closer inspection.', async () => {
          await smoothClick(paragraph.locator('[data-reader-paragraph]'));
          await smoothClick(page.locator('[data-reader-action=values]'));
          assert.equal(await page.locator('#reader-inspector').isVisible(), true);
          assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'false',
            'Local paragraph Values leave global Analysis Off');
        }, {leadMs: 400, holdMs: 1600});
        await withCaption('Open the analysis overview for chapter comparisons.', async () => {
          await smoothClick(page.locator('#workbench-overview-open'));
          await assertReviewConfirmed();
          await smoothClick(page.locator('[data-analysis-workflow=compare]'));
          await smoothClick(page.locator('[data-analysis-section-target=style]'));
        }, {leadMs: 400, holdMs: 1300});
        const dimensions = page.locator('#style-tab-dimensions');
        if (await dimensions.count()) {
          await withCaption('View chapters in the style dimensions chart.', async () => {
            await dimensions.scrollIntoViewIfNeeded();
            await smoothClick(dimensions);
          }, {leadMs: 400, holdMs: 1600});
        }
        await withCaption('Select a chapter to inspect its style coordinates.', async () => {
          await smoothSelect(page.locator('#dim-chapter-select'), '2');
          await page.locator('.dim-selection-panel').scrollIntoViewIfNeeded();
          assert.equal(await page.locator('#dim-selection').getAttribute('data-chapter'), '2');
        }, {leadMs: 400, holdMs: 1600});
        await withCaption('Switch to a two-dimensional chart projection.', async () => {
          await smoothSelect(page.locator('#dim-projection'), 'd1-d2');
          await page.locator('.dim-view-control').filter({has: page.locator('#dim-projection')}).evaluate(element => {
            const toolbar = document.querySelector('.toolbar');
            const offset = toolbar ? toolbar.getBoundingClientRect().height : 0;
            window.scrollTo({top: scrollY + element.getBoundingClientRect().top - offset - 16, behavior: 'instant'});
          });
          assert.equal(await page.locator('#dim-3d-canvas').getAttribute('data-projection'), 'd1-d2');
          assert.ok(await page.locator('#dim-3d-canvas').evaluate(element => {
            const bounds = element.getBoundingClientRect();
            const toolbar = document.querySelector('.toolbar');
            return bounds.top >= (toolbar ? toolbar.getBoundingClientRect().bottom : 0) && bounds.bottom <= innerHeight;
          }), 'The walkthrough shows the full planar chart below the manuscript toolbar');
        }, {leadMs: 400, holdMs: 2800, keep: true});
      } else {
        await page.waitForTimeout(350);
        const rows = page.locator('#research-claims-timeline .research-timeline-strip-row');
        let count = 0;
        await withCaption('Open the timeline to compare recorded claim dates.', async () => {
          await smoothClick(page.locator('[data-view="research"]'));
          await smoothClick(page.locator('[data-rtab="claims"]'));
          await page.waitForTimeout(500);
          await smoothClick(page.locator('#r-open-timeline'));
          await page.waitForFunction(() => document.querySelector('#research-claims-timeline .research-timeline-strip-row'));
          await page.waitForTimeout(450);
          count = await rows.count();
          for (let index = 0; index < count; index++) {
            await smoothHover(rows.nth(index), 550);
          }
        }, {leadMs: 400, holdMs: 900});
        await withCaption('Follow a timeline row to its claim.', async () => {
          await smoothClick(rows.first());
          await placeCaptionClear('#research-claims-list button, #research-claims-timeline button');
          await assertCaptionClear('#research-claims-list button, #research-claims-timeline button');
          await page.waitForTimeout(900);
          await smoothScrollBy(300, 10, 400);
          await page.waitForTimeout(1200);
          await smoothScrollBy(-700, 12, 480);
        }, {leadMs: 400, holdMs: 600});
        await withCaption('Dates organize claims; they do not verify them.', async () => {
          await smoothHover(rows.nth(Math.min(1, count - 1)), 600);
        }, {leadMs: 400, holdMs: 2800, keep: true});
      }
      assert.deepEqual(errors, [], 'Walkthrough recording must be free of runtime errors');
      const video = page.video();
      await context.close();
      const source = await video.path();
      const [startFrame] = anchoredFrames(source, [{id: flow, frames: 1}]);
      const bytes = fs.readFileSync(source);
      const file = path.basename(capture.videoTarget);
      const sidecar = source.replace(/\.webm$/, '.json');
      fs.writeFileSync(sidecar, JSON.stringify({schema_version: 'lixity-guide-recording/1',
        file, sha256: digest(bytes), startFrame}, null, 2) + '\n');
      fs.renameSync(source, capture.videoTarget);
      fs.renameSync(sidecar, capture.videoTarget.replace(/\.webm$/, '.json'));
      results.push({video: file, bytes: bytes.length, startFrame});
    }));
    const base = path.dirname(captures[0].source);
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(base, 'capture-results.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results, null, 2));
  } finally {
    if (guideBrowser) await guideBrowser.close();
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
