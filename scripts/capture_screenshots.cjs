const {selectMetric} = require('../tests/browser/support/analysis-controls.cjs');
const {launchChromium} = require('./browser_tools.cjs');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
// Loopback is a trustworthy context for Web Crypto, just like the native app.
// Every request to this synthetic origin is intercepted; no server is contacted.
const CAPTURE_ORIGIN = 'http://localhost:41737';

async function main() {
  const captures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await launchChromium();
  const results = [];
  try {
    const fixturePath = path.join(path.dirname(captures[0].source), 'research-workspace-fixture.json');
    const researchFixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
    // Intercept a synthetic origin so embedded exact-version images use the same
    // resource URLs as the native app without contacting a running server.
    async function prepareWorkspacePage(target, {cursor = false} = {}) {
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
      const resource = researchFixture[url.pathname + url.search];
      if (url.pathname === '/api/research/image' && resource && resource.asset_path) {
        assert.equal(route.request().method(), 'GET');
        assert.ok(['docs/assets/research/hamburg-free-port-1900.jpg',
          'docs/assets/research/hamburg-harbour-1890-1900.jpg'].includes(resource.asset_path));
        await route.fulfill({status: 200, contentType: resource.media_type,
          body: fs.readFileSync(path.join(__dirname, '..', resource.asset_path))});
        return;
      }
      const allSources = captures.flatMap(item => [item.source, ...(item.extraSources || [])]);
      const matchedSource = allSources.find(src => '/' + path.basename(src) === url.pathname);
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
        return Promise.resolve(new Response(JSON.stringify(result), {
          status: 200,
          headers: {'Content-Type': 'application/json'},
        }));
      };
    }, {fixture: researchFixture});
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
          window.setWalkthroughCaption = text => {
            caption.textContent = text || '';
            caption.style.opacity = text ? '1' : '0';
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
        await page.locator('#analysis-evidence-card').waitFor({state: 'visible'});
        await settle();
        await page.mouse.move(0, 0);
        // Frame the complete native card; surrounding stacked controls obscure
        // its quotation/count distinction when scaled for an editorial page.
        await page.locator('#analysis-evidence-card').screenshot({path: capture.target, animations:'disabled'});
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
        const card = page.locator('#research-dossiers-list .research-card:visible').first();
        await card.locator('[data-research-detail]').click();
        await card.locator('.research-details-body .research-prose').first().waitFor();
        for (const image of await card.locator('.dossier-image img').all()) {
          await image.scrollIntoViewIfNeeded();
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
    for (const capture of captures.filter(item => item.video)) {
      const context = await browser.newContext({
        viewport: {width: capture.width, height: capture.height},
        reducedMotion: 'reduce',
        recordVideo: {dir: path.dirname(capture.videoTarget), size: {width: capture.width, height: capture.height}},
        deviceScaleFactor: 2,
      });
      const recordingStarted = Date.now();
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
      await prepareWorkspacePage(page, {cursor: true});
      page.setDefaultTimeout(15000);
      const flow = path.basename(capture.videoTarget, '.webm');
      const say = async text => {
        await page.evaluate(value => {
          if (window.setWalkthroughCaption) window.setWalkthroughCaption(value);
        }, text);
        await page.waitForTimeout(1200);
        await page.evaluate(() => window.setWalkthroughCaption(''));
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
      await page.goto(CAPTURE_ORIGIN + '/' + path.basename(capture.source));
      if (flow !== 'research-timeline' && await page.locator('#workbench-overview-open').count()) {
        await page.locator('#tab-view-analysis').click();
        if (flow === 'editorial-loop') await page.locator('#workbench-overview-open').click();
      }
      if (flow === 'product-tour') {
        // Fixed eight-second scene buckets keep localized website captions synchronized,
        // while dynamic sub-cuts inside each bucket create a fast-paced, kinetic tour.
        await page.addInitScript(() => {
          const setupTourChrome = () => {
            if (document.getElementById('tour-chrome-style')) return;
            const style = document.createElement('style');
            style.id = 'tour-chrome-style';
            style.textContent = `
              #walkthrough-cursor { width:16px!important;height:16px!important;margin:-8px!important;
                background:rgba(59,130,246,.42)!important;border-color:#93c5fd!important;
                transition:opacity .25s,transform .08s; }
              .tour-focus-ring { position:fixed;pointer-events:none;z-index:2147483645;
                border:2px solid #60a5fa;border-radius:9px;box-shadow:0 0 0 5px rgba(59,130,246,.18);
                animation:tour-ring 2.6s ease both; }
              @keyframes tour-ring { 0% {opacity:0;transform:scale(.98)} 14%,78% {opacity:1;transform:scale(1)} 100% {opacity:0} }
              #tour-hud { position:fixed;top:16px;right:20px;z-index:2147483646;pointer-events:none;
                padding:7px 14px;border-radius:999px;background:rgba(13,19,34,.90);color:#f8fafc;
                border:1px solid rgba(148,163,184,.32);box-shadow:0 8px 24px rgba(0,0,0,.28);
                font:650 12.5px/1.2 system-ui,-apple-system,"Segoe UI",sans-serif;letter-spacing:.06em;
                text-transform:uppercase;opacity:0;transform:translateY(-4px);
                transition:opacity .18s ease,transform .18s ease; }
              #tour-hud.visible { opacity:1;transform:translateY(0); }
            `;
            document.head.appendChild(style);
            const hud = document.createElement('div');
            hud.id = 'tour-hud';
            document.body.appendChild(hud);
          };
          window.setTourHud = label => {
            setupTourChrome();
            const hud = document.getElementById('tour-hud');
            if (!hud) return;
            hud.textContent = label || '';
            hud.classList.toggle('visible', Boolean(label));
          };
          if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setupTourChrome);
          else setupTourChrome();
        });
        await page.emulateMedia({colorScheme: 'light'});
        await page.evaluate(() => document.fonts.ready);
        const started = Date.now();
        const scenes = [];
        const cuts = [];
        const click = async locator => {
          await locator.scrollIntoViewIfNeeded();
          const box = await locator.boundingBox();
          assert.ok(box, 'A directed action must target a visible control');
          await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, {steps: 4});
          await page.waitForTimeout(40);
          await locator.click();
        };
        let manuscriptDraft = '# 1. The Eastern Gate\n\nIt was in the back of the quiet harbour where the watchman waited. "Did you hear the bell?" she asked.\n\nHe shook his head. The fog lay thick over the pilings.\n';
        const baselineDraft = '# 1. The Eastern Gate\n\nIt was in the back of the quiet harbour where the watchman waited.\n\nHe shook his head. The fog lay thick over the pilings.\n';
        await page.route('**/api/manuscript**', async route => {
          const req = route.request();
          const url = req.url();
          if (req.method() === 'GET' && url.includes('/editor-bootstrap.js')) {
            await route.fulfill({
              status: 200,
              contentType: 'application/javascript; charset=utf-8',
              body: fs.readFileSync(path.join(__dirname, '..', 'src/lixity/ui/assets/manuscript-editor.js'), 'utf8'),
            });
            return;
          }
          if (req.method() === 'GET' && url.includes('/editor-bundle.js')) {
            await route.fulfill({
              status: 200,
              contentType: 'application/javascript; charset=utf-8',
              body: fs.readFileSync(path.join(__dirname, '..', 'src/lixity/ui/assets/vendor/codemirror-editor.js'), 'utf8'),
            });
            return;
          }
          if (req.method() === 'GET' && url.includes('/manuscript-delta')) {
            await route.fulfill({
              status: 200,
              contentType: 'application/json',
              body: JSON.stringify({
                ok: true, available: true, has_previous: true, baseline_label: 'Baseline · Chapter 1',
                deltas: {words: 3, asl: -0.4, sticky_pct: 0.0, indirect_speech_per_1000: 0.0, asl_cv: 0.02},
              }),
            });
            return;
          }
          if (req.method() === 'GET' && url.includes('/manuscript-timeline')) {
            await route.fulfill({
              status: 200,
              contentType: 'application/json',
              body: JSON.stringify({
                ok: true,
                points: [
                  {label: 'Rev 1', words: 32, asl: 8.0, asl_cv: 0.42},
                  {label: 'Now', words: 35, asl: 7.6, asl_cv: 0.44},
                ],
              }),
            });
            return;
          }
          if (req.method() === 'GET' && url.includes('/manuscript-edit') && url.includes('recovery=')) {
            await route.fulfill({
              status: 200,
              contentType: 'application/json',
              body: JSON.stringify({
                ok: true, document: 'harbour-manuscript.md',
                id: 'snap-1', kind: 'snapshot', created: 1794682800, text: baselineDraft,
              }),
            });
            return;
          }
          if (req.method() === 'GET' && url.includes('/api/manuscript')) {
            await route.fulfill({
              status: 200,
              contentType: 'application/json',
              body: JSON.stringify({
                ok: true,
                document: 'harbour-manuscript.md',
                text: manuscriptDraft,
                revision: 'rev-1',
                sha256: 'tour-sha256',
                recovery: [{
                  id: 'snap-1', kind: 'snapshot', label: 'Baseline · Chapter 1',
                  created: 1794682800, text: baselineDraft,
                  metrics: {words: 26, asl: 8.7, asl_cv: 0.40, length_entropy: 1.12, sticky_pct: 3.8, indirect_speech_per_1000: 0.0, dialogue_ratio: 0.0, mattr: 0.82, flags_count: 1},
                }],
              }),
            });
            return;
          }
          if (req.method() === 'POST' && url.includes('/api/manuscript')) {
            try { const body = JSON.parse(req.postData() || '{}'); if (typeof body.text === 'string') manuscriptDraft = body.text; } catch {}
            await route.fulfill({
              status: 200,
              contentType: 'application/json',
              body: JSON.stringify({ok: true, saved: true, revision: 'rev-2', sha256: 'tour-sha256-2'}),
            });
            return;
          }
          await route.fallback();
        });
        const gotoTourPage = async (filename, colorScheme = 'light') => {
          await page.emulateMedia({colorScheme});
          await page.goto(CAPTURE_ORIGIN + '/' + filename);
          await page.evaluate(() => document.fonts.ready);
        };
        const computeFrame = async (focus, marker) => {
          const box = await page.locator(focus).first().boundingBox();
          assert.ok(box && box.width > 0 && box.height > 0, 'The camera needs a visible focus region: ' + focus);
          const top = Math.max(0, box.y), bottom = Math.min(900, box.y + box.height);
          const framed = {x: box.x, y: top, width: box.width, height: Math.max(1, bottom - top)};
          const marked = marker ? await page.locator(marker).first().evaluate(node => {
            const range = document.createRange(); range.selectNodeContents(node);
            const rect = node.tagName === 'SUMMARY' ? range.getBoundingClientRect() : node.getBoundingClientRect();
            return {x: rect.x - 3, y: rect.y - 3, width: rect.width + 6, height: rect.height + 6};
          }) : null;
          if (marked && marked.x >= 0 && marked.y >= 0 &&
              marked.x + marked.width <= 1440 && marked.y + marked.height <= 900 &&
              marked.width <= 760 && marked.height <= 300) {
            await page.evaluate(b => {
              document.querySelectorAll('.tour-focus-ring').forEach(node => node.remove());
              const ring = document.createElement('div'); ring.className = 'tour-focus-ring';
              Object.assign(ring.style, {left: b.x + 'px', top: b.y + 'px', width: b.width + 'px', height: b.height + 'px'});
              document.body.appendChild(ring);
              const cursor = document.getElementById('walkthrough-cursor'); if (cursor) cursor.style.opacity = '0';
            }, marked);
          }
          return {
            x: (framed.x + framed.width / 2) / 1440,
            y: (framed.y + framed.height / 2) / 900,
            zoom: Math.max(1, Math.min(1.55, 1440 / (framed.width + 110), 900 / (framed.height + 130))),
          };
        };
        const cut = async (hudLabel, action, focus, marker, holdUntilMs) => {
          const cutStart = Date.now();
          let prevShot = null;
          if (cuts.length) prevShot = await page.screenshot();
          await action();
          if (prevShot) {
            await page.evaluate(data => {
              const image = document.createElement('img'); image.id = 'tour-dissolve';
              image.src = data;
              image.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;z-index:2147483647;pointer-events:none;opacity:1;transition:opacity .20s ease';
              document.body.appendChild(image);
              requestAnimationFrame(() => { image.style.opacity = '0'; setTimeout(() => image.remove(), 220); });
            }, 'data:image/png;base64,' + prevShot.toString('base64'));
          }
          await page.evaluate(label => { if (window.setTourHud) window.setTourHud(label); }, hudLabel);
          const cam = await computeFrame(focus, marker);
          await page.waitForTimeout(Math.max(0, holdUntilMs - (Date.now() - started)));
          await page.evaluate(() => document.querySelectorAll('.tour-focus-ring').forEach(node => node.remove()));
          cuts.push({
            start: Number(((cutStart - started) / 1000).toFixed(3)),
            end: Number(((Date.now() - started) / 1000).toFixed(3)),
            ...cam,
          });
        };
        const runScene = async (index, name, body) => {
          const targetStart = index * 7000;
          const remainingPre = targetStart - (Date.now() - started);
          if (remainingPre > 0) await page.waitForTimeout(remainingPre);
          const sceneStart = (Date.now() - started) / 1000;
          await body((index + 1) * 7000);
          scenes.push({name, start: Number(sceneStart.toFixed(3)), x: 0.5, y: 0.5, zoom: 1.0});
        };

        // Scene 1 (0-7s): Classic-novel hook — Effi Briest sticky sentences + Pride & Prejudice voice contrast + Sandbox
        await runScene(0, 'read', async sceneEnd => {
          await cut('01 · EFFI BRIEST · 33.5% STICKY', async () => {
            await gotoTourPage('tour-effi-briest.html', 'light');
            await click(page.locator('#manuscript-analysis-toggle'));
            await selectMetric(page, 'sticky');
            await page.locator('#chapters .ptext').first().scrollIntoViewIfNeeded();
          }, '#chapters .ptext', '#style-layer', sceneEnd - 4600);
          await cut('01 · PRIDE & PREJUDICE · -9.7W VOICE', async () => {
            await gotoTourPage('tour-pride-prejudice.html', 'light');
            await click(page.locator('#workbench-overview-open'));
            await page.locator('#analysis-measurements').evaluate(node => { node.open = true; });
            await page.locator('#dialogue').scrollIntoViewIfNeeded();
          }, '#dialogue', '#dialogue h2', sceneEnd - 2200);
          await cut('01 · BROWSER SANDBOX · 1-CLICK', async () => {
            await gotoTourPage('sandbox-index.html?preset=effi-briest', 'light');
            await page.locator('#k-sticky').scrollIntoViewIfNeeded();
          }, 'main', '#preset-de', sceneEnd);
        });

        // Scene 2 (7-14s): Direct Speech Mode (D) + Evidence Card + Manuscript Search
        await runScene(1, 'passage', async sceneEnd => {
          await cut('02 · DIRECT SPEECH MODE [D]', async () => {
            await gotoTourPage('tour-pride-prejudice.html', 'light');
            await click(page.locator('#reader-direct-speech'));
            await page.locator('#chapters .ptext.direct-speech-only, #chapters .ptext.direct-speech-mixed, #chapters .ptext').first().scrollIntoViewIfNeeded();
          }, '#chapters .ptext', '#reader-direct-speech', sceneEnd - 4600);
          await cut('02 · PASSAGE EVIDENCE POPOVER', async () => {
            const p = page.locator('#chapters .ptext').nth(1);
            await click(p.locator('[data-reader-paragraph]'));
            await click(page.locator('[data-reader-action=values]'));
            await page.locator('#reader-inspector').waitFor({state: 'visible'});
            await page.locator('#reader-inspector details').first().evaluate(node => { node.open = true; });
          }, '#reader-inspector details', '#reader-inspector details summary', sceneEnd - 2200);
          await cut('02 · INSTANT PASSAGE SEARCH', async () => {
            await gotoTourPage('dashboard-research-workspace.html', 'light');
            await click(page.locator('#tab-view-analysis'));
            await page.locator('#text-search').fill('crate');
            await page.locator('#text-search').press('Enter');
          }, '#chapters .ptext', '#text-search', sceneEnd);
        });

        // Scene 3 (14-21s): Manuscript Editor (#manuscript-write) + Live Session Pulse + Revision Diff
        await runScene(2, 'compare', async sceneEnd => {
          await cut('03 · MANUSCRIPT EDITOR · LIVE', async () => {
            if (await page.locator('#text-search-clear').isVisible()) await click(page.locator('#text-search-clear'));
            await page.evaluate(() => {
              if (!document.getElementById('manuscript-write')) {
                const s = document.createElement('script');
                const existing = document.querySelector('script[nonce]');
                if (existing) s.nonce = existing.nonce || existing.getAttribute('nonce') || '';
                s.src = '/api/manuscript/editor-bootstrap.js';
                document.body.appendChild(s);
              }
            });
            await page.locator('#manuscript-write').waitFor({state: 'visible'});
            await click(page.locator('#manuscript-write'));
            await page.locator('.cm-content').waitFor({state: 'visible'});
            await page.locator('.cm-content').click();
            await page.keyboard.press('Control+End');
            await page.keyboard.type(' Lanterns lit.', {delay: 10});
          }, '.manuscript-editor-toolbar', '#manuscript-session-pulse', sceneEnd - 4400);
          await cut('03 · REVISION DIFF · DELTAS', async () => {
            await click(page.locator('#manuscript-compare'));
            await page.locator('#manuscript-comparison').waitFor({state: 'visible'});
          }, '#manuscript-comparison .modal-card', '#manuscript-comparison h2', sceneEnd - 2400);
          await cut('03 · MESSGRÖSSE · ALL LAYERS', async () => {
            await gotoTourPage('tour-effi-briest.html', 'light');
            await click(page.locator('#manuscript-analysis-toggle'));
            for (const layer of ['sticky', 'echo', 'indirect_speech']) {
              if (await page.locator('#style-layer option[value="' + layer + '"]').count()) {
                await selectMetric(page, layer);
                await page.waitForTimeout(180);
              }
            }
          }, '#chapters .ptext', '#style-layer', sceneEnd);
        });

        // Scene 4 (21-28s): Chapter Matrix (z* & FDR) + Character Voices & Interactions + Scene Hooks & Rhythm
        await runScene(3, 'research', async sceneEnd => {
          await cut('04 · CHAPTER MATRIX · z* & FDR', async () => {
            await gotoTourPage('dashboard-research-workspace.html', 'light');
            await click(page.locator('#tab-view-analysis'));
            await click(page.locator('#workbench-overview-open'));
            await page.locator('#analysis-measurements').evaluate(node => { node.open = true; });
            await click(page.locator('#style-tab-heatmap'));
            await page.locator('#heatmap-ch-3 td:nth-child(6)').evaluate(node =>
              node.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'instant'}));
          }, '#heatmap tbody', '#heatmap-ch-3 td:nth-child(6)', sceneEnd - 4600);
          await cut('04 · SCENES · COHESION DROPS', async () => {
            await page.locator('#scenes').scrollIntoViewIfNeeded();
          }, '#scenes', '#scenes h2', sceneEnd - 2300);
          await cut('04 · ANTI-FLATTENING RHYTHM', async () => {
            await page.emulateMedia({colorScheme: 'dark'});
            await page.locator('#pacing').scrollIntoViewIfNeeded();
          }, '#pacing', '#pacing h2', sceneEnd);
        });

        // Scene 5 (28-35s): Research Dossiers & Source-Verified Claims Timeline
        await runScene(4, 'context', async sceneEnd => {
          await cut('05 · RESEARCH DOSSIERS', async () => {
            await click(page.locator('#tab-view-research'));
            await click(page.locator('[data-rtab=dossiers]'));
            const dossier = page.locator('#research-dossiers-list .research-card').filter({hasText: 'Warehouse 4 case notes'});
            await click(dossier.locator('[data-research-detail=dossier]'));
            await dossier.locator('.research-details-body').waitFor({state: 'visible'});
            await dossier.locator('.dossier-image').first().scrollIntoViewIfNeeded();
          }, '.research-details-body .dossier-image', '#research-dossiers-list .research-card [data-research-detail=dossier]', sceneEnd - 3500);
          await cut('05 · SOURCE-VERIFIED CLAIMS', async () => {
            await click(page.locator('[data-rtab=claims]'));
            await click(page.locator('#r-open-timeline'));
            await page.waitForFunction(() => document.querySelector('#research-claims-timeline .research-timeline-strip-row'));
            await page.locator('#research-claims-timeline').scrollIntoViewIfNeeded();
          }, '#research-claims-timeline', '#research-claims-timeline .research-timeline-strip-row', sceneEnd);
        });

        // Scene 6 (35-42s): Standalone Export & Browser Sandbox CTA
        await runScene(5, 'return', async sceneEnd => {
          await cut('06 · STANDALONE EXPORT', async () => {
            await page.emulateMedia({colorScheme: 'light'});
            await click(page.locator('#tab-view-analysis'));
            if (await page.locator('#workbench-overview-back').isVisible()) await page.locator('#workbench-overview-back').click();
            await click(page.locator('#project-actions > summary'));
            await page.locator('#btn-site-export').evaluate(b => { b.disabled = false; });
            await click(page.locator('#btn-site-export'));
            if (!await page.locator('#modal-site-export').isVisible()) {
              await page.evaluate(() => document.getElementById('modal-site-export')?.showModal());
            }
            await page.locator('#modal-site-export').waitFor({state: 'visible'});
          }, '#modal-site-export .modal-card', '#modal-site-export h3', sceneEnd - 3500);
          await cut('06 · TRY IN BROWSER · 100% OFFLINE', async () => {
            await gotoTourPage('sandbox-index.html?preset=pride-prejudice', 'light');
            await click(page.locator('#direct-speech-btn'));
          }, 'main', '#direct-speech-btn', sceneEnd);
        });

        fs.writeFileSync(
          capture.videoTarget.replace('.webm', '.json'),
          JSON.stringify({
            scenes,
            cuts,
            duration: 42,
            trim: (started - recordingStarted) / 1000,
            socialHooks: [
              {start: cuts[0].start, end: cuts[0].end, text: '33.5% Sticky Sentences in Effi Briest', x: cuts[0].x, zoom: cuts[0].zoom},
              {start: cuts[1].start, end: cuts[1].end, text: 'Voice Contrast: -9.7 Words in Dialogue', x: cuts[1].x, zoom: cuts[1].zoom},
              {start: cuts[3].start, end: cuts[3].end, text: 'Dialogue-Only Mode [D]', x: cuts[3].x, zoom: cuts[3].zoom},
              {start: cuts[6].start, end: cuts[6].end, text: 'Live Manuscript Editor + Session Pulse', x: cuts[6].x, zoom: cuts[6].zoom},
              {start: cuts[7].start, end: cuts[7].end, text: 'Revision Diff: Track Every Rewrite', x: cuts[7].x, zoom: cuts[7].zoom},
              {start: cuts[11].start, end: cuts[11].end, text: 'Anti-Flattening Rhythm Entropy', x: cuts[11].x, zoom: cuts[11].zoom},
              {start: cuts[15].start, end: cuts[15].end, text: 'Try Free in Browser - 100% Offline', x: cuts[15].x, zoom: cuts[15].zoom},
            ],
          }),
        );
      } else if (flow === 'editorial-loop') {
        await page.waitForTimeout(1000);
        await say('Listen to the pulse: Spot where narrative cadence shifts');
        await page.locator('#flags').scrollIntoViewIfNeeded();
        await page.waitForTimeout(900);
        const flagRow = page.locator('#flags [data-marker-kind]').first();
        if (await flagRow.count()) {
          await flagRow.hover();
          await page.waitForTimeout(900);
        }
        await say('Touch the prose: Instant word counts, rhythm, and tense cues');
        await page.locator('#workbench-overview-back').click();
        const paragraph = page.locator('#ch-1 .ptext').nth(2);
        await paragraph.locator('[data-reader-paragraph]').click();
        await page.locator('[data-reader-action=values]').click();
        assert.equal(await page.locator('#reader-inspector').isVisible(), true);
        assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'false',
          'Local paragraph Values leave global Analysis Off');
        await page.waitForTimeout(1200);
        await say('Surgical precision: Inspect sentence melody without leaving context');
        await paragraph.locator('[data-reader-paragraph]').click();
        await page.locator('[data-reader-action=todo]').click();
        await paragraph.locator('.marker-note').pressSequentially('Check the closing cadence here', {delay: 60});
        await assertCaptionClear('.marker-note, [data-marker-save], [data-marker-cancel], #reader-inspector button');
        await page.waitForTimeout(1300);
        await say('Anchor editorial insights directly in your manuscript');
        await page.locator('#workbench-overview-open').click();
        await page.locator('#markers').scrollIntoViewIfNeeded();
        await page.waitForTimeout(1500);
      } else if (flow === 'analysis-review') {
        await page.waitForTimeout(1000);
        await say('Pure focus: Immerse in uninterrupted reading');
        const paragraph = page.locator('#chapters .ptext').first();
        await paragraph.scrollIntoViewIfNeeded();
        assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'false');
        await page.waitForTimeout(1200);
        await say('Reveal the rhythm: Pacing and dialogue balance on demand');
        await paragraph.locator('[data-reader-paragraph]').click();
        await page.locator('[data-reader-action=values]').click();
        assert.equal(await page.locator('#reader-inspector').isVisible(), true);
        assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'false',
          'Local paragraph Values leave global Analysis Off');
        await page.waitForTimeout(1300);
        await say('Macro perspective: Survey the emotional breathing of every chapter');
        await page.locator('#workbench-overview-open').click();
        const dimensions = page.locator('#style-tab-dimensions');
        if (await dimensions.count()) {
          await say('Multi-dimensional style space: Explore narrative registers in 3D');
          await dimensions.scrollIntoViewIfNeeded();
          await page.waitForTimeout(700);
          await dimensions.click();
          await page.waitForTimeout(1300);
        }
        await say('Contrast and compare: Track chapter voice against your baseline');
        await page.locator('#dim-chapter-select').selectOption('2');
        await page.locator('.dim-selection-panel').scrollIntoViewIfNeeded();
        assert.equal(await page.locator('#dim-selection').getAttribute('data-chapter'), '2');
        await page.waitForTimeout(1000);
        await say('Planar projections: Clear patterns without visual clutter');
        await page.locator('#dim-projection').selectOption('d1-d2');
        await page.locator('.dim-view-control').evaluate(element => {
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
        await page.waitForTimeout(1000);
      } else {
        await page.waitForTimeout(900);
        await say('Living memory: Historical facts and scene chronology unified');
        await page.locator('[data-view="research"]').click();
        await page.locator('[data-rtab="claims"]').click();
        await page.waitForTimeout(1200);
        await page.locator('#r-open-timeline').click();
        await page.waitForFunction(() => document.querySelector('#research-claims-timeline .research-timeline-strip-row'));
        await page.waitForTimeout(600);
        const rows = page.locator('#research-claims-timeline .research-timeline-strip-row');
        const count = await rows.count();
        for (let index = 0; index < count; index++) {
          await rows.nth(index).hover();
          await page.waitForTimeout(400);
        }
        await say('Unbroken lineage: Every detail traces back to primary sources');
        await rows.first().click();
        await assertCaptionClear('#research-claims-list button, #research-claims-timeline button');
        await page.waitForTimeout(1200);
        await page.mouse.wheel(0, 300);
        await page.waitForTimeout(1300);
        await page.mouse.wheel(0, -700);
        await page.waitForTimeout(700);
        await say('Immutable truth: Creative decisions grounded in verified evidence');
        await rows.nth(Math.min(1, count - 1)).hover();
        await page.waitForTimeout(1300);
      }
      assert.deepEqual(errors, [], 'Walkthrough recording must be free of runtime errors');
      const video = page.video();
      await context.close();
      fs.copyFileSync(await video.path(), capture.videoTarget);
      results.push({video: path.basename(capture.videoTarget), bytes: fs.statSync(capture.videoTarget).size});
    }
    const base = path.dirname(captures[0].source);
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(base, 'capture-results.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
