// Native PDF export stays explicit, project-bound, read-only and recoverable.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {launchChromium} = require('../../scripts/browser_tools.cjs');

const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-manuscript-pdf-'));
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
import json, runpy
from lixity.language import get_language_profile
from lixity.ui import render_dashboard
from lixity.workspace_labels import WORKSPACE_LABELS
render = runpy.run_path('tests/test_ui_contract.py')['_full_dashboard']
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
`], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024});
assert.equal(fixture.status, 0, fixture.error ? fixture.error.message : fixture.stderr);
const {fixtures, gates} = JSON.parse(fixture.stdout);

// The browser only transfers these synthetic bytes; native PDF validity and
// manuscript content are tested through the real server/export pipeline.
const pdfBytes = Buffer.from('%PDF-1.4\n% Synthetic browser download fixture\n%%EOF\n');
const hostileError = '<img src=x onerror="window.pdfInjected=true"> Synthetic project conflict';

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
      assert.equal(await form.isVisible(), true, 'A loaded native manuscript offers PDF export');
      assert.equal(await form.getAttribute('data-project-token'), 'synthetic-token');
      assert.equal(await select.inputValue(), 'book', 'Reading layout is the initial choice');
      assert.deepEqual(await select.locator('option').evaluateAll(options => options.map(option => option.value)),
        ['book', 'sheet', 'report']);
      assert.equal(await button.isDisabled(), false);
      assert.ok((await button.textContent()).trim().length > 0);
      assert.doesNotMatch(await form.textContent(), /manuscript_pdf_[a-z_]+/, 'Controls use translated labels');
      assert.equal(requests.length, 0, 'Loading the dashboard never starts export');

      for (const layout of ['book', 'sheet', 'report']) {
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
        assert.equal(await form.isVisible(), true, `${name} keeps native export discoverable`);
        assert.equal(await page.locator('#manuscript-pdf-download').isDisabled(), true,
          `${name} cannot export without manuscript paragraphs and a project token`);
      }
      assert.equal(exports, 0);
      await page.close();
    }
    console.log(`Manuscript PDF: capability/JavaScript gating, explicit project-bound downloads, exact bytes, pending state, inert errors and retry passed in seven desktop/mobile locales. Screenshots: ${artifacts}`);
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
