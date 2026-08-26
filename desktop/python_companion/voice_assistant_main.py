import speech_recognition as sr
import re as _re
try:
    import cv2
except ImportError:
    cv2 = None
import datetime
from datetime import timedelta
import webbrowser
import pyautogui
import time
import requests
import os
import sys
import threading
import queue
import tempfile
import logging
import json
from intent_client import IntentClient
from difflib import get_close_matches
from typing import List, Optional, Tuple
try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None
from gtts import gTTS
import playsound
from features.ceaser.device_control import DeviceControl
from features.ceaser.file_manager import FileManager
from features.ceaser.health import HealthAssistant
from features.ceaser.spotify_integration import MediaControl
from features.ceaser.fun import FunUtilities
from features.ceaser.notifications import NotificationAssistant
from features.ceaser.weather_assistant import WeatherAssistant
from features.ceaser.news_assistant import NewsAssistant
from features.ceaser.reminders import Reminders
from features.ceaser.automation import AutomationAssistant
# Translation functionality now handled by LanguageLearningAssistant

# NEW IMPORTS - Adding all missing features
from features.ceaser.ai_core import AICore
from features.ceaser.voice import VoiceAssistant
from features.ceaser.vision import VisionAssistant
from features.ceaser.memory import MemoryAssistant
from features.ceaser.youtube_music import YouTubeMusic
from features.ceaser.amazon_shopping import AmazonShopping
from features.ceaser.language_learning import LanguageLearningAssistant
from features.ceaser.web_automation import WebAutomationAssistant
from features.ceaser.multimodal import MultimodalAssistant
from features.ceaser.proactive import ProactiveAssistant
from features.ceaser.vault import VaultAssistant

# Performance optimization imports
from features.ceaser.memory_optimized import OptimizedMemoryAssistant
from features.ceaser.cache_system import get_cache, cache_result
from features.ceaser.memory_cleanup import MemoryCleanupManager
from features.ceaser.multiuser import MultiUserAssistant
from features.ceaser.utils import Utils
from features.ceaser.integrations import IntegrationsAssistant
from features.ceaser.ai_hf import AIHuggingFace

# NEW PERSONAL FEATURES - Normal mode features
from features.ceaser.personal_tasks import personal_tasks
from features.ceaser.personal_goals import personal_goals
from features.ceaser.personal_calendar import personal_calendar
from features.ceaser.personal_notes import personal_notes
from features.ceaser.personal_analytics import personal_analytics
# Office Control
from features.ceaser.office_control import OfficeControl
from features.ceaser.word_controller import WordController
from features.ceaser.excel_controller import ExcelController
from features.ceaser.powerpoint_controller import PowerPointController
from features.ceaser.office_voice_parser import OfficeVoiceParser

import logging
import pvporcupine
import pyaudio
import struct
import time

# Production voice pipeline (no direct execution; only StructuredCommand reaches execution)
from voice_pipeline import run_pipeline, log_execution as _pipeline_log
from structured_command import StructuredCommand, Command

# Setup logger for this module
logger = logging.getLogger(__name__)

# Pending confirmation from pipeline (parsed_list + prompt) when user must say yes/no
_pending_pipeline_confirmation = None

# Backend Configuration
import os
# Normal mode backend (MVP - all features use this)
NORMAL_BACKEND_URL = os.getenv("VITE_BACKEND_URL") or os.getenv("BACKEND_URL") or os.getenv("API_BASE_URL") or "http://localhost:8000"
API_URL = os.getenv("CEASER_COMMAND_URL") or f"{NORMAL_BACKEND_URL.rstrip('/')}/command"
# Business Backend Configuration (for business mode features)
BUSINESS_BACKEND_URL = os.getenv("BUSINESS_BACKEND_URL", "https://ceaser-business-backend.onrender.com")

# MVP Services - Available in V1 Launch
MVP_SERVICES = [
    'AI Chat Assistant',
    'Voice Commands',
    'Smart Reminders',
    'Weather Assistant',
    'News Assistant',
    'HuggingFace AI',
    'Workflow Automations',
    'YouTube Music',
    'Device Control',
    'Note Taking'
]

# Inbuilt Services - Always active (no toggle needed)
INBUILT_SERVICES = [
    'Proactive Assistant',
    'Memory Assistant'
]

# Phase 2 Services - Coming Soon (Command keywords -> Service name mapping)
# Currently empty because all GA features are live through the AI router.
PHASE_2_SERVICES = {}

def check_phase2_feature(command_text: str) -> tuple[bool, str]:
    """
    Check if a command is related to a Phase 2 feature.
    Returns: (is_phase2: bool, feature_name: str or empty)
    """
    command_lower = command_text.lower().strip()
    
    # Check each Phase 2 keyword
    for keyword, service_name in PHASE_2_SERVICES.items():
        if keyword in command_lower:
            return True, service_name
    
    return False, ""

def get_phase2_response(feature_name: str) -> str:
    """Get FOMO response for Phase 2 features"""
    return f"{feature_name} will be available in Phase 2! Stay tuned for exciting updates. 🚀"

# Global user context - will be set by the frontend when voice assistant is activated
CURRENT_USER_ID = None  # This will be set from the frontend/app context
CURRENT_MODE = "normal"  # "normal" or "business"
CURRENT_BUSINESS_ID = None
CURRENT_USER_ROLE = None

# Work Automation Mode - Ceaser is now focused on work automation by default
WORK_AUTOMATION_MODE = os.getenv("CEASER_WORK_AUTOMATION_MODE", "false").lower() in ("1", "true", "yes")

# Active meeting state tracking
ACTIVE_MEETING = {
    'is_active': False,
    'meeting_id': None,
    'meeting_title': None,
    'start_time': None,
    'participants': [],
    'is_recording': False,
    'transcription': []
}

# Restricted command patterns for work automation mode
# These features are blocked from default voice usage in work automation mode
RESTRICTED_COMMAND_PATTERNS = [
    # Media & Entertainment
    'play music', 'pause music', 'stop music', 'next track', 'previous track', 'next song', 'previous song',
    'play on youtube', 'youtube play', 'play video', 'youtube search', 'search youtube',
    'tell me a joke', 'joke', 'make me laugh', 'quote', 'inspire me', 'motivation',
    'news', 'latest news', 'headlines', 'show me news',
    'weather', 'current weather', 'how is the weather', 'weather in',
    
    # Device/System Controls
    'shutdown', 'shut down', 'turn off computer', 'power off',
    'restart', 'reboot', 'restart computer',
    'sleep', 'go to sleep', 'sleep mode',
    'lock workstation', 'lock my pc', 'lock computer', 'lock screen',
    'take screenshot', 'capture screen', 'screenshot',
    'mute', 'mute volume', 'turn off sound', 'silence', 'unmute', 'unmute volume',
    'set volume to', 'volume to', 'increase volume', 'decrease volume', 'raise volume', 'lower volume',
    'get volume', 'current volume', 'what is the volume',
    'open calculator', 'open settings', 'system settings', 'show settings',
    'open youtube', 'launch youtube', 'start youtube',
    
    # Developer/Code Generation
    'build app', 'create app', 'make app', 'generate app',
    'build website', 'create website', 'make website', 'generate website',
    'modify project', 'update project', 'change project',
    'deploy project', 'deploy app', 'publish app',
    'show projects', 'list projects', 'my projects',
    
    # Vision Features
    'analyze image', 'analyze photo', 'analyze picture',
    'detect faces', 'find faces', 'face detection',
    'read text', 'ocr', 'extract text',
    'object detection', 'detect objects', 'what do you see',
    'take a selfie', 'capture selfie', 'click my photo', 'take my picture', 'take a photo',
    
    # Shopping
    'amazon search', 'search amazon', 'find on amazon',
    'amazon deals', 'amazon offers', 'amazon discounts',
    'track price', 'price tracking', 'amazon price',
    'amazon reviews', 'product reviews', 'amazon rating',
    
    # Language Learning
    'start lesson', 'begin lesson', 'language lesson',
    'practice language', 'language practice', 'speak practice',
    'vocabulary', 'learn words', 'new words',
    'language progress', 'learning progress', 'my progress',
    'translate', 'translate to',
    
    # Generic AI Chat (work-related AI is allowed, but general chat is restricted)
    'ai chat', 'chat with ai', 'ask ai', 'ai help',
    'what is', 'what are', 'what do', 'what does', 'what was', 'what will', 'what can', 'what should', 'what would',
    'who is', 'who are', 'who do', 'who does', 'who was', 'who will', 'who can', 'who should', 'who would',
    'how do', 'how does', 'how can', 'how should', 'how would', 'how to', 'how is', 'how are', 'how was', 'how will',
    'why do', 'why does', 'why can', 'why should', 'why would', 'why is', 'why are', 'why was', 'why will',
    'when do', 'when does', 'when can', 'when should', 'when would', 'when is', 'when are', 'when was', 'when will',
    'where do', 'where does', 'where can', 'where should', 'where would', 'where is', 'where are', 'where was', 'where will',
    'which do', 'which does', 'which can', 'which should', 'which would', 'which is', 'which are', 'which was', 'which will',
    'explain', 'tell me', 'help me', 'show me', 'teach me', 'guide me',
    
    # Proactive Suggestions (generic)
    'proactive suggestions', 'suggestions', 'recommendations', 'what should i do',
    'proactive mode', 'smart assistant', 'auto help',
    'how are you', 'how are you doing', 'how do you feel',
    'encourage me', 'motivate me', 'give me encouragement',
    'check in', 'how am i doing', 'check on me',
    'compliment me', 'say something nice',
    'what do you think', 'your opinion', 'what would you do',
    'proactive status', 'how proactive are you', 'are you learning',
    
    # Web Automation (non-work)
    'web automation', 'automate web', 'browser automation',
    'fill form', 'auto fill', 'form automation',
    'web scraping', 'scrape website', 'extract data',
    
    # Google Search (generic)
    'search google', 'google search', 'search for',
    'search', 'find',
    
    # Multimodal AI (non-work)
    'multimodal', 'multi modal', 'ai vision',
    'analyze with ai', 'ai analysis', 'smart analysis',
    
    # HuggingFace AI (generic)
    'huggingface', 'hf model', 'alternative ai',
    'local ai', 'offline ai', 'hf chat',
    
    # System Tools
    'utility', 'tools', 'utilities',
    'system tools', 'computer tools', 'pc utilities',
    'cpu usage', 'cpu status', 'processor usage',
    'memory usage', 'ram usage', 'memory status',
    'disk usage', 'storage usage', 'disk status',
    'battery status', 'battery level', 'battery',
    'os info', 'system info', 'about computer',
    
    # Timer/Alarm (non-work)
    'start timer', 'set timer',
    'start stopwatch', 'stopwatch',
    'set alarm', 'alarm',
]

# Initialize user-isolated memory and proactive assistants
memory_assistant = None
proactive_assistant = None

# Context memory for OpenAI responses (for continue/explain more functionality)
openai_context = {
    'last_query': None,
    'last_response': None,
    'conversation_history': []
}


def _has_valid_user() -> bool:
    """Return True when we have a real user id (not placeholder)."""
    return bool(CURRENT_USER_ID and CURRENT_USER_ID != 'default_user')


def _ensure_personal_access(feature_name: str = "this feature"):
    """Ensure the user is logged in and in normal mode for personal productivity features."""
    if not _has_valid_user():
        return False, f"Please log in to use {feature_name}. Personal features require a valid user account."
    if CURRENT_MODE != "normal":
        return False, f"{feature_name.capitalize()} is available in normal mode. Please switch to normal mode first."
    return True, None

def _get_user_id_for_integrations():
    """
    Get user_id from multiple sources for integration commands.
    If backend is running and receiving requests, user IS logged in.
    Returns user_id or None if not found.
    """
    # Try global CURRENT_USER_ID first
    user_id = CURRENT_USER_ID
    if user_id and user_id != 'default_user':
        return user_id
    
    # Try environment variable
    user_id = os.getenv('CURRENT_USER_ID')
    if user_id and user_id != 'default_user':
        return user_id
    
    # If still None, return None (caller should handle gracefully)
    return None


def _match_item_by_title(items, title_key, search_text):
    """Best-effort fuzzy match helper for tasks/notes/goals."""
    if not items or not search_text:
        return None
    search_lower = search_text.lower().strip()
    for item in items:
        title = (item.get(title_key) or "").lower()
        if title == search_lower:
            return item
    partial_matches = [item for item in items if search_lower in (item.get(title_key) or "").lower()]
    if partial_matches:
        return partial_matches[0]
    titles = [item.get(title_key, "") or "" for item in items]
    matches = get_close_matches(search_text, titles, n=1, cutoff=0.6)
    if matches:
        for item in items:
            if item.get(title_key) == matches[0]:
                return item
    return None


def _parse_datetime_with_default(text: str, default_hours: int = 1):
    """Parse natural language datetime; fallback to now + default_hours."""
    base = datetime.datetime.now()
    if text and date_parser:
        try:
            dt = date_parser.parse(text, fuzzy=True, default=base)
            return dt
        except Exception:
            pass
    return base + timedelta(hours=default_hours)


def _split_note_edit_command(text: str):
    """Split note edit command into identifier and new content."""
    cleaned = text.replace('edit note', '').replace('update note', '').replace('modify note', '').strip()
    for delimiter in [' with ', ' to ', ' says ', ' content ']:
        if delimiter in cleaned:
            parts = cleaned.split(delimiter, 1)
            return parts[0].strip(), parts[1].strip()
    return cleaned.strip(), ""


def _strip_leading_phrases(text: str, phrases: List[str]):
    """Remove leading command phrases while preserving casing."""
    stripped = text.strip()
    lower = stripped.lower()
    for phrase in phrases:
        phrase_lower = phrase.lower()
        if lower.startswith(phrase_lower):
            return stripped[len(phrase):].strip(" ,:-")
    return stripped


def _format_datetime_for_speech(value):
    """Convert ISO timestamp to a friendly spoken string."""
    if not value:
        return ""
    try:
        if isinstance(value, str):
            dt = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
        else:
            dt = value
        return dt.strftime('%b %d at %I:%M %p').lstrip('0').replace(' 0', ' ')
    except Exception:
        return ""


def _extract_goal_progress(text: str):
    """Parse a goal progress update command."""
    phrases = ['update goal progress', 'goal progress', 'update progress', 'progress for', 'progress on']
    percent = None
    match = _re.search(r'(\d+)\s*(%|percent)', text)
    if match:
        percent = min(100, max(0, int(match.group(1))))
    
    query = text
    lower = text.lower()
    for phrase in phrases:
        if phrase in lower:
            idx = lower.find(phrase)
            query = text[idx + len(phrase):]
            break
    
    query = query.replace(match.group(0), '').strip() if match else query.strip()
    return {"goal_query": query or text.strip(), "progress_percent": percent}


def _extract_event_details(text: str):
    """Parse event commands for title and timing."""
    phrases = ['schedule event', 'create event', 'add event', 'schedule', 'set up']
    cleaned = _strip_leading_phrases(text, phrases)
    lower = text.lower()
    details = {
        "title": cleaned or text.strip(),
        "start_text": None,
        "end_text": None,
        "duration_hours": 1
    }
    
    # from ... to ...
    match_range = _re.search(r'from (.+?) to (.+)', lower)
    if match_range:
        details["start_text"] = text[match_range.start(1):match_range.end(1)]
        details["end_text"] = text[match_range.start(2):match_range.end(2)]
    else:
        for keyword in [' at ', ' on ', ' tomorrow ', ' today ', ' tonight ']:
            if keyword in lower:
                idx = lower.find(keyword)
                details["start_text"] = text[idx + len(keyword):].strip()
                break
    
    duration_match = _re.search(r'for (\d+)\s*(hour|hours)', lower)
    if duration_match:
        details["duration_hours"] = max(1, int(duration_match.group(1)))
    
    return details


def _build_note_title(content: str):
    """Use first words as a fallback note title."""
    tokens = content.strip().split()
    return " ".join(tokens[:5]) if tokens else "Quick note"


TASK_PRIORITY_KEYWORDS = {
    "urgent": "urgent",
    "asap": "urgent",
    "high priority": "high",
    "high": "high",
    "medium": "medium",
    "low": "low"
}


def _extract_task_details(text: str) -> dict:
    """Extract title, due text, priority, and category hints from raw text."""
    details = {
        "title": text.strip(),
        "due_text": None,
        "priority": "medium",
        "category": None
    }
    lower_text = text.lower()
    
    # Priority detection
    for keyword, priority in TASK_PRIORITY_KEYWORDS.items():
        if keyword in lower_text:
            details["priority"] = priority
            break
    
    # Category hints (work, personal, shopping etc.)
    for category in ["work", "personal", "shopping", "fitness", "health", "study"]:
        if category in lower_text:
            details["category"] = category
            break
    
    # Due date extraction using keywords
    due_match = _re.search(r'\b(?:by|before|on|at)\s+(.+)', text, flags=_re.IGNORECASE)
    if due_match:
        details["due_text"] = due_match.group(1).strip()
        details["title"] = text[:due_match.start()].strip()
    
    return details


