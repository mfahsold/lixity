// Curated reading progress never becomes an automatic reveal or an archive browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const {expect} = require(path.join(playwrightModule, 'test'));
const {pythonFixture} = require('./support/python-fixture.cjs');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-reader-publication-'));
const fixtures = pythonFixture(String.raw`
import json
from lixity.language import get_language_profile
from lixity.ui.publication import render_publication
from lixity.ui.dashboard import _script_json
from lixity.ui.manuscript_document import ReaderBlock
documents = {}
for locale in ('en','de','fr','es','it','pt','nl'):
    labels=get_language_profile(locale).labels
    pub={'schema_version':'lixity-reader-publication/1','mode':'reader','title':'Synthetic reader context',
         'introduction':'A public introduction.','max_chapter':3,'chapters':[{'number':i} for i in range(1,4)],
         'identity':'a'*64,'source_sha256':'b'*64,'profile':'public','project_id':'synthetic-project',
         'entries':[{'id':'entry-'+str(i),'title':title,'body':body,'reveal_after_chapter':i,
                     'dossier_id':'synthetic-dossier','revision':1,'section':None,
                     'citations':[],'images':[],'geography':None}
                    for i,title,body in [(0,'Before reading','A safe introduction.'),
                        (1,'After arrival','The garden gate is open.'),(3,'Later revelation','The keeper hid the key.')]]}
    blocks=[ReaderBlock('heading','Arrival',3,3,is_chapter=True),ReaderBlock('paragraph','The gate opened.',5,5),
            ReaderBlock('heading','Return',7,7,is_chapter=True),ReaderBlock('paragraph','The keeper returned.',9,9),
            ReaderBlock('heading','The key',11,11,is_chapter=True),ReaderBlock('paragraph','The key fell.',13,13)]
    modes={}
    for mode in ('reader','companion'):
        value={**pub,'mode':mode}
        html=render_publication(value,reader_document=blocks if mode=='reader' else None,labels=labels,language_key=locale)
        envelope={'schema_version':'lixity-read-only-site-data/1','responses':{},'resources':{},'publication':value}
        html=html.replace('<script>','<script type="application/json" id="lixity-site-data">'+_script_json(envelope)+'</script><script>',1)
        modes[mode]=html
        if locale=='en':
            value={**value,'introduction':''}
            html=render_publication(value,reader_document=blocks if mode=='reader' else None,labels=labels,language_key=locale)
            envelope={**envelope,'publication':value}
            html=html.replace('<script>','<script type="application/json" id="lixity-site-data">'+_script_json(envelope)+'</script><script>',1)
            modes[mode+'_empty']=html
    documents[locale]=modes
print(json.dumps(documents))
`);

