from __future__ import annotations

import io
import wave
from pathlib import Path

import requests

from voice.models import AudioCapture
from voice.stt import SttService


ROOT = Path(__file__).resolve().parents[2]
CAPTURE = AudioCapture(b"\x01\x00" * 16000, 16000, 2, 1000, True)


def test_runtime_and_electron_forward_all_stt_settings():
    runtime_script = (ROOT / "scripts" / "prepare-runtime-env.mjs").read_text(encoding="utf-8")
    main_js = (ROOT / "src" / "main" / "main.js").read_text(encoding="utf-8")
    for name in ("CEASER_STT_PROVIDER", "CEASER_STT_LANGUAGE", "CEASER_STT_GOOGLE_FALLBACK", "CEASER_STT_DEEPGRAM_FALLBACK", "CEASER_DEEPGRAM_STT_MODE"):
        assert name in runtime_script
        assert name in main_js
    assert 'CEASER_STT_PROVIDER: value("CEASER_STT_PROVIDER", "google")' in runtime_script


def test_google_is_primary_and_deepgram_is_fallback(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "safe-test-key")
    monkeypatch.setenv("CEASER_STT_DEEPGRAM_FALLBACK", "true")
    stt = SttService("google")
    calls = []
    monkeypatch.setattr(stt, "_google", lambda _capture: calls.append("google") or (_ for _ in ()).throw(RuntimeError("unavailable")))
    monkeypatch.setattr(stt, "_deepgram", lambda _capture: calls.append("deepgram") or "fallback transcript")

    result = stt.transcribe(CAPTURE)

    assert calls == ["google", "deepgram"]
    assert result.provider == "deepgram"
    assert result.transcript == "fallback transcript"


def test_deepgram_is_primary_and_falls_back_only_when_enabled(monkeypatch):
    monkeypatch.setenv("CEASER_STT_GOOGLE_FALLBACK", "true")
    stt = SttService("deepgram")
    calls = []
    monkeypatch.setattr(stt, "_deepgram", lambda _capture: calls.append("deepgram") or (_ for _ in ()).throw(requests.Timeout()))
    monkeypatch.setattr(stt, "_google", lambda _capture: calls.append("google") or "fallback transcript")

    result = stt.transcribe(CAPTURE)

    assert calls == ["deepgram", "google"]
    assert result.provider == "google"
    assert result.transcript == "fallback transcript"


def test_deepgram_failure_does_not_call_google_when_disabled(monkeypatch):
    monkeypatch.setenv("CEASER_STT_GOOGLE_FALLBACK", "false")
    stt = SttService("deepgram")
    calls = []
    monkeypatch.setattr(stt, "_deepgram", lambda _capture: calls.append("deepgram") or (_ for _ in ()).throw(requests.ConnectionError()))
    monkeypatch.setattr(stt, "_google", lambda _capture: calls.append("google") or "should not run")

    result = stt.transcribe(CAPTURE)

    assert calls == ["deepgram"]
    assert result.provider == "deepgram"
    assert result.metadata["errors"] == ["deepgram:network_error"]


def test_deepgram_wav_is_mono_16khz_pcm16():
    wav_bytes = SttService("deepgram")._wav_bytes(CAPTURE)
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        assert wav.getframerate() == 16000
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2


def test_deepgram_errors_are_safe_and_redacted(monkeypatch, capsys):
    secret = "do-not-log-this-key"
    monkeypatch.setenv("DEEPGRAM_API_KEY", secret)
    monkeypatch.setenv("CEASER_STT_GOOGLE_FALLBACK", "false")
    stt = SttService("deepgram")
    monkeypatch.setattr(stt, "_deepgram", lambda _capture: (_ for _ in ()).throw(requests.Timeout(secret)))

    result = stt.transcribe(CAPTURE)
    output = capsys.readouterr().err

    assert result.metadata["errors"] == ["deepgram:timeout"]
    assert "category=timeout" in output
    assert secret not in output


def test_requests_is_packaged_requirement():
    requirements = (ROOT / "python_companion" / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert "requests" in {line.strip().lower() for line in requirements}
