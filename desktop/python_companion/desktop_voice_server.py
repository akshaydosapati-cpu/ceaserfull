import contextlib
import base64
import json
import logging
import os
import sys
import time
import warnings
import requests
import audioop
import threading
import re
import subprocess
import webbrowser
import zipfile
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlencode, quote

import pyaudio
import websocket

from core.media_state import MediaStateTracker
from core.schemas import CommandRequest
from cloud.capabilities import execute_cloud_command
from voice.engine import VoiceEngine
from voice.diagnostics import RuntimeDiagnostics
from voice.wake_aliases import WAKE_PREFIX_PATTERN, extract_wake_command, strip_wake_prefix
from voice.metrics import InteractionMetrics, LatencyHistory, perf_ms
from voice.state_machine import ConversationalVoiceController
from voice.elevenlabs_provider import ElevenLabsError, ElevenLabsVoiceProvider


def load_env_files():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, ".env"),
        os.path.join(here, "..", ".env.runtime"),
        os.path.join(here, "..", ".env"),
        os.path.join(here, "..", "..", "backend", ".env"),
        os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "CEASER", ".env"),
    ]
    for filename in candidates:
        if not os.path.exists(filename):
            continue
        try:
            with open(filename, "r", encoding="utf-8") as handle:
                for raw in handle:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value and key not in os.environ:
                        os.environ[key] = value
        except Exception:
            pass


load_env_files()
warnings.filterwarnings(
    "ignore",
    message=".*standard-aifc.*",
    category=DeprecationWarning,
    module="speech_recognition",
)

ENV_ALIASES = {
    "OPENWEATHER_API_KEY": ["WEATHER_API_KEY"],
    "GNEWS_API_KEY": ["NEWS_API_KEY"],
    "HF_TOKEN": ["HUGGINGFACE_API_KEY", "HF_API_KEY"],
    "HF_MODEL": ["HUGGINGFACE_MODEL"],
    "BACKEND_API_URL": ["CEASER_API_URL", "BACKEND_URL", "API_BASE_URL"],
}

for target, sources in ENV_ALIASES.items():
    if os.getenv(target):
        continue
    for source in sources:
        if os.getenv(source):
            os.environ[target] = os.getenv(source)
            break

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_TELEMETRY_IMPL", "none")
os.environ.setdefault("CEASER_REFERENCE_FULL_MODE", "1")

if "--reference-full" not in sys.argv:
    sys.argv.append("--reference-full")

import speech_recognition as sr


LANGUAGE = os.getenv("CEASER_STT_LANGUAGE", "en-IN")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
DEEPGRAM_MODEL = os.getenv("DEEPGRAM_MODEL", "nova-2")
DEEPGRAM_LANGUAGE = os.getenv("DEEPGRAM_LANGUAGE", "en")
STT_PROVIDER = os.getenv("CEASER_STT_PROVIDER", "google").lower()
DEEPGRAM_STT_MODE = os.getenv("CEASER_DEEPGRAM_STT_MODE", "live").lower()
ALLOW_GOOGLE_STT_FALLBACK = os.getenv("CEASER_STT_GOOGLE_FALLBACK", "true").lower() in ("1", "true", "yes")
BACKEND_API_URL = os.getenv("CEASER_API_URL") or os.getenv("BACKEND_API_URL") or os.getenv("BACKEND_URL") or "https://ceaser-backend-production-ur04.onrender.com"
CEASER_ACCESS_TOKEN = os.getenv("CEASER_ACCESS_TOKEN")
CEASER_REFRESH_TOKEN = ""
CURRENT_USER_ID = os.getenv("CURRENT_USER_ID")
VOICE_ENERGY_THRESHOLD = int(os.getenv("CEASER_SR_ENERGY_THRESHOLD", "95"))
VOICE_MAX_ENERGY_THRESHOLD = int(os.getenv("CEASER_SR_MAX_ENERGY_THRESHOLD", "280"))
VOICE_PAUSE_THRESHOLD = float(os.getenv("CEASER_SR_PAUSE_THRESHOLD", "0.75"))
VOICE_NON_SPEAKING = float(os.getenv("CEASER_SR_NON_SPEAKING_DURATION", "0.28"))
VOICE_PHRASE_THRESHOLD = float(os.getenv("CEASER_SR_PHRASE_THRESHOLD", "0.12"))
VOICE_DYNAMIC_ENERGY = os.getenv("CEASER_SR_DYNAMIC_ENERGY", "false").lower() in ("1", "true", "yes")
ACTIVE_LISTEN_TIMEOUT = float(os.getenv("CEASER_ACTIVE_LISTEN_TIMEOUT", "5"))
PASSIVE_LISTEN_TIMEOUT = float(os.getenv("CEASER_PASSIVE_LISTEN_TIMEOUT", "2.5"))
ACTIVE_PHRASE_LIMIT = float(os.getenv("CEASER_ACTIVE_PHRASE_LIMIT", "10"))
PASSIVE_PHRASE_LIMIT = float(os.getenv("CEASER_PASSIVE_PHRASE_LIMIT", "5"))
MICROPHONE_DEVICE_INDEX = os.getenv("CEASER_MIC_DEVICE_INDEX")
MIC_LOCK = threading.Lock()
EMIT_LOCK = threading.Lock()
COMMAND_EXECUTION_LOCK = threading.RLock()
WAKE_CANCEL_EVENT = threading.Event()
MIC_CALIBRATED = False
GLOBAL_RECOGNIZER = None
GLOBAL_MICROPHONE = None
GLOBAL_MIC_SOURCE = None
ACTION_CONTEXT = {
    "last_user_command": "",
    "last_response": "",
    "last_kind": "",
    "last_created_path": "",
    "updated_at": 0,
    "backend_auth_error": "",
    "desktop_conversation_id": "",
    "current_user": {},
    "smart_capture": {},
    "media_state": "unknown",
    "media_target": "",
}
MEDIA_STATE = MediaStateTracker()
COMMAND_SERVICE = None
COMMAND_SERVICE_LOCK = threading.Lock()
LEGACY_ASSISTANT = None
LEGACY_ASSISTANT_LOCK = threading.Lock()
PROACTIVE_RUNTIME_THREAD = None
PROACTIVE_RUNTIME_STOP = threading.Event()
VOICE_ENGINE = None
ELEVENLABS_VOICE = ElevenLabsVoiceProvider()
VOICE_CONTROLLER = ConversationalVoiceController()
LATENCY_HISTORY = LatencyHistory()
DIAGNOSTICS = RuntimeDiagnostics(LATENCY_HISTORY)
RECENT_REQUESTS = {}
WAKE_COMMAND_ACTIVE = False
WAKE_WORD_ENABLED = os.getenv("CEASER_WAKE_WORD_ENABLED", "false").lower() in ("1", "true", "yes", "on")

logging.basicConfig(
    level=logging.INFO,
    format="[CEASER Brain] %(message)s",
    stream=sys.stderr,
)

REST_PATTERN = re.compile(
    r"\b(?:take rest|rest now|turn off|shutdown voice|shut down voice|stop voice|goodbye|good bye|go silent|sleep ceaser|sleep caesar)\b",
    re.IGNORECASE,
)


def _silent_speak(_text):
    return None


def get_legacy_assistant():
    global LEGACY_ASSISTANT
    with LEGACY_ASSISTANT_LOCK:
        if LEGACY_ASSISTANT is None:
            started = time.perf_counter()
            import voice_assistant_main as assistant
            assistant.speak = _silent_speak
            if hasattr(assistant, "voice_assistant") and assistant.voice_assistant:
                assistant.voice_assistant.speak = _silent_speak
            if CURRENT_USER_ID:
                with contextlib.suppress(Exception):
                    assistant.set_current_user(CURRENT_USER_ID)
            LEGACY_ASSISTANT = assistant
            sys.stderr.write(f"[CEASER Startup] legacy_assistant_ready elapsed_ms={int((time.perf_counter() - started) * 1000)}\n")
            sys.stderr.flush()
    return LEGACY_ASSISTANT


def get_recognizer():
    global GLOBAL_RECOGNIZER
    if GLOBAL_RECOGNIZER is None:
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = VOICE_ENERGY_THRESHOLD
        recognizer.dynamic_energy_threshold = VOICE_DYNAMIC_ENERGY
        recognizer.dynamic_energy_adjustment_damping = 0.06
        recognizer.dynamic_energy_ratio = 1.1
        recognizer.pause_threshold = VOICE_PAUSE_THRESHOLD
        recognizer.non_speaking_duration = VOICE_NON_SPEAKING
        recognizer.phrase_threshold = VOICE_PHRASE_THRESHOLD
        GLOBAL_RECOGNIZER = recognizer
    return GLOBAL_RECOGNIZER


def get_microphone():
    if MICROPHONE_DEVICE_INDEX not in (None, ""):
        return sr.Microphone(device_index=int(MICROPHONE_DEVICE_INDEX))
    return sr.Microphone()


def get_microphone_source():
    global GLOBAL_MICROPHONE, GLOBAL_MIC_SOURCE, MIC_CALIBRATED
    if GLOBAL_MIC_SOURCE is not None:
        return GLOBAL_MIC_SOURCE
    GLOBAL_MICROPHONE = get_microphone()
    GLOBAL_MIC_SOURCE = GLOBAL_MICROPHONE.__enter__()
    MIC_CALIBRATED = False
    sys.stderr.write("[CEASER Python] Persistent microphone stream opened\n")
    sys.stderr.flush()
    return GLOBAL_MIC_SOURCE


def reset_microphone_source():
    global GLOBAL_MICROPHONE, GLOBAL_MIC_SOURCE, MIC_CALIBRATED
    if GLOBAL_MICROPHONE is not None:
        with contextlib.suppress(Exception):
            GLOBAL_MICROPHONE.__exit__(None, None, None)
    GLOBAL_MICROPHONE = None
    GLOBAL_MIC_SOURCE = None
    MIC_CALIBRATED = False


def calibrate_microphone_once(recognizer, source):
    global MIC_CALIBRATED
    if MIC_CALIBRATED:
        return
    with contextlib.suppress(Exception):
        recognizer.adjust_for_ambient_noise(source, duration=0.35)
        recognizer.energy_threshold = max(
            VOICE_ENERGY_THRESHOLD,
            min(int(recognizer.energy_threshold), VOICE_MAX_ENERGY_THRESHOLD),
        )
        recognizer.dynamic_energy_threshold = VOICE_DYNAMIC_ENERGY
    MIC_CALIBRATED = True
    sys.stderr.write(f"[CEASER Python] Microphone calibrated energy={recognizer.energy_threshold}\n")
    sys.stderr.flush()


def listen_audio(passive=False):
    recognizer = get_recognizer()
    timeout = PASSIVE_LISTEN_TIMEOUT if passive else ACTIVE_LISTEN_TIMEOUT
    phrase_limit = PASSIVE_PHRASE_LIMIT if passive else ACTIVE_PHRASE_LIMIT
    with MIC_LOCK:
        try:
            source = get_microphone_source()
            calibrate_microphone_once(recognizer, source)
            return recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
        except Exception:
            reset_microphone_source()
            source = get_microphone_source()
            calibrate_microphone_once(recognizer, source)
            return recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)


def listen_with_google(passive=False):
    recognizer = get_recognizer()
    audio = listen_audio(passive=passive)
    return recognizer.recognize_google(audio, language=LANGUAGE).strip()


def emit(payload):
    with EMIT_LOCK:
        sys.stdout.write("CEASER_JSON:" + json.dumps(payload, ensure_ascii=True) + "\n")
        sys.stdout.flush()


def emit_v2_event(event, payload=None):
    emit({
        "version": "2.0",
        "type": "event",
        "event": event,
        "payload": payload or {},
    })


def emit_voice_state(state, **payload):
    emit({"id": "voice_status", "status": state, **payload})
    emit_v2_event("voice_state", {"state": state, **payload})


def transcribe_with_deepgram(audio):
    if not DEEPGRAM_API_KEY:
        raise RuntimeError("DEEPGRAM_API_KEY missing")
    audio_bytes = audio.get_wav_data()
    response = requests.post(
        "https://api.deepgram.com/v1/listen",
        params={
            "model": DEEPGRAM_MODEL,
            "language": DEEPGRAM_LANGUAGE,
            "smart_format": "true",
            "punctuate": "true",
        },
        headers={
            "Authorization": f"Token {DEEPGRAM_API_KEY}",
            "Content-Type": "audio/wav",
        },
        data=audio_bytes,
        timeout=18,
    )
    response.raise_for_status()
    data = response.json()
    alternatives = data.get("results", {}).get("channels", [{}])[0].get("alternatives", [])
    transcript = alternatives[0].get("transcript", "") if alternatives else ""
    return transcript.strip()


def transcribe_live_with_deepgram():
    if not DEEPGRAM_API_KEY:
        raise RuntimeError("DEEPGRAM_API_KEY missing")

    sample_rate = int(os.getenv("CEASER_DEEPGRAM_SAMPLE_RATE", "16000"))
    chunk_size = int(os.getenv("CEASER_DEEPGRAM_CHUNK_SIZE", "1024"))
    silence_ms = int(os.getenv("CEASER_VOICE_SILENCE_MS", "1200"))
    max_seconds = float(os.getenv("CEASER_VOICE_MAX_SECONDS", "18"))
    no_speech_seconds = float(os.getenv("CEASER_VOICE_NO_SPEECH_SECONDS", "8"))
    rms_threshold = int(os.getenv("CEASER_VOICE_RMS_THRESHOLD", "350"))

    query = urlencode({
        "model": DEEPGRAM_MODEL,
        "language": DEEPGRAM_LANGUAGE,
        "encoding": "linear16",
        "sample_rate": sample_rate,
        "channels": 1,
        "smart_format": "true",
        "punctuate": "true",
        "interim_results": "false",
        "endpointing": "700",
    })
    url = f"wss://api.deepgram.com/v1/listen?{query}"
    opened = threading.Event()
    finished = threading.Event()
    transcripts = []
    errors = []

    def on_open(_ws):
        opened.set()

    def on_message(_ws, message):
        try:
            data = json.loads(message)
            alt = data.get("channel", {}).get("alternatives", [{}])[0]
            text = str(alt.get("transcript", "")).strip()
            if text:
                transcripts.append(text)
        except Exception:
            pass

    def on_error(_ws, error):
        errors.append(error)
        finished.set()

    def on_close(_ws, *_args):
        finished.set()

    ws = websocket.WebSocketApp(
        url,
        header=[f"Authorization: Token {DEEPGRAM_API_KEY}"],
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    thread = threading.Thread(target=lambda: ws.run_forever(ping_interval=5, ping_timeout=3), daemon=True)
    thread.start()
    if not opened.wait(timeout=6):
        raise TimeoutError("Deepgram live STT did not open")

    sys.stderr.write("[CEASER Python] Deepgram live STT opened\n")
    sys.stderr.flush()
    pa = pyaudio.PyAudio()
    stream = None
    started_at = time.perf_counter()
    last_voice_at = started_at
    speech_started = False
    try:
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=chunk_size,
        )
        while True:
            chunk = stream.read(chunk_size, exception_on_overflow=False)
            ws.send(chunk, opcode=websocket.ABNF.OPCODE_BINARY)
            now = time.perf_counter()
            rms = audioop.rms(chunk, 2)
            if rms >= rms_threshold:
                speech_started = True
                last_voice_at = now
            if speech_started and (now - last_voice_at) * 1000 >= silence_ms:
                break
            if not speech_started and now - started_at >= no_speech_seconds:
                break
            if now - started_at >= max_seconds:
                break
        with contextlib.suppress(Exception):
            ws.send(json.dumps({"type": "CloseStream"}))
        finished.wait(timeout=2.5)
    finally:
        if stream:
            with contextlib.suppress(Exception):
                stream.stop_stream()
                stream.close()
        pa.terminate()
        with contextlib.suppress(Exception):
            ws.close()
    if errors and not transcripts:
        raise RuntimeError(type(errors[0]).__name__)
    cleaned = " ".join(dict.fromkeys(item for item in transcripts if item).keys()).strip()
    if not cleaned:
        raise sr.UnknownValueError()
    return cleaned


