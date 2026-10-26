const {openAnalysisSettings, selectMetric} = require('./support/analysis-controls.cjs');
// Exact evidence highlights preserve prose nodes and expose the same explanation to pointer and keyboard users.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
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
result = {}
result['static'] = dashboard(text, language='en', title='Synthetic static comparison')
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    page = render_dashboard(analysis.chapters, analysis.paragraphs, metrics=analysis.metrics,
        fingerprint=analysis.fingerprint, paragraph_evidence=analysis.evidence, title='Synthetic evidence', controls=True,
        labels={**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}, language_key=locale)
    result['native-' + locale] = page
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
            layers[key] = {'status':'available', 'kind':kind, 'count':count, 'mapped_count':count, 'spans':[{'start':start,'end':start+len(match_text),'count':count}]}
        evidence = {'schema_version':'paragraph-evidence/1', 'paragraph_sha256':hashlib.sha256(paragraph.encode()).hexdigest(),
            'offset_unit':'unicode_codepoint', 'layers': layers}
        entry[3:4] = [evidence]
    page = page[:match.start(2)] + json.dumps(content).replace('</', '<\\/') + page[match.end(2):]
    result[locale] = page
long_text = '# Long evidence\\n\\nI feel the gate. ' + 'The quiet keeper watches the garden and waits beside the river. ' * 250 + 'I felt the rain.'
long_analysis = analyze_document(long_text, CorpusConfig(language='en'), resolve_thresholds(project_config={}), include_evidence=True)
result['longNative'] = render_dashboard(long_analysis.chapters, long_analysis.paragraphs, metrics=long_analysis.metrics,
    fingerprint=long_analysis.fingerprint, paragraph_evidence=long_analysis.evidence, title='Long evidence', controls=True,
    labels={**get_language_profile('en').labels, **WORKSPACE_LABELS['en']}, language_key='en')
