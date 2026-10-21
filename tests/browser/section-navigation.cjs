// Shared document sections retain semantic destinations and independent scroll roots.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-section-navigation-'));
const fixtures = pythonFixture(`
import json
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
from dashboard_fixtures import full_dashboard as render
original = render.__globals__['render_dashboard']
fixtures = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    def localized(*args, **kwargs):
        return original(*args, **{**kwargs, 'labels': labels, 'language_key': locale,
          'enabled_actions': ['analyze', 'manuscript-pdf', 'research-reader'],
          'manuscript_pdf_token': 'synthetic-manuscript', 'research_context_token': 'synthetic-root'})
    render.__globals__['render_dashboard'] = localized
    fixtures[locale] = render()
render.__globals__['render_dashboard'] = lambda *args, **kwargs: original(*args, **{**kwargs, 'controls': False})
fixtures['report'] = render()
print(json.dumps(fixtures))
`, {root});
const dossier = {id: 'synthetic-dossier', project_id: 'synthetic-project', snapshot: 'synthetic-snapshot', revision: 2,
  title: 'Synthetic dossier', body: '# Repeated <img src=x>\n\n' + 'Synthetic notes. '.repeat(120) +
    '\n\n## A deliberately long detail heading that wraps within the existing companion width\n\n' + 'Independent notes. '.repeat(100) + '\n\n# Repeated <img src=x>\n\nFinal synthetic notes.',
  sections: ['Not a rendered heading'], citations: [], tags: [], editable_sections: []};
