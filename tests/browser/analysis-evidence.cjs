// Exact evidence highlights preserve prose nodes and expose the same explanation to pointer and keyboard users.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
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
text = '# Synthetic evidence\\n\\n😀 I feel the gate. The gate was opened slowly. "I can wait," she said. The organization might return. ' + 'The patient keeper watches the garden and the quiet river. ' * 8
analysis = analyze_document(text, CorpusConfig(language='en'), resolve_thresholds(project_config={}), include_evidence=True)
result = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    page = render_dashboard(analysis.chapters, analysis.paragraphs, metrics=analysis.metrics,
        fingerprint=analysis.fingerprint, paragraph_evidence=analysis.evidence, title='Synthetic evidence', controls=True,
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
  await page.locator('#style-layer').selectOption(key);
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
async function menuInspect(page, keyboard = false) {
  const panel = page.locator('.ptext').filter({hasText:'😀 I feel'}).first();
  if (keyboard) {
    await panel.locator('.reader-paragraph-actions').focus();
    await page.keyboard.press('Enter');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
  } else {
    await panel.locator('.reader-paragraph-actions').click();
    await page.locator('[data-reader-action="evidence"]').click();
  }
  await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
}
(async () => {
  const browser = await launchChromium();
  try {
    const long = await browser.newPage({viewport:{width:1440,height:950}, reducedMotion:'reduce'});
    await long.route('**/*', route => route.fulfill({contentType:'text/html',body:fixtures.longNative}));
    await long.goto('http://localhost/');
    await long.locator('#manuscript-analysis-toggle').click();
    await long.locator('#style-layer').selectOption('filter');
    await long.locator('.reader-paragraph-actions').first().click();
    await long.locator('[data-reader-action="evidence"]').click();
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
    await long.locator('#style-layer').selectOption('function');
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
        await page.locator('[data-reader-action="evidence"]').click();
        await page.locator('#analysis-evidence-card').waitFor({state:'visible'});
      } else await menuInspect(page, true);
      assert.equal(await page.locator('#analysis-evidence-card blockquote').textContent(), 'feel');
      assert.equal(await page.locator('#analysis-evidence-card button').first().evaluate(node => node === document.activeElement), true);
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
        await page.locator('#style-layer').selectOption('modal');
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
      await page.locator('#analysis-evidence-enabled').uncheck();
      await settle(page);
      assert.deepEqual(await ranges(page), []);
      await menuInspect(page); // Opting out of paint must not remove accessible inspection.
      assert.equal(await page.locator('#analysis-evidence-card blockquote').textContent(), 'feel');
      await page.keyboard.press('Escape');
      await page.locator('#analysis-evidence-enabled').check();
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
    await native.locator('#style-layer').selectOption('passive');
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
    for (const fault of ['unsupported', 'bad-hash', 'bad-offset', 'unavailable', 'zero', 'partial', 'stale-digest', 'forced-colors']) {
      const page = await browser.newPage({viewport:{width:320,height:480}, reducedMotion:'no-preference'});
      page.setDefaultTimeout(10000);
      if (fault === 'unsupported') await page.addInitScript(() => {window.Highlight = undefined;});
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
          if (fault === 'bad-hash') entry[3].paragraph_sha256 = '0'.repeat(64);
          if (fault === 'bad-offset') entry[3].layers.filter.spans[0].end = 999999;
          if (fault === 'unavailable') entry[3].layers.filter = {kind:'pattern',status:'unavailable',count:null,mapped_count:0,spans:[],reason:'source_mismatch'};
          if (fault === 'zero') entry[3].layers.filter = {kind:'pattern',status:'available',count:0,mapped_count:0,spans:[]};
          if (fault === 'partial') {entry[3].layers.filter.status = 'partial'; entry[3].layers.filter.count = 2; entry[3].layers.filter.reason = 'zero_width_matches';}
        }
      }, fault);
      await page.locator('#manuscript-analysis-toggle').click();
      await page.locator('#style-layer').selectOption('filter');
      await page.locator('.ptext-inner > p').filter({hasText:'😀 I feel'}).first().scrollIntoViewIfNeeded();
      if (fault === 'stale-digest') {
        await page.waitForFunction(() => releaseEvidenceHashes.length > 0);
        await page.locator('#manuscript-analysis-toggle').click();
        await page.evaluate(() => Promise.all(releaseEvidenceHashes.map(release => release())));
        await settle(page);
        assert.deepEqual(await ranges(page), [], 'late verification never paints when analysis is off');
      } else {
        if (['partial', 'forced-colors'].includes(fault)) await page.waitForFunction(() => CSS.highlights.get('lixity-analysis-evidence')?.size === 1);
        else if (fault === 'zero') await page.waitForFunction(() => CSS.highlights.has('lixity-analysis-evidence') && CSS.highlights.get('lixity-analysis-evidence').size === 0);
        else {
          await page.waitForFunction(() => document.getElementById('analysis-evidence-status').textContent.length > 0);
          assert.deepEqual(await ranges(page), [], `${fault}: no invented highlight`);
        }
        await menuInspect(page);
        if (['unsupported', 'partial', 'forced-colors'].includes(fault)) assert.equal(await page.locator('#analysis-evidence-card blockquote').textContent(), 'feel');
        else assert.equal(await page.locator('#analysis-evidence-card blockquote').count(), 0);
        if (fault === 'unavailable') assert.doesNotMatch(await page.locator('#analysis-evidence-card').textContent(), /Mapped:/, 'unavailable/source mismatch must not present measured zero coverage');
        if (fault === 'zero') assert.match(await page.locator('#analysis-evidence-card').textContent(), /0 of 0/, 'actual measured zero remains distinct from unknown');
        if (fault === 'bad-hash') assert.match(await page.locator('#analysis-evidence-card').textContent(), /identity/);
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
