// Context is fetched only for an explicitly opened teleprompter and current project.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');

async function dossierContext(browser, width, artifacts) {
  const page = await browser.newPage({viewport:{width,height:900}}), errors = [], requests = [];
  const id = n => `urn:uuid:00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
  let releaseDetail, failReview = false, holdDetail = true, wrongProject = false, unavailableAnchor = false, cacheCount = 0;
  let detailReady = new Promise(resolve => { releaseDetail = resolve; });
  page.on('pageerror', error => errors.push(error.message));
  const image = (source, version, availability='available') => ({project_id:id(1),source_id:id(source),
    source_version_id:id(version),availability,media_type:'image/png',alt:'Retained synthetic image',title:'Pinned photograph',url:'https://invalid.example/untrusted-image.png'});
  await page.route('http://localhost:41739/**',async route => {
    const url=new URL(route.request().url());
    if(url.pathname==='/') return route.fulfill({contentType:'text/html',body:`<!doctype html><body data-api="/view/synthetic/api" data-manuscript-source-sha256="source-one">
      <form id="settings-form" data-project-token="project-one"></form><div id="research-manager" data-research-token="research-one"></div>
      <button id="reader-teleprompter">Teleprompter</button><main id="chapters"><section class="chapter" id="ch-1"><h2>One</h2>
      <div class="ptext" data-start="3" data-end="3" data-paragraph-sha256="same-text"><div class="ptext-inner"><p>Harbor walls remain.</p></div></div>
      <div class="ptext" data-start="7" data-end="7" data-paragraph-sha256="same-text"><div class="ptext-inner"><p>Harbor walls remain.</p></div></div>
      </section></main></body>`});
    requests.push(url);
    assert.ok(url.pathname.startsWith('/view/synthetic/api/research/'),'All research/media reads retain the workspace path');
    if(url.pathname.endsWith('/image')) {
      assert.equal(url.searchParams.get('project_id'),id(1));
      assert.ok([id(21),id(22),id(23)].includes(url.searchParams.get('version_id')));
      return route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=','base64')});
    }
    assert.equal(url.searchParams.get('research_token'),'research-one');
    if(url.pathname.endsWith('/status')) return route.fulfill({json:{ok:true,initialized:true,project_id:id(1)}});
    if(url.pathname.endsWith('/manuscript-review')) {
      assert.equal(url.searchParams.get('project_token'),'project-one');
      return route.fulfill({json:failReview?{ok:false}:{ok:true,schema_version:'research-manuscript-review-local/1',project_id:id(1),
        current_source_sha256:'source-one',source_state:'available',passage_context:{schema_version:'research-passage-context-local/1',paragraphs:[
          {start_line:3,end_line:3,paragraph_sha256:'same-text',state:unavailableAnchor?'unavailable':'ready',groups:[{dossier:{current:{id:id(2),title:'Old port',revision:2},pins:[{id:id(2),title:'Old port',revision:1}]},
            claims:[{versions:[{dossier_revision:1}]}]}]}
        ].concat(Array.from({length:cacheCount},(_,n)=>({start_line:100+n,end_line:100+n,paragraph_sha256:'cache-'+n,state:'ready',
          groups:[{dossier:{current:{id:id(100+n),title:'Cache example',revision:1},pins:[]},claims:[{versions:[{dossier_revision:1}]}]}]})))}}});
    }
    assert.ok(url.pathname.endsWith('/dossiers'));
    assert.equal(url.searchParams.get('project_token'),'project-one');
    if(!url.searchParams.has('id')) return route.fulfill({json:{ok:true,project_id:id(1),dossiers:[
      {id:id(2),title:'Old port',revision:2,tags:[]},{id:id(3),title:'Harbor',revision:3,tags:[]}]}});
    const cachePin=Array.from({length:cacheCount},(_,n)=>id(100+n)).includes(url.searchParams.get('id'));
    if(cachePin) {
      assert.equal(url.searchParams.get('revision'),'1');
      return route.fulfill({json:{ok:true,project_id:id(1),id:url.searchParams.get('id'),revision:1,title:'Cache example',images:[]}});
    }
    const direct=url.searchParams.get('id')===id(2);
    assert.equal(url.searchParams.get('revision'),direct?'1':'3','Use pinned direct dossier revision or explicit summary revision');
    if(direct&&holdDetail) await detailReady;
    return route.fulfill({json:{ok:true,project_id:wrongProject?id(99):id(1),id:direct?id(2):id(3),revision:direct?1:3,title:direct?'Old port':'Harbor',
      images:direct?[image(11,21),image(12,22),image(14,24,'withdrawn')]:[image(13,23)]}});
  });
  try {
    await page.goto('http://localhost:41739/');
    await page.evaluate(()=>{
      window.API='/view/synthetic/api';window.LixitySite={readOnly:false};
      window.uiLabel=key=>({teleprompter_images_loading:'Loading dossier images',teleprompter_images_failed:'Dossier images unavailable',
        teleprompter_images_suggested:'Suggested by title or tags',image_withdrawn:'Withdrawn image',image_retained:'Retained'}[key]||key);
      window.jsonApi=async url=>(await fetch(url)).json();
    });
    for(const file of ['design-tokens.css','components.css','dashboard.css','dossier-images.css','teleprompter.css']) await page.addStyleTag({content:fs.readFileSync(path.join(__dirname,'../../src/lixity/ui/assets',file),'utf8')});
    for(const file of ['research-core.js','dossier-images.js','teleprompter.js']) await page.addScriptTag({content:fs.readFileSync(path.join(__dirname,'../../src/lixity/ui/assets',file),'utf8')});
    assert.equal(requests.length,0,'Research context is lazy');
    await page.locator('#reader-teleprompter').click();
    await page.waitForFunction(()=>document.querySelector('.teleprompter-sidebar-content')?.dataset.state==='loading');
    releaseDetail();
    await page.waitForFunction(()=>document.querySelectorAll('.teleprompter-sidebar-content img').length===2);
    await page.locator('.teleprompter-dossier-toggle').click();
    await page.waitForFunction(()=>Array.from(document.querySelectorAll('.teleprompter-sidebar-content img')).every(image=>image.complete&&image.naturalWidth));
    assert.ok((await page.locator('.teleprompter-sidebar-content').innerText()).includes('Withdrawn image'));
    const firstImages=await page.locator('.teleprompter-sidebar-content img').evaluateAll(images=>images.map(image=>image.src));
    assert.ok(firstImages.every(url=>url.includes('version_id=')&&!url.includes('/media?id=')));
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:path.join(artifacts,`dossier-${width}.png`),animations:'disabled'});
    for(const bounds of await page.locator('.teleprompter-sidebar-content .dossier-image').evaluateAll(nodes=>nodes.map(node=>{const box=node.getBoundingClientRect();return {left:box.left,right:box.right};}))) {
      assert.ok(bounds.left>=0&&bounds.right<=width,'Retained image cards stay inside the viewport: '+JSON.stringify({width,...bounds,artifacts}));
    }
    // Equal paragraph text/hash at another line must not inherit a direct association.
    await page.evaluate(()=>{
      const panes=document.querySelectorAll('.teleprompter-paragraph');panes[0].style.height='1000px';
      const pane=document.querySelector('.teleprompter-scroll-pane');pane.scrollTop=panes[1].offsetTop-200;pane.dispatchEvent(new Event('scroll'));
    });
    await page.waitForFunction(()=>document.querySelector('.teleprompter-sidebar-content')?.dataset.state==='suggested');
    assert.equal(await page.locator('.teleprompter-sidebar-content img').count(),1);
    assert.ok((await page.locator('.teleprompter-sidebar-content').innerText()).includes('Suggested by title or tags'));
    await page.evaluate(()=>{const pane=document.querySelector('.teleprompter-scroll-pane');pane.scrollTop=0;pane.dispatchEvent(new Event('scroll'));});
    await page.waitForFunction(()=>document.querySelectorAll('.teleprompter-sidebar-content img').length===2);
    assert.equal(requests.filter(url=>url.pathname.endsWith('/dossiers')&&url.searchParams.has('id')).length,2,'One detail read per pin, not per scroll');
    await page.evaluate(()=>{document.querySelector('#settings-form').dataset.projectToken='project-two';});
    await page.waitForFunction(()=>document.querySelector('.teleprompter-sidebar-content')?.dataset.state==='failed');
    assert.equal(await page.locator('.teleprompter-sidebar-content img').count(),0,'Context change removes old images immediately');
    await page.evaluate(()=>{window.LixityTeleprompter.close();document.querySelector('#settings-form').dataset.projectToken='project-one';});
    holdDetail=true;detailReady=new Promise(resolve=>{releaseDetail=resolve;});
    const pendingDetail=page.waitForRequest(request=>request.url().includes('/research/dossiers?id='));
    await page.locator('#reader-teleprompter').click();
    await pendingDetail;
    await page.evaluate(()=>{document.querySelector('#settings-form').dataset.projectToken='project-two';});releaseDetail();
    await page.waitForFunction(()=>document.querySelector('.teleprompter-sidebar-content')?.dataset.state==='failed');
    assert.equal(await page.locator('.teleprompter-sidebar-content img').count(),0,'Late details cannot populate another project');
    await page.evaluate(()=>{window.LixityTeleprompter.close();document.querySelector('#settings-form').dataset.projectToken='project-one';});
    holdDetail=false;wrongProject=true;
    await page.locator('#reader-teleprompter').click();
    await page.waitForFunction(()=>document.querySelector('.teleprompter-sidebar-content')?.dataset.state==='failed');
    assert.equal(await page.locator('.teleprompter-sidebar-content img').count(),0,'Foreign-project dossier details must be rejected');
    await page.evaluate(()=>window.LixityTeleprompter.close());wrongProject=false;unavailableAnchor=true;
    await page.locator('#reader-teleprompter').click();
    await page.waitForFunction(()=>document.querySelector('.teleprompter-sidebar-content')?.dataset.state==='failed');
    assert.equal(await page.locator('.teleprompter-sidebar-content img').count(),0,'Unavailable exact associations cannot become title-match suggestions');
    await page.evaluate(()=>window.LixityTeleprompter.close());unavailableAnchor=false;
    failReview=true;holdDetail=false;
    await page.locator('#reader-teleprompter').click();
    await page.waitForFunction(()=>document.querySelector('.teleprompter-sidebar-content')?.dataset.state==='failed');
    assert.equal(await page.locator('.teleprompter-sidebar-content img').count(),0,'Failed review cannot use stale or heuristic fallback images');
    if(width===1440) {
      await page.evaluate(()=>window.LixityTeleprompter.close());failReview=false;cacheCount=33;
      await page.evaluate(count=>{
        for(let n=0;n<count;n++) {
          const paragraph=document.createElement('div');paragraph.className='ptext';paragraph.dataset.start=paragraph.dataset.end=String(100+n);
          paragraph.dataset.paragraphSha256='cache-'+n;paragraph.innerHTML='<div class="ptext-inner"><p>Cache example.</p></div>';
          document.querySelector('.chapter').appendChild(paragraph);
        }
      },cacheCount);
      await page.locator('#reader-teleprompter').click();
      await page.waitForFunction(()=>document.querySelector('.teleprompter-sidebar-content')?.dataset.state==='ready');
      await page.evaluate(()=>document.querySelectorAll('.teleprompter-paragraph').forEach(paragraph=>{paragraph.style.minHeight='1000px';}));
      async function selectCacheParagraph(n) {
        await page.evaluate(n=>{
          const paragraph=document.querySelector('[data-sha="cache-'+n+'"]'),pane=document.querySelector('.teleprompter-scroll-pane');
          pane.scrollTop+=paragraph.getBoundingClientRect().top-pane.getBoundingClientRect().top-100;pane.dispatchEvent(new Event('scroll'));
        },n);
        await page.waitForFunction(n=>document.querySelector('[data-sha="cache-'+n+'"]')?.classList.contains('is-active')&&
          document.querySelector('.teleprompter-sidebar-content')?.dataset.state==='empty',n);
      }
      for(let n=0;n<cacheCount;n++) await selectCacheParagraph(n);
      await selectCacheParagraph(0);
      assert.equal(requests.filter(url=>url.pathname.endsWith('/dossiers')&&url.searchParams.get('id')===id(100)).length,2,
        'An old dossier is read again after eviction from the bounded per-open detail cache');
    }
    assert.deepEqual(errors,[]);
  } finally {releaseDetail();await page.close();}
}

(async () => {
  const browser = await launchChromium();
  const artifacts=fs.mkdtempSync('/tmp/lixity-teleprompter-images-');
  try {
    const page = await browser.newPage();
    const errors = [], requests = [], writes = [], lifecycleFailures = [];
    let releaseContext;
    const contextReady = new Promise(resolve => { releaseContext = resolve; });
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (request.method() === 'POST') writes.push(request.url()); });
    await page.route('http://localhost:41739/**', async route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/') return route.fulfill({contentType: 'text/html', body: `
        <html><body data-api="/view/synthetic/api" data-speech-capable="true" data-manuscript-source-sha256="source-one">
        <form id="settings-form" data-project-token="project-one"></form>
        <button id="reader-teleprompter">Teleprompter</button>
        <main id="chapters"><section class="chapter" id="ch-1"><h2>One</h2>
        <div class="ptext" data-start="3" data-end="3" data-paragraph-sha256="paragraph"><div class="ptext-inner"><p>A synthetic voice.</p></div></div>
        </section></main></body></html>`});
      requests.push(url);
      assert.equal(url.pathname, '/view/synthetic/api/speech-plan');
      assert.deepEqual(route.request().postDataJSON(), {project_token:'project-one',source_sha256:'source-one',mode:'manuscript',chapter:null});
      await contextReady;
      return route.fulfill({json: {ok:true,timeline:{segments:[{spoken_text:'A synthetic voice.',text:'A synthetic voice.',
        anchor:{start_line:3,end_line:3,paragraph_sha256:'paragraph'},phonemes:[{start:12,end:17,ipa:'vɔɪs'}]}]}}});
    });
    await page.goto('http://localhost:41739/');
    await page.addScriptTag({content: fs.readFileSync(path.join(__dirname, '../../src/lixity/ui/assets/audio-take.js'), 'utf8')});
    await page.addScriptTag({content: fs.readFileSync(path.join(__dirname, '../../src/lixity/ui/assets/speech-presentation.js'), 'utf8')});
    await page.addScriptTag({content: fs.readFileSync(path.join(__dirname, '../../src/lixity/ui/assets/teleprompter.js'), 'utf8')});
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
    assert.equal(requests.length, 0, 'Loading the reader must not request audio or research context');
    await page.locator('#reader-teleprompter').click();
    await page.locator('.teleprompter-paragraph.is-active').waitFor();
    releaseContext();
    await page.locator('.teleprompter-phonetic').waitFor();
    if (await page.locator('.teleprompter-paragraph.is-active[data-sha="paragraph"]').count() !== 1) {
      lifecycleFailures.push('Async context must preserve the active paragraph highlight');
    }
    assert.equal(requests.length, 1, 'Explicit opening reads exactly one token-bound audio context');
    assert.equal(await page.locator('.teleprompter-phonetic rt').textContent(), '[vɔɪs]');
    await page.evaluate(() => window.LixityTeleprompter.close());
    await page.evaluate(() => {
      document.body.dataset.speechCapable = 'false';
      document.querySelector('#settings-form').dataset.projectToken = '';
      window.LixityTeleprompter.open();
    });
    assert.equal(await page.locator('.teleprompter-phonetic').count(), 0, 'Reopening clears context from the previous project');
    assert.equal(requests.length, 1, 'A view without audio capability does not request speech data');
    await page.evaluate(() => {
      window.lateTrackStops = 0;
      Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {configurable:true,
        value:() => new Promise(resolve => { window.resolveTeleprompterMic = resolve; })});
    });
    await page.locator('.teleprompter-btn-record').click();
    await page.evaluate(() => {
      window.LixityTeleprompter.close();
      window.resolveTeleprompterMic({getTracks:() => [{stop:() => { window.lateTrackStops++; }}]});
    });
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
    if (await page.evaluate(() => window.lateTrackStops) !== 1) lifecycleFailures.push('Closing during permission acquisition must stop the late stream');
    await page.evaluate(async () => {
      window.LixityTeleprompter.open();
      // A silent local take exercises actual HTML media playback, not a pause mock.
      const samples = 32000, buffer = new ArrayBuffer(44 + samples * 2), wav = new DataView(buffer);
      function text(offset, value) { for (let i = 0; i < value.length; i++) wav.setUint8(offset + i, value.charCodeAt(i)); }
      text(0, 'RIFF'); wav.setUint32(4, 36 + samples * 2, true); text(8, 'WAVE'); text(12, 'fmt ');
      wav.setUint32(16, 16, true); wav.setUint16(20, 1, true); wav.setUint16(22, 1, true);
      wav.setUint32(24, 8000, true); wav.setUint32(28, 16000, true); wav.setUint16(32, 2, true); wav.setUint16(34, 16, true);
      text(36, 'data'); wav.setUint32(40, samples * 2, true);
      const audio = document.createElement('audio'); audio.id = 'synthetic-teleprompter-take'; audio.loop = true; audio.muted = true;
      window.teleprompterTakeUrl = URL.createObjectURL(new Blob([buffer], {type:'audio/wav'})); audio.src = window.teleprompterTakeUrl;
      document.getElementById('teleprompter-modal').appendChild(audio); await audio.play();
    });
    assert.equal(await page.locator('#synthetic-teleprompter-take').evaluate(audio => audio.paused), false);
    await page.evaluate(() => window.LixityTeleprompter.close());
    if (!await page.locator('#synthetic-teleprompter-take').evaluate(audio => audio.paused)) lifecycleFailures.push('Closing must pause recorded-take playback');
    await page.evaluate(() => { document.getElementById('synthetic-teleprompter-take').pause(); URL.revokeObjectURL(window.teleprompterTakeUrl); });
    await page.evaluate(() => {
      window.studioCalls = []; window.teleprompterSamplesDelivered = false;
      document.addEventListener('lixity:open-speech-studio', event => window.studioCalls.push(event.detail));
      // Feed deterministic silent PCM through the actual take encoder/card path.
      window.AudioContext = class {
        constructor() { this.sampleRate = 24000; this.destination = {}; this.state = 'suspended'; }
        resume() { this.state = 'running'; return Promise.resolve(); }
        createMediaStreamSource() { return {connect() {}, disconnect() {}}; }
        createScriptProcessor() {
          return {disconnect() {}, connect() {
            queueMicrotask(() => { this.onaudioprocess({inputBuffer:{getChannelData:() => new Float32Array(24000)}});
              window.teleprompterSamplesDelivered = true; });
          }};
        }
        close() { return Promise.resolve(); }
      };
      Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {configurable:true,
        value:async () => ({getTracks:() => [{stop() {}}]})});
      window.LixityTeleprompter.open();
    });
    await page.locator('.teleprompter-btn-record').click();
    await page.waitForFunction(() => window.teleprompterSamplesDelivered);
    await page.locator('.teleprompter-btn-record').click();
    const take = page.locator('.teleprompter-dossier-card').filter({has:page.locator('audio')});
    await take.waitFor();
    assert.equal(await take.locator('button').count(), 2, 'A static reading take has paired file exports without native save actions');
    assert.equal(await take.locator('.teleprompter-voice-studio-link').count(), 0);
    const download = page.waitForEvent('download');
    await take.locator('[data-take-download="wav"]').click();
    const saved = await download;
    assert(saved.suggestedFilename().endsWith('.wav'));
    assert.equal(fs.readFileSync(await saved.path()).subarray(0, 4).toString(), 'RIFF');
    assert.deepEqual(await page.evaluate(() => window.studioCalls), []);
    await page.evaluate(() => window.LixityTeleprompter.close());
    assert.equal(await page.locator('#teleprompter-modal').isVisible(), false);
    assert.deepEqual(writes, ['http://localhost:41739/view/synthetic/api/speech-plan'], 'Only the read-only plan request is sent; creating/downloading a take and opening the studio never saves a reference');
    assert.deepEqual(errors, []);
    assert.deepEqual(lifecycleFailures, []);
    for(const width of [1440,320]) await dossierContext(browser,width,artifacts);
    console.log('Teleprompter context, capture cleanup, playback close, WAV download, guarded retained dossier images and centralized studio entry passed: '+artifacts);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
