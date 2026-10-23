// Shared native render: explicit ZIP scope and portable read-only capabilities.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const {pythonFixture} = require('./support/python-fixture.cjs');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-read-only-site-'));
const fixtures = pythonFixture(String.raw`
import json
from lixity.language import get_language_profile
from lixity.pipeline import analyze_document, resolve_document_config
from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui.dashboard import render_dashboard, _script_json
text = '# Synthetic website\n\n## Arrival\n\nThe eastern gate was open. I could hear the rain.\n\n## Return\n\nThe keeper returned before dawn.\n'
config, _ = resolve_document_config(text, 'en')
analysis = analyze_document(text, config, FingerprintThresholds())
documents = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = get_language_profile(locale).labels
    options = dict(labels=labels, language_key=locale, controls=True, title='Synthetic website',
        enabled_actions=('site-export', 'research-reader', 'research-manuscript-review'),
        author_setting_enabled=True, project_token='a'*64,
        manuscript_pdf_token='selected-manuscript-context', research_context_token='selected-research-context')
    options['site_publications']={'public':{'title':'Selected public context','introduction':'','entries':[]}}
    readonly = render_dashboard(analysis.chapters, analysis.paragraphs, paragraph_evidence=analysis.evidence, read_only=True, **options)
    data = {'schema_version':'lixity-read-only-site-data/1','responses':{},'resources':{}}
    readonly = readonly.replace('<script>', '<script type="application/json" id="lixity-site-data">' + _script_json(data) + '</script><script>', 1)
    documents[locale] = {'live': render_dashboard(analysis.chapters, analysis.paragraphs, **options), 'readonly': readonly,
        'empty': render_dashboard(analysis.chapters, analysis.paragraphs, **{**options, 'site_publications': {}}),
        'no_profiles': labels['publication_export_no_profiles'],
        'unsaved_profiles': labels['publication_export_unsaved_profiles'],
        'notice': labels['site_read_only']}
print(json.dumps(documents))
`);

