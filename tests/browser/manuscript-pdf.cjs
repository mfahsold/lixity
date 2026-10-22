const {openProjectActions} = require('./support/project-actions.cjs');
// Native PDF export stays explicit, project-bound, read-only and recoverable.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');

const {pythonFixture} = require('./support/python-fixture.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-manuscript-pdf-'));
const {fixtures, gates} = pythonFixture(`
import json
from lixity.language import get_language_profile
from lixity.ui import render_dashboard
from lixity.workspace_labels import WORKSPACE_LABELS
from dashboard_fixtures import full_dashboard as render
original = render.__globals__['render_dashboard']
fixtures = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    def native(*args, **kwargs):
        return original(*args, **{**kwargs, 'labels': labels, 'language_key': locale,
            'enabled_actions': ['manuscript-pdf'], 'manuscript_pdf_token': 'synthetic-token'})
    render.__globals__['render_dashboard'] = native
    fixtures[locale] = render()
gates = {}
for name, controls, actions, token in (
    ('offline', False, ['manuscript-pdf'], 'synthetic-token'),
    ('embedding', True, ['analyze'], 'synthetic-token'),
    ('implicit', True, None, 'synthetic-token'),
    ('no_token', True, ['manuscript-pdf'], ''),
):
    def gated(*args, **kwargs):
        return original(*args, **{**kwargs, 'controls': controls,
            'enabled_actions': actions, 'manuscript_pdf_token': token})
    render.__globals__['render_dashboard'] = gated
    gates[name] = render()
def no_paragraphs(chapters, paragraphs, **kwargs):
    return original(chapters, [], **{**kwargs, 'controls': True,
        'enabled_actions': ['manuscript-pdf'], 'manuscript_pdf_token': 'synthetic-token'})
render.__globals__['render_dashboard'] = no_paragraphs
gates['no_paragraphs'] = render()
gates['empty'] = render_dashboard([], [], controls=True,
    enabled_actions=['manuscript-pdf'], manuscript_pdf_token='')
print(json.dumps({'fixtures': fixtures, 'gates': gates}))
`, {root});

// Synthetic responses isolate download recovery; the final case exercises
// actual PDF composition through the native server.
const pdfBytes = Buffer.from('%PDF-1.4\n% Synthetic browser download fixture\n%%EOF\n');
const hostileError = '<img src=x onerror="window.pdfInjected=true"> Synthetic project conflict';

