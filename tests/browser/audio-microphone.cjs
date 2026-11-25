// Exercise device discovery and use hardware gain only for an identified mixer.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const labels = require('../../src/lixity/locales/en.json');

async function checkDesktopDevices(browser, server, artifacts, width) {
  const page = await browser.newPage({viewport: {width, height: 900}, reducedMotion: 'reduce'});
  page.setDefaultTimeout(10000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let serverCaptures = 0;
  const builtIn = {id: 'internal', label: 'MacBook Pro Microphone', is_default: true};
  const external = {id: 'usb', label: 'Synthetic USB Microphone with a deliberately long product name', is_default: false};
  try {
    await page.addInitScript(device => {
      const fixture = window.desktopMicrophones = {
        devices: [device], measurements: [], recordings: [], fail: false, holdNext: false, signalPresent: true,
      };
      window.lixityDesktop = {platform: 'macos', audioCapture: {
        listDevices: async () => {
          if (fixture.holdNext) {
            fixture.holdNext = false;
            return new Promise(resolve => { fixture.release = resolve; });
          }
          if (fixture.fail) throw new Error('Synthetic native inventory failure');
          return fixture.devices;
        },
        calibrate: async (id, seconds) => {
          fixture.measurements.push({id, seconds});
          if (fixture.checkFails) throw new Error('Synthetic native check failure');
          return {verdict: 'calibrated', verdict_label: 'Synthetic native calibration',
            peak_dbfs: -10, clipping_samples: 0, snr_db: 30, signal_present: fixture.signalPresent};
        },
        startRecording: async (id, _filename, seconds) => {
          fixture.recordings.push({id, seconds});
          return {recording:true,max_duration_seconds:seconds};
        },
        stopRecording: async () => {
          const frames = 31 * 24000;
          const wav = LixityAudioTake.encodeWav([new Float32Array(frames)], frames, 24000);
          const encoded = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result.split(',')[1]);
            reader.onerror = reject;
            reader.readAsDataURL(new Blob([wav], {type:'audio/wav'}));
          });
          return {wav_base64:encoded,filename:'author-voice.wav'};
        },
        cancelRecording: async () => {},
      }};
    }, builtIn);
    await page.route('**/api/speech?*', async route => {
      const response = await route.fetch(), data = await response.json();
      data.microphone = {devices: [{alsa_id: 'hw:server', label: 'Unrelated server microphone'}],
        default_device: 'hw:server', current_gain: null, gain_info: null};
      data.reference_recording = {...data.reference_recording, duration_seconds:40, reference_seconds:40};
      await route.fulfill({response, json: data});
    });
    await page.route('**/api/audio-microphone', route => {
      serverCaptures += 1;
      return route.fulfill({status: 500, json: {ok: false, message: 'Unexpected server capture'}});
    });
    await page.goto(server.fixture.url);
    await page.locator('#tab-view-project').click();
    const modal = page.locator('#modal-speech');
    const section = modal.locator('#speech-microphone-section');
    const device = section.locator('#speech-microphone_device');
    const current = section.locator('#speech-microphone-current');
    const inventory = section.locator('#speech-microphone-inventory-status');
    const refresh = section.locator('[data-speech-action=microphone_refresh]');
    const calibrate = section.locator('[data-speech-action=microphone_calibrate]');
    const checkStatus = section.locator('#speech-microphone-check-status');
    async function open() {
      await page.locator('#settings-speech-mic').click();
      await page.waitForFunction(() => document.querySelector('#speech-name')?.value === 'Narrator');
    }
    async function awaitInventory(pattern) {
      await inventory.filter({hasText: pattern}).waitFor();
      return inventory.innerText();
    }

    await open();
    await current.filter({hasText: builtIn.label}).waitFor();
    assert.equal(await device.isVisible(), false, 'One device has no dropdown');
    assert.equal(await calibrate.isEnabled(), true, 'A single device remains usable');
    assert.equal(await section.locator('[data-speech-action=microphone_set_gain]').isVisible(), false);
    assert.match(await section.innerText(), /System Settings\s*→\s*Sound\s*→\s*Input/i);
    assert.doesNotMatch(await section.innerText(), /Unrelated server microphone/);
    await modal.screenshot({path: path.join(artifacts, `native-single-${width}.png`)});

    await page.evaluate(devices => { desktopMicrophones.devices = devices; }, [builtIn, external]);
    await refresh.click();
    await device.waitFor();
    assert.deepEqual(await device.locator('option').evaluateAll(options => options.map(option => option.value)),
      [builtIn.id, external.id]);
    assert.match(await device.locator('option:checked').innerText(), /MacBook Pro Microphone.*system default/i);
    assert.equal(await current.isVisible(), false, 'Multiple inputs show only the selector');
    assert.equal(await device.evaluate(select => {
      const rect = select.getBoundingClientRect();
      const parent = select.closest('label');
      return rect.left >= 0 && rect.right <= innerWidth && parent.scrollWidth <= parent.clientWidth;
    }), true, `Long microphone labels fit the control at ${width}px`);
    await device.focus();
    await page.keyboard.press('s');
    assert.equal(await device.inputValue(), external.id, 'The microphone can be selected with the keyboard');
    await refresh.click();
    await device.waitFor();
    assert.equal(await device.inputValue(), external.id, 'Refreshing preserves an available explicit choice');
    await modal.screenshot({path: path.join(artifacts, `native-multiple-${width}.png`)});
    await calibrate.click();
    await section.getByText(labels.speech_microphone_check_calibrated, {exact: true}).waitFor();
    await section.getByText(labels.speech_microphone_check_calibrated_help, {exact: true}).waitFor();
    assert.equal(await page.evaluate(() => desktopMicrophones.measurements[0].id), external.id,
      'The selected native input reaches calibration');
    await page.evaluate(() => { desktopMicrophones.signalPresent = false; });
    await calibrate.click();
    await section.getByText(labels.speech_microphone_check_silent, {exact: true}).waitFor();
    await section.getByText(labels.speech_microphone_check_silent_help, {exact: true}).waitFor();
    await page.evaluate(() => { desktopMicrophones.checkFails = true; });
    await calibrate.click();
    await checkStatus.filter({hasText: 'Could not check the input level. Check microphone access and try again.'}).waitFor();
    assert.equal(await calibrate.isEnabled(), true, 'A failed check can be retried');
    await modal.locator('#speech-tab-reference').click();
    const record = modal.locator('.voice-rec-btn');
    await page.clock.install();
    await record.focus();
    await page.keyboard.press('Enter');
    await modal.locator('.voice-rec-btn.is-recording').waitFor();
    assert.equal(await record.evaluate(button => button === document.activeElement), true,
      'Keyboard focus stays on Start/Stop after native recording begins');
    await page.clock.fastForward(31000);
    await modal.locator('.voice-rec-timer').filter({hasText:'00:31 / 00:40'}).waitFor();
    assert.deepEqual(await page.evaluate(() => desktopMicrophones.recordings), [{id: external.id, seconds:40}],
      'The selected native input also reaches the voice recorder');
    await page.keyboard.press('Space');
    await modal.locator('.voice-rec-btn.is-recording').waitFor({state: 'hidden'});
    await modal.locator('.voice-take-stats').filter({hasText:'31.0 s'}).waitFor();
    await modal.locator('#speech-take_confirmed').check();
    assert.equal(await modal.locator('.voice-save-btn').isEnabled(), true, 'A reviewed take longer than thirty seconds can be saved');
    await modal.locator('[data-speech-action=take_discard]').click();
    await modal.locator('[data-speech-action=close]').click();
    await page.locator('#btn-project-record-voice').click();
    await record.click();
    await modal.locator('.voice-rec-btn.is-recording').waitFor();
    assert.deepEqual(await page.evaluate(() => desktopMicrophones.recordings), Array(2).fill({id: external.id, seconds:40}),
      'Opening Author’s Voice directly retains the microphone chosen for this project');
    await record.click();
    await modal.locator('.voice-rec-btn.is-recording').waitFor({state: 'hidden'});
    await modal.locator('[data-speech-action=take_discard]').click();
    await page.evaluate(builtIn => { desktopMicrophones.devices = [builtIn]; }, builtIn);
    await modal.locator('#speech-tab-microphone').click();
    await current.filter({hasText: builtIn.label}).waitFor();
    assert.equal(await device.isVisible(), false, 'Returning to the microphone tab discovers a removed input');

    await page.evaluate(() => { desktopMicrophones.holdNext = true; });
    await refresh.click();
    await page.waitForFunction(() => typeof desktopMicrophones.release === 'function');
    assert.equal(await refresh.isDisabled(), true);
    assert.match(await inventory.innerText(), /looking for microphones/i);
    await modal.locator('[data-speech-action=close]').click();
    await open();
    await current.filter({hasText: builtIn.label}).waitFor();
    await page.evaluate(async external => {
      desktopMicrophones.release([external]);
      await new Promise(requestAnimationFrame);
    }, external);
    assert.match(await current.innerText(), /MacBook Pro Microphone/, 'A closed dialog cannot overwrite a new discovery');

    await page.evaluate(() => { desktopMicrophones.devices = []; });
    await refresh.click();
    const empty = await awaitInventory(/no.*(?:microphone|input|device)/i);
    assert.match(empty, /connect|system|refresh/i);
    assert.equal(await device.isVisible(), false);
    assert.equal(await calibrate.isDisabled(), true);
    assert.equal(await refresh.isEnabled(), true);
    await page.evaluate(() => { desktopMicrophones.fail = true; });
    await refresh.click();
    const failed = await awaitInventory(/could not|couldn.t|failed|unavailable/i);
    assert.match(failed, /try|system|refresh/i);
    assert.notEqual(failed, empty, 'A native error is distinct from an empty inventory');
    assert.equal(await refresh.isEnabled(), true);
    assert.equal(serverCaptures, 0, 'Native capture must not call the unrelated server mixer');
    assert.deepEqual(errors, []);
  } finally { await page.close(); }
}