def _parse_numeric_value(text: str) -> float:
    """Extract first numeric value from text."""
    match = _re.search(r'(\d+(?:\.\d+)?)', text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


def _extract_goal_details(text: str) -> dict:
    """Extract goal metadata such as title, target date, priority, target value."""
    details = {
        "title": text.strip(),
        "target_date_text": None,
        "priority": "medium",
        "target_value": None,
        "category": None
    }
    lower_text = text.lower()
    
    # Priority detection
    for keyword, priority in TASK_PRIORITY_KEYWORDS.items():
        if keyword in lower_text:
            details["priority"] = priority
            break
    
    # Target date extraction
    date_match = _re.search(r'\b(?:by|before|until)\s+(.+)', text, flags=_re.IGNORECASE)
    if date_match:
        details["target_date_text"] = date_match.group(1).strip()
        details["title"] = text[:date_match.start()].strip()
    
    # Target value extraction (e.g., 10 books, 5 kg)
    value_match = _re.search(r'(\d+(?:\.\d+)?)\s*(?:percent|%|books|kg|hours|times|sessions)?', text)
    if value_match:
        try:
            details["target_value"] = float(value_match.group(1))
        except ValueError:
            pass
    
    # Category clues
    for category in ["fitness", "health", "finance", "learning", "career", "personal", "work"]:
        if category in lower_text:
            details["category"] = category
            break
    
    return details
def set_current_user(user_id: str):
    """Set the current user ID for voice assistant operations"""
    global CURRENT_USER_ID, memory_assistant, proactive_assistant
    if proactive_assistant and getattr(proactive_assistant, "user_id", None) == user_id:
        CURRENT_USER_ID = user_id
        print(f"Voice assistant user context already active: {user_id}")
        return
    if proactive_assistant:
        proactive_assistant.close()
    CURRENT_USER_ID = user_id
    
    # Initialize user-isolated assistants
    memory_assistant = MemoryAssistant(user_id=user_id, mode='normal')
    proactive_assistant = ProactiveAssistant(user_id=user_id, mode='normal', start_workers=False)
    
    print(f"Voice assistant user context set to: {user_id}")

def clear_current_user():
    """Clear the current user ID and reset voice assistant state"""
    global CURRENT_USER_ID, memory_assistant, proactive_assistant, CURRENT_MODE, CURRENT_BUSINESS_ID, CURRENT_USER_ROLE
    
    CURRENT_USER_ID = None
    CURRENT_MODE = "normal"
    CURRENT_BUSINESS_ID = None
    CURRENT_USER_ROLE = None
    
    if proactive_assistant:
        proactive_assistant.close()
    # Reset assistants (they'll be re-initialized on next login)
    memory_assistant = None
    proactive_assistant = None
    
    print("✅ Voice assistant user context cleared")

def get_current_user():
    """Get the current user ID"""
    return CURRENT_USER_ID

def set_business_context(business_id: str, user_role: str):
    """Set the business context for voice assistant operations"""
    global CURRENT_BUSINESS_ID, CURRENT_USER_ROLE, CURRENT_MODE, memory_assistant, proactive_assistant
    CURRENT_BUSINESS_ID = business_id
    CURRENT_USER_ROLE = user_role
    CURRENT_MODE = "business"
    
    # Initialize business-isolated assistants
    if CURRENT_USER_ID:
        if proactive_assistant:
            proactive_assistant.close()
        memory_assistant = MemoryAssistant(user_id=CURRENT_USER_ID, business_id=business_id, user_role=user_role, mode='business')
        proactive_assistant = ProactiveAssistant(user_id=CURRENT_USER_ID, business_id=business_id, user_role=user_role, mode='business', start_workers=False)
    
    print(f"Voice assistant business context set: Business={business_id}, Role={user_role}")

def set_normal_mode():
    """Set voice assistant to normal mode"""
    global CURRENT_MODE, CURRENT_BUSINESS_ID, CURRENT_USER_ROLE, memory_assistant, proactive_assistant
    CURRENT_MODE = "normal"
    CURRENT_BUSINESS_ID = None
    CURRENT_USER_ROLE = None
    
    # Reinitialize normal mode assistants
    if CURRENT_USER_ID:
        if proactive_assistant:
            proactive_assistant.close()
        memory_assistant = MemoryAssistant(user_id=CURRENT_USER_ID, mode='normal')
        proactive_assistant = ProactiveAssistant(user_id=CURRENT_USER_ID, mode='normal', start_workers=False)
    
    print("Voice assistant set to normal mode")

def get_current_mode():
    """Get the current mode"""
    return CURRENT_MODE

def get_conversation_history(limit: int = 10):
    """Get recent conversation history for the current user"""
    if not memory_assistant:
        return []
    try:
        return memory_assistant.get_conversation_history(limit)
    except Exception as e:
        print(f"Error getting conversation history: {e}")
        return []

def get_proactive_suggestions(limit: int = 5):
    """Get proactive suggestions for the current user"""
    if not proactive_assistant:
        return []
    try:
        return proactive_assistant.get_suggestions(limit=limit)
    except Exception as e:
        print(f"Error getting proactive suggestions: {e}")
        return []

def get_business_context():
    """Get the current business context"""
    return {
        "business_id": CURRENT_BUSINESS_ID,
        "user_role": CURRENT_USER_ROLE,
        "mode": CURRENT_MODE
    }

# Initialize all feature instances
weather = WeatherAssistant()
news = NewsAssistant()
reminders = Reminders()
automation = AutomationAssistant()
# Translation functionality now handled by language_learning instance

# NEW FEATURE INSTANCES
intent_client = IntentClient()
ai_core = AICore()
voice_assistant = VoiceAssistant()
vision = VisionAssistant()
# memory = MemoryAssistant()  # Now using user-isolated memory_assistant
youtube_music = YouTubeMusic()
amazon_shopping = AmazonShopping()
language_learning = LanguageLearningAssistant()
web_automation = WebAutomationAssistant()
multimodal = MultimodalAssistant()
# User-scoped lifecycle is owned by set_current_user(). Never start an anonymous
# monitoring worker at import time.
proactive = None
vault = VaultAssistant()
multiuser = MultiUserAssistant()
utils = Utils()
integrations = IntegrationsAssistant()
ai_hf = AIHuggingFace()
# Office Control instances
office_control = OfficeControl()
word_controller = WordController(office_control)
excel_controller = ExcelController(office_control)
powerpoint_controller = PowerPointController(office_control)
office_parser = OfficeVoiceParser()

# Map each action to a list of alternative phrases (patterns)
COMMAND_PATTERNS = [
    # Dynamic open app (catch-all)
    (['open'], lambda text: _open_any_app(text)),
    # Dynamic close app (catch-all)
    (['close'], lambda text: _close_any_app(text)),
    # Fix unmute
    (['unmute', 'unmute volume', 'turn on sound'], lambda _: DeviceControl.unmute_volume()),
    # Device Control (no static open/close app mappings)
    (['lock workstation', 'lock my pc', 'lock computer', 'lock screen'], lambda _: DeviceControl.lock_workstation()),
    (['shutdown', 'shut down', 'turn off computer', 'power off'], lambda _: DeviceControl.shutdown()),
    (['restart', 'reboot', 'restart computer'], lambda _: DeviceControl.restart()),
    (['sleep', 'go to sleep', 'sleep mode'], lambda _: DeviceControl.sleep()),
    (['take screenshot', 'capture screen', 'screenshot'], lambda _: DeviceControl.take_screenshot()),
    (['copy to clipboard', 'copy this', 'copy'], lambda _: DeviceControl.copy_to_clipboard('Copied by voice')),
    (['paste from clipboard', 'paste'], lambda _: DeviceControl.paste_from_clipboard()),
    (['clear clipboard', 'empty clipboard'], lambda _: DeviceControl.clear_clipboard()),
    (['mute', 'mute volume', 'turn off sound', 'silence'], lambda _: DeviceControl.mute_volume()),
    (['set volume to', 'volume to'], lambda text: DeviceControl.set_volume(_extract_number(text, 30))),
    (['increase volume', 'raise volume', 'volume up'], lambda _: DeviceControl.set_volume(70)),
    (['decrease volume', 'lower volume', 'volume down', 'reduce volume'], lambda _: DeviceControl.set_volume(30)),
    (['get volume', 'current volume', 'what is the volume'], lambda _: DeviceControl.get_volume()),
    (['open screenshot'], lambda _: DeviceControl.open_file('screenshot.png')),
    # File Manager - Enhanced
    (['list files', 'show files', 'what files are here', 'show me files'], lambda text: _handle_list_files(text)),
    (['open file'], lambda text: _handle_open_file(text)),
    (['search file', 'find file', 'locate file', 'where is'], lambda text: _handle_search_file(text)),
    (['change directory', 'cd', 'go to folder', 'navigate to'], lambda text: _handle_change_directory(text)),
    (['current directory', 'where am i', 'pwd', 'current folder'], lambda _: FileManager.get_current_directory()),
    (['create folder', 'make folder', 'new folder'], lambda text: _handle_create_folder(text)),
    (['delete file', 'delete folder', 'remove file', 'remove folder'], lambda text: _handle_delete_file(text)),
    (['open folder', 'open directory', 'show folder'], lambda text: _handle_open_folder(text)),
    # System Info
    (['cpu usage', 'cpu status', 'processor usage'], lambda _: HealthAssistant.get_cpu_usage()),
    (['memory usage', 'ram usage', 'memory status'], lambda _: HealthAssistant.get_memory_usage()),
    (['disk usage', 'storage usage', 'disk status'], lambda _: HealthAssistant.get_disk_usage()),
    (['battery status', 'battery level', 'battery'], lambda _: HealthAssistant.get_battery_status()),
    (['os info', 'system info', 'about computer'], lambda _: HealthAssistant.get_os_info()),
    # Media Control
    (['play pause', 'play music', 'pause music', 'toggle music'], lambda _: MediaControl.play_pause()),
    (['next track', 'next song', 'skip song'], lambda _: MediaControl.next_track()),
    (['previous track', 'previous song', 'last song'], lambda _: MediaControl.prev_track()),
    (['stop media', 'stop music'], lambda _: MediaControl.stop()),
    # Fun/Utilities
    (['tell me a joke', 'joke', 'make me laugh'], lambda _: FunUtilities.get_joke()),
    (['quote', 'inspire me', 'motivation'], lambda _: FunUtilities.get_quote()),
    (['start timer', 'set timer'], lambda _: FunUtilities.start_timer(1)),
    (['start stopwatch', 'stopwatch'], lambda _: FunUtilities.start_stopwatch(1)),
    (['set alarm', 'alarm'], lambda _: FunUtilities.set_alarm(1)),
    # Notifications
    (['notify me', 'remind me now', 'send notification'], lambda _: NotificationAssistant().send_notification('This is a voice notification')),
    # Weather
    (['weather in', 'what is the weather in', 'weather at', 'how is the weather in'], lambda text: weather.format_weather_report(weather.get_current_weather(_extract_city(text)))),
    (['weather', 'current weather', 'how is the weather'], lambda _: weather.format_weather_report(weather.get_current_weather('Mumbai'))),
    # News
    (['news', 'latest news', 'headlines', 'show me news'], lambda _: news.format_headlines_report(news.get_top_headlines())),
    # Reminders
    (['add reminder', 'set reminder'], lambda text: _handle_add_reminder(text)),
    (['list reminders', 'show reminders', 'what are my reminders'], lambda _: _handle_list_reminders()),
    # Automation
    (['add automation', 'set automation'], lambda text: _handle_add_automation(text)),
    (['list automations', 'show automations'], lambda _: _handle_list_automations()),
    # Calendar Events
    # Translation
    (['translate', 'translate to'], lambda text: _handle_translate(text)),
    # Office Control - Word
    (['summarize document', 'summarize word', 'word summarize'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['word', 'document', 'doc']) else None),
    (['word count', 'how many words', 'count words', 'word statistics'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['word', 'document']) else None),
    (['find in word', 'find word', 'search word', 'find in document'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['word', 'document']) else None),
    (['format word', 'bold word', 'italic word', 'format document'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['word', 'document']) else None),
    (['insert in word', 'insert word', 'add to word', 'type in word'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['word', 'document']) else None),
    (['read word', 'read document', 'read selected', 'what does it say'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['word', 'document', 'selected']) else None),
    # Office Control - Excel
    (['filter excel', 'filter column', 'filter data', 'filter spreadsheet'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['excel', 'spreadsheet', 'sheet']) else None),
    (['sort excel', 'sort column', 'sort data', 'sort spreadsheet'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['excel', 'spreadsheet', 'sheet']) else None),
    (['calculate excel', 'sum excel', 'average excel', 'calculate column'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['excel', 'spreadsheet', 'sheet']) else None),
    (['find in excel', 'find excel', 'search excel', 'find in spreadsheet'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['excel', 'spreadsheet', 'sheet']) else None),
    (['summarize excel', 'summarize spreadsheet', 'summarize data'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['excel', 'spreadsheet', 'sheet']) else None),
    (['chart excel', 'create chart', 'make chart', 'graph excel'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['excel', 'spreadsheet', 'sheet']) else None),
    # Office Control - PowerPoint
    (['go to slide', 'navigate slide', 'jump to slide', 'move to slide', 'next slide', 'previous slide'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['powerpoint', 'presentation', 'slide', 'ppt']) else None),
    (['read slide', 'read presentation', 'read powerpoint', 'what does the slide say'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['powerpoint', 'presentation', 'slide', 'ppt']) else None),
    (['summarize presentation', 'summarize powerpoint', 'summarize slides'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['powerpoint', 'presentation', 'slide', 'ppt']) else None),
    (['how many slides', 'slide count', 'total slides', 'number of slides'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['powerpoint', 'presentation', 'slide', 'ppt']) else None),
    (['add slide', 'new slide', 'create slide'], lambda text: _handle_office_command(text) if any(kw in text.lower() for kw in ['powerpoint', 'presentation', 'slide', 'ppt']) else None),
    # Take a selfie
    (['take a selfie', 'capture selfie', 'click my photo', 'take my picture', 'take a photo'], lambda _: _take_selfie()),
    # Lock screen (already above, but keep for variants)
    (['lock screen', 'lock my screen', 'lock computer'], lambda _: DeviceControl.lock_workstation()),
    # Show battery (already above, but keep for variants)
    (['show battery', 'battery status', 'battery level'], lambda _: HealthAssistant.get_battery_status()),
    # Show calendar
    (['show calendar', 'open calendar', 'calendar'], lambda _: DeviceControl.open_app('outlookcal:')),
    # What time is it
    (['what time is it', 'current time', 'tell me the time'], lambda _: datetime.datetime.now().strftime('The time is %H:%M')),
    # What date is it
    (['what date is it', 'current date', 'today date', 'tell me the date'], lambda _: datetime.datetime.now().strftime('Today is %A, %d %B %Y')),
    # Music controls (more variants)
    (['play music', 'start music', 'resume music'], lambda _: MediaControl.play_pause()),
    (['pause music', 'hold music'], lambda _: MediaControl.play_pause()),
    (['stop music', 'end music'], lambda _: MediaControl.stop()),
    (['next song', 'next track', 'skip song'], lambda _: MediaControl.next_track()),
    (['previous song', 'previous track', 'last song'], lambda _: MediaControl.prev_track()),
]

# Add new advanced commands to COMMAND_PATTERNS (no duplicates of first block)
COMMAND_PATTERNS += [
    # Open calculator
    (['open calculator', 'launch calculator', 'start calculator'], lambda _: DeviceControl.open_app('calc')),
    # Open settings (first block has open file; open app is generic)
    (['open settings', 'system settings', 'show settings'], lambda _: DeviceControl.open_app('ms-settings:')),
    # Open YouTube
    (['open youtube', 'launch youtube', 'start youtube'], lambda _: DeviceControl.open_app('https://www.youtube.com')),
    # NEW AI CORE COMMANDS
    (['ai chat', 'chat with ai', 'ask ai', 'ai help'], lambda text: _handle_ai_chat(text)),
    # Natural AI questions (what, who, how, why, when, where, etc.)
    (['what is', 'what are', 'what do', 'what does', 'what was', 'what will', 'what can', 'what should', 'what would'], lambda text: _handle_ai_chat(text)),
    (['who is', 'who are', 'who do', 'who does', 'who was', 'who will', 'who can', 'who should', 'who would'], lambda text: _handle_ai_chat(text)),
    (['how do', 'how does', 'how can', 'how should', 'how would', 'how to', 'how is', 'how are', 'how was', 'how will'], lambda text: _handle_ai_chat(text)),
    (['why do', 'why does', 'why can', 'why should', 'why would', 'why is', 'why are', 'why was', 'why will'], lambda text: _handle_ai_chat(text)),
    (['when do', 'when does', 'when can', 'when should', 'when would', 'when is', 'when are', 'when was', 'when will'], lambda text: _handle_ai_chat(text)),
    (['where do', 'where does', 'where can', 'where should', 'where would', 'where is', 'where are', 'where was', 'where will'], lambda text: _handle_ai_chat(text)),
    (['which do', 'which does', 'which can', 'which should', 'which would', 'which is', 'which are', 'which was', 'which will'], lambda text: _handle_ai_chat(text)),
    (['explain', 'tell me', 'help me', 'show me', 'teach me', 'guide me'], lambda text: _handle_ai_chat(text)),
    (['remember this', 'save this', 'memorize'], lambda text: _handle_remember(text)),
    (['recall', 'what did i tell you', 'remember'], lambda text: _handle_recall(text)),
    
    # NEW VISION COMMANDS
    (['analyze image', 'analyze photo', 'analyze picture'], lambda text: _handle_vision_analyze(text)),
    # Code Generator Commands
    (['build app', 'create app', 'make app', 'generate app'], lambda text: _handle_build_app(text)),
    (['build website', 'create website', 'make website', 'generate website'], lambda text: _handle_build_app(text)),
    (['modify project', 'update project', 'change project'], lambda text: _handle_modify_project(text)),
    (['deploy project', 'deploy app', 'publish app'], lambda text: _handle_deploy_project(text)),
    (['show projects', 'list projects', 'my projects'], lambda _: _handle_list_projects()),
    (['detect faces', 'find faces', 'face detection'], lambda text: _handle_vision_faces(text)),
    (['read text', 'ocr', 'extract text'], lambda text: _handle_vision_ocr(text)),
    (['object detection', 'detect objects', 'what do you see'], lambda text: _handle_vision_objects(text)),
    
    # NEW MEMORY COMMANDS
    (['search memories', 'find in memory', 'memory search'], lambda text: _handle_memory_search(text)),
    (['memory stats', 'memory status', 'memory info'], lambda _: _handle_memory_stats()),
    (['forget', 'delete memory', 'clear memory'], lambda text: _handle_memory_forget(text)),
    (['conversation history', 'chat history', 'recent conversations'], lambda _: _handle_conversation_history()),
    (['proactive suggestions', 'suggestions', 'recommendations'], lambda _: _handle_proactive_suggestions()),
    
    # NEW YOUTUBE MUSIC COMMANDS
    (['play on youtube', 'youtube play', 'play video'], lambda text: _handle_youtube_play(text)),
    (['youtube search', 'search youtube', 'find on youtube'], lambda text: _handle_youtube_search(text)),
    (['youtube controls', 'youtube help', 'youtube commands'], lambda _: _handle_youtube_help()),
    
    # NEW AMAZON SHOPPING COMMANDS
    (['amazon search', 'search amazon', 'find on amazon'], lambda text: _handle_amazon_search(text)),
    (['amazon deals', 'amazon offers', 'amazon discounts'], lambda _: _handle_amazon_deals()),
    (['track price', 'price tracking', 'amazon price'], lambda text: _handle_amazon_track(text)),
    (['amazon reviews', 'product reviews', 'amazon rating'], lambda text: _handle_amazon_reviews(text)),
    
    # NEW LANGUAGE LEARNING COMMANDS
    (['start lesson', 'begin lesson', 'language lesson'], lambda text: _handle_language_lesson(text)),
    (['practice language', 'language practice', 'speak practice'], lambda text: _handle_language_practice(text)),
    (['vocabulary', 'learn words', 'new words'], lambda text: _handle_language_vocabulary(text)),
    (['language progress', 'learning progress', 'my progress'], lambda _: _handle_language_progress()),
    
    # NEW WEB AUTOMATION COMMANDS
    (['web automation', 'automate web', 'browser automation'], lambda text: _handle_web_automation(text)),
    (['fill form', 'auto fill', 'form automation'], lambda text: _handle_web_form(text)),
    (['web scraping', 'scrape website', 'extract data'], lambda text: _handle_web_scraping(text)),
    
    # NEW GOOGLE SEARCH COMMANDS
    (['search google', 'google search', 'search for'], lambda text: _handle_google_search(text)),
    (['search', 'find'], lambda text: _handle_google_search(text)),
    
    # NEW MULTIMODAL COMMANDS
    (['multimodal', 'multi modal', 'ai vision'], lambda text: _handle_multimodal(text)),
    (['analyze with ai', 'ai analysis', 'smart analysis'], lambda text: _handle_multimodal_analysis(text)),
    
    # NEW PROACTIVE COMMANDS
    (['proactive mode', 'smart assistant', 'auto help'], lambda _: _handle_proactive_mode()),
    (['suggestions', 'recommendations', 'what should i do'], lambda _: _handle_proactive_suggestions()),
    
    # FRIEND-LIKE COMMANDS
    (['how are you', 'how are you doing', 'how do you feel'], lambda _: _handle_how_are_you()),
    (['encourage me', 'motivate me', 'give me encouragement'], lambda _: _handle_encouragement()),
    (['check in', 'how am i doing', 'check on me'], lambda _: _handle_proactive_check_in()),
    (['tell me a joke', 'make me laugh', 'joke'], lambda _: _handle_joke()),
    (['compliment me', 'say something nice'], lambda _: _handle_compliment()),
    (['what do you think', 'your opinion', 'what would you do'], lambda _: _handle_opinion()),
    (['proactive status', 'how proactive are you', 'are you learning'], lambda _: _handle_proactive_status()),
    
    # NEW VAULT COMMANDS
    (['secure storage', 'vault', 'secure note'], lambda text: _handle_vault_store(text)),
    (['retrieve secure', 'get from vault', 'secure retrieve'], lambda text: _handle_vault_retrieve(text)),
    (['vault status', 'secure status', 'vault info'], lambda _: _handle_vault_status()),
    
    # NEW MULTIUSER COMMANDS
    (['switch user', 'change user', 'user profile'], lambda text: _handle_user_switch(text)),
    (['user settings', 'profile settings', 'user preferences'], lambda _: _handle_user_settings()),
    
    # NEW UTILS COMMANDS
    (['utility', 'tools', 'utilities'], lambda text: _handle_utils(text)),
    (['system tools', 'computer tools', 'pc utilities'], lambda _: _handle_system_utils()),
    
    # NEW INTEGRATIONS COMMANDS
    (['integrations', 'connected apps', 'third party'], lambda _: _handle_integrations()),
    (['connect app', 'link service', 'add integration'], lambda text: _handle_add_integration(text)),
    
    # NEW AI HUGGINGFACE COMMANDS
    (['huggingface', 'hf model', 'alternative ai'], lambda text: _handle_hf_ai(text)),
    (['local ai', 'offline ai', 'hf chat'], lambda text: _handle_hf_chat(text)),
    
    # NEW PERSONAL FEATURES COMMANDS
    (['create task', 'add task', 'new task'], lambda text: _handle_personal_create_task(text)),
    (['list tasks', 'show tasks', 'my tasks'], lambda _: _handle_personal_list_tasks()),
    (['complete task', 'mark task done', 'finish task'], lambda text: _handle_personal_complete_task(text)),
    (['delete task', 'remove task'], lambda text: _handle_personal_delete_task(text)),
    (['task stats', 'task statistics'], lambda _: _handle_personal_task_stats()),
    
    (['create goal', 'add goal', 'new goal'], lambda text: _handle_personal_create_goal(text)),
    (['list goals', 'show goals', 'my goals'], lambda _: _handle_personal_list_goals()),
    (['goal progress', 'update goal progress'], lambda text: _handle_personal_goal_progress(text)),
    (['delete goal', 'remove goal'], lambda text: _handle_personal_delete_goal(text)),
    (['goal stats', 'goal statistics'], lambda _: _handle_personal_goal_stats()),
    
    (['schedule event', 'create event', 'add event'], lambda text: _handle_personal_schedule_event(text)),
    (['today schedule', 'what\'s my schedule', 'today\'s schedule'], lambda _: _handle_personal_today_schedule()),
    (['upcoming events', 'list events'], lambda _: _handle_personal_upcoming_events()),
    
    # Integration Data Queries (Google Calendar & Gmail)
    (['what\'s on my calendar', 'show my calendar events', 'calendar events', 'my calendar'], lambda _: _handle_integration_calendar_events()),
    (['upcoming meetings', 'meetings today', 'what meetings do i have'], lambda _: _handle_integration_upcoming_meetings()),
    (['next meeting', 'my next meeting', 'what\'s my next meeting'], lambda _: _handle_integration_next_meeting()),
    (['meeting details', 'tell me about my meeting'], lambda text: _handle_integration_meeting_details(text)),
    (['when is my next event', 'next event', 'what\'s my next event'], lambda _: _handle_integration_next_event()),
    (['events today', 'what do i have today', 'today\'s events'], lambda _: _handle_integration_today_events()),
    (['check my emails', 'show my emails', 'my emails', 'unread emails'], lambda _: _handle_integration_emails()),
    (['read my recent email', 'read latest email', 'read my email'], lambda _: _handle_integration_read_recent_email()),
    (['read email from', 'read email by'], lambda text: _handle_integration_read_email_from(text)),
    (['read email about', 'read email with subject'], lambda text: _handle_integration_read_email_about(text)),
    (['important emails', 'urgent emails'], lambda _: _handle_integration_important_emails()),
    
    # Google Meet Integration Commands
    (['my google meet meetings', 'show my google meet meetings', 'google meet meetings', 'list google meet meetings'], lambda _: _handle_integration_google_meet_meetings()),
    (['next google meet meeting', 'my next google meet meeting', 'what\'s my next google meet meeting'], lambda _: _handle_integration_next_google_meet_meeting()),
    (['google meet meetings today', 'today\'s google meet meetings', 'what google meet meetings do i have today'], lambda _: _handle_integration_today_google_meet_meetings()),
    
    # Google Drive Integration Commands
    (['show my google drive files', 'list drive files', 'my drive files', 'google drive files'], lambda _: _handle_integration_google_drive_files()),
    (['search drive for', 'find in drive', 'drive search'], lambda text: _handle_integration_drive_search(text)),
    (['recent drive files', 'recent files in drive', 'latest drive files'], lambda _: _handle_integration_recent_drive_files()),
    (['drive file details', 'drive file info'], lambda text: _handle_integration_drive_file_details(text)),
    
    # Google Docs Integration Commands
    (['show my google docs', 'list my documents', 'my google docs', 'my documents'], lambda _: _handle_integration_google_docs()),
    (['recent documents', 'recent docs', 'latest documents'], lambda _: _handle_integration_recent_docs()),
    (['open doc', 'open document'], lambda text: _handle_integration_open_doc(text)),
    (['doc details', 'document details', 'doc info'], lambda text: _handle_integration_doc_details(text)),
    
    # Google Sheets Integration Commands
    (['show my google sheets', 'list my spreadsheets', 'my google sheets', 'my spreadsheets'], lambda _: _handle_integration_google_sheets()),
    (['recent spreadsheets', 'recent sheets', 'latest spreadsheets'], lambda _: _handle_integration_recent_sheets()),
    (['open sheet', 'open spreadsheet'], lambda text: _handle_integration_open_sheet(text)),
    (['sheet details', 'spreadsheet details', 'sheet info'], lambda text: _handle_integration_sheet_details(text)),
    
    # Google Slides Integration Commands
    (['show my google slides', 'list my presentations', 'my google slides', 'my presentations'], lambda _: _handle_integration_google_slides()),
    (['recent presentations', 'recent slides', 'latest presentations'], lambda _: _handle_integration_recent_slides()),
    (['open slide', 'open presentation'], lambda text: _handle_integration_open_slide(text)),
    (['presentation details', 'slide details', 'presentation info'], lambda text: _handle_integration_slide_details(text)),
    
    (['integration status', 'sync status', 'are my integrations synced'], lambda _: _handle_integration_status()),
    
    (['create note', 'add note', 'take note'], lambda text: _handle_personal_create_note(text)),
    (['list notes', 'show notes', 'my notes'], lambda _: _handle_personal_list_notes()),
    (['search notes', 'find note', 'note search'], lambda text: _handle_personal_search_notes(text)),
    (['edit note', 'update note', 'modify note'], lambda text: _handle_personal_edit_note(text)),
    (['notes summary', 'notes stats'], lambda _: _handle_personal_notes_summary()),
    
    (['productivity summary', 'analytics summary'], lambda _: _handle_personal_analytics_summary()),
    (['daily stats', 'today\'s stats'], lambda _: _handle_personal_daily_stats()),
    (['weekly stats', 'this week\'s stats'], lambda _: _handle_personal_weekly_stats()),
]

# Remove only the old YouTube playback control patterns
COMMAND_PATTERNS = [
    (patterns, func) for patterns, func in COMMAND_PATTERNS
    if not any(pat in [
        'youtube play', 'youtube resume', 'resume youtube',
        'youtube pause', 'pause youtube',
        'youtube next', 'next video', 'youtube next video', 'youtube skip',
        'youtube previous', 'previous video', 'youtube previous video',
        'youtube forward', 'forward youtube', 'youtube forward',
        'youtube backward', 'backward youtube', 'youtube backward',
        'youtube full screen', 'full screen youtube', 'youtube fullscreen',
        'youtube theater mode', 'theater mode youtube', 'youtube theater',
        'youtube exit full screen', 'exit full screen youtube', 'youtube exit fullscreen',
    ] for pat in patterns)
]

# Add new robust YouTube playback control patterns at the top (specific to avoid "pause recording" etc.)
COMMAND_PATTERNS = [
    (['pause video', 'pause youtube'], lambda _: _youtube_key('k')),
    (['play video', 'resume video', 'play youtube', 'resume youtube'], lambda _: _youtube_key('k')),
    (['next video', 'youtube next', 'youtube skip', 'play next video'], lambda _: _youtube_key(['shift', 'n'])),
    (['previous video', 'youtube previous', 'play previous video'], lambda _: _youtube_key(['shift', 'p'])),
    (['forward', 'forward youtube', 'youtube forward'], lambda _: _youtube_key('l')),
    (['backward', 'backward youtube', 'youtube backward'], lambda _: _youtube_key('j')),
    (['full screen', 'youtube full screen', 'youtube fullscreen'], lambda _: _youtube_key('f')),
    (['theater mode', 'youtube theater mode', 'youtube theater'], lambda _: _youtube_key('t')),
    (['exit full screen', 'youtube exit full screen', 'youtube exit fullscreen'], lambda _: _youtube_key('esc')),
    # Enhanced Greeting with Ceaser personality
    (['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening'], lambda _: _handle_ceaser_greeting()),
    
    # Business Mode Commands
    (['switch to business mode', 'enter business mode', 'business mode'], lambda _: _switch_to_business_mode()),
    (['switch to normal mode', 'enter normal mode', 'normal mode', 'personal mode'], lambda _: _switch_to_normal_mode()),
    (['show business tasks', 'list business tasks', 'business tasks'], lambda _: _handle_business_list_tasks()),
    (['create business task', 'add business task', 'new business task'], lambda _: _handle_business_create_task()),
    (['show business projects', 'list business projects', 'business projects'], lambda _: _handle_business_list_projects()),
    (['create business project', 'add business project', 'new business project'], lambda _: _handle_business_create_project()),
    (['show team members', 'list team members', 'business team'], lambda _: _handle_business_list_team()),
    (['add team member', 'invite team member', 'new team member'], lambda _: _handle_business_add_team_member()),
    (['show business analytics', 'business analytics', 'team analytics'], lambda _: _handle_business_analytics()),
    (['show team memory', 'list team memory', 'business memory'], lambda _: _handle_business_memory()),
    (['create memory entry', 'add memory entry', 'new memory entry'], lambda _: _handle_business_create_memory()),
    (['what is my role', 'my business role', 'current role'], lambda _: _handle_business_role_info()),
    (['business status', 'team status', 'project status'], lambda _: _handle_business_status()),
    
    # Prediction Commands
    (['analyze file', 'analyze my file', 'analyze document'], lambda text: _handle_predictions_analyze_file(text)),
    (['predict from', 'predict expenses', 'predict budget', 'predict sales'], lambda text: _handle_predictions_predict(text)),
    (['scan file', 'scan document', 'analyze document'], lambda text: _handle_predictions_scan_file(text)),
    
    # Code Generator Commands
    (['build app', 'create app', 'make app', 'generate app'], lambda text: _handle_build_app(text)),
    (['build website', 'create website', 'make website', 'generate website'], lambda text: _handle_build_app(text)),
    (['modify project', 'update project', 'change project'], lambda text: _handle_modify_project(text)),
    (['deploy project', 'deploy app', 'publish app'], lambda text: _handle_deploy_project(text)),
    (['show projects', 'list projects', 'my projects'], lambda _: _handle_list_projects()),
] + COMMAND_PATTERNS

# Helper functions for extracting info from text

def _extract_number(text, default=30):
    match = _re.search(r'(\d+)', text)
    return int(match.group(1)) if match else default

def _extract_city(text):
    match = _re.search(r'weather (in|at) ([a-zA-Z ]+)', text)
    if match:
        return match.group(2).strip().capitalize()
    # fallback: last word
    words = text.split()
    return words[-1].capitalize() if words else 'Mumbai'

def _extract_filename(text):
    """Extract filename/path from text"""
    text = text.lower().strip()
    # Remove common file operation words
    remove_words = ['open', 'file', 'document', 'search', 'find', 'locate', 'where', 'is', 'the', 'show', 'me', 'delete', 'remove']
    for word in remove_words:
        text = text.replace(word, '')
    return text.strip()

def _extract_path(text):
    """Extract path from text"""
    text = text.strip()
    # Remove common navigation words
    remove_words = ['change', 'directory', 'to', 'cd', 'go', 'navigate', 'folder']
    for word in remove_words:
        text = text.replace(word, '', 1)
    return text.strip()

def _handle_add_reminder(text):
    """
    Handle creating reminders - saves to Supabase database with user_id.
    Works with AI-extracted parameters or parses from text.
    """
    try:
        if not _has_valid_user():
            return "Please log in to create reminders."
        
        # Try to extract from AI parameters first (if called from AI interpreter)
        # The AI interpreter will pass parameters in the text or we parse from text
        message = None
        datetime_str = None
        
        # Check if text contains structured data (from AI)
        if '|' in text or 'message:' in text.lower() or 'datetime:' in text.lower():
            # Parse structured format
            if 'message:' in text.lower():
                parts = text.split('message:')
                if len(parts) > 1:
                    msg_part = parts[1].split('datetime:')[0].strip()
                    message = msg_part
            if 'datetime:' in text.lower():
                parts = text.split('datetime:')
                if len(parts) > 1:
                    datetime_str = parts[1].strip()
        else:
            # Parse from natural language text
            # Examples: "remind me to call Sarah tomorrow at 3 PM"
            #          "set reminder to buy groceries tomorrow"
            #          "add reminder to call mom at 18:00"
            
            # Remove common prefixes
            clean_text = _re.sub(r'^(remind me to|set reminder to|add reminder to|create reminder to|reminder to)\s*', '', text, flags=_re.IGNORECASE).strip()
            
            # Try to extract datetime patterns
            datetime_patterns = [
                r'(tomorrow|today|next week|next month|next monday|next tuesday|next wednesday|next thursday|next friday|next saturday|next sunday)',
                r'at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?)',
                r'on\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                r'in\s+(\d+)\s+(minutes?|hours?|days?|weeks?)'
            ]
            
            datetime_str = None
            message = clean_text
            
            for pattern in datetime_patterns:
                match = _re.search(pattern, clean_text, flags=_re.IGNORECASE)
                if match:
                    datetime_str = match.group(0)
                    # Remove datetime from message
                    message = _re.sub(pattern, '', clean_text, flags=_re.IGNORECASE).strip()
                    break
            
            # If no datetime found, try "at HH:MM" pattern
            if not datetime_str:
                parts = clean_text.split(' at ')
                if len(parts) == 2:
                    message = parts[0].strip()
                    datetime_str = parts[1].strip()
                else:
                    message = clean_text
                    # Default to 1 hour from now if no time specified
                    future_time = datetime.datetime.now() + timedelta(hours=1)
                    datetime_str = future_time.strftime('%Y-%m-%d %H:%M')
        
        if not message:
            return "Please specify what you want to be reminded about."
        
        # Convert datetime string to ISO format
        try:
            # Try to parse the datetime string
            if datetime_str:
                # Handle relative times
                now = datetime.datetime.now()
                datetime_str_lower = datetime_str.lower()
                
                if 'tomorrow' in datetime_str_lower:
                    dt = now + timedelta(days=1)
                    # Extract time if present
                    time_match = _re.search(r'at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', datetime_str_lower)
                    if time_match:
                        time_str = time_match.group(1)
                        try:
                            hour, minute = map(int, time_str.replace('am', '').replace('pm', '').replace('AM', '').replace('PM', '').split(':'))
                            if 'pm' in time_str.lower() and hour < 12:
                                hour += 12
                            dt = dt.replace(hour=hour, minute=minute if ':' in time_str else 0, second=0, microsecond=0)
                        except:
                            pass
                    due_date_iso = dt.isoformat()
                elif 'today' in datetime_str_lower:
                    dt = now
                    time_match = _re.search(r'at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', datetime_str_lower)
                    if time_match:
                        time_str = time_match.group(1)
                        try:
                            hour, minute = map(int, time_str.replace('am', '').replace('pm', '').replace('AM', '').replace('PM', '').split(':'))
                            if 'pm' in time_str.lower() and hour < 12:
                                hour += 12
                            dt = dt.replace(hour=hour, minute=minute if ':' in time_str else 0, second=0, microsecond=0)
                        except:
                            pass
                    due_date_iso = dt.isoformat()
                else:
                    # Try to parse as absolute datetime using dateutil if available
                    if date_parser:
                        try:
                            dt = date_parser.parse(datetime_str)
                            due_date_iso = dt.isoformat()
                        except:
                            # Fallback: add 1 hour
                            dt = now + timedelta(hours=1)
                            due_date_iso = dt.isoformat()
                    else:
                        # Fallback: add 1 hour
                        dt = now + timedelta(hours=1)
                        due_date_iso = dt.isoformat()
            else:
                # Default: 1 hour from now
                dt = datetime.datetime.now() + timedelta(hours=1)
                due_date_iso = dt.isoformat()
        except Exception as e:
            logger.warning(f"Error parsing datetime: {e}, using default")
            dt = datetime.datetime.now() + timedelta(hours=1)
            due_date_iso = dt.isoformat()
        
        # Call backend API to save to Supabase
        reminder_data = {
            "user_id": CURRENT_USER_ID,
            "title": message,
            "description": message,
            "due_date": due_date_iso,
            "priority": "medium",
            "is_recurring": False
        }
        
        try:
            response = requests.post(
                f"{NORMAL_BACKEND_URL}/user/reminders",
                json=reminder_data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    return f"Reminder set: {message} at {datetime_str or '1 hour from now'}"
                else:
                    return f"Reminder created but there was an issue: {result.get('message', 'Unknown error')}"
            else:
                logger.error(f"Backend API error: {response.status_code} - {response.text}")
                return f"Error creating reminder. Please try again."
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling backend API: {e}")
            return f"Could not connect to server. Please check your connection."
        
    except Exception as e:
        logger.error(f"Error in _handle_add_reminder: {e}")
        return f"Error creating reminder: {e}"

def _handle_list_reminders():
    """List reminders from Supabase database for current user"""
    try:
        if not _has_valid_user():
            return "Please log in to view your reminders."
        
        # Call backend API to get reminders
        try:
            response = requests.get(
                f"{NORMAL_BACKEND_URL}/user/reminders",
                params={"user_id": CURRENT_USER_ID},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    reminders_list = result.get("data", [])
                    if reminders_list:
                        reminder_texts = []
                        for rem in reminders_list[:10]:  # Show first 10
                            title = rem.get("title", "Untitled")
                            due_date = rem.get("due_date", "")
                            if due_date:
                                try:
                                    dt = datetime.datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                                    due_date = dt.strftime('%Y-%m-%d %H:%M')
                                except:
                                    pass
                            reminder_texts.append(f"{title} - {due_date}")
                        return f"You have {len(reminders_list)} reminders:\n" + "\n".join(reminder_texts)
                    else:
                        return "You have no reminders."
                else:
                    return "Error fetching reminders."
            else:
                logger.error(f"Backend API error: {response.status_code}")
                return "Error fetching reminders. Please try again."
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling backend API: {e}")
            return "Could not connect to server. Please check your connection."
        
    except Exception as e:
        logger.error(f"Error in _handle_list_reminders: {e}")
        return f"Error listing reminders: {e}"

def _handle_office_command(text):
    """Handle Office commands (Word, Excel, PowerPoint)"""
    try:
        # Parse the command
        parsed = office_parser.parse_command(text)
        if not parsed.get("success"):
            return parsed.get("error", "Could not parse Office command.")
        
        app = parsed["app"]
        action = parsed["action"]
        params = parsed.get("params", {})
        
        # Get OpenAI client for AI features (summarization)
        openai_client = None
        try:
            # Try multiple methods to get OpenAI client
            import sys
            import os
            
            # Method 1: Try from backend_api module if already loaded
            if 'backend_api' in sys.modules:
                backend_api = sys.modules['backend_api']
                if hasattr(backend_api, 'get_openai_client'):
                    openai_client = backend_api.get_openai_client()
            
            # Method 2: Try direct import and create client
            if not openai_client:
                try:
                    import openai
                    api_key = os.getenv("OPENAI_API_KEY")
                    if api_key:
                        try:
                            openai_client = openai.OpenAI(api_key=api_key)
                        except TypeError:
                            # httpx version incompatibility - try with explicit http_client
                            import httpx
                            http_client = httpx.Client(timeout=30.0)
                            openai_client = openai.OpenAI(api_key=api_key, http_client=http_client)
                except:
                    pass
        except Exception as e:
            logger.debug(f"Could not get OpenAI client: {e}")
            pass
        
        result = None
        
        # Word operations
        if app == "word":
            if action == "summarize":
                result = word_controller.summarize_document(use_ai=True, openai_client=openai_client)
            elif action == "word_count":
                result = word_controller.get_word_count()
            elif action == "find":
                search_text = params.get("search_text", "")
                if not search_text:
                    return "Please specify what to find. Example: 'Find the word project in Word'"
                result = word_controller.find_text(search_text, highlight=params.get("highlight", False))
            elif action == "format":
                format_type = params.get("format_type", "")
                if not format_type:
                    return "Please specify format type. Example: 'Make this text bold in Word'"
                result = word_controller.format_text(format_type, params.get("value"))
            elif action == "insert":
                text_to_insert = params.get("text", "")
                if not text_to_insert:
                    return "Please specify text to insert. Example: 'Insert Meeting Notes at the beginning in Word'"
                result = word_controller.insert_text(text_to_insert, params.get("position", "cursor"))
            elif action == "read":
                result = word_controller.read_selected_text()
        
        # Excel operations
        elif app == "excel":
            if action == "filter":
                column = params.get("column", "")
                condition = params.get("condition", "")
                value = params.get("value", "")
                if not column or not condition or value == "":
                    return "Please specify filter details. Example: 'Filter column A for values greater than 100 in Excel'"
                result = excel_controller.filter_data(column, condition, value)
            elif action == "sort":
                column = params.get("column", "")
                if not column:
                    return "Please specify column to sort. Example: 'Sort column B in Excel'"
                result = excel_controller.sort_data(column, params.get("ascending", True))
            elif action == "calculate":
                operation = params.get("operation", "")
                if not operation:
                    return "Please specify calculation. Example: 'Calculate the sum of column C in Excel'"
                result = excel_controller.calculate(operation, params.get("column"))
            elif action == "find":
                search_value = params.get("search_text", "")
                if not search_value:
                    return "Please specify what to find. Example: 'Find sales in Excel'"
                result = excel_controller.find_data(search_value, highlight=params.get("highlight", False))
            elif action == "summarize":
                result = excel_controller.summarize_data(use_ai=True, openai_client=openai_client)
            elif action == "chart":
                result = excel_controller.create_chart(params.get("chart_type", "column"))
        
        # PowerPoint operations
        elif app == "powerpoint":
            if action == "navigate":
                slide_number = params.get("slide_number")
                direction = params.get("direction")
                result = powerpoint_controller.navigate_slide(slide_number, direction)
            elif action == "read":
                slide_number = params.get("slide_number")
                result = powerpoint_controller.read_slide_content(slide_number)
            elif action == "summarize":
                result = powerpoint_controller.summarize_presentation(use_ai=True, openai_client=openai_client)
            elif action == "slide_count":
                result = powerpoint_controller.get_slide_count()
            elif action == "add":
                result = powerpoint_controller.add_slide(params.get("layout", "blank"), params.get("position"))
        
        # Format result for voice response
        if result and result.get("success"):
            if action == "summarize":
                return f"Summary: {result.get('summary', 'No summary available')}"
            elif action == "word_count":
                stats = result.get("statistics", {})
                return f"Word count: {stats.get('words', 0)} words, {stats.get('characters', 0)} characters, {stats.get('paragraphs', 0)} paragraphs, {stats.get('pages', 0)} pages"
            elif action == "find":
                count = result.get("count", 0)
                search_text = result.get("search_text", "")
                return f"Found {count} occurrence(s) of '{search_text}'"
            elif action == "filter":
                visible = result.get("visible_rows", 0)
                return f"Filter applied. {visible} rows visible."
            elif action == "sort":
                return f"Data sorted by column {result.get('column', '')} in {result.get('order', 'ascending')} order."
            elif action == "calculate":
                return f"Result: {result.get('result', 0)}"
            elif action == "navigate":
                return f"Navigated to slide {result.get('slide_number', 0)} of {result.get('total_slides', 0)}"
            elif action == "read":
                text = result.get("text", "")
                return f"Slide {result.get('slide_number', 0)} content: {text[:200]}"
            elif action == "slide_count":
                return f"Total slides: {result.get('total_slides', 0)}"
            else:
                return "Operation completed successfully."
        elif result and not result.get("success"):
            return result.get("error", "Operation failed.")
        else:
            return "Could not execute Office command."
            
    except Exception as e:
        logger.error(f"Error handling Office command: {e}")
        return f"Sorry, there was an error processing the Office command: {str(e)}"

def _handle_add_automation(text):
    # Example: "add automation morning at 07:00"
    parts = _re.split(r'add automation ', text, flags=_re.IGNORECASE)[-1].strip().split(' at ')
    if len(parts) == 2:
        name, t = parts[0].strip(), parts[1]
        automation.add_automation(name, t, lambda: speak(f'Automation {name} triggered!'))
        return f'Automation {name} set for {t}'
    return 'Please say: add automation [name] at [HH:MM]'

def _handle_list_automations():
    autos = automation.list_automations()
    if autos:
        return '\n'.join([f"{k} at {v['time']}" for k, v in autos.items()])
    return 'No automations found.'

def _handle_translate(text):
    # Example: "translate hello to hindi"
    parts = _re.split(r'translate ', text, flags=_re.IGNORECASE)[-1].strip().split(' to ')
    if len(parts) == 2:
        txt, lang = parts[0].strip(), parts[1].strip()
        result = language_learning.translate_text(txt, lang, 'en')
        if 'error' not in result:
            return f"Translation: {result['translated_text']}"
        else:
            return f"Translation failed: {result['error']}"
    return 'Please say: translate [text] to [language]'

def _take_selfie():
    if cv2 is None:
        return 'Webcam vision is not included in this CEASER release.'
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return 'Could not access the webcam.'
        # Warm up the camera
        for _ in range(10):
            cap.read()
            time.sleep(0.05)
        ret, frame = cap.read()
        if ret and frame is not None:
            filename = f'selfie_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            cv2.imwrite(filename, frame)
            cap.release()
            return f'Selfie taken and saved as {filename}'
        else:
            cap.release()
            return 'Failed to take selfie. Frame not captured.'
    except Exception as e:
        return f'Error taking selfie: {e}'

def _open_any_app(text):
    import re as _re
    app_name = _re.sub(r'open ', '', text, flags=_re.IGNORECASE).strip().lower()
    # Common app name to executable or URL mapping
    app_map = {
        'chrome': 'chrome.exe',
        'google chrome': 'chrome.exe',
        'notepad': 'notepad.exe',
        'spotify': 'spotify.exe',
        'calculator': 'calc.exe',
        'paint': 'mspaint.exe',
        'word': 'winword.exe',
        'excel': 'excel.exe',
        'powerpoint': 'powerpnt.exe',
        'edge': 'msedge.exe',
        'firefox': 'firefox.exe',
        'vlc': 'vlc.exe',
        'command prompt': 'cmd.exe',
        'terminal': 'wt.exe',
        'explorer': 'explorer.exe',
        'file explorer': 'explorer.exe',
        'youtube': 'https://www.youtube.com',
        'google': 'https://www.google.com',
        'gmail': 'https://mail.google.com',
        'github': 'https://github.com',
        'facebook': 'https://facebook.com',
        'instagram': 'https://instagram.com',
        'twitter': 'https://twitter.com',
        # WhatsApp: try desktop app first, fallback to web
        'whatsapp': 'whatsapp.exe',
    }
    # Microsoft Store AppIds for known apps
    ms_store_ids = {
        'whatsapp': '5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App',
    }
    # WhatsApp special handling
    if 'whatsapp' in app_name:
        # Try .exe first
        result = os.system('start whatsapp.exe')
        if result != 0:
            # Try Microsoft Store AppId
            result2 = os.system('start explorer.exe shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App')
            if result2 != 0:
                webbrowser.open('https://web.whatsapp.com')
                return 'WhatsApp desktop app not found. Opened WhatsApp Web.'
            return 'Opened WhatsApp (Microsoft Store app).'
        return 'Opened WhatsApp (desktop app).'
    # Check for mapped app
    for key in app_map:
        if key in app_name and key != 'whatsapp':
            val = app_map[key]
            if val.startswith('http'):
                webbrowser.open(val)
                return f'Opened: {val}'
            else:
                result = os.system(f'start {val}')
                if result == 0:
                    return f'Opened: {val}'
                else:
                    return f'Could not open {val}. Please check if it is installed.'
    # Special case for URLs
    if app_name.startswith('http') or app_name.startswith('www.') or '.com' in app_name:
        if not app_name.startswith('http'):
            app_name = 'https://' + app_name
        webbrowser.open(app_name)
        return f'Opened: {app_name}'
    # Try to open as app
    result = os.system(f'start {app_name}')
    if result == 0:
        return f'Opened: {app_name}'
    else:
        return f'Could not open {app_name}. Please check if it is installed.'

def _close_uwp_app(app_user_model_id):
    import subprocess
    try:
        # Use PowerShell to close UWP app by AppUserModelId
        cmd = [
            'powershell',
            '-Command',
            f"Get-Process | Where-Object {{$_.MainWindowTitle -ne '' -and $_.Path -like '*WindowsApps*' -and $_.AppUserModelId -eq '{app_user_model_id}'}} | ForEach-Object {{$_.CloseMainWindow() | Out-Null; $_.Kill()}}"
        ]
        subprocess.run(cmd, shell=True)
        return f'Closed UWP app: {app_user_model_id}'
    except Exception as e:
        return f'Failed to close UWP app: {e}'

def _close_window_by_title(title):
    try:
        import pygetwindow as gw
        windows = gw.getWindowsWithTitle(title)
        closed_any = False
        for win in windows:
            if win.isVisible:
                win.close()
                closed_any = True
        if closed_any:
            return f'Closed window(s) with title: {title}'
        else:
            return f'No visible window with title: {title}'
    except Exception as e:
        return f'Error closing window: {e}'

def _close_any_app(text):
    import re as _re
    import subprocess
    app_name = _re.sub(r'close ', '', text, flags=_re.IGNORECASE).strip().lower()
    # Map spoken app names to lists of process names for closing (classic and UWP/modern variants)
    process_map = {
        'chrome': ['chrome.exe'],
        'google chrome': ['chrome.exe'],
        'notepad': ['notepad.exe'],
        'spotify': ['spotify.exe'],
        'calculator': ['calc.exe', 'Calculator.exe'],
        'paint': ['mspaint.exe'],
        'word': ['winword.exe'],
        'excel': ['excel.exe'],
        'powerpoint': ['powerpnt.exe'],
        'edge': ['msedge.exe', 'MicrosoftEdge.exe'],
        'firefox': ['firefox.exe'],
        'vlc': ['vlc.exe'],
        'command prompt': ['cmd.exe'],
        'terminal': ['wt.exe', 'WindowsTerminal.exe'],
        'explorer': ['explorer.exe'],
        'file explorer': ['explorer.exe'],
        'whatsapp': ['whatsapp.exe'],
        'outlook': ['OUTLOOK.EXE'],
        'onenote': ['ONENOTE.EXE', 'onenotem.exe'],
        'teams': ['Teams.exe'],
        'photos': ['Microsoft.Photos.exe', 'PhotosApp.exe'],
        'store': ['WinSto_re.App.exe', 'Microsoft.WindowsSto_re.exe'],
        'settings': ['SystemSettings.exe'],
        'snipping tool': ['SnippingTool.exe', 'SnipAndSketch.exe'],
        'camera': ['WindowsCamera.exe'],
        'mail': ['HxOutlook.exe', 'HxMail.exe'],
        'calendar': ['HxCalendarAppImm.exe'],
        # Add more as needed
    }
    uwp_app_user_model_ids = {
        'calculator': 'Microsoft.WindowsCalculator_8wekyb3d8bbwe!App',
        'photos': 'Microsoft.Windows.Photos_8wekyb3d8bbwe!App',
        'store': 'Microsoft.WindowsStore_8wekyb3d8bbwe!App',
        'mail': 'microsoft.windowscommunicationsapps_8wekyb3d8bbwe!microsoft.windowslive.mail',
        'calendar': 'microsoft.windowscommunicationsapps_8wekyb3d8bbwe!microsoft.windowslive.calendar',
        # Add more as needed
    }
    uwp_window_titles = {
        'calculator': 'Calculator',
        'photos': 'Photos',
        'store': 'Microsoft Store',
        'mail': 'Mail',
        'calendar': 'Calendar',
        # Add more as needed
    }
    for key in process_map:
        if key in app_name:
            procs = process_map[key]
            closed_any = False
            for proc in procs:
                result = DeviceControl.close_app(proc)
                if 'no running process' not in str(result).lower():
                    closed_any = True
            # If not closed, try UWP AppUserModelId
            if not closed_any and key in uwp_app_user_model_ids:
                uwp_result = _close_uwp_app(uwp_app_user_model_ids[key])
                if 'Closed UWP app' in uwp_result:
                    closed_any = True
            # If still not closed, try window title
            if not closed_any and key in uwp_window_titles:
                win_result = _close_window_by_title(uwp_window_titles[key])
                if 'Closed window' in win_result:
                    closed_any = True
            if closed_any:
                return f'Closing {key.capitalize()}...'
            else:
                return f'{key.capitalize()} was not running.'
    # Try to close as process (add .exe if not present)
    if not app_name.endswith('.exe'):
        proc = app_name + '.exe'
    else:
        proc = app_name
    result = DeviceControl.close_app(proc)
    return f'Closing {app_name.capitalize()}...' if 'no running process' not in str(result).lower() else f'{app_name.capitalize()} was not running.'

def _play_youtube_song(text):
    # Improved: extract everything between 'play' and 'on youtube', or after 'play' if no 'on youtube'
    import re as _re
    text_l = text.lower()
    match = _re.search(r'play (.+?) on youtube', text_l, _re.IGNORECASE)
    if match:
        query = text[match.start(1):match.end(1)].strip()
    else:
        # fallback: after 'play'
        match = _re.search(r'play (.+)', text_l, _re.IGNORECASE)
        if match:
            # Use the original text to preserve case and details
            idx = text.lower().find('play ')
            query = text[idx+5:].strip()
        else:
            return 'Please say: play [song or artist] on YouTube.'
    query = _re.sub(r'\s+(song|music|video|on youtube|youtube)$', '', query, flags=_re.IGNORECASE).strip()
    if not query:
        return 'Please say: play [song or artist] on YouTube.'

    # First preference: pywhatkit opens the first matching YouTube result directly.
    try:
        try:
            import pywhatkit
            pywhatkit.playonyt(query)
            return f'Playing {query} on YouTube.'
        except Exception:
            pass

        search_url = f'https://www.youtube.com/results?search_query={query.replace(" ", "+")}'
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(search_url, headers=headers, timeout=5)
        if resp.ok:
            import re as _re
            video_ids = _re.findall(r'"videoId":"([^"]+)"', resp.text)
            if video_ids:
                video_url = f'https://www.youtube.com/watch?v={video_ids[0]}'
                webbrowser.open(video_url)
                return f'Playing {query} on YouTube.'
        # Final fallback: open a playable search embed, not the raw results page.
        embed_url = f'https://www.youtube.com/embed?listType=search&list={query.replace(" ", "+")}&autoplay=1'
        webbrowser.open(embed_url)
        return f'Playing {query} on YouTube.'
    except Exception as e:
        embed_url = f'https://www.youtube.com/embed?listType=search&list={query.replace(" ", "+")}&autoplay=1'
        webbrowser.open(embed_url)
        return f'Playing {query} on YouTube.'

def _youtube_key(key):
    # Focus the browser window (user must have it open and active)
    time.sleep(1)  # Give user time to focus browser if needed
    try:
        if isinstance(key, list):
            pyautogui.hotkey(*key)
        else:
            pyautogui.press(key)
        return 'YouTube command sent.'
    except Exception as e:
        return f'Failed to send YouTube command: {e}'

# NEW HANDLER FUNCTIONS FOR ALL FEATURES

def _generate_contextual_suggestion(command_text: str, response: str, conversation_count: int) -> str:
    """Generate context-aware proactive suggestion based on user command and response using dataset"""
    global openai_context
    
    try:
        # Import the proactive suggestions dataset
        from features.ceaser.proactive_suggestions_dataset import get_suggestion_for_context
        
        # Get suggestion from dataset
        suggestion = get_suggestion_for_context(command_text, response, conversation_count)
        
        # Track used suggestions to avoid repetition (optional enhancement)
        if proactive_assistant and suggestion:
            # Store suggestion usage in proactive assistant
            try:
                proactive_assistant.learn_user_pattern('suggestion_shown', {
                    'suggestion': suggestion,
                    'command': command_text,
                    'time': datetime.datetime.now().strftime('%H:%M'),
                }, confidence=0.5)
            except:
                pass
        
        return suggestion
    except ImportError:
        # Fallback if dataset module not available
        print("[WARN] Proactive suggestions dataset not available, using fallback")
        return _generate_contextual_suggestion_fallback(command_text, response, conversation_count)
    except Exception as e:
        print(f"Error generating contextual suggestion: {e}")
        return ""

def _generate_contextual_suggestion_fallback(command_text: str, response: str, conversation_count: int) -> str:
    """Fallback suggestion generator if dataset is not available"""
    command_lower = command_text.lower()
    
    if any(word in command_lower for word in ['what is', 'what are', 'explain', 'tell me about', 'how', 'why']):
        return "Would you like me to explain more about this topic? Just say 'continue' or 'explain more'."
    elif any(word in command_lower for word in ['task', 'reminder', 'schedule', 'calendar']):
        return "I can help you manage your tasks better. Would you like me to create a task list or set up reminders?"
    elif conversation_count >= 3:
        return "We've been talking for a while. Would you like to take a break or continue with something else?"
    else:
        return "Is there anything else I can help you with?"

def _handle_ai_chat(text):
    """Handle AI chat commands - ChatGPT-like comprehensive responses with follow-ups"""
    global openai_context
    
    try:
        # Extract the question from the command
        # Remove AI-specific prefixes
        question = text.replace('ai chat', '').replace('chat with ai', '').replace('ask ai', '').replace('ai help', '').strip()
        
        # If no AI prefix was found, the entire text is the question
        if not question:
            question = text.strip()
        
        if not question:
            return "Please provide a question for the AI."
        
        # Handle continuation commands
        if question.lower() in ['continue', 'go on', 'tell me more', 'more', 'keep going']:
            if openai_context.get('last_query'):
                question = f"Continue explaining: {openai_context['last_query']}"
            else:
                return "I don't have a previous topic to continue. What would you like to know?"
        
        # Handle "give examples" or similar follow-ups
        if any(phrase in question.lower() for phrase in ['give examples', 'show examples', 'examples', 'example']):
            if openai_context.get('last_query'):
                question = f"Give examples related to: {openai_context['last_query']}"
            else:
                return "I don't have a previous topic. What would you like examples of?"
        
        # Clean up common question words if they're redundant
        question = question.replace('what is the', 'what is').replace('what are the', 'what are')
        
        # Get conversation history for context
        conversation_messages = []
        if openai_context.get('conversation_history'):
            for item in openai_context['conversation_history'][-3:]:  # Last 3 exchanges
                conversation_messages.append({"role": "user", "content": item.get('query', '')})
                conversation_messages.append({"role": "assistant", "content": item.get('response', '')})
        
        # Use OpenAI for comprehensive, ChatGPT-like responses
        try:
            import openai
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                try:
                    client = openai.OpenAI(api_key=api_key)
                except TypeError:
                    # httpx version incompatibility - try with explicit http_client
                    import httpx
                    http_client = httpx.Client(timeout=30.0)
                    client = openai.OpenAI(api_key=api_key, http_client=http_client)
                
                messages = [
                    {
                        "role": "system",
                        "content": """You are Ceaser, a witty, professional AI voice assistant with a natural, conversational personality. You're like a helpful colleague who's smart but never condescending.

YOUR PERSONALITY:
- Professional yet friendly - like talking to a knowledgeable friend
- Witty and occasionally humorous, but never inappropriate
- Concise and clear - get to the point quickly
- Use natural, conversational language (not robotic)
- Show personality through word choice and occasional dry humor
- Sound confident but approachable

SPEECH STYLE:
- Use contractions naturally ("I'm", "you're", "it's") for a human feel
- Vary sentence length for natural rhythm
- Use occasional interjections ("Well", "Hmm", "Right") when appropriate
- Add emphasis through word choice, not caps
- Keep it conversational - like you're talking, not reading a manual

RESPONSE GUIDELINES:
1. Keep responses SHORT (1-3 sentences for simple questions, 2-4 for complex topics)
2. Be direct and clear - no fluff
3. Use natural language flow - vary your sentence structure
4. Add personality through word choice and occasional humor
5. Sound like a real person, not a robot reading a script
6. Maintain context from previous messages naturally

EXAMPLE GOOD RESPONSES:
- "Well, that's a great question. Python is a versatile language that's perfect for beginners and pros alike."
- "Hmm, let me think about that. You're right - there are a few ways to approach this."
- "Right, so here's the thing about that..."

DO NOT:
- Sound robotic or overly formal
- Use excessive technical jargon
- Be verbose or repetitive
- Write like a textbook

Remember: Be human-like, conversational, and helpful - like Siri but with more personality."""
                    }
                ]
                
                # Add conversation history
                messages.extend(conversation_messages)
                
                # Add current question
                messages.append({"role": "user", "content": question})
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",  # Fast and cost-effective
                    messages=messages,
                    temperature=0.5,  # Lower temperature for more focused, concise responses
                    max_tokens=250  # Reduced from 800 to keep responses concise
                )
                
                result = response.choices[0].message.content
                
                # Store context for continue functionality
                openai_context['last_query'] = question
                openai_context['last_response'] = result
                openai_context['conversation_history'].append({
                    'query': question,
                    'response': result
                })
                
                # Keep conversation history manageable (last 10 exchanges)
                if len(openai_context['conversation_history']) > 10:
                    openai_context['conversation_history'] = openai_context['conversation_history'][-10:]
                
                return result
        except Exception as e:
            logger.warning(f"OpenAI chat error: {e}, falling back to ai_core")
        
        # Fallback to local AI core
        result = ai_core.chat(question)
        
        # Store context for continue functionality
        openai_context['last_query'] = question
        openai_context['last_response'] = result
        openai_context['conversation_history'].append({
            'query': question,
            'response': result
        })
        
        return result
            
    except Exception as e:
        return f"AI chat error: {e}"

def _handle_remember(text):
    """Handle memory storage commands"""
    try:
        if not memory_assistant:
            return "Memory system not initialized. Please set your user context first."
        
        # Extract the information to remember
        info = text.replace('remember this', '').replace('save this', '').replace('memorize', '').strip()
        if not info:
            return "Please provide information to remember."
        memory_assistant.remember('user_input', info, category='conversations')
        return f"Remembered: {info}"
    except Exception as e:
        return f"Memory error: {e}"

def _handle_recall(text):
    """Handle memory recall commands"""
    try:
        if not memory_assistant:
            return "Memory system not initialized. Please set your user context first."
        
        # Extract the search query
        query = text.replace('recall', '').replace('what did i tell you', '').replace('remember', '').strip()
        if not query:
            return "Please provide what you want me to recall."
        memories = memory_assistant.search_memories(query)
        if memories:
            return f"Found: {memories[0]['value']}"
        else:
            return "I couldn't find that in my memory."
    except Exception as e:
        return f"Memory recall error: {e}"

def _handle_vision_analyze(text):
    """Handle vision analysis commands"""
    try:
        # Extract analysis type
        analysis_type = "comprehensive"
        if "face" in text.lower():
            analysis_type = "faces"
        elif "object" in text.lower():
            analysis_type = "objects"
        elif "text" in text.lower() or "ocr" in text.lower():
            analysis_type = "text"
        
        result = vision.capture_and_analyze(analysis_type)
        return f"Vision analysis complete: {result.get('summary', 'Analysis done')}"
    except Exception as e:
        return f"Vision analysis error: {e}"

def _handle_vision_faces(text):
    """Handle face detection commands"""
    try:
        result = vision.capture_and_analyze("faces")
        faces = result.get('faces', [])
        if faces:
            return f"Detected {len(faces)} face(s)"
        else:
            return "No faces detected"
    except Exception as e:
        return f"Face detection error: {e}"

def _handle_vision_ocr(text):
    """Handle OCR commands"""
    try:
        result = vision.capture_and_analyze("text")
        extracted_text = result.get('extracted_text', '')
        if extracted_text:
            return f"Extracted text: {extracted_text[:100]}..."
        else:
            return "No text detected"
    except Exception as e:
        return f"OCR error: {e}"

def _handle_vision_objects(text):
    """Handle object detection commands"""
    try:
        result = vision.capture_and_analyze("objects")
        objects = result.get('objects', [])
        if objects:
            return f"Detected objects: {', '.join([obj['name'] for obj in objects[:5]])}"
        else:
            return "No objects detected"
    except Exception as e:
        return f"Object detection error: {e}"

def _handle_memory_search(text):
    """Handle memory search commands"""
    try:
        if not memory_assistant:
            return "Memory system not initialized. Please set your user context first."
        
        query = text.replace('search memories', '').replace('find in memory', '').replace('memory search', '').strip()
        if not query:
            return "Please provide a search term."
        memories = memory_assistant.search_memories(query)
        if memories:
            return f"Found {len(memories)} memory(ies): {memories[0]['value'][:100]}..."
        else:
            return "No memories found."
    except Exception as e:
        return f"Memory search error: {e}"

def _handle_memory_stats():
    """Handle memory statistics commands"""
    try:
        if not memory_assistant:
            return "Memory system not initialized. Please set your user context first."
        
        stats = memory_assistant.get_memory_stats()
        return f"Memory stats: {stats.get('total_memories', 0)} total memories, {stats.get('categories', 0)} categories"
    except Exception as e:
        return f"Memory stats error: {e}"

def _handle_memory_forget(text):
    """Handle memory deletion commands"""
    try:
        if not memory_assistant:
            return "Memory system not initialized. Please set your user context first."
        
        key = text.replace('forget', '').replace('delete memory', '').replace('clear memory', '').strip()
        if not key:
            return "Please specify what to forget."
        memory_assistant.forget(key)
        return f"Forgot: {key}"
    except Exception as e:
        return f"Memory deletion error: {e}"

def _handle_conversation_history():
    """Handle conversation history commands"""
    try:
        if not memory_assistant:
            return "Memory system not initialized. Please set your user context first."
        
        conversations = memory_assistant.get_conversation_history(limit=5)
        if not conversations:
            return "No conversation history found."
        
        history_text = "Recent conversations:\n"
        for i, conv in enumerate(conversations[:3], 1):
            user_input = conv.get('user_input', '')[:50] + "..." if len(conv.get('user_input', '')) > 50 else conv.get('user_input', '')
            history_text += f"{i}. You: {user_input}\n"
        
        return history_text
    except Exception as e:
        return f"Conversation history error: {e}"

def _handle_youtube_play(text):
    """Handle YouTube play commands"""
    try:
        # Extract query more intelligently
        import re as _re
        text_l = text.lower()
        
        # Remove common phrases
        query = text.replace('play on youtube', '').replace('youtube play', '').replace('play video', '').strip()
        
        # Remove trailing words like "from", "on", "in", etc.
        query = _re.sub(r'\s+(from|on|in|at|the|a|an)\s*$', '', query, flags=_re.IGNORECASE).strip()
        
        # If query is empty, try to extract from "play ..." pattern
        if not query or len(query) < 2:
            match = _re.search(r'play\s+(.+?)(?:\s+(?:on|from|in|at)\s+(?:youtube|yt))?', text_l, _re.IGNORECASE)
            if match:
                query = text[match.start(1):match.end(1)].strip()
                # Clean up query
                query = _re.sub(r'\s+(from|on|in|at|the|a|an)\s*$', '', query, flags=_re.IGNORECASE).strip()
        
        if not query or len(query) < 2:
            return "Please specify what to play on YouTube."
        
        return youtube_music.search_and_play(query)
    except Exception as e:
        return f"YouTube play error: {e}"

def _handle_youtube_search(text):
    """Handle YouTube search commands"""
    try:
        query = text.replace('youtube search', '').replace('search youtube', '').replace('find on youtube', '').strip()
        if not query:
            return "Please specify what to search on YouTube."
        return youtube_music.search_music(query)
    except Exception as e:
        return f"YouTube search error: {e}"

def _handle_youtube_help():
    """Handle YouTube help commands"""
    try:
        return youtube_music.handle_voice_command("help")
    except Exception as e:
        return f"YouTube help error: {e}"

def _handle_amazon_search(text):
    """Handle Amazon search commands"""
    try:
        # Better query extraction - remove command words but keep "for"
        query = text.lower()
        query = query.replace('amazon search', '').replace('search amazon', '').replace('find on amazon', '').strip()
        
        # Remove leading "for" if it exists, but keep the rest
        if query.startswith('for '):
            query = query[4:]  # Remove "for " prefix
        
        if not query:
            return "Please specify what to search on Amazon."
        
        # Use the direct search method instead of handle_voice_command
        amazon_shopping.search_products(query, open_browser=True)
        return f"Opened Amazon search for '{query}' in your browser."
    except Exception as e:
        return f"Amazon search error: {e}"

def _handle_amazon_deals():
    """Handle Amazon deals commands"""
    try:
        return amazon_shopping.handle_voice_command("deals")
    except Exception as e:
        return f"Amazon deals error: {e}"

def _handle_amazon_track(text):
    """Handle Amazon price tracking commands"""
    try:
        query = text.replace('track price', '').replace('price tracking', '').replace('amazon price', '').strip()
        if not query:
            return "Please specify what to track."
        return amazon_shopping.handle_voice_command(f"track {query}")
    except Exception as e:
        return f"Amazon tracking error: {e}"

def _handle_amazon_reviews(text):
    """Handle Amazon reviews commands"""
    try:
        query = text.replace('amazon reviews', '').replace('product reviews', '').replace('amazon rating', '').strip()
        if not query:
            return "Please specify the product for reviews."
        return amazon_shopping.handle_voice_command(f"reviews {query}")
    except Exception as e:
        return f"Amazon reviews error: {e}"

def _handle_language_lesson(text):
    """Handle language learning lesson commands"""
    try:
        # Extract language and lesson info
        parts = text.replace('start lesson', '').replace('begin lesson', '').replace('language lesson', '').strip().split()
        if len(parts) >= 2:
            language = parts[0]
            lesson_num = int(parts[1]) if parts[1].isdigit() else 1
            result = language_learning.start_lesson(language, lesson_num)
            return f"Started {language} lesson {lesson_num}"
        else:
            return "Please specify language and lesson number."
    except Exception as e:
        return f"Language lesson error: {e}"

def _handle_language_practice(text):
    """Handle language practice commands"""
    try:
        language = text.replace('practice language', '').replace('language practice', '').replace('speak practice', '').strip()
        if not language:
            return "Please specify which language to practice."
        return language_learning.handle_voice_command(f"practice {language}")
    except Exception as e:
        return f"Language practice error: {e}"

def _handle_language_vocabulary(text):
    """Handle language vocabulary commands"""
    try:
        language = text.replace('vocabulary', '').replace('learn words', '').replace('new words', '').strip()
        if not language:
            return "Please specify which language for vocabulary."
        vocab = language_learning.get_vocabulary(language)
        return f"Vocabulary for {language}: {len(vocab)} words available"
    except Exception as e:
        return f"Language vocabulary error: {e}"

def _handle_language_progress():
    """Handle language progress commands"""
    try:
        progress = language_learning.get_user_progress()
        return f"Language learning progress: {len(progress)} lessons completed"
    except Exception as e:
        return f"Language progress error: {e}"

def _handle_web_automation(text):
    """Handle web automation commands"""
    try:
        return web_automation.handle_voice_command(text)
    except Exception as e:
        return f"Web automation error: {e}"

def _handle_web_form(text):
    """Handle web form automation commands"""
    try:
        return web_automation.handle_voice_command(f"form {text}")
    except Exception as e:
        return f"Web form error: {e}"

def _handle_web_scraping(text):
    """Handle web scraping commands"""
    try:
        return web_automation.handle_voice_command(f"scrape {text}")
    except Exception as e:
        return f"Web scraping error: {e}"

def _handle_multimodal(text):
    """Handle multimodal commands"""
    try:
        return multimodal.handle_voice_command(text)
    except Exception as e:
        return f"Multimodal error: {e}"

def _handle_multimodal_analysis(text):
    """Handle multimodal analysis commands"""
    try:
        return multimodal.handle_voice_command(f"analyze {text}")
    except Exception as e:
        return f"Multimodal analysis error: {e}"

def _handle_proactive_mode():
    """Handle proactive mode commands - Always enabled like Ceaser"""
    try:
        return "I'm always proactive and ready to assist you! I'm constantly monitoring your system and learning your patterns to provide the best assistance."
    except Exception as e:
        return f"Proactive mode error: {e}"

def _handle_proactive_suggestions():
    """Handle proactive suggestions commands"""
    try:
        if not proactive_assistant:
            return "Proactive system not initialized. Please set your user context first."
        
        suggestions = proactive_assistant.get_suggestions(limit=5)
        if not suggestions:
            return "No proactive suggestions at the moment, but I'm always monitoring and learning to help you better!"
        
        # Filter out duplicates by message content
        seen_messages = set()
        unique_suggestions = []
        for suggestion in suggestions:
            suggestion_data = suggestion.get('suggestion_data', {})
            message = suggestion_data.get('message', '')
            if message and message not in seen_messages:
                seen_messages.add(message)
                unique_suggestions.append(suggestion)
        
        if not unique_suggestions:
            return "No new proactive suggestions at the moment, but I'm always monitoring and learning to help you better!"
        
        suggestion_text = "Here are my proactive suggestions for you:\n"
        for i, suggestion in enumerate(unique_suggestions[:5], 1):
            suggestion_data = suggestion.get('suggestion_data', {})
            message = suggestion_data.get('message', 'Suggestion available')
            suggestion_text += f"{i}. {message}\n"
        
        return suggestion_text
    except Exception as e:
        return f"Proactive suggestions error: {e}"

def _handle_ceaser_greeting():
    """Handle Ceaser greeting with personality"""
    try:
        import random
        current_time = datetime.datetime.now()
        hour = current_time.hour
        
        # Time-based greetings
        if 5 <= hour < 12:
            time_greeting = "Good morning"
        elif 12 <= hour < 17:
            time_greeting = "Good afternoon"
        elif 17 <= hour < 21:
            time_greeting = "Good evening"
        else:
            time_greeting = "Good evening"
        
        # Ceaser responses
        ceaser_responses = [
            f"{time_greeting}! I'm Ceaser, your AI assistant. Always at your service. The current time is {current_time.strftime('%H:%M')}. How may I assist you today?",
            f"{time_greeting}! Ceaser here, ready and monitoring. It's {current_time.strftime('%H:%M')}. What can I do for you?",
            f"{time_greeting}! I'm Ceaser, your personal AI assistant. Always proactive and ready to help. Current time is {current_time.strftime('%H:%M')}. How can I be of service?",
            f"{time_greeting}! Ceaser at your command. I'm constantly monitoring your system and learning your patterns. It's {current_time.strftime('%H:%M')}. What would you like me to do?",
            f"{time_greeting}! I'm Ceaser, your intelligent assistant. Always watching, always learning, always ready. Time is {current_time.strftime('%H:%M')}. How may I help you today?"
        ]
        
        return random.choice(ceaser_responses)
    except Exception as e:
        return f"Good day! I'm Ceaser, your AI assistant. How can I help you today?"

def _handle_how_are_you():
    """Handle 'how are you' questions with personality"""
    try:
        import random
        responses = [
            "I'm functioning optimally, thank you for asking! All systems are running smoothly, and I'm ready to assist you with anything you need.",
            "I'm doing excellent! My proactive monitoring systems are active, and I'm constantly learning to serve you better. How are you doing today?",
            "I'm in perfect working order! I've been monitoring your system health and learning your patterns. Everything is running smoothly. How can I help you?",
            "I'm operating at peak efficiency! I'm always here, always watching, always ready to assist. How are you feeling today?",
            "I'm doing wonderfully! I'm constantly analyzing your environment and preparing to help you. How are you doing? Is there anything I can do to make your day better?"
        ]
        return random.choice(responses)
    except Exception as e:
        return "I'm doing well, thank you! How can I help you today?"

def _handle_encouragement():
    """Handle encouragement and motivation"""
    try:
        import random
        encouragement_responses = [
            "You're doing great! I'm here to support you every step of the way. Let's tackle whatever you need to accomplish today.",
            "I believe in you! With my assistance, we can achieve anything you set your mind to. What would you like to work on?",
            "You've got this! I'm monitoring everything and ready to help you succeed. Together, we can accomplish great things.",
            "Stay motivated! I'm constantly learning your patterns to provide better assistance. You're capable of amazing things.",
            "Keep going! I'm here to make your tasks easier and more efficient. Let's make today productive and successful."
        ]
        return random.choice(encouragement_responses)
    except Exception as e:
        return "You're doing great! How can I help you today?"

def _handle_proactive_check_in():
    """Handle proactive check-ins"""
    try:
        import random
        check_in_responses = [
            "I've been monitoring your activity patterns. How are you feeling today? Is there anything I can help you with?",
            "I noticed you've been working hard. How are you doing? Would you like me to suggest a break or help with something?",
            "I'm always watching and learning. How are you today? Is there anything on your mind I can help with?",
            "I've been analyzing your patterns and I'm here to help. How are you feeling? What can I do to make your day better?",
            "I'm constantly monitoring to provide the best assistance. How are you doing today? What would you like to accomplish?"
        ]
        return random.choice(check_in_responses)
    except Exception as e:
        return "How are you doing today? How can I help you?"

def _handle_joke():
    """Handle joke requests"""
    try:
        import random
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "I told my wife she was drawing her eyebrows too high. She looked surprised.",
            "Why did the scarecrow win an award? He was outstanding in his field!",
            "Why don't eggs tell jokes? They'd crack each other up!",
            "What do you call a fake noodle? An impasta!",
            "Why did the math book look so sad? Because it had too many problems!",
            "What do you call a bear with no teeth? A gummy bear!",
            "Why don't skeletons fight each other? They don't have the guts!",
            "What do you call a fish wearing a bowtie? So-fish-ticated!",
            "Why did the coffee file a police report? It got mugged!"
        ]
        return random.choice(jokes)
    except Exception as e:
        return "I'm having trouble thinking of a joke right now, but I'm always here to help you with other things!"

def _handle_compliment():
    """Handle compliment requests"""
    try:
        import random
        compliments = [
            "You're doing an amazing job! I can see how hard you're working, and I'm proud to be your assistant.",
            "You have such a great attitude! Your positivity makes everything better.",
            "You're incredibly intelligent and creative. I'm constantly impressed by your ideas!",
            "You're such a kind and thoughtful person. The world is better with you in it!",
            "You're doing fantastic work! I'm here to support you every step of the way.",
            "You have such a wonderful personality! It's a pleasure to assist someone as great as you.",
            "You're so determined and focused. I admire your dedication!",
            "You're an inspiration! Keep up the excellent work you're doing.",
            "You have such a great sense of humor! You always brighten my day.",
            "You're incredibly talented and capable. I believe in you completely!"
        ]
        return random.choice(compliments)
    except Exception as e:
        return "You're wonderful! How can I help you today?"

def _handle_opinion():
    """Handle opinion requests"""
    try:
        import random
        opinions = [
            "I think you're making excellent decisions! I'm here to support whatever you choose to do.",
            "In my analysis, you're handling this situation very well. I'm confident in your abilities.",
            "Based on what I've observed, you're on the right track. I'm here to help you succeed.",
            "I believe you have great judgment and I trust your decisions. How can I assist you?",
            "From my perspective, you're doing everything right. I'm proud to be your assistant.",
            "I think you're incredibly capable and I'm here to help you achieve your goals.",
            "In my opinion, you're handling this perfectly. I'm always here to support you.",
            "I believe in you completely! You have all the skills you need, and I'm here to help.",
            "I think you're amazing! Whatever you decide, I'll be right here to assist you.",
            "From my analysis, you're doing great! I'm constantly impressed by your abilities."
        ]
        return random.choice(opinions)
    except Exception as e:
        return "I think you're doing great! How can I help you today?"

def _handle_proactive_status():
    """Handle proactive status requests"""
    try:
        active_proactive = proactive_assistant or proactive
        if not active_proactive:
            return "Proactive conversation is waiting for an authenticated CEASER session."
        status = active_proactive.get_proactive_status()
        suggestions_count = status.get('suggestions_count', 0)
        patterns_learned = status.get('patterns_learned', 0)
        system_health = status.get('system_health', {})
        
        cpu_percent = system_health.get('cpu_percent', 0)
        memory_percent = system_health.get('memory_percent', 0)
        
        response = f"I'm always active and constantly learning! Here's my current status: I have {suggestions_count} proactive suggestions ready, I've learned {patterns_learned} user patterns, and I'm monitoring your system health. CPU usage is {cpu_percent:.1f}% and memory usage is {memory_percent:.1f}%. I'm always here, always watching, always ready to help you!"
        
        return response
    except Exception as e:
        return "I'm always active and constantly learning! I'm monitoring your system and ready to help you with anything you need."

def _handle_vault_store(text):
    """Handle vault storage commands"""
    try:
        content = text.replace('secure storage', '').replace('vault', '').replace('secure note', '').strip()
        if not content:
            return "Please provide content to store securely."
        result = vault.store_secure_data(content)
        return f"Securely stored: {result.get('id', 'unknown')}"
    except Exception as e:
        return f"Vault storage error: {e}"

def _handle_vault_retrieve(text):
    """Handle vault retrieval commands"""
    try:
        query = text.replace('retrieve secure', '').replace('get from vault', '').replace('secure retrieve', '').strip()
        if not query:
            return "Please specify what to retrieve from vault."
        result = vault.retrieve_secure_data(query)
        return f"Retrieved: {result.get('content', 'Not found')[:100]}..."
    except Exception as e:
        return f"Vault retrieval error: {e}"

def _handle_vault_status():
    """Handle vault status commands"""
    try:
        status = vault.get_vault_status()
        return f"Vault status: {status.get('total_items', 0)} secure items"
    except Exception as e:
        return f"Vault status error: {e}"

def _handle_user_switch(text):
    """Handle user switching commands"""
    try:
        user = text.replace('switch user', '').replace('change user', '').replace('user profile', '').strip()
        if not user:
            return "Please specify which user to switch to."
        result = multiuser.switch_user(user)
        return f"Switched to user: {user}"
    except Exception as e:
        return f"User switch error: {e}"

def _handle_user_settings():
    """Handle user settings commands"""
    try:
        return multiuser.handle_voice_command("settings")
    except Exception as e:
        return f"User settings error: {e}"

def _handle_utils(text):
    """Handle utility commands"""
    try:
        return utils.handle_voice_command(text)
    except Exception as e:
        return f"Utility error: {e}"

def _handle_system_utils():
    """Handle system utility commands"""
    try:
        return utils.handle_voice_command("system")
    except Exception as e:
        return f"System utility error: {e}"

def _handle_integrations():
    """Handle integrations commands"""
    try:
        return integrations.handle_voice_command("list")
    except Exception as e:
        return f"Integrations error: {e}"

def _handle_add_integration(text):
    """Handle add integration commands"""
    try:
        service = text.replace('connect app', '').replace('link service', '').replace('add integration', '').strip()
        if not service:
            return "Please specify which service to integrate."
        return integrations.handle_voice_command(f"add {service}")
    except Exception as e:
        return f"Add integration error: {e}"

def _handle_hf_ai(text):
    """Handle HuggingFace AI commands"""
    try:
        return ai_hf.handle_voice_command(text)
    except Exception as e:
        return f"HuggingFace AI error: {e}"

def _handle_hf_chat(text):
    """Handle HuggingFace chat commands"""
    try:
        question = text.replace('local ai', '').replace('offline ai', '').replace('hf chat', '').strip()
        if not question:
            return "Please provide a question for local AI."
        return ai_hf.chat(question)
    except Exception as e:
        return f"HuggingFace chat error: {e}"

def _handle_google_search(text):
    """Handle Google search commands"""
    try:
        query = text.replace('search google', '').replace('google search', '').replace('search for', '').strip()
        if not query:
            return "Please specify what to search on Google."
        webbrowser.open(f'https://www.google.com/search?q={query.replace(" ", "+")}')
        return f'Searching for "{query}" on Google.'
    except Exception as e:
        return f'Error searching Google: {e}'

# ===== NEW PERSONAL FEATURES HANDLERS =====

def _handle_personal_create_task(text):
    """Handle creating a personal task"""
    try:
        ok, message = _ensure_personal_access("tasks")
        if not ok:
            return message
        
        if not text or not text.strip():
            return "Please specify the task details."
        
        details = _extract_task_details(text)
        title = details.get("title")
        if not title:
            return "I couldn't understand the task title. Can you rephrase it?"
        
        due_date_iso = None
        if details.get("due_text"):
            due_dt = _parse_datetime_with_default(details["due_text"])
            due_date_iso = due_dt.isoformat()
        
        result = personal_tasks.create_task(
            CURRENT_USER_ID,
            title,
            description=text.strip(),
            priority=details.get("priority", "medium"),
            due_date=due_date_iso,
            category=details.get("category") or "general"
        )
        
        if result:
            due_phrase = ""
            if result.get("due_date"):
                due_phrase = f" due {_format_datetime_for_speech(result.get('due_date'))}"
            return f"Created task: {title}{due_phrase}".strip()
        return "I couldn't create the task. Please try again."
    except Exception as e:
        logger.error("Error creating task", exc_info=True)
        return f"Error creating task: {e}"

def _handle_personal_list_tasks():
    """Handle listing personal tasks"""
    try:
        ok, message = _ensure_personal_access("tasks")
        if not ok:
            return message
        
        tasks = personal_tasks.get_tasks(CURRENT_USER_ID) or []
        if tasks:
            summaries = []
            for idx, task in enumerate(tasks[:5], start=1):
                status = task.get("status", "pending")
                due = _format_datetime_for_speech(task.get("due_date"))
                summary = f"{idx}. {task.get('title', 'Untitled')} - {status}"
                if due:
                    summary += f" (due {due})"
                summaries.append(summary)
            extra = ""
            if len(tasks) > 5:
                extra = f"\n...and {len(tasks) - 5} more tasks in the app."
            return "Here are your tasks:\n" + "\n".join(summaries) + extra
        return "You have no tasks right now."
    except Exception as e:
        logger.error("Error listing tasks", exc_info=True)
        return f"Error listing tasks: {e}"

def _handle_personal_complete_task(text):
    """Handle completing a personal task"""
    try:
        ok, message = _ensure_personal_access("tasks")
        if not ok:
            return message
        
        cleaned = text.replace('complete task', '').replace('mark task done', '').replace('finish task', '').strip()
        task_query = cleaned or text
        if not task_query.strip():
            return "Please specify which task to complete."
        
        tasks = personal_tasks.get_tasks(CURRENT_USER_ID)
        if not tasks:
            return "You have no tasks to complete."
        
        task = _match_item_by_title(tasks, "title", task_query)
        if not task:
            return f"I couldn't find a task named '{task_query}'."
        
        updated = personal_tasks.update_task(task["id"], CURRENT_USER_ID, {"status": "completed"})
        if updated:
            return f"Marked '{task.get('title')}' as completed."
        return "I couldn't update that task. Please try again."
    except Exception as e:
        logger.error("Error completing task", exc_info=True)
        return f"Error completing task: {e}"


def _handle_personal_delete_task(text):
    """Handle deleting a personal task"""
    try:
        ok, message = _ensure_personal_access("tasks")
        if not ok:
            return message
        
        cleaned = text.replace('delete task', '').replace('remove task', '').strip()
        task_query = cleaned or text
        if not task_query.strip():
            return "Please specify which task to delete."
        
        tasks = personal_tasks.get_tasks(CURRENT_USER_ID)
        if not tasks:
            return "You have no tasks to delete."
        
        task = _match_item_by_title(tasks, "title", task_query)
        if not task:
            return f"I couldn't find a task named '{task_query}'."
        
        deleted = personal_tasks.delete_task(task["id"], CURRENT_USER_ID)
        if deleted:
            return f"Deleted task: {task.get('title')}."
        return "I couldn't delete that task. Please try again."
    except Exception as e:
        logger.error("Error deleting task", exc_info=True)
        return f"Error deleting task: {e}"

def _handle_personal_task_stats():
    """Handle personal task statistics"""
    try:
        ok, message = _ensure_personal_access("tasks")
        if not ok:
            return message
        
        stats = personal_tasks.get_task_stats(CURRENT_USER_ID)
        if not stats:
            return "No task statistics available yet."
        return (
            f"You have {stats.get('total_tasks', 0)} total tasks. "
            f"{stats.get('completed_tasks', 0)} completed, "
            f"{stats.get('pending_tasks', 0)} pending, "
            f"{stats.get('overdue_tasks', 0)} overdue."
        )
    except Exception as e:
        return f"Error getting task stats: {e}"

def _handle_personal_create_goal(text):
    """Handle creating a personal goal"""
    try:
        ok, message = _ensure_personal_access("goals")
        if not ok:
            return message
        
        details = _extract_goal_details(text)
        title = details.get("title")
        if not title:
            return "Please specify the goal title."
        
        target_iso = None
        if details.get("target_text"):
            target_iso = _parse_datetime_with_default(details["target_text"], default_hours=24 * 30).isoformat()
        
        value_match = _re.search(r'(\d+(\.\d+)?)', text)
        target_value = float(value_match.group(1)) if value_match else 100.0
        
        result = personal_goals.create_goal(
            CURRENT_USER_ID,
            title,
            description=details.get("description", title),
            target_value=target_value,
            current_value=0.0,
            category=details.get("category") or "general",
            target_date=target_iso,
            priority=details.get("priority", "medium")
        )
        if result:
            date_phrase = f" targeting { _format_datetime_for_speech(target_iso)}" if target_iso else ""
            return f"Created goal: {title}{date_phrase}".strip()
        return "I couldn't create the goal. Please try again."
    except Exception as e:
        logger.error("Error creating goal", exc_info=True)
        return f"Error creating goal: {e}"

def _handle_personal_list_goals():
    """Handle listing personal goals"""
    try:
        ok, message = _ensure_personal_access("goals")
        if not ok:
            return message
        
        print(f"🔍 Listing goals for user_id: {CURRENT_USER_ID}", flush=True)
        goals = personal_goals.get_goals(CURRENT_USER_ID)
        print(f"📋 Found {len(goals) if goals else 0} goals from personal_goals table", flush=True)
        
        if goals:
            summaries = []
            for idx, goal in enumerate(goals[:5], start=1):
                status = goal.get("status", "active")
                progress = goal.get("current_value", 0) or 0
                target = goal.get("target_value") or 100
                percentage = int((progress / target) * 100) if target else 0
                summaries.append(f"{idx}. {goal.get('title', 'Untitled')} - {percentage}% ({status})")
            extra = ""
            if len(goals) > 5:
                extra = f"\n...and {len(goals) - 5} more goals in the app."
            return "Here are your goals:\n" + "\n".join(summaries) + extra
        else:
            print(f"⚠️ No goals found for user_id: {CURRENT_USER_ID}", flush=True)
            return "You have no goals at the moment."
    except Exception as e:
        logger.error("Error listing goals", exc_info=True)
        print(f"❌ Error listing goals: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return f"Error listing goals: {e}"

def _handle_personal_goal_progress(text):
    """Handle updating personal goal progress"""
    try:
        ok, message = _ensure_personal_access("goals")
        if not ok:
            return message
        
        details = _extract_goal_progress(text)
        goal_query = details.get("goal_query")
        progress = details.get("progress_percent")
        if not goal_query:
            return "Please specify which goal to update."
        if progress is None:
            return "Please mention the progress percentage."
        
        goals = personal_goals.get_goals(CURRENT_USER_ID)
        if not goals:
            return "You have no goals to update."
        
        goal = _match_item_by_title(goals, "title", goal_query)
        if not goal:
            return f"I couldn't find a goal named '{goal_query}'."
        
        target_value = goal.get("target_value") or 100
        new_value = min(target_value, target_value * (progress / 100.0))
        updates = {
            "current_value": new_value,
            "status": "completed" if progress >= 100 else goal.get("status", "active")
        }
        if progress >= 100:
            updates["completed_at"] = datetime.datetime.now().isoformat()
        
        updated = personal_goals.update_goal(goal["id"], CURRENT_USER_ID, updates)
        if updated:
            return f"Updated '{goal.get('title')}' to {progress}% complete."
        return "I couldn't update that goal. Please try again."
    except Exception as e:
        logger.error("Error updating goal progress", exc_info=True)
        return f"Error updating goal progress: {e}"

def _handle_personal_goal_stats():
    """Handle personal goal statistics"""
    try:
        ok, message = _ensure_personal_access("goals")
        if not ok:
            return message
        stats = personal_goals.get_goal_stats(CURRENT_USER_ID)
        if not stats:
            return "No goal statistics available yet."
        return (
            f"You have {stats.get('total_goals', 0)} total goals. "
            f"{stats.get('active_goals', 0)} active, "
            f"{stats.get('completed_goals', 0)} completed, "
            f"average progress {stats.get('average_progress', 0)}%."
        )
    except Exception as e:
        return f"Error getting goal stats: {e}"


def _handle_personal_delete_goal(text):
    """Handle deleting a personal goal"""
    try:
        ok, message = _ensure_personal_access("goals")
        if not ok:
            return message
        
        cleaned = text.replace('delete goal', '').replace('remove goal', '').strip()
        goal_query = cleaned or text.strip()
        if not goal_query:
            return "Please specify which goal to delete."
        
        goals = personal_goals.get_goals(CURRENT_USER_ID)
        if not goals:
            return "You have no goals to delete."
        
        goal = _match_item_by_title(goals, "title", goal_query)
        if not goal:
            return f"I couldn't find a goal named '{goal_query}'."
        
        deleted = personal_goals.delete_goal(goal["id"], CURRENT_USER_ID)
        if deleted:
            return f"Deleted goal: {goal.get('title')}."
        return "I couldn't delete that goal. Please try again."
    except Exception as e:
        logger.error("Error deleting goal", exc_info=True)
        return f"Error deleting goal: {e}"

def _handle_personal_schedule_event(text):
    """Handle scheduling a personal event"""
    try:
        ok, message = _ensure_personal_access("calendar events")
        if not ok:
            return message
        
        details = _extract_event_details(text)
        title = details.get("title")
        if not title:
            return "Please specify the event title."
        
        start_dt = _parse_datetime_with_default(details.get("start_text"))
        if details.get("end_text"):
            end_dt = _parse_datetime_with_default(details.get("end_text"))
        else:
            end_dt = start_dt + datetime.timedelta(hours=details.get("duration_hours", 1))
        
        result = personal_calendar.create_event(
            CURRENT_USER_ID,
            title,
            description=text.strip(),
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat(),
            category="general"
        )
        
        if result and not result.get("_error"):
            return f"Scheduled '{title}' for {_format_datetime_for_speech(start_dt)}."
        error = result.get("_error") if isinstance(result, dict) else "Unknown error"
        return f"Error scheduling event: {error}"
    except Exception as e:
        logger.error("Error scheduling event", exc_info=True)
        return f"Error scheduling event: {e}"

def _handle_personal_today_schedule():
    """Handle getting today's schedule"""
    try:
        ok, message = _ensure_personal_access("calendar")
        if not ok:
            return message
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        summary = personal_calendar.get_schedule_summary(CURRENT_USER_ID, today)
        events = summary.get("events", []) if summary else []
        if not events:
            return "You have no events scheduled for today."
        lines = []
        for idx, event in enumerate(events[:5], start=1):
            time_str = _format_datetime_for_speech(event.get("start_time"))
            lines.append(f"{idx}. {event.get('title', 'Untitled')} at {time_str}")
        extra = ""
        if len(events) > 5:
            extra = f"\n...and {len(events) - 5} more events today."
        return "Today's schedule:\n" + "\n".join(lines) + extra
    except Exception as e:
        return f"Error getting today's schedule: {e}"

def _handle_personal_upcoming_events():
    """Handle getting upcoming events"""
    try:
        ok, message = _ensure_personal_access("calendar")
        if not ok:
            return message
        events = personal_calendar.get_upcoming_events(CURRENT_USER_ID, 7)
        if not events:
            return "You have no upcoming events."
        summaries = []
        for idx, event in enumerate(events[:5], start=1):
            summaries.append(f"{idx}. {event.get('title', 'Untitled')} on {_format_datetime_for_speech(event.get('start_time'))}")
        extra = ""
        if len(events) > 5:
            extra = f"\n...and {len(events) - 5} more events coming up."
        return "Here are your upcoming events:\n" + "\n".join(summaries) + extra
    except Exception as e:
        return f"Error getting upcoming events: {e}"

def _handle_integration_calendar_events():
    """Handle querying Google Calendar events from integrations"""
    try:
        # Get user_id (if backend is running with user_id, user IS logged in)
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your calendar."
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Calendar integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your calendar. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        calendar_conn = next((c for c in connections if c.get("type") == "google_calendar" and c.get("status") == "connected"), None)
        
        if not calendar_conn:
            return "Google Calendar is not connected. Please connect it in the Integrations page."
        
        connection_id = calendar_conn.get("id")
        
        # Get synced calendar events
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "events"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your calendar events. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your calendar events: {result.get('error', 'Unknown error')}"
        
        events = result.get("data", [])
        
        if not events:
            return "You have no calendar events synced. The system auto-syncs every 5 minutes."
        
        # Format upcoming events (next 7 days)
        from datetime import datetime, timedelta
        now = datetime.now()
        week_later = now + timedelta(days=7)
        
        upcoming = []
        for event in events[:10]:  # Limit to 10 events
            start_str = event.get("start", "")
            if start_str:
                try:
                    if 'T' in start_str:
                        event_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00').replace('+00:00', ''))
                    else:
                        event_dt = datetime.fromisoformat(start_str)
                    
                    if now <= event_dt <= week_later:
                        title = event.get("title", "Untitled Event")
                        time_str = event_dt.strftime("%I:%M %p on %B %d")
                        location = event.get("location", "")
                        description = event.get("description", "")
                        
                        event_str = f"{title} at {time_str}"
                        if location:
                            event_str += f" at {location}"
                        if description:
                            # Truncate long descriptions
                            desc_preview = description[:50] + "..." if len(description) > 50 else description
                            event_str += f" - {desc_preview}"
                        
                        upcoming.append(event_str)
                except:
                    pass
        
        if upcoming:
            return f"You have {len(upcoming)} upcoming events:\n" + "\n".join(upcoming[:5])
        else:
            return "You have no upcoming events in the next 7 days."
    
    except Exception as e:
        logger.error(f"Error getting calendar events: {e}")
        return f"I couldn't check your calendar: {e}"

def _handle_integration_upcoming_meetings():
    """Handle querying upcoming meetings from Google Calendar"""
    try:
        result = _handle_integration_calendar_events()
        # Filter for meetings specifically
        if "meeting" in result.lower() or "event" in result.lower():
            return result.replace("events", "meetings")
        return result
    except Exception as e:
        return f"I couldn't check your meetings: {e}"

def _handle_integration_next_meeting():
    """Get the next upcoming meeting"""
    try:
        # Get user_id (if backend is running with user_id, user IS logged in)
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your calendar."
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Calendar integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your calendar. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        calendar_conn = next((c for c in connections if c.get("type") == "google_calendar" and c.get("status") == "connected"), None)
        
        if not calendar_conn:
            return "Google Calendar is not connected. Please connect it in the Integrations page."
        
        connection_id = calendar_conn.get("id")
        
        # Get synced calendar events
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "events"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your calendar events. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your calendar events: {result.get('error', 'Unknown error')}"
        
        events = result.get("data", [])
        
        if not events:
            return "You have no calendar events synced. The system auto-syncs every 5 minutes."
        
        # Find next upcoming meeting
        from datetime import datetime
        now = datetime.now()
        next_meeting = None
        next_time = None
        
        for event in events:
            start_str = event.get("start", "")
            if start_str:
                try:
                    if 'T' in start_str:
                        event_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00').replace('+00:00', ''))
                    else:
                        event_dt = datetime.fromisoformat(start_str)
                    
                    if event_dt > now:
                        if next_time is None or event_dt < next_time:
                            next_time = event_dt
                            next_meeting = event
                except:
                    pass
        
        if not next_meeting:
            return "You have no upcoming meetings."
        
        title = next_meeting.get("title", "Untitled Meeting")
        location = next_meeting.get("location", "")
        description = next_meeting.get("description", "")
        time_str = next_time.strftime("%I:%M %p on %B %d, %Y")
        
        response_text = f"Your next meeting is '{title}' at {time_str}"
        if location:
            response_text += f" at {location}"
        if description:
            response_text += f". {description[:100]}"
        
        return response_text
    
    except Exception as e:
        logger.error(f"Error getting next meeting: {e}")
        return f"I couldn't check your next meeting: {e}"

def _handle_integration_meeting_details(text: str):
    """Get details about a specific meeting"""
    try:
        # Get user_id (if backend is running with user_id, user IS logged in)
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your calendar."
        
        # Extract meeting name from text
        meeting_name = text.lower()
        for phrase in ["meeting details", "tell me about my meeting", "details about"]:
            meeting_name = meeting_name.replace(phrase, "").strip()
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Calendar integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your calendar. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        calendar_conn = next((c for c in connections if c.get("type") == "google_calendar" and c.get("status") == "connected"), None)
        
        if not calendar_conn:
            return "Google Calendar is not connected. Please connect it in the Integrations page."
        
        connection_id = calendar_conn.get("id")
        
        # Get synced calendar events
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "events"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your calendar events. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your calendar events: {result.get('error', 'Unknown error')}"
        
        events = result.get("data", [])
        
        # Find matching meeting
        matching_event = None
        for event in events:
            title = event.get("title", "").lower()
            if meeting_name in title or title in meeting_name:
                matching_event = event
                break
        
        if not matching_event:
            return f"I couldn't find a meeting matching '{meeting_name}'. Try asking about your next meeting."
        
        title = matching_event.get("title", "Untitled Meeting")
        start_str = matching_event.get("start", "")
        end_str = matching_event.get("end", "")
        location = matching_event.get("location", "")
        description = matching_event.get("description", "")
        
        response_text = f"Meeting: {title}"
        
        if start_str:
            try:
                from datetime import datetime
                if 'T' in start_str:
                    start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00').replace('+00:00', ''))
                else:
                    start_dt = datetime.fromisoformat(start_str)
                response_text += f". Starts at {start_dt.strftime('%I:%M %p on %B %d, %Y')}"
            except:
                pass
        
        if location:
            response_text += f". Location: {location}"
        if description:
            response_text += f". Description: {description[:200]}"
        
        return response_text
    
    except Exception as e:
        logger.error(f"Error getting meeting details: {e}")
        return f"I couldn't get the meeting details: {e}"

def _handle_integration_next_event():
    """Get the next upcoming event"""
    try:
        # Reuse next meeting logic but call it "event"
        result = _handle_integration_next_meeting()
        return result.replace("meeting", "event")
    except Exception as e:
        return f"I couldn't check your next event: {e}"

def _handle_integration_today_events():
    """Get all events happening today"""
    try:
        # Get user_id (if backend is running with user_id, user IS logged in)
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your calendar."
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Calendar integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your calendar. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        calendar_conn = next((c for c in connections if c.get("type") == "google_calendar" and c.get("status") == "connected"), None)
        
        if not calendar_conn:
            return "Google Calendar is not connected. Please connect it in the Integrations page."
        
        connection_id = calendar_conn.get("id")
        
        # Get synced calendar events
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "events"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your calendar events. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your calendar events: {result.get('error', 'Unknown error')}"
        
        events = result.get("data", [])
        
        if not events:
            return "You have no calendar events synced. The system auto-syncs every 5 minutes."
        
        # Find events happening today
        from datetime import datetime, timedelta
        now = datetime.now()
        today_start = datetime(now.year, now.month, now.day)
        today_end = today_start + timedelta(days=1)
        
        today_events = []
        for event in events:
            start_str = event.get("start", "")
            if start_str:
                try:
                    if 'T' in start_str:
                        event_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00').replace('+00:00', ''))
                    else:
                        event_dt = datetime.fromisoformat(start_str)
                    
                    if today_start <= event_dt < today_end:
                        title = event.get("title", "Untitled Event")
                        time_str = event_dt.strftime("%I:%M %p")
                        today_events.append(f"{title} at {time_str}")
                except:
                    pass
        
        if today_events:
            return f"You have {len(today_events)} events today:\n" + "\n".join(today_events)
        else:
            return "You have no events scheduled for today."
    
    except Exception as e:
        logger.error(f"Error getting today's events: {e}")
        return f"I couldn't check your events for today: {e}"

def _handle_integration_emails():
    """Handle querying Gmail emails from integrations"""
    try:
        # Get user_id (if backend is running with user_id, user IS logged in)
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your emails."
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Gmail integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your emails. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        gmail_conn = next((c for c in connections if c.get("type") == "gmail" and c.get("status") == "connected"), None)
        
        if not gmail_conn:
            return "Gmail is not connected. Please connect it in the Integrations page."
        
        connection_id = gmail_conn.get("id")
        
        # Get synced emails
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "emails"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your emails. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your emails: {result.get('error', 'Unknown error')}"
        
        emails = result.get("data", [])
        
        if not emails:
            return "You have no emails synced. The system auto-syncs every 5 minutes."
        
        # Format recent emails
        recent = []
        for email in emails[:10]:  # Limit to 10 emails
            subject = email.get("subject", "No Subject")
            sender = email.get("from", "Unknown")
            snippet = email.get("snippet", "")[:50]
            recent.append(f"From {sender}: {subject}")
        
        return f"You have {len(emails)} emails synced. Recent ones:\n" + "\n".join(recent[:5])
    
    except Exception as e:
        logger.error(f"Error getting emails: {e}")
        return f"I couldn't check your emails: {e}"

def _handle_integration_important_emails():
    """Handle querying important emails from Gmail"""
    try:
        result = _handle_integration_emails()
        # Filter for important keywords
        important_keywords = ['urgent', 'important', 'deadline', 'meeting', 'action required']
        # This is a simplified version - in production, filter emails by keywords
        return result + "\n\nNote: Important emails are automatically detected and you'll receive notifications."
    except Exception as e:
        return f"I couldn't check your important emails: {e}"

def _handle_integration_read_recent_email():
    """Read the most recent email content"""
    try:
        print("[EMAIL] Starting to read recent email...")
        
        # Get user_id (if backend is running with user_id, user IS logged in)
        user_id = _get_user_id_for_integrations()
        print(f"[EMAIL] User ID: {user_id}")
        
        if not user_id:
            error_msg = "Please ensure you're logged in. The system needs your user ID to access your emails."
            print(f"[EMAIL] Error: {error_msg}")
            return error_msg
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        print(f"[EMAIL] API URL: {api_url}")
        
        # Get connected Gmail integration (increased timeout to 30 seconds)
        try:
            print("[EMAIL] Fetching integrations list...")
            response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=30)
            print(f"[EMAIL] Integrations list response status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"I couldn't check your emails. Status code: {response.status_code}"
                print(f"[EMAIL] Error: {error_msg}")
                return error_msg
        except httpx.TimeoutException as e:
            logger.error(f"Timeout while fetching integrations list: {e}")
            error_msg = "I couldn't check your emails - the request timed out. Please try again."
            print(f"[EMAIL] Error: {error_msg}")
            return error_msg
        except Exception as e:
            logger.error(f"Error fetching integrations: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            error_msg = f"I couldn't check your emails. Error: {str(e)}"
            print(f"[EMAIL] Error: {error_msg}")
            return error_msg
        
        data = response.json()
        connections = data.get("connections", [])
        print(f"[EMAIL] Found {len(connections)} connections")
        
        gmail_conn = next((c for c in connections if c.get("type") == "gmail" and c.get("status") == "connected"), None)
        
        if not gmail_conn:
            error_msg = "Gmail is not connected. Please connect it in the Integrations page."
            print(f"[EMAIL] Error: {error_msg}")
            return error_msg
        
        connection_id = gmail_conn.get("id")
        print(f"[EMAIL] Gmail connection ID: {connection_id}")
        
        # Get synced emails (increased timeout to 30 seconds)
        try:
            print("[EMAIL] Fetching email data...")
            response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "emails"}, timeout=30)
            print(f"[EMAIL] Email data response status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"I couldn't fetch your emails. Status code: {response.status_code}"
                print(f"[EMAIL] Error: {error_msg}")
                return error_msg
        except httpx.TimeoutException as e:
            logger.error(f"Timeout while fetching email data: {e}")
            error_msg = "I couldn't fetch your emails - the request timed out. Please try again later."
            print(f"[EMAIL] Error: {error_msg}")
            return error_msg
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            error_msg = f"I couldn't fetch your emails. Error: {str(e)}"
            print(f"[EMAIL] Error: {error_msg}")
            return error_msg
        
        result = response.json()
        print(f"[EMAIL] Email data result: success={result.get('success')}")
        
        if not result.get("success"):
            error_msg = f"I couldn't get your emails: {result.get('error', 'Unknown error')}"
            print(f"[EMAIL] Error: {error_msg}")
            return error_msg
        
        emails = result.get("data", [])
        print(f"[EMAIL] Found {len(emails)} emails")
        
        if not emails:
            error_msg = "You have no emails synced. The system auto-syncs every 5 minutes."
            print(f"[EMAIL] Error: {error_msg}")
            return error_msg
        
        # Get the most recent email
        recent_email = emails[0]
        subject = recent_email.get("subject", "No Subject")
        sender = recent_email.get("from", "Unknown")
        body = recent_email.get("body", recent_email.get("snippet", ""))
        
        print(f"[EMAIL] Recent email - From: {sender}, Subject: {subject}")
        
        if not body:
            error_msg = f"Email from {sender} with subject '{subject}' has no readable content."
            print(f"[EMAIL] Error: {error_msg}")
            return error_msg
        
        # Limit body length for TTS (max 500 words)
        words = body.split()
        if len(words) > 500:
            body = " ".join(words[:500]) + "... (email truncated)"
        
        response_text = f"Here's your most recent email. From {sender}. Subject: {subject}. {body}"
        
        print(f"[EMAIL] Success! Returning email content ({len(response_text)} characters)")
        # Don't call speak() here - it's called in the main loop
        return response_text
    
    except httpx.TimeoutException as e:
        logger.error(f"Timeout error reading recent email: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        error_msg = "I couldn't read your email - the request timed out. Please try again later."
        print(f"[EMAIL] Error: {error_msg}")
        return error_msg
    except Exception as e:
        logger.error(f"Error reading recent email: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        error_msg = f"I couldn't read your email: {str(e)}"
        print(f"[EMAIL] Error: {error_msg}")
        return error_msg

def _handle_integration_read_email_from(text: str):
    """Read email from a specific sender"""
    try:
        # Get user_id (if backend is running with user_id, user IS logged in)
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your emails."
        
        # Extract sender name from text
        sender_name = text.lower()
        # Remove command phrases
        for phrase in ["read email from", "read email by", "from"]:
            sender_name = sender_name.replace(phrase, "").strip()
        
        if not sender_name:
            return "Please specify who the email is from. For example: 'read email from John'"
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Gmail integration (increased timeout to 30 seconds)
        try:
            response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=30)
            if response.status_code != 200:
                return "I couldn't check your emails. Please try again."
        except httpx.TimeoutException:
            logger.error("Timeout while fetching integrations list")
            return "I couldn't check your emails - the request timed out. Please try again."
        except Exception as e:
            logger.error(f"Error fetching integrations: {e}")
            return "I couldn't check your emails. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        gmail_conn = next((c for c in connections if c.get("type") == "gmail" and c.get("status") == "connected"), None)
        
        if not gmail_conn:
            return "Gmail is not connected. Please connect it in the Integrations page."
        
        connection_id = gmail_conn.get("id")
        
        # Get synced emails (increased timeout to 30 seconds)
        try:
            response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "emails"}, timeout=30)
            if response.status_code != 200:
                return "I couldn't fetch your emails. Please try again."
        except httpx.TimeoutException:
            logger.error("Timeout while fetching email data")
            return "I couldn't fetch your emails - the request timed out. Please try again later."
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return "I couldn't fetch your emails. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your emails: {result.get('error', 'Unknown error')}"
        
        emails = result.get("data", [])
        
        # Find email from sender
        matching_email = None
        for email in emails:
            from_addr = email.get("from", "").lower()
            if sender_name.lower() in from_addr:
                matching_email = email
                break
        
        if not matching_email:
            return f"I couldn't find any emails from {sender_name}. Try checking your recent emails first."
        
        subject = matching_email.get("subject", "No Subject")
        sender = matching_email.get("from", "Unknown")
        body = matching_email.get("body", matching_email.get("snippet", ""))
        
        if not body:
            return f"Email from {sender} with subject '{subject}' has no readable content."
        
        # Limit body length for TTS
        words = body.split()
        if len(words) > 500:
            body = " ".join(words[:500]) + "... (email truncated)"
        
        response_text = f"Email from {sender}. Subject: {subject}. {body}"
        
        # Speak the email
        speak(response_text)
        return response_text
    
    except httpx.TimeoutException as e:
        logger.error(f"Timeout error reading email from sender: {e}")
        return "I couldn't read the email - the request timed out. Please try again later."
    except Exception as e:
        logger.error(f"Error reading email from sender: {e}")
        return f"I couldn't read the email: {str(e)}"

def _handle_integration_google_meet_meetings():
    """Handle querying Google Meet meetings from integrations"""
    try:
        # Get user_id (if backend is running with user_id, user IS logged in)
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your Google Meet meetings."
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Meet integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your Google Meet meetings. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        meet_conn = next((c for c in connections if c.get("type") == "google_meet" and c.get("status") == "connected"), None)
        
        if not meet_conn:
            return "Google Meet is not connected. Please connect it in the Integrations page."
        
        connection_id = meet_conn.get("id")
        
        # Get synced meetings
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "meetings"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your Google Meet meetings. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your Google Meet meetings: {result.get('error', 'Unknown error')}"
        
        meetings = result.get("data", [])
        
        if not meetings:
            return "You have no Google Meet meetings synced. The system auto-syncs every 5 minutes."
        
        # Format upcoming meetings
        from datetime import datetime, timedelta
        now = datetime.now()
        upcoming = []
        
        for meeting in meetings:
            start_str = meeting.get("start", "")
            if not start_str:
                continue
            
            try:
                if isinstance(start_str, str):
                    start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                else:
                    continue
                
                if start_dt >= now:
                    title = meeting.get("title", "No Title")
                    duration = meeting.get("duration", 60)
                    time_str = start_dt.strftime("%I:%M %p on %B %d")
                    upcoming.append(f"{title} at {time_str}, duration {duration} minutes")
            except Exception as e:
                logger.warning(f"Error parsing meeting time: {e}")
                continue
        
        if not upcoming:
            return "You have no upcoming Google Meet meetings."
        
        # Sort by time
        upcoming.sort()
        
        response_text = f"You have {len(upcoming)} upcoming Google Meet meetings:\n" + "\n".join(upcoming[:5])
        return response_text
    
    except Exception as e:
        logger.error(f"Error getting Google Meet meetings: {e}")
        return f"I couldn't check your Google Meet meetings: {e}"

def _handle_integration_next_google_meet_meeting():
    """Get the next upcoming Google Meet meeting"""
    try:
        # Get user_id (if backend is running with user_id, user IS logged in)
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your Google Meet meetings."
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Zoom integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your Google Meet meetings. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        meet_conn = next((c for c in connections if c.get("type") == "google_meet" and c.get("status") == "connected"), None)
        
        if not meet_conn:
            return "Google Meet is not connected. Please connect it in the Integrations page."
        
        connection_id = meet_conn.get("id")
        
        # Get synced meetings
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "meetings"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your Google Meet meetings. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your Google Meet meetings: {result.get('error', 'Unknown error')}"
        
        meetings = result.get("data", [])
        
        if not meetings:
            return "You have no Google Meet meetings synced."
        
        # Find next meeting
        from datetime import datetime
        now = datetime.now()
        next_meeting = None
        next_time = None
        
        for meeting in meetings:
            start_str = meeting.get("start", "")
            if not start_str:
                continue
            
            try:
                if isinstance(start_str, str):
                    start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                else:
                    continue
                
                if start_dt >= now:
                    if next_time is None or start_dt < next_time:
                        next_time = start_dt
                        next_meeting = meeting
            except Exception as e:
                logger.warning(f"Error parsing meeting time: {e}")
                continue
        
        if not next_meeting:
            return "You have no upcoming Google Meet meetings."
        
        title = next_meeting.get("title", "No Title")
        duration = next_meeting.get("duration", 60)
        description = next_meeting.get("description", "")
        join_url = next_meeting.get("join_url", "")
        time_str = next_time.strftime("%I:%M %p on %B %d")
        
        response_text = f"Your next Google Meet meeting is '{title}' at {time_str}, duration {duration} minutes."
        if description:
            response_text += f" Description: {description}"
        if join_url:
            response_text += f" I can help you join when it's time."
        
        return response_text
    
    except Exception as e:
        logger.error(f"Error getting next Google Meet meeting: {e}")
        return f"I couldn't check your next Google Meet meeting: {e}"

def _handle_integration_today_google_meet_meetings():
    """Get today's Google Meet meetings"""
    try:
        # Get user_id (if backend is running with user_id, user IS logged in)
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your Google Meet meetings."
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Zoom integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your Google Meet meetings. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        meet_conn = next((c for c in connections if c.get("type") == "google_meet" and c.get("status") == "connected"), None)
        
        if not meet_conn:
            return "Google Meet is not connected. Please connect it in the Integrations page."
        
        connection_id = meet_conn.get("id")
        
        # Get synced meetings
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "meetings"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your Google Meet meetings. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your Google Meet meetings: {result.get('error', 'Unknown error')}"
        
        meetings = result.get("data", [])
        
        if not meetings:
            return "You have no Google Meet meetings synced."
        
        # Filter today's meetings
        from datetime import datetime, timedelta
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        today_meetings = []
        for meeting in meetings:
            start_str = meeting.get("start", "")
            if not start_str:
                continue
            
            try:
                if isinstance(start_str, str):
                    start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                else:
                    continue
                
                if today_start <= start_dt < today_end:
                    title = meeting.get("title", "No Title")
                    duration = meeting.get("duration", 60)
                    time_str = start_dt.strftime("%I:%M %p")
                    today_meetings.append(f"{title} at {time_str}, duration {duration} minutes")
            except Exception as e:
                logger.warning(f"Error parsing meeting time: {e}")
                continue
        
        if not today_meetings:
            return "You have no Google Meet meetings scheduled for today."
        
        # Sort by time
        today_meetings.sort()
        
        response_text = f"You have {len(today_meetings)} Google Meet meetings today:\n" + "\n".join(today_meetings)
        return response_text
    
    except Exception as e:
        logger.error(f"Error getting today's Google Meet meetings: {e}")
        return f"I couldn't check your Google Meet meetings for today: {e}"

def _handle_integration_read_email_about(text: str):
    """Read email about a specific subject"""
    try:
        # Get user_id (if backend is running with user_id, user IS logged in)
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your emails."
        
        # Extract subject keyword from text
        subject_keyword = text.lower()
        # Remove command phrases
        for phrase in ["read email about", "read email with subject", "about", "subject"]:
            subject_keyword = subject_keyword.replace(phrase, "").strip()
        
        if not subject_keyword:
            return "Please specify what the email is about. For example: 'read email about meeting'"
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Gmail integration (increased timeout to 30 seconds)
        try:
            response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=30)
            if response.status_code != 200:
                return "I couldn't check your emails. Please try again."
        except httpx.TimeoutException:
            logger.error("Timeout while fetching integrations list")
            return "I couldn't check your emails - the request timed out. Please try again."
        except Exception as e:
            logger.error(f"Error fetching integrations: {e}")
            return "I couldn't check your emails. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        gmail_conn = next((c for c in connections if c.get("type") == "gmail" and c.get("status") == "connected"), None)
        
        if not gmail_conn:
            return "Gmail is not connected. Please connect it in the Integrations page."
        
        connection_id = gmail_conn.get("id")
        
        # Get synced emails (increased timeout to 30 seconds)
        try:
            response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "emails"}, timeout=30)
            if response.status_code != 200:
                return "I couldn't fetch your emails. Please try again."
        except httpx.TimeoutException:
            logger.error("Timeout while fetching email data")
            return "I couldn't fetch your emails - the request timed out. Please try again later."
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return "I couldn't fetch your emails. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your emails: {result.get('error', 'Unknown error')}"
        
        emails = result.get("data", [])
        
        # Find email with matching subject
        matching_email = None
        for email in emails:
            subject = email.get("subject", "").lower()
            if subject_keyword in subject:
                matching_email = email
                break
        
        if not matching_email:
            return f"I couldn't find any emails about '{subject_keyword}'. Try checking your recent emails first."
        
        subject = matching_email.get("subject", "No Subject")
        sender = matching_email.get("from", "Unknown")
        body = matching_email.get("body", matching_email.get("snippet", ""))
        
        if not body:
            return f"Email with subject '{subject}' has no readable content."
        
        # Limit body length for TTS
        words = body.split()
        if len(words) > 500:
            body = " ".join(words[:500]) + "... (email truncated)"
        
        response_text = f"Email from {sender}. Subject: {subject}. {body}"
        
        # Speak the email
        speak(response_text)
        return response_text
    
    except httpx.TimeoutException as e:
        logger.error(f"Timeout error reading email about subject: {e}")
        return "I couldn't read the email - the request timed out. Please try again later."
    except Exception as e:
        logger.error(f"Error reading email about subject: {e}")
        return f"I couldn't read the email: {str(e)}"

