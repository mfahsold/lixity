// Capture six deliberate shots. Preparation is excluded by a decoded frame anchor.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {createHash} = require('node:crypto');
const {spawnSync} = require('node:child_process');
const {performance} = require('node:perf_hooks');
const {startNativeServer} = require('../tests/browser/support/native-server.cjs');

const ROOT = path.resolve(__dirname, '..');
const MINIMUM_HOLD = 3;

async function startTourProject(directory) {
  return startNativeServer(`
import json
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path
from lixity.server import LixityServerHandler
from scripts.example_project import create_example_project, save_example_character_dossier

project = Path(sys.argv[1]) / 'warehouse-4'
example = create_example_project(project)
manuscript = project / 'harbour-manuscript.md'
dossier, revision = save_example_character_dossier(project, example['character_evidence_id'])
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.exports_dir = str(project / 'exports')
LixityServerHandler.language = 'en'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'dossier': dossier, 'revision': revision}), flush=True)
server.serve_forever()
`, directory);
}

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

async function recordProductTour(options) {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-tour-'));
  let server;
  try {
    server = await startTourProject(project);
    return await recordTourScenes({...options, ...server.fixture, project});
  } finally {
    if (server) await server.close();
    fs.rmSync(project, {recursive: true, force: true});
  }
}

