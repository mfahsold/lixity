const {openAnalysisSettings, selectMetric} = require('./support/analysis-controls.cjs');
// Exact evidence highlights preserve prose nodes and expose the same explanation to pointer and keyboard users.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium, browserLocales, resolveAxe} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-analysis-evidence-'));
const fixtures = pythonFixture(`
import hashlib, json, re
from lixity import CorpusConfig
from lixity.config import resolve_thresholds
from lixity.pipeline import analyze_document
from lixity.language import get_language_profile
from lixity.workspace_labels import WORKSPACE_LABELS
from lixity.ui import render_dashboard
from lixity.api import dashboard
text = '# Synthetic evidence\\n\\n😀 I feel the gate. The gate was opened slowly. "I can wait," she said. The organization might return. Wait. ' + 'The patient keeper watches the garden and the quiet river. ' * 8
analysis = analyze_document(text, CorpusConfig(language='en'), resolve_thresholds(project_config={}), include_evidence=True)
sticky_text = '# Synthetic sticky evidence\\n\\n🧭 The bell was on the wall and I was near the door. The bell rang.'
# At this exact threshold, the old JS division followed by multiplication rounded below Python.
sticky = analyze_document(sticky_text, CorpusConfig(language='en', sticky_min_words=9, sticky_glue_pct=800 / 12),
    resolve_thresholds(project_config={}), include_evidence=True)
result = {}
result['static'] = dashboard(text, language='en', title='Synthetic static comparison')
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    page = render_dashboard(analysis.chapters, analysis.paragraphs, metrics=analysis.metrics,
        fingerprint=analysis.fingerprint, paragraph_evidence=analysis.evidence, title='Synthetic evidence', controls=True,
        labels={**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}, language_key=locale)
    result['native-' + locale] = page
    result['sticky-' + locale] = render_dashboard(sticky.chapters, sticky.paragraphs, metrics=sticky.metrics,
        fingerprint=sticky.fingerprint, paragraph_evidence=sticky.evidence, title='Synthetic sticky evidence', controls=True,
        labels={**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}, language_key=locale)
    if locale == 'en': result['native'] = page
    # Independent transport fixture: hand-selected spans include an astral prefix.
    # This exercises the UI contract without reimplementing the shared detector.
    match = re.search(r'(<script[^>]+id="paragraph-content"[^>]*>)(.*?)(</script>)', page, re.S)
    content = json.loads(match.group(2))
    for entry in content.values():
        paragraph = entry[0]
        if 'feel' not in paragraph: continue
        layers = {}
        for key, kind, match_text, count in (('asl','sentence','😀 I feel the gate.',1), ('dialogue','dialogue','I can wait',3), ('function','word','the',1), ('filter','pattern','feel',1), ('modal','word','can',1), ('nominal','word','organization',1), ('passive','pattern','was opened',1)):
            start = paragraph.index(match_text)
            span = {'start':start,'end':start+len(match_text),'count':count}
            quotation_context = {'filter': 'outside_quotation', 'modal': 'in_quotation'}.get(key)
            if quotation_context is not None:
                span['quotation_context'] = quotation_context
            layers[key] = {'status':'available', 'kind':kind, 'count':count, 'mapped_count':count, 'spans':[span]}
        evidence = {'schema_version':'paragraph-evidence/1', 'paragraph_sha256':hashlib.sha256(paragraph.encode()).hexdigest(),
            'offset_unit':'unicode_codepoint', 'layers': layers}
        entry[3:4] = [evidence]
    page = page[:match.start(2)] + json.dumps(content).replace('</', '<\\/') + page[match.end(2):]
    result[locale] = page
long_text = ('# Long evidence\\n\\nI feel the gate. ' + 'The quiet keeper watches the garden and waits beside the river. ' * 250
    + 'I felt the rain.\\n\\nShe put the amber lantern by her gate. ' + 'She waited by the steps and watched the moon rise. ' * 65)
long_analysis = analyze_document(long_text, CorpusConfig(language='en'), resolve_thresholds(project_config={}), include_evidence=True)
result['longNative'] = render_dashboard(long_analysis.chapters, long_analysis.paragraphs, metrics=long_analysis.metrics,
    fingerprint=long_analysis.fingerprint, paragraph_evidence=long_analysis.evidence, title='Long evidence', controls=True,
    labels={**get_language_profile('en').labels, **WORKSPACE_LABELS['en']}, language_key='en')
comparison_text = '# Comparable synthetic paragraphs\\n\\nWait.\\n\\nKeeper waits.\\n\\n' + 'The quiet keeper follows the river through the garden and listens to the rain ' * 5 + '.'
comparison = analyze_document(comparison_text, CorpusConfig(language='en'), resolve_thresholds(project_config={}), include_evidence=True)
result['comparable'] = render_dashboard(comparison.chapters, comparison.paragraphs, metrics=comparison.metrics,
    fingerprint=comparison.fingerprint, paragraph_evidence=comparison.evidence, title='Comparable synthetic paragraphs', controls=True,
    labels={**get_language_profile('en').labels, **WORKSPACE_LABELS['en']}, language_key='en')
echo_text = '# Partial echo mapping\\n\\nq\\u0315\\u0323abc q\\u0323\\u0315abc q\\u0323\\u0315abc'
echo_config = CorpusConfig(language='en', word_regex=r'q\\u0323(\\u0315abc)')
echo = analyze_document(echo_text, echo_config, resolve_thresholds(project_config={}), include_evidence=True)
result['partial-echo'] = render_dashboard(echo.chapters, echo.paragraphs, metrics=echo.metrics,
    fingerprint=echo.fingerprint, paragraph_evidence=echo.evidence, title='Partial echo mapping', controls=True,
    labels={**get_language_profile('en').labels, **WORKSPACE_LABELS['en']}, language_key='en')
german_text = '# Deutsche Nominalhinweise\\n\\nZUR Untersuchung geht sie nur.\\n\\nZur Tür geht sie nur.'
german = analyze_document(german_text, CorpusConfig(language='de'), resolve_thresholds(project_config={}), include_evidence=True)
result['german-nominal'] = render_dashboard(german.chapters, german.paragraphs, metrics=german.metrics,
    fingerprint=german.fingerprint, paragraph_evidence=german.evidence, title='Deutsche Nominalhinweise', controls=True,
    labels={**get_language_profile('de').labels, **WORKSPACE_LABELS['de']}, language_key='de')
print(json.dumps(result))
`, {root});

const expected = {asl:'😀 I feel the gate.', dialogue:'I can wait', function:'the', filter:'feel', modal:'can', nominal:'organization', passive:'was opened'};
async function settle(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}
async function ranges(page) {
  return page.evaluate(() => [...(CSS.highlights?.get('lixity-analysis-evidence') || [])].map(range => range.toString()));
}
async function selected(page, key) {
  await selectMetric(page, key);
  if (!await page.locator('#analysis-evidence-enabled').isChecked()) await marksEnabled(page, true);
  await page.locator('.ptext-inner > p').filter({hasText:'😀 I feel'}).first().scrollIntoViewIfNeeded();
  await page.waitForFunction(text => [...(CSS.highlights?.get('lixity-analysis-evidence') || [])].some(range => range.toString() === text), expected[key]);
  await page.evaluate(text => {
    const range = [...CSS.highlights.get('lixity-analysis-evidence')].find(range => range.toString() === text);
    const panel = range.startContainer.parentElement.closest('.ptext');
    setPassageScrollMargin(panel);
    const clearance = parseFloat(getComputedStyle(panel).scrollMarginTop) || 12;
    window.scrollBy({top:range.getClientRects()[0].top - clearance, behavior:'instant'});
  }, expected[key]);
  await settle(page);
}
async function point(page) {
  return page.evaluate(() => {
    const range = [...CSS.highlights.get('lixity-analysis-evidence')][0], rect = range.getClientRects()[0];
    return {x:rect.left + rect.width / 2, y:rect.top + rect.height / 2};
  });
}
async function touchArrivalAndCancellation(browser) {
  const page = await browser.newPage({viewport:{width:320,height:480},hasTouch:true,reducedMotion:'reduce'});
  try {
    await page.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures.en}));
    await page.goto('http://localhost/');
    await page.locator('#manuscript-analysis-toggle').click();
    await selected(page, 'filter');
    const at = await point(page);
    async function startWithoutClick() {
      await page.evaluate(({x,y}) => {
        const paragraph = document.elementFromPoint(x,y).closest('.ptext-inner > p');
        const options = {bubbles:true, pointerType:'touch', pointerId:7, clientX:x, clientY:y};
        paragraph.dispatchEvent(new PointerEvent('pointerdown', options));
        paragraph.dispatchEvent(new PointerEvent('pointerup', options));
      }, at);
    }
    await startWithoutClick();
    await page.locator('#analysis-evidence-card').waitFor({state:'visible',timeout:2000});
    assert.equal(await page.locator('.analysis-evidence-guide').evaluate(node => node.open), false,
      'a missing compatibility click still opens a closed explanation');
    await page.evaluate(({x,y}) => {
      document.elementFromPoint(x,y).dispatchEvent(new MouseEvent('click',
        {bubbles:true,cancelable:true,detail:1,clientX:x,clientY:y}));
    }, at);
    assert.equal(await page.locator('.analysis-evidence-guide').evaluate(node => node.open), false,
      'a late compatibility click cannot activate a control in the fallback card');
    await page.keyboard.press('Escape');

    await startWithoutClick();
    await page.evaluate(() => document.dispatchEvent(new Event('lixity:workbench-change')));
    await page.waitForTimeout(650);
    assert.equal(await page.locator('#analysis-evidence-card').isVisible(), false,
      'a view change cancels a pending touch fallback');

    await selected(page, 'filter');
    await startWithoutClick();
    await page.evaluate(() => window.scrollBy({top:-50,behavior:'instant'}));
    await page.waitForTimeout(650);
    assert.equal(await page.locator('#analysis-evidence-card').isVisible(), false,
      'scrolling cancels a pending touch fallback');

    await selected(page, 'filter');
    await startWithoutClick();
    await page.evaluate(({x,y}) => document.body.dispatchEvent(new MouseEvent('click',
      {bubbles:true,cancelable:true,detail:1,clientX:x,clientY:y})), at);
    await page.waitForTimeout(650);
    assert.equal(await page.locator('#analysis-evidence-card').isVisible(), false,
      'a click delivered elsewhere cancels a pending touch fallback');

    await selected(page, 'filter');
    await startWithoutClick();
    await startWithoutClick();
    await page.evaluate(({x,y}) => {
      document.elementFromPoint(x,y).dispatchEvent(new MouseEvent('click',
        {bubbles:true,cancelable:true,detail:1,clientX:x,clientY:y}));
    }, at);
    await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
    await page.keyboard.press('Escape');
    await page.waitForTimeout(650);
    assert.equal(await page.locator('#analysis-evidence-card').isVisible(), false,
      'a later tap supersedes the earlier fallback and does not reopen the card');
  } finally {await page.close();}
}
async function explainFromMenu(page, keyboard = false) {
  const explore = page.locator('#manuscript-context-menu [data-reader-action="values"]');
  if (keyboard) {await explore.focus(); await page.keyboard.press('Enter');}
  else await explore.click();
  const explain = page.locator('#reader-inspector-body [data-reader-action="evidence"]');
  if (keyboard) {await explain.focus(); await page.keyboard.press('Enter');}
  else await explain.click();
}
async function menuInspect(page, keyboard = false) {
  const panel = page.locator('.ptext').filter({hasText:'😀 I feel'}).first();
  const trigger = panel.locator('.reader-paragraph-actions');
  await trigger.scrollIntoViewIfNeeded();
  // Opening the menu and moving the viewport are separate user actions.
  await settle(page);
  if (keyboard) {
    await trigger.focus();
    await page.keyboard.press('Enter');
  } else await trigger.click();
  await explainFromMenu(page, keyboard);
  await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
}
async function marksEnabled(page, enabled) {
  await openAnalysisSettings(page);
  await page.locator('#analysis-evidence-enabled').setChecked(enabled);
  await page.keyboard.press('Escape');
}
async function localizedSentenceCards(browser) {
  const units = {de:['Wort','Wörter'], en:['word','words'], fr:['mot','mots'], es:['palabra','palabras'], it:['parola','parole'], pt:['palavra','palavras'], nl:['woord','woorden']};
  for (const [locale, words] of Object.entries(units)) for (const width of [1440, 320]) {
    const page = await browser.newPage({viewport:{width,height:width === 320 ? 480 : 950}, hasTouch:width === 320,
      reducedMotion:'reduce', colorScheme:width === 320 ? 'dark' : 'light'});
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures['native-' + locale]}));
    await page.goto('http://localhost/');
    await page.locator('#manuscript-analysis-toggle').click();
    await marksEnabled(page, true);
    for (const [quote, count] of [['😀 I feel the gate.', 4], ['Wait.', 1]]) {
      await page.locator('.ptext-inner > p').filter({hasText:'😀 I feel'}).first().scrollIntoViewIfNeeded();
      await page.waitForFunction(quote => [...(CSS.highlights.get('lixity-analysis-evidence') || [])].some(range => range.toString() === quote), quote);
      const at = await page.evaluate(quote => {
        const range = [...CSS.highlights.get('lixity-analysis-evidence')].find(range => range.toString() === quote);
        let rect = range.getClientRects()[0];
        const panel = range.startContainer.parentElement.closest('.ptext'); setPassageScrollMargin(panel);
        const clearance = parseFloat(getComputedStyle(panel).scrollMarginTop) || 12;
        window.scrollBy({top:rect.top - clearance,behavior:'instant'});
        rect = range.getClientRects()[0];
        return {x:rect.x + Math.min(20, rect.width / 2),y:rect.y + rect.height / 2};
      }, quote);
      await settle(page);
      if (width === 320) await page.touchscreen.tap(at.x,at.y); else await page.mouse.move(at.x,at.y);
      const card = page.locator('#analysis-evidence-card'); await card.waitFor({state:'visible'});
      assert.equal(await card.locator('.analysis-evidence-sentence-words').textContent(), count + ' ' + words[count === 1 ? 0 : 1], locale + ' native tokenizer count and localized unit');
      assert.equal(await card.locator('.analysis-evidence-number').textContent(), String(count), 'sentence count has a distinct numeric presentation');
      assert.equal(await card.locator('.analysis-evidence-paragraph').count(), 1, 'paragraph value is explicitly separated from the selected sentence');
      const question = await page.evaluate(() => uiLabel('evidence_review_asl'));
      assert.ok((await card.locator('.analysis-evidence-explanation').textContent()).includes(question),
        'reading question is visible without opening the guide');
      assert.equal(await card.locator('.analysis-evidence-guide').evaluate(node => node.open), false, 'method and coverage stay secondary by default');
      const selection = await card.evaluate(node => {
        const quote = node.querySelector('blockquote').getBoundingClientRect();
        const count = node.querySelector('.analysis-evidence-measure').getBoundingClientRect();
        return {quoteRight:quote.right, countLeft:count.left, offset:Math.abs(quote.top - count.top)};
      });
      assert.ok(selection.countLeft >= selection.quoteRight && selection.offset <= 1,
        'the selected quote and localized count share a compact scope before the paragraph reference');
      if (locale === 'de' && width === 320 && count === 1) {
        assert.ok(await card.evaluate(node => node.getBoundingClientRect().height < 408),
          'a short sentence explanation leaves viewport room for reading');
      }
      if (locale === 'en' && width === 320 && count === 1) {
        const axePath = resolveAxe();
        if (axePath) {
          await page.addScriptTag({path:axePath});
          const passed = await card.evaluate(async node => {
            const badge = node.querySelector('.analysis-evidence-quote-context');
            const results = await axe.run(node, {runOnly:['color-contrast']});
            return results.passes.some(rule => rule.nodes.some(item => node.querySelector(item.target[0]) === badge));
          });
          assert.equal(passed, true, 'The quotation context badge meets text contrast in dark mode');
        } else console.log('axe-core unavailable; quotation context contrast audit skipped');
      }
      assert.equal(await card.locator('.analysis-evidence-close').evaluate(node => {const box=node.getBoundingClientRect(); return box.width >= 44 && box.height >= 44;}), true, 'compact close remains an accessible touch target');
      assert.equal(await card.evaluate(node => {const box=node.getBoundingClientRect(); return box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight;}), true, 'native localized card remains inside viewport');
      if (count === 4) await page.screenshot({path:path.join(artifacts, `sentence-${locale}-${width}.png`)});
      await page.keyboard.press('Escape');
    }
    assert.deepEqual(errors, []); await page.close();
    console.log(`${locale}/${width}: native sentence counts and presentation passed`);
  }
}

