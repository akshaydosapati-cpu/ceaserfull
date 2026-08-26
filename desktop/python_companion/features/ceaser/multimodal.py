import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union
import threading
import sqlite3
from pathlib import Path
import base64
import hashlib

# Try to import advanced AI libraries
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("[INFO] OpenAI not available for multimodal features.")

def _create_openai_client(api_key: str):
    """
    Safely create OpenAI client, handling httpx version incompatibilities.
    """
    try:
        # Try standard initialization first
        return openai.OpenAI(api_key=api_key)
    except TypeError as e:
        # httpx version incompatibility - try with explicit http_client
        try:
            import httpx
            # Create httpx client without proxies parameter
            http_client = httpx.Client(timeout=30.0)
            return openai.OpenAI(api_key=api_key, http_client=http_client)
        except Exception as e2:
            logging.getLogger(__name__).warning(f"Failed to initialize OpenAI client: {e2}")
            return None
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to initialize OpenAI client: {e}")
        return None

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("[INFO] OpenCV not available for image processing.")

try:
    import speech_recognition as sr
    import pyttsx3
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False
    print("[INFO] Speech recognition not available.")

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[INFO] PIL not available for image processing.")

# Try to import screen capture libraries
try:
    import pyautogui
    import PIL.ImageGrab
    SCREEN_CAPTURE_AVAILABLE = True
except ImportError:
    SCREEN_CAPTURE_AVAILABLE = False
    print("[INFO] Screen capture not available. Install with: pip install pyautogui pillow")

# Try to import file monitoring libraries
try:
    import watchdog
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    FILE_MONITORING_AVAILABLE = True
except ImportError:
    FILE_MONITORING_AVAILABLE = False
    print("[INFO] File monitoring not available. Install with: pip install watchdog")

