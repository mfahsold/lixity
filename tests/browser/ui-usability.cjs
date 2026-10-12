// Real held HTTP responses against a disposable synthetic research project.
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(require('node:path').join(playwrightModule,'test'));
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const {createInterface} = require('node:readline');
const root=path.resolve(__dirname,'../..');
const artifacts=fs.mkdtempSync(path.join(os.tmpdir(),'lixity-ui-usability-'));
function bounded(promise,label) {
  let timer;return Promise.race([promise,new Promise((_,reject)=>{
    timer=setTimeout(()=>reject(new Error('Timed out: '+label)),10000);
  })]).finally(()=>clearTimeout(timer));
}
(async()=>{
  const server=spawn(process.env.PYTHON_BIN||path.join(root,'.venv/bin/python'),['-u','-c',`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
project=Path(sys.argv[1])/'synthetic-project'
api.init(project,title='Synthetic usability project')
LixityServerHandler.workspace_root=str(project)
LixityServerHandler.research_dir=str(project)
LixityServerHandler.language='en'
LixityServerHandler.refresh()
server=ThreadingHTTPServer(('127.0.0.1',0),LixityServerHandler)
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}'}),flush=True)
server.serve_forever()
`,artifacts],{cwd:root,env:{...process.env,PYTHONPATH:path.join(root,'src')},stdio:['ignore','pipe','pipe']});
  let stderr='',browser;const lines=createInterface({input:server.stdout});
  server.stderr.on('data',data=>{stderr+=data;});
  const releases=[];
  try {
    const fixture=await bounded(new Promise((resolve,reject)=>{
      lines.once('line',line=>resolve(JSON.parse(line)));
      server.once('error',reject);server.once('exit',code=>reject(new Error('Synthetic server exited '+code+': '+stderr)));
    }),'fixture startup');
    browser=await launchChromium();
    for(const width of [1440,320]) {
    const page=await browser.newPage({viewport:{width,height:1000}});
    page.setDefaultTimeout(10000);
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.goto(fixture.url);
    await page.locator('[data-view=research]').click();
    for(const [tab,action,button,title,body] of [
      ['claims','research-claim-add','r-claim-create-btn','r-claim-title','r-claim-statement'],
      ['dossiers','research-dossier','r-dos-create-btn','r-dos-title','r-dos-body'],
      ['decisions','research-decision-add','r-decision-create-btn','r-decision-title','r-decision-rationale'],
    ]) {
      await page.locator(`[data-rtab=${tab}]`).click();
      await page.locator('#'+title).fill('First synthetic '+tab);
      await page.locator('#'+body).fill('First permitted synthetic text.');
      let release,requested,reads=0,cleaning=false;
      const gate=new Promise(resolve=>{release=resolve;});releases.push(release);
      const ready=new Promise(resolve=>{requested=resolve;});
      const url=fixture.url+'/api/'+action;
      await page.route(url,async route=>{
        reads++;const response=await route.fetch();requested();await gate;
        try{await route.fulfill({response});}catch(error){if(!cleaning)throw error;}
      });
      try {
        await page.locator('#'+button).click();await bounded(ready,action+' accepted response');
        await expect(page.locator('#'+button)).toBeDisabled();
        await expect(page.locator('#'+button)).toHaveAttribute('aria-busy','true');
        await page.locator('#'+button).dispatchEvent('click');
        await page.locator('#'+title).fill('New unsaved synthetic '+tab);
        await page.locator('#'+body).fill('A newer unsaved synthetic draft.');
        const accepted=page.waitForResponse(response=>response.url()===url);
        release();await accepted;
        await expect(page.locator('#'+button)).toBeEnabled();
        assert.equal(reads,1,'Pending form submits exactly once');
        await expect(page.locator('#'+title)).toHaveValue('New unsaved synthetic '+tab);
        await expect(page.locator('#'+body)).toHaveValue('A newer unsaved synthetic draft.');
        const status=page.locator('#'+button+'-status');
        await expect(status).toHaveClass(/\bok\b/);
        await expect(status).not.toBeEmpty();
        assert.ok(await status.evaluate(element=>Math.abs(element.getBoundingClientRect().top-
          document.querySelector('#'+element.id.replace(/-status$/,'')).getBoundingClientRect().bottom)<120),
          'Result remains beside the submitting action');
      }finally{cleaning=true;release();await page.unroute(url);}
      await page.route(url,route=>route.fulfill({status:400,json:{ok:false,message:'Synthetic rejected <img src=x onerror=alert(1)> draft'}}));
      try {
        await page.locator('#'+button).click();
        await expect(page.locator('#'+button+'-status')).toHaveClass(/\berr\b/);
        await expect(page.locator('#'+title)).toHaveValue('New unsaved synthetic '+tab);
        await expect(page.locator('#'+body)).toHaveValue('A newer unsaved synthetic draft.');
        assert.equal(await page.locator('#'+button+'-status img').count(),0,'Error text is inert');
        await expect(page.locator('#'+button)).toBeEnabled();
      }finally{await page.unroute(url);}
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      await page.screenshot({path:path.join(artifacts,`${tab}-${width}.png`)});
    }
    await page.locator('[data-rtab=claims]').click();
    const token=await page.locator('#research-manager').getAttribute('data-research-token');
    let exported;
    page.on('request',request=>{if(new URL(request.url()).pathname==='/api/research/matrix')exported=new URL(request.url());});
    const download=page.waitForEvent('download');await page.locator('#r-claim-matrix-btn').click();await download;
    assert.equal(exported.searchParams.get('research_token'),token,'Matrix reuses guarded research read');
    await page.locator('[data-view=research]').focus();await page.keyboard.press('ArrowRight');
    await expect(page.locator('[data-view=analysis]')).toBeFocused();
    await expect(page.locator('[data-view=research]')).toHaveAttribute('tabindex','-1');
    await page.locator('[data-view=research]').click();
    await page.locator('[data-rtab=sources]').focus();await page.keyboard.press('ArrowRight');
    await expect(page.locator('[data-rtab=search]')).toBeFocused();
    await page.keyboard.press('Enter');await expect(page.locator('[data-rtab=search]')).toHaveAttribute('aria-selected','true');
    assert.deepEqual(errors,[]);
    await page.close();
    }
    console.log('UI usability: real held create responses preserve newer drafts, single busy save/local inert feedback, guarded matrix and shared keyboard tabs passed at1440/320. '+artifacts);
  }finally{
    releases.forEach(release=>release());if(browser)await browser.close();lines.close();
    if(server.exitCode===null&&server.signalCode===null){const exited=once(server,'exit');server.kill();await bounded(exited,'server cleanup');}
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
