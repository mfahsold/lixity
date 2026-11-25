// Portable takes enter the existing studio as a draft, never as an implicit save.
const {launchChromium,launchFirefox} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

(async () => {
  const artifacts=fs.mkdtempSync('/tmp/lixity-audio-take-studio-');
  const server=await startNativeServer(`
import base64, json, os, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
from lixity.speech import generate_silence_wav
from lixity.speech_references import save_reference
import lixity.speech_status as status
status.worker_health=lambda target, **kwargs: {'target':target,'state':'unavailable','model':None}
base=Path(sys.argv[1]); root=base/'project'; root.mkdir()
os.environ['XDG_DATA_HOME']=str(base/'data')
source=root/'manuscript.md'; source.write_text('## Garten\\n\\nEin Vogel singt.\\n')
wav=generate_silence_wav(2)
reference=save_reference(root,wav,'Initial synthetic reference.')
(root/'lixity.toml').write_text(f'''language="de"
[audio]
selected="author"
[audio.profiles.author]
name="Synthetic author"
engine="qwen3-base"
language="de"
voice="reference"
reference_id="{reference.id}"
''')
LixityServerHandler.workspace_root=str(root)
LixityServerHandler.source_input=str(source)
LixityServerHandler.exports_dir=str(base/'exports')
LixityServerHandler.language='de'
LixityServerHandler.refresh()
server=ThreadingHTTPServer(('127.0.0.1',0),LixityServerHandler)
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','wav':base64.b64encode(wav).decode(),
                  'excerpt':base64.b64encode(generate_silence_wav(1.5)).decode(),'source':str(source)}),flush=True)
server.serve_forever()
`,artifacts);
  const wav=Buffer.from(server.fixture.wav,'base64');
  const metadata={schema_version:'lixity-audio-take/1',audio:{filename:'synthetic.wav',sha256:crypto.createHash('sha256').update(wav).digest('hex'),format:'wav-pcm',channels:1,sample_rate_hz:24000,sample_width_bits:16,frames:48000,duration_seconds:2},transcript:{text:'A synthetic draft transcript.',status:'draft'}};
  const browser=await (process.argv.includes('--firefox') ? launchFirefox() : launchChromium());
  try {
    for(const width of [1440,320]) {
      const page=await browser.newPage({viewport:{width,height:900}}),writes=[],errors=[];
      page.setDefaultTimeout(10000);
      page.on('request',request=>{if(request.method()==='POST')writes.push(request.url());});
      page.on('pageerror',error=>errors.push(error.message));
      await page.route('**/api/speech?*',async route=>{
        const response=await route.fetch();
        await route.fulfill({response,json:{...await response.json(),can_trim_take:true}});
      });
      await page.route('**/api/audio-take-trim',route=>route.fulfill({json:{ok:true,audio:server.fixture.excerpt}}));
      async function handoff(wrong=false) {
        await page.evaluate(({bytes,metadata,wrong})=>{
          const blob=new Blob([Uint8Array.from(atob(bytes),c=>c.charCodeAt(0))],{type:'audio/wav'});
          document.dispatchEvent(new CustomEvent('lixity:open-speech-studio',{detail:{mode:'reference',
            take:{blob,transcript:metadata.transcript.text,transcript_status:metadata.transcript.status,metadata},
            context:{project_token:wrong?'another-project':document.querySelector('#settings-form').dataset.projectToken,source_sha256:document.body.dataset.manuscriptSourceSha256}}}));
        },{bytes:server.fixture.wav,metadata,wrong});
      }
      async function discardTake(focusSelector='.voice-rec-btn') {
        const source=await page.locator('.voice-take-card audio').getAttribute('src');
        const priorWrites=writes.length;
        await page.evaluate(() => {
          if (window.revokedTakeUrls) return;
          window.revokedTakeUrls = [];
          const revoke = URL.revokeObjectURL.bind(URL);
          URL.revokeObjectURL = url => {window.revokedTakeUrls.push(url); revoke(url);};
        });
        await page.locator('[data-speech-action=take_discard]').press('Enter');
        assert.equal(await page.locator('.voice-take-card').isVisible(),false);
        assert.equal(await page.locator('.voice-take-card audio').getAttribute('src'),null);
        assert.equal(await page.locator('.voice-take-card textarea').inputValue(),'');
        assert.equal(await page.locator('#speech-take_confirmed').isChecked(),false);
        assert.equal(await page.locator(focusSelector).evaluate(control => control === document.activeElement),true);
        assert.ok(await page.evaluate(url => window.revokedTakeUrls.includes(url), source));
        assert.equal(writes.length,priorWrites,'Discard stays in the review and does not write to the server');
      }
      try {
        await page.goto(server.fixture.url);
        const bound=await page.evaluate(()=>({project_token:document.querySelector('#settings-form').dataset.projectToken,source_sha256:document.body.dataset.manuscriptSourceSha256}));
        await handoff();
        await page.waitForFunction(()=>document.querySelector('#speech-name')?.value==='Synthetic author');
        assert.equal(await page.locator('.voice-take-card').isVisible(),true,'A handed-off take must be presented for review');
        assert.equal(await page.locator('.voice-take-card textarea').inputValue(),metadata.transcript.text);
        assert.equal(await page.locator('.voice-save-btn').isDisabled(),true,'Draft transcript requires explicit confirmation');
        assert.equal(await page.locator('#speech-take_confirmed').getAttribute('aria-describedby'),'speech-take-notice');
        assert.equal(await page.locator('#speech-take_confirmed').getAttribute('data-help'),null,'Existing inline guidance must not become a duplicate tooltip over Save');
        assert.deepEqual(writes,[],'Importing a take cannot create a voice reference');
        const wavDownload=page.waitForEvent('download');
        await page.locator('[data-speech-action=take_download_wav]').click();
        assert.deepEqual(fs.readFileSync(await (await wavDownload).path()),wav,'Studio exports the unchanged WAV');
        const jsonDownload=page.waitForEvent('download');
        await page.locator('[data-speech-action=take_download_json]').click();
        const exported=JSON.parse(fs.readFileSync(await (await jsonDownload).path(),'utf8'));
        assert.equal(exported.transcript.status,'draft','Portable export must not confirm a draft transcript');
        assert.equal(exported.transcript.text,metadata.transcript.text);
        assert.equal(exported.audio.sha256,metadata.audio.sha256);
        await page.locator('#modal-speech [data-speech-action=close]').click();
        assert.equal(await page.locator('#modal-speech').isVisible(),true,'Downloading a copy retains the draft until an explicit choice');
        assert.equal(await page.locator('#speech-status').textContent(),await page.evaluate(()=>uiLabel('speech_take_unsaved')));
        await discardTake();
        await page.locator('#modal-speech [data-speech-action=close]').click();
        assert.equal(await page.locator('#modal-speech').isVisible(),false);
        await handoff();
        await page.locator('.voice-take-card').waitFor();
        await page.locator('#speech-take_confirmed').check();
        assert.equal(await page.locator('.voice-save-btn').isEnabled(),true);
        await page.locator('.voice-take-card textarea').fill('The reviewed synthetic transcript.');
        assert.equal(await page.locator('#speech-take_confirmed').isChecked(),false,'Editing the transcript clears the earlier confirmation');
        assert.equal(await page.locator('.voice-save-btn').isDisabled(),true);
        const beforeSource=await page.locator('.voice-take-card audio').getAttribute('src');
        await handoff(true);
        assert.equal(await page.locator('.voice-take-card audio').getAttribute('src'),beforeSource,'A different project cannot replace the active draft');
        assert.equal(await page.locator('.voice-take-card textarea').inputValue(),'The reviewed synthetic transcript.');
        await page.locator('.voice-upload-section summary').click();
        await page.locator('#speech-upload_voice_file').setInputFiles({name:'synthetic.wav',mimeType:'audio/wav',buffer:wav});
        await page.locator('#speech-take_metadata_file').setInputFiles({name:'synthetic.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({...metadata,audio:{...metadata.audio,sha256:'0'.repeat(64)}}))});
        await page.locator('[data-speech-action=take_import]').click();
        await page.waitForFunction(()=>document.querySelector('#speech-status').textContent===uiLabel('speech_take_invalid'));
        assert.equal(await page.locator('.voice-take-card audio').getAttribute('src'),beforeSource,'A corrupt sidecar must leave the current take intact');
        assert.deepEqual(writes,[]);
        await page.locator('#speech-take_metadata_file').setInputFiles({name:'synthetic.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({...metadata,transcript:{text:'Restored transcript.',status:'confirmed'}}))});
        await page.locator('[data-speech-action=take_import]').click();
        await page.waitForFunction(()=>document.querySelector('.voice-take-card textarea').value==='Restored transcript.');
        assert.equal(await page.locator('#speech-take_confirmed').isChecked(),true,'Verified sidecar restores its explicit transcript status');
        assert.equal(await page.locator('.voice-save-btn').isEnabled(),true);
        assert.deepEqual(writes,[],'Successful import also remains an unsaved draft');
        const trim=page.locator('#speech-take-trim');
        await trim.locator('summary').click();
        const trimStart=trim.locator('#speech-take_trim_start'), trimEnd=trim.locator('#speech-take_trim_end');
        const applyTrim=trim.locator('[data-speech-action=take_trim_apply]');
        const trimStatus=page.locator('#speech-take-trim-status');
        async function expectTrimStatus(key) {
          const message=await page.evaluate(key=>uiFormat(`speech_take_trim_${key}`,{min:1,max:60}),key);
          await trimStatus.filter({hasText:message}).waitFor();
        }
        await trimEnd.fill('2');
        await trimStart.fill('1.5');
        await applyTrim.click();
        await expectTrimStatus('range');
        assert.deepEqual(writes,[],'A range shorter than one second must not cross the backend boundary');
        await trimStart.fill('0.5');
        const trimRequest=page.waitForRequest(request=>request.url().endsWith('/api/audio-take-trim'));
        await applyTrim.click();
        const trimPayload=(await trimRequest).postDataJSON();
        assert.equal(trimPayload.start_frame,12000);
        assert.equal(trimPayload.end_frame,48000);
        assert.equal(trimPayload.project_token,bound.project_token);
        assert.equal(trimPayload.source_sha256,bound.source_sha256);
        assert.equal(crypto.createHash('sha256').update(Buffer.from(trimPayload.audio,'base64')).digest('hex'),metadata.audio.sha256);
        await expectTrimStatus('ready');
        assert.equal(await page.locator('.voice-take-card textarea').inputValue(),'','An excerpt takes a fresh exact transcript');
        assert.equal(await page.locator('#speech-take_confirmed').isChecked(),false);
        assert.equal(await page.locator('.voice-save-btn').isDisabled(),true);
        const excerptDownload=page.waitForEvent('download');
        await page.locator('[data-speech-action=take_download_json]').click();
        const excerpt=JSON.parse(fs.readFileSync(await (await excerptDownload).path(),'utf8'));
        assert.equal(excerpt.audio.frames,36000);
        assert.equal(excerpt.audio.duration_seconds,1.5);
        assert.equal(excerpt.transcript.status,'missing');
        await trim.locator('[data-speech-action=take_trim_restore]').click();
        assert.equal(await page.locator('.voice-take-card textarea').inputValue(),'Restored transcript.');
        assert.equal(await page.locator('#speech-take_confirmed').isChecked(),true);
        assert.equal(await page.locator('.voice-save-btn').isEnabled(),true);
        const restoredDownload=page.waitForEvent('download');
        await page.locator('[data-speech-action=take_download_wav]').click();
        assert.deepEqual(fs.readFileSync(await (await restoredDownload).path()),wav,'Restoring returns the byte-identical original take');
        assert.deepEqual(writes.map(url=>new URL(url).pathname),['/api/audio-take-trim'],'Trimming and restoring do not save a reference');
        await trim.locator('summary').click();
        await trimStart.fill('0.5');
        await trimEnd.fill('2');
        await applyTrim.click();
        await expectTrimStatus('ready');
        await page.evaluate(() => {document.body.dataset.manuscriptSourceSha256 = 'f'.repeat(64);});
        await page.waitForFunction(()=>document.querySelector('#speech-status').textContent===uiLabel('speech_take_context'));
        assert.equal(await page.locator('.voice-save-btn').isDisabled(),true,'A stale recording cannot be saved to the changed manuscript');
        await discardTake('#speech-title');
        assert.equal(await trim.locator('[data-speech-action=take_trim_restore]').isVisible(),false,'Discard also releases the original behind an excerpt');
        await page.locator('#modal-speech [data-speech-action=close]').click();
        await page.evaluate(hash => {document.body.dataset.manuscriptSourceSha256 = hash;},bound.source_sha256);
        await handoff();
        await page.locator('.voice-take-card').waitFor();
        await page.locator('.voice-take-card textarea').fill('The reviewed synthetic transcript.');
        await page.locator('#speech-take_confirmed').check();
        const saved=page.waitForRequest(request=>request.url().endsWith('/api/audio-microphone'));
        await Promise.all([page.waitForNavigation(),page.locator('.voice-save-btn').click()]);
        const submitted=(await saved).postDataJSON();
        assert.equal(submitted.transcript,'The reviewed synthetic transcript.');
        assert.equal(submitted.project_token,bound.project_token,'Reference save remains bound to the imported take’s project');
        assert.equal(submitted.source_sha256,bound.source_sha256,'Reference save remains bound to the imported take’s source revision');
        assert.deepEqual(errors,[]);
      } catch(error) {
        await page.screenshot({path:path.join(artifacts,`failed-${width}.png`)}); throw error;
      } finally {await page.close();}
    }
    console.log('Studio take handoff, excerpt and original restoration, transcript confirmation and context isolation passed: '+artifacts);
  } finally {await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
