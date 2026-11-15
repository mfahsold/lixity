// Capture six deliberate shots. Preparation is excluded by a decoded frame anchor.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createHash} = require('node:crypto');
const {spawnSync} = require('node:child_process');
const {performance} = require('node:perf_hooks');

const ROOT = path.resolve(__dirname, '..');
const MINIMUM_HOLD = 3;

function anchorFrame(source, requiredFrames) {
  // Read a corner of every decoded source frame, rather than guessing when
  // Playwright's first screencast frame arrived from a wall-clock stopwatch.
  const decoded = spawnSync('ffmpeg', ['-v', 'error', '-i', source, '-vf',
    'crop=2:2:0:0,scale=1:1,format=rgb24', '-f', 'rawvideo', 'pipe:1'], {maxBuffer: 16 * 1024 * 1024});
  assert.equal(decoded.status, 0, 'Frame-anchor decoding failed: ' + String(decoded.stderr));
  const pixels = decoded.stdout;
  assert.equal(pixels.length % 3, 0);
  let markers = 0, first = -1;
  for (let frame = 0; frame < pixels.length / 3; frame++) {
    const marked = pixels[frame * 3] > 240 && pixels[frame * 3 + 1] < 20 && pixels[frame * 3 + 2] > 240;
    if (marked) {
      assert.equal(first, -1, 'A recording must contain one contiguous frame anchor');
      markers++;
    } else if (markers && first === -1) first = frame;
  }
  assert.ok(markers >= 3 && first >= 0, 'The recording must contain a visible frame anchor');
  assert.ok(pixels.length / 3 - first >= requiredFrames, 'The complete shot must follow its frame anchor');
  return first;
}