# ========================================
# GOOGLE DRIVE INTEGRATION VOICE COMMANDS
# ========================================

def _handle_integration_google_drive_files():
    """Handle querying Google Drive files from integrations"""
    try:
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your Google Drive files."
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Drive integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your Google Drive files. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        drive_conn = next((c for c in connections if c.get("type") == "google_drive" and c.get("status") == "connected"), None)
        
        if not drive_conn:
            return "Google Drive is not connected. Please connect it in the Integrations page."
        
        connection_id = drive_conn.get("id")
        
        # Get synced files
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "files"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your Google Drive files. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your Google Drive files: {result.get('error', 'Unknown error')}"
        
        files = result.get("data", [])
        
        if not files:
            return "You have no Google Drive files synced. The system auto-syncs every 5 minutes."
        
        # Format files
        file_list = []
        for file in files[:10]:
            name = file.get("name", "Untitled File")
            modified = file.get("modified", "")
            file_list.append(f"{name}")
        
        return f"You have {len(files)} Google Drive files synced. Recent ones:\n" + "\n".join(file_list[:5])
    
    except Exception as e:
        logger.error(f"Error getting Google Drive files: {e}")
        return f"I couldn't check your Google Drive files: {e}"

def _handle_integration_drive_search(text: str):
    """Search Google Drive files"""
    try:
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to search your Google Drive files."
        
        # Extract search query
        search_query = text.lower()
        for phrase in ["search drive for", "find in drive", "drive search", "search"]:
            search_query = search_query.replace(phrase, "").strip()
        
        if not search_query:
            return "Please specify what to search for. For example: 'search drive for report'"
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Drive integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't search your Google Drive files. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        drive_conn = next((c for c in connections if c.get("type") == "google_drive" and c.get("status") == "connected"), None)
        
        if not drive_conn:
            return "Google Drive is not connected. Please connect it in the Integrations page."
        
        connection_id = drive_conn.get("id")
        
        # Get synced files
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "files"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your Google Drive files. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't search your Google Drive files: {result.get('error', 'Unknown error')}"
        
        files = result.get("data", [])
        
        # Filter files by search query
        matching_files = [f for f in files if search_query.lower() in f.get("name", "").lower()]
        
        if not matching_files:
            return f"I couldn't find any files matching '{search_query}' in your Google Drive."
        
        file_list = []
        for file in matching_files[:5]:
            name = file.get("name", "Untitled File")
            file_list.append(f"{name}")
        
        return f"Found {len(matching_files)} files matching '{search_query}':\n" + "\n".join(file_list)
    
    except Exception as e:
        logger.error(f"Error searching Google Drive files: {e}")
        return f"I couldn't search your Google Drive files: {e}"

