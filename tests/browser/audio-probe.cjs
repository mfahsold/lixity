// The project voice probe reuses the existing take review for every part.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

function silenceWav(seconds) {
  const rate = 24000, samples = rate * seconds, buffer = Buffer.alloc(44 + samples * 2);
  buffer.write('RIFF', 0); buffer.writeUInt32LE(buffer.length - 8, 4); buffer.write('WAVE', 8);
  buffer.write('fmt ', 12); buffer.writeUInt32LE(16, 16); buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(1, 22); buffer.writeUInt32LE(rate, 24); buffer.writeUInt32LE(rate * 2, 28);
  buffer.writeUInt16LE(2, 32); buffer.writeUInt16LE(16, 34); buffer.write('data', 36);
  buffer.writeUInt32LE(samples * 2, 40); return buffer;
}

(async () => {
  const artifacts = fs.mkdtempSync('/tmp/lixity-audio-probe-');
  const server = await startNativeServer(`
import json, os, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
from lixity.speech import generate_silence_wav
from lixity.speech_references import save_reference
import lixity.speech_status as speech_status
speech_status.worker_health = lambda target, **kwargs: {'target':target,'state':'unavailable','model':None}
base = Path(sys.argv[1]); root = base/'project'; root.mkdir()
os.environ['XDG_DATA_HOME'] = str(base/'data'); os.environ['XDG_CACHE_HOME'] = str(base/'cache')
source = root/'manuscript.md'
lines = ['## Harbour', '']
for index in range(1, 31):
    lines.extend([f'Mara visits the old lighthouse at Travemünde number {index}.',
                  f"Hansen checks Kowalski's freight manifest beside the harbour of Lübeck number {index}.",
                  f'The latent taxes disturb the invoice from Rotterdam number {index}.', ''])
source.write_text('\\n'.join(lines), encoding='utf-8')
reference = save_reference(root, generate_silence_wav(1), 'Initial synthetic reference.')
(root/'lixity.toml').write_text(f'''language="en"
[audio]
selected="narrator"
[audio.profiles.narrator]
name="Synthetic narrator"
engine="qwen3-base"
language="en"
voice="reference"
reference_id="{reference.id}"
''', encoding='utf-8')
LixityServerHandler.workspace_root=str(root); LixityServerHandler.source_input=str(source)
LixityServerHandler.exports_dir=str(base/'exports'); LixityServerHandler.language='en'; LixityServerHandler.refresh()
server=ThreadingHTTPServer(('127.0.0.1',0),LixityServerHandler)
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','source':str(source)}),flush=True)
server.serve_forever()
  `, artifacts);
  const browser = await launchChromium();
  try {
    for (const width of [1440, 320, 2560]) {
      const page = await browser.newPage({viewport:{width, height:900}}), errors = [], setPosts = [];
      page.setDefaultTimeout(15000);
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => { if (request.url().endsWith('/api/audio-reference-set')) setPosts.push(request); });
      try {
        await page.goto(server.fixture.url);
        await page.locator('#tab-view-project').click();
        await page.locator('#btn-project-voice-probe').click();
        await page.waitForFunction(() => !document.querySelector('#speech-probe-generate')?.disabled);
        await page.locator('#speech-probe-generate').click();
        await page.waitForFunction(() => document.querySelectorAll('[data-probe-part]').length >= 3 &&
          document.querySelector('#speech-probe-script')?.textContent.trim());
        const count = await page.locator('[data-probe-part]').count();
        assert.ok(count <= 6, 'A ready probe has at most six parts');
        assert.match(await page.locator('#speech-probe-script').textContent(), /Travemünde|lighthouse|Mara|Hansen|Lübeck/);
        assert.equal(await page.locator('#speech-probe-save').isDisabled(), true);
        const geometry = await page.locator('#voice-calibration-probe').evaluate(element => ({
          left:element.getBoundingClientRect().left, right:element.getBoundingClientRect().right,
          scroll:element.scrollWidth, client:element.clientWidth,
        }));
        assert.ok(geometry.left >= 0 && geometry.right <= width + 1, 'Probe stays inside the viewport');
        assert.ok(geometry.scroll <= geometry.client + 1, 'Probe content does not overflow horizontally');
        await page.locator('.voice-upload-section > summary').click();
        const wav = silenceWav(Math.ceil(150 / count));
        for (let index = 0; index < count; index++) {
          await page.locator(`[data-probe-part-index="${index}"]`).click();
          const script = await page.locator('#speech-probe-script').textContent();
          await page.locator('#speech-upload_voice_file').setInputFiles({
            name:`probe-${index + 1}.wav`, mimeType:'audio/wav', buffer:wav,
          });
          await page.locator('#speech-upload_voice_transcript').fill(script);
          await page.locator('[data-speech-action=take_import]').click();
          await page.locator('.voice-take-card').waitFor({state:'visible'});
          assert.equal(await page.locator('.voice-save-btn').isDisabled(), true, 'A draft transcript needs confirmation');
          await page.locator('#speech-take_confirmed').check();
          assert.equal(await page.locator('.voice-save-btn').isEnabled(), true);
          await page.locator('.voice-save-btn').click();
        }
        assert.equal(await page.locator('#speech-probe-save').isDisabled(), true, 'Retention permission is explicit');
        await page.locator('#speech-probe-retention').check();
        await page.locator('#speech-probe-fallback').selectOption('2');
        assert.equal(await page.locator('#speech-probe-save').isEnabled(), true);
        const pending = page.waitForRequest(request => request.url().endsWith('/api/audio-reference-set'));
        const responsePromise = page.waitForResponse(response => response.url().endsWith('/api/audio-reference-set'));
        const navigation = page.waitForNavigation().catch(() => null);
        await page.locator('#speech-probe-save').click();
        const submitted = await pending;
        const payload = submitted.postDataJSON();
        const saveResponse = await responsePromise;
        assert.equal(saveResponse.status(), 200);
        await navigation;
        assert.equal(payload.parts.length, count);
        assert.equal(payload.fallback_part_index, 2);
        assert.equal(payload.allow_retention, true);
        assert.ok(payload.parts.every(part => part.confirmed === true && part.transcript.trim()));
        assert.equal(setPosts.length, 1, 'Only the complete set is uploaded');
        await page.locator('#tab-view-project').click();
        await page.locator('#btn-project-record-voice').click();
        await page.waitForFunction(() => !document.querySelector('#speech-name')?.disabled);
        await page.locator('.voice-library-section > summary').click();
        const setItem = page.locator('.voice-ref-item').filter({hasText:'Voice probe'}).first();
        await setItem.waitFor();
        assert.match(await setItem.textContent(), new RegExp(`${count} parts`));
        assert.equal(await setItem.locator('button').filter({hasText:/^▶ \d+$/}).count(), count);
        await setItem.locator('button').filter({hasText:/^▶ 2$/}).click();
        await page.waitForFunction(() => document.querySelector('.speech-playback audio')?.getAttribute('src'));
        await page.locator('#modal-speech').screenshot({path:path.join(artifacts, `probe-${width}.png`)});
        assert.deepEqual(errors, []);
      } catch (error) {
        await page.screenshot({path:path.join(artifacts, `failed-${width}.png`)}); throw error;
      } finally { await page.close(); }
    }
    console.log('Project voice probe generation, per-part confirmation, fallback, retention, activation and playback passed: '+artifacts);
  } finally { await browser.close(); await server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