class MultimodalAssistant:
    def __init__(self, db_path='multimodal.db', media_dir='./multimodal_media'):
        self.db_path = db_path
        self.media_dir = Path(media_dir)
        self.media_dir.mkdir(exist_ok=True)
        
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()
        
        # Initialize logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Initialize AI components
        self.openai_client = None
        if OPENAI_AVAILABLE:
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                self.openai_client = _create_openai_client(api_key)
        
        # Speech recognition
        self.recognizer = None
        self.microphone = None
        if SPEECH_AVAILABLE:
            self.recognizer = sr.Recognizer()
            try:
                self.microphone = sr.Microphone()
            except Exception as e:
                self.logger.warning(f"Microphone not available: {e}")
        
        # Text-to-speech
        self.tts_engine = None
        if SPEECH_AVAILABLE:
            try:
                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty('rate', 150)
                self.tts_engine.setProperty('volume', 0.8)
            except Exception as e:
                self.logger.warning(f"TTS engine not available: {e}")
        
        # Processing queues
        self.image_queue = []
        self.audio_queue = []
        self.text_queue = []
        
        # Desktop-specific features
        self.screen_monitoring_active = False
        self.file_monitoring_active = False
        self.auto_analysis_enabled = False
        self.monitored_directories = []
        self.analysis_history = []
        self.cross_references = {}
        
        # Screen monitoring
        self.screen_observer = None
        self.last_screen_hash = None
        self.screen_change_threshold = 0.1
        
        # File monitoring
        self.file_observer = None
        self.monitored_files = set()
        
        # Multi-monitor support
        self.monitor_configs = []
        self._detect_monitors()
        
        # Start background processing
        self.processing_active = True
        self.processing_thread = threading.Thread(target=self._background_processing, daemon=True)
        self.processing_thread.start()

    def _create_tables(self):
        """Create SQLite tables for multimodal data"""
        with self.conn:
            # Media files storage
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS media_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_hash TEXT UNIQUE,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    processed_at DATETIME,
                    analysis_result TEXT
                )
            ''')
            
            # Multimodal sessions
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS multimodal_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE,
                    session_type TEXT,
                    input_data TEXT,
                    output_data TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    processing_time REAL
                )
            ''')
            
            # Analysis results
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    media_id INTEGER,
                    analysis_type TEXT,
                    result_data TEXT,
                    confidence REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (media_id) REFERENCES media_files (id)
                )
            ''')
            
            # Cross references
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS cross_references (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relationship TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Screen monitoring history
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS screen_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    screen_path TEXT NOT NULL,
                    monitor_id INTEGER,
                    change_detected BOOLEAN,
                    analysis_result TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # File monitoring events
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS file_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    auto_analyzed BOOLEAN,
                    analysis_result TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_media_type ON media_files(file_type)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_type ON multimodal_sessions(session_type)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_cross_refs ON cross_references(source_id, target_id)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_screen_history ON screen_history(created_at)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_file_events ON file_events(created_at)')

    def process_image(self, image_path: str, analysis_type: str = "general") -> Dict[str, Any]:
        """Process and analyze an image"""
        try:
            if not CV2_AVAILABLE:
                return {"error": "OpenCV not available for image processing"}
            
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                return {"error": "Could not load image"}
            
            # Generate file hash
            with open(image_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            
            # Store in database
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO media_files (file_path, file_type, file_hash, metadata)
                    VALUES (?, ?, ?, ?)
                ''', (image_path, 'image', file_hash, json.dumps({'analysis_type': analysis_type})))
                
                media_id = cursor.lastrowid
                if not media_id:
                    cursor.execute('SELECT id FROM media_files WHERE file_hash = ?', (file_hash,))
                    media_id = cursor.fetchone()[0]
            
            # Basic image analysis
            analysis_result = {
                'dimensions': {
                    'width': image.shape[1],
                    'height': image.shape[0],
                    'channels': image.shape[2] if len(image.shape) > 2 else 1
                },
                'file_size': os.path.getsize(image_path),
                'file_format': Path(image_path).suffix.lower()
            }
            
            # Advanced analysis with OpenAI if available
            if self.openai_client and analysis_type in ["objects", "text", "faces", "general"]:
                try:
                    with open(image_path, "rb") as image_file:
                        response = self.openai_client.chat.completions.create(
                            model="gpt-4-vision-preview",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": f"Analyze this image and provide a detailed description. Focus on {analysis_type} if specified."},
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:image/jpeg;base64,{base64.b64encode(image_file.read()).decode('utf-8')}"
                                            }
                                        }
                                    ]
                                }
                            ],
                            max_tokens=500
                        )
                    
                    analysis_result['ai_analysis'] = response.choices[0].message.content
                    
                except Exception as e:
                    self.logger.error(f"OpenAI analysis failed: {e}")
                    analysis_result['ai_analysis'] = "AI analysis unavailable"
            
            # Store analysis result
            with self.conn:
                self.conn.execute('''
                    UPDATE media_files 
                    SET processed_at = CURRENT_TIMESTAMP, analysis_result = ?
                    WHERE id = ?
                ''', (json.dumps(analysis_result), media_id))
                
                self.conn.execute('''
                    INSERT INTO analysis_results (media_id, analysis_type, result_data, confidence)
                    VALUES (?, ?, ?, ?)
                ''', (media_id, analysis_type, json.dumps(analysis_result), 0.8))
            
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"Failed to process image: {e}")
            return {"error": str(e)}

    def process_audio(self, audio_path: str, analysis_type: str = "transcription") -> Dict[str, Any]:
        """Process and analyze audio"""
        try:
            if not SPEECH_AVAILABLE:
                return {"error": "Speech recognition not available"}
            
            # Generate file hash
            with open(audio_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            
            # Store in database
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO media_files (file_path, file_type, file_hash, metadata)
                    VALUES (?, ?, ?, ?)
                ''', (audio_path, 'audio', file_hash, json.dumps({'analysis_type': analysis_type})))
                
                media_id = cursor.lastrowid
                if not media_id:
                    cursor.execute('SELECT id FROM media_files WHERE file_hash = ?', (file_hash,))
                    media_id = cursor.fetchone()[0]
            
            analysis_result = {
                'file_size': os.path.getsize(audio_path),
                'file_format': Path(audio_path).suffix.lower()
            }
            
            # Audio transcription
            if analysis_type == "transcription":
                try:
                    with sr.AudioFile(audio_path) as source:
                        audio = self.recognizer.record(source)
                        transcription = self.recognizer.recognize_google(audio)
                        analysis_result['transcription'] = transcription
                        analysis_result['confidence'] = 0.8
                        
                except sr.UnknownValueError:
                    analysis_result['transcription'] = "Could not understand audio"
                    analysis_result['confidence'] = 0.0
                except sr.RequestError as e:
                    analysis_result['transcription'] = f"Speech recognition service error: {e}"
                    analysis_result['confidence'] = 0.0
            
            # Store analysis result
            with self.conn:
                self.conn.execute('''
                    UPDATE media_files 
                    SET processed_at = CURRENT_TIMESTAMP, analysis_result = ?
                    WHERE id = ?
                ''', (json.dumps(analysis_result), media_id))
                
                self.conn.execute('''
                    INSERT INTO analysis_results (media_id, analysis_type, result_data, confidence)
                    VALUES (?, ?, ?, ?)
                ''', (media_id, analysis_type, json.dumps(analysis_result), analysis_result.get('confidence', 0.5)))
            
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"Failed to process audio: {e}")
            return {"error": str(e)}

    def process_text(self, text: str, analysis_type: str = "general") -> Dict[str, Any]:
        """Process and analyze text"""
        try:
            analysis_result = {
                'text_length': len(text),
                'word_count': len(text.split()),
                'character_count': len(text.replace(' ', '')),
                'analysis_type': analysis_type
            }
            
            # Basic text analysis
            analysis_result['sentiment'] = self._analyze_sentiment(text)
            analysis_result['key_topics'] = self._extract_key_topics(text)
            analysis_result['language'] = self._detect_language(text)
            
            # Advanced analysis with OpenAI if available
            if self.openai_client:
                try:
                    response = self.openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {
                                "role": "user",
                                "content": f"Analyze this text and provide insights. Focus on {analysis_type} if specified: {text}"
                            }
                        ],
                        max_tokens=300
                    )
                    
                    analysis_result['ai_analysis'] = response.choices[0].message.content
                    
                except Exception as e:
                    self.logger.error(f"OpenAI text analysis failed: {e}")
                    analysis_result['ai_analysis'] = "AI analysis unavailable"
            
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"Failed to process text: {e}")
            return {"error": str(e)}

    def create_multimodal_session(self, session_type: str, inputs: Dict[str, Any]) -> str:
        """Create a multimodal processing session"""
        try:
            session_id = f"session_{int(time.time())}"
            
            with self.conn:
                self.conn.execute('''
                    INSERT INTO multimodal_sessions (session_id, session_type, input_data)
                    VALUES (?, ?, ?)
                ''', (session_id, session_type, json.dumps(inputs)))
            
            return session_id
            
        except Exception as e:
            self.logger.error(f"Failed to create multimodal session: {e}")
            return ""

    def process_multimodal_input(self, session_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Process multiple types of input together"""
        try:
            start_time = time.time()
            results = {}
            
            # Process each input type
            if 'image' in inputs:
                results['image'] = self.process_image(inputs['image'], inputs.get('image_analysis', 'general'))
            
            if 'audio' in inputs:
                results['audio'] = self.process_audio(inputs['audio'], inputs.get('audio_analysis', 'transcription'))
            
            if 'text' in inputs:
                results['text'] = self.process_text(inputs['text'], inputs.get('text_analysis', 'general'))
            
            # Combine results for comprehensive analysis
            if self.openai_client and len(results) > 1:
                combined_analysis = self._combine_multimodal_results(results)
                results['combined_analysis'] = combined_analysis
            
            processing_time = time.time() - start_time
            
            # Update session
            with self.conn:
                self.conn.execute('''
                    UPDATE multimodal_sessions 
                    SET output_data = ?, processing_time = ?
                    WHERE session_id = ?
                ''', (json.dumps(results), processing_time, session_id))
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to process multimodal input: {e}")
            return {"error": str(e)}

    def capture_image(self, save_path: Optional[str] = None) -> Optional[str]:
        """Capture an image using the camera"""
        try:
            if not CV2_AVAILABLE:
                self.logger.error("OpenCV not available for image capture")
                return None
            
            # Initialize camera
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                self.logger.error("Could not open camera")
                return None
            
            # Capture frame
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                self.logger.error("Could not capture image")
                return None
            
            # Save image
            if not save_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = str(self.media_dir / f"captured_image_{timestamp}.jpg")
            
            cv2.imwrite(save_path, frame)
            self.logger.info(f"Image captured and saved: {save_path}")
            
            return save_path
            
        except Exception as e:
            self.logger.error(f"Failed to capture image: {e}")
            return None

    def record_audio(self, duration: int = 5, save_path: Optional[str] = None) -> Optional[str]:
        """Record audio from microphone"""
        try:
            if not SPEECH_AVAILABLE or not self.microphone:
                self.logger.error("Speech recognition not available for audio recording")
                return None
            
            # Record audio
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source)
                audio = self.recognizer.listen(source, timeout=duration, phrase_time_limit=duration)
            
            # Save audio
            if not save_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = str(self.media_dir / f"recorded_audio_{timestamp}.wav")
            
            with open(save_path, "wb") as f:
                f.write(audio.get_wav_data())
            
            self.logger.info(f"Audio recorded and saved: {save_path}")
            return save_path
            
        except Exception as e:
            self.logger.error(f"Failed to record audio: {e}")
            return None

    def speak_text(self, text: str) -> bool:
        """Convert text to speech"""
        try:
            if not self.tts_engine:
                self.logger.error("TTS engine not available")
                return False
            
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to speak text: {e}")
            return False

    # ===== DESKTOP ENHANCEMENTS =====

    def _detect_monitors(self):
        """Detect available monitors"""
        try:
            if SCREEN_CAPTURE_AVAILABLE:
                # Use screeninfo for monitor detection
                try:
                    from screeninfo import get_monitors
                    monitors = get_monitors()
                    for i, monitor in enumerate(monitors):
                        self.monitor_configs.append({
                            'id': i,
                            'name': f"Monitor {i+1}",
                            'width': monitor.width,
                            'height': monitor.height,
                            'left': monitor.x,
                            'top': monitor.y,
                            'is_primary': i == 0
                        })
                    self.logger.info(f"Detected {len(self.monitor_configs)} monitors")
                except ImportError:
                    # Fallback to single monitor
                    screen_width, screen_height = pyautogui.size()
                    self.monitor_configs.append({
                        'id': 0,
                        'name': "Primary Monitor",
                        'width': screen_width,
                        'height': screen_height,
                        'left': 0,
                        'top': 0,
                        'is_primary': True
                    })
                    self.logger.info("Using single monitor configuration")
        except Exception as e:
            self.logger.error(f"Failed to detect monitors: {e}")
            # Default single monitor
            self.monitor_configs.append({
                'id': 0,
                'name': "Default Monitor",
                'width': 1920,
                'height': 1080,
                'left': 0,
                'top': 0,
                'is_primary': True
            })

    def capture_screen(self, monitor_id: int = 0, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[str]:
        """Capture screen or specific region"""
        try:
            if not SCREEN_CAPTURE_AVAILABLE:
                return None
            
            if region:
                screenshot = PIL.ImageGrab.grab(bbox=region)
            elif monitor_id < len(self.monitor_configs):
                monitor = self.monitor_configs[monitor_id]
                screenshot = PIL.ImageGrab.grab(bbox=(monitor['left'], monitor['top'], 
                                                     monitor['left'] + monitor['width'], 
                                                     monitor['top'] + monitor['height']))
            else:
                screenshot = PIL.ImageGrab.grab()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = str(self.media_dir / f"screen_{monitor_id}_{timestamp}.png")
            screenshot.save(save_path)
            
            return save_path
            
        except Exception as e:
            self.logger.error(f"Failed to capture screen: {e}")
            return None

    def capture_window(self, window_title: str = None) -> Optional[str]:
        """Capture specific window"""
        try:
            if not SCREEN_CAPTURE_AVAILABLE:
                return None
            
            if window_title:
                windows = pyautogui.getWindowsWithTitle(window_title)
                if windows:
                    window = windows[0]
                    window.activate()
                    time.sleep(0.5)
                    screenshot = pyautogui.screenshot(region=window.box)
                else:
                    return None
            else:
                screenshot = pyautogui.screenshot()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = str(self.media_dir / f"window_{timestamp}.png")
            screenshot.save(save_path)
            
            return save_path
            
        except Exception as e:
            self.logger.error(f"Failed to capture window: {e}")
            return None

    def start_screen_monitoring(self, interval: int = 5, monitor_id: int = 0):
        """Start continuous screen monitoring"""
        try:
            if not SCREEN_CAPTURE_AVAILABLE:
                return False
            
            self.screen_monitoring_active = True
            self.screen_monitor_thread = threading.Thread(
                target=self._screen_monitoring_loop, 
                args=(interval, monitor_id), 
                daemon=True
            )
            self.screen_monitor_thread.start()
            self.logger.info(f"Started screen monitoring on monitor {monitor_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start screen monitoring: {e}")
            return False

    def stop_screen_monitoring(self):
        """Stop screen monitoring"""
        self.screen_monitoring_active = False
        self.logger.info("Stopped screen monitoring")

    def _screen_monitoring_loop(self, interval: int, monitor_id: int):
        """Screen monitoring loop"""
        while self.screen_monitoring_active:
            try:
                # Capture current screen
                current_path = self.capture_screen(monitor_id)
                if current_path:
                    # Check for significant changes
                    if self._has_screen_changed(current_path):
                        # Auto-analyze if enabled
                        if self.auto_analysis_enabled:
                            self.process_image(current_path, "general")
                        self.last_screen_hash = self._get_image_hash(current_path)
                
                time.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Screen monitoring error: {e}")
                time.sleep(interval)

    def _has_screen_changed(self, image_path: str) -> bool:
        """Check if screen has changed significantly"""
        try:
            current_hash = self._get_image_hash(image_path)
            if self.last_screen_hash is None:
                return True
            
            # Simple hash comparison (can be enhanced with more sophisticated diff)
            return current_hash != self.last_screen_hash
            
        except Exception as e:
            self.logger.error(f"Failed to check screen changes: {e}")
            return False

    def _get_image_hash(self, image_path: str) -> str:
        """Get hash of image for change detection"""
        try:
            with open(image_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            self.logger.error(f"Failed to get image hash: {e}")
            return ""

    def start_file_monitoring(self, directory: str):
        """Start monitoring directory for new files"""
        try:
            if not FILE_MONITORING_AVAILABLE:
                return False
            
            if directory not in self.monitored_directories:
                self.monitored_directories.append(directory)
                
                event_handler = MultimodalFileHandler(self)
                observer = Observer()
                observer.schedule(event_handler, directory, recursive=True)
                observer.start()
                
                self.file_observer = observer
                self.file_monitoring_active = True
                self.logger.info(f"Started monitoring directory: {directory}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to start file monitoring: {e}")
            return False

    def stop_file_monitoring(self):
        """Stop file monitoring"""
        if self.file_observer:
            self.file_observer.stop()
            self.file_observer.join()
        self.file_monitoring_active = False
        self.logger.info("Stopped file monitoring")

    def enable_auto_analysis(self, enabled: bool = True):
        """Enable/disable automatic analysis"""
        self.auto_analysis_enabled = enabled
        self.logger.info(f"Auto analysis {'enabled' if enabled else 'disabled'}")

    def batch_process_files(self, file_paths: List[str], analysis_type: str = "general") -> Dict[str, Any]:
        """Process multiple files in batch"""
        try:
            results = {}
            total_files = len(file_paths)
            
            for i, file_path in enumerate(file_paths):
                self.logger.info(f"Processing file {i+1}/{total_files}: {file_path}")
                
                if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff')):
                    results[file_path] = self.process_image(file_path, analysis_type)
                elif file_path.lower().endswith(('.mp3', '.wav', '.m4a', '.flac')):
                    results[file_path] = self.process_audio(file_path, analysis_type)
                elif file_path.lower().endswith(('.txt', '.md', '.doc', '.docx', '.pdf')):
                    # For text files, read content first
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            text_content = f.read()
                        results[file_path] = self.process_text(text_content, analysis_type)
                    except Exception as e:
                        results[file_path] = {"error": f"Failed to read file: {e}"}
                else:
                    results[file_path] = {"error": "Unsupported file type"}
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to batch process files: {e}")
            return {"error": str(e)}

    def search_files(self, query: str, directory: str = None, file_types: List[str] = None) -> List[str]:
        """Search for files matching criteria"""
        try:
            if not directory:
                directory = str(self.media_dir)
            
            matching_files = []
            
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    # Check file type filter
                    if file_types:
                        if not any(file.lower().endswith(ft.lower()) for ft in file_types):
                            continue
                    
                    # Check if query matches filename or content
                    if query.lower() in file.lower():
                        matching_files.append(file_path)
                    else:
                        # Try to search in file content for text files
                        if file.lower().endswith(('.txt', '.md', '.log')):
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                    if query.lower() in content.lower():
                                        matching_files.append(file_path)
                            except:
                                pass
            
            return matching_files
            
        except Exception as e:
            self.logger.error(f"Failed to search files: {e}")
            return []

    def create_cross_reference(self, source_id: str, target_id: str, relationship: str):
        """Create cross-reference between different media items"""
        try:
            self.cross_references[f"{source_id}_{target_id}"] = {
                'source_id': source_id,
                'target_id': target_id,
                'relationship': relationship,
                'created_at': datetime.now().isoformat()
            }
            
            # Store in database
            with self.conn:
                self.conn.execute('''
                    INSERT INTO cross_references (source_id, target_id, relationship, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (source_id, target_id, relationship, datetime.now()))
            
            self.logger.info(f"Created cross-reference: {source_id} -> {target_id} ({relationship})")
            
        except Exception as e:
            self.logger.error(f"Failed to create cross-reference: {e}")

    def get_related_content(self, content_id: str) -> List[Dict[str, Any]]:
        """Get related content based on cross-references"""
        try:
            related = []
            
            # Check direct references
            for ref_id, ref_data in self.cross_references.items():
                if ref_data['source_id'] == content_id:
                    related.append({
                        'id': ref_data['target_id'],
                        'relationship': ref_data['relationship'],
                        'type': 'target'
                    })
                elif ref_data['target_id'] == content_id:
                    related.append({
                        'id': ref_data['source_id'],
                        'relationship': ref_data['relationship'],
                        'type': 'source'
                    })
            
            return related
            
        except Exception as e:
            self.logger.error(f"Failed to get related content: {e}")
            return []

    def analyze_trends(self, time_period: str = "7d") -> Dict[str, Any]:
        """Analyze trends in analysis history"""
        try:
            from datetime import timedelta
            
            # Get analysis history for the period
            end_date = datetime.now()
            if time_period == "1d":
                start_date = end_date - timedelta(days=1)
            elif time_period == "7d":
                start_date = end_date - timedelta(days=7)
            elif time_period == "30d":
                start_date = end_date - timedelta(days=30)
            else:
                start_date = end_date - timedelta(days=7)
            
            # Query database for analysis results in period
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT analysis_type, confidence, created_at
                FROM analysis_results
                WHERE created_at BETWEEN ? AND ?
                ORDER BY created_at
            ''', (start_date.isoformat(), end_date.isoformat()))
            
            results = cursor.fetchall()
            
            # Analyze trends
            trend_analysis = {
                'period': time_period,
                'total_analyses': len(results),
                'analysis_types': {},
                'confidence_trend': [],
                'peak_usage_times': []
            }
            
            for analysis_type, confidence, created_at in results:
                if analysis_type not in trend_analysis['analysis_types']:
                    trend_analysis['analysis_types'][analysis_type] = 0
                trend_analysis['analysis_types'][analysis_type] += 1
                trend_analysis['confidence_trend'].append(confidence)
            
            return trend_analysis
            
        except Exception as e:
            self.logger.error(f"Failed to analyze trends: {e}")
            return {"error": str(e)}

    def get_smart_suggestions(self, context: str = None) -> List[str]:
        """Get smart suggestions based on context and history"""
        try:
            suggestions = []
            
            # Get recent analysis types
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT analysis_type, COUNT(*) as count
                FROM analysis_results
                WHERE created_at > datetime('now', '-7 days')
                GROUP BY analysis_type
                ORDER BY count DESC
                LIMIT 5
            ''')
            
            recent_types = cursor.fetchall()
            
            # Generate suggestions based on patterns
            if recent_types:
                most_common = recent_types[0][0]
                suggestions.append(f"Continue {most_common} analysis")
                suggestions.append(f"Batch process {most_common} files")
            
            # Context-based suggestions
            if context:
                if "screen" in context.lower():
                    suggestions.append("Start screen monitoring")
                    suggestions.append("Capture specific window")
                elif "file" in context.lower():
                    suggestions.append("Search for related files")
                    suggestions.append("Batch process similar files")
                elif "text" in context.lower():
                    suggestions.append("Extract text from images")
                    suggestions.append("Analyze document structure")
            
            # General suggestions
            suggestions.extend([
                "Enable auto-analysis for new files",
                "Monitor directory for changes",
                "Create cross-references between related content",
                "Analyze usage trends"
            ])
            
            return suggestions[:5]  # Return top 5 suggestions
            
        except Exception as e:
            self.logger.error(f"Failed to get smart suggestions: {e}")
            return []

    def get_media_files(self, file_type: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get processed media files"""
        try:
            cursor = self.conn.cursor()
            if file_type:
                cursor.execute('''
                    SELECT id, file_path, file_type, metadata, created_at, processed_at, analysis_result
                    FROM media_files
                    WHERE file_type = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (file_type, limit))
            else:
                cursor.execute('''
                    SELECT id, file_path, file_type, metadata, created_at, processed_at, analysis_result
                    FROM media_files
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (limit,))
            
            files = []
            for row in cursor.fetchall():
                file_id, file_path, file_type, metadata, created_at, processed_at, analysis_result = row
                files.append({
                    'id': file_id,
                    'file_path': file_path,
                    'file_type': file_type,
                    'metadata': json.loads(metadata) if metadata else {},
                    'created_at': created_at,
                    'processed_at': processed_at,
                    'analysis_result': json.loads(analysis_result) if analysis_result else {}
                })
            
            return files
            
        except Exception as e:
            self.logger.error(f"Failed to get media files: {e}")
            return []

    def get_analysis_results(self, media_id: Optional[int] = None, analysis_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get analysis results"""
        try:
            cursor = self.conn.cursor()
            if media_id and analysis_type:
                cursor.execute('''
                    SELECT id, media_id, analysis_type, result_data, confidence, created_at
                    FROM analysis_results
                    WHERE media_id = ? AND analysis_type = ?
                    ORDER BY created_at DESC
                ''', (media_id, analysis_type))
            elif media_id:
                cursor.execute('''
                    SELECT id, media_id, analysis_type, result_data, confidence, created_at
                    FROM analysis_results
                    WHERE media_id = ?
                    ORDER BY created_at DESC
                ''', (media_id,))
            elif analysis_type:
                cursor.execute('''
                    SELECT id, media_id, analysis_type, result_data, confidence, created_at
                    FROM analysis_results
                    WHERE analysis_type = ?
                    ORDER BY created_at DESC
                ''', (analysis_type,))
            else:
                cursor.execute('''
                    SELECT id, media_id, analysis_type, result_data, confidence, created_at
                    FROM analysis_results
                    ORDER BY created_at DESC
                ''')
            
            results = []
            for row in cursor.fetchall():
                result_id, media_id, analysis_type, result_data, confidence, created_at = row
                results.append({
                    'id': result_id,
                    'media_id': media_id,
                    'analysis_type': analysis_type,
                    'result_data': json.loads(result_data),
                    'confidence': confidence,
                    'created_at': created_at
                })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to get analysis results: {e}")
            return []

    def _analyze_sentiment(self, text: str) -> str:
        """Basic sentiment analysis"""
        positive_words = ['good', 'great', 'excellent', 'amazing', 'wonderful', 'happy', 'love', 'like']
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'dislike', 'sad', 'angry', 'frustrated']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'

    def _extract_key_topics(self, text: str) -> List[str]:
        """Extract key topics from text"""
        # Simple keyword extraction
        common_words = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
        words = text.lower().split()
        keywords = [word for word in words if word not in common_words and len(word) > 3]
        
        # Count frequency
        from collections import Counter
        word_counts = Counter(keywords)
        return [word for word, count in word_counts.most_common(5)]

    def _detect_language(self, text: str) -> str:
        """Basic language detection"""
        # Simple language detection based on common words
        english_words = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for']
        spanish_words = ['el', 'la', 'y', 'o', 'pero', 'en', 'a', 'de', 'por']
        
        text_lower = text.lower()
        english_count = sum(1 for word in english_words if word in text_lower)
        spanish_count = sum(1 for word in spanish_words if word in text_lower)
        
        if english_count > spanish_count:
            return 'english'
        elif spanish_count > english_count:
            return 'spanish'
        else:
            return 'unknown'

    def _combine_multimodal_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Combine results from different modalities"""
        try:
            if not self.openai_client:
                return {"error": "OpenAI not available for combined analysis"}
            
            # Prepare combined input
            combined_input = "Analyze the following multimodal data:\n\n"
            
            if 'image' in results and 'ai_analysis' in results['image']:
                combined_input += f"Image Analysis: {results['image']['ai_analysis']}\n\n"
            
            if 'audio' in results and 'transcription' in results['audio']:
                combined_input += f"Audio Transcription: {results['audio']['transcription']}\n\n"
            
            if 'text' in results and 'ai_analysis' in results['text']:
                combined_input += f"Text Analysis: {results['text']['ai_analysis']}\n\n"
            
            # Get combined analysis
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "user",
                        "content": f"{combined_input}Provide a comprehensive analysis that combines all this information."
                    }
                ],
                max_tokens=400
            )
            
            return {
                'combined_analysis': response.choices[0].message.content,
                'modalities_used': list(results.keys())
            }
            
        except Exception as e:
            self.logger.error(f"Failed to combine multimodal results: {e}")
            return {"error": str(e)}

    def _background_processing(self):
        """Background processing thread"""
        while self.processing_active:
            try:
                # Process queued items
                if self.image_queue:
                    image_path = self.image_queue.pop(0)
                    self.process_image(image_path)
                
                if self.audio_queue:
                    audio_path = self.audio_queue.pop(0)
                    self.process_audio(audio_path)
                
                if self.text_queue:
                    text = self.text_queue.pop(0)
                    self.process_text(text)
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                self.logger.error(f"Background processing error: {e}")
                time.sleep(5)

    def handle_voice_command(self, cmd: str) -> str:
        """Handle voice commands for multimodal features"""
        cmd = cmd.lower()
        
        # Basic capture commands
        if "capture image" in cmd or "take photo" in cmd:
            image_path = self.capture_image()
            if image_path:
                return f"Image captured: {image_path}"
            else:
                return "Failed to capture image. Please check camera."
        
        elif "record audio" in cmd or "start recording" in cmd:
            # Extract duration if specified
            duration = 5
            if "for" in cmd:
                try:
                    duration_text = cmd.split("for")[1].split()[0]
                    duration = int(duration_text)
                except:
                    pass
            
            audio_path = self.record_audio(duration)
            if audio_path:
                return f"Audio recorded for {duration} seconds: {audio_path}"
            else:
                return "Failed to record audio. Please check microphone."
        
        # Desktop screen capture commands
        elif "capture screen" in cmd or "screenshot" in cmd:
            screen_path = self.capture_screen()
            if screen_path:
                return f"Screen captured: {screen_path}"
            else:
                return "Failed to capture screen."
        
        elif "capture window" in cmd:
            # Extract window title if specified
            window_title = None
            if "window" in cmd:
                parts = cmd.split("window")
                if len(parts) > 1:
                    window_title = parts[1].strip()
            
            window_path = self.capture_window(window_title)
            if window_path:
                return f"Window captured: {window_path}"
            else:
                return "Failed to capture window."
        
        # Screen monitoring commands
        elif "start screen monitoring" in cmd or "monitor screen" in cmd:
            if self.start_screen_monitoring():
                return "Screen monitoring started. I'll track changes automatically."
            else:
                return "Failed to start screen monitoring."
        
        elif "stop screen monitoring" in cmd:
            self.stop_screen_monitoring()
            return "Screen monitoring stopped."
        
        # File monitoring commands
        elif "start file monitoring" in cmd or "monitor files" in cmd:
            # Default to current media directory
            if self.start_file_monitoring(str(self.media_dir)):
                return f"File monitoring started for {self.media_dir}"
            else:
                return "Failed to start file monitoring."
        
        elif "stop file monitoring" in cmd:
            self.stop_file_monitoring()
            return "File monitoring stopped."
        
        # Auto-analysis commands
        elif "enable auto analysis" in cmd or "auto analyze" in cmd:
            self.enable_auto_analysis(True)
            return "Auto-analysis enabled. New files will be analyzed automatically."
        
        elif "disable auto analysis" in cmd:
            self.enable_auto_analysis(False)
            return "Auto-analysis disabled."
        
        # Batch processing commands
        elif "batch process" in cmd or "process multiple files" in cmd:
            # This would need file paths from context
            return "Please specify files to batch process. Say 'batch process [file1, file2, ...]'"
        
        # File search commands
        elif "search files" in cmd or "find files" in cmd:
            # Extract search query
            if "search files" in cmd:
                query = cmd.split("search files")[1].strip()
            elif "find files" in cmd:
                query = cmd.split("find files")[1].strip()
            else:
                query = ""
            
            if query:
                files = self.search_files(query)
                if files:
                    return f"Found {len(files)} files matching '{query}'"
                else:
                    return f"No files found matching '{query}'"
            else:
                return "Please specify search query. Say 'search files [query]'"
        
        # Analysis commands
        elif "analyze image" in cmd:
            # This would need image path from context
            return "Please specify the image to analyze. Say 'analyze image [path]'"
        
        elif "transcribe audio" in cmd:
            # This would need audio path from context
            return "Please specify the audio file to transcribe. Say 'transcribe audio [path]'"
        
        # Cross-reference commands
        elif "create cross reference" in cmd or "link content" in cmd:
            return "Please specify source and target content IDs to create cross-reference."
        
        elif "get related content" in cmd:
            return "Please specify content ID to find related content."
        
        # Trend analysis commands
        elif "analyze trends" in cmd or "usage trends" in cmd:
            trends = self.analyze_trends()
            if "error" not in trends:
                return f"Trend analysis: {trends['total_analyses']} analyses in last 7 days"
            else:
                return "Failed to analyze trends."
        
        # Smart suggestions
        elif "get suggestions" in cmd or "smart suggestions" in cmd:
            suggestions = self.get_smart_suggestions()
            if suggestions:
                return f"Suggestions: {', '.join(suggestions[:3])}"
            else:
                return "No suggestions available."
        
        # TTS commands
        elif "speak" in cmd or "say" in cmd:
            # Extract text to speak
            text_start = cmd.find("speak") + 6 if "speak" in cmd else cmd.find("say") + 4
            text = cmd[text_start:].strip()
            if text:
                if self.speak_text(text):
                    return f"Spoke: {text}"
                else:
                    return "Failed to speak text."
            else:
                return "Please specify what to speak. Say 'speak [text]'"
        
        # General multimodal commands
        elif "multimodal analysis" in cmd:
            return "To perform multimodal analysis, I need image, audio, or text input. Please specify what to analyze."
        
        elif "desktop features" in cmd or "available features" in cmd:
            return "Desktop features: screen capture, window capture, file monitoring, auto-analysis, batch processing, file search, cross-references, trend analysis, and smart suggestions."
        
        else:
            return "Multimodal command not recognized. Try 'capture screen', 'start monitoring', 'enable auto analysis', 'search files', or 'analyze trends'."

    def stop_processing(self):
        """Stop background processing"""
        self.processing_active = False

    def close(self):
        """Close database connection and stop processing"""
        self.stop_processing()
        if self.conn:
            self.conn.close()

# Voice command helper functions
def format_media_info(media: Dict[str, Any]) -> str:
    """Format media information for voice output"""
    file_type = media.get('file_type', 'unknown')
    created_at = media.get('created_at', 'Unknown')
    processed = 'Yes' if media.get('processed_at') else 'No'
    
    return f"{file_type.capitalize()} file created {created_at}, processed: {processed}"

def format_analysis_info(analysis: Dict[str, Any]) -> str:
    """Format analysis information for voice output"""
    analysis_type = analysis.get('analysis_type', 'unknown')
    confidence = analysis.get('confidence', 0)
    created_at = analysis.get('created_at', 'Unknown')
    
    return f"{analysis_type} analysis with {confidence:.1f} confidence, created {created_at}"


# File monitoring handler class
class MultimodalFileHandler(FileSystemEventHandler):
    def __init__(self, multimodal_assistant):
        self.multimodal_assistant = multimodal_assistant
        self.logger = logging.getLogger(__name__)
    
    def on_created(self, event):
        """Handle file creation events"""
        if not event.is_directory:
            try:
                file_path = event.src_path
                self.logger.info(f"New file detected: {file_path}")
                
                # Auto-analyze if enabled
                if self.multimodal_assistant.auto_analysis_enabled:
                    self._auto_analyze_file(file_path)
                
                # Record event
                self._record_file_event(file_path, "created")
                
            except Exception as e:
                self.logger.error(f"Error handling file creation: {e}")
    
    def on_modified(self, event):
        """Handle file modification events"""
        if not event.is_directory:
            try:
                file_path = event.src_path
                self.logger.info(f"File modified: {file_path}")
                
                # Auto-analyze if enabled
                if self.multimodal_assistant.auto_analysis_enabled:
                    self._auto_analyze_file(file_path)
                
                # Record event
                self._record_file_event(file_path, "modified")
                
            except Exception as e:
                self.logger.error(f"Error handling file modification: {e}")
    
    def on_deleted(self, event):
        """Handle file deletion events"""
        if not event.is_directory:
            try:
                file_path = event.src_path
                self.logger.info(f"File deleted: {file_path}")
                
                # Record event
                self._record_file_event(file_path, "deleted")
                
            except Exception as e:
                self.logger.error(f"Error handling file deletion: {e}")
    
    def _auto_analyze_file(self, file_path: str):
        """Automatically analyze new/modified files"""
        try:
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                result = self.multimodal_assistant.process_image(file_path, "general")
                self.logger.info(f"Auto-analyzed image: {file_path}")
                
            elif file_ext in ['.mp3', '.wav', '.m4a', '.flac']:
                result = self.multimodal_assistant.process_audio(file_path, "transcription")
                self.logger.info(f"Auto-analyzed audio: {file_path}")
                
            elif file_ext in ['.txt', '.md', '.log']:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text_content = f.read()
                    result = self.multimodal_assistant.process_text(text_content, "general")
                    self.logger.info(f"Auto-analyzed text: {file_path}")
                except Exception as e:
                    self.logger.error(f"Failed to read text file: {e}")
                    
        except Exception as e:
            self.logger.error(f"Failed to auto-analyze file {file_path}: {e}")
    
    def _record_file_event(self, file_path: str, event_type: str):
        """Record file event in database"""
        try:
            with self.multimodal_assistant.conn:
                self.multimodal_assistant.conn.execute('''
                    INSERT INTO file_events (file_path, event_type, auto_analyzed, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (file_path, event_type, self.multimodal_assistant.auto_analysis_enabled, datetime.now()))
                
        except Exception as e:
            self.logger.error(f"Failed to record file event: {e}") 