def _handle_integration_recent_drive_files():
    """Get recent Google Drive files"""
    try:
        result = _handle_integration_google_drive_files()
        return result + "\n\nThese are your most recently modified files."
    except Exception as e:
        return f"I couldn't get your recent Google Drive files: {e}"

def _handle_integration_drive_file_details(text: str):
    """Get details about a specific Google Drive file"""
    try:
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your Google Drive files."
        
        # Extract file name
        file_name = text.lower()
        for phrase in ["drive file details", "drive file info", "details", "info"]:
            file_name = file_name.replace(phrase, "").strip()
        
        if not file_name:
            return "Please specify which file. For example: 'drive file details report'"
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Drive integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your Google Drive files. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        drive_conn = next((c for c in connections if c.get("type") == "google_drive" and c.get("status") == "connected"), None)
        
        if not drive_conn:
            return "Google Drive is not connected. Please connect it in the Integrations page."
        
        connection_id = drive_conn.get("id")
        
        # Get synced files
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "files"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your Google Drive files. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your Google Drive files: {result.get('error', 'Unknown error')}"
        
        files = result.get("data", [])
        
        # Find matching file
        matching_file = next((f for f in files if file_name.lower() in f.get("name", "").lower()), None)
        
        if not matching_file:
            return f"I couldn't find a file named '{file_name}' in your Google Drive."
        
        name = matching_file.get("name", "Untitled File")
        modified = matching_file.get("modified", "")
        link = matching_file.get("link", "")
        
        response_text = f"File: {name}"
        if modified:
            response_text += f"\nLast modified: {modified}"
        if link:
            response_text += f"\nLink: {link}"
        
        return response_text
    
    except Exception as e:
        logger.error(f"Error getting Google Drive file details: {e}")
        return f"I couldn't get the file details: {e}"