comparison_text = '# Comparable synthetic paragraphs\\n\\nWait.\\n\\nKeeper waits.\\n\\n' + 'The quiet keeper follows the river through the garden and listens to the rain ' * 5 + '.'
comparison = analyze_document(comparison_text, CorpusConfig(language='en'), resolve_thresholds(project_config={}), include_evidence=True)
result['comparable'] = render_dashboard(comparison.chapters, comparison.paragraphs, metrics=comparison.metrics,
    fingerprint=comparison.fingerprint, paragraph_evidence=comparison.evidence, title='Comparable synthetic paragraphs', controls=True,
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
  if (keyboard) {
    await panel.locator('.reader-paragraph-actions').focus();
    await page.keyboard.press('Enter');
  } else await panel.locator('.reader-paragraph-actions').click();
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
      assert.equal(await card.locator('.analysis-evidence-close').evaluate(node => {const box=node.getBoundingClientRect(); return box.width >= 44 && box.height >= 44;}), true, 'compact close remains an accessible touch target');
      assert.equal(await card.evaluate(node => {const box=node.getBoundingClientRect(); return box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight;}), true, 'native localized card remains inside viewport');
      if (count === 4) await page.screenshot({path:path.join(artifacts, `sentence-${locale}-${width}.png`)});
      await page.keyboard.press('Escape');
    }
    assert.deepEqual(errors, []); await page.close();
    console.log(`${locale}/${width}: native sentence counts and presentation passed`);
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
      assert.equal(await page.locator('#reader-analysis-settings > summary').count(), 0);
      await page.screenshot({path:path.join(artifacts, `native-settings-${width}.png`)});
      await page.keyboard.press('Escape');
      // Direct analysis controls support keyboard input without opening a popup.
      const metric = page.locator('#style-layer');
      await metric.focus(); await page.keyboard.press('End'); await page.keyboard.press('Enter');
      assert.equal(await metric.inputValue(), 'nominal', 'End selects the final metric in the grouped selector');
      await page.keyboard.press('Home'); await page.keyboard.press('ArrowDown'); await page.keyboard.press('Enter');
      assert.equal(await metric.inputValue(), 'asl');
      assert.equal(await metric.evaluate(node => node === document.activeElement), true);
      for (const id of ['analysis-evidence-enabled', 'analysis-comparison-enabled']) {
        const control = page.locator('#' + id), other = page.locator('#' + (id === 'analysis-evidence-enabled' ? 'analysis-comparison-enabled' : 'analysis-evidence-enabled'));
        await control.focus(); await page.keyboard.press('Space');
        assert.equal(await control.isChecked(), false);
        assert.equal(await other.isChecked(), true, 'the two analysis decorations have independent controls');
        assert.equal(await control.evaluate(node => node === document.activeElement), true);
        await page.keyboard.press('Space'); assert.equal(await control.isChecked(), true);
      }
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
      assert.equal(await page.locator('body').evaluate(node => node.classList.contains('layer-on')), true, 'restored metric reapplies shared paragraph layer');
      assert.equal(await page.locator('#layer-legend').isVisible(), true);
      assert.equal(await page.locator('#layer-legend-title').textContent(), 'Sentence length · words per sentence',
        'the restored metric names its raw measurement unit');
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
      await page.locator('#paragraph-filter-reset').click();
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
(async () => {
  const browser = await launchChromium();
  try {
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
        await selectMetric(page, 'nominal');
        assert.equal(await page.locator('#style-layer option:checked').textContent(), 'Nomen-Endungen');
        await page.locator('.layer-comparison-note > summary').click();
        assert.match(await page.locator('#layer-comparison-hint').textContent(), /Die Prüfung des Antrags erfolgt/);
        assert.match(await page.locator('#layer-comparison-hint').textContent(), /Gezählt werden nur/);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        await page.screenshot({path:path.join(artifacts, `german-nominal-guide-${width}.png`)});
        await page.locator('.layer-comparison-note > summary').click();
        await page.locator('.ptext').first().scrollIntoViewIfNeeded();
        await page.waitForFunction(() => [...(CSS.highlights?.get('lixity-analysis-evidence') || [])].some(range => range.toString() === 'Untersuchung'));
        assert.deepEqual(await ranges(page), ['Untersuchung'], 'German contractions are excluded from actual nominal highlights');
        await page.screenshot({path:path.join(artifacts, `german-nominal-${width}.png`)});
        await selectMetric(page, 'function');
        await page.waitForFunction(() => [...(CSS.highlights?.get('lixity-analysis-evidence') || [])].some(range => range.toString() === 'ZUR'));
        const words = await ranges(page);
        assert.ok(words.includes('ZUR') && words.includes('Zur'), 'The same contractions remain visible in the function-word measurement');
      } finally {await page.close();}
    }
    await nativeLegends(browser);
    if (process.env.LIXITY_LEGENDS_ONLY) return;
    await pendingInspectorCards(browser);
    await localizedSentenceCards(browser);
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
        assert.equal(await card.locator('.analysis-evidence-comparison-label strong').textContent(), 'z = ' + (info[2] >= 0 ? '+' : '') + info[2].toFixed(2), 'comparison exposes the existing numeric paragraph score');
        assert.match(await card.locator('.analysis-evidence-comparison-label').textContent(), index === 0 ? /below the chapter median/ : /above the chapter median/);
        assert.equal(await card.locator('.analysis-evidence-scale').getAttribute('aria-label'), info[1], 'bounded visual scale retains the full paragraph reference explanation');
        assert.equal(await card.locator('.analysis-evidence-comparison').evaluate(node => node.style.getPropertyValue('--evidence-comparison-position')), Math.max(0,Math.min(100,50 + info[2] / 2.5 * 50)) + '%', 'marker uses the same fixed ±2.5 range as the existing diverging legend');
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
      await page.close();
    }
    await nativeEntry(browser);
    const long = await browser.newPage({viewport:{width:1440,height:950}, reducedMotion:'reduce'});
    await long.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures.longNative}));
    await long.goto('http://localhost/');
    await long.locator('#manuscript-analysis-toggle').click();
    await selectMetric(long, 'filter');
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
    await long.close();
    console.log('long paragraph next-match arrival: passed');
    for (const locale of ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl']) for (const width of [1440, 320]) {
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
        await page.touchscreen.tap(at.x, at.y);
        await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
      }
      assert.equal(await page.locator('#analysis-evidence-card blockquote').textContent(), 'feel');
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
    for (const fault of ['adjacent', 'unsupported', 'no-crypto', 'bad-hash', 'bad-offset', 'unavailable', 'zero', 'partial', 'stale-digest', 'forced-colors']) {
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
          if (fault === 'zero') entry[3].layers.filter = {kind:'pattern',status:'available',count:0,mapped_count:0,spans:[]};
          if (fault === 'partial') {entry[3].layers.filter.status = 'partial'; entry[3].layers.filter.count = 2; entry[3].layers.filter.reason = 'zero_width_matches';}
        }
      }, fault);
      await page.locator('#manuscript-analysis-toggle').click();
      await selectMetric(page, 'filter');
      await page.locator('.ptext-inner > p').filter({hasText:'😀 I feel'}).first().scrollIntoViewIfNeeded();
      if (fault === 'stale-digest') {
        await page.waitForFunction(() => releaseEvidenceHashes.length > 0);
        await page.locator('#manuscript-analysis-toggle').click();
        await page.evaluate(() => Promise.all(releaseEvidenceHashes.map(release => release())));
        await settle(page);
        assert.deepEqual(await ranges(page), [], 'late verification never paints when analysis is off');
      } else {
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
        if (fault === 'unavailable') assert.doesNotMatch(await page.locator('#analysis-evidence-card').textContent(), /Mapped:/, 'unavailable/source mismatch must not present measured zero coverage');
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
project = Path(sys.argv[1])
manuscript = project / 'legend.md'
manuscript.write_text('## Synthetic legend chapter\n\nI feel the rain.\n\nThe gate was opened slowly beside the quiet garden.\n\nWait. The keeper watches the courtyard and listens.\n', encoding='utf-8')
(project / 'lixity.toml').write_text('title = "Synthetic legend clarity"\n', encoding='utf-8')
LixityServerHandler.workspace_root = str(project)
LixityServerHandler.source_input = str(manuscript)
LixityServerHandler.language = LOCALE
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1', 0), LixityServerHandler)
print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'manuscript': str(manuscript)}), flush=True)
server.serve_forever()
`;
  for (const locale of ['en', 'de', 'fr', 'es', 'it', 'pt', 'nl']) {
    const directory = fs.mkdtempSync(path.join(artifacts, 'legend-' + locale + '-'));
    const server = await startNativeServer(source.replace('LOCALE', JSON.stringify(locale)), directory);
    const bytes = fs.readFileSync(server.fixture.manuscript);
    try {
      const cases = [{width:1440}, {width:320}];
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
          assert.equal(await counted.isVisible(), true, 'Counted text has its own visible legend');
          assert.equal(await comparison.isVisible(), true, 'Paragraph comparison has a separate visible legend');
          assert.equal(await page.locator('.toolbar > .legend').isVisible(), false, 'An active metric hides the unrelated tense key in reading');
          const labels = await page.evaluate(() => ({counted:uiLabel('legend_counted_text'), comparison:uiLabel('legend_paragraph_comparison')}));
          assert.equal(await counted.locator('strong').textContent(), labels.counted);
          assert.equal(await comparison.locator('strong').first().textContent(), labels.comparison);
          assert.equal(await counted.locator('.analysis-evidence-swatch').evaluate(node => getComputedStyle(node).textDecorationLine.includes('underline')), true);
          for (const key of ['asl', 'passive']) {
            await selectMetric(page, key);
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
          assert.equal(await page.locator('.toolbar > .legend').isVisible(), true, 'Overview retains the tense key');
          await page.locator('#workbench-overview-back').click();
          await page.locator('#manuscript-analysis-toggle').click();
          assert.equal(await legend.isVisible(), false);
          await page.locator('#manuscript-analysis-toggle').click();
          await selectMetric(page, '');
          assert.equal(await legend.isVisible(), false);
          assert.deepEqual(await page.locator('#chapters .ptext').evaluateAll(nodes => nodes.map(node => ({id:node.id, hash:node.dataset.paragraphSha256, text:node.querySelector('.ptext-inner > p').textContent}))), before);
          assert.deepEqual(errors, []); assert.deepEqual(writes, []);
        } finally {await page.close();}
      }
      assert.deepEqual(fs.readFileSync(server.fixture.manuscript), bytes);
    } finally {await server.close();}
  }
  console.log('Native legends: distinct counted text/comparison keys, visible color meaning, Off/None/unchecked persistence, unavailable marks, and source identity passed in seven locales at desktop/mobile. ' + artifacts);
}
