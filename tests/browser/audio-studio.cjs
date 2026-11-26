// Synthetic native workspace: focused audio tabs, permission feedback and recording cleanup.
const {launchChromium, launchFirefox, resolveAxe} = require('../../scripts/browser_tools.cjs');
const {startNativeServer} = require('./support/native-server.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const labels = require('../../src/lixity/locales/de.json');

(async () => {
  const artifacts = fs.mkdtempSync('/tmp/lixity-audio-studio-');
  const server = await startNativeServer(`
import json, os, sys, time
from pathlib import Path
from http.server import ThreadingHTTPServer
from lixity.server import LixityServerHandler
import lixity.speech_status as speech_status
speech_status.worker_health = lambda target, **kwargs: {'target':target, 'state':'unavailable', 'model':None}
root = Path(sys.argv[1]); source = root / 'manuscript.md'
os.environ['XDG_DATA_HOME'] = str(root / 'app-data')
source.write_text('## One\\n\\nA synthetic passage.\\n')
from lixity.speech import generate_silence_wav
from lixity.speech_profiles import audio_capabilities
from lixity.speech_references import save_reference
reference = save_reference(root, generate_silence_wav(1), 'Initial synthetic reference.')
(root / 'lixity.toml').write_text(f'''language = "de"
[audio]
selected = "narrator"
[audio.profiles.narrator]
name = "Narrator"
engine = "qwen3-base"
voice = "reference"
reference_id = "{reference.id}"
''')
original_save = LixityServerHandler._save_recorded_reference
def held_save(self, payload):
    # Hold the real native request, leaving Firefox's response transport intact.
    (root / 'save-pending').touch()
    deadline = time.monotonic() + 20
    while not (root / 'release-save').exists():
        if time.monotonic() >= deadline:
            self._json({'ok':False, 'message':'Synthetic save gate timed out'}, 504)
            return
        time.sleep(0.01)
    original_save(self, payload)
LixityServerHandler._save_recorded_reference = held_save
LixityServerHandler.workspace_root = str(root)
LixityServerHandler.source_input = str(source)
LixityServerHandler.exports_dir = str(root / 'exports')
LixityServerHandler.language = 'de'
LixityServerHandler.refresh()
server = ThreadingHTTPServer(('127.0.0.1',0), LixityServerHandler)
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}', 'source':str(source), 'reference':reference.id,
                  'capabilities':audio_capabilities()}), flush=True)
server.serve_forever()
`, artifacts);
  const useFirefox = process.argv.includes('--firefox');
  const browser = useFirefox
    ? await launchFirefox({firefoxUserPrefs: {'media.autoplay.default': 0}})
    : await launchChromium();
  const original = fs.readFileSync(server.fixture.source);
  const axe = resolveAxe();
  if (!axe) console.log('axe-core unavailable; full audio dialog accessibility audit not run');
  try {
    for (const width of [2560, 1440, 900, 320]) {
      const page = await browser.newPage({viewport: {width, height: 900}});
      page.setDefaultTimeout(15000);
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      try {
        const customDefault = width === 320 && !useFirefox;
        const capabilities = server.fixture.capabilities;
        const profile = capabilities['qwen3-base'];
        const modelDefault = customDefault ? 1.27 : capabilities['mlx-audio'].speed.default;
        const pauseBounds = profile.control_support.pause_seconds;
        const pauseMaximum = customDefault ? 8.75 : pauseBounds.maximum;
        if (customDefault) await page.route('**/api/speech?*', async route => {
          const response = await route.fetch();
          const data = await response.json();
          data.capabilities['mlx-audio'].speed.default = modelDefault;
          for (const cap of Object.values(data.capabilities)) cap.control_support.pause_seconds.maximum = pauseMaximum;
          await route.fulfill({response, json: data});
        }, {times:1});
        await page.goto(server.fixture.url);
        // Match the existing native-dialog audit harness; keep the application's CSP intact.
        if (axe) await page.evaluate(fs.readFileSync(axe, 'utf8'));
        async function auditDialog(surface) {
          if (!axe) return;
          // Opening motion temporarily composites text below its settled contrast.
          await page.waitForFunction(() => {
            const dialog = document.querySelector('#modal-speech');
            return dialog?.open && getComputedStyle(dialog).opacity === '1';
          });
          const audit = await page.evaluate(async () => {
            const result = await window.axe.run('#modal-speech');
            return {violations: result.violations.map(item => ({id: item.id, nodes: item.nodes.map(node => node.target)})),
              incomplete: result.incomplete.map(item => item.id)};
          });
          fs.writeFileSync(path.join(artifacts, `axe-${surface.replaceAll(' ', '-')}-${width}.json`), JSON.stringify(audit));
          assert.deepEqual(audit.violations, [],
            `No automated accessibility violations in ${surface} at ${width}px`);
        }
        assert.ok(await page.title());
        await page.locator('#tab-view-project').click();
        await page.locator('#btn-project-record-voice').click();
        await page.waitForFunction(() => document.querySelector('#speech-name')?.value === 'Narrator');
        assert.equal(await page.locator('.author-voice-studio').isVisible(), true);
        assert.equal(await page.locator('.speech-export-section').isVisible(), false,
          'Recording must not show the direction export section');
        assert.equal(await page.locator('.speech-render-section').isVisible(), false,
          'Recording must not show synthesis or provider controls');
        assert.equal(await page.locator('#speech-microphone-section').isVisible(), false,
          'Hardware settings belong only to the microphone tab');
        const tabs = page.locator('#modal-speech [role=tab]:visible');
        assert.equal(await tabs.count(), 3);
        assert.equal(await page.locator('#speech-tab-reader').isVisible(), true);
        assert.equal(await page.locator('#speech-tab-reader').getAttribute('role'), null,
          'The manuscript shortcut leaves the project settings tablist');
        assert.equal(await tabs.nth(0).getAttribute('aria-selected'), 'true');
        assert.equal(await tabs.nth(0).getAttribute('tabindex'), '0');
        await tabs.nth(0).focus();
        await page.keyboard.press('ArrowRight');
        assert.equal(await tabs.nth(1).getAttribute('aria-selected'), 'true');
        assert.equal(await tabs.nth(1).evaluate(element => element === document.activeElement), true);
        assert.equal(await page.locator('#speech-engine').isVisible(), true);
        assert.equal(await page.locator('#speech-profile').isVisible(), false,
          'A project with one profile shows its name without a picker');
        assert.equal(await page.locator('.speech-profile-picker .speech-choice-readout strong').textContent(), 'Narrator');
        const removeProfile = page.locator('[data-speech-action=remove_profile]');
        assert.equal(await removeProfile.isVisible(), true);
        await removeProfile.click();
        assert.equal(await page.locator('#speech-status').textContent(), labels.speech_profile_remove_last_schema,
          'Older audio settings explain the review needed before removing the last profile');
        assert.equal(await page.locator('#speech-engine option[value=qwen3-base]').evaluate(option => option.parentElement.label),
          labels.speech_engine_group_reference);
        assert.equal(await page.locator('#speech-recording_duration').isVisible(), false,
          'Project recording preferences stay with Author’s Voice');
        assert.equal(await page.locator('#speech-worker-status').isVisible(), false,
          'Service diagnostics start collapsed');
        assert.equal(await page.locator('.speech-profile-footer [data-speech-action=save]').isVisible(), true);
        assert.equal(await page.locator('.author-voice-studio').isVisible(), false);
        assert.equal(await page.locator('.speech-export-section').isVisible(), false);
        assert.equal(await page.locator('#speech-microphone-section').isVisible(), false);
        assert.ok((await page.locator('#speech-engine').getAttribute('data-help'))?.length > 20,
          'Model selection explains its effect in contextual help');
        const speed = page.locator('#speech-speed');
        const speedHint = page.locator('#speech-speed-hint');
        async function assertTempo(labelKey, helpKey, defaultValue) {
          const help = labels[helpKey].replace('{default}', new Intl.NumberFormat('de').format(defaultValue));
          assert.equal(await page.getByRole('spinbutton', {name:labels[labelKey], exact:true}).isVisible(), true);
          assert.equal(await speedHint.textContent(), help);
          assert.equal(await speed.getAttribute('data-help'), help);
          assert.equal(await speed.getAttribute('aria-describedby'), 'speech-speed-hint');
          assert.ok(await speed.evaluate(input => input.closest('label').scrollWidth <= input.closest('label').clientWidth));
        }
        await assertTempo('speech_speed', 'speech_speed_hint', profile.speed.default);
        async function assertPauseBounds(keys, required) {
          for (const key of keys) {
            const input = page.locator('#speech-' + key);
            assert.equal(await input.getAttribute('min'), String(pauseBounds.minimum));
            assert.equal(await input.getAttribute('max'), String(pauseMaximum));
            assert.equal(await input.getAttribute('step'), 'any');
            assert.equal(await input.getAttribute('required'), required ? '' : null);
          }
        }
        await assertPauseBounds(['paragraph_pause', 'scene_pause'], true);
        await page.locator('#speech-engine').selectOption('mlx-audio');
        await page.locator('#speech-language').selectOption('de');
        assert.equal(await page.locator('#speech-voice').isVisible(), true,
          'ZONOS3 exposes its fixed voices directly');
        assert.equal(await page.locator('#speech-provider_model').isVisible(), false,
          'The fixed local worker does not masquerade as an arbitrary HTTP provider');
        assert.equal(await page.locator('#speech-base_url').isVisible(), false);
        assert.equal(await page.locator('#speech-language').isVisible(), true);
        assert.equal(await speed.inputValue(), String(modelDefault),
          'Switching to ZONOS3 adopts its model speed default');
        await assertTempo('speech_speed_model', 'speech_speed_hint_model', modelDefault);
        assert.deepEqual(await page.locator('#speech-voice option').evaluateAll(options => options.map(option => option.value)),
          ['liesel', 'wolfgang', 'reference']);
        await page.locator('#modal-speech').screenshot({path: path.join(artifacts, `zonos-${width}.png`)});
        await page.locator('#speech-voice').selectOption('reference');
        assert.equal(await page.locator('#speech-reference_id').isVisible(), true,
          'Choosing the clone mode exposes the project reference');
        assert.equal(await page.locator('#speech-reference_id').getAttribute('required'), '',
          'The clone mode requires an explicit saved recording');
        await page.locator('#speech-reference_id').selectOption(server.fixture.reference);
        await page.locator('#speech-voice').selectOption('liesel');
        assert.equal(await page.locator('#speech-reference_id').inputValue(), '',
          'Returning to a fixed voice clears the incompatible reference binding');
        assert.equal(await page.locator('#speech-reference_id').isVisible(), false);
        assert.match(await page.locator('#speech-speed-hint').textContent(), /Modell|model|modèle/i,
          'ZONOS3 speed is explained as a model condition');
        await tabs.nth(1).focus();
        await page.keyboard.press('ArrowRight');
        assert.equal(await tabs.nth(1).evaluate(element => element === document.activeElement), true,
          'The keyboard stays on the active profile tab while edits block a switch');
        assert.equal(await tabs.nth(1).getAttribute('aria-selected'), 'true');
        assert.equal(await page.locator('#speech-status').textContent(), labels.speech_profiles_unsaved);
        await page.locator('[data-speech-action=profiles_discard]').click();
        await assertTempo('speech_speed', 'speech_speed_hint', profile.speed.default);
        await auditDialog('profiles');
        await page.locator('#modal-speech').screenshot({path: path.join(artifacts, `profiles-${width}.png`)});
        await page.locator('#speech-tab-reader').click();
        assert.deepEqual(await tabs.evaluateAll(items => items.map(tab => tab.id)),
          ['speech-tab-direction', 'speech-tab-output']);
        assert.equal(await page.locator('#modal-speech').evaluate(dialog => dialog.matches('.speech-docked[open]:not(:modal)')), true);
        assert.equal(await page.locator('#speech-chapter').isVisible(), true);
        assert.equal(await page.locator('.speech-export-section').isVisible(), true);
        assert.equal(await page.locator('#speech-export_scope').inputValue(), 'preview');
        assert.equal(await page.locator('#speech-engine').isVisible(), false);
        assert.equal(await page.locator('#speech-microphone-section').isVisible(), false);
        assert.equal(await page.locator('#speech-chapter_audio_file').isVisible(), false);
        assert.match(await page.locator('#speech-project-profile').textContent(), /Narrator/);
        assert.equal(await page.locator('#speech-direction_text').evaluate(text => Boolean(
          text.compareDocumentPosition(document.getElementById('speech-target')) & Node.DOCUMENT_POSITION_FOLLOWING
        )), true, 'The manuscript passage comes before optional render settings');
        assert.equal(await page.locator('[data-speech-action=preview]').evaluate(button => button.classList.contains('primary')), true);
        await assertPauseBounds(['direction_before', 'direction_after'], false);
        assert.equal(await page.locator('#speech-direction_after').inputValue(), '',
          'A blank direction override inherits the profile pause');
        await auditDialog('direction');
        await page.locator('#modal-speech').screenshot({path: path.join(artifacts, `direction-${width}.png`)});
        const scrollPanel = page.locator('#speech-panel');
        await scrollPanel.evaluate(element => { element.scrollTop = element.scrollHeight; });
        assert.ok(await scrollPanel.evaluate(element => element.scrollTop > 0));
        const directionTab = page.locator('#speech-tab-direction');
        const outputTab = page.locator('#speech-tab-output');
        await directionTab.focus();
        await page.keyboard.press('End');
        assert.equal(await outputTab.getAttribute('aria-selected'), 'true');
        assert.equal(await page.locator('#speech-chapter_audio_file').isVisible(), true);
        assert.equal(await page.locator('#speech-direction_text').isVisible(), false);
        assert.equal(await scrollPanel.evaluate(element => element.scrollTop), 0,
          'Switching audio tabs starts the new section at its heading');
        await auditDialog('output');
        await directionTab.click();
        await page.locator('#speech-edit-project-voice').click();
        const profileTab = page.locator('#speech-tab-profiles');
        const microphoneTab = page.locator('#speech-tab-microphone');
        assert.equal(await page.locator('#modal-speech').evaluate(dialog => dialog.matches(':modal')), true);
        assert.equal(await profileTab.getAttribute('aria-selected'), 'true');
        await profileTab.focus();
        await page.keyboard.press('End');
        assert.equal(await microphoneTab.getAttribute('aria-selected'), 'true');
        assert.equal(await page.locator('#speech-microphone-section').isVisible(), true);
        assert.equal(await page.locator('.speech-export-section').isVisible(), false);
        assert.equal(await page.locator('.speech-render-section').isVisible(), false);
        assert.equal(await page.locator('.author-voice-studio').isVisible(), false);
        const refreshMicrophones = page.locator('[data-speech-action=microphone_refresh]');
        assert.equal(await refreshMicrophones.isVisible(), true);
        assert.ok(await refreshMicrophones.evaluate(control => {
          const button = control.getBoundingClientRect();
          const section = control.closest('#speech-microphone-section').getBoundingClientRect();
          return button.left >= section.left && button.right <= section.right && control.scrollWidth <= control.clientWidth;
        }), 'The refresh control fits the microphone panel');
        await auditDialog('microphone');
        await page.locator('#modal-speech').screenshot({path: path.join(artifacts, `microphone-${width}.png`)});
        await microphoneTab.focus();
        await page.keyboard.press('Home');
        assert.equal(await tabs.nth(0).getAttribute('aria-selected'), 'true');
        assert.ok((await page.locator('.voice-rec-btn').getAttribute('data-help'))?.length > 20,
          'Recording has contextual guidance');
        await page.locator('.voice-rec-btn').focus();
        await page.waitForFunction(() => document.querySelector('#lixity-tooltip')?.getAttribute('aria-hidden') === 'false');
        assert.equal(await page.locator('#lixity-tooltip .tooltip-copy').textContent(),
          await page.locator('.voice-rec-btn').getAttribute('data-help'), 'Keyboard focus reveals recording help');
        await tabs.nth(0).focus();
        assert.equal(await page.evaluate(() => {
          const panel = document.querySelector('#modal-speech');
          return document.documentElement.scrollWidth <= innerWidth + 1 && panel.scrollWidth <= panel.clientWidth + 1;
        }), true, 'Page and dialog fit desktop and narrow mobile widths');
        await auditDialog('author voice');
        await page.mouse.move(0, 0);
        await page.locator('#modal-speech .modal-body').evaluate(element => {element.scrollTop = 0;});
        await page.waitForFunction(() => {
          const tip = document.querySelector('#lixity-tooltip');
          return !tip || getComputedStyle(tip).visibility === 'hidden';
        });
        await page.locator('#modal-speech').screenshot({path: path.join(artifacts, `voice-${width}.png`)});

        await page.evaluate(() => {
          window.microphoneAttempts = 0;
          navigator.mediaDevices.getUserMedia = async () => {
            ++window.microphoneAttempts;
            throw new DOMException('Permission denied by synthetic browser', 'NotAllowedError');
          };
        });
        await page.locator('.voice-rec-btn').click();
        await page.waitForFunction(() => document.querySelector('#speech-status')?.textContent === uiLabel('speech_mic_permission'));
        assert.match(await page.locator('#speech-status').textContent(), /Browser|Berechtigung|erlaub/i,
          'Permission refusal explains how to allow microphone access');
        assert.equal(await page.locator('.voice-rec-btn').isEnabled(), true, 'Permission failure permits retry');
        await page.locator('.voice-rec-btn').click();
        await page.waitForFunction(() => window.microphoneAttempts === 2);
        assert.equal(await page.evaluate(() => window.microphoneAttempts), 2);
        await page.locator('#modal-speech').screenshot({path: path.join(artifacts, `permission-${width}.png`)});

        await page.locator('[data-speech-action=recording_duration_edit]').click();
        const recordingDuration = page.getByRole('spinbutton', {name:labels.speech_recording_duration});
        assert.equal(await recordingDuration.evaluate(input => input === document.activeElement), true);
        assert.equal(await tabs.nth(0).getAttribute('aria-selected'), 'true',
          'Changing the recording limit stays in Author’s Voice');
        assert.equal(await recordingDuration.inputValue(), '');
        assert.equal(await recordingDuration.getAttribute('placeholder'), '60');
        assert.ok(await recordingDuration.evaluate(input => input.closest('label').scrollWidth <= input.closest('label').clientWidth));
        await recordingDuration.fill('61');
        assert.equal(await recordingDuration.evaluate(input => input.checkValidity()), false);
        await recordingDuration.fill('28');
        await tabs.nth(1).click();
        assert.equal(await tabs.nth(0).getAttribute('aria-selected'), 'true');
        assert.equal(await page.locator('#speech-status').textContent(), labels.speech_recording_duration_unsaved);
        const durationSave = page.locator('[data-speech-action=recording_duration_save]');
        async function persistRecordingDuration(expected) {
          const posted = page.waitForRequest(request => new URL(request.url()).pathname === '/api/settings');
          const reloaded = page.waitForEvent('load');
          await durationSave.click();
          const payload = (await posted).postDataJSON();
          assert.deepEqual(payload.audio_recording, expected);
          assert.equal(Object.hasOwn(payload, 'audio'), false, 'Saving a project limit does not save edited voice profiles');
          await reloaded;
          await page.locator('#tab-view-project').click();
          await page.locator('#btn-project-record-voice').click();
          await page.waitForFunction(() => document.querySelector('#speech-name')?.value === 'Narrator');
          await page.locator('.voice-rec-btn:enabled').waitFor();
        }
        await persistRecordingDuration({reference_seconds:28});

        // Real Web Audio signal with a synthetic stream; never use physical input devices.
        await page.evaluate(async () => {
          window.syntheticAudio = new AudioContext();
          window.syntheticDestination = window.syntheticAudio.createMediaStreamDestination();
          window.syntheticOscillator = window.syntheticAudio.createOscillator();
          window.syntheticOscillator.frequency.value = 440;
          window.syntheticOscillator.connect(window.syntheticDestination);
          window.syntheticOscillator.start();
          await window.syntheticAudio.resume();
          window.recordingTracks = [];
          navigator.mediaDevices.getUserMedia = async () => {
            const stream = window.syntheticDestination.stream.clone();
            window.recordingTracks.push(...stream.getTracks());
            return stream;
          };
        });
        await page.getByRole('button', {name:labels.speech_sample_full, exact:true}).click();
        const record = page.locator('.voice-rec-btn');
        assert.match(await page.locator('#speech-record-limit').innerText(), /28 Sekunden/);
        await record.focus();
        await page.keyboard.press('Enter');
        await page.waitForFunction(() => document.querySelector('.voice-rec-btn')?.classList.contains('is-recording'));
        assert.equal(await record.evaluate(button => button === document.activeElement), true);
        assert.equal(await record.getAttribute('data-help'), labels.speech_record_stop_help);
        assert.match(await page.locator('.voice-rec-timer').innerText(), /^\d\d:\d\d \/ 00:28$/);
        assert.equal(await page.locator('.voice-record-controls').evaluate(controls => controls.scrollWidth <= controls.clientWidth + 1), true);
        await tabs.nth(0).click();
        assert.equal(await page.locator('#speech-status').textContent(),
          await page.evaluate(() => uiLabel('speech_record_running')),
          'Selecting the active tab preserves the running recording feedback');
        await page.waitForFunction(() => document.querySelector('.voice-rec-timer')?.textContent.startsWith('00:02'));
        await record.press('Space');
        await page.waitForFunction(() => Boolean(document.querySelector('.voice-take-card audio')?.getAttribute('src')));
        assert.equal(await page.locator('.voice-take-card').isVisible(), true);
        assert.equal(await page.evaluate(() => window.recordingTracks.every(track => track.readyState === 'ended')), true,
          'Stopping recording releases every microphone track');
        const take = page.locator('.voice-take-card .speech-player');
        assert.equal(await take.isVisible(), true, 'A completed take exposes the same audio player as previews');
        await page.waitForFunction(() => document.querySelector('.voice-take-card audio')?.duration > 0);
        const playLabel = await page.evaluate(() => uiLabel('speech_player_play'));
        await take.getByRole('button', {name: playLabel, exact: true}).click();
        await page.waitForFunction(() => document.querySelector('.voice-take-card audio')?.currentTime > 0);
        assert.equal(await take.getAttribute('data-spectrum'), 'playback');
        assert.match(await take.locator('.speech-player-time').textContent(), /0:0[012]\s*\/\s*0:0[123]/);
        await page.locator('#modal-speech').screenshot({path: path.join(artifacts, `take-${width}.png`)});
        await page.evaluate(() => {
          window.originalProcessor = window.AudioWorkletNode;
          window.AudioWorkletNode = function(...args) {
            const processor = new window.originalProcessor(...args);
            // Model a device that starts but supplies no buffers before being stopped.
            Object.defineProperty(processor.port, 'onmessage', {set() {}, configurable: true});
            return processor;
          };
        });
        await page.locator('.voice-rec-btn').click();
        await page.waitForFunction(() => document.querySelector('.voice-rec-btn')?.classList.contains('is-recording'));
        await page.locator('.voice-rec-btn').click();
        assert.equal(await page.locator('.voice-save-btn').isEnabled(), false,
          'An empty replacement take cannot save the previous audio with a new transcript');
        await page.evaluate(() => {window.AudioWorkletNode = window.originalProcessor;});
        await record.click();
        await page.waitForFunction(() => document.querySelector('.voice-rec-timer')?.textContent.startsWith('00:01'));
        await record.click();
        const discardTake = page.locator('[data-speech-action=take_discard]');
        await discardTake.waitFor();
        await page.locator('#modal-speech [data-speech-action=close]').focus();
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('#speech-status').textContent(), labels.speech_take_unsaved);
        await discardTake.click();
        assert.equal(await page.locator('.voice-take-card').isVisible(), false);
        assert.equal(await record.evaluate(button => button === document.activeElement), true);
        assert.equal(await page.locator('#speech-status').textContent(), labels.speech_take_discarded);
        await page.locator('.voice-rec-btn').click();
        await page.waitForFunction(() => document.querySelector('.voice-rec-btn')?.classList.contains('is-recording'));
        await page.locator('#modal-speech [data-speech-action=close]').click();
        await page.waitForFunction(() => window.recordingTracks.every(track => track.readyState === 'ended'));
        assert.equal(await page.locator('#modal-speech').isVisible(), false);

        // A permission response may arrive after dismissal. It must not reopen recording.
        await page.locator('#tab-view-project').click();
        await page.locator('#btn-project-record-voice').click();
        await page.waitForFunction(() => document.querySelector('#speech-name')?.value === 'Narrator');
        await page.evaluate(() => {
          navigator.mediaDevices.getUserMedia = () => new Promise(resolve => {window.resolveMicrophone = resolve;});
        });
        await page.locator('.voice-rec-btn').click();
        await page.waitForFunction(() => Boolean(window.resolveMicrophone));
        assert.equal(await page.locator('.voice-rec-btn').isEnabled(), false,
          'A pending microphone prompt cannot launch a second recording request');
        await page.locator('#modal-speech [data-speech-action=close]').click();
        await page.evaluate(() => {
          const stream = window.syntheticDestination.stream.clone();
          window.recordingTracks.push(...stream.getTracks());
          window.resolveMicrophone(stream);
        });
        await page.waitForFunction(() => window.recordingTracks.every(track => track.readyState === 'ended'));
        assert.equal(await page.locator('#modal-speech').isVisible(), false);
        await page.locator('#btn-project-record-voice').click();
        await page.waitForFunction(() => document.querySelector('#speech-name')?.value === 'Narrator');
        await page.evaluate(() => {
          navigator.mediaDevices.getUserMedia = async () => window.syntheticDestination.stream.clone();
        });
        await page.locator('.voice-rec-btn').click();
        await page.waitForFunction(() => document.querySelector('.voice-rec-btn')?.classList.contains('is-recording'));
        await page.waitForFunction(() => document.querySelector('.voice-rec-timer')?.textContent.startsWith('00:02'));
        await page.locator('.voice-rec-btn').click();
        await page.evaluate(async () => {
          window.syntheticOscillator.stop();
          window.syntheticDestination.stream.getTracks().forEach(track => track.stop());
          await window.syntheticAudio.close();
        });
        await page.locator('#speech-take_confirmed').waitFor();
        assert.equal(await page.locator('.voice-save-btn').isEnabled(),false,'A captured script remains an unconfirmed draft');
        const transcript = 'Only these synthetic words were spoken.';
        await page.locator('.voice-take-card textarea').fill(transcript);
        await page.locator('#speech-take_confirmed').check();
        // Gate in the disposable server so this exercises an ordinary HTTP body
        // in both browsers, including the pending-save tab/recording guards.
        const pendingFile=path.join(artifacts,'save-pending'), releaseFile=path.join(artifacts,'release-save');
        fs.rmSync(pendingFile,{force:true}); fs.rmSync(releaseFile,{force:true});
        const pendingRequest=page.waitForRequest(request=>request.url().endsWith('/api/audio-microphone'));
        await page.locator('.voice-save-btn').click();
        const savedPayload=(await pendingRequest).postDataJSON();
        const pendingDeadline=Date.now()+10000;
        while(!fs.existsSync(pendingFile)) {
          assert.ok(Date.now()<pendingDeadline,'The native server must receive the held save');
          await new Promise(resolve=>setTimeout(resolve,10));
        }
        assert.equal(savedPayload.transcript, transcript, 'Saving uses the reviewed transcript exactly');
        assert.equal(await page.locator('.voice-rec-btn').isEnabled(), false,
          'Saving a voice cannot race with recording a replacement');
        await tabs.nth(1).click();
        assert.equal(await tabs.nth(0).getAttribute('aria-selected'), 'true', 'Pending save keeps its source tab');
        const savedResponse = page.waitForResponse(response => response.url().endsWith('/api/audio-microphone'));
        const reloaded = page.waitForEvent('load');
        // Preserve the original save assertion if failure closes the page before any reload.
        reloaded.catch(() => {});
        fs.writeFileSync(releaseFile,'release');
        const response = await savedResponse;
        assert.equal(response.status(), 200);
        await reloaded.catch(async error => {
          const state = await page.evaluate(() => ({ready: document.readyState, title: document.title,
            status: document.querySelector('#speech-status')?.textContent,
            open: document.querySelector('#modal-speech')?.open,
            navigation: performance.getEntriesByType('navigation').map(entry => ({type: entry.type, load: entry.loadEventEnd})),
            saveDisabled: document.querySelector('.voice-save-btn')?.disabled,
            recordDisabled:document.querySelector('.voice-rec-btn')?.disabled,
            confirmationHidden:document.querySelector('#speech-take_confirmed')?.closest('label').hidden,
          }));
          await page.screenshot({path: path.join(artifacts, `save-load-failure-${width}.png`)});
          throw new Error('Saved reference did not finish reloading: ' + JSON.stringify(state) +
            '; response status: '+response.status()+'; pageerrors: '+JSON.stringify(errors), {cause: error});
        });
        if (axe) await page.evaluate(fs.readFileSync(axe, 'utf8'));
        await page.locator('#tab-view-project').click();
        const reopenedSpeech=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/speech');
        await page.locator('#btn-project-record-voice').click();
        const persisted=await (await reopenedSpeech).json();
        await page.waitForFunction(() => document.querySelector('#speech-name')?.value === 'Narrator');
        await page.waitForFunction(text => document.querySelector('.voice-active-card')?.textContent.includes(text), transcript)
          .catch(async error => {
            const detail = '\nSaved-reference UI: ' + JSON.stringify(await page.evaluate(() => ({
              status: document.querySelector('#speech-status')?.textContent,
              badge: document.querySelector('.voice-active-card')?.textContent,
              profile: document.querySelector('#speech-profile')?.value,
              engine: document.querySelector('#speech-engine')?.value,
              reference: document.querySelector('#speech-reference_id')?.value,
              library: document.querySelector('.voice-reference-list')?.textContent,
            })));
            throw new Error(detail, {cause: error});
          });
        const activeReference=persisted.settings.profiles[persisted.settings.selected].reference_id;
        assert.equal(persisted.references.find(reference=>reference.id===activeReference)?.transcript,transcript,
          'The reloaded native profile activates the exact reviewed recording');
        assert.equal(await page.locator('#speech-reference_id').inputValue(),activeReference);
        assert.equal(await page.locator('#speech-engine').inputValue(), 'qwen3-base',
          'The author voice refresh shows the server-selected reference engine');
        assert.ok((await page.locator('.voice-reference-list').textContent()).includes(transcript));
        await page.locator('.author-voice-studio .voice-active-card').scrollIntoViewIfNeeded();
        await auditDialog('saved author voice');
        await page.locator('#modal-speech').screenshot({path: path.join(artifacts, `saved-${width}.png`)});
        await page.locator('[data-speech-action=recording_duration_edit]').click();
        assert.equal(await recordingDuration.inputValue(), '28', 'Saving the take retains the recording preference');
        await recordingDuration.fill('');
        await persistRecordingDuration({});
        assert.match(await page.locator('#speech-record-limit').innerText(), /60 Sekunden/);
        assert.deepEqual(errors, []);
      } finally { await page.close(); }
    }
    assert.deepEqual(fs.readFileSync(server.fixture.source), original);
    console.log(`Audio studio desktop/mobile passed (${useFirefox ? 'Firefox' : 'Chromium'} ${browser.version()}): ${artifacts}`);
  } finally { await browser.close(); await server.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