def listen_once_legacy(passive=False):
    emit({"id": "voice_status", "status": "listening", "passive": passive})
    sys.stderr.write("[CEASER Python] Microphone listening started\n")
    sys.stderr.flush()

    provider = "google"
    transcript = ""
    if STT_PROVIDER == "deepgram":
        try:
            if DEEPGRAM_STT_MODE == "live":
                transcript = transcribe_live_with_deepgram()
                provider = "deepgram_live"
            else:
                raise RuntimeError("Deepgram live disabled")
        except Exception as exc:
            sys.stderr.write(f"[CEASER Python] Deepgram live STT failed: {type(exc).__name__}\n")
            sys.stderr.flush()
            try:
                audio = listen_audio(passive=passive)
                transcript = transcribe_with_deepgram(audio)
                provider = "deepgram"
            except Exception as upload_exc:
                sys.stderr.write(f"[CEASER Python] Deepgram upload STT failed: {type(upload_exc).__name__}\n")
                sys.stderr.flush()
                if not ALLOW_GOOGLE_STT_FALLBACK:
                    raise

    if not transcript:
        transcript = listen_with_google(passive=passive)
        provider = "google"

    emit_voice_state("transcribing", provider=provider)
    sys.stderr.write(f"[CEASER Python] Transcript ({provider}): {transcript}\n")
    sys.stderr.flush()
    return {"transcript": transcript, "provider": provider}


def transcript_wake_fallback():
    while True:
        listened = listen_once_legacy(passive=True)
        transcript = listened.get("transcript", "")
        provider = listened.get("provider")
        if REST_PATTERN.search(transcript):
            return {"transcript": transcript, "provider": provider, "resting": True}
        wake = extract_wake_command(transcript)
        if not wake.get("woke"):
            sys.stderr.write(f"[CEASER Python] Degraded transcript wake ignored: {transcript[:90]}\n")
            sys.stderr.flush()
            continue
        emit_voice_state("wake_detected", transcript=transcript, provider=provider, wake_mode="transcript_degraded")
        command = wake.get("command", "").strip()
        if not command:
            emit_voice_state("command_listening", provider=provider, wake_mode="transcript_degraded")
            active = listen_once_legacy(passive=False)
            command = active.get("transcript", "")
            provider = active.get("provider") or provider
        return {"transcript": command, "provider": provider, "wake_transcript": transcript, "wake_mode": "transcript_degraded"}


def get_voice_engine():
    global VOICE_ENGINE
    if VOICE_ENGINE is None:
        here = os.path.dirname(os.path.abspath(__file__))
        VOICE_ENGINE = VoiceEngine(
            base_dir=here,
            emit_event=emit_v2_event,
            # VoiceEngine owns transcript wake fallback. Supplying the older
            # recorder path here would create a second production STT route.
            transcript_wake_fallback=None,
            wake_extractor=extract_wake_command,
            session_id=f"voice_{int(time.time() * 1000)}",
        )
        try:
            VOICE_ENGINE.start()
            details = VOICE_ENGINE.microphone_details()
            emit_voice_state("wake_listening" if WAKE_WORD_ENABLED else "command_listening", reason="voice_engine_ready", **details)
        except Exception as exc:
            sys.stderr.write(f"[CEASER Voice] engine_start_failed reason={type(exc).__name__}\n")
            sys.stderr.flush()
            emit_voice_state("degraded", reason=type(exc).__name__, wake_mode="transcript_degraded" if WAKE_WORD_ENABLED else "hotkey")
            VOICE_ENGINE = None
    return VOICE_ENGINE


def listen_once(passive=False, recoverable_no_speech=False):
    engine = get_voice_engine()
    if not engine:
        emit_voice_state("failed", reason="voice_engine_unavailable", passive=passive)
        raise RuntimeError("voice_engine_unavailable")
    metrics = InteractionMetrics()
    if passive:
        metrics.mark("wake_detected_at")
        result = engine.wait_for_wake_and_capture()
    else:
        metrics.mark("command_speech_started_at")
        result = engine.capture_hotkey_command(recoverable_no_speech=recoverable_no_speech)
    metrics.mark("command_speech_ended_at")
    for key in (
        "command_speech_started_at",
        "command_speech_ended_at",
        "stt_started_at",
        "stt_completed_at",
    ):
        if result.metadata.get(key):
            metrics.mark(key, int(result.metadata[key]))
    if result.error_code:
        DIAGNOSTICS.record_recovery("stt_or_wake_failure", error_code=result.error_code)
        if result.metadata.get("recoverable") and result.error_code in ("no_speech", "stt_failed", "empty_transcript"):
            raise sr.WaitTimeoutError(result.error_code)
        if result.error_code in ("no_speech", "wake_timeout"):
            raise sr.WaitTimeoutError(result.error_code)
        raise sr.UnknownValueError()
    transcript = result.transcript.strip()
    if not transcript:
        raise sr.UnknownValueError()
    sys.stderr.write(f"[CEASER Python] Transcript ({result.provider}): {transcript}\n")
    sys.stderr.flush()
    payload = {"transcript": transcript, "provider": result.provider, "confidence": result.confidence, "duration_ms": result.duration_ms, **result.metadata}
    payload["voice_metrics"] = metrics.safe_metrics()
    return payload


def split_command_steps(command):
    text = str(command or "").strip()
    if not text:
        return []
    parts = re.split(r"\b(?:and then|then|after that|next)\b", text, flags=re.IGNORECASE)
    return [part.strip(" ,.;") for part in parts if part.strip(" ,.;")]


def listen_for_wake_command(force_command_listening=False):
    global WAKE_COMMAND_ACTIVE
    follow_up = bool(not force_command_listening and VOICE_CONTROLLER.should_accept_without_wake())
    initial_state = "command_listening" if force_command_listening or not WAKE_WORD_ENABLED else ("follow_up_listening" if follow_up else "wake_listening")
    emit_voice_state(initial_state, expires_at=VOICE_CONTROLLER.follow_up_until if follow_up else 0)
    if force_command_listening:
        sys.stderr.write("[CEASER Python] Hotkey direct command listening started\n")
    else:
        sys.stderr.write("[CEASER Python] Follow-up listening started\n" if follow_up else "[CEASER Python] Command listening started\n" if not WAKE_WORD_ENABLED else "[CEASER Python] Wake listening started\n")
    sys.stderr.flush()
    if WAKE_COMMAND_ACTIVE:
        idle_state = "wake_listening" if WAKE_WORD_ENABLED and not force_command_listening else "command_listening"
        emit_voice_state(idle_state, reason="duplicate_listen_request_suppressed", wake_request_active=True)
        return {"status": idle_state, "transcript": "", "message": "", "context_kind": "voice_session", "wake_request_active": True}
    WAKE_COMMAND_ACTIVE = True
    WAKE_CANCEL_EVENT.clear()
    if not VOICE_CONTROLLER.begin_capture():
        WAKE_COMMAND_ACTIVE = False
        return {"status": "command_listening" if force_command_listening or not WAKE_WORD_ENABLED else "wake_listening", "transcript": "", "message": "", "context_kind": "voice_session", "voice_control": "busy"}
    engine = get_voice_engine()
    hotkey_direct = bool(force_command_listening or (engine and getattr(engine.config, "wake_mode", "") == "hotkey" and not follow_up))
    if hotkey_direct:
        emit_voice_state("command_listening", reason="hotkey_mode_direct_capture")
        sys.stderr.write("[CEASER Python] Hotkey mode direct command capture\n")
        sys.stderr.flush()
    recoverable_command_wait = hotkey_direct or follow_up
    try:
        while True:
            if WAKE_CANCEL_EVENT.is_set():
                return {"status": "command_listening" if force_command_listening or not WAKE_WORD_ENABLED else "wake_listening", "transcript": "", "message": "", "recoverable": True, "reason": "superseded_by_command"}
            try:
                listened = listen_once(passive=(not follow_up and not hotkey_direct), recoverable_no_speech=recoverable_command_wait)
                if WAKE_CANCEL_EVENT.is_set():
                    return {"status": "command_listening" if force_command_listening or not WAKE_WORD_ENABLED else "wake_listening", "transcript": "", "message": "", "recoverable": True, "reason": "superseded_by_command"}
                break
            except (sr.WaitTimeoutError, sr.UnknownValueError) as exc:
                if not recoverable_command_wait:
                    raise
                # Silence and unrecognized background audio are normal while the
                # persistent command session is idle. Keep listening quietly.
                time.sleep(0.25)
                continue
            except Exception as exc:  # noqa: BLE001 - hotkey wait must not spin renderer requests.
                if not recoverable_command_wait:
                    raise
                emit_voice_state("command_listening", reason="hotkey_capture_retry", recoverable=True, error_type=type(exc).__name__)
                sys.stderr.write(f"[CEASER Python] Hotkey command capture retry: {type(exc).__name__}: {str(exc)[:160]}\n")
                sys.stderr.flush()
                time.sleep(0.5)
                continue
    finally:
        VOICE_CONTROLLER.end_capture()
        WAKE_COMMAND_ACTIVE = False
    command = strip_wake_prefix(listened.get("transcript", ""))
    provider = listened.get("provider")
    control = VOICE_CONTROLLER.handle_control(command)
    if control:
        control["stt_provider"] = provider
        return control
    if REST_PATTERN.search(command):
        return {
            "status": "resting",
            "transcript": command,
            "message": "CEASER is going silent.",
            "stt_provider": provider,
            "context_kind": "voice_session",
        }
    command, corrected = VOICE_CONTROLLER.normalize_correction(command)
    response = execute_text(
        command,
        source="voice",
        context={
            "wake_transcript": listened.get("wake_transcript", ""),
            "wake_mode": listened.get("wake_mode", get_voice_engine().active_wake_mode() if get_voice_engine() else ""),
            "follow_up_without_wake": follow_up,
            "mid_course_correction": corrected,
            "previous_voice_command": VOICE_CONTROLLER.last_command,
        },
        request_id=f"voice_{int(time.time() * 1000)}",
        stt_metadata={
            "provider": provider,
            "wake_transcript": listened.get("wake_transcript", ""),
            "confidence": listened.get("confidence"),
            "language": listened.get("language"),
            "detected_language": listened.get("detected_language"),
            "secondary_languages": listened.get("secondary_languages", []),
            "code_switched": bool(listened.get("code_switched")),
            "original_transcript": listened.get("original_transcript", ""),
            "translated_for_routing": bool(listened.get("translated_for_routing")),
        },
    )
    response["stt_provider"] = provider
    response["follow_up_without_wake"] = follow_up
    response["mid_course_correction"] = corrected
    return VOICE_CONTROLLER.record_execution(command, response)


def infer_response_kind(command, response):
    text = f"{command} {response}".lower()
    if any(word in text for word in ("email", "mail", "subject:", "dear ", "regards")):
        return "email"
    if any(word in text for word in ("report", "document", "pdf", "proposal", "business plan", "assignment")):
        return "document"
    if any(word in text for word in ("table", "|---", "spreadsheet", "excel")):
        return "table"
    return "answer"


def remember_result(command, response, kind=None, path=""):
    if not response:
        return
    ACTION_CONTEXT.update({
        "last_user_command": str(command or "").strip(),
        "last_response": str(response or "").strip(),
        "last_kind": kind or infer_response_kind(command, response),
        "last_created_path": path or ACTION_CONTEXT.get("last_created_path", ""),
        "updated_at": time.time(),
    })


def clean_backend_text(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if not (text.startswith("{") or text.startswith("[")):
        return text
    try:
        data = json.loads(text)
    except Exception:
        return text
    if isinstance(data, dict):
        lines = []
        title = data.get("title") or data.get("type")
        summary = data.get("summary") or data.get("message") or data.get("answer")
        if title:
            lines.append(str(title).strip())
        if summary:
            lines.append(str(summary).strip())
        sections = data.get("sections") or []
        for section in sections:
            if not isinstance(section, dict):
                continue
            heading = section.get("title") or section.get("name")
            details = section.get("details") or section.get("description")
            items = section.get("items") or []
            if heading:
                lines.append(f"\n{heading}")
            if details:
                lines.append(str(details).strip())
            for item in items[:8]:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("title") or item.get("label") or "Item"
                    desc = item.get("description") or item.get("details") or item.get("status") or ""
                    lines.append(f"- {name}" + (f": {desc}" if desc else ""))
                else:
                    lines.append(f"- {item}")
        for key in ("actions", "next_steps", "warnings"):
            items = data.get(key) or []
            if items:
                label = key.replace("_", " ").title()
                lines.append(f"\n{label}")
                for item in items[:5]:
                    lines.append(f"- {item}")
        cleaned = "\n".join(line for line in lines if str(line).strip()).strip()
        return cleaned or text
    if isinstance(data, list):
        return "\n".join(f"- {item}" for item in data[:10])
    return text


def context_is_recent(max_age_seconds=1800):
    return bool(ACTION_CONTEXT.get("last_response")) and time.time() - float(ACTION_CONTEXT.get("updated_at") or 0) <= max_age_seconds


def copy_to_clipboard(text):
    value = str(text or "")
    if not value:
        return False
    if os.name == "nt":
        subprocess.run("clip", input=value, text=True, check=False)
        return True
    return False


def save_last_result(extension=".txt"):
    if not context_is_recent():
        return ""
    safe_ext = extension if extension.startswith(".") else f".{extension}"
    base_dir = os.path.join(os.path.expanduser("~"), "Documents", "CEASER")
    os.makedirs(base_dir, exist_ok=True)
    filename = f"ceaser-output-{time.strftime('%Y%m%d-%H%M%S')}{safe_ext}"
    path = os.path.join(base_dir, filename)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(ACTION_CONTEXT["last_response"])
    ACTION_CONTEXT["last_created_path"] = path
    return path


def open_path(path):
    if path and os.path.exists(path):
        os.startfile(path)
        return True
    return False


def persistent_env_path():
    base = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "CEASER")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, ".env")


def update_persistent_env(updates):
    try:
        path = persistent_env_path()
        values = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                for raw in handle:
                    if "=" in raw and not raw.lstrip().startswith("#"):
                        key, value = raw.rstrip("\n").split("=", 1)
                        values[key.strip()] = value.strip()
        for key, value in updates.items():
            cleaned = str(value or "").strip()
            if cleaned and cleaned.lower() not in ("undefined", "null", "false"):
                values[key] = cleaned
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
    except Exception as exc:
        sys.stderr.write(f"[CEASER Python] Could not persist desktop session: {type(exc).__name__}\n")
        sys.stderr.flush()


def clear_desktop_session():
    global CEASER_ACCESS_TOKEN, CEASER_REFRESH_TOKEN, CURRENT_USER_ID
    CEASER_ACCESS_TOKEN = ""
    CEASER_REFRESH_TOKEN = ""
    CURRENT_USER_ID = ""
    ACTION_CONTEXT["backend_auth_error"] = "401"
    ACTION_CONTEXT["current_user"] = {}
    try:
        path = persistent_env_path()
        values = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                for raw in handle:
                    if "=" in raw and not raw.lstrip().startswith("#"):
                        key, value = raw.rstrip("\n").split("=", 1)
                        if key.strip() not in ("CEASER_ACCESS_TOKEN", "CEASER_REFRESH_TOKEN", "CURRENT_USER_ID", "CEASER_LINKED_AT"):
                            values[key.strip()] = value.strip()
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(f"{key}={value}" for key, value in values.items()) + ("\n" if values else ""))
    except Exception:
        pass


def refresh_ceaser_session():
    global CEASER_ACCESS_TOKEN, CEASER_REFRESH_TOKEN, CURRENT_USER_ID
    if not BACKEND_API_URL or not CEASER_REFRESH_TOKEN or len(str(CEASER_REFRESH_TOKEN)) < 20:
        return False
    try:
        response = requests.post(
            f"{BACKEND_API_URL.rstrip('/')}/auth/refresh",
            headers={"Content-Type": "application/json"},
            json={"refresh_token": CEASER_REFRESH_TOKEN},
            timeout=20,
        )
        if not response.ok:
            sys.stderr.write(f"[CEASER Python] Session refresh failed: {response.status_code}\n")
            sys.stderr.flush()
            if response.status_code == 401:
                clear_desktop_session()
            return False
        data = response.json()
        access = data.get("access_token")
        refresh = data.get("refresh_token") or CEASER_REFRESH_TOKEN
        user = data.get("user") or {}
        user_id = user.get("id") or CURRENT_USER_ID
        if not access:
            return False
        CEASER_ACCESS_TOKEN = access
        CEASER_REFRESH_TOKEN = refresh
        CURRENT_USER_ID = user_id
        ACTION_CONTEXT["backend_auth_error"] = ""
        if user_id:
            ACTION_CONTEXT["current_user"] = user
        update_persistent_env({
            "CEASER_ACCESS_TOKEN": access,
            "CEASER_REFRESH_TOKEN": refresh,
            "CURRENT_USER_ID": user_id,
            "CEASER_LINKED_AT": datetime.utcnow().isoformat() + "Z",
        })
        sys.stderr.write("[CEASER Python] Desktop session refreshed\n")
        sys.stderr.flush()
        return True
    except Exception as exc:
        sys.stderr.write(f"[CEASER Python] Session refresh unavailable: {type(exc).__name__}\n")
        sys.stderr.flush()
        return False


