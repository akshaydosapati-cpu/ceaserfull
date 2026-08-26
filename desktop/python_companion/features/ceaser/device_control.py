import os
import subprocess
import sys
import ctypes
import psutil

class DeviceControl:
    @staticmethod
    def open_app(app_path_or_name):
        """Open an application by path or name (e.g., 'notepad', 'calc', or full path)."""
        try:
            if os.path.isfile(app_path_or_name):
                subprocess.Popen([app_path_or_name])
            else:
                subprocess.Popen([app_path_or_name], shell=True)
            return f"Opened: {app_path_or_name}"
        except Exception as e:
            return f"Failed to open {app_path_or_name}: {e}"

    @staticmethod
    def close_app(process_name):
        """Close all processes matching the given name (e.g., 'notepad.exe')."""
        closed = 0
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and proc.info['name'].lower() == process_name.lower():
                try:
                    proc.terminate()
                    closed += 1
                except Exception:
                    pass
        if closed:
            return f"Closed {closed} instance(s) of {process_name}"
        else:
            return f"No running process found: {process_name}"

    @staticmethod
    def lock_workstation():
        """Lock the Windows workstation."""
        try:
            ctypes.windll.user32.LockWorkStation()
            return "Workstation locked."
        except Exception as e:
            return f"Failed to lock workstation: {e}"

    @staticmethod
    def shutdown():
        """Shutdown the computer."""
        try:
            os.system('shutdown /s /t 1')
            return "Shutdown initiated."
        except Exception as e:
            return f"Failed to shutdown: {e}"

    @staticmethod
    def restart():
        """Restart the computer."""
        try:
            os.system('shutdown /r /t 1')
            return "Restart initiated."
        except Exception as e:
            return f"Failed to restart: {e}"

    @staticmethod
    def sleep():
        """Put the computer to sleep."""
        try:
            ctypes.windll.PowrProf.SetSuspendState(0, 1, 0)
            return "Sleep mode activated."
        except Exception as e:
            return f"Failed to sleep: {e}"

    @staticmethod
    def take_screenshot(save_path='screenshot.png'):
        """Take a screenshot and save to the given path. Tries pyautogui, then PIL.ImageGrab."""
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            screenshot.save(save_path)
            return f"Screenshot saved to {save_path}"
        except Exception as e1:
            try:
                from PIL import ImageGrab
                screenshot = ImageGrab.grab()
                screenshot.save(save_path)
                return f"Screenshot saved to {save_path} (ImageGrab fallback)"
            except Exception as e2:
                return f"Failed to take screenshot: {e1} | Fallback error: {e2}"

    @staticmethod
    def copy_to_clipboard(text):
        """Copy text to clipboard."""
        try:
            import pyperclip
            pyperclip.copy(text)
            return "Text copied to clipboard."
        except Exception as e:
            return f"Failed to copy to clipboard: {e}"

    @staticmethod
    def paste_from_clipboard():
        """Paste text from clipboard."""
        try:
            import pyperclip
            return pyperclip.paste()
        except Exception as e:
            return f"Failed to paste from clipboard: {e}"

    @staticmethod
    def clear_clipboard():
        """Clear the clipboard."""
        try:
            import pyperclip
            pyperclip.copy('')
            return "Clipboard cleared."
        except Exception as e:
            return f"Failed to clear clipboard: {e}"

    @staticmethod
    def mute_volume():
        """Mute system volume (Windows only)."""
        try:
            import ctypes
            # Simulate pressing the volume mute key
            VK_VOLUME_MUTE = 0xAD
            ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 2, 0)
            return "System volume muted."
        except Exception as e:
            return f"Failed to mute volume: {e}"

    @staticmethod
    def unmute_volume():
        """Unmute system volume (Windows only)."""
        # On Windows, toggling mute again unmutes
        return DeviceControl.mute_volume()

    @staticmethod
    def set_volume(level):
        """Set system volume (0-100, Windows only)."""
        try:
            import comtypes
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            # SetMasterVolumeLevelScalar expects 0.0 to 1.0
            volume.SetMasterVolumeLevelScalar(float(level) / 100, None)
            return f"System volume set to {level}%"
        except Exception as e:
            return f"Failed to set volume: {e}"

    @staticmethod
    def get_volume():
        """Get current system volume (0-100, Windows only)."""
        try:
            import comtypes
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            level = int(volume.GetMasterVolumeLevelScalar() * 100)
            return level
        except Exception as e:
            return f"Failed to get volume: {e}"

    @staticmethod
    def open_file(file_path):
        """Open a file/document with the default app (Windows only)."""
        try:
            os.startfile(file_path)
            return f"Opened file: {file_path}"
        except Exception as e:
            return f"Failed to open file: {e}"

    @staticmethod
    def open_url(url):
        """Open a URL in the default web browser."""
        try:
            import webbrowser
            # Ensure URL has protocol
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            webbrowser.open(url)
            return f"Opened URL: {url}"
        except Exception as e:
            return f"Failed to open URL {url}: {e}" 