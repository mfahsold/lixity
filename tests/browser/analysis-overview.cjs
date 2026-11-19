// Synthetic overview: retained measurements, readable long lists and chapter identity.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');

const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-analysis-overview-'));
const fixtures = pythonFixture(`
import json
from lixity.characters import presence_report
from lixity.dialogue import dialogue_report
from lixity.language import LANGUAGE_PROFILES
from lixity.models import CorpusConfig
from lixity.motifs import motif_report
from lixity.pacing import pacing_report
from lixity.scenes import scene_report_for_display
from lixity.showing import showing_report
from lixity.pipeline import analyze_document
from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui import render_dashboard
from lixity.ui.narration import render_showing_panel
from tests.locales import LOCALES
prose = [
    "Mara walks to the gate. She watches the street. I see the light. I go to the house. I see the tree. I went to the house. I saw the tree. I heard the bell. I saw the light. I went to the gate. ",
    "The observer believed that the decision was considered carefully, because every detail of the explanation seemed important to the people who waited inside the quiet room. Mara carried the lamp. ",
    "Rain fell. A door shut. The bell rang. Footsteps stopped. A bird called. Tomas shut the gate. ",
]
chunks = []
for number in range(1, 17):
    paragraphs = [prose[(number + paragraph) % 3] * 4 for paragraph in range(5)]
    paragraphs.insert(2, ('"Come here," Mara said. "Leave the lamp beside the gate." Tomas nodded. ') * (number + 1))
    chunks.append(f"## Chapter {number}: A synthetic title for table review\\n\\n" + "\\n\\n".join(paragraphs))
chunks.append("## Short observation\\n\\nMara waits.")
text = "\\n\\n".join(chunks)
config = CorpusConfig(language="en")
analysis = analyze_document(text, config, FingerprintThresholds(z_mild=100, z_strong=100))
reports = dict(dialogue=dialogue_report(text, config).to_dict(),
               motifs=motif_report(text, {"Gate": r"\\bgate\\b"}, config).to_dict(),
               scenes=scene_report_for_display(text, config, None),
               characters=presence_report(text, ["Mara", "Tomas", "Unmentioned name"], config),
               pacing=pacing_report(text, config).to_dict(),
               showing=showing_report(text, config, metrics=analysis.metrics).to_dict())
def render(language, controls):
    return render_dashboard(analysis.chapters, analysis.paragraphs, metrics=analysis.metrics,
        fingerprint=analysis.fingerprint, labels=LANGUAGE_PROFILES[language].labels,
        language_key=language, controls=controls, markers=[], title="Synthetic analysis overview", **reports)
print(json.dumps({"locales": {language: render(language, True) for language in LOCALES}, "standalone": render("en", False),
    "unavailable": {language: render_showing_panel({"chapter_list": [{"chapter_num": 1, "balance": 0.0}]},
        LANGUAGE_PROFILES[language].labels, language) for language in LOCALES},
    "flags": sum(paragraph.is_flagged for paragraph in analysis.paragraphs)}))
`, {root});

async function textLines(locator) {
  return locator.evaluate(element => {
    const range = document.createRange();
    range.selectNodeContents(element);
    return [...new Set(Array.from(range.getClientRects(), box => Math.round(box.top)))].length;
  });
}

async function pinnedIdentity(page, panel, cellIndex) {
  const region = page.locator(`#${panel} .table-wrap`).first();
  await region.scrollIntoViewIfNeeded();
  await region.evaluate(element => { element.scrollLeft = element.scrollWidth; });
  const geometry = await region.evaluate((element, index) => {
    const box = element.getBoundingClientRect();
    const cell = element.querySelector('tbody tr').children[index].getBoundingClientRect();
    return {scrollLeft: element.scrollLeft, viewport: box.width, content: element.scrollWidth,
      left: cell.left - box.left, right: cell.right - box.left};
  }, cellIndex);
  if (geometry.content > geometry.viewport) {
    assert.ok(geometry.scrollLeft > 0, `${panel}: the table actually scrolled`);
    assert.ok(geometry.left >= -1 && geometry.right <= geometry.viewport + 1,
      `${panel}: record identity remains visible after scrolling: ${JSON.stringify(geometry)}`);
  }
}

