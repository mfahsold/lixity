// A sentence selection prepares a whole-passage evidence draft; saving stays explicit.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {createInterface} = require('node:readline');
const {once} = require('node:events');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-selection-'));
const firstPassage = '😀 The archive opened in 1924. The courtyard stayed quiet. <img src=x onerror=window.selectionInjected=true>';

async function selectText(page, selector, phrase, endSelector) {
  await page.locator(selector).evaluate((element, args) => {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    let node;
    while (walker.nextNode()) {
      if (walker.currentNode.textContent.includes(args.phrase)) {node = walker.currentNode; break;}
    }
    if (!node) throw new Error('Synthetic phrase is absent');
    const at = node.textContent.indexOf(args.phrase);
    const range = document.createRange();
    range.setStart(node, at);
    if (args.endSelector) {
      const end = document.querySelector(args.endSelector).firstChild;
      range.setEnd(end, Math.min(8, end.textContent.length));
    } else range.setEnd(node, at + args.phrase.length);
    const selection = getSelection();
    selection.removeAllRanges(); selection.addRange(range);
    document.dispatchEvent(new Event('selectionchange'));
  }, {phrase, endSelector});
}

(async () => {
  const server = spawn(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-u', '-c', `
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
from lixity.ui import render_dashboard
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
base = Path(sys.argv[1]); project = base / 'project'
api.init(project, title='Synthetic selection project')
text = '\\r\\n😀 The archive opened in 1924. The courtyard stayed quiet. <img src=x onerror=window.selectionInjected=true>\\r\\n\\r\\nAnother witness disputed the year.\\r\\n\\r\\nRepeated synthetic sentence.\\r\\n\\r\\nRepeated synthetic sentence.'
source = base / 'source.txt'; source.write_text(text, encoding='utf-8')
capture = api.ingest(project, source, allow_retention=True, title='Synthetic <img src=x> source')
claim = api.create_claim(project, title='Archive opening', statement='The archive opened in 1924.')
detail = api.get_source(project, capture['source_id'])
fixtures = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    fixtures[locale] = render_dashboard([], [], controls=True, enabled_actions=[], labels=labels, language_key=locale)
(base / 'fixtures.json').write_text(json.dumps(fixtures), encoding='utf-8')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.research_dir = str(project)
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'source': capture['source_id'],
    'passage': detail['passages'][0]['id'], 'other_passage': detail['passages'][1]['id'],
    'version': detail['version_id'], 'claim': claim['claim_id']}), flush=True)