def load_current_user_context():
    global CURRENT_USER_ID
    if ACTION_CONTEXT.get("current_user"):
        return ACTION_CONTEXT["current_user"]
    if not BACKEND_API_URL or not CEASER_ACCESS_TOKEN:
        return {}
    try:
        response = requests.get(
            f"{BACKEND_API_URL.rstrip('/')}/auth/me",
            headers={"Authorization": f"Bearer {CEASER_ACCESS_TOKEN}"},
            timeout=12,
        )
        if response.status_code == 401 and refresh_ceaser_session():
            response = requests.get(
                f"{BACKEND_API_URL.rstrip('/')}/auth/me",
                headers={"Authorization": f"Bearer {CEASER_ACCESS_TOKEN}"},
                timeout=12,
            )
        if response.ok:
            user = response.json()
            user_id = user.get("id") or CURRENT_USER_ID
            CURRENT_USER_ID = user_id
            ACTION_CONTEXT["current_user"] = user
            if user_id:
                update_persistent_env({"CURRENT_USER_ID": user_id})
            return ACTION_CONTEXT["current_user"]
        if response.status_code == 401:
            clear_desktop_session()
    except Exception:
        pass
    return {}


def handle_projects_command(command):
    lowered = str(command or "").lower().strip()
    if not re.search(r"\b(my|current|active|ceaser)?\s*projects?\b", lowered):
        return None
    if not re.search(r"\b(what|show|list|tell|have|status|project)\b", lowered):
        return None
    if not BACKEND_API_URL:
        return {"status": "error", "message": "CEASER backend is not configured.", "context_kind": "projects"}
    if not CEASER_ACCESS_TOKEN and not refresh_ceaser_session():
        return {"status": "error", "message": "Please reconnect CEASER from the web console to view your projects.", "context_kind": "auth"}
    try:
        response = requests.get(
            f"{BACKEND_API_URL.rstrip('/')}/projects",
            headers={"Authorization": f"Bearer {CEASER_ACCESS_TOKEN}"},
            timeout=15,
        )
        if response.status_code == 401 and refresh_ceaser_session():
            response = requests.get(
                f"{BACKEND_API_URL.rstrip('/')}/projects",
                headers={"Authorization": f"Bearer {CEASER_ACCESS_TOKEN}"},
                timeout=15,
            )
        if response.status_code == 401:
            clear_desktop_session()
            return {"status": "error", "message": "Your desktop session expired. Please reconnect CEASER from the web console.", "context_kind": "auth"}
        if not response.ok:
            return {"status": "error", "message": "I could not load your CEASER projects right now.", "context_kind": "projects"}
        projects = response.json() if response.content else []
        if not projects:
            return {"status": "completed", "message": "You do not have any active CEASER projects yet.", "context_kind": "projects"}
        lines = [f"You have {len(projects)} CEASER project{'s' if len(projects) != 1 else ''}:"]
        for project in projects[:8]:
            name = project.get("name") or project.get("title") or "Untitled project"
            status = project.get("status") or "active"
            description = project.get("description") or ""
            line = f"- {name} ({status})"
            if description:
                line += f": {description}"
            lines.append(line)
        if len(projects) > 8:
            lines.append(f"And {len(projects) - 8} more.")
        return {"status": "completed", "message": "\n".join(lines), "context_kind": "projects"}
    except Exception as exc:
        sys.stderr.write(f"[CEASER Python] Projects lookup failed: {type(exc).__name__}\n")
        sys.stderr.flush()
        return {"status": "error", "message": "I could not reach CEASER projects right now.", "context_kind": "projects"}


def handle_account_command(command):
    lowered = str(command or "").lower().strip()
    if not re.search(r"\b(my name|what'?s my name|who am i|my email|signed[- ]?in email|account details|profile)\b", lowered):
        return None
    user = load_current_user_context()
    if not user:
        if ACTION_CONTEXT.get("backend_auth_error") == "401":
            return {"status": "error", "message": "Your desktop session expired. Please reconnect CEASER from the web console.", "context_kind": "auth"}
        return {"status": "error", "message": "Please reconnect CEASER from the web console so I can read your account.", "context_kind": "auth"}
    name = (
        user.get("name")
        or user.get("full_name")
        or user.get("display_name")
        or user.get("username")
        or (user.get("profile") or {}).get("name")
        or ""
    )
    email = user.get("email") or (user.get("profile") or {}).get("email") or ""
    if "email" in lowered:
        message = f"You are signed in with {email}." if email else "I could not find an email address on your CEASER account."
    elif "account" in lowered or "profile" in lowered:
        parts = []
        if name:
            parts.append(f"Name: {name}")
        if email:
            parts.append(f"Email: {email}")
        parts.append(f"User ID: {user.get('id') or CURRENT_USER_ID or 'available after reconnect'}")
        message = "\n".join(parts)
    else:
        message = f"Your name is {name}." if name else "I could not find your name on your CEASER account."
    return {"status": "completed", "message": message, "context_kind": "account"}


def handle_system_command(command):
    lowered = str(command or "").lower().strip()
    if not lowered:
        return None
    try:
        if re.search(r"\b(lock screen|lock my screen|lock computer|lock my pc|lock workstation)\b", lowered):
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return {"status": "completed", "message": "Computer locked.", "context_kind": "desktop_action"}
        if re.fullmatch(r"(sleep|sleep computer|put computer to sleep|put pc to sleep)", lowered):
            subprocess.Popen('rundll32.exe powrprof.dll,SetSuspendState 0,1,0', shell=True)
            return {"status": "completed", "message": "Putting the computer to sleep.", "context_kind": "desktop_action"}
        if re.fullmatch(r"(show desktop|minimize all|desktop)", lowered):
            import pyautogui
            pyautogui.hotkey("win", "d")
            return {"status": "completed", "message": "Desktop shown.", "context_kind": "desktop_action"}
        if re.fullmatch(r"(switch window|switch app|alt tab)", lowered):
            import pyautogui
            pyautogui.hotkey("alt", "tab")
            return {"status": "completed", "message": "Switched window.", "context_kind": "desktop_action"}
    except Exception as exc:
        return {"status": "error", "message": f"System command failed: {type(exc).__name__}", "context_kind": "desktop_action"}
    return None


def handle_battery_command(command):
    lowered = str(command or "").lower().strip()
    if not re.search(r"\b(battery|charge|charging|power percentage|battery percentage|battery level)\b", lowered):
        return None
    try:
        import psutil
        battery = psutil.sensors_battery()
        if not battery:
            return {"status": "error", "message": "I could not find a battery on this device.", "context_kind": "desktop_action"}
        percent = int(round(float(battery.percent)))
        charging = bool(battery.power_plugged)
        state = "charging" if charging else "not charging"
        return {
            "status": "completed",
            "message": f"Battery is at {percent} percent and is {state}.",
            "context_kind": "desktop_action",
            "battery_percent": percent,
            "charging": charging,
        }
    except Exception as exc:
        return {"status": "error", "message": f"I could not read the battery status: {type(exc).__name__}", "context_kind": "desktop_action"}