async function settle(page) { await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))); }
async function indicatorAtCurrent(nav, horizontal=false) {
 await expect.poll(()=>nav.evaluate((node,horizontal)=>{
  const link=node.querySelector('[aria-current=true]'), dot=node.querySelector('[data-section-indicator]');
  if(!link||!dot)return Infinity;
  const a=link.getBoundingClientRect(), b=dot.getBoundingClientRect();
  return Math.max(Math.abs(b.x+b.width/2-(horizontal?a.x+a.width/2:a.x-9)),
    Math.abs(b.y+b.height/2-(horizontal?a.bottom-2:a.y+a.height/2)));
 },horizontal)).toBeLessThan(1);
}
async function mappedLifecycle(page, detail) {
 await page.locator('#tab-view-research').click();
 const fullNav=page.locator('#synthetic-full-dossier [data-section-nav]');
 const fullContents=page.locator('#synthetic-full-dossier [data-section-contents]');
 if(await fullContents.getAttribute('open')===null) await fullContents.locator('summary').click();
 await indicatorAtCurrent(fullNav);
 for(const width of [320,1440]) {
  await page.setViewportSize({width,height:900});
  const bounds=()=>fullNav.evaluate(node=>({page:document.documentElement.scrollWidth,viewport:innerWidth,
   nav:node.clientWidth,content:node.scrollWidth,track:node.querySelector('[data-section-track]').getBoundingClientRect().width}));
  for(const phase of ['immediate','settled']) {
   const size=await bounds();
   assert.ok(size.page<=size.viewport,`${phase} resized contents must not widen the page: ${JSON.stringify(size)}`);
   assert.ok(size.content<=size.nav+1&&size.track<=size.nav+1,
    `${phase} decorative track must fit the resized native contents: ${JSON.stringify(size)}`);
   await indicatorAtCurrent(fullNav);
  }
 }
 await page.evaluate(detail=>{
  const host=document.getElementById('synthetic-full-dossier');
  window.syntheticOldNav=host.querySelector('[data-section-nav]');
  const mapped={...detail,section_map:{'First <script>': '# Repeated\n\n'+ 'Map notes. '.repeat(200),
    'Second': '# Repeated\n\nMore notes.'}};
  host.innerHTML=researchDossierDetailHtml(mapped);enhanceResearchDossierClaims(host,mapped);
 },detail);
 const host=page.locator('#synthetic-full-dossier'), nav=host.locator('[data-section-nav]');
 await expect.poll(()=>page.evaluate(()=>!!window.syntheticOldNav._sectionNavigation)).toBe(false);
 await expect(nav.locator('[data-section-indicator]')).toHaveCount(1);
 const block=host.locator('.research-dossier-section-block').first();
 const summaryId=await block.locator('summary').getAttribute('id');
 await block.locator('summary').click();
 await expect(block).not.toHaveAttribute('open','');
 await nav.locator(`[data-section-link="${summaryId}"]`).click();
 await expect(block).toHaveAttribute('open','');
 await indicatorAtCurrent(nav);
 await page.emulateMedia({reducedMotion:'no-preference'});
 // Manual root scrolling exercises current-state changes without a second navigation owner.
 await host.locator('.research-folder-citations').evaluate(node=>node.scrollIntoView());
 await expect(nav.locator('[aria-current=true]')).toHaveAttribute('data-section-link',await host.locator('.research-folder-citations').getAttribute('id'));
 await page.evaluate(()=>document.dispatchEvent(new Event('scroll')));
 await settle(page);
 await expect.poll(()=>nav.locator('[data-section-indicator]').evaluate(node=>getComputedStyle(node).transitionDuration)).toBe('0.2s');
 await page.emulateMedia({reducedMotion:'reduce'});
 await expect.poll(()=>nav.locator('[data-section-indicator]').evaluate(node=>getComputedStyle(node).transitionDuration)).toBe('0s');
 await indicatorAtCurrent(nav);
 await page.addStyleTag({content:'.research-dossier-contents a {line-height:1.8;letter-spacing:.12em;word-spacing:.16em;}'});
 await page.setViewportSize({width:1024,height:900});
 await indicatorAtCurrent(nav);
 const heading=host.locator('.research-dossier-body-rendered h1').first();
 const headingId=await heading.getAttribute('id');
 await host.locator('[data-source-toggle]').click();
 await expect(heading).not.toBeVisible();
 await nav.locator(`[data-section-link="${headingId}"]`).click();
 await expect(heading).toBeVisible();
 // Decoration can disappear without deleting the native links or their targets.
 await nav.evaluate(node=>node._sectionNavigation.dispose());
 await expect(nav.locator('[data-section-indicator]')).toHaveCount(0);
 await expect(host.locator('[data-section-current]')).toBeEmpty();
 const notes=host.locator('.research-folder-notes'), notesId=await notes.getAttribute('id');
 await nav.locator(`[data-section-link="${notesId}"]`).click();
 await expect(notes).toBeInViewport();
}
(async () => {
 const browser = await launchChromium();
 try {
  const cases = process.env.SECTION_NAV_SMOKE==='touch' ? [['en',320,480,'no-preference',true]] :
    process.env.SECTION_NAV_SMOKE ? [[ 'en', process.env.SECTION_NAV_SMOKE==='mobile'?320:1440, process.env.SECTION_NAV_SMOKE==='mobile'?480:950, 'reduce']] :
    Object.keys(fixtures).filter(locale=>locale!=='report').flatMap(locale => [[1440,950],[1024,900],[390,900],[320,480]].map(([w,h]) => [locale,w,h,'reduce']))
      .concat([['en',1440,950,'no-preference'],['en',320,480,'no-preference',true]]);
  for (const [locale,width,height,motion,touch=false] of cases) {
   const page = await browser.newPage({viewport:{width,height},reducedMotion:motion,hasTouch:touch});
   const errors=[], writes=[];
   let releaseClaims;
   const claimsGate=new Promise(resolve=>{releaseClaims=resolve;});
   page.on('pageerror',error=>errors.push(error.message));
   await page.route('http://lixity.test/**',async route=>{
    const url=new URL(route.request().url());
    if(route.request().method()!=='GET') writes.push(url.pathname);
    if(url.pathname==='/api/research/status') return route.fulfill({json:{ok:true,initialized:true,project_id:dossier.project_id,project_root:'synthetic-project',dossiers:[dossier],claims:[],sources:[],decisions:[]}});
    if(url.pathname==='/api/research/dossiers') return route.fulfill({json:url.searchParams.has('id')?{ok:true,...dossier}:{ok:true,project_id:dossier.project_id,dossiers:[dossier]}});
    if(url.pathname==='/api/research/claims' && url.searchParams.has('dossier_id')) await claimsGate;
    if(url.pathname.startsWith('/api/')) return route.fulfill({json:{ok:true,project_id:dossier.project_id,snapshot:dossier.snapshot,claims:[],links:[],records:[],sources:[],decisions:[]}});
    return route.fulfill({contentType:'text/html',body:fixtures[locale]});
   });
   await page.goto('http://lixity.test/');
   await page.evaluate(dark=>document.documentElement.dataset.theme=dark?'dark':'light',width===1024||motion==='no-preference');
   await page.locator('#workbench-overview-open').click();
   const analysis=page.locator('#analysis-sections');
   await expect(analysis.locator('[data-section-indicator]')).toHaveCount(1);
   await analysis.locator('[data-section-link=matrix]').click();

   await expect(analysis.locator('[aria-current=true]')).toHaveAttribute('data-section-link','matrix');
   await expect(analysis.locator('[data-section-indicator]')).toBeVisible();
   await page.locator('#workbench-overview-back').click();
   await page.locator('#workspace-reader-toggle').click();
   await expect(page.locator('#workspace-reader-dossier')).toBeEnabled();
   await page.locator('#workspace-reader-dossier').selectOption(dossier.id);
   const folder=page.locator('#workspace-reader-body .research-dossier-folder');
   const nav=folder.locator('[data-section-nav]');
   await expect(nav).toHaveCount(1);
   const disclosure=folder.locator('[data-section-contents]');
   if(width<=900) { await expect(disclosure).not.toHaveAttribute('open',''); await disclosure.locator('summary')[touch?'tap':'click'](); }
   const targets=await nav.locator('[data-section-link]').evaluateAll(links=>links.map(link=>{
    const target=document.getElementById(link.dataset.sectionLink);
    return {id:target?.id,text:link.textContent,tag:target?.tagName,within:!!target&&link.closest('.research-dossier-folder').contains(target)};
   }));
   assert.equal(targets.length,6,'Notes, three real body headings, Claims and Citations only');
   assert.equal(targets.every(target=>target.within),true);
   assert.equal(new Set(targets.map(target=>target.id)).size,6,'Repeated heading names keep separate destinations');
   assert.equal(targets.some(target=>target.text==='Not a rendered heading'),false);
   assert.equal(await folder.locator('img').count(),0);
   assert.deepEqual(await nav.locator('[data-section-link]').evaluateAll(nodes=>nodes.map(node=>{let depth=0;for(let p=node.parentElement;p&&!p.matches('nav');p=p.parentElement)if(p.tagName==='UL')depth++;return depth;})),[1,2,3,2,1,1], 'Actual heading levels nest beneath Notes');
   const claimsId=targets[4].id;
   await expect(folder.locator('.research-dossier-claims')).toHaveAttribute('aria-busy','true');
   releaseClaims();
   await expect(folder.locator('.research-dossier-claims')).toHaveAttribute('id',claimsId);
   await expect(folder.locator('.research-dossier-claims')).not.toHaveAttribute('aria-busy','true');
   await expect(nav.locator('[data-section-indicator]')).toHaveCount(1);
   await nav.locator('[data-section-link]').first().click();
   await nav.locator('[data-section-link]').first().scrollIntoViewIfNeeded();
   await settle(page);
   await page.screenshot({path:path.join(artifacts,`contents-${locale}-${width}-${motion}.png`)});
   await nav.locator('[data-section-link]').last()[touch?'tap':'click']();

   await expect(nav.locator('[aria-current=true]')).toHaveAttribute('data-section-link',targets[5].id);
   await indicatorAtCurrent(nav);
   const location=folder.locator('[data-section-location]');

   await expect(location).toBeInViewport();
   await expect(location).toContainText(targets[5].text);
   await settle(page);
   await expect.poll(()=>location.evaluate(node=>node.getBoundingClientRect().y-Math.max(0,node.closest('.workspace-context-panel').getBoundingClientRect().y))).toBeGreaterThanOrEqual(-1);
   const orientation=await location.evaluate(node=>{
    const bar=node.getBoundingClientRect(), root=node.closest('.workspace-context-panel');
    const target=document.getElementById(node.parentElement.querySelector('[aria-current=true]').dataset.sectionLink).getBoundingClientRect();
    return {bar:bar.toJSON(),target:target.toJSON(),root:root.getBoundingClientRect().toJSON()};
   });
   assert.ok(orientation.bar.height>=44 && orientation.bar.height<=45);
   assert.ok(orientation.bar.y>=Math.max(0,orientation.root.y)-1);
   assert.ok(orientation.target.y>=orientation.bar.bottom-1,'Destination clears persistent orientation');
   await page.screenshot({path:path.join(artifacts,`location-${locale}-${width}-${motion}.png`)});
   const scrollHeight=await folder.evaluate(node=>node.closest('.workspace-context-panel').scrollHeight);
   await folder.locator('.research-folder-notes').evaluate(node=>node.scrollIntoView());
   await expect(location).not.toContainText(targets[5].text);
   await expect(location).toContainText(await nav.locator('[aria-current=true]').textContent());
   assert.equal(await folder.evaluate(node=>node.closest('.workspace-context-panel').scrollHeight),scrollHeight,'Current-label change never changes scroll geometry');
   await location[touch?'tap':'click']();
   await expect(disclosure.locator('summary')).toBeInViewport();
   await disclosure.locator('summary')[touch?'tap':'click']();
   await expect(disclosure).not.toHaveAttribute('open','');
   await folder.locator('.research-folder-citations').evaluate(node=>node.scrollIntoView());
   await location[touch?'tap':'click']();
   await expect(disclosure).toHaveAttribute('open','');
   await expect(disclosure.locator('summary')).toBeInViewport();
   if(locale==='en' && width===1440 && motion==='reduce') {
    const dock=page.locator('#workspace-context-panel');
    await dock.evaluate(node=>{node.scrollTop=1000;});
    await settle(page);
    const middle=await dock.evaluate(node=>node.scrollTop);
    await page.setViewportSize({width,height:height-50});
    await settle(page);
    assert.equal(await dock.evaluate(node=>node.scrollTop),middle,'Dock shrink preserves a non-end reading offset');
    await page.setViewportSize({width,height});
    await location.click();
   }
   const ids=targets.map(target=>target.id);
   const accepted = await folder.evaluate(node=>{window.syntheticAcceptedFolder=node; return Array.from(node.querySelectorAll(":scope > section")).map(section=>section.textContent);});
   // Another accepted rendering of the same record cannot steal these anchors.
   await page.evaluate(detail=>{
    const host=document.createElement('div');host.id='synthetic-full-dossier';
    document.getElementById('view-pane-research').appendChild(host);
    host.innerHTML=researchDossierDetailHtml(detail);
    enhanceResearchDossierClaims(host,detail);
   },dossier);
   assert.equal(await page.locator('[data-section-target]').evaluateAll(nodes=>new Set(nodes.map(n=>n.id)).size===nodes.length),true);
   await page.locator('#tab-view-research').click();
   const full=page.locator('#synthetic-full-dossier');
   const fullDisclosure=full.locator('[data-section-contents]');
   if(width<=900) await fullDisclosure.locator('summary').click();
   await full.locator('[data-section-link]').last().click();
   await expect(full.locator('[aria-current=true]')).toHaveAttribute('data-section-link',await full.locator('.research-folder-citations').getAttribute('id'));
   await expect(full.locator('[data-section-location]')).toBeInViewport();
   const fullArrival=await full.evaluate(host=>({bar:host.querySelector('[data-section-location]').getBoundingClientRect().toJSON(),
     target:host.querySelector('.research-folder-citations').getBoundingClientRect().toJSON()}));
   assert.ok(fullArrival.bar.y>=0 && fullArrival.target.y>=fullArrival.bar.bottom-1,'Window-root arrival clears exactly one compact bar');

   if(locale==='en' && width===1440 && motion==='reduce') {
    await fullDisclosure.locator('summary').click();
    await page.addStyleTag({content:'html {overflow-anchor:none;}'});
    await full.locator('.research-folder-citations').evaluate(node=>node.scrollIntoView());
    await expect(full.locator('[data-section-location]')).toContainText(targets[5].text);
    // A media-sized layout change has no child/class mutation or scroll event.
    await full.locator('.research-folder-notes').evaluate(node=>{node.style.paddingBottom='1000px';});
    await expect(full.locator('[data-section-location]')).not.toContainText(targets[5].text);
    await full.locator('.research-folder-notes').evaluate(node=>node.style.removeProperty('padding-bottom'));
   }
   await page.locator('#tab-view-analysis').click();
   assert.deepEqual(await nav.locator('[data-section-link]').evaluateAll(nodes=>nodes.map(n=>n.dataset.sectionLink)),ids,'View return preserves accepted targets');
   assert.equal(await folder.evaluate(node=>node===window.syntheticAcceptedFolder),true);
   assert.deepEqual(await folder.locator(":scope > section").allTextContents(),accepted);
   if(locale==='en' && width===1440 && motion==='reduce') await mappedLifecycle(page, dossier);
   await settle(page);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
   await page.screenshot({path:path.join(artifacts,`sections-${locale}-${width}-${motion}.png`)});
   await page.close();
  }
  const noScript = await browser.newPage({javaScriptEnabled:false,viewport:{width:1440,height:950}});
  await noScript.route('http://lixity.test/**',route=>route.fulfill({contentType:'text/html',body:fixtures.report}));
  await noScript.goto('http://lixity.test/');
  const nativeLink=noScript.locator('#analysis-sections [data-section-link]').last();
  const nativeTarget=await nativeLink.getAttribute('href');
  await nativeLink.click();
  assert.equal(new URL(noScript.url()).hash,nativeTarget);
  await expect(noScript.locator(nativeTarget)).toBeInViewport();
  await expect(noScript.locator('[data-section-indicator]')).toHaveCount(0);
  await noScript.close();
  console.log('PASS shared section navigation; artifacts '+artifacts);
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
