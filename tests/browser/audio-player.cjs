// Synthetic audio exercises the shared player without microphone access or a project.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

(async () => {
  const assets = path.resolve(__dirname, '../../src/lixity/ui/assets');
  assert.ok(fs.existsSync(path.join(assets, 'speech-player.js')), 'Shared speech player exists');
  const browser = await launchChromium();
  const output = fs.mkdtempSync('/tmp/lixity-audio-player-');
  try {
    for (const width of [1440, 320]) {
      const page = await browser.newPage({viewport: {width, height: 800}});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.setContent('<html lang="en"><title>Audio player check</title><body><main style="max-width:600px"><audio hidden></audio></main></body></html>');
      for (const name of ['design-tokens.css', 'components.css', 'speech-player.css']) {
        await page.addStyleTag({path: path.join(assets, name)});
      }
      await page.addScriptTag({path: path.join(assets, 'speech-player.js')});
      await page.evaluate(() => {
        window.playerErrors = [];
        window.audio = document.querySelector('audio');
        window.player = createSpeechPlayer(audio, {label: key => key, onError: message => playerErrors.push(message)});
        const samples = 44100 * 4, data = new ArrayBuffer(44 + samples * 2), view = new DataView(data);
        function string(offset, value) { for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i)); }
        string(0, 'RIFF'); view.setUint32(4, 36 + samples * 2, true); string(8, 'WAVE'); string(12, 'fmt ');
        view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
        view.setUint32(24, 44100, true); view.setUint32(28, 88200, true); view.setUint16(32, 2, true);
        view.setUint16(34, 16, true); string(36, 'data'); view.setUint32(40, samples * 2, true);
        for (let i = 0; i < samples; i++) view.setInt16(44 + i * 2, 8000 * Math.sin(i * 2 * Math.PI * 440 / 44100), true);
        window.sourceUrl = URL.createObjectURL(new Blob([data], {type: 'audio/wav'}));
      });
      assert.equal(await page.locator('.speech-player').isVisible(), false);
      await page.evaluate(() => { audio.src = sourceUrl; audio.hidden = false; });
      await page.waitForFunction(() => document.querySelector('.speech-player-time').textContent.endsWith('0:04'));
      assert.equal(await page.locator('.speech-player').isVisible(), true);
      await page.getByRole('button', {name: 'player_play', exact: true}).click();
      await page.waitForFunction(() => !audio.paused && audio.currentTime > 0.1);
      await page.waitForFunction(() => document.querySelector('.speech-player').dataset.spectrum === 'playback');
      assert.equal(await page.getByRole('button', {name: 'player_pause', exact: true}).count(), 1);
      await page.getByRole('button', {name: 'player_pause', exact: true}).click();
      assert.equal(await page.evaluate(() => audio.paused), true);
      await page.getByRole('slider', {name: 'player_seek', exact: true}).fill('2');
      assert.ok(Math.abs(await page.evaluate(() => audio.currentTime) - 2) < 0.1);
      await page.getByRole('slider', {name: 'player_volume', exact: true}).fill('0.3');
      assert.equal(await page.evaluate(() => audio.volume), 0.3);
      await page.getByRole('button', {name: 'player_mute', exact: true}).click();
      assert.equal(await page.evaluate(() => audio.muted), true);
      await page.getByRole('button', {name: 'player_unmute', exact: true}).click();
      assert.equal(await page.evaluate(() => audio.muted), false);
      await page.evaluate(async () => {
        window.liveContext = new AudioContext();
        window.liveSource = liveContext.createOscillator();
        window.liveAnalyser = liveContext.createAnalyser();
        liveAnalyser.fftSize = 256;
        liveSource.connect(liveAnalyser); liveSource.start();
        await liveContext.resume();
        player.setLiveAnalyser(liveAnalyser);
      });
      assert.equal(await page.getByRole('button', {name: 'player_play', exact: true}).isEnabled(), false);
      await page.waitForFunction(() => document.querySelector('.speech-player').dataset.spectrum === 'live');
      const initial = await page.locator('canvas').evaluate(canvas => canvas.toDataURL());
      await page.evaluate(() => { liveSource.frequency.value = 3000; });
      await page.waitForFunction(previous => document.querySelector('canvas').toDataURL() !== previous, initial);
      await page.screenshot({path: path.join(output, `live-${width}.png`)});
      await page.evaluate(async () => { player.clearLiveAnalyser(); liveSource.stop(); await liveContext.close(); });
      assert.equal(await page.getByRole('button', {name: 'player_play', exact: true}).isEnabled(), true);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.screenshot({path: path.join(output, `player-${width}.png`)});
      let axe;
      for (const candidate of ['axe-core/axe.min.js', path.join(os.homedir(), 'rosts_services/node_modules/axe-core/axe.min.js')]) {
        try { axe = require.resolve(candidate); break; } catch {}
      }
      if (axe) {
        await page.addScriptTag({path: axe});
        const violations = await page.evaluate(async () => (await window.axe.run('.speech-player')).violations);
        assert.deepEqual(violations, [], 'No automated accessibility violations on the player');
      } else { console.log('axe-core unavailable; player accessibility audit not run'); }
      await page.evaluate(() => { audio.hidden = true; });
      await page.waitForFunction(() => document.querySelector('.speech-player').hidden);
      await page.evaluate(() => { player.destroy(); });
      assert.equal(await page.locator('.speech-player').count(), 0);
      assert.deepEqual(await page.evaluate(() => ({connected:audio.isConnected, source:audio.getAttribute('src'), paused:audio.paused})),
        {connected:false, source:null, paused:true}, 'Disposal releases the media element together with its Web Audio routing');
      assert.deepEqual(await page.evaluate(() => playerErrors), []);
      // Lack of Web Audio must preserve ordinary audio playback with an explicit limit.
      await page.evaluate(() => {
        window.AudioContext = undefined; window.webkitAudioContext = undefined;
        window.audio = document.createElement('audio'); document.querySelector('main').appendChild(audio);
        window.player = createSpeechPlayer(audio, {label: key => key, onError: message => playerErrors.push(message)});
        audio.src = sourceUrl;
      });
      await page.getByRole('button', {name: 'player_play', exact: true}).click();
      await page.waitForFunction(() => !audio.paused && document.querySelector('.speech-player-spectrum-state').textContent === 'player_spectrum_unavailable');
      await page.evaluate(() => { player.destroy(); URL.revokeObjectURL(sourceUrl); });
      assert.deepEqual(await page.evaluate(() => playerErrors), []);
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log(`Audio player desktop/mobile checks passed; screenshots: ${output}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