async function localizedContributions(browser) {
  const quote = '🧭 The bell was on the wall and I was near the door.';
  const counted = ['The', 'was', 'on', 'the', 'and', 'I', 'was', 'the'];
  for (const locale of ['de', 'en', 'fr', 'es', 'it', 'pt', 'nl']) {
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport:{width,height:width === 320 ? 480 : 950}, hasTouch:width === 320,
        reducedMotion:'reduce', colorScheme:width === 320 ? 'dark' : 'light'});
      try {
        await page.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures['sticky-' + locale]}));
        await page.goto('http://localhost/');
        await page.locator('#manuscript-analysis-toggle').click();
        await selectMetric(page, 'sticky');
        assert.equal(await page.locator('.reader-comparison-controls').isVisible(), false);
        async function openRange(text) {
          await page.locator('.ptext-inner > p').first().scrollIntoViewIfNeeded();
          await page.waitForFunction(text => [...(CSS.highlights.get('lixity-analysis-evidence') || [])].some(range => range.toString() === text), text);
          const at = await page.evaluate(text => {
            const range = [...CSS.highlights.get('lixity-analysis-evidence')].find(range => range.toString() === text);
            const panel = range.startContainer.parentElement.closest('.ptext');
            setPassageScrollMargin(panel);
            const clearance = parseFloat(getComputedStyle(panel).scrollMarginTop) || 12;
            window.scrollBy({top:range.getClientRects()[0].top - clearance,behavior:'instant'});
            const rect = range.getClientRects()[0];
            return {x:rect.x + Math.min(20, rect.width / 2), y:rect.y + rect.height / 2};
          }, text);
          await settle(page);
          if (width === 320) await page.touchscreen.tap(at.x, at.y);
          else await page.mouse.click(at.x, at.y);
          const card = page.locator('#analysis-evidence-card');
          await card.waitFor({state:'visible'});
          return card;
        }
        const card = await openRange(quote);
        assert.equal(await card.locator('blockquote').textContent(), quote, 'marking preserves the original sentence');
        assert.deepEqual(await card.locator('blockquote mark').allTextContents(), counted);
        const reference = card.locator('a[href*="/guides/metrics/"]');
        assert.ok(await reference.isVisible(), 'The exact sentence evidence exposes its measurement reference');
        assert.equal(await reference.getAttribute('href'), `/guides/metrics/${locale}.html#measure-sticky`);
        assert.equal(await reference.textContent(), await page.evaluate(() => uiLabel('metric_reference_link')));
        const expected = await page.evaluate(() => {
          const format = new Intl.NumberFormat(document.documentElement.lang, {style:'percent',maximumFractionDigits:3});
          return {
            count: uiFormat('evidence_sticky_count', {count:8, words:12, percent:format.format(8 / 12)}),
            rule: uiFormat('evidence_sticky_rule', {words:9, percent:format.format(8 / 12)}),
            review: uiLabel('evidence_review_sticky'),
          };
        });
        const explanation = await card.locator('.analysis-evidence-explanation').textContent();
        assert.ok(Object.values(expected).every(text => explanation.includes(text)) && !explanation.includes('evidence_'),
          'The UI explains the sentence selected by the backend at the exact threshold');
        assert.deepEqual(await page.evaluate(() => [...CSS.highlights.get('lixity-analysis-contribution')].map(range => range.toString())), counted);
        assert.ok(await card.evaluate(node => {const r = node.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight;}));
        assert.ok(await card.evaluate(node => {
          const question = node.querySelector('.analysis-evidence-explanation > p:last-child');
          return question.getBoundingClientRect().bottom <= node.getBoundingClientRect().bottom;
        }), `${locale}/${width}: the reading question fits before scrolling the card`);
        if (locale === 'de' || locale === 'en') await page.screenshot({path:path.join(artifacts, `sticky-${locale}-${width}.png`)});
        await page.keyboard.press('Escape');
        assert.equal(await page.evaluate(() => CSS.highlights.has('lixity-analysis-contribution')), false);
        await selectMetric(page, 'echo');
        await openRange('bell');
        assert.deepEqual(await page.evaluate(() => [...CSS.highlights.get('lixity-analysis-related')].map(range => range.toString())), ['bell']);
        assert.equal(await card.locator('.analysis-evidence-explanation .analysis-evidence-value').count(), 1);
      } finally {await page.close();}
    }
  }
}

async function pendingInspectorCards(browser) {
  for (const interrupt of ['arrival', 'wheel', 'keyboard', 'context', 'dock-scroll']) {
    const page = await browser.newPage({viewport:{width:320,height:480}, reducedMotion:'reduce'});
    await page.addInitScript(() => {
      const digest = crypto.subtle.digest.bind(crypto.subtle);
      window.releaseInspectorHashes = [];
      crypto.subtle.digest = (...args) => new Promise(resolve => releaseInspectorHashes.push(() => digest(...args).then(resolve)));
    });
    await page.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures.comparable}));
    await page.goto('http://localhost/'); await page.locator('#manuscript-analysis-toggle').click();
    const panel = page.locator('.ptext').first();
    await panel.locator('.reader-paragraph-actions').focus(); await page.keyboard.press('Enter');
    await page.locator('#manuscript-context-menu [data-reader-action="values"]').focus(); await page.keyboard.press('Enter');
    await page.evaluate(() => {
      const inspect = LixityAnalysisEvidence.inspect;
      LixityAnalysisEvidence.inspect = (...args) => (window.pendingInspectorCard = inspect(...args));
    });
    const explain = page.locator('#reader-inspector-body [data-reader-action="evidence"]');
    await explain.focus(); await page.keyboard.press('Enter');
    await page.waitForFunction(() => releaseInspectorHashes.length > 0);
    await settle(page); // Let the real dock-arrival scroll notification run while verification is held.
    if (interrupt === 'wheel') {await page.mouse.move(1,470); await page.mouse.wheel(0,100);}
    if (interrupt === 'keyboard') await page.keyboard.press('PageDown');
    if (interrupt === 'context') await page.locator('#tab-view-project').click();
    if (interrupt === 'dock-scroll') await page.locator('#workspace-context-panel').evaluate(node => {node.scrollTop += 12;});
    await settle(page);
    await page.evaluate(() => Promise.all(releaseInspectorHashes.splice(0).map(release => release())));
    await page.evaluate(() => pendingInspectorCard); await settle(page);
    assert.equal(await page.locator('#analysis-evidence-card').isVisible(), interrupt === 'arrival', interrupt + ': held verification respects native context arrival and subsequent user intent');
    await page.close();
  }
}

