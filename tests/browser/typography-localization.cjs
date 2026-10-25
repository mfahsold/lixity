// Semantic reading roles must survive the app/Pages cascade and localization.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {pythonFixture} = require('./support/python-fixture.cjs');

const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-typography-localization-'));
const siteRoot = path.join(artifacts, 'site');
const fixtures = pythonFixture(`
import json
from lixity.language import get_language_profile
from lixity.ui import render_dashboard
from lixity.workspace_labels import WORKSPACE_LABELS
from dashboard_fixtures import full_dashboard
documents = {}
for locale in ('en', 'de', 'fr', 'es', 'it', 'pt', 'nl'):
    def localized(*args, _locale=locale, **kwargs):
        return render_dashboard(*args, **{**kwargs, 'language_key': _locale,
            'labels': get_language_profile(_locale).labels})
    full_dashboard.__globals__['render_dashboard'] = localized
    documents[locale] = full_dashboard()
print(json.dumps({'documents': documents, 'labels': WORKSPACE_LABELS}))
`, {root});
const markdown = '# Document heading\n\n## Section heading\n\n### Subsection heading\n\n' +
  '#### Detail heading\n\n##### Fifth heading\n\n###### Sixth heading\n\n' +
  'Synthetic café, Straße, ação and naïve prose with `inline_code`.\n\n' +
  '```text\nfor count in range(3): print(count)\n```\n\n' +
  '| Measure | Value |\n| --- | --- |\n| Synthetic | 1234.5 |';
const source = {id: 'synthetic-source', title: 'Synthetic typography source',
  media_type: 'text/markdown', byte_length: Buffer.byteLength(markdown), passages: 1, tags: [], context: {}};
const sourceDetail = {...source, text: markdown, passages: [{id: 'synthetic-passage', verbatim: markdown}]};
const status = {ok: true, initialized: true, project_id: 'synthetic-project',
  project_root: '/tmp/synthetic-project', sources: [source], dossiers: [], claims: [], decisions: []};

async function textRole(locator) {
  return locator.evaluate(element => {
    const css = getComputedStyle(element);
    return {family: css.fontFamily, size: parseFloat(css.fontSize), weight: css.fontWeight};
  });
}