(async () => {
  const browser = await launchChromium();
  const errors = [];
  try {
    for (const [locale, fixture] of Object.entries(fixtures)) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion: 'reduce'});
      page.on('pageerror', error => errors.push(error.message));
      const consoleErrors = [];
      page.on('console', message => {if (message.type() === 'error') consoleErrors.push(message.text());});
      const posts = [];
      const receipts = [];
      let rejectNext = false;
      let failure = '';
      await page.route('http://lixity.test/**', async route => {
        const request = route.request();
        if (request.url().endsWith('/api/site-export-report')) {
          receipts.push(request.postDataJSON());
          await route.fulfill({contentType:'application/json', body:'{"ok":true}'});
          return;
        }
        if (request.url().endsWith('/api/site-export')) {
          posts.push(request.postDataJSON());
          if (failure === 'network') return route.abort('failed');
          if (failure === 'http') return route.fulfill({status:502, contentType:'text/html', body:'Synthetic proxy error'});
          if (failure === 'html') return route.fulfill({contentType:'text/html', body:'Synthetic non-ZIP response'});
          if (failure === 'zip') return route.fulfill({contentType:'application/zip', body:'Not a ZIP'});
          if (rejectNext) {
            rejectNext = false;
            await route.fulfill({status:409, contentType:'application/json', body:JSON.stringify({message:'Synthetic context changed.'})});
            return;
          }
          await route.fulfill({contentType: 'application/zip', headers:{'X-Lixity-Export-ID':'a'.repeat(32)},
            body: Buffer.from('504b0506000000000000000000000000000000000000', 'hex')});
        } else await route.fulfill({contentType: 'text/html',
          body:request.url().endsWith('/empty') ? fixture.empty : fixture.live});
      });
      await page.goto('http://lixity.test/');
      await page.locator('#project-actions').evaluate(element => {element.open = true;});
      await page.locator('#btn-site-export').click();
      await expect(page.locator('#modal-site-export')).toBeVisible();
      await expect(page.locator('#site-export-research')).not.toBeChecked();
      await expect(page.locator('#site-export-sources')).not.toBeChecked();
      await expect(page.locator('#site-export-sources')).toBeDisabled();
      if (locale === 'en') await page.locator('#modal-site-export').screenshot({path:path.join(artifacts, `website-dialog-${width}.png`)});
      await page.locator('#site-export-research').check();
      await page.locator('#site-export-sources').check();
      await page.locator('#site-export-research').uncheck();
      await expect(page.locator('#site-export-sources')).not.toBeChecked();
      await expect(page.locator('#site-export-sources')).toBeDisabled();
      const downloaded = page.waitForEvent('download');
      await page.locator('#site-export-download').click();
      const download = await downloaded;
      assert.equal(download.suggestedFilename(), 'lixity-reading-website.zip');
      assert.deepEqual(posts, [{project_token: 'selected-manuscript-context', include_research: false, include_source_files: false}]);
      if (locale === 'en') {
        for (const mode of ['reader','companion']) {
          await page.locator('#site-export-mode').selectOption(mode);
          if (mode === 'reader') await expect(page.locator('#site-export-download')).toBeDisabled();
          await expect(page.locator('#site-export-research')).toBeHidden();
          await page.locator('#site-export-profile').selectOption('public');
          await page.locator('#site-export-max-chapter').selectOption('1');
          await expect(page.locator('#site-export-sources')).toBeEnabled();
          await page.locator('#modal-site-export').screenshot({path:path.join(artifacts, `website-dialog-${mode}-${width}.png`)});
          const modeDownload=page.waitForEvent('download');
          await page.locator('#site-export-download').click();
          await modeDownload;
          assert.deepEqual(posts.at(-1),{project_token:'selected-manuscript-context', include_research:false,
            include_source_files:false,mode,publication_profile:'public',max_chapter:1});
        }
        await page.locator('#site-export-mode').selectOption('review');
      }
      if (locale !== 'en') {
        await page.locator('#site-export-mode').selectOption('companion');
        await page.locator('#site-export-profile').selectOption('public');
        await page.locator('#site-export-max-chapter').selectOption('1');
        await expect(page.locator('#site-export-download')).toBeEnabled();
        assert.ok(await page.locator('#modal-site-export').evaluate(element => element.scrollWidth <= element.clientWidth + 1));
        await page.locator('#site-export-mode').selectOption('review');
      }
      if (locale === 'en') {
        await page.locator('#site-export-research').check();
        await page.locator('#site-export-sources').check();
        rejectNext = true;
        await page.locator('#site-export-download').click();
        await expect(page.locator('#site-export-status.err')).toContainText('Synthetic context changed.');
        await expect(page.locator('#site-export-research')).toBeChecked();
        await expect(page.locator('#site-export-sources')).toBeChecked();
        const retryDownload = page.waitForEvent('download');
        await page.locator('#site-export-download').click();
        await retryDownload;
        assert.deepEqual(posts.slice(-2), Array(2).fill({project_token:'selected-manuscript-context', include_research:true, include_source_files:true}));
        for (const [kind, detail] of [
          ['network', 'could not reach the application'],
          ['http', 'HTTP 502'],
          ['html', 'Content-Type: text/html'],
          ['zip', 'could not be read as a valid ZIP'],
        ]) {
          failure = kind;
          await page.locator('#site-export-download').click();
          await expect(page.locator('#site-export-status.err')).toContainText(detail);
          await expect(page.locator('#site-export-download')).toBeEnabled();
          await expect(page.locator('#site-export-research')).toBeChecked();
          await expect(page.locator('#site-export-sources')).toBeChecked();
          if (kind === 'html') {
            await page.locator('#modal-site-export').screenshot({path:path.join(artifacts, `website-error-${width}.png`)});
          }
        }
        failure = '';
        await page.evaluate(() => {
          window.lixityOriginalResponseBlob = Response.prototype.blob;
          Response.prototype.blob = async () => {throw new DOMException('Synthetic private-looking detail', 'AbortError');};
        });
        await page.locator('#site-export-download').click();
        await expect(page.locator('#site-export-status.err')).toContainText('AbortError');
        await expect(page.locator('#site-export-status.err')).toContainText('could not finish reading');
        await expect.poll(() => receipts.at(-1)).toEqual({
          export_id:'a'.repeat(32), stage:'response_read', error_name:'AbortError',
        });
        await page.evaluate(() => {Response.prototype.blob = window.lixityOriginalResponseBlob;});
        await page.evaluate(() => {
          window.lixityOriginalCreateObjectURL = URL.createObjectURL;
          URL.createObjectURL = () => {throw new TypeError('Synthetic download failure');};
        });
        await page.locator('#site-export-download').click();
        await expect(page.locator('#site-export-status.err')).toContainText('browser could not start the download');
        await expect(page.locator('#site-export-status.err')).toContainText('TypeError: Synthetic download failure');
        await expect.poll(() => receipts.at(-1)).toEqual({
          export_id:'a'.repeat(32), stage:'download_start', error_name:'TypeError',
        });
        await page.evaluate(() => {URL.createObjectURL = window.lixityOriginalCreateObjectURL;});
        const recoveredDownload = page.waitForEvent('download');
        await page.locator('#site-export-download').click();
        await recoveredDownload;
        await expect(page.locator('#site-export-status.ok')).toBeVisible();
        await expect.poll(() => receipts.at(-1)).toEqual({
          export_id:'a'.repeat(32), stage:'download_started', error_name:null,
        });
        assert.ok(!JSON.stringify(receipts).includes('private-looking'));
        assert.ok(consoleErrors.some(message => message.includes('response_read') && message.includes('AbortError')));
        assert.ok(!consoleErrors.some(message => message.includes('Synthetic private-looking detail')));
      }
      const dialog = page.locator('#modal-site-export');
      assert.ok(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth + 1));
      await page.keyboard.press('Escape');
      await expect(page.locator('#btn-site-export')).toBeFocused();
      await page.goto('http://lixity.test/empty');
      await page.locator('#project-actions').evaluate(element => {element.open = true;});
      await page.locator('#btn-site-export').click();
      await page.locator('#site-export-mode').selectOption('reader');
      await expect(page.locator('#site-export-profile')).toBeDisabled();
      await expect(page.locator('#site-export-profile-state')).toHaveText(fixture.no_profiles);
      await expect(page.locator('#site-export-max-chapter')).toBeDisabled();
      await expect(page.locator('#site-export-download')).toBeDisabled();
      await expect(page.locator('#site-export-sources')).toBeDisabled();
      if (['de', 'en'].includes(locale)) await page.locator('#modal-site-export').screenshot({
        path:path.join(artifacts, `empty-profiles-${locale}-${width}.png`),
      });
      await page.locator('#site-export-edit-profiles').click();
      await expect(page.locator('#modal-site-export')).not.toBeVisible();
      await expect(page.locator('[data-site-publication-add-profile]')).toBeFocused();
      await page.locator('[data-site-publication-add-profile]').click();
      await page.locator('[data-site-publication-field=id]').fill('draft');
      await page.locator('[data-site-publication-field=title]').fill('PRIVATE_SYNTHETIC_DRAFT');
      await page.locator('#btn-site-export').click();
      await page.locator('#site-export-mode').selectOption('reader');
      await expect(page.locator('#site-export-profile-draft')).toHaveText(fixture.unsaved_profiles);
      await expect(page.locator('#site-export-profile option')).toHaveCount(1);
      await expect(page.locator('#site-export-download')).toBeDisabled();
      await expect.poll(() => receipts.at(-1)?.stage).toBe('profiles_empty');
      assert.ok(!JSON.stringify(receipts).includes('PRIVATE_SYNTHETIC_DRAFT'));
      await page.keyboard.press('Escape');
      await page.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: fixture.readonly}));
      const requests = [];
      page.on('request', request => requests.push(request.url()));
      await page.goto('http://lixity.test/');
      await expect(page.locator('.site-read-only-notice')).toHaveText(fixture.notice);
      for (const selector of ['#tab-view-project', '#project-actions', '#research-setup-guide', '#research-tab-search', '#research-tab-grounding', '#research-revision-edit-tab']) {
        await expect(page.locator(selector)).toBeHidden();
      }
      await page.locator('#tab-view-analysis').focus();
      await page.keyboard.press(width >= 1100 ? 'End' : 'End');
      await expect(page.locator('#tab-view-research')).toBeFocused();
      await page.locator('#tab-view-analysis').click();
      const blocked = await page.evaluate(async () => {
        try { await fetch('/api/site-export', {method:'POST'}); return false; } catch (_) { return true; }
      });
      assert.equal(blocked, true);
      assert.deepEqual(requests, ['http://lixity.test/']);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      if (locale === 'en') await page.screenshot({path: path.join(artifacts, `read-only-${width}.png`), fullPage: false});
      await page.close();
    }
    assert.deepEqual(errors, []);
    console.log('Read-only/native export desktop/mobile seven-locale checks passed:', artifacts);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