async function checkNativeEditorialPdf(browser) {
  let textChecked = true;
  const server = await startNativeServer(`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
project = Path(sys.argv[1]) / 'synthetic-editorial-project'
project.mkdir()
manuscript = project / 'editorial.md'
manuscript.write_text(
    '# Editorial fixture\\n\\n'
    'A **synthetic editorial** paragraph with '
    + chr(92) + 'emph{retained emphasis} and '
    + chr(92) + 'textbf{retained weight}.\\n\\n'
    '## Review section\\n\\n'
    '- First retained list item.\\n- Second retained list item.\\n\\n'
    '> A retained quotation.\\n', encoding='utf-8')
(project / 'lixity.toml').write_text('title = "Synthetic editorial fixture"\\nlanguage = "en"\\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.exports_dir = str(project / 'exports')
LixityServerHandler.language = 'en'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'manuscript': str(manuscript)}), flush=True)
server.serve_forever()
`, artifacts);
  try {
    const before = fs.readFileSync(server.fixture.manuscript);
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}, acceptDownloads: true});
      const errors = [], requests = [];
      let downloads = 0;
      page.on('pageerror', error => errors.push(error.message));
      page.on('download', () => { downloads++; });
      page.on('request', request => {
        if (new URL(request.url()).pathname === '/api/manuscript-pdf') requests.push(request.postDataJSON());
      });
      await page.goto(server.fixture.url);
      await openProjectActions(page);
      await page.locator('#manuscript-pdf-title').click();
      assert.equal(await page.locator('#manuscript-pdf-layout').inputValue(), 'editor');
      const downloading = page.waitForEvent('download');
      await page.locator('#manuscript-pdf-download').click();
      const download = await downloading;
      assert.equal(download.suggestedFilename(), 'manuscript-editor.pdf');
      const downloaded = path.join(artifacts, `native-editor-${width}.pdf`);
      await download.saveAs(downloaded);
      const bytes = fs.readFileSync(downloaded);
      assert.ok(bytes.subarray(0, 5).equals(Buffer.from('%PDF-')) && bytes.subarray(-20).toString().includes('%%EOF'), 'The native download is a complete PDF');
      assert.ok((bytes.toString('latin1').match(/\/Type \/Page\b/g) || []).length >= 1, 'The native PDF contains actual pages');
      assert.match(bytes.toString('latin1'), /\/MediaBox \[0 0 595\.\d+ 841\.\d+\]/, 'Editorial output uses A4 pages');
      assert.equal(requests.length, 1);
      assert.equal(requests[0].layout, 'editor');
      assert.match(requests[0].project_token, /^[0-9a-f]{64}$/);
      assert.deepEqual(fs.readFileSync(server.fixture.manuscript), before, 'Downloading preserves the selected manuscript bytes');
      const extracted = spawnSync('pdftotext', [downloaded, '-'], {encoding: 'utf8'});
      if (extracted.error && extracted.error.code === 'ENOENT') {
        textChecked = false;
        console.log('Native editorial PDF text inspection skipped: pdftotext is unavailable; bytes/A4/pages were checked.');
      } else {
        assert.equal(extracted.status, 0, extracted.stderr);
        const text = extracted.stdout.replace(/\s+/g, ' ');
        for (const expected of ['synthetic editorial', 'retained emphasis', 'retained weight', 'Review section', 'First retained list item', 'A retained quotation']) {
          assert.ok(text.includes(expected), `Native editorial download retains ${expected}`);
        }
        assert.ok(!text.includes('\\emph{') && !text.includes('\\textbf{'), 'Supported TeX text commands are rendered instead of copied literally');
      }
      await page.locator('#manuscript-pdf-layout').selectOption('document');
      const documentDownload = page.waitForEvent('download');
      await page.locator('#manuscript-pdf-download').click();
      const plain = await documentDownload;
      assert.equal(plain.suggestedFilename(), 'manuscript-document.pdf');
      const plainPath = path.join(artifacts, `native-document-${width}.pdf`);
      await plain.saveAs(plainPath);
      assert.equal(requests.at(-1).layout, 'document');
      assert.match(fs.readFileSync(plainPath).toString('latin1'), /\/MediaBox \[0 0 595\.\d+ 841\.\d+\]/);
      const plainText = spawnSync('pdftotext', [plainPath, '-'], {encoding: 'utf8'});
      if (!plainText.error) {
        assert.equal(plainText.status, 0, plainText.stderr);
        assert.ok(plainText.stdout.includes('Editorial fixture'), 'Neutral documents retain the authored title');
        assert.ok(plainText.stdout.includes('First retained list item'), 'Neutral documents retain actual source prose');
        assert.ok(!plainText.stdout.includes('Synthetic editorial fixture'), 'Entered metadata does not add a control header or cover');
      }
      assert.deepEqual(fs.readFileSync(server.fixture.manuscript), before);
      await page.locator('#manuscript-pdf').screenshot({path: path.join(artifacts, `native-document-${width}.png`)});
      if (width === 1440) {
        const invalid = Buffer.concat([before, Buffer.from('\nUnsupported math $x^2 + y^2$.\n')]);
        const downloadsBefore = downloads;
        const exportDirectory = path.join(path.dirname(server.fixture.manuscript), 'exports');
        const exportsExisted = fs.existsSync(exportDirectory);
        try {
          fs.writeFileSync(server.fixture.manuscript, invalid);
          const rejected = page.waitForResponse(response => new URL(response.url()).pathname === '/api/manuscript-pdf' && response.request().method() === 'POST');
          await page.locator('#manuscript-pdf-download').click();
          const response = await rejected;
          assert.equal(response.status(), 400, 'Unsupported math produces a prompt HTTP error');
          const result = await response.json();
          assert.equal(result.ok, false);
          assert.match(result.message, /Unsupported TeX math.*line \d+/);
          await page.waitForFunction(() => !document.querySelector('#manuscript-pdf-download').disabled && document.querySelector('#manuscript-pdf-status').classList.contains('err'));
          assert.ok((await page.locator('#manuscript-pdf-status').textContent()).includes('Unsupported TeX math'), 'The native PDF error is visible beside the download control');
          assert.equal(downloads, downloadsBefore, 'Unsupported math cannot trigger a PDF download');
          assert.equal(fs.existsSync(exportDirectory), exportsExisted, 'Rejected composition creates no export directory');
          assert.deepEqual(fs.readFileSync(server.fixture.manuscript), invalid, 'The rejected request does not rewrite manuscript text');
        } finally { fs.writeFileSync(server.fixture.manuscript, before); }
      }
      assert.deepEqual(errors, []);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.locator('#manuscript-pdf').screenshot({path: path.join(artifacts, `native-editor-${width}.png`)});
      await page.close();
    }
    return textChecked;
  } finally { await server.close(); }
}

