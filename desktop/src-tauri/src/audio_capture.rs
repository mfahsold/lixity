//! Cross-platform 24 kHz mono 16-bit PCM capture & level calibration via `cpal` + `hound`.
//!
//! Delivers identical microphone recording and `-13.0` to `-7.0 dBFS` signal checks
//! across macOS (CoreAudio), Windows (WASAPI), and Linux (PipeWire/ALSA), matching
//! the exact calibration rubric of `src/lixity/speech_record.py` and the portable
//! `lixity-audio-take/1` WAV+SHA-256 metadata contract.

use base64::Engine;
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::io::Cursor;
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

pub const TARGET_SAMPLE_RATE: u32 = 24_000;
const MIN_DURATION_SEC: f32 = 1.0;
const MAX_DURATION_SEC: f32 = 30.0;

#[derive(Debug, Serialize)]
pub struct CaptureDeviceInfo {
    pub id: String,
    pub label: String,
    pub is_default: bool,
}

#[derive(Debug, Serialize)]
pub struct CalibrationSegment {
    pub time_seconds: f64,
    pub peak_dbfs: f64,
    pub rms_dbfs: f64,
    pub clipping: bool,
}

#[derive(Debug, Serialize)]
pub struct CalibrationReport {
    pub schema_version: &'static str,
    pub duration_seconds: f64,
    pub sample_rate: u32,
    pub peak_dbfs: f64,
    pub clipping_samples: usize,
    pub noise_floor_dbfs: f64,
    pub snr_db: f64,
    pub segments: Vec<CalibrationSegment>,
    pub verdict: &'static str,
    pub verdict_label: &'static str,
}

#[derive(Debug, Serialize)]
pub struct RecordedTakeResult {
    pub schema_version: &'static str,
    pub filename: String,
    pub wav_base64: String,
    pub sha256: String,
    pub channels: u16,
    pub sample_rate_hz: u32,
    pub sample_width_bits: u16,
    pub frames: usize,
    pub duration_seconds: f64,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct RecordingLiveStatus {
    pub recording: bool,
    pub elapsed_seconds: f64,
    pub peak_dbfs: f64,
    pub rms_dbfs: f64,
    pub auto_stopped: bool,
    pub max_duration_seconds: f32,
}

impl Default for RecordingLiveStatus {
    fn default() -> Self {
        Self {
            recording: false,
            elapsed_seconds: 0.0,
            peak_dbfs: -120.0,
            rms_dbfs: -120.0,
            auto_stopped: false,
            max_duration_seconds: MAX_DURATION_SEC,
        }
    }
}

type CaptureResult = Result<(Vec<f32>, u32), String>;

struct ActiveCapture {
    window: String,
    stop_flag: Arc<AtomicBool>,
    auto_stopped: Arc<AtomicBool>,
    live_peak_bits: Arc<AtomicU32>,
    live_rms_bits: Arc<AtomicU32>,
    started_at: Option<Instant>,
    filename: String,
    join_handle: JoinHandle<CaptureResult>,
}

/// Thread-safe handle for interactive Start / Stop voice recording across OSes.
///
/// Owns the non-`Send` `cpal::Stream` strictly inside a dedicated capture thread so
/// Tauri commands stay `Send + Sync` on CoreAudio, WASAPI and ALSA/PipeWire.
#[derive(Default)]
pub struct InteractiveRecorder {
    active: Mutex<Option<ActiveCapture>>,
}

impl InteractiveRecorder {
    pub fn start(
        &self,
        window: String,
        device_name: Option<String>,
        filename: String,
    ) -> Result<(), String> {
        let mut guard = self
            .active
            .lock()
            .map_err(|_| "Recorder state lock poisoned".to_string())?;
        if guard.is_some() {
            return Err("A recording session is already running".to_string());
        }

        let stop_flag = Arc::new(AtomicBool::new(false));
        let auto_stopped = Arc::new(AtomicBool::new(false));
        let live_peak_bits = Arc::new(AtomicU32::new(0.0_f32.to_bits()));
        let live_rms_bits = Arc::new(AtomicU32::new(0.0_f32.to_bits()));
        let (ready_tx, ready_rx) = mpsc::sync_channel::<Result<(), String>>(1);

        let thread_stop = Arc::clone(&stop_flag);
        let thread_auto = Arc::clone(&auto_stopped);
        let thread_peak = Arc::clone(&live_peak_bits);
        let thread_rms = Arc::clone(&live_rms_bits);

        let join_handle = thread::spawn(move || {
            run_capture_loop(
                device_name.as_deref(),
                thread_stop,
                thread_auto,
                thread_peak,
                thread_rms,
                ready_tx,
            )
        });

        *guard = Some(ActiveCapture {
            window,
            stop_flag: Arc::clone(&stop_flag),
            auto_stopped,
            live_peak_bits,
            live_rms_bits,
            started_at: None,
            filename,
            join_handle,
        });
        // The window can close while a microphone driver is still starting.
        drop(guard);
        let result = ready_rx
            .recv_timeout(Duration::from_secs(5))
            .unwrap_or_else(|_| Err("Timed out initializing microphone stream".to_string()));
        let same_session = |active: &ActiveCapture| Arc::ptr_eq(&active.stop_flag, &stop_flag);
        if let Err(err) = result {
            self.cancel_matching(same_session);
            return Err(err);
        }
        let mut guard = self
            .active
            .lock()
            .map_err(|_| "Recorder state lock poisoned".to_string())?;
        if let Some(active) = guard.as_mut().filter(|active| same_session(active)) {
            active.started_at = Some(Instant::now());
            Ok(())
        } else {
            Err("Recording was cancelled before the microphone was ready".to_string())
        }
    }

