//! Cross-platform 24 kHz mono 16-bit PCM capture & level calibration via `cpal` + `hound`.
//!
//! Delivers identical microphone recording and `-13.0` to `-7.0 dBFS` signal checks
//! across macOS (CoreAudio), Windows (WASAPI), and Linux (PipeWire/ALSA), matching
//! the exact calibration rubric of `src/lixity/speech_record.py` and the portable
//! `lixity-audio-take/1` WAV+SHA-256 metadata contract.

use base64::Engine;
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::Sample;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::io::Cursor;
use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering};
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

pub const TARGET_SAMPLE_RATE: u32 = 24_000;
const MIN_DURATION_SEC: f32 = 1.0;
const MAX_DURATION_SEC: f32 = 60.0;
const MAX_CALIBRATION_DURATION_SEC: f32 = 30.0;
const NO_SIGNAL_DBFS: f64 = -120.0;
static CAPTURE_COUNTER: AtomicU64 = AtomicU64::new(1);

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
    pub signal_present: bool,
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
    pub signal_present: bool,
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
            signal_present: false,
            peak_dbfs: NO_SIGNAL_DBFS,
            rms_dbfs: NO_SIGNAL_DBFS,
            auto_stopped: false,
            max_duration_seconds: MAX_DURATION_SEC,
        }
    }
}

type CaptureResult = Result<(Vec<f32>, u32), String>;

struct CaptureStartError {
    reason: &'static str,
    message: String,
}

#[derive(Clone, Copy)]
struct CaptureLog {
    id: u64,
    write: fn(&str, &str),
}

impl CaptureLog {
    fn event(self, stage: &'static str, reason: &'static str, duration_ms: Option<u64>) {
        // Only fixed labels and bounded numeric values enter the sidecar log.
        let mut line = format!(
            "event=desktop_audio_capture capture_id={} stage={stage}",
            self.id
        );
        if !reason.is_empty() {
            line.push_str(&format!(" reason={reason}"));
        }
        if let Some(duration_ms) = duration_ms {
            line.push_str(&format!(" duration_ms={duration_ms}"));
        }
        (self.write)(if stage == "failed" { "WARN" } else { "INFO" }, &line);
    }
}

