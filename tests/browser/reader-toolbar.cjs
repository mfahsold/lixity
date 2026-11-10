const {launchChromium, launchFirefox} = require('../../scripts/browser_tools.cjs');
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root,'.venv/bin/python'), ['-c',
 'from dashboard_fixtures import full_dashboard; from lixity.server.constants import NATIVE_UI_ACTIONS; print(full_dashboard(NATIVE_UI_ACTIONS, language_key="de"))'],
 {cwd:root,env:{...process.env,PYTHONPATH:'src:tests'},encoding:'utf8',maxBuffer:8*1024*1024});
assert.equal(fixture.status,0,fixture.stderr);
(async()=>{
 const browser=await (process.argv.includes('--firefox') ? launchFirefox : launchChromium)();
 try {
  const page=await browser.newPage({colorScheme:'dark'});
  await page.route('http://lixity.test/**',r=>r.fulfill(r.request().url().includes('/api/') ? {json:{ok:true,records:[]}} : {contentType:'text/html',body:fixture.stdout}));
  for(const width of [1837,1468,1440,390,320]) {
   await page.setViewportSize({width,height:900});await page.goto('http://lixity.test');
   const toolbar=page.locator('#manuscript-reader-controls');
   if(width>=1440) assert((await toolbar.boundingBox()).height<=64,'All German native tools fit one desktop row');
   assert(await page.locator('#reader-speech').isVisible());
   assert(await page.locator('#workspace-reader-toggle').isVisible());
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   await page.locator('#reader-focus').click();
   if(width>=1440) assert((await page.locator('#reader-chapter').boundingBox()).width<=240);
   await page.keyboard.press('Escape');
   assert.equal(await page.locator('body').evaluate(el=>el.classList.contains('reader-focus')),false);
   await page.evaluate(()=>{
    const host=document.createElement('div');host.id='card-layout-fixture';document.body.append(host);
    window.LixityResearchCards.render(host,{items:[{id:'synthetic',title:'Synthetic dossier',reader:true,revision:'dossier'}]});
   });
   const actions=page.locator('#card-layout-fixture .research-card-actions');
   await actions.waitFor();
   const centers=await actions.locator('button').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return r.y+r.height/2;}));
   if(width>=1440) assert(Math.max(...centers)-Math.min(...centers)<1,'Dossier actions share a vertical center');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  console.log('German native toolbar: one desktop row, bounded focus selector, mobile actions and Escape passed.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