async function nativeEntry(browser) {
  const server = await startNativeServer(`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
project = Path(sys.argv[1]) / 'entry-project'
project.mkdir(exist_ok=True)
manuscript = project / 'manuscript.md'
manuscript.write_text('# Synthetic first entry\\n\\n## The garden\\n\\nI feel the rain. The gate was opened slowly. The organization might return. I felt the breeze.\\n\\nThe keeper watches the garden.\\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.research_dir = None
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.exports_dir = str(Path(sys.argv[1]) / 'exports')
LixityServerHandler.language = 'en'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'manuscript': str(manuscript)}), flush=True)
server.serve_forever()
`, artifacts);
  try {
    const originalBytes = fs.readFileSync(server.fixture.manuscript);
    const returning = await browser.newPage({viewport:{width:1440,height:950}, reducedMotion:'reduce'});
    await returning.addInitScript(() => localStorage.setItem('lixity.manuscript.reader', JSON.stringify({
      metric:'asl', evidence:true, comparison:false
    })));
    await returning.goto(server.fixture.url);
    await returning.locator('#manuscript-analysis-toggle').click();
    assert.equal(await returning.locator('#analysis-evidence-enabled').isChecked(), true, 'an existing enabled preference is retained');
    assert.equal(await returning.locator('#analysis-comparison-enabled').isChecked(), false, 'an existing disabled comparison is retained');
    await returning.waitForFunction(() => CSS.highlights.get('lixity-analysis-evidence')?.size > 0);
    await returning.close();
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport:{width,height:width === 320 ? 480 : 950}, hasTouch:width === 320, reducedMotion:'reduce'});
      const errors = [], writes = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => {if (request.method() !== 'GET') writes.push(request.method() + ' ' + new URL(request.url()).pathname);});
      await page.goto(server.fixture.url);
      const paragraph = page.locator('.ptext-inner > p').filter({hasText:'I feel the rain.'}).first();
      const actions = paragraph.locator('..').locator('.reader-paragraph-actions');
      const text = await paragraph.textContent();
      assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'false');
      await page.locator('#manuscript-analysis-toggle').click();
      // No programmatic layer activation: the author's first explicit On must work.
      assert.equal(await page.locator('#style-layer').inputValue(), 'asl', 'first Analysis On selects named sentence length');
      assert.equal(await page.locator('#reader-analysis-settings #style-layer').count(), 1, 'one direct metric selector in the analysis controls');
      assert.equal(await page.locator('#style-layer').count(), 1);
      assert.equal(await page.locator('#style-layer option:checked').textContent(), 'Sentence length');
      await openAnalysisSettings(page);
      assert.equal(await page.locator('#style-layer').isVisible(), true, 'the metric selector is directly visible beside the analysis switches');
      assert.equal(await page.locator('#analysis-evidence-enabled').isVisible(), true);
      assert.equal(await page.locator('#analysis-comparison-enabled').isVisible(), true);
      assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), false, 'first use leaves counted-text marks off');
      assert.equal(await page.locator('#analysis-comparison-enabled').isChecked(), true, 'first use retains paragraph comparison');
      await settle(page);
      assert.deepEqual(await ranges(page), [], 'first use does not underline every recognized sentence');
      assert.equal(await page.locator('#reader-analysis-settings > summary').count(), 0);
      await page.screenshot({path:path.join(artifacts, `native-settings-${width}.png`)});
      await actions.click(); await explainFromMenu(page);
      await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
      assert.deepEqual(await ranges(page), [], 'explicit inspection works without enabling global marks');
      assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), false, 'inspection keeps the default preference');
      await page.keyboard.press('Escape');
      if (width === 320) {
        await page.locator('#reader-inspector-close').focus();
        const scheduled = await page.evaluate(() => {
          const original = window.requestAnimationFrame, frames = [];
          window.requestAnimationFrame = callback => { frames.push(callback); return frames.length; };
          try {
            document.getElementById('reader-inspector-close').click();
            document.getElementById('style-layer').focus();
          } finally { window.requestAnimationFrame = original; }
          for (const callback of frames) callback(performance.now());
          return frames.length;
        });
        assert.ok(scheduled > 0, 'closing the narrow inspector schedules its return layout');
        assert.equal(await page.locator('#style-layer').evaluate(node => node === document.activeElement), true,
          'a queued dock return does not steal focus the user moved to another control');
      }
      if (await page.locator('#workspace-reader-close').isVisible()) await page.locator('#workspace-reader-close').click();
      await page.keyboard.press('Escape');
      // Direct analysis controls support keyboard input without opening a popup.
      const metric = page.locator('#style-layer');
      await metric.focus();
      if (process.platform === 'darwin') {
        // macOS native <select> popups ignore closed-control End/Home chords; verify
        // option ordering, portable selection, and focus retention instead.
        const values = await metric.locator('option').evaluateAll(nodes => nodes.map(node => node.value));
        assert.equal(values[values.length - 1], 'nominal', 'nominal is the final metric in the grouped selector');
        assert.equal(values[1], 'asl', 'asl is the first selectable metric after None');
        await metric.selectOption('nominal');
        assert.equal(await metric.inputValue(), 'nominal', 'selecting the final metric updates #style-layer');
        await metric.selectOption('asl');
        assert.equal(await metric.inputValue(), 'asl');
      } else {
        await page.keyboard.press('End'); await page.keyboard.press('Enter');
        assert.equal(await metric.inputValue(), 'nominal', 'End selects the final metric in the grouped selector');
        await page.keyboard.press('Home'); await page.keyboard.press('ArrowDown'); await page.keyboard.press('Enter');
        assert.equal(await metric.inputValue(), 'asl');
      }
      assert.equal(await metric.evaluate(node => node === document.activeElement), true);
      for (const id of ['analysis-evidence-enabled', 'analysis-comparison-enabled']) {
        const control = page.locator('#' + id), other = page.locator('#' + (id === 'analysis-evidence-enabled' ? 'analysis-comparison-enabled' : 'analysis-evidence-enabled'));
        const before = await control.isChecked(), otherBefore = await other.isChecked();
        await control.focus(); await page.keyboard.press('Space');
        assert.equal(await control.isChecked(), !before);
        assert.equal(await other.isChecked(), otherBefore, 'the two analysis decorations have independent controls');
        assert.equal(await control.evaluate(node => node === document.activeElement), true);
        await page.keyboard.press('Space'); assert.equal(await control.isChecked(), before);
      }
      await marksEnabled(page, true);
      // Appearance retains its keyboard popup and returns focus to its trigger.
      await page.locator('#reader-settings > summary').focus(); await page.keyboard.press('Enter');
      assert.equal(await page.locator('#reader-settings').evaluate(node => node.open), true);
      assert.equal(await page.locator('.reader-settings[open]').count(), 1);
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#reader-settings').evaluate(node => node.open), false);
      assert.equal(await page.locator('#reader-settings > summary').evaluate(node => node === document.activeElement), true);
      await actions.click(); await page.keyboard.press('Escape');
      await page.waitForFunction(() => [...(CSS.highlights.get('lixity-analysis-evidence') || [])].some(range => range.toString() === 'I feel the rain.'));
      await page.evaluate(() => {
        const range = [...CSS.highlights.get('lixity-analysis-evidence')].find(range => range.toString() === 'I feel the rain.');
        const panel = range.startContainer.parentElement.closest('.ptext'); setPassageScrollMargin(panel);
        const clearance = parseFloat(getComputedStyle(panel).scrollMarginTop) || 12;
        window.scrollBy({top:range.getClientRects()[0].top - clearance,behavior:'instant'});
      });
      await settle(page);
      await page.screenshot({path:path.join(artifacts, `native-controls-${width}.png`)});
      const point = await page.evaluate(() => {
        const range = [...CSS.highlights.get('lixity-analysis-evidence')].find(range => range.toString() === 'I feel the rain.');
        const rect = range.getClientRects()[0]; return {x:rect.x + rect.width / 2,y:rect.y + rect.height / 2};
      });
      assert.equal(await page.evaluate(at => Boolean(document.elementFromPoint(at.x,at.y)?.closest('.ptext-inner > p')), point), true, 'first native evidence interaction targets visible prose below the sticky controls');
      if (width === 320) await page.touchscreen.tap(point.x, point.y);
      else await page.mouse.move(point.x, point.y);
      await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
      assert.equal(await page.locator('#analysis-evidence-card blockquote').textContent(), 'I feel the rain.');
      await page.screenshot({path:path.join(artifacts, `native-first-on-${width}.png`)});
      if (width === 1440) {
        async function inspectAt(quote) {
          await paragraph.scrollIntoViewIfNeeded(); await settle(page);
          await paragraph.evaluate((node, quote) => {
            const start = node.textContent.indexOf(quote), range = document.createRange();
            range.setStart(node.firstChild, start); range.setEnd(node.firstChild, start + quote.length);
            const panel = node.closest('.ptext'); setPassageScrollMargin(panel);
            const clearance = parseFloat(getComputedStyle(panel).scrollMarginTop) || 12;
            window.scrollBy({top:range.getClientRects()[0].top - clearance,behavior:'instant'});
          }, quote);
          await settle(page);
          const at = await paragraph.evaluate((node, quote) => {
            const start = node.textContent.indexOf(quote), range = document.createRange();
            range.setStart(node.firstChild, start); range.setEnd(node.firstChild, start + quote.length);
            const rect = range.getClientRects()[0]; return {x:rect.x + rect.width / 2,y:rect.y + rect.height / 2};
          }, quote);
          await page.mouse.click(at.x, at.y, {button:'right'});
          await explainFromMenu(page);
          await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
          assert.equal(await page.locator('#analysis-evidence-card blockquote').textContent(), quote, 'right-click inspects the exact pointed occurrence');
        }
        await page.keyboard.press('Escape');
        await inspectAt('The gate was opened slowly.');
        assert.equal(await page.locator('.analysis-evidence-sentence-words').textContent(), '5 words');
        await page.keyboard.press('Escape');
        await page.locator('#manuscript-analysis-toggle').click();
        await inspectAt('The gate was opened slowly.'); // Retain the exact source point through enable/layout.
        await page.keyboard.press('Escape');
        await selectMetric(page, 'filter');
        await inspectAt('felt');
        await page.screenshot({path:path.join(artifacts, 'native-right-click-second-1440.png')});
        await page.keyboard.press('Escape');
        await selectMetric(page, 'asl');
      }
      await page.locator('#manuscript-analysis-toggle').click(); await settle(page);
      assert.deepEqual(await ranges(page), []);
      assert.equal(await page.locator('#analysis-evidence-card').isVisible(), false);
      // The same action is discoverable with Analysis Off, through native context/keyboard input.
      if (width === 1440) await paragraph.click({button:'right'});
      else {await actions.focus(); await page.keyboard.press('Shift+F10');}
      await explainFromMenu(page);
      await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
      assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'true');
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#reader-inspector-body [data-reader-action="evidence"]').evaluate(node => node === document.activeElement), true, 'explicit inspection returns focus to its originating context control');
      await page.reload();
      await page.locator('#manuscript-analysis-toggle').click();
      assert.equal(await page.locator('#style-layer').inputValue(), 'asl');
      assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), true, 'reload retains explicitly enabled marks');
      assert.equal(await page.locator('body').evaluate(node => node.classList.contains('layer-on')), true, 'restored metric reapplies shared paragraph layer');
      assert.equal(await page.locator('#layer-legend').isVisible(), true);
      assert.equal(await page.locator('#layer-legend-title').textContent(), 'Sentence length · words per sentence',
        'the restored metric names its raw measurement unit');
      await page.locator('.layer-comparison-note > summary').click();
      await page.locator('#layer-clear').press('Enter');
      assert.equal(await page.locator('#style-layer').inputValue(), '', 'The legend clears the native metric selector');
      assert.equal(await page.locator('#style-layer').evaluate(select => select === document.activeElement), true,
        'Clearing the metric returns keyboard focus to the selector');
      await selectMetric(page, 'asl');
      assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), true,
        'Reselecting a cleared metric restores its own counted-text preference');
      await page.locator('#analysis-evidence-enabled').uncheck();
      await page.keyboard.press('Escape');
      await page.locator('#manuscript-analysis-toggle').click();
      await page.locator('#manuscript-analysis-toggle').click(); await settle(page);
      assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), false, 'On respects deliberate disabled marks');
      assert.deepEqual(await ranges(page), []);
      assert.equal(await page.locator('#analysis-comparison-enabled').isChecked(), true, 'paragraph comparison survives disabling counted text');
      await page.locator('#analysis-comparison-enabled').uncheck();
      assert.equal(await page.locator('body').evaluate(node => node.classList.contains('comparison-on')), false);
      await selectMetric(page, '');
      await page.locator('#manuscript-analysis-toggle').click();
      await page.locator('#manuscript-analysis-toggle').click();
      assert.equal(await page.locator('#style-layer').inputValue(), '', 'On respects deliberate None');
      await page.reload();
      await page.locator('#manuscript-analysis-toggle').click();
      assert.equal(await page.locator('#style-layer').inputValue(), '', 'reload retains deliberate None');
      assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), false, 'reload retains disabled marks');
      assert.equal(await page.locator('#analysis-comparison-enabled').isChecked(), false, 'reload independently retains disabled paragraph comparison');
      await actions.click(); await explainFromMenu(page);
      await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
      assert.equal(await page.locator('#style-layer').inputValue(), 'asl', 'explicit inspection chooses a usable metric after None');
      assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), false, 'inspection preserves paint preference');
      assert.equal(await page.locator('#analysis-comparison-enabled').isChecked(), false, 'inspection preserves comparison preference');
      await page.keyboard.press('Escape');
      await page.locator('#reader-focus').click();
      await actions.click(); await explainFromMenu(page);
      await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
      assert.equal(await page.locator('body').evaluate(node => node.classList.contains('reader-focus')), false, 'explicit inspection uses existing workbench exit from Focus reading');
      await page.keyboard.press('Escape');
      await page.locator('#style-layer').evaluate(select => {
        select.dataset.resetChanges = '0';
        select.addEventListener('change', () => { select.dataset.resetChanges = String(Number(select.dataset.resetChanges) + 1); });
      });
      await page.locator('#paragraph-filter-reset').click();
      assert.equal(await page.locator('#style-layer').getAttribute('data-reset-changes'), '1',
        'Reset uses the same change event as the native metric selector');
      await page.reload(); await page.locator('#manuscript-analysis-toggle').click();
      assert.equal(await page.locator('#style-layer').inputValue(), '', 'reset remains a deliberate None after reload');
      await openAnalysisSettings(page);
      await page.locator('#manuscript-analysis-toggle').click();
      assert.equal(await page.locator('#reader-analysis-settings').isVisible(), false, 'Analysis Off hides the direct metric and switches');
      for (const interrupt of ['metric', 'scroll-key']) {
        if (await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed') === 'true') await page.locator('#manuscript-analysis-toggle').click();
        await actions.click();
        await page.locator('#manuscript-context-menu [data-reader-action="values"]').click();
        await page.evaluate(() => {
          window.heldEntryFrames = [];
          window.entryRAF = requestAnimationFrame;
          window.requestAnimationFrame = callback => {heldEntryFrames.push(callback); return heldEntryFrames.length;};
          const inspect = LixityAnalysisEvidence.inspect;
          LixityAnalysisEvidence.inspect = (...args) => (window.entryInspection = inspect(...args));
        });
        await page.locator('#reader-inspector-body [data-reader-action="evidence"]').click();
        if (interrupt === 'scroll-key') {
          await actions.focus(); await page.keyboard.press('PageDown');
        } else await page.evaluate(() => {
          const select = document.getElementById('style-layer');
          select.value = 'filter'; select.dispatchEvent(new Event('change', {bubbles:true}));
        });
        await page.evaluate(() => {
          window.requestAnimationFrame = entryRAF;
          heldEntryFrames.splice(0).forEach(callback => callback(performance.now()));
        });
        await page.evaluate(() => entryInspection);
        assert.equal(await page.locator('#analysis-evidence-card').isVisible(), false, `a later ${interrupt} cancels inspection during its held opening layout`);
      }
      assert.equal(await paragraph.textContent(), text);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      assert.deepEqual(errors, []); assert.deepEqual(writes, []);
      await page.close();
    }
    assert.deepEqual(fs.readFileSync(server.fixture.manuscript), originalBytes, 'reader controls never edit manuscript bytes');
  } finally {await server.close();}
}
async function metricPreferences(browser) {
  const keys = ['asl', 'function', 'dialogue', 'filter', 'passive', 'modal', 'nominal'];
  for (const width of [1440, 320]) {
    const page = await browser.newPage({viewport:{width,height:900}, reducedMotion:'reduce'});
    await page.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures.native}));
    await page.goto('http://localhost/');
    await page.locator('#manuscript-analysis-toggle').click();
    assert.equal(await page.locator('#style-layer').inputValue(), 'asl');
    assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), false);
    for (const key of keys) {
      await selectMetric(page, key);
      assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), false, key + ' starts without counted text');
      if (key === 'modal' || key === 'passive') await marksEnabled(page, true);
    }
    for (const key of keys) {
      await selectMetric(page, key);
      assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), key === 'modal' || key === 'passive', key + ' retains its own choice');
    }
    await page.reload();
    await page.locator('#manuscript-analysis-toggle').click();
    for (const key of keys) {
      await selectMetric(page, key);
      assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), key === 'modal' || key === 'passive', key + ' survives reload');
    }
    await page.close();
  }
  for (const old of [{metric:'modal', evidence:true, comparison:false}, {metric:'', evidence:true, comparison:true}]) {
    const page = await browser.newPage();
    await page.addInitScript(value => {if (!localStorage.getItem('lixity.manuscript.reader')) localStorage.setItem('lixity.manuscript.reader', JSON.stringify(value));}, old);
    await page.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures.native}));
    await page.goto('http://localhost/');
    await page.locator('#manuscript-analysis-toggle').click();
    assert.equal(await page.locator('#style-layer').inputValue(), old.metric);
    assert.equal(await page.locator('#analysis-comparison-enabled').isChecked(), old.comparison);
    await selectMetric(page, 'asl');
    assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), false, 'legacy preference must not leak to another metric');
    await selectMetric(page, 'modal');
    assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), old.metric === 'modal', 'legacy value belongs only to its last metric');
    await page.reload(); await page.locator('#manuscript-analysis-toggle').click();
    assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), old.metric === 'modal', 'migrated preference survives reload');
    await selectMetric(page, 'asl');
    assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), false);
    await page.close();
  }
  const page = await browser.newPage();
  await page.addInitScript(() => Object.defineProperty(window, 'localStorage', {value:{getItem(){throw Error('blocked');},setItem(){throw Error('blocked');}}}));
  await page.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures.native}));
  await page.goto('http://localhost/');
  await page.locator('#manuscript-analysis-toggle').click();
  await selectMetric(page, 'modal'); await marksEnabled(page, true);
  await selectMetric(page, 'asl');
  assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), false);
  await selectMetric(page, 'modal');
  assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), true, 'in-memory choices survive blocked storage');
  await page.close();
}
(async () => {
  const browser = await launchChromium();
  try {
    await nativeQuotationEvidence(browser);
    if (process.env.LIXITY_QUOTATION_ONLY) return;
    await touchArrivalAndCancellation(browser);
    await metricPreferences(browser);
    const proximity = await browser.newPage({viewport:{width:1440,height:950}, reducedMotion:'reduce'});
    await proximity.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures.native}));
    await proximity.goto('http://localhost/');
    await proximity.locator('#manuscript-analysis-toggle').click();
    await selected(proximity, 'asl');
    const cursor = await proximity.evaluate(() => {
      const boxes = [...CSS.highlights.get('lixity-analysis-evidence')].flatMap(range => [...range.getClientRects()]);
      const rect = boxes.sort((a,b) => b.width - a.width)[0];
      return {x:rect.right - 3, y:rect.top + rect.height / 2};
    });
    await proximity.mouse.move(cursor.x, cursor.y);
    const floating = proximity.locator('#analysis-evidence-card');
    await floating.waitFor({state:'visible'});
    const floatingBox = await floating.boundingBox();
    assert.ok(Math.abs(floatingBox.x - Math.max(8, Math.min(cursor.x + 12, 1440 - floatingBox.width - 8))) <= 1,
      'Sentence evidence opens beside the hovered words, rather than at the start of the line');
    await proximity.screenshot({path:path.join(artifacts, 'sentence-pointer-distance-1440.png')});
    await proximity.close();
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport:{width,height:950}, reducedMotion:'reduce'});
      try {
        await page.route('**/*', route => route.fulfill({contentType:'text/html', body:fixtures['german-nominal']}));
        await page.goto('http://localhost/');
        await page.locator('#manuscript-analysis-toggle').click();
        await marksEnabled(page, true);
        await selectMetric(page, 'nominal');
        await marksEnabled(page, true);
        assert.equal(await page.locator('#style-layer option:checked').textContent(), 'Nominalstil-Muster');
        await page.locator('.layer-comparison-note > summary').click();
        assert.match(await page.locator('#layer-comparison-hint').textContent(), /je 1\.000 Wörter/);
        assert.match(await page.locator('#layer-comparison-hint').textContent(), /etwa Endungen wie „-ung“/);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        await page.screenshot({path:path.join(artifacts, `german-nominal-guide-${width}.png`)});
        await page.locator('.layer-comparison-note > summary').click();
        await page.locator('.ptext').first().scrollIntoViewIfNeeded();
        await page.waitForFunction(() => [...(CSS.highlights?.get('lixity-analysis-evidence') || [])].some(range => range.toString() === 'Untersuchung'));
        assert.deepEqual(await ranges(page), ['Untersuchung'], 'German contractions are excluded from actual nominal highlights');
        await page.screenshot({path:path.join(artifacts, `german-nominal-${width}.png`)});
        await selectMetric(page, 'function');
        await marksEnabled(page, true);
        await page.waitForFunction(() => [...(CSS.highlights?.get('lixity-analysis-evidence') || [])].some(range => range.toString() === 'ZUR'));
        const words = await ranges(page);
        assert.ok(words.includes('ZUR') && words.includes('Zur'), 'The same contractions remain visible in the function-word measurement');
      } finally {await page.close();}
    }
    await nativeLegends(browser);
    if (process.env.LIXITY_LEGENDS_ONLY) return;
    await pendingInspectorCards(browser);
    await localizedSentenceCards(browser);
    await localizedContributions(browser);
    const echoPage = await browser.newPage({viewport:{width:1440,height:950}, reducedMotion:'reduce'});
    try {
      await echoPage.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures['partial-echo']}));
      await echoPage.goto('http://localhost/');
      await echoPage.locator('#manuscript-analysis-toggle').click();
      await selectMetric(echoPage, 'echo');
      await echoPage.locator('.ptext .reader-paragraph-actions').first().click();
      await explainFromMenu(echoPage);
      const card = echoPage.locator('#analysis-evidence-card');
      await card.waitFor({state:'visible'});
      assert.match(await card.locator('.analysis-evidence-explanation .analysis-evidence-value').textContent(),
        /appears 3 times here\. Lixity counted 3 word echoes/, 'partial mapping keeps backend group and paragraph counts');
      assert.match(await card.locator('.analysis-evidence-warning').textContent(), /cannot be located exactly/);
      assert.equal(await echoPage.evaluate(() => CSS.highlights.get('lixity-analysis-related').size), 1,
        'only the mapped occurrence in the same backend group is highlighted');
    } finally {await echoPage.close();}
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport:{width,height:width === 320 ? 480 : 950}, reducedMotion:'reduce', colorScheme:width === 320 ? 'dark' : 'light'});
      await page.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures.comparable}));
      await page.goto('http://localhost/');
      await page.locator('#manuscript-analysis-toggle').click();
      for (const index of [0, 2]) {
        const target = page.locator('.ptext').nth(index);
        await target.locator('.reader-paragraph-actions').click(); await explainFromMenu(page);
        const card = page.locator('#analysis-evidence-card'); await card.waitFor({state:'visible'});
        const info = await target.evaluate(node => chipLayers(paragraphChips[node.id]).asl);
        assert.ok(index === 0 ? info[2] < 0 : info[2] > 2.5, 'native paragraph has the expected existing reference direction');
        assert.deepEqual(await card.locator('.analysis-evidence-comparison dl dd').allTextContents(),
          [`${info[3]} words per sentence`, `${info[6]} words per sentence`],
          'comparison pairs the paragraph value and the engine’s chapter median in the metric unit');
        const score = card.locator('.analysis-evidence-guide .analysis-evidence-comparison-score');
        assert.equal(await score.textContent(), 'z = ' + (info[2] >= 0 ? '+' : '') + info[2].toFixed(2),
          'the numeric z score remains in the analysis details');
        assert.equal(await score.isVisible(), false, 'the technical score stays hidden until requested');
        assert.match(await card.locator('.analysis-evidence-comparison-label').textContent(), index === 0 ? /below the chapter median/ : /above the chapter median/);
        assert.equal(await card.locator('.analysis-evidence-scale').getAttribute('aria-label'), info[1], 'bounded visual scale retains the full paragraph reference explanation');
        assert.equal(await card.locator('.analysis-evidence-scale').evaluate(node => node.style.getPropertyValue('--evidence-comparison-position')),
          info[5] + '%', 'marker uses the position prepared with the chapter comparison');
        assert.equal(await card.locator('.analysis-evidence-scale').evaluate(node => {
          const track = node.getBoundingClientRect(), marker = node.querySelector('span').getBoundingClientRect();
          return marker.left >= track.left - 1 && marker.right <= track.right + 1;
        }), true, 'existing z score stays inside the visual scale');
        if (width === 320) {
          assert.equal(await target.evaluate(node => node.getBoundingClientRect().top >= innerHeight), true, 'narrow context keeps the selected manuscript paragraph offscreen');
          assert.equal(await page.locator('#reader-inspector-body [data-reader-action="evidence"]').isVisible(), true, 'explicit explanation is anchored to the visible context action');
        }
        if (index === 2) {
          await page.screenshot({path:path.join(artifacts, `comparison-${width}.png`)});
          await card.locator('.analysis-evidence-guide summary').click();
          await card.evaluate(node => {node.scrollTop = node.scrollHeight;}); await settle(page);
          assert.equal(await card.locator('.analysis-evidence-close').evaluate(node => {
            const close = node.getBoundingClientRect(), parent = node.closest('.analysis-evidence-card').getBoundingClientRect();
            return close.top >= parent.top && close.bottom <= Math.min(parent.bottom,innerHeight) && close.height >= 44;
          }), true, 'close remains visible after scrolling a long explanation');
        }
        await page.keyboard.press('Escape');
        if (width === 320 && index === 0) {
          const oldTrigger = await page.locator('#reader-inspector-body [data-reader-action="evidence"]').elementHandle();
          await page.locator('.ptext').last().locator('.reader-paragraph-actions').click();
          await page.locator('#manuscript-context-menu [data-reader-action="values"]').click();
          await target.evaluate(async (node, trigger) => {await LixityAnalysisEvidence.inspect(node,trigger);}, oldTrigger);
          assert.equal(await card.isVisible(), false, 'a superseded inspector action cannot reopen the old offscreen paragraph');
          await oldTrigger.dispose();
        } else if (width === 320) {
          await page.locator('#reader-inspector-body [data-reader-action="evidence"]').click();
          await card.waitFor({state:'visible'});
          await page.locator('#workspace-context-panel').evaluate(node => {node.scrollTop += 12;}); await settle(page);
          assert.equal(await card.isVisible(), false, 'scrolling the actual inspector scrollport dismisses its anchored explanation');
          await page.locator('#reader-inspector-body [data-reader-action="evidence"]').click();
          await card.waitFor({state:'visible'});
          await page.mouse.move(1,470); await page.mouse.wheel(0,100);
          await card.waitFor({state:'hidden'});
          assert.equal(await card.isVisible(), false, 'scrolling outside the context-anchored explanation dismisses it');
        }
      }
      if (width === 1440) {
        const target = page.locator('.ptext').first();
        await target.evaluate(node => { chipLayers(paragraphChips[node.id]).asl.length = 5; });
        await target.locator('.reader-paragraph-actions').click(); await explainFromMenu(page);
        const card = page.locator('#analysis-evidence-card');
        await card.waitFor({state:'visible'});
        assert.match(await card.locator('.analysis-evidence-comparison-label').textContent(), /below the chapter median/);
        assert.equal(await card.locator('.analysis-evidence-scale').count(), 0,
          'a missing visual coordinate leaves the measured comparison text visible');
      }
      await page.close();
    }
    await nativeEntry(browser);
    const long = await browser.newPage({viewport:{width:1440,height:950}, reducedMotion:'reduce'});
    await long.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures.longNative}));
    await long.goto('http://localhost/');
    await long.locator('#manuscript-analysis-toggle').click();
    await marksEnabled(long, true);
    await selectMetric(long, 'filter');
    await marksEnabled(long, true);
    await long.locator('.reader-paragraph-actions').first().click();
    await explainFromMenu(long);
    await long.locator('#analysis-evidence-card').waitFor({state:'visible'});
    assert.equal(await long.locator('#analysis-evidence-card blockquote').textContent(), 'feel');
    await long.getByRole('button',{name:'Next match',exact:true}).click();
    await settle(long);
    assert.equal(await long.locator('#analysis-evidence-card blockquote').textContent(), 'felt');
    assert.equal(await long.evaluate(() => {
      const range = [...CSS.highlights.get('lixity-analysis-current')][0], rect = range.getBoundingClientRect();
      const header = document.getElementById('manuscript-reader-controls').getBoundingClientRect();
      return rect.top >= header.bottom && rect.bottom <= innerHeight;
    }), true, 'Next match reveals the actual offscreen evidence range');
    await long.keyboard.press('Escape');
    await selectMetric(long, 'function');
    await marksEnabled(long, true);
    await long.locator('.ptext-inner > p').first().scrollIntoViewIfNeeded();
    await long.waitForFunction(() => CSS.highlights.get('lixity-analysis-evidence')?.size >= 1000);
    const benchmark = await long.evaluate(async () => {
      const original = Range.prototype.getClientRects;
      let calls = 0, elapsed = 0;
      Range.prototype.getClientRects = function() {const start = performance.now(); const value = original.call(this); elapsed += performance.now() - start; calls++; return value;};
      const prose = document.querySelector('.ptext-inner > p');
      try {
        for (let frame = 0; frame < 12; frame++) {
          prose.dispatchEvent(new PointerEvent('pointermove', {bubbles:true,pointerType:'mouse',clientX:0,clientY:0}));
          await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        }
      } finally {Range.prototype.getClientRects = original;}
      return {ranges:CSS.highlights.get('lixity-analysis-evidence').size, frames:12, rectangleCalls:calls, rectangleMs:elapsed};
    });
    assert.ok(benchmark.rectangleCalls <= benchmark.ranges * 2, 'stable pointer frames do not repeatedly measure every evidence rectangle');
    fs.writeFileSync(path.join(artifacts,'hit-benchmark.json'), JSON.stringify(benchmark,null,2));
    console.log('worst-case range hit benchmark:', benchmark);
    await long.evaluate(() => {
      const panel = document.querySelector('.ptext');
      window.scrollBy({top:panel.getBoundingClientRect().top + innerHeight, behavior:'instant'});
    });
    await settle(long);
    const scrollBenchmark = await long.evaluate(async () => {
      const key = 'lixity-analysis-evidence', registry = CSS.highlights;
      const marks = registry.get(key), original = registry.set, initialY = scrollY;
      let replacements = 0;
      registry.set = function(name, value) {
        if (name === key) replacements++;
        return original.call(this, name, value);
      };
      try {
        for (let frame = 0; frame < 12; frame++) {
          window.scrollBy({top:12, behavior:'instant'});
          await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        }
      } finally {delete registry.set;}
      return {distance:scrollY - initialY, ranges:marks.size, sameMarks:marks === registry.get(key), replacements};
    });
    console.log('in-paragraph scroll benchmark:', scrollBenchmark);
    assert.deepEqual(scrollBenchmark, {distance:144, ranges:benchmark.ranges, sameMarks:true, replacements:0},
      'scrolling through one long paragraph keeps its exact highlight ranges without replacements');
    await long.locator('.ptext').last().evaluate(panel => {
      window.scrollBy({top:panel.getBoundingClientRect().top + 1, behavior:'instant'});
    });
    await long.waitForFunction(() => {
      const marks = [...(CSS.highlights.get('lixity-analysis-evidence') || [])];
      const panels = document.querySelectorAll('.ptext');
      const last = panels[panels.length - 1];
      return marks.length > 0 && last && marks.every(range => last.contains(range.startContainer));
    });
    await long.close();
    console.log('long paragraph next-match arrival: passed');
    for (const locale of browserLocales) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport:{width,height:width === 320 ? 480 : 950},
        hasTouch:width === 320, reducedMotion:'reduce', colorScheme:width === 320 ? 'dark' : 'light'});
      page.setDefaultTimeout(10000);
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures[locale]}));
      await page.goto('http://localhost/');
      await page.locator('#manuscript-analysis-toggle').click();
      const paragraph = page.locator('.ptext-inner > p').filter({hasText:'😀 I feel'}).first();
      await paragraph.evaluate(node => {window.originalEvidenceProse = {node, children:[...node.childNodes], text:node.textContent};});
      for (const [key, quote] of Object.entries(expected)) {
        await selected(page, key);
        assert.deepEqual(await ranges(page), [quote], `${locale}/${width}/${key}: exact evidence, including Unicode offsets`);
      }
      await selected(page, 'filter');
      assert.equal(await paragraph.evaluate(node => node === originalEvidenceProse.node && node.textContent === originalEvidenceProse.text &&
        originalEvidenceProse.children.every((child, index) => node.childNodes[index] === child)), true, 'highlight never replaces prose nodes');
      const at = await point(page);
      assert.equal(await page.evaluate(at => Boolean(document.elementFromPoint(at.x,at.y)?.closest('.ptext-inner > p')), at), true, 'native pointer targets the visible marked prose');
      if (width === 1440) {
        const focus = await page.evaluate(() => document.activeElement.id);
        await page.mouse.move(at.x, at.y);
        await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
        assert.equal(await page.evaluate(() => document.activeElement.id), focus, 'hover does not steal focus');
      } else {
        if (locale === 'en') await page.evaluate(() => {
          // A frame can run between pointerup and the compatibility click.
          // Force that ordering to verify the tap cannot activate the card.
          document.addEventListener('pointerup', event => {
            if (event.pointerType !== 'touch') return;
            const original = window.requestAnimationFrame;
            window.requestAnimationFrame = callback => {
              window.requestAnimationFrame = original;
              callback(performance.now());
              return 0;
            };
          }, {capture:true, once:true});
        });
        await page.touchscreen.tap(at.x, at.y);
        await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
        assert.equal(await page.locator('.analysis-evidence-guide').evaluate(node => node.open), false,
          'opening on touch does not activate the card with the same tap');
      }
      assert.equal(await page.locator('#analysis-evidence-card blockquote').textContent(), 'feel');
      assert.equal(await page.locator('#analysis-evidence-card .analysis-evidence-quote-context').textContent(),
        await page.evaluate(() => uiLabel('evidence_quote_outside_quotation')));
      assert.equal(await page.evaluate(() => {
        const rect = document.getElementById('analysis-evidence-card').getBoundingClientRect();
        return rect.left >= 0 && rect.right <= innerWidth && rect.top >= 0 && rect.bottom <= innerHeight;
      }), true, 'explanation stays bounded at 320×480 and desktop');
      if (locale === 'en' || locale === 'de') await page.screenshot({path:path.join(artifacts, `${locale}-${width}.png`)});
      await page.locator('.analysis-evidence-guide summary').click();
      assert.equal(await page.locator('.analysis-evidence-guide').evaluate(node => node.open), true);
      await settle(page);
      assert.equal(await page.locator('#analysis-evidence-card').evaluate(node => {const box=node.getBoundingClientRect(); return box.top >= 0 && box.bottom <= innerHeight;}), true, 'expanded heuristic guide remains bounded');
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#analysis-evidence-card').isVisible(), false);
      await selected(page, 'modal');
      await page.evaluate(() => window.LixityAnalysisEvidence.inspectSpan(document.querySelector('.ptext'), 'modal', 0));
      await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
      assert.equal(await page.locator('#analysis-evidence-card .analysis-evidence-quote-context').textContent(),
        await page.evaluate(() => uiLabel('evidence_quote_in_quotation')));
      await page.keyboard.press('Escape');
      await selected(page, 'nominal');
      assert.equal(await page.evaluate(() => LixityAnalysisEvidence.inspectSpan(document.querySelector('.ptext'), 'nominal', 0)), true);
      assert.equal(await page.locator('#analysis-evidence-card .analysis-evidence-quote-context').getAttribute('data-quote-context'), 'unknown');
      await page.keyboard.press('Escape');
      await selected(page, 'filter');
      if (width === 1440) {
        await paragraph.scrollIntoViewIfNeeded();
        const contextAt = await point(page);
        await page.mouse.click(contextAt.x, contextAt.y, {button:'right'});
        await explainFromMenu(page);
        await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
      } else await menuInspect(page, true);
      assert.equal(await page.locator('#analysis-evidence-card blockquote').textContent(), 'feel');
      await settle(page);
      assert.equal(await page.locator('#analysis-evidence-card').isVisible(), true, 'queued context-arrival scroll does not dismiss the keyboard explanation');
      assert.equal(await page.locator('#analysis-evidence-card button').first().evaluate(node => node === document.activeElement), true, 'keyboard inspection keeps focus on its close action after context layout');
      await page.keyboard.press('Escape');
      // Backward selection survives switching overlay state; source prose remains untouched.
      await paragraph.evaluate(node => {
        const text = node.firstChild; getSelection().setBaseAndExtent(text, 12, text, 3);
        window.evidenceSelection = {anchor:getSelection().anchorOffset, focus:getSelection().focusOffset, text:getSelection().toString()};
        document.getElementById('analysis-evidence-enabled').click();
      });
      await settle(page);
      assert.deepEqual(await ranges(page), []);
      assert.equal(await paragraph.evaluate(node => getSelection().anchorNode === node.firstChild &&
        getSelection().anchorOffset === evidenceSelection.anchor && getSelection().focusOffset === evidenceSelection.focus &&
        getSelection().toString() === evidenceSelection.text), true, 'backward selection retained');
      await page.evaluate(() => {getSelection().removeAllRanges(); document.getElementById('analysis-evidence-enabled').click();});
      await selected(page, 'filter');
      // The existing search renderer can replace nodes; rebuilt ranges must reference current marks.
      await page.locator('#text-search').fill('feel');
      await paragraph.scrollIntoViewIfNeeded();
      await page.waitForFunction(() => [...(CSS.highlights.get('lixity-analysis-evidence') || [])].some(range =>
        range.toString() === 'feel' && range.startContainer.isConnected && document.querySelector('mark.text-hit') && range.intersectsNode(document.querySelector('mark.text-hit'))));
      await page.locator('#text-search-clear').click();
      await selected(page, 'filter');
      if (locale === 'en') {
        await paragraph.evaluate(node => {
          const panel = node.closest('.ptext'), start = node.textContent.indexOf('feel');
          LixityManuscriptLinks.marks(panel, [{start, end:start + 4}]);
          window.retainedClaimMark = node.querySelector('.manuscript-claim-hit');
        });
        await page.waitForFunction(() => [...(CSS.highlights.get('lixity-analysis-evidence') || [])].some(range => range.toString() === 'feel' && range.intersectsNode(retainedClaimMark)));
        await selectMetric(page, 'modal');
        assert.equal(await paragraph.evaluate(node => node.querySelector('.manuscript-claim-hit') === retainedClaimMark), true, 'analysis never replaces existing research marks');
        await paragraph.evaluate(node => LixityManuscriptLinks.marks(node.closest('.ptext'), []));
        await selected(page, 'filter');
        if (width === 320) {
          const drag = await point(page), session = await page.context().newCDPSession(page);
          await session.send('Input.dispatchTouchEvent', {type:'touchStart',touchPoints:[{x:drag.x,y:drag.y}]});
          await session.send('Input.dispatchTouchEvent', {type:'touchMove',touchPoints:[{x:drag.x,y:drag.y - 60}]});
          await session.send('Input.dispatchTouchEvent', {type:'touchEnd',touchPoints:[]});
          await settle(page);
          assert.equal(await page.locator('#analysis-evidence-card').isVisible(), false, 'touch scroll is not an evidence tap');
          await session.detach();
        }
      }
      if (locale === 'en' && width === 1440) {
        await page.locator('#reader-settings summary').click();
        await page.locator('#reader-text-larger').click();
        await page.locator('#reader-settings summary').click();
        await selected(page, 'filter');
        const resized = await point(page);
        await page.mouse.move(resized.x, resized.y);
        await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
        assert.equal(await page.locator('#analysis-evidence-card blockquote').textContent(), 'feel', 'cached hit geometry updates with reading font preferences');
        await page.keyboard.press('Escape');
      }
      await marksEnabled(page, false);
      await settle(page);
      assert.deepEqual(await ranges(page), []);
      await menuInspect(page); // Opting out of paint must not remove accessible inspection.
      assert.equal(await page.locator('#analysis-evidence-card blockquote').textContent(), 'feel');
      await page.keyboard.press('Escape');
      await marksEnabled(page, true);
      await page.locator('#manuscript-analysis-toggle').click();
      await settle(page);
      assert.deepEqual(await ranges(page), []);
      assert.equal(await page.locator('#analysis-evidence-card').isVisible(), false);
      assert.deepEqual(errors, []);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.close();
      console.log(`${locale}/${width}: seven metrics, pointer, keyboard, selection, search and opt-out passed`);
    }
    // The production Python matcher and renderer supply native evidence without fixture replacement.
    const native = await browser.newPage({viewport:{width:1440,height:950}, reducedMotion:'reduce'});
    await native.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures.native}));
    await native.goto('http://localhost/');
    await native.locator('#manuscript-analysis-toggle').click();
    await selected(native, 'filter');
    assert.ok((await ranges(native)).includes('feel'), 'native shared detector contributes exact filter evidence');
    await selectMetric(native, 'passive');
    await marksEnabled(native, true);
    await native.locator('.ptext-inner > p').filter({hasText:'😀 I feel'}).first().scrollIntoViewIfNeeded();
    await native.waitForFunction(() => [...(CSS.highlights.get('lixity-analysis-evidence') || [])].some(range => range.toString() === 'was opened'));
    await menuInspect(native);
    assert.equal(await native.locator('#analysis-evidence-card blockquote').textContent(), 'was opened');
    await native.keyboard.press('Escape');
    await selected(native, 'function');
    const adjacent = await native.evaluate(() => [...CSS.highlights.get('lixity-analysis-evidence')].slice(0,2).map(range => {
      const rect = range.getClientRects()[0]; return {quote:range.toString(),x:rect.left+rect.width/2,y:rect.top+rect.height/2};
    }));
    await native.mouse.move(adjacent[0].x,adjacent[0].y);
    await native.locator('#analysis-evidence-card').waitFor({state:'visible'});
    await native.mouse.move(adjacent[1].x,adjacent[1].y);
    await settle(native); // Let the alternate hover schedule, then leave before its deliberate 100ms dwell.
    await native.mouse.move(adjacent[0].x,adjacent[0].y);
    await native.waitForTimeout(150); // Observe expiry of the cancelled hover, not layout stabilization.
    assert.equal(await native.locator('#analysis-evidence-card blockquote').textContent(), adjacent[0].quote, 'returning to current match cancels adjacent pending hover');
    await native.keyboard.press('Escape');
    await selected(native, 'asl');
    await menuInspect(native);
    assert.equal(await native.locator('.analysis-evidence-sentence-words').textContent(), '4 words', 'actual first sentence token count');
    await native.getByRole('button', {name:'Next match', exact:true}).click();
    assert.equal(await native.locator('#analysis-evidence-card blockquote').textContent(), 'The gate was opened slowly.');
    assert.equal(await native.locator('.analysis-evidence-sentence-words').textContent(), '5 words', 'unequal sentence lengths come from shared tokenizer, not paragraph average');
    await native.emulateMedia({reducedMotion:'no-preference'});
    assert.equal(await native.locator('#analysis-evidence-card').evaluate(node => node.getAnimations().length), 0, 'explanation does not animate or shift when motion preference changes');
    await native.close();
    console.log('native shared evidence renderer: passed');
    // Honest fallbacks and asynchronous cancellation use the same rendered dashboard.
    for (const fault of ['adjacent', 'unsupported', 'no-crypto', 'bad-hash', 'bad-offset', 'unavailable',
      'language-unavailable', 'unmapped', 'zero', 'partial', 'stale-digest', 'forced-colors']) {
      const page = await browser.newPage({viewport:{width:320,height:480}, reducedMotion:'no-preference'});
      page.setDefaultTimeout(10000);
      if (fault === 'unsupported') await page.addInitScript(() => {window.Highlight = undefined;});
      if (fault === 'no-crypto') await page.addInitScript(() => {Object.defineProperty(crypto, 'subtle', {value:undefined});});
      if (fault === 'stale-digest') await page.addInitScript(() => {
        const digest = crypto.subtle.digest.bind(crypto.subtle);
        window.releaseEvidenceHashes = [];
        crypto.subtle.digest = (...args) => new Promise(resolve => releaseEvidenceHashes.push(() => digest(...args).then(resolve)));
      });
      await page.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures.en}));
      await page.goto('http://localhost/');
      if (fault === 'forced-colors') await page.emulateMedia({forcedColors:'active'});
      await page.evaluate(fault => {
        for (const entry of Object.values(paragraphContent)) {
          if (!entry[3]) continue;
          if (fault === 'adjacent') {
            // Independent UI transport projection: configured patterns may yield adjacent spans.
            const start = entry[3].layers.filter.spans[0].start;
            entry[3].layers.filter = {kind:'pattern',status:'available',count:2,mapped_count:2,
              spans:[{start,end:start + 2,count:1},{start:start + 2,end:start + 4,count:1}]};
          }
          if (fault === 'bad-hash') entry[3].paragraph_sha256 = '0'.repeat(64);
          if (fault === 'bad-offset') entry[3].layers.filter.spans[0].end = 999999;
          if (fault === 'unavailable') entry[3].layers.filter = {kind:'pattern',status:'unavailable',count:null,mapped_count:0,spans:[],reason:'source_mismatch'};
          if (fault === 'language-unavailable') entry[3].layers.filter = {kind:'pattern',status:'unavailable',count:null,mapped_count:0,spans:[],reason:'language_unavailable'};
          if (fault === 'unmapped') entry[3].layers.filter = {kind:'pattern',status:'unavailable',count:2,mapped_count:0,spans:[],reason:'inline_mapping_unavailable'};
          if (fault === 'zero') entry[3].layers.filter = {kind:'pattern',status:'available',count:0,mapped_count:0,spans:[]};
          if (fault === 'partial') {entry[3].layers.filter.status = 'partial'; entry[3].layers.filter.count = 2; entry[3].layers.filter.reason = 'zero_width_matches';}
        }
      }, fault);
      await page.locator('#manuscript-analysis-toggle').click();
      await marksEnabled(page, true);
      await selectMetric(page, 'filter');
      await marksEnabled(page, true);
      await page.locator('.ptext-inner > p').filter({hasText:'😀 I feel'}).first().scrollIntoViewIfNeeded();
      if (fault === 'stale-digest') {
        await page.waitForFunction(() => releaseEvidenceHashes.length > 0);
        await page.locator('#manuscript-analysis-toggle').click();
        await page.evaluate(() => Promise.all(releaseEvidenceHashes.map(release => release())));
        await settle(page);
        assert.deepEqual(await ranges(page), [], 'late verification never paints when analysis is off');
      } else {
        const noticeKeys = {'bad-hash':'evidence_mismatch', 'bad-offset':'evidence_unavailable', unavailable:'evidence_mismatch',
          'language-unavailable':'layer_language_unavailable', unmapped:'evidence_unmapped', zero:'evidence_no_visible_matches'};
        if (noticeKeys[fault]) await page.waitForFunction(key => document.getElementById('analysis-evidence-status').textContent === uiLabel(key), noticeKeys[fault]);
        if (fault === 'adjacent') await page.waitForFunction(() => CSS.highlights.get('lixity-analysis-evidence')?.size === 2);
        else if (['partial', 'forced-colors'].includes(fault)) await page.waitForFunction(() => CSS.highlights.get('lixity-analysis-evidence')?.size === 1);
        else if (fault === 'zero') {
          await settle(page);
          assert.deepEqual(await ranges(page), [], 'A measured zero paints no ranges; an empty registry entry is optional');
        }
        else {
          await page.waitForFunction(() => document.getElementById('analysis-evidence-status').textContent.length > 0);
          assert.deepEqual(await ranges(page), [], `${fault}: no invented highlight`);
        }
        if (fault === 'adjacent') {
          await page.locator('.ptext').filter({hasText:'😀 I feel'}).first().locator('.reader-paragraph-actions').click();
          await page.keyboard.press('Escape');
          const at = await page.evaluate(() => {
            const prose = document.querySelector('.ptext-inner > p'), offset = prose.textContent.indexOf('feel') + 2;
            const range = document.createRange(); range.setStart(prose.firstChild, offset); range.setEnd(prose.firstChild, offset + 1);
            const rect = range.getClientRects()[0], inspect = LixityAnalysisEvidence.inspect;
            LixityAnalysisEvidence.inspect = (...args) => {window.boundaryPoint = args[2]; return inspect(...args);};
            return {x:rect.x + .1,y:rect.y + rect.height / 2,offset};
          });
          await page.mouse.click(at.x, at.y, {button:'right'});
          await explainFromMenu(page);
          await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
          assert.equal(await page.evaluate(() => boundaryPoint.offset), at.offset, 'native caret lands exactly at adjacent span boundary after Unicode prefix');
        } else await menuInspect(page);
        if (fault === 'adjacent') assert.equal(await page.locator('#analysis-evidence-card blockquote').textContent(), 'el', 'exclusive previous end belongs to the next span');
        else if (['unsupported', 'partial', 'forced-colors'].includes(fault)) assert.equal(await page.locator('#analysis-evidence-card blockquote').textContent(), 'feel');
        else assert.equal(await page.locator('#analysis-evidence-card blockquote').count(), 0);
        if (['unavailable', 'language-unavailable', 'bad-offset'].includes(fault)) {
          assert.equal(await page.locator('#analysis-evidence-card .analysis-evidence-number').count(), 0, 'unknown measurements have no numeric result');
          assert.doesNotMatch(await page.locator('#analysis-evidence-card').textContent(), /Mapped:/, 'unknown measurements have no mapping tally');
        }
        if (fault === 'language-unavailable') assert.match(await page.locator('#analysis-evidence-card').textContent(), /unavailable for the selected language profile/);
        if (fault === 'unmapped') {
          assert.equal(await page.locator('#analysis-evidence-card .analysis-evidence-number').textContent(), '2');
          assert.match(await page.locator('#analysis-evidence-card').textContent(), /Mapped: 0 of 2/);
        }
        if (fault === 'zero') assert.match(await page.locator('#analysis-evidence-card').textContent(), /0 of 0/, 'actual measured zero remains distinct from unknown');
        if (fault === 'bad-hash') assert.match(await page.locator('#analysis-evidence-card').textContent(), /identity/);
        if (fault === 'no-crypto') assert.match(await page.locator('#analysis-evidence-card').textContent(), /HTTPS or on localhost/);
        if (fault === 'partial') assert.match(await page.locator('#analysis-evidence-card').textContent(), /1 of 2/);
        await page.keyboard.press('Escape');
        await page.locator('#tab-view-project').click();
        await settle(page);
        assert.deepEqual(await ranges(page), [], 'hidden analysis clears ranges');
        assert.equal(await page.locator('#analysis-evidence-card').isVisible(), false);
      }
      await page.close();
      console.log(`${fault}: fallback/cancellation passed`);
    }
    console.log('analysis-evidence passed; artifacts: ' + artifacts);
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode=1;});

