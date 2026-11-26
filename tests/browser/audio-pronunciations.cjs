const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const temp = fs.mkdtempSync('/tmp/lixity-pronunciations-');
  const server = await startNativeServer(`
import json, os, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
import lixity.speech_status as speech_status
speech_status.worker_health = lambda target, **kwargs: {'target':target, 'state':'unavailable',
    'transport':'loopback' if target == 'local' else 'ssh', 'model':None}
root = Path(sys.argv[1]) / 'project'; root.mkdir()
source = root / 'manuscript.md'
os.environ['XDG_DATA_HOME'] = str(root.parent / 'data')
source.write_text('## One\\n\\nA synthetic passage.\\n')
(root / 'lixity.toml').write_text('''language = "de"
[audio]
selected = "narrator"
[audio.profiles.narrator]
name = "Narrator"
engine = "qwen3"
pronunciations = { "Example" = "Eksampl", "River" = "Rivver", "A=B" = "Equal" }
[audio.profiles.second]
name = "Second"
engine = "qwen3"
''')
LixityServerHandler.workspace_root = str(root)
LixityServerHandler.source_input = str(source)
LixityServerHandler.exports_dir = str(root / 'exports')
LixityServerHandler.language = 'de'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}'}), flush=True)
server.serve_forever()
`, temp);
  const browser = await launchChromium();
  try {
    async function openPronunciation(page) {
      await page.locator('#tab-view-project').click();
      await page.locator('#settings-speech').click();
      await page.locator('#speech-lexicon > summary').click();
    }
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}});
      await page.goto(server.fixture.url);
      await openPronunciation(page);
      assert.equal(await page.locator('#speech-pronunciation_scope').inputValue(), 'profile');
      await page.locator('#speech-pronunciation_search').fill('River');
      assert.equal(await page.locator('[data-pronunciation-row]:visible').count(), 1);
      await page.locator('#speech-pronunciation_search').fill('No matching entry');
      assert.equal(await page.locator('[data-pronunciation-row]:visible').count(), 0);
      assert.ok(await page.locator('#speech-lexicon .pronunciation-empty').isVisible());
      await page.locator('#speech-pronunciation_search').fill('River');
      await page.locator('[data-pronunciation-row]:visible button').first().click();
      assert.equal(await page.locator('#speech-pronunciation_term').inputValue(), 'River');
      await page.locator('#speech-pronunciation_spoken').fill('Riwer');
      await page.locator('[data-speech-action=pronunciation_apply]').click();
      assert.match(await page.locator('#speech-pronunciations').inputValue(), /River=Riwer/);
      await page.locator('[data-speech-action=close]').click();
      assert.equal(await page.locator('#modal-speech').isVisible(), true, 'Applied entries remain unsaved project changes');
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#modal-speech').isVisible(), true, 'Escape preserves applied entries');
      await page.locator('#speech-pronunciation_search').fill('');
      assert.equal(await page.locator('[data-pronunciation-row]:visible').count(), 3);
      await page.locator('#speech-pronunciation_term').fill('Garden');
      await page.locator('#speech-pronunciation_spoken').fill('Gardn');
      await page.locator('[data-speech-action=pronunciation_apply]').click();
      assert.equal(await page.locator('[data-pronunciation-row]:visible').count(), 4);
      await page.locator('#speech-pronunciation_search').fill('A=B');
      await page.locator('[data-pronunciation-row]:visible button').first().click();
      await page.locator('#speech-pronunciation_spoken').fill('NewEqual');
      await page.locator('[data-speech-action=pronunciation_apply]').click();
      await page.locator('#speech-pronunciation_search').fill('');
      await page.locator('#speech-pronunciation_term').fill('Example');
      await page.locator('#speech-pronunciation_spoken').fill('Replacement');
      await page.locator('#speech-pronunciation_search').fill('River');
      await page.locator('[data-pronunciation-row]:visible button').first().click();
      assert.equal(await page.locator('#speech-pronunciation_term').inputValue(), 'Example', 'Editing another row preserves the unfinished draft');
      assert.equal(await page.locator('#speech-pronunciation_spoken').inputValue(), 'Replacement');
      await page.locator('[data-speech-action=remove_profile]').click();
      assert.equal(await page.locator('#speech-pronunciation_term').inputValue(), 'Example', 'Removing a profile cannot erase an unfinished entry');
      assert.equal(await page.locator('#speech-profile').inputValue(), 'narrator');
      await page.locator('[data-speech-action=pronunciation_apply]').click();
      assert.match(await page.locator('#speech-status').textContent(), /\S/);
      assert.match(await page.locator('#speech-pronunciations').inputValue(), /Example=Eksampl/);
      await page.locator('[data-speech-action=close]').click();
      assert.equal(await page.locator('#modal-speech').isVisible(), true, 'Closing preserves an unfinished entry');
      await page.locator('[data-speech-action=pronunciation_discard]').click();
      await page.locator('#modal-speech').screenshot({path:temp + '/pronunciations-' + width + '.png'});
      if (width === 1440) {
        await page.evaluate(() => { document.body.dataset.manuscriptSourceSha256 = 'e'.repeat(64); });
        assert.equal(await page.locator('#modal-speech').isVisible(), true, 'Context changes retain applied unsaved entries');
        assert.match(await page.locator('#speech-pronunciations').inputValue(), /River=Riwer/);
        assert.equal(await page.locator('[data-speech-action=save]').isDisabled(), true);
        await page.locator('[data-speech-action=profiles_discard]').click();
        await page.locator('[data-speech-action=close]').click();
        assert.equal(await page.locator('#modal-speech').isVisible(), false, 'Explicit discard permits closing');
      } else {
        await page.route('**/api/settings', route => route.fulfill({status:409, json:{ok:false, message:'Synthetic save conflict'}}), {times:1});
        await page.locator('[data-speech-action=save]').click();
        await page.waitForFunction(() => document.querySelector('#speech-status').textContent === 'Synthetic save conflict');
        assert.equal(await page.locator('#speech-pronunciation_term').isDisabled(), false, 'Failed save unlocks the preserved draft');
        assert.match(await page.locator('#speech-pronunciations').inputValue(), /River=Riwer/);
        let release, began;
        const waiting = new Promise(resolve => { release = resolve; });
        const started = new Promise(resolve => { began = resolve; });
        await page.route('**/api/settings', async route => { began(); await waiting; await route.continue(); }, {times:1});
        const save = page.waitForResponse(response => response.url().endsWith('/api/settings'));
        await page.locator('[data-speech-action=save]').click();
        await started;
        assert.equal(await page.locator('#speech-pronunciation_term').isDisabled(), true, 'Pending save freezes profile inputs');
        assert.equal(await page.locator('#speech-profile').isDisabled(), true);
        await page.locator('[data-speech-action=close]').click();
        assert.equal(await page.locator('#modal-speech').isVisible(), true, 'Pending save cannot be closed');
        release();
        assert.equal((await save).status(), 200);
        await page.waitForLoadState('load');
        const config = fs.readFileSync(temp + '/project/lixity.toml', 'utf8');
        assert.match(config, /Riwer/); assert.match(config, /Gardn/); assert.match(config, /Eksampl/); assert.match(config, /A=B/); assert.match(config, /NewEqual/);
      }
      await page.close();
    }
    const page = await browser.newPage({viewport: {width: 320, height: 900}});
    await page.goto(server.fixture.url);
    await openPronunciation(page);
    const scope = page.locator('#speech-pronunciation_scope');
    const ipa = page.locator('#speech-pronunciation_ipa');
    const term = page.locator('#speech-pronunciation_term');
    const spoken = page.locator('#speech-pronunciation_spoken');
    const rows = page.locator('[data-pronunciation-row]:visible');
    const config = temp + '/project/lixity.toml';
    await scope.selectOption('project');
    assert.equal(await ipa.isVisible(), false, 'Older schemas expose the reviewed update before project editing');
    await page.locator('[data-speech-action=pronunciation_schema_review]').click();
    await Promise.all([
      page.waitForNavigation(),
      page.locator('[data-speech-action=schema_apply]').click(),
    ]);
    assert.equal(fs.readdirSync(temp + '/data/lixity/audio-backups').length, 1);
    await openPronunciation(page);
    assert.equal(await scope.inputValue(), 'project');
    assert.equal(await ipa.isVisible(), true);
    assert.equal(await page.locator('#speech-lexicon').evaluate(box => box.scrollWidth <= box.clientWidth), true);
    await term.fill('Vogel');
    await ipa.fill('ˈfoːɡəl');
    await scope.selectOption('profile');
    assert.equal(await scope.inputValue(), 'project', 'Scope switches preserve the unfinished IPA draft');
    assert.equal(await ipa.inputValue(), 'ˈfoːɡəl');
    await spoken.fill('Fohgel');
    await page.locator('[data-speech-action=pronunciation_apply]').click();
    assert.match(await rows.first().textContent(), /ˈfoːɡəl.*Fohgel/);
    await term.fill('Kiel');
    await ipa.fill('kiːl');
    await page.locator('[data-speech-action=pronunciation_apply]').click();
    assert.equal(await rows.count(), 2, 'IPA without a respelling is a valid entry');
    await scope.selectOption('profile');
    assert.equal(await ipa.isVisible(), false);
    assert.match(await page.locator('#speech-pronunciations').inputValue(), /River=Riwer/);
    const savedLexicon = page.waitForNavigation();
    await page.locator('[data-speech-action=save]').click();
    await savedLexicon;
    assert.match(fs.readFileSync(config, 'utf8'), /lixity-pronunciation-lexicon\/1/);
    await openPronunciation(page);
    assert.equal(await scope.inputValue(), 'project');
    assert.equal(await rows.count(), 2);
    await rows.filter({hasText:'Kiel'}).locator('[data-speech-action=pronunciation_remove]').click();
    assert.equal(await rows.count(), 1);
    const savedRemoval = page.waitForNavigation();
    await page.locator('[data-speech-action=save]').click();
    await savedRemoval;
    const persisted = fs.readFileSync(config, 'utf8');
    assert.match(persisted, /Vogel.*ˈfoːɡəl.*Fohgel/);
    assert.doesNotMatch(persisted, /Kiel/);
    assert.match(persisted, /Riwer/);
    assert.match(persisted, /NewEqual/);
    assert.equal(fs.readFileSync(temp + '/project/manuscript.md', 'utf8'), '## One\n\nA synthetic passage.\n');
    await page.close();
  } finally { await browser.close(); await server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
