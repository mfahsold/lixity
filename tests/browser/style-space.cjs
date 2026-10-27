const fs = require('node:fs');
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const assert = require('node:assert/strict');
const path = require('node:path');
const os = require('node:os');
const {pythonFixture} = require('./support/python-fixture.cjs');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-ui-'));
const locales = pythonFixture(`
from lixity.api import dashboard
import json
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
print(json.dumps({language: dashboard(text, language=language, title="Browser regression")
                  for language in ("en", "de", "fr", "es", "it", "pt", "nl")}))
`);

(async () => {
  const browser = await launchChromium();
  try {
  const page = await browser.newPage({viewport: {width: 1280, height: 900}, hasTouch: true});
  const errors = [];
  const results = [];
  page.on('pageerror', error => errors.push(error.message));
  const original = locales.en;
  const payload = {threshold:2.5,axes:[{idx:1},{idx:2},{idx:3}],labels:{status_flagged:'flagged',not_flagged:'Not flagged'},points:[{ch:1,title:'<img src=x onerror="window.tooltipInjected=true">',x:0,y:0,z:0,flagged:false},{ch:2,title:'Second chapter',x:3,y:0,z:0,flagged:true}]};
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
  async function settledScreenshot(target, name) {
    await target.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await target.screenshot({path:path.join(artifacts,name), animations:'disabled'});
  }
  async function observeCanvasLabels(target) {
    await target.addInitScript(() => {
      window.canvasLabels = [];
      const clear = CanvasRenderingContext2D.prototype.clearRect;
      const paint = CanvasRenderingContext2D.prototype.fillText;
      CanvasRenderingContext2D.prototype.clearRect = function(...args) {
        if (this.canvas.id === 'dim-3d-canvas') window.canvasLabels = [];
        return clear.apply(this, args);
      };
      CanvasRenderingContext2D.prototype.fillText = function(text, x, y, ...args) {
        if (this.canvas.id === 'dim-3d-canvas') {
          const metrics = this.measureText(text);
          window.canvasLabels.push({text, font: this.font,
            left: x - metrics.actualBoundingBoxLeft, right: x + metrics.actualBoundingBoxRight,
            top: y - metrics.actualBoundingBoxAscent, bottom: y + metrics.actualBoundingBoxDescent});
        }
        return paint.call(this, text, x, y, ...args);
      };
    });
  }
  async function checkCanvasLabels(target) {
    const {labels, width, height} = await target.evaluate(() => {
      const canvas = document.querySelector('#dim-3d-canvas');
      return {labels: window.canvasLabels, width: canvas.clientWidth, height: canvas.clientHeight};
    });
    assert.ok(labels.some(label => label.text === '+D1'), JSON.stringify(labels));
    assert.ok(labels.some(label => /^\d+$/.test(label.text)), JSON.stringify(labels));
    for (const [index, label] of labels.entries()) {
      assert.ok(Number(label.font.match(/(\d+)px/)[1]) >= 12, JSON.stringify(label));
      assert.match(label.text, /^(?:[+−]D[123]|\d+)$/);
      assert.ok(label.left >= 0 && label.right <= width && label.top >= 0 && label.bottom <= height,
        JSON.stringify({label, width, height}));
      for (const previous of labels.slice(0, index)) {
        assert.ok(label.right <= previous.left || label.left >= previous.right ||
          label.bottom <= previous.top || label.top >= previous.bottom,
        'Canvas labels overlap: ' + JSON.stringify({label, previous}));
      }
    }
  }
  await check('chapter selection persists independently of hover and reading', async () => {
    const selector = page.locator('#dim-chapter-select');
    await selector.selectOption('2');
    assert.equal(await page.locator('#dim-selection').getAttribute('data-chapter'), '2');
    assert.equal(await page.locator('#dim-read-chapter').getAttribute('href'), '#ch-2');
    await page.mouse.move(0, 0);
    assert.equal(await selector.inputValue(), '2');
    await page.locator('#dim-read-chapter').click();
    await page.waitForFunction(() => document.querySelector('#ch-2').classList.contains('flash'));
  });
  await check('planar projection retains scores and exposes its state', async () => {
    await page.locator('#dim-projection').selectOption('d1-d2');
    assert.equal(await page.locator('#dim-3d-canvas').getAttribute('data-projection'), 'd1-d2');
    assert.equal(await page.locator('#dim-ctl-spin').isDisabled(), true);
    await page.locator('#dim-projection').selectOption('3d');
    assert.equal(await page.locator('#dim-ctl-spin').isDisabled(), false);
  });
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
    // The flash lands after the smooth scroll settles (see flashOnArrival).
    await page.waitForFunction(selector => document.querySelector(selector).classList.contains('flash'),
      '#ch-1', {timeout: 2500});
    await page.locator('#dim-scores a[href="#ch-2"]').tap();
    await page.waitForFunction(selector => document.querySelector(selector).classList.contains('flash'),
      '#ch-2', {timeout: 2500});
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
  await check('only supplied axes are described as measured scores', async () => {
    const limited = {...payload, axes: payload.axes.slice(0, 1)};
    const encoded = JSON.stringify(limited).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;').replaceAll('>','&gt;');
    const limitedHtml = original.replace(/data-dim3d="[^"]*"/, () => `data-dim3d="${encoded}"`);
    const single = await browser.newPage({viewport: {width: 1440, height: 1000}});
    try {
      await single.route('http://lixity.test/**', route => route.fulfill({contentType:'text/html', body:limitedHtml}));
      await single.goto('http://lixity.test/');
      await single.locator('#style-tab-dimensions').click();
      await single.locator('#dim-3d-canvas').scrollIntoViewIfNeeded();
      const box = await single.locator('#dim-3d-canvas').boundingBox();
      await single.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      assert.equal(await single.locator('.dim-tt-row').count(), 1);
      assert.equal(await single.locator('#dim-selection dd').count(), 1);
    } finally { await single.close(); }
  });
  await check('cutoff tooltips preserve precise localized configuration', async () => {
    for (const [language, threshold, expected] of [
      ['en',2.00014,'2.00014'], ['de',2.00014,'2,00014'], ['en',0.004,'0.004'],
      ['en',1e-100,'1e-100']
    ]) {
      const precise = {...payload, language, threshold, points:[{...payload.points[0],flagged:true}]};
      if (threshold === 1e-100) precise.threshold_label = expected;
      const encoded = JSON.stringify(precise).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;').replaceAll('>','&gt;');
      const content = original.replace(/data-dim3d="[^"]*"/, () => `data-dim3d="${encoded}"`);
      const precisePage = await browser.newPage({viewport:{width:1440,height:1000}});
      try {
        await precisePage.route('http://lixity.test/**', route => route.fulfill({contentType:'text/html', body:content}));
        await precisePage.goto('http://lixity.test/');
        await precisePage.locator('#style-tab-dimensions').click();
        await precisePage.locator('#dim-3d-canvas').scrollIntoViewIfNeeded();
        const box = await precisePage.locator('#dim-3d-canvas').boundingBox();
        await precisePage.mouse.move(box.x+box.width/2,box.y+box.height/2);
        assert.ok((await precisePage.locator('.dim-tt-flag').textContent()).includes(expected));
      } finally { await precisePage.close(); }
    }
  });
  await check('canvas resolves readable palette through manual and system theme changes', async () => {
    const themePage = await browser.newPage({viewport:{width:1440,height:1000},colorScheme:'light'});
    try {
      await themePage.addInitScript(() => {
        window.axisPaints = [];
        const paint = CanvasRenderingContext2D.prototype.fillText;
        CanvasRenderingContext2D.prototype.fillText = function(text,...args) {
          if (String(text).includes('+D1')) window.axisPaints.push(this.fillStyle);
          return paint.call(this,text,...args);
        };
      });
      await themePage.route('http://lixity.test/**', route => route.fulfill({contentType:'text/html', body:original}));
      await themePage.goto('http://lixity.test/');
      await themePage.locator('#style-tab-dimensions').click();
      for (const [system,manual] of [['light','light'],['light','dark'],['dark','light'],['dark','dark']]) {
        await themePage.emulateMedia({colorScheme:system});
        const before = await themePage.evaluate(() => window.axisPaints.length);
        await themePage.evaluate(theme => document.documentElement.setAttribute('data-theme',theme),manual);
        await themePage.waitForFunction(count => window.axisPaints.length>count,before);
        const expected = await themePage.evaluate(() => {
          const probe=document.createElement('span');probe.style.color='var(--muted)';document.body.appendChild(probe);
          const color=getComputedStyle(probe).color;probe.remove();
          const context=document.createElement('canvas').getContext('2d');context.fillStyle=color;return context.fillStyle;
        });
        const painted = await themePage.evaluate(() => window.axisPaints.at(-1));
        assert.ok(await themePage.evaluate(count => window.axisPaints.length>count,before));
        assert.equal(painted,expected,system+' OS / '+manual+' manual');
        await themePage.locator('#dimensions').evaluate(element => window.scrollTo({top:scrollY+element.getBoundingClientRect().top-(document.querySelector('.toolbar')?.offsetHeight||0)-12,behavior:'instant'}));
        await settledScreenshot(themePage,`theme-${system}-${manual}.png`);
      }
    } finally { await themePage.close(); }
  });
  for (const [language, localized] of Object.entries(locales)) {
    for (const width of [1440, 320]) {
      await check(`${language} style help and chapter selection at ${width}px`, async () => {
        const localizedPage = await browser.newPage({viewport:{width,height:1000}, hasTouch:width===320, reducedMotion:'reduce'});
        try {
          localizedPage.on('pageerror', error => errors.push(error.message));
          await observeCanvasLabels(localizedPage);
          await localizedPage.route('http://lixity.test/**', route => route.fulfill({contentType:'text/html', body:localized}));
          await localizedPage.goto('http://lixity.test/');
          await localizedPage.locator('#style-tab-dimensions').click();
          const dimensions = localizedPage.locator('#dimensions');
          assert.ok((await dimensions.locator('.dim-guide').textContent()).length > 50);
          assert.ok((await dimensions.locator('.dim-coverage').textContent()).includes('3 / 3'));
          await localizedPage.locator('#dim-chapter-select').selectOption('2');
          assert.equal(await localizedPage.locator('#dim-selection').getAttribute('data-chapter'), '2');
          const row = localizedPage.locator('#dim-scores tbody tr').nth(1);
          assert.deepEqual(await localizedPage.locator('#dim-selection dd').allTextContents(), await row.locator('td.num').allTextContents());
          const measuredAxes = await localizedPage.locator('#dim-3d-canvas').evaluate(element => JSON.parse(element.getAttribute('data-dim3d')).axes);
          const meanings = await localizedPage.locator('#dim-selection .dim-axis-meaning').allTextContents();
          measuredAxes.forEach((axis, index) => {
            if (axis.pos) assert.ok(meanings[index].includes('+ ' + axis.pos));
            if (axis.neg) assert.ok(meanings[index].includes('− ' + axis.neg));
          });
          assert.ok((await localizedPage.locator('#dim-selection').textContent()).includes(await row.locator('td').last().textContent()));
          const spatial = await localizedPage.locator('#dim-3d-canvas').evaluate(element => element.toDataURL());
          const layout = await dimensions.evaluate(element => {
            const box = selector => {
              const {x,y,width,height} = element.querySelector(selector).getBoundingClientRect();
              return {x,y,width,height};
            };
            return {panel: element.getBoundingClientRect().width, plot: box('.dim-3d-box'),
              inspector: box('.dim-selection-panel'), cards: box('.dim-cards-col'), scores: box('.dim-score-wrap')};
          });
          if (width === 1440) {
            assert.ok(layout.inspector.x >= layout.plot.x + layout.plot.width,
              'Chapter inspector must sit beside the desktop plot: ' + JSON.stringify(layout));
            assert.ok(Math.abs(layout.inspector.y - layout.plot.y) <= 1, JSON.stringify(layout));
          } else {
            assert.ok(layout.inspector.y >= layout.plot.y + layout.plot.height, JSON.stringify(layout));
          }
          assert.ok(layout.cards.y >= Math.max(layout.plot.y + layout.plot.height,
            layout.inspector.y + layout.inspector.height), JSON.stringify(layout));
          assert.ok(Math.abs(layout.scores.width - layout.panel) <= 2,
            'Chapter scores must use the panel width: ' + JSON.stringify(layout));
          assert.ok(layout.scores.y >= layout.cards.y + layout.cards.height, JSON.stringify(layout));
          await checkCanvasLabels(localizedPage);
          await localizedPage.locator('#dim-projection').selectOption('d1-d2');
          await checkCanvasLabels(localizedPage);
          await localizedPage.locator('#dim-3d-canvas').screenshot({path:path.join(artifacts, `${language}-${width}-canvas.png`)});
          assert.notEqual(await localizedPage.locator('#dim-3d-canvas').evaluate(element => element.toDataURL()), spatial);
          assert.equal(await localizedPage.locator('#dim-ctl-left').isDisabled(), true);
          await localizedPage.locator('#dim-expert summary').click();
          const coefficients = await localizedPage.locator('#dim-expert td.num').allTextContents();
          assert.ok(coefficients.length > 0 && coefficients.every(value => /^[+-]?\d+[.,]\d{3}$/.test(value)));
          assert.equal(await localizedPage.locator('#dim-expert').evaluate(element => element.textContent.includes('dim_')), false);
          await localizedPage.locator('#dim-expert summary').click();
          assert.ok(await localizedPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
          await dimensions.evaluate(element => {
            const toolbar = document.querySelector('.toolbar');
            window.scrollTo({top:scrollY+element.getBoundingClientRect().top-(toolbar?.offsetHeight||0)-12, behavior:'instant'});
          });
          await settledScreenshot(localizedPage, `${language}-${width}-overview.png`);
          if (width === 320) {
            await localizedPage.locator('.dim-selection-panel').evaluate(element => {
              const toolbar = document.querySelector('.toolbar');
              window.scrollTo({top:scrollY+element.getBoundingClientRect().top-(toolbar?.offsetHeight||0)-12, behavior:'instant'});
            });
            await settledScreenshot(localizedPage, `${language}-${width}-selection.png`);
          }
        } finally { await localizedPage.close(); }
      });
    }
  }
  // Final visual evidence uses the unmodified chart and matching score table.
  await page.route('http://lixity.test/**', route => route.fulfill({contentType: 'text/html', body: original}));
  await page.goto('http://lixity.test/');
  await page.locator('#style-tab-dimensions').click();
  await page.locator('#dimensions').evaluate(element => window.scrollTo({top:scrollY+element.getBoundingClientRect().top-(document.querySelector('.toolbar')?.offsetHeight||0)-12,behavior:'instant'}));
  await settledScreenshot(page, 'mobile.png');
  await page.setViewportSize({width:1280,height:900});
  await page.locator('#dimensions').evaluate(element => window.scrollTo({top:scrollY+element.getBoundingClientRect().top-(document.querySelector('.toolbar')?.offsetHeight||0)-12,behavior:'instant'}));
  await settledScreenshot(page, 'desktop.png');
  await check('console has no runtime errors', () => assert.deepEqual(errors, []));
  console.log(JSON.stringify({results,artifacts}, null, 2));
  process.exitCode = results.some(result => !result.passed) ? 1 : 0;
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
