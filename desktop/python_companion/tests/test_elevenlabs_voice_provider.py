from __future__ import annotations

import os
import struct
from unittest.mock import Mock, patch

import pytest

from voice.elevenlabs_provider import ElevenLabsError, ElevenLabsVoiceProvider
from voice.models import AudioCapture
from voice.stt import SttService


def capture() -> AudioCapture:
    return AudioCapture(
        pcm=struct.pack("<" + "h" * 320, *([100] * 320)),
        sample_rate=16000,
        sample_width=2,
        duration_ms=20,
        speech_detected=True,
    )


def test_elevenlabs_stt_is_selected_and_receives_wav(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret-value")
    service = SttService(provider="elevenlabs")
    response = Mock(ok=True, status_code=200)
    response.json.return_value = {"text": "open calculator", "language_code": "en"}
    with patch("voice.elevenlabs_provider.requests.post", return_value=response) as post:
        result = service.transcribe(capture())
    assert result.provider == "elevenlabs"
    assert result.transcript == "open calculator"
    uploaded = post.call_args.kwargs["files"]["file"][1]
    assert uploaded[:4] == b"RIFF"
    assert uploaded[8:12] == b"WAVE"


def test_missing_key_falls_back_without_exposing_secret(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("CEASER_STT_GOOGLE_FALLBACK", "true")
    service = SttService(provider="elevenlabs")
    with patch.object(service, "_google", return_value="fallback works") as google:
        result = service.transcribe(capture(), quiet_failures=True)
    assert result.provider == "google"
    assert result.transcript == "fallback works"
    google.assert_called_once()


def test_fallback_disabled_never_calls_google(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("CEASER_STT_GOOGLE_FALLBACK", "false")
    service = SttService(provider="elevenlabs")
    with patch.object(service, "_google") as google:
        result = service.transcribe(capture(), quiet_failures=True)
    assert result.error_code == "stt_failed"
    assert result.metadata["errors"] == ["elevenlabs:missing_key"]
    google.assert_not_called()


def test_streaming_tts_and_safe_auth_category(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "do-not-log-this")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "voice-id")
    provider = ElevenLabsVoiceProvider()
    response = Mock(ok=True, status_code=200)
    response.iter_content.return_value = [b"audio", b"-bytes"]
    with patch("voice.elevenlabs_provider.requests.post", return_value=response) as post:
        speech = provider.synthesize("Hello")
    assert speech.audio == b"audio-bytes"
    assert post.call_args.kwargs["stream"] is True
    assert "/stream" in post.call_args.args[0]

    denied = Mock(ok=False, status_code=401)
    with patch("voice.elevenlabs_provider.requests.post", return_value=denied):
        with pytest.raises(ElevenLabsError) as error:
            provider.synthesize("Hello")
    assert error.value.category == "authentication_failed"
    assert "do-not-log-this" not in str(error.value)
