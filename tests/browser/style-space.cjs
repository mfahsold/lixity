const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const path = require('node:path');
const os = require('node:os');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-ui-'));
const python = process.env.PYTHON_BIN || path.join(root, '.venv/bin/python');
const fixture = spawnSync(python, ['-c', `
from lixity.api import dashboard
text = """## First chapter

I see the rain. I walk to the window. I drink my coffee.

## Second chapter

The house was sold and the door had been locked. The decision regarding the description of the property was difficult and the rent was high.
"""
print(dashboard(text, language="en", title="Browser regression"))
`], {cwd: root, env: {...process.env, PYTHONPATH: path.join(root, 'src')}, encoding:'utf8',maxBuffer:8*1024*1024});
assert.equal(fixture.status,0,fixture.stderr);

(async () => {
  const browser = await chromium.launch({headless: true});
  try {
  const page = await browser.newPage({viewport: {width: 1280, height: 900}});
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
  fs.writeFileSync(path.join(artifacts,'dashboard.html'), html);
  await page.goto('file://' + path.join(artifacts,'dashboard.html'));
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
    assert.equal(await page.locator('.dim-canvas-wrap').evaluate(element => element.clientHeight), 320);
  });
  await check('loading bars leave room for their labels', async () => {
    const widths = await page.locator('#dimensions .load b').evaluateAll(elements => elements.map(element => element.getBoundingClientRect().width));
    assert.ok(widths.length > 0 && widths.every(width => width >= 40), JSON.stringify(widths));
  });
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
