// Hardware gain is editable only for an identified mixer, never a guessed card.
const {launchChromium} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const artifacts = fs.mkdtempSync('/tmp/lixity-audio-microphone-');
  const server = await startNativeServer(`
import json, os, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
import lixity.speech_record as record
import lixity.speech_status as speech_status
record.get_microphone_status = lambda: {'devices':[], 'current_gain':None, 'gain_info':None}
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
      page.on('pageerror',error=>errors.push(error.message));
      let known = true;
      const hardware = {devices:[
        {alsa_id:'plughw:CARD=USB,DEV=0',card:1,card_id:'USB',label:'Synthetic USB microphone'},
        {alsa_id:'plughw:CARD=OTHER,DEV=0',card:2,card_id:'OTHER',label:'Synthetic other microphone'}],
      default_device:'plughw:CARD=USB,DEV=0',current_gain:37,
      gain_info:{card:1,control:'Mic',gain:37,min:4,max:80,db:10}};
      await page.route('**/api/speech?*',async route=>{
        const response=await route.fetch(),data=await response.json();
        data.microphone=known ? hardware : {...hardware,current_gain:null,gain_info:null};
        await route.fulfill({response,json:data});
      });
      await page.route('**/api/audio-microphone',route=>{
        const payload=route.request().postDataJSON();actions.push(payload);
        // Real mixer changes and capture are never invoked by this test.
        if(payload.action==='set_gain') return route.fulfill({json:{ok:true,...hardware,current_gain:payload.gain,
          gain_info:{...hardware.gain_info,gain:payload.gain,db:15}}});
        assert.equal(payload.action,'calibrate');
        return route.fulfill({json:{ok:true,calibration:{verdict:'calibrated',verdict_label:'Synthetic calibration',
          peak_dbfs:-10,clipping_samples:0,snr_db:30,recommended_gain:35}}});
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
        assert.equal(await gain.getAttribute('min'),'4','Use the actual mixer range');
        assert.equal(await gain.getAttribute('max'),'80');
        assert.equal(await gain.inputValue(),'37');
        assert.equal(await slider.inputValue(),'37');
        await gain.fill('81');
        await apply.click();
        assert.equal(actions.length,0,'Out-of-range input cannot change hardware');
        await gain.fill('40');
        await apply.click();
        await page.waitForFunction(()=>!document.querySelector('[data-speech-action=microphone_set_gain]').disabled &&
          document.querySelector('#speech-microphone-gain-info').textContent.includes('15.0 dB'));
        assert.deepEqual(actions[0],{action:'set_gain',gain:40,card:1,control:'Mic'},'Apply explicitly targets the identified mixer');
        await device.selectOption(hardware.devices[1].alsa_id);
        assert.equal(await gain.isDisabled(),true,'Another device cannot inherit the default mixer gain');
        assert.equal(await apply.isDisabled(),true);
        assert.equal(await gain.inputValue(),'','Unavailable is not the old gain or a guessed default');
        assert.equal(await slider.isVisible(),false,'An unknown gain has no misleading slider position');
        assert.match(await page.locator('#speech-microphone-section').innerText(),/unavailable|unknown/i);
        await apply.evaluate(button=>button.click());
        assert.equal(actions.length,1);
        await page.locator('[data-speech-action=microphone_calibrate]').click();
        await page.waitForFunction(()=>document.querySelector('.audio-calib-result').textContent.includes('Synthetic calibration'));
        assert.deepEqual(actions[1],{action:'calibrate',device:hardware.devices[1].alsa_id},
          'Measuring another microphone must not change gain on a default card');
        assert.equal(await page.locator('.audio-calib-result button').count(),0,'An unverified mixer cannot receive a gain recommendation');
        await page.locator('#modal-speech [data-speech-action=close]').click();
        known=false;
        await open();
        assert.equal(await gain.inputValue(),'');
        assert.equal(await gain.isDisabled(),true);
        assert.equal(await apply.isDisabled(),true);
        assert.doesNotMatch(await page.locator('#speech-microphone-section').innerText(),/15\.0 dB/,'Reopening clears stale decibel metadata');
        await page.locator('#modal-speech').screenshot({path:path.join(artifacts,`unknown-${width}.png`)});
        await page.locator('#modal-speech [data-speech-action=close]').click();
        known=true; hardware.current_gain=110; hardware.gain_info={...hardware.gain_info,gain:110,max:120};
        await open();
        assert.equal(await gain.inputValue(),'110','Known hardware readings remain truthful outside the supported control range');
        assert.equal(await gain.getAttribute('max'),'120');
        assert.equal(await slider.inputValue(),'110');
        assert.equal(await apply.isDisabled(),true,'The UI does not claim unsupported mixer-write ranges');
        assert.deepEqual(errors,[]);
      } finally {await page.close();}
    }
    console.log(`Microphone hardware association, unknown state, limits and explicit mixer payload passed: ${artifacts}`);
  } finally {await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
