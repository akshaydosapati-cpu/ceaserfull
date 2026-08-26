import smtplib
from email.mime.text import MIMEText
import time
import webbrowser
import pyautogui
import subprocess
import os
import schedule
import threading

try:
    import pygetwindow as gw
except ImportError:
    gw = None

class AutomationAssistant:
    def __init__(self):
        self.automations = {}
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()

    def add_automation(self, name, time_str, action):
        # time_str: 'HH:MM' 24-hour format
        def job():
            action()
        schedule.every().day.at(time_str).do(job)
        self.automations[name] = {'time': time_str, 'action': action}

    def list_automations(self):
        return self.automations

    def remove_automation(self, name):
        if name in self.automations:
            del self.automations[name]
            # Note: schedule does not support removing jobs by name directly

    def _run_scheduler(self):
        while self.running:
            schedule.run_pending()
            time.sleep(1)

    def close(self):
        self.running = False
        self.thread.join()

    def automate_task(self, task_description):
        if 'email' in task_description.lower():
            # These should be set securely in production
            sender = 'your_email@gmail.com'
            password = 'your_password'
            recipient = 'recipient_email@gmail.com'
            subject = 'Automated Email from Jarvis'
            body = 'This is a test email sent by Jarvis.'
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = sender
            msg['To'] = recipient
            try:
                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                    server.login(sender, password)
                    server.sendmail(sender, recipient, msg.as_string())
                return 'Email sent.'
            except Exception as e:
                return f'Failed to send email: {e}'
        elif 'open website' in task_description:
            url = task_description.split('open website')[-1].strip()
            return self.open_website(url)
        elif 'search google for' in task_description:
            query = task_description.split('search google for')[-1].strip()
            return self.google_search(query)
        elif 'open chrome' in task_description.lower():
            return self.open_application('chrome')
        elif 'open firefox' in task_description.lower():
            return self.open_application('firefox')
        elif 'open edge' in task_description.lower():
            return self.open_application('edge')
        elif 'open notepad' in task_description.lower():
            return self.open_application('notepad')
        elif 'open calculator' in task_description.lower():
            return self.open_application('calculator')
        elif 'open spotify' in task_description.lower():
            return self.open_application('spotify')
        elif 'play music' in task_description.lower() or 'play song' in task_description.lower():
            # Extract song/artist from command
            if 'on youtube' in task_description.lower():
                query = task_description.lower().replace('play music', '').replace('play song', '').replace('on youtube', '').strip()
                return self.play_music_youtube(query)
            elif 'on spotify' in task_description.lower():
                query = task_description.lower().replace('play music', '').replace('play song', '').replace('on spotify', '').strip()
                return self.play_music_spotify(query)
            else:
                query = task_description.lower().replace('play music', '').replace('play song', '').strip()
                return self.play_music_youtube(query)  # Default to YouTube
        elif 'search youtube' in task_description.lower():
            query = task_description.lower().replace('search youtube', '').strip()
            return self.youtube_search(query)
        elif 'click button' in task_description:
            button_text = task_description.split('click button')[-1].strip()
            return self.click_button(button_text)
        elif 'fill field' in task_description:
            try:
                parts = task_description.split('fill field')[-1].strip().split('with')
                field_name = parts[0].strip()
                value = parts[1].strip()
                return self.fill_field(field_name, value)
            except Exception as e:
                return f'Could not fill field: {e}'
        elif 'move mouse to' in task_description:
            try:
                coords = task_description.split('move mouse to')[-1].strip().split(',')
                x = int(coords[0].strip())
                y = int(coords[1].strip())
                return self.move_mouse(x, y)
            except Exception as e:
                return f'Could not move mouse: {e}'
        elif 'type text' in task_description:
            text = task_description.split('type text')[-1].strip()
            return self.type_text(text)
        elif 'switch to window' in task_description:
            window_title = task_description.split('switch to window')[-1].strip()
            return self.switch_window(window_title)
        elif 'run script' in task_description:
            script_path = task_description.split('run script')[-1].strip()
            return self.run_script(script_path)
        return 'Automation task not recognized.'

    def open_website(self, url):
        try:
            webbrowser.open(url)
            return f'Opened website: {url}'
        except Exception as e:
            return f'Failed to open website: {e}'

    def google_search(self, query):
        try:
            url = f'https://www.google.com/search?q={query.replace(" ", "+")}'
            webbrowser.open(url)
            return f'Searched Google for: {query}'
        except Exception as e:
            return f'Failed to search Google: {e}'

    def click_button(self, button_text=None):
        try:
            # If button_text is provided, try to locate on screen (requires screenshot of button)
            if button_text:
                # Placeholder: In real use, would need image recognition
                return 'Button click by text not implemented. Use coordinates or image.'
            else:
                pyautogui.click()
                return 'Clicked at current mouse position.'
        except Exception as e:
            return f'Failed to click button: {e}'

    def fill_field(self, field_name, value):
        try:
            # Placeholder: In real use, would need image recognition or accessibility API
            pyautogui.typewrite(value)
            return f'Filled field {field_name} with {value}'
        except Exception as e:
            return f'Failed to fill field: {e}'

    def move_mouse(self, x, y):
        try:
            pyautogui.moveTo(x, y, duration=0.5)
            return f'Moved mouse to ({x}, {y})'
        except Exception as e:
            return f'Failed to move mouse: {e}'

    def type_text(self, text):
        try:
            pyautogui.typewrite(text)
            return f'Typed text: {text}'
        except Exception as e:
            return f'Failed to type text: {e}'

    def switch_window(self, window_title):
        if not gw:
            return 'pygetwindow not installed.'
        try:
            windows = gw.getWindowsWithTitle(window_title)
            if windows:
                win = windows[0]
                win.activate()
                return f'Switched to window: {window_title}'
            else:
                return f'Window not found: {window_title}'
        except Exception as e:
            return f'Failed to switch window: {e}'

    def run_script(self, script_path):
        try:
            if script_path.endswith('.py'):
                subprocess.Popen(['python', script_path], shell=True)
            else:
                os.startfile(script_path)
            return f'Ran script: {script_path}'
        except Exception as e:
            return f'Failed to run script: {e}'

    def open_application(self, app_name):
        """Open various applications"""
        try:
            app_commands = {
                'chrome': 'chrome',
                'firefox': 'firefox',
                'edge': 'msedge',
                'notepad': 'notepad',
                'calculator': 'calc',
                'spotify': 'spotify',
                'discord': 'discord',
                'teams': 'teams',
                'zoom': 'zoom',
                'vscode': 'code'
            }

            if app_name in app_commands:
                subprocess.Popen([app_commands[app_name]], shell=True)
                return f'Opened {app_name}'
            else:
                return f'Application {app_name} not supported'
        except Exception as e:
            return f'Failed to open {app_name}: {e}'

    def play_music_youtube(self, query):
        """Play music on YouTube"""
        try:
            search_url = f'https://www.youtube.com/results?search_query={query.replace(" ", "+")}'
            webbrowser.open(search_url)
            return f'Searching YouTube for: {query}'
        except Exception as e:
            return f'Failed to search YouTube: {e}'

    def play_music_spotify(self, query):
        """Play music on Spotify"""
        try:
            search_url = f'https://open.spotify.com/search/{query.replace(" ", "%20")}'
            webbrowser.open(search_url)
            return f'Searching Spotify for: {query}'
        except Exception as e:
            return f'Failed to search Spotify: {e}'

    def youtube_search(self, query):
        """Search YouTube"""
        try:
            search_url = f'https://www.youtube.com/results?search_query={query.replace(" ", "+")}'
            webbrowser.open(search_url)
            return f'Searched YouTube for: {query}'
        except Exception as e:
            return f'Failed to search YouTube: {e}'

    def execute_system_command(self, action_config):
        """Execute system commands based on action configuration"""
        try:
            command_type = action_config.get('systemCommand')

            if command_type == 'open_app':
                app = action_config.get('application')
                return self.open_application(app)

            elif command_type == 'play_music':
                platform = action_config.get('application')
                query = action_config.get('searchQuery', '')
                if platform == 'youtube':
                    return self.play_music_youtube(query)
                elif platform == 'spotify':
                    return self.play_music_spotify(query)
                else:
                    return self.play_music_youtube(query)  # Default to YouTube

            elif command_type == 'open_website':
                url = action_config.get('website', '')
                return self.open_website(url)

            elif command_type == 'search_web':
                engine = action_config.get('application', 'google')
                query = action_config.get('searchQuery', '')
                if engine == 'youtube':
                    return self.youtube_search(query)
                else:
                    return self.google_search(query)

            elif command_type == 'get_news':
                category = action_config.get('category', 'general')
                country = action_config.get('country', 'us')
                return self.get_news_briefing(category, country)

            elif command_type == 'get_weather':
                city = action_config.get('city', 'Mumbai')
                return self.get_weather_report(city)

            elif command_type == 'custom_command':
                command = action_config.get('systemCommand', '')
                return self.run_script(command)

            else:
                return f'Unknown system command: {command_type}'

        except Exception as e:
            return f'Failed to execute system command: {e}'

    def get_news_briefing(self, category='general', country='us'):
        """Get news briefing"""
        try:
            from features.ceaser.news_assistant import NewsAssistant
            news = NewsAssistant()
            headlines = news.get_top_headlines(category=category, country=country)
            if headlines and headlines.get('success'):
                return f"📰 News Briefing ({category.title()}): {headlines.get('message', 'Latest headlines retrieved')}"
            else:
                return f"❌ Failed to get news: {headlines.get('error', 'Unknown error')}"
        except Exception as e:
            return f"❌ News briefing failed: {e}"

    def get_weather_report(self, city='Mumbai'):
        """Get weather report"""
        try:
            from features.ceaser.weather_assistant import WeatherAssistant
            weather = WeatherAssistant()
            weather_data = weather.get_current_weather(city)
            if weather_data and weather_data.get('success'):
                return f"🌤️ Weather Report for {city}: {weather_data.get('message', 'Current weather retrieved')}"
            else:
                return f"❌ Failed to get weather: {weather_data.get('error', 'Unknown error')}"
        except Exception as e:
            return f"❌ Weather report failed: {e}" 