import random
import time
import threading
import pyjokes
import requests

class FunAssistant:
    def __init__(self):
        self.jokes = [
            "Why did the computer show up at work late? It had a hard drive!",
            "Why do programmers prefer dark mode? Because light attracts bugs!",
            "Why did the developer go broke? Because he used up all his cache!"
        ]

    def tell_joke(self):
        return random.choice(self.jokes)

    def play_game(self):
        return "Let's play a game! (stub)"

    def sing_song(self):
        return 'Singing a song! (stub)'

class FunUtilities:
    @staticmethod
    def get_joke():
        try:
            return pyjokes.get_joke()
        except Exception as e:
            return f"Failed to get joke: {e}"

    @staticmethod
    def get_quote():
        try:
            import requests
            try:
                resp = requests.get('https://api.quotable.io/random', timeout=5)
                resp.raise_for_status()
                data = resp.json()
                return f'{data["content"]} — {data["author"]}'
            except requests.exceptions.SSLError as ssl_err:
                resp = requests.get('https://api.quotable.io/random', timeout=5, verify=False)
                if resp.status_code == 200:
                    data = resp.json()
                    return f'(SSL WARNING) {data["content"]} — {data["author"]}'
                else:
                    return f'Failed to fetch quote (SSL fallback): {resp.status_code}'
            except Exception as e:
                return f'Failed to get quote: {e}'
        except Exception as e:
            return f'Failed to get quote: {e}'

    @staticmethod
    def start_timer(seconds, callback=None):
        def timer_thread():
            time.sleep(seconds)
            if callback:
                callback()
        t = threading.Thread(target=timer_thread)
        t.start()
        return f'Timer started for {seconds} seconds.'

    @staticmethod
    def start_stopwatch(duration=10, callback=None):
        def stopwatch_thread():
            start = time.time()
            while time.time() - start < duration:
                time.sleep(1)
            if callback:
                callback()
        t = threading.Thread(target=stopwatch_thread)
        t.start()
        return f'Stopwatch started for {duration} seconds.'

    @staticmethod
    def set_alarm(seconds, callback=None):
        def alarm_thread():
            time.sleep(seconds)
            if callback:
                callback()
        t = threading.Thread(target=alarm_thread)
        t.start()
        return f'Alarm set for {seconds} seconds from now.' 