(async () => {
  const artifacts = fs.mkdtempSync('/tmp/lixity-audio-microphone-');
  const server = await startNativeServer(`
import json, os, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
import lixity.speech_record as record
import lixity.speech_status as speech_status
record.get_microphone_status = lambda **kwargs: {'devices':[], 'current_gain':None, 'gain_info':None}
speech_status.worker_health = lambda target, **kwargs: {'target':target, 'state':'unavailable', 'model':None}
root = Path(sys.argv[1]); source = root / 'manuscript.md'
os.environ['XDG_DATA_HOME'] = str(root / 'app-data')
source.write_text('## One\\n\\nA synthetic passage.\\n')
(root / 'lixity.toml').write_text('language="en"\\n[audio]\\nselected="narrator"\\n[audio.profiles.narrator]\\nname="Narrator"\\nengine="qwen3"\\n')
LixityServerHandler.workspace_root = str(root)
LixityServerHandler.source_input = str(source)
LixityServerHandler.exports_dir = str(root / 'exports')
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1',0), LixityServerHandler)
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}'}), flush=True)
server.serve_forever()
`, artifacts);
  const browser = await launchChromium();
  try {
    for (const width of [1440,320]) {
      const page = await browser.newPage({viewport:{width,height:900}}), errors=[], actions=[];
      page.setDefaultTimeout(10000);
      page.on('pageerror',error=>errors.push(error.message));
      let known = true, statusReads = 0, writeOutcome = 'held', finishWrite, announceHeldWrite;
      const heldWrite = new Promise(resolve => { announceHeldWrite = resolve; });
      const hardware = {devices:[
        {alsa_id:'plughw:CARD=USB,DEV=0',card:1,card_id:'USB',label:'Synthetic USB microphone'},
        {alsa_id:'plughw:CARD=OTHER,DEV=0',card:2,card_id:'OTHER',label:'Synthetic other microphone'}],
      default_device:'plughw:CARD=USB,DEV=0',current_gain:37,
      gain_info:{card:'USB',control:'Mic',gain:37,min:4,max:80,db:10,writable:true}};
      const inventory = (device = hardware.default_device) => known && device === hardware.default_device
        ? hardware : {...hardware,current_gain:null,gain_info:null};
      await page.route('**/api/speech?*',async route=>{
        const response=await route.fetch(),data=await response.json();
        data.microphone=inventory();
        await route.fulfill({response,json:data});
      });
      await page.route('**/api/audio-microphone',async route=>{
        const payload=route.request().postDataJSON();
        if (payload.action === 'status') {
          statusReads += 1;
          return route.fulfill({json:{ok:true,...inventory(payload.device)}});
        }
        actions.push(payload);
        // Real mixer changes and capture are never invoked by this test.
        if (payload.action === 'set_gain') {
          if (writeOutcome === 'held') await new Promise(resolve => { finishWrite = resolve; announceHeldWrite(); });
          if (writeOutcome === 'rejected') return route.fulfill({status: 400, json: {ok: false}});
          if (writeOutcome === 'unknown') {
            return route.fulfill({json: {...hardware, ok: true, current_gain: null, gain_info: null}});
          }
          const actual = writeOutcome === 'limited' ? 38 : payload.gain;
          return route.fulfill({json:{ok:true,...hardware,current_gain:actual,
            gain_info:{...hardware.gain_info,gain:actual,db:15}}});
        }
        assert.equal(payload.action,'calibrate');
        return route.fulfill({json:{ok:true,calibration:{verdict:'calibrated',verdict_label:'Synthetic calibration',
          peak_dbfs:-10,clipping_samples:0,snr_db:30,signal_present:true,recommended_gain:35}}});
      });
      try {
        await page.goto(server.fixture.url);
        await page.locator('#tab-view-project').click();
        async function open() {
          await page.locator('#settings-speech-mic').click();
          await page.waitForFunction(()=>document.querySelector('#speech-name')?.value==='Narrator');
        }
        await open();
        const device=page.locator('#speech-microphone-section select');
        const gain=page.locator('#speech-microphone-section input[type=number]');
        const slider=page.locator('#speech-microphone-section input[type=range]');
        const apply=page.locator('[data-speech-action=microphone_set_gain]');
        const refresh=page.locator('[data-speech-action=microphone_refresh]');
        const gainStatus=page.getByRole('status').and(page.locator('#speech-microphone-gain-status'));
        async function selectInput(value) {
          const verification=page.waitForRequest(request=>request.url().endsWith('/api/audio-microphone') &&
            request.postDataJSON().action==='status');
          await device.selectOption(value);
          assert.deepEqual((await verification).postDataJSON(), {action:'status',device:value},
            'Changing capture input requests a fresh reading for that device');
          await page.waitForFunction(()=>!document.querySelector('[data-speech-action=microphone_refresh]').disabled);
        }
        assert.equal(await gain.getAttribute('min'),'4','Use the actual mixer range');
        assert.equal(await gain.getAttribute('max'),'80');
        assert.equal(await gain.inputValue(),'37');
        assert.equal(await slider.inputValue(),'37');
        await apply.click();
        await gainStatus.filter({hasText: 'Input gain is already 37.'}).waitFor();
        assert.equal(actions.length, 0, 'An unchanged input gain is acknowledged without writing again');
        await gain.fill('81');
        await apply.click();
        await gainStatus.filter({hasText: 'Enter a whole number from 4 to 80.'}).waitFor();
        assert.equal(actions.length,0,'Out-of-range input cannot change hardware');
        await gain.fill('40');
        const writeRequest = page.waitForRequest(request => request.url().endsWith('/api/audio-microphone') &&
          request.postDataJSON().action === 'set_gain');
        await apply.click();
        await writeRequest;
        await heldWrite;
        await gainStatus.filter({hasText: 'Applying input gain…'}).waitFor();
        assert.equal(await apply.isDisabled(), true, 'Pending feedback appears before the mixer reply');
        finishWrite();
        await gainStatus.filter({hasText: /Hardware (?:gain|level) set to 40\./}).waitFor();
        assert.match(await page.locator('#speech-microphone-gain-info').innerText(), /15\.0 dB/);
        assert.deepEqual(actions[0],{action:'set_gain',gain:40,card:'USB',control:'Mic'},'Apply targets the identified ALSA mixer');
        writeOutcome = 'limited';
        await gain.fill('45');
        await apply.click();
        await gainStatus.filter({hasText: 'Requested 45. The device reports 38.'}).waitFor();
        assert.equal(await gain.inputValue(), '38', 'Use the device read-back when it differs from the request');
        writeOutcome = 'rejected';
        await gain.fill('44');
        await apply.click();
        await gainStatus.filter({hasText: 'Could not change input gain. Check the device and try again.'}).waitFor();
        assert.equal(await apply.isEnabled(), true);
        writeOutcome = 'unknown';
        await gain.fill('46');
        await apply.click();
        await gainStatus.filter({hasText: 'Could not confirm the input gain. Refresh devices before trying again.'}).waitFor();
        assert.equal(await gain.inputValue(), '', 'Unverified write acknowledgment cannot establish the input gain');
        await refresh.click();
        await gain.waitFor({state: 'visible'});
        await selectInput(hardware.devices[1].alsa_id);
        assert.equal(await gain.isDisabled(),true,'Another device cannot inherit the default mixer gain');
        assert.equal(await apply.isDisabled(),true);
        assert.equal(await gain.inputValue(),'','Unavailable is not the old gain or a guessed default');
        assert.equal(await slider.isVisible(),false,'An unknown gain has no misleading slider position');
        assert.match(await page.locator('#speech-microphone-section').innerText(),/unavailable|unknown/i);
        await apply.evaluate(button=>button.click());
        assert.equal(actions.length,4);
        await page.locator('[data-speech-action=microphone_calibrate]').click();
        await page.locator('.audio-calib-result').getByText(labels.speech_microphone_check_calibrated, {exact: true}).waitFor();
        assert.deepEqual(actions.at(-1),{action:'calibrate',device:hardware.devices[1].alsa_id},
          'Measuring another microphone must not change gain on a default card');
        assert.equal(await page.locator('.audio-calib-result button').count(),0,'An unverified mixer cannot receive a gain recommendation');
        await selectInput(hardware.default_device);
        assert.equal(await gain.isEnabled(), true);
        const readsBeforeRefresh = statusReads;
        known=false;
        await refresh.click();
        await page.waitForFunction(() => document.querySelector('#speech-microphone-section input[type=number]').value === '');
        assert.equal(statusReads, readsBeforeRefresh + 1, 'The browser refresh reads the server capture inventory');
        assert.equal(await device.inputValue(), hardware.default_device);
        await page.locator('#modal-speech [data-speech-action=close]').click();
        await open();
        assert.equal(await gain.inputValue(),'');
        assert.equal(await gain.isDisabled(),true);
        assert.equal(await apply.isDisabled(),true);
        assert.doesNotMatch(await page.locator('#speech-microphone-section').innerText(),/15\.0 dB/,'Reopening clears stale decibel metadata');
        await page.locator('#modal-speech').screenshot({path:path.join(artifacts,`unknown-${width}.png`)});
        await page.locator('#modal-speech [data-speech-action=close]').click();
        known=true; hardware.gain_info={...hardware.gain_info,writable:false};
        await open();
        assert.equal(await gain.inputValue(),'37','A read-only device still reports its measured gain');
        assert.equal(await apply.isVisible(),false,'Only the server may mark a mixer writable');
        await page.locator('#modal-speech [data-speech-action=close]').click();
        hardware.current_gain=110; hardware.gain_info={...hardware.gain_info,gain:110,max:120};
        await open();
        assert.equal(await gain.inputValue(),'110','Known hardware readings remain truthful outside the supported control range');
        assert.equal(await gain.getAttribute('max'),'120');
        assert.equal(await slider.inputValue(),'110');
        assert.equal(await apply.isDisabled(),true,'The UI does not claim unsupported mixer-write ranges');
        assert.deepEqual(errors,[]);
      } finally {finishWrite?.(); await page.close();}
      await checkDesktopDevices(browser, server, artifacts, width);
    }
    console.log(`Microphone discovery, native selection, availability, mixer association and limits passed: ${artifacts}`);
  } finally {await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