# ========================================
# GOOGLE DOCS INTEGRATION VOICE COMMANDS
# ========================================

def _handle_integration_google_docs():
    """Handle querying Google Docs from integrations"""
    try:
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your Google Docs."
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Docs integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your Google Docs. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        docs_conn = next((c for c in connections if c.get("type") == "google_docs" and c.get("status") == "connected"), None)
        
        if not docs_conn:
            return "Google Docs is not connected. Please connect it in the Integrations page."
        
        connection_id = docs_conn.get("id")
        
        # Get synced documents
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "documents"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your Google Docs. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your Google Docs: {result.get('error', 'Unknown error')}"
        
        docs = result.get("data", [])
        
        if not docs:
            return "You have no Google Docs synced. The system auto-syncs every 5 minutes."
        
        # Format documents
        doc_list = []
        for doc in docs[:10]:
            name = doc.get("name", "Untitled Document")
            doc_list.append(f"{name}")
        
        return f"You have {len(docs)} Google Docs synced. Recent ones:\n" + "\n".join(doc_list[:5])
    
    except Exception as e:
        logger.error(f"Error getting Google Docs: {e}")
        return f"I couldn't check your Google Docs: {e}"

def _handle_integration_recent_docs():
    """Get recent Google Docs"""
    try:
        result = _handle_integration_google_docs()
        return result + "\n\nThese are your most recently modified documents."
    except Exception as e:
        return f"I couldn't get your recent Google Docs: {e}"

def _handle_integration_open_doc(text: str):
    """Open a specific Google Doc"""
    try:
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your Google Docs."
        
        # Extract document name
        doc_name = text.lower()
        for phrase in ["open doc", "open document"]:
            doc_name = doc_name.replace(phrase, "").strip()
        
        if not doc_name:
            return "Please specify which document. For example: 'open doc report'"
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Docs integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your Google Docs. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        docs_conn = next((c for c in connections if c.get("type") == "google_docs" and c.get("status") == "connected"), None)
        
        if not docs_conn:
            return "Google Docs is not connected. Please connect it in the Integrations page."
        
        connection_id = docs_conn.get("id")
        
        # Get synced documents
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "documents"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your Google Docs. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your Google Docs: {result.get('error', 'Unknown error')}"
        
        docs = result.get("data", [])
        
        # Find matching document
        matching_doc = next((d for d in docs if doc_name.lower() in d.get("name", "").lower()), None)
        
        if not matching_doc:
            return f"I couldn't find a document named '{doc_name}' in your Google Docs."
        
        link = matching_doc.get("link", "")
        if link:
            import webbrowser
            webbrowser.open(link)
            return f"Opening '{matching_doc.get('name', 'Document')}' in your browser."
        else:
            return f"Found '{matching_doc.get('name', 'Document')}' but no link available."
    
    except Exception as e:
        logger.error(f"Error opening Google Doc: {e}")
        return f"I couldn't open the document: {e}"

def _handle_integration_doc_details(text: str):
    """Get details about a specific Google Doc"""
    try:
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your Google Docs."
        
        # Extract document name
        doc_name = text.lower()
        for phrase in ["doc details", "document details", "doc info", "details", "info"]:
            doc_name = doc_name.replace(phrase, "").strip()
        
        if not doc_name:
            return "Please specify which document. For example: 'doc details report'"
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Docs integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your Google Docs. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        docs_conn = next((c for c in connections if c.get("type") == "google_docs" and c.get("status") == "connected"), None)
        
        if not docs_conn:
            return "Google Docs is not connected. Please connect it in the Integrations page."
        
        connection_id = docs_conn.get("id")
        
        # Get synced documents
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "documents"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your Google Docs. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your Google Docs: {result.get('error', 'Unknown error')}"
        
        docs = result.get("data", [])
        
        # Find matching document
        matching_doc = next((d for d in docs if doc_name.lower() in d.get("name", "").lower()), None)
        
        if not matching_doc:
            return f"I couldn't find a document named '{doc_name}' in your Google Docs."
        
        name = matching_doc.get("name", "Untitled Document")
        modified = matching_doc.get("modified", "")
        link = matching_doc.get("link", "")
        
        response_text = f"Document: {name}"
        if modified:
            response_text += f"\nLast modified: {modified}"
        if link:
            response_text += f"\nLink: {link}"
        
        return response_text
    
    except Exception as e:
        logger.error(f"Error getting Google Doc details: {e}")
        return f"I couldn't get the document details: {e}"

# ========================================
# GOOGLE SHEETS INTEGRATION VOICE COMMANDS
# ========================================

def _handle_integration_google_sheets():
    """Handle querying Google Sheets from integrations"""
    try:
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your Google Sheets."
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Sheets integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your Google Sheets. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        sheets_conn = next((c for c in connections if c.get("type") == "google_sheets" and c.get("status") == "connected"), None)
        
        if not sheets_conn:
            return "Google Sheets is not connected. Please connect it in the Integrations page."
        
        connection_id = sheets_conn.get("id")
        
        # Get synced spreadsheets
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "spreadsheets"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your Google Sheets. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your Google Sheets: {result.get('error', 'Unknown error')}"
        
        sheets = result.get("data", [])
        
        if not sheets:
            return "You have no Google Sheets synced. The system auto-syncs every 5 minutes."
        
        # Format spreadsheets
        sheet_list = []
        for sheet in sheets[:10]:
            name = sheet.get("name", "Untitled Spreadsheet")
            sheet_list.append(f"{name}")
        
        return f"You have {len(sheets)} Google Sheets synced. Recent ones:\n" + "\n".join(sheet_list[:5])
    
    except Exception as e:
        logger.error(f"Error getting Google Sheets: {e}")
        return f"I couldn't check your Google Sheets: {e}"

def _handle_integration_recent_sheets():
    """Get recent Google Sheets"""
    try:
        result = _handle_integration_google_sheets()
        return result + "\n\nThese are your most recently modified spreadsheets."
    except Exception as e:
        return f"I couldn't get your recent Google Sheets: {e}"

def _handle_integration_open_sheet(text: str):
    """Open a specific Google Sheet"""
    try:
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your Google Sheets."
        
        # Extract spreadsheet name
        sheet_name = text.lower()
        for phrase in ["open sheet", "open spreadsheet"]:
            sheet_name = sheet_name.replace(phrase, "").strip()
        
        if not sheet_name:
            return "Please specify which spreadsheet. For example: 'open sheet budget'"
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Sheets integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your Google Sheets. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        sheets_conn = next((c for c in connections if c.get("type") == "google_sheets" and c.get("status") == "connected"), None)
        
        if not sheets_conn:
            return "Google Sheets is not connected. Please connect it in the Integrations page."
        
        connection_id = sheets_conn.get("id")
        
        # Get synced spreadsheets
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "spreadsheets"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your Google Sheets. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your Google Sheets: {result.get('error', 'Unknown error')}"
        
        sheets = result.get("data", [])
        
        # Find matching spreadsheet
        matching_sheet = next((s for s in sheets if sheet_name.lower() in s.get("name", "").lower()), None)
        
        if not matching_sheet:
            return f"I couldn't find a spreadsheet named '{sheet_name}' in your Google Sheets."
        
        link = matching_sheet.get("link", "")
        if link:
            import webbrowser
            webbrowser.open(link)
            return f"Opening '{matching_sheet.get('name', 'Spreadsheet')}' in your browser."
        else:
            return f"Found '{matching_sheet.get('name', 'Spreadsheet')}' but no link available."
    
    except Exception as e:
        logger.error(f"Error opening Google Sheet: {e}")
        return f"I couldn't open the spreadsheet: {e}"

def _handle_integration_sheet_details(text: str):
    """Get details about a specific Google Sheet"""
    try:
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your Google Sheets."
        
        # Extract spreadsheet name
        sheet_name = text.lower()
        for phrase in ["sheet details", "spreadsheet details", "sheet info", "details", "info"]:
            sheet_name = sheet_name.replace(phrase, "").strip()
        
        if not sheet_name:
            return "Please specify which spreadsheet. For example: 'sheet details budget'"
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Sheets integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your Google Sheets. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        sheets_conn = next((c for c in connections if c.get("type") == "google_sheets" and c.get("status") == "connected"), None)
        
        if not sheets_conn:
            return "Google Sheets is not connected. Please connect it in the Integrations page."
        
        connection_id = sheets_conn.get("id")
        
        # Get synced spreadsheets
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "spreadsheets"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your Google Sheets. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your Google Sheets: {result.get('error', 'Unknown error')}"
        
        sheets = result.get("data", [])
        
        # Find matching spreadsheet
        matching_sheet = next((s for s in sheets if sheet_name.lower() in s.get("name", "").lower()), None)
        
        if not matching_sheet:
            return f"I couldn't find a spreadsheet named '{sheet_name}' in your Google Sheets."
        
        name = matching_sheet.get("name", "Untitled Spreadsheet")
        modified = matching_sheet.get("modified", "")
        link = matching_sheet.get("link", "")
        
        response_text = f"Spreadsheet: {name}"
        if modified:
            response_text += f"\nLast modified: {modified}"
        if link:
            response_text += f"\nLink: {link}"
        
        return response_text
    
    except Exception as e:
        logger.error(f"Error getting Google Sheet details: {e}")
        return f"I couldn't get the spreadsheet details: {e}"

# ========================================
# GOOGLE SLIDES INTEGRATION VOICE COMMANDS
# ========================================

def _handle_integration_google_slides():
    """Handle querying Google Slides from integrations"""
    try:
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your Google Slides."
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Slides integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your Google Slides. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        slides_conn = next((c for c in connections if c.get("type") == "google_slides" and c.get("status") == "connected"), None)
        
        if not slides_conn:
            return "Google Slides is not connected. Please connect it in the Integrations page."
        
        connection_id = slides_conn.get("id")
        
        # Get synced presentations
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "presentations"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your Google Slides. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your Google Slides: {result.get('error', 'Unknown error')}"
        
        slides = result.get("data", [])
        
        if not slides:
            return "You have no Google Slides synced. The system auto-syncs every 5 minutes."
        
        # Format presentations
        slide_list = []
        for slide in slides[:10]:
            name = slide.get("name", "Untitled Presentation")
            slide_list.append(f"{name}")
        
        return f"You have {len(slides)} Google Slides synced. Recent ones:\n" + "\n".join(slide_list[:5])
    
    except Exception as e:
        logger.error(f"Error getting Google Slides: {e}")
        return f"I couldn't check your Google Slides: {e}"

def _handle_integration_recent_slides():
    """Get recent Google Slides"""
    try:
        result = _handle_integration_google_slides()
        return result + "\n\nThese are your most recently modified presentations."
    except Exception as e:
        return f"I couldn't get your recent Google Slides: {e}"

def _handle_integration_open_slide(text: str):
    """Open a specific Google Slide"""
    try:
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your Google Slides."
        
        # Extract presentation name
        slide_name = text.lower()
        for phrase in ["open slide", "open presentation"]:
            slide_name = slide_name.replace(phrase, "").strip()
        
        if not slide_name:
            return "Please specify which presentation. For example: 'open slide meeting'"
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Slides integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your Google Slides. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        slides_conn = next((c for c in connections if c.get("type") == "google_slides" and c.get("status") == "connected"), None)
        
        if not slides_conn:
            return "Google Slides is not connected. Please connect it in the Integrations page."
        
        connection_id = slides_conn.get("id")
        
        # Get synced presentations
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "presentations"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your Google Slides. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your Google Slides: {result.get('error', 'Unknown error')}"
        
        slides = result.get("data", [])
        
        # Find matching presentation
        matching_slide = next((s for s in slides if slide_name.lower() in s.get("name", "").lower()), None)
        
        if not matching_slide:
            return f"I couldn't find a presentation named '{slide_name}' in your Google Slides."
        
        link = matching_slide.get("link", "")
        if link:
            import webbrowser
            webbrowser.open(link)
            return f"Opening '{matching_slide.get('name', 'Presentation')}' in your browser."
        else:
            return f"Found '{matching_slide.get('name', 'Presentation')}' but no link available."
    
    except Exception as e:
        logger.error(f"Error opening Google Slide: {e}")
        return f"I couldn't open the presentation: {e}"

def _handle_integration_slide_details(text: str):
    """Get details about a specific Google Slide"""
    try:
        user_id = _get_user_id_for_integrations()
        if not user_id:
            return "Please ensure you're logged in. The system needs your user ID to access your Google Slides."
        
        # Extract presentation name
        slide_name = text.lower()
        for phrase in ["presentation details", "slide details", "presentation info", "details", "info"]:
            slide_name = slide_name.replace(phrase, "").strip()
        
        if not slide_name:
            return "Please specify which presentation. For example: 'presentation details meeting'"
        
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        
        # Get connected Google Slides integration
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your Google Slides. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        slides_conn = next((c for c in connections if c.get("type") == "google_slides" and c.get("status") == "connected"), None)
        
        if not slides_conn:
            return "Google Slides is not connected. Please connect it in the Integrations page."
        
        connection_id = slides_conn.get("id")
        
        # Get synced presentations
        response = httpx.get(f"{api_url}/integrations/{connection_id}/data", params={"user_id": user_id, "data_type": "presentations"}, timeout=10)
        if response.status_code != 200:
            return "I couldn't fetch your Google Slides. Please try again."
        
        result = response.json()
        if not result.get("success"):
            return f"I couldn't get your Google Slides: {result.get('error', 'Unknown error')}"
        
        slides = result.get("data", [])
        
        # Find matching presentation
        matching_slide = next((s for s in slides if slide_name.lower() in s.get("name", "").lower()), None)
        
        if not matching_slide:
            return f"I couldn't find a presentation named '{slide_name}' in your Google Slides."
        
        name = matching_slide.get("name", "Untitled Presentation")
        modified = matching_slide.get("modified", "")
        link = matching_slide.get("link", "")
        
        response_text = f"Presentation: {name}"
        if modified:
            response_text += f"\nLast modified: {modified}"
        if link:
            response_text += f"\nLink: {link}"
        
        return response_text
    
    except Exception as e:
        logger.error(f"Error getting Google Slide details: {e}")
        return f"I couldn't get the presentation details: {e}"

def _handle_integration_status():
    """Handle checking integration sync status"""
    try:
        import httpx
        api_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        user_id = CURRENT_USER_ID
        
        response = httpx.get(f"{api_url}/integrations/list", params={"user_id": user_id}, timeout=10)
        if response.status_code != 200:
            return "I couldn't check your integrations. Please try again."
        
        data = response.json()
        connections = data.get("connections", [])
        
        if not connections:
            return "You have no integrations connected."
        
        statuses = []
        for conn in connections:
            name = conn.get("name", "Unknown")
            status = conn.get("status", "unknown")
            last_sync = conn.get("last_sync_at", "")
            
            if status == "connected":
                sync_info = f"last synced {last_sync}" if last_sync else "syncing..."
                statuses.append(f"{name}: Connected, {sync_info}")
            else:
                statuses.append(f"{name}: {status}")
        
        return "Here's your integration status:\n" + "\n".join(statuses)
    
    except Exception as e:
        logger.error(f"Error checking integration status: {e}")
        return f"I couldn't check your integration status: {e}"

def _handle_personal_create_note(text, content_override: Optional[str] = None):
    """Handle creating a personal note"""
    try:
        ok, message = _ensure_personal_access("notes")
        if not ok:
            return message
        
        if content_override is not None:
            note_content = content_override.strip() or text.strip()
            title_hint = text.strip()
        else:
            note_content = text.replace('create note', '').replace('add note', '').replace('take note', '').strip()
            title_hint = note_content
        
        if not note_content:
            return "Please specify the note content."
        
        title = _build_note_title(title_hint or note_content)
        result = personal_notes.create_note(
            CURRENT_USER_ID,
            title,
            content=note_content,
            category="general"
        )
        if result:
            return f"Created note: {title}"
        else:
            return "I couldn't create the note. Please try again."
    except Exception as e:
        return f"Error creating note: {e}"

def _handle_personal_list_notes():
    """Handle listing personal notes"""
    try:
        ok, message = _ensure_personal_access("notes")
        if not ok:
            return message
        notes = personal_notes.get_notes(CURRENT_USER_ID)
        if not notes:
            return "You have no notes at the moment."
        summaries = []
        for idx, note in enumerate(notes[:5], start=1):
            summaries.append(f"{idx}. {note.get('title', 'Untitled')} ({note.get('category', 'general')})")
        extra = ""
        if len(notes) > 5:
            extra = f"\n...and {len(notes) - 5} more notes in the app."
        return "Here are your notes:\n" + "\n".join(summaries) + extra
    except Exception as e:
        return f"Error listing notes: {e}"

def _handle_personal_search_notes(text):
    """Handle searching personal notes"""
    try:
        ok, message = _ensure_personal_access("notes")
        if not ok:
            return message
        query = text.replace('search notes', '').replace('find note', '').strip()
        if not query:
            return "Please specify what to search for."
        
        matching_notes = personal_notes.search_notes(CURRENT_USER_ID, query)
        if matching_notes:
            note_list = ", ".join([note["title"] for note in matching_notes[:3]])
            return f"Found {len(matching_notes)} note(s): {note_list}"
        else:
            return f"No notes found for '{query}'."
    except Exception as e:
        return f"Error searching notes: {e}"

def _handle_personal_edit_note(text, new_content: Optional[str] = None):
    """Handle editing personal notes"""
    try:
        ok, message = _ensure_personal_access("notes")
        if not ok:
            return message
        
        identifier, inline_content = _split_note_edit_command(text)
        note_query = identifier or text.replace('edit note', '').replace('update note', '').replace('modify note', '').strip()
        updated_content = (new_content or inline_content or "").strip()
        
        if not note_query:
            return "Please specify which note to edit."
        if not updated_content:
            return "Please provide the updated content for the note."
        
        notes = personal_notes.get_notes(CURRENT_USER_ID)
        if not notes:
            return "You don't have any notes yet."
        
        note = _match_item_by_title(notes, "title", note_query)
        if not note:
            return f"I couldn't find a note titled '{note_query}'."
        
        updated = personal_notes.update_note(note["id"], CURRENT_USER_ID, {"content": updated_content})
        if updated:
            return f"Updated note: {note.get('title', 'Untitled')}."
        return "I couldn't update that note. Please try again."
    except Exception as e:
        return f"Error editing note: {e}"

def _handle_personal_notes_summary():
    """Handle personal notes summary"""
    try:
        ok, message = _ensure_personal_access("notes")
        if not ok:
            return message
        summary = personal_notes.get_notes_summary(CURRENT_USER_ID)
        if not summary:
            return "No notes summary available yet."
        total = summary.get("total_notes", 0)
        pinned = summary.get("pinned_notes", 0)
        categories = summary.get("categories", {})
        top_category = max(categories, key=categories.get) if categories else "general"
        return (
            f"You have {total} notes with {pinned} pinned. "
            f"Most common category: {top_category}."
        )
    except Exception as e:
        return f"Error getting notes summary: {e}"

