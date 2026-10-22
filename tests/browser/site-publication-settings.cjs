// Curated publication profiles share native settings validation/save/draft handling.
const {startNativeServer} = require('./support/native-server.cjs');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const assert = require('node:assert/strict');
const {expect} = require(path.join(playwrightModule, 'test'));
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-site-publication-settings-'));
(async () => {
  const server = await startNativeServer(`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.config import prepare_project_settings
from lixity.research import api
from lixity.server import LixityServerHandler
from lixity.workspace_labels import WORKSPACE_LABELS
project = Path(sys.argv[1])
api.init(project, title='Synthetic publication editor')
manuscript = project / 'manuscript.md'
manuscript.write_text('## Opening\\n\\nRain falls across the quiet garden.\\n\\n## Arrival\\n\\nA visitor enters.\\n')
dossier = api.create_dossier(project, 'Setting <img src=x onerror=alert(1)>',
    '## Background\\n\\nA public setting note.\\n\\n## Repeated\\n\\nOne.\\n\\n## Repeated\\n\\nTwo.')
api.revise_record(project, 'dossier', dossier['dossier_id'], expected_revision=1,
    changes={'body': '## Background\\n\\nRevised public setting note.\\n\\n## Later\\n\\nLater note.'},
    change_kind='correction', reason='Synthetic version')
unknown = 'urn:uuid:11111111-1111-4111-8111-111111111111'
prepare_project_settings(project, {'site_publications': {'existing': {'title': 'Preserved profile',
    'entries': [{'dossier_id': unknown, 'revision': 7, 'section': 'Former section',
    'reveal_after_chapter': 1}]}}}).commit()
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
labels = {locale: {key: value for key, value in terms.items() if key.startswith('publication_editor_')}
          for locale, terms in WORKSPACE_LABELS.items()}
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'dossier': dossier['dossier_id'],
                  'unknown': unknown, 'labels': labels}), flush=True)
server.serve_forever()
`, artifacts);
  let browser, release;
  try {
    browser = await launchChromium();
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [], warnings = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (['error', 'warning'].includes(message.type())) warnings.push(message.text()); });
    await page.addInitScript(() => {
      const original = window.setTimeout;
      window.setTimeout = function(callback, delay, ...args) {
        if (delay === 1200) { window.finishSettingsReload = () => callback(...args); return 0; }
        return original.call(window, callback, delay, ...args);
      };
    });
    const fixture = server.fixture, endpoint = fixture.url + '/api/settings';
    const field = (scope, key) => scope.locator('[data-site-publication-field=' + key + ']');
    let payload;
    page.on('request', request => { if (request.url() === endpoint) payload = request.postDataJSON(); });
    const manuscriptBefore = fs.readFileSync(path.join(artifacts, 'manuscript.md'));
    for (const width of [1440, 320]) {
      await page.setViewportSize({width, height: 1000});
      await page.goto(fixture.url);
      await page.locator('#tab-view-project').click();
      await page.locator('#settings-site-publications > summary').click();
      const editor = page.locator('#site-publication-editor');
      const existing = editor.locator('[data-site-publication-profile]').filter({has: page.locator('[data-site-publication-field=id][value=existing]')});
      await expect(editor.locator('[data-site-publication-profile]')).toHaveCount(width === 1440 ? 1 : 2);
      // Unknown or withdrawn references stay selected until the author corrects them.
      const initial = editor.locator('[data-site-publication-profile]').first();
      await initial.locator(':scope > summary').click();
      const unresolved = initial.locator('[data-site-publication-entry]').first();
      await unresolved.locator(':scope > summary').click();
      await expect(field(unresolved, 'dossier_id')).toHaveValue(fixture.unknown);
      await expect(field(unresolved, 'revision')).toHaveValue('7');
      await expect(field(unresolved, 'section')).toHaveValue('Former section');
      assert.equal(await page.evaluate(() => window.LixityPublicationSettings.readChanges().site_publications), undefined);
      if (width === 1440) {
        await editor.locator('[data-site-publication-add-profile]').click();
        const profile = editor.locator('[data-site-publication-profile]').last();
        await field(profile, 'id').fill('readers');
        await field(profile, 'title').fill('Reader <img src=x onerror=alert(1)>');
        await field(profile, 'introduction').fill('Authored public introduction.');
        await profile.locator('[data-site-publication-add-entry]').click();
        const entry = profile.locator('[data-site-publication-entry]').first();
        await expect(field(entry, 'include_citations')).not.toBeChecked();
        await expect(field(entry, 'include_geography')).not.toBeChecked();
        await field(entry, 'dossier_id').selectOption(fixture.dossier);
        await field(entry, 'revision').selectOption('1');
        await expect(field(entry, 'section').locator('option[value=Background]')).toHaveCount(1);
        await expect(field(entry, 'section').locator('option[value=Repeated]')).toHaveCount(0);
        await field(entry, 'section').selectOption('Background');
        await field(entry, 'reveal_after_chapter').fill('1.5');
        let requests = 0;
        const count = request => { if (request.url() === endpoint) requests++; };
        page.on('request', count);
        await profile.locator(':scope > summary').click();
        await page.locator('[data-action=settings]').click();
        assert.equal(requests, 0, 'Fractional chapter gates fail before submitting');
        await expect(profile).toHaveAttribute('open', '');
        await expect(entry).toHaveAttribute('open', '');
        await field(entry, 'reveal_after_chapter').fill('1');
        await field(entry, 'title').fill('Public heading');
        await field(profile, 'id').fill('existing');
        await page.locator('[data-action=settings]').click();
        assert.equal(requests, 0, 'Duplicate profile IDs fail before submitting');
        await field(profile, 'id').fill('readers');
        await profile.locator('[data-site-publication-add-entry]').click();
        const later = profile.locator('[data-site-publication-entry]').last();
        await field(later, 'dossier_id').selectOption(fixture.dossier);
        await field(later, 'title').fill('Temporary ordered entry');
        const defaults = await page.evaluate(() => window.LixityPublicationSettings.readChanges().site_publications.readers.entries.at(-1));
        assert.equal(defaults.reveal_after_chapter, 0);
        assert.equal(Object.hasOwn(defaults, 'revision'), false, 'Blank version retains explicit current-at-export semantics');
        assert.equal(Object.hasOwn(defaults, 'section'), false, 'Whole body is an explicit displayed choice');
        await later.locator('[data-site-publication-up]').click();
        assert.equal(await page.evaluate(() => window.LixityPublicationSettings.readChanges().site_publications.readers.entries[0].title),
          'Temporary ordered entry', 'Entry ordering is preserved in the saved array');
        await profile.locator('[data-site-publication-entry]').first().locator('[data-site-publication-remove]').click();
        await expect(profile.locator('[data-site-publication-add-entry]')).toBeFocused();
        const response = page.waitForResponse(result => result.url() === endpoint);
        await page.locator('[data-action=settings]').click();
        assert.equal((await response).status(), 200);
        page.off('request', count);
        await page.waitForFunction(() => !document.querySelector('[data-action=settings]').disabled);
        assert.equal(payload.site_publications.existing.entries[0].dossier_id, fixture.unknown);
        assert.deepEqual(payload.site_publications.readers.entries[0], {dossier_id: fixture.dossier,
          revision: 1, section: 'Background', reveal_after_chapter: 1, title: 'Public heading',
          include_citations: false, include_geography: false});
        assert.equal(Object.hasOwn(payload, 'include_source_files'), false);
        assert.deepEqual(await page.evaluate(() => window.LixityPublicationSettings.savedProfiles()), payload.site_publications);
      }
      for (const locale of ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl']) {
        await page.locator('#set-language').selectOption(locale);
        const response = page.waitForResponse(result => result.url() === endpoint);
        await page.locator('[data-action=settings]').click();
        assert.equal((await response).status(), 200);
        await page.waitForFunction(() => !document.querySelector('[data-action=settings]').disabled);
        await page.reload();
        await page.locator('#tab-view-project').click();
        try { await page.locator('#settings-site-publications > summary').click({timeout: 5000}); }
        catch (error) {
          console.error('Settings state:', await page.evaluate(() => ({url: location.href, body: document.body.dataset,
            active: [...document.querySelectorAll('.view-pane.active')].map(node => node.id),
            parents: [...document.querySelector('#settings-site-publications').parentElement.parentElement.children].map(node => [node.tagName,node.id,node.hidden])})));
          await page.screenshot({path:path.join(artifacts,'settings-hidden.png')}); throw error;
        }
        const profile = editor.locator('[data-site-publication-profile]').last();
        await profile.locator(':scope > summary').click();
        const entry = profile.locator('[data-site-publication-entry]').first();
        await entry.locator(':scope > summary').click();
        await expect(field(profile, 'id')).toHaveValue('readers');
        await expect(field(entry, 'section')).toHaveValue('Background');
        await expect(field(entry, 'include_citations')).not.toBeChecked();
        assert.equal(await field(entry, 'section').evaluate(input => input.parentElement.firstChild.textContent), fixture.labels[locale].publication_editor_section);
        assert.equal(await editor.locator('img').count(), 0, 'Titles stay inert');
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${locale} editor fits ${width}px`);
        if (locale === 'en') await page.locator('#settings-site-publications').screenshot({path: path.join(artifacts, `editor-${width}.png`)});
        await profile.locator(':scope > summary').click();
      }
      const zoomProfile = editor.locator('[data-site-publication-profile]').last();
      await zoomProfile.locator(':scope > summary').click();
      await page.evaluate(() => { document.documentElement.style.zoom = '2'; });
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const outside = await editor.evaluate(host => [...host.querySelectorAll('*')].filter(node => {
        const box=node.getBoundingClientRect(); return box.width && (box.right>innerWidth+1 || box.left < -1);
      }).map(node=>[node.tagName,node.id,node.getBoundingClientRect().right]));
      assert.deepEqual(outside, [], 'Profile controls fit the visible page at 200% zoom');
      const horizontal = await page.evaluate(() => {
        scrollTo({left:1e6, top:scrollY, behavior:'instant'});
        const result = {scrollX, width:innerWidth, scrollWidth:document.documentElement.scrollWidth};
        scrollTo({left:0, top:scrollY, behavior:'instant'}); return result;
      });
      if (horizontal.scrollX) console.error('Zoom travel:', width, await page.locator('html').getAttribute('lang'), horizontal);
      assert.equal(horizontal.scrollX, 0, 'Zoomed settings have no actual horizontal travel');
      assert.ok(horizontal.scrollWidth <= horizontal.width, 'Zoomed document remains within the viewport');
      await editor.screenshot({path:path.join(artifacts, `editor-zoom-${width}.png`)});
      await page.evaluate(() => { document.documentElement.style.zoom = ''; });
      await zoomProfile.locator(':scope > summary').click();
    }
    // An application-level server rejection preserves the draft and accepted snapshot.
    const rejectedProfile = page.locator('[data-site-publication-profile]').last();
    await rejectedProfile.locator(':scope > summary').click();
    const acceptedBefore = await page.evaluate(() => window.LixityPublicationSettings.savedProfiles());
    await field(rejectedProfile, 'introduction').fill('Rejected draft stays visible');
    await page.route(endpoint, route => route.fulfill({json:{ok:false,message:'Synthetic rejected settings save'}}));
    const rejectedResponse = page.waitForResponse(result => result.url() === endpoint);
    await page.locator('[data-action=settings]').click(); await rejectedResponse;
    await page.waitForFunction(() => !document.querySelector('[data-action=settings]').disabled);
    await expect(page.locator('#ctl-status')).toContainText('Synthetic rejected settings save');
    await expect(field(rejectedProfile, 'introduction')).toHaveValue('Rejected draft stays visible');
    assert.deepEqual(await page.evaluate(() => window.LixityPublicationSettings.savedProfiles()), acceptedBefore);
    await page.unroute(endpoint);
    await rejectedProfile.locator(':scope > summary').click();
    // A real save may succeed while newer local rows remain unsaved.
    let ready;
    const accepted = new Promise(resolve => { ready = resolve; });
    const gate = new Promise(resolve => { release = resolve; });
    await page.route(endpoint, async route => { const response = await route.fetch(); ready(); await gate; await route.fulfill({response}); });
    const editor = page.locator('#site-publication-editor');
    const profile = editor.locator('[data-site-publication-profile]').last();
    await profile.locator(':scope > summary').click();
    await field(profile, 'introduction').fill('Saved before later draft');
    await page.locator('[data-action=settings]').click(); await accepted;
    await editor.locator('[data-site-publication-add-profile]').click();
    const draft = editor.locator('[data-site-publication-profile]').last();
    await field(draft, 'id').fill('unsaved'); await field(draft, 'title').fill('Later draft');
    const response = page.waitForResponse(result => result.url() === endpoint); release(); await response;
    await page.waitForFunction(() => !document.querySelector('[data-action=settings]').disabled);
    await page.evaluate(() => window.finishSettingsReload && window.finishSettingsReload());
    await expect(editor.locator('[data-site-publication-profile]')).toHaveCount(3);
    assert.equal(await page.evaluate(() => Object.hasOwn(window.LixityPublicationSettings.savedProfiles(), 'unsaved')), false);
    assert.ok(await page.evaluate(() => window.LixityPublicationSettings.readChanges().site_publications.unsaved));
    await page.unroute(endpoint);
    // A future field or an invalid blank section is retained until explicitly repaired.
    for (const malformed of [
      {future: {title: 'Kept future data', entries: [], future_field: 'KEEP THIS'}},
      {future: {title: 'Kept blank section', entries: [{dossier_id: fixture.unknown, section: ''}]}},
    ]) {
      const nativeHtml = await (await page.request.get(fixture.url)).text();
      const original = JSON.stringify(malformed);
      const escaped = original.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      const recoveryUrl = fixture.url + '/recovery-fixture';
      await page.route(recoveryUrl, route => route.fulfill({contentType:'text/html',
        body:nativeHtml.replace(/(id="site-publication-editor"[^>]*data-initial=")[^"]*/, '$1' + escaped)}));
      await page.goto(recoveryUrl);
      await page.locator('#tab-view-project').click();
      await page.locator('#settings-site-publications > summary').click();
      const recovery = page.locator('[data-site-publication-field=recovery]');
      await expect(recovery).toHaveValue(original);
      assert.deepEqual(await page.evaluate(() => window.LixityPublicationSettings.readChanges()), {},
        'Unchanged malformed data does not block unrelated settings');
      assert.equal(await recovery.evaluate(input => input.checkValidity()), true);
      const response = page.waitForResponse(result => result.url() === endpoint);
      await page.locator('[data-action=settings]').click();
      assert.equal((await response).status(), 200);
      await page.waitForFunction(() => !document.querySelector('[data-action=settings]').disabled);
      assert.equal(Object.hasOwn(payload, 'site_publications'), false);
      await expect(recovery).toHaveValue(original);
      await recovery.fill('{broken');
      assert.deepEqual(await page.evaluate(() => window.LixityPublicationSettings.readChanges()), {});
      assert.equal(await recovery.evaluate(input => input.checkValidity()), false);
      await recovery.fill('{}');
      await page.locator('[data-site-publication-recover]').click();
      assert.deepEqual(await page.evaluate(() => window.LixityPublicationSettings.readChanges()), {site_publications:{}},
        'An explicitly corrected empty map remains an intentional clear operation');
      await page.unroute(recoveryUrl);
    }
    assert.deepEqual(fs.readFileSync(path.join(artifacts, 'manuscript.md')), manuscriptBefore);
    assert.deepEqual(errors, []); assert.deepEqual(warnings, []);
    console.log('Publication settings passed: native saves, unresolved refs, unique pinned sections,7 locales, desktop/mobile/zoom, inert text and held drafts. Screenshots: ' + artifacts);
  } finally {
    if (release) release();
    try { if (browser) await browser.close(); }
    finally { await server.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
