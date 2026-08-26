from __future__ import annotations

import contextlib
import html
import io
import json
import os
import sys
import time
import warnings
import wave

import requests
warnings.filterwarnings(
    "ignore",
    message=".*standard-aifc.*",
    category=DeprecationWarning,
    module="speech_recognition",
)
import speech_recognition as sr

from voice.models import AudioCapture, TranscriptResult
from voice.elevenlabs_provider import ElevenLabsError, ElevenLabsVoiceProvider
from conversation.language_analyzer import LanguageAnalyzer


class DeepgramSttError(RuntimeError):
    """A redacted error category safe for STT diagnostics and fallback decisions."""

    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


class GoogleCloudSttError(RuntimeError):
    """A credential-safe Google Cloud STT failure category."""

    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


class SttService:
    def __init__(self, provider: str = "google", language: str = "en-IN"):
        self.provider = (provider or "google").lower()
        self.language = language
        self.deepgram_key = os.getenv("DEEPGRAM_API_KEY")
        self.deepgram_model = os.getenv("DEEPGRAM_MODEL", "nova-2")
        self.deepgram_language = os.getenv("DEEPGRAM_LANGUAGE", "en")
        self.allow_google_fallback = os.getenv("CEASER_STT_GOOGLE_FALLBACK", "true").lower() in ("1", "true", "yes")
        self.allow_deepgram_fallback = os.getenv("CEASER_STT_DEEPGRAM_FALLBACK", "true").lower() in ("1", "true", "yes")
        self.google_cloud_project = os.getenv("GOOGLE_CLOUD_PROJECT") or None
        self.google_primary_language = os.getenv("CEASER_GOOGLE_STT_PRIMARY_LANGUAGE", "en-IN")
        self.google_alternative_languages = [
            item.strip()
            for item in os.getenv("CEASER_GOOGLE_STT_ALTERNATIVE_LANGUAGES", "te-IN,hi-IN,ta-IN").split(",")
            if item.strip()
        ][:3]
        self.translation_provider = os.getenv("CEASER_TRANSLATION_PROVIDER", "").lower()
        self.translation_target = os.getenv("CEASER_TRANSLATION_TARGET_LANGUAGE", "en")
        self._google_speech_client = None
        self._google_cloud_unavailable_category: str | None = None
        self._google_translate_client = None
        self.language_analyzer = LanguageAnalyzer()
        self.elevenlabs = ElevenLabsVoiceProvider()

    def transcribe(self, capture: AudioCapture, *, quiet_failures: bool = False) -> TranscriptResult:
        if not capture.speech_detected or not capture.pcm:
            return TranscriptResult("", self.provider, duration_ms=capture.duration_ms, error_code=capture.error_code or "no_speech")
        started = time.perf_counter()
        errors: list[str] = []
        providers = [self.provider]
        if self.provider == "deepgram" and self.allow_google_fallback:
            providers.append("google")
        elif self.provider == "elevenlabs" and self.allow_google_fallback:
            providers.append("google")
        elif self.provider == "google_cloud" and self.allow_google_fallback:
            providers.append("google")
        elif self.provider == "google" and self.allow_deepgram_fallback and self.deepgram_key:
            providers.append("deepgram")
        for provider in providers:
            try:
                if provider == "deepgram":
                    text = self._deepgram(capture)
                    provider_metadata = {}
                elif provider == "elevenlabs":
                    text, provider_metadata = self.elevenlabs.transcribe(capture)
                elif provider == "google_cloud":
                    text, provider_metadata = self._google_cloud(capture)
                else:
                    text = self._google(capture)
                    provider_metadata = {}
                original_text = text.strip()
                detected_locale = str(provider_metadata.get("detected_language") or "")
                if provider == "google_cloud" and detected_locale and not detected_locale.lower().startswith("en"):
                    text = self._translate_for_routing(original_text, detected_locale)
                analysis = self.language_analyzer.analyze(original_text)
                metadata = {"audio_ms": capture.duration_ms, "rms_peak": capture.rms_peak, "language_confidence": analysis.confidence, **provider_metadata}
                if text.strip() != original_text:
                    metadata.update({"original_transcript": original_text, "translated_for_routing": True})
                if provider == "google_cloud":
                    sys.stderr.write(
                        "[CEASER Voice] stt_completed provider=google_cloud "
                        f"detected_language={detected_locale or 'unknown'} "
                        f"translated_for_routing={bool(metadata.get('translated_for_routing'))}\n"
                    )
                    sys.stderr.flush()
                return TranscriptResult(text.strip(), provider, duration_ms=int((time.perf_counter() - started) * 1000), language=detected_locale or analysis.primary_language, secondary_languages=list(analysis.secondary_languages), code_switched=analysis.code_switched, metadata=metadata)
            except Exception as exc:  # noqa: BLE001 - normalized STT fallback.
                category = self._failure_category(provider, exc)
                errors.append(f"{provider}:{category}")
                if not quiet_failures:
                    sys.stderr.write(f"[CEASER Voice] stt_failed provider={provider} category={category}\n")
                    sys.stderr.flush()
        return TranscriptResult("", providers[-1], duration_ms=int((time.perf_counter() - started) * 1000), error_code="stt_failed", metadata={"errors": errors})

    @staticmethod
    def _failure_category(provider: str, exc: Exception) -> str:
        if provider == "elevenlabs":
            return exc.category if isinstance(exc, ElevenLabsError) else "provider_error"
        if provider == "deepgram":
            if isinstance(exc, DeepgramSttError):
                return exc.category
            if isinstance(exc, requests.Timeout):
                return "timeout"
            if isinstance(exc, requests.ConnectionError):
                return "network_error"
            if isinstance(exc, requests.RequestException):
                return "http_error"
            if isinstance(exc, (ValueError, KeyError, IndexError, TypeError)):
                return "invalid_response"
            return "http_error"
        if provider == "google_cloud":
            if isinstance(exc, GoogleCloudSttError):
                return exc.category
            return type(exc).__name__
        return type(exc).__name__

    def _google(self, capture: AudioCapture) -> str:
        recognizer = sr.Recognizer()
        audio = sr.AudioData(capture.pcm, capture.sample_rate, capture.sample_width)
        return recognizer.recognize_google(audio, language=self.language)

    def _google_cloud(self, capture: AudioCapture) -> tuple[str, dict]:
        if self._google_cloud_unavailable_category:
            raise GoogleCloudSttError(self._google_cloud_unavailable_category)
        try:
            import google.auth
            from google.auth import exceptions as google_auth_exceptions
            from google.auth.transport.requests import Request as GoogleAuthRequest
            from google.api_core import exceptions as google_exceptions
            from google.cloud import speech_v1p1beta1 as speech
        except ImportError as exc:
            raise GoogleCloudSttError("sdk_missing") from exc
        try:
            sys.stderr.write(
                f"[CEASER Voice] stt_started provider=google_cloud "
                f"primary_language={self.google_primary_language} alternatives={len(self.google_alternative_languages)}\n"
            )
            sys.stderr.flush()
            if self._google_speech_client is None:
                credentials, project_id = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
                if not credentials.valid:
                    credentials.refresh(GoogleAuthRequest())
                self._google_speech_client = speech.SpeechClient(credentials=credentials)
                if not self.google_cloud_project and project_id:
                    self.google_cloud_project = project_id
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=capture.sample_rate,
                audio_channel_count=1,
                language_code=self.google_primary_language,
                alternative_language_codes=self.google_alternative_languages,
                enable_automatic_punctuation=True,
                model="latest_short",
            )
            response = self._google_speech_client.recognize(
                config=config,
                audio=speech.RecognitionAudio(content=capture.pcm),
                timeout=5,
            )
        except google_auth_exceptions.RefreshError as exc:
            self._google_cloud_unavailable_category = "reauthentication_required"
            raise GoogleCloudSttError("reauthentication_required") from exc
        except google_auth_exceptions.DefaultCredentialsError as exc:
            self._google_cloud_unavailable_category = "credentials_missing"
            raise GoogleCloudSttError("credentials_missing") from exc
        except google_exceptions.Unauthenticated as exc:
            self._google_cloud_unavailable_category = "authentication_failed"
            raise GoogleCloudSttError("authentication_failed") from exc
        except google_exceptions.PermissionDenied as exc:
            raise GoogleCloudSttError("permission_denied") from exc
        except google_exceptions.ResourceExhausted as exc:
            raise GoogleCloudSttError("rate_limited") from exc
        except google_exceptions.DeadlineExceeded as exc:
            raise GoogleCloudSttError("timeout") from exc
        except google_exceptions.GoogleAPICallError as exc:
            raise GoogleCloudSttError("api_error") from exc
        if not response.results:
            raise GoogleCloudSttError("no_transcript")
        result = response.results[0]
        if not result.alternatives:
            raise GoogleCloudSttError("invalid_response")
        alternative = result.alternatives[0]
        return alternative.transcript.strip(), {
            "detected_language": str(getattr(result, "language_code", "") or self.google_primary_language),
            "provider_confidence": float(getattr(alternative, "confidence", 0.0) or 0.0),
        }

    def _translate_for_routing(self, text: str, source_locale: str) -> str:
        if self.translation_provider != "google_cloud" or not text:
            return text
        try:
            from google.cloud import translate_v2 as translate

            if self._google_translate_client is None:
                self._google_translate_client = translate.Client(project=self.google_cloud_project)
            result = self._google_translate_client.translate(
                text,
                target_language=self.translation_target,
                source_language=source_locale.split("-", 1)[0],
                format_="text",
            )
            return html.unescape(str(result.get("translatedText") or text)).strip()
        except Exception as exc:  # noqa: BLE001 - translation is optional; preserve the source transcript.
            sys.stderr.write(f"[CEASER Voice] translation_failed provider=google_cloud category={type(exc).__name__}\n")
            sys.stderr.flush()
            return text

    def _deepgram(self, capture: AudioCapture) -> str:
        if not self.deepgram_key:
            raise DeepgramSttError("missing_key")
        try:
            response = requests.post(
                "https://api.deepgram.com/v1/listen",
                params={"model": self.deepgram_model, "language": self.deepgram_language, "smart_format": "true", "punctuate": "true"},
                headers={"Authorization": f"Token {self.deepgram_key}", "Content-Type": "audio/wav"},
                data=self._wav_bytes(capture),
                timeout=18,
            )
        except requests.Timeout as exc:
            raise DeepgramSttError("timeout") from exc
        except requests.ConnectionError as exc:
            raise DeepgramSttError("network_error") from exc
        except requests.RequestException as exc:
            raise DeepgramSttError("http_error") from exc
        if not response.ok:
            category = {401: "http_401", 403: "http_403", 429: "http_429"}.get(response.status_code, "http_error")
            raise DeepgramSttError(category)
        try:
            data = response.json()
            return str(data.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "")).strip()
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise DeepgramSttError("invalid_response") from exc

    @staticmethod
    def _wav_bytes(capture: AudioCapture) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(capture.sample_width)
            wav.setframerate(capture.sample_rate)
            wav.writeframes(capture.pcm)
        return buffer.getvalue()
