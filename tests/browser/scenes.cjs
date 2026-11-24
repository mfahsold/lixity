const {openAnalysisSection} = require('./support/analysis-workflow.cjs');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-scenes-ui-'));
const fixtures = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
import json, sys
from pathlib import Path
from lixity import api
narration = 'The lamps stood quietly against the tall windows. ' * 12
exchanges = '"One two three four five six seven eight." ' * 12
speech = '"' + ('one two three four five six seven eight ' * 12).strip() + '."'
text = ('## Sample <svg onload="window.injected=1">\\n\\n' + narration + '\\n\\n' + exchanges
        + '\\n\\n---\\n\\n' + narration + '\\n\\n' + speech)
settings = {'scene_analysis': {'assignments': {'1:1': '<b>close</b>', '1:2': 'formal', '3:1': 'formal'},
    'planned': ['3:1'],
    'groups': {'<b>close</b>': {'targets': {'asl': [2, 6]}}, 'formal': {'targets': {'hd_d': [0.2, 0.8]}}}}}
languages = ('de', 'en', 'fr', 'es', 'it', 'pt', 'nl')
pending = {'scene_analysis': {'assignments': {'2:1': '<b>planned</b>'},
    'planned': ['2:1'], 'groups': {'<b>planned</b>': {}}}}
documents = {}
for kind, source, config in (('measured', text, settings),
                             ('planned', '## Draft\\n\\nA quiet draft starts here.', pending)):
    documents[kind] = {}
    for language in languages:
        target = Path(sys.argv[1]) / f'{kind}-{language}.html'
        target.write_text(api.dashboard(source, language=language, project_config=config), encoding='utf-8')
        documents[kind][language] = str(target)
