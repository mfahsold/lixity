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
from lixity.pacing import pacing_report
from lixity.pipeline import analyze_document
from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui import render_dashboard
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
               characters=presence_report(text, ["Mara", "Tomas", "Unmentioned name"], config),
               pacing=pacing_report(text, config).to_dict())
def render(language, controls):
    return render_dashboard(analysis.chapters, analysis.paragraphs, metrics=analysis.metrics,
        fingerprint=analysis.fingerprint, labels=LANGUAGE_PROFILES[language].labels,
        language_key=language, controls=controls, title="Synthetic analysis overview", **reports)
print(json.dumps({"locales": {language: render(language, True) for language in
    ("en", "de", "fr", "es", "it", "pt", "nl")}, "standalone": render("en", False),
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
  const region = page.locator(`#${panel} .table-wrap`);
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
    for (const [locale, html] of Object.entries(fixtures.locales)) for (const width of [1440, 320]) {
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
      if (locale === 'en' || locale === 'de') await page.locator('#characters').screenshot({path: path.join(artifacts, `characters-${locale}-${width}.png`)});
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${locale} at ${width}: no horizontal page overflow`);
      await page.close();
    }
    const report = await browser.newPage({viewport: {width: 320, height: 900}, javaScriptEnabled: false});
    await report.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: fixtures.standalone}));
    await report.goto('http://lixity.test/');
    assert.equal(await report.locator('#analysis-measurements').getAttribute('open'), '');
    assert.ok(await report.locator('#analysis-measurements .kpi').first().isVisible(), 'Standalone reports retain visible measurements without JavaScript');
    await report.close();
    assert.deepEqual(errors, []);
    assert.equal(writes, 0, 'Overview browsing performs no writes');
    console.log(`Analysis overview: native disclosure, complete measurements, long flags, readable anchors, pinned table identity and unavailable values in seven desktop/mobile locales passed. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