(async () => {
  const browser = await launchChromium();
  try {
    for (const [locale, html] of Object.entries(fixtures)) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}, acceptDownloads: true});
      const errors = [], requests = [], downloads = [];
      let response = 'pdf', release = null, pending = null, onRequest = null;
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => {
        if (!['error', 'warning'].includes(message.type())) return;
        // Chromium reports the deliberately rejected HTTP request separately
        // from the application's rendered conflict; other errors are failures.
        if (message.location().url.endsWith('/api/manuscript-pdf') &&
            /^Failed to load resource: the server responded with a status of 409\b/.test(message.text())) return;
        errors.push(message.text());
      });
      page.on('download', download => downloads.push(download));
      await page.route('http://lixity.test/**', async route => {
        const request = route.request(), url = new URL(request.url());
        if (url.pathname === '/api/manuscript-pdf') {
          requests.push({method: request.method(), payload: request.postDataJSON()});
          if (onRequest) {onRequest(); onRequest = null;}
          if (pending) await pending;
          if (response === 'conflict') return route.fulfill({status: 409, json: {ok: false, message: hostileError}});
          if (response === 'html') return route.fulfill({contentType: 'text/html', body: '<html>Synthetic non-PDF response</html>'});
          if (response === 'bad_pdf') return route.fulfill({contentType: 'application/pdf', body: 'Synthetic invalid PDF response'});
          const layout = request.postDataJSON().layout;
          return route.fulfill({headers: {'Content-Type': 'application/pdf',
            'Content-Disposition': `attachment; filename="manuscript-${layout}.pdf"`}, body: pdfBytes});
        }
        if (url.pathname.startsWith('/api/')) return route.fulfill({json: {ok: false, locked: true, records: []}});
        return route.fulfill({contentType: 'text/html', body: html});
      });
      await page.goto('http://lixity.test/');
      assert.match(await page.title(), /^Testroman – /);
      assert.ok((await page.locator('body').innerText()).includes('Testroman'));
      await page.locator('#tab-view-analysis').click();
      const form = page.locator('#manuscript-pdf-form');
      const select = page.locator('#manuscript-pdf-layout');
      const button = page.locator('#manuscript-pdf-download');
      const status = page.locator('#manuscript-pdf-status');
      assert.equal(await form.locator('xpath=ancestor::*[@id="project-controls"]').count(), 1,
        'PDF export belongs to the global project controls');
      assert.equal(await page.locator('#view-pane-analysis #manuscript-pdf-form').count(), 0);
      assert.equal(await page.locator('#manuscript-pdf-form').count(), 1, 'There is one canonical export form');
      assert.equal(await form.isVisible(), false, 'Project export starts compact');
      await openProjectActions(page);
      await page.locator('#manuscript-pdf-title').click();
      assert.equal(await form.isVisible(), true, 'A loaded native manuscript offers PDF export');
      assert.equal(await form.getAttribute('data-project-token'), 'synthetic-token');
      assert.equal(await select.inputValue(), 'editor', 'Editorial A4 is the initial choice');
      assert.deepEqual(await select.locator('option').evaluateAll(options => options.map(option => option.value)),
        ['editor', 'book', 'sheet', 'report', 'document']);
      assert.equal(await button.isDisabled(), false);
      assert.ok((await button.textContent()).trim().length > 0);
      assert.doesNotMatch(await form.textContent(), /manuscript_pdf_[a-z_]+/, 'Controls use translated labels');
      assert.doesNotMatch(await page.locator('#manuscript-pdf-hint').textContent(), /manuscript_pdf_[a-z_]+/, 'The editorial hint is translated');
      assert.equal(requests.length, 0, 'Loading the dashboard never starts export');
      for (const view of ['research', 'project', 'analysis']) {
        await page.locator(`#tab-view-${view}`).click();
        assert.equal(await form.isVisible(), true, `Project export remains visible in ${view}`);
      }

      for (const layout of ['editor', 'book', 'sheet', 'report', 'document']) {
        await select.selectOption(layout);
        assert.equal(requests.length, downloads.length, 'Selecting a layout sends nothing');
        pending = new Promise(resolve => {release = resolve;});
        const requested = new Promise(resolve => {onRequest = resolve;});
        const downloadPromise = page.waitForEvent('download');
        await button.click();
        await page.waitForFunction(() => document.querySelector('#manuscript-pdf-download').disabled);
        assert.equal(await select.isDisabled(), true, 'Pending export locks layout selection');
        assert.equal(await button.getAttribute('aria-busy'), 'true');
        await requested;
        assert.deepEqual(requests.at(-1), {method: 'POST', payload: {layout, project_token: 'synthetic-token'}},
          'Export sends only layout and opaque project identity');
        release(); pending = null;
        const download = await downloadPromise;
        assert.equal(download.suggestedFilename(), `manuscript-${layout}.pdf`);
        const downloaded = path.join(artifacts, `${locale}-${width}-${layout}.pdf`);
        await download.saveAs(downloaded);
        assert.deepEqual(fs.readFileSync(downloaded), pdfBytes, 'Downloaded bytes match the response exactly');
        await page.waitForFunction(() => !document.querySelector('#manuscript-pdf-download').disabled);
        assert.equal(await select.isDisabled(), false);
        assert.notEqual(await button.getAttribute('aria-busy'), 'true');
      }

      await select.selectOption('sheet');
      for (const failure of ['conflict', 'html', 'bad_pdf']) {
        response = failure;
        const beforeDownloads = downloads.length, beforeRequests = requests.length;
        await button.click();
        await page.waitForFunction(() => !document.querySelector('#manuscript-pdf-download').disabled &&
          !document.querySelector('#manuscript-pdf-status').hidden);
        assert.equal(requests.length, beforeRequests + 1);
        assert.equal(downloads.length, beforeDownloads, `${failure} cannot produce a download`);
        assert.equal(await select.inputValue(), 'sheet', 'A failure preserves the chosen layout');
        assert.equal(await select.isDisabled(), false);
        assert.equal(await status.isVisible(), true);
        assert.ok((await status.textContent()).trim().length > 0);
        if (failure === 'conflict') assert.ok((await status.textContent()).includes('Synthetic project conflict'));
        assert.equal(await form.locator('img, script').count(), 0, 'Server errors remain inert text');
        assert.equal(await page.evaluate(() => Boolean(window.pdfInjected)), false);
        if (failure === 'conflict' && locale === 'en' && width === 320) {
          await page.locator('#manuscript-pdf').screenshot({path: path.join(artifacts, 'conflict-mobile.png')});
        }
      }

      response = 'pdf';
      const retry = page.waitForEvent('download');
      await button.click();
      assert.equal((await retry).suggestedFilename(), 'manuscript-sheet.pdf', 'The preserved layout can be retried');
      await page.waitForFunction(() => !document.querySelector('#manuscript-pdf-download').disabled);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true,
        `${locale} controls fit at ${width}px`);
      assert.deepEqual(errors, []);
      await page.locator('#manuscript-pdf').screenshot({path: path.join(artifacts, `${locale}-${width}.png`)});
      await page.close();
    }
    const noScript = await browser.newPage({javaScriptEnabled: false, viewport: {width: 320, height: 900}});
    await noScript.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: fixtures.en}));
    await noScript.goto('http://lixity.test/');
    await openProjectActions(noScript);
    await noScript.locator('#manuscript-pdf-title').click();
    assert.equal(await noScript.locator('#manuscript-pdf-form').isVisible(), true);
    assert.equal(await noScript.locator('#manuscript-pdf-download').isDisabled(), true,
      'Without JavaScript the native action cannot submit an incomplete request');
    assert.ok((await noScript.locator('#manuscript-pdf noscript').textContent()).trim().length > 0);
    await noScript.close();

    for (const [name, html] of Object.entries(gates)) {
      const page = await browser.newPage({viewport: {width: 320, height: 900}});
      let exports = 0;
      await page.route('http://lixity.test/**', route => {
        if (route.request().url().endsWith('/api/manuscript-pdf')) exports++;
        return route.fulfill(route.request().url().includes('/api/')
          ? {json: {ok: false, locked: true, records: []}} : {contentType: 'text/html', body: html});
      });
      await page.goto('http://lixity.test/');
      const form = page.locator('#manuscript-pdf-form');
      if (['offline', 'embedding', 'implicit'].includes(name)) assert.equal(await form.count(), 0, `${name} has no native export action`);
      else {
        await page.locator('#tab-view-analysis').click();
        await openProjectActions(page);
        await page.locator('#manuscript-pdf-title').click();
        assert.equal(await form.isVisible(), true, `${name} keeps native export discoverable`);
        assert.equal(await page.locator('#manuscript-pdf-download').isDisabled(), true,
          `${name} cannot export without manuscript paragraphs and a project token`);
      }
      assert.equal(exports, 0);
      await page.close();
    }
    const nativeTextChecked = await checkNativeEditorialPdf(browser);
    console.log(`Manuscript PDF: editorial default and five layouts; capability/JavaScript gating, project-bound downloads, exact bytes, pending/errors/retry in seven desktop/mobile locales; real native Markdown/TeX-text PDF bytes/A4/pages at1440/320 and explicit math HTTP400 without a download passed; ${nativeTextChecked ? 'extracted content verified' : 'text inspection skipped (pdftotext unavailable)'}. Screenshots: ${artifacts}`);
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