print(json.dumps(documents))
`, artifacts], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8', maxBuffer: 1024*1024});
assert.equal(fixtures.status, 0, fixtures.error || fixtures.stderr);
const documents = JSON.parse(fixtures.stdout);

(async () => {
  const browser = await launchChromium();
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let document;
    await page.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: document}));
    for (const [language, filename] of Object.entries(documents.measured)) {
      document = fs.readFileSync(filename, 'utf8');
      for (const width of [1440, 320]) {
        await page.setViewportSize({width, height: 900});
        await page.goto('http://lixity.test/');
        assert.equal(await page.locator('#scenes .scene-detail').count(), 2);
        assert.equal(await page.locator('#scenes .scene-planned').count(), 1);
        assert.equal(await page.locator('#scenes svg, #scenes b').count(), 0);
        assert.equal(await page.evaluate(() => window.injected), undefined);
        const rows = page.locator('#scenes .scene-overview tbody tr');
        assert.deepEqual(await rows.evaluateAll(elements => elements.map(row => row.dataset.sceneRow)), ['1:1', '1:2']);
        assert.equal(await page.locator('#scenes .scene-overview [data-claim-level="L0"]').count(), 2);
        assert.deepEqual(await rows.locator('td:first-of-type .scene-track > span:last-child').allTextContents(),
          language === 'en' ? ['50.0%', '50.0%'] : ['50,0 %', '50,0 %'],
          'Equal quoted-word shares remain equal on the measured track');
        const measurements = page.locator('#scenes > .scene-measurements');
        assert.equal(await measurements.getAttribute('open'), null);
        assert.equal(await page.locator('#scenes .scene-detail summary').first().isVisible(), false);
        const link = page.locator('#scenes .scene-overview a').first();
        await link.focus();
        await page.keyboard.press('Enter');
        assert.equal(await page.evaluate(() => document.activeElement.id), 'scene-evidence-1-1',
          'Opening a scene transfers keyboard focus to the evidence');
        assert.equal(await measurements.getAttribute('open'), '');
        assert.equal(await page.locator('#scenes .scene-detail[open]').count(), 1);
        const evidence = page.locator('#scenes .scene-detail[open] .scene-evidence');
        assert.deepEqual(await evidence.locator('[data-claim-level]').evaluateAll(elements =>
          elements.map(element => element.dataset.claimLevel)), ['L0', 'L2', 'L1', 'L3']);
        assert.deepEqual(await evidence.locator('.scene-block-counts strong').allTextContents(), ['12', '0', '0']);
        assert.equal(await page.locator('#scenes .scene-detail[open] tbody tr').count(), 16);
        for (const cell of await page.locator('#scenes .scene-detail[open] td, #scenes .scene-detail[open] thead th:not(:first-child)').all()) {
          assert.ok(await cell.evaluate(element => {
            const range = document.createRange();
            range.selectNodeContents(element);
            // Inline sample counts contribute multiple rectangles on the same
            // baseline. Real wrapping separates their vertical text bands.
            const rects = Array.from(range.getClientRects()).filter(rect => rect.width && rect.height);
            return rects.length > 0 && Math.max(...rects.map(rect => rect.top)) < Math.min(...rects.map(rect => rect.bottom));
          }), 'Values and comparison headers stay on one readable line');
        }
        const wrap = page.locator('#scenes .scene-detail[open] .table-wrap');
        assert.equal(await wrap.getAttribute('tabindex'), '0');
        if (width === 320) {
          assert.ok(await wrap.evaluate(el => el.scrollWidth > el.clientWidth));
          await wrap.focus();
          await page.keyboard.press('ArrowRight');
          await page.waitForFunction(() => document.querySelector('#scenes .scene-detail[open] .table-wrap').scrollLeft > 0);
        }
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), language + ' ' + width);
        assert.ok(!await page.locator('#scenes').textContent().then(text => /scene_(support|value|range|guidance)|panel_scenes|\{min_tokens\}/.test(text)));
        await page.locator('#scenes').screenshot({path: path.join(artifacts, `${language}-${width}.png`)});
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('#scenes .scene-detail[open]').count(), 0);
        assert.equal(await measurements.getAttribute('open'), '');
        assert.equal(await page.locator('#scenes .scene-detail summary').first().evaluate(el => el === document.activeElement), true);
        await page.keyboard.press('Escape');
        assert.equal(await measurements.getAttribute('open'), null);
        assert.equal(await measurements.locator(':scope > summary').evaluate(el => el === document.activeElement), true);
        await link.focus(); await page.keyboard.press('Enter');
        await page.keyboard.press('Tab');
        assert.equal(await page.evaluate(() => document.activeElement.getAttribute('href')), '#ch-1',
          'Tab from the evidence reaches the corresponding manuscript chapter');
        await page.keyboard.press('Tab');
        assert.equal(await page.evaluate(() => document.activeElement.id), 'scene-metrics-1-1');
        await page.keyboard.press('Tab');
        assert.equal(await page.locator('#scenes .scene-detail[data-scene="1:2"] > summary')
          .evaluate(el => el === document.activeElement), true,
        'Tab continues from the opened measurements to the next scene summary');
        await page.keyboard.press('Shift+Tab');
        assert.equal(await page.evaluate(() => document.activeElement.id), 'scene-metrics-1-1');
        await page.keyboard.press('Escape'); await page.keyboard.press('Escape');
        // The ordinary href reveals nested measurements without application JavaScript.
        const context = await browser.newContext({javaScriptEnabled: false, viewport: {width, height: 900}});
        try {
          const plain = await context.newPage();
          await plain.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: document}));
          await plain.goto('http://lixity.test/');
          await plain.locator('#scenes .scene-overview a').last().click();
          assert.equal(await plain.locator('#scenes > .scene-measurements').getAttribute('open'), '');
          assert.equal(await plain.locator('#scenes .scene-detail[data-scene="1:2"]').getAttribute('open'), '');
          assert.equal(await plain.locator('#scene-metrics-1-2 table').isVisible(), true);
          assert.deepEqual(await plain.locator('#scenes .scene-detail[open] .scene-block-counts strong').allTextContents(),
            ['0', '0', '1'], 'The same quoted-word share can describe one long block');
        } finally { await context.close(); }
      }
    }
    for (const [language, filename] of Object.entries(documents.planned)) {
      document = fs.readFileSync(filename, 'utf8');
      for (const width of [1440, 320]) for (const theme of ['light', 'dark']) {
        await page.setViewportSize({width, height: 900});
        await page.emulateMedia({colorScheme: theme, reducedMotion: 'reduce'});
        await page.goto('http://lixity.test/');
        const plans = page.locator('#scenes .scene-planned');
        const summary = plans.locator('summary');
        assert.equal(await plans.locator('table, [data-jump], b').count(), 0,
          'Plans have no fabricated measurements or nonexistent chapter links');
        await summary.focus();
        await page.keyboard.press('Enter');
        assert.equal(await plans.getAttribute('open'), '');
        assert.equal(await plans.locator('li').textContent(), '2:1 · <b>planned</b>');
        assert.equal(await plans.locator('p').isVisible(), true);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        const bounds = await plans.boundingBox();
        assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= width + 1);
        await page.locator('#scenes').screenshot({path: path.join(artifacts, `planned-${language}-${width}-${theme}.png`)});
        await page.keyboard.press('Enter');
        assert.equal(await plans.getAttribute('open'), null, 'The same control collapses plans');
        assert.equal(await summary.evaluate(element => element === document.activeElement), true);
      }
    }
    await nativeLongScenes(browser);
    assert.deepEqual(errors, []);
    console.log('Scenes: ordered evidence, keyboard details, seven locales, and local intent rehearsal passed. ' + artifacts);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});

async function nativeLongScenes(browser) {
  const directory = path.join(artifacts, 'native-project');
  fs.mkdirSync(directory);
  const server = await startNativeServer(String.raw`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
