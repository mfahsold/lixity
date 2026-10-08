const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {launchChromium} = require('../../scripts/browser_tools.cjs');

const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-nda-draft-'));
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
import base64, json
from lixity.language import get_language_profile
from lixity.ui import render_dashboard
from lixity.nda import _minimal_pdf
from lixity.nda_templates import NDA_DOCUMENT_LABELS
from lixity.workspace_labels import WORKSPACE_LABELS
fixtures = {}
for language in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = {**get_language_profile(language).labels, **WORKSPACE_LABELS[language]}
    fixtures[language] = {'labels': labels, 'documentTitle': NDA_DOCUMENT_LABELS[language]['title'], 'html': render_dashboard(
        [], [], title='Synthetic Project', nda_project_name='Synthetic Project', labels=labels, language_key=language,
        controls=True, enabled_actions=['nda-draft', 'analyze', 'rebuild'], debug=True)}
print(json.dumps({'fixtures': fixtures, 'pdf': base64.b64encode(
    _minimal_pdf('Synthetic agreement', ['Synthetic download transport fixture.'])).decode('ascii'),
    'standalone': render_dashboard([], [], controls=True, enabled_actions=['analyze', 'rebuild'])}))
`], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024});
assert.equal(fixture.status, 0, fixture.error ? fixture.error.message : fixture.stderr);
const {fixtures, pdf, standalone} = JSON.parse(fixture.stdout);
const pdfBytes = Buffer.from(pdf, 'base64');
const name = '<img src=x onerror="window.ndaInjected=true">';
const address = 'Synthetic address\nSecond line';
const agreement = values => `Synthetic agreement\nName: ${values.name}\nAddress: ${values.address}\nProject: ${values.project_name}\nDate: ${values.date}\nPlace: ${values.place}\n`;

(async () => {
  const browser = await launchChromium();
  try {
    for (const language of Object.keys(fixtures)) for (const width of [1440, 320]) {
      const context = await browser.newContext({viewport: {width, height: 900}, hasTouch: true, timezoneId: 'Europe/Berlin'});
      const page = await context.newPage();
      await page.clock.setFixedTime(new Date('2026-10-06T23:30:00Z'));
      const requests = [], logs = [], errors = [];
      let reject = false, pending = null;
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => logs.push(message.text()));
      await page.route('http://lixity.test/**', async route => {
        if (route.request().url().endsWith('/api/nda-draft')) {
          const values = route.request().postDataJSON();
          requests.push(values);
          if (pending) await pending;
          if (reject) return route.fulfill({status: 400, json: {ok: false, message: 'Synthetic failure'}});
          return route.fulfill(values.format === 'pdf'
            ? {contentType: 'application/pdf', body: pdfBytes}
            : {contentType: 'text/plain; charset=utf-8', body: agreement(values)});
        }
        if (route.request().url().includes('/api/')) return route.fulfill({json: {ok: true, initialized: false, records: []}});
        return route.fulfill({contentType: 'text/html', body: fixtures[language].html});
      });
      await page.goto('http://lixity.test/');
      await page.locator('#tab-view-project').click();
      assert.equal(await page.locator('#nda-draft-form').count(), 1);
      assert.equal(await page.locator('#nda-draft-form input, #nda-draft-form textarea').count(), 5);
      assert.equal(await page.locator('#nda-manager, #nda-passphrase, #nda-table, [data-nda-status]').count(), 0);
      assert.equal(requests.length, 0, 'No NDA request before an explicit action');
      assert.equal(await page.locator('#nda-project-name').inputValue(), 'Synthetic Project');
      assert.equal(await page.locator('#nda-date').inputValue(), '2026-10-07', 'Calendar date uses the client locale, not UTC');
      assert.equal(await page.locator('#nda-draft h2').textContent(), fixtures[language].labels.nda_draft_title);
      assert.equal(await page.locator('#nda-draft h2').textContent(), fixtures[language].documentTitle, 'The app names the agreement without a draft qualifier');
      assert.equal(await page.locator('label[for=nda-name]').textContent(), fixtures[language].labels.nda_draft_name);
      if (width === 320) await page.locator('#nda-preview-btn').tap();
      else {
        await page.locator('#nda-preview-btn').focus();
        await page.keyboard.press('Enter');
      }
      assert.equal(requests.length, 0, 'Required fields validate before submission');
      await page.locator('#nda-name').fill(name);
      await page.locator('#nda-address').fill(address);
      await page.locator('#nda-place').fill('Synthetic place');
      let release;
      pending = new Promise(resolve => {release = resolve;});
      await page.locator('#nda-preview-btn').click();
      await page.waitForFunction(() => document.querySelector('#nda-preview-btn').disabled);
      assert.equal(await page.locator('#nda-name').isDisabled(), true);
      release();
      pending = null;
      await page.waitForFunction(() => !document.querySelector('#nda-preview-btn').disabled);
      const expected = {name, address, project_name: 'Synthetic Project', date: '2026-10-07', place: 'Synthetic place', format: 'text'};
      assert.deepEqual(requests.at(-1), expected);
      assert.equal(await page.locator('#nda-draft-preview').textContent(), agreement(expected));
      assert.equal(await page.locator('#nda-draft-preview img, #nda-draft-preview script').count(), 0);
      assert.equal(await page.evaluate(() => Boolean(window.ndaInjected)), false);
      for (const [selector, format, bytes] of [['#nda-pdf-btn', 'pdf', pdfBytes], ['#nda-text-btn', 'text', Buffer.from(agreement(expected))]]) {
        const downloaded = page.waitForEvent('download');
        if (width === 320) await page.locator(selector).tap();
        else await page.locator(selector).click();
        const download = await downloaded;
        assert.equal(requests.at(-1).format, format);
        assert.equal(download.suggestedFilename(), 'nda.' + (format === 'pdf' ? 'pdf' : 'txt'));
        const file = path.join(artifacts, `${language}-${width}.${format === 'pdf' ? 'pdf' : 'txt'}`);
        await download.saveAs(file);
        assert.deepEqual(fs.readFileSync(file), bytes);
      }
      reject = true;
      await page.locator('#nda-preview-btn').click();
      await page.waitForFunction(() => !document.querySelector('#nda-preview-btn').disabled);
      assert.equal(await page.locator('#nda-name').inputValue(), name);
      assert.ok((await page.locator('#nda-draft-status').textContent()).includes(fixtures[language].labels.nda_draft_failed));
      assert.ok((await page.locator('#nda-draft-status').textContent()).includes('Synthetic failure'), 'A safe server reason helps correct permanent errors');
      assert.ok(!logs.some(line => line.includes(name) || line.includes(address)), 'Personal data and document text stay out of logs');
      assert.deepEqual(errors, []);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${language}/${width} overflow`);
      await page.locator('#nda-draft').screenshot({path: path.join(artifacts, `${language}-${width}.png`)});
      await page.reload();
      assert.equal(await page.locator('#nda-name').inputValue(), '', 'NDA details are not persisted');
      await context.close();
    }
    const page = await browser.newPage();
    await page.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: standalone}));
    await page.goto('http://lixity.test/');
    assert.equal(await page.locator('#nda-draft-form').count(), 0);
    await page.close();
    console.log(`Minimal NDA: five fields, local date, inert preview, private logs, binary downloads, validation/failure and seven desktop/mobile locales passed. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
