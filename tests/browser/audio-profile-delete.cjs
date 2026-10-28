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
''')
view = direction_state(root, source, language='de')
save_direction(root, source, {'anchor': view['passages'][0]['anchor'], 'profile_id': 'second'},
               expected_source_sha256=view['source_sha256'], expected_settings_sha256=view['settings_sha256'],
               expected_direction_sha256=view['direction_sha256'], language='de')
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
      await page.locator('#speech-profile').selectOption('second');
      await page.locator('[data-speech-action=remove_profile]').click();
      assert.equal(await page.locator('#speech-profile option[value=second]').count(), 1);
      assert.match(await page.locator('#modal-speech [role=status]').textContent(), /regie/i);
      await page.locator('#speech-profile').selectOption('spare');
      await page.locator('[data-speech-action=remove_profile]').click();
      assert.equal(await page.locator('#speech-profile option[value=spare]').count(), 0);
      assert.equal(await page.locator('#speech-profile').inputValue(), 'narrator');
      assert.match(await page.locator('#modal-speech [role=status]').textContent(), /sav|speicher/i);
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
  } finally { await browser.close(); await server.close(); }
  console.log('Audio profile removal stages changes and preserves one profile on desktop/mobile: ' + temp);
})().catch(error => { console.error(error); process.exitCode = 1; });