server.serve_forever()
`, artifacts], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, stdio: ['ignore', 'pipe', 'pipe']});
  const lines = createInterface({input: server.stdout});
  let stderr = '', browser;
  server.stderr.on('data', data => {stderr = (stderr + data).slice(-5000);});
  try {
    const fixture = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Synthetic server startup timed out: ' + stderr)), 15000);
      lines.once('line', line => {clearTimeout(timer); resolve(JSON.parse(line));});
      server.once('error', error => {clearTimeout(timer); reject(error);});
      server.once('exit', code => {clearTimeout(timer); reject(new Error(`Synthetic server exited ${code}: ${stderr}`));});
    });
    const fixtures = JSON.parse(fs.readFileSync(path.join(artifacts, 'fixtures.json'), 'utf8'));
    browser = await launchChromium();
    for (const [locale, html] of Object.entries(fixtures)) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 950}, hasTouch: true});
      page.setDefaultTimeout(10000);
      const posts = [], errors = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => {if (request.method() === 'POST') posts.push({path: new URL(request.url()).pathname, payload: request.postDataJSON()});});
      await page.route(fixture.url + '/', route => route.fulfill({contentType: 'text/html', body: html}));
      await page.goto(fixture.url);
      await page.locator('[data-rtab=sources]').click();
      await page.locator('[data-research-detail=source]').click();
      const doc = '.research-source-doc-rendered';
      await page.waitForFunction(() => document.querySelector('.research-source-doc-rendered p'));
      assert.equal(await page.locator('.selection-use').count(), 1, 'Source reading offers an accessible selection action');
      await selectText(page, doc + ' p:first-child', 'The archive opened in 1924.');
      await page.waitForFunction(() => !document.querySelector('.selection-use').disabled);
      assert.equal(posts.length, 0, 'Selecting text writes nothing');
      if (locale === 'de') await page.locator('#research-sources-list .research-details-body').screenshot({path: path.join(artifacts, `source-selection-${width}.png`)});
      await page.locator('.selection-use').focus();
      await page.keyboard.press('Enter');
      assert.equal(await page.locator('#r-link-passage-id').inputValue(), fixture.passage);
      assert.equal(await page.locator('#rtab-claims').isVisible(), true);
      assert.equal(await page.locator('#research-evidence-draft .selection-quote').textContent(), 'The archive opened in 1924.');
      assert.equal(await page.locator('#research-evidence-draft .selection-context').textContent(), firstPassage);
      assert.equal(await page.locator('#r-link-rationale').inputValue(), '', 'A selection never becomes an invented rationale');
      assert.equal(posts.length, 0, 'Preparing a draft writes nothing');
      assert.deepEqual(await page.locator('#r-claim-confidence option').evaluateAll(options => options.map(option => option.value)),
        ['hypothetical', 'evidenced', 'disputed'], 'Author-readable states preserve the wire values');
      if (locale === 'de') await page.locator('#research-evidence-draft').locator('..').screenshot({path: path.join(artifacts, `selected-draft-${width}.png`)});
      await page.locator('#r-link-claim-select').selectOption(fixture.claim);
      await page.locator('#r-link-relation').selectOption('qualifies');
      await page.locator('#r-link-rationale').fill('Synthetic author review.');
      await page.locator('#r-link-evidence-btn').click();
      await page.waitForFunction(() => document.querySelector('#r-link-passage-id').value === '');
      assert.deepEqual(posts, [{path: '/api/research-evidence-link', payload: {
        claim_id: fixture.claim, passage_id: fixture.passage, relation: 'qualifies', rationale: 'Synthetic author review.'}}]);
      const saved = await (await page.request.get(fixture.url + '/api/research/claims?claim_id=' + fixture.claim)).json();
      const link = saved.evidence_links.at(-1);
      assert.equal(link.passage_id, fixture.passage);
      assert.equal(link.citation.verbatim, firstPassage, 'The accepted citation pins the full retained paragraph');
      assert.equal(link.citation.source_version_id, fixture.version);

      await page.locator('[data-rtab=sources]').click();
      await selectText(page, doc + ' p:first-child', 'The archive', doc + ' p:nth-child(2)');
      assert.equal(await page.locator('.selection-use').isDisabled(), true, 'A cross-paragraph selection is rejected');
      await selectText(page, '#r-active-root', 'project');
      assert.equal(await page.locator('.selection-use').isDisabled(), true, 'Text outside the loaded source is rejected');
      await selectText(page, doc + ' p:nth-child(3)', 'Repeated synthetic sentence.');
      assert.equal(await page.locator('.selection-use').isDisabled(), true, 'Ambiguous retained paragraphs are rejected');
      await selectText(page, doc + ' p:first-child', 'The courtyard stayed quiet.');
      await page.locator('[data-source-toggle]').click();
      assert.equal(await page.locator('.selection-use').isDisabled(), true, 'Switching source representation invalidates a selection');
      await selectText(page, '.research-source-doc-raw', 'The archive opened in 1924.');
      assert.equal(await page.locator('.selection-use').isDisabled(), false, 'Raw text resolves Python character offsets after emoji');
      await selectText(page, '.research-source-doc-raw', 'Another witness disputed the year.');
      assert.equal(await page.locator('.selection-use').isDisabled(), false,
        'Raw selections preserve retained offsets after leading newlines and CRLF');
      await page.locator('.selection-use').click();
      assert.equal(await page.locator('#r-link-passage-id').inputValue(), fixture.other_passage);
      await page.locator('#research-evidence-draft button').click();
      await page.locator('[data-rtab=sources]').click();
      await page.route(fixture.url + '/api/research/sources', async route => {
        const response = await route.fetch();
        const data = await response.json(); data.sources[0].version_id = 'synthetic-refreshed-version';
        await route.fulfill({json: data});
      });
      await page.evaluate(() => refreshResearchSources(null, null, true));
      assert.equal(await page.locator('.selection-use:enabled').count(), 0, 'Refreshing a source version invalidates its old selection');
      await page.unroute(fixture.url + '/api/research/sources');
      await page.locator('[data-research-detail=source]').click();
      await page.waitForFunction(() => document.querySelector('.research-source-doc-rendered p'));
      await page.locator('[data-source-view=passages]').click();
      await page.locator('.research-source-passages-wrap [data-use-passage=claim]').first().tap();
      assert.equal(await page.locator('#r-link-passage-id').inputValue(), fixture.passage, 'Whole-passage actions remain a touch fallback');
      assert.equal(await page.locator('#research-evidence-draft .selection-context').textContent(), firstPassage);
      assert.equal(posts.length, 1, 'The fallback still only prepares a draft');
      let expectedSaves = 1;
      if (locale === 'en' && width === 1440) {
        let release, requested;
        const gate = new Promise(resolve => {release = resolve;});
        const started = new Promise(resolve => {requested = resolve;});
        await page.route(fixture.url + '/api/research-evidence-link', async route => {
          requested(); await gate; await route.continue();
        });
        await page.locator('#r-link-rationale').fill('Submitted rationale.');
        await page.locator('#r-link-evidence-btn').click();
        await started;
        assert.equal(await page.locator('#r-link-evidence-btn').isDisabled(), true,
          'A pending save cannot submit duplicate evidence');
        const accepted = page.waitForResponse(response => response.url().endsWith('/api/research-evidence-link') && response.request().method() === 'POST');
        await page.locator('#r-link-rationale').fill('New unsaved rationale.');
        release();
        await (await accepted).finished();
        await page.waitForFunction(() => !document.querySelector('#r-link-evidence-btn').disabled);
        assert.equal(await page.locator('#r-link-rationale').inputValue(), 'New unsaved rationale.',
          'An accepted pending save does not erase newer edits');
        assert.equal(await page.locator('#r-link-passage-id').inputValue(), fixture.passage);
        assert.equal(await page.locator('#research-evidence-draft').isVisible(), true);
        await page.unroute(fixture.url + '/api/research-evidence-link');
        expectedSaves = 2;
        let finishStatus, statusRequested, statusReads = 0;
        const statusGate = new Promise(resolve => {finishStatus = resolve;});
        const statusStarted = new Promise(resolve => {statusRequested = resolve;});
        await page.route(fixture.url + '/api/research/status', async route => {
          if (++statusReads !== 1) return route.continue();
          const response = await route.fetch(), data = await response.json();
          data.project_id = 'synthetic-old-project';
          statusRequested(); await statusGate; await route.fulfill({json: data});
        });
        const oldStatus = page.evaluate(() => refreshResearchProjectInfo());
        await statusStarted;
        await page.evaluate(() => refreshResearchProjectInfo());
        finishStatus(); await oldStatus;
        assert.equal(await page.locator('#r-link-passage-id').inputValue(), fixture.passage,
          'A superseded project-status read cannot discard the current evidence draft');
        await page.unroute(fixture.url + '/api/research/status');
      }
      await page.route(fixture.url + '/api/research/status', route => route.abort());
      await page.evaluate(() => refreshResearchProjectInfo());
      assert.equal(await page.locator('#r-link-passage-id').inputValue(), fixture.passage,
        'An unavailable status read does not discard an evidence draft');
      await page.unroute(fixture.url + '/api/research/status');
      assert.equal(await page.evaluate(() => Boolean(window.selectionInjected)), false);
      assert.equal(await page.locator('.research-source-doc-rendered img, #research-evidence-draft img').count(), 0);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      assert.deepEqual(errors, []);
      await page.locator('#research-evidence-draft').screenshot({path: path.join(artifacts, `${locale}-${width}.png`)});
      await page.locator('.selection-technical > summary').click();
      await page.locator('#r-link-passage-id').fill(fixture.other_passage);
      assert.equal(await page.locator('#research-evidence-draft').isVisible(), false,
        'An edited advanced passage identifier cannot keep another passage preview');
      assert.equal(await page.locator('#r-link-passage-id').inputValue(), fixture.other_passage,
        'Invalidating the preview preserves the explicit manual target');
      await page.route(fixture.url + '/api/research/status', async route => {
        const response = await route.fetch();
        const data = await response.json(); data.project_id = 'synthetic-other-project';
        await route.fulfill({json: data});
      });
      await page.evaluate(() => refreshResearchProjectInfo());
      assert.equal(await page.locator('#r-link-passage-id').inputValue(), '', 'Changing project invalidates the old evidence target');
      await page.unroute(fixture.url + '/api/research/status');
      await page.evaluate(() => refreshResearchProjectInfo());
      await page.locator('[data-rtab=sources]').click();
      await page.evaluate(() => refreshResearchSources(null, null, true));
      const details = page.locator('[data-research-detail=source]');
      if (await details.evaluate(button => button.parentElement.open)) await details.click();
      await page.route(fixture.url + '/api/research/sources?id=*', route => route.fulfill({json: {
        ok: true, id: fixture.source, media_type: 'image/png', title: 'Synthetic image', context: {}, passages: []}}));
      await details.click();
      await page.waitForFunction(() => document.querySelector('.research-details-body').textContent.includes('image/png'));
      assert.equal(await page.locator('.selection-use').count(), 0, 'Images do not offer text evidence selection');
      await details.click();
      await page.unroute(fixture.url + '/api/research/sources?id=*');
      await page.route(fixture.url + '/api/research/sources?id=*', route => route.fulfill({json: {
        ok: false, message: 'Synthetic source withdrawn'}}));
      await details.click();
      await page.waitForFunction(() => document.querySelector('.research-details-body').textContent.includes('Synthetic source withdrawn'));
      assert.equal(await page.locator('.selection-use').count(), 0, 'Withdrawn sources do not offer selection');
      assert.equal(posts.length, expectedSaves);
      if (locale === 'en' && width === 1440) {
        await details.click();
        await page.unroute(fixture.url + '/api/research/sources?id=*');
        let release, requested, reads = 0;
        const gate = new Promise(resolve => {release = resolve;});
        const started = new Promise(resolve => {requested = resolve;});
        await page.route(fixture.url + '/api/research/sources?id=*', async route => {
          if (++reads !== 1) return route.continue();
          const response = await route.fetch(), data = await response.json();
          data.title = 'Superseded request'; data.text = 'Old synthetic reading.';
          data.passages = [{id: fixture.passage, start: 0, end: 22, verbatim: data.text}];
          requested(); await gate; await route.fulfill({json: data});
        });
        await details.click(); await started;
        await details.click(); await details.click();
        await page.waitForFunction(() => {
          const doc = document.querySelector('.research-source-doc-rendered');
          return doc && doc.textContent.includes('The courtyard stayed quiet.');
        });
        const earlier = page.waitForResponse(response => response.url().includes('/api/research/sources?id='));
        release(); await (await earlier).finished();
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        assert.ok((await page.locator('.research-source-doc-rendered').textContent()).includes('The courtyard stayed quiet.'),
          'A superseded detail response cannot overwrite the newer source reading');
        await page.unroute(fixture.url + '/api/research/sources?id=*');
      }
      await page.close();
    }
    console.log(`Source selection: explicit full-passage evidence pins, accessible draft actions, ambiguity guards, inert text and desktop/mobile locales passed. Screenshots: ${artifacts}`);
  } finally {
    if (browser) await browser.close();
    lines.close(); server.kill('SIGTERM');
    if (server.exitCode === null) await once(server, 'exit');
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
