const {startNativeServer} = require('./support/native-server.cjs');
// Native register settings round-trip, validation and draft preservation.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const assert = require('node:assert/strict');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-register-settings-'));
(async () => {
  const server = await startNativeServer(`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
from lixity.workspace_labels import WORKSPACE_LABELS
project = Path(sys.argv[1])
manuscript = project / 'manuscript.md'
manuscript.write_text('\\n\\n'.join(f'## Chapter {n}\\n\\n' + 'Rain falls softly across the quiet garden. ' * (20+n) for n in range(1,6)))
(project / 'lixity.toml').write_text('title = "Synthetic registers"\\n')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
keys = ('register_name', 'register_target', 'register_lower', 'register_upper')
labels = {language: {key: terms[key] for key in keys} for language, terms in WORKSPACE_LABELS.items()}
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'labels': labels}), flush=True)
server.serve_forever()
`, artifacts);
  let browser, release;
  try {
    const fixture = server.fixture;
    browser = await launchChromium();
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    page.setDefaultTimeout(10000);
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
    const endpoint = fixture.url + '/api/settings';
    for (const width of [1440, 320]) {
      assert.equal((await page.request.post(endpoint, {data: {language: 'en'}})).status(), 200);
      await page.setViewportSize({width, height: 1000});
      await page.goto(fixture.url);
      await page.locator('[data-view=project]').click();
      await page.locator('#settings-registers > summary').click();
      // Native validation and persistence run at desktop and mobile widths.
      while (await page.locator('[data-register-profile]').count()) await page.locator('[data-register-profile] > .row [data-register-remove]').first().click();
      while (await page.locator('[data-register-assignment]').count()) await page.locator('[data-register-assignment] [data-register-remove]').first().click();
      await page.locator('[data-register-add-profile]').click();
      const card = page.locator('[data-register-profile]');
      const name = 'Voice <img src=x onerror=alert(1)> \"A\" ' + width;
      await card.locator('[data-register-field=register_name]').fill(name);
      await card.locator('[data-register-add-target]').click();
      await card.locator('[data-register-field=register_target]').selectOption('asl');
      await card.locator('[data-register-field=register_lower]').fill('12');
      await card.locator('[data-register-field=register_upper]').fill('5');
      await page.locator('[data-register-add-assignment]').click();
      const assignment = page.locator('[data-register-assignment]');
      await assignment.locator('[data-register-field=register_selector]').fill('1');
      await assignment.locator('[data-register-field=register_name]').fill(name);
      let requests = 0;
      const observe = request => { if (request.url() === endpoint) requests++; };
      page.on('request', observe);
      await page.locator('[data-action=settings]').click();
      assert.equal(requests, 0, 'Reversed bounds are rejected before submitting');
      assert.ok(await card.locator('[data-register-field=register_upper]').evaluate(input => input.validationMessage));
      await card.locator('[data-register-field=register_lower]').fill('5');
      await card.locator('[data-register-field=register_upper]').fill('12');
      if (width === 1440) {
        await card.locator('[data-register-add-target]').click();
        const duplicate = card.locator('[data-register-range]').last();
        await duplicate.locator('[data-register-field=register_lower]').fill('5');
        await duplicate.locator('[data-register-field=register_upper]').fill('12');
        await page.locator('[data-action=settings]').click();
        assert.equal(requests, 0, 'Duplicate target is rejected before submitting');
        await card.locator('[data-register-range]').first().locator('[data-register-remove]').click();
        // Removing the conflicting row alone must clear stale validity.
      }
      const before = fs.readFileSync(path.join(artifacts, 'manuscript.md'));
      const response = page.waitForResponse(result => result.url() === endpoint);
      await page.locator('[data-action=settings]').click();
      assert.equal((await response).status(), 200);
      await page.waitForFunction(() => !document.querySelector('[data-action=settings]').disabled);
      page.off('request', observe);
      await page.reload();
      await page.locator('[data-view=project]').click();
      await page.locator('#settings-registers > summary').click();
      // Every locale renders saved machine values and exercises dynamic controls.
      for (const locale of ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl']) {
        if (locale !== 'en') {
          assert.equal((await page.request.post(endpoint, {data: {language: locale}})).status(), 200);
          await page.goto(fixture.url);
          await page.locator('[data-view=project]').click();
          await page.locator('#settings-registers > summary').click();
        }
        assert.match(await page.title(), /Synthetic registers/);
        assert.equal(await page.locator('#register-editor').isDisabled(), false);
        assert.equal(await card.locator('[data-register-field=register_name]').inputValue(), name);
        assert.equal(await card.locator('[data-register-field=register_target]').inputValue(), 'asl');
        assert.equal(await card.locator('[data-register-field=register_lower]').inputValue(), '5');
        assert.equal(await card.locator('[data-register-field=register_upper]').inputValue(), '12');
        assert.equal(await assignment.locator('[data-register-field=register_selector]').inputValue(), '1');
        assert.equal(await page.locator('#register-targets [data-register]').count(), 1);
        assert.equal(await page.locator('#register-targets img, #register-editor img').count(), 0, 'Names stay inert');
        await card.locator('[data-register-add-target]').click();
        const added = card.locator('[data-register-range]').last();
        for (const key of ['register_target', 'register_lower', 'register_upper']) {
          assert.equal(await added.locator('[data-register-field=' + key + ']').evaluate(input => input.parentElement.firstChild.textContent),
            fixture.labels[locale][key], 'Dynamically added controls use the selected locale');
        }
        assert.equal(await card.locator('[data-register-field=register_name]').evaluate(input => input.parentElement.firstChild.textContent),
          fixture.labels[locale].register_name);
        await added.locator('[data-register-remove]').click();
        assert.equal(await card.locator('[data-register-range]').count(), 1, 'Removing a draft preserves the saved range');
        assert.deepEqual(fs.readFileSync(path.join(artifacts, 'manuscript.md')), before);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'No horizontal viewport overflow');
        await page.locator('#settings-registers').screenshot({path: path.join(artifacts, `${locale}-${width}.png`)});
      }
    }
    // A newly added row while a real save is pending must prevent reload.
    let ready;
    const accepted = new Promise(resolve => { ready = resolve; });
    const gate = new Promise(resolve => { release = resolve; });
    await page.route(endpoint, async route => { const response = await route.fetch(); ready(); await gate; await route.fulfill({response}); });
    await page.locator('[data-register-profile] [data-register-field=register_lower]').fill('4');
    await page.locator('[data-action=settings]').click(); await accepted;
    await page.locator('[data-register-add-profile]').click();
    await page.locator('[data-register-profile]').last().locator('[data-register-field=register_name]').fill('New unsaved voice');
    const response = page.waitForResponse(result => result.url() === endpoint); release(); await response;
    await page.waitForFunction(() => !document.querySelector('[data-action=settings]').disabled);
    await page.waitForFunction(() => Boolean(window.finishSettingsReload));
    await page.evaluate(() => window.finishSettingsReload());
    assert.equal(await page.locator('[data-register-profile]').count(), 2, 'Pending save preserves new draft rows');
    assert.deepEqual(errors, []);
    assert.deepEqual(warnings, []);
    console.log('Register settings passed: desktop/mobile native validation and saves; seven-locale controls, machine values, inert names and held drafts. Screenshots: ' + artifacts);
  } finally {
    if (release) release();
    try { if (browser) await browser.close(); }
    finally { await server.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