def extract_news_topic(command):
    text = str(command or "").strip()
    if not re.search(r"\b(news|headlines|latest updates|current updates)\b", text, re.IGNORECASE):
        return ""
    cleaned = re.sub(r"\b(give|get|show|tell me|what are|what is|latest|current|today'?s|the|news|headlines|updates|about|on|for|please)\b", " ", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .?!,")
    return cleaned or "general"


def handle_news_command(command):
    topic = extract_news_topic(command)
    if not topic:
        return None
    try:
        from features.ceaser.news_assistant import NewsAssistant
        news = NewsAssistant()
        if topic == "general":
            data = news.get_top_headlines(country=os.getenv("NEWS_DEFAULT_REGION", "in"), num_headlines=5)
        else:
            data = news.search_news(topic, num_results=5)
        if not data.get("success"):
            return {"status": "error", "message": f"I could not fetch news right now: {data.get('error', 'news unavailable')}", "context_kind": "news"}
        articles = data.get("articles") or []
        lines = []
        for index, article in enumerate(articles[:5], 1):
            title = str(article.get("title") or "").strip()
            source = str(article.get("source") or "").strip()
            if title:
                lines.append(f"{index}. {title}" + (f" - {source}" if source else ""))
        message = "Latest news" + (f" for {topic}" if topic != "general" else "") + ":\n" + "\n".join(lines)
        return {"status": "completed", "message": message, "context_kind": "news", "topic": topic}
    except Exception as exc:
        return {"status": "error", "message": f"News lookup failed: {type(exc).__name__}", "context_kind": "news"}


def handle_weather_command(command):
    lowered = str(command or "").strip()
    if not re.search(r"\b(weather|temperature|forecast)\b", lowered, re.IGNORECASE):
        return None
    city_match = re.search(r"\b(?:in|for|at)\s+([a-z][a-z .'-]{1,60})", lowered, re.IGNORECASE)
    city = (city_match.group(1).strip(" .?!,") if city_match else os.getenv("WEATHER_DEFAULT_CITY", "").strip())
    try:
        from features.ceaser.weather_assistant import WeatherAssistant
        weather = WeatherAssistant()
        if weather.api_key:
            if not city:
                return {
                    "status": "needs_input",
                    "message": "Which city would you like the weather for?",
                    "context_kind": "weather",
                }
            data = weather.get_current_weather(city)
            if data.get("success"):
                place = ", ".join(filter(None, [str(data.get("city") or ""), str(data.get("country") or "")]))
                message = weather.format_weather_report(data)
                return {"status": "completed", "message": message, "context_kind": "weather", "weather": {**data, "location": place or city}}
            return {"status": "error", "message": f"I could not fetch the weather right now: {data.get('error', 'weather unavailable')}", "context_kind": "weather"}

        # A no-key desktop remains useful: open a live weather result instead
        # of routing a simple current-conditions request through cloud AI.
        query = f"weather {city}".strip()
        url = "https://www.google.com/search?" + urlencode({"q": query})
        webbrowser.open(url)
        return {"status": "completed", "message": f"Opening live weather for {city or 'your area'}.", "context_kind": "weather", "url": url}
    except Exception as exc:
        return {"status": "error", "message": f"I could not open weather right now: {type(exc).__name__}", "context_kind": "weather"}


COMMON_SITE_ALIASES = {
    "facebook": "facebook.com",
    "fb": "facebook.com",
    "youtube": "youtube.com",
    "google": "google.com",
    "gmail": "mail.google.com",
    "github": "github.com",
    "ceaser": "heyceaser.in",
    "hey ceaser": "heyceaser.in",
    "heyceaser": "heyceaser.in",
    "ceaser website": "heyceaser.in",
    "ceaserwebsite": "heyceaser.in",
    "ceaser console": "heyceaser.in/console",
    "ceaserconsole": "heyceaser.in/console",
    "caeser": "heyceaser.in",
    "caesar": "heyceaser.in",
    "cesar": "heyceaser.in",
}


def normalize_spoken_url(value):
    text = str(value or "").lower().strip()
    text = re.sub(r"\b(open|launch|start|run|go to|visit|browse to|website|site|please)\b", " ", text)
    text = text.replace(" dot ", ".").replace(" dot", ".").replace("dot ", ".")
    text = text.replace(" point ", ".").replace(" slash ", "/").replace(" forward slash ", "/")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*\.\s*", ".", text)
    text = text.replace(" ", "")
    text = text.strip(".,;:!?")
    text = re.sub(r"^(?:caeser|caesar|cesar)(?:\.?tech|\.?in)?$", "heyceaser.in", text)
    if text in COMMON_SITE_ALIASES:
        text = COMMON_SITE_ALIASES[text]
    if re.fullmatch(r"[a-z0-9-]+", text) and text in COMMON_SITE_ALIASES:
        text = COMMON_SITE_ALIASES[text]
    if re.search(r"\.[a-z]{2,}(?:/.*)?$", text) or text.startswith(("http://", "https://", "www.")):
        if not text.startswith(("http://", "https://")):
            text = "https://" + text.lstrip("/")
        return text
    return ""


def normalize_spoken_command(command):
    text = str(command or "").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return ""

    text = WAKE_PREFIX_PATTERN.sub("", text).strip()
    replacements = [
        (r"\b(?:paper|people|pepper|paypal)\s+pause\s+(?:the\s+)?(?:music|song|track)\b", "pause music"),
        (r"\b(?:paper|people|pepper|paypal)\s+play\s+(?:the\s+)?(?:music|song|track)\b", "play music"),
        (r"\b(?:pause|stop)\s+(?:the\s+)?(?:song|track|audio)\b", "pause music"),
        (r"\b(?:resume|continue)\s+(?:the\s+)?(?:song|track|audio|music)\b", "resume music"),
        (r"\b(?:skip|next)\s+(?:the\s+)?(?:song|track|audio|music)\b", "next music"),
        (r"\b(?:previous|last|back|go back)\s+(?:the\s+)?(?:song|track|audio|music)\b", "previous music"),
        (r"\b(?:screen\s*capture|capture\s+(?:the\s+)?screen|grab\s+(?:the\s+)?screen|take\s+a\s+screen\s*shot)\b", "take screenshot"),
        (r"^\s*(?:go to|visit|browse to|open website|open site)\s+", "open "),
        (r"^\s*(?:open up|bring up|show me|show|start|launch|run)\s+", "open "),
        (r"\b(?:compose|draft|prepare|send|write)\s+(?:a\s+)?(?:mail|message|gmail)\b", "write email"),
        (r"\b(?:which|show|list)\s+(?:are\s+)?(?:my\s+)?projects\b", "what projects do I have"),
        (r"\b(?:who am i|my profile|account details|signed in account)\b", "what is my account"),
        (r"\b(?:hey\s+)?(?:ceaser|caesar|cesar)\s*(?:dot|point)\s*(?:tech|in)\b", "heyceaser.in"),
        (r"^\s*(?:total\s+)?(?:system\s+)?(?:volume|sound)\s+(?:level\s+)?(?:to|at|is)\s+(\d{1,3})\s*(?:percent|%)?\s*$", r"set volume to \1%"),
        (r"^\s*(?:set|change|make|put|turn)\s+(?:the\s+)?(?:system\s+)?(?:volume|sound)\s+(?:level\s+)?(?:to|at)\s+(\d{1,3})\s*(?:percent|%)?\s*$", r"set volume to \1%"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def extract_percent_value(text):
    match = re.search(r"\b(\d{1,3})\s*(?:percent|%)?\b", str(text or ""), re.IGNORECASE)
    if not match:
        return None
    value = max(0, min(100, int(match.group(1))))
    return value


def handle_volume_command(command):
    lowered = str(command or "").lower().strip()
    if not re.search(r"\b(volume|sound|mute|unmute|louder|quieter)\b", lowered):
        return None
    try:
        from features.ceaser.device_control import DeviceControl
        if re.search(r"\b(unmute|turn on sound)\b", lowered):
            message = DeviceControl.unmute_volume()
            status = "error" if str(message).lower().startswith("failed") else "completed"
            return {"status": status, "message": message, "context_kind": "desktop_action"}
        if re.search(r"\b(mute|silence audio|turn off sound)\b", lowered):
            message = DeviceControl.mute_volume()
            status = "error" if str(message).lower().startswith("failed") else "completed"
            return {"status": status, "message": message, "context_kind": "desktop_action"}
        level = extract_percent_value(lowered)
        if level is not None and re.search(r"\b(set|change|make|put|turn|volume|sound|level|to|at)\b", lowered):
            message = DeviceControl.set_volume(level)
            status = "error" if str(message).lower().startswith("failed") else "completed"
            return {"status": status, "message": message, "context_kind": "desktop_action", "volume": level}
    except Exception as exc:
        return {"status": "error", "message": f"Volume control failed: {type(exc).__name__}", "context_kind": "desktop_action"}
    return None


def extract_google_search_query(command):
    text = str(command or "").strip()
    if not text:
        return ""
    patterns = [
        r"^\s*(?:search|look up|lookup|find)\s+(?:for\s+)?(.+?)\s+(?:in|on|with|using)\s+google\s*$",
        r"^\s*(?:search|look up|lookup|find)\s+google\s+(?:for\s+)?(.+?)\s*$",
        r"^\s*(?:google|search google|google search)\s+(?:for\s+)?(.+?)\s*$",
        r"^\s*(?:search|look up|lookup|find)\s+(?:for\s+)?(.+?)\s*$",
    ]
    for pattern in patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            query = re.sub(r"\s+", " ", match.group(1)).strip(" .?!,")
            if query and not re.match(r"^(?:my files|files|folders|notes|memories|notion|github|repos?|repositories)\b", query, re.IGNORECASE):
                return query
    return ""


def handle_google_search_command(command):
    query = extract_google_search_query(command)
    if not query:
        return None
    try:
        url = "https://www.google.com/search?" + urlencode({"q": query})
        webbrowser.open(url)
        return {
            "status": "completed",
            "message": f"Searching Google for {query}.",
            "context_kind": "desktop_action",
            "url": url,
            "query": query,
        }
    except Exception as exc:
        return {"status": "error", "message": f"I could not search Google: {type(exc).__name__}", "context_kind": "desktop_action"}


def handle_open_url_command(command):
    raw = str(command or "").strip()
    if not re.match(r"^\s*(open|launch|start|run|go to|visit|browse to|open website|open site)\s+.+", raw, re.IGNORECASE):
        return None
    url = normalize_spoken_url(raw)
    if not url:
        return None
    try:
        webbrowser.open(url)
        return {"status": "completed", "message": f"Opened {url}.", "context_kind": "desktop_action", "url": url}
    except Exception as exc:
        return {"status": "error", "message": f"I could not open {url}: {type(exc).__name__}", "context_kind": "desktop_action"}


def handle_close_url_command(command):
    raw = str(command or "").strip()
    if re.fullmatch(r"\s*(?:close|quit|exit)\s+(?:(?:the|this|current|active)\s+)?(?:browser\s+)?(?:tab|page)\s*", raw, re.IGNORECASE):
        try:
            import pyautogui
            import pygetwindow as gw
            title = str(gw.getActiveWindowTitle() or "")
            if not re.search(r"(chrome|edge|firefox|brave|opera)", title, re.IGNORECASE):
                return {"status": "needs_clarification", "message": "Which browser tab should I close?", "context_kind": "desktop_action"}
            before_title = title
            pyautogui.hotkey("ctrl", "w")
            time.sleep(0.2)
            after_title = str(gw.getActiveWindowTitle() or "")
            browser_still_open = any(re.search(r"(chrome|edge|firefox|brave|opera)", str(window.title or ""), re.IGNORECASE) for window in gw.getAllWindows())
            verified = browser_still_open and after_title != before_title
            ACTION_CONTEXT.pop("pending_selection", None)
            return {
                "status": "completed" if verified else "error",
                "message": "Closed the active browser tab." if verified else "I could not verify that the browser tab closed without closing the browser.",
                "context_kind": "desktop_action",
                "verified": verified,
                "error_code": None if verified else "verification_failed",
            }
        except Exception as exc:
            return {"status": "error", "message": f"I could not close the active browser tab: {type(exc).__name__}", "context_kind": "desktop_action"}
    if not re.match(r"^\s*(close|quit|exit)\s+.+", raw, re.IGNORECASE):
        return None
    target = re.sub(r"^\s*(close|quit|exit)\s+", "", raw, flags=re.IGNORECASE).strip()
    target = re.sub(r"^(?:the\s+)?(?:browser\s+)?(?:tab|page)\s+(?:for\s+|called\s+|named\s+)?", "", target, flags=re.IGNORECASE).strip()
    target = re.sub(r"\s+(?:browser\s+)?(?:tab|page)\s*$", "", target, flags=re.IGNORECASE).strip()
    target = re.sub(r"^(?:the\s+)", "", target, flags=re.IGNORECASE).strip()
    target = re.sub(r"\s+(?:in|on|from)\s+(?:google\s+)?(?:chrome|edge|firefox|brave|opera)\s*$", "", target, flags=re.IGNORECASE).strip()
    url = normalize_spoken_url("open " + target)
    lowered = target.lower()
    is_site = bool(url) or any(site in lowered for site in ("youtube", "facebook", "gmail", "google", "github", "ceaser"))
    if not is_site:
        return None
    try:
        closed = close_named_browser_tab(target)
        label = url.replace("https://", "") if url else target
        if not closed:
            return {"status": "error", "message": f"I could not find an open browser tab for {label}.", "context_kind": "desktop_action"}
        return {"status": "completed", "message": f"Closed the browser tab for {label}.", "context_kind": "desktop_action"}
    except Exception as exc:
        return {"status": "error", "message": f"I could not close that browser tab: {type(exc).__name__}", "context_kind": "desktop_action"}


def close_named_browser_tab(target, max_tabs=20):
    """Close an explicitly named browser tab without closing an unrelated active tab."""
    import pyautogui
    import time
    try:
        import pygetwindow as gw
    except Exception:
        return False
    target_text = re.sub(r"^https?://|^www\.", "", str(target or "").lower()).split(".", 1)[0].strip()
    ordinals = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "fifth": 5, "5th": 5, "sixth": 6, "6th": 6, "seventh": 7, "7th": 7, "eighth": 8, "8th": 8}
    target_index = next((index for word, index in ordinals.items() if re.search(rf"\b{word}\b", target_text)), None)
    aliases = {"youtube": ("youtube",), "google": ("google",), "gmail": ("gmail", "inbox"), "github": ("github",)}
    needles = aliases.get(target_text, (target_text,))
    browsers = [window for window in gw.getAllWindows() if re.search(r"(chrome|edge|firefox|brave|opera)", window.title or "", re.IGNORECASE)]
    if not browsers:
        return False
    browsers.sort(key=lambda window: not bool(getattr(window, "isActive", False)))
    for browser in browsers:
        with contextlib.suppress(Exception):
            browser.activate()
            time.sleep(0.12)
            if target_index is not None:
                pyautogui.hotkey("ctrl", str(target_index))
                time.sleep(0.12)
                before_title = str(gw.getActiveWindowTitle() or "")
                pyautogui.hotkey("ctrl", "w")
                time.sleep(0.2)
                after_title = str(gw.getActiveWindowTitle() or "")
                browser_open = any(re.search(r"(chrome|edge|firefox|brave|opera)", str(window.title or ""), re.IGNORECASE) for window in gw.getAllWindows())
                return browser_open and after_title != before_title
            first_title = ""
            for _ in range(max_tabs):
                title = str(gw.getActiveWindowTitle() or "")
                if not first_title:
                    first_title = title
                if any(needle and needle in title.lower() for needle in needles):
                    pyautogui.hotkey("ctrl", "w")
                    time.sleep(0.2)
                    remaining_titles = [str(window.title or "").lower() for window in gw.getAllWindows() if re.search(r"(chrome|edge|firefox|brave|opera)", str(window.title or ""), re.IGNORECASE)]
                    return bool(remaining_titles) and not any(any(needle and needle in item for needle in needles) for item in remaining_titles)
                pyautogui.hotkey("ctrl", "tab")
                time.sleep(0.08)
                if str(gw.getActiveWindowTitle() or "") == first_title:
                    break
    return False


def find_youtube_video(query):
    clean = str(query or "").strip()
    if not clean:
        return None
    try:
        response = requests.get(
            "https://www.youtube.com/results",
            params={"search_query": clean},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=8,
        )
        if response.status_code >= 400:
            return None
        ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', response.text)
        video_id = next((item for index, item in enumerate(ids) if ids.index(item) == index), "")
        if not video_id:
            return None
        title_match = re.search(rf'"videoId":"{re.escape(video_id)}"[\s\S]{{0,1200}}?"title":\{{"runs":\[\{{"text":"([^"]+)"', response.text)
        return {"id": video_id, "title": title_match.group(1).replace("\\u0026", "&") if title_match else clean}
    except Exception:
        return None


def handle_music_command(command):
    text = str(command or "").strip()
    lowered = text.lower()
    media_action = handle_media_control_command(command)
    if media_action:
        return media_action
    new_tab = bool(re.search(r"\b(?:in|on)\s+(?:a\s+)?new\s+tab\b", text, re.IGNORECASE))
    text = re.sub(r"\s+\b(?:in|on)\s+(?:a\s+)?new\s+tab\b", "", text, flags=re.IGNORECASE).strip()
    match = re.match(r"^\s*play\s+(.+?)(?:\s+(?:song|music|video))?(?:\s+(?:on|in)\s+(?:youtube|yt))?\s*$", text, re.IGNORECASE)
    if not match:
        return None
    query = match.group(1).strip()
    if not query or query.lower() in ("music", "song", "video"):
        return None
    video = find_youtube_video(query)
    if video:
        url = f"https://www.youtube.com/watch?v={video['id']}&autoplay=1"
        open_media_url(url, new_tab=new_tab)
        MEDIA_STATE.record("new_playback", query)
        ACTION_CONTEXT.update({"media_state": MEDIA_STATE.status, "media_target": MEDIA_STATE.target})
        return {
            "status": "completed",
            "message": f"Playing {video['title']} on YouTube.",
            "music": {"title": video["title"], "source": "YouTube", "url": url, "query": query},
        }
    url = "https://www.youtube.com/results?search_query=" + quote(query)
    open_media_url(url, new_tab=new_tab)
    MEDIA_STATE.record("new_playback", query)
    ACTION_CONTEXT.update({"media_state": MEDIA_STATE.status, "media_target": MEDIA_STATE.target})
    return {
        "status": "completed",
        "message": f"I opened YouTube results for {query}.",
        "music": {"title": query, "source": "YouTube", "url": url, "query": query},
    }


def open_media_url(url, new_tab=False):
    """Open media in the active browser tab when possible so a new song replaces the old one."""
    try:
        import pyautogui
        import time
        if new_tab:
            webbrowser.open_new_tab(url)
            return True
        browser_window = None
        try:
            import pygetwindow as gw
            browsers = [
                window for window in gw.getAllWindows()
                if re.search(r"(chrome|edge|firefox|brave|opera|youtube)", window.title or "", re.IGNORECASE)
            ]
            if browsers:
                browser_window = next((window for window in browsers if getattr(window, "isActive", False)), browsers[0])
                browser_window.activate()
                time.sleep(0.15)
        except Exception:
            browser_window = None
        if browser_window is None:
            webbrowser.open(url, new=2)
            return True
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.05)
        pyautogui.write(url, interval=0)
        pyautogui.press("enter")
        return True
    except Exception:
        webbrowser.open(url)
        return False


def handle_media_control_command(command):
    lowered = str(command or "").lower().strip()
    if not lowered:
        return None
    try:
        import pyautogui
        import ctypes
        import time

        def focus_media_window():
            """Move keyboard seek commands away from the CEASER overlay."""
            try:
                import pygetwindow as gw
                windows = [
                    window for window in gw.getAllWindows()
                    if re.search(r"(chrome|edge|firefox|brave|opera|youtube|spotify)", window.title or "", re.IGNORECASE)
                ]
                if windows:
                    active = next((window for window in windows if getattr(window, "isActive", False)), windows[0])
                    active.activate()
                    time.sleep(0.12)
                    return True
            except Exception:
                pass
            return False

        def send_global_media_key(vk):
            user32 = ctypes.windll.user32
            user32.keybd_event(vk, 0, 0, 0)
            user32.keybd_event(vk, 0, 2, 0)
            return True
        resolution = MEDIA_STATE.resolve(lowered)
        if resolution.action == "pause":
            pyautogui.press("playpause")
            MEDIA_STATE.record("pause")
            ACTION_CONTEXT["media_state"] = MEDIA_STATE.status
            return {"status": "completed", "message": "Media playback paused.", "context_kind": "desktop_action"}
        if resolution.action == "resume":
            pyautogui.press("playpause")
            MEDIA_STATE.record("resume")
            ACTION_CONTEXT["media_state"] = MEDIA_STATE.status
            return {"status": "completed", "message": "Resumed the current media.", "context_kind": "desktop_action"}
        if resolution.action == "generic_play" or re.search(r"\b(play pause|play/pause|toggle music)\b", lowered):
            send_global_media_key(0xB3)
            MEDIA_STATE.record("generic_play")
            ACTION_CONTEXT["media_state"] = MEDIA_STATE.status
            return {"status": "completed", "message": "Media playback started.", "context_kind": "desktop_action"}
        if re.fullmatch(r"(forward|forward song|forward music|forward the music|seek forward|skip forward|move forward)", lowered) or re.search(r"\b(forward|seek forward|skip forward|move forward|go forward)\s+(?:by\s+)?(?:ten|10|five|5)?\s*(?:seconds?|sec)?\b", lowered):
            focus_media_window()
            pyautogui.press("right")
            return {"status": "completed", "message": "Moved playback forward.", "context_kind": "desktop_action"}
        if re.fullmatch(r"(backward|backward song|backward music|backward the music|rewind|seek backward|skip backward|move backward)", lowered) or re.search(r"\b(backward|rewind|seek backward|skip backward|move backward|go backward)\s+(?:by\s+)?(?:ten|10|five|5)?\s*(?:seconds?|sec)?\b", lowered):
            focus_media_window()
            pyautogui.press("left")
            return {"status": "completed", "message": "Moved playback back.", "context_kind": "desktop_action"}
        if re.fullmatch(r"(next|skip|next song|skip song|next track|skip track|play next|play next song|play next track)", lowered) or re.search(r"\b(next track|next music|next song|skip track|skip this|skip the song|skip the music|play next|play next song)\b", lowered):
            send_global_media_key(0xB0)
            return {"status": "completed", "message": "Skipped to the next track.", "context_kind": "desktop_action"}
        if re.fullmatch(r"(previous|prev|previous song|last song|previous track|play previous|play previous song|play previous track)", lowered) or re.search(r"\b(previous track|previous music|previous song|last song|play previous|play previous song)\b", lowered):
            send_global_media_key(0xB1)
            return {"status": "completed", "message": "Went back to the previous track.", "context_kind": "desktop_action"}
        if resolution.action == "stop":
            pyautogui.press("stop")
            MEDIA_STATE.record("stop")
            ACTION_CONTEXT["media_state"] = MEDIA_STATE.status
            return {"status": "completed", "message": "Stopped media playback.", "context_kind": "desktop_action"}
        if re.search(r"\b(volume up|increase volume|turn up volume|raise volume|make it louder|louder|sound up|increase sound|turn it up)\b", lowered):
            pyautogui.press("volumeup", presses=3)
            return {"status": "completed", "message": "Volume increased.", "context_kind": "desktop_action"}
        if re.search(r"\b(volume down|decrease volume|turn down volume|lower volume|make it quieter|quieter|sound down|decrease sound|turn it down)\b", lowered):
            pyautogui.press("volumedown", presses=3)
            return {"status": "completed", "message": "Volume decreased.", "context_kind": "desktop_action"}
        if re.search(r"\b(mute|unmute|mute volume|unmute volume|silence audio|turn off sound|turn on sound)\b", lowered):
            pyautogui.press("volumemute")
            return {"status": "completed", "message": "Volume mute toggled.", "context_kind": "desktop_action"}
    except Exception as exc:
        return {"status": "error", "message": f"Media control failed: {type(exc).__name__}", "context_kind": "desktop_action"}
    return None


WINDOWS_APP_ALIASES = {
    "settings": ("Settings", "ms-settings:"),
    "windows settings": ("Settings", "ms-settings:"),
    "calculator": ("Calculator", "calc.exe"),
    "calc": ("Calculator", "calc.exe"),
    "paint": ("Paint", "mspaint.exe"),
    "notepad": ("Notepad", "notepad.exe"),
    "file explorer": ("File Explorer", "explorer.exe"),
    "explorer": ("File Explorer", "explorer.exe"),
    "task manager": ("Task Manager", "taskmgr.exe"),
    "device manager": ("Device Manager", "devmgmt.msc"),
    "control panel": ("Control Panel", "control.exe"),
    "registry editor": ("Registry Editor", "regedit.exe"),
    "regedit": ("Registry Editor", "regedit.exe"),
    "services": ("Services", "services.msc"),
    "powershell": ("PowerShell", "powershell.exe"),
    "command prompt": ("Command Prompt", "cmd.exe"),
    "cmd": ("Command Prompt", "cmd.exe"),
    "snipping tool": ("Snipping Tool", "snippingtool.exe"),
    "chrome": ("Google Chrome", "chrome.exe"),
    "google chrome": ("Google Chrome", "chrome.exe"),
    "edge": ("Microsoft Edge", "msedge.exe"),
    "whatsapp": ("WhatsApp", ""),
    "whats app": ("WhatsApp", ""),
    "vs code": ("Visual Studio Code", "code.exe"),
    "vscode": ("Visual Studio Code", "code.exe"),
    "visual studio code": ("Visual Studio Code", "code.exe"),
    "word": ("Microsoft Word", "winword.exe"),
    "excel": ("Microsoft Excel", "excel.exe"),
    "powerpoint": ("Microsoft PowerPoint", "powerpnt.exe"),
}

SYSTEM_APP_TARGETS = {
    "ms-settings:", "calc.exe", "mspaint.exe", "notepad.exe", "explorer.exe",
    "taskmgr.exe", "devmgmt.msc", "control.exe", "regedit.exe", "services.msc",
    "powershell.exe", "cmd.exe", "snippingtool.exe",
}


def normalize_app_query(value):
    text = re.sub(r"\b(open|launch|start|run|switch|focus|to|close|quit|exit|terminate|kill|please|app|application)\b", " ", str(value or "").lower())
    text = re.sub(r"\b(browser)\b", " ", text)
    text = re.sub(r"[^\w\s.+#-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def focus_running_windows_app(label, target):
    process = os.path.splitext(os.path.basename(str(target or "")))[0]
    script = f"""
$ws = New-Object -ComObject WScript.Shell
if ($ws.AppActivate('{str(label).replace("'", "''")}')) {{ exit 0 }}
if ('{process.replace("'", "''")}' -and $ws.AppActivate('{process.replace("'", "''")}')) {{ exit 0 }}
exit 1
"""
    try:
        completed = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True, text=True, timeout=1)
        return completed.returncode == 0
    except Exception:
        return False


def chrome_profiles():
    user_data = os.path.join(os.getenv("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")), "Google", "Chrome", "User Data")
    try:
        with open(os.path.join(user_data, "Local State"), "r", encoding="utf-8") as handle:
            cache = (json.load(handle).get("profile") or {}).get("info_cache") or {}
    except Exception:
        return []
    return [
        {"directory": directory, "name": str(data.get("name") or directory), "email": str(data.get("user_name") or "")}
        for directory, data in cache.items()
    ]


