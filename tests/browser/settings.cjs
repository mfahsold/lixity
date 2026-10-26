const {launchChromium} = require('../../scripts/browser_tools.cjs');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const {startNativeServer} = require('./support/native-server.cjs');

const {pythonFixture} = require('./support/python-fixture.cjs');
const root = path.resolve(__dirname, '../..');
const data = pythonFixture(`
import json
from lixity.workspace_labels import WORKSPACE_LABELS
from lixity.language import get_language_profile
from lixity.pipeline import analyze_document, resolve_document_config
from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui import render_dashboard
text = ("## Eins\\n\\n" + "Ich gehe. Ich sehe den Regen. Ich höre die Stadt. Ich trinke Kaffee. " * 8
    + "\\n\\n## Zwei\\n\\n"
    + "Das Haus wurde verkauft und die Tür war verschlossen. Die Zeitung lag auf dem Tisch. " * 7)
config, language = resolve_document_config(text, "de")
result = analyze_document(text, config, FingerprintThresholds())
result.fingerprint.fdr_flagged = {1: ["asl"]}
baseline = render_dashboard(result.chapters, result.paragraphs, metrics=result.metrics,
    fingerprint=result.fingerprint, labels=language.labels, language_key="de", controls=True,
    enabled_actions=("analyze", "rebuild", "nda-draft"), nda_project_name="Synthetic project")
fixtures = {}
for locale in ("en", "de", "fr", "es", "it", "pt", "nl"):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    checks = {"title": {"status":"missing", "value":None, "source":None},
              "author_name": {"status":"mismatch", "value":'Other <img src=x onerror=alert(1)> Writer', "source":"front_matter"}}
    fixtures[locale] = {"labels": labels, "loaded": render_dashboard([], [], controls=True,
         language_key=locale, current_language=locale, labels=labels, title="Synthetic project",
         project_author="Synthetic Writer", author_setting_enabled=True, identity_check=checks, project_token="a" * 64,
         enabled_actions=("analyze","nda-draft"), nda_project_name="Synthetic project"),
         "empty": render_dashboard([], [], controls=True, language_key=locale, labels=labels,
         enabled_actions=("analyze","nda-draft"))}
print(json.dumps({"baseline":baseline,"fixtures":fixtures}))
`, {root});
const identityArtifacts=require('node:fs').mkdtempSync('/tmp/lixity-project-identity-settings-');

