const {startNativeServer} = require('./support/native-server.cjs');
// Explicit metadata, fresh save tokens and drafts against a synthetic local API.
const {launchChromium,playwrightModule}=require('../../scripts/browser_tools.cjs');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const assert=require('node:assert/strict');
const {expect}=require(path.join(playwrightModule,'test'));
const artifacts=fs.mkdtempSync(path.join(os.tmpdir(),'lixity-publication-settings-'));
function bounded(promise,label){let timer;return Promise.race([promise,new Promise((_,reject)=>{
  timer=setTimeout(()=>reject(new Error('Timed out: '+label)),10000);
})]).finally(()=>clearTimeout(timer));}
(async()=>{
  const server=await startNativeServer(`
import json,sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
project=Path(sys.argv[1])/'synthetic-publication'
api.init(project,title='Synthetic publication project')
other=Path(sys.argv[1])/'other-synthetic-publication'
api.init(other,title='Other synthetic publication project')
LixityServerHandler.workspace_root=str(project)
LixityServerHandler.research_dir=str(project)
LixityServerHandler.language='en'
LixityServerHandler.refresh()
server=ThreadingHTTPServer(('127.0.0.1',0),LixityServerHandler)
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','project':str(project),'other':str(other)}),flush=True)
server.serve_forever()
`,artifacts);
  let browser,release;
  try{
    const fixture=server.fixture;
    browser=await launchChromium();const page=await browser.newPage({viewport:{width:1440,height:1000}});
    page.setDefaultTimeout(10000);
    await page.addInitScript(()=>{
      const original=window.setTimeout;
      window.setTimeout=function(callback,delay,...args){
        if(delay===1200){window.finishSettingsReload=()=>callback(...args);return 0;}
        return original.call(window,callback,delay,...args);
      };
    });
    const url=fixture.url+'/api/settings';
    for(const width of [1440,320]) {
    await page.setViewportSize({width,height:1000});
    await page.goto(fixture.url);await page.locator('[data-view=project]').click();
    await expect(page.locator('#settings-publication')).not.toHaveAttribute('open','');
    await page.locator('#settings-publication > summary').click();
    await page.locator('#set-publication-enabled').check();
    await page.locator('#set-publication-publisher_name').fill('First synthetic publisher');
    await page.locator('#set-publication-year').fill('2026');
    const oldToken=await page.locator('#settings-form').getAttribute('data-project-token');
    assert.match(oldToken,/^[a-f0-9]{64}$/);
    let requested,submitted,accepted,cleaning=false;
    const ready=new Promise(resolve=>{requested=resolve;});const gate=new Promise(resolve=>{release=resolve;});
    await page.route(url,async route=>{
      submitted=route.request().postDataJSON();const response=await route.fetch();accepted=await response.json();
      requested();await gate;try{await route.fulfill({response});}catch(error){if(!cleaning)throw error;}
    });
    try{
      await page.locator('[data-action=settings]').click();await bounded(ready,'accepted settings');
      assert.ok(Object.hasOwn(submitted,'publication'),'Edited publication fields are submitted together');
      assert.equal(submitted.publication.publisher_name,'First synthetic publisher');
      assert.equal(submitted.publication.year,'2026');assert.equal(submitted.publication.enabled,true);
      assert.equal(submitted.project_token,oldToken);
      assert.equal(Object.hasOwn(submitted,'title'),false,'Publication-only save does not persist a display title');
      assert.equal(Object.hasOwn(submitted,'author_name'),false,'Unchanged identity is not resubmitted');
      await page.locator('#set-publication-publisher_name').fill('New unsaved synthetic publisher');
      const response=page.waitForResponse(result=>result.url()===url);release();await response;
      await expect(page.locator('[data-action=settings]')).toBeEnabled();
      await expect(page.locator('#set-publication-publisher_name')).toHaveValue('New unsaved synthetic publisher');
      await expect(page.locator('#settings-form')).toHaveAttribute('data-project-token',accepted.project_token);
      assert.notEqual(accepted.project_token,oldToken);
      await page.waitForFunction(()=>Boolean(window.finishSettingsReload));
      await page.evaluate(()=>window.finishSettingsReload());
      await expect(page.locator('#set-publication-publisher_name')).toHaveValue('New unsaved synthetic publisher');
    }finally{cleaning=true;release();await page.unroute(url);}
    const second=page.waitForRequest(request=>request.url()===url);
    const secondResponse=page.waitForResponse(response=>response.url()===url);
    await page.locator('[data-action=settings]').click();const request=await second;
    assert.equal(request.postDataJSON().project_token,accepted.project_token);
    assert.equal(request.postDataJSON().publication.publisher_name,'New unsaved synthetic publisher');
    assert.equal((await secondResponse).status(),200);
    await expect(page.locator('[data-action=settings]')).toBeEnabled();
    await page.locator('#settings-thresholds > summary').click();
    await page.locator('#set-z-mild').fill('2.5');
    const thresholdRequest=page.waitForRequest(request=>request.url()===url);
    const thresholdResponse=page.waitForResponse(response=>response.url()===url);
    await page.locator('[data-action=settings]').click();
    const thresholdPayload=(await thresholdRequest).postDataJSON();
    for(const key of ['publication','title','author_name']) assert.equal(Object.hasOwn(thresholdPayload,key),false);
    assert.equal((await thresholdResponse).status(),200);
    await expect(page.locator('[data-action=settings]')).toBeEnabled();
    // A deliberately stale token must fail visibly and preserve all entered data.
    await page.locator('#settings-form').evaluate((form,token)=>{form.dataset.projectToken=token;},accepted.project_token);
    await page.locator('#set-publication-publisher_name').fill('Synthetic rejected draft');
    const stale=page.waitForResponse(response=>response.url()===url);
    await page.locator('[data-action=settings]').click();assert.equal((await stale).status(),409);
    await expect(page.locator('#set-publication-publisher_name')).toHaveValue('Synthetic rejected draft');
    await expect(page.locator('#ctl-status')).toHaveClass(/err/);
    }
    // The old form must not write publication into another selected root.
    await page.reload();await page.locator('[data-view=project]').click();
    await page.locator('#settings-publication > summary').click();
    assert.equal((await page.request.post(fixture.url+'/api/project-open',{data:{path:fixture.other}})).status(),200);
    await page.locator('#set-publication-publisher_name').fill('Wrong-root rejected draft');
    const staleRoot=page.waitForResponse(response=>response.url()===url);
    await page.locator('[data-action=settings]').click();assert.equal((await staleRoot).status(),409);
    await expect(page.locator('#set-publication-publisher_name')).toHaveValue('Wrong-root rejected draft');
    assert.equal((await page.request.post(fixture.url+'/api/project-open',{data:{path:fixture.project}})).status(),200);
    await page.reload();await page.locator('[data-view=project]').click();
    await page.locator('#settings-publication > summary').click();
    // An older accepted response cannot overwrite a connected form's newer context.
    let supersededReady,supersededRelease;
    const supersededGate=new Promise(resolve=>{supersededRelease=resolve;});
    const supersededAccepted=new Promise(resolve=>{supersededReady=resolve;});
    release=supersededRelease;
    await page.route(url,async route=>{const response=await route.fetch();supersededReady();await supersededGate;await route.fulfill({response});});
    await page.locator('#settings-thresholds > summary').click();
    await page.locator('#set-z-mild').fill('2.6');
    await page.locator('[data-action=settings]').click();await bounded(supersededAccepted,'superseded settings response');
    const replacementToken='1'.repeat(64);
    await page.locator('#settings-form').evaluate((form,token)=>{form.dataset.projectToken=token;},replacementToken);
    await page.locator('#ctl-status').evaluate(status=>{status.textContent='New context status';});
    const supersededResponse=page.waitForResponse(response=>response.url()===url);supersededRelease();await supersededResponse;
    await expect(page.locator('[data-action=settings]')).toBeEnabled();
    await expect(page.locator('#ctl-status')).toHaveText('New context status');
    await expect(page.locator('#settings-form')).toHaveAttribute('data-project-token',replacementToken);
    assert.equal(await page.evaluate(()=>Boolean(window.finishSettingsReload)),false);
    await page.unroute(url);
    for(const language of ['en','de','fr','es','it','pt','nl']){
      await page.request.post(url,{data:{language}});await page.reload();await page.locator('[data-view=project]').click();
      await page.locator('#settings-publication > summary').click();
      for(const width of language==='en'?[1440,390,320]:[1440,320]){
        await page.setViewportSize({width,height:1000});
        await expect(page.locator('#set-publication-publisher_name')).toHaveValue('New unsaved synthetic publisher');
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
        assert.equal(await page.locator('#set-publication-year').getAttribute('type'),'text');
        assert.equal(await page.locator('#settings-publication').getByText('publication_title',{exact:true}).count(),0);
        await page.locator('#settings-publication').screenshot({path:path.join(artifacts,`publication-${language}-${width}.png`)});
      }
    }
    console.log('Publication settings: explicit fields, held real saves at1440/320, identity/unchanged publication omission, newer drafts/fresh tokens/stale tokens/roots/responses and seven locales1440/390/320 passed. '+artifacts);
  }finally{
    if(release)release();
    try{if(browser)await browser.close();}finally{await server.close();}
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
