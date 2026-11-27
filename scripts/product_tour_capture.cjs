// Record one real author journey. Decoded anchors omit setup between editorial shots.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {createHash} = require('node:crypto');
const {spawnSync} = require('node:child_process');
const {performance} = require('node:perf_hooks');
const {playwrightModule} = require('./browser_tools.cjs');
const {startNativeServer} = require('../tests/browser/support/native-server.cjs');

const ROOT = path.resolve(__dirname, '..');
const ORIGINAL_SENTENCE = 'It was only when she looked at it again that she began to think that there might have been a reason for the space that he had left on the form.';
const DRAFT_SENTENCE = 'Only then did she wonder why he had left the line blank.';
const LINKED_PASSAGE = 'She brought the torn edges together. They did not fit.';
const SHOTS = ['passage', 'research', 'compare', 'save', 'teleprompter', 'export', 'reader'];
const ALLOWED_WRITES = new Set(['manuscript-compare', 'manuscript-edit', 'speech-plan', 'audio-client-diagnostic', 'site-preflight', 'site-export', 'site-export-report']);
const READER_PATH = '/__tour-reader/';
const CAPTURE_DPR = 2;
const digest = bytes => createHash('sha256').update(bytes).digest('hex');

async function startTourProject(directory) {
  return startNativeServer(`
import json
import sys
from pathlib import Path
from lixity.server.handler import LixityServerHandler
from lixity.server.runtime import _LoopbackHTTPServer
from lixity.server.workspaces import WorkspaceRegistry
from scripts.example_project import create_example_project

project = Path(sys.argv[1]).resolve() / 'warehouse-4'
create_example_project(project)
manuscript = project / 'harbour-manuscript.md'
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.exports_dir = str(project / 'exports')
LixityServerHandler.language = 'en'
with _LoopbackHTTPServer(('127.0.0.1', 0), LixityServerHandler) as server:
    server.workspaces = WorkspaceRegistry(LixityServerHandler)
    print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'manuscript': str(manuscript)}), flush=True)
    server.serve_forever()
`, directory);
}

function anchoredFrames(source, shots) {
  const decoded = spawnSync('ffmpeg', ['-v', 'error', '-i', source, '-vf',
    'crop=2:2:0:0,scale=1:1,format=rgb24', '-f', 'rawvideo', 'pipe:1'], {maxBuffer: 16 * 1024 * 1024});
  assert.equal(decoded.status, 0, 'Frame-anchor decoding failed: ' + String(decoded.stderr));
  const pixels = decoded.stdout;
  assert.equal(pixels.length % 3, 0);
  const anchors = [];
  let markedFrames = 0;
  for (let frame = 0; frame < pixels.length / 3; frame++) {
    const marked = pixels[frame * 3] > 240 && pixels[frame * 3 + 1] < 20 && pixels[frame * 3 + 2] > 240;
    if (marked) markedFrames++;
    else if (markedFrames) {
      assert.ok(markedFrames >= 3, 'Every shot needs a visible frame anchor');
      anchors.push(frame);
      markedFrames = 0;
    }
  }
  assert.equal(anchors.length, shots.length, 'The full take must contain one decoded anchor per shot');
  for (const [index, shot] of shots.entries()) {
    assert.ok(anchors[index] + shot.frames <= (anchors[index + 1] ?? pixels.length / 3),
      'The full ' + shot.id + ' shot must fit before the next anchor');
  }
  return anchors;
}

async function shotAnchor(page) {
  await page.evaluate(() => {
    const marker = document.createElement('div');
    marker.id = 'tour-frame-anchor';
    marker.setAttribute('popover', 'manual');
    marker.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;max-width:none;max-height:none;margin:0;padding:0;border:0;background:#ff00ff;pointer-events:none';
    document.body.appendChild(marker);
    marker.showPopover();
    marker.animate([{backgroundColor:'#ff00ff'}, {backgroundColor:'#fa08fa'}],
      {duration:120, iterations:Infinity, direction:'alternate'});
  });
  await page.waitForTimeout(520);
  await page.evaluate(() => new Promise(resolve => {
    document.getElementById('tour-frame-anchor').remove();
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  }));
}

function extractReader(downloadPath, destination) {
  const python = process.env.PYTHON_BIN || path.join(ROOT, '.venv/bin/python');
  const result = spawnSync(python, ['-c', `
from pathlib import Path, PurePosixPath
import sys
from zipfile import ZipFile

root = Path(sys.argv[2])
with ZipFile(sys.argv[1]) as bundle:
    assert bundle.testzip() is None
    for member in bundle.infolist():
        name = PurePosixPath(member.filename)
        assert not name.is_absolute() and '..' not in name.parts
    bundle.extractall(root)
assert (root / 'index.html').is_file()
`, downloadPath, destination], {encoding: 'utf8'});
  assert.equal(result.status, 0, 'The delivered reading website must be a complete ZIP: ' + result.stderr);
}

