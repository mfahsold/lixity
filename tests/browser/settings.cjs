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
from lixity.config import prepare_project_settings
projects = []
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    project = base / locale
    project.mkdir()
    source = project / 'manuscript.md'
    source.write_text('# Synthetic audio project\\n\\n## One\\n\\nA bird crosses the quiet garden.\\n\\nA second bird follows.\\n\\n## Two\\n\\nThe garden is still.\\n', encoding='utf-8')
    config = project / 'lixity.toml'
    config.write_text('language = "' + locale + '"\\n', encoding='utf-8')
    # Explicit English narrator also makes Dutch UI testing independent of
    # unsupported default Dutch synthesis; no language is guessed or converted.
    prepare_project_settings(project, {'audio': {'selected':'narrator', 'profiles':{
        'narrator': {'name':'Narrator', 'engine':'qwen3', 'language':'en', 'voice':'Ryan'}}}}).commit()
    projects.append({'locale':locale, 'root':str(project), 'source':str(source), 'config':str(config)})
legacy = base / 'legacy-audio'
legacy.mkdir()
legacy_source = legacy / 'manuscript.md'
legacy_source.write_text('## Synthetic legacy project\\n\\nA river flows.\\n', encoding='utf-8')
legacy_config = legacy / 'lixity.toml'
legacy_config.write_text('language = "en"\\n[audio]\\nschema_version = "lixity-audio-settings/1"\\nselected = "retained_narrator"\\n[audio.profiles.retained_narrator]\\nname = "Retained narrator"\\nengine = "piper"\\nlanguage = "en"\\nvoice = "en_US-lessac-medium"\\npronunciations = { "Synthetic" = "Example" }\\n[audio.profiles.retained_second]\\nname = "Retained second"\\nengine = "piper"\\nlanguage = "de"\\nvoice = "de_DE-thorsten-medium"\\n', encoding='utf-8')
def fake_render(source, output, *, profile, progress, cancelled, **kwargs):
    progress(0, 1)
    time.sleep(.7)
    Path(output).write_bytes(generate_silence_wav(.1))
    progress(1, 1)
    return Path(output)
