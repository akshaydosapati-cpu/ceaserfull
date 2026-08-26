from __future__ import annotations

import shutil
import socket
import ctypes
from typing import Any, Callable

from awareness.event_sources import EventFactory
from awareness.models import AwarenessEvent
from awareness.producers.base import EventProducer


class SystemProducer(EventProducer):
    name = "system"
    poll_interval_seconds = 30.0

    def __init__(self, emit=None, probe: Callable[[], dict[str, Any]] | None = None) -> None:
        super().__init__(emit)
        self.probe = probe or self._probe
        self.factory = EventFactory()
        self._last_network: bool | None = None
        self._last_battery_bucket = ""
        self._last_disk_low = False

    def normalize_event(self, raw: dict[str, Any]) -> AwarenessEvent | None:
        event_type = raw.get("type")
        if not event_type:
            return None
        return self.factory.system(event_type, raw.get("title", event_type), raw.get("summary", ""), raw.get("payload", {}))

    def companion_startup(self) -> AwarenessEvent:
        return self.factory.system("companion_startup", "CEASER companion started", "Desktop companion runtime is active.")

    def companion_shutdown(self) -> AwarenessEvent:
        return self.factory.system("companion_shutdown", "CEASER companion stopped", "Desktop companion runtime is shutting down.")

    def _poll(self, context: dict) -> list[AwarenessEvent]:
        data = self.probe()
        events: list[AwarenessEvent] = []
        network = bool(data.get("network_connected"))
        if self._last_network is not None and network != self._last_network:
            event_type = "network_changed" if network else "network_down"
            title = "Network connected" if network else "Network disconnected"
            events.append(self.factory.system(event_type, title, title, {"connected": network}))
        self._last_network = network

        percent = data.get("battery_percent")
        charging = bool(data.get("battery_charging"))
        if percent is not None:
            bucket = f"{int(percent // 10) * 10}:{charging}"
            if percent <= 20 and bucket != self._last_battery_bucket:
                events.append(self.factory.system("battery_low", "Battery low", f"Battery is at {int(percent)}%.", {"battery_percent": int(percent), "charging": charging}))
            self._last_battery_bucket = bucket

        disk_free = data.get("disk_free_percent")
        disk_low = disk_free is not None and disk_free < 10
        if disk_low and not self._last_disk_low:
            events.append(self.factory.system("low_disk_space", "Low disk space", f"Disk free space is below {int(disk_free)}%.", {"disk_free_percent": int(disk_free)}))
        self._last_disk_low = disk_low
        return events

    def _probe(self) -> dict[str, Any]:
        total, used, free = shutil.disk_usage(".")
        return {
            "network_connected": self._network_connected(),
            **self._battery_status(),
            "disk_free_percent": free / total * 100 if total else 100,
            "audio_device_available": True,
        }

    def _network_connected(self) -> bool:
        try:
            socket.create_connection(("1.1.1.1", 53), timeout=0.4).close()
            return True
        except OSError:
            return False

    def _battery_status(self) -> dict[str, Any]:
        class SystemPowerStatus(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_byte),
                ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte),
                ("SystemStatusFlag", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_ulong),
                ("BatteryFullLifeTime", ctypes.c_ulong),
            ]

        status = SystemPowerStatus()
        try:
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
                percent = None if status.BatteryLifePercent == 255 else int(status.BatteryLifePercent)
                return {"battery_percent": percent, "battery_charging": status.ACLineStatus == 1}
        except Exception:
            pass
        return {"battery_percent": None, "battery_charging": False}
