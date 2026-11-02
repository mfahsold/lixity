# Audio Direction & Listening 🎙️

Listening to prose read aloud is one of the most effective techniques during line editing to catch awkward phrasing, rhythm hitches, and unnatural dialogue cadences.

---

## 1. Local Speech Synthesis

Lixity integrates private, offline speech engines:

* **Offline & Private:** Voice generation runs locally (e.g. via Piper TTS or Thorsten VITS). No manuscript bytes are sent to third parties.
* **OpenAI-Compatible Providers:** Optional support for self-hosted or remote OpenAI-compatible speech services with customizable voices.

---

## 2. Chapter Direction & Delivery

* **Pacing & Pauses:** Automatic insertion of breathing room and scene boundary pauses.
* **Pronunciation Overrides:** Project-wide phonetic rules for fictional names, historical terminology, and dialects (configured in `lixity.toml`).
* **Audio Auditing:** Verify reading duration, clipping, and loudness metrics to prepare audiobook production plans.
