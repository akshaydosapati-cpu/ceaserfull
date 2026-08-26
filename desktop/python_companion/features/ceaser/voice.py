import speech_recognition as sr
import pyttsx3
import time
import re
import os
import struct
import pyaudio

# Try to import Porcupine for wake word detection
try:
    import pvporcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False
    print("[WARN] Porcupine not available. Wake word detection disabled.")

class VoiceAssistant:
    @staticmethod
    def speak(text, rate=180, voice=None):
        """Speak text using text-to-speech"""
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', rate)
            
            if voice:
                engine.setProperty('voice', voice)
            
            # Clean text for speech
            clean_text = VoiceAssistant.clean_for_speech(text)
            engine.say(clean_text)
            engine.runAndWait()
            return True
        except Exception as e:
            print(f"Error in speech: {e}")
            return False

    @staticmethod
    def listen(timeout=5):
        """Listen for speech and convert to text"""
        try:
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                print("Listening...")
                audio = recognizer.listen(source, timeout=timeout)
                
            text = recognizer.recognize_google(audio)
            print(f"You said: {text}")
            return text.lower()
        except sr.WaitTimeoutError:
            print("No speech detected")
            return None
        except sr.UnknownValueError:
            print("Could not understand audio")
            return None
        except Exception as e:
            print(f"Error in speech recognition: {e}")
            return None

    def __init__(self, wake_word_path=None, access_key=None):
        """Initialize voice assistant with wake word detection"""
        # Initialize text-to-speech engine with error handling
        try:
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', 180)  # Slower rate for Indian English
            self.tts_engine.setProperty('volume', 0.9)
        except Exception as e:
            print(f"Warning: TTS engine initialization failed: {e}")
            print("Voice assistant will work without text-to-speech functionality")
            self.tts_engine = None
        
        # Try to select an Indian English voice/accent if available
        voices = []
        if self.tts_engine:
            voices = self.tts_engine.getProperty('voices')
            if not isinstance(voices, (list, tuple)):
                voices = []
        
        selected = False
        for v in voices:
            name = getattr(v, 'name', '').lower()
            # Safely extract language code
            lang = ''
            if hasattr(v, 'languages'):
                langs = getattr(v, 'languages')
                if isinstance(langs, (list, tuple)) and langs:
                    lang = str(langs[0]).lower()
                elif isinstance(langs, str):
                    lang = langs.lower()
            id_ = getattr(v, 'id', '').lower()
            # Check for Indian English accent in name, language, or id
            if 'india' in name or 'en-in' in lang or 'en-in' in id_ or 'hindi' in name:
                if self.tts_engine:
                    self.tts_engine.setProperty('voice', v.id)
                selected = True
                break
        # Fallback: select a male voice if Indian English not found
        if not selected:
            for v in voices:
                name = getattr(v, 'name', '')
                gender = getattr(v, 'gender', '')
                if name and isinstance(name, str) and 'male' in name.lower():
                    if self.tts_engine:
                        self.tts_engine.setProperty('voice', v.id)
                    break
                if gender and isinstance(gender, str) and 'male' in gender.lower():
                    if self.tts_engine:
                        self.tts_engine.setProperty('voice', v.id)
                    break
        
        # Initialize wake word detection
        self.porcupine = None
        self.audio_stream = None
        self.pa = None
        
        reference_full_mode = os.getenv("CEASER_REFERENCE_FULL_MODE", "").lower() in ("1", "true", "yes")
        if reference_full_mode:
            print("[INFO] Picovoice wake engine skipped; CEASER desktop uses the Electron + Python STT wake flow.")
        elif PORCUPINE_AVAILABLE:
            try:
                # Use provided path or default
                wake_word_path = wake_word_path or os.path.join(
                    os.path.dirname(__file__), 
                    '..', '..', 'Hey-Ceaser_en_windows_v3_0_0.ppn'
                )
                access_key = access_key or "glBj2gbb6eVhPUAS4H3cMq4gL2R07AjPqMvry3Lf1Y4c6+nk/MukTg=="
                
                self.porcupine = pvporcupine.create(
                    access_key=access_key,
                    keyword_paths=[wake_word_path]
                )
                print("[INFO] Wake word detection initialized successfully")
            except Exception as e:
                print(f"[WARN] Failed to initialize wake word detection: {e}")
                self.porcupine = None

    def clean_for_speech(self, text):
        # Remove Markdown bold/italic/list symbols and headings
        text = re.sub(r'\*\*|\*|__|_', '', text)
        text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)  # Remove list bullets
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)         # Remove headings
        text = text.replace('•', '')                                    # Remove bullet symbols
        return text.strip()

    def wake_word_detect(self, timeout=10):
        """Detect wake word using Porcupine"""
        if not self.porcupine:
            print("[WARN] Wake word detection not available")
            return False
            
        try:
            # Initialize audio stream if not already done
            if not self.audio_stream:
                self.pa = pyaudio.PyAudio()
                self.audio_stream = self.pa.open(
                    rate=self.porcupine.sample_rate,
                    channels=1,
                    format=pyaudio.paInt16,
                    input=True,
                    frames_per_buffer=self.porcupine.frame_length
                )
            
            print("Listening for wake word...")
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    pcm = self.audio_stream.read(self.porcupine.frame_length, exception_on_overflow=False)
                    pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
                    keyword_index = self.porcupine.process(pcm)
                    
                    if keyword_index >= 0:
                        print("Wake word detected!")
                        return True
                        
                except Exception as e:
                    print(f"Error in wake word detection: {e}")
                    break
                    
            return False
            
        except Exception as e:
            print(f"Error in wake word detection: {e}")
            return False

    def start_wake_word_listening(self):
        """Start listening for wake word in background"""
        if not self.porcupine:
            print("[WARN] Wake word detection not available")
            return False
            
        try:
            # Initialize audio stream if not already done
            if not self.audio_stream:
                self.pa = pyaudio.PyAudio()
                self.audio_stream = self.pa.open(
                    rate=self.porcupine.sample_rate,
                    channels=1,
                    format=pyaudio.paInt16,
                    input=True,
                    frames_per_buffer=self.porcupine.frame_length
                )
            
            print("Starting wake word listening...")
            return True
            
        except Exception as e:
            print(f"Error starting wake word listening: {e}")
            return False

    def stop_wake_word_listening(self):
        """Stop wake word listening and cleanup"""
        try:
            if self.audio_stream:
                self.audio_stream.close()
                self.audio_stream = None
            if self.pa:
                self.pa.terminate()
                self.pa = None
            print("Wake word listening stopped")
        except Exception as e:
            print(f"Error stopping wake word listening: {e}")

    def cleanup(self):
        """Cleanup resources"""
        self.stop_wake_word_listening()

    def handle_joke(self, fun):
        """Handle joke request"""
        joke = fun.get_random_joke()
        self.speak(joke)

    def handle_play_game(self, fun):
        """Handle game request"""
        game = fun.start_game()
        self.speak(game)

    def handle_sing_song(self, fun):
        """Handle song request"""
        song = fun.sing_song()
        self.speak(song)

    def handle_object_detection(self, vision):
        """Handle object detection request"""
        result = vision.detect_objects()
        self.speak(result)

    def handle_face_authenticate(self, vision):
        """Handle face authentication"""
        result = vision.face_authentication()
        self.speak(result)

    def handle_emotion(self, vision):
        """Handle emotion detection"""
        result = vision.detect_emotion()
        self.speak(result)

    def handle_language_practice(self, lang, lang_name):
        """Handle language practice"""
        practice = lang.practice_language(lang_name)
        self.speak(practice)

    def handle_find_file(self, fileman, filename):
        """Handle file search"""
        result = fileman.find_file(filename)
        self.speak(result)

    def handle_delete_files(self, fileman, pattern):
        """Handle file deletion"""
        result = fileman.delete_files(pattern)
        self.speak(result)

    def handle_reminder(self, notify, message, time_str):
        """Handle reminder creation"""
        result = notify.create_reminder(message, time_str)
        self.speak(result)

    def handle_device_control(self, device, command):
        """Handle device control"""
        result = device.control_device(command)
        self.speak(result)

    def handle_automation(self, auto, command):
        """Handle automation"""
        result = auto.run_automation(command)
        self.speak(result)

    def handle_google_search(self, query):
        """Handle Google search"""
        try:
            import webbrowser
            search_url = f"https://www.google.com/search?q={query}"
            webbrowser.open(search_url)
            return f"Searching Google for {query}"
        except Exception as e:
            return f"Error performing Google search: {e}"

    def handle_wikipedia(self, query):
        """Handle Wikipedia search"""
        try:
            import wikipedia
            result = wikipedia.summary(query, sentences=2)
            return result
        except Exception as e:
            return f"Error searching Wikipedia: {e}"

    def handle_youtube_search(self, query):
        """Handle YouTube search"""
        try:
            import webbrowser
            search_url = f"https://www.youtube.com/results?search_query={query}"
            webbrowser.open(search_url)
            return f"Searching YouTube for {query}"
        except Exception as e:
            return f"Error searching YouTube: {e}"

    def handle_play_song(self, song):
        """Handle song playback"""
        try:
            import webbrowser
            search_url = f"https://www.youtube.com/results?search_query={song}"
            webbrowser.open(search_url)
            return f"Playing {song} on YouTube"
        except Exception as e:
            return f"Error playing song: {e}"

def run_voice_assistant():
    """Run the voice assistant"""
    assistant = VoiceAssistant()
    print("Voice Assistant initialized. Say 'Hey Ceaser' to activate.")
    
    try:
        while True:
            if assistant.wake_word_detect():
                assistant.speak("Hello! How can I help you today?")
                command = assistant.listen()
                if command:
                    # Process command here
                    assistant.speak(f"You said: {command}")
    except KeyboardInterrupt:
        print("Voice Assistant stopped.")
    finally:
        assistant.cleanup()

if __name__ == "__main__":
    run_voice_assistant() 
