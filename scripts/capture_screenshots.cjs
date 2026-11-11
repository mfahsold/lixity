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
      const capture = captures.find(item => '/' + path.basename(item.source) === url.pathname);
      assert.ok(capture, 'Unknown screenshot resource: ' + url.pathname);
      await route.fulfill({status: 200, contentType: 'text/html; charset=utf-8',
        body: fs.readFileSync(capture.source)});
    });
    await target.addInitScript(({fixture}) => {
      window.captureRequests = [];
      window.fetch = (input, options) => {
        const url = typeof input === 'string' ? input : input.url;
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
          caption.style.cssText = 'position:fixed;left:50%;bottom:26px;transform:translateX(-50%);max-width:78%;' +
            'padding:10px 16px;border-radius:999px;background:rgba(17,24,39,.88);color:#fff;' +
            'font:600 15px/1.35 system-ui,-apple-system,"Segoe UI",sans-serif;letter-spacing:.01em;text-align:center;' +
            'z-index:2147483647;pointer-events:none;opacity:0;';
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
        // Fixed eight-second scenes keep localized website captions synchronized.
        // Trim the load interval in the encoder; every view is the real app.
        await page.emulateMedia({colorScheme: 'light'});
        await page.evaluate(() => document.fonts.ready);
        // Recording-only direction: real controls, a visible pointer and one
        // bounded focus ring. These overlays never enter product exports.
        await page.addStyleTag({content: `
          #walkthrough-cursor { width:16px!important;height:16px!important;margin:-8px!important;
            background:rgba(115,146,255,.4)!important;border-color:#a8baff!important;
            transition:opacity .4s,transform .1s; }
          .tour-focus-ring { position:fixed;pointer-events:none;z-index:2147483645;
            border:2px solid #809aff;border-radius:9px;box-shadow:0 0 0 5px rgba(100,130,255,.14);
            animation:tour-ring 3.6s ease both; }
          @keyframes tour-ring { 0% {opacity:0;transform:scale(.99)} 15%,75% {opacity:1;transform:scale(1)} 100% {opacity:0} }
        `});
        const started = Date.now();
        const scenes = [];
        const click = async locator => {
          await locator.scrollIntoViewIfNeeded();
          const box = await locator.boundingBox();
          assert.ok(box, 'A directed action must target a visible control');
          await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, {steps: 16});
          await page.waitForTimeout(180);
          await locator.click();
        };
        const scene = async (name, action, focus, marker = null) => {
          const start = Date.now();
          // Brief dissolves carry orientation across view and theme changes.
          if (scenes.length) {
            const previous = await page.screenshot();
            await page.evaluate(data => {
              const image = document.createElement('img'); image.id = 'tour-dissolve';
              image.src = data; image.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;z-index:2147483646;pointer-events:none;transition:opacity .45s ease';
              document.body.appendChild(image);
            }, 'data:image/png;base64,' + previous.toString('base64'));
          }
          await action();
          await page.evaluate(() => {
            const image = document.getElementById('tour-dissolve');
            if (image) { image.style.opacity = '0'; setTimeout(() => image.remove(), 500); }
          });
          const box = await page.locator(focus).first().boundingBox();
          assert.ok(box && box.width > 0 && box.height > 0, 'The camera needs a visible focus region');
          const top = Math.max(0, box.y), bottom = Math.min(900, box.y + box.height);
          const framed = {x: box.x, y: top, width: box.width, height: Math.max(1, bottom - top)};
          scenes.push({name, start: (start - started) / 1000,
            x: (framed.x + framed.width / 2) / 1440, y: (framed.y + framed.height / 2) / 900,
            zoom: Math.max(1, Math.min(1.5, 1440 / (framed.width + 100), 900 / (framed.height + 130)))});
          await page.waitForTimeout(600);
          const marked = marker ? await page.locator(marker).first().evaluate(node => {
            // A summary's hit area spans the panel; emphasize its label instead.
            const range = document.createRange(); range.selectNodeContents(node);
            const rect = node.tagName === 'SUMMARY' ? range.getBoundingClientRect() : node.getBoundingClientRect();
            return {x: rect.x - 3, y: rect.y - 3, width: rect.width + 6, height: rect.height + 6};
          }) : null;
          if (marker) assert.ok(marked && marked.x >= 0 && marked.y >= 0 &&
            marked.x + marked.width <= 1440 && marked.y + marked.height <= 900 &&
            marked.width <= 700 && marked.height <= 250, `Mark only a complete, compact visible target: ${name} ${JSON.stringify(marked)}`);
          await page.evaluate(box => {
            document.querySelectorAll('.tour-focus-ring').forEach(node => node.remove());
            if (box) {
            const ring = document.createElement('div'); ring.className = 'tour-focus-ring';
            Object.assign(ring.style, {left:box.x+'px',top:box.y+'px',width:box.width+'px',height:box.height+'px'});
            document.body.appendChild(ring);
            }
            const cursor = document.getElementById('walkthrough-cursor'); if(cursor) cursor.style.opacity='0';
          }, marked);
          assert.ok(Date.now() - start < 6500, 'Directed actions must fit their eight-second scene');
          await page.waitForTimeout(Math.max(0, 8000 - (Date.now() - start)));
          await page.evaluate(() => document.querySelectorAll('.tour-focus-ring').forEach(node => node.remove()));
        };
        await scene('read', async () => {
          await click(page.locator('#tab-view-analysis'));
          await page.evaluate(() => window.scrollTo({top: 0, behavior: 'instant'}));
        }, '#chapters .ptext p');
        await scene('passage', async () => {
          const paragraph = page.locator('#chapters .ptext').first();
          await click(paragraph.locator('[data-reader-paragraph]'));
          await click(page.locator('[data-reader-action=values]'));
          await page.locator('#reader-inspector').waitFor({state: 'visible'});
          await page.locator('#reader-inspector details').first().evaluate(node => { node.open = true; });
        }, '#reader-inspector details', '#reader-inspector details summary');
        await scene('compare', async () => {
          await click(page.locator('#workbench-overview-open'));
          await page.locator('#analysis-measurements').evaluate(node => { node.open = true; });
          await click(page.locator('#style-tab-heatmap'));
          await page.locator('#heatmap-ch-3 td:nth-child(6)').evaluate(node =>
            node.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'instant'}));
        }, '#heatmap tbody', '#heatmap-ch-3 td:nth-child(6)');
        await scene('research', async () => {
          await page.emulateMedia({colorScheme: 'dark'});
          await click(page.locator('#tab-view-research'));
          await click(page.locator('[data-rtab=dossiers]'));
          await page.evaluate(() => window.scrollTo({top: 0, behavior: 'instant'}));
        }, '#research-dossiers-list .research-card', '#research-dossiers-list .research-card [data-research-detail=dossier]');
        await scene('context', async () => {
          const dossier = page.locator('#research-dossiers-list .research-card').filter({hasText: 'Warehouse 4 case notes'});
          await click(dossier.locator('[data-research-detail=dossier]'));
          await dossier.locator('.research-details-body').waitFor({state: 'visible'});
          await dossier.locator('.dossier-image').first().scrollIntoViewIfNeeded();
        }, '.research-details-body .dossier-image');
        await scene('return', async () => {
          await click(page.locator('#tab-view-analysis'));
          if (await page.locator('#workbench-overview-back').isVisible()) await page.locator('#workbench-overview-back').click();
          if (await page.locator('#reader-inspector-close').isVisible()) await page.locator('#reader-inspector-close').click();
          await page.evaluate(() => window.scrollTo({top: 0, behavior: 'instant'}));
        }, '#chapters .ptext p');
        fs.writeFileSync(capture.videoTarget.replace('.webm', '.json'), JSON.stringify({scenes, duration: 48, trim: (started - recordingStarted) / 1000}));
      } else if (flow === 'editorial-loop') {
        await page.waitForTimeout(1000);
        await say('Flagged passages become your review queue');
        await page.locator('#flags').scrollIntoViewIfNeeded();
        await page.waitForTimeout(900);
        const flagRow = page.locator('#flags [data-marker-kind]').first();
        if (await flagRow.count()) {
          await flagRow.hover();
          await page.waitForTimeout(900);
        }
        await say('Open a flagged passage: values and source lines');
        await page.locator('#workbench-overview-back').click();
        const paragraph = page.locator('#ch-1 .ptext').nth(2);
        await paragraph.locator('[data-reader-paragraph]').click();
        await page.locator('[data-reader-action=values]').click();
        assert.equal(await page.locator('#reader-inspector').isVisible(), true);
        assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'false',
          'Local paragraph Values leave global Analysis Off');
        await page.waitForTimeout(1200);
        await say('Values, source lines, tense flags \u2014 per paragraph');
        await paragraph.locator('[data-reader-paragraph]').click();
        await page.locator('[data-reader-action=todo]').click();
        await paragraph.locator('.marker-note').pressSequentially('Check the closing cadence here', {delay: 60});
        await assertCaptionClear('.marker-note, [data-marker-save], [data-marker-cancel], #reader-inspector button');
        await page.waitForTimeout(1300);
        await say('Draft a note, then review the marker list');
        await page.locator('#workbench-overview-open').click();
        await page.locator('#markers').scrollIntoViewIfNeeded();
        await page.waitForTimeout(1500);
      } else if (flow === 'analysis-review') {
        await page.waitForTimeout(1000);
        await say('Start with Analysis off: plain reading view');
        const paragraph = page.locator('#chapters .ptext').first();
        await paragraph.scrollIntoViewIfNeeded();
        assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'false');
        await page.waitForTimeout(1200);
        await say('Open any paragraph: values on demand');
        await paragraph.locator('[data-reader-paragraph]').click();
        await page.locator('[data-reader-action=values]').click();
        assert.equal(await page.locator('#reader-inspector').isVisible(), true);
        assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'false',
          'Local paragraph Values leave global Analysis Off');
        await page.waitForTimeout(1300);
        await say('Open the overview to compare measured style dimensions');
        await page.locator('#workbench-overview-open').click();
        const dimensions = page.locator('#style-tab-dimensions');
        if (await dimensions.count()) {
          await say('See the same data as style dimensions');
          await dimensions.scrollIntoViewIfNeeded();
          await page.waitForTimeout(700);
          await dimensions.click();
          await page.waitForTimeout(1300);
        }
        await say('Pin a chapter to keep its scores in view');
        await page.locator('#dim-chapter-select').selectOption('2');
        await page.locator('.dim-selection-panel').scrollIntoViewIfNeeded();
        assert.equal(await page.locator('#dim-selection').getAttribute('data-chapter'), '2');
        await page.waitForTimeout(1000);
        await say('Flatten the view to compare chapter positions');
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
        await say('The timeline places dated claims on one shared axis');
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
        await say('Open a claim to read its card and evidence');
        await rows.first().click();
        await assertCaptionClear('#research-claims-list button, #research-claims-timeline button');
        await page.waitForTimeout(1200);
        await page.mouse.wheel(0, 300);
        await page.waitForTimeout(1300);
        await page.mouse.wheel(0, -700);
        await page.waitForTimeout(700);
        await say('Each bar links to its claim and evidence');
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
