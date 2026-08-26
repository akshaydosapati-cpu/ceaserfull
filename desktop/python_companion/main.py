from fastapi import FastAPI, Body
from pydantic import BaseModel
import pyautogui
import pyttsx3
import speech_recognition as sr
from typing import List
import os
import sqlite3
import importlib.util
import sys

# Dynamically import ceaser modules
CEASER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend/ceaser'))
sys.path.append(CEASER_PATH)
def import_ceaser_module(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(CEASER_PATH, f"{name}.py"))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

automation = import_ceaser_module('automation')
device_control = import_ceaser_module('device_control')
notifications = import_ceaser_module('notifications')
youtube_music = import_ceaser_module('youtube_music')
news_assistant = import_ceaser_module('news_assistant')
weather_assistant = import_ceaser_module('weather_assistant')
spotify_integration = import_ceaser_module('spotify_integration')
amazon_shopping = import_ceaser_module('amazon_shopping')
translation = import_ceaser_module('translation')
vision = import_ceaser_module('vision')
fun = import_ceaser_module('fun')
health = import_ceaser_module('health')
memory = import_ceaser_module('memory')
file_manager = import_ceaser_module('file_manager')
web_automation = import_ceaser_module('web_automation')

# Import new feature classes
from features.ceaser.device_control import DeviceControl
from features.ceaser.file_manager import FileManager
from features.ceaser.health import HealthAssistant
from features.ceaser.spotify_integration import MediaControl
from features.ceaser.voice import VoiceAssistant
from features.ceaser.fun import FunUtilities
from features.ceaser.notifications import NotificationAssistant

app = FastAPI()

# --- Persistent Storage (sqlite) for reminders, notes, memory ---
DB_PATH = os.path.join(os.path.dirname(__file__), 'companion.db')
conn = sqlite3.connect(DB_PATH, check_same_thread=False)

