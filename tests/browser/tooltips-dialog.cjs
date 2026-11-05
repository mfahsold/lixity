const {launchChromium, launchFirefox, playwrightModule} = require('../../scripts/browser_tools.cjs');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
const {expect} = require(path.join(playwrightModule, 'test'));

const assets = path.resolve(__dirname, '../../src/lixity/ui/assets');
const css = ['design-tokens.css', 'components.css', 'dashboard.css', 'speech-player.css']
  .map(file => fs.readFileSync(path.join(assets, file), 'utf8')).join('\n');
const script = ['vendor/preact-10.29.8.min.js', 'vendor/htm-3.1.1.umd.js', 'component-layer.js', 'tooltips.js']
  .map(file => fs.readFileSync(path.join(assets, file), 'utf8')).join('\n');
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'lixity-tooltips-dialog-'));
const engine = process.argv.includes('--firefox') ? 'firefox' : 'chromium';
const explanation = 'Erlaube dieser Seite den Mikrofonzugriff. Lies den Text in deiner natürlichen Stimme vor. Beende die Aufnahme, höre sie an und prüfe den gesprochenen Text vor dem Speichern.';

(async () => {
  const browser = engine === 'firefox'
    ? await launchFirefox() : await launchChromium();
  const errors = [];
  try {
    for (const viewport of [{width: 1830, height: 705}, {width: 320, height: 700}]) {
      const page = await browser.newPage({viewport, reducedMotion: 'reduce'});
      page.on('pageerror', error => errors.push(error.message));
      await page.setContent(`<!doctype html><html lang="de" data-theme="dark"><style>${css}</style><body>
        <button id="outside" data-help="Hilfe außerhalb des Dialogs.">Projekt</button>
        <dialog class="lixity-modal" id="modal-speech" aria-labelledby="speech-title">
          <div class="modal-card"><header class="modal-header"><h3 id="speech-title">Autorenstimme</h3>
            <button id="close" type="button">Schließen</button></header>
            <div class="modal-body"><div style="height:420px">Synthetischer Lesetext</div>
              <button id="record" class="ctl" type="button" data-help="${explanation}">Aufnahme starten</button>
              <div style="height:500px">Gespeicherte Aufnahmen</div>
            </div>
          </div>
        </dialog><script>${script}</script></body></html>`);
      const dialog = page.locator('dialog');
      const trigger = page.locator('#record');
      const tip = page.locator('#lixity-tooltip');
      await dialog.evaluate(el => el.showModal());
      await trigger.evaluate(el => el.scrollIntoView({block: 'center'}));
      await trigger.focus();
      await expect(tip).toHaveAttribute('aria-hidden', 'false');
      await expect(tip.locator('.tooltip-copy')).toHaveText(explanation);
      await page.screenshot({path: path.join(artifacts, `${engine}-${viewport.width}.png`)});
      const geometry = await page.evaluate(() => {
        const dialog = document.querySelector('dialog');
        const tip = document.querySelector('#lixity-tooltip');
        const trigger = document.querySelector('#record');
        return {dialog: dialog.getBoundingClientRect().toJSON(), tip: tip.getBoundingClientRect().toJSON(),
          trigger: trigger.getBoundingClientRect().toJSON(), left: tip.style.left, top: tip.style.top,
          position: getComputedStyle(tip).position, filter: getComputedStyle(dialog).backdropFilter,
          scrollWidth: tip.scrollWidth, clientWidth: tip.clientWidth};
      });
      fs.writeFileSync(path.join(artifacts, `${engine}-${viewport.width}.json`), JSON.stringify(geometry, null, 2));
      assert.ok(geometry.tip.width >= Math.min(240, geometry.dialog.width - 24),
        `Dialog help must retain a readable width: ${JSON.stringify(geometry)}; ${artifacts}`);
      assert.ok(geometry.tip.left >= geometry.dialog.left && geometry.tip.right <= geometry.dialog.right,
        `Help must fit the dialog horizontally: ${JSON.stringify(geometry)}`);
      assert.ok(geometry.tip.top >= geometry.dialog.top && geometry.tip.bottom <= geometry.dialog.bottom,
        `Help must fit the dialog vertically: ${JSON.stringify(geometry)}`);
      assert.ok(geometry.tip.bottom <= geometry.trigger.top || geometry.tip.top >= geometry.trigger.bottom,
        'Help must leave its control available');
      assert.ok(geometry.scrollWidth <= geometry.clientWidth + 1, 'Help must wrap without horizontal clipping');
      assert.equal(await tip.evaluate(el => el.parentElement.id), 'modal-speech');
      await page.locator('#close').focus();
      await trigger.hover();
      await expect(tip).toHaveAttribute('aria-hidden', 'false');
      const hovered = await tip.boundingBox();
      assert.ok(hovered.width >= Math.min(240, geometry.dialog.width - 24), 'Pointer help must also retain its width');
      assert.ok(hovered.x >= geometry.dialog.left && hovered.x + hovered.width <= geometry.dialog.right,
        'Pointer placement must fit the dialog horizontally');
      await page.screenshot({path: path.join(artifacts, `${engine}-${viewport.width}-hover.png`)});
      await trigger.focus();
      await page.keyboard.press('Escape');
      await expect(tip).toHaveAttribute('aria-hidden', 'true');
      assert.equal(await dialog.getAttribute('open'), '', 'Escape dismisses help before the dialog');
      await page.locator('.modal-body').evaluate((body, help) => {
        body.innerHTML = '<div style="height:130px">Synthetic form</div>' +
          '<div class="setting-field"><span class="form-label">Capture level</span>' +
          '<div class="row"><input id="gain" type="number" class="ctl" aria-label="Capture level"></div></div>' +
          '<button id="apply" class="ctl" type="button">Set level</button>' +
          '<div class="row"><button id="calibrate" class="ctl" type="button">Measure level</button></div>' +
          '<div style="height:300px">Synthetic result</div>';
        body.querySelector('#gain').dataset.help = help;
        window.applied = 0;
        body.querySelector('#apply').addEventListener('click', () => window.applied++);
        body.scrollTop = 0;
      }, explanation);
      await page.locator('#gain').fill('40');
      await expect(tip).toHaveAttribute('aria-hidden', 'false');
      assert.equal(await page.locator('#apply').evaluate(button => {
        const box = button.getBoundingClientRect();
        return button.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2));
      }), true, 'Focused field guidance leaves the following action available to the pointer');
      await page.locator('#apply').click();
      assert.equal(await page.evaluate(() => window.applied), 1);
      await dialog.evaluate(el => el.close());
      await page.locator('#outside').focus();
      await expect(tip).toHaveAttribute('aria-hidden', 'false');
      assert.equal(await tip.evaluate(el => el.parentElement.tagName), 'BODY');
      const outside = await tip.boundingBox();
      assert.ok(outside.x >= 0 && outside.x + outside.width <= viewport.width, 'Help returns to viewport positioning');
      await page.close();
    }
    assert.deepEqual(errors, []);
    console.log(`${engine}: actual blurred native dialog help remains readable, unclipped and dismissible at desktop/mobile widths; ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
