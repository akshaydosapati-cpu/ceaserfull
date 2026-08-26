from __future__ import annotations

import io
import os
import time
import wave
from dataclasses import dataclass

import requests

from voice.models import AudioCapture


class ElevenLabsError(RuntimeError):
    """Credential-safe ElevenLabs failure used by voice fallback logic."""

    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


@dataclass(frozen=True)
class SynthesizedSpeech:
    audio: bytes
    mime_type: str
    first_audio_ms: int
    total_ms: int


class ElevenLabsVoiceProvider:
    def __init__(self) -> None:
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
        self.base_url = os.getenv("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io").rstrip("/")
        self.stt_model = os.getenv("ELEVENLABS_STT_MODEL", "scribe_v2")
        self.tts_model = os.getenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5")
        self.timeout = max(3.0, float(os.getenv("ELEVENLABS_TIMEOUT_SECONDS", "18")))

    def transcribe(self, capture: AudioCapture) -> tuple[str, dict]:
        self._require_key()
        started = time.perf_counter()
        try:
            response = requests.post(
                f"{self.base_url}/v1/speech-to-text",
                headers={"xi-api-key": self.api_key},
                files={"file": ("command.wav", self._wav_bytes(capture), "audio/wav")},
                data={"model_id": self.stt_model, "tag_audio_events": "false"},
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise ElevenLabsError("timeout") from exc
        except requests.ConnectionError as exc:
            raise ElevenLabsError("network_error") from exc
        except requests.RequestException as exc:
            raise ElevenLabsError("http_error") from exc
        self._raise_for_status(response)
        try:
            payload = response.json()
            text = str(payload.get("text") or "").strip()
        except (ValueError, TypeError, AttributeError) as exc:
            raise ElevenLabsError("invalid_response") from exc
        if not text:
            raise ElevenLabsError("no_transcript")
        return text, {
            "detected_language": str(payload.get("language_code") or payload.get("language") or ""),
            "provider_latency_ms": int((time.perf_counter() - started) * 1000),
        }

    def synthesize(self, text: str) -> SynthesizedSpeech:
        self._require_key()
        if not self.voice_id:
            raise ElevenLabsError("missing_voice_id")
        started = time.perf_counter()
        first_audio_ms = 0
        chunks: list[bytes] = []
        try:
            response = requests.post(
                f"{self.base_url}/v1/text-to-speech/{self.voice_id}/stream",
                params={"output_format": "mp3_22050_32"},
                headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
                json={"text": text, "model_id": self.tts_model},
                stream=True,
                timeout=self.timeout,
            )
            self._raise_for_status(response)
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                if not chunks:
                    first_audio_ms = int((time.perf_counter() - started) * 1000)
                chunks.append(chunk)
        except ElevenLabsError:
            raise
        except requests.Timeout as exc:
            raise ElevenLabsError("timeout") from exc
        except requests.ConnectionError as exc:
            raise ElevenLabsError("network_error") from exc
        except requests.RequestException as exc:
            raise ElevenLabsError("http_error") from exc
        audio = b"".join(chunks)
        if not audio:
            raise ElevenLabsError("invalid_response")
        return SynthesizedSpeech(
            audio=audio,
            mime_type="audio/mpeg",
            first_audio_ms=first_audio_ms,
            total_ms=int((time.perf_counter() - started) * 1000),
        )

    def _require_key(self) -> None:
        if not self.api_key:
            raise ElevenLabsError("missing_key")

    @staticmethod
    def _raise_for_status(response) -> None:
        if response.ok:
            return
        category = {
            401: "authentication_failed",
            403: "permission_denied",
            429: "rate_limited",
        }.get(response.status_code, "http_error")
        raise ElevenLabsError(category)

    @staticmethod
    def _wav_bytes(capture: AudioCapture) -> bytes:
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(capture.sample_width)
            wav.setframerate(capture.sample_rate)
            wav.writeframes(capture.pcm)
        return output.getvalue()