# Create tables if not exist
with conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY, title TEXT, time TEXT, active INTEGER)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, content TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS memory (key TEXT PRIMARY KEY, value TEXT)''')

# --- Models ---
class Reminder(BaseModel):
    id: int
    title: str
    time: str
    active: bool

class Note(BaseModel):
    id: int
    content: str

# --- Voice Assistant (TTS, STT) ---
@app.post("/voice/tts")
def text_to_speech(text: str = Body(...)):
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()
    return {"status": "spoken"}

@app.post("/voice/stt")
def speech_to_text():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        audio = recognizer.listen(source, timeout=5)
    try:
        text = recognizer.recognize_google(audio)  # type: ignore
        return {"text": text}
    except Exception as e:
        return {"error": str(e)}

# --- Automation ---
auto = automation.AutomationAssistant()
@app.post("/automation")
def run_automation(command: str = Body(...)):
    return {"result": auto.automate_task(command)}

# --- Device Control ---
# Device Control endpoints
@app.post("/device/open-app")
def open_app(app_path: str = Body(...)):
    return {"result": DeviceControl.open_app(app_path)}

@app.post("/device/close-app")
def close_app(process_name: str = Body(...)):
    return {"result": DeviceControl.close_app(process_name)}

@app.post("/device/lock")
def lock_workstation():
    return {"result": DeviceControl.lock_workstation()}

@app.post("/device/shutdown")
def shutdown():
    return {"result": DeviceControl.shutdown()}

@app.post("/device/restart")
def restart():
    return {"result": DeviceControl.restart()}

@app.post("/device/sleep")
def sleep():
    return {"result": DeviceControl.sleep()}

@app.post("/device/screenshot")
def screenshot(save_path: str = Body('screenshot.png')):
    return {"result": DeviceControl.take_screenshot(save_path)}

@app.post("/device/clipboard/copy")
def copy_clipboard(text: str = Body(...)):
    return {"result": DeviceControl.copy_to_clipboard(text)}

@app.get("/device/clipboard/paste")
def paste_clipboard():
    return {"result": DeviceControl.paste_from_clipboard()}

@app.post("/device/clipboard/clear")
def clear_clipboard():
    return {"result": DeviceControl.clear_clipboard()}

@app.post("/device/volume/mute")
def mute_volume():
    return {"result": DeviceControl.mute_volume()}

@app.post("/device/volume/unmute")
def unmute_volume():
    return {"result": DeviceControl.unmute_volume()}

@app.post("/device/volume/set")
def set_volume(level: int = Body(...)):
    return {"result": DeviceControl.set_volume(level)}

@app.get("/device/volume/get")
def get_volume():
    return {"result": DeviceControl.get_volume()}

@app.post("/device/open-file")
def open_file(file_path: str = Body(...)):
    return {"result": DeviceControl.open_file(file_path)}

# --- Notifications ---
# Notifications endpoint
@app.post("/notify")
def notify(message: str = Body(...), title: str = Body('Ceaser Notification')):
    return {"result": NotificationAssistant().send_notification(message, title)}

# --- Proactive Assistant ---
# proactive = proactive_module.ProactiveAssistant() # Uncomment if needed

# --- YouTube Music ---
ytmusic = youtube_music.YouTubeMusic()
@app.post("/youtube-music")
def youtube_music_action(action: str = Body(...), query: str = Body(None)):
    if action == "search":
        return {"result": ytmusic.search_and_play(query)}
    elif action == "play":
        return {"result": ytmusic.play_song(query)}
    elif action == "pause":
        return {"result": ytmusic.pause_playback()}
    return {"error": "Unknown action"}

# --- News Assistant ---
news = news_assistant.NewsAssistant()
@app.get("/news")
def get_news():
    return news.get_headlines()

# --- Weather Assistant ---
weather = weather_assistant.WeatherAssistant()
@app.get("/weather")
def get_weather(city: str = "Mumbai"):
    return weather.get_current_weather(city)

# --- Spotify Integration ---
spotify = spotify_integration.SpotifyAssistant()
@app.post("/spotify")
def spotify_action(action: str = Body(...), query: str = Body(None)):
    if action == "play":
        return {"result": spotify.play(query)}
    elif action == "pause":
        return {"result": spotify.pause()}
    elif action == "next":
        return {"result": spotify.next_track()}
    elif action == "prev":
        return {"result": spotify.previous_track()}
    return {"error": "Unknown action"}

# --- Amazon Shopping ---
amazon = amazon_shopping.AmazonShoppingAssistant()
@app.post("/amazon")
def amazon_action(query: str = Body(...)):
    return {"result": amazon.search_and_buy(query)}

# --- Translation ---
translate = translation.TranslationAssistant()
@app.post("/translate")
def translate_text(text: str = Body(...), target_lang: str = Body("en")):
    return {"result": translate.translate(text, target_lang)}

# --- Vision ---
vision = vision.VisionAssistant()
@app.post("/vision/object-detect")
def detect_object(image_path: str = Body(...)):
    return {"result": vision.detect_object(image_path)}

@app.post("/vision/face-auth")
def face_auth(image_path: str = Body(...)):
    return {"result": vision.face_authenticate(image_path)}

@app.post("/vision/emotion")
def detect_emotion(image_path: str = Body(...)):
    return {"result": vision.detect_emotion(image_path)}

# --- Fun ---
fun_mod = fun.FunAssistant()
@app.get("/fun/joke")
def tell_joke():
    return {"result": fun_mod.tell_joke()}

# --- Health ---
health_mod = health.HealthAssistant()
# System Info endpoints
@app.get("/system/cpu")
def cpu_usage():
    return {"result": HealthAssistant.get_cpu_usage()}

@app.get("/system/memory")
def memory_usage():
    return {"result": HealthAssistant.get_memory_usage()}

@app.get("/system/disk")
def disk_usage():
    return {"result": HealthAssistant.get_disk_usage()}

@app.get("/system/battery")
def battery_status():
    return {"result": HealthAssistant.get_battery_status()}

@app.get("/system/os")
def os_info():
    return {"result": HealthAssistant.get_os_info()}

# --- Media Control ---
# Media Control endpoints
@app.post("/media/play-pause")
def play_pause():
    return {"result": MediaControl.play_pause()}

@app.post("/media/next")
def next_track():
    return {"result": MediaControl.next_track()}

@app.post("/media/prev")
def prev_track():
    return {"result": MediaControl.prev_track()}

@app.post("/media/stop")
def stop():
    return {"result": MediaControl.stop()}

# --- Memory (persistent) ---
mem = memory.MemoryAssistant(db_path=DB_PATH)
@app.post("/memory/remember")
def remember(key: str = Body(...), value: str = Body(...)):
    mem.remember(key, value)
    return {"status": "remembered"}

@app.get("/memory/recall")
def recall(key: str):
    return {"value": mem.recall(key)}

# --- File Manager ---
fileman = file_manager.FileManagerAssistant()
# File Manager endpoints
@app.post("/file/list")
def list_dir(path: str = Body(...)):
    return {"result": FileManager.list_dir(path)}

@app.post("/file/create-folder")
def create_folder(path: str = Body(...)):
    return {"result": FileManager.create_folder(path)}

@app.post("/file/delete")
def delete_path(path: str = Body(...)):
    return {"result": FileManager.delete_path(path)}

@app.post("/file/move")
def move_path(src: str = Body(...), dst: str = Body(...)):
    return {"result": FileManager.move_path(src, dst)}

@app.post("/file/copy")
def copy_path(src: str = Body(...), dst: str = Body(...)):
    return {"result": FileManager.copy_path(src, dst)}

@app.post("/file/rename")
def rename_path(src: str = Body(...), dst: str = Body(...)):
    return {"result": FileManager.rename_path(src, dst)}

@app.post("/file/open-folder")
def open_folder(path: str = Body(...)):
    return {"result": FileManager.open_folder(path)}

# --- Web Automation ---
webauto = web_automation.WebAutomationAssistant()
@app.post("/web-automation/book-meeting")
def book_meeting():
    return {"result": webauto.book_meeting()}

# --- Fun/Utilities ---
# Fun/Utilities endpoints
@app.get("/fun/joke")
def get_joke():
    return {"result": FunUtilities.get_joke()}

@app.get("/fun/quote")
def get_quote():
    return {"result": FunUtilities.get_quote()}

@app.post("/fun/timer")
def start_timer(seconds: int = Body(...)):
    return {"result": FunUtilities.start_timer(seconds)}

@app.post("/fun/stopwatch")
def start_stopwatch(duration: int = Body(...)):
    return {"result": FunUtilities.start_stopwatch(duration)}

@app.post("/fun/alarm")
def set_alarm(seconds: int = Body(...)):
    return {"result": FunUtilities.set_alarm(seconds)}

# --- Reminders (persistent) ---
@app.get("/reminders", response_model=List[Reminder])
def get_reminders():
    cur = conn.cursor()
    cur.execute('SELECT id, title, time, active FROM reminders')
    rows = cur.fetchall()
    return [Reminder(id=row[0], title=row[1], time=row[2], active=bool(row[3])) for row in rows]

@app.post("/reminders", response_model=Reminder)
def add_reminder(reminder: Reminder):
    with conn:
        conn.execute('INSERT INTO reminders (id, title, time, active) VALUES (?, ?, ?, ?)', (reminder.id, reminder.title, reminder.time, int(reminder.active)))
    return reminder

@app.put("/reminders/{reminder_id}", response_model=Reminder)
def update_reminder(reminder_id: int, reminder: Reminder):
    with conn:
        conn.execute('UPDATE reminders SET title=?, time=?, active=? WHERE id=?', (reminder.title, reminder.time, int(reminder.active), reminder_id))
    return reminder

@app.delete("/reminders/{reminder_id}")
def delete_reminder(reminder_id: int):
    with conn:
        conn.execute('DELETE FROM reminders WHERE id=?', (reminder_id,))
    return {"status": "deleted"}

# --- Notes (persistent) ---
@app.get("/notes", response_model=List[Note])
def get_notes():
    cur = conn.cursor()
    cur.execute('SELECT id, content FROM notes')
    rows = cur.fetchall()
    return [Note(id=row[0], content=row[1]) for row in rows]

@app.post("/notes", response_model=Note)
def add_note(note: Note):
    with conn:
        conn.execute('INSERT INTO notes (id, content) VALUES (?, ?)', (note.id, note.content))
    return note

@app.put("/notes/{note_id}", response_model=Note)
def update_note(note_id: int, note: Note):
    with conn:
        conn.execute('UPDATE notes SET content=? WHERE id=?', (note.content, note_id))
    return note

@app.delete("/notes/{note_id}")
def delete_note(note_id: int):
    with conn:
        conn.execute('DELETE FROM notes WHERE id=?', (note_id,))
    return {"status": "deleted"}