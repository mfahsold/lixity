// Synthetic capture only: no microphone, speakers, project or server mutation.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pythonFixture} = require('./support/python-fixture.cjs');
const labels=pythonFixture('import json; from lixity.workspace_labels import WORKSPACE_LABELS; print(json.dumps(WORKSPACE_LABELS["de"]))');

const textContrast = locator => locator.evaluate(element => {
  const channels = color => color.match(/[\d.]+/g).map(Number);
  const luminance = rgb => rgb.slice(0, 3).map(value => value / 255)
    .map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4)
    .reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
  const layers = [];
  for (let node = element; node; node = node.parentElement) {
    const [red, green, blue, alpha = 1] = channels(getComputedStyle(node).backgroundColor);
    layers.push({rgb: [red, green, blue], alpha});
    if (alpha === 1) break;
  }
  const background = layers.reduceRight((base, {rgb, alpha}) =>
    rgb.map((value, index) => value * alpha + base[index] * (1 - alpha)), [255, 255, 255]);
  const foreground = luminance(channels(getComputedStyle(element).color));
  const backdrop = luminance(background);
  return (Math.max(foreground, backdrop) + .05) / (Math.min(foreground, backdrop) + .05);
});

(async () => {
  const browser = await launchChromium();
  const artifacts = fs.mkdtempSync('/tmp/lixity-teleprompter-take-');
  try {
    for (const width of [1440,320]) {
      const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce'}), errors=[];
      page.on('pageerror',error=>errors.push(error.message));
      await page.route('http://localhost:41739/**',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><html lang="en"><body data-speech-capable="false" data-manuscript-source-sha256="synthetic-source"><form id="settings-form" data-project-token="synthetic-project"></form><button id="reader-teleprompter">Teleprompter</button><main id="chapters"><section class="chapter" id="ch-1"><h2>Garden</h2><div class="ptext" data-start="3" data-end="3" data-paragraph-sha256="synthetic-paragraph"><div class="ptext-inner"><p>A synthetic reading script is not a transcript.</p></div></div></section></main></body></html>'}));
      await page.goto('http://localhost:41739/');
      const theme = width === 1440 ? 'light' : 'dark';
      await page.evaluate(({labels, theme})=>{
        window.uiLabel=key=>labels[key]||key;
        document.documentElement.dataset.theme=theme;
      },{labels, theme});
      await page.evaluate(()=>{
        window.testCapture={requests:[],stops:0,closes:0,resumes:0,portsClosed:0,revoked:[],mode:'pending'};
        const create=URL.createObjectURL.bind(URL),revoke=URL.revokeObjectURL.bind(URL);
        URL.createObjectURL=value=>create(value);URL.revokeObjectURL=url=>{testCapture.revoked.push(url);revoke(url);};
        Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia:()=>new Promise((resolve,reject)=>testCapture.requests.push({resolve,reject}))}});
        window.AudioContext=class {
          constructor(options){this.sampleRate=options?.sampleRate||48000;this.state='suspended';this.destination={};
            this.audioWorklet={addModule:()=>testCapture.mode==='module-pending'
              ? new Promise(resolve=>{testCapture.resolveModule=resolve;}) : Promise.resolve()};}
          resume(){testCapture.resumes++; if(testCapture.mode==='resume-error')return Promise.reject(new Error('synthetic closed context'));this.state='running';return Promise.resolve();}
          close(){testCapture.closes++;this.state='closed';return Promise.resolve();}
          createMediaStreamSource(){return {connect(){},disconnect(){}};}
        };
        window.AudioWorkletNode=class {
          constructor(){this.port={close(){testCapture.portsClosed++;}};testCapture.processor=this;}
          connect(){}
          disconnect(){}
        };
        window.resolveCapture=()=>testCapture.requests.at(-1).resolve({getTracks:()=>[{stop:()=>testCapture.stops++}]});
        window.feedCapture=()=>testCapture.processor.port.onmessage({data:new Float32Array(48000)});
        document.addEventListener('lixity:open-speech-studio',event=>{window.handedTake=event.detail;});
      });
      for(const file of ['design-tokens.css','components.css','teleprompter.css','speech-player.css'])await page.addStyleTag({content:fs.readFileSync('src/lixity/ui/assets/'+file,'utf8')});
      for(const file of ['icons.js','audio-take.js','speech-player.js','teleprompter.js'])await page.addScriptTag({path:path.resolve('src/lixity/ui/assets',file)});
      const record=page.locator('.teleprompter-btn-record'),state=page.locator('#teleprompter-record-status'),card=page.locator('.teleprompter-take-card');
      try {
        await page.locator('#reader-teleprompter').click();
        const play = page.locator('.teleprompter-btn-primary');
        await play.hover();
        const start = await textContrast(play);
        await play.click();
        const pause = await textContrast(play);
        await play.click();
        const context = page.locator('.teleprompter-dossier-toggle');
        await context.click();
        const note = page.locator('.teleprompter-sidebar-empty');
        await note.waitFor();
        const sidebar = await textContrast(note);
        await context.click();
        assert.ok([start, pause, sidebar].every(value => value >= 4.5),
          `Contrast at ${width}px with the ${theme} app theme: start ${start}, pause ${pause}, sidebar ${sidebar}`);
        assert.equal(await page.locator('#teleprompter-modal').evaluate(el=>getComputedStyle(el).colorScheme),'dark');
        await record.click();
        assert.equal(await state.getAttribute('data-state'),'pending','Permission pending is visible before audio capture begins');
        assert.ok(await state.isVisible());assert.equal(await record.evaluate(el=>el.classList.contains('is-active')),false);
        await page.evaluate(()=>testCapture.requests.at(-1).reject(new DOMException('Denied','NotAllowedError')));
        await page.waitForFunction(()=>document.querySelector('#teleprompter-record-status')?.dataset.state==='failed');
        assert.match(await state.innerText(),/Mikrofon|microphone/i);assert.equal(await record.evaluate(el=>el.classList.contains('is-active')),false);
        await record.click();await page.evaluate(()=>resolveCapture());
        await page.waitForFunction(()=>document.querySelector('#teleprompter-record-status')?.dataset.state==='running');
        assert.equal(await page.evaluate(()=>testCapture.resumes),1);await page.evaluate(()=>feedCapture());await record.click();
        await card.waitFor();assert.equal(await card.locator('textarea').inputValue(),'','Reading script is never silently a transcript');
        assert.equal(await card.locator('input[type=checkbox]').isChecked(),false);
        assert.equal(await card.locator('[data-take-studio]').count(),0,'Static reading copies retain downloads without offering an unavailable native Studio');
        const originalUrl=await card.locator('audio').getAttribute('src');
        await card.locator('textarea').fill('A river flows.');await card.locator('textarea').press('End');await card.locator('textarea').press('Space');
        assert.equal(await card.locator('textarea').inputValue(),'A river flows. ','Teleprompter shortcuts must not consume transcript editing');
        await card.locator('input[type=checkbox]').check();
        await card.locator('textarea').fill('Invalid\u0001transcript');
        assert.ok(await card.locator('[data-take-download="json"]').isDisabled(),'Invalid visible transcript cannot export stale confirmed metadata');
        await card.locator('textarea').fill('A river flows. ');await card.locator('input[type=checkbox]').check();
        assert.equal(await state.getAttribute('data-state'),'ready');
        await page.waitForFunction(()=>{const rect=document.querySelector('.teleprompter-sidebar.is-open').getBoundingClientRect();return rect.left>=0&&rect.right<=innerWidth+1;});
        await page.screenshot({path:path.join(artifacts,'take-'+width+'.png')});
        const downloads={};
        for(const kind of ['wav','json']){
          const pending=page.waitForEvent('download');await card.locator('[data-take-download="'+kind+'"]').click();const download=await pending;
          downloads[kind]={name:download.suggestedFilename(),mimeType:kind==='wav'?'audio/wav':'application/json',buffer:fs.readFileSync(await download.path())};
        }
        const metadata=JSON.parse(downloads.json.buffer);assert.equal(metadata.transcript.status,'confirmed');assert.equal(metadata.audio.sample_rate_hz,24000);
        // Failed pairing preserves the previously playable card and URL.
        await page.locator('#teleprompter-take-files').setInputFiles([downloads.wav,{...downloads.json,buffer:Buffer.from('{}')}]);
        await page.waitForFunction(()=>document.querySelector('#teleprompter-record-status')?.dataset.state==='failed');
        assert.equal(await card.locator('audio').getAttribute('src'),originalUrl);
        await page.evaluate(()=>document.body.dataset.speechCapable='true');
        await page.locator('#teleprompter-take-files').setInputFiles([downloads.wav,downloads.json]);
        await page.waitForFunction(previous=>document.querySelector('.teleprompter-take-card audio')?.src!==previous,originalUrl);
        assert.ok(await page.evaluate(url=>testCapture.revoked.includes(url),originalUrl));assert.equal(await card.count(),1);
        await card.locator('textarea').fill('Invalid\u0001transcript');
        assert.ok(await card.locator('[data-take-studio]').isDisabled(),'An invalid transcript cannot be handed to native Studio');
        await card.locator('textarea').fill('A river flows. ');await card.locator('input[type=checkbox]').check();
        // A validation result arriving after project selection changed cannot replace the current take.
        const retainedUrl=await card.locator('audio').getAttribute('src');
        await page.evaluate(()=>{const digest=crypto.subtle.digest.bind(crypto.subtle);crypto.subtle.digest=async(...args)=>{testCapture.hashWaiting=true;await new Promise(resolve=>testCapture.finishHash=resolve);return digest(...args);};testCapture.restoreHash=()=>crypto.subtle.digest=digest;});
        await page.locator('#teleprompter-take-files').setInputFiles([downloads.wav,downloads.json]);
        await page.waitForFunction(()=>testCapture.hashWaiting);
        await page.evaluate(()=>{document.body.dataset.manuscriptSourceSha256='changed-source';testCapture.finishHash();});
        await page.waitForFunction(()=>!document.querySelector('.teleprompter-btn-record').disabled);
        assert.equal(await card.locator('audio').getAttribute('src'),retainedUrl);
        await page.evaluate(()=>{testCapture.restoreHash();document.body.dataset.manuscriptSourceSha256='synthetic-source';});
        await page.evaluate(()=>LixityTeleprompter.close());await page.locator('#reader-teleprompter').click();
        await page.locator('.teleprompter-dossier-toggle').click();assert.equal(await card.count(),1,'Sidebar context refresh cannot remove the take');
        await card.locator('[data-take-studio]').click();
        const handoff=await page.evaluate(()=>({mode:handedTake.mode,context:handedTake.context,transcript:handedTake.take.transcript,status:handedTake.take.transcript_status}));
        assert.deepEqual(handoff,{mode:'reference',context:{project_token:'synthetic-project',source_sha256:'synthetic-source'},transcript:'A river flows. ',status:'confirmed'});
        // Closing pending permission revokes a late stream without starting capture.
        await page.locator('#reader-teleprompter').click();await record.click();await page.evaluate(()=>LixityTeleprompter.close());
        const stopped=await page.evaluate(()=>testCapture.stops);await page.evaluate(()=>resolveCapture());await page.waitForFunction(before=>testCapture.stops>before,stopped);
        await page.locator('#reader-teleprompter').click();await record.click();
        await page.evaluate(()=>{document.body.dataset.manuscriptSourceSha256='changed-source';resolveCapture();});
        await page.waitForFunction(()=>document.querySelector('#teleprompter-record-status')?.dataset.state==='failed');
        assert.equal(await record.evaluate(el=>el.classList.contains('is-active')),false);
        await page.evaluate(()=>{document.body.dataset.manuscriptSourceSha256='synthetic-source';LixityTeleprompter.close();});
        await page.locator('#reader-teleprompter').click();await page.evaluate(()=>testCapture.mode='resume-error');await record.click();await page.evaluate(()=>resolveCapture());
        await page.waitForFunction(()=>document.querySelector('#teleprompter-record-status')?.dataset.state==='failed');
        assert.equal(await record.evaluate(el=>el.classList.contains('is-active')),false);
        // A worklet arriving after dismissal cannot reactivate capture or retain a port.
        await page.evaluate(()=>testCapture.mode='module-pending');
        await record.click();await page.evaluate(()=>resolveCapture());
        await page.waitForFunction(()=>typeof testCapture.resolveModule==='function');
        const beforeModule=await page.evaluate(()=>({stops:testCapture.stops,ports:testCapture.portsClosed}));
        await page.evaluate(()=>{LixityTeleprompter.close();testCapture.resolveModule();});
        await page.waitForFunction(before=>testCapture.stops===before.stops+1&&testCapture.portsClosed===before.ports+1,beforeModule);
        assert.equal(await record.evaluate(el=>el.classList.contains('is-active')),false);assert.deepEqual(errors,[]);
      } finally {await page.close();}
    }
    console.log('Teleprompter capture, transcript review, portable files, preserved take and Studio handoff passed: '+artifacts);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
