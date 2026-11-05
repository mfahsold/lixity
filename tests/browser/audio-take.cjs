// Portable takes bind exact PCM bytes to an explicitly reviewed transcript.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {launchChromium} = require('../../scripts/browser_tools.cjs');

(async () => {
  const server = http.createServer((_request, response) => response.end('<!doctype html><html lang="en"><title>Portable takes</title><body></body></html>'));
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await launchChromium();
  try {
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    const helper = path.resolve('src/lixity/ui/assets/audio-take.js');
    if (fs.existsSync(helper)) await page.addScriptTag({path:helper});
    assert.equal(await page.evaluate(() => typeof window.LixityAudioTake), 'object', 'The current portable take API is available');
    const result = await page.evaluate(async () => {
      const api = window.LixityAudioTake;
      function wav(seconds=2, rate=24000) {
        const frames = seconds * rate, buffer = new ArrayBuffer(44 + frames * 2), view = new DataView(buffer);
        function string(offset, text) { [...text].forEach((char,index) => view.setUint8(offset+index,char.charCodeAt(0))); }
        string(0,'RIFF');view.setUint32(4,buffer.byteLength-8,true);string(8,'WAVE');string(12,'fmt ');
        view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);
        view.setUint32(24,rate,true);view.setUint32(28,rate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);
        string(36,'data');view.setUint32(40,frames*2,true);return new Blob([buffer],{type:'audio/wav'});
      }
      window.syntheticTakeWav = wav;
      const take = await api.create(wav(), {filename:'synthetic.wav', transcript:'A river flows.', transcript_status:'draft'});
      const confirmed = api.withTranscript(take,'A river flows.','confirmed');
      const sidecar = new File([JSON.stringify(confirmed.metadata)],'synthetic.json',{type:'application/json'});
      const restored = await api.importFiles(new File([take.blob],'synthetic.wav'),sidecar);
      const errors = {};
      const original = new Uint8Array(await take.blob.arrayBuffer());
      const reordered = new Uint8Array(original.length);
      reordered.set(original.slice(0,12)); reordered.set(original.slice(36),12); reordered.set(original.slice(12,36),original.length-24);
      for (const [name, audio, metadata] of [
        ['hash', wav(3), confirmed.metadata],
        ['format', new Blob(['not wav']), confirmed.metadata],
        ['schema', take.blob, {...confirmed.metadata,schema_version:'future/1'}],
        ['duration', take.blob, {...confirmed.metadata,audio:{...confirmed.metadata.audio,duration_seconds:50}}],
        ['confirmed_empty', take.blob, {...confirmed.metadata,transcript:{text:'',status:'confirmed'}}],
        ['data_before_format', new Blob([reordered]), confirmed.metadata],
      ]) {
        try { await api.importFiles(new File([audio],'synthetic.wav'),new File([JSON.stringify(metadata)],'synthetic.json')); errors[name]='accepted'; }
        catch (error) { errors[name]=error.code; }
      }
      const long = await api.create(wav(31),{filename:'long.wav',transcript:'A river flows.',transcript_status:'confirmed'});
      const differentRate = await api.create(wav(2,48000),{filename:'other.wav',transcript:'A river flows.',transcript_status:'confirmed'});
      window.savedTake = confirmed;
      return {metadata:restored.metadata, draft:api.referenceEligibility(take), confirmed:api.referenceEligibility(restored),
        empty:api.referenceEligibility(await api.create(wav(),{filename:'empty.wav'})),
        long:api.referenceEligibility(long),differentRate:api.referenceEligibility(differentRate),errors};
    });
    assert.equal(result.metadata.schema_version,'lixity-audio-take/1');
    assert.match(result.metadata.audio.sha256,/^[0-9a-f]{64}$/);
    assert.equal(result.metadata.audio.frames,48000);
    assert.equal(result.metadata.audio.duration_seconds,2);
    assert.deepEqual(result.metadata.transcript,{text:'A river flows.',status:'confirmed'});
    assert.equal(result.confirmed.eligible,true);
    assert.equal(result.draft.reason,'confirmation');assert.equal(result.empty.reason,'missing');
    assert.equal(result.long.reason,'duration');assert.equal(result.differentRate.reason,'format');
    assert.deepEqual(result.errors,{hash:'hash',format:'format',schema:'schema',duration:'format',confirmed_empty:'transcript',data_before_format:'format'});
    for (const kind of ['wav','json']) {
      const pending=page.waitForEvent('download');
      await page.evaluate(kind => LixityAudioTake.download(savedTake,kind),kind);
      const download=await pending; assert.equal(download.suggestedFilename(),`synthetic.${kind}`);
    }
    console.log('Portable take exact-byte roundtrip, invalid-input preservation contract and explicit downloads passed.');
    await page.close();
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => {console.error(error);process.exitCode=1;});
