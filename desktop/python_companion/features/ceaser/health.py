import psutil
import platform
import os

class HealthAssistant:
    def __init__(self):
        pass

    @staticmethod
    def get_cpu_usage():
        try:
            return psutil.cpu_percent(interval=1)
        except Exception as e:
            return f"Failed to get CPU usage: {e}"

    @staticmethod
    def get_memory_usage():
        try:
            mem = psutil.virtual_memory()
            return {'total': mem.total, 'used': mem.used, 'percent': mem.percent}
        except Exception as e:
            return f"Failed to get memory usage: {e}"

    @staticmethod
    def get_disk_usage():
        try:
            disk = psutil.disk_usage(os.path.abspath(os.sep))
            return {'total': disk.total, 'used': disk.used, 'percent': disk.percent}
        except Exception as e:
            return f"Failed to get disk usage: {e}"

    @staticmethod
    def get_battery_status():
        try:
            battery = psutil.sensors_battery()
            if battery:
                return {'percent': battery.percent, 'plugged': battery.power_plugged}
            else:
                return 'No battery found.'
        except Exception as e:
            return f"Failed to get battery status: {e}"

    @staticmethod
    def get_os_info():
        try:
            return {
                'system': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor()
            }
        except Exception as e:
            return f"Failed to get OS info: {e}" 