    pub fn owns_capture(&self, window: &str) -> bool {
        self.active
            .lock()
            .is_ok_and(|guard| guard.as_ref().is_some_and(|active| active.window == window))
    }

    pub fn status(&self, window: &str) -> RecordingLiveStatus {
        let Ok(guard) = self.active.lock() else {
            return RecordingLiveStatus::default();
        };
        let Some(active) = guard.as_ref().filter(|active| active.window == window) else {
            return RecordingLiveStatus::default();
        };
        let Some(started_at) = active.started_at else {
            return RecordingLiveStatus::default();
        };
        let auto = active.auto_stopped.load(Ordering::Relaxed);
        let peak_amp = f32::from_bits(active.live_peak_bits.load(Ordering::Relaxed)) as f64;
        let rms_amp = f32::from_bits(active.live_rms_bits.load(Ordering::Relaxed)) as f64;
        RecordingLiveStatus {
            recording: !auto && !active.join_handle.is_finished(),
            elapsed_seconds: round2(started_at.elapsed().as_secs_f64()),
            peak_dbfs: round1(dbfs(peak_amp * 32_768.0)),
            rms_dbfs: round1(dbfs(rms_amp * 32_768.0)),
            auto_stopped: auto,
            max_duration_seconds: MAX_DURATION_SEC,
        }
    }

    fn take_matching(
        &self,
        matches: impl FnOnce(&ActiveCapture) -> bool,
    ) -> Result<Option<ActiveCapture>, String> {
        let mut guard = self
            .active
            .lock()
            .map_err(|_| "Recorder state lock poisoned".to_string())?;
        let Some(active) = guard.as_ref().filter(|active| matches(active)) else {
            return Ok(None);
        };
        active.stop_flag.store(true, Ordering::SeqCst);
        Ok(guard.take())
    }

    pub fn stop(&self, window: &str) -> Result<RecordedTakeResult, String> {
        let session = self
            .take_matching(|active| active.window == window && active.started_at.is_some())?
            .ok_or_else(|| "No active recording session for this window".to_string())?;
        let (raw, rate) = session
            .join_handle
            .join()
            .map_err(|_| "Audio capture thread panicked".to_string())??;
        finalize_wav_take(&raw, rate, &session.filename)
    }

    fn cancel_matching(&self, matches: impl FnOnce(&ActiveCapture) -> bool) {
        if let Ok(Some(active)) = self.take_matching(matches) {
            let _ = active.join_handle.join();
        }
    }

    pub fn cancel(&self, window: &str) {
        self.cancel_matching(|active| active.window == window);
    }

    pub fn discard_window(&self, window: &str) {
        // Window events run on the GUI thread. Signal shutdown now and let
        // the capture thread finish without blocking its former window.
        let _ = self.take_matching(|active| active.window == window);
    }

