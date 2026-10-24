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
        if (method !== 'GET' && !['/api/nda-draft', '/api/research-search', '/api/research-record-prepare', '/api/research-revision-batch-prepare'].includes(url)) {
          throw new Error('Screenshot capture cannot mutate a project: ' + method + ' ' + url);
        }
        if (url === '/api/research-search') {
          const query = JSON.parse(options.body);
          if (query.query !== 'warehouse customs' || query.scope !== 'sources') {
            throw new Error('Screenshot search must match the generated API result');
          }
        }
        let result = fixture[url];
        if (url === '/api/nda-draft') {
          const draft = JSON.parse(options.body);
          if (draft.format !== 'text' || Object.keys(draft).length !== 6 ||
              Object.keys(result.fields).some(key => draft[key] !== result.fields[key])) {
            throw new Error('NDA capture must match the generated synthetic agreement');
          }
          return Promise.resolve(new Response(result.text, {
            status: 200, headers: {'Content-Type': 'text/plain; charset=utf-8'},
          }));
        }
        if (url === '/api/research-record-prepare') {
          const draft = JSON.parse(options.body);
          result = fixture[url][draft.id];
          if (draft.kind !== 'dossier' || !result || JSON.stringify(draft.changes) !== JSON.stringify(result.changes)) {
            throw new Error('Revision capture must match the generated draft');
          }
        } else if (url === '/api/research-revision-batch-prepare') {
          const draft = JSON.parse(options.body);
          if (JSON.stringify(draft.operations) !== JSON.stringify(result.operations)) {
            throw new Error('Grouped revision capture must match the generated operations');
          }
        }
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
    async function captureThrough(capture, selector, lastSelector) {
      const last = typeof lastSelector === 'string' ? page.locator(lastSelector) : lastSelector;
      await last.waitFor({state: 'visible'});
      await settle();
      capture.maxHeight = Math.ceil(await last.evaluate((last, selector) => {
        const target = document.querySelector(selector);
        return last.getBoundingClientRect().bottom - target.getBoundingClientRect().top
          + parseFloat(getComputedStyle(target).paddingBottom);
      }, selector));
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
      if (path.basename(target) === 'dashboard-layer.png') {
        await page.waitForFunction(() =>
          CSS.highlights?.get('lixity-analysis-evidence')?.size > 0 &&
          document.getElementById('analysis-evidence-status')?.textContent === '');
      }
      const job = captures.find(item => item.target === target) || {};
      const options = {path: target, animations: 'disabled'};
      if (selector) {
        const element = page.locator(selector);
        const clip = await element.evaluate(node => {
          const rect = node.getBoundingClientRect();
          return {x: rect.x + scrollX, y: rect.y + scrollY, width: rect.width, height: rect.height};
        });
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
        if (/^dashboard-(dimensions|reference|markers|flags|heatmap|scenes)/.test(name)) await page.locator('#workbench-overview-open').click();
        else if (/^dashboard-(editorial|layer)/.test(name)) await page.locator('#manuscript-analysis-toggle').click();
      }
      if (name.startsWith('dashboard-dimensions') || ['dashboard-light.png', 'dashboard-dark.png', 'dashboard-mobile.png', 'dashboard-reference.png', 'dashboard-heatmap.png', 'dashboard-layer.png'].includes(name)) await selectView('analysis');
      if (name.startsWith('dashboard-reader-focus')) {
        await selectView('analysis');
        assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'false');
        await page.locator('#reader-settings > summary').click();
        await page.locator('#reader-text-larger').click();
        await page.locator('#reader-settings > summary').click();
        await captureThrough(capture, '#workspace-reader', page.locator('#ch-1 .ptext').first());
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
      } else if (name === 'dashboard-light.png' || name === 'dashboard-dark.png') {
        // A complete opening chapter makes the entrance image a coherent
        // reading task. Use a real viewport; preserve the native shell.
        const bottom = await page.locator('#ch-1 .ptext').last().evaluate(node => node.getBoundingClientRect().bottom + scrollY);
        assert.ok(bottom < 1400, 'Reader entrance must remain a compact opening chapter');
        await page.setViewportSize({width: capture.width, height: Math.ceil(bottom + 32)});
        await save(capture.target);
      } else if (name.startsWith('dashboard-dimensions')) {
        await page.locator('#style-tab-dimensions').click();
        const before = await page.evaluate(() => captureRequests.length);
        await page.locator('#dim-chapter-select').selectOption('2');
        assert.equal(await page.locator('#dim-selection').getAttribute('data-chapter'), '2');
        if (name.includes('mobile')) await page.locator('#dim-projection').selectOption('d1-d2');
        assert.equal(await page.evaluate(() => captureRequests.length), before,
          'Chapter selection and planar projection use the existing local analysis');
        await captureThrough(capture, '#dimensions', '.dim-layout');
        await save(capture.target, '#dimensions');
      } else if (name === 'dashboard-reference.png') {
        await page.locator('#style-tab-bands').click();
        await save(capture.target, '#bands');
      } else if (name === 'dashboard-settings.png') {
        await selectView('project');
        await page.locator('#settings-thresholds > summary').click();
        await save(capture.target, '#settings-form');
      } else if (name === 'dashboard-markers.png') {
        await save(capture.target, '#markers');
      } else if (name.startsWith('dashboard-flags')) {
        await selectView('analysis');
        await save(capture.target, '#flags');
      } else if (name === 'dashboard-editorial.png') {
        await selectView('analysis');
        const paragraph = page.locator('#ch-1 .ptext').first();
        await paragraph.locator('[data-reader-paragraph]').click();
        await page.locator('[data-reader-action=values]').click();
        await paragraph.locator('[data-reader-paragraph]').click();
        await page.locator('[data-reader-action=todo]').click();
        await paragraph.locator('.marker-note').fill('Check the gate observation');
        await captureThrough(capture, '#workspace-reader-layout', paragraph);
        await save(capture.target, '#workspace-reader-layout');
      } else if (name.startsWith('dashboard-heatmap')) {
        await page.evaluate(() => {
          const rows = document.querySelectorAll('table.heatmap tbody tr');
          for (let i = 20; i < rows.length; i++) rows[i].remove();
        });
        await save(capture.target, '#heatmap');
      } else if (name === 'dashboard-layer.png') {
        await selectMetric(page, 'asl');
        assert.equal(await page.locator('#layer-legend').isVisible(), true);
        assert.ok(await page.locator('#ch-1 .ptext.metric-notable').count() > 0);
        // Frame a complete passage excerpt, not offscreen prose whose lazy
        // evidence correctly waits until it enters the reading viewport.
        const passages = page.locator('#ch-1 .ptext');
        await captureThrough(capture, '#workspace-reader-layout',
          passages.nth(Math.min(2, await passages.count() - 1)));
        await save(capture.target, '#workspace-reader-layout');
      } else if (name === 'dashboard-welcome.png') {
        await selectView('research');
        await save(capture.target);
      } else if (name === 'dashboard-project-modal.png') {
        await openProjectActions();
        await page.locator('#btn-modal-new-project').click();
        await page.locator('#tab-btn-scratch').click();
        await page.locator('#new-proj-title').fill('Harbour story');
        await saveDialog(capture.target, '#modal-project-create');
      } else if (name.startsWith('dashboard-project-settings')) {
        await selectView('project');
        await selectManuscript();
        await page.locator('#modal-project-create').waitFor({state: 'visible'});
        await page.locator('#modal-project-create .modal-close').click();
        await page.locator('#modal-project-create').waitFor({state: 'hidden'});
        assert.equal(await page.locator('#set-author-name').isVisible(), true);
        assert.equal(await page.locator('#nda-draft-form input, #nda-draft-form textarea').count(), 5);
        await save(capture.target, '#controls');
      } else if (name.startsWith('dashboard-project-import')) {
        await selectView('project');
        await selectManuscript();
        await page.locator('#import-preview-box').waitFor({state: 'visible'});
        assert.equal(await page.locator('#btn-submit-import-project').isEnabled(), true);
        await saveDialog(capture.target, '#modal-project-create');
      } else if (name.startsWith('dashboard-nda')) {
        await selectView('project');
        const fields = researchFixture['/api/nda-draft'].fields;
        for (const [key, value] of Object.entries(fields)) {
          await page.locator(`#nda-draft-form [name="${key}"]`).fill(value);
        }
        await page.locator('#nda-preview-btn').click();
        await page.locator('#nda-preview-wrap').waitFor({state: 'visible'});
        assert.equal(await page.locator('#nda-draft-preview').textContent(), researchFixture['/api/nda-draft'].text);
        await save(capture.target, '#nda-draft');
      } else if (name.startsWith('dashboard-project-open')) {
        await openProjectActions();
        await page.locator('#btn-modal-open-project').click();
        await page.locator('#open-proj-choose').click();
        await page.locator('#open-project-chooser-list button').first().waitFor();
        assert.ok(await page.locator('#modal-project-open').evaluate(element => element.scrollWidth <= element.clientWidth));
        await saveDialog(capture.target, '#modal-project-open');
      } else if (name.startsWith('dashboard-scenes')) {
        await selectView('analysis');
        await page.locator('#scenes summary').first().click();
        // Show a readable excerpt; the full sample contains many chapters.
        await page.evaluate(() => {
          document.querySelectorAll('#scenes .scene-overview tbody tr').forEach((row, index) => {
            if (index >= 3) row.remove();
          });
          document.querySelectorAll('#scenes .scene-detail').forEach((detail, index) => {
            if (index >= 3) detail.remove();
          });
        });
        await save(capture.target, '#scenes');
      } else if (name.startsWith('dashboard-research-review')) {
        await selectView('research');
        await page.locator('[data-rtab="review"]').click();
        await page.locator('#research-editorial-review .research-card').first().waitFor();
        await page.locator('#research-manuscript-review .manuscript-link-review-item').first().waitFor();
        await save(capture.target, '#research-manuscript-review-section');
      } else if (name.startsWith('dashboard-research-change-set')) {
        await selectView('research');
        await page.locator('[data-rtab="dossiers"]').click();
        await page.locator('#research-dossiers-list .research-card').first().waitFor();
        const operations = researchFixture['/api/research-revision-batch-prepare'].operations;
        for (const operation of operations) {
          await page.locator(`[data-research-revise="dossier"][data-record-id="${operation.id}"]`).click();
          await page.locator('#research-revision-field-title').fill(operation.changes.title);
          await page.locator('[name="research_revision_change_kind"][value="correction"]').check();
          await page.locator('#research-revision-reason').fill(operation.reason);
          await page.locator('#research-revision-batch-add').click();
          await page.locator('#research-revision-status').filter({hasText: 'nothing saved'}).waitFor();
          await page.keyboard.press('Escape');
        }
        await page.locator('#research-revision-batch-review').click();
        await page.locator('#research-revision-batch-apply:enabled').waitFor();
        await saveDialog(capture.target, '#modal-research-revision-batch');
      } else if (name.startsWith('dashboard-research-timeline')) {
        await selectView('research');
        await page.locator('[data-rtab="claims"]').click();
        await page.locator('#r-open-timeline').click();
        await page.waitForFunction(() => document.querySelector('#research-claims-timeline .research-timeline-strip-row'));
        if (name.includes('mobile')) {
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        }
        await save(capture.target, '#research-claims-timeline');
      } else if (name.startsWith('dashboard-research-claims')) {
        await selectView('research');
        await page.locator('[data-rtab="claims"]').click();
        await page.locator('#research-claims-list .research-card').first().waitFor();
        await page.locator('[data-load-evidence]').first().click();
        await page.locator('.claim-evidence-subpanel .research-passage-quote').first().waitFor();
        if (name.includes('mobile')) {
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        }
        await captureThrough(capture, '#research-manager', '#research-claims-list .research-card:first-child');
        await save(capture.target, '#research-manager');
      } else if (name.startsWith('dashboard-research-decisions')) {
        await selectView('research');
        await page.locator('[data-rtab="decisions"]').click();
        await page.locator('#research-decisions-list .research-card').first().waitFor();
        if (name.includes('mobile')) {
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        }
        await captureThrough(capture, '#research-manager', '#research-decisions-list .research-card:first-child');
        await save(capture.target, '#research-manager');
      } else if (name.startsWith('dashboard-research-sources') || name.startsWith('dashboard-research-dossiers') || name.startsWith('dashboard-dossier-')) {
        await selectView('research');
        const sources = name.startsWith('dashboard-research-sources');
        const kind = sources ? 'sources' : 'dossiers';
        await page.locator(`[data-rtab="${kind}"]`).click();
        if (sources) {
          assert.equal(await page.locator('#zotero-box').getAttribute('open'), null, 'Zotero capture stays optional until opened');
          assert.equal(await page.locator('#r-local-import').getAttribute('open'), null, 'Local import stays optional until opened');
        }
        await page.locator(`#research-${kind}-list .research-card`).first().waitFor();
        await settle();
        const before = await page.evaluate(() => captureRequests.length);
        await page.locator(`#r-filter-${kind}`).fill(sources ? 'customs' : 'warehouse');
        assert.equal(await page.evaluate(() => captureRequests.length), before, 'List filtering is local');
        const card = page.locator(`#research-${kind}-list .research-card:visible`).first();
        await card.locator('[data-research-detail]').click();
        await card.locator('.research-details-body .research-prose').first().waitFor();
        if (!sources) {
          for (const image of await card.locator('.dossier-image img').all()) {
            await image.scrollIntoViewIfNeeded();
            await image.evaluate(element => element.decode());
          }
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
          if (!sources) await card.locator('[data-research-detail]').click();
          await captureThrough(capture, '#research-manager', sources ? card.locator('.research-source-view-bar') : card);
          await save(capture.target, '#research-manager');
        }
      } else if (name.startsWith('dashboard-research-search')) {
        await selectView('research');
        await page.locator('[data-rtab="search"]').click();
        await page.locator('#r-search-query').fill('warehouse customs');
        await page.locator('#r-search-scope').selectOption('sources');
        await page.locator('#r-search-btn').click();
        await page.locator('#research-search-results .research-passage-card').first().waitFor();
        await save(capture.target, '#research-manager');
      } else if (name === 'cli-research.png' || name === 'cli-style.png') {
        await save(capture.target, '.win');
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
        await page.waitForTimeout(1500);
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
      if (flow === 'editorial-loop') {
        await page.waitForTimeout(1200);
        await say('Flagged passages become your review queue');
        await page.locator('#flags').scrollIntoViewIfNeeded();
        await page.waitForTimeout(1100);
        const flagRow = page.locator('#flags [data-marker-kind]').first();
        if (await flagRow.count()) {
          await flagRow.hover();
          await page.waitForTimeout(1200);
        }
        await say('Explore a passage for its values and source lines');
        await page.locator('#workbench-overview-back').click();
        const paragraph = page.locator('#ch-1 .ptext').nth(2);
        await paragraph.locator('[data-reader-paragraph]').click();
        await page.locator('[data-reader-action=values]').click();
        assert.equal(await page.locator('#reader-inspector').isVisible(), true);
        assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'false',
          'Local paragraph Values leave global Analysis Off');
        await page.waitForTimeout(1500);
        await say('Read the values, source lines and tense flags');
        await paragraph.locator('[data-reader-paragraph]').click();
        await page.locator('[data-reader-action=todo]').click();
        await paragraph.locator('.marker-note').pressSequentially('Check the closing cadence here', {delay: 60});
        await assertCaptionClear('.marker-note, [data-marker-save], [data-marker-cancel], #reader-inspector button');
        await page.waitForTimeout(1300);
        await say('Draft a note, then review existing manuscript markers');
        await page.locator('#workbench-overview-open').click();
        await page.locator('#markers').scrollIntoViewIfNeeded();
        await page.waitForTimeout(2000);
      } else if (flow === 'analysis-review') {
        await page.waitForTimeout(1300);
        await say('Read the continuous manuscript with Analysis off');
        const paragraph = page.locator('#chapters .ptext').first();
        await paragraph.scrollIntoViewIfNeeded();
        assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'false');
        await page.waitForTimeout(1500);
        await say('Explore a passage and its source lines');
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
          await say('Switch to the style dimensions for the same data');
          await dimensions.scrollIntoViewIfNeeded();
          await page.waitForTimeout(900);
          await dimensions.click();
          await page.waitForTimeout(1700);
        }
        await say('Select a chapter to keep its measured scores in view');
        await page.locator('#dim-chapter-select').selectOption('2');
        await page.locator('.dim-selection-panel').scrollIntoViewIfNeeded();
        assert.equal(await page.locator('#dim-selection').getAttribute('data-chapter'), '2');
        await page.waitForTimeout(1300);
        await say('Use a flat view to inspect the same chapter positions');
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
        await page.waitForTimeout(1300);
      } else {
        await page.waitForTimeout(1100);
        await say('The timeline places dated claims on one shared axis');
        await page.locator('[data-view="research"]').click();
        await page.locator('[data-rtab="claims"]').click();
        await page.waitForTimeout(1200);
        await page.locator('#r-open-timeline').click();
        await page.waitForFunction(() => document.querySelector('#research-claims-timeline .research-timeline-strip-row'));
        await page.waitForTimeout(750);
        const rows = page.locator('#research-claims-timeline .research-timeline-strip-row');
        const count = await rows.count();
        for (let index = 0; index < count; index++) {
          await rows.nth(index).hover();
          await page.waitForTimeout(500);
        }
        await say('Open a claim to read its card and evidence');
        await rows.first().click();
        await assertCaptionClear('#research-claims-list button, #research-claims-timeline button');
        await page.waitForTimeout(1600);
        await page.mouse.wheel(0, 300);
        await page.waitForTimeout(1700);
        await page.mouse.wheel(0, -700);
        await page.waitForTimeout(900);
        await say('Every bar links back to its claim and evidence');
        await rows.nth(Math.min(1, count - 1)).hover();
        await page.waitForTimeout(1700);
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
