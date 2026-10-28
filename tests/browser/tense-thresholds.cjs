// Thresholds and metric overlays must agree on which tense signals are inspectable.
const assert = require('node:assert/strict');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const root = path.resolve(__dirname, '../..');
const fixtures = pythonFixture(`
import json
from dashboard_fixtures import full_dashboard as render
original = render.__globals__['render_dashboard']
fixtures = {}
for threshold in (1, 2, 3):
    def override(*args, **kwargs):
        for severity, p in enumerate(args[1][:3], 1):
            p.severity = severity
            p.flag_min = 2  # Deliberately different from the dashboard threshold.
        return original(*args, **{**kwargs, 'flag_min_severity': threshold})
    render.__globals__['render_dashboard'] = override
    fixtures[threshold] = render(include_evidence=True)
print(json.dumps(fixtures))
`, {root});
(async () => {
  const browser = await launchChromium();
  try {
    for (const [threshold, html] of Object.entries(fixtures)) for (const width of [1440, 390]) {
      const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion: 'reduce'});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://localhost/**', route => route.fulfill({contentType: 'text/html', body: html}));
      await page.goto('http://localhost/');
      await page.locator('#tab-view-analysis').click();
      for (let severity = 1; severity <= 3; severity++) {
        const panel = page.locator(`#p-${severity - 1}`);
        const flagged = severity >= Number(threshold);
        assert.equal(await panel.evaluate(node => node.classList.contains('flagged')), flagged,
          `Threshold ${threshold} classifies severity ${severity}`);
        assert.equal(await page.locator(`#flags .flag-row[data-target=p-${severity - 1}]`).count(), flagged ? 1 : 0,
          'The overview uses the same threshold as the manuscript');
        await panel.locator('.reader-paragraph-actions').click();
        await page.locator('#manuscript-context-menu [data-reader-action=values]').click();
        assert.equal(await page.locator('#reader-inspector .reader-passage-flag').count(), flagged ? 1 : 0,
          `Threshold ${threshold} exposes the severity ${severity} explanation on request`);
        await page.locator('#reader-inspector-close').click();
      }
      await page.locator('#manuscript-analysis-toggle').click();
      const panel = page.locator(`#p-${Number(threshold) - 1}`);
      await page.locator('#style-layer').selectOption('asl');
      assert.equal(await panel.locator('.reader-review-flag').isVisible(), false);
      await panel.locator('.reader-paragraph-actions').click();
      await page.locator('#manuscript-context-menu [data-reader-action=values]').click();
      assert.equal(await page.locator('#reader-inspector .reader-passage-flag').isVisible(), true,
        'The passage menu retains the tense explanation with an active metric');
      await page.locator('#reader-inspector-close').click();
      await page.locator('#style-layer').selectOption('');
      assert.equal(await panel.locator('.reader-review-flag').isVisible(), true);
      assert.deepEqual(errors, []);
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
