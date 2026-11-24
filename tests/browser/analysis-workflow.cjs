const fs = require('node:fs');
const assert = require('node:assert/strict');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');
const {controls, dashboard, words} = pythonFixture(`
import json
from pathlib import Path
from lixity.config import resolve_thresholds
from lixity.format import num
from lixity.pipeline import analyze_document, resolve_document_config
from lixity.ui import DashboardContent, DashboardOptions, render_analysis
from lixity.ui.analysis_navigation import render_analysis_workflows
from lixity.ui.manuscript_document import reader_blocks

labels = {'workflow_review':'Review passages','workflow_compare':'Compare chapters','workflow_explore':'Explore patterns'}
controls = render_analysis_workflows([
    ('flags', 'Flags'), ('matrix', 'Chapters'), ('style', 'Style'),
    ('register-targets', 'Register targets'), ('pacing', 'Pacing'), ('scenes', 'Scenes'),
    ('analysis-measurements', 'Manuscript measurements'),
], labels)
source = Path('samples/first-look.md').read_text(encoding='utf-8')
config, resolved = resolve_document_config(source, 'en', project_config={})
thresholds = resolve_thresholds(project_config={})
analysis = analyze_document(source, config, thresholds, include_evidence=True)
dashboard = render_analysis(
    analysis, resolved, title='Synthetic overview integration',
    flag_min_severity=thresholds.flag_min_severity,
    options=DashboardOptions(controls=True, enabled_actions=[]),
    content=DashboardContent(reader_document=reader_blocks(source, config, analysis.paragraphs)),
)
print(json.dumps({'controls': controls, 'dashboard': dashboard, 'words': num(analysis.metrics.tokens, 'en', 0)}))
`);
const script = fs.readFileSync('src/lixity/ui/assets/analysis-navigation.js', 'utf8');
const interactions = fs.readFileSync('src/lixity/ui/assets/interactions.js', 'utf8');
const css = fs.readFileSync('src/lixity/ui/assets/analysis-navigation.css', 'utf8');
const html = `<!doctype html><title>Analysis workflow regression</title><style>${css}</style>
<div id="analysis-outline-document" data-guided-analysis="1"><section id="analysis-review"><p>Status and next passage</p>${controls}</section>
<div id="manuscript-analysis-panels"><details id="analysis-measurements"><summary>Manuscript measurements</summary><p>Measured manuscript scope</p></details><section id="flags"><h2>Flags</h2><input aria-label="Draft" value="Unsaved"><a href="#p-0" id="passage-link">Read passage</a></section><section id="matrix">Chapters<button id="open-metric">Inspect metric</button></section><section id="register-targets">Project register targets</section><dialog id="analysis-metric-context">Measured evidence</dialog><section id="style"><div id="dimensions">Dimensions</div></section><section id="pacing">Pacing</section><section id="scenes">Scenes</section></div></div>
<nav id="analysis-sections"><a data-section-link="flags" href="#flags">Flags</a></nav><nav id="analysis-outline-nav"><a data-section-link="style" href="#style">Style</a></nav><main id="chapters"><p id="p-0">Actual manuscript passage</p></main>
<script>${interactions}
${script}
document.getElementById("open-metric").onclick = function() { document.getElementById("analysis-metric-context").showModal(); };</script>`;

async function checkNativeOverview(page, fragment, target = '') {
  // Distinct query strings exercise initial script and fragment handling on every route.
  await page.goto('http://workflow.test/native?landing=' + encodeURIComponent(fragment.slice(1)) + fragment);
  if (!fragment) await page.locator('#workbench-overview-open').click();
  await page.waitForFunction(() => window.LixityWorkbench?.state().surface === 'overview');
  const panels = page.locator('#manuscript-analysis-panels > :visible');
  assert.equal(await panels.count(), 1);
  if (target) {
    assert.equal(await panels.first().getAttribute('id'), target);
    assert.equal(await page.locator(fragment).isVisible(), true);
    assert.equal(await page.locator('[data-analysis-workflow="compare"]').getAttribute('aria-pressed'), 'true');
  } else {
    const measurements = page.locator('#analysis-measurements[open]');
    const total = measurements.locator('.kpi > b').first();
    assert.equal(await total.isVisible(), true);
    assert.equal(await total.textContent(), words);
    assert.equal(await page.locator('[data-analysis-workflow][aria-pressed="true"]').count(), 0);
    assert.equal(await page.locator('.analysis-workflow-sections').isVisible(), false);
    const compareName = await page.evaluate(() => `${uiLabel('workflow_compare')} ${uiLabel('workflow_compare_hint')}`);
    assert.ok(await page.getByRole('button', {name: compareName, exact: true}).isVisible(),
      'The workflow is addressable by its displayed title and hint');
    if (fragment) {
      await page.waitForFunction(() => {
        const title = document.querySelector('#analysis-measurements > summary').getBoundingClientRect();
        const toolbar = document.getElementById('manuscript-reader-controls');
        const inset = getComputedStyle(toolbar).position === 'sticky'
          ? Math.max(0, toolbar.getBoundingClientRect().bottom) : 0;
        return title.top >= inset && title.bottom <= innerHeight;
      });
    }
  }
}

(async () => {
  const browser = await launchChromium();
  try {
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://workflow.test/**', route => route.fulfill({
        contentType:'text/html',
        body: new URL(route.request().url()).pathname === '/native' ? dashboard : html,
      }));
      await page.goto('http://workflow.test/');
      assert.equal(await page.title(), 'Analysis workflow regression');
      assert.equal(await page.locator('[data-analysis-workflow]:visible').count(), 3);
      assert.equal(await page.locator('#analysis-measurements[open] p').isVisible(), true);
      assert.equal(await page.locator('#manuscript-analysis-panels > :visible').count(), 1);
      await page.locator('[data-analysis-workflow="review"]').focus();
      await page.keyboard.press('Enter');
      assert.equal(await page.locator('#flags').isVisible(), true);
      await page.locator('#flags input').fill('Retain my draft');
      await page.locator('[data-analysis-workflow="compare"]').click();
      assert.equal(await page.locator('#matrix').isVisible(), true);
      assert.equal(await page.locator('#manuscript-analysis-panels > :visible').count(), 1);
      await page.locator('[data-analysis-section-target="style"]').click();
      assert.equal(await page.locator('#style').isVisible(), true);
      assert.equal(await page.locator('#style').evaluate(section => section.contains(document.activeElement)), true,
        'Opening a report focuses its destination through the shared interaction helper');
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
      await checkNativeOverview(page, '');
      await checkNativeOverview(page, '#manuscript-analysis-panels');
      await checkNativeOverview(page, '#matrix', 'matrix');
      await checkNativeOverview(page, '#heatmap', 'style');
      await page.goto('http://workflow.test/native?landing=unknown#%5B');
      await page.locator('#workbench-overview-open').click();
      assert.ok(await page.locator('#analysis-measurements[open]').isVisible(),
        'An unrecognized link fragment leaves the overview reachable');
      assert.deepEqual(errors, []);
      await page.close();
    }
    const context = await browser.newContext({javaScriptEnabled:false});
    const page = await context.newPage();
    await page.setContent(html);
    assert.equal(await page.locator('#manuscript-analysis-panels > :visible').count(), 7);
    await context.close();
    console.log(JSON.stringify({passed:true,widths:[1440,320],checks:['default manuscript measurements','three workflows','single active panel','cold root and section links','nested style targets','retained input','passage link','no script readability','console']}));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
