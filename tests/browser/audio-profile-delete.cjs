const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const temp = fs.mkdtempSync('/tmp/lixity-audio-profile-delete-');
  const server = await startNativeServer(`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
import lixity.speech_status as speech_status
speech_status.worker_health = lambda target, **kwargs: {'target':target, 'state':'unavailable',
    'transport':'loopback' if target == 'local' else 'ssh', 'model':None}
from lixity.speech_direction import direction_state, save_direction
root = Path(sys.argv[1]); source = root / 'manuscript.md'
source.write_text('## One\\n\\nA bird crosses the garden.\\n')
(root / 'lixity.toml').write_text('''language = "de"
[audio]
selected = "narrator"
[audio.profiles.narrator]
name = "Narrator"
engine = "qwen3"
[audio.profiles.second]
name = "Second"
engine = "qwen3"
[audio.profiles.spare]
name = "Spare"
engine = "qwen3"
[audio.profiles.other]
name = "Other source"
engine = "qwen3"
''')
view = direction_state(root, source, language='de')
save_direction(root, source, {'anchor': view['passages'][0]['anchor'], 'profile_id': 'second'},
               expected_source_sha256=view['source_sha256'], expected_settings_sha256=view['settings_sha256'],
               expected_direction_sha256=view['direction_sha256'], language='de')
other = root / 'other.md'
other.write_text('## Other\\n\\nThe river rises.\\n')
other_view = direction_state(root, other, language='de')
save_direction(root, other, {'anchor': other_view['passages'][0]['anchor'], 'profile_id': 'other'},
               expected_source_sha256=other_view['source_sha256'], expected_settings_sha256=other_view['settings_sha256'],
               expected_direction_sha256=other_view['direction_sha256'], language='de')
LixityServerHandler.workspace_root = str(root)
LixityServerHandler.source_input = str(source)
LixityServerHandler.exports_dir = str(root / 'exports')
LixityServerHandler.language = 'de'
LixityServerHandler.refresh()
single = root / 'single'
single.mkdir()
(single / 'manuscript.md').write_text(source.read_text())
(single / 'lixity.toml').write_text('''language = "de"
manuscript = "manuscript.md"
[audio]
schema_version = "lixity-audio-settings/5"
selected = "narrator"
[audio.profiles.narrator]
name = "Only narrator"
engine = "qwen3"
''')
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'single':str(single)}), flush=True)
server.serve_forever()
`, temp);
  const browser = await launchChromium();
  try {
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}});
      await page.goto(server.fixture.url);
      await page.locator('#tab-view-project').click();
      await page.locator('#settings-speech').click();
      await page.locator('#speech-profile').selectOption('second');
      await page.locator('[data-speech-action=remove_profile]').click();
      assert.equal(await page.locator('#speech-profile option[value=second]').count(), 1);
      const guidance = await page.locator('#speech-status').textContent();
      assert.match(guidance, /regie/i);
      const configBefore = fs.readFileSync(temp + '/lixity.toml');
      await page.locator('#speech-profile').selectOption('other');
      await page.locator('[data-speech-action=remove_profile]').click();
      assert.equal(await page.locator('#speech-profile option[value=other]').count(), 0);
      await page.route('**/api/settings', async route => {
        const response = await route.fetch();
        assert.equal(response.status(), 400);
        const body = await response.json();
        assert.equal(body.code, 'voice-profile-in-use');
        await route.fulfill({response, json:{...body, message:'Changed diagnostic text'}});
      });
      await page.locator('[data-speech-action=save]').click();
      await page.locator('#speech-status').filter({hasText: guidance}).waitFor();
      assert.deepEqual(fs.readFileSync(temp + '/lixity.toml'), configBefore);
      await page.unroute('**/api/settings');
      await page.locator('[data-speech-action=profiles_discard]').click();
      assert.equal(await page.locator('#speech-profile option[value=other]').count(), 1);
      await page.locator('#speech-profile').selectOption('spare');
      await page.locator('[data-speech-action=remove_profile]').click();
      assert.equal(await page.locator('#speech-profile option[value=spare]').count(), 0);
      assert.equal(await page.locator('#speech-profile').inputValue(), 'narrator');
      assert.match(await page.locator('#speech-status').textContent(), /sav|speicher/i);
      await page.locator('#modal-speech').screenshot({path: temp + '/profile-delete-' + width + '.png'});
      if (width === 320) {
        const saved = page.waitForResponse(response => response.url().endsWith('/api/settings'));
        await page.locator('[data-speech-action=save]').click();
        assert.equal((await saved).status(), 200);
        await page.waitForLoadState('load');
        assert.doesNotMatch(fs.readFileSync(temp + '/lixity.toml', 'utf8'), /Spare/);
      }
      await page.close();
    }
    const page = await browser.newPage({viewport: {width:320,height:900}});
    assert.equal((await page.request.post(server.fixture.url + '/api/project-open', {data:{path:server.fixture.single}})).status(), 200);
    await page.goto(server.fixture.url);
    await page.locator('#tab-view-project').click();
    await page.locator('#settings-speech').click();
    const remove = page.locator('[data-speech-action=remove_profile]');
    await remove.click();
    const current = page.locator('.speech-profile-picker .speech-choice-readout strong');
    assert.ok((await current.textContent()).includes('kein Stimmprofil'));
    await page.locator('[data-speech-action=profiles_discard]').click();
    assert.equal(await current.textContent(), 'Only narrator');
    await remove.click();
    const posted = page.waitForRequest(request => request.url().endsWith('/api/settings'));
    const reloaded = page.waitForEvent('load');
    await page.locator('[data-speech-action=save]').click();
    const {audio} = (await posted).postDataJSON();
    assert.equal(audio.selected, '');
    assert.deepEqual(audio.profiles, {});
    await reloaded;
    await page.locator('#tab-view-project').click();
    await page.locator('#settings-speech').click();
    await page.locator('[data-speech-action=create]:enabled').waitFor();
    assert.equal(await remove.isVisible(), false);
    assert.equal(await page.locator('.speech-profile-footer').isVisible(), false);
    await page.close();
  } finally { await browser.close(); await server.close(); }
  console.log('Audio profile removal stages changes and supports an empty profile list on desktop/mobile: ' + temp);
})().catch(error => { console.error(error); process.exitCode = 1; });
