const {launchChromium, playwrightModule} = require('../../scripts/browser_tools.cjs');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
const {expect} = require(path.join(playwrightModule, 'test'));

const root = path.resolve(__dirname, '../..');
const assets = path.join(root, 'src/lixity/ui/assets');
const css = ['design-tokens.css', 'dashboard.css'].map(file => fs.readFileSync(path.join(assets, file), 'utf8')).join('\n');
const script = fs.readFileSync(path.join(assets, 'tooltips.js'), 'utf8');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-tooltips-'));
const explanation = 'A dossier holds synthetic notes and optional passage references; it is not an accepted claim.';

(async () => {
  const browser = await launchChromium();
  try {
    const errors = [];
    for (const width of [1440, 320]) {
      // Keep each fixture's pointer, focus and touch state independent. Replacing
      // DOM under the previous fixture's stationary pointer can queue a genuine
      // mouseover after the first keyboard-focus assertion has started.
      const page = await browser.newPage({hasTouch: true, viewport: {width, height: 900}});
      page.on('pageerror', error => errors.push(error.message));
      await page.setContent(`<!doctype html><html lang="en"><style>${css}</style>
        <style>
          #navigation {position:fixed;top:150px;left:20px}
          #composer {position:fixed;top:205px;left:20px;right:20px}
          #composer summary {width:max-content;max-width:100%}
          dialog {width:min(30rem, 90vw);padding:1rem}
        </style><body>
        <button id="navigation" type="button" title="Show sources">Sources</button>
        <button id="second-action" type="button" data-help="Second action explanation." style="position:fixed;top:150px;left:120px">Other</button>
        <details id="composer"><summary id="help" data-help="${explanation}" aria-describedby="hint">Create dossier</summary></details>
        <span id="hint" hidden>Preserved description</span>
        <div id="scroll-panel" style="position:fixed;top:350px;left:20px;height:80px;overflow:auto">
          <button id="scroll-help" data-help="Nested scrolling help">Help</button><div style="height:400px"></div>
        </div>
        <dialog id="modal"><span class="help" id="modal-help" tabindex="0" data-help="Synthetic native dialog help.">Help</span>
          <input id="modal-input" aria-label="Synthetic field" data-help="Synthetic field guidance."></dialog>
        <div class="pswp" id="vendor-viewer" hidden><button id="vendor-close" title="Close synthetic viewer">Close</button></div>
        <div role="button" style="position:fixed;top:460px;left:20px"><span class="help" id="nested-help" tabindex="0" data-help="Nested term explanation.">Term</span></div>
        <script>
          window.navigationClicks=0;document.querySelector('#navigation').addEventListener('click',()=>window.navigationClicks++);
          document.querySelector('#modal').addEventListener('keydown',event=>{
            if(event.key==='Escape'&&event.target.id==='modal-input')event.currentTarget.close();
          });
          document.querySelector('#vendor-viewer').addEventListener('keydown',event=>{
            if(event.key==='Escape')event.currentTarget.hidden=true;
          });
        </script>
        <script>${script}</script></body></html>`);
      const help = page.locator('#help');
      const tip = page.locator('#lixity-tooltip');
      const copy = tip.locator('.tooltip-copy');

      await page.locator('#scroll-help').focus();
      await expect(copy).toHaveText('Nested scrolling help');
      await page.locator('#scroll-panel').evaluate(el => { el.scrollTop = 100; });
      await expect(tip).toHaveAttribute('aria-hidden', 'true');

      await page.locator('#navigation').focus();
      await expect(copy).toHaveText('Show sources');
      await page.locator('#navigation').evaluate(el => { el.title = 'Hide sources'; });
      await expect(copy).toHaveText('Hide sources');
      await page.mouse.move(0, 0);
      await page.locator('#navigation').hover();
      await expect(copy).toHaveText('Hide sources');
      await page.locator('#navigation').evaluate(el => { el.removeAttribute('title'); el.removeAttribute('data-tip'); });
      await expect(tip).toHaveAttribute('aria-hidden', 'true');

      // The composer appears below navigation after research initialization.
      // Its help must not trap a native click on the preceding tab.
      await help.hover();
      await expect(tip).toBeVisible();
      await page.locator('#navigation').click({timeout: 1500});
      assert.equal(await page.evaluate(() => window.navigationClicks), 1);

      await help.focus();
      await expect(copy).toHaveText(explanation);
      await expect(tip).toHaveCSS('backdrop-filter', 'blur(12px)');
      await page.locator('html').evaluate(node => node.style.setProperty('--glass-blur', '4px'));
      await expect(tip).toHaveCSS('backdrop-filter', 'blur(4px)');
      await page.locator('html').evaluate(node => node.style.removeProperty('--glass-blur'));
      assert.equal(await help.getAttribute('aria-describedby'), 'hint lixity-tooltip');
      await page.keyboard.press('Escape');
      await expect(tip).toHaveAttribute('aria-hidden', 'true');
      assert.equal(await help.getAttribute('aria-describedby'), 'hint');
      assert.equal(await page.evaluate(() => document.activeElement.id), 'help');
      assert.equal(await page.locator('#composer').getAttribute('open'), null,
        'Showing or dismissing help must preserve the native disclosure');

      for (const event of ['lixity:viewchange', 'lixity:workbench-change']) {
        await help.evaluate(el => el.blur());
        await help.focus();
        await expect(tip).toBeVisible();
        await page.evaluate(name => document.dispatchEvent(new Event(name)), event);
        await expect(tip).toHaveAttribute('aria-hidden', 'true');
        assert.equal(await help.getAttribute('aria-describedby'), 'hint');
      }
      await help.evaluate(el => el.blur());
      await help.focus();
      await page.locator('#composer').evaluate(el => { el.hidden = true; window.dispatchEvent(new Event('resize')); });
      await expect(tip).toHaveAttribute('aria-hidden', 'true');
      await page.locator('#composer').evaluate(el => { el.hidden = false; });

      await help.hover();
      await tip.hover();
      await page.waitForTimeout(200);
      await expect(tip).toHaveAttribute('aria-hidden', 'false');
      await page.mouse.move(0, 0);
      await expect(tip).toHaveAttribute('aria-hidden', 'true');

      await help.evaluate(el => { el.dataset.help = 'A longer synthetic localized explanation. '.repeat(600); el.blur(); });
      await help.focus();
      await expect(tip).toBeVisible();
      assert.ok(await tip.evaluate((el, trigger) => {
        const box = el.getBoundingClientRect();
        const anchor = document.querySelector(trigger).getBoundingClientRect();
        return box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight
          && (box.top >= anchor.bottom || box.bottom <= anchor.top);
      }, '#help'), 'Long help stays in the viewport without covering its trigger');
      assert.ok(await tip.evaluate(el => el.scrollHeight > el.clientHeight), 'Long help remains scrollable');
      await page.screenshot({path: path.join(artifacts, `long-help-context-${width}.png`)});
      await tip.hover();
      await page.mouse.wheel(0, 300);
      await expect.poll(() => tip.evaluate(el => el.scrollTop)).toBeGreaterThan(0);
      await tip.screenshot({path: path.join(artifacts, `long-help-${width}.png`)});
      await page.locator('#navigation').click({timeout: 1500});
      assert.equal(await page.evaluate(() => window.navigationClicks), 2);

      await page.locator('#navigation').evaluate(el => { el.dataset.help = 'Native action explanation.'; el.blur(); });
      await page.locator('#navigation').focus();
      await expect(copy).toHaveText('Native action explanation.');
      await page.locator('#navigation').click();
      await expect(tip).toHaveAttribute('aria-hidden', 'true');
      await page.locator('#navigation').focus();
      await expect(tip).toHaveAttribute('aria-hidden', 'true');
      await page.locator('#second-action').hover();
      await expect(tip).toHaveAttribute('aria-hidden', 'false');
      await expect(copy).toHaveText('Second action explanation.');
      await page.locator('#second-action').evaluate(el => { el.removeAttribute('data-help'); });
      await help.focus();
      await page.locator('#navigation').focus();
      await expect(copy).toHaveText('Native action explanation.');
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#navigation').evaluate(el => el.matches(':hover')), false);
      await page.locator('#navigation').press('Enter');
      await expect(tip).toHaveAttribute('aria-hidden', 'true');
      await page.locator('#navigation').hover();
      await expect(tip).toHaveAttribute('aria-hidden', 'false');
      await expect(copy).toHaveText('Native action explanation.');
      await page.keyboard.press('Escape');
      await page.locator('#navigation').evaluate(el => { el.removeAttribute('data-help'); });

      await page.locator('#vendor-viewer').evaluate(el => { el.hidden = false; });
      await page.locator('#vendor-close').focus();
      assert.equal(await page.locator('#vendor-close').getAttribute('title'), 'Close synthetic viewer',
        'PhotoSwipe controls retain their native title instead of shared tooltip ownership');
      await expect(tip).toHaveAttribute('aria-hidden', 'true');
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#vendor-viewer').evaluate(el => el.hidden), true,
        'PhotoSwipe keeps its own one-Escape close behavior');

      // A trigger near the viewport bottom uses the available space above it.
      await help.evaluate(el => { el.closest('details').style.top = '850px'; el.blur(); });
      await help.focus();
      assert.ok(await tip.evaluate(el => {
        const box = el.getBoundingClientRect();
        return box.top >= 0 && box.bottom <= document.querySelector('#help').getBoundingClientRect().top;
      }));
      await page.keyboard.press('Escape');

      // Touch toggles standalone help, without toggling a native disclosure.
      await help.evaluate(el => {
        el.closest('details').style.top = '205px';
        el.dataset.help = 'Synthetic touch help.';
        el.classList.add('help');
      });
      await help.tap();
      await expect(tip).toHaveAttribute('aria-hidden', 'false');
      await help.tap();
      await expect(tip).toHaveAttribute('aria-hidden', 'true');
      assert.equal(await page.locator('#composer').getAttribute('open'), null);

      const nested = page.locator('#nested-help');
      await nested.focus();
      await expect(copy).toHaveText('Nested term explanation.');
      await nested.press('Enter');
      await expect(tip).toHaveAttribute('aria-hidden', 'true');
      await nested.press('Space');
      await expect(tip).toHaveAttribute('aria-hidden', 'false');
      await page.keyboard.press('Escape');

      await page.evaluate(() => document.querySelector('#modal').showModal());
      await page.locator('#modal-help').focus();
      await expect(page.locator('#modal #lixity-tooltip')).toBeVisible();
      await page.keyboard.press('Enter');
      await expect(tip).toHaveAttribute('aria-hidden', 'true');
      await page.keyboard.press('Space');
      await expect(tip).toHaveAttribute('aria-hidden', 'false');
      await page.keyboard.press('Escape');
      await expect(tip).toHaveAttribute('aria-hidden', 'true');
      assert.equal(await page.locator('#modal').getAttribute('open'), '', 'Escape dismisses help before its modal');
      await page.locator('#modal-input').focus();
      await expect(copy).toHaveText('Synthetic field guidance.');
      await page.keyboard.press('Escape');
      await expect(tip).toHaveAttribute('aria-hidden', 'true');
      assert.equal(await page.locator('#modal').getAttribute('open'), '',
        'Input help consumes Escape before a surrounding dialog Escape handler');
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#modal').getAttribute('open'), null,
        'After help closes, a subsequent Escape reaches the dialog');
      await page.close();
    }
    assert.deepEqual(errors, []);
    console.log('Tooltips: native navigation, hover persistence, long scrolling help, keyboard/Escape, touch and dialog top layer passed; ' + artifacts);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
