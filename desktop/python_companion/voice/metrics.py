from __future__ import annotations

import os
import statistics
import time
from dataclasses import dataclass, field
from typing import Any


DEFAULT_THRESHOLDS_MS = {
    "wake_latency_ms": 400,
    "stt_latency_ms": 1200,
    "routing_latency_ms": 100,
    "execution_latency_ms": 500,
    "tts_start_latency_ms": 1000,
}


def perf_ms() -> int:
    return int(time.perf_counter() * 1000)


def wall_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class InteractionMetrics:
    wake_detected_at: int = 0
    command_speech_started_at: int = 0
    command_speech_ended_at: int = 0
    stt_started_at: int = 0
    stt_completed_at: int = 0
    routing_started_at: int = 0
    routing_completed_at: int = 0
    execution_started_at: int = 0
    execution_completed_at: int = 0
    tts_requested_at: int = 0
    tts_started_at: int = 0
    tts_completed_at: int = 0
    wake_resumed_at: int = 0
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def mark(self, name: str, value: int | None = None) -> None:
        if hasattr(self, name):
            setattr(self, name, value or perf_ms())

    def safe_metrics(self) -> dict[str, Any]:
        metrics = {
            "wake_latency_ms": self._delta("wake_detected_at", "command_speech_started_at"),
            "endpointing_latency_ms": self._delta("command_speech_ended_at", "stt_started_at"),
            "stt_latency_ms": self._delta("stt_started_at", "stt_completed_at"),
            "routing_latency_ms": self._delta("routing_started_at", "routing_completed_at"),
            "execution_latency_ms": self._delta("execution_started_at", "execution_completed_at"),
            "tts_start_latency_ms": self._delta("tts_requested_at", "tts_started_at"),
            "total_latency_ms": self._total_latency(),
        }
        warnings = self.threshold_warnings(metrics)
        return {**metrics, "warnings": warnings}

    def threshold_warnings(self, metrics: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        metrics = metrics or {}
        warnings = []
        for name, default in DEFAULT_THRESHOLDS_MS.items():
            threshold = int(os.getenv(f"CEASER_{name.upper()}_WARN", str(default)))
            value = metrics.get(name)
            if isinstance(value, int) and value > threshold:
                warnings.append({"metric": name, "value_ms": value, "threshold_ms": threshold})
        self.warnings = warnings
        return warnings

    def _delta(self, start: str, end: str) -> int | None:
        start_value = int(getattr(self, start, 0) or 0)
        end_value = int(getattr(self, end, 0) or 0)
        if not start_value or not end_value or end_value < start_value:
            return None
        return end_value - start_value

    def _total_latency(self) -> int | None:
        starts = [value for value in [self.wake_detected_at, self.command_speech_started_at, self.routing_started_at] if value]
        ends = [value for value in [self.tts_completed_at, self.wake_resumed_at, self.execution_completed_at] if value]
        if not starts or not ends:
            return None
        return max(ends) - min(starts)


class LatencyHistory:
    def __init__(self, limit: int = 100) -> None:
        self.limit = limit
        self.samples: dict[str, list[int]] = {}

    def add(self, metrics: dict[str, Any]) -> None:
        for key, value in metrics.items():
            if key == "warnings" or not isinstance(value, int):
                continue
            bucket = self.samples.setdefault(key, [])
            bucket.append(value)
            if len(bucket) > self.limit:
                del bucket[0 : len(bucket) - self.limit]

    def percentiles(self) -> dict[str, dict[str, int]]:
        result = {}
        for key, values in self.samples.items():
            if not values:
                continue
            ordered = sorted(values)
            result[key] = {
                "p50": self._percentile(ordered, 50),
                "p95": self._percentile(ordered, 95),
            }
        return result

    def _percentile(self, ordered: list[int], percentile: int) -> int:
        if len(ordered) == 1:
            return ordered[0]
        index = round((percentile / 100) * (len(ordered) - 1))
        return ordered[max(0, min(index, len(ordered) - 1))]


def redact_diagnostics(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(secret in lowered for secret in ("token", "secret", "key", "password", "credential")):
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_diagnostics(item)
        return redacted
    if isinstance(value, list):
        return [redact_diagnostics(item) for item in value]
    return value
