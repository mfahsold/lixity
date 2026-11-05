// Completed chapter imports are explicit, bound, and usable without a speech worker.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async()=>{
  const artifacts=fs.mkdtempSync('/tmp/lixity-audio-chapter-import-');
  const server=await startNativeServer(`
import base64,json,sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server.handler import LixityServerHandler
from lixity.speech import generate_silence_wav
import lixity.speech_status as status
status.worker_health=lambda target,**kwargs:{'target':target,'state':'unavailable','model':None}
base=Path(sys.argv[1]); root=base/'project'; root.mkdir()
source=root/'manuscript.md'; source.write_text('## Garden\\n\\nA synthetic bird sings.\\n\\n## Street\\n\\nA second synthetic scene.\\n')
(root/'lixity.toml').write_text('language="en"\\nmanuscript="manuscript.md"\\n')
LixityServerHandler.workspace_root=str(root); LixityServerHandler.source_input=str(source)
LixityServerHandler.exports_dir=str(base/'exports'); LixityServerHandler.language='en'
LixityServerHandler.refresh()
server=ThreadingHTTPServer(('127.0.0.1',0),LixityServerHandler)
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','wav':base64.b64encode(generate_silence_wav(.1)).decode()}),flush=True)
server.serve_forever()
`,artifacts);
  const browser=await launchChromium();
  try {
    for(const width of [1440,320]) {
      const page=await browser.newPage({viewport:{width,height:900}}),errors=[];
      page.on('pageerror',error=>errors.push(error.message));
      try {
        await page.goto(server.fixture.url);
        await page.evaluate(()=>document.dispatchEvent(new CustomEvent('lixity:open-speech-studio',{detail:{mode:'output'}})));
        await page.locator('#speech-chapter_audio_file').waitFor({state:'visible'});
        await page.waitForFunction(()=>!document.querySelector('[data-speech-action=chapter_audio_import]').disabled);
        await page.locator('#speech-chapter').selectOption('2');
        const bound=await page.evaluate(()=>({project_token:document.querySelector('#settings-form').dataset.projectToken,source_sha256:document.body.dataset.manuscriptSourceSha256}));
        await page.locator('#speech-chapter_audio_file').setInputFiles({name:'chapter.wav',mimeType:'audio/wav',buffer:Buffer.from(server.fixture.wav,'base64')});
        const pending=page.waitForRequest(request=>request.url().endsWith('/api/speech-audio-import'));
        await page.locator('[data-speech-action=chapter_audio_import]').click();
        const submitted=(await pending).postDataJSON();
        assert.equal(submitted.chapter,2);
        assert.equal(submitted.project_token,bound.project_token);
        assert.equal(submitted.source_sha256,bound.source_sha256);
        await page.waitForFunction(()=>document.querySelector('#speech-chapter-audio-status').textContent.includes(uiLabel('speech_chapter_audio_ready')));
        const inventory=await page.evaluate(async bound=>(await fetch('/api/speech-audio-artifacts?'+new URLSearchParams(bound))).json(),bound);
        assert.equal(inventory.artifacts.length,1);
        assert.equal(inventory.artifacts[0].origin,'imported');
        assert.equal(await page.locator('#speech-chapter-audio-status').innerText().then(text=>text.includes(inventory.artifacts[0].audio_sha256)),false);
        await page.locator('#speech-chapter_audio_file').setInputFiles({name:'broken.wav',mimeType:'audio/wav',buffer:Buffer.from('not a WAV')});
        await page.locator('[data-speech-action=chapter_audio_import]').click();
        await page.waitForFunction(()=>document.querySelector('#speech-chapter-audio-status').textContent.includes('WAV'));
        const after=await page.evaluate(async bound=>(await fetch('/api/speech-audio-artifacts?'+new URLSearchParams(bound))).json(),bound);
        assert.deepEqual(after.artifacts,inventory.artifacts,'A bad import cannot replace retained audio');
        await page.locator('#speech-chapter-audio-status').scrollIntoViewIfNeeded();
        await page.screenshot({path:path.join(artifacts,`chapter-import-${width}.png`)});
        const inventoryFailure='Synthetic retained-audio inventory is unreadable.';
        await page.route('**/api/speech-audio-artifacts?*',route=>route.fulfill({status:503,json:{ok:false,message:inventoryFailure}}));
        await page.locator('#speech-tab-profiles').click();
        await page.locator('#speech-tab-reader').click();
        await page.waitForFunction(message=>document.querySelector('#speech-chapter-audio-status').textContent===message,inventoryFailure);
        await page.locator('#speech-chapter').selectOption('1');
        assert.equal(await page.locator('#speech-chapter-audio-status').innerText(),inventoryFailure,
          'Changing chapter after an unreadable inventory must not claim an old missing/ready state');
        await page.locator('#speech-chapter').selectOption('2');
        assert.equal(await page.locator('#speech-chapter-audio-status').innerText(),inventoryFailure);
        await page.unroute('**/api/speech-audio-artifacts?*');
        await page.locator('#speech-tab-profiles').click();
        await page.locator('#speech-tab-reader').click();
        await page.waitForFunction(()=>document.querySelector('#speech-chapter-audio-status').textContent.includes(uiLabel('speech_chapter_audio_ready')));
        assert.deepEqual(errors,[]);
      } finally {await page.close();}
    }
    console.log('Chapter audio import and failed replacement passed: '+artifacts);
  } finally {await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
