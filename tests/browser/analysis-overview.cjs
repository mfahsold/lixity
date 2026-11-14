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
        language_key=language, controls=controls, title="Synthetic analysis overview", **reports)
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
      await page.goto('http://lixity.test/');
      assert.equal(await page.title(), 'Synthetic analysis overview – ' +
        (await page.locator('.workspace-shell .product-name').textContent()).trim(),
        'Browser history identifies the manuscript and product without repeating an analysis slogan');
      await page.locator('#workbench-overview-open').click();
      const navigation = page.locator('#analysis-sections');
      assert.deepEqual(await navigation.locator('[data-section-link]').evaluateAll(nodes => nodes.map(n => n.dataset.sectionLink)),
        ['flags','pacing','scenes','dialogue','dist','showing','characters','motifs','style','matrix']);
      assert.equal(await navigation.locator('svg').count(), 0, 'Overview section links are not a progress timeline');
      const orientation = await navigation.evaluate(nav => {
        const bounds = nav.getBoundingClientRect();
        return {before:!!(nav.compareDocumentPosition(document.getElementById('analysis-review')) & Node.DOCUMENT_POSITION_FOLLOWING),
          bounds:bounds.toJSON(), width:nav.clientWidth, content:nav.scrollWidth,
          links:[...nav.querySelectorAll('a')].map(a=>a.getBoundingClientRect().toJSON())};
      });
      assert.ok(orientation.before, 'Section choices precede the review callout');
      assert.equal(await navigation.evaluate(nav=>nav.parentElement.id), 'manuscript-reader-controls',
        'The same navigation shares the existing measured reader header');
      assert.ok(orientation.content <= orientation.width + 1, 'All section choices fit without horizontal clipping');
      assert.ok(orientation.links.every(rect=>rect.left>=orientation.bounds.left-1 && rect.right<=orientation.bounds.right+1),
        'Every label is wholly visible inside the overview navigation');
      if (width<=390) assert.ok(new Set(orientation.links.map(rect=>Math.round(rect.top))).size>1, 'Mobile section links wrap');
      if ((locale === 'en' || locale === 'de') && [1440, 320].includes(width)) {
        const entry = page.locator('#analysis-review a[data-jump="#dim-canvas"]');
        assert.equal(await page.locator('#dimensions').isVisible(), false, 'Another style tab starts selected');
        await entry.click();
        assert.equal(await page.locator('#dimensions').isVisible(), true, 'The direct route reveals the style space');
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
      if (locale === 'en' || locale === 'de') await page.locator('#manuscript-reader-controls').screenshot({
        path:path.join(artifacts, `navigation-${locale}-${width}.png`)});
      for (const target of ['flags','pacing','scenes','dialogue','dist','showing','characters','motifs','style','matrix']) {
        await navigation.locator(`[data-section-link=${target}]`).click();
        await page.waitForFunction(target=>document.querySelector('#analysis-sections [aria-current=true]')?.dataset.sectionLink===target,target);
        const destinationNavigation = await navigation.boundingBox();
        assert.ok(destinationNavigation.y >= -1 && destinationNavigation.y + destinationNavigation.height <= 900,
          `Overview navigation remains reachable after a section jump: ${JSON.stringify({locale,width,target,bounds:destinationNavigation})}`);
      }
      await navigation.locator('[data-section-link=showing]').click();
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
      await navigation.locator('[data-section-link=flags]').click();
      const measurements = page.locator('#analysis-measurements');
      assert.equal(await measurements.getAttribute('open'), null, 'Dense measurements initially stay folded');
      assert.equal(await measurements.locator('.kpi').first().isVisible(), false);
      assert.ok(await page.locator('#flags').isVisible(), 'Flag review remains outside the disclosure');
      const summary = measurements.locator(':scope > summary');
      assert.ok((await summary.textContent()).trim().length > 0);
      await summary.focus();
      await page.keyboard.press('Enter');
      assert.equal(await measurements.evaluate(element => element.open), true);
      assert.ok(await measurements.locator('.kpi').count() >= 20, 'All grouped measurements remain available');
      await page.locator('#workbench-overview-back').click();
      await page.locator('#workbench-overview-open').click();
      assert.equal(await measurements.evaluate(element => element.open), true, 'Returning preserves the native disclosure state');
      await summary.focus();
      await page.keyboard.press('Enter');
      assert.equal(await measurements.evaluate(element => element.open), false);

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

      await pinnedIdentity(page, 'matrix', 1);
      const counts = await page.locator('#matrix tbody tr').evaluateAll(rows => rows.map(row => row.lastElementChild.textContent));
      assert.deepEqual(counts, [...Array(16).fill('0'), '–'], 'Measured zero and unavailable comparisons remain distinct');
      if (locale === 'en' || locale === 'de') await page.locator('#matrix').screenshot({path: path.join(artifacts, `matrix-${locale}-${width}.png`)});
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
        await navigation.locator('[data-section-link=matrix]').click();
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
    console.log(`Analysis overview: native disclosure, complete measurements, long flags, readable anchors, pinned table identity and unavailable values in ${Object.keys(fixtures.locales).length} desktop/mobile locales passed. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