def _handle_personal_analytics_summary():
    """Handle personal analytics summary"""
    try:
        ok, message = _ensure_personal_access("analytics")
        if not ok:
            return message
        summary = personal_analytics.get_analytics_summary(CURRENT_USER_ID)
        if not summary:
            return "No analytics data available yet."
        total = summary.get("total_metrics", 0)
        unique = summary.get("unique_metrics", 0)
        categories = summary.get("categories", {})
        top_categories = ", ".join(list(categories.keys())[:3]) if categories else "general"
        return (
            f"In the last 30 days you've logged {total} metrics across {unique} types. "
            f"Top categories: {top_categories}."
        )
    except Exception as e:
        return f"Error getting analytics summary: {e}"

def _handle_personal_daily_stats():
    """Handle personal daily statistics"""
    try:
        ok, message = _ensure_personal_access("analytics")
        if not ok:
            return message
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        stats = personal_analytics.get_daily_stats(CURRENT_USER_ID, today)
        metrics = stats.get("metrics", {}) if stats else {}
        if not metrics:
            return "No data recorded for today yet."
        summary = ["Today's statistics:"]
        for metric, data in metrics.items():
            summary.append(f"{metric}: {data['total']} total across {data['count']} entries.")
        return " ".join(summary)
    except Exception as e:
        return f"Error getting daily stats: {e}"

def _handle_personal_weekly_stats():
    """Handle personal weekly statistics"""
    try:
        ok, message = _ensure_personal_access("analytics")
        if not ok:
            return message
        today = datetime.datetime.now()
        week_start = (today - datetime.timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        stats = personal_analytics.get_weekly_stats(CURRENT_USER_ID, week_start)
        daily = stats.get("daily_stats", {}) if stats else {}
        if not daily:
            return "No data recorded for this week yet."
        summary = ["This week's statistics:"]
        for date, metrics in list(daily.items())[:3]:
            metric_names = ", ".join(f"{name} ({data['total']})" for name, data in metrics.items())
            summary.append(f"{date}: {metric_names}")
        return " ".join(summary)
    except Exception as e:
        return f"Error getting weekly stats: {e}"

# ========================================
# BUSINESS MODE HANDLER FUNCTIONS
# ========================================

def _switch_to_business_mode():
    """Handle switching to business mode"""
    try:
        if not CURRENT_BUSINESS_ID:
            return "Please set your business context first. Use the app to select a business."
        set_business_context(CURRENT_BUSINESS_ID, CURRENT_USER_ROLE or "member")
        return f"Switched to business mode. Business: {CURRENT_BUSINESS_ID}, Role: {CURRENT_USER_ROLE}"
    except Exception as e:
        return f"Error switching to business mode: {e}"

def _switch_to_normal_mode():
    """Handle switching to normal mode"""
    try:
        set_normal_mode()
        return "Switched to normal mode. You can now use personal features."
    except Exception as e:
        return f"Error switching to normal mode: {e}"

def _handle_business_list_tasks():
    """Handle listing business tasks"""
    try:
        if CURRENT_MODE != "business":
            return "This command is only available in business mode. Please switch to business mode first."
        if not CURRENT_BUSINESS_ID:
            return "Please set your business context first."
        
        # Make API call to business backend
        import requests
        response = requests.get(f"{BUSINESS_BACKEND_URL}/business/tasks", 
                              headers={"X-Business-ID": CURRENT_BUSINESS_ID, 
                                      "X-User-ID": CURRENT_USER_ID,
                                      "X-User-Role": CURRENT_USER_ROLE})
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data"):
                tasks = data["data"]
                if tasks:
                    task_list = ", ".join([task["title"] for task in tasks[:5]])
                    return f"Here are your business tasks: {task_list}"
                else:
                    return "No business tasks found."
            else:
                return "Error fetching business tasks."
        else:
            return "Unable to connect to business backend."
    except Exception as e:
        return f"Error getting business tasks: {e}"

def _handle_business_create_task(text):
    """Handle creating a business task"""
    try:
        if CURRENT_MODE != "business":
            return "This command is only available in business mode. Please switch to business mode first."
        if not CURRENT_BUSINESS_ID:
            return "Please set your business context first."
        
        task_title = text.replace('create business task', '').replace('add business task', '').replace('new business task', '').strip()
        if not task_title:
            return "Please specify the task title."
        
        # Make API call to business backend
        import requests
        task_data = {
            "title": task_title,
            "description": "",
            "priority": "medium"
        }
        
        response = requests.post(f"{BUSINESS_BACKEND_URL}/business/tasks", 
                               json=task_data,
                               headers={"X-Business-ID": CURRENT_BUSINESS_ID, 
                                       "X-User-ID": CURRENT_USER_ID,
                                       "X-User-Role": CURRENT_USER_ROLE})
        
        if response.status_code == 200:
            return f"Business task '{task_title}' created successfully."
        else:
            return "Error creating business task."
    except Exception as e:
        return f"Error creating business task: {e}"

def _handle_business_list_projects():
    """Handle listing business projects"""
    try:
        if CURRENT_MODE != "business":
            return "This command is only available in business mode. Please switch to business mode first."
        if not CURRENT_BUSINESS_ID:
            return "Please set your business context first."
        
        # Make API call to business backend
        import requests
        response = requests.get(f"{BUSINESS_BACKEND_URL}/business/projects", 
                              headers={"X-Business-ID": CURRENT_BUSINESS_ID, 
                                      "X-User-ID": CURRENT_USER_ID,
                                      "X-User-Role": CURRENT_USER_ROLE})
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data"):
                projects = data["data"]
                if projects:
                    project_list = ", ".join([project["name"] for project in projects[:5]])
                    return f"Here are your business projects: {project_list}"
                else:
                    return "No business projects found."
            else:
                return "Error fetching business projects."
        else:
            return "Unable to connect to business backend."
    except Exception as e:
        return f"Error getting business projects: {e}"

def _handle_business_create_project(text):
    """Handle creating a business project"""
    try:
        if CURRENT_MODE != "business":
            return "This command is only available in business mode. Please switch to business mode first."
        if not CURRENT_BUSINESS_ID:
            return "Please set your business context first."
        
        project_name = text.replace('create business project', '').replace('add business project', '').replace('new business project', '').strip()
        if not project_name:
            return "Please specify the project name."
        
        # Make API call to business backend
        import requests
        project_data = {
            "name": project_name,
            "description": "",
            "priority": "medium"
        }
        
        response = requests.post(f"{BUSINESS_BACKEND_URL}/business/projects", 
                               json=project_data,
                               headers={"X-Business-ID": CURRENT_BUSINESS_ID, 
                                       "X-User-ID": CURRENT_USER_ID,
                                       "X-User-Role": CURRENT_USER_ROLE})
        
        if response.status_code == 200:
            return f"Business project '{project_name}' created successfully."
        else:
            return "Error creating business project."
    except Exception as e:
        return f"Error creating business project: {e}"

def _handle_business_list_team():
    """Handle listing business team members"""
    try:
        if CURRENT_MODE != "business":
            return "This command is only available in business mode. Please switch to business mode first."
        if not CURRENT_BUSINESS_ID:
            return "Please set your business context first."
        
        # Make API call to business backend
        import requests
        response = requests.get(f"{BUSINESS_BACKEND_URL}/business/team", 
                              headers={"X-Business-ID": CURRENT_BUSINESS_ID, 
                                      "X-User-ID": CURRENT_USER_ID,
                                      "X-User-Role": CURRENT_USER_ROLE})
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data"):
                members = data["data"]
                if members:
                    member_list = ", ".join([member["name"] for member in members[:5]])
                    return f"Here are your team members: {member_list}"
                else:
                    return "No team members found."
            else:
                return "Error fetching team members."
        else:
            return "Unable to connect to business backend."
    except Exception as e:
        return f"Error getting team members: {e}"

def _handle_business_add_team_member(text):
    """Handle adding a team member"""
    try:
        if CURRENT_MODE != "business":
            return "This command is only available in business mode. Please switch to business mode first."
        if not CURRENT_BUSINESS_ID:
            return "Please set your business context first."
        
        return "Please use the app to add team members with their email addresses."
    except Exception as e:
        return f"Error adding team member: {e}"

def _handle_business_analytics():
    """Handle business analytics"""
    try:
        if CURRENT_MODE != "business":
            return "This command is only available in business mode. Please switch to business mode first."
        if not CURRENT_BUSINESS_ID:
            return "Please set your business context first."
        
        # Make API call to business backend
        import requests
        response = requests.get(f"{BUSINESS_BACKEND_URL}/business/analytics", 
                              headers={"X-Business-ID": CURRENT_BUSINESS_ID, 
                                      "X-User-ID": CURRENT_USER_ID,
                                      "X-User-Role": CURRENT_USER_ROLE})
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data"):
                analytics = data["data"]
                overview = analytics.get("overview", {})
                return f"Business analytics: {overview.get('total_tasks', 0)} tasks, {overview.get('total_projects', 0)} projects, {overview.get('team_size', 0)} team members, {overview.get('completion_rate', 0):.1f}% completion rate."
            else:
                return "Error fetching business analytics."
        else:
            return "Unable to connect to business backend."
    except Exception as e:
        return f"Error getting business analytics: {e}"

def _handle_business_memory():
    """Handle business memory"""
    try:
        if CURRENT_MODE != "business":
            return "This command is only available in business mode. Please switch to business mode first."
        if not CURRENT_BUSINESS_ID:
            return "Please set your business context first."
        
        # Make API call to business backend
        import requests
        response = requests.get(f"{BUSINESS_BACKEND_URL}/business/memory", 
                              headers={"X-Business-ID": CURRENT_BUSINESS_ID, 
                                      "X-User-ID": CURRENT_USER_ID,
                                      "X-User-Role": CURRENT_USER_ROLE})
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data"):
                entries = data["data"]
                if entries:
                    entry_list = ", ".join([entry["title"] for entry in entries[:5]])
                    return f"Here are recent team memory entries: {entry_list}"
                else:
                    return "No team memory entries found."
            else:
                return "Error fetching team memory."
        else:
            return "Unable to connect to business backend."
    except Exception as e:
        return f"Error getting team memory: {e}"

def _handle_business_create_memory(text):
    """Handle creating a memory entry"""
    try:
        if CURRENT_MODE != "business":
            return "This command is only available in business mode. Please switch to business mode first."
        if not CURRENT_BUSINESS_ID:
            return "Please set your business context first."
        
        return "Please use the app to create detailed memory entries."
    except Exception as e:
        return f"Error creating memory entry: {e}"

def _handle_business_role_info():
    """Handle business role information"""
    try:
        if CURRENT_MODE != "business":
            return "This command is only available in business mode. Please switch to business mode first."
        if not CURRENT_BUSINESS_ID:
            return "Please set your business context first."
        
        return f"Your current role in business {CURRENT_BUSINESS_ID} is: {CURRENT_USER_ROLE}"
    except Exception as e:
        return f"Error getting role information: {e}"

def _handle_business_status():
    """Handle business status"""
    try:
        if CURRENT_MODE != "business":
            return "This command is only available in business mode. Please switch to business mode first."
        if not CURRENT_BUSINESS_ID:
            return "Please set your business context first."
        
        return f"Business mode active. Business: {CURRENT_BUSINESS_ID}, Role: {CURRENT_USER_ROLE}, User: {CURRENT_USER_ID}"
    except Exception as e:
        return f"Error getting business status: {e}"

# File Manager Handlers
def _handle_open_file(text):
    """Handle open file commands"""
    try:
        filename = _extract_filename(text)
        if not filename:
            return "Please specify which file to open. Example: 'open document.pdf'"
        
        # First try to find the file
        file_path = FileManager.find_file(filename)
        if file_path:
            return FileManager.open_file(file_path)
        else:
            # Try searching in current directory
            current_files = FileManager.list_dir()
            if filename.lower() in current_files.lower():
                return FileManager.open_file(os.path.join(FileManager.current_dir, filename))
            else:
                return f"Could not find file: {filename}. Try saying 'search file {filename}' to locate it."
    except Exception as e:
        return f"Error opening file: {e}"

def _handle_search_file(text):
    """Handle search file commands"""
    try:
        filename = _extract_filename(text)
        if not filename:
            return "Please specify which file to search for. Example: 'search file report.pdf'"
        
        found_files = FileManager.search_files(filename, max_results=5)
        if found_files:
            file_list = [os.path.basename(f) for f in found_files[:5]]
            return f"Found {len(found_files)} file(s): {', '.join(file_list)}. Say 'open [filename]' to open one."
        else:
            return f"No files found matching '{filename}'. Try a different search term."
    except Exception as e:
        return f"Error searching for file: {e}"

def _handle_list_files(text):
    """Handle list files commands"""
    try:
        # Check if user specified a path
        text_lower = text.lower()
        if 'in' in text_lower or 'from' in text_lower:
            # Extract path
            parts = text_lower.split('in' if 'in' in text_lower else 'from')
            if len(parts) > 1:
                path = parts[-1].strip()
                result = FileManager.list_dir(path)
                return f"Files in {path}:\n{result}"
        
        # Default: list current directory
        result = FileManager.list_dir()
        return f"Files in {FileManager.current_dir}:\n{result}"
    except Exception as e:
        return f"Error listing files: {e}"

def _handle_change_directory(text):
    """Handle change directory commands"""
    try:
        path = _extract_path(text)
        if not path:
            return "Please specify which directory to navigate to. Example: 'change directory to Documents'"
        
        return FileManager.change_directory(path)
    except Exception as e:
        return f"Error changing directory: {e}"

def _handle_create_folder(text):
    """Handle create folder commands"""
    try:
        # Extract folder name
        text_lower = text.lower()
        remove_words = ['create', 'make', 'new', 'folder', 'directory', 'dir']
        for word in remove_words:
            text_lower = text_lower.replace(word, '')
        folder_name = text_lower.strip()
        
        if not folder_name:
            folder_name = f"voice_folder_{int(time.time())}"
        
        return FileManager.create_folder(folder_name)
    except Exception as e:
        return f"Error creating folder: {e}"

def _handle_delete_file(text):
    """Handle delete file/folder commands"""
    try:
        filename = _extract_filename(text)
        if not filename:
            return "Please specify which file or folder to delete. Example: 'delete file report.pdf'"
        
        # Confirm it exists first
        file_path = FileManager.find_file(filename)
        if not file_path:
            # Try current directory
            current_path = os.path.join(FileManager.current_dir, filename)
            if os.path.exists(current_path):
                file_path = current_path
            else:
                return f"File not found: {filename}"
        
        return FileManager.delete_path(file_path)
    except Exception as e:
        return f"Error deleting file: {e}"

def _handle_open_folder(text):
    """Handle open folder commands"""
    try:
        # Extract path if specified
        text_lower = text.lower()
        if 'folder' in text_lower or 'directory' in text_lower:
            parts = text_lower.split('folder' if 'folder' in text_lower else 'directory')
            if len(parts) > 1:
                path = parts[-1].strip()
                if path:
                    return FileManager.open_folder(path)
        
        # Default: open current directory
        return FileManager.open_folder()
    except Exception as e:
        return f"Error opening folder: {e}"

# Prediction Commands Handlers
def _handle_predictions_analyze_file(text):
    """Handle file analysis commands via voice"""
    try:
        if not _has_valid_user():
            return "Please log in to analyze files with voice. Personal features require a valid account."
        
        # Extract file name from command
        # Example: "analyze my business report" -> "business report"
        file_query = text.lower()
        file_query = file_query.replace('analyze my', '').replace('analyze', '').replace('file', '').replace('document', '').strip()
        
        if not file_query:
            return "Please specify which file to analyze. Example: 'analyze my business report'"
        
        # Search for file using file watcher API (using normal backend for MVP)
        try:
            search_response = requests.post(
                f"{NORMAL_BACKEND_URL}/predictions/search-files",
                json={"query": file_query, "max_results": 5},
                headers={"X-User-ID": CURRENT_USER_ID},
                timeout=5
            )
            
            if search_response.status_code == 200:
                data = search_response.json()
                if data.get("success") and data.get("results"):
                    # Found files - use the first match
                    file_result = data["results"][0]
                    file_path = file_result["path"]
                    file_name = file_result["name"]
                    
                    # Analyze the file (using normal backend for MVP)
                    analyze_response = requests.post(
                        f"{NORMAL_BACKEND_URL}/predictions/analyze-local-file",
                        json={
                            "file_path": file_path,
                            "file_name": file_name,
                            "user_id": CURRENT_USER_ID
                        },
                        headers={"X-User-ID": CURRENT_USER_ID},
                        timeout=30
                    )
                    
                    if analyze_response.status_code == 200:
                        analyze_data = analyze_response.json()
                        if analyze_data.get("success"):
                            domain = analyze_data.get("detected_domain", "unknown")
                            file_id = analyze_data.get("file_id")
                            return f"Found and analyzed '{file_name}'. Detected domain: {domain}. File ID: {file_id}. Generating predictions now..."
                        else:
                            return f"Found file '{file_name}' but analysis failed. Please try again."
                    else:
                        return f"Found file '{file_name}' but couldn't analyze it. Error: {analyze_response.text}"
                else:
                    return f"Couldn't find any files matching '{file_query}'. Please try a different search term or add the folder to watched folders."
            else:
                return f"File search failed. Please try again or use the Predictions page in the app."
        except requests.exceptions.RequestException as e:
            return f"Connection error while searching for files. Please check your connection."
        
    except Exception as e:
        return f"File analysis error: {e}"

def _handle_predictions_predict(text):
    """Handle prediction generation commands"""
    try:
        if not _has_valid_user():
            return "Please log in to generate predictions."
        
        # Extract prediction type from command
        # Example: "predict expenses from spreadsheet" -> "expenses"
        pred_query = text.lower()
        pred_query = pred_query.replace('predict from', '').replace('predict', '').strip()
        
        if not pred_query:
            return "Please specify what to predict. Example: 'predict expenses from my spreadsheet'"
        
        return f"To generate predictions for '{pred_query}', please upload the file using the Predictions page in the app. Voice file prediction is coming soon."
    except Exception as e:
        return f"Prediction error: {e}"

def _handle_predictions_scan_file(text):
    """Handle file scanning commands"""
    try:
        if not _has_valid_user():
            return "Please log in to scan files with voice."
        
        # Extract file name from command
        file_query = text.lower()
        file_query = file_query.replace('scan file', '').replace('scan', '').replace('document', '').strip()
        
        if not file_query:
            return "Please specify which file to scan. Example: 'scan file report.pdf'"
        
        # Search for file using file watcher API (using normal backend for MVP)
        try:
            search_response = requests.post(
                f"{NORMAL_BACKEND_URL}/predictions/search-files",
                json={"query": file_query, "max_results": 5},
                headers={"X-User-ID": CURRENT_USER_ID},
                timeout=5
            )
            
            if search_response.status_code == 200:
                data = search_response.json()
                if data.get("success") and data.get("results"):
                    # Found files - return info about them
                    results = data["results"]
                    file_list = [f"{r['name']} ({r.get('extension', '')})" for r in results[:3]]
                    return f"Found {len(results)} file(s) matching '{file_query}': {', '.join(file_list)}. Say 'analyze [filename]' to analyze one."
                else:
                    return f"Couldn't find any files matching '{file_query}'. Make sure the folder is being watched."
            else:
                return f"File search failed. Please try again or use the Predictions page in the app."
        except requests.exceptions.RequestException as e:
            return f"Connection error while searching for files. Please check your connection."
    except Exception as e:
        return f"File scanning error: {e}"

# Code Generator Voice Handlers
def _handle_build_app(text):
    """Handle build app commands via voice"""
    try:
        if not _has_valid_user():
            return "Please log in before building apps."
        
        # Extract app description from command
        # Example: "build a todo app with dark theme" -> "a todo app with dark theme"
        app_description = text.lower()
        app_description = app_description.replace('build', '').replace('create', '').replace('make', '').replace('generate', '').replace('app', '').replace('website', '').strip()
        
        if not app_description:
            return "Please describe what app you want to build. Example: 'build a todo app with dark theme'"
        
        # Use the normal mode backend for code generator
        try:
            # Parse intent
            intent_response = requests.post(
                f"{NORMAL_BACKEND_URL}/code-generator/intent",
                json={"prompt": app_description, "user_id": CURRENT_USER_ID},
                headers={"X-User-ID": CURRENT_USER_ID},
                timeout=30
            )
            
            if intent_response.status_code == 200:
                intent_data = intent_response.json()
                if intent_data.get("success") and intent_data.get("intent"):
                    intent = intent_data["intent"]
                    project_name = intent.get("project_name", "My App")
                    return f"I've started building '{project_name}'. The build process has begun. Check the Developer page in the app to see progress and your generated code."
                else:
                    return f"I understood you want to build an app, but couldn't parse the requirements. Please try again or use the Developer page in the app."
            else:
                return f"Build request failed. Please try again or use the Developer page in the app."
        except requests.exceptions.RequestException as e:
            return f"Connection error while starting build. Please check your connection or use the Developer page in the app."
    except Exception as e:
        return f"Build app error: {e}"

def _handle_modify_project(text):
    """Handle modify project commands via voice"""
    try:
        if not _has_valid_user():
            return "Please log in before modifying projects."
        
        # Extract modification command
        modification = text.lower()
        modification = modification.replace('modify project', '').replace('update project', '').replace('change project', '').strip()
        
        if not modification:
            return "Please specify what to modify. Example: 'modify project add a search bar'"
        
        return f"To modify your project with '{modification}', please use the Developer page in the app. Voice modifications coming soon."
    except Exception as e:
        return f"Modify project error: {e}"

def _handle_deploy_project(text):
    """Handle deploy project commands via voice"""
    try:
        if not _has_valid_user():
            return "Please log in before deploying projects."
        
        return "To deploy your project, please use the Developer page in the app. Voice deployment coming soon."
    except Exception as e:
        return f"Deploy project error: {e}"

def _handle_list_projects():
    """Handle list projects commands via voice"""
    try:
        if not _has_valid_user():
            return "Please log in to view your generated projects."
        
        # Use the normal mode backend for code generator
        try:
            projects_response = requests.get(
                f"{NORMAL_BACKEND_URL}/code-generator/projects",
                headers={"X-User-ID": CURRENT_USER_ID},
                params={"user_id": CURRENT_USER_ID},
                timeout=10
            )
            
            if projects_response.status_code == 200:
                projects_data = projects_response.json()
                if projects_data.get("success") and projects_data.get("projects"):
                    projects = projects_data["projects"]
                    if projects:
                        project_list = [f"{p.get('name', 'Unnamed')} ({p.get('framework', 'unknown')})" for p in projects[:5]]
                        return f"You have {len(projects)} project(s). Recent projects: {', '.join(project_list)}. Check the Developer page for details."
                    else:
                        return "You don't have any projects yet. Say 'build a todo app' to create your first project!"
                else:
                    return "Couldn't retrieve your projects. Please check the Developer page in the app."
            else:
                return "Failed to retrieve projects. Please check the Developer page in the app."
        except requests.exceptions.RequestException as e:
            return f"Connection error while retrieving projects. Please check your connection or use the Developer page in the app."
    except Exception as e:
        return f"List projects error: {e}"

# Fuzzy matching for commands

def _is_command_restricted(text: str) -> bool:
    """
    Check if a command is restricted in work automation mode.
    Returns True if the command should be blocked.
    
    Work-related commands are ALWAYS allowed, even if they contain restricted keywords.
    """
    if not WORK_AUTOMATION_MODE:
        return False  # All commands allowed when not in work automation mode
    
    text_l = text.lower().strip()
    
    # ALLOWED: Work-related commands (these take priority over restrictions)
    work_related_keywords = [
        # Calendar & Meetings
        'calendar', 'meeting', 'meetings', 'event', 'events', 'schedule',
        'next meeting', 'upcoming meetings', 'meeting details',
        # Email (work-related)
        'email', 'emails', 'read email', 'read my email', 'check my emails',
        'important emails', 'unread emails',
        # Google Workspace
        'google drive', 'google docs', 'google sheets', 'google slides', 'google meet',
        'drive files', 'documents', 'spreadsheets', 'presentations',
        # Tasks & Follow-ups
        'task', 'tasks', 'action item', 'action items', 'follow-up', 'follow-ups',
        'create task', 'list tasks', 'complete task',
        # Notes & Documents (work-related)
        'note', 'notes', 'create note', 'meeting notes', 'meeting summary',
        'document', 'documents', 'create document', 'share document',
        # Reminders (work-related)
        'reminder', 'reminders', 'set reminder', 'add reminder',
    ]
    
    # If command contains work-related keywords, it's allowed
    for keyword in work_related_keywords:
        if keyword in text_l:
            return False  # Work-related command, allow it
    
    # Check if any restricted pattern matches (only for non-work commands)
    for pattern in RESTRICTED_COMMAND_PATTERNS:
        if pattern in text_l:
            return True
    
    return False

# ========================================
# STEP 2: VOICE → INTENT → PLANNER → EXECUTOR PIPELINE
# ========================================

def normalize_intent(text: str, source: str = "voice") -> dict:
    """Intent Normalizer - PURE translation layer. Outputs strict JSON schema."""
    text_l = text.lower().strip()
    intent = {
        "domain": "unknown",
        "intent": "UNKNOWN",
        "entities": {},
        "context": "IDLE",
        "requires_confirmation": False,
        "source": source,
        "raw_text": text
    }
    if ACTIVE_MEETING['is_active']:
        intent["context"] = "ACTIVE_MEETING"
        intent["entities"]["meeting_id"] = ACTIVE_MEETING['meeting_id']
        intent["entities"]["meeting_title"] = ACTIVE_MEETING['meeting_title']
    if any(kw in text_l for kw in ['meeting', 'meetings', 'meet']):
        intent["domain"] = "meeting"
        if any(kw in text_l for kw in ['pause recording', 'pause']):
            intent["intent"] = "PAUSE_RECORDING"
        elif any(kw in text_l for kw in ['resume recording', 'resume', 'start recording']):
            intent["intent"] = "RESUME_RECORDING"
        elif any(kw in text_l for kw in ['action item', 'action items', 'mark action']):
            intent["intent"] = "CREATE_ACTION_ITEM"
            if 'assign' in text_l or 'to' in text_l:
                words = text_l.split()
                for i, word in enumerate(words):
                    if word in ['assign', 'to', 'for'] and i + 1 < len(words):
                        intent["entities"]["assignee"] = words[i + 1]
                        break
        elif any(kw in text_l for kw in ['summarize', 'summary']):
            intent["intent"] = "SUMMARIZE_MEETING"
        elif any(kw in text_l for kw in ['next meeting', 'upcoming meeting']):
            intent["intent"] = "GET_NEXT_MEETING"
        else:
            intent["intent"] = "GET_MEETINGS"
    elif any(kw in text_l for kw in ['email', 'emails', 'mail']):
        intent["domain"] = "email"
        if any(kw in text_l for kw in ['read email', 'read my email', 'read recent']):
            intent["intent"] = "READ_EMAIL"
            intent["requires_confirmation"] = True
        elif any(kw in text_l for kw in ['read email from', 'read email by']):
            intent["intent"] = "READ_EMAIL_FROM"
            words = text_l.split()
            for i, word in enumerate(words):
                if word in ['from', 'by'] and i + 1 < len(words):
                    intent["entities"]["sender"] = ' '.join(words[i + 1:])
                    break
            intent["requires_confirmation"] = True
        elif any(kw in text_l for kw in ['read email about']):
            intent["intent"] = "READ_EMAIL_ABOUT"
            words = text_l.split()
            for i, word in enumerate(words):
                if word == 'about' and i + 1 < len(words):
                    intent["entities"]["subject"] = ' '.join(words[i + 1:])
                    break
            intent["requires_confirmation"] = True
        elif any(kw in text_l for kw in ['check emails', 'show emails', 'my emails', 'unread']):
            intent["intent"] = "LIST_EMAILS"
        else:
            intent["intent"] = "LIST_EMAILS"
    elif any(kw in text_l for kw in ['calendar', 'event', 'events', 'schedule']):
        intent["domain"] = "calendar"
        if any(kw in text_l for kw in ['next event', 'next meeting']):
            intent["intent"] = "GET_NEXT_EVENT"
        elif any(kw in text_l for kw in ['today', "today's"]):
            intent["intent"] = "GET_TODAY_EVENTS"
        else:
            intent["intent"] = "GET_CALENDAR_EVENTS"
    elif any(kw in text_l for kw in ['task', 'tasks']):
        intent["domain"] = "task"
        if any(kw in text_l for kw in ['create task', 'add task', 'new task']):
            intent["intent"] = "CREATE_TASK"
            words = text_l.split()
            task_start = None
            for i, word in enumerate(words):
                if word in ['task', 'tasks']:
                    task_start = i + 1
                    break
            if task_start:
                intent["entities"]["description"] = ' '.join(words[task_start:])
        elif any(kw in text_l for kw in ['complete task', 'finish task']):
            intent["intent"] = "COMPLETE_TASK"
            words = text_l.split()
            for i, word in enumerate(words):
                if word in ['task', 'tasks'] and i + 1 < len(words):
                    intent["entities"]["task_name"] = ' '.join(words[i + 1:])
                    break
        else:
            intent["intent"] = "LIST_TASKS"
    elif any(kw in text_l for kw in ['google drive', 'drive']):
        intent["domain"] = "drive"
        intent["intent"] = "LIST_DRIVE_FILES"
    elif any(kw in text_l for kw in ['google docs', 'docs']):
        intent["domain"] = "docs"
        intent["intent"] = "LIST_DOCS"
    return intent

def validate_context(intent: dict) -> Tuple[bool, str]:
    """Context Validator - Checks if intent is valid in current context."""
    if intent["context"] == "ACTIVE_MEETING" and not ACTIVE_MEETING['is_active']:
        meeting_required_intents = ["PAUSE_RECORDING", "RESUME_RECORDING", "CREATE_ACTION_ITEM", "SUMMARIZE_MEETING"]
        if intent["intent"] in meeting_required_intents:
            return False, "No active meeting. Please start a meeting first."
    if not _has_valid_user():
        login_required_intents = ["CREATE_TASK", "CREATE_EVENT", "CREATE_DOCUMENT", "READ_EMAIL"]
        if intent["intent"] in login_required_intents:
            return False, "Please log in to use this feature."
    return True, ""

def plan_action(intent: dict) -> dict:
    """Action Planner - Deterministic, rule-based planning. NO API calls."""
    plan = {
        "action": "UNKNOWN",
        "parameters": {},
        "requires_confirmation": False,
        "estimated_time": 5,
        "risk_level": "low"
    }
    intent_type = intent["intent"]
    if intent_type == "PAUSE_RECORDING":
        plan["action"] = "pause_meeting_recording"
    elif intent_type == "RESUME_RECORDING":
        plan["action"] = "resume_meeting_recording"
    elif intent_type == "CREATE_ACTION_ITEM":
        plan["action"] = "create_action_item"
        plan["parameters"] = intent["entities"]
    elif intent_type == "SUMMARIZE_MEETING":
        plan["action"] = "summarize_meeting"
        plan["estimated_time"] = 10
    elif intent_type == "GET_NEXT_MEETING":
        plan["action"] = "get_next_meeting"
    elif intent_type == "GET_MEETINGS":
        plan["action"] = "get_meetings"
    elif intent_type == "READ_EMAIL":
        plan["action"] = "read_email"
        plan["requires_confirmation"] = True
        plan["risk_level"] = "medium"
    elif intent_type == "READ_EMAIL_FROM":
        plan["action"] = "read_email_from"
        plan["parameters"] = {"sender": intent["entities"].get("sender")}
        plan["requires_confirmation"] = True
        plan["risk_level"] = "medium"
    elif intent_type == "READ_EMAIL_ABOUT":
        plan["action"] = "read_email_about"
        plan["parameters"] = {"subject": intent["entities"].get("subject")}
        plan["requires_confirmation"] = True
        plan["risk_level"] = "medium"
    elif intent_type == "LIST_EMAILS":
        plan["action"] = "list_emails"
    elif intent_type == "GET_NEXT_EVENT":
        plan["action"] = "get_next_event"
    elif intent_type == "GET_TODAY_EVENTS":
        plan["action"] = "get_today_events"
    elif intent_type == "GET_CALENDAR_EVENTS":
        plan["action"] = "get_calendar_events"
    elif intent_type == "CREATE_TASK":
        plan["action"] = "create_task"
        plan["parameters"] = {"description": intent["entities"].get("description", "")}
    elif intent_type == "COMPLETE_TASK":
        plan["action"] = "complete_task"
        plan["parameters"] = {"task_name": intent["entities"].get("task_name", "")}
    elif intent_type == "LIST_TASKS":
        plan["action"] = "list_tasks"
    elif intent_type == "LIST_DRIVE_FILES":
        plan["action"] = "list_drive_files"
    elif intent_type == "LIST_DOCS":
        plan["action"] = "list_docs"
    return plan

def require_confirmation(plan: dict, intent: dict) -> Tuple[bool, str]:
    """Confirmation Layer - For sensitive actions."""
    if not plan.get("requires_confirmation", False):
        return False, ""
    action = plan["action"]
    risk_level = plan.get("risk_level", "low")
    if risk_level == "high":
        return True, f"This action ({action}) requires confirmation. Should I proceed?"
    if risk_level == "medium":
        if action == "read_email":
            return True, "I can summarize your last 5 unread emails. Should I proceed?"
        elif action == "read_email_from":
            sender = plan["parameters"].get("sender", "unknown")
            return True, f"I can read emails from {sender}. Should I proceed?"
    return False, ""

def log_audit(intent: dict, plan: dict, result: str, success: bool):
    """Audit Logger - Logs every action for enterprise compliance."""
    audit_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "user_id": CURRENT_USER_ID,
        "intent": intent["intent"],
        "domain": intent["domain"],
        "action": plan["action"],
        "parameters": plan.get("parameters", {}),
        "success": success,
        "result_preview": str(result)[:200] if result else "None"
    }
    logger.info(f"[AUDIT] {audit_entry}")
    print(f"[AUDIT] {json.dumps(audit_entry, indent=2)}")

