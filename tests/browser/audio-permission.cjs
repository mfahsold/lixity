// Exercise browser permission enforcement over real native HTTP headers.
// Chromium supplies a synthetic device; getUserMedia itself is never replaced.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const artifacts = fs.mkdtempSync('/tmp/lixity-audio-permission-');
  const server = await startNativeServer(`
import json, os, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
import lixity.speech_status as speech_status
speech_status.worker_health = lambda target, **kwargs: {'target':target, 'state':'unavailable', 'model':None}
root = Path(sys.argv[1]); source = root / 'manuscript.md'
os.environ['XDG_DATA_HOME'] = str(root / 'app-data')
source.write_text('## Synthetic chapter\\n\\nA bird crosses the quiet garden.\\n')
from lixity.speech import generate_silence_wav
from lixity.speech_references import save_reference
reference = save_reference(root, generate_silence_wav(1), 'Initial synthetic reference.')
(root / 'lixity.toml').write_text(f'''language = "de"
[audio]
selected = "narrator"
[audio.profiles.narrator]
name = "Narrator"
engine = "qwen3-base"
voice = "reference"
reference_id = "{reference.id}"
''')
LixityServerHandler.workspace_root = str(root)
LixityServerHandler.source_input = str(source)
LixityServerHandler.exports_dir = str(root / 'exports')
LixityServerHandler.language = 'de'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}', 'source':str(source)}), flush=True)
server.serve_forever()
`, artifacts);
  const browser = await launchChromium({args: ['--use-fake-device-for-media-stream']});
  const manuscript = fs.readFileSync(server.fixture.source);
  try {
    for (const width of [1440, 320]) {
      const context = await browser.newContext({viewport: {width, height: 900}});
      await context.grantPermissions(['microphone'], {origin: server.fixture.url});
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      try {
        const response = await page.goto(server.fixture.url);
        const policy = response.headers()['permissions-policy'];
        const microphone = await page.evaluate(async () => {
          try {
            const stream = await navigator.mediaDevices.getUserMedia({audio: true});
            stream.getTracks().forEach(track => track.stop());
            return {ok: true};
          } catch (error) { return {ok: false, name: error.name, message: error.message}; }
        });
        assert.equal(microphone.ok, true,
          'Actual getUserMedia with granted microphone permission must succeed under ' + policy + ': ' + JSON.stringify(microphone));
        await page.locator('#tab-view-project').click();
        await page.locator('#btn-project-record-voice').click();
        await page.waitForFunction(() => document.querySelector('#speech-name')?.value === 'Narrator');
        await page.locator('.voice-rec-btn').click();
        await page.waitForFunction(() => document.querySelector('.voice-rec-btn')?.classList.contains('is-recording') ||
          (!document.querySelector('.voice-rec-btn')?.disabled &&
            document.querySelector('#speech-status')?.textContent !== uiLabel('speech_mic_pending')))
          .catch(async error => { throw new Error('Recorder did not settle: ' + await page.locator('#speech-status').textContent(), {cause: error}); });
        assert.equal(await page.locator('.voice-rec-btn').evaluate(button => button.classList.contains('is-recording')), true,
          'Granted browser microphone must record under the actual Permissions-Policy (' + policy + '): ' +
          await page.locator('#speech-status').textContent());
        assert.match(policy, /microphone=\(self\)/);
        assert.equal(await page.evaluate(() => document.featurePolicy.allowsFeature('microphone')), true);
        assert.equal(await page.locator('#speech-status').textContent(),
          await page.evaluate(() => uiLabel('speech_record_running')),
          'Successful microphone acquisition visibly confirms that recording is running');
        await page.waitForFunction(() => document.querySelector('.voice-rec-timer')?.textContent.startsWith('00:02'));
        if (width === 320) {
          await page.locator('.voice-rec-btn').scrollIntoViewIfNeeded();
          await page.locator('#modal-speech').screenshot({path: path.join(artifacts, 'running-320.png')});
        }
        await page.locator('.voice-rec-btn').click();
        assert.equal(await page.locator('.voice-save-btn').isEnabled(), false,
          'A captured reading prompt remains a draft until the spoken transcript is confirmed');
        await page.waitForFunction(()=>document.querySelector('.voice-take-stats').textContent.includes('24000 Hz'));
        assert.match(await page.locator('.voice-take-stats').textContent(), /24000 Hz/);
        assert.equal(await page.locator('#speech-take_confirmed').isChecked(),false);
        const transcript = `Synthetic browser device ${width}.`;
        await page.locator('.voice-take-card textarea').fill(transcript);
        await page.locator('#speech-take_confirmed').check();
        assert.equal(await page.locator('.voice-save-btn').isEnabled(),true);
        const submitted = page.waitForRequest(request => new URL(request.url()).pathname === '/api/audio-microphone');
        const reloaded = page.waitForEvent('load');
        reloaded.catch(() => {});
        await page.locator('.voice-save-btn').click();
        const payload = (await submitted).postDataJSON();
        assert.equal(payload.transcript, transcript);
        const wav = Buffer.from(payload.audio, 'base64');
        assert.equal(wav.subarray(0, 4).toString(), 'RIFF');
        assert.equal(wav.readUInt32LE(24), 24000);
        assert.equal(wav.readUInt16LE(22), 1);
        assert.ok(wav.length > 48000, 'At least one second of real browser-acquired PCM was recorded');
        await reloaded;
        await page.locator('#tab-view-project').click();
        await page.locator('#btn-project-record-voice').click();
        await page.waitForFunction(text => document.querySelector('.author-voice-studio .voice-active-card')?.textContent.includes(text), transcript);
        assert.equal(await page.locator('#speech-engine').inputValue(), 'qwen3-base');
        await page.locator('#modal-speech').screenshot({path: path.join(artifacts, `granted-${width}.png`)});
        assert.deepEqual(errors, []);
      } finally { await context.close(); }
    }

    const denied = await browser.newContext({viewport: {width: 320, height: 900}});
    // Permissions omitted from the explicit grant are denied by Chromium.
    await denied.grantPermissions([], {origin: server.fixture.url});
    const page = await denied.newPage();
    try {
      await page.goto(server.fixture.url);
      assert.equal(await page.evaluate(() => document.featurePolicy.allowsFeature('microphone')), true,
        'The denial case must test browser permission, not a server policy denial');
      assert.equal(await page.evaluate(async () => (await navigator.permissions.query({name: 'microphone'})).state), 'denied');
      await page.locator('#tab-view-project').click();
      await page.locator('#btn-project-record-voice').click();
      await page.waitForFunction(() => document.querySelector('#speech-name')?.value === 'Narrator');
      await page.locator('.voice-rec-btn').click();
      await page.waitForFunction(() => document.querySelector('#speech-status')?.textContent === uiLabel('speech_mic_permission'));
      assert.match(await page.locator('#speech-status').textContent(), /Browser|Berechtigung|erlaub/i);
      assert.equal(await page.locator('.voice-rec-btn').isEnabled(), true, 'Permission refusal leaves retry available');
      assert.equal(await page.locator('.voice-rec-btn').evaluate(button => button.classList.contains('is-recording')), false);
      await page.locator('#modal-speech').screenshot({path: path.join(artifacts, 'denied-320.png')});
    } finally { await denied.close(); }
    assert.deepEqual(fs.readFileSync(server.fixture.source), manuscript);
    console.log(`Native microphone policy, real getUserMedia grant/deny and reference save passed: ${artifacts}`);
  } finally { await browser.close(); await server.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