    pub fn cancel_all(&self) {
        self.cancel_matching(|_| true);
    }
}

pub fn list_input_devices() -> Result<Vec<CaptureDeviceInfo>, String> {
    let host = cpal::default_host();
    let default_name = host
        .default_input_device()
        .and_then(|dev| dev.name().ok());
    let devices = host
        .input_devices()
        .map_err(|e| format!("Unable to enumerate audio input devices: {e}"))?;

    let mut out = Vec::new();
    for dev in devices {
        if let Ok(name) = dev.name() {
            let is_default = default_name.as_deref() == Some(name.as_str());
            out.push(CaptureDeviceInfo {
                id: name.clone(),
                label: name,
                is_default,
            });
        }
    }
    Ok(out)
}

fn select_input_device(preferred: Option<&str>) -> Result<cpal::Device, String> {
    let host = cpal::default_host();
    if let Some(wanted) = preferred.map(str::trim).filter(|s| !s.is_empty()) {
        let devices = host
            .input_devices()
            .map_err(|e| format!("Audio device lookup failed: {e}"))?;
        for dev in devices {
            if dev.name().ok().as_deref() == Some(wanted) {
                return Ok(dev);
            }
        }
        return Err(format!("Audio input device not found: {wanted}"));
    }
    host.default_input_device()
        .ok_or_else(|| "No default microphone device available".to_string())
}

/// Linear down/up-sampling from hardware sample rate to 24 kHz mono f32 samples.
pub fn resample_mono(input: &[f32], src_rate: u32, dst_rate: u32) -> Vec<f32> {
    if input.is_empty() || src_rate == 0 || dst_rate == 0 {
        return Vec::new();
    }
    if src_rate == dst_rate {
        return input.to_vec();
    }
    let ratio = src_rate as f64 / dst_rate as f64;
    let out_len = ((input.len() as f64) / ratio).floor().max(1.0) as usize;
    let mut output = Vec::with_capacity(out_len);
    for idx in 0..out_len {
        let pos = idx as f64 * ratio;
        let left = (pos.floor() as usize).min(input.len() - 1);
        let right = (left + 1).min(input.len() - 1);
        let frac = (pos - left as f64) as f32;
        output.push(input[left] * (1.0 - frac) + input[right] * frac);
    }
    output
}

pub fn f32_to_pcm16(samples: &[f32]) -> Vec<i16> {
    samples
        .iter()
        .map(|&s| {
            let clamped = if s.is_finite() { s.clamp(-1.0, 1.0) } else { 0.0 };
            if clamped < 0.0 {
                (clamped * 32768.0).round().clamp(-32768.0, 32767.0) as i16
            } else {
                (clamped * 32767.0).round().clamp(-32768.0, 32767.0) as i16
            }
        })
        .collect()
}

pub fn encode_mono_pcm16_wav(samples: &[i16], sample_rate: u32) -> Result<Vec<u8>, String> {
    let spec = hound::WavSpec {
        channels: 1,
        sample_rate,
        bits_per_sample: 16,
        sample_format: hound::SampleFormat::Int,
    };
    let mut cursor = Cursor::new(Vec::<u8>::with_capacity(44 + samples.len() * 2));
    {
        let mut writer = hound::WavWriter::new(&mut cursor, spec)
            .map_err(|e| format!("WAV encoder init failed: {e}"))?;
        for &s in samples {
            writer
                .write_sample(s)
                .map_err(|e| format!("WAV write failed: {e}"))?;
        }
        writer
            .finalize()
            .map_err(|e| format!("WAV finalize failed: {e}"))?;
    }
    Ok(cursor.into_inner())
}

pub fn dbfs(value: f64) -> f64 {
    20.0 * (value.max(1.0) / 32768.0).log10()
}

fn round1(v: f64) -> f64 {
    (v * 10.0).round() / 10.0
}

fn round2(v: f64) -> f64 {
    (v * 100.0).round() / 100.0
}

/// Descriptive signal analysis matching `src/lixity/speech_record.py::analyze_signal`.
pub fn analyze_pcm16_signal(samples: &[i16], sample_rate: u32) -> CalibrationReport {
    if samples.is_empty() || sample_rate == 0 {
        return CalibrationReport {
            schema_version: "lixity-audio-calibration/1",
            duration_seconds: 0.0,
            sample_rate,
            peak_dbfs: -120.0,
            clipping_samples: 0,
            noise_floor_dbfs: -120.0,
            snr_db: 0.0,
            segments: Vec::new(),
            verdict: "too_quiet",
            verdict_label: "MEHR LUFT ALS NÖTIG",
        };
    }

    let peak_val = samples
        .iter()
        .map(|&s| (s as i32).unsigned_abs() as f64)
        .fold(0.0_f64, f64::max);
    let peak_db = dbfs(peak_val);
    let clipping = samples
        .iter()
        .filter(|&&s| (s as i32).unsigned_abs() >= 32_600)
        .count();

    let half_sec = (sample_rate / 2).max(1) as usize;
    let mut floors = Vec::new();
    let mut segments = Vec::new();
    for (idx, chunk) in samples.chunks_exact(half_sec).enumerate() {
        let cp = chunk
            .iter()
            .map(|&s| (s as i32).unsigned_abs() as f64)
            .fold(0.0_f64, f64::max);
        let sum_sq: f64 = chunk.iter().map(|&s| (s as f64) * (s as f64)).sum();
        let rms = (sum_sq / chunk.len() as f64).sqrt();
        floors.push(rms);
        segments.push(CalibrationSegment {
            time_seconds: round1(idx as f64 * 0.5),
            peak_dbfs: round1(dbfs(cp)),
            rms_dbfs: round1(dbfs(rms)),
            clipping: cp >= 32_600.0,
        });
    }

    let floor_db = floors
        .into_iter()
        .reduce(f64::min)
        .map(dbfs)
        .unwrap_or(-120.0);
    let snr_db = (peak_db - floor_db).max(0.0);

    let (verdict, verdict_label) = if (-13.0..=-7.0).contains(&peak_db) {
        ("calibrated", "CALIBRIERT FÜR AUFNAHMEN!")
    } else if peak_db > -7.0 {
        ("too_hot", "ZU HEISS")
    } else {
        ("too_quiet", "MEHR LUFT ALS NÖTIG")
    };

    CalibrationReport {
        schema_version: "lixity-audio-calibration/1",
        duration_seconds: round2(samples.len() as f64 / sample_rate as f64),
        sample_rate,
        peak_dbfs: round1(peak_db),
        clipping_samples: clipping,
        noise_floor_dbfs: round1(floor_db),
        snr_db: round1(snr_db),
        segments,
        verdict,
        verdict_label,
    }
}

fn update_live_levels(samples: &[f32], peak_bits: &AtomicU32, rms_bits: &AtomicU32) {
    if samples.is_empty() {
        return;
    }
    let mut peak = 0.0_f32;
    let mut sum_sq = 0.0_f64;
    for &s in samples {
        let a = s.abs();
        if a > peak {
            peak = a;
        }
        sum_sq += (s as f64) * (s as f64);
    }
    let rms = (sum_sq / samples.len() as f64).sqrt() as f32;
    peak_bits.store(peak.to_bits(), Ordering::Relaxed);
    rms_bits.store(rms.to_bits(), Ordering::Relaxed);
}

struct CaptureStreamParams {
    channels: usize,
    sample_format: cpal::SampleFormat,
    config: cpal::StreamConfig,
    max_samples: usize,
    captured: Arc<Mutex<Vec<f32>>>,
    auto_stopped: Arc<AtomicBool>,
    peak_bits: Arc<AtomicU32>,
    rms_bits: Arc<AtomicU32>,
    stream_err: Arc<Mutex<Option<String>>>,
}

fn build_capture_stream(
    device: &cpal::Device,
    params: CaptureStreamParams,
) -> Result<cpal::Stream, String> {
    let CaptureStreamParams {
        channels,
        sample_format,
        config,
        max_samples,
        captured,
        auto_stopped,
        peak_bits,
        rms_bits,
        stream_err,
    } = params;
    let err_fn = move |err: cpal::StreamError| {
        if let Ok(mut guard) = stream_err.lock() {
            *guard = Some(err.to_string());
        }
    };
    let stream = match sample_format {
        cpal::SampleFormat::F32 => device.build_input_stream(
            &config,
            move |data: &[f32], _| {
                if let Ok(mut out) = captured.lock() {
                    let mut mono = Vec::with_capacity(data.len() / channels.max(1));
                    for frame in data.chunks(channels) {
                        if out.len() >= max_samples {
                            auto_stopped.store(true, Ordering::Relaxed);
                            break;
                        }
                        let s = frame[0];
                        out.push(s);
                        mono.push(s);
                    }
                    update_live_levels(&mono, &peak_bits, &rms_bits);
                }
            },
            err_fn,
            None,
        ),
        cpal::SampleFormat::I16 => device.build_input_stream(
            &config,
            move |data: &[i16], _| {
                if let Ok(mut out) = captured.lock() {
                    let mut mono = Vec::with_capacity(data.len() / channels.max(1));
                    for frame in data.chunks(channels) {
                        if out.len() >= max_samples {
                            auto_stopped.store(true, Ordering::Relaxed);
                            break;
                        }
                        let s = frame[0] as f32 / 32768.0;
                        out.push(s);
                        mono.push(s);
                    }
                    update_live_levels(&mono, &peak_bits, &rms_bits);
                }
            },
            err_fn,
            None,
        ),
        cpal::SampleFormat::U16 => device.build_input_stream(
            &config,
            move |data: &[u16], _| {
                if let Ok(mut out) = captured.lock() {
                    let mut mono = Vec::with_capacity(data.len() / channels.max(1));
                    for frame in data.chunks(channels) {
                        if out.len() >= max_samples {
                            auto_stopped.store(true, Ordering::Relaxed);
                            break;
                        }
                        let s = (frame[0] as f32 - 32768.0) / 32768.0;
                        out.push(s);
                        mono.push(s);
                    }
                    update_live_levels(&mono, &peak_bits, &rms_bits);
                }
            },
            err_fn,
            None,
        ),
        other => return Err(format!("Unsupported microphone sample format: {other:?}")),
    }
    .map_err(|e| format!("Unable to open microphone stream: {e}"))?;
    Ok(stream)
}

fn run_capture_loop(
    device_name: Option<&str>,
    stop_flag: Arc<AtomicBool>,
    auto_stopped: Arc<AtomicBool>,
    live_peak_bits: Arc<AtomicU32>,
    live_rms_bits: Arc<AtomicU32>,
    ready_tx: mpsc::SyncSender<Result<(), String>>,
) -> Result<(Vec<f32>, u32), String> {
    let device = match select_input_device(device_name) {
        Ok(d) => d,
        Err(e) => {
            let _ = ready_tx.send(Err(e.clone()));
            return Err(e);
        }
    };
    let supported = match device.default_input_config() {
        Ok(cfg) => cfg,
        Err(e) => {
            let msg = format!("Failed reading microphone configuration: {e}");
            let _ = ready_tx.send(Err(msg.clone()));
            return Err(msg);
        }
    };
    let sample_rate = supported.sample_rate().0;
    let channels = supported.channels() as usize;
    let sample_format = supported.sample_format();
    let config: cpal::StreamConfig = supported.into();
    let max_samples = (sample_rate as f64 * MAX_DURATION_SEC as f64) as usize;

    let captured: Arc<Mutex<Vec<f32>>> = Arc::new(Mutex::new(Vec::with_capacity(
        (sample_rate as usize).saturating_mul(10),
    )));
    let stream_err: Arc<Mutex<Option<String>>> = Arc::new(Mutex::new(None));

    let stream = match build_capture_stream(
        &device,
        CaptureStreamParams {
            channels,
            sample_format,
            config,
            max_samples,
            captured: Arc::clone(&captured),
            auto_stopped: Arc::clone(&auto_stopped),
            peak_bits: live_peak_bits,
            rms_bits: live_rms_bits,
            stream_err: Arc::clone(&stream_err),
        },
    ) {
        Ok(s) => s,
        Err(e) => {
            let _ = ready_tx.send(Err(e.clone()));
            return Err(e);
        }
    };

    if stop_flag.load(Ordering::SeqCst) {
        let error = "Recording was cancelled".to_string();
        let _ = ready_tx.send(Err(error.clone()));
        return Err(error);
    }
    if let Err(e) = stream.play() {
        let msg = format!("Failed starting microphone stream: {e}");
        let _ = ready_tx.send(Err(msg.clone()));
        return Err(msg);
    }
    let _ = ready_tx.send(Ok(()));

    let started = Instant::now();
    let max_dur = Duration::from_secs_f32(MAX_DURATION_SEC);
    while !stop_flag.load(Ordering::Relaxed)
        && !auto_stopped.load(Ordering::Relaxed)
        && stream_err.lock().is_ok_and(|error| error.is_none())
    {
        if started.elapsed() >= max_dur {
            auto_stopped.store(true, Ordering::Relaxed);
            break;
        }
        thread::sleep(Duration::from_millis(25));
    }
    drop(stream);

    let failure = stream_err
        .lock()
        .map_err(|_| "Audio capture error state poisoned".to_string())?
        .take();
    if let Some(err) = failure {
        return Err(format!("Microphone capture error: {err}"));
    }
    let samples = captured
        .lock()
        .map(|g| g.clone())
        .map_err(|_| "Audio capture buffer poisoned".to_string())?;
    Ok((samples, sample_rate))
}

fn record_mono_f32(device_name: Option<&str>, duration_seconds: f32) -> Result<(Vec<f32>, u32), String> {
    if !(MIN_DURATION_SEC..=MAX_DURATION_SEC).contains(&duration_seconds) {
        return Err(format!(
            "Recording duration must be between {MIN_DURATION_SEC} and {MAX_DURATION_SEC} seconds"
        ));
    }
    let device = select_input_device(device_name)?;
    let supported = device
        .default_input_config()
        .map_err(|e| format!("Failed reading microphone configuration: {e}"))?;
    let sample_rate = supported.sample_rate().0;
    let channels = supported.channels() as usize;
    let sample_format = supported.sample_format();
    let config: cpal::StreamConfig = supported.into();
    let max_samples = (sample_rate as f32 * (duration_seconds + 0.5)) as usize;

    let captured: Arc<Mutex<Vec<f32>>> = Arc::new(Mutex::new(Vec::with_capacity(max_samples)));
    let stream_err: Arc<Mutex<Option<String>>> = Arc::new(Mutex::new(None));
    let auto_stopped = Arc::new(AtomicBool::new(false));
    let peak_bits = Arc::new(AtomicU32::new(0));
    let rms_bits = Arc::new(AtomicU32::new(0));

    let stream = build_capture_stream(
        &device,
        CaptureStreamParams {
            channels,
            sample_format,
            config,
            max_samples,
            captured: Arc::clone(&captured),
            auto_stopped,
            peak_bits,
            rms_bits,
            stream_err: Arc::clone(&stream_err),
        },
    )?;

    stream
        .play()
        .map_err(|e| format!("Failed starting microphone stream: {e}"))?;
    thread::sleep(Duration::from_secs_f32(duration_seconds));
    drop(stream);

    if let Some(err) = stream_err.lock().ok().and_then(|g| g.clone()) {
        return Err(format!("Microphone capture error: {err}"));
    }
    let samples = captured
        .lock()
        .map(|g| g.clone())
        .map_err(|_| "Audio capture buffer poisoned".to_string())?;
    Ok((samples, sample_rate))
}

fn finalize_wav_take(raw: &[f32], rate: u32, filename: &str) -> Result<RecordedTakeResult, String> {
    let safe_name = crate::downloads::sanitize_suggested_filename(filename);
    let safe_wav = if safe_name.to_ascii_lowercase().ends_with(".wav") {
        safe_name
    } else {
        format!("{safe_name}.wav")
    };
    let resampled = resample_mono(raw, rate, TARGET_SAMPLE_RATE);
    if resampled.is_empty() {
        return Err("No audio samples were captured".to_string());
    }
    let pcm = f32_to_pcm16(&resampled);
    let wav_bytes = encode_mono_pcm16_wav(&pcm, TARGET_SAMPLE_RATE)?;
    let sha256 = hex::encode(Sha256::digest(&wav_bytes));
    let wav_base64 = base64::engine::general_purpose::STANDARD.encode(&wav_bytes);
    Ok(RecordedTakeResult {
        schema_version: "lixity-audio-take/1",
        filename: safe_wav,
        wav_base64,
        sha256,
        channels: 1,
        sample_rate_hz: TARGET_SAMPLE_RATE,
        sample_width_bits: 16,
        frames: pcm.len(),
        duration_seconds: pcm.len() as f64 / TARGET_SAMPLE_RATE as f64,
    })
}

pub fn calibrate_microphone(
    device_name: Option<&str>,
    duration_seconds: f32,
) -> Result<CalibrationReport, String> {
    let (raw, rate) = record_mono_f32(device_name, duration_seconds)?;
    let pcm = f32_to_pcm16(&raw);
    Ok(analyze_pcm16_signal(&pcm, rate))
}

pub fn record_wav_take(
    device_name: Option<&str>,
    duration_seconds: f32,
    filename: &str,
) -> Result<RecordedTakeResult, String> {
    let (raw, rate) = record_mono_f32(device_name, duration_seconds)?;
    finalize_wav_take(&raw, rate, filename)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn calibration_verdict_matches_lixity_band() {
        // Peak around -10 dBFS (~10362 in 16-bit signed PCM) -> calibrated
        let calibrated = vec![10_362_i16; 24_000];
        let report = analyze_pcm16_signal(&calibrated, 24_000);
        assert_eq!(report.verdict, "calibrated");
        assert_eq!(report.clipping_samples, 0);

        // Clipping signal -> too_hot
        let hot = vec![32_700_i16; 24_000];
        assert_eq!(analyze_pcm16_signal(&hot, 24_000).verdict, "too_hot");

        // Quiet signal -> too_quiet
        let quiet = vec![500_i16; 24_000];
        assert_eq!(analyze_pcm16_signal(&quiet, 24_000).verdict, "too_quiet");
    }

    #[test]
    fn wav_encoding_and_resampling_produce_valid_riff() {
        let input = vec![0.25_f32; 48_000];
        let resampled = resample_mono(&input, 48_000, 24_000);
        assert_eq!(resampled.len(), 24_000);
        let pcm = f32_to_pcm16(&resampled);
        let wav = encode_mono_pcm16_wav(&pcm, 24_000).unwrap();
        assert_eq!(&wav[0..4], b"RIFF");
        assert_eq!(&wav[8..12], b"WAVE");
    }

    #[test]
    fn finalize_wav_take_appends_extension_and_hashes_output() {
        let input = vec![0.15_f32; 48_000];
        let take = finalize_wav_take(&input, 48_000, "author-voice").unwrap();
        assert_eq!(take.filename, "author-voice.wav");
        assert_eq!(take.sample_rate_hz, TARGET_SAMPLE_RATE);
        assert_eq!(take.channels, 1);
        assert_eq!(take.frames, 24_000);
        assert_eq!(take.sha256.len(), 64);
    }

    #[test]
    fn interactive_recorder_idle_status_and_stop_guard() {
        let recorder = InteractiveRecorder::default();
        let st = recorder.status("main");
        assert!(!st.recording);
        assert!(!st.auto_stopped);
        assert!(recorder.stop("main").is_err());
    }

    fn test_capture(started_at: Option<Instant>) -> ActiveCapture {
        let stop_flag = Arc::new(AtomicBool::new(false));
        let capture_stop = Arc::clone(&stop_flag);
        ActiveCapture {
            window: "recording-window".to_string(),
            stop_flag,
            auto_stopped: Arc::new(AtomicBool::new(false)),
            live_peak_bits: Arc::new(AtomicU32::new(0)),
            live_rms_bits: Arc::new(AtomicU32::new(0)),
            started_at,
            filename: "synthetic.wav".to_string(),
            join_handle: thread::spawn(move || {
                while !capture_stop.load(Ordering::Relaxed) {
                    thread::park_timeout(Duration::from_millis(1));
                }
                Ok((vec![0.25; 240], TARGET_SAMPLE_RATE))
            }),
        }
    }

    #[test]
    fn another_window_cannot_inspect_stop_or_cancel_a_take() {
        let capture = test_capture(Some(Instant::now()));
        let stopped = Arc::clone(&capture.stop_flag);
        let recorder = InteractiveRecorder {
            active: Mutex::new(Some(capture)),
        };
        assert_eq!(recorder.status("other"), RecordingLiveStatus::default());
        assert!(recorder.stop("other").is_err());
        recorder.cancel("other");
        assert!(recorder.status("recording-window").recording);
        assert!(!stopped.load(Ordering::SeqCst));

        let take = recorder.stop("recording-window").unwrap();
        assert_eq!(take.frames, 240);
        assert!(stopped.load(Ordering::SeqCst));
        assert!(!recorder.owns_capture("recording-window"));
    }

    #[test]
    fn closing_the_recording_window_signals_even_a_pending_take() {
        let capture = test_capture(None);
        let stopped = Arc::clone(&capture.stop_flag);
        let recorder = InteractiveRecorder {
            active: Mutex::new(Some(capture)),
        };
        assert!(recorder.owns_capture("recording-window"));
        assert!(!recorder.status("recording-window").recording);
        recorder.discard_window("other");
        assert!(!stopped.load(Ordering::SeqCst));
        recorder.discard_window("recording-window");
        assert!(stopped.load(Ordering::SeqCst));
        assert!(!recorder.owns_capture("recording-window"));
    }
}