(async () => {
  const browser = await launchChromium();
  const errors = [];
  let writes = 0;
  try {
    for (const [locale, html] of Object.entries(fixtures.locales)) for (const width of
      (locale === 'en' ? [1440,1280,1024,768,390,320] : [1440,320])) {
      const page = await browser.newPage({viewport: {width, height: 900}, hasTouch: true, reducedMotion: 'reduce'});
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://lixity.test/**', route => {
        if (route.request().method() !== 'GET') writes++;
        return route.fulfill(route.request().url().includes('/api/')
          ? {json: {ok: true, locked: true, records: []}} : {contentType: 'text/html', body: html});
      });
      await page.addInitScript(() => localStorage.setItem('lixity:hide-review-guide', '1'));
      await page.goto('http://lixity.test/');
      assert.equal(await page.title(), 'Synthetic analysis overview – ' +
        (await page.locator('.workspace-shell .product-name').textContent()).trim(),
        'Browser history identifies the manuscript and product without repeating an analysis slogan');
      await page.locator('#workbench-overview-open').click();
      const navigation = page.locator('[data-analysis-workflows]');
      const entries = navigation.locator('[data-analysis-workflow]');
      const visiblePanels = () => page.locator('#manuscript-analysis-panels > :visible').count();
      assert.equal(await entries.count(), 3, 'The overview starts with three editorial workflows');
      assert.deepEqual(await entries.evaluateAll(nodes => nodes.map(n => n.dataset.analysisWorkflow)),
        ['review', 'compare', 'explore']);
      assert.equal(await visiblePanels(), 0, 'The initial overview does not expand every analysis panel');
      assert.equal(await page.locator('#analysis-sections').isVisible(), false,
        'The exhaustive section navigation is replaced by the workflow chooser');
      assert.equal(await page.locator('#analysis-outline-nav').isVisible(), false,
        'A second exhaustive feature list does not compete with the workflow chooser');
      const orientation = await navigation.evaluate(nav => {
        const bounds = nav.getBoundingClientRect();
        return {bounds:bounds.toJSON(), width:nav.clientWidth, content:nav.scrollWidth,
          entries:[...nav.querySelectorAll('[data-analysis-workflow]')].map(a=>a.getBoundingClientRect().toJSON())};
      });
      assert.ok(orientation.content <= orientation.width + 1, 'Workflow choices fit without horizontal clipping');
      assert.ok(orientation.entries.every(rect=>rect.left>=orientation.bounds.left-1 && rect.right<=orientation.bounds.right+1),
        'Every workflow label is wholly visible');
      if (width<=390) assert.equal(new Set(orientation.entries.map(rect=>Math.round(rect.top))).size,3,
        'Mobile workflow entries form a readable single column');
      async function selectSection(target, scroll = true) {
        const choice = navigation.locator(`[data-analysis-section-target="${target}"]`);
        const workflow = await choice.getAttribute('data-analysis-section-workflow');
        await navigation.locator(`[data-analysis-workflow="${workflow}"]`).click();
        await choice.click();
        assert.equal(await visiblePanels(), 1, `${target}: only one major analysis panel is active`);
        assert.equal(await page.locator(`#${target}`).isVisible(), true, `${target}: selected panel is visible`);
        assert.equal(await choice.getAttribute('aria-pressed'), 'true');
        assert.equal(await navigation.locator('[data-analysis-workflow][aria-pressed=true]').count(), 1);
        if (scroll) await page.locator(`#${target}`).scrollIntoViewIfNeeded();
      }
      if ((locale === 'en' || locale === 'de') && [1440, 320].includes(width)) {
        assert.equal(await page.locator('#dimensions').isVisible(), false, 'Style measurements start concealed');
        await selectSection('style');
        await page.locator('#style-tab-dimensions').click();
        assert.equal(await page.locator('#dimensions').isVisible(), true, 'The comparison workflow reveals the style space');
        assert.equal(await page.locator('#style-tab-dimensions').getAttribute('aria-selected'), 'true');
        for (const [kind, sign] of [['pos', '+'], ['neg', '−']]) {
          const loading = page.locator(`#dimensions .load.${kind}[role=button]`).first();
          assert.ok(await loading.count(), `The fixture contains a ${kind} loading`);
          assert.equal((await loading.locator('.load-sign').textContent()).trim(), sign,
            'Loading direction remains visible independently of its color');
          assert.ok((await loading.ariaSnapshot()).includes(sign), 'Loading direction is present in its accessible name');
        }
        await page.locator('#workbench-overview-back').click();
        assert.equal(await page.locator('#manuscript-analysis-toggle').getAttribute('aria-pressed'), 'false',
          'Returning restores the previous reading choice');
        await page.locator('#workbench-overview-open').click();
      }
      if (locale === 'en' || locale === 'de') await navigation.screenshot({
        path:path.join(artifacts, `navigation-${locale}-${width}.png`)});
      for (const target of ['flags','pacing','scenes','dialogue','dist','showing','characters','motifs','style','matrix']) {
        await selectSection(target);
      }
      await selectSection('showing');
      const signalPanel = page.locator('#showing');
      const signalMethod = signalPanel.locator('details.signal-method');
      const signalSummary = signalMethod.locator('summary');
      const signalBrief = signalPanel.locator(':scope > p.ctl-note').first();
      const measurementsBefore = await signalPanel.locator('.kpi-row').textContent();
      assert.equal(await signalMethod.evaluate(element=>element.open), false);
      assert.ok(await signalBrief.isVisible(), `${locale}: comparison limits remain visible`);
      assert.equal(await signalMethod.locator('p').isVisible(), false);
      if ((locale === 'de' || locale === 'en') && (width === 1440 || width === 320))
        await signalPanel.screenshot({path:path.join(artifacts, `signals-${locale}-${width}.png`)});
      if (width === 320) await signalSummary.tap();
      else { await signalSummary.focus(); await page.keyboard.press('Enter'); }
      assert.equal(await signalMethod.evaluate(element=>element.open), true);
      assert.ok(await signalMethod.locator('p').isVisible(), `${locale}: method is available on demand`);
      assert.ok(await signalBrief.isVisible());
      assert.equal(await signalPanel.locator('.kpi-row').textContent(), measurementsBefore,
        'Opening help does not alter measurements');
      if (width === 320) await signalSummary.tap();
      else { await signalSummary.focus(); await page.keyboard.press('Enter'); }
      assert.equal(await signalMethod.evaluate(element=>element.open), false);
      const neg = signalPanel.locator('.signal-bar .signal-negative').first();
      const pos = signalPanel.locator('.signal-bar .signal-positive').first();
      assert.ok(await neg.count() && await pos.count(), 'Synthetic values cover both directions');
      for (const scheme of ['light', 'dark']) {
        await page.emulateMedia({colorScheme: scheme});
        const bars = await Promise.all([neg, pos].map(locator=>locator.evaluate(element=>{
          const bar = element.parentElement.getBoundingClientRect();
          const part = element.getBoundingClientRect();
          return {left:part.left, right:part.right, middle:bar.left + bar.width/2,
            color:getComputedStyle(element).backgroundColor};
        })));
        assert.ok(Math.abs(bars[0].right-bars[0].middle) < 1 && Math.abs(bars[1].left-bars[1].middle) < 1,
          `${locale}/${width}/${scheme}: negative and positive meet at zero`);
        assert.notEqual(bars[0].color, bars[1].color, 'Directions use distinct comparison colors');
        if (scheme === 'dark' && locale === 'de' && (width === 320 || width === 1440))
          await signalPanel.screenshot({path:path.join(artifacts, `signals-${locale}-${width}-dark.png`)});
      }
      await page.emulateMedia({colorScheme:'light'});
      await selectSection('analysis-measurements');
      const measurements = page.locator('#analysis-measurements');
      assert.equal(await measurements.getAttribute('open'), '', 'Selecting measurements opens the overview');
      assert.ok(await measurements.locator('.kpi').first().isVisible());
      assert.equal(await page.locator('#flags').isVisible(), false, 'The measurement view does not also expand flag review');
      const summary = measurements.locator(':scope > summary');
      assert.ok((await summary.textContent()).trim().length > 0);
      const vocabulary = measurements.locator('#kpi-lexis-drawer');
      assert.equal(await vocabulary.locator('.kpi').first().isVisible(), false, 'Vocabulary indices stay folded');
      if (locale === 'de' && [1440, 320].includes(width))
        await measurements.screenshot({path:path.join(artifacts, `measurements-${locale}-${width}.png`)});
      await vocabulary.locator('summary').focus();
      await page.keyboard.press('Enter');
      assert.ok(await vocabulary.locator('.kpi').first().isVisible(), 'Vocabulary indices can be opened with the keyboard');
      const measurementClipping = await measurements.locator('.kpi:visible, summary:visible, .panel-guide:visible').evaluateAll(nodes =>
        nodes.filter(node => node.scrollWidth > node.clientWidth + 1).map(node => node.textContent));
      assert.deepEqual(measurementClipping, [], `${locale}/${width}: measurement labels and instructions fit`);
      const readability = measurements.locator('#readability-measurements');
      assert.ok(await readability.isVisible(), 'Readability formulas appear when measurements open');
      assert.deepEqual(await readability.locator('dt').allTextContents(), ['Flesch Reading Ease', 'LIX'],
        'Each formula appears once and retains its measured formula name in every interface locale');
      const clipped = await readability.locator('h3, p, dl, dl > div, dt, dd').evaluateAll(nodes =>
        nodes.filter(node => node.scrollWidth > node.clientWidth + 1).map(node => node.textContent));
      assert.deepEqual(clipped, [], `${locale}/${width}: localized readability labels fit the available width`);
      if (locale === 'de' && [1440, 320].includes(width))
        await readability.screenshot({path:path.join(artifacts, `readability-${locale}-${width}.png`)});
      await page.locator('#workbench-overview-back').click();
      await page.locator('#workbench-overview-open').click();
      assert.equal(await measurements.evaluate(element => element.open), true, 'Returning preserves the native disclosure state');
      await summary.focus();
      await page.keyboard.press('Enter');
      assert.equal(await measurements.evaluate(element => element.open), false);

      await selectSection('flags');
      const flags = page.locator('#flags .flags-wrap');
      assert.equal(await flags.getAttribute('role'), 'region');
      assert.ok(await flags.getAttribute('aria-label'));
      assert.equal(await page.locator('#flags tbody tr').count(), fixtures.flags);
      assert.equal(Number(await page.locator('#flags h2 .badge').textContent()), fixtures.flags);
      assert.equal(await page.locator('#flags [data-marker-kind]').count(), 0,
        'Observations do not directly generate manuscript tasks');
      const reason = page.locator('#flags tbody tr:first-child .triage-reason');
      const openedPassages = await page.locator('#chapters .ptext.open').count();
      await reason.locator('summary').click();
      assert.ok(await reason.locator('p').isVisible());
      assert.equal(await page.locator('#chapters .ptext.open').count(), openedPassages,
        'Explaining an observation must not also follow the flag row');
      await reason.locator('summary').click();
      assert.ok(await page.locator('#workbench-overview-back').isVisible(), 'Inspection retains the overview');
      await flags.scrollIntoViewIfNeeded();
      assert.equal(await textLines(page.locator('#flags tbody tr:first-child .badge')), 1,
        `${locale} at ${width}: severity must remain readable on one line`);
      assert.equal(await textLines(page.locator('#flags tbody tr:first-child td').nth(2)), 1,
        `${locale} at ${width}: line anchor must stay on one line`);
      assert.ok(await page.locator('#flags tbody tr:first-child .flag-excerpt').evaluate(element => element.getBoundingClientRect().width >= 200),
        `${locale} at ${width}: the excerpt receives usable width`);
      assert.ok(await flags.evaluate(element => element.scrollHeight > element.clientHeight), 'Long flags remain bounded');
      await flags.focus();
      await page.keyboard.press('PageDown');
      await page.waitForFunction(() => document.querySelector('#flags .flags-wrap').scrollTop > 0);
      await flags.evaluate(element => { element.scrollTop = element.scrollHeight; });
      assert.ok(await flags.evaluate(element => {
        const last = element.querySelector('tbody tr:last-child').getBoundingClientRect();
        return last.bottom <= element.getBoundingClientRect().bottom + 1;
      }), 'The final flag remains reachable');
      await page.mouse.move(0, 0);
      await page.evaluate(() => document.activeElement.blur());
      if (locale === 'en' || locale === 'de') await page.locator('#flags').screenshot({path: path.join(artifacts, `flags-${locale}-${width}.png`)});

      await selectSection('matrix');
      await pinnedIdentity(page, 'matrix', 1);
      const counts = await page.locator('#matrix tbody tr').evaluateAll(rows => rows.map(row => row.lastElementChild.textContent));
      assert.deepEqual(counts, [...Array(16).fill('0'), '–'], 'Measured zero and unavailable comparisons remain distinct');
      if (locale === 'en' || locale === 'de') await page.locator('#matrix').screenshot({path: path.join(artifacts, `matrix-${locale}-${width}.png`)});
      await selectSection('characters');
      await pinnedIdentity(page, 'characters', 0);
      const characterHelp = page.locator('#characters th .help[data-help]').last();
      assert.equal(await page.locator('#characters th .help[data-help]').count(), 3);
      await characterHelp.focus();
      await page.waitForFunction(() => document.querySelector('#lixity-tooltip').classList.contains('visible'));
      assert.equal(await page.locator('#lixity-tooltip .tooltip-copy').textContent(), await characterHelp.getAttribute('data-help'),
        `${locale}: focused column help explains coverage`);
      await page.keyboard.press('Escape');
      if (locale === 'en' || locale === 'de') await page.locator('#characters').screenshot({path: path.join(artifacts, `characters-${locale}-${width}.png`)});
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${locale} at ${width}: no horizontal page overflow`);
      if (width===320 && (locale==='en'||locale==='de')) {
        await page.setViewportSize({width,height:480});
        await page.evaluate(()=>document.documentElement.style.fontSize='200%');
        await page.evaluate(()=>scrollTo(0,0));
        assert.equal(await page.locator('#manuscript-reader-controls').evaluate(node=>getComputedStyle(node).position),'static',
          'Short enlarged overview headers scroll naturally instead of covering the content');
        assert.ok(await navigation.evaluate(nav=>nav.scrollWidth<=nav.clientWidth+1), 'Enlarged labels still wrap');
        await selectSection('matrix', false);
        assert.ok(await page.locator('#matrix').evaluate(node=>{
          const rect=node.getBoundingClientRect(); return rect.top>=0 && rect.top<innerHeight;
        }), 'A section arrival remains visible at480px height and200% text');
        await page.screenshot({path:path.join(artifacts,`navigation-short-enlarged-${locale}.png`)});
      }
      await page.close();
    }
    const report = await browser.newPage({viewport: {width: 320, height: 900}, javaScriptEnabled: false});
    await report.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: fixtures.standalone}));
    await report.goto('http://lixity.test/');
    assert.equal(await report.locator('#analysis-measurements').getAttribute('open'), '');
    assert.ok(await report.locator('#analysis-measurements .kpi').first().isVisible(), 'Standalone reports retain visible measurements without JavaScript');
    assert.ok(await report.locator('#readability-measurements').isVisible(), 'Standalone reports show formula inputs without JavaScript');
    await report.locator('#kpi-lexis-drawer summary').click();
    assert.ok(await report.locator('#kpi-lexis-drawer .kpi').first().isVisible(),
      'Vocabulary measurements are accessible without JavaScript');
    assert.equal(await report.locator('#analysis-sections a').count(),10);
    assert.ok(await report.locator('#analysis-sections').isVisible(), 'Static reports retain the same real section links without JavaScript');
    for (const selector of [
      '#matrix tbody tr a[href^="#ch-"]', '#characters tbody tr a[href^="#ch-"]',
      '#motifs tbody tr a[href^="#ch-"]', '#dialogue .row a[href^="#ch-"]',
      '#pacing .row a[href^="#ch-"]', '#showing .row a[href^="#ch-"]',
    ]) {
      const link = report.locator(selector).first();
      assert.equal(await link.count(), 1, `${selector}: native chapter link exists`);
      const target = await link.getAttribute('href');
      await link.click();
      assert.equal(new URL(report.url()).hash, target, `${selector}: native link navigates without JavaScript`);
      assert.equal(await report.locator(target).isVisible(), true);
    }
    assert.equal(await report.locator('#matrix tbody tr[role="button"]').count(), 0,
      'The chapter table keeps row semantics and exposes links inside its identity cells');
    assert.equal(await report.locator('#characters tbody tr[role="button"]').count(), 0,
      'The character table keeps row semantics');
    for (const scheme of ['light', 'dark']) {
      await report.emulateMedia({colorScheme: scheme});
      const style = await report.locator('#matrix tbody a.chapter-link').first().evaluate(link => {
        const probe = document.createElement('span');
        probe.style.color = 'var(--accent)'; document.body.appendChild(probe);
        const expected = getComputedStyle(probe).color;
        probe.style.color = 'var(--surface)';
        const background = getComputedStyle(probe).color;
        probe.remove();
        const rgb = value => value.match(/\d+/g).slice(0, 3).map(Number);
        const luminance = value => rgb(value).map(v => v / 255)
          .map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4)
          .reduce((sum, v, index) => sum + v * [.2126, .7152, .0722][index], 0);
        const foreground = getComputedStyle(link).color;
        const levels = [luminance(foreground), luminance(background)].sort((a, b) => a - b);
        return {foreground, expected, underline: getComputedStyle(link).textDecorationLine,
          contrast: (levels[1] + .05) / (levels[0] + .05)};
      });
      assert.equal(style.foreground, style.expected, `${scheme}: chapter links use the central accent`);
      assert.ok(style.underline.includes('underline'), `${scheme}: chapter links remain visibly identifiable`);
      assert.ok(style.contrast >= 4.5, `${scheme}: chapter link contrast is ${style.contrast}`);
    }
    await report.close();
    for (const [locale, html] of Object.entries(fixtures.unavailable)) {
      const page = await browser.newPage({viewport: {width: 320, height: 900}, hasTouch: true});
      await page.setContent(html);
      assert.equal(await page.locator('#showing .kpi-row').count(), 0, `${locale}: no fabricated comparison`);
      assert.equal(await page.locator('#showing > p.ctl-note').count(), 2, `${locale}: limits and unavailable explanation remain visible`);
      assert.ok(await page.locator('#showing > p.ctl-note').last().isVisible());
      await page.locator('#showing .signal-method summary').tap();
      assert.ok(await page.locator('#showing .signal-method p').isVisible());
      assert.ok(await page.locator('#showing > p.ctl-note').last().isVisible());
      await page.close();
    }
    assert.deepEqual(errors, []);
    assert.equal(writes, 0, 'Overview browsing performs no writes');
    console.log(`Analysis overview: three workflows, one active panel, native disclosure, complete measurements, long flags, readable anchors, pinned table identity and unavailable values in ${Object.keys(fixtures.locales).length} desktop/mobile locales passed. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