async function verifyNativeMetricReference(page, locale, chapterFeatures) {
  const guideBase = `/guides/metrics/${locale}.html`;
  const label = await page.evaluate(() => uiLabel('metric_reference_link'));
  const source = page.url();
  assert.equal(await page.locator('body').getAttribute('data-metric-guide'), guideBase);
  await selectMetric(page, '');
  const readerGuide = page.locator('#reader-analysis-guide');
  await readerGuide.locator('summary').click();
  const measurementLink = readerGuide.locator('a[href*="/guides/metrics/"]');
  assert.ok(await measurementLink.isVisible());
  assert.equal(await measurementLink.evaluate(link => link.href), new URL(`${guideBase}#measurements`, source).href);
  assert.equal(await measurementLink.textContent(), label);
  await selectMetric(page, 'asl');
  assert.equal(await measurementLink.evaluate(link => link.href), new URL(`${guideBase}#measure-asl`, source).href);
  await readerGuide.locator('summary').click();

  assert.equal(await page.evaluate(() => LixityAnalysisEvidence.inspectSpan(document.querySelector('#chapters .ptext'), 'asl', 0)), true);
  const reference = page.locator('#analysis-evidence-card a[href*="/guides/metrics/"]');
  assert.ok(await reference.isVisible());
  assert.equal(await reference.textContent(), label);
  const [guide] = await Promise.all([page.waitForEvent('popup'), reference.click()]);
  try {
    await guide.waitForURL(new URL(`${guideBase}#measure-asl`, source).href, {waitUntil:'domcontentloaded'});
    assert.equal(await guide.locator('html').getAttribute('lang'), locale);
    assert.ok(await guide.locator('#measure-asl:target').isVisible());
    assert.ok(await guide.evaluate(() => window.opener === null));
    const layers = await page.locator('#style-layer option').evaluateAll(options => options.map(option => option.value).filter(Boolean));
    const featureIds = [...chapterFeatures, ...layers].map(key => `measure-${key}`);
    const sectionIds = ['analysis-review', 'measurements', 'flags', 'pacing', 'dist', 'sticky', 'dialogue',
      'showing', 'motifs', 'characters', 'scenes', 'style', 'matrix', 'register-targets', 'revisions'];
    assert.deepEqual(await guide.evaluate(ids => ids.filter(id => !document.getElementById(id)),
      [...new Set([...sectionIds, ...featureIds])]), [], `${locale}: all measurement links have actual destinations`);
    assert.equal(page.url(), source, 'Opening a reference leaves the workspace at the reading location');
  } finally {
    await guide.close();
    if (await page.locator('#analysis-evidence-card').isVisible()) await page.keyboard.press('Escape');
  }
}

