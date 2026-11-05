// The recording prompt and capture controls wait for current project settings.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const artifacts = fs.mkdtempSync('/tmp/lixity-audio-loading-');
  const server = await startNativeServer(`
import json, os, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
import lixity.speech_status as speech_status
speech_status.worker_health = lambda target, **kwargs: {'target':target, 'state':'unavailable', 'model':None}
root = Path(sys.argv[1]); source = root / 'manuscript.md'
os.environ['XDG_DATA_HOME'] = str(root / 'app-data')
source.write_text('## One\\n\\nA synthetic passage.\\n')
(root / 'lixity.toml').write_text('language="de"\\n[audio]\\nselected="narrator"\\n[audio.profiles.narrator]\\nname="Narrator"\\nengine="qwen3"\\n')
LixityServerHandler.workspace_root = str(root)
LixityServerHandler.source_input = str(source)
LixityServerHandler.exports_dir = str(root / 'exports')
LixityServerHandler.language = 'de'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1',0), LixityServerHandler)
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}', 'source':str(source)}), flush=True)
server.serve_forever()
`, artifacts);
  const browser = await launchChromium();
  const original = fs.readFileSync(server.fixture.source);
  try {
    for (const viewport of [{width: 1440, height: 900}, {width: 390, height: 480}]) {
      const page = await browser.newPage({viewport});
      const errors = []; page.on('pageerror', error => errors.push(error.message));
      let releaseSettings;
      try {
        await page.goto(server.fixture.url);
        await page.locator('#tab-view-project').click();
        await page.evaluate(() => {
          window.microphoneAttempts = 0;
          navigator.mediaDevices.getUserMedia = async () => {
            ++window.microphoneAttempts;
            throw new DOMException('Synthetic refusal', 'NotAllowedError');
          };
        });
        let settingsRequested;
        const requested = new Promise(resolve => { settingsRequested = resolve; });
        const held = new Promise(resolve => { releaseSettings = resolve; });
        const readingText = 'This synthetic reading prompt arrived with the project settings.';
        await page.route('**/api/speech?*', async route => {
          const response = await route.fetch();
          const data = await response.json();
          data.calibration_texts = {phonetic: readingText, short: readingText};
          settingsRequested(); await held;
          await route.fulfill({response, json: data});
        }, {times: 1});
        await page.locator('#btn-project-record-voice').click();
        await requested;
        const record = page.locator('.voice-rec-btn');
        const status = page.locator('#speech-status');
        assert.equal(await record.isDisabled(), true,
          'Recording waits for the project prompt and settings, so a late read cannot replace spoken text');
        await record.evaluate(button => button.click());
        assert.equal(await page.evaluate(() => window.microphoneAttempts), 0,
          'A pending settings read must not request microphone access');
        await page.locator('#speech-tab-reference').click();
        assert.equal(await status.textContent(), await page.evaluate(() => uiLabel('speech_loading')));
        await page.locator('#modal-speech').screenshot({path: path.join(artifacts, `loading-${viewport.width}.png`)});
        releaseSettings();
        await page.waitForFunction(() => !document.querySelector('.voice-rec-btn').disabled);
        assert.equal(await page.locator('.voice-prompt-text').textContent(), readingText,
          'Capture is enabled only after the supplied reading text is displayed');
        await record.click();
        const denied = await page.evaluate(() => uiLabel('speech_mic_permission'));
        await page.waitForFunction(text => document.querySelector('#speech-status').textContent === text, denied);
        assert.equal(await page.evaluate(() => window.microphoneAttempts), 1);
        await page.locator('#modal-speech [data-speech-action=close]').click();

        await page.route('**/api/speech?*', route => route.fulfill({status: 400,
          json: {ok: false, message: 'Synthetic speech settings unavailable'}}), {times: 1});
        await page.locator('#btn-project-record-voice').click();
        await page.waitForFunction(() => document.querySelector('#speech-status').textContent === 'Synthetic speech settings unavailable');
        assert.equal(await record.isDisabled(), true, 'A failed settings read does not enable recording with stale text');
        await record.evaluate(button => button.click());
        assert.equal(await page.evaluate(() => window.microphoneAttempts), 1);
        await page.locator('#modal-speech').screenshot({path: path.join(artifacts, `unavailable-${viewport.width}.png`)});
        await page.locator('#modal-speech [data-speech-action=close]').click();
        await page.locator('#btn-project-record-voice').click();
        await page.waitForFunction(() => !document.querySelector('.voice-rec-btn').disabled);
        assert.notEqual(await page.locator('.voice-prompt-text').textContent(), readingText,
          'Reopening reads the current project prompt instead of retaining the previous response');
        assert.doesNotMatch(await status.textContent(), /Synthetic speech settings unavailable/);
        assert.deepEqual(errors, []);
      } finally { if (releaseSettings) releaseSettings(); await page.close(); }
    }
    assert.deepEqual(fs.readFileSync(server.fixture.source), original);
    console.log(`Audio loading desktop/mobile checks passed: ${artifacts}`);
  } finally { await browser.close(); await server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