async function recordTourScenes({browser, capture, prepareWorkspacePage, url: origin, dossier, revision, project}) {
  const plan = JSON.parse(fs.readFileSync(path.join(ROOT, 'docs/videos/product-tour-timing.json'), 'utf8'));
  assert.equal(plan.schema_version, 'lixity-product-tour-timing/1');
  assert.equal(plan.fps, 25);
  assert.equal(plan.duration, 48);
  assert.deepEqual(plan.scenes.map(scene => scene.id), ['read', 'passage', 'compare', 'chapters', 'dossier', 'pdf']);
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
      await prepareWorkspacePage(page, {cursor: true, fixtures: false});
      // Record only the disposable app. Comparison reads the unsaved text;
      // an accidental save or other write fails the recording.
      await page.route('**/*', route => {
        const request = route.request(), url = new URL(request.url());
        if (url.origin !== origin) return route.abort();
        assert.ok(request.method() !== 'POST' || url.pathname === '/api/manuscript-compare',
          'Unexpected write in the product tour: ' + url.pathname);
        return route.continue();
      });
      page.setDefaultTimeout(15000);
      const open = async () => {
        await page.goto(origin);
        await page.evaluate(() => document.fonts.ready);
      };
      const settle = async () => page.evaluate(() => new Promise(resolve =>
        requestAnimationFrame(() => requestAnimationFrame(resolve))));
      let target, verify, act;
      const dossierSummary = page.locator(`#research-dossiers-list [data-research-detail=dossier][data-record-id="${dossier}"]`);
      const dossierCard = dossierSummary.locator('..');

      if (scene.id === 'read') {
        await open();
        await page.locator('#workbench-overview-open').click();
        target = page.locator('[data-review-passage]');
        const paragraph = page.locator('#' + await target.getAttribute('data-target'));
        verify = async () => {
          await paragraph.waitFor({state: 'visible'});
          await visible(page, paragraph.locator('.ptext-inner > p'), 'Review passage reached from the overview');
        };
      } else if (scene.id === 'passage') {
        await open();
        await page.locator('#manuscript-analysis-toggle').click();
        await page.locator('#style-layer').selectOption('sticky');
        const readingMarks = page.locator('#reader-analysis-options > summary');
        await readingMarks.click();
        await page.locator('#analysis-evidence-enabled').check();
        await readingMarks.press('Enter');
        const paragraphId = await page.evaluate(() => Object.keys(paragraphContent).find(id => {
          const layer = paragraphContent[id][3]?.layers?.sticky;
          return layer && layer.mapped_count > 0 && paragraphContent[id][0].length < 500 && document.getElementById(id);
        }));
        assert.ok(paragraphId, 'Warehouse 4 must contain a short paragraph with sentence evidence');
        const paragraph = page.locator('#' + paragraphId);
        await proseAtTop(paragraph);
        target = paragraph.locator('.ptext-inner > p');
        await page.waitForFunction(id => [...(CSS.highlights.get('lixity-analysis-evidence') || [])].some(range =>
          range.startContainer.parentElement.closest('.ptext')?.id === id), paragraphId);
        act = async click => {
          const point = await page.evaluate(id => {
            const hit = [...CSS.highlights.get('lixity-analysis-evidence')].find(range =>
              range.startContainer.parentElement.closest('.ptext')?.id === id);
            const rect = hit.getClientRects()[0];
            return {x: rect.x + Math.min(20, rect.width / 2), y: rect.y + rect.height / 2};
          }, paragraphId);
          await click(target, point);
        };
        verify = async () => {
          const card = page.locator('#analysis-evidence-card');
          await card.waitFor({state: 'visible'});
          assert.ok(await card.locator('blockquote mark').count(), 'The explanation marks counted words in the exact sentence');
          await visible(page, card.locator('.analysis-evidence-explanation'), 'Why the sentence was selected and how to review it');
        };
      } else if (scene.id === 'compare') {
        const filename = path.join(project, 'warehouse-4', 'harbour-manuscript.md');
        const original = fs.readFileSync(filename, 'utf8');
        await open();
        await page.locator('#manuscript-write').click();
        await page.locator('.cm-content').waitFor({state: 'visible'});
        await page.locator('#manuscript-versions > summary').click();
        await page.locator('#manuscript-compare').click();
        target = page.locator('#manuscript-comparison-draft');
        await target.waitFor({state: 'visible'});
        act = async click => {
          await click(target);
          await target.evaluate(node => node.setSelectionRange(node.value.length, node.value.length));
          await page.keyboard.type(' Lanterns lit.', {delay: 80});
        };
        verify = async () => {
          assert.equal(await page.locator('#manuscript-comparison-base').inputValue(), original);
          assert.equal(await page.locator('#manuscript-comparison-current').inputValue(), original);
          assert.equal(await target.inputValue(), original + ' Lanterns lit.');
          const chapter = page.locator('#manuscript-comparison-chapters li').filter({hasText: '+2 words'});
          await chapter.waitFor({state: 'visible'});
          await visible(page, chapter, 'Measured chapter change');
          assert.equal(fs.readFileSync(filename, 'utf8'), original);
        };
      } else if (scene.id === 'chapters') {
        await open();
        await page.locator('#workbench-overview-open').click();
        await page.locator('[data-analysis-workflow=compare]').click();
        await page.locator('[data-analysis-section-target=style]').click();
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
      } else {
        await open();
        await page.locator('#tab-view-research').click();
        await dossierSummary.waitFor({state: 'visible'});
        await dossierSummary.evaluate(node => node.scrollIntoView({block: 'center', behavior: 'instant'}));
        const body = dossierCard.locator('.research-dossier-body-rendered');
        if (scene.id === 'dossier') {
          target = dossierSummary;
          verify = async () => {
            await body.waitFor({state: 'visible'});
            await body.locator('table').waitFor({state: 'visible'});
            assert.ok(await body.locator('blockquote').count(), 'The generated dossier keeps the quoted manuscript passages');
            await body.locator('table').evaluate(node => node.scrollIntoView({block: 'center', behavior: 'instant'}));
            await visible(page, body.locator('table thead'), 'Chapter distribution in the saved character dossier');
          };
        } else {
          await dossierSummary.click();
          target = dossierCard.locator('[data-dossier-pdf-export]');
          await target.scrollIntoViewIfNeeded();
          act = async click => {
            const downloading = page.waitForEvent('download');
            await click(target);
            const download = await downloading;
            assert.ok(download.suggestedFilename().endsWith('-v' + revision + '.pdf'));
            const bytes = fs.readFileSync(await download.path());
            assert.equal(bytes.subarray(0, 5).toString(), '%PDF-');
            assert.ok(bytes.subarray(-32).toString().includes('%%EOF'), 'Download must be a complete PDF');
          };
          verify = async () => {
            const status = dossierCard.locator('[data-dossier-pdf-status]');
            await status.getByText(/PDF download started/i).waitFor({state: 'visible'});
            await visible(page, status, 'Download confirmation');
          };
        }
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
        // Keep the screencast producing frames while the top-layer marker is
        // visible. A static backdrop can otherwise yield a single marker frame.
        marker.animate([{backgroundColor:'#ff00ff'}, {backgroundColor:'#fa08fa'}],
          {duration:120, iterations:Infinity, direction:'alternate'});
      });
      await page.waitForTimeout(500);
      await page.evaluate(() => document.getElementById('tour-frame-anchor').remove());
      const started = performance.now();
      const clicks = [];
      const click = async (locator, point) => {
        const box = await locator.boundingBox();
        assert.ok(box && box.width && box.height, 'A tour click needs a visible target');
        const destination = point || {x: box.x + box.width / 2, y: box.y + box.height / 2};
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
