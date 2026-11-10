const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root,'.venv/bin/python'), ['-c',
 'from dashboard_fixtures import full_dashboard; from lixity.server.constants import NATIVE_UI_ACTIONS; print(full_dashboard(NATIVE_UI_ACTIONS, language_key="de"))'],
 {cwd:root,env:{...process.env,PYTHONPATH:'src:tests'},encoding:'utf8',maxBuffer:8*1024*1024});
assert.equal(fixture.status,0,fixture.stderr);
(async()=>{
 const browser=await launchChromium();
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
  }
  console.log('German native toolbar: one desktop row, bounded focus selector, mobile actions and Escape passed.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
