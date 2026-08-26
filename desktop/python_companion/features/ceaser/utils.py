# ceaser/utils.py
import os
import logging
import platform
import psutil
import tempfile
import shutil
import hashlib
# import speedtest  # Commented out - optional dependency
import subprocess
import requests

def is_question_command(command):
    """Detect if command contains question keywords that should route to ChatGPT API"""
    question_keywords = [
        "explain", "what", "which", "why", "how", "when", "where", "who", "whose", "whom",
        "what is", "what are", "what does", "what do", "what was", "what will",
        "how to", "how do", "how does", "how can", "how would", "how should",
        "why is", "why are", "why does", "why do", "why was", "why will",
        "when is", "when are", "when does", "when do", "when was", "when will",
        "where is", "where are", "where does", "where do", "where was", "where will",
        "who is", "who are", "who does", "who do", "who was", "who will",
        "tell me about", "describe", "define", "define what", "what does it mean",
        "can you explain", "could you explain", "please explain", "i want to know",
        "i need to know", "help me understand", "what's the difference", "what's the meaning",
        "how does it work", "what causes", "what makes", "what creates", "what produces"
    ]
    command_lower = command.lower().strip()
    
    # Exclude weather and news commands from question detection
    if any(x in command_lower for x in ["weather", "temperature", "forecast", "news", "headlines", "latest", "in india", "in japan", "in china", "in uk", "in usa", "in canada", "in australia", "in germany", "in france", "in brazil", "in russia", "in south korea", "in italy", "in spain", "in mexico", "in singapore", "in uae", "in saudi arabia", "in south africa"]):
        return False
    
    for keyword in question_keywords:
        if command_lower.startswith(keyword) or f" {keyword} " in command_lower:
            return True
    if "?" in command:
        return True
    return False


def map_command_to_service(command: str):
    cmd = command.lower()
    # Refined keyword-based mapping for device control (remove generic words)
    device_keywords = [
        'open', 'close', 'volume', 'brightness', 'calculator', 'notepad', 'chrome', 'firefox', 'edge', 'explorer', 'paint', 'word', 'excel', 'powerpoint', 'outlook', 'spotify', 'discord', 'steam', 'zoom', 'teams', 'slack', 'vscode', 'visual studio', 'photoshop', 'illustrator', 'premiere', 'after effects', 'blender', 'unity', 'unreal', 'obs', 'audacity', 'vlc', 'winrar', '7zip', 'adobe reader', 'lock', 'shutdown', 'restart', 'sleep', 'hibernate', 'log off', 'sign out', 'logout', 'minimize all', 'show desktop', 'maximize', 'full screen', 'switch window', 'alt tab', 'copy', 'ctrl c', 'paste', 'ctrl v', 'cut', 'ctrl x', 'undo', 'ctrl z', 'redo', 'ctrl y', 'select all', 'ctrl a', 'save', 'ctrl s', 'new', 'ctrl n', 'open', 'ctrl o', 'print', 'ctrl p', 'find', 'ctrl f', 'replace', 'ctrl h', 'refresh', 'f5', 'back', 'go back', 'forward', 'go forward', 'home', 'go home', 'end', 'go to end', 'page up', 'page down', 'delete', 'del', 'enter', 'return', 'escape', 'esc', 'tab', 'space', 'spacebar', 'screenshot'
    ]
    for keyword in device_keywords:
        if keyword in cmd:
            return 'device_control'
    # Expanded keyword-based mapping for YouTube Music
    youtube_keywords = [
        'youtube', 'play', 'song', 'music', 'video', 'search'
    ]
    for keyword in youtube_keywords:
        if keyword in cmd:
            return 'youtube_music'
    # Expanded keyword-based mapping for News
    news_keywords = [
        'news', 'headlines', 'latest'
    ]
    for keyword in news_keywords:
        if keyword in cmd:
            return 'news'
    # Expanded keyword-based mapping for Weather
    weather_keywords = [
        'weather', 'temperature', 'forecast'
    ]
    for keyword in weather_keywords:
        if keyword in cmd:
            return 'weather'
    # Expanded keyword-based mapping for Note Taking
    note_keywords = [
        'note', 'write', 'save', 'remember', 'notepad'
    ]
    for keyword in note_keywords:
        if keyword in cmd:
            return 'note_taking'
    # Expanded keyword-based mapping for Spotify
    spotify_keywords = [
        'spotify', 'play', 'song'
    ]
    for keyword in spotify_keywords:
        if keyword in cmd:
            return 'spotify'
    # Expanded keyword-based mapping for Amazon
    amazon_keywords = [
        'amazon', 'shop', 'buy'
    ]
    for keyword in amazon_keywords:
        if keyword in cmd:
            return 'amazon'
    # Expanded keyword-based mapping for Translation
    translation_keywords = [
        'translate', 'language'
    ]
    for keyword in translation_keywords:
        if keyword in cmd:
            return 'translation'
    # Expanded keyword-based mapping for Reminders
    reminder_keywords = [
        'remind', 'reminder'
    ]
    for keyword in reminder_keywords:
        if keyword in cmd:
            return 'notifications'
    # Expanded keyword-based mapping for Vision
    vision_keywords = [
        'what\'s in my hand', 'what do you see', 'object in my hand', 'detect object', 'detect in camera', 'what am i holding'
    ]
    for keyword in vision_keywords:
        if keyword in cmd:
            return 'vision'
    # Expanded keyword-based mapping for Automation
    automation_keywords = [
        'automate', 'schedule', 'routine'
    ]
    for keyword in automation_keywords:
        if keyword in cmd:
            return 'automation'
    # Expanded keyword-based mapping for Fun
    fun_keywords = [
        'joke', 'fun', 'game'
    ]
    for keyword in fun_keywords:
        if keyword in cmd:
            return 'fun'
    # Expanded keyword-based mapping for Health
    health_keywords = [
        'health'
    ]
    for keyword in health_keywords:
        if keyword in cmd:
            return 'health'
    # Expanded keyword-based mapping for Memory
    memory_keywords = [
        'memory', 'recall'
    ]
    for keyword in memory_keywords:
        if keyword in cmd:
            return 'memory'
    # Expanded keyword-based mapping for AI Assistant
    ai_keywords = [
        'ai', 'chat'
    ]
    for keyword in ai_keywords:
        if keyword in cmd:
            return 'ai'
    
    # Fallback to AI Assistant if no specific service is found
    return 'ai'


