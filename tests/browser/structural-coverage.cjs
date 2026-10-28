// Render missing-data notices for synthetic structural diagnostics.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');

const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-structural-coverage-'));
const fixtures = pythonFixture(`
import json
from pathlib import Path
from lixity.language import LANGUAGE_PROFILES
from lixity.analyzer import CorpusAnalyzer
from lixity.models import CorpusConfig
from lixity.style_fingerprint import StyleFingerprint
from lixity.ui.heatmap import render_heatmap_panel, render_metric_context, render_style_passport_panel
from lixity.ui.structural import style_structural
assets = Path('src/lixity/ui/assets')
css = '\\n'.join((assets / filename).read_text() for filename in
    ('design-tokens.css', 'components.css', 'dashboard.css'))
def render(language, partial):
    source = ([None, None, 1., 2., 10., 11., 12., 13.] if partial else
              [None, None, None, 2., 10., 11., 12., 13.])
    columns = {'asl': dict(enumerate(source, 1))}
    baseline = {'asl': {'n': 5, 'sigma': 1.}}
    if partial:
        columns['dialog_pct'] = dict(enumerate([1.,2.,3.,4.,5.,6.,7.,8.], 1))
        baseline['dialog_pct'] = {'n': 8, 'sigma': 1.}
    fp = StyleFingerprint(n_chapters=8, values=columns, baseline=baseline)
    fp.structural_diagnostics = fp._derive_structural_diagnostics()
    labels = LANGUAGE_PROFILES[language].labels
    html = style_structural([None] * 8, fp, labels=labels, language_key=language)
    return {'html': '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><style>' + css + '</style>' + html,
        'unavailable': labels['structural_unavailable'],
        'partial': labels['structural_partly_unavailable'],
        'trend': labels['structural_partial_trend'],
        'distribution': labels['structural_partial_distribution']}
def zero_mad(language):
    text = '\\n\\n'.join('## Chapter ' + str(index) + '\\n\\n' +
        ('The garden waits. ' if index < 4 else 'The quiet garden waits. ') * 50
        for index in range(1,5))
    metrics = CorpusAnalyzer(CorpusConfig(language='en')).analyze_text(text)
    fp = StyleFingerprint.from_metrics(metrics)
    assert fp.baseline['asl']['comparison_status'] == 'zero_mad_varying'
    labels = LANGUAGE_PROFILES[language].labels
    html = (render_style_passport_panel(fp, labels, language) +
            render_heatmap_panel(fp, metrics, labels, language) +
            render_metric_context(fp, metrics.chapters, labels, language))
    js = (assets / 'metric-context.js').read_text()
    return {'html': '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><style>' + css + '</style>' + html + '<script>' + js + '</script>',
            'reason': labels['baseline_zero_mad']}
print(json.dumps({language: {**{str(partial): render(language, partial) for partial in (False, True)},
    'zero': zero_mad(language)} for language in ('en','de','fr','es','it','pt','nl')}))
`, {root});

(async () => {
  const browser = await launchChromium();
  try {
    for (const [language, modes] of Object.entries(fixtures)) for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}});
      for (const [mode, data] of Object.entries(modes)) {
        if (mode === 'zero') continue;
        await page.setContent(data.html);
        const panel = page.locator('#structural');
        assert.ok(await panel.isVisible());
        assert.equal(await panel.locator('.badge-success').count(), 0);
        assert.ok(await panel.getByText(data.trend, {exact: true}).isVisible());
        if (mode === 'False') assert.equal(await panel.getByText(data.unavailable, {exact: true}).count(), 2);
        else {
          assert.ok(await panel.getByText(data.partial, {exact: true}).count() >= 1);
          assert.ok(await panel.getByText(data.distribution, {exact: true}).isVisible());
        }
        assert.ok(await panel.evaluate(element => element.scrollWidth <= element.clientWidth + 1),
          `${language}/${width}: panel should not overflow`);
        if (language === 'de') await panel.screenshot({path: path.join(artifacts, `${language}-${width}-${mode}.png`)});
      }
      await page.setContent(modes.zero.html);
      const cell = page.locator('#heatmap td[data-chapter="4"][data-metric-feature="asl"]');
      assert.equal(await cell.textContent(), '–');
      assert.ok((await cell.getAttribute('aria-label')).includes(modes.zero.reason));
      assert.ok(await page.locator('#bands').getByText(modes.zero.reason, {exact: true}).count() > 0);
      await cell.evaluate(element => window.LixityMetricContext.open(element));
      const dialog = page.locator('#analysis-metric-context');
      assert.ok(await dialog.isVisible());
      assert.ok((await dialog.locator('#metric-context-definition').textContent()).includes(modes.zero.reason));
      assert.ok((await dialog.locator('[data-metric-row="asl"] td:last-child').textContent()).includes(modes.zero.reason));
      if (language === 'de') await dialog.screenshot({path: path.join(artifacts, `${language}-${width}-zero-mad.png`)});
      await page.close();
    }
    console.log(`Structural coverage in seven locales on desktop/mobile passed: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
