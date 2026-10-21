// A fitting chart must not suggest hidden rows; overflowing charts retain every row.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');

const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-chart-scroll-'));
const fixtures = pythonFixture(`
import json
from lixity.language import LANGUAGE_PROFILES
from lixity.pipeline import analyze_document, resolve_document_config
from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui import render_dashboard
from lixity.pacing import pacing_report
from lixity.showing import showing_report
prose = [
    "The observer believed that the decision was considered carefully, because every detail of the explanation seemed important to the people who waited inside the quiet room.",
    "Rain fell. A door shut. The bell rang. Footsteps stopped. A bird called.",
    '\\"Come here,\\" she said. \\"Leave the lamp beside the gate.\\" The keeper nodded.',
]
documents = {}
for count in (6, 24):
    text = "\\n\\n".join(f"## Chapter {number}\\n\\n" + (prose[(number-1) % 3] + " ") * 15
                        for number in range(1, count+1))
    config, _ = resolve_document_config(text, "en")
    analysis = analyze_document(text, config, FingerprintThresholds())
    pacing = pacing_report(text, config).to_dict()
    showing = showing_report(text, config, metrics=analysis.metrics).to_dict()
    documents[str(count)] = {}
    for language in ("en", "de", "fr", "es", "it", "pt", "nl"):
        profile = LANGUAGE_PROFILES[language]
        documents[str(count)][language] = render_dashboard(
            analysis.chapters, analysis.paragraphs, metrics=analysis.metrics,
            fingerprint=analysis.fingerprint, pacing=pacing, showing=showing,
            labels=profile.labels, language_key=language, title="Synthetic scroll review", controls=True)
print(json.dumps(documents))
`, {root});

async function lastBarIsFullyPainted(chart, name) {
  const last = chart.locator('.row .bar i').last();
  const point = await last.evaluate(element => {
    const box = element.getBoundingClientRect();
    const host = element.closest('.dist').getBoundingClientRect();
    return {x: box.left - host.left + Math.min(8, box.width / 2),
      y: box.top - host.top + box.height / 2,
      color: getComputedStyle(element).backgroundColor};
  });
  const image = await chart.screenshot({animations: 'disabled'});
  if (name.includes('-en-') || name.includes('-de-')) fs.writeFileSync(path.join(artifacts, name + '.png'), image);
  const pixel = await chart.page().evaluate(async ({image, x, y}) => {
    const picture = new Image();
    picture.src = 'data:image/png;base64,' + image;
    await picture.decode();
    const canvas = document.createElement('canvas');
    canvas.width = picture.width; canvas.height = picture.height;
    const context = canvas.getContext('2d');
    context.drawImage(picture, 0, 0);
    return Array.from(context.getImageData(Math.floor(x), Math.floor(y), 1, 1).data);
  }, {image: image.toString('base64'), ...point});
  const expected = point.color.match(/[\d.]+/g).slice(0, 3).map(Number);
  assert.ok(expected.every((channel, index) => Math.abs(channel - pixel[index]) <= 2),
    `${name}: the final data bar must retain its full colour, not fade like hidden content: ${JSON.stringify({expected, pixel})}`);
}

async function touchScroll(page, chart) {
  const box = await chart.boundingBox();
  const x = box.x + box.width / 2, start = box.y + box.height - 35;
  const session = await page.context().newCDPSession(page);
  try {
    await session.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [{x, y: start}]});
    for (let distance = 30; distance <= 180; distance += 30) {
      await session.send('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: [{x, y: start - distance}]});
    }
    await session.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
  } finally { await session.detach(); }
}

async function scrollInput(chart, action) {
  // Wait for native scrolling to finish before another input or fixture reset;
  // otherwise the preceding PageDown animation can overwrite the wheel result.
  await chart.evaluate(element => {
    element.dataset.testScrollEnded = 'false';
    element.addEventListener('scrollend', () => { element.dataset.testScrollEnded = 'true'; }, {once: true});
  });
  await action();
  await chart.page().waitForFunction(selector => document.querySelector(selector).dataset.testScrollEnded === 'true',
    '#' + await chart.evaluate(element => element.closest('section').id) + ' .dist.scrollable', {timeout: 5000});
}

