const {startNativeServer} = require('./support/native-server.cjs');
// Real held HTTP responses against a disposable synthetic research project.
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(require('node:path').join(playwrightModule,'test'));
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const artifacts=fs.mkdtempSync(path.join(os.tmpdir(),'lixity-ui-usability-'));
function bounded(promise,label) {
  let timer;return Promise.race([promise,new Promise((_,reject)=>{
    timer=setTimeout(()=>reject(new Error('Timed out: '+label)),10000);
  })]).finally(()=>clearTimeout(timer));
}
(async()=>{
  const server=await startNativeServer(`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.research import api
from lixity.server import LixityServerHandler
project=Path(sys.argv[1])/'synthetic-project'
api.init(project,title='Synthetic usability project')
manuscript=project/'manuscript.md'
manuscript.write_text('## One\\n\\nMara waits. '+('Measured prose. '*1234)+'\\n\\n## Two\\n\\nShe opens the door.\\n',encoding='utf-8')
(project/'lixity.toml').write_text('[characters.Mara]\\npov_in_chapters = [2]\\n',encoding='utf-8')
LixityServerHandler.workspace_root=str(project)
LixityServerHandler.research_dir=str(project)
LixityServerHandler.source_input=str(manuscript)
LixityServerHandler.language='en'
LixityServerHandler.refresh()
server=ThreadingHTTPServer(('127.0.0.1',0),LixityServerHandler)
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}'}),flush=True)
server.serve_forever()
`,artifacts);
  let browser;
  const releases=[];
  try {
    const fixture=server.fixture;
    browser=await launchChromium();
    for(const width of [1440,320]) {
    const page=await browser.newPage({viewport:{width,height:1000}});
    page.setDefaultTimeout(10000);
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.goto(fixture.url);
    await expect(page.locator('#characters')).toContainText('Character name mentions');
    await expect(page.locator('#characters')).toContainText('Declared POV chapters');
    const figure=page.locator('#characters tbody tr').first();
    await expect(figure.locator('td').nth(1)).toHaveText('1');
    await expect(figure.locator('td').nth(2)).toHaveText('1 / 2');
    await expect(figure.locator('td').last()).toHaveText('2');
    const overview=page.locator('#scenes .scene-overview');
    await expect(overview.locator('tbody tr')).toHaveCount(2);
    await overview.screenshot({path:path.join(artifacts,`scenes-${width}.png`)});
    const numericCells=await overview.locator('tbody td').evaluateAll(cells=>cells.map(cell=>{
      const range=document.createRange();range.selectNodeContents(cell);
      return {text:cell.textContent,lines:new Set(Array.from(range.getClientRects(),rect=>Math.round(rect.top))).size};
    }));
    assert.equal(numericCells.length,8,'Both scenes expose all four measured values');
    assert.ok(numericCells.every(cell=>cell.lines===1),
      'Scene numbers and their units remain on one line: '+JSON.stringify(numericCells));
    if(width===320) {
      await overview.focus();await page.keyboard.press('ArrowRight');
      await expect.poll(()=>overview.evaluate(element=>element.scrollLeft)).toBeGreaterThan(0);
      await overview.evaluate(element=>{element.scrollLeft=0;});
      const table=page.locator('#characters .table-wrap');
      assert.ok((await page.locator('#characters th').first().boundingBox()).width>=50,
        'Character headers must remain readable instead of wrapping into single letters');
      assert.ok(await page.locator('#characters th').first().evaluate(element=>{
        const style=getComputedStyle(element);
        return element.getBoundingClientRect().height-parseFloat(style.paddingTop)-parseFloat(style.paddingBottom)<=parseFloat(style.lineHeight)+1;
      }),'Short character headings keep whole words on mobile');
      await table.focus();await page.keyboard.press('ArrowRight');
      await expect.poll(()=>table.evaluate(element=>element.scrollLeft)).toBeGreaterThan(0);
      await table.evaluate(element=>{element.scrollLeft=0;});
    }
    await page.locator('#characters').screenshot({path:path.join(artifacts,`characters-${width}.png`)});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await page.locator('[data-view=research]').click();
    await expect(page.locator('[data-rtab=dossiers]')).toHaveAttribute('aria-selected','true');
    await expect(page.locator('#rtab-dossiers')).toBeVisible();
    await page.locator('[data-rtab=dossiers]').focus();await page.keyboard.press('ArrowRight');
    await expect(page.locator('[data-rtab=claims]')).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('#rtab-claims')).toBeVisible();
    await page.locator('[data-rtab=sources]').click();
    await expect(page.locator('#r-ingest-text')).not.toBeVisible();
    await expect(page.locator('#r-zotero-browse')).not.toBeVisible();
    let zoteroReads=0;
    await page.route('**/api/research-zotero',route=>{zoteroReads++;return route.fulfill({json:{ok:false,message:'Synthetic Zotero unavailable'}});});
    await page.locator('#zotero-box > summary').focus();await page.keyboard.press('Enter');
    await expect(page.locator('#r-zotero-browse')).toBeVisible();
    if(width===320)assert.ok((await page.locator('#r-zotero-query').boundingBox()).width>=200,
      'Mobile capture search must leave enough room to enter a query');
    assert.equal(zoteroReads,0,'Opening the capture selector never browses or retains automatically');
    await page.locator('#r-zotero-query').fill('Unsaved synthetic capture search');
    await page.locator('#r-zotero-retention').check();
    await page.locator('#zotero-box > summary').click();
    await page.locator('#zotero-box > summary').click();
    await expect(page.locator('#r-zotero-query')).toHaveValue('Unsaved synthetic capture search');
    await expect(page.locator('#r-zotero-retention')).toBeChecked();
    await page.locator('#r-zotero-browse').click();
    await expect(page.locator('#r-zotero-results')).toContainText('Synthetic Zotero unavailable');
    await page.locator('#r-local-import > summary').focus();await page.keyboard.press('Space');
    await page.locator('#r-ingest-text').fill('An unsaved synthetic local capture.');
    await page.locator('#r-local-import > summary').click();
    await page.locator('[data-rtab=dossiers]').click();
    await page.locator('[data-rtab=sources]').click();
    await page.locator('#r-local-import > summary').click();
    await expect(page.locator('#r-ingest-text')).toHaveValue('An unsaved synthetic local capture.');
    await expect(page.locator('#r-zotero-results')).toContainText('Synthetic Zotero unavailable');
    assert.equal(zoteroReads,1,'Tab and disclosure changes preserve the result without a repeat browse');
    await page.unroute('**/api/research-zotero');
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
    await page.locator('[data-view=research]').focus();await page.keyboard.press(width >= 1100 ? 'ArrowUp' : 'ArrowLeft');
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
    releases.forEach(release=>release());
    try{if(browser)await browser.close();}finally{await server.close();}
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