async function verifyInlineMarkPreferences(browser, url) {
  const page = await browser.newPage({viewport:{width:320,height:480}, reducedMotion:'reduce'});
  const marks = page.locator('#analysis-evidence-enabled');
  const analysis = page.locator('#manuscript-analysis-toggle');
  const inlineOptions = ['sticky', 'dialogue_tag', 'indirect_speech', 'echo'];
  try {
    await page.goto(url);
    await analysis.click();
    for (const key of inlineOptions) {
      await selectMetric(page, key);
      assert.equal(await marks.isChecked(), true, `${key} defaults to marking on first use`);
      await marks.uncheck();
      await selectMetric(page, '');
      await selectMetric(page, 'asl');
      await selectMetric(page, key);
      assert.equal(await marks.isChecked(), false, `${key} keeps the explicit choice when revisited`);
    }
    await analysis.click();
    await analysis.click();
    assert.equal(await marks.isChecked(), false, 'Turning Analysis off and on keeps the explicit choice');
    await page.reload();
    await analysis.click();
    assert.equal(await page.locator('#style-layer').inputValue(), 'echo', 'Reload restores the selected metric');
    assert.equal(await page.locator('#layer-evidence-legend').isVisible(), false, 'Reload leaves the marked-text legend hidden');
    for (const key of inlineOptions) {
      await selectMetric(page, key);
      assert.equal(await marks.isChecked(), false, `${key} keeps its own explicit choice after reload`);
    }
    await marks.check();
    await selectMetric(page, 'sticky');
    await selectMetric(page, 'echo');
    assert.equal(await marks.isChecked(), true, 'The reader also remembers an explicit re-enable');
  } finally {await page.close();}
}

