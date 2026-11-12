const {launchChromium, launchFirefox} = require('../../scripts/browser_tools.cjs');
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const captures = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-toolbar-'));
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
function dashboard(language) {
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root,'.venv/bin/python'), ['-c',
 'from dashboard_fixtures import full_dashboard; from lixity.server.constants import NATIVE_UI_ACTIONS; print(full_dashboard(NATIVE_UI_ACTIONS, language_key="' + language + '"))'],
 {cwd:root,env:{...process.env,PYTHONPATH:'src:tests'},encoding:'utf8',maxBuffer:8*1024*1024});
assert.equal(fixture.status,0,fixture.stderr);
return fixture.stdout;
}
(async()=>{
 const browser=await (process.argv.includes('--firefox') ? launchFirefox : launchChromium)();
 try {
  let html;
  const page=await browser.newPage({colorScheme:'dark'});
  await page.route('http://lixity.test/**',r=>r.fulfill(r.request().url().endsWith('/manuscript-editor.js') ? {contentType:'application/javascript',body:fs.readFileSync(path.join(root,'src/lixity/ui/assets/manuscript-editor.js'),'utf8')} : r.request().url().includes('/api/') ? {json:{ok:true,records:[]}} : {contentType:'text/html',body:html}));
  for(const language of ['de','en','fr','es','it','pt','nl']) {
  html=dashboard(language);
  for(const theme of ['light','dark']) {
  await page.emulateMedia({colorScheme:theme});
  // Geometry is theme-independent; retain both themes at every sampled width.
  // DE/EN cover all breakpoints; other locales cover wide, compact and mobile.
  const widths = process.argv.includes('--exhaustive') || ['de','en'].includes(language)
    ? [1837,1536,1468,1440,1280,1024,768,390,320] : [1468,1024,320];
  for(const width of widths) {
   await page.setViewportSize({width,height:900});await page.goto('http://lixity.test');
   await page.addScriptTag({url:'http://lixity.test/api/manuscript-editor.js'});
   assert(await page.locator('#manuscript-write').isVisible());
   const toolbar=page.locator('#manuscript-reader-controls');
   if(width>=1024) assert((await toolbar.boundingBox()).height<=64,`All native tools including Write fit one desktop row at ${width}px (${language}, ${theme})`);
   const chapterSelect=page.locator('#reader-chapter');
   if(await chapterSelect.isVisible() && width>=768) {
    const isTruncated=await chapterSelect.evaluate(el=>el.scrollWidth>el.clientWidth);
    assert.equal(isTruncated,false,`Chapter select in ${language} at ${width}px must not be truncated`);
   }
   assert(await page.locator('#reader-speech').isVisible());
   assert(await page.locator('#workspace-reader-toggle').isVisible());
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   if(language==='de' && theme==='dark' && [1468,1024,390].includes(width)) await page.screenshot({path:path.join(captures, `${width}.png`)});
   await page.locator('#reader-settings > summary').click();
   assert(await page.locator('#reader-width').isVisible());
   await page.keyboard.press('Escape');
   assert.equal(await page.locator('#reader-settings').evaluate(el=>el.open),false,'Escape closes appearance settings');
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
  }
  }
  console.log('Seven-language native toolbar, light/dark: one desktop row, bounded focus selector, mobile actions and Escape passed.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