(async () => {
  const browser = await launchChromium();
  const errors = [];
  try {
    for (const count of [6, 24]) for (const [locale, html] of Object.entries(fixtures[count])) {
      for (const width of [1440, 320]) for (const theme of ['dark', 'light']) {
        const page = await browser.newPage({viewport: {width, height: 900}, colorScheme: theme,
          reducedMotion: 'reduce', hasTouch: true});
        page.on('pageerror', error => errors.push(error.message));
        await page.route('http://lixity.test/**', route => route.fulfill(
          route.request().url().includes('/api/') ? {json: {ok: true, locked: true, records: []}}
            : {contentType: 'text/html', body: html}));
        await page.goto('http://lixity.test/');
        assert.equal(await page.locator('h1').textContent(), 'Synthetic scroll review');
        await page.locator('#workbench-overview-open').click();
        for (const panel of ['pacing', 'showing']) {
          const chart = page.locator(`#${panel} .dist.scrollable`);
          assert.equal(await chart.locator('.row').count(), count);
          await chart.scrollIntoViewIfNeeded();
          const dimensions = await chart.evaluate(element => ({height: element.clientHeight, content: element.scrollHeight}));
          if (count === 6 && width === 1440) assert.equal(dimensions.height, dimensions.content,
            'All six rows fit: there is no hidden content or need for a scrollbar');
          if (count === 24) {
            assert.ok(dimensions.content > dimensions.height);
            await chart.locator('.row').first().focus();
            await scrollInput(chart, () => page.keyboard.press('PageDown'));
            assert.ok(await chart.evaluate(element => element.scrollTop > 0), 'Keyboard scroll moves the chart');
            await scrollInput(chart, () => chart.evaluate(element => { element.scrollTop = 0; }));
            const box = await chart.boundingBox();
            await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
            await scrollInput(chart, () => page.mouse.wheel(0, 100000));
            await page.waitForFunction(selector => {
              const element = document.querySelector(selector);
              return Math.abs(element.scrollHeight - element.clientHeight - element.scrollTop) <= 1;
            }, `#${panel} .dist.scrollable`, {timeout: 3000}).catch(async error => {
              const state = await chart.evaluate(element => {
                const box = element.getBoundingClientRect();
                const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
                return {top: element.scrollTop, height: element.clientHeight, content: element.scrollHeight,
                  y: box.y, pageTop: window.scrollY, hit: hit && hit.className};
              });
              throw new Error(`${panel}-${count}-${locale}-${width}-${theme}: wheel did not reach the final row: ${JSON.stringify(state)}`, {cause: error});
            });
            if (width === 320 && locale === 'en' && theme === 'dark') {
              await scrollInput(chart, () => chart.evaluate(element => { element.scrollTop = 0; }));
              await scrollInput(chart, () => touchScroll(page, chart));
              await page.waitForFunction(selector => document.querySelector(selector).scrollTop > 0,
                `#${panel} .dist.scrollable`);
              await chart.locator('.row').last().focus();
            }
          }
          await chart.locator('.row').last().focus();
          await page.evaluate(() => document.activeElement.blur());
          await page.mouse.move(0, 0);
          await lastBarIsFullyPainted(chart, `${panel}-${count}-${locale}-${width}-${theme}`);
          assert.ok(await chart.evaluate(element => {
            const last = element.lastElementChild.getBoundingClientRect(), box = element.getBoundingClientRect();
            return last.bottom <= box.bottom + 1;
          }), 'The final row remains entirely visible at the scroll end');
        }
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        await page.close();
      }
    }
    assert.deepEqual(errors, []);
    console.log(`Chapter charts: fitting and long lists, fully painted final rows, wheel/keyboard/touch, seven locales and desktop/mobile themes passed. ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
