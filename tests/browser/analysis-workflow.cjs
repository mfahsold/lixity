const fs = require('node:fs');
const assert = require('node:assert/strict');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const controls = pythonFixture(`
import json
from lixity.ui.analysis_navigation import render_analysis_workflows
labels = {'workflow_review':'Review passages','workflow_compare':'Compare chapters','workflow_explore':'Explore patterns'}
print(json.dumps(render_analysis_workflows([('flags','Flags'),('matrix','Chapters'),('style','Style'),('register-targets','Register targets'),('pacing','Pacing'),('scenes','Scenes')], labels)))
`);
const script = fs.readFileSync('src/lixity/ui/assets/analysis-navigation.js', 'utf8');
const css = fs.readFileSync('src/lixity/ui/assets/analysis-navigation.css', 'utf8');
const html = `<!doctype html><title>Analysis workflow regression</title><style>${css}</style>
<div id="analysis-outline-document" data-guided-analysis="1"><section id="analysis-review"><p>Status and next passage</p>${controls}</section>
<div id="manuscript-analysis-panels"><section id="flags"><h2>Flags</h2><input aria-label="Draft" value="Unsaved"><a href="#p-0" id="passage-link">Read passage</a></section><section id="matrix">Chapters<button id="open-metric">Inspect metric</button></section><section id="register-targets">Project register targets</section><dialog id="analysis-metric-context">Measured evidence</dialog><section id="style"><div id="dimensions">Dimensions</div></section><section id="pacing">Pacing</section><section id="scenes">Scenes</section></div></div>
<nav id="analysis-sections"><a data-section-link="flags" href="#flags">Flags</a></nav><nav id="analysis-outline-nav"><a data-section-link="style" href="#style">Style</a></nav><main id="chapters"><p id="p-0">Actual manuscript passage</p></main>
<script>${script}
document.getElementById("open-metric").onclick = function() { document.getElementById("analysis-metric-context").showModal(); };</script>`;
(async () => {
  const browser = await launchChromium();
  try {
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://workflow.test/**', route => route.fulfill({contentType:'text/html',body:html}));
      await page.goto('http://workflow.test/');
      assert.equal(await page.title(), 'Analysis workflow regression');
      assert.equal(await page.locator('[data-analysis-workflow]:visible').count(), 3);
      assert.equal(await page.locator('#manuscript-analysis-panels > :visible').count(), 0);
      await page.locator('[data-analysis-workflow="review"]').focus();
      await page.keyboard.press('Enter');
      assert.equal(await page.locator('#flags').isVisible(), true);
      await page.locator('#flags input').fill('Retain my draft');
      await page.locator('[data-analysis-workflow="compare"]').click();
      assert.equal(await page.locator('#matrix').isVisible(), true);
      assert.equal(await page.locator('#manuscript-analysis-panels > :visible').count(), 1);
      await page.locator('[data-analysis-section-target="style"]').click();
      assert.equal(await page.locator('#style').isVisible(), true);
      await page.evaluate(() => { location.hash = '#scenes'; });
      await page.waitForFunction(() => !document.getElementById('scenes').hidden);
      assert.equal(await page.locator('[data-analysis-workflow="explore"]').getAttribute('aria-pressed'), 'true');
      await page.evaluate(() => window.LixityAnalysisNavigation.reveal(document.getElementById('dimensions')));
      assert.equal(await page.locator('#style').isVisible(), true);
      await page.locator('[data-analysis-workflow="review"]').click();
      assert.equal(await page.locator('#flags input').inputValue(), 'Retain my draft');
      await page.locator('[data-analysis-workflow="compare"]').click();
      assert.equal(await page.locator('#style').isVisible(), true);
      await page.locator('[data-analysis-section-target="register-targets"]').click();
      assert.equal(await page.locator('#register-targets').isVisible(), true);
      await page.locator('[data-analysis-section-target="matrix"]').click();
      await page.locator('#open-metric').click();
      assert.equal(await page.locator('#analysis-metric-context').isVisible(), true);
      await page.keyboard.press('Escape');
      await page.locator('[data-analysis-workflow="review"]').click();
      await page.locator('#passage-link').click();
      assert.equal(await page.locator('#p-0').isVisible(), true);
      assert.equal(await page.locator('#manuscript-analysis-panels > :visible').count(), 1);
      assert.equal(await page.evaluate(() => Array.from(document.querySelectorAll('[data-analysis-workflow]')).every(button => button.scrollWidth <= button.clientWidth)), true);
      assert.deepEqual(errors, []);
      await page.close();
    }
    const context = await browser.newContext({javaScriptEnabled:false});
    const page = await context.newPage();
    await page.setContent(html);
    assert.equal(await page.locator('#manuscript-analysis-panels > :visible').count(), 6);
    await context.close();
    console.log(JSON.stringify({passed:true,widths:[1440,320],checks:['compact initial state','three workflows','single active panel','deep links','nested style targets','retained input','passage link','no script readability','console']}));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