async function nativeQuotationEvidence(browser) {
  const profiles = {
    de:['„','“','Mara wartet','Bleib hier.','Komm morgen.','Mara ging.','D’Artagnan blieb allein.'],
    en:['“','”','Mara waits','Stay here.','Come tomorrow.','Mara left.','I can’t go today.'],
    es:['«','»','Mara espera','Quédate aquí.','Ven mañana.','Mara salió.','D’Artagnan siguió solo.'],
    fr:['«','»','Mara attend','Reste ici.','Viens demain.','Mara partit.','L’objectif reste clair.'],
    it:['«','»','Mara aspetta','Resta qui.','Vieni domani.','Mara partì.','L’autore resta solo.'],
    nl:['‘','’','Mara wacht','Blijf hier.','Kom morgen.','Mara vertrok.',"'s Morgens bleef zij."],
    pt:['“','”','Mara espera','Fique aqui.','Venha amanhã.','Mara saiu.','D’Artagnan ficou sozinho.'],
  };
  const source = String.raw`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
project = Path(sys.argv[1])
language, opening, closing, intro, first, second, outro, apostrophe = PROFILE
manuscript = project / 'quotation-boundaries.md'
manuscript.write_text(
    f'## Synthetic quotation chapter\n\n{intro}. {opening}{first}\n\n{second}{closing} {outro}\n\n'
    f'## Synthetic unresolved quotation\n\n{opening}{first}\n\n'
    f'## Synthetic narration chapter\n\n{apostrophe}\n\n{opening}{first}{closing} X\n',
    encoding='utf-8',
)
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.language = language
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'manuscript': str(manuscript)}), flush=True)
server.serve_forever()
`;
  for (const locale of browserLocales) {
    const [opening, closing, , first, second, , apostrophe] = profiles[locale];
    const marker = opening + '…' + closing;
    const directory = fs.mkdtempSync(path.join(artifacts, 'quotation-' + locale + '-'));
    const server = await startNativeServer(source.replace('PROFILE', JSON.stringify([locale, ...profiles[locale]])), directory);
    const before = fs.readFileSync(server.fixture.manuscript);
    try {
      for (const width of locale === 'de' || locale === 'en' ? [320, 1440] : [320]) {
        const page = await browser.newPage({viewport:{width,height:780},reducedMotion:'reduce',colorScheme:width === 320 ? 'dark' : 'light'});
        const errors = [], writes = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('request', request => {if (request.method() !== 'GET') writes.push(request.url());});
        try {
          await page.goto(server.fixture.url);
          assert.equal(await page.locator('html').getAttribute('lang'), locale);
          const evidence = await page.locator('#chapters .ptext').evaluateAll(nodes => nodes.map(node => {
            const item = paragraphContent[node.id], layer = item[3].layers.dialogue;
            return {text:item[0], count:layer.count, denominator:layer.denominator, reason:layer.reason,
              quoteRanges:layer.quotation_ranges.map(([start,end]) => Array.from(item[0]).slice(start,end).join('')),
              spans:layer.spans.map(span => ({marker:span.quotation_marker, context:span.quotation_context}))};
          }));
          assert.equal(evidence.length, 5);
          for (const [index, text] of [first, second].entries()) {
            assert.equal(evidence[index].count, 2);
            assert.equal(evidence[index].denominator, 4);
            assert.deepEqual(evidence[index].quoteRanges, [text]);
            assert.deepEqual(evidence[index].spans, [{marker, context:'in_quotation'}]);
          }
          assert.equal(evidence[2].reason, 'quotation_context_unresolved');
          assert.deepEqual(evidence[2].quoteRanges, [], 'An unclosed mark cannot extend into a later chapter');
          assert.equal(evidence[3].text, apostrophe);
          assert.equal(evidence[3].count, 0);
          assert.equal(evidence[3].reason, undefined);
          assert.equal(evidence[4].count, 2);
          assert.equal(evidence[4].denominator, 3);

          await page.locator('#manuscript-analysis-toggle').click();
          await selectMetric(page, 'dialogue');
          await marksEnabled(page, true);
          const paragraph = page.locator('#chapters .ptext').nth(1);
          await paragraph.scrollIntoViewIfNeeded();
          await page.waitForFunction(text => [...(CSS.highlights.get('lixity-analysis-evidence') || [])]
            .some(range => range.toString() === text), second);
          await paragraph.locator('.reader-paragraph-actions').click();
          await explainFromMenu(page);
          const card = page.locator('#analysis-evidence-card');
          await card.waitFor({state:'visible'});
          assert.equal(await card.locator('blockquote').textContent(), second);
          assert.equal(await card.locator('[data-quote-context]').getAttribute('data-quote-context'), 'in_quotation');
          const localized = await page.evaluate(value => ({
            share:uiCountFormat('evidence_quotation_share', 4, {quoted:2}),
            marker:uiFormat('evidence_quotation_marker', {marker:value}),
          }), marker);
          assert.ok((await card.locator('.analysis-evidence-paragraph').textContent()).includes(localized.share));
          assert.equal(await card.locator('.analysis-evidence-explanation p').first().textContent(), localized.marker);
          assert.equal(await card.evaluate(node => {
            const box = node.getBoundingClientRect();
            return box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight;
          }), true);
          await page.keyboard.press('Escape');
          await page.locator('#reader-direct-speech').click();
          assert.equal(await page.locator('#reader-direct-speech').getAttribute('aria-pressed'), 'true');
          await page.waitForFunction(expected => [...(CSS.highlights.get('lixity-direct-speech') || [])]
            .map(range => range.toString()).join('|') === expected, [first, second, first].join('|'));
          assert.equal(await page.locator('#chapters .ptext').nth(4).evaluate(node =>
            node.classList.contains('direct-speech-mixed')), true, 'A short word outside the quote is still narration');
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
          assert.deepEqual(errors, []);
          assert.deepEqual(writes, []);
        } finally {await page.close();}
      }
      assert.deepEqual(fs.readFileSync(server.fixture.manuscript), before);
    } finally {await server.close();}
  }
  console.log('Native quotation evidence: chapter boundaries, literal highlights, localized counts, punctuation and direct speech agree.');
}

