const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-minimal-workflows-'));
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
import json, runpy, tempfile
from pathlib import Path
from lixity.research import api
from lixity.workspace_labels import WORKSPACE_LABELS
from lixity.language import get_language_profile
render = runpy.run_path('tests/test_ui_contract.py')['_full_dashboard']
original = render.__globals__['render_dashboard']
fixtures = {}
for language in ('en','de','fr','es','it','pt','nl'):
    labels = {**get_language_profile(language).labels, **WORKSPACE_LABELS[language]}
    def localized(*args, **kwargs):
        return original(*args, **kwargs, labels=labels, language_key=language,
                        enabled_actions=('analyze',), current_language=language)
    render.__globals__['render_dashboard'] = localized
    fixtures[language] = {'html': render(), 'labels': labels}
with tempfile.TemporaryDirectory() as directory:
    project = Path(directory) / 'synthetic'
    api.init(project, title='Synthetic minimal workflows')
    api.create_dossier(project, title='Synthetic dossier', body='Synthetic notes.')
    overview = api.project_overview(project)
    print(json.dumps({'fixtures':fixtures,'overview':overview}))
`], {cwd:root,env:{...process.env,PYTHONPATH:path.join(root,'src')},encoding:'utf8',maxBuffer:32*1024*1024});
assert.equal(fixture.status,0,fixture.stderr);
const data = JSON.parse(fixture.stdout);
(async () => {
  const browser = await launchChromium();
  const errors = [];
  const posts = [];
  const gets = [];
  let markerResponse = {status:400,body:{ok:false,message:'Synthetic marker rejected'}};
  let markerWait;
  try {
    for (const language of ['en','de','fr','es','it','pt','nl']) {
      const page = await browser.newPage({viewport:{width:1440,height:1000}});
      page.setDefaultTimeout(5000);
      page.on('pageerror',error=>errors.push(error.message));
      await page.route('http://lixity.test/**',async route => {
        const request=route.request();
        const pathname = new URL(request.url()).pathname;
        if(pathname==='/api/marker-add') {
          posts.push(request.postDataJSON());
          if(markerWait) await markerWait;
          return route.fulfill({status:markerResponse.status,json:markerResponse.body});
        }
        if(pathname==='/api/research/status') {gets.push(pathname);return route.fulfill({json:{ok:true,initialized:true,project_root:'/synthetic',...data.overview}});}
        if(pathname.startsWith('/api/')) {gets.push(pathname);return route.fulfill({json:{ok:true,...data.overview}});}
        return route.fulfill({contentType:'text/html',body:data.fixtures[language].html});
      });
      const beforeGets=gets.length;
      await page.goto('http://lixity.test/');
      await page.locator('#research-dossiers-list .research-card').waitFor({state:'attached'});
      assert.deepEqual(gets.slice(beforeGets),['/api/research/status'],'Initial overview lists do not trigger four redundant GETs');
      assert.equal(await page.locator('[data-action=analyze]').count(),1,'Native refresh exposes a single analyze action');
      assert.equal(await page.locator('[data-action=rebuild]').count(),0,'The supported alias is not another native button');
      await page.locator('#btn-modal-new-project').click();
      await page.locator('#tab-btn-scratch').click();
      await page.locator('.template-card:has(input[value=research])').click();
      assert.equal(await page.locator('#new-proj-research').isChecked(),true);
      assert.equal(await page.locator('#new-proj-research').isDisabled(),true,'Required research archive cannot appear optional');
      await page.locator('.template-card:has(input[value=minimal])').click();
      assert.equal(await page.locator('#new-proj-research').isDisabled(),false);
      assert.equal(await page.locator('#new-proj-research').isChecked(),false,'Leaving the forced template restores the prior explicit choice');
      await page.locator('#form-project-create [data-close-modal]').click();
      await page.locator('#tab-view-analysis').click();
      for(const width of [1440,320]) {
        await page.setViewportSize({width,height:1000});
        const chip=page.locator('#chapters .chip').first();
        const paragraph=page.locator('#'+await chip.getAttribute('data-target'));
        if (!await paragraph.evaluate(element=>element.classList.contains('open'))) {
          const id=await paragraph.getAttribute('id');
          await page.locator(`.chip[data-target="${id}"]`).click();
        }
        const add=paragraph.locator('[data-marker-kind=todo]');
        await add.click();
        const slot=add.locator('..').locator('.marker-note-slot');
        const input=slot.locator('.marker-note');
        await input.fill('Synthetic nonempty note <b>');
        const save=slot.locator('[data-marker-save]');
        const cancel=slot.locator('[data-marker-cancel]');
        assert.equal(await save.textContent(),data.fixtures[language].labels.marker_save);
        assert.equal(await cancel.textContent(),data.fixtures[language].labels.modal_cancel);
        const beforePosts=posts.length;
        let release;
        markerWait=new Promise(resolve=>{release=resolve;});
        await save.click();
        await page.waitForFunction(() => document.querySelector('[data-marker-save]').disabled);
        assert.equal(await input.isDisabled(),true,'Pending requests preserve an immutable draft');
        await add.click({force:true});
        assert.equal(await slot.locator('.marker-note').count(),1,'Repeated activation cannot replace a pending draft');
        assert.equal(posts.length,beforePosts+1);
        release();markerWait=null;
        await page.waitForFunction(() => document.querySelector('[data-marker-feedback]').textContent.includes('Synthetic marker rejected'));
        assert.ok((await slot.locator('[data-marker-feedback]').textContent()).includes('Synthetic marker rejected'));
        assert.equal(await input.inputValue(),'Synthetic nonempty note <b>');
        assert.equal(await input.isDisabled(),false);
        assert.equal(await save.isDisabled(),false);
        markerResponse={status:400,body:{ok:true,message:'Synthetic malformed success'}};
        await input.press('Enter');
        await page.waitForFunction(() => document.querySelector('[data-marker-feedback]').textContent.includes('Synthetic malformed success'));
        assert.equal(await input.inputValue(),'Synthetic nonempty note <b>','HTTP error cannot clear a draft despite ok:true');
        markerResponse={status:400,body:{ok:false,message:'Synthetic marker rejected'}};
        await slot.screenshot({path:path.join(artifacts,`marker-${language}-${width}.png`)});
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
        await cancel.click();
        assert.equal(await page.locator('.marker-note').count(),0);
        await page.locator('#filter-flags').check();
        await page.locator('#style-layer').selectOption('asl');
        await page.locator('#layer-only').check();
        await page.locator('#paragraph-filter-reset').click();
        assert.equal(await page.locator('#filter-flags').isChecked(),false);
        assert.equal(await page.locator('#layer-only').isChecked(),false);
        assert.equal(await page.locator('#style-layer').inputValue(),'');
      }
      await page.close();
    }
    assert.deepEqual(errors,[]);
    console.log(`Minimal workflows: native marker Save/Cancel, actual HTTP400, pending/draft preservation, overview reuse, single refresh, reset, seven locales at1440/320 passed. Screenshots: ${artifacts}`);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