async function verifyNativeDefaults(browser) {
  const artifacts=fs.mkdtempSync('/tmp/lixity-settings-defaults-native-');
  const server=await startNativeServer(`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
base = Path(sys.argv[1])
projects = []
for width in (1440, 320):
    root = base / str(width)
    root.mkdir()
    source = root / 'manuscript.md'
    source.write_text('# Synthetic settings project\\n\\n## One\\n\\nA bird crosses the quiet garden.\\n', encoding='utf-8')
    config = root / 'lixity.toml'
    config.write_text('language = "en"\\nfdr_q = 0.05\\nmin_chapters = 7\\n', encoding='utf-8')
    projects.append({'root': str(root), 'source': str(source), 'config': str(config), 'width':width})
LixityServerHandler.workspace_root = projects[0]['root']
LixityServerHandler.source_input = projects[0]['source']
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'projects': projects}), flush=True)
server.serve_forever()
`,artifacts);
  try {
    for(const project of server.fixture.projects) {
      const {width}=project;
      const originals={config:fs.readFileSync(project.config),source:fs.readFileSync(project.source)};
      const page=await browser.newPage({viewport:{width,height:1000}});
      const errors=[];
      page.on('pageerror',error=>errors.push(error.message));
      page.on('console',message=>{if(['error','warning'].includes(message.type())) errors.push(message.text());});
      const opened=await page.request.post(server.fixture.url+'/api/project-open',{data:{path:project.root}});
      assert.equal(opened.status(),200);
      await page.goto(server.fixture.url);
      await page.locator('#tab-view-project').click();
      assert.equal(await page.locator('#set-language').inputValue(),'en');
      const identitySummary=page.locator('#settings-identity > summary');
      await identitySummary.focus();
      await page.keyboard.press('Enter');
      assert.equal(await page.locator('#project-identity-check').isVisible(),true);
      assert.equal(await page.locator('[data-identity-status=matched]').textContent(),data.fixtures.en.labels.project_identity_matched);
      assert.ok((await page.locator('#project-identity-check').textContent()).includes(data.fixtures.en.labels.project_identity_enter_author_name));
      await page.locator('#settings-thresholds > summary').click();
      await page.locator('#set-fdr-q').fill('0.02');
      await page.locator('#set-save-analysis-defaults').check();
      await page.locator('#settings-reset').click();
      assert.equal(await page.locator('#set-fdr-q').inputValue(),'0.05');
      assert.equal(await page.locator('#set-save-analysis-defaults').isChecked(),true,'Reset does not change the explicit save preference');
      assert.deepEqual(fs.readFileSync(project.config),originals.config,'Reset cannot save configuration');
      await page.locator('#set-save-analysis-defaults').uncheck();
      await page.locator('#set-fdr-q').fill('0.02');
      async function apply() {
        const response=page.waitForResponse(response=>response.url().endsWith('/api/settings'));
        const reloaded=page.waitForEvent('load');
        await page.locator('[data-action=settings]').click();
        const result=await response;
        assert.equal(result.status(),200,await result.text());
        assert.equal((await result.json()).ok,true);
        await reloaded;
        await page.locator('#tab-view-project').click();
      }
      await apply();
      assert.deepEqual(fs.readFileSync(project.config),originals.config,'Unchecked native Apply must not write defaults');
      await page.locator('#settings-thresholds > summary').click();
      assert.equal(await page.locator('#set-fdr-q').inputValue(),'0.02');
      await page.locator('#set-save-analysis-defaults').check();
      await page.locator('#set-language').selectOption('auto');
      await page.locator('#set-fdr-q').fill('0.013000000000003');
      await apply();
      const saved=fs.readFileSync(project.config,'utf8');
      assert.ok(saved.includes('language = "auto"'));
      assert.ok(saved.includes('fdr_q = 0.013000000000003'));
      assert.ok(saved.includes('min_chapters = 7'));
      assert.deepEqual(fs.readFileSync(project.source),originals.source,'Saving defaults cannot modify manuscript bytes');
      assert.equal(await page.locator('#set-save-analysis-defaults').isChecked(),false);
      const reopened=await page.request.post(server.fixture.url+'/api/project-open',{data:{path:project.root}});
      assert.equal(reopened.status(),200);
      await page.reload();
      await page.locator('#tab-view-project').click();
      await page.locator('#settings-thresholds > summary').click();
      assert.equal(await page.locator('#set-language').inputValue(),'auto');
      assert.equal(await page.locator('#set-fdr-q').inputValue(),'0.013000000000003');
      assert.equal(await page.locator('#set-save-analysis-defaults').isChecked(),false);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      await page.locator('#settings-form').screenshot({path:path.join(artifacts,`${width}.png`)});
      assert.deepEqual(errors,[]);
      await page.close();
    }
    console.log('Native settings defaults: keyboard disclosure, reset without save, unchecked byte preservation, explicit save/reopen and unchanged manuscripts at1440/320 passed. '+artifacts);
  } finally {await server.close();}
}

