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
use std::sync::{Arc, Mutex};
use std::time::Duration;

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

    let captured: Arc<Mutex<Vec<f32>>> = Arc::new(Mutex::new(Vec::with_capacity(
        (sample_rate as f32 * duration_seconds) as usize,
    )));
    let capture_clone = Arc::clone(&captured);
    let stream_err: Arc<Mutex<Option<String>>> = Arc::new(Mutex::new(None));
    let err_clone = Arc::clone(&stream_err);
    let err_fn = move |err: cpal::StreamError| {
        if let Ok(mut guard) = err_clone.lock() {
            *guard = Some(err.to_string());
        }
    };

    let stream = match sample_format {
        cpal::SampleFormat::F32 => device.build_input_stream(
            &config,
            move |data: &[f32], _| {
                if let Ok(mut out) = capture_clone.lock() {
                    for frame in data.chunks(channels) {
                        out.push(frame[0]);
                    }
                }
            },
            err_fn,
            None,
        ),
        cpal::SampleFormat::I16 => device.build_input_stream(
            &config,
            move |data: &[i16], _| {
                if let Ok(mut out) = capture_clone.lock() {
                    for frame in data.chunks(channels) {
                        out.push(frame[0] as f32 / 32768.0);
                    }
                }
            },
            err_fn,
            None,
        ),
        cpal::SampleFormat::U16 => device.build_input_stream(
            &config,
            move |data: &[u16], _| {
                if let Ok(mut out) = capture_clone.lock() {
                    for frame in data.chunks(channels) {
                        out.push((frame[0] as f32 - 32768.0) / 32768.0);
                    }
                }
            },
            err_fn,
            None,
        ),
        other => return Err(format!("Unsupported microphone sample format: {other:?}")),
    }
    .map_err(|e| format!("Unable to open microphone stream: {e}"))?;

    stream
        .play()
        .map_err(|e| format!("Failed starting microphone stream: {e}"))?;
    std::thread::sleep(Duration::from_secs_f32(duration_seconds));
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
    let safe_name = crate::downloads::sanitize_suggested_filename(filename);
    let safe_wav = if safe_name.to_ascii_lowercase().ends_with(".wav") {
        safe_name
    } else {
        format!("{safe_name}.wav")
    };
    let (raw, rate) = record_mono_f32(device_name, duration_seconds)?;
    let resampled = resample_mono(&raw, rate, TARGET_SAMPLE_RATE);
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
}