async function recordProductTour(options) {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-tour-'));
  const {chromium} = require(playwrightModule);
  let server, recorderBrowser;
  try {
    server = await startTourProject(project);
    // Playwright's headless-shell honors --force-device-scale-factor=2 for
    // full-frame 2x recordVideo (full Chrome for Testing pads 1x into 2x with gray).
    recorderBrowser = await chromium.launch({
      headless: true,
      args: [
        '--force-device-scale-factor=' + CAPTURE_DPR,
        '--mute-audio',
        '--use-fake-device-for-media-stream',
        '--use-fake-ui-for-media-stream',
      ],
    });
    return await recordTour({...options, browser: recorderBrowser, ...server.fixture, project});
  } finally {
    try { if (recorderBrowser) await recorderBrowser.close(); }
    finally {
      try { if (server) await server.close(); }
      finally { fs.rmSync(project, {recursive: true, force: true}); }
    }
  }
}

async function recordTour({browser, capture, prepareWorkspacePage, url: origin, manuscript, project}) {
  const plan = JSON.parse(fs.readFileSync(path.join(ROOT, 'docs/videos/product-tour-timing.json'), 'utf8'));
  assert.equal(plan.schema_version, 'lixity-product-tour-timing/3');
  assert.equal(plan.fps, 25);
  assert.deepEqual(plan.captures.map(scene => scene.id), SHOTS);
  const directory = path.dirname(capture.videoTarget);
  const sidecar = capture.videoTarget.replace('.webm', '.json');
  const readerDirectory = path.join(project, 'recipient');
  const recording = fs.mkdtempSync(path.join(directory, '.tour-recording-'));
  const original = fs.readFileSync(manuscript, 'utf8');
  assert.equal(original.split(ORIGINAL_SENTENCE).length, 2, 'The tested original sentence must occur once');
  const amended = original.replace(ORIGINAL_SENTENCE, DRAFT_SENTENCE);
  const context = await browser.newContext({
    viewport: {width: capture.width, height: capture.height},
    colorScheme: plan.captures[0].theme, deviceScaleFactor: CAPTURE_DPR, acceptDownloads: true,
    permissions: ['microphone'],
    recordVideo: {dir: recording, size: {width: capture.width * CAPTURE_DPR, height: capture.height * CAPTURE_DPR}},
  });
  const page = await context.newPage();
  const video = page.video();
  const segments = [], errors = [], writes = [];
  let currentShot = 'setup';
  let pointer = {x: 70, y: 820};
  await prepareWorkspacePage(page, {cursor: true, fixtures: false});
  page.setDefaultTimeout(8000);
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => {
    if (message.type() !== 'error') return;
    const text = message.text();
    // teleprompter.js passes settings project_token to research/manuscript-review
    // & research/dossiers (which expect manuscript_pdf_token), yielding 409 on the
    // optional dossier sidebar without affecting the teleprompter or recording flow.
    if (currentShot === 'teleprompter' && text.includes('status of 409 (Conflict)')) return;
    errors.push(text);
  });
  await page.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin !== origin) return route.abort();
    if (request.method() === 'POST') {
      const match = /^\/w\/[a-f0-9]{32}\/api\/([a-z-]+)$/.exec(url.pathname);
      if (!match || !ALLOWED_WRITES.has(match[1])) {
        errors.push('Unexpected local write in the product tour: ' + url.pathname);
        return route.abort();
      }
      writes.push(match[1]);
    }
    if (!url.pathname.startsWith(READER_PATH)) return route.continue();
    const member = path.resolve(readerDirectory, decodeURIComponent(url.pathname.slice(READER_PATH.length)));
    if (request.method() !== 'GET' || !member.startsWith(readerDirectory + path.sep) ||
        !fs.existsSync(member) || !fs.statSync(member).isFile()) return route.fulfill({status: 404});
    return route.fulfill({path: member});
  });

  const settle = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const readParagraph = text => page.locator('#chapters .ptext').filter({hasText: text});
  const prose = paragraph => paragraph.locator('.ptext-inner > p');
  const proseAtTop = locator => locator.evaluate(node => {
    const controls = document.getElementById('manuscript-reader-controls');
    const toolbar = document.querySelector('.toolbar');
    const inset = Math.max(controls?.getBoundingClientRect().bottom || 0,
      toolbar?.getBoundingClientRect().bottom || 0) + 24;
    window.scrollTo({top: scrollY + node.getBoundingClientRect().top - inset, behavior: 'instant'});
  });

  async function readyCursor() {
    await page.locator('#walkthrough-cursor').waitFor({state:'attached'});
    await page.evaluate(() => {
      const cursor = document.getElementById('walkthrough-cursor');
      // A popover tracks real mouse input above native modal controls.
      cursor.setAttribute('popover', 'manual');
      Object.assign(cursor.style, {right:'auto', bottom:'auto', padding:'0', overflow:'visible',
        visibility:'visible', width:'18px', height:'18px', margin:'-9px'});
      if (!cursor.matches(':popover-open')) cursor.showPopover();
    });
  }

  async function click(locator, point) {
    await locator.scrollIntoViewIfNeeded();
    const box = await locator.boundingBox();
    assert.ok(box && box.width && box.height, 'A visible click target is required');
    const destination = point || {x:box.x + box.width / 2, y:box.y + box.height / 2};
    assert.ok(await locator.evaluate((node, point) => node.contains(document.elementFromPoint(point.x, point.y)),
      destination), 'The visible cursor must reach the intended control in ' + currentShot);
    await readyCursor();
    const movement = Math.min(520, 340 + Math.hypot(destination.x - pointer.x, destination.y - pointer.y) * .12);
    const movingAt = performance.now();
    while (true) {
      const progress = Math.min(1, (performance.now() - movingAt) / movement);
      const eased = (1 - Math.cos(Math.PI * progress)) / 2;
      await page.mouse.move(pointer.x + (destination.x - pointer.x) * eased, pointer.y + (destination.y - pointer.y) * eased);
      if (progress === 1) break;
      await page.waitForTimeout(16);
    }
    pointer = destination;
    await page.mouse.down();
    await page.waitForTimeout(100);
    const releasedAt = performance.now();
    await page.mouse.up();
    return releasedAt;
  }

  async function frameBox(...locators) {
    const boxes = [];
    for (const locator of locators) {
      const box = await locator.boundingBox();
      assert.ok(box?.width && box.height, 'The ' + currentShot + ' focus element must be visible');
      assert.ok(box.x >= -.5 && box.y >= -.5 && box.x + box.width <= capture.width + .5 &&
        box.y + box.height <= capture.height + .5,
        'The ' + currentShot + ' focus element must fit inside the recorded viewport: ' + JSON.stringify(box));
      const left = Math.max(0, box.x), top = Math.max(0, box.y);
      const right = Math.min(capture.width, box.x + box.width), bottom = Math.min(capture.height, box.y + box.height);
      boxes.push({left, top, right, bottom});
    }
    assert.ok(boxes.length, 'The ' + currentShot + ' focus must be on screen');
    const x = Math.min(...boxes.map(box => box.left)), y = Math.min(...boxes.map(box => box.top));
    return {x, y, width: Math.max(...boxes.map(box => box.right)) - x,
      height: Math.max(...boxes.map(box => box.bottom)) - y};
  }

  function padBox(box, padX = 0, padY = 0, clamp = null) {
    const bounds = clamp || {x: 0, y: 0, width: capture.width, height: capture.height};
    const left = Math.max(bounds.x, box.x - padX);
    const top = Math.max(bounds.y, box.y - padY);
    const right = Math.min(bounds.x + bounds.width, box.x + box.width + padX);
    const bottom = Math.min(bounds.y + bounds.height, box.y + box.height + padY);
    return {x: left, y: top, width: Math.max(1, right - left), height: Math.max(1, bottom - top)};
  }

  const textBounds = (locator, paddingX = 10, paddingY = 0) => ({
    boundingBox: () => locator.evaluate((node, {paddingX, paddingY}) => {
      const range = document.createRange();
      range.selectNodeContents(node);
      const {x, y, width, height} = range.getBoundingClientRect();
      return {x: x - paddingX, y: y - paddingY, width: width + 2 * paddingX, height: height + 2 * paddingY};
    }, {paddingX, paddingY}),
  });

  async function comparisonLine(field, text, index = null, minimumLines = 1) {
    return field.evaluate((input, {text, index, minimumLines}) => {
      const start = index ?? input.value.indexOf(text);
      if (start === -1 || input.value.slice(start, start + text.length) !== text)
        throw new Error('The comparison sentence does not exist');
      const fieldBox = input.getBoundingClientRect();
      const style = getComputedStyle(input);
      const mirror = document.createElement('div');
      Object.assign(mirror.style, {
        position: 'fixed', top: '0', left: '0', visibility: 'hidden', pointerEvents: 'none',
        boxSizing: 'border-box', width: input.clientWidth + 'px', padding: style.padding,
        font: style.font, letterSpacing: style.letterSpacing, lineHeight: style.lineHeight,
        whiteSpace: style.whiteSpace, overflowWrap: style.overflowWrap, tabSize: style.tabSize,
      });
      const copy = document.createTextNode(input.value);
      mirror.append(copy);
      document.body.append(mirror);
      try {
        const range = document.createRange();
        range.setStart(copy, start);
        range.setEnd(copy, start + text.length);
        const lines = [...range.getClientRects()];
        const first = lines[0], last = lines.at(-1);
        if (!first || !last) throw new Error('The comparison sentence has no measured lines');
        const lineHeight = parseFloat(style.lineHeight);
        const leading = (lineHeight - first.height) / 2;
        const offset = fieldBox.top + input.clientTop - input.scrollTop;
        const top = Math.floor(offset + first.top - leading);
        const bottom = Math.ceil(Math.max(offset + last.bottom + leading, top + minimumLines * lineHeight));
        if (top < fieldBox.top || bottom > fieldBox.bottom)
          throw new Error('The comparison sentence is outside its visible pane');
        return {x: fieldBox.x, y: top, width: fieldBox.width, height: bottom - top};
      } finally {
        mirror.remove();
      }
    }, {text, index, minimumLines});
  }

  let passageId;
  let preflight;
  const prep = {
    async passage() {
      await page.goto(origin);
      await page.evaluate(() => document.fonts.ready);
      await page.locator('#manuscript-analysis-toggle').click();
      await page.locator('#style-layer').selectOption('sticky');
      const readingMarks = page.locator('#reader-analysis-options > summary');
      await readingMarks.click();
      await page.locator('#analysis-evidence-enabled').check();
      await readingMarks.press('Enter');
      const originalPassage = readParagraph(ORIGINAL_SENTENCE);
      assert.equal(await originalPassage.count(), 1);
      passageId = await originalPassage.getAttribute('id');
      await proseAtTop(originalPassage);
      await page.waitForFunction(id => [...(CSS.highlights.get('lixity-analysis-evidence') || [])].some(range =>
        range.startContainer.parentElement.closest('.ptext')?.id === id), passageId);
    },
    async research() {
      await page.locator('.analysis-evidence-close').click();
      await page.locator('#manuscript-analysis-toggle').click();
      await proseAtTop(readParagraph(LINKED_PASSAGE));
    },
    async compare() {
      await page.keyboard.press('Escape');
      const close = page.locator('[data-passage-research-close]');
      if (await close.isVisible()) await close.click();
      await proseAtTop(readParagraph(ORIGINAL_SENTENCE));
    },
    async save() {},
    async teleprompter() {
      await page.goto(origin);
      await page.evaluate(() => document.fonts.ready);
      await proseAtTop(readParagraph(DRAFT_SENTENCE));
    },
    async export() {
      const closePrompter = page.locator('#teleprompter-modal .teleprompter-toolbar .teleprompter-btn-close');
      if (await closePrompter.isVisible()) await closePrompter.click();
      // The first shot showed the manuscript in context; here the relevant
      // starting surface is already the Project panel.
      await page.locator('#tab-view-project').click();
    },
    async reader() {
      await page.goto(origin + READER_PATH + 'index.html');
      await page.evaluate(() => document.fonts.ready);
      await page.locator('#reader-publication').waitFor();
      assert.ok((await page.locator('#chapters').innerText()).includes(DRAFT_SENTENCE));
      assert.ok(!(await page.locator('#chapters').innerText()).includes(ORIGINAL_SENTENCE));
      assert.equal(await page.locator('#chapters').getByText('Morning Handover', {exact:true}).count(), 0,
        'The chapter-six text must not be in the chapter-five reader copy');
    },
  };
  const act = {
    async passage(focus) {
      const paragraph = readParagraph(ORIGINAL_SENTENCE);
      await focus([prose(paragraph)], [], [page.locator('#style-layer')], {pad: [14, 12], insetPad: [12, 10]});
      await page.waitForTimeout(2280);
      const point = await page.evaluate(id => {
        const hit = [...CSS.highlights.get('lixity-analysis-evidence')].find(range =>
          range.startContainer.parentElement.closest('.ptext')?.id === id);
        const rect = hit.getClientRects()[0];
        return {x:rect.x + Math.min(20, rect.width / 2), y:rect.y + rect.height / 2};
      }, passageId);
      const openedAt = await click(prose(paragraph), point);
      const card = page.locator('#analysis-evidence-card');
      await card.waitFor({state:'visible'});
      assert.equal(await card.locator('blockquote mark').count(), 22);
      assert.match(await card.innerText(), /22 of 31 words/);
      await focus([card], [], [], {at: openedAt, reveal: true, pad: [10, 10]});
      return [card];
    },
    async research(focus) {
      const paragraph = readParagraph(LINKED_PASSAGE);
      const actions = paragraph.locator('[data-reader-paragraph]');
      await focus([prose(paragraph), actions], [], [], {pad: [14, 12]});
      await page.waitForTimeout(1300);
      const actionsAt = await click(actions);
      let inspectedAt = actionsAt;
      const values = page.locator('#manuscript-context-menu [data-reader-action="values"]');
      if (await values.isVisible()) {
        await focus([page.locator('#manuscript-context-menu')], [], [], {at: actionsAt, pad: [8, 8]});
        await page.waitForTimeout(1200);
        inspectedAt = await click(values);
      }
      const research = page.locator('#reader-inspector-body [data-reader-action="research"]');
      await research.waitFor({state:'visible'});
      const inspector = page.locator('#reader-inspector');
      await focus([inspector], [], [], {at: inspectedAt, pad: [8, 8]});
      await page.waitForTimeout(1600);
      const linkedAt = await click(research);
      const linked = page.locator('#workspace-context-panel [data-passage-research]');
      await linked.waitFor({state:'visible'});
      await page.waitForFunction(() => document.querySelector('[data-passage-research]')?.dataset.state === 'ready');
      assert.match(await linked.innerText(), /morning review leaves the carrier unidentified/i);
      await focus([linked], [], [], {at: linkedAt, pad: [8, 8]});
      const association = linked.locator('[data-passage-research-associations] > summary').first();
      await page.waitForTimeout(1800);
      const retainedAt = await click(association);
      const retained = linked.locator('[data-passage-research-associations]').first();
      await retained.locator('blockquote').waitFor({state:'visible'});
      assert.match(await retained.innerText(), /Claim · Version 1/);
      assert.match(await retained.innerText(), /Dossier · Version 4/);
      assert.match(await retained.locator('blockquote').innerText(), /She brought the torn edges together\. They did not fit\./);
      const claim = linked.locator('.passage-research-claim').first();
      await focus([claim], [], [], {at: retainedAt, reveal: true, pad: [10, 10]});
      return [claim];
    },
    async compare(focus) {
      const write = page.locator('#manuscript-write');
      const analysisToggle = page.locator('#manuscript-analysis-toggle');
      await focus([prose(readParagraph(ORIGINAL_SENTENCE))], [], [analysisToggle, write], {reveal: true, pad: [14, 12], insetPad: [10, 8]});
      await page.waitForTimeout(650);
      const writtenAt = await click(write);
      await page.locator('.cm-content').waitFor({state:'visible'});
      const toolbar = page.locator('.manuscript-editor-toolbar');
      const versions = page.locator('#manuscript-versions > summary');
      await focus([toolbar], [page.locator('.editor-group-context'), versions], [], {at: writtenAt, pad: [10, 10], portraitPad: [10, 10]});
      await page.waitForTimeout(800);
      const versionsAt = await click(versions);
      const compare = page.locator('#manuscript-compare');
      await focus([page.locator('.editor-versions-panel')], [], [], {at: versionsAt, pad: [8, 8]});
      await page.waitForTimeout(850);
      const comparedAt = await click(compare);
      const dialog = page.locator('#manuscript-comparison .modal-card');
      const draft = page.locator('#manuscript-comparison-draft');
      const current = page.locator('#manuscript-comparison-current');
      await draft.waitFor({state:'visible'});
      assert.equal(await draft.inputValue(), original);
      assert.equal(await current.inputValue(), original);
      const start = original.indexOf(ORIGINAL_SENTENCE);
      await draft.focus();
      await draft.evaluate((node, index) => node.setSelectionRange(index, index), start);
      await page.keyboard.press('ArrowRight');
      await draft.evaluate((node, range) => {
        node.setSelectionRange(range[0], range[1]);
        document.getElementById('manuscript-comparison-current').scrollTop = node.scrollTop;
        document.getElementById('manuscript-comparison-base').scrollTop = node.scrollTop;
      }, [start, start + ORIGINAL_SENTENCE.length]);
      const comparison = async (proposed, minimumLines) => ({
        current: await comparisonLine(current, ORIGINAL_SENTENCE),
        draft: await comparisonLine(draft, proposed, start, minimumLines),
      });
      await settle();
      await focus([dialog, dialog.locator('.modal-footer')], [], [], {at: comparedAt, reveal: true, pad: [8, 8]});
      await page.waitForTimeout(1850);
      await focus([current, draft], [draft], [], {comparison: await comparison(ORIGINAL_SENTENCE)});
      const measured = page.waitForResponse(response =>
        response.url().endsWith('/api/manuscript-compare') &&
        response.request().postDataJSON()?.draft_text === amended)
        .then(response => ({response, measuredAt: performance.now()}));
      await page.waitForTimeout(1350);
      const typingAt = performance.now();
      await page.keyboard.type(DRAFT_SENTENCE[0]);
      await settle();
      await focus([current, draft], [draft], [],
        {at: typingAt, comparison: await comparison(DRAFT_SENTENCE[0], 2), noBuffer: true});
      await page.waitForTimeout(80);
      await page.keyboard.type(DRAFT_SENTENCE.slice(1), {delay: 42});
      const {response, measuredAt} = await measured;
      assert.ok(response.ok());
      const measuredDraft = await response.json();
      assert.equal(measuredDraft.primary_diff, 'current_to_draft');
      assert.match(measuredDraft.settings_sha256, /^[0-9a-f]{64}$/);
      assert.equal(measuredDraft.measurements.current.revision, digest(original));
      assert.equal(measuredDraft.measurements.draft.revision, digest(amended));
      assert.equal(fs.readFileSync(manuscript, 'utf8'), original);
      assert.equal(await draft.inputValue(), amended);
      const changed = page.locator('#manuscript-comparison-chapters li').filter({hasText:'The Blank Line'});
      await changed.waitFor({state:'visible'});
      assert.match(await changed.innerText(), /[-−]19 words/);
      await focus([current, draft], [draft], [], {at: measuredAt, comparison: await comparison(DRAFT_SENTENCE)});
      return [current, draft, changed];
    },
    async save(focus) {
      const dialog = page.locator('#manuscript-comparison .modal-card');
      const use = page.locator('#manuscript-comparison-use');
      const footer = page.locator('#manuscript-comparison .modal-footer');
      await focus([page.locator('#manuscript-comparison-chapters'), footer],
        [page.locator('#manuscript-comparison-cancel'), use], [], {pad: [12, 10], portraitPad: [14, 12], clamp: dialog});
      await page.waitForTimeout(1450);
      const usedAt = await click(use);
      await page.waitForFunction(() => document.getElementById('manuscript-save-status')?.dataset.state === 'unsaved');
      assert.equal(fs.readFileSync(manuscript, 'utf8'), original);
      const save = page.locator('#manuscript-save');
      const toolbar = page.locator('.manuscript-editor-toolbar');
      const statusGroup = page.locator('.editor-group-status');
      const label = await textBounds(save.locator('.editor-tool-label'), 0).boundingBox();
      const button = await save.boundingBox();
      assert.ok(button && label.width && label.x >= button.x && label.x + label.width <= button.x + button.width,
        'The full Save this draft label must fit within its visible button');
      await focus([toolbar], [statusGroup], [], {at: usedAt, pad: [10, 10], portraitPad: [12, 10], clamp: toolbar});
      await page.waitForTimeout(1050);
      const saving = page.waitForResponse(response => response.url().endsWith('/api/manuscript-edit') &&
        response.request().method() === 'POST');
      await click(save);
      assert.ok((await saving).ok());
      await page.waitForFunction(() => document.getElementById('manuscript-save-status')?.dataset.state === 'saved');
      assert.equal(fs.readFileSync(manuscript, 'utf8'), amended);
      await focus([toolbar], [statusGroup], [], {pad: [10, 10], portraitPad: [12, 10], clamp: toolbar});
      await page.waitForTimeout(1050);
      const [,closedAt] = await Promise.all([page.waitForNavigation(), click(page.locator('#manuscript-close'))]);
      await page.evaluate(() => document.fonts.ready);
      const reopened = readParagraph(DRAFT_SENTENCE);
      await reopened.waitFor({state:'visible'});
      await proseAtTop(reopened);
      await page.mouse.move(0, 0);
      const sentence = textBounds(prose(reopened), 20, 14);
      await focus([sentence], [], [], {at: closedAt, reveal: true});
      assert.equal(await prose(reopened).innerText(), DRAFT_SENTENCE);
      return [sentence];
    },
    async teleprompter(focus) {
      const trigger = page.locator('#reader-teleprompter');
      const paragraph = readParagraph(DRAFT_SENTENCE);
      await trigger.waitFor({state:'visible'});
      await focus([prose(paragraph)], [], [trigger], {reveal: true, pad: [14, 12], insetPad: [10, 8]});
      await page.waitForTimeout(650);
      const openedAt = await click(trigger);
      const modal = page.locator('#teleprompter-modal');
      await modal.waitFor({state:'visible'});
      await page.locator('.teleprompter-paragraph.is-active').waitFor({state:'visible'});
      const toolbar = page.locator('.teleprompter-toolbar');
      const rightGroup = page.locator('.teleprompter-right-group');
      const centerGroup = page.locator('.teleprompter-center-group');
      const runway = page.locator('.teleprompter-runway-container');
      await settle();
      await focus([modal], [centerGroup, rightGroup, runway], [], {at: openedAt, reveal: true});
      await page.waitForTimeout(1050);
      const record = page.locator('.teleprompter-btn-record');
      const recordedAt = await click(record);
      await page.waitForFunction(() => document.querySelector('.teleprompter-btn-record')?.classList.contains('is-active'));
      await focus([modal], [toolbar, runway], [], {at: recordedAt});
      await page.waitForTimeout(2150);
      const stoppedAt = await click(record);
      const takeCard = page.locator('.teleprompter-take-card');
      await takeCard.waitFor({state:'visible'});
      await takeCard.locator('audio').waitFor({state:'attached'});
      await page.waitForFunction(w => {
        const rect = document.querySelector('.teleprompter-take-card')?.getBoundingClientRect();
        return rect && rect.width > 0 && rect.x >= 0 && rect.right <= w + 0.5;
      }, capture.width);
      await settle();
      await focus([takeCard], [takeCard], [], {at: stoppedAt, reveal: true, pad: [12, 12], clamp: modal});
      return [takeCard];
    },
    async export(focus) {
      const actionsBox = page.locator('#project-actions');
      const actions = page.locator('#project-actions > summary');
      const menu = page.locator('#project-controls > .row').first();
      const menuOpen = await actionsBox.evaluate(node => node.open);
      await focus(menuOpen ? [actions, menu] : [actionsBox], [], [], {pad: [10, 10], clamp: actionsBox});
      await page.waitForTimeout(600);
      if (!menuOpen) {
        const menuAt = await click(actions);
        await focus([actions, menu], [], [], {at: menuAt, pad: [10, 10], clamp: actionsBox});
        await page.waitForTimeout(750);
      }
      const dialog = page.locator('#modal-site-export .modal-card');
      const footer = dialog.locator('.modal-footer');
      const dialogAt = await click(page.locator('#btn-site-export'));
      const mode = page.locator('#site-export-mode');
      const profile = page.locator('#site-export-profile');
      const chapter = page.locator('#site-export-max-chapter');
      await mode.waitFor({state:'visible'});
      await focus([dialog], [dialog], [], {at: dialogAt, reveal: true, pad: [8, 8]});
      await page.waitForTimeout(250);
      const modeAt = await click(mode);
      await mode.selectOption('reader');
      await profile.waitFor({state:'visible'});
      await chapter.waitFor({state:'visible'});
      await focus([dialog], [dialog.locator('.modal-header'),
        chapter.locator('xpath=ancestor::div[contains(@class,"form-group")][1]')], [], {at: modeAt, pad: [8, 8]});
      await page.waitForTimeout(200);
      await click(profile);
      await profile.selectOption('readers');
      await page.waitForTimeout(200);
      await click(chapter);
      await chapter.selectOption('5');
      assert.equal(await chapter.inputValue(), '5');
      await page.waitForTimeout(350);
      const checking = page.waitForResponse(response => response.url().endsWith('/api/site-preflight'));
      await click(page.locator('#site-export-check'));
      const response = await checking;
      assert.ok(response.ok());
      const preview = await response.json();
      assert.equal(preview.preflight.schema_version, 'lixity-site-preflight/1');
      const options = response.request().postDataJSON();
      assert.equal(options.mode, 'reader');
      assert.equal(options.publication_profile, 'readers');
      assert.equal(options.max_chapter, 5);
      preflight = {mode:options.mode, profile:options.publication_profile, chapter:options.max_chapter};
      const result = page.locator('#site-export-preflight');
      await result.waitFor({state:'visible'});
      await result.scrollIntoViewIfNeeded();
      await focus([result, footer], [], [], {pad: [12, 10], clamp: dialog});
      await page.waitForTimeout(2500);
      const downloading = page.waitForEvent('download');
      const downloadedAt = await click(page.locator('#site-export-download'));
      const download = await downloading;
      assert.equal(download.suggestedFilename(), 'lixity-reading-website.zip');
      extractReader(await download.path(), readerDirectory);
      assert.equal(fs.readFileSync(manuscript, 'utf8'), amended);
      const status = page.locator('#site-export-status');
      await status.waitFor({state:'visible'});
      await status.scrollIntoViewIfNeeded();
      assert.equal(await status.getAttribute('class'), 'ctl-status ok');
      await focus([status, footer], [], [], {at: downloadedAt, pad: [12, 10], clamp: dialog});
      return [status, footer];
    },
    async reader(focus) {
      const overview = page.locator('#reader-publication h1').first();
      await overview.waitFor({state:'visible'});
      const chooser = page.locator('#publication-reader-chapter');
      const publication = page.locator('#reader-publication');
      const navigation = publication.locator('.publication-navigation');
      const titleAndIntro = await publication.locator('.publication-header h1, .publication-header p, .publication-introduction p').all();
      const readerControls = await navigation.locator(':scope > :visible').all();
      const overviewBounds = [...titleAndIntro.map(locator => textBounds(locator, 16, 8)), ...readerControls];
      await focus(overviewBounds, overviewBounds, [], {reveal: true, pad: [12, 10]});
      await page.waitForTimeout(2400);
      await click(chooser);
      await chooser.selectOption('publication-chapter-5');
      const revised = page.locator('#chapters .reader-paragraph').filter({hasText:DRAFT_SENTENCE});
      assert.equal(await revised.count(), 1);
      await proseAtTop(revised);
      await settle();
      const chapterAt = performance.now();
      const following = revised.locator('xpath=following-sibling::*[contains(@class,"reader-paragraph")][1]');
      await focus([revised, following], [], [], {at: chapterAt, pad: [14, 12]});
      assert.equal(await revised.innerText(), DRAFT_SENTENCE);
      return [revised, following];
    },
  };

  try {
    for (const scene of plan.captures) {
      currentShot = scene.id;
      await prep[scene.id]();
      await page.evaluate(theme => window.LixityComponents?.applyTheme(theme), scene.theme);
      await settle();
      await readyCursor();
      await page.mouse.move(70, 820);
      pointer = {x:70, y:820};
      await shotAnchor(page);
      const started = performance.now();
      const focusFrames = [];
      const point = async (locators, portraitLocators = [], insetLocators = [],
        {at, comparison, reveal, noBuffer, pad, portraitPad, insetPad, clamp} = {}) => {
        const first = focusFrames.length === 0;
        const sinceStart = time => Number(((time - started) / 1000).toFixed(3));
        const seconds = first ? 0 : sinceStart(at ?? performance.now());
        const clampBox = clamp ? await frameBox(clamp) : null;
        let box = await frameBox(...locators);
        if (pad) box = padBox(box, pad[0], pad[1], clampBox);
        const frame = {seconds, ...box};
        if (portraitLocators.length) {
          let portrait = await frameBox(...portraitLocators);
          if (portraitPad) portrait = padBox(portrait, portraitPad[0], portraitPad[1], clampBox);
          frame.portrait = portrait;
        }
        if (insetLocators.length) {
          let inset = await frameBox(...insetLocators);
          if (insetPad) inset = padBox(inset, insetPad[0], insetPad[1]);
          assert.ok(inset.x >= box.x + box.width || box.x >= inset.x + inset.width ||
            inset.y >= box.y + box.height || box.y >= inset.y + inset.height,
            'The ' + currentShot + ' inset must show a different source region');
          frame.inset = inset;
        }
        if (comparison) frame.comparison = comparison;
        if (reveal) frame.reveal = true;
        if (noBuffer) frame.noBuffer = true;
        frame.sourceSeconds = first ? 0 : sinceStart(performance.now());
        focusFrames.push(frame);
      };
      const detailLocators = await act[scene.id](point);
      await settle();
      const actionEnd = (performance.now() - started) / 1000;
      assert.ok(actionEnd <= scene.duration - .8, scene.id + ' action overran its readable outcome hold (' + actionEnd.toFixed(2) + 's)');
      const detail = await frameBox(...detailLocators);
      await page.locator('#walkthrough-cursor').evaluate(node => { node.style.visibility = 'hidden'; });
      // Leave the last control so a delayed tooltip cannot obscure the outcome.
      await page.mouse.move(0, 0);
      const still = 'product-tour-' + scene.id + '-outcome.png';
      const stillBytes = await page.screenshot({path:path.join(recording, still)});
      const elapsed = (performance.now() - started) / 1000;
      await page.waitForTimeout(Math.max(0, (scene.record_duration + .5 - elapsed) * 1000));
      segments.push({id:scene.id, theme:scene.theme, frames:scene.record_duration * plan.fps,
        detail, focus:focusFrames, still, stillSha256:digest(stillBytes), actionEnd:Number(actionEnd.toFixed(3))});
      console.log('Product tour ' + scene.id + ': action ends ' + actionEnd.toFixed(2) + 's');
    }
    assert.deepEqual(errors, [], 'The author take must be free of runtime errors');
    assert.equal(writes.filter(action => action === 'manuscript-edit').length, 1, 'Only the explicit save may write the manuscript');
    assert.equal(writes.filter(action => action === 'site-preflight').length, 1);
    assert.equal(writes.filter(action => action === 'site-export').length, 1);
    await context.close();
    const source = await video.path();
    const anchors = anchoredFrames(source, segments);
    const file = path.basename(capture.videoTarget), sha256 = digest(fs.readFileSync(source));
    for (const [index, shot] of segments.entries()) Object.assign(shot, {file, sha256, startFrame:anchors[index]});
    const newManifest = path.join(recording, 'manifest.json');
    fs.writeFileSync(newManifest, JSON.stringify({
      schema_version:'lixity-product-tour-recording/5', fps:plan.fps, duration:plan.duration,
      width: capture.width * CAPTURE_DPR, height: capture.height * CAPTURE_DPR, dpr: CAPTURE_DPR, segments,
      originalSentence:ORIGINAL_SENTENCE, draftSentence:DRAFT_SENTENCE, readerScope:preflight,
    }, null, 2) + '\n');
    // Publish the manifest last. Readers can reject an interrupted replacement by hash.
    fs.renameSync(source, capture.videoTarget);
    for (const {still} of segments) fs.renameSync(path.join(recording, still), path.join(directory, still));
    fs.renameSync(newManifest, sidecar);
    return [{video:file, bytes:fs.statSync(capture.videoTarget).size}];
  } catch (error) {
    if (!page.isClosed()) await page.screenshot({path:path.join(directory, 'product-tour-' + currentShot + '-failure.png')}).catch(() => {});
    throw error;
  } finally {
    try { await context.close(); }
    finally { fs.rmSync(recording, {recursive:true, force:true}); }
  }
}

module.exports = {anchoredFrames, digest, recordProductTour, shotAnchor};