def parse_chrome_profile_request(command):
    text = re.sub(r"^\s*(?:open|launch|start|switch\s+to)\s+", "", str(command or "").strip(), flags=re.IGNORECASE)
    patterns = (
        r"^(?:google\s+)?chrome\s+(?:with\s+|using\s+)?profile\s+(.+?)(?:\s+in\s+(?:a\s+)?new\s+window)?$",
        r"^(.+?)\s+profile\s+(?:in|on)\s+(?:google\s+)?chrome(?:\s+in\s+(?:a\s+)?new\s+window)?$",
        r"^(?:google\s+)?chrome\s+(?:with|using)\s+(.+?)\s+profile(?:\s+in\s+(?:a\s+)?new\s+window)?$",
    )
    for pattern in patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip(), bool(re.search(r"\bnew\s+window\b", text, re.IGNORECASE))
    return "", False


def launch_chrome_profile(profile_query, force_new=False):
    query = re.sub(r"\s+", " ", str(profile_query or "").lower()).strip()
    profiles = chrome_profiles()
    matches = [profile for profile in profiles if any(query == value or query in value for value in (profile["name"].lower(), profile["email"].lower(), profile["directory"].lower()))]
    if not matches:
        names = ", ".join(profile["name"] for profile in profiles)
        return {"status": "error", "message": f"I could not find that Chrome profile. Available profiles are {names}." if names else "I could not read Chrome profiles on this computer."}
    if len(matches) > 1:
        return {"status": "needs_clarification", "message": "Which Chrome profile did you mean: " + " or ".join(profile["name"] for profile in matches) + "?"}
    profile = matches[0]
    candidates = [
        os.path.join(os.getenv("ProgramFiles", r"C:\Program Files"), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.getenv("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    executable = next((candidate for candidate in candidates if os.path.exists(candidate)), shutil.which("chrome.exe"))
    if not executable:
        return {"status": "error", "message": "I found the Chrome profile, but Chrome is not installed in a standard location."}
    args = [executable, f"--profile-directory={profile['directory']}"]
    if force_new:
        args.append("--new-window")
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"status": "completed", "message": f"Opened the {profile['name']} Chrome profile.", "profile": profile["name"]}
    except Exception:
        return {"status": "error", "message": f"I found the {profile['name']} profile, but Chrome could not open it."}


def launch_windows_target(label, target, focus_existing=True):
    try:
        if focus_existing and target.lower().endswith(".exe") and focus_running_windows_app(label, target):
            return {"status": "completed", "message": f"Switched to {label}.", "focused": True}
        if target.startswith("http"):
            webbrowser.open(target)
        elif target.endswith(":"):
            os.startfile(target)
        else:
            resolved = shutil.which(target)
            if resolved:
                subprocess.Popen([resolved], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                return None
        return {"status": "completed", "message": f"{label} opened."}
    except Exception:
        return None


APP_PROCESS_ALIASES = {
    "google chrome": ["chrome.exe"],
    "chrome": ["chrome.exe"],
    "microsoft edge": ["msedge.exe"],
    "edge": ["msedge.exe"],
    "whatsapp": ["WhatsApp.exe", "WhatsAppApp.exe"],
    "whats app": ["WhatsApp.exe", "WhatsAppApp.exe"],
    "visual studio code": ["Code.exe"],
    "vs code": ["Code.exe"],
    "vscode": ["Code.exe"],
    "word": ["WINWORD.EXE"],
    "microsoft word": ["WINWORD.EXE"],
    "excel": ["EXCEL.EXE"],
    "microsoft excel": ["EXCEL.EXE"],
    "powerpoint": ["POWERPNT.EXE"],
    "power point": ["POWERPNT.EXE"],
    "microsoft powerpoint": ["POWERPNT.EXE"],
    "notepad": ["notepad.exe"],
    "calculator": ["CalculatorApp.exe", "calc.exe"],
    "calc": ["CalculatorApp.exe", "calc.exe"],
    "settings": ["SystemSettings.exe"],
    "windows settings": ["SystemSettings.exe"],
    "file explorer": ["explorer.exe"],
    "explorer": ["explorer.exe"],
    "task manager": ["Taskmgr.exe"],
    "paint": ["mspaint.exe"],
    "command prompt": ["cmd.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe", "pwsh.exe"],
    "spotify": ["Spotify.exe"],
}


def discover_process_names_for_app(query):
    requested = normalize_app_query(query)
    if not requested:
        return []
    if requested in APP_PROCESS_ALIASES:
        return APP_PROCESS_ALIASES[requested]
    if requested in WINDOWS_APP_ALIASES:
        label, target = WINDOWS_APP_ALIASES[requested]
        if target and target.lower().endswith(".exe"):
            return [target]
        return APP_PROCESS_ALIASES.get(label.lower(), [])
    if requested.endswith(".exe"):
        return [requested]
    return [requested.replace(" ", "") + ".exe"]


def close_windows_app(command):
    raw = str(command or "").strip()
    if re.fullmatch(r"(?:close|quit|exit|terminate)", raw, re.IGNORECASE):
        active_target = str(ACTION_CONTEXT.get("last_opened_application") or "").strip()
        if not active_target:
            return {
                "status": "needs_clarification",
                "message": "Which application should I close?",
                "context_kind": "desktop_action",
            }
        raw = f"close {active_target}"
    if not re.match(r"^\s*(close|quit|exit|terminate|kill)\s+.+", raw, re.IGNORECASE):
        return None
    requested = normalize_app_query(raw)
    if not requested:
        return None
    if normalize_spoken_url("open " + requested):
        return None
    processes = discover_process_names_for_app(raw)
    closed = []
    for proc in processes:
        if not proc:
            continue
        proc_name = proc if proc.lower().endswith(".exe") else f"{proc}.exe"
        try:
            completed = subprocess.run(
                ["taskkill", "/IM", proc_name, "/T"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if completed.returncode != 0:
                completed = subprocess.run(
                    ["taskkill", "/F", "/IM", proc_name, "/T"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            if completed.returncode == 0:
                closed.append(proc_name)
        except Exception:
            continue
    if closed:
        ACTION_CONTEXT.pop("last_opened_application", None)
        return {
            "status": "completed",
            "message": f"Closed {requested}.",
            "context_kind": "desktop_action",
            "closed_processes": closed,
        }

    # Last chance: try closing the active app window by title/name.
    script = f"""
$ws = New-Object -ComObject WScript.Shell
if ($ws.AppActivate('{requested.replace("'", "''")}')) {{
  Start-Sleep -Milliseconds 120
  $ws.SendKeys('%{{F4}}')
  exit 0
}}
exit 1
"""
    try:
        completed = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True, text=True, timeout=4)
        if completed.returncode == 0:
            ACTION_CONTEXT.pop("last_opened_application", None)
            return {"status": "completed", "message": f"Closed {requested}.", "context_kind": "desktop_action"}
    except Exception:
        pass

    return {"status": "error", "message": f"I could not close {requested}. It may not be running.", "context_kind": "desktop_action"}


def open_local_shell_target(query):
    text = re.sub(r"^\s*(?:open|show|launch|start|run)\s+", "", str(query or ""), flags=re.IGNORECASE).strip()
    text = re.sub(r"\s+(?:in|with)\s+(?:the\s+)?file\s+explorer\s*$", "", text, flags=re.IGNORECASE).strip()
    lowered = text.lower().strip(" .")
    if lowered in {"recycle bin", "recyclebin", "trash"}:
        target = "shell:RecycleBinFolder"
        label = "Recycle Bin"
    elif lowered in {"file explorer", "explorer", "windows explorer", "this pc", "my computer"}:
        target = "shell:MyComputerFolder"
        label = "File Explorer"
    else:
        folder_names = {
            "downloads": "Downloads", "download": "Downloads",
            "documents": "Documents", "document": "Documents", "my documents": "Documents",
            "desktop": "Desktop", "pictures": "Pictures", "videos": "Videos", "music": "Music",
        }
        folder_key = next((key for key in folder_names if lowered == key or lowered.endswith(f" in {key}") or lowered.endswith(f" from {key}")), "")
        if not folder_key:
            return None
        folder = os.path.join(os.path.expanduser("~"), folder_names[folder_key])
        requested_name = re.sub(rf"\s+(?:in|from)\s+(?:my\s+)?{re.escape(folder_key)}\s*$", "", text, flags=re.IGNORECASE).strip()
        if requested_name.lower() in folder_names:
            requested_name = ""
        if requested_name:
            matches = []
            if os.path.isdir(folder):
                for root, _dirs, files in os.walk(folder):
                    matches.extend(os.path.join(root, name) for name in files if name.lower() == requested_name.lower())
                    if matches:
                        break
                if not matches:
                    for root, _dirs, files in os.walk(folder):
                        matches.extend(os.path.join(root, name) for name in files if requested_name.lower() in name.lower())
                        if matches:
                            break
            if not matches:
                return {"status": "error", "message": f"I could not find {requested_name} in {folder_names[folder_key]}.", "context_kind": "desktop_action"}
            os.startfile(matches[0])
            return {"status": "completed", "message": f"Opened {os.path.basename(matches[0])}.", "context_kind": "desktop_action", "verified": True}
        target = folder
        label = folder_names[folder_key]
    try:
        subprocess.Popen(["explorer.exe", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"status": "completed", "message": f"{label} opened.", "context_kind": "desktop_action", "verified": True}
    except Exception:
        return {"status": "error", "message": f"{label} could not be opened.", "context_kind": "desktop_action", "verified": False}


def discover_and_launch_windows_app(query):
    profile_name, profile_force_new = parse_chrome_profile_request(query)
    if profile_name:
        return launch_chrome_profile(profile_name, profile_force_new)
    force_new = bool(re.search(r"\bnew\s+(?:window|instance|app|application|chrome|notepad|browser)\b", str(query or ""), re.IGNORECASE))
    cleaned_query = str(query or "")
    if force_new:
        cleaned_query = re.sub(r"\b(?:a\s+)?new\s+", " ", cleaned_query, count=1, flags=re.IGNORECASE)
        cleaned_query = re.sub(r"\s+(?:window|instance)\s*$", " ", cleaned_query, flags=re.IGNORECASE)
    local_shell = open_local_shell_target(cleaned_query)
    if local_shell:
        return local_shell
    requested = normalize_app_query(cleaned_query)
    if not requested:
        return None
    if requested in {"recycle bin", "recyclebin", "trash"}:
        try:
            subprocess.Popen(
                ["explorer.exe", "shell:RecycleBinFolder"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {"status": "completed", "message": "Recycle Bin opened."}
        except Exception:
            return {"status": "error", "message": "Recycle Bin could not be opened."}
    if requested in WINDOWS_APP_ALIASES:
        label, target = WINDOWS_APP_ALIASES[requested]
        if target:
            launched = launch_windows_target(label, target, focus_existing=not force_new)
            if launched:
                return launched
        requested = label.lower()

    script = f"""
$q='{requested.replace("'", "''")}'
$allApps=Get-StartApps
$exact=$allApps | Where-Object {{ $_.Name.ToLower() -eq $q }} | Select-Object -First 1
if($exact) {{ Write-Output ('UWP:' + $exact.Name + '|' + $exact.AppID); exit 0 }}
$apps=$allApps | Where-Object {{ $_.Name.ToLower().Contains($q) }} | Select-Object -First 4
if($apps.Count -gt 1) {{ $apps | ForEach-Object {{ Write-Output ('AMBIG:' + $_.Name) }}; exit 2 }}
if($apps.Count -eq 1) {{ Write-Output ('UWP:' + $apps[0].Name + '|' + $apps[0].AppID); exit 0 }}
$pf86=[Environment]::GetFolderPath('ProgramFilesX86')
$roots=@(
  "$env:ProgramData\\Microsoft\\Windows\\Start Menu\\Programs",
  "$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs",
  "$env:USERPROFILE\\Desktop",
  "$env:PUBLIC\\Desktop",
  "$env:ProgramFiles",
  "$pf86",
  "$env:LOCALAPPDATA\\Programs"
)
foreach($root in $roots) {{
  if(Test-Path $root) {{
    $lnk=Get-ChildItem $root -Recurse -Filter *.lnk -ErrorAction SilentlyContinue | Where-Object {{ $_.BaseName.ToLower() -eq $q -or $_.BaseName.ToLower().Contains($q) }} | Select-Object -First 1
    if($lnk) {{ Write-Output ('LNK:' + $lnk.BaseName + '|' + $lnk.FullName); exit 0 }}
    $exe=Get-ChildItem $root -Recurse -Filter *.exe -ErrorAction SilentlyContinue | Where-Object {{ $_.BaseName.ToLower() -eq $q -or $_.BaseName.ToLower().Contains($q) }} | Select-Object -First 1
    if($exe) {{ Write-Output ('EXE:' + $exe.BaseName + '|' + $exe.FullName); exit 0 }}
  }}
}}
$regRoots=@(
  'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\*',
  'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\*',
  'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
  'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
  'HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*'
)
foreach($reg in $regRoots) {{
  try {{
    $item=Get-ItemProperty $reg -ErrorAction SilentlyContinue | Where-Object {{
      ($_.DisplayName -and $_.DisplayName.ToLower().Contains($q)) -or ($_.PSChildName -and $_.PSChildName.ToLower().Contains($q))
    }} | Select-Object -First 1
    if($item) {{
      $name=$item.DisplayName
      if(-not $name) {{ $name=$item.PSChildName -replace '\\.exe$','' }}
      $target=$item.DisplayIcon
      if(-not $target) {{ $target=$item.'(default)' }}
      if($target) {{
        $target=($target -split ',')[0].Trim('"')
        Write-Output ('EXE:' + $name + '|' + $target)
        exit 0
      }}
    }}
  }} catch {{}}
}}
exit 1
"""
    try:
        completed = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True, text=True, timeout=8)
        output = (completed.stdout or "").strip().splitlines()
        if completed.returncode == 2 and output:
            names = [line.replace("AMBIG:", "", 1) for line in output if line.startswith("AMBIG:")]
            return {"status": "needs_clarification", "message": "I found multiple apps: " + ", ".join(names[:4]), "matches": [{"name": name} for name in names[:4]]}
        if output:
            line = output[0]
            if line.startswith("UWP:"):
                label, app_id = line.replace("UWP:", "", 1).split("|", 1)
                if not force_new and focus_running_windows_app(label, ""):
                    return {"status": "completed", "message": f"Switched to {label}.", "focused": True}
                subprocess.Popen(f'start "" "shell:AppsFolder\\{app_id}"', shell=True)
                return {"status": "completed", "message": f"{label} opened."}
            if line.startswith("LNK:"):
                label, shortcut = line.replace("LNK:", "", 1).split("|", 1)
                if not force_new and focus_running_windows_app(label, ""):
                    return {"status": "completed", "message": f"Switched to {label}.", "focused": True}
                os.startfile(shortcut)
                return {"status": "completed", "message": f"{label} opened."}
            if line.startswith("EXE:"):
                label, executable = line.replace("EXE:", "", 1).split("|", 1)
                if not force_new and focus_running_windows_app(label, executable):
                    return {"status": "completed", "message": f"Switched to {label}.", "focused": True}
                subprocess.Popen(f'start "" "{executable}"', shell=True)
                return {"status": "completed", "message": f"{label} opened."}
    except Exception:
        pass

    return None


def summarize_vision_result(result, analysis_type="comprehensive"):
    if not isinstance(result, dict):
        return "Vision analysis finished."
    if result.get("error"):
        return f"Vision failed: {result['error']}"
    text_data = result.get("text_analysis") or {}
    face_data = result.get("face_analysis") or {}
    object_data = result.get("object_analysis") or {}
    extracted = str(text_data.get("extracted_text") or "").strip()
    if analysis_type == "text":
        if extracted:
            return f"I read this text from the screen:\n{extracted[:1800]}"
        return "I captured the screen, but I could not find readable text."
    if analysis_type == "faces":
        return f"Detected {face_data.get('face_count', 0)} face(s)."
    if analysis_type == "objects":
        objects = object_data.get("objects") or []
        names = []
        for item in objects[:8]:
            names.append(str(item.get("type") or item.get("name") or "object"))
        return f"Detected objects: {', '.join(names)}." if names else "I did not detect clear objects."
    parts = []
    if extracted:
        parts.append(f"Text found: {extracted[:900]}")
    if "face_count" in face_data:
        parts.append(f"Faces: {face_data.get('face_count', 0)}")
    if "object_count" in object_data:
        parts.append(f"Objects: {object_data.get('object_count', 0)}")
    path_value = result.get("file_path")
    if path_value:
        parts.append(f"Captured image: {path_value}")
    return "\n".join(parts) if parts else "Screen captured and analyzed."


def handle_screenshot_command(command):
    lowered = str(command or "").lower()
    if not re.search(r"\b(?:take|capture|save|grab)\b.*\b(?:screen\s*shot|screenshot|screen)\b|\b(?:screen\s*shot|screenshot)\b", lowered):
        return None
    try:
        folder = os.path.join(os.path.expanduser("~"), "Pictures", "CEASER Screenshots")
        os.makedirs(folder, exist_ok=True)
        filename = f"ceaser-screenshot-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
        path_value = os.path.join(folder, filename)
        try:
            import pyautogui
            image = pyautogui.screenshot()
            image.save(path_value)
        except Exception:
            from PIL import ImageGrab
            image = ImageGrab.grab()
            image.save(path_value)
        return {
            "status": "completed",
            "message": f"Screenshot saved to {path_value}",
            "path": path_value,
            "context_kind": "screenshot",
        }
    except Exception as exc:
        return {"status": "error", "message": f"I could not take the screenshot: {type(exc).__name__}"}


def handle_vision_command(command):
    lowered = str(command or "").lower()
    is_vision_request = re.search(
        r"\b(ocr|read|scan|extract|copy)\b.*\b(screen|screenshot|image|visible text|text)\b"
        r"|\b(read my screen|scan my screen|extract text|screen ocr)\b"
        r"|\b(analyze|analyse|describe|explain|what is on|what's on|understand)\b.*\b(screen|screenshot|image|window)\b"
        r"|\b(screen info|display info|screen information|display information)\b",
        lowered,
    )
    if not is_vision_request:
        return None
    try:
        if "screen info" in lowered or "display info" in lowered or "screen information" in lowered:
            info = get_legacy_assistant().vision.get_screen_info()
            if info.get("error"):
                return {"status": "error", "message": f"Screen info failed: {info['error']}"}
            return {
                "status": "completed",
                "message": f"Screen size: {info.get('screen_width')}x{info.get('screen_height')}. Mouse position: {info.get('mouse_position')}. Open windows: {len(info.get('available_windows') or [])}.",
                "vision": info,
            }
        analysis_type = "text" if any(word in lowered for word in ("ocr", "read text", "extract text", "scan text", "read my screen")) else "comprehensive"
        if "face" in lowered:
            analysis_type = "faces"
        elif "object" in lowered:
            analysis_type = "objects"
        result = get_legacy_assistant().vision.capture_screen_and_analyze(analysis_type)
        message = summarize_vision_result(result, analysis_type)
        return {
            "status": "completed" if not result.get("error") else "error",
            "message": message,
            "vision": result,
            "path": result.get("file_path", ""),
        }
    except Exception as exc:
        return {"status": "error", "message": f"Vision command failed: {type(exc).__name__}"}


def handle_follow_up_action(command):
    lowered = str(command or "").lower().strip()
    if not lowered:
        return None

    capture = ACTION_CONTEXT.get("smart_capture") or {}
    if capture.get("text") and re.search(r"\b(this|it|file|document|page|section|summary|summarize|summarise|explain|simplify|translate|questions|quiz|timeline|topics|action items|deadline|date|people)\b", lowered):
        file_name = (capture.get("file") or {}).get("name", "the captured file")
        prompt = (
            f"The user is asking a follow-up about the Smart Capture file: {file_name}.\n"
            "Answer only from this captured file where possible. If the requested page/section is not available, say what is available.\n\n"
            f"User follow-up: {command}\n\n"
            f"Previous analysis:\n{capture.get('analysis', '')[:5000]}\n\n"
            f"Captured text:\n{capture.get('text', '')[:14000]}"
        )
        message = call_ceaser_backend_chat(prompt, already_wrapped=True) or summarize_capture_locally(capture.get("file") or {}, capture.get("text") or "")
        remember_result(command, message, "smart_capture", (capture.get("file") or {}).get("path", ""))
        return {"status": "completed", "message": message, "context_kind": "smart_capture"}

    wants_previous = re.search(
        r"\b(it|that|this|previous|last)\b|\b(the email|the document|the draft|draft)\b",
        lowered,
    )
    if wants_previous and not context_is_recent():
        return {"status": "needs_context", "message": "I need something to work with first."}

    if any(phrase in lowered for phrase in ("copy it", "copy that", "copy this", "copy previous", "copy the email", "copy the document")):
        copy_to_clipboard(ACTION_CONTEXT["last_response"])
        return {"status": "completed", "message": "Copied the last CEASER output."}

    if ("gmail" in lowered or "mail" in lowered) and any(word in lowered for word in ("draft", "compose", "add it", "put it", "open")):
        body = ACTION_CONTEXT.get("last_response", "") if context_is_recent() else ""
        copy_to_clipboard(body)
        url = "https://mail.google.com/mail/?view=cm&fs=1"
        if body:
            url += "&body=" + quote(body[:6000])
        webbrowser.open(url)
        return {"status": "completed", "message": "Opened Gmail compose and copied the draft text."}

    if any(phrase in lowered for phrase in ("save it", "save that", "save this", "make file", "create file")):
        ext = ".md" if "markdown" in lowered or "md" in lowered else ".txt"
        path = save_last_result(ext)
        if path:
            return {"status": "completed", "message": f"Saved it to {path}", "path": path}

    if any(phrase in lowered for phrase in ("open it", "open that", "open the file", "show it", "show the file")):
        if open_path(ACTION_CONTEXT.get("last_created_path", "")):
            return {"status": "completed", "message": "Opened the saved file."}

    if any(phrase in lowered for phrase in ("make it table", "make it a table", "turn it into table", "create table", "table format")):
        prompt = "Convert the previous CEASER output into a clean markdown table where possible. Keep it concise.\n\nPrevious output:\n" + ACTION_CONTEXT["last_response"]
        message = call_ceaser_backend_chat(prompt) or "I could not convert it into a table right now."
        return {"status": "completed", "message": message}

    if any(phrase in lowered for phrase in ("make it list", "turn it into list", "checklist", "make checklist", "create checklist")):
        prompt = "Convert the previous CEASER output into a clear checklist. Keep it practical.\n\nPrevious output:\n" + ACTION_CONTEXT["last_response"]
        message = call_ceaser_backend_chat(prompt) or "I could not convert it into a checklist right now."
        return {"status": "completed", "message": message}

    if any(phrase in lowered for phrase in ("make chart", "create chart", "show chart", "pie chart", "bar chart", "graph")):
        prompt = "Create chart-ready data from the previous CEASER output. If values exist, return labels and values. If not, explain what values are needed.\n\nPrevious output:\n" + ACTION_CONTEXT["last_response"]
        message = call_ceaser_backend_chat(prompt) or "I prepared the chart request, but I need numeric values to draw a chart."
        return {"status": "completed", "message": message}

    if any(phrase in lowered for phrase in ("summarize it", "summarise it", "summarize this", "summarise this", "brief it", "make it brief", "explain briefly")):
        prompt = "Summarize the previous CEASER output briefly in simple language.\n\nPrevious output:\n" + ACTION_CONTEXT["last_response"]
        message = call_ceaser_backend_chat(prompt) or ACTION_CONTEXT["last_response"][:700]
        return {"status": "completed", "message": message}

    if any(phrase in lowered for phrase in ("brief me more", "explain more", "more details", "explain in detail", "expand it")):
        prompt = "Expand the previous CEASER output with more useful detail, examples, and practical explanation.\n\nPrevious output:\n" + ACTION_CONTEXT["last_response"]
        message = call_ceaser_backend_chat(prompt) or "I need the CEASER backend connection to expand that properly."
        return {"status": "completed", "message": message}

    if ("word" in lowered or "document" in lowered) and any(word in lowered for word in ("add", "paste", "put", "open")):
        copy_to_clipboard(ACTION_CONTEXT["last_response"])
        try:
            get_legacy_assistant().DeviceControl.open_app("winword")
        except Exception:
            webbrowser.open("ms-word:")
        return {"status": "completed", "message": "Opened Word and copied the content for pasting."}

    return None


def is_email_generation_command(command):
    text = str(command or "").lower().strip()
    return bool(
        re.search(r"\b(write|draft|generate|create|compose|prepare|make|send)\b.*\b(email|mail|gmail|message|letter)\b", text)
        or re.search(r"\b(email|mail|message|letter)\b.*\b(write|draft|generate|create|compose|prepare|make|send)\b", text)
    )


def build_email_prompt(command):
    details = parse_email_request(command)
    recipient = details.get("recipient") or "the recipient"
    topic = details.get("topic") or "the requested topic"
    word_count = details.get("word_count")
    length_rule = f"Target length: about {word_count} words.\n" if word_count else "Use enough detail to be useful, normally 120-180 words unless the request implies otherwise.\n"
    return (
        "You are a professional correspondence composer for the CEASER desktop overlay.\n"
        "Return ONLY the final message text. Do not return JSON. Do not mention agents, Friday, structured responses, validation, or schemas.\n"
        "Do not ask for more context. Use professional neutral placeholders only where truly needed.\n"
        f"Recipient: {recipient}\n"
        f"Topic/request: {topic}\n"
        f"{length_rule}"
        "Format exactly like this:\n\n"
        "Subject: ...\n\n"
        "Dear ...,\n\n"
        "...\n\n"
        "Regards,\n"
        "[Sender Name]"
    )


def parse_email_request(command):
    text = str(command or "").strip()
    cleaned = text
    word_count = None
    count_match = re.search(r"\b(?:in|around|about|approximately)?\s*(\d{2,4})\s*words?\b", cleaned, flags=re.IGNORECASE)
    if count_match:
        try:
            word_count = int(count_match.group(1))
        except ValueError:
            word_count = None
        cleaned = (cleaned[:count_match.start()] + cleaned[count_match.end():]).strip()
    recipient = ""
    match = re.search(r"\b(?:to|for)\s+([A-Z][A-Za-z0-9._-]+|[a-z][a-z0-9._-]+)", text)
    if match:
        recipient = match.group(1).strip().title()
    topic = cleaned
    topic = re.sub(r"\b(write|draft|generate|create|compose|prepare|make)\b", "", topic, flags=re.IGNORECASE)
    topic = re.sub(r"\b(an|a)?\s*(email|mail|gmail)\b", "", topic, flags=re.IGNORECASE)
    topic = re.sub(r"\b(to|for)\s+[A-Za-z0-9._-]+", "", topic, flags=re.IGNORECASE)
    topic = re.sub(r"^\s*(about|regarding|for|on)\s+", "", topic, flags=re.IGNORECASE)
    topic = topic.strip(" ,.-") or "the requested update"
    return {"recipient": recipient, "topic": topic, "word_count": word_count}


def fallback_email_draft(command):
    details = parse_email_request(command)
    recipient = details.get("recipient") or "there"
    topic = details.get("topic") or "the requested update"
    word_count = details.get("word_count")
    subject = topic[:1].upper() + topic[1:]
    if word_count and word_count >= 120:
        body = (
            f"I hope you are doing well.\n\n"
            f"I wanted to share a detailed note regarding {topic}. This topic is important because it connects current progress, future planning, and the decisions we need to make with clarity. "
            f"The main idea is to present the subject in a simple, useful, and professional way so that everyone involved can understand the context and respond with confidence.\n\n"
            f"In relation to {topic}, I would like to highlight that we should focus on the key purpose, the expected outcome, and the next practical steps. "
            f"If there are any specific requirements, timelines, or changes needed, please share them so they can be included before the final version is sent or acted upon.\n\n"
            f"Please review this and let me know your thoughts. I would be happy to make any updates based on your feedback."
        )
    else:
        body = (
            f"I hope you are doing well.\n\n"
            f"I wanted to share an update regarding {topic}. Please review this and let me know if you would like any changes or additional details.\n\n"
            "Thank you."
        )
    return (
        f"Subject: {subject}\n\n"
        f"Dear {recipient},\n\n"
        f"{body}\n\n"
        "Regards,\n"
        "[Your Name]"
    )


SMART_CAPTURE_EXTENSIONS = {
    ".pdf": "PDF",
    ".docx": "Word Document",
    ".doc": "Word Document",
    ".pptx": "PowerPoint",
    ".ppt": "PowerPoint",
    ".xlsx": "Excel Spreadsheet",
    ".xls": "Excel Spreadsheet",
    ".csv": "CSV Spreadsheet",
    ".txt": "Text Document",
    ".md": "Markdown Document",
    ".json": "JSON File",
    ".xml": "XML File",
    ".png": "Image",
    ".jpg": "Image",
    ".jpeg": "Image",
    ".gif": "Image",
    ".bmp": "Image",
    ".webp": "Image",
    ".zip": "ZIP Archive",
}


def smart_capture_progress(stage, file_path="", progress=0):
    emit({
        "id": "voice_status",
        "status": "capture_progress",
        "stage": stage,
        "file": os.path.basename(file_path) if file_path else "",
        "progress": progress,
    })


def detect_smart_capture_file(file_path):
    ext = os.path.splitext(str(file_path or ""))[1].lower()
    label = SMART_CAPTURE_EXTENSIONS.get(ext, "File")
    size = 0
    try:
        size = os.path.getsize(file_path)
    except Exception:
        pass
    return {
        "name": os.path.basename(file_path),
        "path": file_path,
        "extension": ext,
        "type": label,
        "size": size,
        "estimated_seconds": 4 if size < 6_000_000 else 8,
    }


def extract_pptx_text(file_path):
    try:
        slides = []
        with zipfile.ZipFile(file_path) as archive:
            names = sorted(
                [name for name in archive.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)],
                key=lambda value: int(re.search(r"slide(\d+)\.xml", value).group(1)),
            )
            for index, name in enumerate(names, start=1):
                xml_data = archive.read(name)
                root = ET.fromstring(xml_data)
                texts = []
                for node in root.iter():
                    if node.tag.endswith("}t") and node.text:
                        texts.append(node.text.strip())
                if texts:
                    slides.append(f"Slide {index}: " + " ".join(texts))
        return "\n".join(slides)
    except Exception:
        return "PowerPoint text could not be extracted."


def parse_smart_capture_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    with open(file_path, "rb") as handle:
        content = handle.read()
    if ext == ".pptx":
        return extract_pptx_text(file_path)
    if ext == ".zip":
        try:
            with zipfile.ZipFile(file_path) as archive:
                names = archive.namelist()[:80]
            return "ZIP archive contents:\n" + "\n".join(f"- {name}" for name in names)
        except Exception:
            return "ZIP archive could not be read."
    try:
        from features.ceaser.predictions.file_parser import FileParser
        parsed = FileParser().parse_content(content, os.path.basename(file_path))
    except Exception:
        try:
            parsed = content.decode("utf-8", errors="ignore")
        except Exception:
            parsed = f"Binary file, {len(content)} bytes."
    if isinstance(parsed, dict):
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    return str(parsed or "").strip()


def build_capture_prompt(metadata, extracted_text):
    preview = str(extracted_text or "").strip()
    if len(preview) > 14000:
        preview = preview[:14000] + "\n\n[Content truncated for desktop analysis.]"
    return (
        "You are CEASER Smart Capture. Analyze this dropped file for the desktop overlay.\n"
        "Return a useful, concise analysis with: summary, key topics, important dates, people/entities, action items, and questions the user can ask next. "
        "If extraction is weak, say what was detected and what may be missing. Do not mention OCR unless the file is an image or scanned document.\n\n"
        f"File name: {metadata.get('name')}\n"
        f"File type: {metadata.get('type')}\n"
        f"Extension: {metadata.get('extension')}\n\n"
        f"Extracted content:\n{preview}"
    )


def summarize_capture_locally(metadata, extracted_text):
    text = str(extracted_text or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9._%+-]*", text)
    people = []
    for match in re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", text):
        if match not in people and len(people) < 8:
            people.append(match)
    dates = re.findall(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b", text, flags=re.I)[:8]
    top_lines = lines[:5]
    return (
        f"{metadata.get('name')} analyzed.\n\n"
        f"Summary:\n" + ("\n".join(f"- {line[:180]}" for line in top_lines) if top_lines else "- No readable text was extracted.") + "\n\n"
        f"Key facts:\n- Type: {metadata.get('type')}\n- Words detected: {len(words)}\n"
        + (f"- Important dates: {', '.join(dates)}\n" if dates else "")
        + (f"- People/entities: {', '.join(people)}\n" if people else "")
        + "\nNext actions:\n- Ask for a summary\n- Ask questions\n- Create notes\n- Extract action items"
    )


def analyze_smart_capture_file(file_path):
    path_value = os.path.abspath(str(file_path or "").strip())
    if not path_value or not os.path.exists(path_value):
        return {"status": "error", "message": "I could not find that file.", "context_kind": "smart_capture"}
    metadata = detect_smart_capture_file(path_value)
    ext = metadata["extension"]
    if ext not in SMART_CAPTURE_EXTENSIONS:
        return {"status": "error", "message": f"{metadata['name']} is not supported for Smart Capture yet.", "context_kind": "smart_capture", "file": metadata}
    smart_capture_progress("Reading file", path_value, 18)
    extracted = parse_smart_capture_file(path_value)
    smart_capture_progress("Understanding structure", path_value, 42)
    if not extracted or extracted.lower().startswith(("pdf content (requires", "docx content (requires", "image content (requires")):
        message = summarize_capture_locally(metadata, extracted)
    else:
        smart_capture_progress("Generating insights", path_value, 72)
        message = call_ceaser_backend_chat(build_capture_prompt(metadata, extracted), already_wrapped=True) or summarize_capture_locally(metadata, extracted)
    smart_capture_progress("Ready", path_value, 100)
    ACTION_CONTEXT["smart_capture"] = {
        "file": metadata,
        "text": str(extracted or "")[:30000],
        "analysis": message,
        "updated_at": time.time(),
    }
    remember_result(f"analyze {metadata['name']}", message, "smart_capture", path_value)
    return {
        "status": "completed",
        "message": message,
        "context_kind": "smart_capture",
        "file": metadata,
        "capture": {
            "summary": message,
            "text_chars": len(str(extracted or "")),
            "actions": ["Summary", "Topics", "Questions", "Timeline", "Explain", "Translate"],
        },
    }


def handle_email_generation_command(command):
    if not is_email_generation_command(command):
        return None
    prompt = build_email_prompt(command)
    message = call_ceaser_backend_chat(prompt, already_wrapped=True)
    invalid_markers = (
        "structured response unavailable",
        "could not be validated as structured data",
        "response was not valid json",
        "regenerate the response",
    )
    if message and any(marker in message.lower() for marker in invalid_markers):
        message = fallback_email_draft(command)
    if not message:
        if ACTION_CONTEXT.get("backend_auth_error") == "401":
            return {
                "status": "error",
                "message": "Your desktop session expired. Please reconnect CEASER from the web console.",
                "context_kind": "auth",
            }
        message = fallback_email_draft(command)
    remember_result(command, message, "email")
    return {"status": "completed", "message": message, "context_kind": "email"}


LOCAL_COMMAND_PATTERN = re.compile(
    r"\b(open|launch|start|run|visit|browse|close|quit|exit|play|pause|resume|continue|stop|next|skip|previous|back|"
    r"screenshot|screen\s*shot|capture|volume|mute|unmute|settings|calculator|notepad|"
    r"chrome|edge|whatsapp|word|excel|powerpoint|vs\s*code|visual\s+studio\s+code|"
    r"youtube|facebook|gmail|browser|website|site|tab|folder|file|clipboard|copy|paste|lock|shutdown|restart|sleep|window|screen|ocr|profile|account|projects?)\b",
    re.IGNORECASE,
)

AI_COMMAND_PATTERN = re.compile(
    r"\b(explain|tell me|what is|what's|who is|why|how|write|draft|create|generate|"
    r"summarize|summarise|research|compare|plan|make a report|make an email|"
    r"prepare|brief|teach|translate|define|what do you think|do you think|your opinion|"
    r"your thoughts|thoughts on|talk about|discuss|describe)\b",
    re.IGNORECASE,
)


def should_use_ai(command):
    text = str(command or "").strip()
    if not text:
        return False
    if LOCAL_COMMAND_PATTERN.search(text) and not AI_COMMAND_PATTERN.search(text):
        return False
    words = text.split()
    return bool(AI_COMMAND_PATTERN.search(text) or text.endswith("?") or len(words) >= 2)


def execute_single_step(command):
    pending = ACTION_CONTEXT.get("pending_selection") or {}
    if pending and float(pending.get("expires_at") or 0) < time.time():
        ACTION_CONTEXT.pop("pending_selection", None)
        pending = {}
    if pending and pending.get("kind") == "application":
        choice = str(command or "").strip()
        options = [str(item.get("name") or "").strip() for item in pending.get("matches") or []]
        ordinal = {"first": 0, "one": 0, "1": 0, "second": 1, "two": 1, "2": 1, "third": 2, "three": 2, "3": 2, "fourth": 3, "four": 3, "4": 3}.get(choice.lower())
        selected = options[ordinal] if ordinal is not None and ordinal < len(options) else next(
            (item for item in options if choice.lower() == item.lower() or choice.lower() in item.lower()), ""
        )
        if selected:
            ACTION_CONTEXT.pop("pending_selection", None)
            command = f"open {selected}"

    email_result = handle_email_generation_command(command)
    if email_result:
        return email_result

    follow_up = handle_follow_up_action(command)
    if follow_up:
        return follow_up

    account_result = handle_account_command(command)
    if account_result:
        remember_result(command, account_result.get("message", ""), "account")
        return account_result

    projects_result = handle_projects_command(command)
    if projects_result:
        remember_result(command, projects_result.get("message", ""), "projects")
        return projects_result

    battery_result = handle_battery_command(command)
    if battery_result:
        remember_result(command, battery_result.get("message", ""), "desktop_action")
        return battery_result

    volume_result = handle_volume_command(command)
    if volume_result:
        remember_result(command, volume_result.get("message", ""), "desktop_action")
        return volume_result

    google_result = handle_google_search_command(command)
    if google_result:
        remember_result(command, google_result.get("message", ""), "desktop_action")
        return google_result

    news_result = handle_news_command(command)
    if news_result:
        remember_result(command, news_result.get("message", ""), "news")
        return news_result

    weather_result = handle_weather_command(command)
    if weather_result:
        remember_result(command, weather_result.get("message", ""), "weather")
        return weather_result

    cloud_result = execute_cloud_command(command, context={"current_user_id": CURRENT_USER_ID})
    if cloud_result:
        remember_result(command, cloud_result.get("message", ""), "cloud")
        if cloud_result.get("error_code") in ("auth_required", "revoked"):
            ACTION_CONTEXT["backend_auth_error"] = "401"
        return cloud_result

    system_result = handle_system_command(command)
    if system_result:
        remember_result(command, system_result.get("message", ""), "desktop_action")
        return system_result

    screenshot_result = handle_screenshot_command(command)
    if screenshot_result:
        remember_result(command, screenshot_result.get("message", ""), "screenshot", screenshot_result.get("path", ""))
        return screenshot_result

    vision_result = handle_vision_command(command)
    if vision_result:
        remember_result(command, vision_result.get("message", ""), "vision", vision_result.get("path", ""))
        return vision_result

    music_result = handle_music_command(command)
    if music_result:
        remember_result(command, music_result.get("message", ""), "music")
        return music_result

    if re.search(r"\b(refresh|rebuild|update|rescan|scan)\s+(apps|applications|app list|application list)\b", str(command or ""), re.IGNORECASE):
        return {"status": "completed", "message": "Application discovery is refreshed automatically by the desktop companion. Try opening the app again now."}

    url_result = handle_open_url_command(command)
    if url_result:
        remember_result(command, url_result.get("message", "Website opened."), "desktop_action")
        return url_result

    close_url_result = handle_close_url_command(command)
    if close_url_result:
        remember_result(command, close_url_result.get("message", "Browser tab closed."), "desktop_action")
        return close_url_result

    close_app_result = close_windows_app(command)
    if close_app_result:
        remember_result(command, close_app_result.get("message", "App closed."), "desktop_action")
        return close_app_result

    if re.match(r"^\s*(open|launch|start|run|switch\s+to|focus)\s+.+", str(command or ""), re.IGNORECASE):
        launched_app = discover_and_launch_windows_app(command)
        if launched_app:
            if launched_app.get("status") == "needs_clarification" and launched_app.get("matches"):
                ACTION_CONTEXT["pending_selection"] = {
                    "kind": "application",
                    "matches": launched_app["matches"],
                    "expires_at": time.time() + 40,
                }
            ACTION_CONTEXT["last_opened_application"] = normalize_app_query(command)
            remember_result(command, launched_app.get("message", "App opened."), "desktop_action")
            return launched_app
        requested_app = normalize_app_query(command)
        return {
            "status": "error",
            "message": f"I could not find {requested_app}. Say refresh apps, then try again.",
            "context_kind": "desktop_action",
        }

    if LOCAL_COMMAND_PATTERN.search(str(command or "")) and not AI_COMMAND_PATTERN.search(str(command or "")):
        return {
            "status": "error",
            "message": "I could not match that desktop command. Try saying it more directly.",
            "context_kind": "desktop_action",
        }

    if should_use_ai(command):
        message = call_ceaser_backend_chat(command)
        if not message:
            if ACTION_CONTEXT.get("backend_auth_error") == "401":
                return {
                    "status": "error",
                    "message": "Your desktop session expired. Please reconnect CEASER from the web console.",
                    "context_kind": "auth",
                }
            if ACTION_CONTEXT.get("backend_auth_error") == "missing_session":
                return {
                    "status": "error",
                    "message": "Connect your CEASER account to use AI answers. Local desktop controls are still available.",
                    "context_kind": "auth",
                }
            return {
                "status": "error",
                "message": "AI response is unavailable right now. Check the backend connection.",
                "context_kind": "answer",
            }
    else:
        # Do not hand normal production traffic to the copied reference
        # assistant. Its broad command map contains unfinished features that
        # are not registered or verified in the current capability system.
        return {
            "status": "error",
            "message": "I could not match that CEASER capability yet. Try a supported desktop action or ask CEASER a question.",
            "context_kind": "unsupported_command",
            "error_code": "unsupported_capability",
        }
    remember_result(command, message)
    return {"status": "completed", "message": message}


def execute_text_legacy(text):
    command = normalize_spoken_command(text)
    if not command:
        return {"status": "empty", "transcript": "", "message": "No command heard."}
    started = time.perf_counter()
    try:
        emit({"id": "voice_status", "status": "executing", "command": command})
        steps = split_command_steps(command)
        results = []
        final_status = "completed"
        last_outcome = {}
        for step in steps:
            outcome = execute_single_step(step)
            last_outcome = outcome
            status = str(outcome.get("status") or "completed")
            if status in ("error", "needs_context", "needs_clarification", "empty"):
                final_status = status
            if outcome.get("path"):
                ACTION_CONTEXT["last_created_path"] = outcome["path"]
            results.append(outcome.get("message") or "")
        message = results[-1] if results else "Done."
        return {
            "status": final_status,
            "transcript": command,
            "message": message,
            "steps": len(steps),
            "matches": last_outcome.get("matches", []),
            "context_kind": ACTION_CONTEXT.get("last_kind", ""),
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
    except Exception as exc:
        return {
            "status": "error",
            "transcript": command,
            "message": "I could not complete that command.",
            "error": type(exc).__name__,
        }


def get_command_service():
    global COMMAND_SERVICE
    with COMMAND_SERVICE_LOCK:
        if COMMAND_SERVICE is None:
            started = time.perf_counter()
            from core.command_service import CommandService
            COMMAND_SERVICE = CommandService(legacy_handler=execute_single_step)
            sys.stderr.write(f"[CEASER Startup] command_service_ready elapsed_ms={int((time.perf_counter() - started) * 1000)}\n")
            sys.stderr.flush()
    return COMMAND_SERVICE


def _proactive_generator(instructions, payload):
    return call_ceaser_backend_chat(f"{instructions}\n\nStructured context:\n{payload}", already_wrapped=True)


def _proactive_context():
    user = dict(ACTION_CONTEXT.get("current_user") or {})
    stored_preferences = COMMAND_SERVICE.long_term_memory.companion_preferences(CURRENT_USER_ID or "") if COMMAND_SERVICE else {}
    preferences = dict(user.get("companion_preferences") or ACTION_CONTEXT.get("companion_preferences") or stored_preferences or {})
    session = COMMAND_SERVICE.context_resolver.session_manager.get("desktop_session", CURRENT_USER_ID or "").snapshot() if COMMAND_SERVICE else {}
    return {
        "companion_preferences": preferences,
        "active_voice_conversation": VOICE_CONTROLLER.state in {"speaking", "command_listening", "follow_up_listening", "executing"},
        "do_not_disturb": bool(ACTION_CONTEXT.get("do_not_disturb")),
        "active_meeting": bool(ACTION_CONTEXT.get("active_meeting")),
        "session_mode": ACTION_CONTEXT.get("session_mode", ""),
        "conversation_state": session.get("conversation_state") or {},
        "recent_topic": (session.get("conversation_state") or {}).get("current_topic") or "",
        "recent_turns": (session.get("recent_turns") or [])[-6:],
    }


def _deliver_proactive(payload):
    emit_v2_event("proactive_message", payload)


def start_proactive_runtime():
    global PROACTIVE_RUNTIME_THREAD
    if PROACTIVE_RUNTIME_THREAD and PROACTIVE_RUNTIME_THREAD.is_alive():
        return

    def run():
        delay = max(0.0, float(os.getenv("CEASER_PROACTIVE_START_DELAY_SECONDS", "15")))
        if PROACTIVE_RUNTIME_STOP.wait(delay):
            return
        service = get_command_service()
        service.configure_proactive_runtime(
            delivery=_deliver_proactive,
            generator=_proactive_generator,
            user_id_provider=lambda: CURRENT_USER_ID or "",
            context_provider=_proactive_context,
            thread_recorder=lambda payload: service.record_proactive_thread(CURRENT_USER_ID or "", payload),
        )
        service.start_awareness_producers()
        sys.stderr.write("[CEASER Proactive] runtime_started workers=1\n")
        sys.stderr.flush()
        while not PROACTIVE_RUNTIME_STOP.wait(5):
            service.poll_awareness_producers(_proactive_context())
        service.stop_awareness_producers()

    PROACTIVE_RUNTIME_STOP.clear()
    PROACTIVE_RUNTIME_THREAD = threading.Thread(target=run, name="ceaser-proactive-runtime", daemon=True)
    PROACTIVE_RUNTIME_THREAD.start()


LAST_POWER_INACTIVE_AT = 0.0


def execute_text(text, source="typed", context=None, request_id=None, session_id=None, stt_metadata=None):
    command = normalize_spoken_command(text)
    if not command:
        emit_voice_state("failed", reason="empty_transcript", source=source)
        return {
            "status": "empty",
            "transcript": "",
            "message": "No command heard.",
            "fallback_used": False,
            "error_code": "empty_transcript",
        }
    # A bare "continue" is a media resume only while media is known to be paused.
    command = MEDIA_STATE.normalize_for_routing(command)
    control = VOICE_CONTROLLER.handle_control(command)
    if control:
        return control
    command, corrected = VOICE_CONTROLLER.normalize_correction(command)
    req_id = request_id or f"desktop_{int(time.time() * 1000)}"
    if req_id in RECENT_REQUESTS:
        return {
            "status": "cancelled",
            "transcript": command,
            "message": "Duplicate command ignored.",
            "request_id": req_id,
            "duplicate_execution_prevented": True,
        }
    RECENT_REQUESTS[req_id] = time.time()
    for old_id, created_at in list(RECENT_REQUESTS.items()):
        if time.time() - created_at > 120:
            RECENT_REQUESTS.pop(old_id, None)
    session = session_id or ACTION_CONTEXT.get("desktop_conversation_id") or "desktop_session"
    merged_context = dict(context or {})
    ACTION_CONTEXT["desktop_file_context"] = merged_context.get("desktop_file_context")
    if stt_metadata:
        merged_context["stt"] = stt_metadata
    if corrected:
        merged_context["mid_course_correction"] = True
        merged_context["previous_voice_command"] = VOICE_CONTROLLER.last_command
    request = CommandRequest(
        request_id=req_id,
        user_id=CURRENT_USER_ID or "",
        session_id=session,
        source=source,
        raw_text=str(text or ""),
        normalized_text=command,
        context=merged_context,
        metadata={"compatibility_transport": "CEASER_JSON", "stt": stt_metadata or {}},
    )
    metrics = InteractionMetrics()
    started = time.perf_counter()
    try:
        metrics.mark("routing_started_at")
        emit_voice_state("routing", command=command, request_id=req_id, source=source)
        metrics.mark("routing_completed_at")
        metrics.mark("execution_started_at")
        ACTION_CONTEXT["active_request_stt"] = dict(stt_metadata or {})
        with COMMAND_EXECUTION_LOCK:
            result = get_command_service().execute(request)
        ACTION_CONTEXT.pop("active_request_stt", None)
        metrics.mark("execution_completed_at")
        emit_voice_state("executing", command=command, request_id=req_id, capability=result.capability, source=source)
        response = result.to_legacy()
        metrics.mark("tts_requested_at")
        response.update(
            {
                "transcript": command,
                "request_id": req_id,
                "session_id": session,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "desktop_brain_v2": True,
                "capability": result.capability,
                "verified": result.verified,
                "error_code": result.error_code,
                "fallback_used": False,
                "mid_course_correction": corrected,
                "performance": metrics.safe_metrics(),
            }
        )
        LATENCY_HISTORY.add(response["performance"])
        emit_voice_state(
            "completed" if result.status == "completed" else "failed",
            command=command,
            request_id=req_id,
            capability=result.capability,
            verified=result.verified,
            source=source,
        )
        return VOICE_CONTROLLER.record_execution(command, response)
    except Exception as exc:
        ACTION_CONTEXT.pop("active_request_stt", None)
        DIAGNOSTICS.record_recovery("command_service_failure", reason=type(exc).__name__)
        sys.stderr.write(f"[CEASER Python] CommandService failed request_id={req_id} reason={type(exc).__name__}; controlled recovery returned\n")
        sys.stderr.flush()
        emit_voice_state("recovering", command=command, request_id=req_id, reason=type(exc).__name__, source=source)
        fallback = {
            "status": "error",
            "message": "CEASER could not complete that command. Please try again.",
            "spoken_response": "I could not complete that command. Please try again.",
            "verified": False,
            "error_code": "command_service_unavailable",
            "fallback_used": False,
            "fallback_reason": type(exc).__name__,
            "desktop_brain_v2": True,
            "request_id": req_id,
            "session_id": session,
            "mid_course_correction": corrected,
        }
        metrics.mark("execution_completed_at")
        fallback["performance"] = metrics.safe_metrics()
        LATENCY_HISTORY.add(fallback["performance"])
        return VOICE_CONTROLLER.record_execution(command, fallback)


def call_ceaser_backend_chat(command, already_wrapped=False):
    ACTION_CONTEXT["backend_auth_error"] = ""
    if not BACKEND_API_URL:
        return ""
    if not CEASER_ACCESS_TOKEN and not refresh_ceaser_session():
        ACTION_CONTEXT["backend_auth_error"] = "missing_session"
        return ""
    backend_started = time.perf_counter()
    first_response_ms = None
    try:
        user = load_current_user_context()
        user_command = str(command or "").strip()
        if already_wrapped:
            message = user_command
        else:
            stt_context = dict(ACTION_CONTEXT.get("active_request_stt") or {})
            detected_language = str(stt_context.get("detected_language") or stt_context.get("language") or "").strip()
            original_transcript = str(stt_context.get("original_transcript") or "").strip()
            language_instruction = ""
            if detected_language and not detected_language.lower().startswith(("en", "english")):
                language_instruction = (
                    f" Respond naturally in the user's detected language ({detected_language})."
                    " Preserve necessary application names and technical terms."
                )
            original_request_line = f"Original spoken request: {original_transcript}\n" if original_transcript else ""
            message = (
                "Answer this desktop companion request with a complete, useful response for on-screen reading. "
                "Use clear paragraphs or bullets when helpful. Do not say that details are on screen; include the actual details. "
                "Use the signed-in user's CEASER memories, projects, files, documents, reports, conversations, and integrations whenever relevant. "
                "If the user asks about their CEASER content, answer from their account context instead of generic knowledge. "
                "Speak as CEASER: confident, warm, direct, and conversational, without pretending to be human or inventing emotions. "
                "Use light wit only when appropriate; prioritize truth, clarity, and completing the user's work. "
                "Keep it concise enough for a small desktop overlay, but do not reduce it to a preview."
                f"{language_instruction}\n\n"
                f"{original_request_line}User request: {user_command}"
            )
        payload = {
            "message": message,
            "source": "desktop_companion",
            "voice": True,
            "original_message": user_command,
            "request_id": f"desktop_{int(time.time() * 1000)}",
            "device_id": os.getenv("CEASER_DESKTOP_DEVICE_ID") or None,
            "desktop_file_context": ACTION_CONTEXT.get("desktop_file_context"),
        }
        if ACTION_CONTEXT.get("desktop_conversation_id"):
            payload["conversation_id"] = ACTION_CONTEXT["desktop_conversation_id"]
        if user.get("id"):
            payload["user_id"] = user.get("id")
        request_started = time.perf_counter()
        response = requests.post(
            f"{BACKEND_API_URL.rstrip('/')}/ceaser/chat",
            headers={
                "Authorization": f"Bearer {CEASER_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=55,
        )
        first_response_ms = int((time.perf_counter() - request_started) * 1000)
        if response.status_code == 401 and refresh_ceaser_session():
            request_started = time.perf_counter()
            response = requests.post(
                f"{BACKEND_API_URL.rstrip('/')}/ceaser/chat",
                headers={
                    "Authorization": f"Bearer {CEASER_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=55,
            )
            first_response_ms = int((time.perf_counter() - request_started) * 1000)
        if not response.ok:
            elapsed = int((time.perf_counter() - backend_started) * 1000)
            sys.stderr.write(
                "[CEASER Python] Backend chat failed: "
                f"status={response.status_code} backend_request_ms={elapsed} first_response_ms={first_response_ms}\n"
            )
            sys.stderr.flush()
            if response.status_code == 401:
                clear_desktop_session()
            return ""
        parse_started = time.perf_counter()
        data = response.json()
        parse_ms = int((time.perf_counter() - parse_started) * 1000)
        if data.get("conversation_id"):
            ACTION_CONTEXT["desktop_conversation_id"] = data.get("conversation_id")
        text = (
            data.get("response")
            or data.get("answer")
            or data.get("message")
            or data.get("content")
            or ""
        )
        elapsed = int((time.perf_counter() - backend_started) * 1000)
        diagnostics = data.get("diagnostics") or data.get("observability") or data.get("metrics") or {}
        chroma_ms = diagnostics.get("chroma_init_ms") or diagnostics.get("chromadb_init_ms")
        proactive_ms = diagnostics.get("proactive_init_ms")
        context_ms = diagnostics.get("context_rag_ms") or diagnostics.get("retrieval_ms") or diagnostics.get("context_build_ms")
        provider_first_token_ms = diagnostics.get("first_token_ms") or diagnostics.get("upstream_first_token_ms")
        sys.stderr.write(
            "[CEASER Python] Backend chat latency "
            f"backend_request_ms={elapsed} first_response_ms={first_response_ms} response_parse_ms={parse_ms} "
            f"chroma_init_ms={chroma_ms if chroma_ms is not None else 'n/a'} "
            f"proactive_init_ms={proactive_ms if proactive_ms is not None else 'n/a'} "
            f"context_rag_ms={context_ms if context_ms is not None else 'n/a'} "
            f"provider_first_token_ms={provider_first_token_ms if provider_first_token_ms is not None else 'n/a'}\n"
        )
        sys.stderr.flush()
        return clean_backend_text(text)
    except Exception as exc:
        elapsed = int((time.perf_counter() - backend_started) * 1000)
        sys.stderr.write(
            f"[CEASER Python] Backend chat unavailable: {type(exc).__name__} backend_request_ms={elapsed} first_response_ms={first_response_ms}\n"
        )
        sys.stderr.flush()
        return ""


def handle(payload):
    global CEASER_ACCESS_TOKEN, CURRENT_USER_ID
    req_id = payload.get("id")
    typ = payload.get("type")
    request_body = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    persistent_command_mode = bool(
        request_body.get("persistent_command_mode", payload.get("persistent_command_mode", False))
    )
    try:
        if typ == "execute_command" and str(payload.get("version") or "") == "2.0":
            WAKE_CANCEL_EVENT.set()
            body = payload.get("payload") or {}
            response = execute_text(
                body.get("text", ""),
                source=body.get("source") or "typed",
                context=body.get("context") or {},
                request_id=req_id,
                session_id=body.get("session_id"),
            )
        elif typ == "listen_once":
            sys.stderr.write("[CEASER Python] listen_once request received\n")
            sys.stderr.flush()
            listened = listen_once(passive=False)
            response = execute_text(
                listened.get("transcript", ""),
                source="voice",
                request_id=req_id,
                stt_metadata={"provider": listened.get("provider")},
            )
            response["stt_provider"] = listened.get("provider")
        elif typ == "listen_wake_command":
            sys.stderr.write("[CEASER Python] listen_wake_command request received\n")
            sys.stderr.flush()
            response = listen_for_wake_command(force_command_listening=persistent_command_mode)
        elif typ == "execute_text":
            WAKE_CANCEL_EVENT.set()
            response = execute_text(
                payload.get("text", ""),
                source=payload.get("source") or "typed",
                context=payload.get("context") or {},
                request_id=req_id,
                session_id=payload.get("session_id"),
            )
        elif typ == "analyze_file":
            response = analyze_smart_capture_file(payload.get("path", ""))
        elif typ == "voice_playback":
            state = str(payload.get("state") or "").lower()
            if state == "speaking":
                VOICE_CONTROLLER.begin_speaking(payload.get("overlay_response", ""), payload.get("spoken_response"))
                response = {"status": "completed", "message": "Voice playback marked as speaking.", "voice_state": VOICE_CONTROLLER.state}
            elif state == "interrupted":
                DIAGNOSTICS.record_recovery("tts_interrupted", reason=str(payload.get("reason") or "interrupted"))
                response = VOICE_CONTROLLER.interrupt(str(payload.get("reason") or "interrupted"))
            else:
                VOICE_CONTROLLER.end_speaking()
                response = {"status": "completed", "message": "Voice playback finished.", "voice_state": VOICE_CONTROLLER.state}
        elif typ == "synthesize_speech":
            provider = os.getenv("CEASER_TTS_PROVIDER", "system").lower()
            if provider != "elevenlabs":
                response = {"status": "unavailable", "provider": provider, "reason": "provider_disabled"}
            else:
                text = str(payload.get("text") or "").strip()[:4000]
                try:
                    speech = ELEVENLABS_VOICE.synthesize(text)
                    response = {
                        "status": "completed",
                        "provider": "elevenlabs",
                        "audio_base64": base64.b64encode(speech.audio).decode("ascii"),
                        "mime_type": speech.mime_type,
                        "first_audio_ms": speech.first_audio_ms,
                        "total_ms": speech.total_ms,
                    }
                except ElevenLabsError as exc:
                    sys.stderr.write(f"[CEASER Voice] tts_failed provider=elevenlabs category={exc.category}\n")
                    sys.stderr.flush()
                    response = {"status": "unavailable", "provider": "elevenlabs", "reason": exc.category}
        elif typ == "session_update":
            CEASER_ACCESS_TOKEN = str(payload.get("access_token") or CEASER_ACCESS_TOKEN or "")
            CURRENT_USER_ID = str(payload.get("user_id") or CURRENT_USER_ID or "")
            user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
            if user:
                ACTION_CONTEXT["current_user"] = user
            ACTION_CONTEXT["backend_auth_error"] = ""
            response = {"status": "completed", "message": "Desktop session updated.", "session_updated": True}
        elif typ == "proactive_dismiss":
            get_command_service().dismiss_proactive()
            response = {"status": "completed", "message": "Proactive message dismissed."}
        elif typ == "companion_preferences_save":
            saved = get_command_service().long_term_memory.save_companion_preferences(CURRENT_USER_ID or "", payload.get("preferences") or {})
            ACTION_CONTEXT["companion_preferences"] = saved.model_dump()
            response = {"status": "completed", "message": "Companion preferences saved.", "preferences": saved.model_dump()}
        elif typ == "companion_preferences_get":
            preferences = get_command_service().long_term_memory.companion_preferences(CURRENT_USER_ID or "")
            response = {"status": "completed", "message": "Companion preferences loaded.", "preferences": preferences}
        elif typ == "diagnostics":
            response = {
                "status": "completed",
                "message": "Diagnostics ready.",
                "diagnostics": DIAGNOSTICS.snapshot(voice_engine=VOICE_ENGINE, python_requests=len(RECENT_REQUESTS)),
            }
        elif typ == "power_event":
            global LAST_POWER_INACTIVE_AT
            state = str(payload.get("state") or "")
            if state in ("resume", "unlock-screen"):
                DIAGNOSTICS.record_recovery("power_resume", state=state)
                if VOICE_ENGINE:
                    with contextlib.suppress(Exception):
                        VOICE_ENGINE.microphone.reopen()
                absence_seconds = max(0, int(time.time() - LAST_POWER_INACTIVE_AT)) if LAST_POWER_INACTIVE_AT else 0
                if absence_seconds:
                    event = get_command_service().awareness_engine.factory.system(
                        "user_returned",
                        "User returned",
                        "The authenticated user returned after an inactive period.",
                        {
                            "social_trigger": "returned_after_absence",
                            "absence_seconds": absence_seconds,
                            "relevance": 0.85,
                            "confidence": 1.0,
                            "timing": 0.9,
                            "allow_spoken_notice": True,
                            "correlation_id": f"return:{int(LAST_POWER_INACTIVE_AT // 900)}",
                        },
                    )
                    get_command_service().observe_event(event, _proactive_context())
                LAST_POWER_INACTIVE_AT = 0.0
            elif state in ("suspend", "lock-screen"):
                DIAGNOSTICS.record_recovery("power_suspend", state=state)
                LAST_POWER_INACTIVE_AT = time.time()
            response = {"status": "completed", "message": "Power event handled.", "power_state": state}
        else:
            response = {"status": "error", "message": "Unknown command."}
    except sr.WaitTimeoutError:
        if typ == "listen_wake_command":
            idle_state = "command_listening" if persistent_command_mode or not WAKE_WORD_ENABLED else "wake_listening"
            emit_voice_state(idle_state, request_id=req_id, reason="recoverable_no_speech")
            response = {"status": idle_state, "transcript": "", "message": "", "recoverable": True}
        else:
            emit_voice_state("failed", request_id=req_id, reason="stt_timeout")
            response = {"status": "empty", "transcript": "", "message": "No command heard."}
    except sr.UnknownValueError:
        if typ == "listen_wake_command":
            idle_state = "command_listening" if persistent_command_mode or not WAKE_WORD_ENABLED else "wake_listening"
            emit_voice_state(idle_state, request_id=req_id, reason="recoverable_unrecognized_speech")
            response = {"status": idle_state, "transcript": "", "message": "", "recoverable": True}
        else:
            emit_voice_state("failed", request_id=req_id, reason="unrecognized_speech")
            response = {"status": "empty", "transcript": "", "message": "I did not catch that."}
    except sr.RequestError:
        emit_voice_state("failed", request_id=req_id, reason="stt_unavailable")
        response = {"status": "error", "transcript": "", "message": "Voice service unavailable."}
    except Exception as exc:
        emit_voice_state("recovering", request_id=req_id, reason=type(exc).__name__)
        response = {"status": "error", "transcript": "", "message": "Voice assistant failed.", "error": type(exc).__name__}
    response["id"] = req_id
    emit(response)


def main():
    try:
        emit({"id": "ready", "status": "ready", "message": "Python companion ready."})
        start_proactive_runtime()
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            if line == "__quit__":
                break
            try:
                payload = json.loads(line)
                thread = threading.Thread(
                    target=handle,
                    args=(payload,),
                    name=f"ceaser-request-{str(payload.get('id') or 'event')[-24:]}",
                    daemon=True,
                )
                thread.start()
            except Exception as exc:
                emit({"id": None, "status": "error", "message": "Invalid request.", "error": type(exc).__name__})
    finally:
        PROACTIVE_RUNTIME_STOP.set()
        if COMMAND_SERVICE:
            with contextlib.suppress(Exception):
                COMMAND_SERVICE.stop_awareness_producers()
        if getattr(LEGACY_ASSISTANT, "proactive_assistant", None):
            with contextlib.suppress(Exception):
                LEGACY_ASSISTANT.proactive_assistant.close()
        reset_microphone_source()


if __name__ == "__main__":
    main()