(async()=>{
  const browser=await launchChromium();
  const errors=[];
  try {
    for (const [locale,modes] of Object.entries(fixtures)) for (const width of [1440,320]) {
      const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce'});
      const requests=[];
      page.on('pageerror',e=>errors.push(e.message));
      page.on('request',r=>requests.push(r.url()));
      await page.route('http://publication.test/**',r=>r.fulfill({contentType:'text/html',body:modes.reader}));
      await page.goto('http://publication.test/');
      const entries=page.locator('#publication-entries');
      await expect(entries.locator('article')).toHaveCount(1);
      await expect(entries).toContainText('Before reading');
      await expect(page.locator('#publication-context #publication-progress-form')).toHaveCount(1);
      if(locale==='en') await page.screenshot({path:path.join(artifacts,`reader-initial-${width}.png`)});
      if (width === 1440) {
        const firstChapter = await page.locator('#publication-chapter-1').boundingBox();
        assert.ok(firstChapter.y < 350, `The manuscript should begin beside its context controls, near the top (${firstChapter.y}px; ${artifacts})`);
      }
      await expect(page.locator('#publication-contents')).not.toContainText('Later revelation');
      await page.locator('#publication-progress').selectOption('1');
      await expect(entries.locator('article')).toHaveCount(1);
      await page.locator('#publication-progress-apply').click();
      await expect(entries.locator('article')).toHaveCount(2);
      await page.locator('#publication-preview-open').click();
      await page.locator('#publication-preview-progress').selectOption('3');
      await page.locator('#publication-preview-form button[type=submit]').click();
      await expect(entries).toContainText('Later revelation');
      await expect(page.locator('#publication-progress')).toHaveValue('1');
      await page.locator('#publication-preview-close').click();
      await expect(entries.locator('article')).toHaveCount(2);
      await page.reload();
      await expect(page.locator('#publication-progress')).toHaveValue('1');
      await expect(entries.locator('article')).toHaveCount(2);
      await page.locator('#publication-progress-reset').click();
      await expect(entries.locator('article')).toHaveCount(1);
      await page.locator('#publication-context-search').fill('gate');
      await expect(entries.locator('article')).toHaveCount(0);
      await page.locator('#publication-context-search').fill('');
      if (locale === 'en' && width === 1440) {
        for (const bad of ['999','-1','1.5','true','null','"3spoiler"','broken']) {
          await page.evaluate(value=>{
            const key=Object.keys(localStorage).find(key=>key.startsWith('lixity_publication_progress:'));
            localStorage.setItem(key,value);
          },bad);
          await page.reload();
          await expect(page.locator('#publication-progress')).toHaveValue('0');
          await expect(entries.locator('article')).toHaveCount(1);
        }
        await page.locator('#publication-progress').selectOption('3');
        await page.locator('#publication-progress-apply').click();
        await entries.locator('article h3').last().focus();
        await page.evaluate(()=>{
          document.getElementById('publication-progress').value='1';
          document.getElementById('publication-progress-form').requestSubmit();
        });
        await expect(page.locator('#publication-progress')).toBeFocused();
        await expect(entries).not.toContainText('Later revelation');
        await page.locator('#publication-progress-reset').click();
        await page.locator('#publication-reader-chapter').selectOption('publication-chapter-3');
        await expect(page.locator('#publication-progress')).toHaveValue('0');
      }
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      if(locale==='en') await page.screenshot({path:path.join(artifacts,`reader-${width}.png`)});
      await page.route('http://publication.test/**',r=>r.fulfill({contentType:'text/html',body:modes.companion}));
      await page.reload();
      await expect(page.locator('#chapters')).toHaveCount(0);
      await expect(page.locator('body')).not.toContainText('The gate opened.');
      await expect(entries.locator('article')).toHaveCount(1);
      await page.locator('#publication-progress').selectOption('3');
      await page.locator('#publication-progress-apply').click();
      await expect(entries.locator('article')).toHaveCount(3);
      const companionFlow = await page.locator('#publication-context').evaluate(node=>({
        content:node.scrollHeight,visible:node.clientHeight,
      }));
      assert.ok(companionFlow.content <= companionFlow.visible + 1,
        `The standalone companion uses the page scroll rather than a nested reader panel: ${JSON.stringify(companionFlow)}`);
      assert.deepEqual(requests.filter(url=>url!=='http://publication.test/'),[]);
      if(locale==='en') await page.screenshot({path:path.join(artifacts,`companion-${width}.png`)});
      await page.close();
    }
    for (const mode of ['reader','companion']) {
      const page=await browser.newPage();
      page.on('pageerror',e=>errors.push(e.message));
      await page.route('http://publication.test/**',r=>r.fulfill({contentType:'text/html',body:fixtures.en[mode+'_empty']}));
      await page.goto('http://publication.test/');
      await expect(page.locator('.publication-introduction')).toHaveCount(0);
      await expect(page.locator('#publication-entries article')).toHaveCount(1);
      await page.close();
    }
    const blocked=await browser.newPage();
    blocked.on('pageerror',e=>errors.push(e.message));
    await blocked.addInitScript(()=>Object.defineProperty(window,'localStorage',{get(){throw new DOMException('Synthetic unavailable storage','SecurityError');}}));
    await blocked.route('http://publication.test/**',r=>r.fulfill({contentType:'text/html',body:fixtures.en.companion}));
    await blocked.goto('http://publication.test/');
    await expect(blocked.locator('#publication-progress')).toHaveValue('0');
    await blocked.locator('#publication-progress').selectOption('1');
    await blocked.locator('#publication-progress-apply').click();
    await expect(blocked.locator('#publication-entries article')).toHaveCount(2);
    await expect(blocked.locator('#publication-progress-status')).toContainText('could not be saved');
    await blocked.close();
    assert.deepEqual(errors,[]);
    console.log('Curated reader/companion progress, preview, reset, saved state and seven locales passed:',artifacts);
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
