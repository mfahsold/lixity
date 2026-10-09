const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '../..');
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
import json
from lixity.workspace_labels import WORKSPACE_LABELS
from lixity.language import get_language_profile
from lixity.pipeline import analyze_document, resolve_document_config
from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui import render_dashboard
text = "## Eins\\n\\nIch gehe. Ich sehe den Regen.\\n\\n## Zwei\\n\\nDas Haus wurde verkauft und die Tür war verschlossen.\\n"
config, language = resolve_document_config(text, "de")
result = analyze_document(text, config, FingerprintThresholds())
result.fingerprint.fdr_flagged = {1: ["asl"]}
baseline = render_dashboard(result.chapters, result.paragraphs, metrics=result.metrics,
    fingerprint=result.fingerprint, labels=language.labels, language_key="de", controls=True,
    enabled_actions=("analyze", "rebuild", "nda-draft"), nda_project_name="Synthetic project")
fixtures = {}
for locale in ("en", "de", "fr", "es", "it", "pt", "nl"):
    labels = {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}
    checks = {"title": {"status":"matched", "value":"Synthetic project", "source":"title_page"},
              "author_name": {"status":"mismatch", "value":'Other <img src=x onerror=alert(1)> Writer', "source":"front_matter"}}
    fixtures[locale] = {"labels": labels, "loaded": render_dashboard([], [], controls=True,
         language_key=locale, current_language=locale, labels=labels, title="Synthetic project",
         project_author="Synthetic Writer", author_setting_enabled=True, identity_check=checks,
         enabled_actions=("analyze","nda-draft"), nda_project_name="Synthetic project"),
         "empty": render_dashboard([], [], controls=True, language_key=locale, labels=labels,
         enabled_actions=("analyze","nda-draft"))}
print(json.dumps({"baseline":baseline,"fixtures":fixtures}))
`], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8', maxBuffer: 8*1024*1024});
assert.equal(fixture.status, 0, fixture.stderr);
const data=JSON.parse(fixture.stdout);
const identityArtifacts=require('node:fs').mkdtempSync('/tmp/lixity-project-identity-settings-');

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
    assert.equal(await page.locator('[data-action="nda"], #nda-add-btn').count(), 0);
    assert.equal(await page.locator('#nda-draft-form').count(), 1);
    const groups = await page.locator('#controls > .ctl-group').evaluateAll(elements => elements.map(element => {
      const style = getComputedStyle(element);
      return {top: style.borderTopWidth, bottom: style.borderBottomWidth, margin: style.marginTop, padding: style.paddingTop};
    }));
    assert.equal(groups.length, 3);
    assert.deepEqual(groups.map(group => group.top), ['0px', '1px', '1px']);
    assert.ok(groups.every(group => group.bottom === '0px' && group.margin === '0px'));
    assert.deepEqual(groups.map(group => group.padding), ['0px', '16px', '16px']);
    await page.locator('#controls').screenshot({path: '/tmp/lixity-controls-fixed.png'});
    await page.locator('.settings-form .settings-advanced > summary').click();
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
    await page.locator('#heatmap-fdr-only').check();
    assert.equal(await page.locator('#heatmap tbody tr:visible').count(), 1);
    await page.locator('#heatmap-fdr-only').uncheck();
    assert.equal(await page.locator('#heatmap tbody tr:visible').count(), 2);
    const fonts = await page.evaluate(() => ({title: getComputedStyle(document.querySelector('.project-header h1')).fontFamily,
      body: getComputedStyle(document.body).fontFamily, heading: getComputedStyle(document.querySelector('#heatmap h2')).fontFamily}));
    assert.match(fonts.title, /Palatino/);
    assert.equal(fonts.body, fonts.heading);
    assert.notEqual(fonts.title, fonts.body);
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
      const author=page.locator('#set-author-name');
      assert.equal(await author.inputValue(),'Synthetic Writer');
      assert.equal(await author.isDisabled(),false);
      assert.equal(await author.getAttribute('maxlength'),'500');
      assert.equal(await page.locator('label[for=set-author-name]').textContent(),data.fixtures[language].labels.project_author_name);
      assert.equal(await page.locator('#project-identity-check [data-identity-status=matched]').textContent(),data.fixtures[language].labels.project_identity_matched);
      assert.equal(await page.locator('#project-identity-check [data-identity-status=mismatch]').textContent(),data.fixtures[language].labels.project_identity_mismatch);
      assert.equal(await page.locator('#project-identity-check img, #project-identity-check script').count(),0);
      assert.ok((await page.locator('#project-identity-check').textContent()).includes('Other <img src=x onerror=alert(1)> Writer'));
      const identityText=await page.locator('#project-identity-check').textContent();
      assert.ok(identityText.includes(data.fixtures[language].labels.project_identity_source_metadata));
      assert.ok(identityText.includes(data.fixtures[language].labels.project_identity_source_title_page));
      assert.equal(identityText.includes('front_matter'),false);
      assert.equal(await page.locator('#nda-draft-form input, #nda-draft-form textarea').count(),5,'Project authorship adds no NDA field');
      const draft='  Synthetic Élise  Writer <b>  ';
      await author.fill(draft);
      pending=new Promise(resolve=>{release=resolve;});
      const request=page.waitForRequest(request=>request.url().endsWith('/api/settings'));
      await page.locator('[data-action=settings]').click();
      await request;
      assert.equal(await author.isDisabled(),true,'Pending save keeps the submitted author draft stable');
      assert.equal(await page.locator('[data-action=settings]').isDisabled(),true);
      release(); pending=null;
      await page.waitForFunction(()=>!document.querySelector('[data-action=settings]').disabled);
      assert.equal(await author.inputValue(),draft,'Failed settings preserve the author input');
      assert.equal(await author.isDisabled(),false);
      assert.equal(settingsPosts[0].author_name,draft.trim(),'Only outer whitespace is normalized');
      assert.equal(settingsPosts[0].title,'Synthetic project','Existing title stays in the ordinary settings payload');
      assert.equal(settingsPosts[0].fdr_q,0.05);
      assert.ok((await page.locator('#ctl-status').textContent()).includes('Synthetic settings failure'));
      await page.locator('#settings-form').screenshot({path:path.join(identityArtifacts,`${language}-${width}.png`)});
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),language+' '+width);
      loaded=false; await page.reload(); await page.locator('#tab-view-project').click();
      assert.equal(await author.isDisabled(),true,'Author setting requires an active project');
      assert.equal(await author.inputValue(),'','No product default author is supplied');
      assert.ok((await page.locator('#set-author-name-help').textContent()).includes(data.fixtures[language].labels.project_author_unavailable));
      const count=settingsPosts.length;
      await page.locator('[data-action=settings]').click();
      await page.waitForFunction(()=>!document.querySelector('[data-action=settings]').disabled);
      assert.equal(settingsPosts.length,count+1);
      assert.equal(Object.hasOwn(settingsPosts.at(-1),'author_name'),false,'Disabled author capability cannot submit a project author');
      await page.close();
    }
    assert.deepEqual(errors, []);
    console.log('Project identity author/status, five NDA fields, inert data, pending/error payloads and seven desktop/mobile locales passed. '+identityArtifacts);
    console.log('Settings: localized values, validation, reset, payload, FDR filter, title-only serif and mobile layout passed');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
