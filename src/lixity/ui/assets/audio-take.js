/** Portable local PCM takes; no uploads, inferred transcripts or audio conversion. */
(function() {
  "use strict";
  var schema = "lixity-audio-take/1", maximumBytes = 64 * 1024 * 1024;
  function fail(code) { var error = new Error("Invalid audio take: " + code); error.code = code; throw error; }
  function keys(value, names) {
    return value && typeof value === "object" && !Array.isArray(value) &&
      Object.keys(value).length === names.length && names.every(function(key) { return Object.hasOwn(value, key); });
  }
  function filename(value) {
    if (typeof value !== "string" || value.length > 180 || !value.trim() || value !== value.trim() ||
        /[\\/\x00-\x1f\x7f]/.test(value) || !/\.wav$/i.test(value)) fail("filename");
    return value;
  }
  function transcript(text, status) {
    if (typeof text !== "string" || text.length > 100000 || /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(text) ||
        !["missing", "draft", "confirmed"].includes(status) || status === "confirmed" && !text.trim() ||
        status === "missing" && text.trim()) fail("transcript");
    return {text:text, status:status};
  }
  async function inspect(blob) {
    if (!(blob instanceof Blob) || !blob.size || blob.size > maximumBytes) fail("size");
    var buffer = await blob.arrayBuffer(), data = new DataView(buffer);
    function word(offset) { return String.fromCharCode.apply(null, new Uint8Array(buffer, offset, 4)); }
    if (buffer.byteLength < 44 || word(0) !== "RIFF" || word(8) !== "WAVE" || data.getUint32(4, true) + 8 !== buffer.byteLength) fail("format");
    var format = null, bytes = null, offset = 12;
    while (offset + 8 <= buffer.byteLength) {
      var kind = word(offset), size = data.getUint32(offset + 4, true), start = offset + 8;
      if (start + size > buffer.byteLength) fail("format");
      if (kind === "fmt ") {
        if (format || size < 16 || data.getUint16(start, true) !== 1) fail("format");
        format = {format:"wav-pcm", channels:data.getUint16(start + 2, true), sample_rate_hz:data.getUint32(start + 4, true),
          sample_width_bits:data.getUint16(start + 14, true)};
        if (![1, 2].includes(format.channels) || format.sample_width_bits !== 16 ||
            format.sample_rate_hz < 8000 || format.sample_rate_hz > 192000 ||
            data.getUint16(start + 12, true) !== format.channels * 2 ||
            data.getUint32(start + 8, true) !== format.sample_rate_hz * format.channels * 2) fail("format");
      } else if (kind === "data") {
        if (!format || bytes !== null) fail("format"); bytes = size;
      }
      offset = start + size + size % 2;
    }
    if (offset !== buffer.byteLength || !format || !bytes || bytes % (format.channels * 2)) fail("format");
    format.frames = bytes / (format.channels * 2);
    format.duration_seconds = format.frames / format.sample_rate_hz;
    if (!window.crypto || !window.crypto.subtle) fail("hash");
    var digest = await window.crypto.subtle.digest("SHA-256", buffer);
    format.sha256 = Array.from(new Uint8Array(digest), function(value) { return value.toString(16).padStart(2, "0"); }).join("");
    return format;
  }
  function take(blob, metadata) {
    return {blob:blob, transcript:metadata.transcript.text, transcript_status:metadata.transcript.status, metadata:metadata};
  }
  async function create(blob, options) {
    options = options || {};
    var name = filename(options.filename || "recording.wav"), text = options.transcript || "";
    var status = options.transcript_status || (text.trim() ? "draft" : "missing");
    var words = transcript(text, status), audio = await inspect(blob);
    return take(blob, {schema_version:schema, audio:Object.assign({filename:name}, audio), transcript:words});
  }
  async function validate(value) {
    var metadata = value && value.metadata;
    if (!keys(metadata, ["schema_version", "audio", "transcript"]) || metadata.schema_version !== schema ||
        !keys(metadata.audio, ["filename", "sha256", "format", "channels", "sample_rate_hz", "sample_width_bits", "frames", "duration_seconds"]) ||
        !keys(metadata.transcript, ["text", "status"])) fail("schema");
    filename(metadata.audio.filename);
    var words = transcript(metadata.transcript.text, metadata.transcript.status);
    if (value.transcript !== words.text || value.transcript_status !== words.status) fail("transcript");
    var actual = await inspect(value.blob);
    if (actual.sha256 !== metadata.audio.sha256) fail("hash");
    if (Object.keys(actual).some(function(key) { return actual[key] !== metadata.audio[key]; })) fail("format");
    return take(value.blob, {schema_version:schema, audio:Object.assign({filename:metadata.audio.filename}, actual), transcript:words});
  }
  async function importFiles(wav, json) {
    if (!(wav instanceof File) || !(json instanceof Blob) || json.size > 1024 * 1024) fail("size");
    var metadata;
    try { metadata = JSON.parse(await json.text()); } catch (_) { fail("schema"); }
    var value = take(wav, {transcript:metadata && metadata.transcript || {}}); value.metadata = metadata;
    var verified = await validate(value);
    if (wav.name !== verified.metadata.audio.filename) fail("filename");
    return verified;
  }
  function withTranscript(value, text, status) {
    return take(value.blob, Object.assign({}, value.metadata, {transcript:transcript(text, status)}));
  }
  function referenceEligibility(value) {
    var audio = value.metadata.audio;
    var reason = audio.channels !== 1 || audio.sample_rate_hz !== 24000 || audio.sample_width_bits !== 16 ? "format" :
      audio.duration_seconds < 1 || audio.duration_seconds > 30 ? "duration" :
      !value.transcript.trim() ? "missing" : value.transcript.length > 2000 ? "transcript" :
      value.transcript_status !== "confirmed" ? "confirmation" : "";
    return {eligible:!reason, reason:reason};
  }
  async function download(value, kind) {
    var verified = await validate(value);
    if (!["wav", "json"].includes(kind)) fail("format");
    var blob = kind === "wav" ? verified.blob : new Blob([JSON.stringify(verified.metadata, null, 2) + "\n"], {type:"application/json"});
    var url = URL.createObjectURL(blob), link = document.createElement("a");
    link.href = url; link.download = kind === "wav" ? verified.metadata.audio.filename : verified.metadata.audio.filename.replace(/\.wav$/i, ".json");
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
  }
  function encodeWav(chunks, totalSamples, sampleRate) {
    if (!Number.isInteger(totalSamples) || totalSamples < 1 || 44 + totalSamples * 2 > maximumBytes ||
        !Number.isInteger(sampleRate) || sampleRate < 8000 || sampleRate > 192000 ||
        chunks.reduce(function(sum, chunk) { return sum + chunk.length; }, 0) !== totalSamples) fail("size");
    var buffer = new ArrayBuffer(44 + totalSamples * 2), view = new DataView(buffer);
    function string(offset, value) { for (var i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i)); }
    string(0, "RIFF"); view.setUint32(4, 36 + totalSamples * 2, true); string(8, "WAVE"); string(12, "fmt ");
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
    string(36, "data"); view.setUint32(40, totalSamples * 2, true);
    var offset = 44;
    chunks.forEach(function(chunk) { for (var i = 0; i < chunk.length; i++) {
      if (!Number.isFinite(chunk[i])) fail("format");
      var sample = Math.max(-1, Math.min(1, chunk[i]));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true); offset += 2;
    }});
    return new Uint8Array(buffer);
  }
  window.LixityAudioTake = Object.freeze({create:create, validate:validate, importFiles:importFiles,
    withTranscript:withTranscript, referenceEligibility:referenceEligibility, download:download, encodeWav:encodeWav, maximumBytes:maximumBytes});
})();
