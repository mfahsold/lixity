// Recorder errors identify their failing stage without retaining private input.
const {launchChromium,launchFirefox} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async()=>{
  const artifacts=fs.mkdtempSync('/tmp/lixity-audio-diagnostics-');
  const server=await startNativeServer(`
import json, os, sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
import lixity.speech_record as record
import lixity.speech_status as speech_status
record.get_microphone_status=lambda: {'devices':[], 'current_gain':None, 'gain_info':None}
speech_status.worker_health=lambda target, **kwargs: {'target':target, 'state':'unavailable', 'model':None}
root=Path(sys.argv[1]);source=root/'manuscript.md'
os.environ['XDG_DATA_HOME']=str(root/'app-data')
source.write_text('## One\\n\\nA synthetic passage.\\n')
(root/'lixity.toml').write_text('language="en"\\n[audio]\\nselected="narrator"\\n[audio.profiles.narrator]\\nname="Narrator"\\nengine="qwen3"\\n')
LixityServerHandler.workspace_root=str(root)
LixityServerHandler.source_input=str(source)
LixityServerHandler.exports_dir=str(root/'exports')
LixityServerHandler.refresh()
server=ThreadingHTTPServer(('127.0.0.1',0),LixityServerHandler)
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}'}),flush=True)
server.serve_forever()
`,artifacts);
  const browser=await (process.argv.includes('--firefox') ? launchFirefox() : launchChromium());
  try {
    for(const viewport of [{width:1440,height:900},{width:320,height:900},{width:1830,height:705}]) {
      const page=await browser.newPage({viewport}),consoleErrors=[],pageErrors=[];
      page.on('console',message=>{if(message.type()==='error'&&message.text().includes('[Lixity:error]'))consoleErrors.push(message.text());});
      page.on('pageerror',error=>pageErrors.push(error.message));
      try {
        await page.addInitScript(()=>localStorage.setItem('lixity_debug','0'));
        await page.goto(server.fixture.url);
        await page.locator('#tab-view-project').click();
        await page.locator('#btn-project-record-voice').click();
        await page.waitForFunction(()=>!document.querySelector('.voice-rec-btn')?.disabled);
        await page.evaluate(()=>{
          window.diagnostics=[];window.captureCalls=0;
          window.originalMediaDevices=navigator.mediaDevices;
          window.originalResume=AudioContext.prototype.resume;
          const error=LixityLog.error;
          LixityLog.error=function(...args){diagnostics.push(args);return error.apply(this,args);};
          navigator.mediaDevices.getUserMedia=async()=>{
            ++captureCalls;
            throw new DOMException('PRIVATE_ERROR_DEVICE_37 /private/project.wav','NotAllowedError');
          };
        });
        assert.equal(await page.evaluate(()=>LixityLog.isDebug()),false);
        const button=page.locator('.voice-rec-btn'),state=page.locator('.voice-record-state'),detail=page.locator('.voice-record-error');
        const status=page.locator('#speech-status');
        async function visibleFeedback() {
          await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
          const bounds=await page.evaluate(()=>{
            const panel=document.querySelector('#modal-speech .modal-body').getBoundingClientRect();
            const button=document.querySelector('.voice-rec-btn').getBoundingClientRect();
            const state=document.querySelector('.voice-record-state').getBoundingClientRect();
            const detail=document.querySelector('.voice-record-error');
            const error=detail.hidden ? null : detail.getBoundingClientRect();
            return {panel:{top:panel.top,bottom:panel.bottom,height:panel.height},
              top:Math.min(button.top,state.top),bottom:Math.max(button.bottom,state.bottom),
              error:error&&{top:error.top,bottom:error.bottom},scrollY,departure:window.recordingScrollY};
          });
          assert.ok(bounds.top>=bounds.panel.top-1&&bounds.bottom<=bounds.panel.bottom+1,
            `Recording button and inline feedback stay in the dialog viewport at ${viewport.width}×${viewport.height}: ${JSON.stringify(bounds)}`);
          if(bounds.error && bounds.error.bottom-bounds.top<=bounds.panel.height-16) {
            assert.ok(bounds.error.bottom<=bounds.panel.bottom+1,'Error details remain fully visible when they fit beside the controls');
          }
          assert.equal(bounds.scrollY,bounds.departure,'Showing recording feedback never scrolls the underlying document');
        }
        await button.evaluate(node=>node.addEventListener('pointerdown',()=>{window.recordingScrollY=scrollY;},{once:true}));
        await button.click();
        await page.waitForFunction(()=>document.querySelector('#modal-speech [role=status]').textContent===uiLabel('speech_mic_permission'));
        const first=await page.evaluate(()=>diagnostics);
        assert.equal(first.length,1,'A handled permission failure is logged even when debug is off');
        assert.equal(first[0][1].stage,'microphone_request');
        assert.equal(first[0][1].error_name,'NotAllowedError');
        assert.equal(first[0][1].secure_context,true);
        assert.equal(first[0][1].get_user_media_available,true);
        const policy=await page.evaluate(()=>{
          try{return (document.permissionsPolicy||document.featurePolicy)?.allowsFeature('microphone')??null;}
          catch{return null;}
        });
        assert.equal(first[0][1].microphone_policy,policy);
        assert.equal(await state.getAttribute('data-state'),'failed');
        assert.equal(await state.getAttribute('role'),'status');
        assert.equal(await state.getAttribute('aria-live'),'polite');
        assert.equal(await detail.textContent(),await status.textContent());
        assert.equal(await status.isVisible(),false,'Recorder errors appear once, beside the recording controls');
        assert.ok((await button.getAttribute('aria-describedby')).split(' ').includes(await detail.getAttribute('id')));
        assert.equal(await button.isEnabled(),true);
        await visibleFeedback();

        await page.evaluate(()=>{
          navigator.mediaDevices.getUserMedia=()=>{++captureCalls;return new Promise((_resolve,reject)=>{window.rejectCapture=reject;});};
        });
        await button.click();
        await page.waitForFunction(()=>typeof rejectCapture==='function');
        assert.equal(await state.getAttribute('data-state'),'busy','Retry has its own immediate visible state');
        assert.equal(await detail.isVisible(),false,'A retry clears the preceding error details');
        assert.equal(await button.isDisabled(),true);
        await visibleFeedback();
        await page.evaluate(()=>rejectCapture(new DOMException('PRIVATE_ERROR_TRANSCRIPT_21','PRIVATE_ERROR_DEVICE_NAME_99')));
        await page.waitForFunction(()=>document.querySelector('.voice-record-state').dataset.state==='failed');
        assert.equal(await page.evaluate(()=>diagnostics.length),2);
        assert.equal(await page.evaluate(()=>diagnostics.at(-1)[1].error_name),'UnknownError',
          'Unexpected exception names cannot copy private data into diagnostics');

        await page.evaluate(()=>{
          AudioContext.prototype.resume=async()=>{throw new DOMException('PRIVATE_ERROR_CONTEXT_22','NotAllowedError');};
        });
        await button.click();
        await page.waitForFunction(()=>document.querySelector('#modal-speech [role=status]').textContent===uiLabel('speech_mic_failed'));
        const contextFailure=await page.evaluate(()=>diagnostics.at(-1));
        assert.equal(contextFailure[1].stage,'audio_context_resume');
        assert.equal(contextFailure[1].error_name,'NotAllowedError');
        assert.equal(await page.evaluate(()=>captureCalls),2,'Audio initialization failure never asks for microphone permission');
        assert.equal(await detail.textContent(),await status.textContent());

        await page.evaluate(()=>{
          AudioContext.prototype.resume=originalResume;
          Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:undefined});
          Object.defineProperty(document,'featurePolicy',{configurable:true,value:undefined});
          Object.defineProperty(document,'permissionsPolicy',{configurable:true,value:undefined});
        });
        await button.click();
        await page.waitForFunction(()=>document.querySelector('#modal-speech [role=status]').textContent===uiLabel('speech_mic_unavailable'));
        const unavailable=await page.evaluate(()=>diagnostics.at(-1));
        assert.equal(unavailable[1].stage,'preflight');
        assert.equal(unavailable[1].media_devices_available,false);
        assert.equal(unavailable[1].get_user_media_available,false);
        assert.equal(unavailable[1].microphone_policy,null,'Unsupported policy inspection is unknown, not a denial');
        const logs=await page.evaluate(()=>diagnostics);
        assert.equal(logs.length,4);
        assert.equal(consoleErrors.length,4,'Every active failure reaches the always-on error logger');
        const allowed=['stage','error_name','secure_context','media_devices_available','get_user_media_available',
          'audio_context_available','audio_context_state','microphone_policy','top_level'];
        for(const [,diagnostic] of logs)assert.deepEqual(Object.keys(diagnostic).sort(),allowed.slice().sort());
        assert.doesNotMatch(JSON.stringify(logs),/PRIVATE_|project\.wav|manuscript|transcript|deviceId|groupId|source_sha256|project_token|http:/i);

        await page.evaluate(()=>{
          Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:originalMediaDevices});
          navigator.mediaDevices.getUserMedia=()=>new Promise(resolve=>{window.resolveCapture=resolve;});
        });
        await button.click();
        await page.waitForFunction(()=>typeof resolveCapture==='function');
        await page.locator('#modal-speech [data-speech-action=close]').click();
        await page.evaluate(async()=>{
          const context=new AudioContext(),stream=context.createMediaStreamDestination().stream;
          window.lateTracks=stream.getTracks();resolveCapture(stream);
          await context.close();
        });
        await page.waitForFunction(()=>lateTracks.every(track=>track.readyState==='ended'));
        assert.equal(await page.evaluate(()=>diagnostics.length),4,'Closing a pending permission request is not reported as an error');
        await page.locator('#btn-project-record-voice').click();
        await page.waitForFunction(()=>!document.querySelector('.voice-rec-btn')?.disabled);
        assert.equal(await state.getAttribute('data-state'),'idle');
        assert.equal(await detail.isVisible(),false);
        assert.equal(await button.getAttribute('aria-describedby'),null);
        assert.deepEqual(pageErrors,[]);
      } finally {await page.close();}
    }
    console.log(`Recorder stage diagnostics, privacy, retry feedback and cancellation passed: ${artifacts}`);
  } finally {await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
