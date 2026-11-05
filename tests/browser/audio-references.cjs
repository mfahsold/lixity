// Saved recordings have human names while opaque identities stay in API values.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const artifacts = fs.mkdtempSync('/tmp/lixity-audio-references-');
  const server = await startNativeServer(`
import json, os, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.config import prepare_project_settings
from lixity.server import LixityServerHandler
from lixity.speech import generate_silence_wav
from lixity.speech_references import save_reference
from tests.locales import LOCALES
import lixity.speech_status as speech_status
speech_status.worker_health = lambda target, **kwargs: {'target':target, 'state':'unavailable', 'model':None}
base = Path(sys.argv[1]); projects = []
os.environ['XDG_DATA_HOME'] = str(base / 'app-data')
for locale in LOCALES:
    for width in (1440, 320):
        root = base / (locale + str(width)); root.mkdir()
        source = root / 'manuscript.md'
        source.write_text('## One\\n\\nA synthetic bird crosses a quiet garden.\\n')
        (root / 'lixity.toml').write_text('language="' + locale + '"\\n')
        first = save_reference(root, generate_silence_wav(2), 'A synthetic morning begins. ' * 12)
        second = save_reference(root, generate_silence_wav(3), 'A synthetic evening ends. <img src=x onerror=alert(1)>')
        missing = 'b' * 64
        prepare_project_settings(root, {'audio': {'selected':'narrator', 'profiles':{
            'narrator': {'name':'Narrator', 'engine':'qwen3-base', 'language':'en', 'voice':'reference', 'reference_id':first.id},
            'missing': {'name':'Retained narrator', 'engine':'qwen3-base', 'language':'en', 'voice':'reference', 'reference_id':missing}}}}).commit()
        projects.append({'root':str(root), 'source':str(source), 'config':str(root/'lixity.toml'),
            'locale':locale, 'width':width, 'first':first.id, 'second':second.id, 'missing':missing})
LixityServerHandler.workspace_root = projects[0]['root']
LixityServerHandler.source_input = projects[0]['source']
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1',0), LixityServerHandler)
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}', 'projects':projects}), flush=True)
server.serve_forever()
`, artifacts);
  const browser = await launchChromium();
  try {
    for (const fixture of server.fixture.projects) {
      const page = await browser.newPage({viewport:{width:fixture.width, height:900}});
      const original = fs.readFileSync(fixture.source), errors = [];
      page.on('pageerror', error => errors.push(error.message));
      async function openProfiles() {
        await page.locator('#tab-view-project').click();
        await page.locator('#settings-speech').click();
        await page.waitForFunction(() => document.querySelector('#speech-name')?.value && !document.querySelector('#speech-name').disabled);
      }
      async function assertHumanText() {
        const text = await page.locator('#modal-speech').innerText();
        for (const id of [fixture.first, fixture.second, fixture.missing]) {
          assert.equal(text.includes(id.slice(0,8)), false, 'Neither complete nor shortened recording identities are visible');
        }
        assert.equal(await page.locator('#modal-speech img').count(), 0, 'Transcripts are text, never markup');
      }
      try {
        assert.equal((await page.request.post(server.fixture.url+'/api/project-open', {data:{path:fixture.root}})).status(),200);
        await page.goto(server.fixture.url);
        await openProfiles();
        const reference = page.locator('#speech-reference_id');
        assert.equal(await reference.evaluate(el => el.tagName), 'SELECT', 'Choose a named project recording instead of typing an opaque ID');
        assert.equal(await reference.evaluate(el => el.closest('label').classList.contains('setting-field')), true);
        assert.equal(await reference.inputValue(),fixture.first);
        assert.match(await reference.locator('option:checked').textContent(), /A synthetic morning begins/);
        assert.match(await reference.locator('option:checked').textContent(), /2([.,]0)? s/);
        assert.equal(await reference.locator('option[value=""]').count(),1, 'The selection can be explicitly cleared');
        await assertHumanText();
        const bounds = await reference.boundingBox();
        assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= fixture.width, 'Long recording names stay inside the viewport');

        await page.locator('#speech-profile').selectOption('missing');
        assert.equal(await reference.inputValue(),fixture.missing, 'A missing saved reference must not silently fall back to another recording');
        assert.equal(await reference.locator('option:checked').textContent(),await page.evaluate(() => uiLabel('speech_reference_unavailable')));
        await assertHumanText();
        await Promise.all([page.waitForNavigation(),page.locator('[data-speech-action=save]').click()]);
        await openProfiles();
        assert.equal(await reference.inputValue(),fixture.missing, 'Saving other profile state preserves the unavailable reference');
        assert.ok(fs.readFileSync(fixture.config,'utf8').includes(fixture.missing));

        await page.locator('#speech-profile').selectOption('narrator');
        await reference.selectOption('');
        await page.locator('[data-speech-action=create]').click();
        assert.equal(await page.locator('#speech-status').textContent(),await page.evaluate(() => uiLabel('speech_model_need_reference')));
        assert.equal(await reference.inputValue(),'');
        await reference.selectOption(fixture.second);
        const saving = page.waitForRequest(request => request.url().endsWith('/api/settings'));
        await Promise.all([page.waitForNavigation(),page.locator('[data-speech-action=save]').click()]);
        assert.equal((await saving).postDataJSON().audio.profiles.narrator.reference_id,fixture.second,
          'Human option labels preserve the original identity in the settings contract');
        await openProfiles();
        assert.equal(await reference.inputValue(),fixture.second, 'The chosen recording persists after saving and reopening');
        await assertHumanText();
        await page.locator('#speech-tab-reference').click();
        assert.match(await page.locator('.voice-badge-text').textContent(),/A synthetic evening ends/);
        await page.locator('.voice-library-section > summary').click();
        await assertHumanText();
        await page.locator('#modal-speech').screenshot({path:path.join(artifacts,`${fixture.locale}-${fixture.width}.png`)});
        if (fixture.locale==='en' && fixture.width===1440) {
          const savedConfig=fs.readFileSync(fixture.config);
          const activateLabel=await page.evaluate(()=>uiLabel('speech_use_as_active'));
          const firstRecording=page.locator('.voice-ref-item').filter({hasText:'A synthetic morning begins.'});
          await page.route('**/api/settings',route=>route.fulfill({status:409,json:{ok:false,message:'Synthetic activation failure'}}),{times:1});
          await firstRecording.getByRole('button',{name:activateLabel,exact:true}).click();
          await page.waitForFunction(()=>document.querySelector('#speech-status').textContent==='Synthetic activation failure');
          assert.equal(await page.locator('#speech-tab-profiles').getAttribute('aria-selected'),'true',
            'A failed activation opens the retained draft for correction or discard');
          assert.equal(await reference.inputValue(),fixture.first);
          assert.match(await page.locator('.voice-badge-text').textContent(),/A synthetic evening ends/,
            'A rejected settings write cannot announce a newly active recording');
          assert.deepEqual(fs.readFileSync(fixture.config),savedConfig);
          await page.locator('[data-speech-action=profiles_discard]').click();
          assert.equal(await reference.inputValue(),fixture.second);
          await page.locator('#speech-tab-reader').click();
        } else await page.locator('#speech-tab-reader').click();
        await page.locator('[data-speech-action=direction_plan]').click();
        await page.waitForFunction(() => !document.querySelector('.speech-plan').hidden);
        assert.match(await page.locator('.speech-plan').textContent(),/A synthetic evening ends/);
        await assertHumanText();
        await page.locator('#modal-speech [data-speech-action=close]').click();
        if (fixture.locale==='en' && fixture.width===1440) {
          const savedConfig=fs.readFileSync(fixture.config), settingsPosts=[];
          const recordPost=request=>{if(request.url().endsWith('/api/settings'))settingsPosts.push(request);};
          page.on('request',recordPost);
          await page.route('**/api/speech?*',async route=>{
            const response=await route.fetch(),data=await response.json();
            Object.assign(data.settings.profiles[data.settings.selected],{engine:'qwen3-design',voice:'design',voice_description:'A synthetic warm narrator.'});
            delete data.settings.profiles[data.settings.selected].reference_id;
            await route.fulfill({response,json:data});
          },{times:1});
          await openProfiles();
          await page.locator('#speech-tab-reference').click();
          if (!(await page.locator('.voice-library-section').evaluate(el=>el.open))) await page.locator('.voice-library-section > summary').click();
          const activateLabel=await page.evaluate(()=>uiLabel('speech_use_as_active'));
          await page.locator('.voice-ref-item').filter({hasText:'A synthetic morning begins.'}).getByRole('button',{name:activateLabel,exact:true}).click();
          assert.equal(await page.locator('#speech-tab-profiles').getAttribute('aria-selected'),'true');
          assert.equal(await reference.inputValue(),fixture.first,'Incompatible model keeps the requested recording as a visible draft');
          assert.equal(await reference.evaluate(el=>el.validity.customError),true);
          assert.equal(await page.locator('#speech-voice_description').inputValue(),'A synthetic warm narrator.');
          assert.equal(settingsPosts.length,0,'An incompatible activation cannot write settings');
          assert.deepEqual(fs.readFileSync(fixture.config),savedConfig);
          await page.locator('[data-speech-action=profiles_discard]').click();
          await page.locator('#modal-speech [data-speech-action=close]').click();
          page.off('request',recordPost);
        }
        const unknownProfile = 'opaque_profile_57af39';
        await page.route('**/api/speech?*',async route => {
          const response = await route.fetch(), data = await response.json();
          // Retained metadata can be incomplete without changing the archive.
          data.references.find(reference => reference.id === fixture.second).transcript = '';
          const passage = data.direction.passages[0];
          data.direction.directions.push({id:'opaque_direction_5930b', anchor:passage.anchor,
            start:0, end:null, instructions:'Synthetic retained direction',
            profile_id:unknownProfile, pause_before:0, pause_after:null, stale:false});
          await route.fulfill({response,json:data});
        }, {times:1});
        await openProfiles();
        assert.equal(await reference.inputValue(),fixture.second);
        assert.ok((await reference.locator('option:checked').textContent()).startsWith(await page.evaluate(() => uiLabel('speech_reference_untitled'))),
          'Missing recording text uses a human fallback, never the identity');
        await page.locator('#speech-tab-reader').click();
        await page.locator('#speech-direction_passage').selectOption({index:1});
        await page.locator('#speech-direction_entries').selectOption('opaque_direction_5930b');
        assert.equal(await page.locator('#speech-direction_profile').inputValue(),unknownProfile);
        assert.equal(await page.locator('#speech-direction_profile option:checked').textContent(),await page.evaluate(() => uiLabel('speech_profile_unavailable')));
        assert.equal((await page.locator('#modal-speech').innerText()).includes(unknownProfile),false);
        await assertHumanText();
        assert.deepEqual(fs.readFileSync(fixture.source),original);
        assert.deepEqual(errors,[]);
      } finally { await page.close(); }
    }
    console.log(`Named audio references: seven locales, desktop/mobile, missing selection retention, persistence and plan labels passed. ${artifacts}`);
  } finally { await browser.close(); await server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
