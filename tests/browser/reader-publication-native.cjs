// Production curation, chapter omission and shared media work without a live API.
const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'), os=require('node:os'), http=require('node:http');
const {pathToFileURL}=require('node:url');
const {launchChromium,playwrightModule}=require('../../scripts/browser_tools.cjs');
const {expect}=require(path.join(playwrightModule,'test'));
const {pythonFixture}=require('./support/python-fixture.cjs');
const artifacts=fs.mkdtempSync(path.join(os.tmpdir(),'lixity-publication-native-'));
const fixture=pythonFixture(String.raw`
import hashlib,json
from pathlib import Path
from lixity.config import prepare_project_settings
from lixity.research import api
from lixity.site_export import prepare_site
from tests.test_site_publication_export import publication_project
from tests.test_research_geography import geography
base=Path(ARTIFACTS)
project,profiles,dossier,*_=publication_project.__wrapped__(base)
record=api.get_record(project,'dossier',dossier)
body=record['record']['body'].replace('APPROVED_PUBLIC_BODY','APPROVED_PUBLIC_BODY\n\n'+chr(96)*3+'mermaid\ngraph LR\n A[Gate] --> B[Arrival]\n'+chr(96)*3+'\n\n')
api.revise_record(project,'dossier',dossier,changes={'body':body,'geography':geography()},expected_revision=2,
    change_kind='correction',reason='Synthetic publication rendering fixture.')
entry=profiles['readers']['entries'][0]
entry.update(revision=3,include_citations=True,include_geography=True)
prepare_project_settings(project,{'site_publications':profiles}).commit()
def digest():return {str(p.relative_to(project)):hashlib.sha256(p.read_bytes()).hexdigest() for p in project.rglob('*') if p.is_file()}
before=digest()
for mode in ('reader','companion'):
 for cap in (1,3):
  bundle=prepare_site(project,mode=mode,publication_profile='readers',max_chapter=cap,include_source_files=True)
  for name,content in bundle.files.items():
   target=base/(mode+'-'+str(cap))/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
for name,sections in [('chapter-analysis',['chapters']),('language-analysis',['language']),('full-analysis',['full'])]:
 bundle=prepare_site(project,mode='reader',publication_profile='readers',max_chapter=1,analysis_sections=sections)
 for file,content in bundle.files.items():
  target=base/name/file;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
assert digest()==before
print(json.dumps({'project':str(project),'before':before}))
`.replace('ARTIFACTS',JSON.stringify(artifacts)));
(async()=>{
 const server=http.createServer((req,res)=>{
  const file=path.resolve(artifacts,'.'+new URL(req.url,'http://local').pathname.replace(/^\/nested/,''));
  if(!file.startsWith(artifacts+'/')||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',file.endsWith('.html')?'text/html':file.endsWith('.png')?'image/png':'application/octet-stream');res.end(fs.readFileSync(file));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin='http://127.0.0.1:'+server.address().port,browser=await launchChromium(),errors=[];
 try{
  for(const scheme of ['file','http'])for(const width of [1440,320])for(const mode of ['reader','companion']){
   const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce'}),requests=[];
   page.on('pageerror',error=>errors.push(error.message));
   page.on('console',message=>{if(['error','warning'].includes(message.type()))errors.push(message.text());});
   page.on('request',request=>requests.push(request.url()));
   const url=cap=>scheme==='file'?pathToFileURL(path.join(artifacts,`${mode}-${cap}/index.html`)).href:`${origin}/nested/${mode}-${cap}/index.html`;
   await page.goto(url(1));
   await expect(page.locator('#publication-entries')).toContainText('APPROVEDPUBLICBODY');
   await expect(page.locator('#publication-entries')).not.toContainText('LATEENTRYBODY');
   assert.equal(await page.locator('#publication-progress option').count(),2);
   assert.equal(await page.locator('#research-manager, #settings-form, #manuscript-analysis-toggle').count(),0);
   if(mode==='reader'){
    await expect(page.locator('#chapters')).toContainText('EARLY_NOVEL_PROSE');
    await expect(page.locator('#chapters')).not.toContainText('MIDDLE_NOVEL_PROSE');
   }else assert.equal(await page.locator('#chapters').count(),0);
   const image=page.locator('img[alt="APPROVED_IMAGE_ALT"]');
   await expect(image).toBeVisible();await expect(image).toHaveJSProperty('naturalWidth',1);
   await page.locator('.research-diagram-canvas').scrollIntoViewIfNeeded();
   await expect(page.locator('.research-diagram-canvas svg')).toBeVisible();
   await page.locator('[data-diagram-enlarge]').click();
   await expect(page.locator('#modal-dossier-image-enlarge')).toBeVisible();await page.keyboard.press('Escape');
   await page.locator('[data-geo-map]').scrollIntoViewIfNeeded();await expect(page.locator('.geography-map')).toBeVisible();
   await expect(page.locator('[data-geo-basemap]')).toBeHidden();
   await expect(page.locator('.geography-basemap-hint')).toBeHidden();
   await expect(page.locator('#publication-entries')).toContainText('APPROVED_CITATION_QUOTE');
   await expect(page.locator('#publication-entries a[download]')).toHaveCount(1);
   await page.screenshot({path:path.join(artifacts,`${mode}-${scheme}-${width}.png`)});
   const geometry=await page.evaluate(()=>({fits:document.documentElement.scrollWidth<=innerWidth+1,
     width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
     outside:Array.from(document.querySelectorAll('body *')).filter(element=>{const b=element.getBoundingClientRect();return b.width&&b.right>innerWidth+1;}).slice(0,12).map(element=>({tag:element.tagName,class:element.className,width:element.getBoundingClientRect().width,right:element.getBoundingClientRect().right}))}));
   assert.ok(geometry.fits,JSON.stringify({mode,scheme,width,...geometry}));
   await page.goto(url(3));
   await expect(page.locator('#publication-contents')).not.toContainText('LATE_OVERRIDE_TITLE');
   await page.locator('#publication-progress').selectOption('3');await page.locator('#publication-progress-apply').click();
   await expect(page.locator('#publication-entries')).toContainText('LATEENTRYBODY');
   assert.ok(!requests.some(url=>/\/api\/|openstreetmap|https:\/\//.test(url)),requests.join('\n'));
   await page.close();
  }
  for(const scheme of ['file','http'])for(const width of [1440,320])for(const selected of ['chapter-analysis','language-analysis','full-analysis']){
   const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce'}),requests=[];
   page.on('pageerror',error=>errors.push(error.message));
   page.on('console',message=>{if(['error','warning'].includes(message.type()))errors.push(message.text());});
   page.on('request',request=>requests.push(request.url()));
   const url=scheme==='file'?pathToFileURL(path.join(artifacts,`${selected}/index.html`)).href:`${origin}/nested/${selected}/index.html`;
   await page.goto(url);
   await page.locator('a[href="analysis.html"]').click();
   await expect(page.locator('body')).not.toContainText('MIDDLE_NOVEL_PROSE');
   if(selected==='full-analysis'){
    await expect(page.locator('body')).toContainText('EARLY_NOVEL_PROSE');
    assert.equal(await page.locator('[data-read-only="true"]').count(),1);
   }else{
    assert.equal(await page.locator('#analysis-section-chapters').count(),selected==='chapter-analysis'?1:0);
    assert.equal(await page.locator('#analysis-section-language').count(),selected==='language-analysis'?1:0);
    await expect(page.locator('body')).not.toContainText('EARLY_NOVEL_PROSE');
   }
   await page.screenshot({path:path.join(artifacts,`${selected}-${scheme}-${width}.png`)});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${selected} ${width} overflows`);
   await page.locator('a[href="index.html"]').first().click();
   await expect(page.locator('#publication-entries')).toContainText('APPROVEDPUBLICBODY');
   assert.ok(!requests.some(url=>/\/api\/|openstreetmap|https:\/\//.test(url)),requests.join('\n'));
   await page.close();
  }
  const after={};function scan(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){const file=path.join(dir,entry.name);if(entry.isDirectory())scan(file);else after[path.relative(fixture.project,file).split(path.sep).join('/')]=require('node:crypto').createHash('sha256').update(fs.readFileSync(file)).digest('hex');}}scan(fixture.project);
  assert.deepEqual(after,fixture.before);assert.deepEqual(errors,[]);
  console.log('Production curated reader/companion file/HTTP, capped prose, shared Mermaid/image/map/citation and identity passed:',artifacts);
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
