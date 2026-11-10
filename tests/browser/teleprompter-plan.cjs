// Teleprompter reading cues reuse the canonical exported speech projection.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const browser = await launchChromium();
  const artifacts = fs.mkdtempSync('/tmp/lixity-teleprompter-plan-');
  const source = 'Ein <em id="synthetic-markup">Wort</em> Vogel und Amsel.';
  const anchor = {start_line:3,end_line:3,paragraph_sha256:'synthetic-paragraph'};
  const start = source.indexOf('Vogel');
  const profile = {name:'Synthetic author',voice:'reference',reference_id:'opaque-reference',phonemes:{Vogel:'ˈfoːɡəl'}};
  function segment(text, begin, controls, instructions, phones, before, after) {
    return {text,spoken_text:text,original_text:text,profile,anchor,
      source_range:{start:begin,end:begin+text.length,unit:'unicode-code-point',projection:'spoken-projection'},
      instructions,prosody:controls,phonemes:phones,pause_before:before,pause_after:after};
  }
  const timeline = {schema_version:'lixity-audio-timeline/2',segments:[
    segment(source.slice(0,start),0,{duration_scaling_factor:1.25},'',[],0.2,0),
    segment('Vogel',start,{pitch_variance_scale:1.4},'Leise sprechen',[{start:0,end:5,text:'Vogel',ipa:'ˈfoːɡəl'}],0,0),
    segment(source.slice(start+5),start+5,{energy_variance_scale:0.8},'',[],0,0.6)
  ]};
  try {
    for (const width of [1440,320]) {
      const page = await browser.newPage({viewport:{width,height:900}}), errors = [], plans = [];
      let failPlan = false, releasePlan;
      const planReady = new Promise(resolve => { releasePlan = resolve; });
      page.on('pageerror',error=>errors.push(error.message));
      await page.route('http://localhost:41739/**', async route => {
        const url = new URL(route.request().url());
        if(url.pathname==='/') return route.fulfill({contentType:'text/html',body:`<!doctype html><html><body data-api="/view/synthetic/api" data-speech-capable="true" data-manuscript-source-sha256="synthetic-source">
          <form id="settings-form" data-project-token="synthetic-project"></form><button id="reader-teleprompter">Teleprompter</button>
          <main id="chapters"><section class="chapter" id="ch-1"><h2>Garten</h2><div class="ptext" data-start="3" data-end="3" data-paragraph-sha256="synthetic-paragraph"><div class="ptext-inner"><p>${source.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')}</p></div></div></section></main></body></html>`});
        if(url.pathname.endsWith('/speech-plan')) {
          assert.equal(route.request().method(),'POST');
          plans.push(route.request().postDataJSON());
          await planReady;
          return route.fulfill({status:failPlan?409:200,json:failPlan?{ok:false,message:'Synthetic stale direction'}:{ok:true,timeline}});
        }
        // The old UI's GET is kept only to demonstrate the failing regression.
        assert.ok(url.pathname.endsWith('/speech'));
        return route.fulfill({json:{ok:true,settings:{pronunciations:{}},direction:{directions:[]}}});
      });
      await page.goto('http://localhost:41739/');
      for (const file of ['design-tokens.css','dashboard.css','teleprompter.css']) await page.addStyleTag({content:fs.readFileSync(path.join(__dirname,'../../src/lixity/ui/assets',file),'utf8')});
      await page.evaluate(() => {window.uiLabel=key=>({teleprompter_plan_loading:'Regie wird geladen…',teleprompter_plan_ready:'Gespeicherte Sprechprojektion',teleprompter_plan_failed:'Regie nicht verfügbar. Manuskripttext ohne Sprechhinweise.',speech_prosody_duration_scaling_factor:'Sprechdauer',speech_prosody_pitch_variance_scale:'Intonation',speech_prosody_energy_variance_scale:'Betonung',speech_export_pause_before:'Pause davor',speech_export_pause_after:'Pause danach'}[key]||key);});
      for (const file of ['speech-presentation.js','teleprompter.js']) {
        const script=path.join(__dirname,'../../src/lixity/ui/assets',file);
        if(fs.existsSync(script)) await page.addScriptTag({content:fs.readFileSync(script,'utf8')});
      }
      try {
        await page.locator('#reader-teleprompter').click();
        // Establish the initial active passage before releasing the async plan.
        // The runway selects it on a deferred layout tick, independently of fetch.
        await page.waitForFunction(() => document.querySelectorAll('.teleprompter-paragraph.is-active').length === 1);
        releasePlan();
        for (const selector of ['.teleprompter-toolbar .teleprompter-btn-close','.teleprompter-btn-record','.teleprompter-speed-control input']) {
          const rect=await page.locator(selector).boundingBox();
          assert.ok(rect.x>=0 && rect.x+rect.width<=width,selector+' must remain reachable on compact screens');
        }
        assert.equal(await page.locator('.teleprompter-text #synthetic-markup').count(),0,'Manuscript markup must remain literal text, never HTML');
        await page.locator('.teleprompter-phonetic rt').waitFor();
        assert.equal(await page.locator('.teleprompter-phonetic rt').textContent(),'[ˈfoːɡəl]');
        assert.equal((await page.locator('.teleprompter-spoken').allTextContents()).join(''),source.replace('Vogel','Vogel[ˈfoːɡəl]'));
        assert.deepEqual(plans,[{project_token:'synthetic-project',source_sha256:'synthetic-source',mode:'manuscript',chapter:null}]);
        const cues=await page.locator('.teleprompter-cue').allTextContents();
        assert.equal(cues.length,3,'Every exported range has its own effective cues');
        assert.ok(cues.some(text=>text.includes('Sprechdauer: 1.25')&&text.includes('Pause davor: 0.2 s')),'Pause and structured controls do not require free-text instructions');
        assert.ok(cues.some(text=>text.includes('Leise sprechen')&&text.includes('Intonation: 1.4')));
        assert.ok(cues.some(text=>text.includes('Betonung: 0.8')&&text.includes('Pause danach: 0.6 s')));
        assert.ok(!(await page.locator('#teleprompter-modal').innerText()).includes('opaque-reference'));
        assert.equal(await page.locator('.teleprompter-paragraph.is-active').count(),1,'Async plan loading preserves the active passage');
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
        const spokenBounds=await page.locator('.teleprompter-text').boundingBox();
        assert.ok(spokenBounds.x>=0 && spokenBounds.x+spokenBounds.width<=width,'Spoken text and cues fit inside the visible runway');
        await page.screenshot({path:path.join(artifacts,`plan-${width}.png`),animations:'disabled'});
        await page.evaluate(()=>window.LixityTeleprompter.close());
        failPlan=true;
        await page.locator('#reader-teleprompter').click();
        await page.waitForFunction(()=>document.querySelector('#teleprompter-plan-status')?.dataset.state==='failed');
        assert.equal(await page.locator('.teleprompter-cue,.teleprompter-phonetic').count(),0,'Failed planning cannot retain previous project cues');
        assert.equal(await page.locator('.teleprompter-text').textContent(),source);
        assert.ok(await page.locator('#teleprompter-plan-status').isVisible());
        assert.deepEqual(errors,[]);
      } finally {await page.close();}
    }
    console.log('Canonical teleprompter projection, safe text, IPA, range prosody and error fallback passed: '+artifacts);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
