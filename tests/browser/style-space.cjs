const fs = require('node:fs');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const assert = require('node:assert/strict');
const path = require('node:path');
const os = require('node:os');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-ui-'));
const python = process.env.PYTHON_BIN || path.join(root, '.venv/bin/python');
const fixture = spawnSync(python, ['-c', `
from lixity.api import dashboard
# Three varying chapters above the diversity floor expose optional style axes.
text = "## First chapter\\n\\n" + (
    "I see the rain. I walk to the window. I drink my coffee. "
) * 10
text += "\\n\\n## Second chapter\\n\\n" + (
    "The house was sold and the door had been locked. The decision regarding "
    "the description of the property was difficult and the rent was high. "
) * 6
text += "\\n\\n## Third chapter\\n\\n" + (
    'Rain falls. "Come closer!" A bird crosses the garden while the river rises. '
) * 10
text += "\\n\\nI walk home." * 100
text = text.replace("First chapter", '<img src=x onerror="window.tooltipInjected=true">', 1)
print(dashboard(text, language="en", title="Browser regression"))
`], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding:'utf8',maxBuffer:8*1024*1024});
assert.equal(fixture.status,0,fixture.stderr);

(async () => {
  const browser = await launchChromium();
  try {
  const page = await browser.newPage({viewport: {width: 1280, height: 900}, hasTouch: true});
  const errors = [];
  const results = [];
  page.on('pageerror', error => errors.push(error.message));
  const original = fixture.stdout;
  const payload = {threshold:2.5,axes:[],points:[{ch:1,title:'<img src=x onerror="window.tooltipInjected=true">',x:0,y:0,z:0,flagged:false},{ch:2,title:'Second chapter',x:3,y:0,z:0,flagged:true}]};
  const encoded = JSON.stringify(payload).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;').replaceAll('>','&gt;');
  const html = original.replace(/data-dim3d="[^"]*"/, () => `data-dim3d="${encoded}"`);
  await page.addInitScript(() => {
    window.frameCount = 0;
    const frame = window.requestAnimationFrame.bind(window);
    window.requestAnimationFrame = callback => frame(time => { window.frameCount++; callback(time); });
  });
  await page.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: html}));
  await page.goto('http://lixity.test/');
  await page.locator('#style-tab-dimensions').click();
  await page.locator('#dimensions').scrollIntoViewIfNeeded();
  page.setDefaultTimeout(5000);
  async function check(name, run) {
    try { await run(); results.push({name, passed: true}); }
    catch (error) { results.push({name, passed: false, error: error.message}); }
  }
  await check('idle canvas does not animate', async () => {
    await page.waitForTimeout(150);
    const before = await page.evaluate(() => window.frameCount);
    await page.waitForTimeout(200);
    assert.ok(await page.evaluate(() => window.frameCount) - before <= 1);
  });
  await check('toggle exposes pressed state', async () => {
    await page.locator('#dim-ctl-traj').click();
    assert.equal(await page.locator('#dim-ctl-traj').getAttribute('aria-pressed'), 'false');
    await page.locator('#dim-ctl-traj').click();
    assert.equal(await page.locator('#dim-ctl-traj').getAttribute('aria-pressed'), 'true');
  });
  await check('a hidden style tab pauses a spinning canvas', async () => {
    await page.locator('#dim-ctl-spin').click();
    await page.locator('#style-tab-bands').click();
    await page.waitForTimeout(100);
    const before = await page.evaluate(() => window.frameCount);
    await page.waitForTimeout(200);
    assert.ok(await page.evaluate(() => window.frameCount) - before <= 1);
    await page.locator('#style-tab-dimensions').click();
    await page.waitForTimeout(100);
    assert.ok(await page.evaluate(() => window.frameCount) - before > 1, 'The visible canvas resumes');
    await page.locator('#dim-ctl-reset').click();
  });
  await check('chapter scores provide semantic text and safe chapter links', async () => {
    assert.equal(await page.locator('#dim-scores tbody tr').count(), 3);
    assert.equal(await page.locator('#dim-scores caption').textContent(), 'Chapter scores');
    assert.equal(await page.locator('#dim-scores a[href="#ch-1"]').textContent(), '1. ' + payload.points[0].title);
    assert.equal(await page.locator('#dim-scores img, #dim-scores script').count(), 0);
    assert.ok(await page.locator('#dim-scores').textContent().then(value => value.includes('Not flagged')));
    const scores = await page.locator('#dim-scores td.num').allTextContents();
    assert.equal(scores.length, 9);
    assert.ok(scores.every(score => /^[+-]?\d+\.\d{2}$/.test(score)), JSON.stringify(scores));
    const chapter = page.locator('#dim-scores a[href="#ch-1"]');
    await chapter.focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#ch-1').evaluate(element => element.classList.contains('flash')), true);
    await page.locator('#dim-scores a[href="#ch-2"]').tap();
    assert.equal(await page.locator('#ch-2').evaluate(element => element.classList.contains('flash')), true);
    assert.equal(await page.evaluate(() => Boolean(window.tooltipInjected)), false);
  });
  await check('chapter score links work without JavaScript', async () => {
    const fallback = await browser.newPage({javaScriptEnabled: false, viewport: {width: 320, height: 844}});
    try {
      await fallback.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: original}));
      await fallback.goto('http://lixity.test/');
      assert.equal(await fallback.locator('#dim-scores tbody tr').count(), 3);
      await fallback.locator('#dim-scores a[href="#ch-2"]').click();
      assert.ok(fallback.url().endsWith('#ch-2'));
    } finally { await fallback.close(); }
  });
  await check('keyboard controls rotate and zoom the existing canvas', async () => {
    assert.equal(await page.locator('.dim-navigation button').count(), 6);
    await page.locator('#dim-ctl-reset').click();
    await page.locator('#dim-3d-canvas').scrollIntoViewIfNeeded();
    const initial = await page.locator('#dim-3d-canvas').screenshot();
    for (const id of ['dim-ctl-left', 'dim-ctl-right', 'dim-ctl-up', 'dim-ctl-down', 'dim-ctl-zoom-in', 'dim-ctl-zoom-out']) {
      const control = page.locator('#' + id);
      assert.ok((await control.textContent()).trim().length > 0);
      await control.focus();
      await page.keyboard.press('Enter');
      assert.notDeepEqual(await page.locator('#dim-3d-canvas').screenshot(), initial, id);
      await page.locator('#dim-ctl-reset').click();
      assert.deepEqual(await page.locator('#dim-3d-canvas').screenshot(), initial, id + ' reset');
    }
    await page.locator('#dim-ctl-zoom-in').tap();
    assert.notDeepEqual(await page.locator('#dim-3d-canvas').screenshot(), initial, 'touch zoom');
    await page.locator('#dim-ctl-reset').click();
  });
  await check('chapter title is text, not executable markup', async () => {
    await page.locator('#dim-3d-canvas').scrollIntoViewIfNeeded();
    const box = await page.locator('#dim-3d-canvas').boundingBox();
    assert.equal(await page.evaluate(({x,y}) => document.elementFromPoint(x,y)?.id,{x:box.x+box.width/2,y:box.y+box.height/2}), 'dim-3d-canvas');
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    assert.equal(await page.locator('.dim-tt-title').textContent(), payload.points[0].title);
    assert.equal(await page.evaluate(() => Boolean(window.tooltipInjected)), false);
  });
  await check('zoomed point hit testing matches drawing', async () => {
    await page.locator('#dim-3d-canvas').scrollIntoViewIfNeeded();
    const box = await page.locator('#dim-3d-canvas').boundingBox();
    for (let iteration = 0; iteration < 8; iteration++) await page.locator('#dim-3d-canvas').dispatchEvent('wheel',{deltaY:-100});
    const zoom = Math.pow(1.08,8);
    const radius = Math.min(box.width,box.height)*0.4;
    const normalized = 3/(2.5*1.35)*radius*zoom;
    const depth = -normalized*Math.sin(0.55)*Math.cos(0.35);
    const scale = 520/(700+depth);
    const screenX = box.x+box.width/2+normalized*Math.cos(0.55)*scale;
    const screenY = box.y+box.height/2-normalized*Math.sin(0.55)*Math.sin(0.35)*scale;
    await page.mouse.move(screenX,screenY);
    assert.equal(await page.locator('.dim-tt-title').textContent(),'Second chapter');
    assert.equal(await page.locator('#dim-3d-tooltip').isVisible(),true);
    await page.locator('#dim-ctl-reset').click();
  });
  await check('mobile dimensions fit viewport', async () => {
    await page.setViewportSize({width: 390, height: 844});
    const dimensions = await page.locator('#dimensions').evaluate(element => ({scroll:element.scrollWidth,width:element.clientWidth}));
    assert.ok(dimensions.scroll <= dimensions.width + 1, JSON.stringify(dimensions));
    assert.equal(await page.locator('.dim-canvas-wrap').evaluate(element => element.clientHeight), 260);
  });
  await check('loading bars leave room for their labels', async () => {
    const widths = await page.locator('#dimensions .load b').evaluateAll(elements => elements.map(element => element.getBoundingClientRect().width));
    assert.ok(widths.length > 0 && widths.every(width => width >= 40), JSON.stringify(widths));
  });
  await check('touch targets remain readable in a scrolling paragraph strip', async () => {
    await page.setViewportSize({width: 320, height: 844});
    const targets = await page.locator('.chip, .dim-ctl').evaluateAll(elements => elements.map(element => {
      const box = element.getBoundingClientRect();
      return {width: box.width, height: box.height};
    }));
    assert.ok(targets.every(box => box.width >= 44 && box.height >= 44), JSON.stringify(targets));
    const strip = page.locator('#ch-3 .strip');
    assert.ok(await strip.evaluate(element => element.scrollWidth > element.clientWidth));
    const last = strip.locator('.chip').last();
    await last.tap();
    assert.equal(await last.getAttribute('aria-expanded'), 'true');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.locator('#ch-3').screenshot({path: path.join(artifacts, 'paragraph-touch.png')});
  });
  // Final visual evidence uses the unmodified chart and matching score table.
  await page.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: original}));
  await page.goto('http://lixity.test/');
  await page.locator('#style-tab-dimensions').click();
  await page.locator('#dimensions').screenshot({path:path.join(artifacts,'mobile.png')});
  await page.setViewportSize({width:1280,height:900});
  await page.locator('#dimensions').screenshot({path:path.join(artifacts,'desktop.png')});
  await check('console has no runtime errors', () => assert.deepEqual(errors, []));
  console.log(JSON.stringify({results,artifacts}, null, 2));
  process.exitCode = results.some(result => !result.passed) ? 1 : 0;
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
