const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const temp = fs.mkdtempSync('/tmp/lixity-pronunciations-');
  const server = await startNativeServer(`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
root = Path(sys.argv[1]); source = root / 'manuscript.md'
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
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}});
      await page.goto(server.fixture.url);
      await page.locator('#tab-view-project').click();
      await page.locator('#settings-speech').click();
      await page.locator('#speech-lexicon > summary').click();
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
      assert.match(await page.locator('#modal-speech [role=status]').textContent(), /\S/);
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
        await page.waitForFunction(() => document.querySelector('#modal-speech [role=status]').textContent === 'Synthetic save conflict');
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
        const config = fs.readFileSync(temp + '/lixity.toml', 'utf8');
        assert.match(config, /Riwer/); assert.match(config, /Gardn/); assert.match(config, /Eksampl/); assert.match(config, /A=B/); assert.match(config, /NewEqual/);
      }
      await page.close();
    }
  } finally { await browser.close(); await server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