async function verifyNativeSpeech(browser) {
  const artifacts=fs.mkdtempSync('/tmp/lixity-speech-native-');
  const server=await startNativeServer(`
import json, sys, time
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
import lixity.speech_jobs as jobs
from lixity.speech import generate_silence_wav
base = Path(sys.argv[1])
source = base / 'manuscript.md'
source.write_text('# Synthetic audio project\\n\\n## One\\n\\nA bird crosses the quiet garden.\\n\\nA second bird follows.\\n\\n## Two\\n\\nThe garden is still.\\n', encoding='utf-8')
config = base / 'lixity.toml'
config.write_text('language = "en"\\n', encoding='utf-8')
def fake_render(source, output, *, profile, progress, cancelled, **kwargs):
    progress(0, 1)
    time.sleep(.7)
    Path(output).write_bytes(generate_silence_wav(.1))
    progress(1, 1)
    return Path(output)
jobs.render_speech_audio = fake_render
LixityServerHandler.workspace_root = str(base)
LixityServerHandler.source_input = str(source)
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'source':str(source), 'config':str(config)}), flush=True)
server.serve_forever()
`,artifacts);
  try {
    const original=fs.readFileSync(server.fixture.source);
    for(const width of [1440,320]) {
      const page=await browser.newPage({viewport:{width,height:1000}}), errors=[];
      page.on('pageerror',error=>errors.push(error.message));
      await page.goto(server.fixture.url);
      await page.locator('#tab-view-project').click();
      await page.locator('#settings-speech').click();
      const dialog=page.locator('#modal-speech');
      await page.waitForFunction(()=>document.querySelector('#speech-name')?.value==='Narrator');
      assert.equal(await dialog.isVisible(),true);
      assert.equal(await page.locator('#speech-instructions').isDisabled(),true);
      assert.equal(await page.locator('#speech-speed').isDisabled(),false);
      await page.locator('#speech-engine').selectOption('qwen3');
      assert.equal(await page.locator('#speech-instructions').isDisabled(),false);
      assert.equal(await page.locator('#speech-speed').isDisabled(),true);
      assert.equal(await page.locator('#speech-speed').locator('..').isVisible(),false);
      assert.equal(await page.locator('#speech-advanced_voice').locator('..').isVisible(),false);
      assert.equal(await page.locator('#speech-instructions').isVisible(),true);
      assert.equal(await page.locator('#speech-language option:checked').textContent(),'English');
      assert.equal(await page.locator('#speech-runtime-hint').isVisible(),true);
      assert.ok((await page.locator('#speech-runtime-hint').textContent()).includes('CPU rendering can be slow'));
      await page.locator('#speech-instructions').fill('Read calmly.');
      await page.locator('#speech-pronunciations').fill('Lixity=Lik-si-tee');
      await page.locator('[data-speech-action=preview]').click();
      await page.waitForFunction(()=>!document.querySelector('#modal-speech audio').hidden);
      const audio=page.locator('#modal-speech audio');
      const response=await page.request.get(new URL(await audio.getAttribute('src'),server.fixture.url).href);
      assert.equal(response.status(),200);
      assert.equal((await response.body()).subarray(0,4).toString(),'RIFF');
      assert.ok((await page.locator('#modal-speech').textContent()).includes('first bounded paragraph'));
      await page.locator('#speech-name').fill('Edited narrator');
      assert.equal(await audio.isVisible(),false,'Profile edits remove completed audio');
      await page.locator('[data-speech-action=preview]').click();
      await page.waitForFunction(()=>!document.querySelector('[data-speech-action=cancel]').disabled);
      await page.locator('[data-speech-action=cancel]').click();
      await page.waitForFunction(()=>document.querySelector('#modal-speech [role=status]').textContent.includes('cancelled'));
      assert.equal(await audio.isVisible(),false,'Cancelled inference cannot publish audio');
      await page.locator('[data-speech-action=preview]').click();
      await page.locator('#speech-name').fill('Newer draft');
      await page.waitForTimeout(1000);
      assert.equal(await audio.isVisible(),false,'Late results cannot attach after profile edits');
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      await dialog.locator('.modal-body').evaluate(el=>{el.scrollTop=0;});
      await dialog.screenshot({path:path.join(artifacts,`audio-${width}.png`)});
      await dialog.locator('.modal-body').evaluate(el=>{el.scrollTop=el.scrollHeight;});
      await dialog.screenshot({path:path.join(artifacts,`audio-actions-${width}.png`)});
      await page.keyboard.press('Escape');
      assert.equal(await dialog.isVisible(),false);
      await page.locator('#tab-view-analysis').click();
      await page.locator('#reader-speech').click();
      await page.waitForFunction(()=>!document.querySelector('#speech-name').disabled && document.querySelector('#speech-name').value==='Narrator');
      assert.equal(await dialog.isVisible(),true,'Reader and settings use one dialog');
      assert.equal(await page.locator('#modal-speech').count(),1);
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#reader-speech').evaluate(el=>el===document.activeElement),true,'Escape returns focus to the reader entry');
      await page.evaluate(()=>{
        const paragraph=document.querySelector('#chapters .ptext');
        const range=document.createRange(); range.selectNodeContents(paragraph);
        const selection=getSelection(); selection.removeAllRanges(); selection.addRange(range);
      });
      await page.locator('#reader-speech').click();
      await page.waitForFunction(()=>document.querySelector('#speech-name').value==='Narrator');
      const selectedRequest=page.waitForRequest(request=>request.url().endsWith('/api/speech-render'));
      await page.locator('[data-speech-action=preview]').click();
      const selectedPayload=(await selectedRequest).postDataJSON();
      assert.ok(selectedPayload.paragraph?.paragraph_sha256,'Reader preview retains exact paragraph identity');
      await page.waitForFunction(()=>!document.querySelector('#modal-speech audio').hidden);
      assert.ok((await dialog.textContent()).includes('selected paragraph'));
      await page.locator('[data-speech-action=preview]').click();
      await page.waitForFunction(()=>!document.querySelector('[data-speech-action=cancel]').disabled);
      await page.evaluate(()=>{document.body.dataset.manuscriptSourceSha256='f'.repeat(64);});
      await page.waitForFunction(()=>!document.querySelector('#modal-speech').open);
      await page.waitForTimeout(1000);
      assert.equal(await audio.getAttribute('src'),null,'Source changes close the dialog and cannot resurrect audio');
      assert.deepEqual(errors,[]);
      await page.close();
    }
    assert.deepEqual(fs.readFileSync(server.fixture.source),original,'Preview never modifies source');
    assert.equal(fs.readFileSync(server.fixture.config,'utf8'),'language = "en"\n','Draft previews never save settings');
    const savedPage=await browser.newPage({viewport:{width:1440,height:1000}});
    await savedPage.goto(server.fixture.url);
    await savedPage.locator('#tab-view-project').click();
    await savedPage.locator('#settings-speech').click();
    await savedPage.waitForFunction(()=>document.querySelector('#speech-name').value==='Narrator');
    await savedPage.locator('#speech-language').selectOption('de');
    await savedPage.locator('[data-speech-action=create]').click();
    assert.equal(await savedPage.locator('#speech-language').inputValue(),'de','New Qwen profiles retain the supported chosen language');
    await savedPage.locator('#speech-name').fill('Saved synthetic narrator');
    await Promise.all([savedPage.waitForNavigation(),savedPage.locator('[data-speech-action=save]').click()]);
    await savedPage.locator('#tab-view-project').click();
    await savedPage.locator('#settings-speech').click();
    await savedPage.waitForFunction(()=>document.querySelector('#speech-name').value==='Saved synthetic narrator');
    assert.equal(await savedPage.locator('#speech-engine').inputValue(),'qwen3');
    assert.ok(fs.readFileSync(server.fixture.config,'utf8').includes('Saved synthetic narrator'));
    assert.deepEqual(fs.readFileSync(server.fixture.source),original);
    await savedPage.close();
    console.log('Native audio: synthetic WAV, draft controls, cancellation, stale results, keyboard/Escape, unchanged sources at1440/320 passed. '+artifacts);
  } finally {await server.close();}
}