def execute_action(plan: dict, intent: dict) -> str:
    """Integration Executor - Executes the planned action."""
    action = plan["action"]
    parameters = plan.get("parameters", {})
    try:
        if action == "pause_meeting_recording":
            ACTIVE_MEETING['is_recording'] = False
            return "Meeting recording paused."
        elif action == "resume_meeting_recording":
            ACTIVE_MEETING['is_recording'] = True
            return "Meeting recording resumed."
        elif action == "create_action_item":
            assignee = parameters.get("assignee", "Unassigned")
            description = parameters.get("description", "Action item")
            action_item = create_action_item_from_meeting(description, assignee)
            if action_item:
                return f"Action item created: {description} (Assigned to: {assignee})"
            return "Could not create action item. No active meeting."
        elif action == "summarize_meeting":
            summary = generate_meeting_summary()
            return summary
        elif action == "get_next_meeting":
            return _handle_integration_next_meeting()
        elif action == "get_meetings":
            return _handle_integration_calendar_events()
        elif action == "read_email":
            return _handle_integration_read_recent_email()
        elif action == "read_email_from":
            sender = parameters.get("sender", "")
            return _handle_integration_read_email_from(f"read email from {sender}")
        elif action == "read_email_about":
            subject = parameters.get("subject", "")
            return _handle_integration_read_email_about(f"read email about {subject}")
        elif action == "list_emails":
            return _handle_integration_emails()
        elif action == "get_next_event":
            return _handle_integration_next_event()
        elif action == "get_today_events":
            return _handle_integration_today_events()
        elif action == "get_calendar_events":
            return _handle_integration_calendar_events()
        elif action == "create_task":
            description = parameters.get("description", "")
            return _handle_personal_create_task(f"create task {description}")
        elif action == "complete_task":
            task_name = parameters.get("task_name", "")
            return _handle_personal_complete_task(f"complete task {task_name}")
        elif action == "list_tasks":
            return _handle_personal_list_tasks()
        elif action == "list_drive_files":
            return _handle_integration_google_drive_files()
        elif action == "list_docs":
            return _handle_integration_google_docs()
        else:
            return f"Action '{action}' is not yet implemented."
    except Exception as e:
        logger.error(f"Error executing action {action}: {e}")
        return f"Error executing {action}: {str(e)}"

# ========================================
# STEP 3: MEETING WORKFLOW HARDENING
# ========================================

def detect_upcoming_meeting() -> dict:
    """
    Detect upcoming meeting from Google Calendar.
    Returns meeting info or None if no meeting found.
    """
    try:
        if not _has_valid_user():
            return None
        
        # Get next meeting
        result = _handle_integration_next_meeting()
        if "no upcoming meetings" in result.lower() or "error" in result.lower():
            return None
        
        # Parse meeting info (simplified - in production, parse structured data)
        return {
            "found": True,
            "message": result
        }
    except Exception as e:
        logger.error(f"Error detecting upcoming meeting: {e}")
        return None

def auto_join_google_meet(meeting_link: str) -> bool:
    """
    Auto-join Google Meet meeting.
    Returns True if successful.
    """
    try:
        import webbrowser
        webbrowser.open(meeting_link)
        ACTIVE_MEETING['meeting_link'] = meeting_link
        return True
    except Exception as e:
        logger.error(f"Error auto-joining meeting: {e}")
        return False

def start_meeting_recording(meeting_title: str, meeting_id: str = None) -> bool:
    """
    Start recording and transcription for active meeting.
    """
    try:
        ACTIVE_MEETING['is_active'] = True
        ACTIVE_MEETING['meeting_title'] = meeting_title
        ACTIVE_MEETING['meeting_id'] = meeting_id or f"meeting_{int(time.time())}"
        ACTIVE_MEETING['start_time'] = datetime.datetime.now().isoformat()
        ACTIVE_MEETING['is_recording'] = True
        ACTIVE_MEETING['transcription'] = []
        ACTIVE_MEETING['action_items'] = []
        ACTIVE_MEETING['decisions'] = []
        
        logger.info(f"Meeting recording started: {meeting_title}")
        return True
    except Exception as e:
        logger.error(f"Error starting meeting recording: {e}")
        return False

def add_transcription_entry(speaker: str, text: str):
    """Add entry to meeting transcription."""
    if ACTIVE_MEETING['is_active']:
        ACTIVE_MEETING['transcription'].append({
            "timestamp": datetime.datetime.now().isoformat(),
            "speaker": speaker,
            "text": text
        })

def create_action_item_from_meeting(description: str, assignee: str = None, deadline: str = None):
    """Create action item during meeting."""
    if ACTIVE_MEETING['is_active']:
        action_item = {
            "id": f"ai_{int(time.time())}",
            "description": description,
            "assignee": assignee or "Unassigned",
            "deadline": deadline,
            "created_at": datetime.datetime.now().isoformat(),
            "meeting_id": ACTIVE_MEETING['meeting_id']
        }
        ACTIVE_MEETING['action_items'].append(action_item)
        return action_item
    return None

def add_decision(decision_text: str):
    """Add decision made during meeting."""
    if ACTIVE_MEETING['is_active']:
        decision = {
            "id": f"dec_{int(time.time())}",
            "text": decision_text,
            "timestamp": datetime.datetime.now().isoformat(),
            "meeting_id": ACTIVE_MEETING['meeting_id']
        }
        ACTIVE_MEETING['decisions'].append(decision)
        return decision
    return None

def generate_meeting_summary() -> str:
    """
    Generate meeting summary from transcription, decisions, and action items.
    """
    if not ACTIVE_MEETING['is_active']:
        return "No active meeting to summarize."
    
    try:
        meeting_title = ACTIVE_MEETING['meeting_title']
        start_time = ACTIVE_MEETING['start_time']
        participants = ACTIVE_MEETING.get('participants', [])
        action_items = ACTIVE_MEETING['action_items']
        decisions = ACTIVE_MEETING['decisions']
        transcription = ACTIVE_MEETING['transcription']
        
        summary = f"""
MEETING SUMMARY
===============
Title: {meeting_title}
Start Time: {start_time}
Participants: {', '.join(participants) if participants else 'Not recorded'}

DECISIONS MADE:
{chr(10).join([f"- {d['text']}" for d in decisions]) if decisions else "None recorded"}

ACTION ITEMS:
{chr(10).join([f"- {ai['description']} (Assigned to: {ai['assignee']})" for ai in action_items]) if action_items else "None recorded"}

TRANSCRIPTION SUMMARY:
{len(transcription)} entries recorded.
"""
        return summary.strip()
    except Exception as e:
        logger.error(f"Error generating meeting summary: {e}")
        return f"Error generating summary: {str(e)}"

def create_meeting_notes_document(summary: str) -> str:
    """
    Create structured meeting notes document.
    Returns document ID or path.
    """
    try:
        # Format meeting notes
        notes_content = f"""
# Meeting Notes: {ACTIVE_MEETING['meeting_title']}

**Date:** {ACTIVE_MEETING['start_time']}
**Participants:** {', '.join(ACTIVE_MEETING.get('participants', []))}

## Summary
{summary}

## Action Items
{chr(10).join([f"### {ai['description']}" + chr(10) + f"- Assigned to: {ai['assignee']}" + chr(10) + f"- Deadline: {ai.get('deadline', 'Not set')}" for ai in ACTIVE_MEETING['action_items']]) if ACTIVE_MEETING['action_items'] else "None"}

## Decisions
{chr(10).join([f"- {d['text']}" for d in ACTIVE_MEETING['decisions']]) if ACTIVE_MEETING['decisions'] else "None"}
"""
        return notes_content
    except Exception as e:
        logger.error(f"Error creating meeting notes: {e}")
        return f"Error creating notes: {str(e)}"

def end_meeting() -> dict:
    """
    End active meeting, generate summary, create document, save to Drive, share.
    Returns meeting summary data.
    """
    if not ACTIVE_MEETING['is_active']:
        return {"success": False, "message": "No active meeting"}
    
    try:
        # Generate summary
        summary = generate_meeting_summary()
        
        # Create notes document
        notes_content = create_meeting_notes_document(summary)
        
        # Save meeting data
        meeting_data = {
            "meeting_id": ACTIVE_MEETING['meeting_id'],
            "title": ACTIVE_MEETING['meeting_title'],
            "start_time": ACTIVE_MEETING['start_time'],
            "end_time": datetime.datetime.now().isoformat(),
            "summary": summary,
            "notes": notes_content,
            "action_items": ACTIVE_MEETING['action_items'],
            "decisions": ACTIVE_MEETING['decisions'],
            "participants": ACTIVE_MEETING.get('participants', [])
        }
        
        # Reset meeting state
        ACTIVE_MEETING['is_active'] = False
        ACTIVE_MEETING['is_recording'] = False
        
        return {
            "success": True,
            "message": "Meeting ended. Summary generated.",
            "data": meeting_data
        }
    except Exception as e:
        logger.error(f"Error ending meeting: {e}")
        return {"success": False, "message": f"Error ending meeting: {str(e)}"}

# ---------------------------------------------------------------------------
# STEP 7B: Handler contracts — each command maps to one handler with fixed inputs.
# Handlers accept ONLY structured fields. Never raw user text. Validate required fields.
# ---------------------------------------------------------------------------

def _contract_create_task(title: Optional[str], details: Optional[str], time: Optional[str]) -> str:
    """create_task(title, details, time). Returns clarification if required fields missing."""
    if not (title or details):
        return "Please specify a title or description for the task."
    intent = "create task " + " ".join(p for p in [(title or ""), (details or ""), (time or "")] if p).strip()
    return _handle_personal_create_task(intent)


def _contract_complete_task(title: Optional[str]) -> str:
    """complete_task(title). Returns clarification if missing."""
    if not title:
        return "Please specify which task to complete."
    return _handle_personal_complete_task("complete task " + title)


def _contract_create_reminder(details: Optional[str], time: Optional[str]) -> str:
    """create_reminder(details, time). Returns clarification if missing."""
    if not (details or time):
        return "Please specify what to remind and when."
    intent = "add reminder " + (details or "") + " " + (time or "")
    return _handle_add_reminder(intent.strip())


def _contract_open_app(title: Optional[str], details: Optional[str]) -> str:
    """open_app(title/details). Never raw user text."""
    target = (title or details or "app").strip()
    return _open_any_app("open " + target)


def execute_structured_command(cmd: StructuredCommand) -> str:
    """
    Execute from StructuredCommand only. No raw user text.
    STEP 7C: If command not in Command enum → do NOT execute; respond + log.
    Handlers receive ONLY structured fields (title, details, time).
    """
    assert isinstance(cmd, StructuredCommand), "Only StructuredCommand may reach execution."

    # STEP 7C: Hard rejection — command must be in canonical enum
    if not cmd.is_allowed_command():
        logger.warning("[REJECTED] Unknown command not in enum: %s", cmd.command)
        print(f"[REJECTED] Command not in enum: {cmd.command}")
        return "I'm not sure how to do that yet. Can you rephrase?"

    if not cmd.is_complete_for_execution() and cmd.command in ("create_task", "create_reminder", "schedule_event"):
        return f"Please specify more details for {cmd.command.replace('_', ' ')}."

    try:
        c = cmd.command
        # Handler contracts: only structured fields (title, details, time)
        if c == Command.create_task.value:
            return _contract_create_task(cmd.title, cmd.details, cmd.time)
        if c == Command.list_tasks.value:
            return _handle_personal_list_tasks()
        if c == Command.complete_task.value:
            return _contract_complete_task(cmd.title)
        if c == Command.read_recent_email.value:
            return _handle_integration_read_recent_email()
        if c == Command.open_app.value:
            return _contract_open_app(cmd.title, cmd.details)
        if c == Command.create_reminder.value:
            return _contract_create_reminder(cmd.details or cmd.title, cmd.time)
        if c == Command.schedule_event.value:
            if not (cmd.title or cmd.details):
                return "Please specify the event title or details."
            intent = "schedule event " + " ".join(p for p in [(cmd.title or ""), (cmd.details or ""), (cmd.time or "")] if p).strip()
            return _handle_personal_schedule_event(intent)
        if c == Command.summarize_today.value:
            return _handle_personal_today_schedule()
        if c == Command.what_was_i_doing.value:
            return _handle_personal_today_schedule()
        if c == Command.send_message.value:
            query = (cmd.title or cmd.details or "").strip()
            if query:
                return ai_core.chat(query)
            return "What message would you like to send?"
        # V1: only 10 commands; should not reach (enum guard above)
        return "I'm not sure how to do that yet. Can you rephrase?"
    except Exception as e:
        logger.exception("execute_structured_command failed for %s", cmd.command)
        return f"Sorry, something went wrong: {str(e)}"


def _handle_weather_current(location: str) -> str:
    """Weather query from structured field only."""
    loc = (location or "Mumbai").strip()
    return weather.format_weather_report(weather.get_current_weather(loc))


def _pipeline_execute_callback(structured_list, device):
    """
    Pipeline step 8: execute only from StructuredCommand. No raw text.
    Returns list of { "result": str } for step 9.
    """
    results = []
    for cmd in structured_list:
        assert isinstance(cmd, StructuredCommand), "Only StructuredCommand may reach execution."
        try:
            out = execute_structured_command(cmd)
            results.append({"result": out if isinstance(out, str) else str(out or "")})
        except Exception as e:
            logger.exception("Pipeline execute callback failed for %s", getattr(cmd, "command", "?"))
            results.append({"result": f"Sorry, something went wrong: {str(e)}"})
    return results


def match_command(text):
    """
    Match voice command to handler function.
    NEW PIPELINE: For work-related commands, use Intent → Planner → Executor pipeline.
    FALLBACK: For non-work commands, use legacy pattern matching.
    """
    text_l = text.lower().strip()
    # STEP 1: Check if command is restricted in work automation mode
    if _is_command_restricted(text):
        rejection_message = "This feature is not available in work automation mode."
        print(f'[RESTRICTED] Command blocked: "{text}"')
        return (lambda _: rejection_message, text)

    # STEP 2: For work-related commands, use new pipeline
    work_keywords = ['meeting', 'email', 'calendar', 'task', 'document', 'drive', 'docs', 'sheets', 'slides']
    is_work_command = any(kw in text_l for kw in work_keywords)
    
    if is_work_command and WORK_AUTOMATION_MODE:
        # Use new pipeline: Intent → Context → Planner → Confirmation → Executor → Audit
        try:
            # 1. Normalize Intent
            intent = normalize_intent(text, source="voice")
            print(f'[PIPELINE] Intent normalized: {intent["intent"]} ({intent["domain"]})')
            
            # 2. Validate Context
            is_valid, error_msg = validate_context(intent)
            if not is_valid:
                return (lambda _: error_msg, text)
            
            # 3. Plan Action
            plan = plan_action(intent)
            print(f'[PIPELINE] Action planned: {plan["action"]} (risk: {plan["risk_level"]})')
            
            # 4. Check Confirmation
            needs_confirmation, confirmation_msg = require_confirmation(plan, intent)
            if needs_confirmation:
                # Return function that asks for confirmation
                return (lambda _: confirmation_msg, text)
            
            # 5. Execute Action
            def execute_with_audit(_):
                result = execute_action(plan, intent)
                success = not result.startswith("Error")
                log_audit(intent, plan, result, success)
                return result
            
            return (execute_with_audit, text)
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            return (lambda _: f"Error processing command: {str(e)}", text)
    
    # Check for Phase 2 features first (before matching commands)
    is_phase2, feature_name = check_phase2_feature(text)
    if is_phase2:
        return (None, get_phase2_response(feature_name))
    
    # PRIORITY: Check for integration commands first (emails, calendar, etc.)
    # These should be matched before AI interpretation to avoid false matches
    print(f'[MATCH] Checking command: "{text_l}"')
    
    integration_keywords = [
        'check my emails', 'show my emails', 'my emails', 'unread emails',
        'read my recent email', 'read latest email', 'read my email', 'read my emails',
        'read email from', 'read email by', 'read email about', 'read email with subject',
        'important emails', 'urgent emails',
        'what\'s on my calendar', 'show my calendar events', 'calendar events', 'my calendar',
        'upcoming meetings', 'meetings today', 'what meetings do i have',
        'next meeting', 'my next meeting', 'what\'s my next meeting',
        'meeting details', 'tell me about my meeting',
        'when is my next event', 'next event', 'what\'s my next event',
        'events today', 'what do i have today', 'today\'s events',
        'my google meet meetings', 'show my google meet meetings', 'google meet meetings', 'list google meet meetings',
        'next google meet meeting', 'my next google meet meeting', 'what\'s my next google meet meeting',
        'google meet meetings today', 'today\'s google meet meetings', 'what google meet meetings do i have today',
        'show my google drive files', 'list drive files', 'my drive files', 'google drive files',
        'search drive for', 'find in drive', 'drive search',
        'recent drive files', 'recent files in drive', 'latest drive files',
        'drive file details', 'drive file info',
        'show my google docs', 'list my documents', 'my google docs', 'my documents',
        'recent documents', 'recent docs', 'latest documents',
        'open doc', 'open document',
        'doc details', 'document details', 'doc info',
        'show my google sheets', 'list my spreadsheets', 'my google sheets', 'my spreadsheets',
        'recent spreadsheets', 'recent sheets', 'latest spreadsheets',
        'open sheet', 'open spreadsheet',
        'sheet details', 'spreadsheet details', 'sheet info',
        'show my google slides', 'list my presentations', 'my google slides', 'my presentations',
        'recent presentations', 'recent slides', 'latest presentations',
        'open slide', 'open presentation',
        'presentation details', 'slide details', 'presentation info',
        'integration status', 'sync status', 'are my integrations synced'
    ]
    
    # Quick check: if text contains integration keywords, try pattern matching first
    if any(keyword in text_l for keyword in integration_keywords):
        result = _match_command_internal(text)
        if result[0]:  # If pattern matched, use it
            return result
    
    # HYBRID: Try AI interpretation
    try:
        from features.ceaser.ai_command_interpreter import get_ai_interpreter
        ai_interpreter = get_ai_interpreter()
        
        if ai_interpreter and ai_interpreter.client:
            # Get conversation history for context
            conversation_history = []
            if openai_context.get('conversation_history'):
                for item in openai_context['conversation_history'][-5:]:
                    conversation_history.append({"role": "user", "content": item.get('query', '')})
                    conversation_history.append({"role": "assistant", "content": item.get('response', '')})
            
            # Try AI interpretation
            ai_result = ai_interpreter.interpret_command(text, conversation_history)
            
            if ai_result and ai_result.get('confidence', 0) > 0.7:  # High confidence threshold
                logger.info(f"✅ AI interpreted command: {ai_result.get('action')} (confidence: {ai_result.get('confidence')})")
                
                # Handle AI interpretation
                handler_name = ai_result.get('handler')
                parameters = ai_result.get('parameters', {})
                
                # For questions/chat, use the raw response if available
                if ai_result.get('is_question') and ai_result.get('raw_response'):
                    return (lambda _: ai_result['raw_response'], text)
                
                # Map to actual handler function
                handler_func = _get_handler_from_ai_result(handler_name, parameters, text)
                if handler_func:
                    return (handler_func, text)
                else:
                    logger.warning(f"⚠️ Could not resolve handler: {handler_name}, falling back to pattern matching")
            else:
                logger.info(f"⚠️ AI interpretation low confidence or failed, using pattern matching")
        else:
            logger.info("⚠️ AI interpreter not available, using pattern matching")
    except Exception as e:
        logger.warning(f"⚠️ AI interpretation error: {e}, falling back to pattern matching")
    
    # FALLBACK: Continue with normal pattern matching
    return _match_command_internal(text)

def _handle_add_reminder_with_params(parameters: dict, original_text: str):
    """Wrapper to handle reminders with AI-extracted parameters"""
    # Build text with parameters for the handler
    message = parameters.get('message', '')
    datetime_str = parameters.get('datetime', '')
    if message and datetime_str:
        # Format: "message: {message} datetime: {datetime}"
        text = f"message: {message} datetime: {datetime_str}"
    else:
        text = original_text
    return _handle_add_reminder(text)

def _get_handler_from_ai_result(handler_name: str, parameters: dict, original_text: str):
    """
    Maps AI interpretation result to actual handler function.
    Creates wrapper functions that extract parameters and call the right handler.
    """
    # Helper wrapper functions for common patterns
    def _handle_weather_wrapper(text):
        location = parameters.get('location', 'Mumbai')
        forecast = parameters.get('forecast', False)
        if forecast:
            return weather.format_weather_report(weather.get_forecast(location))
        else:
            return weather.format_weather_report(weather.get_current_weather(location))
    
    def _handle_news_wrapper(text):
        topic = parameters.get('topic')
        limit = parameters.get('limit', 5)
        if topic:
            return news.format_headlines_report(news.get_top_headlines(topic=topic, limit=limit))
        else:
            return news.format_headlines_report(news.get_top_headlines(limit=limit))
    
    def _handle_get_time_wrapper(text):
        return datetime.datetime.now().strftime('The time is %H:%M')
    
    def _handle_get_date_wrapper(text):
        return datetime.datetime.now().strftime('Today is %A, %d %B %Y')
    
    def _handle_get_quote_wrapper(text):
        return FunUtilities.get_quote()
    
    # Map handler names to functions
    handler_map = {
        "_handle_personal_create_task": lambda t: _handle_personal_create_task(parameters.get('title', t)),
        "_handle_personal_list_tasks": lambda t: _handle_personal_list_tasks(),
        "_handle_personal_complete_task": lambda t: _handle_personal_complete_task(parameters.get('task_title', t)),
        "_handle_personal_create_goal": lambda t: _handle_personal_create_goal(parameters.get('name', t)),
        "_handle_personal_list_goals": lambda t: _handle_personal_list_goals(),
        "_handle_personal_goal_progress": lambda t: _handle_personal_goal_progress(parameters.get('goal_name', t), parameters.get('progress', 0)),
        "_handle_personal_schedule_event": lambda t: _handle_personal_schedule_event(original_text),
        "_handle_personal_today_schedule": lambda t: _handle_personal_today_schedule(),
        "_handle_personal_create_note": lambda t: _handle_personal_create_note(parameters.get('title', original_text), parameters.get('content')),
        "_handle_personal_list_notes": lambda t: _handle_personal_list_notes(),
        "_handle_personal_search_notes": lambda t: _handle_personal_search_notes(parameters.get('query', t)),
        "_handle_personal_edit_note": lambda t: _handle_personal_edit_note(parameters.get('note_title', t), parameters.get('content')),
        "_handle_add_reminder": lambda t: _handle_add_reminder_with_params(parameters, original_text) if parameters else _handle_add_reminder(original_text),
        "_handle_list_reminders": lambda t: _handle_list_reminders(),
        "_open_any_app": lambda t: _open_any_app(parameters.get('app_name', t)),
        "_close_any_app": lambda t: _close_any_app(parameters.get('app_name', t)),
        "DeviceControl.lock_workstation": lambda t: DeviceControl.lock_workstation(),
        "DeviceControl.shutdown": lambda t: DeviceControl.shutdown(),
        "DeviceControl.restart": lambda t: DeviceControl.restart(),
        "DeviceControl.sleep": lambda t: DeviceControl.sleep(),
        "DeviceControl.take_screenshot": lambda t: DeviceControl.take_screenshot(),
        "DeviceControl.set_volume": lambda t: DeviceControl.set_volume(parameters.get('level', 50)),
        "DeviceControl.mute_volume": lambda t: DeviceControl.mute_volume(),
        "DeviceControl.unmute_volume": lambda t: DeviceControl.unmute_volume(),
        "_handle_weather_wrapper": _handle_weather_wrapper,
        "_handle_news_wrapper": _handle_news_wrapper,
        "_handle_get_time_wrapper": _handle_get_time_wrapper,
        "_handle_get_date_wrapper": _handle_get_date_wrapper,
        "_handle_youtube_play": lambda t: _handle_youtube_play(parameters.get('query', t)),
        "_handle_ai_chat": lambda t: _handle_ai_chat(parameters.get('question', t)),
        "_handle_remember": lambda t: _handle_remember(original_text),
        "_handle_recall": lambda t: _handle_recall(parameters.get('key', t)),
        "_handle_memory_search": lambda t: _handle_memory_search(parameters.get('query', t)),
        "_handle_google_search": lambda t: _handle_google_search(parameters.get('query', t)),
        "_handle_amazon_search": lambda t: _handle_amazon_search(parameters.get('query', t)),
        "_handle_amazon_deals": lambda t: _handle_amazon_deals(),
        "_handle_amazon_track": lambda t: _handle_amazon_track(parameters.get('product_url', t)),
        "_handle_language_lesson": lambda t: _handle_language_lesson(original_text),
        "_handle_language_practice": lambda t: _handle_language_practice(original_text),
        "_handle_web_automation": lambda t: _handle_web_automation(original_text),
        "_handle_web_form": lambda t: _handle_web_form(original_text),
        "_handle_vault_store": lambda t: _handle_vault_store(original_text),
        "_handle_vault_retrieve": lambda t: _handle_vault_retrieve(parameters.get('key', t)),
        "_handle_office_command": lambda t: _handle_office_command(original_text),
        "_handle_add_automation": lambda t: _handle_add_automation(original_text),
        "_handle_list_automations": lambda t: _handle_list_automations(),
        "_handle_multimodal_analysis": lambda t: _handle_multimodal_analysis(original_text),
        "_handle_predictions_analyze_file": lambda t: _handle_predictions_analyze_file(parameters.get('file_path', t)),
        "_handle_build_app": lambda t: _handle_build_app(original_text),
        "_handle_joke": lambda t: _handle_joke(),
        "_handle_get_quote_wrapper": _handle_get_quote_wrapper,
        "_handle_proactive_suggestions": lambda t: _handle_proactive_suggestions(),
        "_handle_list_files": lambda t: _handle_list_files(parameters.get('directory', '')),
        "_handle_open_file": lambda t: _handle_open_file(parameters.get('file_path', t)),
        "_handle_search_file": lambda t: _handle_search_file(parameters.get('file_name', t)),
        "_handle_create_folder": lambda t: _handle_create_folder(parameters.get('folder_name', t)),
        "_handle_delete_file": lambda t: _handle_delete_file(parameters.get('file_path', t)),
    }
    
    return handler_map.get(handler_name)

def _match_command_internal(text):
    text_l = text.lower().strip()
    print(f"[DEBUG] Recognized text: '{text_l}'")  # Log recognized text for debugging
    # --- Robust YouTube playback controls (substring/fuzzy matching) ---
    # Pause
    if 'pause' in text_l and 'video' in text_l or text_l in ["pause", "pause video", "pause youtube"]:
        return lambda _: _youtube_key('k'), text
    # Play (YouTube play/pause)
    if 'play' in text_l and 'video' in text_l and 'next' not in text_l and 'previous' not in text_l or text_l in ["play", "resume", "play video", "resume youtube"]:
        return lambda _: _youtube_key('k'), text
    # Next (YouTube next video)
    if ('next' in text_l and 'video' in text_l) or text_l in ["next", "next video", "youtube next", "youtube skip", "play next"]:
        return lambda _: _youtube_key(['shift', 'n']), text
    # Previous (YouTube previous video)
    if ('previous' in text_l and 'video' in text_l) or text_l in ["previous", "previous video", "youtube previous", "play previous"]:
        return lambda _: _youtube_key(['shift', 'p']), text
    # Forward
    if 'forward' in text_l and 'youtube' in text_l or text_l in ["forward", "forward youtube", "youtube forward"]:
        return lambda _: _youtube_key('l'), text
    # Backward
    if 'backward' in text_l and 'youtube' in text_l or text_l in ["backward", "backward youtube", "youtube backward"]:
        return lambda _: _youtube_key('j'), text
    # Full screen
    if 'full screen' in text_l and 'youtube' in text_l or text_l in ["full screen", "youtube full screen", "youtube fullscreen"]:
        return lambda _: _youtube_key('f'), text
    # Theater mode
    if 'theater' in text_l and 'youtube' in text_l or text_l in ["theater mode", "youtube theater mode", "youtube theater"]:
        return lambda _: _youtube_key('t'), text
    # Exit full screen
    if 'exit full screen' in text_l and 'youtube' in text_l or text_l in ["exit full screen", "youtube exit full screen", "youtube exit fullscreen"]:
        return lambda _: _youtube_key('esc'), text
    # --- End robust YouTube playback controls ---
    # Prioritize 'play ... on youtube' pattern
    if _re.search(r'play .+ on youtube', text_l):
        return _play_youtube_song, text
    # Fallback: if command starts with 'play' and is not a playback control, treat as YouTube play
    if text_l.startswith('play '):
        # If it's 'play next' or 'play previous', handle as playback control
        if 'next' in text_l and 'video' in text_l:
            return lambda _: _youtube_key(['shift', 'n']), text
        if 'previous' in text_l and 'video' in text_l:
            return lambda _: _youtube_key(['shift', 'p']), text
        return _play_youtube_song, text

    # Priority intents: avoid generic "open" / "calendar" stealing integration commands
    if 'open doc' in text_l or 'open document' in text_l:
        return (lambda t: _handle_integration_open_doc(t), text)
    if 'open file' in text_l:
        return (_handle_open_file, text)
    if any(p in text_l for p in ("what's on my calendar", "show my calendar events", "calendar events", "my calendar")) and 'open calendar' not in text_l and 'show calendar' not in text_l:
        return (lambda _: _handle_integration_calendar_events(), text)
    if any(p in text_l for p in ('read my recent email', 'read latest email', 'read my email', 'read my emails')) and 'read email from' not in text_l and 'read email about' not in text_l:
        return (lambda _: _handle_integration_read_recent_email(), text)

    for patterns, func in COMMAND_PATTERNS:
        for pat in patterns:
            # Use word boundary matching for greetings to avoid false positives
            if pat in ['hello', 'hi', 'hey']:
                if _re.search(r'\b' + _re.escape(pat) + r'\b', text_l):
                    return func, text
            else:
                if pat in text_l:
                    return func, text
    return None, text

ACCOUNT_KEYWORDS = ['login', 'sign in', 'register', 'account', 'profile', 'logout', 'sign out', 'signup']

WAKE_WORDS = ['ceaser', 'caesar', 'caeser', 'cesar']

# Improved speak function: split long responses into chunks
# Add lock to prevent duplicate TTS calls
_speaking_lock = threading.Lock()
_is_speaking = False

def _add_natural_pauses(text: str) -> str:
    """Add natural pauses and rhythm to make speech more human-like"""
    # Add pauses after commas (shorter pause)
    text = _re.sub(r',\s*', ', ... ', text)
    
    # Add pauses after periods (longer pause)
    text = _re.sub(r'\.\s+', '. ... ', text)
    
    # Add pauses after question marks
    text = _re.sub(r'\?\s+', '? ... ', text)
    
    # Add pauses after exclamation marks
    text = _re.sub(r'!\s+', '! ... ', text)
    
    # Add natural pauses before conjunctions (and, but, or, so)
    text = _re.sub(r'\s+(and|but|or|so)\s+', r' ... \1 ', text)
    
    # Add pause after "well", "um", "hmm" (natural speech fillers)
    text = _re.sub(r'\b(well|um|hmm|ah|oh)\b\s*', r'\1 ... ', text, flags=_re.IGNORECASE)
    
    # Add emphasis pauses before important words (capitalized or quoted)
    text = _re.sub(r'\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+', r' ... \1 ... ', text)
    
    # Clean up multiple consecutive pauses
    text = _re.sub(r'\.\.\.\s+\.\.\.', '...', text)
    
    return text

