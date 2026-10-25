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
from lixity.models import CorpusConfig
from lixity.scenes import scene_report_for_display
from dashboard_fixtures import full_dashboard as render
original = render.__globals__['render_dashboard']
fixtures = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    def localized(*args, **kwargs):
        return original(*args, **{**kwargs, 'labels': labels, 'language_key': locale,
          'enabled_actions': ['analyze', 'manuscript-pdf', 'research-reader'],
          'scenes': scene_report_for_display(render.__globals__['SAMPLE'], CorpusConfig(language='de'), None),
          'manuscript_pdf_token': 'synthetic-manuscript', 'research_context_token': 'synthetic-root'})
    render.__globals__['render_dashboard'] = localized
    fixtures[locale] = render()
original_sample = render.__globals__['SAMPLE']
render.__globals__['SAMPLE'] += '\\n\\n## Reading continuity\\n\\n' + '\\n\\n'.join(
    'Synthetic paragraph %d. ' % number + 'A quiet garden gives this scene a place to continue. ' * 6
    for number in range(40))
continuity_labels = {**get_language_profile('en').labels, **WORKSPACE_LABELS['en']}
render.__globals__['render_dashboard'] = lambda *args, **kwargs: original(*args, **{**kwargs,
    'labels': continuity_labels, 'language_key': 'en', 'enabled_actions': ['analyze', 'research-reader'],
    'manuscript_pdf_token': 'synthetic-manuscript', 'research_context_token': 'synthetic-root'})