jobs.render_speech_audio = fake_render
LixityServerHandler.workspace_root = projects[0]['root']
LixityServerHandler.source_input = projects[0]['source']
LixityServerHandler.exports_dir = str(base / 'exports')
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'projects':projects, 'legacy': {'root':str(legacy), 'source':str(legacy_source), 'config':str(legacy_config)}}), flush=True)
server.serve_forever()
`,artifacts);
  try {
    for(const project of server.fixture.projects) for(const width of [1440,320]) {
      const {locale}=project, labels=data.fixtures[locale].labels;
      const original=fs.readFileSync(project.source), originalConfig=fs.readFileSync(project.config);
      const page=await browser.newPage({viewport:{width,height:1000}}), errors=[];
      page.on('pageerror',error=>errors.push(error.message));
      assert.equal((await page.request.post(server.fixture.url+'/api/project-open',{data:{path:project.root}})).status(),200);
      await page.goto(server.fixture.url);
      assert.equal(await page.locator('html').getAttribute('lang'),locale);
      await page.locator('#tab-view-project').click();
      await page.locator('#settings-speech').click();
      const dialog=page.locator('#modal-speech');
      await page.waitForFunction(()=>document.querySelector('#speech-name')?.value==='Narrator');
      assert.equal(await dialog.isVisible(),true);
      assert.equal(await page.locator('#speech-name').isVisible(),true, 'Project audio opens the profile editor');
      assert.equal(await page.locator('#speech-direction_text').isVisible(),false, 'Passage direction is reserved for the reader');
      assert.equal(await page.locator('#speech-chapter').isVisible(),false, 'Chapter output has a separate entry');
      assert.equal(await page.locator('#speech-pronunciations').isVisible(),false, 'Pronunciations start collapsed');
      assert.equal(await page.locator('#speech-speed, #speech-advanced_voice').count(),0,
        'The dialog has no unsupported speed or cached voice controls');
      assert.equal(await page.locator('#speech-engine').inputValue(),'qwen3');
      assert.equal(await page.locator('#speech-voice_description').isVisible(),false);
      await page.locator('#speech-engine').selectOption('qwen3-design');
      assert.equal(await page.locator('#speech-voice').isVisible(),false);
      assert.equal(await page.locator('#speech-voice_description').isVisible(),true);
      await page.locator('#speech-voice_description').fill('A natural German narrator with a calm voice.');
      await dialog.screenshot({path:path.join(artifacts,`voice-design-${locale}-${width}.png`)});
      await page.locator('#speech-engine').selectOption('qwen3');
      assert.equal(await page.locator('#speech-voice').isVisible(),true);
      assert.equal(await dialog.getByText(/Piper/i).count(),0,
        JSON.stringify(await dialog.getByText(/Piper/i).allTextContents()));
      assert.equal(await page.locator('#speech-instructions').isDisabled(),false);
      assert.equal(await page.locator('#speech-instructions').isVisible(),true);
      assert.equal(await page.locator('#speech-language').inputValue(),'en');
      await page.locator('#speech-lexicon > summary').click();
      await page.locator('#speech-pronunciations').locator('xpath=ancestor::details[1]/summary').click();
      await page.locator('#speech-pronunciations').fill('Lixity=Lik-si-tee');
      await page.locator('#speech-pronunciation_search').fill('Lixity');
      assert.equal(await page.locator('[data-pronunciation-row]:visible').count(), 1);
      await page.keyboard.press('Escape');
      assert.equal(await dialog.isVisible(),true,'Profile edits need an explicit save or discard');
      await page.locator('[data-speech-action=profiles_discard]').click();
      await page.keyboard.press('Escape');
      await page.locator('#tab-view-analysis').click();
      await page.locator('#reader-speech').click();
      await page.waitForFunction(()=>document.querySelector('#speech-direction_text')?.value.includes('bird'));
      assert.equal(await page.locator('#speech-name').isVisible(),false, 'Reader keeps the profile editor out of passage work');
      assert.equal(await page.locator('#speech-profile').isVisible(),true, 'Reader exposes the current project profile');
      assert.equal(await page.locator('[data-speech-action=chapter_render]').isVisible(),false);
      assert.equal(await page.locator('#speech-target').isDisabled(),false);
      assert.equal(await page.locator('#speech-runtime-hint').isVisible(),true);
      assert.ok((await page.locator('#speech-runtime-hint').textContent()).includes(labels.speech_runtime_hint));
      assert.equal(await page.locator('#speech-target').isVisible(),true);
      assert.equal(await page.locator('#speech-target').inputValue(),'local','Execution defaults to this computer');
      await page.waitForFunction(()=>document.querySelector('#speech-direction_text')?.value.includes('bird'));
      assert.equal(await page.locator('#speech-direction_text').getAttribute('readonly'),'');
      await page.locator('#speech-direction_style').selectOption('tense');
      const originalPassage = await page.locator('#speech-direction_passage').inputValue();
      const draftInstructions = await page.locator('#speech-direction_instructions').inputValue();
      await dialog.locator('[data-speech-action=close]').click();
      assert.equal(await dialog.isVisible(), true, 'Closing must not discard an unsaved direction draft');
      assert.equal(await page.locator('#speech-direction_instructions').inputValue(), draftInstructions);
      await page.keyboard.press('Escape');
      assert.equal(await dialog.isVisible(), true, 'Escape must not discard an unsaved direction draft');
      assert.equal(await page.locator('#speech-direction_instructions').inputValue(), draftInstructions);
      assert.equal(await dialog.locator('[role=status]').textContent(), labels.speech_direction_switch_first);
      await page.evaluate(()=>document.dispatchEvent(new CustomEvent('lixity:workbench-change')));
      assert.equal(await dialog.isVisible(), true, 'Workbench changes must not discard an unsaved direction draft');
      assert.equal(await page.locator('#speech-direction_instructions').inputValue(), draftInstructions);
      await page.locator('#speech-direction_passage').selectOption({index: 2});
      assert.equal(await page.locator('#speech-direction_passage').inputValue(), originalPassage, 'Changing passage must retain an unsaved direction draft');
      assert.equal(await page.locator('#speech-direction_instructions').inputValue(), draftInstructions);
      assert.equal(await dialog.locator('[role=status]').textContent(), labels.speech_direction_switch_first);
      await page.locator('#speech-chapter').selectOption('2');
      assert.equal(await page.locator('#speech-chapter').inputValue(), '1', 'Changing chapter must retain an unsaved direction draft');
      assert.equal(await page.locator('#speech-direction_instructions').inputValue(), draftInstructions);
      await page.locator('#speech-direction_text').evaluate(el=>el.setSelectionRange(2,6));
      await page.locator('[data-speech-action=direction_selection]').click();
      const directionPlanRequest=page.waitForRequest(request=>request.url().endsWith('/api/speech-plan'));
      await page.locator('[data-speech-action=direction_plan]').click();
      const draft=(await directionPlanRequest).postDataJSON().draft_direction;
      assert.equal(draft.start,2); assert.equal(draft.end,6);

      await page.waitForFunction(()=>!document.querySelector('.speech-plan').hidden);
      assert.ok((await page.locator('.speech-plan').textContent()).includes('restrained tension'));
      await page.locator('#speech-direction_text').evaluate(el=>el.scrollIntoView({block:'center'}));
      await dialog.screenshot({path:path.join(artifacts,`direction-${locale}-${width}.png`)});
      let axePath; try { axePath=require.resolve('axe-core'); } catch (_) { axePath=path.join(require('node:os').homedir(),'rosts_services/node_modules/axe-core/axe.js'); }
      if(fs.existsSync(axePath)) {
        await page.evaluate(fs.readFileSync(axePath,'utf8'));
        const audit=await page.evaluate(async()=>await axe.run(document.getElementById('modal-speech')));
        assert.deepEqual(audit.violations.map(v=>({id:v.id,impact:v.impact})),[], 'Audio direction accessibility');
        fs.writeFileSync(path.join(artifacts,`direction-a11y-${locale}-${width}.json`),JSON.stringify({violations:audit.violations,incomplete:audit.incomplete.map(v=>v.id)}));
      } else console.log('axe-core unavailable; automated audio direction accessibility audit skipped');

      await page.route('**/api/speech-direction', route=>route.fulfill({status:409, json:{ok:false, message:'Synthetic save failure'}}), {times:1});
      await page.locator('[data-speech-action=direction_save]').click();
      await page.waitForFunction(()=>document.querySelector('#modal-speech [role=status]').textContent === 'Synthetic save failure');
      assert.equal(await page.locator('#speech-direction_instructions').isDisabled(), false, 'Failed save re-enables the preserved draft');
      assert.equal(await page.locator('#speech-direction_instructions').inputValue(), draftInstructions);
      let releaseDirection;
      const directionPending = new Promise(resolve=>{releaseDirection=resolve;});
      await page.route('**/api/speech-direction', async route=>{await directionPending; await route.continue();}, {times:1});
      await page.locator('[data-speech-action=direction_save]').click();
      assert.equal(await page.locator('#speech-direction_instructions').isDisabled(), true, 'Pending save keeps the submitted direction stable');
      assert.equal(await page.locator('#speech-direction_passage').isDisabled(), true);
      assert.equal(await page.locator('#speech-chapter').isDisabled(), true);
      await dialog.locator('[data-speech-action=close]').click();
      assert.equal(await dialog.isVisible(), true, 'Pending direction save cannot be closed');
      releaseDirection();
      await page.waitForFunction(()=>document.querySelector('#speech-direction_entries').options.length===2);
      assert.equal(await page.locator('#speech-chapter').isDisabled(), false, 'Chapter selection returns after save');
      const ledger=path.join(project.root,'.lixity','audio-directions.json');
      assert.equal(JSON.parse(fs.readFileSync(ledger)).entries.length,1);
      await page.locator('#speech-direction_entries').selectOption({index:1});
      const originalEntry = await page.locator('#speech-direction_entries').inputValue();
      await page.locator('#speech-direction_instructions').fill('A synthetic draft direction.');
      await page.locator('#speech-direction_entries').selectOption({index:0});
      assert.equal(await page.locator('#speech-direction_entries').inputValue(), originalEntry, 'Changing entry must retain an unsaved direction draft');
      assert.equal(await page.locator('#speech-direction_instructions').inputValue(), 'A synthetic draft direction.');
      await page.locator('[data-speech-action=direction_discard]').click();
      await page.locator('#speech-direction_passage').selectOption({index:2});
      assert.notEqual(await page.locator('#speech-direction_passage').inputValue(), originalPassage, 'Discard permits a passage switch');
      await page.locator('#speech-direction_passage').selectOption(originalPassage);
      await page.locator('#speech-direction_entries').selectOption({index:1});
      await page.locator('#speech-direction_text').evaluate(el=>el.setSelectionRange(2,18));
      await page.locator('[data-speech-action=direction_selection]').click();
      await page.locator('[data-speech-action=direction_plan]').click();
      await page.waitForFunction(()=>!document.querySelector('.speech-plan').hidden);
      await page.locator('[data-speech-action=direction_save]').click();
      await page.waitForFunction(()=>document.querySelector('#speech-direction_entries').options.length===2 && document.querySelector('#speech-direction_entries').options[1].textContent.startsWith('2–18'));
      assert.equal(JSON.parse(fs.readFileSync(ledger)).entries.length,1,'Range edits replace the selected original');
      await page.locator('#speech-direction_entries').selectOption({index:1});
      await page.locator('[data-speech-action=direction_remove]').click();
      await page.waitForFunction(()=>document.querySelector('#speech-direction_entries').options.length===1);
      assert.equal(JSON.parse(fs.readFileSync(ledger)).entries.length,0);
      await page.locator('[data-speech-action=preview]').click();
      await page.waitForFunction(()=>!document.querySelector('#modal-speech audio').hidden);
      const audio=page.locator('#modal-speech audio');
      const response=await page.request.get(new URL(await audio.getAttribute('src'),server.fixture.url).href);
      assert.equal(response.status(),200);
      assert.equal((await response.body()).subarray(0,4).toString(),'RIFF');
      assert.ok((await page.locator('#modal-speech').textContent()).includes(labels.speech_paragraph_preview));
      await page.locator('#speech-target').selectOption('jetson');
      assert.equal(await audio.isVisible(),false,'Changing execution target removes audio from the previous target');
      assert.ok((await page.locator('#speech-runtime-hint').textContent()).includes(labels.speech_jetson_hint));
      const jetsonRequest=page.waitForRequest(request=>request.url().endsWith('/api/speech-render'));
      await page.locator('[data-speech-action=preview]').click();
      const jetsonPayload=(await jetsonRequest).postDataJSON();
      assert.equal(jetsonPayload.target,'jetson');
      assert.equal(jetsonPayload.profile.engine,'qwen3');
      assert.equal(jetsonPayload.profile.speed,1);
      assert.equal(Object.hasOwn(jetsonPayload.profile,'target'),false,'Execution selection is separate from the portable narrator');
      await page.waitForFunction(()=>!document.querySelector('#modal-speech audio').hidden);
      await dialog.locator('.modal-body').evaluate(el=>{el.scrollTop=el.scrollHeight;});
      await dialog.screenshot({path:path.join(artifacts,`audio-jetson-${locale}-${width}.png`)});
      await page.locator('#speech-target').selectOption('local');
      assert.equal(await audio.isVisible(),false,'Returning to local clears the Jetson result');
      assert.equal((await page.locator('#modal-speech').textContent()).includes(labels.speech_target_jetson + ' ·'),false,'Returning to local clears the previous result context');
      assert.ok((await page.locator('#speech-runtime-hint').textContent()).includes(labels.speech_runtime_hint));
      await page.locator('#speech-target').selectOption('jetson');
      await page.locator('[data-speech-action=preview]').click();
      await page.waitForFunction(()=>!document.querySelector('[data-speech-action=cancel]').disabled);
      await page.locator('#speech-target').selectOption('local');
      await page.waitForTimeout(1000);
      assert.equal(await audio.isVisible(),false,'A late result cannot attach after switching targets');
      const localRequest=page.waitForRequest(request=>request.url().endsWith('/api/speech-render'));
      await page.locator('[data-speech-action=preview]').click();
      assert.equal((await localRequest).postDataJSON().target,'local');
      await page.waitForFunction(()=>!document.querySelector('#modal-speech audio').hidden);
      const previousChapter=await page.locator('#speech-chapter').inputValue();
      await dialog.locator('[data-speech-action=output_title]').click();
      assert.equal(await page.locator('#speech-chapter').inputValue(),previousChapter, 'Reader shortcut retains the chapter');
      assert.equal(await page.locator('#speech-name').isVisible(),false);
      assert.equal(await page.locator('#speech-direction_text').isVisible(),false);
      assert.equal(await page.locator('#speech-chapter').isVisible(),true);
      assert.equal(await page.locator('#speech-reuse').isChecked(),true);
      await page.locator('#speech-reuse').uncheck();
      const freshRequest=page.waitForRequest(request=>request.url().endsWith('/api/speech-render'));
      await page.locator('[data-speech-action=chapter_render]').click();
      assert.equal((await freshRequest).postDataJSON().fresh_audio,true,'Explicit fresh chapter bypasses reusable segments');
      await page.waitForFunction(()=>!document.querySelector('#modal-speech audio').hidden);
      await page.locator('#speech-reuse').check();
      const resumedRequest=page.waitForRequest(request=>request.url().endsWith('/api/speech-render'));
      await page.locator('[data-speech-action=chapter_render]').click();
      assert.equal((await resumedRequest).postDataJSON().fresh_audio,false,'Chapter retries reuse completed segments by default');
      await page.waitForFunction(()=>!document.querySelector('#modal-speech audio').hidden);
      await page.locator('#speech-target').selectOption('jetson');
      assert.equal(await audio.isVisible(),false,'Changing target removes completed audio');
      await page.locator('[data-speech-action=preview]').click();
      await page.waitForFunction(()=>!document.querySelector('[data-speech-action=cancel]').disabled);
      await page.locator('[data-speech-action=cancel]').click();
      await page.waitForFunction(text=>document.querySelector('#modal-speech [role=status]').textContent.includes(text),labels.speech_state_cancelled);
      assert.equal(await audio.isVisible(),false,'Cancelled inference cannot publish audio');
      await page.locator('[data-speech-action=preview]').click();
      await page.locator('#speech-target').selectOption('local');
      await page.waitForTimeout(1000);
      assert.equal(await audio.isVisible(),false,'Late results cannot attach after profile edits');
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      await dialog.locator('.modal-body').evaluate(el=>{el.scrollTop=0;});
      await dialog.screenshot({path:path.join(artifacts,`audio-${locale}-${width}.png`)});
      await dialog.locator('.modal-body').evaluate(el=>{el.scrollTop=el.scrollHeight;});
      await dialog.screenshot({path:path.join(artifacts,`audio-actions-${locale}-${width}.png`)});
      await page.keyboard.press('Escape');
      assert.equal(await dialog.isVisible(),false);
      await page.locator('#tab-view-analysis').click();
      await page.locator('#reader-chapter').selectOption('ch-2');
      await page.locator('#reader-speech').click();
      await page.waitForFunction(()=>!document.querySelector('#speech-name').disabled && document.querySelector('#speech-name').value==='Narrator');
      assert.equal(await dialog.isVisible(),true,'Reader and settings use one dialog');
      assert.equal(await page.locator('#speech-chapter').inputValue(),'2','Audio retains the reader chapter');
      assert.equal(await page.locator('#speech-direction_text').inputValue(),'The garden is still.');
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
      assert.ok((await dialog.textContent()).includes(labels.speech_paragraph_preview));
      await page.locator('[data-speech-action=preview]').click();
      await page.waitForFunction(()=>!document.querySelector('[data-speech-action=cancel]').disabled);
      await page.evaluate(()=>{document.body.dataset.manuscriptSourceSha256='f'.repeat(64);});
      await page.waitForFunction(()=>!document.querySelector('#modal-speech').open);
      await page.waitForTimeout(1000);
      assert.equal(await audio.getAttribute('src'),null,'Source changes close the dialog and cannot resurrect audio');
      if (locale === 'de') {
        await page.reload();
        await page.locator('#tab-view-analysis').click();
        await page.locator('#reader-speech').click();
        await page.waitForFunction(()=>document.querySelector('#speech-direction_text')?.value.includes('bird'));
        await page.locator('#speech-direction_instructions').fill('Copyable synthetic draft.');
        await page.evaluate(()=>{document.body.dataset.manuscriptSourceSha256='e'.repeat(64);});
        await page.waitForTimeout(50);
        assert.equal(await dialog.isVisible(), true, 'A changed source preserves an unsaved draft');
        assert.equal(await dialog.locator('[role=status]').textContent(), labels.speech_direction_context_changed);
        assert.equal(await page.locator('#speech-direction_instructions').inputValue(), 'Copyable synthetic draft.');
        assert.equal(await page.locator('[data-speech-action=direction_save]').isDisabled(), true, 'Stale draft cannot be saved into another context');
        assert.equal(await page.locator('[data-speech-action=preview]').isDisabled(), true, 'Stale draft cannot be synthesized');
        await page.locator('[data-speech-action=direction_discard]').click();
        await dialog.locator('[data-speech-action=close]').click();
        assert.equal(await dialog.isVisible(), false, 'Explicit discard permits closing the stale draft');
      }
      assert.deepEqual(errors,[]);
      assert.deepEqual(fs.readFileSync(project.source),original,'Preview never modifies source');
      assert.deepEqual(fs.readFileSync(project.config),originalConfig,'Draft previews never save settings');
      await page.close();
    }
    const savedProject=server.fixture.projects[0], original=fs.readFileSync(savedProject.source);
    const savedPage=await browser.newPage({viewport:{width:1440,height:1000}});
    assert.equal((await savedPage.request.post(server.fixture.url+'/api/project-open',{data:{path:savedProject.root}})).status(),200);
    await savedPage.goto(server.fixture.url);
    await savedPage.locator('#tab-view-project').click();
    await savedPage.locator('#settings-speech').click();
    await savedPage.waitForFunction(()=>document.querySelector('#speech-name').value==='Narrator');
    await savedPage.locator('#speech-language').selectOption('de');
    await savedPage.locator('[data-speech-action=create]').click();
    assert.equal(await savedPage.locator('#speech-language').inputValue(),'de','New Qwen profiles retain the supported chosen language');
    await savedPage.locator('#speech-name').fill('Saved synthetic narrator');
    await savedPage.locator('#speech-engine').selectOption('qwen3-design');
    await savedPage.locator('#speech-voice_description').fill('A natural German narrator with a calm voice.');
    const saveRequest=savedPage.waitForRequest(request=>request.url().endsWith('/api/settings'));
    await Promise.all([savedPage.waitForNavigation(),savedPage.locator('[data-speech-action=save]').click()]);
    const savedPayload=(await saveRequest).postDataJSON();
    assert.equal(Object.hasOwn(savedPayload.audio,'target'),false);
    assert.ok(Object.values(savedPayload.audio.profiles).every(profile=>!Object.hasOwn(profile,'target')));
    await savedPage.locator('#tab-view-project').click();
    await savedPage.locator('#settings-speech').click();
    await savedPage.waitForFunction(()=>document.querySelector('#speech-name').value==='Saved synthetic narrator');
    assert.equal(await savedPage.locator('#speech-engine').inputValue(),'qwen3-design');
    assert.equal(await savedPage.locator('#speech-voice_description').inputValue(),'A natural German narrator with a calm voice.');
    await savedPage.keyboard.press('Escape');
    await savedPage.locator('#settings-speech-output').click();
    await savedPage.waitForFunction(()=>document.querySelector('#speech-profile')?.value);
    assert.equal(await savedPage.locator('#speech-target').inputValue(),'local','Execution target is not restored from saved audio settings');
    assert.equal(/^target\s*=/m.test(fs.readFileSync(savedProject.config,'utf8')),false,'Project TOML excludes the per-render target');
    assert.ok(fs.readFileSync(savedProject.config,'utf8').includes('Saved synthetic narrator'));
    assert.deepEqual(fs.readFileSync(savedProject.source),original);
    await savedPage.close();
    const legacyProject=server.fixture.legacy;
    const legacyConfig=fs.readFileSync(legacyProject.config), legacySource=fs.readFileSync(legacyProject.source);
    for(const width of [1440,320]) {
      const page=await browser.newPage({viewport:{width,height:1000}}), errors=[], posts=[];
      page.on('pageerror',error=>errors.push(error.message));
      page.on('request',request=>{if(request.method()==='POST') posts.push(request.url());});
      assert.equal((await page.request.post(server.fixture.url+'/api/project-open',{data:{path:legacyProject.root}})).status(),200);
      await page.goto(server.fixture.url);
      await page.locator('#tab-view-project').click();
      const opened=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/api/speech') && response.request().method()==='GET');
      await page.locator('#settings-speech').click();
      const data=await (await opened).json();
      assert.equal(data.requires_migration,true);
      assert.equal(data.settings,null);
      assert.ok(data.configuration_error.includes('audio-migrate'));
      const dialog=page.locator('#modal-speech');
      await page.waitForFunction(()=>document.querySelector('#modal-speech [role=status]').textContent.includes('audio-migrate'));
      for(const action of ['create','save','preview','chapter_render'])
        assert.equal(await dialog.locator('[data-speech-action='+action+']').isDisabled(),true,action+' requires explicit migration');
      assert.equal(await page.locator('#speech-name').isDisabled(),true);
      assert.equal(await dialog.locator('audio').isVisible(),false);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      await dialog.screenshot({path:path.join(artifacts,`audio-migration-blocked-${width}.png`)});
      await page.keyboard.press('Escape');
      assert.equal(await dialog.isVisible(),false);
      assert.equal(await page.locator('#settings-speech').evaluate(el=>el===document.activeElement),true);
      await page.locator('#tab-view-analysis').click();
      await page.locator('#reader-speech').click();
      await page.waitForFunction(()=>document.querySelector('#modal-speech [role=status]').textContent.includes('audio-migrate'));
      assert.equal(await dialog.locator('[data-speech-action=create]').isDisabled(),true);
      assert.equal(await dialog.locator('[data-speech-action=save]').isDisabled(),true);
      await page.keyboard.press('Escape');
      assert.equal(await dialog.isVisible(),false);
      assert.deepEqual(posts,[],'Opening, reading and closing legacy audio settings cannot send writes');
      assert.deepEqual(errors,[]);
      assert.deepEqual(fs.readFileSync(legacyProject.config),legacyConfig,'Both retained legacy profiles and their lexicon survive dialog access');
      assert.deepEqual(fs.readFileSync(legacyProject.source),legacySource,'Migration guidance never changes source');
      await page.close();
    }
    console.log('Native Qwen audio: synthetic WAV over real HTTP, seven locales at1440/320, VoiceDesign profiles, paragraph previews, cache/target controls, cancellation, stale results, keyboard/Escape and unchanged sources passed. '+artifacts);
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
