const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const {spawnSync} = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '../..');
const fixture = spawnSync(process.env.PYTHON_BIN || path.join(root, '.venv/bin/python'), ['-c', `
from lixity.pipeline import analyze_document, resolve_document_config
from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui import render_dashboard
text = "## Eins\\n\\nIch gehe. Ich sehe den Regen.\\n\\n## Zwei\\n\\nDas Haus wurde verkauft und die Tür war verschlossen.\\n"
config, language = resolve_document_config(text, "de")
result = analyze_document(text, config, FingerprintThresholds())
result.fingerprint.fdr_flagged = {1: ["asl"]}
print(render_dashboard(result.chapters, result.paragraphs, metrics=result.metrics,
    fingerprint=result.fingerprint, labels=language.labels, language_key="de", controls=True))
`], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding: 'utf8', maxBuffer: 8*1024*1024});
assert.equal(fixture.status, 0, fixture.stderr);

(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 900}});
    const submissions = [];
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://lixity.test/**', async route => {
      if (route.request().url().includes('/api/')) {
        if (route.request().url().endsWith('/settings')) submissions.push(route.request().postDataJSON());
        await route.fulfill({json: {ok: true, locked: true, records: [], message: 'Test'}});
      } else await route.fulfill({contentType: 'text/html', body: fixture.stdout});
    });
    await page.goto('http://lixity.test/');
    await page.locator('.settings-advanced summary').click();
    assert.equal(await page.locator('#set-z-mild').inputValue(), '2.5');
    assert.equal(await page.locator('#set-fdr-q').inputValue(), '0.05');
    await page.locator('#set-z-strong').fill('1.5');
    await page.locator('[data-action="settings"]').click();
    assert.equal(submissions.length, 0);
    assert.ok(await page.locator('#set-z-strong').evaluate(input => input.validationMessage.length > 0));
    await page.locator('#settings-reset').click();
    assert.equal(await page.locator('#set-z-strong').inputValue(), '3.5');
    assert.equal(submissions.length, 0);
    await page.locator('#set-z-mild').fill('2.1');
    await Promise.all([
      page.waitForResponse(response => response.url().endsWith('/api/settings')),
      page.locator('[data-action="settings"]').click(),
    ]);
    assert.equal(submissions.length, 1);
    assert.equal(submissions[0].z_mild, 2.1);
    assert.equal(submissions[0].fdr_q, 0.05);
    await page.locator('#heatmap-fdr-only').check();
    assert.equal(await page.locator('#heatmap tbody tr:visible').count(), 1);
    await page.locator('#heatmap-fdr-only').uncheck();
    assert.equal(await page.locator('#heatmap tbody tr:visible').count(), 2);
    const fonts = await page.evaluate(() => ({title: getComputedStyle(document.querySelector('.project-header h1')).fontFamily,
      body: getComputedStyle(document.body).fontFamily, heading: getComputedStyle(document.querySelector('#heatmap h2')).fontFamily}));
    assert.match(fonts.title, /Palatino/);
    assert.equal(fonts.body, fonts.heading);
    assert.notEqual(fonts.title, fonts.body);
    await page.setViewportSize({width: 390, height: 844});
    assert.ok(await page.locator('#settings-form').evaluate(form => form.scrollWidth <= form.clientWidth));
    assert.deepEqual(errors, []);
    console.log('Settings: localized values, validation, reset, payload, FDR filter, title-only serif and mobile layout passed');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