async function recordProductTour({browser, capture, prepareWorkspacePage, origin}) {
  const plan = JSON.parse(fs.readFileSync(path.join(ROOT, 'docs/videos/product-tour-timing.json'), 'utf8'));
  assert.equal(plan.schema_version, 'lixity-product-tour-timing/1');
  assert.equal(plan.fps, 25);
  assert.equal(plan.duration, 48);
  assert.deepEqual(plan.scenes.map(scene => scene.id), ['read', 'passage', 'compare', 'research', 'context', 'return']);
  assert.deepEqual(plan.scenes.map(scene => [scene.start, scene.end]),
    [[0, 8], [8, 16], [16, 24], [24, 32], [32, 40], [40, 48]]);
  const directory = path.dirname(capture.videoTarget);
  const sidecar = capture.videoTarget.replace('.webm', '.json');
  // Fixed segment filenames may be replaced during this run. An old manifest
  // must never describe a mixture of old and partially recorded new footage.
  fs.rmSync(sidecar, {force: true});
  const segments = [];

  const visible = async (page, locator, label) => {
    assert.ok(await locator.evaluate(node => {
      const box = node.getBoundingClientRect();
      return box.width > 0 && box.height > 0 && box.left >= 0 && box.top >= 0 &&
        box.right <= innerWidth && box.bottom <= innerHeight;
    }), label + ' must fit inside the recorded viewport');
  };
  const proseAtTop = async locator => locator.evaluate(node => {
    const controls = document.getElementById('manuscript-reader-controls');
    const toolbar = document.querySelector('.toolbar');
    const inset = Math.max(controls ? controls.getBoundingClientRect().bottom : 0,
      toolbar ? toolbar.getBoundingClientRect().bottom : 0) + 24;
    window.scrollTo({top: scrollY + node.getBoundingClientRect().top - inset, behavior: 'instant'});
  });

  for (const scene of plan.scenes) {
    const duration = scene.end - scene.start;
    assert.equal(duration, 8);
    const frames = duration * plan.fps;
    const context = await browser.newContext({viewport: {width: capture.width, height: capture.height},
      reducedMotion: 'reduce', colorScheme: 'light', deviceScaleFactor: 2,
      recordVideo: {dir: directory, size: {width: capture.width, height: capture.height}}});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    let video;
    try {
      await prepareWorkspacePage(page, {cursor: true});
      // Product-tour fixtures are completely local; guide map captures retain
      // their existing separate network policy.
      await page.route('**/*', route => new URL(route.request().url()).origin === origin ? route.fallback() : route.abort());
      page.setDefaultTimeout(15000);
      const open = async filename => {
        await page.goto(origin + '/' + filename);
        await page.evaluate(() => document.fonts.ready);
      };
      const settle = async () => page.evaluate(() => new Promise(resolve =>
        requestAnimationFrame(() => requestAnimationFrame(resolve))));
      let target, verify, act;

      if (scene.id === 'read') {
        await open('tour-effi-briest.html');
        await page.locator('#manuscript-analysis-toggle').click();
        await page.locator('#style-layer').selectOption('sticky');
        await page.locator('#analysis-evidence-enabled').check();
        await page.locator('#analysis-comparison-enabled').uncheck();
        const paragraphId = await page.evaluate(() => Object.keys(paragraphContent).find(id => {
          const layer = paragraphContent[id][3]?.layers?.sticky;
          return layer && layer.mapped_count > 0 && paragraphContent[id][0].length < 700 && document.getElementById(id);
        }));
        assert.ok(paragraphId, 'The classic must contain mapped sticky-sentence evidence');
        await proseAtTop(page.locator('[id="' + paragraphId + '"]'));
        await page.waitForFunction(() => (CSS.highlights.get('lixity-analysis-evidence')?.size || 0) > 0);
        await page.locator('#manuscript-analysis-toggle').click();
        target = page.locator('#manuscript-analysis-toggle');
        verify = async () => {
          assert.equal(await target.getAttribute('aria-pressed'), 'true');
          await proseAtTop(page.locator('[id="' + paragraphId + '"]'));
          await page.waitForFunction(() => [...(CSS.highlights.get('lixity-analysis-evidence') || [])].some(range => {
            const rect = range.getBoundingClientRect();
            return rect.top >= 0 && rect.bottom <= innerHeight && rect.width > 0;
          }));
          assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), true);
        };
      } else if (scene.id === 'passage') {
        await open('tour-pride-prejudice.html');
        const paragraphId = await page.evaluate(() => Object.keys(paragraphContent).find(id => {
          const value = paragraphContent[id];
          return value[3]?.layers?.dialogue?.mapped_count > 0 && /[“"]/.test(value[0]) && document.getElementById(id);
        }));
        assert.ok(paragraphId, 'The dialogue scene needs an actual quoted exchange');
        await proseAtTop(page.locator('[id="' + paragraphId + '"]'));
        target = page.locator('#reader-direct-speech');
        verify = async () => {
          assert.equal(await target.getAttribute('aria-pressed'), 'true');
          await page.waitForFunction(() => [...(CSS.highlights.get('lixity-direct-speech') || [])].some(range => {
            const rect = range.getBoundingClientRect(); return rect.top >= 0 && rect.bottom <= innerHeight;
          }));
          assert.equal(await page.locator('#reader-inspector').isVisible(), false);
        };
      } else if (scene.id === 'compare') {
        const original = '# 1. The Eastern Gate\n\nThe watchman waited beside the quiet harbour. "Did you hear the bell?" she asked.\n\nHe shook his head. Fog covered the pilings.\n';
        const snapshot = {ok: true, document: 'harbour-manuscript.md', text: original,
          revision: 'tour-original', sha256: createHash('sha256').update(original).digest('hex'), recovery: []};
        await page.route('**/api/**', async route => {
          const url = new URL(route.request().url());
          if (url.pathname.endsWith('/editor-bootstrap.js') || url.pathname.endsWith('/editor-bundle.js')) {
            const asset = url.pathname.endsWith('/editor-bootstrap.js') ? 'manuscript-editor.js' : 'vendor/codemirror-editor.js';
            await route.fulfill({contentType: 'application/javascript', body: fs.readFileSync(path.join(ROOT, 'src/lixity/ui/assets', asset))});
          } else if (url.pathname === '/api/manuscript-edit') {
            assert.equal(route.request().method(), 'GET', 'An isolated comparison draft must never save the original');
            await route.fulfill({contentType: 'application/json', body: JSON.stringify(snapshot)});
          } else await route.fallback();
        });
        await open(path.basename(capture.source));
        await page.locator('#tab-view-analysis').click();
        await page.evaluate(() => {
          if (document.getElementById('manuscript-write')) return;
          const script = document.createElement('script');
          const existing = document.querySelector('script[nonce]');
          if (existing) script.nonce = existing.nonce || existing.getAttribute('nonce');
          script.src = '/api/editor-bootstrap.js'; document.body.appendChild(script);
        });
        await page.locator('#manuscript-write').click();
        await page.locator('.cm-content').waitFor({state: 'visible'});
        await page.locator('#manuscript-compare').click();
        target = page.locator('#manuscript-comparison-draft');
        await target.waitFor({state: 'visible'});
        act = async click => {
          await click(target);
          await page.keyboard.press('Control+End');
          await page.keyboard.type(' Lanterns lit.', {delay: 80});
        };
        verify = async () => {
          assert.equal(await page.locator('#manuscript-comparison-base').inputValue(), original);
          assert.equal(await page.locator('#manuscript-comparison-current').inputValue(), original);
          assert.equal(await target.inputValue(), original + ' Lanterns lit.');
          assert.equal(await page.locator('#manuscript-save-status').getAttribute('data-state'), 'saved');
          assert.equal(await page.locator('#manuscript-comparison-use').isEnabled(), true);
        };
      } else if (scene.id === 'research') {
        await open(path.basename(capture.source));
        await page.locator('#tab-view-analysis').click();
        await page.locator('#workbench-overview-open').click();
        await page.locator('#analysis-measurements').evaluate(node => {node.open = true;});
        await page.locator('#style-tab-heatmap').click();
        target = page.locator('#heatmap-ch-3 td[data-layer="asl"]');
        await target.scrollIntoViewIfNeeded();
        verify = async () => {
          assert.equal(await page.locator('#analysis-metric-context').isVisible(), true);
          assert.equal(await page.locator('#metric-context-read').getAttribute('href'), '#ch-3');
          assert.equal(await page.locator('#metric-context-values .metric-context-selected').getAttribute('data-metric-row'), 'asl');
          assert.ok((await page.locator('#metric-context-value').innerText()).match(/\d/),
            'The chapter cell must show its actual measured value');
          await visible(page, page.locator('#metric-context-chapter'), 'Selected chapter');
          await visible(page, page.locator('#metric-context-value'), 'Selected chapter measurement');
        };
      } else if (scene.id === 'context') {
        await open(path.basename(capture.source));
        await page.locator('#tab-view-research').click();
        await page.locator('[data-rtab="claims"]').click();
        await page.locator('#r-open-timeline').click();
        target = page.locator('#research-claims-timeline .research-timeline-strip-row').first();
        await target.waitFor({state: 'visible'});
        // The initial overview and timeline reads can replace the same rows.
        // Position the current row in one browser turn rather than retaining
        // an element through Playwright's multi-frame stability wait.
        await target.evaluate(node => node.scrollIntoView({block: 'center', behavior: 'instant'}));
        verify = async () => {
          assert.equal(await page.locator('#rtab-timeline').isVisible(), true);
          assert.ok(await page.locator('#research-claims-timeline .research-timeline-dated > li').evaluateAll(nodes => {
            const shown = nodes.filter(node => { const rect = node.getBoundingClientRect(); return rect.top >= 0 && rect.bottom <= innerHeight; });
            return shown.some(node => node.textContent.includes('With evidence')) &&
              shown.some(node => node.textContent.includes('Author assumption'));
          }), 'Timeline outcomes must visibly distinguish evidence labels from author assumptions');
        };
      } else {
        await open('sandbox-index.html');
        if (await page.locator('#lang-toggle').innerText() === 'EN') await page.locator('#lang-toggle').click();
        await page.locator('#preset-clear').click();
        target = page.locator('#preset-en');
        verify = async () => {
          assert.ok((await page.locator('#input').inputValue()).includes('Netherfield'));
          assert.ok(Number(await page.locator('#k-words').innerText()) > 0);
          await visible(page, page.locator('#input'), 'Sandbox passage input');
          await visible(page, page.locator('.kpis'), 'Sandbox passage results');
          await visible(page, page.locator('#privacy-pill'), 'Sandbox local-processing context');
        };
      }

      await settle();
      await visible(page, target, scene.id + ' action');
      // This annotation follows actual mouse input; it never changes product state.
      await page.addStyleTag({content: '#walkthrough-cursor{width:18px!important;height:18px!important;margin:-9px!important;transition:opacity .2s,transform .08s}'});
      await page.evaluate(() => {
        const cursor = document.getElementById('walkthrough-cursor');
        // Native dialogs live above ordinary z-index overlays. A manual popover
        // keeps the recording annotation visible during the comparison action.
        cursor.setAttribute('popover', 'manual');
        Object.assign(cursor.style, {right: 'auto', bottom: 'auto', padding: '0', overflow: 'visible'});
        cursor.showPopover();
      });
      let pointer = {x: 70, y: 820};
      await page.mouse.move(pointer.x, pointer.y);
      await page.evaluate(() => {
        const marker = document.createElement('div'); marker.id = 'tour-frame-anchor';
        // A top-layer marker also covers a native comparison dialog and its
        // backdrop. Ordinary z-index overlays would be dimmed behind it.
        marker.setAttribute('popover', 'manual');
        marker.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;max-width:none;max-height:none;margin:0;padding:0;border:0;background:#ff00ff;z-index:2147483647;pointer-events:none';
        document.body.appendChild(marker);
        marker.showPopover();
      });
      await page.waitForTimeout(280);
      await page.evaluate(() => document.getElementById('tour-frame-anchor').remove());
      const started = performance.now();
      const clicks = [];
      const click = async locator => {
        const box = await locator.boundingBox();
        assert.ok(box && box.width && box.height, 'A tour click needs a visible target');
        const destination = {x: box.x + box.width / 2, y: box.y + box.height / 2};
        assert.ok(await locator.evaluate((node, point) => node.contains(document.elementFromPoint(point.x, point.y)), destination),
          'The directed click must reach its stated control');
        // Leave room for the final browser input acknowledgement, while the
        // measured travel still has to fit the 600–900 ms presentation budget.
        const movement = Math.min(800, 600 + Math.hypot(destination.x - pointer.x, destination.y - pointer.y) / 1440 * 150);
        const movingAt = performance.now();
        while (true) {
          const progress = Math.min(1, (performance.now() - movingAt) / movement);
          const eased = (1 - Math.cos(Math.PI * progress)) / 2;
          await page.mouse.move(pointer.x + (destination.x - pointer.x) * eased, pointer.y + (destination.y - pointer.y) * eased);
          if (progress === 1) break;
          await page.waitForTimeout(20);
        }
        pointer = destination;
        const movedFor = (performance.now() - movingAt) / 1000;
        assert.ok(movedFor >= .6 && movedFor <= .9,
          'Cursor travel must retain its planned 600–900 ms pace (' + movedFor.toFixed(3) + 's)');
        await page.waitForTimeout(120);
        assert.ok(await page.locator('#walkthrough-cursor').evaluate(node => {
          const rect = node.getBoundingClientRect();
          return node.matches(':popover-open') && getComputedStyle(node).opacity === '1' &&
            rect.left >= 0 && rect.top >= 0 && rect.right <= innerWidth && rect.bottom <= innerHeight;
        }), 'The actual recorded cursor must remain visible above the active surface');
        await page.mouse.down(); await page.waitForTimeout(120); await page.mouse.up();
        clicks.push({movement: Number(movedFor.toFixed(3)), x: destination.x, y: destination.y});
      };
      await page.waitForTimeout(1000);
      const actionStart = (performance.now() - started) / 1000;
      if (act) await act(click); else await click(target);
      await verify();
      await page.evaluate(() => {document.getElementById('walkthrough-cursor').style.visibility = 'hidden';});
      await page.mouse.move(70, 820);
      await settle();
      const actionEnd = (performance.now() - started) / 1000;
      assert.ok(actionEnd <= duration - MINIMUM_HOLD, scene.id + ' action overran its readable outcome hold');
      await page.screenshot({path: path.join(directory, 'product-tour-' + scene.id + '-outcome.png')});
      await page.waitForTimeout(Math.max(0, (duration + 1) * 1000 - (performance.now() - started)));
      assert.deepEqual(errors, [], 'Product-tour scene must be free of runtime errors');
      video = page.video();
      await context.close();
      const file = 'product-tour-' + scene.id + '.webm';
      const source = path.join(directory, file);
      fs.copyFileSync(await video.path(), source);
      const startFrame = anchorFrame(source, frames);
      const sha256 = createHash('sha256').update(fs.readFileSync(source)).digest('hex');
      segments.push({id: scene.id, file, sha256, startFrame, frames, actionStart: Number(actionStart.toFixed(3)),
        actionEnd: Number(actionEnd.toFixed(3)), outcomeHold: Number((duration - actionEnd).toFixed(3)), clicks});
      console.log('Product tour ' + scene.id + ': action ends ' + actionEnd.toFixed(2) + 's; readable hold ' + (duration - actionEnd).toFixed(2) + 's');
    } catch (error) {
      if (!page.isClosed()) await page.screenshot({path: path.join(directory, 'product-tour-' + scene.id + '-failure.png')}).catch(() => {});
      throw error;
    } finally {
      if (!video) await context.close();
    }
  }
  const pendingSidecar = sidecar + '.tmp-' + process.pid;
  try {
    fs.writeFileSync(pendingSidecar, JSON.stringify({
      schema_version: 'lixity-product-tour-recording/1', fps: plan.fps, duration: plan.duration, segments,
    }, null, 2));
    fs.renameSync(pendingSidecar, sidecar);
  } finally {
    fs.rmSync(pendingSidecar, {force: true});
  }
  return segments.map(segment => ({video: segment.file, bytes: fs.statSync(path.join(directory, segment.file)).size}));
}

module.exports = {recordProductTour};
