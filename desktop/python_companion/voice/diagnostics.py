from __future__ import annotations

import os
import time
from typing import Any

from voice.metrics import LatencyHistory, redact_diagnostics


STARTED_AT = time.time()


class RuntimeDiagnostics:
    def __init__(self, latency_history: LatencyHistory | None = None) -> None:
        self.latency_history = latency_history or LatencyHistory()
        self.last_recovery_event: dict[str, Any] = {}

    def record_recovery(self, event: str, **payload: Any) -> None:
        self.last_recovery_event = {"event": event, "timestamp": time.time(), **payload}

    def snapshot(
        self,
        *,
        voice_engine: Any = None,
        producer_health: dict[str, Any] | None = None,
        queue_sizes: dict[str, int] | None = None,
        python_requests: int = 0,
    ) -> dict[str, Any]:
        microphone = {}
        wake_mode = "unknown"
        stt_provider = os.getenv("CEASER_STT_PROVIDER", "google")
        voice_state = "unknown"
        if voice_engine:
            with suppress_errors():
                microphone = dict(voice_engine.microphone.device_info or {})
            with suppress_errors():
                wake_mode = voice_engine.active_wake_mode()
            with suppress_errors():
                stt_provider = voice_engine.stt.provider
            with suppress_errors():
                voice_state = voice_engine.state.state.lower()
        snapshot = {
            "active_microphone_device": microphone.get("name") or "default microphone",
            "active_wake_mode": wake_mode,
            "stt_provider": stt_provider,
            "voice_state": voice_state,
            "python_process_uptime_ms": int((time.time() - STARTED_AT) * 1000),
            "idle_cpu_estimate": "unknown",
            "memory_usage": self._memory_usage(),
            "producer_health": producer_health or {},
            "queue_sizes": queue_sizes or {"python_pending_requests": python_requests},
            "last_recovery_event": self.last_recovery_event,
            "recent_latency_percentiles": self.latency_history.percentiles(),
        }
        return redact_diagnostics(snapshot)

    def _memory_usage(self) -> dict[str, Any]:
        try:
            import resource

            return {"rss_kb": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)}
        except Exception:
            return {"rss_kb": None}


class suppress_errors:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return True