(async () => {
  const browser = await launchChromium();
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 900}});
    const submissions = [];
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://lixity.test/**', async route => {
      if (route.request().url().includes('/api/')) {
        if (route.request().url().endsWith('/settings')) submissions.push(route.request().postDataJSON());
        await route.fulfill({json: {ok: true, locked: true, records: [], message: 'Test'}});
      } else await route.fulfill({contentType: 'text/html', body: data.baseline});
    });
    await page.goto('http://lixity.test/');
    await page.locator('#tab-view-project').click();
    assert.equal(await page.locator('#tab-view-project').getAttribute('aria-selected'), 'true');
    await page.locator('#controls').screenshot({path: '/tmp/lixity-controls-fixed.png'});
    await page.locator('#settings-thresholds > summary').click();
    assert.equal(await page.locator('#set-z-mild').inputValue(), '2.5');
    assert.equal(await page.locator('#set-fdr-q').inputValue(), '0.05');
    await page.locator('#set-z-strong').fill('1.5');
    await page.locator('[data-action="settings"]').click();
    assert.equal(submissions.length, 0);
    assert.ok(await page.locator('#set-z-strong').evaluate(input => input.validationMessage.length > 0));
    await page.locator('#set-z-strong').fill('3.7');
    await Promise.all([
      page.waitForResponse(response => response.url().endsWith('/api/settings')),
      page.locator('#set-z-strong').press('Enter'),
    ]);
    assert.equal(submissions.length, 1, 'Correcting the order error clears validity for keyboard submission');
    await page.locator('#set-fdr-q').fill('0');
    await page.locator('[data-action="settings"]').click();
    assert.equal(submissions.length, 1, 'The exclusive FDR lower bound is rejected');
    await page.locator('#set-fdr-q').fill('0.013');
    await Promise.all([
      page.waitForResponse(response => response.url().endsWith('/api/settings')),
      page.locator('#set-fdr-q').press('Enter'),
    ]);
    assert.equal(submissions.length, 2, 'Correcting an exclusive-bound error supports keyboard submission');
    assert.equal(submissions[1].fdr_q, 0.013);
    await page.locator('#settings-reset').click();
    assert.equal(await page.locator('#set-z-strong').inputValue(), '3.5');
    assert.equal(submissions.length, 2);
    await page.locator('#set-z-mild').fill('2.1');
    await Promise.all([
      page.waitForResponse(response => response.url().endsWith('/api/settings')),
      page.locator('[data-action="settings"]').click(),
    ]);
    assert.equal(submissions.length, 3);
    assert.equal(submissions[2].z_mild, 2.1);
    assert.equal(submissions[2].fdr_q, 0.05);
    await page.locator('#tab-view-analysis').click();
    await page.locator('#workbench-overview-open').click();
    await page.locator('#style-tab-heatmap').click();
    await page.locator('#heatmap-fdr-only').check();
    assert.equal(await page.locator('#heatmap tbody tr:visible').count(), 1);
    await page.locator('#heatmap-fdr-only').uncheck();
    assert.equal(await page.locator('#heatmap tbody tr:visible').count(), 2);
    await page.setViewportSize({width: 390, height: 844});
    await page.locator('#tab-view-project').click();
    assert.ok(await page.locator('#settings-form').evaluate(form => form.scrollWidth <= form.clientWidth));
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.locator('#controls').screenshot({path: '/tmp/lixity-controls-mobile-fixed.png'});
    await page.close();
    for (const language of Object.keys(data.fixtures)) for (const width of [1440,320]) {
      const page=await browser.newPage({viewport:{width,height:1000}});
      const settingsPosts=[];
      let loaded=true, release;
      let pending=null;
      page.on('pageerror',error=>errors.push(error.message));
      await page.route('http://lixity.test/**',async route=>{
        const request=route.request();
        if(request.url().endsWith('/api/settings')) {
          settingsPosts.push(request.postDataJSON());
          if(pending) await pending;
          return route.fulfill({status:400,json:{ok:false,message:'Synthetic settings failure'}});
        }
        if(request.url().includes('/api/')) return route.fulfill({json:{ok:true,initialized:false}});
        return route.fulfill({contentType:'text/html',body:data.fixtures[language][loaded?'loaded':'empty']});
      });
      await page.goto('http://lixity.test/');
      await page.locator('#tab-view-project').click();
      assert.equal(page.url(),'http://lixity.test/#view-project');
      assert.ok((await page.title()).includes('Synthetic project'));
      assert.equal(await page.locator('#settings-form h3').isVisible(),true);
      assert.equal(await page.locator('#settings-scope-help').isVisible(),true);
      assert.equal(await page.locator('#settings-project-details > legend').textContent(),data.fixtures[language].labels.settings_project_details);
      assert.equal(await page.locator('#settings-analysis > legend').textContent(),data.fixtures[language].labels.settings_analysis);
      assert.equal(await page.locator('#settings-project-details #set-title').count(),1);
      assert.equal(await page.locator('#settings-project-details #set-author-name').count(),1);
      assert.equal(await page.locator('#settings-analysis #set-language').count(),1);
      assert.equal(await page.locator('#settings-analysis #set-save-analysis-defaults').count(),1);
      await page.locator('#set-title').focus();
      await page.keyboard.press('Tab');
      assert.equal(await page.locator('#set-author-name').evaluate(field=>document.activeElement===field),true);
      await page.keyboard.press('Tab');
      assert.equal(await page.locator('#settings-identity > summary').evaluate(field=>document.activeElement===field),true);
      await page.keyboard.press('Enter');
      assert.equal(await page.locator('#project-identity-check').isVisible(),true);
      const comparisonSpacing=await page.locator('#settings-identity > summary').evaluate(summary=>({
        previous:summary.getBoundingClientRect().top-summary.parentElement.previousElementSibling.getBoundingClientRect().bottom,
        next:summary.nextElementSibling.getBoundingClientRect().top-summary.getBoundingClientRect().bottom,
      }));
      assert.ok(comparisonSpacing.previous>=6,'Keyboard focus outline must clear the preceding help text');
      assert.ok(comparisonSpacing.next>=6,'Keyboard focus outline must clear the following help text');
      await page.locator('#settings-form').screenshot({path:path.join(identityArtifacts,`${language}-${width}-comparison.png`)});
      assert.equal(await page.locator('#set-language-help').textContent(),data.fixtures[language].labels.settings_language_hint);
      assert.equal(await page.locator('#settings-project-save-help').textContent(),data.fixtures[language].labels.settings_project_save_hint);
      const languageDescription=await page.locator('#set-language').evaluate(field=>
        field.getAttribute('aria-describedby').split(/\s+/).map(id=>document.getElementById(id).textContent).join(' '));
      assert.ok(languageDescription.includes(data.fixtures[language].labels.settings_language_hint));
      assert.ok(languageDescription.includes(data.fixtures[language].labels.settings_intro));
      const saveDefaults=page.locator('#set-save-analysis-defaults');
      assert.equal(await saveDefaults.isChecked(),false,'Project defaults are always an explicit opt-in');
      assert.equal(await saveDefaults.isDisabled(),false);
      assert.ok((await saveDefaults.locator('..').textContent()).includes(data.fixtures[language].labels.settings_save_analysis_defaults));
      await page.locator('#settings-thresholds > summary').click();
      for(const id of ['set-z-mild','set-z-strong','set-fdr-q','set-fdr-method','set-dim-threshold','set-flag-min-sev']) {
        const field=page.locator('#'+id);
        assert.equal(await field.isVisible(),true);
        assert.ok((await field.getAttribute('aria-describedby')).split(/\s+/).includes('settings-scope-help'));
      }
      const author=page.locator('#set-author-name');
      assert.equal(await author.inputValue(),'Synthetic Writer');
      assert.equal(await author.isDisabled(),false);
      assert.equal(await author.getAttribute('maxlength'),'500');
      assert.equal(await page.locator('label[for=set-author-name]').textContent(),data.fixtures[language].labels.project_author_name);
      assert.equal(await page.locator('#project-identity-check [data-identity-status=missing]').textContent(),data.fixtures[language].labels.project_identity_missing);
      const titleComparison=page.locator('#project-identity-check dd').first();
      assert.ok((await titleComparison.textContent()).includes(data.fixtures[language].labels.project_identity_saved+': Synthetic project'));
      assert.ok((await titleComparison.textContent()).includes(data.fixtures[language].labels.project_identity_manuscript+': '+data.fixtures[language].labels.project_identity_missing));
      assert.equal(await page.locator('#project-identity-check [data-identity-status=mismatch]').textContent(),data.fixtures[language].labels.project_identity_mismatch);
      assert.equal(await page.locator('#project-identity-check img, #project-identity-check script').count(),0);
      assert.ok((await page.locator('#project-identity-check').textContent()).includes('Other <img src=x onerror=alert(1)> Writer'));
      const identityText=await page.locator('#project-identity-check').textContent();
      assert.ok(identityText.includes(data.fixtures[language].labels.project_identity_source_metadata));
      assert.equal(identityText.includes('front_matter'),false);
      const draft='  Synthetic Élise  Writer <b>  ';
      await author.fill(draft);
      // Locale cases submit the primary action; pending-state transitions only
      // need one representative language at each viewport.
      if(language==='en') pending=new Promise(resolve=>{release=resolve;});
      const request=page.waitForRequest(request=>request.url().endsWith('/api/settings'));
      await page.locator('[data-action=settings]').click();
      await request;
      if(language==='en') {
        assert.equal(await author.isDisabled(),true,'Pending save keeps the submitted author draft stable');
        assert.equal(await page.locator('[data-action=settings]').isDisabled(),true);
        release(); pending=null;
      }
      await page.waitForFunction(()=>!document.querySelector('[data-action=settings]').disabled);
      assert.equal(await author.inputValue(),draft,'Failed settings preserve the author input');
      assert.equal(await author.isDisabled(),false);
      assert.equal(settingsPosts[0].author_name,draft.trim(),'Only outer whitespace is normalized');
      assert.equal(settingsPosts[0].title,undefined,'Changing the author does not persist the unchanged display title');
      assert.equal(settingsPosts[0].fdr_q,0.05);
      assert.equal(Object.hasOwn(settingsPosts[0],'save_analysis_defaults'),false,'Unchecked Apply retains session behavior');
      assert.ok((await page.locator('#ctl-status').textContent()).includes('Synthetic settings failure'));
      await saveDefaults.check();
      await page.locator('#set-language').selectOption('auto');
      await page.locator('#set-fdr-q').fill('0.013000000000003');
      const optIn=page.waitForRequest(request=>request.url().endsWith('/api/settings'));
      await page.locator('[data-action=settings]').click();
      await optIn;
      await page.waitForFunction(()=>!document.querySelector('[data-action=settings]').disabled);
      assert.equal(settingsPosts.at(-1).save_analysis_defaults,true);
      assert.equal(settingsPosts.at(-1).language,'auto','Persist the explicitly selected auto value, not the displayed locale');
      assert.equal(settingsPosts.at(-1).fdr_q,0.013000000000003);
      assert.equal(settingsPosts.at(-1).project_token,'a'.repeat(64));
      assert.equal(await saveDefaults.isChecked(),true,'Failed saves retain the opt-in draft for retry');
      await page.locator('#settings-form').screenshot({path:path.join(identityArtifacts,`${language}-${width}.png`)});
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),language+' '+width);
      loaded=false; await page.reload(); await page.locator('#tab-view-project').click();
      assert.equal(await page.locator('#settings-scope-help').isVisible(),true);
      assert.equal(await page.locator('#settings-project-save-help').count(),0,'No project save promise without the capability');
      assert.equal(await saveDefaults.isDisabled(),true);
      assert.equal(await saveDefaults.isChecked(),false);
      assert.equal(await author.isDisabled(),true,'Author setting requires an active project');
      assert.equal(await author.inputValue(),'','No product default author is supplied');
      assert.ok((await page.locator('#set-author-name-help').textContent()).includes(data.fixtures[language].labels.project_author_unavailable));
      if(language==='en') {
        const count=settingsPosts.length;
        await page.locator('[data-action=settings]').click();
        await page.waitForFunction(()=>!document.querySelector('[data-action=settings]').disabled);
        assert.equal(settingsPosts.length,count+1);
        assert.equal(Object.hasOwn(settingsPosts.at(-1),'author_name'),false,'Disabled author capability cannot submit a project author');
        assert.equal(Object.hasOwn(settingsPosts.at(-1),'save_analysis_defaults'),false,'An idle workspace cannot request project defaults');
      }
      await page.close();
    }
    assert.deepEqual(errors, []);
    await verifyNativeDefaults(browser);
    await verifyNativeSpeech(browser);
    console.log('Settings guidance and project identity: seven desktop/mobile locales, accessible scope/default hints, inert data and failed primary saves; pending/capability cases at both widths passed. '+identityArtifacts);
    console.log('Settings: localized values, validation, keyboard submission, reset, payload, FDR filter and mobile layout passed');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