(async () => {
  let browser;
  const failures = [];
  async function check(name, run) {
    try { await run(); }
    catch (error) { failures.push(`${name}: ${error.message}`); }
  }
  try {
    const staged = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'),
      ['scripts/stage_pages.py', '--output', siteRoot], {cwd: root, encoding: 'utf8'});
    assert.equal(staged.status, 0, staged.stderr);
    browser = await launchChromium();
    const context = await browser.newContext({reducedMotion: 'reduce', colorScheme: 'light'});
    const errors = [], writes = [];
    await context.route('http://lixity.test/**', route => {
      const request = route.request(), url = new URL(request.url());
      if (request.method() !== 'GET') writes.push(url.pathname);
      if (url.pathname.startsWith('/app/')) return route.fulfill({contentType: 'text/html',
        body: fixtures.documents[url.pathname.split('/')[2]]});
      if (url.pathname === '/api/research/status') return route.fulfill({json: status});
      if (url.pathname === '/api/research/sources') return route.fulfill({json: url.searchParams.has('id')
        ? {ok: true, project_id: status.project_id, ...sourceDetail}
        : {ok: true, project_id: status.project_id, sources: [source]}});
      if (url.pathname.startsWith('/api/')) return route.fulfill({json: {ok: true,
        records: [], sources: [], dossiers: [], claims: [], decisions: []}});
      if (!url.pathname.startsWith('/site/')) return route.abort();
      const file = path.resolve(siteRoot, url.pathname.slice('/site/'.length));
      assert.ok(file.startsWith(siteRoot + path.sep));
      return route.fulfill({contentType: file.endsWith('.css') ? 'text/css'
        : file.endsWith('.js') ? 'text/javascript' : file.endsWith('.png') ? 'image/png'
        : file.endsWith('.svg') ? 'image/svg+xml' : 'text/html', body: fs.readFileSync(file)});
    });
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      window.typographyCanvasLabels = [];
      const clear = CanvasRenderingContext2D.prototype.clearRect;
      const paint = CanvasRenderingContext2D.prototype.fillText;
      CanvasRenderingContext2D.prototype.clearRect = function(...args) {
        if (this.canvas.id === 'dim-3d-canvas') window.typographyCanvasLabels = [];
        return clear.apply(this, args);
      };
      CanvasRenderingContext2D.prototype.fillText = function(text, ...args) {
        if (this.canvas.id === 'dim-3d-canvas') window.typographyCanvasLabels.push({text, font: this.font});
        return paint.call(this, text, ...args);
      };
    });
    for (const [locale, document] of Object.entries(fixtures.documents)) {
      assert.ok(document.length > 1000);
      for (const width of [1440, 320]) {
        const name = `${locale}-${width}`;
        await page.setViewportSize({width, height: 900});
        await page.goto(`http://lixity.test/app/${locale}`);
        await check(`${name} language and label pack`, async () => {
          assert.equal(await page.locator('html').getAttribute('lang'), locale);
          const packed = await page.locator('body').evaluate(element => JSON.parse(element.dataset.uiLabels));
          for (const [key, value] of Object.entries(fixtures.labels[locale])) assert.equal(packed[key], value, key);
          for (const [key, english] of Object.entries(fixtures.labels.en)) {
            const fields = value => Array.from(value.matchAll(/\{([a-z_]+)\}/g), match => match[1]).sort();
            assert.deepEqual(fields(packed[key]), fields(english), key);
          }
        });
        await page.locator('#tab-view-analysis').click();
        await check(`${name} separate reading roles`, async () => {
          const body = await textRole(page.locator('body'));
          const manuscript = await textRole(page.locator('.ptext p').first());
          const control = await textRole(page.locator('#tab-view-analysis'));
          const code = await textRole(page.locator('code').first());
          assert.equal(body.size, 16);
          assert.equal(control.family, body.family);
          assert.notEqual(manuscript.family, body.family, 'Manuscript keeps its literary face');
          assert.ok(manuscript.size >= body.size, 'Continuous manuscript remains a reading surface');
          assert.notEqual(code.family, body.family, 'Technical values keep their monospace face');
        });
        await check(`${name} consistent interface type roles`, async () => {
          const primary = await textRole(page.locator('#tab-view-analysis'));
          const settings = await textRole(page.locator('#reader-settings > summary'));
          const metric = await textRole(page.locator('#style-layer'));
          const metricLabel = await textRole(page.locator('.metric-layer-control > span'));
          const counted = await textRole(page.locator('.analysis-evidence-key'));
          const comparison = await textRole(page.locator('.analysis-comparison-key'));
          const adjacent = await textRole(page.locator('#manuscript-analysis-toggle'));
          const help = await textRole(page.locator('.reader-shortcuts dd').first());
          assert.equal(primary.size, 14, 'Primary destinations retain control size on narrow screens');
          assert.equal(settings.size, adjacent.size, 'Adjacent reader commands share a type role');
          assert.equal(settings.size, 14);
          assert.equal(metric.size, settings.size, 'The directly selected metric retains the control role');
          assert.equal(metric.family, settings.family);
          assert.equal(metricLabel.size, 13, 'The metric scope uses the supporting metadata role');
          assert.equal(counted.size, 13, 'The counted-text switch keeps a readable supporting label');
          assert.equal(comparison.size, counted.size, 'Both independent analysis switches share a type role');
          assert.equal(help.size, 13, 'Supporting help remains readable and uses one metadata role');
        });
        await page.locator('#tab-view-research').click();
        await page.locator('#research-tabs').waitFor({state: 'visible'});
        await page.locator('[data-rtab=sources]').click();
        await page.locator('[data-research-detail=source]').click();
        const prose = page.locator('.research-source-doc-rendered');
        await prose.locator('h6').waitFor();
        await check(`${name} source heading readability`, async () => {
          const bodySize = (await textRole(prose.locator('p').first())).size;
          const headings = await prose.locator('h1,h2,h3,h4,h5,h6').evaluateAll(elements =>
            elements.map(element => ({tag: element.tagName, size: parseFloat(getComputedStyle(element).fontSize)})));
          assert.equal(headings.length, 6);
          assert.ok(headings.every(heading => heading.size >= bodySize),
            `Document headings must not shrink below their prose: ${JSON.stringify(headings)}`);
          assert.ok(headings.every((heading, index) => !index || heading.size <= headings[index - 1].size),
            'Heading levels preserve their visual order');
        });
        await check(`${name} source code size`, async () => {
          const pre = await textRole(prose.locator('pre'));
          const code = await textRole(prose.locator('pre code'));
          assert.equal(code.size, pre.size, 'Fenced code must not compound the inline-code reduction');
          assert.equal(code.family, pre.family);
          assert.notEqual(code.family, (await textRole(prose)).family);
        });
        await check(`${name} translated source toolbar`, async () => {
          const bar = page.locator('.research-source-view-bar');
          assert.equal(await bar.locator('[data-source-toggle]').textContent(), fixtures.labels[locale].research_show_source);
          assert.ok((await bar.locator('[data-source-view=doc]').textContent()).includes(fixtures.labels[locale].research_doc_view));
          assert.ok((await bar.locator('[data-source-view=passages]').textContent()).includes(fixtures.labels[locale].research_passages_view));
          const bounds = await bar.evaluate(element => {
            const host = element.getBoundingClientRect();
            return Array.from(element.querySelectorAll('button'), button => {
              const box = button.getBoundingClientRect();
              return {text: button.textContent, contained: box.left >= host.left - 1 && box.right <= host.right + 1,
                unclipped: button.scrollWidth <= button.clientWidth + 1};
            });
          });
          assert.ok(bounds.every(button => button.contained && button.unclipped), JSON.stringify(bounds));
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
          await bar.locator('[data-source-toggle]').click();
          assert.equal(await bar.locator('[data-source-toggle]').textContent(), fixtures.labels[locale].research_show_preview);
          assert.equal(await page.locator('.research-source-doc-raw').textContent(), markdown,
            'Localization never rewrites the retained source');
          await bar.locator('[data-source-toggle]').click();
        });
        if (locale === 'fr' || locale === 'pt') await page.locator('#research-sources-list .research-details-body').screenshot({
          path: path.join(artifacts, `source-${name}.png`)});
      }
    }
    for (const width of [1440, 320]) {
      await page.setViewportSize({width, height: 900});
      await page.goto('http://lixity.test/site/index.html');
      await check(`Pages-${width} shared control family`, async () => {
        const body = await textRole(page.locator('body'));
        assert.equal((await textRole(page.locator('#themeToggle'))).family, body.family);
        assert.equal((await textRole(page.locator('.hero-cta a').first())).family, body.family);
      });
      await page.goto('http://lixity.test/site/guides/installation.html');
      await check(`Pages-${width} guide code size`, async () => {
        const pre = await textRole(page.locator('pre:visible').first());
        const code = await textRole(page.locator('pre:visible code').first());
        assert.equal(code.size, pre.size, 'Guide commands inherit their pre size');
        assert.equal(code.family, pre.family);
        assert.notEqual(code.family, (await textRole(page.locator('body'))).family);
      });
      await page.locator('pre:visible').first().screenshot({path: path.join(artifacts, `guide-code-${width}.png`)});
      await page.goto('http://lixity.test/app/en');
      await page.locator('#tab-view-analysis').click();
      await page.locator('#workbench-overview-open').click();
      await page.locator('#style-tab-dimensions').click();
      await page.locator('#dim-3d-canvas').scrollIntoViewIfNeeded();
      await page.evaluate(() => {
        document.documentElement.style.setProperty('--font', 'serif');
        document.documentElement.style.setProperty('--font-mono', 'monospace');
        document.documentElement.style.setProperty('--text-note', '1.125rem');
        document.documentElement.style.setProperty('--weight-strong', '700');
        window.dispatchEvent(new Event('resize'));
      });
      await check(`canvas-${width} shared typography tokens`, async () => {
        const labels = await page.evaluate(() => window.typographyCanvasLabels);
        const axis = labels.find(label => /^[+−]D/.test(label.text));
        const chapter = labels.find(label => /^\d+$/.test(label.text));
        assert.ok(axis && chapter, JSON.stringify(labels));
        assert.equal(axis.font, '18px serif', 'Axis labels follow the shared UI family and note size');
        assert.match(chapter.font, /^(?:bold|700) 18px monospace$/,
          'Chapter numerals follow the technical family and strong weight');
      });
      await page.locator('#dim-3d-canvas').screenshot({path: path.join(artifacts, `canvas-tokens-${width}.png`)});
    }
    assert.deepEqual(errors, [], 'Runtime errors');
    assert.deepEqual(writes, [], 'Reading and presentation controls never write project data');
    assert.deepEqual(failures, [], 'Typography/localization regressions');
    console.log(`Typography: semantic headings, code reading sizes, separate font roles, token-based canvas text and seven localized desktop/mobile source toolbars passed. Screenshots: ${artifacts}`);
  } finally {
    try { if (browser) await browser.close(); }
    finally { fs.rmSync(siteRoot, {recursive: true, force: true}); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