class Utils:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def handle_voice_command(self, cmd: str) -> str:
        """Handle utility voice commands"""
        cmd_lower = cmd.lower().strip()
        
        if 'system' in cmd_lower:
            return self._handle_system_utils(cmd)
        elif 'file' in cmd_lower or 'folder' in cmd_lower:
            return self._handle_file_utils(cmd)
        elif 'network' in cmd_lower or 'internet' in cmd_lower:
            return self._handle_network_utils(cmd)
        elif 'process' in cmd_lower or 'task' in cmd_lower:
            return self._handle_process_utils(cmd)
        elif 'help' in cmd_lower:
            return self._get_utils_help()
        else:
            return "Available utility commands: system, file, network, process, help"
    
    def _handle_system_utils(self, cmd: str) -> str:
        """Handle system utility commands"""
        if 'info' in cmd or 'status' in cmd:
            return self._get_system_info()
        elif 'cleanup' in cmd or 'clean' in cmd:
            return self._system_cleanup()
        elif 'optimize' in cmd or 'performance' in cmd:
            return self._optimize_system()
        else:
            return "System utilities: info, cleanup, optimize"
    
    def _handle_file_utils(self, cmd: str) -> str:
        """Handle file utility commands"""
        if 'organize' in cmd:
            return self._organize_files()
        elif 'duplicate' in cmd:
            return self._find_duplicates()
        elif 'backup' in cmd:
            return self._create_backup()
        else:
            return "File utilities: organize, duplicate, backup"
    
    def _handle_network_utils(self, cmd: str) -> str:
        """Handle network utility commands"""
        if 'speed' in cmd or 'test' in cmd:
            return self._test_network_speed()
        elif 'ping' in cmd:
            return self._ping_test()
        elif 'connection' in cmd:
            return self._check_connection()
        else:
            return "Network utilities: speed test, ping, connection"
    
    def _handle_process_utils(self, cmd: str) -> str:
        """Handle process utility commands"""
        if 'list' in cmd or 'show' in cmd:
            return self._list_processes()
        elif 'kill' in cmd or 'stop' in cmd:
            return self._kill_process(cmd)
        elif 'monitor' in cmd:
            return self._monitor_processes()
        else:
            return "Process utilities: list, kill, monitor"
    
    def _get_system_info(self) -> str:
        """Get system information"""
        try:
            import platform
            import psutil
            
            info = {
                'os': platform.system(),
                'version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor(),
                'cpu_count': psutil.cpu_count(),
                'memory_total': f"{psutil.virtual_memory().total / (1024**3):.1f} GB",
                'disk_total': f"{psutil.disk_usage('/').total / (1024**3):.1f} GB"
            }
            
            return f"System Info: {info['os']} {info['version']}, CPU: {info['cpu_count']} cores, RAM: {info['memory_total']}, Disk: {info['disk_total']}"
        except Exception as e:
            return f"Error getting system info: {e}"
    
    def _system_cleanup(self) -> str:
        """Perform system cleanup"""
        try:
            import tempfile
            import shutil
            
            # Clean temp files
            temp_dir = tempfile.gettempdir()
            temp_files = len(os.listdir(temp_dir))
            
            # Clean browser cache (basic)
            cache_dirs = [
                os.path.expanduser("~/.cache"),
                os.path.expanduser("~/AppData/Local/Temp")
            ]
            
            cleaned = 0
            for cache_dir in cache_dirs:
                if os.path.exists(cache_dir):
                    try:
                        for item in os.listdir(cache_dir):
                            item_path = os.path.join(cache_dir, item)
                            if os.path.isfile(item_path):
                                os.remove(item_path)
                                cleaned += 1
                    except Exception:
                        pass
            
            return f"System cleanup completed. Cleaned {cleaned} temporary files."
        except Exception as e:
            return f"Error during cleanup: {e}"
    
    def _optimize_system(self) -> str:
        """Optimize system performance"""
        try:
            import psutil
            
            # Get current system status
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            
            optimizations = []
            
            if cpu_percent > 80:
                optimizations.append("High CPU usage detected")
            
            if memory_percent > 80:
                optimizations.append("High memory usage detected")
            
            if optimizations:
                return f"System optimization needed: {'; '.join(optimizations)}"
            else:
                return "System is running optimally"
        except Exception as e:
            return f"Error optimizing system: {e}"
    
    def _organize_files(self) -> str:
        """Organize files in current directory"""
        try:
            import shutil
            
            current_dir = os.getcwd()
            organized = 0
            
            # Create organization folders
            folders = {
                'Documents': ['.pdf', '.doc', '.docx', '.txt'],
                'Images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp'],
                'Videos': ['.mp4', '.avi', '.mov', '.mkv'],
                'Music': ['.mp3', '.wav', '.flac', '.aac'],
                'Archives': ['.zip', '.rar', '.7z', '.tar']
            }
            
            for folder, extensions in folders.items():
                folder_path = os.path.join(current_dir, folder)
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)
                
                for file in os.listdir(current_dir):
                    if os.path.isfile(file):
                        file_ext = os.path.splitext(file)[1].lower()
                        if file_ext in extensions:
                            src = os.path.join(current_dir, file)
                            dst = os.path.join(folder_path, file)
                            shutil.move(src, dst)
                            organized += 1
            
            return f"File organization completed. Moved {organized} files."
        except Exception as e:
            return f"Error organizing files: {e}"
    
    def _find_duplicates(self) -> str:
        """Find duplicate files"""
        try:
            import hashlib
            
            current_dir = os.getcwd()
            file_hashes = {}
            duplicates = []
            
            for root, dirs, files in os.walk(current_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'rb') as f:
                            file_hash = hashlib.md5(f.read()).hexdigest()
                            
                        if file_hash in file_hashes:
                            duplicates.append((file_hashes[file_hash], file_path))
                        else:
                            file_hashes[file_hash] = file_path
                    except Exception:
                        pass
            
            return f"Found {len(duplicates)} duplicate files."
        except Exception as e:
            return f"Error finding duplicates: {e}"
    
    def _create_backup(self) -> str:
        """Create backup of important files"""
        try:
            import shutil
            from datetime import datetime
            
            backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.makedirs(backup_dir, exist_ok=True)
            
            # Backup common important directories
            important_dirs = [
                os.path.expanduser("~/Documents"),
                os.path.expanduser("~/Desktop"),
                os.path.expanduser("~/Pictures")
            ]
            
            backed_up = 0
            for dir_path in important_dirs:
                if os.path.exists(dir_path):
                    dir_name = os.path.basename(dir_path)
                    backup_path = os.path.join(backup_dir, dir_name)
                    shutil.copytree(dir_path, backup_path)
                    backed_up += 1
            
            return f"Backup created: {backup_dir} with {backed_up} directories."
        except Exception as e:
            return f"Error creating backup: {e}"
    
    def _test_network_speed(self) -> str:
        """Test network speed"""
        try:
            try:
                import speedtest
                
                st = speedtest.Speedtest()
                st.get_best_server()
                
                download_speed = st.download() / 1_000_000  # Convert to Mbps
                upload_speed = st.upload() / 1_000_000  # Convert to Mbps
                
                return f"Network Speed: Download {download_speed:.1f} Mbps, Upload {upload_speed:.1f} Mbps"
            except ImportError:
                return "Speedtest module not available. Install with: pip install speedtest-cli"
        except Exception as e:
            return f"Error testing network speed: {e}"
    
    def _ping_test(self) -> str:
        """Test ping to common servers"""
        try:
            import subprocess
            
            servers = ['8.8.8.8', '1.1.1.1', 'google.com']
            results = []
            
            for server in servers:
                try:
                    result = subprocess.run(['ping', '-n', '1', server], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        results.append(f"{server}: OK")
                    else:
                        results.append(f"{server}: Failed")
                except Exception:
                    results.append(f"{server}: Timeout")
            
            return f"Ping test: {'; '.join(results)}"
        except Exception as e:
            return f"Error testing ping: {e}"
    
    def _check_connection(self) -> str:
        """Check internet connection"""
        try:
            import requests
            
            response = requests.get('http://www.google.com', timeout=5)
            if response.status_code == 200:
                return "Internet connection: OK"
            else:
                return "Internet connection: Limited"
        except Exception:
            return "Internet connection: Failed"
    
    def _list_processes(self) -> str:
        """List running processes"""
        try:
            import psutil
            
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Sort by CPU usage
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
            
            top_processes = processes[:5]
            result = "Top processes by CPU usage:\n"
            for proc in top_processes:
                result += f"{proc['name']}: {proc['cpu_percent']:.1f}% CPU, {proc['memory_percent']:.1f}% RAM\n"
            
            return result
        except Exception as e:
            return f"Error listing processes: {e}"
    
    def _kill_process(self, cmd: str) -> str:
        """Kill a specific process"""
        try:
            import psutil
            
            # Extract process name from command
            process_name = None
            for word in cmd.split():
                if word not in ['kill', 'stop', 'process']:
                    process_name = word
                    break
            
            if not process_name:
                return "Please specify which process to kill"
            
            killed = 0
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if process_name.lower() in proc.info['name'].lower():
                        proc.terminate()
                        killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            return f"Killed {killed} process(es) matching '{process_name}'"
        except Exception as e:
            return f"Error killing process: {e}"
    
    def _monitor_processes(self) -> str:
        """Monitor system processes"""
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('/').percent
            
            return f"System Monitor: CPU {cpu_percent}%, RAM {memory_percent}%, Disk {disk_percent}%"
        except Exception as e:
            return f"Error monitoring processes: {e}"
    
    def _get_utils_help(self) -> str:
        """Get help for utilities"""
        return """Available Utilities:
        
System: info, cleanup, optimize
File: organize, duplicate, backup  
Network: speed test, ping, connection
Process: list, kill, monitor

Say 'system info' for system information, 'file organize' to organize files, etc."""


def route_command(command, modules):
    """
    Route command to the correct module. 'modules' is a dict with all assistants and helpers.
    """
    cmd = command.lower().strip()
    ai = modules['ai']
    device_control = modules['device_control']
    youtube_music = modules['youtube_music']
    note_taking = modules['note_taking']
    weather = modules['weather']
    news = modules['news']
    spotify = modules['spotify']
    amazon = modules['amazon']
    translation = modules['translation']
    notifications = modules['notifications']
    vision = modules['vision']
    automation = modules['automation']
    fun = modules['fun']
    health = modules['health']
    memory = modules['memory']
    # 1. AI Core - Question Detection
    if is_question_command(command):
        try:
            response = ai.chat(command)
            # Organize AI response into sections if possible
            sections = []
            if response:
                # Split by numbered/bulleted list or paragraphs
                import re
                # Try to split by numbered list
                numbered = re.split(r'\n\d+\. ', response)
                if len(numbered) > 1:
                    sections = [numbered[0].strip()] + [f"{i+1}. {s.strip()}" for i, s in enumerate(numbered[1:])]
                else:
                    # Try to split by bullet points
                    bullets = re.split(r'\n[-*•]\s+', response)
                    if len(bullets) > 1:
                        sections = [b.strip() for b in bullets if b.strip()]
                    else:
                        # Split by double newlines (paragraphs)
                        paras = [p.strip() for p in response.split('\n\n') if p.strip()]
                        if len(paras) > 1:
                            sections = paras
            return {
                "type": "ai",
                "raw": response,
                "sections": sections if sections else [response] if response else []
            }
        except Exception as e:
            return {"type": "ai", "raw": f"Sorry, I'm having trouble connecting to my AI brain: {e}", "sections": []}
    # 2. YouTube
    if ("youtube" in cmd and ("play" in cmd or "song" in cmd or "music" in cmd or "video" in cmd or "search" in cmd)) or cmd.startswith("play "):
        return youtube_music.handle_voice_command(cmd)
    if cmd in ["open youtube", "youtube"]:
        import webbrowser
        webbrowser.open("https://www.youtube.com/")
        return "YouTube opened in your browser."
    if any(x in cmd for x in ["pause", "resume", "skip", "next", "previous", "back", "forward", "mute", "unmute", "volume up", "volume down", "fullscreen"]):
        return youtube_music.handle_voice_command(cmd)
    # 3. Note taking
    if any(x in cmd for x in ["note", "write", "save", "remember", "notepad"]):
        return note_taking.handle_voice_command(cmd)
    # 4. Weather
    if any(x in cmd for x in ["weather", "temperature", "forecast"]):
        city = "New York"  # Default city
        if "weather in" in cmd or "weather for" in cmd:
            parts = cmd.split()
            for i, part in enumerate(parts):
                if part in ["in", "for"] and i + 1 < len(parts):
                    city = parts[i + 1]
                    break
        weather_data = weather.get_current_weather(city)
        if weather_data['success']:
            return weather.format_weather_report(weather_data)
        else:
            return f"Sorry, I couldn't get the weather: {weather_data['error']}"
    # 5. News
    if any(x in cmd for x in ["news", "headlines", "latest"]):
        country_code = None
        country_name = None
        if "in " in cmd or "from " in cmd:
            parts = cmd.split()
            for i, part in enumerate(parts):
                if part in ["in", "from"] and i + 1 < len(parts):
                    country_name = parts[i + 1].capitalize()
                    break
        country_mapping = {
            'india': 'in', 'japan': 'jp', 'china': 'cn', 'uk': 'gb', 'united kingdom': 'gb',
            'usa': 'us', 'united states': 'us', 'america': 'us', 'canada': 'ca',
            'germany': 'de', 'france': 'fr', 'brazil': 'br', 'russia': 'ru', 'south korea': 'kr',
            'italy': 'it', 'spain': 'es', 'mexico': 'mx', 'singapore': 'sg', 'uae': 'ae', 'saudi arabia': 'sa', 'south africa': 'za'
        }
        if country_name:
            country_code = country_mapping.get(country_name.lower())
            if country_code:
                news_data = news.get_top_headlines(country=country_code)
            else:
                return {"type": "news", "error": f"Sorry, I don't have news for {country_name}. Available countries: USA, UK, India, Japan, China, Canada, Australia, Germany, France, Brazil, Russia, South Korea, Italy, Spain, Mexico, Singapore, UAE, Saudi Arabia, South Africa."}
        else:
            news_data = news.get_top_headlines()
        if news_data['success']:
            # Organize headlines for frontend
            headlines = [
                {
                    "title": a["title"],
                    "source": a["source"],
                    "description": a["description"]
                } for a in news_data["articles"]
            ]
            # summary is now empty, so frontend uses only headlines
            return {
                "type": "news",
                "headlines": headlines,
                "summary": ""
            }
        else:
            return {"type": "news", "error": f"Sorry, I couldn't get the news: {news_data['error']}"}
    # 6. Device/App Control
    if any(x in cmd for x in [
        'open', 'close', 'volume', 'brightness', 'calculator', 'notepad', 'chrome', 'firefox', 'edge', 'explorer', 'paint', 'word', 'excel', 'powerpoint', 'outlook', 'spotify', 'discord', 'steam', 'zoom', 'teams', 'slack', 'vscode', 'visual studio', 'photoshop', 'illustrator', 'premiere', 'after effects', 'blender', 'unity', 'unreal', 'obs', 'audacity', 'vlc', 'winrar', '7zip', 'adobe reader', 'lock', 'shutdown', 'restart', 'sleep', 'hibernate', 'log off', 'sign out', 'logout', 'minimize all', 'show desktop', 'maximize', 'full screen', 'switch window', 'alt tab', 'copy', 'ctrl c', 'paste', 'ctrl v', 'cut', 'ctrl x', 'undo', 'ctrl z', 'redo', 'ctrl y', 'select all', 'ctrl a', 'save', 'ctrl s', 'new', 'ctrl n', 'open', 'ctrl o', 'print', 'ctrl p', 'find', 'ctrl f', 'replace', 'ctrl h', 'refresh', 'f5', 'back', 'go back', 'forward', 'go forward', 'home', 'go home', 'end', 'go to end', 'page up', 'page down', 'delete', 'del', 'enter', 'return', 'escape', 'esc', 'tab', 'space', 'spacebar', 'screenshot']):
        from backend.api_server_integrated import SERVICES
        device_service = next((s for s in SERVICES if s['id'] == 'device_control'), None)
        if not device_service or not device_service.get('isActive', False):
            return 'Device Control is disabled, please enable to use.'
        return device_control.control_device(cmd)
    # 7. Spotify
    if any(x in cmd for x in ["music", "spotify", "play", "song"]) and not "youtube" in cmd:
        try:
            result = spotify.get_current_playback()
            if result is None or (isinstance(result, str) and ("no refresh token" in result.lower() or "not connected" in result.lower() or "error" in result.lower())):
                return "Spotify is not connected. Please link your account to use Spotify features."
            return result
        except Exception:
            return "Spotify is not connected. Please link your account to use Spotify features."
    # 8. Web Search
    if any(x in cmd for x in ["search google", "google search", "search for"]) or (cmd.startswith("search ") and "google" in cmd):
        import webbrowser
        if "search google" in cmd:
            query = cmd.replace("search google", "").strip()
        elif "google search" in cmd:
            query = cmd.replace("google search", "").strip()
        elif cmd.startswith("search ") and "google" in cmd:
            query = cmd.replace("search", "").replace("google", "").strip()
        else:
            query = cmd.replace("search", "").strip()
        if query:
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(search_url)
            return f"Searching Google for '{query}'"
        else:
            return "Please specify what to search for."
    # 9. Shopping
    if any(x in cmd for x in ["amazon", "shop", "buy"]):
        return amazon.handle_voice_command(cmd)
    # 10. Translation
    if any(x in cmd for x in ["translate", "language"]):
        return translation.translate(cmd, "es")
    # 11. Reminders
    if any(x in cmd for x in ["remind", "reminder"]):
        return notifications.set_reminder(cmd, "in 1 minute")
    # 12. Vision
    if any(x in cmd for x in ["what's in my hand", "what do you see", "object in my hand", "detect object", "detect in camera", "what am i holding"]):
        # Vision detection loop: interactive, voice-driven
        voice = modules.get('voice')
        ai = modules['ai']
        vision = modules['vision']
        if not voice:
            return vision.detect_object_with_camera()  # fallback: single detection
        voice.speak("Activating object detection. Show me the object in your hand. Say 'stop detection' anytime to exit.")
        while True:
            detected = vision.detect_object_with_camera()
            voice.speak(f"I see: {detected}. Do you want me to explain about that?")
            response = voice.listen()
            if response and "yes" in response.lower():
                explanation = ai.chat(f"Explain the object: {detected}.")
                voice.speak(explanation)
            elif response and "no" in response.lower():
                voice.speak("Do you want me to leave detection?")
                leave_response = voice.listen()
                if leave_response and "yes" in leave_response.lower():
                    voice.speak("Leaving detection mode. Ready for your next command.")
                    break
                elif leave_response and "no" in leave_response.lower():
                    voice.speak("Continuing detection. Show me the next object or say 'stop detection' to exit.")
                    continue
            # Listen for 'stop detection' at any time
            if response and "stop detection" in response.lower():
                voice.speak("Detection stopped. Ready for your next command.")
                break
        return "Vision detection loop ended."
    # 13. Automation
    if any(x in cmd for x in ["automate", "schedule", "routine"]):
        return automation.automate_task(cmd)
    # 14. Fun
    if any(x in cmd for x in ["joke", "fun", "game"]):
        return fun.tell_joke()
    # 15. Health
    if any(x in cmd for x in ["health"]):
        return health  # Implement health feature as needed
    # 16. Memory
    if any(x in cmd for x in ["memory", "recall"]):
        return memory.recall(cmd)
    # Fallback
    return "Sorry, I didn't understand that command. Please try again or say 'help' for options." 