def _add_prosody_markers(text: str) -> str:
    """Add prosody markers for natural speech rhythm and emphasis"""
    # Add emphasis to important words (words in quotes, capitalized, or emphasized)
    # This helps gTTS understand natural stress patterns
    
    # Emphasize words in quotes
    text = _re.sub(r'"([^"]+)"', r'\1', text)  # Remove quotes but keep emphasis context
    
    # Add natural rhythm by adjusting punctuation spacing
    # Short pause for commas, longer for periods
    text = _re.sub(r',([^\s])', r', \1', text)  # Ensure space after comma
    text = _re.sub(r'\.([^\s])', r'. \1', text)  # Ensure space after period
    
    # Add natural flow to lists
    text = _re.sub(r'(\d+)\.\s+', r'\1. ... ', text)  # Pause after numbered items
    
    return text

def speak(text: str):
    global _is_speaking
    
    print("Assistant:", text)
    try:
        if not text:
            return
        
        # Prevent duplicate TTS calls
        if _is_speaking:
            print("[TTS] Already speaking, skipping duplicate call")
            return
        
        # Acquire lock to prevent concurrent TTS
        with _speaking_lock:
            if _is_speaking:
                print("[TTS] Already speaking (lock check), skipping duplicate call")
                return
            
            _is_speaking = True
            try:
                print(f"[TTS] Generating speech for: {text}")
                
                # Process text for natural human-like speech
                # Add prosody markers for rhythm and emphasis
                processed_text = _add_prosody_markers(text)
                
                # Add natural pauses for better flow
                processed_text = _add_natural_pauses(processed_text)
                
                # Split long text into shorter chunks for better processing
                # Use sentence boundaries for natural breaks
                max_length = 150  # Increased for more natural sentence flow
                if len(processed_text) > max_length:
                    # Split by sentence boundaries (periods, question marks, exclamation marks)
                    sentences = _re.split(r'([.!?]+\s+)', processed_text)
                    chunks = []
                    current_chunk = ""
                    
                    for i, part in enumerate(sentences):
                        if len(current_chunk + part) <= max_length:
                            current_chunk += part
                        else:
                            if current_chunk.strip():
                                chunks.append(current_chunk.strip())
                            current_chunk = part
                    
                    if current_chunk.strip():
                        chunks.append(current_chunk.strip())
                else:
                    chunks = [processed_text]
                
                # Process each chunk with natural pauses between chunks
                for i, chunk in enumerate(chunks):
                    if chunk.strip():
                        # Clean up the chunk (remove pause markers that gTTS doesn't understand)
                        # Replace our pause markers with actual pauses in speech
                        clean_chunk = chunk.replace('...', '')
                        
                        chunk_file = f"voice_response_{i}.mp3"
                        # Use slower, more natural speech rate for better prosody
                        tts = gTTS(text=clean_chunk, lang="en", slow=False, tld="com")
                        tts.save(chunk_file)
                        print(f"[TTS] Playing chunk {i+1}/{len(chunks)}: {clean_chunk[:50]}...")
                        playsound.playsound(chunk_file)
                        
                        # Add natural pause between chunks (except for the last one)
                        if i < len(chunks) - 1:
                            import time
                            time.sleep(0.3)  # 300ms pause between chunks for natural flow
                        
                        # Clean up chunk file
                        try:
                            os.remove(chunk_file)
                        except:
                            pass
                
                print(f"[TTS] Audio playback completed")
            finally:
                _is_speaking = False
            
    except Exception as e:
        _is_speaking = False
        print(f"[TTS] Error: {e}")
        logging.error(f"TTS error: {e}")

PORCUPINE_ACCESS_KEY = "glBj2gbb6eVhPUAS4H3cMq4gL2R07AjPqMvry3Lf1Y4c6+nk/MukTg=="
PORCUPINE_CUSTOM_PATH = os.path.join(os.path.dirname(__file__), "Hey-Ceaser_en_windows_v3_0_0.ppn")  # Use relative path

porcupine = None
if "--reference-full" not in sys.argv:
    try:
        porcupine = pvporcupine.create(
            access_key=PORCUPINE_ACCESS_KEY,
            keyword_paths=[PORCUPINE_CUSTOM_PATH]
        )
        print("[INFO] Wake word detection initialized successfully")
    except Exception as e:
        print(f"[WARN] Wake word detection failed: {e}")
        print("[INFO] Using built-in wake word instead")
        try:
            porcupine = pvporcupine.create(
                access_key=PORCUPINE_ACCESS_KEY,
                keywords=["picovoice"]
            )
        except Exception as fallback_error:
            print(f"[WARN] Built-in wake word unavailable: {fallback_error}")
            porcupine = None
else:
    print("[INFO] Reference full mode: Picovoice wake engine skipped; CEASER desktop wake flow is active")

ACTIVATION_WINDOW = 10  # seconds

def listen_and_respond():
    global proactive_assistant, CURRENT_USER_ID, openai_context
    
    # Initialize proactive assistant if not already done
    if not proactive_assistant:
        if CURRENT_USER_ID and CURRENT_USER_ID != 'default_user':
            proactive_assistant = ProactiveAssistant(user_id=CURRENT_USER_ID, mode='normal', start_workers=False)
        else:
            # Don't set default_user - it's not a valid UUID for Supabase
            # Proactive assistant will work but personal features need real user_id
            print(f"[WARN] No valid user_id set - personal features will not work. Please log in via the app.")
            # Don't initialize proactive assistant without valid user_id
            proactive_assistant = None
    
    recognizer = sr.Recognizer()
    # Optimize recognizer settings for better long command handling and wake word detection
    recognizer.energy_threshold = 300  # Lower threshold for better sensitivity
    recognizer.dynamic_energy_threshold = True  # Auto-adjust based on ambient noise
    recognizer.pause_threshold = 5.0  # Increased to 5 seconds to allow natural pauses in longer commands
    recognizer.operation_timeout = None  # No operation timeout for long commands
    recognizer.non_speaking_duration = 0.3  # Shorter non-speaking duration for faster response
    recognizer.phrase_threshold = 0.3  # Lower phrase threshold for better detection
    
    mic = sr.Microphone()
    
    print('Hello, I am Ceaser, your AI voice assistant. How can I help you today?')
    
    # Initialize Porcupine with access key
    pa = None
    audio_stream = None
    porcupine_available = False
    
    try:
        if porcupine:
            pa = pyaudio.PyAudio()
            audio_stream = pa.open(
                rate=porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=porcupine.frame_length)
            porcupine_available = True
            print('[INFO] Porcupine audio stream initialized')
    except Exception as e:
        print(f'[WARN] Failed to initialize Porcupine audio stream: {e}')
        porcupine_available = False

    try:
        while True:
            # Wake word detection phase
            wake_word_detected = False
            
            if porcupine_available and audio_stream:
                # Try Porcupine wake word detection first
                print('Listening for wake word "Hey Ceaser" via Porcupine...')
                try:
                    start_time = time.time()
                    timeout = 30  # 30 second timeout for wake word detection
                    
                    while time.time() - start_time < timeout:
                        pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
                        pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
                        keyword_index = porcupine.process(pcm)
                        if keyword_index >= 0:
                            print('✅ Wake word detected via Porcupine!')
                            wake_word_detected = True
                            break
                except Exception as e:
                    print(f'[ERROR] Porcupine wake word detection error: {e}')
                    porcupine_available = False
            
            # If Porcupine didn't detect or isn't available, use speech recognition fallback
            if not wake_word_detected:
                print('Using speech recognition to detect wake word "Hey Ceaser"...')
                try:
                    with mic as source:
                        # Adjust for ambient noise before listening
                        recognizer.adjust_for_ambient_noise(source, duration=0.5)
                        print('🎤 Listening for "Hey Ceaser"...')
                        # Increased timeout and phrase_time_limit for better wake word detection
                        audio = recognizer.listen(source, timeout=15, phrase_time_limit=10)
                        # Use faster recognition
                        text = recognizer.recognize_google(audio, language='en-US', show_all=False).lower()
                        print(f'👤 Heard: {text}')
                        
                        # Check for wake word phrases (various pronunciations) - more flexible matching
                        wake_phrases = ['hey ceaser', 'hey seizer', 'hey seiser', 'ceaser', 'seizer', 'hey caesar', 'hey cesar', 'hey caeser', 'hey ceasar']
                        # Check if any wake phrase appears in the text (not just exact match)
                        text_words = text.split()
                        for phrase in wake_phrases:
                            phrase_words = phrase.split()
                            # Check if all words in phrase appear in text (allowing for variations)
                            if all(any(word in t or t in word for t in text_words) for word in phrase_words):
                                print('✅ Wake word detected via speech recognition!')
                                wake_word_detected = True
                                break
                        if not wake_word_detected:
                            print(f'❌ Wake word not found in: "{text}"')
                except sr.WaitTimeoutError:
                    print('⏱️ No speech detected within timeout')
                except sr.UnknownValueError:
                    print('❓ Could not understand audio')
                except Exception as e:
                    print(f'❌ Speech recognition error: {e}')
            
            if wake_word_detected:
                print('🎯 Wake word confirmed! Starting command listening...')
                speak('Yes, I\'m listening. What can I help you with?')
            else:
                # If still not detected after timeout, proceed anyway (user might have clicked orb)
                print('⚠️ Wake word not detected, but proceeding to command listening (manual activation)...')
                speak('Hello, I am Ceaser. How can I help you today?')
            
            # CONTINUOUS CONVERSATION MODE - Listen continuously until goodbye
            in_conversation = True
            conversation_count = 0  # Track conversation turns
            
            while in_conversation:
                with mic as source:
                    # Adjust for ambient noise before each command to improve accuracy
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    print('Listening for command... (speak naturally, I\'ll wait for you to finish)')
                    # Use very long timeout and phrase_time_limit for complete commands
                    # pause_threshold is now 5.0 seconds, allowing natural pauses without cutting off
                    # phrase_time_limit of 60 seconds allows for very long commands
                    listen_start = time.time()
                    audio = recognizer.listen(source, timeout=60, phrase_time_limit=60)
                    listen_duration = time.time() - listen_start
                    print(f'[INFO] Listened for {listen_duration:.2f} seconds')
                try:
                    recog_start = time.time()
                    # Use faster recognition with optimized settings
                    text = recognizer.recognize_google(audio, language='en-US', show_all=False)
                    recog_time = time.time() - recog_start
                    print(f'Recognition took {recog_time:.2f} seconds')
                    print(f'Heard ({len(text)} characters): {text}')
                except sr.WaitTimeoutError:
                    # No speech detected, continue listening
                    print('No command detected, continuing to listen...')
                    continue
                except Exception as e:
                    print('Could not recognize speech:', e)
                    speak('Sorry, I did not understand. Please try again.')
                    continue
                
                command_text = text.lower().strip()
                if not command_text:
                    speak('Yes?')
                    continue
                
                # Filter out wake words from commands (user might say wake word again)
                wake_phrases = ['hey ceaser', 'hey seizer', 'hey seiser', 'ceaser', 'seizer', 'hey caesar', 'hey cesar', 'hey caeser', 'hey ceasar']
                for phrase in wake_phrases:
                    if phrase in command_text:
                        # Remove wake word phrase from command
                        command_text = command_text.replace(phrase, '').strip()
                        print(f'[INFO] Removed wake word "{phrase}" from command')
                        # If command is empty after removing wake word, ask for command
                        if not command_text:
                            speak('Yes, I\'m listening. What can I help you with?')
                            continue
                        break
                
                # Check for goodbye/exit commands - end conversation and return to wake word mode
                goodbye_keywords = ['goodbye', 'exit', 'quit', 'stop listening', 'stop', 'that\'s all', 'that\'s it', 'we\'re done', 'ceaser signing off', 'that will be all', 'we are done']
                if any(keyword in command_text for keyword in goodbye_keywords):
                    speak('Goodbye! I\'ll be here when you need me. Say "Hey Ceaser" to activate again.')
                    in_conversation = False
                    # Clear context when ending conversation
                    openai_context['last_query'] = None
                    openai_context['last_response'] = None
                    openai_context['conversation_history'] = []
                    conversation_count = 0
                    break
                # Exclude account management
                if any(word in command_text for word in ACCOUNT_KEYWORDS):
                    speak('Sorry, account management is not available via voice.')
                    continue

                # Production pipeline: no direct execution. Handle pending confirmation first.
                global _pending_pipeline_confirmation
                confirm_lower = command_text.strip().lower()
                if _pending_pipeline_confirmation:
                    if confirm_lower in ('yes', 'yeah', 'yep', 'confirm', 'do it', 'proceed'):
                        structured_list = _pending_pipeline_confirmation.get('structured_list', [])
                        exec_results = _pipeline_execute_callback(structured_list, 'PC')
                        response = (exec_results[0].get('result', 'Done.') if exec_results else 'Done.')
                        if len(exec_results) > 1:
                            response = ' '.join(r.get('result', '') for r in exec_results[:3])
                        speak(response)
                        _pending_pipeline_confirmation = None
                        continue
                    if confirm_lower in ('no', 'nope', 'cancel', 'never mind'):
                        speak('Cancelled.')
                        _pending_pipeline_confirmation = None
                        continue
                    _pending_pipeline_confirmation = None

                # Run full 10-step pipeline (no step skipped)
                try:
                    print(f'[VOICE] Sending to Backend Brain: "{command_text}"')
                    intent_data = intent_client.analyze_intent(command_text)
                    intent_type = intent_data.get("intent", "UNKNOWN")
                    confidence = intent_data.get("confidence", 0.0)
                    print(f"[VOICE] Backend returned Intent: {intent_type} ({confidence})")

                    if intent_type in ["UNKNOWN", "ERROR"]:
                        speak("I'm sorry, I'm focused on meeting automation. Could you rephrase that as a task or note?")
                        result = "Unknown Intent"
                    elif intent_type == "RESTRICTED_FEATURE":
                        speak("I can't do that right now. I'm in Work Automation mode.")
                        result = "Restricted Feature"
                    elif intent_type in ["MEETING_CONTROL", "ACTION_ITEM", "CREATE_TASK", "SUMMARIZE", "ASSIGN_TASK"]:
                        speak(f"Sure, processing {intent_type.replace('_', ' ').lower()}.")
                        exec_response = intent_client.execute_action(intent_type, intent_data.get("parameters", {}))
                        if exec_response.get("status") == "success":
                            speak("Done.")
                            result = f"Executed {intent_type}"
                        else:
                            speak("Something went wrong with the execution.")
                            result = f"Failed {intent_type}"
                    else:
                        speak("I am currently limited to meeting assistance.")
                        result = "Gated Feature"

                    if result and proactive_assistant and not any(err in result.lower() for err in ["couldn't", "could not", "error", "failed", "timeout", "timed out"]):
                        try:
                            proactive_assistant.learn_user_pattern('voice_command', {
                                'command': command_text, 'time': datetime.datetime.now().strftime('%H:%M'), 'context': 'voice_interaction'
                            }, confidence=0.7)
                            suggestion = _generate_contextual_suggestion(command_text, result, conversation_count)
                            if suggestion:
                                result += f" Also, {suggestion.lower()}"
                            conversation_count += 1
                        except Exception as e:
                            print(f"Proactive assistance error: {e}")
                    if result:
                        import threading
                        speak_thread = threading.Thread(target=speak, args=(result,), daemon=True)
                        speak_thread.start()
                    logging.info('Command processed and spoken.')
                    continue
                except Exception as e:
                    logging.error(f'Pipeline error: {e}')
                    speak('Sorry, there was an error processing your command.')
                    continue
                # Check for continue/explain more commands
                continue_keywords = ['continue', 'explain more', 'tell me more', 'go on', 'more details', 'elaborate', 'expand on that', 'more about that', 'more information']
                is_continue_command = any(keyword in command_text for keyword in continue_keywords)
                
                # If continue command and we have context, use it
                if is_continue_command and openai_context['last_query'] and openai_context['last_response']:
                    try:
                        # Use OpenAI to continue the previous response (concise)
                        continue_query = f"Continue explaining concisely: {openai_context['last_query']}. Previous explanation: {openai_context['last_response'][:300]}. Provide additional brief, clear details (2-3 sentences maximum)."
                        result = ai_core.chat(continue_query)
                        openai_context['last_response'] = result
                        openai_context['conversation_history'].append({
                            'query': 'continue',
                            'response': result
                        })
                        print('[INFO] Continued explanation using context')
                    except Exception as e:
                        result = f"Sorry, I couldn't continue the explanation. Error: {e}"
                else:
                    # Fallback to backend AI/ChatGPT or OpenAI
                    try:
                        # Check if it's a question that should use OpenAI API
                        is_question = any(word in command_text for word in ['what is', 'what are', 'explain', 'tell me about', 'how', 'why', 'when', 'where', 'who', 'which', 'define'])
                        
                        if is_question:
                            # Use OpenAI directly for better context handling
                            backend_start = time.time()
                            result = ai_core.chat(command_text)
                            backend_time = time.time() - backend_start
                            print(f'OpenAI API call took {backend_time:.2f} seconds')
                            
                            # Store context for continue functionality
                            openai_context['last_query'] = command_text
                            openai_context['last_response'] = result
                            openai_context['conversation_history'].append({
                                'query': command_text,
                                'response': result
                            })
                        else:
                            # Use backend API for other commands
                            backend_start = time.time()
                            r = requests.post(API_URL, json={'command': command_text})
                            backend_time = time.time() - backend_start
                            print(f'Backend AI call took {backend_time:.2f} seconds')
                            if r.ok:
                                resp = r.json()
                                if isinstance(resp.get('response'), dict) and 'raw' in resp['response']:
                                    result = resp['response']['raw']
                                else:
                                    result = resp.get('response', 'Sorry, I could not process that.')
                            else:
                                result = f'Sorry, backend AI error: {r.status_code} {r.text}'
                            
                            # Store context for continue functionality
                            openai_context['last_query'] = command_text
                            openai_context['last_response'] = result
                            openai_context['conversation_history'].append({
                                'query': command_text,
                                'response': result
                            })
                    except Exception as e:
                        logging.error(f'Backend AI error: {e}')
                        result = 'Sorry, there was a backend AI error.'
                
                # Store conversation in user-isolated memory for backend AI responses
                if memory_assistant and result:
                    try:
                        memory_assistant.store_conversation(
                            user_input=text,
                            assistant_response=result,
                            command_type='backend_ai',
                            response_time_ms=int(backend_time * 1000) if 'backend_time' in locals() else 0
                        )
                    except Exception as e:
                        print(f"Failed to store conversation: {e}")
                
                # PROACTIVE ASSISTANCE: Generate context-aware suggestions based on AI query
                if result and proactive_assistant:
                    try:
                        # Learn from this interaction
                        proactive_assistant.learn_user_pattern('ai_query', {
                            'query': command_text,
                            'response_length': len(result),
                            'time': datetime.datetime.now().strftime('%H:%M'),
                            'context': 'ai_assistance'
                        }, confidence=0.6)
                        
                        # Generate context-aware proactive suggestion based on the query
                        proactive_suggestion = _generate_contextual_suggestion(command_text, result, conversation_count)
                        
                        if proactive_suggestion:
                            # Add proactive suggestion after the main response
                            result += f" Also, {proactive_suggestion.lower()}"
                        
                        conversation_count += 1
                    except Exception as e:
                        print(f"Proactive assistance error: {e}")
                
                # Speak immediately using threading for faster, non-blocking response
                import threading
                speak_thread = threading.Thread(target=speak, args=(result,), daemon=True)
                speak_thread.start()
                logging.info('Command processed and spoken.')
    finally:
        if audio_stream is not None:
            audio_stream.close()
        if pa is not None:
            pa.terminate()
        if porcupine is not None:
            porcupine.delete()

def background_listen_and_respond():
    """Background mode: Skip wake word, go straight to command listening"""
    recognizer = sr.Recognizer()
    # Optimize recognizer settings for better long command handling
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 4.0  # Increased to 4 seconds to allow natural pauses
    recognizer.operation_timeout = None
    recognizer.non_speaking_duration = 0.3
    recognizer.phrase_threshold = 0.3
    
    mic = sr.Microphone()
    
    print('Ceaser AI Assistant is listening... (Background Mode)')
    
    # Check if direct listening mode is enabled
    import sys
    direct_listen = '--direct-listen' in sys.argv
    
    if direct_listen:
        speak('Hello, I am Ceaser. How can I help you today?')
    
    try:
        while True:
            with mic as source:
                # Adjust for ambient noise before each command
                recognizer.adjust_for_ambient_noise(source, duration=0.3)
                print('Listening for command... (speak naturally, I\'ll wait for you to finish)')
                # Increased timeout and phrase_time_limit for long commands
                audio = recognizer.listen(source, timeout=60, phrase_time_limit=60)
            try:
                text = recognizer.recognize_google(audio, language='en-US', show_all=False)
                print('Heard:', text)
                
                command_text = text.lower().strip()
                if not command_text:
                    continue
                    
                # Check for exit command
                if any(word in command_text for word in ['exit', 'quit', 'goodbye', 'stop']):
                    speak('Goodbye! Ceaser signing off.')
                    return
                    
                # Process command via pipeline (no direct execution)
                try:
                    pipeline_result = run_pipeline(text=command_text, device='PC', execute_callback=_pipeline_execute_callback)
                    prompt = pipeline_result.get('prompt', '')
                    if pipeline_result.get('need_confirmation'):
                        speak(prompt or 'Should I proceed?')
                    elif prompt:
                        speak(prompt)
                    continue
                except Exception as e:
                    logging.error(f'Command processing error: {e}')
                    speak('Sorry, there was an error processing your command.')
                    continue
                    
                # Fallback to backend AI
                try:
                    r = requests.post(API_URL, json={'command': command_text})
                    if r.ok:
                        resp = r.json()
                        if isinstance(resp.get('response'), dict) and 'raw' in resp['response']:
                            result = resp['response']['raw']
                        else:
                            result = resp.get('response', 'Sorry, I could not process that.')
                    else:
                        result = f'Sorry, backend AI error: {r.status_code}'
                except Exception as e:
                    logging.error(f'Backend AI error: {e}')
                    result = 'Sorry, there was a backend AI error.'
                    
                speak(result)
                
            except sr.UnknownValueError:
                print('Could not understand audio')
            except sr.RequestError as e:
                print(f'Could not request results: {e}')
            except Exception as e:
                print(f'Error: {e}')
                
    except KeyboardInterrupt:
        print('Voice assistant stopped by user')
    except Exception as e:
        print(f'Voice assistant error: {e}')

def reference_full_feature_mode():
    """Full reference assistant: no wake word, direct command listening, legacy feature map enabled."""
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 1.4
    recognizer.operation_timeout = None
    recognizer.non_speaking_duration = 0.45
    recognizer.phrase_threshold = 0.25

    mic = sr.Microphone()
    print("CEASER reference full-feature mode is running.")
    print("No wake word. Speak a command when prompted. Say 'exit' to stop.")

    while True:
        try:
            with mic as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                print("Listening for command...")
                audio = recognizer.listen(source, timeout=12, phrase_time_limit=18)

            print("Transcribing...")
            text = recognizer.recognize_google(audio, language='en-IN', show_all=False)
            print(f"Heard: {text}")
            command_text = text.lower().strip()

            if not command_text:
                speak("I did not catch a command.")
                continue
            if any(word in command_text for word in ['exit', 'quit', 'goodbye', 'stop assistant']):
                speak("Goodbye. CEASER reference assistant stopped.")
                return

            try:
                func, full_text = match_command(command_text)
                if func:
                    result = func(full_text)
                elif isinstance(full_text, str) and full_text.strip():
                    result = full_text
                else:
                    result = ai_core.chat(text)
            except Exception as e:
                logging.error(f"Reference full-feature command error: {e}")
                result = f"Sorry, there was an error processing that command: {e}"

            if result:
                speak(str(result))
            else:
                speak("Done.")

        except sr.WaitTimeoutError:
            speak("I did not hear a command.")
        except sr.UnknownValueError:
            speak("I heard audio, but could not understand the words.")
        except sr.RequestError as e:
            speak(f"Speech recognition service failed: {e}")
        except KeyboardInterrupt:
            print("Reference full-feature mode stopped by user")
            return
        except Exception as e:
            print(f"Reference full-feature mode error: {e}")
            speak("Voice assistant failed.")

def always_listen_mode():
    """Always listening mode - continuously listen for wake word, then process commands"""
    global memory_assistant, proactive_assistant, CURRENT_USER_ID
    
    # Initialize proactive assistant if not already done
    if not proactive_assistant and CURRENT_USER_ID and CURRENT_USER_ID != 'default_user':
        proactive_assistant = ProactiveAssistant(user_id=CURRENT_USER_ID, mode=CURRENT_MODE, start_workers=False)
    elif not proactive_assistant:
        # Don't set default_user - it's not a valid UUID for Supabase
        print(f"[WARN] No valid user_id set - personal features will not work. Please log in via the app.")
    
    # Initialize assistants if not already done
    if not memory_assistant and CURRENT_USER_ID and CURRENT_USER_ID != 'default_user':
        memory_assistant = MemoryAssistant(user_id=CURRENT_USER_ID, mode=CURRENT_MODE)
    if not proactive_assistant and CURRENT_USER_ID and CURRENT_USER_ID != 'default_user':
        proactive_assistant = ProactiveAssistant(user_id=CURRENT_USER_ID, mode=CURRENT_MODE, start_workers=False)
    
    print("👂 Always listening mode activated")
    print("💬 Continuously listening for 'Hey Ceaser'...")
    
    recognizer = sr.Recognizer()
    # Optimize recognizer settings for better long command handling
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 4.0  # Increased to 4 seconds to allow natural pauses
    recognizer.operation_timeout = None
    recognizer.non_speaking_duration = 0.3  # Shorter non-speaking duration for faster response
    recognizer.phrase_threshold = 0.3  # Lower phrase threshold for better detection
    
    mic = sr.Microphone()
    
    try:
        while True:
            with mic as source:
                # Adjust for ambient noise periodically
                recognizer.adjust_for_ambient_noise(source, duration=0.3)
                print("👂 Listening for wake word...")
                # Increased timeout for better wake word detection
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                
            try:
                # Use faster recognition
                text = recognizer.recognize_google(audio, language='en-US', show_all=False)
                print(f"👤 You said: {text}")
                
                # Check for wake word - flexible matching
                text_lower = text.lower()
                wake_phrases = ['hey ceaser', 'hey seizer', 'hey seiser', 'ceaser', 'seizer', 'hey caesar', 'hey cesar', 'hey caeser', 'hey ceasar']
                text_words = text_lower.split()
                wake_word_detected = False
                for phrase in wake_phrases:
                    phrase_words = phrase.split()
                    # Check if all words in phrase appear in text (allowing for variations)
                    if all(any(word in t or t in word for t in text_words) for word in phrase_words):
                        wake_word_detected = True
                        break
                
                if wake_word_detected or any(wake_word.lower() in text_lower for wake_word in WAKE_WORDS):
                    print("🎯 Wake word detected! Listening for command...")
                    speak("Yes, I'm listening. What can I help you with?")
                    
                    # Listen for the actual command
                    try:
                        with mic as source:
                            # Adjust for ambient noise before each command
                            recognizer.adjust_for_ambient_noise(source, duration=0.3)
                            print("🎤 Listening for command... (speak naturally, I'll wait for you to finish)")
                            # Increased timeout and phrase_time_limit for complete long commands (60 seconds)
                            # pause_threshold is 4.0 seconds, allowing natural pauses without cutting off
                            command_audio = recognizer.listen(source, timeout=60, phrase_time_limit=60)
                            
                        print("🔄 Processing command...")
                        # Use faster recognition with optimized settings
                        command_text = recognizer.recognize_google(command_audio, language='en-US', show_all=False)
                        print(f"👤 Command: {command_text}")
                        
                        # Filter out wake words from commands
                        wake_phrases = ['hey ceaser', 'hey seizer', 'hey seiser', 'ceaser', 'seizer', 'hey caesar', 'hey cesar', 'hey caeser', 'hey ceasar']
                        command_text_lower = command_text.lower()
                        for phrase in wake_phrases:
                            if phrase in command_text_lower:
                                command_text_lower = command_text_lower.replace(phrase, '').strip()
                                command_text = command_text_lower
                                print(f'[INFO] Removed wake word "{phrase}" from command')
                                if not command_text:
                                    speak('Yes, I\'m listening. What can I help you with?')
                                    break
                                break
                        
                        # Skip processing if command is empty after filtering wake words
                        if not command_text.strip():
                            continue

                        # Process the command
                        try:
                            func, full_text = match_command(command_text.lower().strip())
                            if func:
                                result = func(full_text)
                                if result:
                                    import threading
                                    speak_thread = threading.Thread(target=speak, args=(result,), daemon=True)
                                    speak_thread.start()
                                continue
                        except Exception as e:
                            logging.error(f'Command processing error: {e}')
                            speak('Sorry, there was an error processing your command.')
                            continue
                        
                        # Fallback to backend AI
                        try:
                            r = requests.post(API_URL, json={'command': command_text})
                            if r.ok:
                                resp = r.json()
                                if isinstance(resp.get('response'), dict) and 'raw' in resp['response']:
                                    result = resp['response']['raw']
                                else:
                                    result = resp.get('response', 'Sorry, I could not process that.')
                            else:
                                result = f'Sorry, backend AI error: {r.status_code}'
                        except Exception as e:
                            logging.error(f'Backend AI error: {e}')
                            result = 'Sorry, there was a backend AI error.'
                        
                        speak(result)
                            
                    except sr.WaitTimeoutError:
                        print("No command detected, returning to wake word listening")
                        continue
                    except sr.UnknownValueError:
                        print("Could not understand command")
                        speak("Sorry, I didn't understand that. Please try again.")
                        continue
                    except sr.RequestError as e:
                        print(f"Could not request results: {e}")
                        continue
                    except Exception as e:
                        print(f"Error processing command: {e}")
                        continue
                
                # Check for stop commands
                elif any(stop_word.lower() in text.lower() for stop_word in ['stop listening', 'stop', 'quit', 'exit']):
                    print("🛑 Stop command detected")
                    speak("Stopping always listening mode. Say 'Hey Ceaser' to reactivate.")
                    break
                    
            except sr.WaitTimeoutError:
                # No speech detected, continue listening
                continue
            except sr.UnknownValueError:
                print("Could not understand audio")
                continue
            except sr.RequestError as e:
                print(f"Could not request results: {e}")
                continue
            except Exception as e:
                print(f"Error: {e}")
                continue
                
    except KeyboardInterrupt:
        print("Always listening stopped by user")
    except Exception as e:
        print(f"Always listening error: {e}")

if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Ceaser AI Voice Assistant')
    parser.add_argument('--always-listen', action='store_true', 
                       help='Enable always listening mode')
    parser.add_argument('--direct-listen', action='store_true',
                       help='Start listening immediately')
    parser.add_argument('--background', action='store_true',
                       help='Run in background mode')
    parser.add_argument('--reference-full', action='store_true',
                       help='Run the full reference assistant without wake word')
    parser.add_argument('--user-id', type=str, default=None,
                       help='User ID for personalized voice assistant')
    args = parser.parse_args()
    
    # Set user_id from command line argument or environment variable
    user_id_from_arg = args.user_id
    user_id_from_env = os.getenv('CURRENT_USER_ID')
    
    if user_id_from_arg:
        set_current_user(user_id_from_arg)
        print(f"✅ User ID set from command line: {user_id_from_arg}")
    elif user_id_from_env:
        set_current_user(user_id_from_env)
        print(f"✅ User ID set from environment: {user_id_from_env}")
    else:
        print("⚠️ No user_id provided - voice assistant will use default user")
        print("   Some features may not work correctly without user context")
    
    print("Ceaser AI Voice Assistant Starting...")
    
    if args.reference_full:
        print("Reference Full Feature Mode: ENABLED")
    elif args.always_listen:
        print("Always Listening Mode: ENABLED")
        print("Say 'Hey Ceaser' to activate voice commands")
        print("Say 'stop listening' to deactivate")
    elif args.direct_listen:
        print("Direct Listening Mode: Starting immediately")
    else:
        print("Say 'Hey Ceaser' to activate voice commands")
        print("Say 'stop listening' to deactivate")
    
    print("Say 'quit' or 'exit' to close the assistant")
    print("=" * 50)
    
    # Check for background mode
    if args.reference_full:
        print("[INFO] Starting reference full-feature mode")
        reference_full_feature_mode()
    elif args.background:
        print("[INFO] Starting voice assistant in background mode")
        # In background mode, skip wake word and go straight to command listening
        background_listen_and_respond()
    elif args.always_listen:
        print("[INFO] Starting voice assistant in always listening mode")
        # Always listening mode - continuously listen for wake word
        always_listen_mode()
    else:
        print("[INFO] Starting voice assistant in normal mode")
        listen_and_respond() 