struct ActiveCapture {
    log: CaptureLog,
    window: String,
    max_duration_seconds: f32,
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
pub struct InteractiveRecorder {
    active: Mutex<Option<ActiveCapture>>,
    log: fn(&str, &str),
}

impl Default for InteractiveRecorder {
    fn default() -> Self {
        Self {
            active: Mutex::new(None),
            log: crate::sidecar::log_desktop_event,
        }
    }
}

impl InteractiveRecorder {
    pub fn start(
        &self,
        window: String,
        device_name: Option<String>,
        filename: String,
        max_duration_seconds: Option<u32>,
    ) -> Result<(), String> {
        let log = CaptureLog {
            id: CAPTURE_COUNTER.fetch_add(1, Ordering::Relaxed),
            write: self.log,
        };
        log.event("requested", "", None);
        let max_duration_seconds =
            max_duration_seconds.map_or(MAX_DURATION_SEC, |seconds| seconds as f32);
        validate_duration(max_duration_seconds, MAX_DURATION_SEC).inspect_err(|_| {
            log.event("failed", "invalid_duration", None);
        })?;
        let mut guard = self.active.lock().map_err(|_| {
            log.event("failed", "recorder_state", None);
            "Recorder state lock poisoned".to_string()
        })?;
        if guard.is_some() {
            log.event("failed", "recording_already_active", None);
            return Err("A recording session is already running".to_string());
        }

        let stop_flag = Arc::new(AtomicBool::new(false));
        let auto_stopped = Arc::new(AtomicBool::new(false));
        let live_peak_bits = Arc::new(AtomicU32::new(0.0_f32.to_bits()));
        let live_rms_bits = Arc::new(AtomicU32::new(0.0_f32.to_bits()));
        let (ready_tx, ready_rx) = mpsc::sync_channel::<Result<(), CaptureStartError>>(1);

        let thread_stop = Arc::clone(&stop_flag);
        let thread_auto = Arc::clone(&auto_stopped);
        let thread_levels = (Arc::clone(&live_peak_bits), Arc::clone(&live_rms_bits));

        let join_handle = thread::spawn(move || {
            run_capture_loop(
                device_name.as_deref(),
                max_duration_seconds,
                thread_stop,
                thread_auto,
                thread_levels,
                ready_tx,
                log,
            )
        });

        *guard = Some(ActiveCapture {
            log,
            window,
            max_duration_seconds,
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
            .unwrap_or_else(|error| {
                Err(match error {
                    mpsc::RecvTimeoutError::Timeout => CaptureStartError {
                        reason: "startup_timeout",
                        message: "Timed out initializing microphone stream".to_string(),
                    },
                    mpsc::RecvTimeoutError::Disconnected => CaptureStartError {
                        reason: "capture_thread",
                        message: "Microphone capture stopped before it was ready".to_string(),
                    },
                })
            });
        let same_session = |active: &ActiveCapture| Arc::ptr_eq(&active.stop_flag, &stop_flag);
        if let Err(error) = result {
            if let Ok(Some(active)) = self.take_matching(same_session) {
                log.event("failed", error.reason, None);
                let _ = active.join_handle.join();
            }
            return Err(error.message);
        }
        let mut guard = self
            .active
            .lock()
            .map_err(|_| "Recorder state lock poisoned".to_string())?;
        if let Some(active) = guard.as_mut().filter(|active| same_session(active)) {
            active.started_at = Some(Instant::now());
            log.event("started", "", None);
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
            elapsed_seconds: round2(
                started_at
                    .elapsed()
                    .as_secs_f64()
                    .min(f64::from(active.max_duration_seconds)),
            ),
            signal_present: peak_amp > 0.0,
            peak_dbfs: round1(dbfs(peak_amp * 32_768.0)),
            rms_dbfs: round1(dbfs(rms_amp * 32_768.0)),
            auto_stopped: auto,
            max_duration_seconds: active.max_duration_seconds,
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
        let log = session.log;
        let (raw, rate) = session
            .join_handle
            .join()
            .map_err(|_| {
                log.event("failed", "capture_thread", None);
                "Audio capture thread panicked".to_string()
            })??;
        let take = finalize_wav_take(&raw, rate, &session.filename).inspect_err(|_| {
            let reason = if raw.is_empty() {
                "empty_capture"
            } else {
                "wav_encoding"
            };
            log.event("failed", reason, None);
        })?;
        let duration_ms = (take.duration_seconds * 1000.0)
            .round()
            .clamp(0.0, 60_000.0) as u64;
        let reason = if session.auto_stopped.load(Ordering::Relaxed) {
            "duration_limit"
        } else {
            "stop_requested"
        };
        log.event("ready", reason, Some(duration_ms));
        Ok(take)
    }

    fn cancel_matching(&self, matches: impl FnOnce(&ActiveCapture) -> bool, reason: &'static str) {
        if let Ok(Some(active)) = self.take_matching(matches) {
            active.log.event("discarded", reason, None);
            let _ = active.join_handle.join();
        }
    }

    pub fn cancel(&self, window: &str) {
        self.cancel_matching(|active| active.window == window, "cancel_requested");
    }

    pub fn discard_window(&self, window: &str) {
        // Window events run on the GUI thread. Signal shutdown now and let
        // the capture thread finish without blocking its former window.
        if let Ok(Some(active)) = self.take_matching(|active| active.window == window) {
            active.log.event("discarded", "window_closed", None);
        }
    }

    pub fn cancel_all(&self) {
        self.cancel_matching(|_| true, "app_exit");
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
    if value == 0.0 {
        NO_SIGNAL_DBFS
    } else {
        20.0 * (value.max(1.0) / 32768.0).log10()
    }
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
            signal_present: false,
            peak_dbfs: NO_SIGNAL_DBFS,
            clipping_samples: 0,
            noise_floor_dbfs: NO_SIGNAL_DBFS,
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
        .unwrap_or(NO_SIGNAL_DBFS);
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
        signal_present: peak_val > 0.0,
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
    if params.channels == 0 {
        return Err("Microphone configuration has no input channels".to_string());
    }
    use cpal::SampleFormat::*;
    match params.sample_format {
        I8 => build_pcm_stream::<i8>(device, params),
        I16 => build_pcm_stream::<i16>(device, params),
        I32 => build_pcm_stream::<i32>(device, params),
        I64 => build_pcm_stream::<i64>(device, params),
        U8 => build_pcm_stream::<u8>(device, params),
        U16 => build_pcm_stream::<u16>(device, params),
        U32 => build_pcm_stream::<u32>(device, params),
        U64 => build_pcm_stream::<u64>(device, params),
        F32 => build_pcm_stream::<f32>(device, params),
        F64 => build_pcm_stream::<f64>(device, params),
        other => Err(format!("Unsupported microphone sample format: {other:?}")),
    }
}

fn append_first_channel<T: Sample>(
    output: &mut Vec<f32>,
    input: &[T],
    channels: usize,
    limit: usize,
) where
    f32: cpal::FromSample<T>,
{
    let remaining = limit.saturating_sub(output.len());
    output.extend(
        input
            .iter()
            .step_by(channels)
            .take(remaining)
            .map(|&sample| f32::from_sample(sample)),
    );
}

fn build_pcm_stream<T: cpal::SizedSample>(
    device: &cpal::Device,
    params: CaptureStreamParams,
) -> Result<cpal::Stream, String>
where
    f32: cpal::FromSample<T>,
{
    let CaptureStreamParams {
        channels,
        config,
        max_samples,
        captured,
        auto_stopped,
        peak_bits,
        rms_bits,
        stream_err,
        ..
    } = params;
    device
        .build_input_stream(
            &config,
            move |data: &[T], _| {
                if let Ok(mut out) = captured.lock() {
                    let start = out.len();
                    append_first_channel(&mut out, data, channels, max_samples);
                    update_live_levels(&out[start..], &peak_bits, &rms_bits);
                    if out.len() == max_samples {
                        auto_stopped.store(true, Ordering::Relaxed);
                    }
                }
            },
            move |err: cpal::StreamError| {
                if let Ok(mut guard) = stream_err.lock() {
                    *guard = Some(err.to_string());
                }
            },
            None,
        )
        .map_err(|e| format!("Unable to open microphone stream: {e}"))
}

fn finish_capture(
    stream: cpal::Stream,
    captured: &Mutex<Vec<f32>>,
    stream_err: &Mutex<Option<String>>,
    sample_rate: u32,
) -> CaptureResult {
    drop(stream);
    let failure = stream_err
        .lock()
        .map_err(|_| "Audio capture error state poisoned".to_string())?
        .take();
    if let Some(err) = failure {
        return Err(format!("Microphone capture error: {err}"));
    }
    let mut samples = captured
        .lock()
        .map_err(|_| "Audio capture buffer poisoned".to_string())?;
    Ok((std::mem::take(&mut *samples), sample_rate))
}

fn run_capture_loop(
    device_name: Option<&str>,
    max_duration_seconds: f32,
    stop_flag: Arc<AtomicBool>,
    auto_stopped: Arc<AtomicBool>,
    live_levels: (Arc<AtomicU32>, Arc<AtomicU32>),
    ready_tx: mpsc::SyncSender<Result<(), CaptureStartError>>,
    log: CaptureLog,
) -> Result<(Vec<f32>, u32), String> {
    let start_failed = |reason, message: String| {
        let _ = ready_tx.send(Err(CaptureStartError {
            reason,
            message: message.clone(),
        }));
        Err(message)
    };
    let device = match select_input_device(device_name) {
        Ok(d) => d,
        Err(e) => return start_failed("input_device", e),
    };
    let supported = match device.default_input_config() {
        Ok(cfg) => cfg,
        Err(e) => {
            return start_failed(
                "input_configuration",
                format!("Failed reading microphone configuration: {e}"),
            );
        }
    };
    let sample_rate = supported.sample_rate().0;
    let channels = supported.channels() as usize;
    let sample_format = supported.sample_format();
    let config: cpal::StreamConfig = supported.into();
    let max_samples = capture_frame_limit(sample_rate, max_duration_seconds);

    let captured: Arc<Mutex<Vec<f32>>> = Arc::new(Mutex::new(Vec::with_capacity(
        max_samples.min((sample_rate as usize).saturating_mul(10)),
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
            peak_bits: live_levels.0,
            rms_bits: live_levels.1,
            stream_err: Arc::clone(&stream_err),
        },
    ) {
        Ok(s) => s,
        Err(e) => return start_failed("stream_open", e),
    };

    if stop_flag.load(Ordering::SeqCst) {
        return start_failed("cancel_requested", "Recording was cancelled".to_string());
    }
    if let Err(e) = stream.play() {
        return start_failed(
            "stream_start",
            format!("Failed starting microphone stream: {e}"),
        );
    }
    let _ = ready_tx.send(Ok(()));

    let started = Instant::now();
    let max_dur = Duration::from_secs_f32(max_duration_seconds);
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
    finish_capture(stream, &captured, &stream_err, sample_rate)
        .inspect(|_| {
            if auto_stopped.load(Ordering::Relaxed) {
                log.event("capture_ended", "duration_limit", None);
            }
        })
        .inspect_err(|_| log.event("failed", "stream_error", None))
}

fn capture_frame_limit(sample_rate: u32, duration_seconds: f32) -> usize {
    (f64::from(sample_rate) * f64::from(duration_seconds)) as usize
}

fn validate_duration(seconds: f32, maximum: f32) -> Result<(), String> {
    if !(MIN_DURATION_SEC..=maximum).contains(&seconds) {
        return Err(format!(
            "Recording duration must be between {MIN_DURATION_SEC} and {maximum} seconds"
        ));
    }
    Ok(())
}

fn record_mono_f32(
    device_name: Option<&str>,
    duration_seconds: f32,
    maximum_seconds: f32,
) -> CaptureResult {
    validate_duration(duration_seconds, maximum_seconds)?;
    let device = select_input_device(device_name)?;
    let supported = device
        .default_input_config()
        .map_err(|e| format!("Failed reading microphone configuration: {e}"))?;
    let sample_rate = supported.sample_rate().0;
    let channels = supported.channels() as usize;
    let sample_format = supported.sample_format();
    let config: cpal::StreamConfig = supported.into();
    let max_samples = capture_frame_limit(sample_rate, duration_seconds);

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
    finish_capture(stream, &captured, &stream_err, sample_rate)
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
    let (raw, rate) = record_mono_f32(device_name, duration_seconds, MAX_CALIBRATION_DURATION_SEC)?;
    let pcm = f32_to_pcm16(&raw);
    Ok(analyze_pcm16_signal(&pcm, rate))
}

pub fn record_wav_take(
    device_name: Option<&str>,
    duration_seconds: f32,
    filename: &str,
) -> Result<RecordedTakeResult, String> {
    let (raw, rate) = record_mono_f32(device_name, duration_seconds, MAX_DURATION_SEC)?;
    finalize_wav_take(&raw, rate, filename)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;

    thread_local! {
        static CAPTURE_EVENTS: RefCell<Vec<(String, String)>> = const { RefCell::new(Vec::new()) };
    }

    fn record_capture_event(level: &str, event: &str) {
        CAPTURE_EVENTS.with(|events| {
            events
                .borrow_mut()
                .push((level.to_string(), event.to_string()))
        });
    }

    #[test]
    fn recording_status_and_buffer_share_the_sixty_second_limit() {
        let status = InteractiveRecorder::default().status("synthetic-window");
        assert_eq!(status.max_duration_seconds, 60.0);
        assert_eq!(
            capture_frame_limit(48_000, status.max_duration_seconds),
            2_880_000
        );
        assert_eq!(capture_frame_limit(48_000, 31.5), 1_512_000);
    }

    #[test]
    fn capture_keeps_only_the_first_channel_and_stops_at_the_sample_limit() {
        let mut samples = Vec::new();
        append_first_channel(&mut samples, &[0.25_f32, 1.0, -0.25, 1.0], 2, 5);
        append_first_channel(&mut samples, &[16_384_i16, i16::MAX], 2, 5);
        append_first_channel(&mut samples, &[16_384_u16, u16::MAX], 2, 5);
        append_first_channel(&mut samples, &[1_i32 << 30, i32::MAX, 0, 0], 2, 5);
        append_first_channel(&mut samples, &[1.0_f32, 1.0], 2, 5);
        assert_eq!(samples, [0.25, -0.25, 0.5, -0.5, 0.5]);
    }

    #[test]
    fn calibration_verdict_matches_lixity_band() {
        // Peak around -10 dBFS (~10362 in 16-bit signed PCM) -> calibrated
        let calibrated = vec![10_362_i16; 24_000];
        let report = analyze_pcm16_signal(&calibrated, 24_000);
        assert_eq!(report.verdict, "calibrated");
        assert!(report.signal_present);
        assert_eq!(report.clipping_samples, 0);

        // Clipping signal -> too_hot
        let hot = vec![32_700_i16; 24_000];
        assert_eq!(analyze_pcm16_signal(&hot, 24_000).verdict, "too_hot");

        // Quiet signal -> too_quiet
        let quiet = vec![500_i16; 24_000];
        assert_eq!(analyze_pcm16_signal(&quiet, 24_000).verdict, "too_quiet");

        let silent = vec![0_i16; 24_000];
        let report = analyze_pcm16_signal(&silent, 24_000);
        assert!(!report.signal_present);
        assert_eq!(report.peak_dbfs, -120.0);
        assert_eq!(report.noise_floor_dbfs, -120.0);
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
            log: CaptureLog {
                id: 123,
                write: record_capture_event,
            },
            window: "recording-window".to_string(),
            max_duration_seconds: 37.0,
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
            log: record_capture_event,
        };
        assert_eq!(recorder.status("other"), RecordingLiveStatus::default());
        assert!(recorder.stop("other").is_err());
        recorder.cancel("other");
        let status = recorder.status("recording-window");
        assert!(status.recording);
        assert_eq!(status.max_duration_seconds, 37.0);
        assert_eq!(
            capture_frame_limit(48_000, status.max_duration_seconds),
            1_776_000
        );
        assert!(!stopped.load(Ordering::SeqCst));

        let take = recorder.stop("recording-window").unwrap();
        assert_eq!(take.frames, 240);
        assert_eq!(CAPTURE_EVENTS.with(|events| events.take()), [(
            "INFO".to_string(),
            "event=desktop_audio_capture capture_id=123 stage=ready reason=stop_requested duration_ms=10".to_string(),
        )]);
        assert!(stopped.load(Ordering::SeqCst));
        assert!(!recorder.owns_capture("recording-window"));
    }

    #[test]
    fn invalid_interactive_limits_are_rejected_before_opening_the_device() {
        let recorder = InteractiveRecorder {
            log: record_capture_event,
            ..InteractiveRecorder::default()
        };
        for seconds in [0, 61] {
            let error = recorder
                .start(
                    "synthetic-window".to_string(),
                    None,
                    "synthetic.wav".to_string(),
                    Some(seconds),
                )
                .unwrap_err();
            assert_eq!(error, "Recording duration must be between 1 and 60 seconds");
            assert!(!recorder.owns_capture("synthetic-window"));
            let events = CAPTURE_EVENTS.with(|events| events.take());
            assert_eq!(events.len(), 2);
            let prefix = events[0].1.strip_suffix(" stage=requested").unwrap();
            assert_eq!(events[0].0, "INFO");
            assert_eq!(
                events[1],
                (
                    "WARN".to_string(),
                    format!("{prefix} stage=failed reason=invalid_duration")
                )
            );
            assert!(prefix.starts_with("event=desktop_audio_capture capture_id="));
        }
    }

    #[test]
    fn closing_the_recording_window_signals_even_a_pending_take() {
        let capture = test_capture(None);
        let stopped = Arc::clone(&capture.stop_flag);
        let recorder = InteractiveRecorder {
            active: Mutex::new(Some(capture)),
            log: record_capture_event,
        };
        assert!(recorder.owns_capture("recording-window"));
        assert!(!recorder.status("recording-window").recording);
        recorder.discard_window("other");
        assert!(!stopped.load(Ordering::SeqCst));
        recorder.discard_window("recording-window");
        assert_eq!(
            CAPTURE_EVENTS.with(|events| events.take()),
            [(
                "INFO".to_string(),
                "event=desktop_audio_capture capture_id=123 stage=discarded reason=window_closed"
                    .to_string(),
            )]
        );
        assert!(stopped.load(Ordering::SeqCst));
        assert!(!recorder.owns_capture("recording-window"));
    }
}
