// Native author profiles keep phonetic overrides separate from spelling changes.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const artifacts = fs.mkdtempSync('/tmp/lixity-audio-phonetics-');
  const server = await startNativeServer(`
import json, os, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
from lixity.speech import generate_silence_wav
from lixity.speech_references import save_reference
import lixity.speech_status as status
status.worker_health = lambda target, **kwargs: {'target':target, 'state':'unavailable', 'model':None}
base = Path(sys.argv[1]); root = base / 'project'; root.mkdir()
os.environ['XDG_DATA_HOME'] = str(base / 'data')
source = root / 'manuscript.md'; source.write_text('## Garten\\n\\nDer rote Vogel singt leise.\\n\\nDer blaue Vogel antwortet.\\n')
(root / 'lixity.toml').write_text('''language="de"
[audio]
selected="retained"
[audio.profiles.retained]
name="Retained voice"
engine="qwen3"
language="de"
voice="Ryan"
''')
reference = save_reference(root, generate_silence_wav(2), 'Eine rein synthetische Referenzaufnahme.')
with (root / 'lixity.toml').open('a') as stream:
    stream.write(f'''[audio.profiles.retired]
name="Retained F5 voice"
engine="f5-tts"
language="de"
voice="reference"
reference_id="{reference.id}"
''')
LixityServerHandler.workspace_root = str(root)
LixityServerHandler.source_input = str(source)
LixityServerHandler.exports_dir = str(root / 'exports')
LixityServerHandler.language = 'de'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1',0), LixityServerHandler)
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}', 'reference':reference.id,
                  'source':str(source), 'config':str(root / 'lixity.toml')}), flush=True)
server.serve_forever()
`, artifacts);
  const browser = await launchChromium();
  try {
    const originalSource = fs.readFileSync(server.fixture.source);
    const originalConfig = fs.readFileSync(server.fixture.config);
    for (const width of [1440, 320]) {
      fs.writeFileSync(server.fixture.config, originalConfig);
      const page = await browser.newPage({viewport:{width,height:900}}), errors = [];
      page.on('pageerror', error => errors.push(error.message));
      const writes = [];
      page.on('request', request => { if (request.method() === 'POST') writes.push({url:request.url(),data:request.postDataJSON()}); });
      async function openProfile(name) {
        await page.locator('#tab-view-project').click();
        await page.locator('#settings-speech').click();
        await page.waitForFunction(expected => document.querySelector('#speech-name')?.value === expected, name);
      }
      async function saveProfile() {
        const result = page.waitForResponse(response => response.url().endsWith('/api/settings'));
        await Promise.all([page.waitForNavigation(), page.locator('[data-speech-action=save]').click()]);
        assert.equal((await result).status(), 200);
      }
      try {
        await page.goto(server.fixture.url);
        await openProfile('Retained voice');
        assert.equal(await page.locator('#speech-engine').inputValue(),'qwen3','Existing profiles keep their selected engine');
        assert.equal(await page.locator('#speech-engine option[value="ims-toucan"]').textContent(),'IMS-Toucan',
          'An advertised engine uses its own name instead of a Qwen variant label');
        assert.equal(await page.locator('#speech-engine option[value="f5-tts"]').count(),0,'An unavailable retired runtime is not offered for new choices');
        await page.locator('#speech-profile').selectOption('retired');
        assert.equal(await page.locator('#speech-engine').inputValue(),'f5-tts','Existing retired profiles remain readable without changing the engine');
        assert.match(await page.locator('#speech-worker-status').textContent(),/kein funktionsfähiger/);
        await page.locator('[data-speech-action=profiles_discard]').click();
        assert.equal(await page.locator('#speech-profile').inputValue(),'retained','Discard restores the saved profile selection before migration');
        await page.locator('[data-speech-action=create]').click();
        assert.equal(await page.locator('#speech-profile option').count(),2,'New controls require a reviewed settings migration');
        assert.deepEqual(fs.readFileSync(server.fixture.config),originalConfig,'Opening and requesting a new profile never silently migrates');
        await page.locator('[data-speech-action=schema_preview]').click();
        await page.waitForFunction(() => document.querySelector('#speech-schema-review').textContent.includes('lixity-audio-settings/5'));
        assert.deepEqual(fs.readFileSync(server.fixture.config),originalConfig,'The migration preview is read-only');
        await Promise.all([page.waitForNavigation(),page.locator('[data-speech-action=schema_apply]').click()]);
        await openProfile('Retained voice');
        await page.locator('[data-speech-action=create]').click();
        assert.equal(await page.locator('#speech-engine').inputValue(),'ims-toucan','A new German author profile chooses the reference-capable engine');
        assert.equal(await page.locator('#speech-language').inputValue(),'de');
        await page.locator('#speech-name').fill('Synthetic author voice');
        await page.locator('#speech-reference_id').selectOption(server.fixture.reference);
        assert.ok((await page.locator('#speech-reference_id option:checked').textContent()).includes('synthetische'));
        assert.ok(!(await page.locator('#speech-reference_id option:checked').textContent()).includes(server.fixture.reference));
        assert.ok((await page.locator('#speech-worker-guide').getAttribute('href')).endsWith('#ims-toucan-author-voice-and-phonetic-direction'));
        const duration = page.locator('#speech-prosody-duration_scaling_factor');
        assert.equal(await duration.getAttribute('min'),'0.5');
        assert.equal(await duration.getAttribute('max'),'2');
        await duration.fill('3');
        const beforeInvalid = writes.length;
        await page.locator('[data-speech-action=save]').click();
        assert.equal(writes.length,beforeInvalid,'An out-of-range control cannot be submitted');
        assert.equal(await duration.evaluate(el=>el.validity.rangeOverflow),true);
        await duration.fill('1.25');
        await page.locator('#speech-prosody-energy_variance_scale').fill('0.8');
        await page.locator('#speech-phonemes-section summary').click();
        await page.locator('#speech-phonemes').fill('Vogel=ˈfoːɡəl\nVogel=foːɡəl');
        await page.locator('[data-speech-action=save]').click();
        assert.equal(writes.length,beforeInvalid,'Duplicate phonetic terms cannot overwrite each other silently');
        await page.locator('#speech-phonemes').fill('Vogel=ˈfoːɡəl');
        await page.locator('#speech-instructions').fill('An authored export-only performance note.');
        await saveProfile();
        const saved = writes.filter(row=>row.url.endsWith('/api/settings')).at(-1).data.audio;
        assert.equal(saved.schema_version,'lixity-audio-settings/5');
        assert.equal(saved.profiles.retained.engine,'qwen3');
        assert.equal(saved.profiles.retained.voice,'Ryan');
        assert.deepEqual(saved.profiles[saved.selected].phonemes,{Vogel:'ˈfoːɡəl'});
        assert.deepEqual(saved.profiles[saved.selected].prosody,{duration_scaling_factor:1.25,energy_variance_scale:0.8});
        await openProfile('Synthetic author voice');
        assert.equal(await page.locator('#speech-prosody-pitch_variance_scale').inputValue(),'','Unspecified controls remain absent rather than copied defaults');
        assert.equal(await duration.inputValue(),'1.25');
        assert.equal(await page.locator('#speech-phonemes').inputValue(),'Vogel=ˈfoːɡəl');
        await page.locator('#speech-tab-reader').click();
        const beforeRender = writes.length;
        await page.locator('[data-speech-action=preview]').click();
        assert.equal(writes.length,beforeRender,'Unsupported free-text profile direction is rejected before synthesis');
        assert.match(await page.locator('#speech-status').textContent(),/Planexport/);
        await page.locator('[data-speech-action=direction_plan]').click();
        await page.waitForSelector('[data-speech-action=export_json]');
        const profileDownload = page.waitForEvent('download');
        await page.locator('[data-speech-action=export_json]').click();
        const exported = JSON.parse(fs.readFileSync(await (await profileDownload).path(),'utf8'));
        assert.equal(exported.schema_version,'lixity-audio-timeline/2');
        assert.ok(exported.segments.some(row=>row.instructions.includes('export-only')),'Authored free text is retained in export');
        assert.ok(exported.segments.some(row=>row.phonemes.some(phone=>phone.ipa==='ˈfoːɡəl')),'IPA export is separate from spelling');
        await page.locator('#speech-tab-profiles').click();
        await page.locator('#speech-instructions').fill('');
        await saveProfile();
        await openProfile('Synthetic author voice');
        await page.locator('#speech-tab-reader').click();
        const entries = page.locator('#speech-direction_entries');
        // The second viewport reuses only the synthetic direction store.
        if (await entries.locator('option').count()>1) {
          await entries.selectOption({index:1});
          const removed=page.waitForResponse(response=>response.url().endsWith('/api/speech-direction'));
          await page.locator('[data-speech-action=direction_remove]').click();
          assert.equal((await removed).status(),200);
          await page.waitForFunction(()=>document.querySelector('#speech-direction_entries').options.length===1);
        }
        const text = await page.locator('#speech-direction_text').inputValue();
        const start = text.indexOf('Vogel');
        await page.locator('#speech-direction_text').evaluate((el,range)=>el.setSelectionRange(...range),[start,start+5]);
        await page.locator('[data-speech-action=direction_selection]').click();
        await page.locator('#speech-direction-prosody-pitch_variance_scale').fill('1.4');
        await page.locator('#speech-direction-prosody-duration_scaling_factor').fill('0.9');
        const directionResult = page.waitForResponse(response=>response.url().endsWith('/api/speech-direction'));
        await page.locator('[data-speech-action=direction_save]').click();
        assert.equal((await directionResult).status(),200);
        await page.waitForFunction(()=>document.querySelector('#speech-direction_entries').options.length===2);
        await entries.selectOption({index:1});
        assert.equal(await page.locator('#speech-direction-prosody-duration_scaling_factor').inputValue(),'0.9');
        assert.equal(await page.locator('#speech-direction-prosody-energy_variance_scale').inputValue(),'','Empty range controls inherit the selected profile');
        await page.locator('#speech-direction-prosody-pitch_variance_scale').fill('1.9');
        await page.locator('[data-speech-action=direction_discard]').click();
        assert.equal(await page.locator('#speech-direction-prosody-pitch_variance_scale').inputValue(),'1.4','Discard restores saved structured direction');
        await page.locator('#speech-export_scope').selectOption('chapter');
        await page.locator('[data-speech-action=direction_plan]').click();
        await page.waitForSelector('[data-speech-action=export_json]');
        const rangeDownload = page.waitForEvent('download');
        await page.locator('[data-speech-action=export_json]').click();
        const timeline = JSON.parse(fs.readFileSync(await (await rangeDownload).path(),'utf8'));
        const directed = timeline.segments.find(row=>row.direction?.prosody?.pitch_variance_scale===1.4);
        assert.ok(directed,'The saved range carries structured controls in the exported timeline');
        assert.deepEqual(directed.prosody,{duration_scaling_factor:0.9,pitch_variance_scale:1.4,energy_variance_scale:0.8});
        assert.deepEqual(directed.source_range,{start,end:start+5,unit:'unicode-code-point',projection:'spoken-projection'});
        assert.ok((await page.locator('.speech-plan').textContent()).includes('1.4'),'The preview shows effective range controls');
        assert.ok(!(await page.locator('.speech-plan').textContent()).includes(server.fixture.reference),'Recording identities remain opaque in rendered UI');
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'The compact layout has no document overflow');
        assert.deepEqual(fs.readFileSync(server.fixture.source),originalSource,'Speech controls never modify the manuscript');
        assert.deepEqual(errors,[]);
        await page.locator('#speech-direction-prosody-pitch_variance_scale').evaluate(el=>el.scrollIntoView({block:'center'}));
        await page.locator('#modal-speech').screenshot({path:path.join(artifacts,`prosody-${width}.png`)});
      } catch(error) {
        console.error(JSON.stringify({width,status:await page.locator('#speech-status').textContent(),writes,errors},null,2));
        await page.screenshot({path:path.join(artifacts,`failed-${width}.png`)});
        throw error;
      } finally { await page.close(); }
    }
    console.log('Audio phonetics browser checks passed: '+artifacts);
  } finally { await browser.close(); await server.close(); }
})().catch(error => {console.error(error); process.exitCode=1;});