async function nativeLegends(browser) {
  const classic = await browser.newPage({viewport:{width:320,height:480}});
  try {
    await classic.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures.static}));
    await classic.goto('http://localhost/');
    await classic.locator('#style-layer').selectOption('asl');
    assert.equal(await classic.locator('#layer-comparison-legend').isVisible(), true);
    assert.equal(await classic.locator('#layer-evidence-legend').isVisible(), false, 'Classic reports have no active counted-text owner');
    assert.equal(await classic.locator('#analysis-evidence-status').isVisible(), false);
  } finally {await classic.close();}
  const source = String.raw`
import json, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
from lixity.style_fingerprint import FEATURES
project = Path(sys.argv[1])
language = LOCALE
manuscript = project / 'legend.md'
prose = '## Synthetic legend chapter\n\nI feel the rain.\n\nThe gate was opened slowly beside the quiet garden.\n\nWait. The keeper watches the courtyard and listens.\n'
if language == 'generic':
    prose += '\n'.join('\nThe keeper tends the garden, opens the gate, and walks away.' for _ in range(28))
manuscript.write_text(prose, encoding='utf-8')
(project / 'lixity.toml').write_text('title = "Synthetic legend clarity"\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.language = language
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'manuscript': str(manuscript),
    'features': [field for field, _, _ in FEATURES]}), flush=True)
server.serve_forever()
`;
  for (const locale of browserLocales) {
    const directory = fs.mkdtempSync(path.join(artifacts, 'legend-' + locale + '-'));
    const server = await startNativeServer(source.replace('LOCALE', JSON.stringify(locale)), directory);
    const bytes = fs.readFileSync(server.fixture.manuscript);
    try {
      if (locale === 'de') await verifyInlineMarkPreferences(browser, server.fixture.url);
      const cases = [{width:1440}, {width:320}];
      if (locale === 'de' || locale === 'fr') cases.push({width:390});
      if (locale === 'en') cases.push({width:320, fault:'unsupported'}, {width:320, fault:'missing'});
      for (const {width, fault} of cases) {
        const page = await browser.newPage({viewport:{width,height:width === 320 ? 480 : 950}, reducedMotion:'reduce', colorScheme:width === 320 ? 'dark' : 'light'});
        const errors = [], writes = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('console', message => {if (['error', 'warning'].includes(message.type())) errors.push(message.text());});
        page.on('request', request => {if (request.method() !== 'GET') writes.push(request.url());});
        if (fault === 'unsupported') await page.addInitScript(() => {window.Highlight = undefined;});
        try {
          await page.goto(server.fixture.url);
          assert.equal(new URL(page.url()).origin, server.fixture.url);
          assert.match(await page.title(), /Synthetic legend clarity/);
          assert.equal(await page.locator('h1').textContent(), 'Synthetic legend clarity');
          const before = await page.locator('#chapters .ptext').evaluateAll(nodes => nodes.map(node => ({id:node.id, hash:node.dataset.paragraphSha256, text:node.querySelector('.ptext-inner > p').textContent})));
          if (fault === 'missing') await page.evaluate(() => {Object.values(paragraphContent).forEach(entry => {entry[3] = null;});});
          const legend = page.locator('#layer-legend'), counted = page.locator('#layer-evidence-legend'), comparison = page.locator('#layer-comparison-legend');
          assert.equal(await legend.isVisible(), false);
          await page.locator('#manuscript-analysis-toggle').click();
          assert.equal(await counted.isVisible(), false, 'Counted text is initially off');
          assert.equal(await comparison.isVisible(), true, 'Paragraph comparison is initially on');
          assert.deepEqual(await ranges(page), [], 'No counted-text ranges are painted by default');
          await marksEnabled(page, true);
          assert.equal(await counted.isVisible(), true, 'Counted text has its own visible legend');
          assert.equal(await comparison.isVisible(), true, 'Paragraph comparison has a separate visible legend');
          assert.equal(await page.locator('.toolbar > .legend').isVisible(), false, 'An active metric hides the unrelated tense key in reading');
          const labels = await page.evaluate(() => ({counted:uiLabel('legend_counted_text'), comparison:uiLabel('legend_paragraph_comparison')}));
          assert.equal(await counted.locator('strong').textContent(), labels.counted);
          assert.equal(await comparison.locator('strong').first().textContent(), labels.comparison);
          assert.equal(await counted.locator('.analysis-evidence-swatch').evaluate(node => getComputedStyle(node).textDecorationLine.includes('underline')), true);
          if (width === 1440) await verifyNativeMetricReference(page, locale, server.fixture.features);
          for (const key of ['asl', 'passive']) {
            await selectMetric(page, key);
            await marksEnabled(page, true);
            const current = await page.locator('#style-layer option:checked').evaluate(node => ({title:node.textContent,hint:node.dataset.hint}));
            assert.equal(await page.locator('#layer-comparison-hint').textContent(), current.hint);
            const guide = legend.locator('.layer-comparison-note');
            assert.equal(await guide.evaluate(node => node.open), false, 'detailed counting/comparison guidance stays secondary by default');
            assert.equal(await page.locator('#layer-comparison-hint').isVisible(), false);
            await guide.locator('summary').click();
            assert.equal(await page.locator('#layer-comparison-hint').isVisible(), true);
            assert.ok((await page.locator('#layer-evidence-hint').textContent()).includes(current.title));
            await guide.locator('summary').click();
          }
          await page.locator('#analysis-comparison-enabled').uncheck();
          assert.equal(await comparison.isVisible(), false, 'the comparison switch controls its own legend');
          assert.equal(await counted.isVisible(), true, 'disabling paragraph comparison retains counted-text explanation');
          assert.equal(await page.locator('#analysis-evidence-enabled').isChecked(), true);
          assert.equal(await page.locator('.reader-comparison-value:visible').count(), 0, 'disabled comparison hides raw paragraph buttons');
          await page.locator('#analysis-comparison-enabled').check();
          assert.equal(await comparison.isVisible(), true);
          if (fault) {
            await page.locator('#chapters .ptext').first().scrollIntoViewIfNeeded();
            await page.waitForFunction(() => document.getElementById('analysis-evidence-status').textContent.length > 0);
            assert.equal(await page.locator('#analysis-evidence-status').isVisible(), true);
            assert.equal(await page.locator('#reader-analysis-settings').isVisible(), true);
            assert.equal(await page.locator('#analysis-evidence-status').evaluate(node => Boolean(node.closest('#reader-analysis-settings'))), false, 'Unavailable marks are explained outside the direct analysis controls');
            assert.equal(await page.evaluate(() => CSS.highlights?.get('lixity-analysis-evidence')?.size || 0), 0);
          }
          await openAnalysisSettings(page); await page.locator('#analysis-evidence-enabled').uncheck();
          await page.keyboard.press('Escape');
          assert.equal(await counted.isVisible(), false);
          assert.equal(await comparison.isVisible(), true, 'Disabling counted marks retains paragraph comparisons');
          await page.reload(); await page.locator('#manuscript-analysis-toggle').click();
          assert.equal(await counted.isVisible(), false, 'Reload preserves the unchecked preference');
          assert.equal(await page.locator('#style-layer').inputValue(), 'passive');
          await openAnalysisSettings(page); await page.locator('#analysis-evidence-enabled').check();
          await page.keyboard.press('Escape');
          assert.equal(await counted.isVisible(), true);
          await legend.evaluate(node => {
            const toolbar = document.getElementById('manuscript-reader-controls').getBoundingClientRect();
            window.scrollBy({top:node.getBoundingClientRect().top - toolbar.bottom - 8,behavior:'instant'});
          });
          await settle(page);
          assert.equal(await legend.evaluate(node => {const box=node.getBoundingClientRect(); return box.left >= 0 && box.right <= innerWidth;}), true);
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
          await page.screenshot({path:path.join(artifacts, `legends-${locale}-${width}-${fault || 'mapped'}.png`)});
          await page.locator('#workbench-overview-open').click();
          assert.equal(await page.locator('[data-analysis-workflows]').isVisible(), true, 'Overview shows the guided entry points');
          assert.equal(await page.locator('.toolbar > .legend').isVisible(), false, 'Overview hides the manuscript toolbar');
          await page.locator('#workbench-overview-back').click();
          await page.locator('#manuscript-analysis-toggle').click();
          assert.equal(await legend.isVisible(), false);
          await page.locator('#manuscript-analysis-toggle').click();
          await selectMetric(page, '');
          assert.equal(await legend.isVisible(), false);
          assert.equal(await page.locator('.toolbar > .legend').isVisible(), true, 'Analysis without a selected metric shows the tense key beside the manuscript');
          assert.deepEqual(await page.locator('#chapters .ptext').evaluateAll(nodes => nodes.map(node => ({id:node.id, hash:node.dataset.paragraphSha256, text:node.querySelector('.ptext-inner > p').textContent}))), before);
          assert.deepEqual(errors, []); assert.deepEqual(writes, []);
        } finally {await page.close();}
      }
      assert.deepEqual(fs.readFileSync(server.fixture.manuscript), bytes);
    } finally {await server.close();}
  }
  const directory = fs.mkdtempSync(path.join(artifacts, 'legend-generic-'));
  const server = await startNativeServer(source.replace('LOCALE', JSON.stringify('generic')), directory);
  const page = await browser.newPage({viewport:{width:320,height:480}, reducedMotion:'reduce'});
  try {
    await page.goto(server.fixture.url);
    await page.locator('#manuscript-analysis-toggle').click();
    await selectMetric(page, 'passive');
    const unavailable = await page.evaluate(() => uiLabel('layer_language_unavailable'));
    assert.equal(await page.locator('#style-layer option:checked').getAttribute('data-available'), '0');
    assert.equal(await page.locator('#layer-language-unavailable').textContent(), unavailable);
    assert.equal(await page.locator('#layer-language-unavailable').isVisible(), true);
    assert.equal(await page.locator('#analysis-evidence-enabled').isDisabled(), true);
    assert.equal(await page.locator('#layer-comparison-legend').isVisible(), false);
    const guide = page.locator('#reader-analysis-guide');
    await guide.locator('summary').click();
    assert.ok((await guide.locator('#reader-analysis-guide-state').textContent()).includes(unavailable));
    assert.equal(await guide.locator('#reader-metric-reference').evaluate(link => link.href),
      new URL('/guides/metrics/en.html#measure-passive', page.url()).href);
    await guide.locator('summary').click();
    await page.locator('.ptext').first().locator('.reader-paragraph-actions').click();
    await explainFromMenu(page);
    const card = page.locator('#analysis-evidence-card');
    await card.waitFor({state:'visible'});
    assert.equal(await card.locator('.analysis-evidence-warning').textContent(), unavailable);
    assert.equal(await card.locator('.analysis-evidence-number').count(), 0);
    await page.keyboard.press('Escape');
    await selectMetric(page, 'asl');
    assert.equal(await page.locator('#analysis-evidence-enabled').isDisabled(), false);
    assert.equal(await page.locator('#layer-language-unavailable').isVisible(), false);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    // The full explanation precedes the manuscript. The native selector still
    // exposes the short status once that explanation has scrolled off screen.
    for (const width of [320,1440]) {
      await page.setViewportSize({width,height:720});
      await page.locator('.ptext').nth(16).evaluate(node => node.scrollIntoView({block:'center',behavior:'instant'}));
      await selectMetric(page, 'passive');
      const state = await page.locator('#style-layer').evaluate(select => {
        const option = select.selectedOptions[0];
        const picker = select.getBoundingClientRect();
        const note = document.getElementById('layer-language-unavailable').getBoundingClientRect();
        const style = getComputedStyle(select);
        const ctx = document.createElement('canvas').getContext('2d');
        ctx.font = [style.fontWeight,style.fontSize,style.fontFamily].join(' ');
        const shortStatus = uiLabel('metric_context_missing');
        return {caption:option.textContent, shortStatus,
          statusFits:ctx.measureText(shortStatus).width <= select.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
          pickerInView:picker.top >= 0 && picker.bottom <= innerHeight && picker.left >= 0 && picker.right <= innerWidth,
          noteAboveViewport:note.bottom < 0, fits:document.documentElement.scrollWidth <= innerWidth};
      });
      assert.ok(state.noteAboveViewport && state.pickerInView, `Depth and sticky selection at ${width}px`);
      assert.ok(state.caption.startsWith(state.shortStatus + ' · ') && state.statusFits && state.fits,
        `Unavailable status stays visible without widening the selector at ${width}px`);
      await selectMetric(page, 'asl');
      assert.ok(!(await page.locator('#style-layer option:checked').textContent()).includes(state.shortStatus));
    }
  } finally {
    await page.close();
    await server.close();
  }
  console.log('Native legends: distinct counted text/comparison keys, visible color meaning, Off/None/unchecked persistence, unavailable marks, and source identity passed at desktop/mobile. ' + artifacts);
}