project = Path(sys.argv[1])
manuscript = project / 'manuscript.md'
chapters = []
for number in range(1, 15):
    scenes = ['A door closed. The garden waited in the rain. ' * 25
              for _ in range(2 if number <= 5 else 1)]
    chapters.append(f'## Synthetic chapter {number}: The river garden\n\n' + '\n\n---\n\n'.join(scenes))
manuscript.write_text('\n\n'.join(chapters), encoding='utf-8')
(project / 'lixity.toml').write_text('title = "Synthetic scene navigation"\nlanguage = "en"\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}'}), flush=True)
server.serve_forever()
`, directory);
  const original = fs.readFileSync(path.join(directory, 'manuscript.md'));
  const page = await browser.newPage({reducedMotion: 'reduce'});
  const errors = [], writes = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (!['GET', 'HEAD'].includes(request.method())) writes.push(request.method()); });
  try {
    for (const width of [1440, 320]) {
      await page.setViewportSize({width, height: 900});
      await page.goto(server.fixture.url);
      assert.match(await page.title(), /Synthetic scene navigation/);
      await page.locator('#workbench-overview-open').click();
      await openAnalysisSection(page, 'scenes');
      const catalogue = page.locator('#scenes > .scene-measurements');
      assert.equal(await catalogue.getAttribute('open'), null);
      assert.equal(await page.locator('#scenes .scene-overview tbody tr').count(), 19);
      assert.equal(await catalogue.locator('.scene-detail').count(), 19);
      assert.equal(await catalogue.locator('.scene-detail summary').first().isVisible(), false);
      const overview = page.locator('#scenes .scene-overview');
      assert.equal(await overview.evaluate(element => element.clientHeight <= 416), true,
        'The complete scene overview stays inside the shared bounded table region');
      await overview.focus();
      let pageDowns = 0;
      while (pageDowns < 12 && !await overview.evaluate(element =>
        element.scrollTop + element.clientHeight >= element.scrollHeight - 1)) {
        await overview.evaluate(element => {
          element.dataset.testScrollEnded = 'false';
          element.addEventListener('scrollend', () => { element.dataset.testScrollEnded = 'true'; }, {once: true});
        });
        await page.keyboard.press('PageDown');
        await page.waitForFunction(() => document.querySelector('#scenes .scene-overview').dataset.testScrollEnded === 'true');
        pageDowns++;
      }
      assert.ok(pageDowns > 0, 'Keyboard PageDown scrolls the scene overview itself');
      assert.equal(await overview.evaluate(element => {
        const box = element.getBoundingClientRect(), last = element.querySelector('tbody tr:last-child').getBoundingClientRect();
        return last.bottom <= box.bottom + 1 && last.top >= box.top - 1;
      }), true, 'Keyboard scrolling reaches the complete final scene row');
      assert.ok(await overview.evaluate(element => {
        const first = element.querySelector('tbody tr');
        return Math.abs(first.getBoundingClientRect().top - first.cells[0].getBoundingClientRect().top) < 1;
      }), 'Scene names scroll vertically with their values');
      await overview.evaluate(element => { element.scrollTop = 0; element.scrollLeft = element.scrollWidth; });
      assert.equal(await overview.evaluate(element => {
        const box = element.getBoundingClientRect(), identity = element.querySelector('tbody th').getBoundingClientRect();
        return identity.left >= box.left - 1 && identity.right <= box.right + 1 &&
          identity.top >= box.top - 1 && identity.bottom <= box.bottom + 1;
      }), true, 'The scene identity remains fully visible after horizontal scrolling');
      const identityWidth = await overview.locator('tbody th').first().evaluate(element => element.getBoundingClientRect().width);
      assert.ok(identityWidth <= (width === 320 ? 160 : 240),
        `The identity column leaves space for measured values (${width}px viewport, ${identityWidth}px identity)`);
      assert.ok(await overview.locator('tbody th').first().evaluate(cell => {
        const bounds = cell.getBoundingClientRect(), range = document.createRange();
        range.selectNodeContents(cell.querySelector('a'));
        return Array.from(range.getClientRects(), rect => rect.left >= bounds.left && rect.right <= bounds.right)
          .every(Boolean);
      }), 'Scene titles wrap inside the pinned column without covering measurements');
      assert.equal(await overview.locator('tbody tr').count(), 19, 'Scrolling preserves every scene row');
      await page.locator('#scenes').screenshot({path: path.join(artifacts, `native-${width}-closed.png`)});
      const firstLink = page.locator('#scenes .scene-overview a').first();
      await firstLink.focus(); await page.keyboard.press('Enter');
      assert.equal(await catalogue.getAttribute('open'), '');
      assert.equal(await page.locator('#scene-metrics-1-1 table').isVisible(), true);
      assert.equal(await page.evaluate(() => document.activeElement.id), 'scene-evidence-1-1',
        'Native scene navigation keeps keyboard focus at the visible evidence');
      await page.keyboard.press('Escape');
      assert.equal(await catalogue.locator('.scene-detail[open]').count(), 0);
      assert.equal(await catalogue.locator('.scene-detail[data-scene="1:1"] > summary')
        .evaluate(el => el === document.activeElement), true);
      await page.keyboard.press('Escape');
      assert.equal(await catalogue.getAttribute('open'), null);
      assert.equal(await catalogue.locator(':scope > summary').evaluate(el => el === document.activeElement), true);
      await page.locator('#scenes .scene-overview a').last().click();
      assert.equal(await page.locator('#scene-metrics-14-1 table').isVisible(), true);
      await page.locator('#scene-metrics-14-1').scrollIntoViewIfNeeded();
      await page.locator('#scene-metrics-14-1').screenshot({path: path.join(artifacts, `native-${width}-last-scene.png`)});
      // Every scene has real measurements, and opening one never closes another.
      for (const detail of await catalogue.locator('.scene-detail').all()) {
        await detail.locator('summary').focus(); await page.keyboard.press('Enter');
        if (await detail.getAttribute('open') === null) await page.keyboard.press('Enter');
        assert.equal(await detail.locator('tbody tr').count(), 16);
      }
      assert.equal(await catalogue.locator('.scene-detail[open]').count(), 19);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      const context = await browser.newContext({javaScriptEnabled: false, viewport: {width, height: 900}});
      try {
        const plain = await context.newPage();
        await plain.goto(server.fixture.url + '/#scene-metrics-14-1');
        assert.equal(await plain.locator('#scenes > .scene-measurements').getAttribute('open'), '');
        assert.equal(await plain.locator('#scenes .scene-detail[data-scene="14:1"]').getAttribute('open'), '');
        assert.equal(await plain.locator('#scene-metrics-14-1 table').isVisible(), true);
      } finally { await context.close(); }
    }
    assert.deepEqual(fs.readFileSync(path.join(directory, 'manuscript.md')), original);
    assert.deepEqual(writes, []);
    await rehearse(page, server.fixture.url, directory, original);
    assert.deepEqual(errors, []);
  } finally { await page.close(); await server.close(); }
}

async function rehearse(page, url, directory, original) {
  const board = page.locator('#scene-rehearsal');
  const form = board.locator('form');
  const submit = form.locator('button[type="submit"]');
  const cards = board.locator('[data-intent-id]');
  const statePath = path.join(directory, '.lixity', 'analysis-intents.json');
  async function openBoard() {
    await page.goto(url);
    await page.locator('#workbench-overview-open').click();
    await openAnalysisSection(page, 'scenes');
    await board.locator(':scope > summary').click();
  }
  async function add(scene, kind, text) {
    await page.locator('#scene-intent-editor > summary').click();
    await form.locator('[name="scene_id"]').selectOption(scene);
    await form.locator('[name="kind"]').selectOption(kind);
    await form.locator('[name="intent"]').fill(text);
    await form.locator('[name="voice"]').fill('Mara');
    await form.locator('[name="hypothesis"]').fill('The disclosure may reframe the question.');
    const response = page.waitForResponse(r => r.url().endsWith('/api/analysis-intents') && r.request().method() === 'POST');
    await submit.click();
    assert.equal((await response).status(), 200);
    await board.locator('#scene-rehearsal-status.ok').waitFor();
  }
  const order = () => cards.locator('[data-intent-field="intent"]').allTextContents();
  const measured = () => page.locator('.scene-overview [data-scene-row]').evaluateAll(
    rows => rows.map(row => row.dataset.sceneRow)
  );
  await page.setViewportSize({width: 390, height: 840});
  await openBoard();
  await board.locator('#scene-rehearsal-empty').waitFor();
  assert.equal(fs.existsSync(statePath), false, 'Opening the rehearsal writes nothing');
  await add('1:1', 'question', '<em>What was in the letter?</em>');
  await add('1:2', 'reveal', 'The letter was empty.');
  assert.equal(await cards.locator('em').count(), 0, 'Authored intentions render as text');
  const sourceOrder = await measured();
  const beforeOrder = await order();
  const beforeMove = fs.readFileSync(statePath);
  await cards.first().locator('[data-intent-action="down"]').click();
  const reverse = beforeOrder.slice().reverse();
  assert.deepEqual(await order(), reverse);
  assert.deepEqual(await measured(), sourceOrder);
  assert.deepEqual(fs.readFileSync(statePath), beforeMove, 'Moving a card alone writes nothing');
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await board.screenshot({path: path.join(artifacts, 'rehearsal-mobile.png')});
  await openBoard();
  await cards.last().waitFor();
  assert.deepEqual(await order(), beforeOrder, 'Reloading discards an unconfirmed rehearsal order');
  await cards.first().locator('[data-intent-action="down"]').click();
  await board.locator('[data-intent-action="save_order"]').click();
  await board.locator('#scene-rehearsal-status.ok').waitFor();
  await openBoard();
  await cards.last().waitFor();
  assert.deepEqual(await order(), reverse);
  assert.deepEqual(await measured(), sourceOrder);
  assert.deepEqual(fs.readFileSync(path.join(directory, 'manuscript.md')), original);

  const revised = Buffer.concat([original, Buffer.from('\n\nA letter falls through the door.\n')]);
  fs.writeFileSync(path.join(directory, 'manuscript.md'), revised);
  const refresh = await page.request.post(url + '/api/analyze', {data: {}});
  assert.equal(refresh.status(), 200);
  await openBoard();
  await cards.last().waitFor();
  assert.deepEqual(await cards.locator('[data-intent-field="status"]').allTextContents(),
    ['Review after revision', 'Review after revision']);
  assert.equal(await cards.locator('a:visible').count(), 0, 'A stale anchor has no authoritative link');
  await cards.first().locator('[data-intent-action="edit"]').click();
  assert.equal(await form.locator('[name="scene_id"]').inputValue(), '');
  await form.locator('[name="scene_id"]').selectOption('1:2');
  const preview = form.locator('#scene-intent-preview');
  const pendingIntent = await form.locator('[name="intent"]').inputValue();
  await preview.press('Enter');
  assert.equal(await page.evaluate(() => document.activeElement.id), 'scene-evidence-1-2');
  const back = page.locator('#scene-evidence-1-2 #scene-intent-return button');
  assert.ok(await back.isVisible());
  await back.press('Enter');
  assert.equal(await preview.evaluate(el => el === document.activeElement), true);
  assert.equal(await form.locator('[name="intent"]').inputValue(), pendingIntent);
  assert.equal(await form.locator('[name="scene_id"]').inputValue(), '1:2');
  await submit.click();
  await board.locator('#scene-rehearsal-status.ok').waitFor();
  assert.deepEqual(await cards.locator('[data-intent-field="status"]').allTextContents(),
    ['Current text', 'Review after revision']);
  const measuredLink = cards.first().locator('[data-intent-field="scene-link"]');
  await measuredLink.focus();
  await page.keyboard.press('Enter');
  assert.equal(await page.evaluate(() => document.activeElement.id), 'scene-evidence-1-2');
  assert.deepEqual(fs.readFileSync(path.join(directory, 'manuscript.md')), revised);

  fs.writeFileSync(path.join(directory, 'manuscript.md'), '');
  const savedState = fs.readFileSync(statePath);
  assert.equal((await page.request.post(url + '/api/analyze', {data: {}})).status(), 200);
  await page.goto(url);
  await page.locator('#tab-view-analysis').click();
  await board.locator(':scope > summary').click();
  await cards.last().waitFor();
  assert.deepEqual(await cards.locator('[data-intent-field="status"]').allTextContents(),
    ['Review after revision', 'Review after revision']);
  assert.equal(await board.locator('#scene-intent-editor').isVisible(), false);
  assert.deepEqual(fs.readFileSync(statePath), savedState);

  fs.writeFileSync(path.join(directory, 'manuscript.md'), revised);
  assert.equal((await page.request.post(url + '/api/analyze', {data: {}})).status(), 200);
  await openBoard();
  await cards.last().waitFor();
  const token = await board.locator('#scene-intents-token').inputValue();
  async function savedCards() {
    const response = await page.request.get(url + '/api/analysis-intents', {params: {project_token: token}});
    assert.equal(response.status(), 200);
    return response.json();
  }
  async function saveElsewhere(state, changes) {
    const response = await page.request.post(url + '/api/analysis-intents', {data: {
      project_token: token,
      expected_source_sha256: state.source_sha256,
      expected_analysis_sha256: state.analysis_sha256,
      expected_intents_sha256: state.intents_sha256,
      ...changes,
    }});
    assert.equal(response.status(), 200);
  }
  const reload = board.locator('[data-intent-action="load"]');
  const orderSave = board.locator('[data-intent-action="save_order"]');
  const state = await savedCards();
  await cards.first().locator('[data-intent-action="down"]').click();
  await saveElsewhere(state, {action: 'save_order', ids: state.cards.map(card => card.id).reverse()});
  await orderSave.click();
  await reload.waitFor();
  assert.equal(await orderSave.isDisabled(), true);
  await reload.click();
  await board.locator('#scene-rehearsal-status').filter({hasText: /The saved order changed/}).waitFor();
  assert.equal(await orderSave.isVisible(), false);
  assert.deepEqual(await order(), state.cards.map(card => card.intent).reverse(),
    'Another window’s saved order replaces the conflicted draft');

  const edited = await savedCards();
  const [first, second] = edited.cards;
  await cards.first().locator('[data-intent-action="edit"]').click();
  await form.locator('[name="scene_id"]').selectOption('1:1');
  await form.locator('[name="intent"]').fill('Local rehearsal draft');
  page.once('dialog', dialog => dialog.dismiss());
  await cards.last().locator('[data-intent-action="edit"]').click();
  assert.equal(await form.locator('[name="intent"]').inputValue(), 'Local rehearsal draft',
    'Dismissing the change-of-card confirmation keeps the unsaved draft');
  await saveElsewhere(edited, {action: 'save', id: first.id, scene_id: '1:1', kind: first.kind,
    intent: 'Changed elsewhere', hypothesis: first.hypothesis, voice: first.voice});
  await submit.click();
  await reload.waitFor();
  assert.equal(await submit.isDisabled(), true);
  await reload.click();
  const useDraft = board.locator('[data-intent-action="save_as_new"]');
  await useDraft.waitFor();
  assert.equal(await useDraft.evaluate(el => document.activeElement === el), true);
  assert.equal(await submit.isDisabled(), true);
  assert.equal(await form.locator('[name="intent"]').inputValue(), 'Local rehearsal draft');
  await useDraft.click();
  assert.equal(await submit.isEnabled(), true);
  await submit.click();
  await cards.nth(2).waitFor();
  const recovered = await savedCards();
  assert.deepEqual(recovered.cards.map(card => card.intent),
    ['Changed elsewhere', second.intent, 'Local rehearsal draft'],
    'Preserving a draft never overwrites the other window’s card without review');
}