fixtures['continuity'] = render()
render.__globals__['SAMPLE'] = original_sample
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
async function wideOutline(page, host) {
 const contents=host.locator('[data-section-contents]'), notes=host.locator('.research-folder-notes');
 await notes.evaluate(node=>node.scrollIntoView());
 await settle(page);
 // The source document now starts before the supplemental actions. Cross the
 // sticky threshold before measuring a pinned navigation position.
 await page.evaluate(()=>scrollBy(0,80));
 await settle(page);
 const before=await host.evaluate(node=>({
  contents:node.querySelector('[data-section-contents]').getBoundingClientRect().toJSON(),
  document:node.querySelector('.research-folder-notes').getBoundingClientRect().toJSON(),
  scroll:scrollY,viewport:innerHeight
 }));
 assert.ok(before.contents.x>=before.document.right+8,
  `The full heading tree must sit to the RIGHT of the reading document: ${JSON.stringify(before)}`);
 assert.ok(before.document.width>=384,'The outline leaves readable center-column width');
 assert.ok(before.contents.y>=0 && before.contents.bottom<=before.viewport,
  'The complete navigation viewport fits vertically beside the document');
 await page.evaluate(()=>scrollBy(0,300));
 await settle(page);
 const after=await host.evaluate(node=>({
  contents:node.querySelector('[data-section-contents]').getBoundingClientRect().toJSON(),
  document:node.querySelector('.research-folder-notes').getBoundingClientRect().toJSON(),scroll:scrollY
 }));
 assert.ok(after.scroll-before.scroll>=299,'The middle document actually scrolls');
 assert.ok(Math.abs(after.contents.y-before.contents.y)<2,
  `The right tree stays sticky while the middle document scrolls: ${JSON.stringify({before,after})}`);
 assert.ok(before.document.y-after.document.y>=299,'The document moves independently of its right tree');
 await page.screenshot({path:path.join(artifacts,`right-outline-${await page.locator('html').getAttribute('lang')}-${await page.evaluate(()=>innerWidth)}.png`)});
 await expect(host.locator('[data-section-location]')).not.toBeVisible();
 await contents.locator('summary').click();
 await expect(contents).not.toHaveAttribute('open','');
 await contents.locator('summary').click();
 await expect(contents).toHaveAttribute('open','');
 await indicatorAtCurrent(contents.locator('[data-section-nav]'));
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
  const mapped={...detail,body:'## First <script>\n\n# Repeated\n\n' + 'Map notes. '.repeat(200) +
    '\n\n## Second\n\n# Repeated\n\nMore notes.',
    section_map:{'Not a reading source':'Ignored lookup projection'}};
  host.innerHTML=researchDossierDetailHtml(mapped);enhanceResearchDossierClaims(host,mapped);
 },detail);
 const host=page.locator('#synthetic-full-dossier'), nav=host.locator('[data-section-nav]');
 await expect.poll(()=>page.evaluate(()=>!!window.syntheticOldNav._sectionNavigation)).toBe(false);
 await expect(nav.locator('[data-section-indicator]')).toHaveCount(1);
 const section=host.locator('.research-dossier-body-rendered h2').first();
 const sectionId=await section.getAttribute('id');
 await nav.locator(`[data-section-link="${sectionId}"]`).click();
 await expect(section).toBeInViewport();
 await indicatorAtCurrent(nav);
 await expect(section).toHaveClass(/\bflash\b/);
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
async function longOutline(page, detail) {
 await page.setViewportSize({width:1440,height:950});
 await page.locator('#tab-view-research').click();
 await page.evaluate(detail=>{
  const body=Array.from({length:90},(_,n)=>`## ${n}. Wrapped heading <img src=x> with a deliberate repeated name\n\n`+
   `Synthetic paragraph ${n}. `+'Independent reading notes. '.repeat(24)).join('\n\n');
  const host=document.getElementById('synthetic-full-dossier');
  const long={...detail,body};host.innerHTML=researchDossierDetailHtml(long);enhanceResearchDossierClaims(host,long);
 },detail);
 const host=page.locator('#synthetic-full-dossier'), contents=host.locator('[data-section-contents]'), nav=contents.locator('nav');
 await expect(nav.locator('[data-section-link]')).toHaveCount(93);
 await expect(host.locator('.research-dossier-claims')).not.toHaveAttribute('aria-busy','true');
 const requestedScroll=await host.locator('.research-folder-citations').evaluate(node=>{node.scrollIntoView();return scrollY;});
 await expect(nav.locator('[aria-current=true]')).toHaveAttribute('data-section-link',await host.locator('.research-folder-citations').getAttribute('id'));
 const activeBounds=()=>contents.evaluate(node=>{
  const viewport=node.querySelector('nav').getBoundingClientRect(), active=node.querySelector('[aria-current=true]').getBoundingClientRect();
  return {visible:active.top>=viewport.top && active.bottom<=viewport.bottom,
   viewport:viewport.toJSON(),active:active.toJSON(),scroll:node.querySelector('nav').scrollTop,
   height:node.querySelector('nav').scrollHeight,available:node.style.getPropertyValue('--outline-available-height'),
   position:getComputedStyle(node).position};
 });
 await expect.poll(activeBounds,{message:'Passive document scrolling keeps the current heading visible inside the bounded right tree'})
  .toMatchObject({visible:true}).catch(async error=>{console.error('Long outline bounds: '+JSON.stringify(await activeBounds()));throw error;});
 assert.equal(await page.evaluate(()=>scrollY),requestedScroll,'Revealing the active outline row never scrolls the reading document');
 await indicatorAtCurrent(nav);
 const orientation=await contents.evaluate(node=>({outline:node.getBoundingClientRect().toJSON(),
  summary:node.querySelector('summary').getBoundingClientRect().toJSON(),scroll:node.scrollTop,
  position:getComputedStyle(node.querySelector('summary')).position,viewport:innerHeight}));
 assert.ok(orientation.summary.y>=0&&orientation.summary.bottom<=orientation.viewport&&
  orientation.summary.y>=orientation.outline.y&&orientation.summary.bottom<=orientation.outline.bottom,
  `Native Sections close/reopen stays reachable above the bounded tree: ${JSON.stringify(orientation)}`);
 await expect.poll(()=>nav.evaluate(node=>node.scrollHeight>node.clientHeight&&node.clientHeight<=innerHeight)).toBe(true);
 await contents.locator('summary').click();
 await expect(contents).not.toHaveAttribute('open','');
 await contents.locator('summary').click();
 await expect(contents).toHaveAttribute('open','');
 const last=nav.locator('[data-section-link]').last();
 await last.focus();await page.keyboard.press('Enter');
 await expect(nav.locator('[aria-current=true]')).toHaveAttribute('data-section-link',await host.locator('.research-folder-citations').getAttribute('id'));
 await page.screenshot({path:path.join(artifacts,'right-outline-long-1440.png')});
 assert.equal(await host.locator('img').count(),0,'Authored heading markup stays inert');
 await host.locator('.research-dossier-body-rendered p').first().evaluate(node=>{
  window.retainedDossierProse=node;window.retainedDossierText=node.textContent;
  const text=node.firstChild;getSelection().setBaseAndExtent(text,12,text,2);
  window.retainedDossierSelection={anchor:text,anchorOffset:12,focus:text,focusOffset:2,quote:getSelection().toString()};
 });
 for(const width of [1024,390,320,1440]) {
  await page.setViewportSize({width,height:900});
  for(const phase of ['immediate','settled']) {
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${phase} long contents fit at ${width}`);
   await settle(page);
  }
  assert.equal(await host.evaluate(node=>node.querySelector('.research-dossier-body-rendered p')===window.retainedDossierProse&&
   window.retainedDossierProse.textContent===window.retainedDossierText),true,'Responsive placement preserves the accepted prose node');
  assert.equal(await page.evaluate(()=>{const s=getSelection(), saved=window.retainedDossierSelection;
   return s.anchorNode===saved.anchor&&s.anchorOffset===saved.anchorOffset&&s.focusNode===saved.focus&&
    s.focusOffset===saved.focusOffset&&s.toString()===saved.quote;}),true,'Responsive placement preserves backward native selection');
  if(width<1024) {
   await expect(host.locator('[data-section-location]')).toBeVisible();
   assert.equal(await contents.evaluate(node=>getComputedStyle(node).position),'static','Narrow outlines keep native compact flow');
  }
 }
 await page.evaluate(()=>document.documentElement.style.fontSize='200%');
 await settle(page);
 await expect(host.locator('[data-section-location]')).toBeVisible();
 assert.equal(await contents.evaluate(node=>getComputedStyle(node).position),'static','200% text zoom falls back before the document becomes cramped');
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'200% text zoom retains page bounds');
 await page.screenshot({path:path.join(artifacts,'right-outline-text-zoom-200.png')});
 await page.evaluate(()=>document.documentElement.style.removeProperty('font-size'));
}
async function companionOverviewReturn(browser, motion) {
 const page=await browser.newPage({viewport:{width:320,height:900},reducedMotion:motion});
 const detail={...dossier,body:'## Garden\n\nA saved synthetic note.',sections:['Garden']};
 const errors=[], writes=[];
 let hold=false, notifyHeld, release;
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('http://lixity.test/**',route=>{
  const url=new URL(route.request().url());
  if(route.request().method()!=='GET') writes.push(url.pathname);
  if(url.pathname==='/api/research/dossiers') {
   const json=url.searchParams.has('id')?{ok:true,...detail}:{ok:true,project_id:detail.project_id,dossiers:[detail]};
   if(hold&&url.searchParams.has('id')) {
    hold=false;
    return new Promise(resolve=>{release=()=>route.fulfill({json}).then(resolve);notifyHeld();});
   }
   return route.fulfill({json});
  }
  if(url.pathname.startsWith('/api/')) return route.fulfill({json:{ok:true,initialized:true,
   project_id:detail.project_id,snapshot:detail.snapshot,records:[],sources:[],dossiers:[detail],
   claims:[],decisions:[],candidates:[],links:[]}});
  return route.fulfill({contentType:'text/html',body:fixtures.continuity});
 });
 await page.goto('http://lixity.test/');
 await page.locator('#tab-view-analysis').click();
 await page.locator('#manuscript-analysis-toggle').click();
 await page.locator('#workspace-reader-toggle').click();
 await expect(page.locator('#workspace-reader-dossier')).toBeEnabled();
 await page.locator('#workspace-reader-dossier').selectOption(detail.id);
 await page.locator('#workspace-reader-body h3').waitFor();
 for(const action of ['back','off']) {
  await page.locator('#chapters .ptext').nth(25).scrollIntoViewIfNeeded();
  await settle(page);
  const origin=await page.evaluate(()=>{
   const anchor=LixityReader.capture();window.returnedSectionPanel=anchor.panel;
   return {id:anchor.panel.id,top:anchor.top,text:anchor.panel.textContent};
  });
  await page.locator('#workbench-overview-open').click();
  await page.locator('#analysis-sections [data-section-link]').last().click();
  const held=new Promise(resolve=>{notifyHeld=resolve;hold=true;});
  await page.locator(action==='back'?'#workbench-overview-back':'#manuscript-analysis-toggle').click();
  await held;
  await settle(page);
  const top=()=>page.locator('#'+origin.id).evaluate(node=>node.getBoundingClientRect().top);
  assert.ok(Math.abs(await top()-origin.top)<=2,'Overview return restores the passage while the resumed dossier response is held');
  const pendingHeight=await page.locator('#workspace-context-panel').evaluate(node=>node.getBoundingClientRect().height);
  await release();
  await page.locator('#workspace-reader-body h3').waitFor();
  await expect(page.locator('#workspace-reader-panel')).toHaveAttribute('aria-busy','false');
  await settle(page);
  assert.ok(await page.locator('#workspace-context-panel').evaluate(node=>node.getBoundingClientRect().height)>pendingHeight,
   'The released dossier actually grows the compact dock above the manuscript');
  const returnedTop=await top();
  assert.ok(Math.abs(returnedTop-origin.top)<=2,
   `${motion}/${action}: the resumed compact dossier must preserve the original passage after its asynchronous height change (${origin.top} → ${returnedTop})`);
  assert.equal(await page.locator('#'+origin.id).evaluate((node,text)=>node===window.returnedSectionPanel&&node.textContent===text,origin.text),true,
   'Companion outline presentation retains the exact manuscript node and content');
  assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'),String(action==='back'));
  await expect(page.locator('#workspace-reader-panel')).toBeVisible();
 }
 assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
 await page.close();
 console.log(`Compact dossier resumed-response returns passed with ${motion} motion`);
}
(async () => {
 const browser = await launchChromium();
 try {
  for(const motion of ['reduce','no-preference']) await companionOverviewReturn(browser,motion);
  const cases = process.env.SECTION_NAV_SMOKE==='touch' ? [['en',320,480,'no-preference',true]] :
    process.env.SECTION_NAV_SMOKE ? [[ 'en', process.env.SECTION_NAV_SMOKE==='mobile'?320:1440, process.env.SECTION_NAV_SMOKE==='mobile'?480:950, 'reduce']] :
    Object.keys(fixtures).filter(locale=>!['report','continuity'].includes(locale)).flatMap(locale => [[1440,950],[1024,900],[390,900],[320,480]].map(([w,h]) => [locale,w,h,'reduce']))
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
   await expect(analysis.locator('[data-section-link]')).toHaveCount(6);
   await expect(analysis.locator('[data-section-indicator]')).toHaveCount(0);
   await analysis.locator('[data-section-link=matrix]').click();

   await expect(analysis.locator('[aria-current=true]')).toHaveAttribute('data-section-link','matrix');
   await expect(analysis.locator('[aria-current=true]')).toHaveCSS('text-decoration-line','underline');
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
   const accepted = await folder.evaluate(node=>{window.syntheticAcceptedFolder=node; return Array.from(node.querySelectorAll(".research-dossier-document > section")).map(section=>section.textContent);});
   assert.ok(accepted.length>=3,'The accepted source snapshot includes Notes, Claims and Citations');
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
   if(width>=1024) await wideOutline(page,full);
   await full.locator('[data-section-link]').last().click();
   await expect(full.locator('[aria-current=true]')).toHaveAttribute('data-section-link',await full.locator('.research-folder-citations').getAttribute('id'));
   await indicatorAtCurrent(full.locator('[data-section-nav]'));
   if(width<1024) {
    await expect(full.locator('[data-section-location]')).toBeInViewport();
    const fullArrival=await full.evaluate(host=>({bar:host.querySelector('[data-section-location]').getBoundingClientRect().toJSON(),
      target:host.querySelector('.research-folder-citations').getBoundingClientRect().toJSON()}));
    assert.ok(fullArrival.bar.y>=0 && fullArrival.target.y>=fullArrival.bar.bottom-1,'Window-root arrival clears exactly one compact bar');
   }

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
   assert.deepEqual(await folder.locator(".research-dossier-document > section").allTextContents(),accepted);
   if(locale==='en' && width===1440 && motion==='reduce') {
    if(process.env.SECTION_NAV_SMOKE!=='outline') await mappedLifecycle(page, dossier);
    await longOutline(page,dossier);
   }
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
