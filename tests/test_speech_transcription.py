"""MLX-Audio transcription stays explicit, bounded and pipeline-compatible."""
from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from lixity.audio_audit import parse_external_transcript
from lixity.cli import main
from lixity.speech import generate_silence_wav
from lixity.speech_transcription import DEFAULT_MODEL, transcribe_audio


@contextmanager
def transcription_server(result):
    records = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            length = int(self.headers["Content-Length"])
            records.append((self.path, self.headers["Content-Type"], self.rfile.read(length)))
            data = (json.dumps({"text": "partial"}) + "\n" + json.dumps(result) + "\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", records
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_transcribe_audio_uses_mlx_endpoint_and_normalizes_parakeet_tokens(tmp_path):
    audio = tmp_path / "chapter.wav"
    audio.write_bytes(generate_silence_wav(0.02))
    result = {
        "schema_version": "untrusted-schema",
        "audio_sha256": "untrusted-digest",
        "model": "untrusted-model",
        "text": "Hallo Welt",
        "language": "de",
        "sentences": [{
            "text": "Hallo Welt",
            "start": 0.0,
            "end": 0.8,
            "tokens": [
                {"text": "Hallo", "start": 0.0, "end": 0.35},
                {"text": "Welt", "start": 0.4, "end": 0.8},
            ],
        }],
    }
    with transcription_server(result) as (url, records):
        transcript = transcribe_audio(audio, base_url=url, language="de")

    assert records[0][0] == "/v1/audio/transcriptions"
    assert records[0][1].startswith("multipart/form-data; boundary=")
    body = records[0][2]
    assert b'name="model"' in body and DEFAULT_MODEL.encode() in body
    assert b'name="response_format"' in body and b"ndjson" in body
    assert b'name="language"' in body and b"de" in body
    assert audio.read_bytes() in body
    assert transcript["schema_version"] == "lixity-audio-transcription/1"
    assert transcript["audio_sha256"] != "untrusted-digest"
    assert transcript["model"] == DEFAULT_MODEL
    assert transcript["text"] == "Hallo Welt"
    assert transcript["words"] == [
        {"word": "Hallo", "start": 0.0, "end": 0.35},
        {"word": "Welt", "start": 0.4, "end": 0.8},
    ]
    words, model = parse_external_transcript(transcript)
    assert words == transcript["words"]
    assert model == DEFAULT_MODEL


def test_transcribe_audio_rejects_symlink_input(tmp_path):
    audio = tmp_path / "input.wav"
    audio.write_bytes(generate_silence_wav(0.01))
    link = tmp_path / "linked.wav"
    link.symlink_to(audio)
    try:
        transcribe_audio(link)
    except ValueError as error:
        assert "symlink" in str(error)
    else:
        raise AssertionError("symlink input was accepted")


def test_audio_transcribe_cli_writes_json_atomically(tmp_path, monkeypatch, capsys):
    audio = tmp_path / "input.wav"
    audio.write_bytes(generate_silence_wav(0.01))
    output = tmp_path / "transcript.json"
    transcript = {
        "schema_version": "lixity-audio-transcription/1",
        "audio_sha256": "a" * 64,
        "model": DEFAULT_MODEL,
        "language": "de",
        "text": "Synthetischer Satz.",
        "words": [],
    }

    def fake_transcribe(path, **kwargs):
        assert path == str(audio)
        assert kwargs == {
            "base_url": "http://127.0.0.1:8000/v1",
            "model": DEFAULT_MODEL,
            "language": "de",
        }
        return transcript

    monkeypatch.setattr("lixity.speech_transcription.transcribe_audio", fake_transcribe)
    assert main(["audio-transcribe", str(audio), "--language", "de", "--output", str(output)]) == 0
    assert json.loads(output.read_text()) == transcript
    assert capsys.readouterr().out == ""
