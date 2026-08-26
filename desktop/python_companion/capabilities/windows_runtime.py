from __future__ import annotations

import ctypes
import os
import platform
import subprocess
import time
import socket
import uuid
from pathlib import Path
from typing import Any, Callable

import psutil

from features.ceaser.device_control import DeviceControl
from features.ceaser.file_manager import FileManager


class WindowsCapabilityRuntime:
    """Lazy, bounded Windows handlers. No model-provided shell is accepted."""

    def __init__(self, legacy_handler: Callable[[str], dict[str, Any]]) -> None:
        self.legacy_handler = legacy_handler
        self.implemented = {
            "app.open", "app.close", "app.focus", "app.list_running", "app.restart", "app.foreground", "app.windows",
            "window.list", "window.get_active", "window.minimize", "window.maximize", "window.restore", "window.focus", "window.close", "window.move", "window.resize", "window.snap_left", "window.snap_right", "window.fullscreen", "window.move_to_monitor", "window.show_desktop",
            "system.open_settings", "system.lock", "system.sleep", "system.shutdown", "system.restart", "system.sign_out",
            "audio.volume.get", "audio.volume.set", "audio.volume.up", "audio.volume.down", "audio.mute", "audio.unmute",
            "media.play", "media.pause", "media.play_pause", "media.stop", "media.next", "media.previous", "media.seek_forward", "media.seek_backward",
            "clipboard.read", "clipboard.write", "clipboard.clear", "screen.capture_all", "screen.capture_monitor", "screen.capture_active_window", "screen.capture_region",
            "file.search", "file.list", "file.read", "file.create", "file.rename", "file.copy", "file.move", "file.delete", "file.stat", "file.open", "file.reveal", "file.recent", "file.calculate_size",
            "directory.create", "directory.list", "network.status", "network.ip_info", "wifi.status", "wifi.current_network", "wifi.list_networks", "wifi.connect", "wifi.disconnect", "wifi.enable", "wifi.disable",
            "display.list", "display.primary", "display.brightness.get", "display.brightness.set", "display.brightness.up", "display.brightness.down", "monitor.list", "monitor.primary", "bluetooth.enable", "bluetooth.disable", "bluetooth.open_settings",
            "input.type_text", "input.hotkey", "input.copy", "input.cut", "input.paste", "input.select_all", "input.undo", "input.redo", "input.save",
            "storage.drives", "storage.free_space", "storage.usage", "storage.removable_devices", "storage.open_drive",
            "printer.list", "printer.default", "printer.status", "printer.queue", "printer.cancel_job", "printer.open_settings", "printer.print_file", "recycle.empty",
            "system.os_version", "system.device_name", "system.cpu_info", "system.memory_info", "system.disk_info", "system.battery_info", "system.network_info", "system.display_info",
        }

    def available(self, capability: str) -> tuple[bool, str]:
        if platform.system() != "Windows":
            return False, "This capability requires Windows."
        if capability not in self.implemented:
            return False, "This capability has no production handler on this device."
        if capability.startswith("display.brightness"):
            try:
                import screen_brightness_control  # noqa: F401
            except Exception:
                return False, "Brightness control is unsupported on this display."
        if capability.startswith("wifi."):
            if not any("wi-fi" in str(name).lower() or "wireless" in str(name).lower() for name in psutil.net_if_addrs()):
                return False, "No Wi-Fi adapter was detected."
        if capability.startswith("bluetooth.") and capability != "bluetooth.open_settings":
            if platform.release() not in {"10", "11"}:
                return False, "Bluetooth radio control requires Windows 10 or newer."
        if capability.startswith("printer."):
            try:
                import win32print  # noqa: F401
            except Exception:
                return False, "Windows printer support is not installed on this device."
        return True, ""

    def execute(self, capability: str, args: dict[str, Any], original_text: str) -> dict[str, Any]:
        supported, reason = self.available(capability)
        if not supported:
            return self._result("unsupported", reason, capability, False, "hardware_unsupported")
        started = time.perf_counter()
        try:
            result = self._execute(capability, args, original_text)
        except TimeoutError:
            result = self._result("error", "The action timed out.", capability, False, "timeout")
        except Exception:
            result = self._result("error", "I could not complete that Windows action.", capability, False, "execution_failed")
        result["duration_ms"] = int((time.perf_counter() - started) * 1000)
        return result

    def _execute(self, capability: str, args: dict[str, Any], original_text: str) -> dict[str, Any]:
        if capability in {"app.open", "app.close", "app.focus"}:
            return self.legacy_handler(original_text)
        if capability in {"app.restart", "app.foreground"}:
            target = str(args.get("target") or args.get("application") or "").strip()
            if not target: return self._result("needs_clarification", "Which application?", capability, False, "missing_target")
            if capability == "app.foreground": return self._window("window.focus", target, args)
            closed = self.legacy_handler(f"close {target}")
            if str(closed.get("status", "")).lower() not in {"completed", "success"}: return closed
            return self.legacy_handler(f"open {target}")
        if capability == "app.windows":
            return self._window("window.list", str(args.get("target") or args.get("application") or ""), args)
        if capability == "app.list_running":
            names = sorted({str(p.info.get("name") or "") for p in psutil.process_iter(["name"]) if p.info.get("name")})
            return self._result("completed", f"{len(names)} applications and processes are running.", capability, True, data={"applications": names[:100]})
        if capability.startswith("window.") and capability != "window.show_desktop":
            return self._window(capability, str(args.get("target") or ""), args)
        if capability == "window.show_desktop":
            ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0); ctypes.windll.user32.keybd_event(0x44, 0, 0, 0); ctypes.windll.user32.keybd_event(0x44, 0, 2, 0); ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0)
            return self._result("completed", "Desktop shown.", capability, True)
        if capability == "system.open_settings":
            page = str(args.get("page") or "").lower()
            pages = {"network": "network", "bluetooth": "bluetooth", "display": "display", "sound": "sound", "apps": "appsfeatures", "storage": "storagesense", "power": "powersleep", "privacy": "privacy", "windows update": "windowsupdate", "update": "windowsupdate"}
            os.startfile(f"ms-settings:{pages.get(page, '')}")
            return self._result("completed", f"{page.title() + ' ' if page else ''}Settings opened.", capability, True)
        if capability in {"system.lock", "system.sleep", "system.shutdown", "system.restart", "system.sign_out"}:
            actions = {"system.lock": DeviceControl.lock_workstation, "system.sleep": DeviceControl.sleep, "system.shutdown": DeviceControl.shutdown, "system.restart": DeviceControl.restart, "system.sign_out": lambda: subprocess.run(["shutdown", "/l"], check=True) or "Signing out."}
            message = str(actions[capability]())
            return self._from_message(capability, message)
        if capability.startswith("audio."):
            return self._audio(capability, args)
        if capability.startswith("media."):
            return self._media(capability, original_text)
        if capability.startswith("clipboard."):
            if capability == "clipboard.read":
                value = DeviceControl.paste_from_clipboard(); return self._result("completed", "Clipboard content is ready.", capability, not str(value).startswith("Failed"), data={"text": value})
            message = DeviceControl.copy_to_clipboard(str(args.get("text") or "")) if capability == "clipboard.write" else DeviceControl.clear_clipboard()
            return self._from_message(capability, message)
        if capability.startswith("screen.capture_"):
            return self._capture(capability, args)
        if capability.startswith("file.") or capability in {"directory.create", "directory.list"}:
            return self._file(capability, args)
        if capability in {"network.status", "network.ip_info", "wifi.status", "wifi.current_network", "wifi.list_networks"}:
            return self._network(capability)
        if capability in {"wifi.connect", "wifi.disconnect"}:
            argv = ["netsh", "wlan", "connect", f"name={args.get('network', '')}"] if capability.endswith("connect") else ["netsh", "wlan", "disconnect"]
            completed = subprocess.run(argv, capture_output=True, text=True, timeout=10)
            return self._result("completed" if completed.returncode == 0 else "error", completed.stdout.strip() or "Wi-Fi action completed.", capability, completed.returncode == 0, None if completed.returncode == 0 else "execution_failed")
        if capability in {"wifi.enable", "wifi.disable"}:
            return self._wifi_radio(capability)
        if capability in {"display.list", "display.primary", "monitor.list", "monitor.primary"}:
            monitors = self._monitors(); primary = next((m for m in monitors if m["primary"]), monitors[0])
            data = primary if capability.endswith("primary") else monitors
            return self._result("completed", f"Detected {len(monitors)} display(s).", capability, True, data={"display": data} if capability.endswith("primary") else {"displays": data})
        if capability.startswith("display.brightness."):
            return self._brightness(capability, args)
        if capability in {"bluetooth.enable", "bluetooth.disable"}:
            return self._bluetooth_radio(capability)
        if capability == "bluetooth.open_settings":
            os.startfile("ms-settings:bluetooth"); return self._result("completed", "Bluetooth settings opened.", capability, True)
        if capability.startswith("input."):
            return self._input(capability, args)
        if capability.startswith("storage."):
            return self._storage(capability, args)
        if capability.startswith("printer."):
            return self._printer(capability, args)
        if capability == "recycle.empty":
            code = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x0001 | 0x0002 | 0x0004)
            return self._result("completed" if code == 0 else "error", "Recycle Bin emptied." if code == 0 else "Recycle Bin could not be emptied.", capability, code == 0, None if code == 0 else "execution_failed")
        if capability.startswith("system.") and capability in {"system.os_version", "system.device_name", "system.cpu_info", "system.memory_info", "system.disk_info", "system.battery_info", "system.network_info", "system.display_info"}:
            return self._system_info(capability)
        return self._result("unsupported", "This capability is not available on this device.", capability, False, "capability_unavailable")

    def _window(self, capability: str, target: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        import pygetwindow
        args = args or {}
        windows = [w for w in pygetwindow.getAllWindows() if w.title and (not target or target.lower() in w.title.lower())]
        if not windows: return self._result("error", "I could not find that window.", capability, False, "target_not_found")
        if capability == "window.list": return self._result("completed", f"Found {len(windows)} windows.", capability, True, data={"windows": [self._window_data(w) for w in windows[:50]]})
        if capability == "window.get_active":
            active = pygetwindow.getActiveWindow(); return self._result("completed", "Active window identified.", capability, bool(active), data={"window": self._window_data(active) if active else None})
        index = args.get("index")
        if index is None and len(windows) > 1: return self._result("needs_clarification", "I found multiple matching windows. Which one?", capability, False, "ambiguous_target", {"targets": [self._window_data(w) for w in windows[:8]]})
        window = windows[max(0, min(len(windows)-1, int(index or 1)-1))]; before = self._window_data(window)
        if capability in {"window.minimize", "window.maximize", "window.restore", "window.focus", "window.close"}:
            {"window.minimize": window.minimize, "window.maximize": window.maximize, "window.restore": window.restore, "window.focus": window.activate, "window.close": window.close}[capability]()
        elif capability in {"window.move", "window.resize"}:
            if capability == "window.move": window.moveTo(int(args.get("x", window.left)), int(args.get("y", window.top)))
            else: window.resizeTo(max(200, int(args.get("width", window.width))), max(120, int(args.get("height", window.height))))
        elif capability in {"window.snap_left", "window.snap_right", "window.fullscreen", "window.move_to_monitor"}:
            monitors = self._monitors(); monitor_index = int(args.get("monitor", 1)) - 1
            if capability == "window.move_to_monitor" and not (0 <= monitor_index < len(monitors)): return self._result("unsupported", "That monitor is not available.", capability, False, "hardware_unsupported")
            monitor = monitors[monitor_index if capability == "window.move_to_monitor" else 0]
            if capability == "window.fullscreen": window.maximize()
            else:
                width = monitor["width"] // (2 if capability.startswith("window.snap_") else 1)
                x = monitor["left"] + (width if capability == "window.snap_right" else 0)
                window.restore(); window.moveTo(x, monitor["top"]); window.resizeTo(width, monitor["height"])
        time.sleep(.15)
        if capability == "window.close":
            verified = not any(w.title == before["title"] for w in pygetwindow.getAllWindows())
        elif capability == "window.minimize":
            verified = bool(getattr(window, "isMinimized", False))
        elif capability in {"window.maximize", "window.fullscreen"}:
            verified = bool(getattr(window, "isMaximized", False))
        elif capability in {"window.restore", "window.focus"}:
            verified = not bool(getattr(window, "isMinimized", False))
        else:
            current = self._window_data(window)
            verified = current != before
        return self._result("completed" if verified else "error", f"{before['title']} updated.", capability, verified, None if verified else "verification_failed", {"window": before})

    @staticmethod
    def _window_data(window) -> dict[str, Any]:
        return {"title": window.title, "left": window.left, "top": window.top, "width": window.width, "height": window.height}

    @staticmethod
    def _monitors() -> list[dict[str, Any]]:
        try:
            from screeninfo import get_monitors
            return [{"index": i + 1, "left": m.x, "top": m.y, "width": m.width, "height": m.height, "primary": bool(getattr(m, "is_primary", i == 0))} for i, m in enumerate(get_monitors())]
        except Exception:
            user32 = ctypes.windll.user32
            return [{"index": 1, "left": 0, "top": 0, "width": user32.GetSystemMetrics(0), "height": user32.GetSystemMetrics(1), "primary": True}]

    def _capture(self, capability: str, args: dict[str, Any]) -> dict[str, Any]:
        from PIL import ImageGrab
        root = Path(os.getenv("LOCALAPPDATA", Path.home())) / "CEASER" / "captures"; root.mkdir(parents=True, exist_ok=True)
        asset_id = f"capture-{uuid.uuid4().hex}"; path = root / f"{asset_id}.png"; bbox = None
        if capability == "screen.capture_monitor":
            monitors = self._monitors(); index = int(args.get("monitor", 1)) - 1
            if not 0 <= index < len(monitors): return self._result("unsupported", "That monitor is not available.", capability, False, "hardware_unsupported")
            m = monitors[index]; bbox = (m["left"], m["top"], m["left"] + m["width"], m["top"] + m["height"])
        elif capability == "screen.capture_active_window":
            import pygetwindow
            w = pygetwindow.getActiveWindow()
            if not w: return self._result("error", "No active window was found.", capability, False, "target_not_found")
            bbox = (w.left, w.top, w.left + w.width, w.top + w.height)
        elif capability == "screen.capture_region":
            bbox = tuple(int(args[k]) for k in ("left", "top", "right", "bottom")) if all(k in args for k in ("left", "top", "right", "bottom")) else None
            if not bbox: return self._result("needs_clarification", "Select a screen region first.", capability, False, "missing_region")
        ImageGrab.grab(bbox=bbox, all_screens=True).save(path)
        verified = path.exists() and path.stat().st_size > 0
        return self._result("completed" if verified else "error", "Screenshot captured." if verified else "Screenshot verification failed.", capability, verified, None if verified else "verification_failed", {"asset_reference": asset_id, "mime_type": "image/png"})

    def _audio(self, capability: str, args: dict[str, Any]) -> dict[str, Any]:
        if capability == "audio.volume.get": return self._result("completed", f"Volume is {DeviceControl.get_volume()}%.", capability, True, data={"level": DeviceControl.get_volume()})
        if capability in {"audio.volume.set", "audio.volume.up", "audio.volume.down"}:
            current = int(DeviceControl.get_volume())
            requested = args.get("level")
            step = max(1, min(25, int(args.get("step") or 10)))
            level = int(requested) if requested is not None else current + step if capability.endswith("up") else current - step
            level = max(0, min(100, level)); message = DeviceControl.set_volume(level); verified = abs(int(DeviceControl.get_volume()) - level) <= 1
            return self._result("completed" if verified else "error", message, capability, verified, None if verified else "verification_failed", {"level": DeviceControl.get_volume()})
        message = DeviceControl.mute_volume() if capability in {"audio.mute", "audio.unmute"} else ""
        return self._from_message(capability, message)

    def _media(self, capability: str, original_text: str = "") -> dict[str, Any]:
        if capability in {"media.seek_forward", "media.seek_backward"}:
            before = self._media_timeline_position()
            legacy = self.legacy_handler(original_text)
            if str(legacy.get("status") or "").lower() not in {"completed", "success"}:
                return legacy
            time.sleep(.35)
            after = self._media_timeline_position()
            moved = before is not None and after is not None and (after > before if capability.endswith("forward") else after < before)
            if not moved:
                return self._result("error", "The active media app did not apply that seek command.", capability, False, "verification_failed", {"position_before": before, "position_after": after})
            return self._result("completed", "Moved playback forward." if capability.endswith("forward") else "Moved playback back.", capability, True, data={"position_before": before, "position_after": after})
        virtual_keys = {
            "media.next": 0xB0, "media.previous": 0xB1, "media.stop": 0xB2,
            "media.play": 0xB3, "media.pause": 0xB3, "media.play_pause": 0xB3,
        }
        desired = {"media.play": "Playing", "media.pause": "Paused", "media.stop": "Stopped"}.get(capability)
        before = self._media_playback_state()
        before_identity = self._media_identity() if capability in {"media.next", "media.previous"} else None
        labels = {"media.play": "Playback resumed.", "media.pause": "Playback paused.", "media.play_pause": "Playback toggled.", "media.stop": "Playback stopped.", "media.next": "Skipped forward.", "media.previous": "Went back."}
        if desired and before == desired:
            return self._result("completed", labels[capability], capability, True, data={"dispatch": "not_needed", "playback_status": before, "state_verified": True})
        accepted = self._send_virtual_key(virtual_keys[capability])
        if not accepted:
            return self._result("error", "Windows did not accept that media key.", capability, False, "execution_failed")
        time.sleep(.2)
        after = self._media_playback_state()
        if capability in {"media.next", "media.previous"}:
            deadline = time.time() + 2.0
            after_identity = self._media_identity()
            while before_identity and after_identity == before_identity and time.time() < deadline:
                time.sleep(.2)
                after_identity = self._media_identity()
            if not before_identity or not after_identity or after_identity == before_identity:
                return self._result("error", "The active media app did not change tracks.", capability, False, "verification_failed", {"track_before": before_identity, "track_after": after_identity})
            return self._result("completed", labels[capability], capability, True, data={"dispatch": "windows_media_key", "track_before": before_identity, "track_after": after_identity, "state_verified": True})
        if desired and after and after != desired:
            return self._result("error", "The active media app did not apply that command.", capability, False, "verification_failed", {"dispatch": "windows_media_key", "playback_status": after, "state_verified": True})
        return self._result("completed", labels[capability], capability, True, data={"dispatch": "windows_media_key", "playback_status": after, "state_verified": bool(after)})
    @staticmethod
    def _send_virtual_key(vk: int) -> bool:
        user32 = ctypes.windll.user32
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)
        return True

    @staticmethod
    def _media_playback_state() -> str | None:
        script = r'''
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null=[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media.Control,ContentType=WindowsRuntime]
function Await($Operation, [Type]$ResultType) {
  $m=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 } | Select-Object -First 1
  $t=$m.MakeGenericMethod($ResultType).Invoke($null,@($Operation)); $t.Wait(); $t.Result
}
$manager=Await ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
$session=$manager.GetCurrentSession()
if($session) { [string]$session.GetPlaybackInfo().PlaybackStatus }
'''
        try:
            completed = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, timeout=3)
            state = completed.stdout.strip().splitlines()[-1].strip() if completed.returncode == 0 and completed.stdout.strip() else ""
            return state if state in {"Playing", "Paused", "Stopped", "Closed", "Changing"} else None
        except (OSError, subprocess.SubprocessError):
            return None

    @staticmethod
    def _media_timeline_position() -> int | None:
        script = r'''
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null=[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media.Control,ContentType=WindowsRuntime]
function Await($Operation, [Type]$ResultType) {
  $m=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 } | Select-Object -First 1
  $t=$m.MakeGenericMethod($ResultType).Invoke($null,@($Operation)); $t.Wait(); $t.Result
}
$manager=Await ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
$session=$manager.GetCurrentSession()
if($session) { [long]$session.GetTimelineProperties().Position.Ticks }
'''
        try:
            completed = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, timeout=3)
            return int(completed.stdout.strip().splitlines()[-1]) if completed.returncode == 0 and completed.stdout.strip() else None
        except (ValueError, OSError, subprocess.SubprocessError):
            return None

    @staticmethod
    def _media_identity() -> str | None:
        script = r'''
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null=[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media.Control,ContentType=WindowsRuntime]
function Await($Operation, [Type]$ResultType) {
  $m=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 } | Select-Object -First 1
  $t=$m.MakeGenericMethod($ResultType).Invoke($null,@($Operation)); $t.Wait(); $t.Result
}
$manager=Await ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
$session=$manager.GetCurrentSession()
if($session) {
  $props=Await ($session.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
  Write-Output ($session.SourceAppUserModelId + '|' + $props.Title + '|' + $props.Artist)
}
'''
        try:
            completed = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, timeout=3)
            value = completed.stdout.strip().splitlines()[-1].strip() if completed.returncode == 0 and completed.stdout.strip() else ""
            return value or None
        except (OSError, subprocess.SubprocessError):
            return None

    def _brightness(self, capability: str, args: dict[str, Any]) -> dict[str, Any]:
        import screen_brightness_control as sbc
        current_values = [int(value) for value in sbc.get_brightness()]
        if not current_values:
            return self._result("unsupported", "Brightness control is unavailable on this display.", capability, False, "hardware_unsupported")
        current = current_values[0]
        if capability == "display.brightness.get":
            return self._result("completed", f"Brightness is {current}%.", capability, True, data={"level": current})
        delta = int(args.get("step", 10))
        requested = args.get("level")
        target = int(requested if requested is not None else current + delta if capability.endswith("up") else current - delta)
        target = max(0, min(100, target))
        sbc.set_brightness(target)
        time.sleep(.35)
        after = [int(value) for value in sbc.get_brightness()]
        verified = bool(after) and all(abs(value - target) <= 1 for value in after)
        return self._result("completed" if verified else "error", f"Brightness set to {target}%." if verified else "The display did not apply the brightness change.", capability, verified, None if verified else "verification_failed", {"level": after[0] if after else current})

    def _bluetooth_radio(self, capability: str) -> dict[str, Any]:
        desired = "On" if capability == "bluetooth.enable" else "Off"
        script = rf'''
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null=[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]
function Await($Operation, [Type]$ResultType) {{
  $m=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{ $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 }} | Select-Object -First 1
  $t=$m.MakeGenericMethod($ResultType).Invoke($null,@($Operation)); $t.Wait(); $t.Result
}}
$access=Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus])
if([string]$access -ne 'Allowed') {{ Write-Output '{{"ok":false,"error":"permission_required"}}'; exit 4 }}
$radios=Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
$radio=$radios | Where-Object {{ [string]$_.Kind -eq 'Bluetooth' }} | Select-Object -First 1
if(-not $radio) {{ Write-Output '{{"ok":false,"error":"hardware_unsupported"}}'; exit 3 }}
$result=Await ($radio.SetStateAsync([Windows.Devices.Radios.RadioState]::{desired})) ([Windows.Devices.Radios.RadioAccessStatus])
Start-Sleep -Milliseconds 300
[pscustomobject]@{{ok=([string]$radio.State -eq '{desired}');state=[string]$radio.State;access=[string]$result}} | ConvertTo-Json -Compress
'''
        completed = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, timeout=10)
        try:
            import json
            payload = json.loads(next((line for line in reversed(completed.stdout.splitlines()) if line.strip().startswith("{")), "{}"))
        except Exception:
            payload = {}
        verified = completed.returncode == 0 and bool(payload.get("ok"))
        error = payload.get("error") or ("permission_required" if completed.returncode == 4 else "execution_failed")
        return self._result("completed" if verified else "error", f"Bluetooth turned {desired.lower()}." if verified else "Windows did not allow the Bluetooth state change.", capability, verified, None if verified else error, {"state": payload.get("state")})

    def _file(self, capability: str, args: dict[str, Any]) -> dict[str, Any]:
        source, destination = str(args.get("path") or args.get("source") or ""), str(args.get("destination") or "")
        if any(Path(source).name.lower() in {".env", "credentials.json", "id_rsa"} for _ in [0]): return self._result("error", "That protected file cannot be accessed.", capability, False, "permission_required")
        if capability == "file.search":
            matches = FileManager.search_files(str(args.get("query") or Path(source).name), search_path=str(args.get("scope") or Path.home()), max_results=min(50, int(args.get("limit") or 20)))
            return self._result("completed", f"Found {len(matches)} matching files.", capability, True, data={"files": matches})
        if capability == "file.recent":
            roots = [Path.home() / "Downloads", Path.home() / "Documents", Path.home() / "Desktop"]
            files = sorted((p for root in roots if root.exists() for p in root.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
            return self._result("completed", f"Found {len(files)} recent files.", capability, True, data={"files": [str(p) for p in files]})
        if capability == "file.read":
            path = Path(source).resolve()
            if path.suffix.lower() not in {".txt", ".md", ".json", ".csv", ".log"}: return self._result("unsupported", "This file type is not supported for direct reading.", capability, False, "capability_unavailable")
            return self._result("completed", "File content is ready.", capability, True, data={"content": path.read_text(encoding="utf-8", errors="replace")[:200000]})
        if capability == "file.create":
            path = Path(source).resolve(); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(str(args.get("content") or ""), encoding="utf-8")
            return self._result("completed", f"Created {path.name}.", capability, path.exists(), data={"path": str(path)})
        if capability == "file.stat":
            stat = Path(source).resolve().stat(); return self._result("completed", "File information is ready.", capability, True, data={"size": stat.st_size, "modified_at": stat.st_mtime})
        if capability == "file.calculate_size":
            path = Path(source).resolve(); size = path.stat().st_size if path.is_file() else sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
            return self._result("completed", f"Size is {size} bytes.", capability, True, data={"size": size})
        if capability == "file.reveal":
            subprocess.Popen(["explorer", "/select,", str(Path(source).resolve())]); return self._result("completed", "File revealed in Explorer.", capability, True)
        handlers = {"file.open": lambda: FileManager.open_file(source), "file.list": lambda: FileManager.list_dir(source or None), "file.rename": lambda: FileManager.rename_path(source, destination), "file.copy": lambda: FileManager.copy_path(source, destination), "file.move": lambda: FileManager.move_path(source, destination), "file.delete": lambda: FileManager.delete_path(source), "directory.create": lambda: FileManager.create_folder(source), "directory.list": lambda: FileManager.list_dir(source or None)}
        message = str(handlers[capability]()); failed = message.lower().startswith(("failed", "file not found"))
        return self._result("error" if failed else "completed", message, capability, not failed, None if not failed else "execution_failed")

    def _network(self, capability: str) -> dict[str, Any]:
        if capability in {"wifi.current_network", "wifi.list_networks"}:
            argv = ["netsh", "wlan", "show", "interfaces" if capability.endswith("network") else "networks"]
            output = subprocess.run(argv, capture_output=True, text=True, timeout=8).stdout
            return self._result("completed", "Wi-Fi information is ready.", capability, bool(output), data={"details": output[:8000]})
        data = {name: [item.address for item in values if item.address] for name, values in psutil.net_if_addrs().items()}
        return self._result("completed", "Network information is ready.", capability, True, data={"interfaces": data})

    def _wifi_radio(self, capability: str) -> dict[str, Any]:
        adapters = [name for name in psutil.net_if_addrs() if "wi-fi" in name.lower() or "wireless" in name.lower()]
        if not adapters: return self._result("unsupported", "No Wi-Fi adapter was detected.", capability, False, "hardware_unsupported")
        name = adapters[0]; enabled = capability == "wifi.enable"
        completed = subprocess.run(["netsh", "interface", "set", "interface", f"name={name}", f"admin={'enabled' if enabled else 'disabled'}"], capture_output=True, text=True, timeout=10)
        time.sleep(.5); state = psutil.net_if_stats().get(name); verified = completed.returncode == 0 and bool(state) and bool(state.isup) == enabled
        error = None if verified else ("permission_required" if completed.returncode else "verification_failed")
        return self._result("completed" if verified else "error", f"Wi-Fi {'enabled' if enabled else 'disabled'}." if verified else "Wi-Fi state could not be verified.", capability, verified, error)

    def _input(self, capability: str, args: dict[str, Any]) -> dict[str, Any]:
        import pyautogui
        if capability == "input.type_text":
            text = str(args.get("text") or "")
            if not text: return self._result("needs_clarification", "What should I type?", capability, False, "missing_text")
            pyautogui.write(text, interval=min(.05, float(args.get("interval", .01))))
        else:
            keys = {"input.copy": ("ctrl", "c"), "input.cut": ("ctrl", "x"), "input.paste": ("ctrl", "v"), "input.select_all": ("ctrl", "a"), "input.undo": ("ctrl", "z"), "input.redo": ("ctrl", "y"), "input.save": ("ctrl", "s")}
            if capability == "input.hotkey":
                requested = tuple(str(k).lower() for k in args.get("keys", [])); allowed = {("ctrl", "f"), ("ctrl", "shift", "s"), ("alt", "tab"), ("escape",)}
                if requested not in allowed: return self._result("error", "That shortcut is not allowed.", capability, False, "permission_required")
                keys_to_press = requested
            else: keys_to_press = keys[capability]
            pyautogui.hotkey(*keys_to_press)
        return self._result("completed", "Keyboard action completed.", capability, True)

    def _storage(self, capability: str, args: dict[str, Any]) -> dict[str, Any]:
        partitions = psutil.disk_partitions(all=False)
        rows = []
        for part in partitions:
            try: usage = psutil.disk_usage(part.mountpoint)
            except OSError: continue
            rows.append({"device": part.device, "mountpoint": part.mountpoint, "fstype": part.fstype, "total": usage.total, "used": usage.used, "free": usage.free, "removable": "removable" in part.opts.lower()})
        if capability == "storage.open_drive":
            target = str(args.get("drive") or args.get("path") or "")
            row = next((r for r in rows if target.lower() in {r["device"].lower(), r["mountpoint"].lower()}), None)
            if not row: return self._result("error", "That drive was not found.", capability, False, "target_not_found")
            os.startfile(row["mountpoint"]); return self._result("completed", "Drive opened.", capability, True)
        selected = [r for r in rows if r["removable"]] if capability == "storage.removable_devices" else rows
        return self._result("completed", f"Found {len(selected)} drive(s).", capability, True, data={"drives": selected})

    def _printer(self, capability: str, args: dict[str, Any]) -> dict[str, Any]:
        import win32print
        printers = [item[2] for item in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
        default = win32print.GetDefaultPrinter() if printers else None
        if capability == "printer.open_settings": os.startfile("ms-settings:printers"); return self._result("completed", "Printer settings opened.", capability, True)
        if capability in {"printer.list", "printer.default", "printer.status"}: return self._result("completed", f"Found {len(printers)} printer(s).", capability, True, data={"printers": printers, "default": default})
        if capability == "printer.print_file":
            source = Path(str(args.get("path") or "")).resolve()
            if not source.is_file(): return self._result("error", "Choose an existing file to print.", capability, False, "target_not_found")
            os.startfile(str(source), "print"); return self._result("completed", f"Sent {source.name} to the printer.", capability, True)
        return self._result("unsupported", "Printer queue control is not available through the installed Windows API.", capability, False, "capability_unavailable")

    def _system_info(self, capability: str) -> dict[str, Any]:
        battery = psutil.sensors_battery(); mapping = {
            "system.os_version": {"system": platform.system(), "release": platform.release(), "version": platform.version()},
            "system.device_name": {"device_name": socket.gethostname()},
            "system.cpu_info": {"processor": platform.processor(), "logical_cores": psutil.cpu_count()},
            "system.memory_info": dict(psutil.virtual_memory()._asdict()),
            "system.disk_info": {"drives": [{"mountpoint": p.mountpoint, **dict(psutil.disk_usage(p.mountpoint)._asdict())} for p in psutil.disk_partitions(False) if os.path.exists(p.mountpoint)]},
            "system.battery_info": dict(battery._asdict()) if battery else {"available": False},
            "system.network_info": {"interfaces": list(psutil.net_if_addrs())},
            "system.display_info": {"displays": self._monitors()},
        }
        return self._result("completed", "System information is ready.", capability, True, data=mapping[capability])

    @staticmethod
    def _from_message(capability: str, message: Any) -> dict[str, Any]:
        text = str(message); failed = text.lower().startswith("failed")
        return WindowsCapabilityRuntime._result("error" if failed else "completed", text, capability, not failed, None if not failed else "execution_failed")

    @staticmethod
    def _result(status: str, message: str, capability: str, verified: bool, error_code: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"status": status, "message": message, "capability": capability, "verified": verified, "error_code": error_code, **(data or {})}
