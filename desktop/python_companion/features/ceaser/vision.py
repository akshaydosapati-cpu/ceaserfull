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

# Try to import computer vision libraries
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("[INFO] OpenCV not available for computer vision features.")

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[INFO] PIL not available for image processing.")

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
    
    # Configure Tesseract path for Windows
    possible_paths = [
        "C:/Program Files/Tesseract-OCR/tesseract.exe",
        "C:/Program Files (x86)/Tesseract-OCR/tesseract.exe",
        "tesseract.exe"  # If in PATH
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            print(f"[INFO] Tesseract configured: {path}")
            break
    else:
        print("[WARN] Tesseract executable not found in common locations")
        
except ImportError:
    TESSERACT_AVAILABLE = False
    print("[INFO] Tesseract not available for OCR features.")

try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    print("[INFO] Face recognition not available. Install with: pip install face_recognition")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("[INFO] OpenAI not available for advanced vision analysis.")

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

# Try to import screen capture libraries
try:
    import pyautogui
    import PIL.ImageGrab
    SCREEN_CAPTURE_AVAILABLE = True
except ImportError:
    SCREEN_CAPTURE_AVAILABLE = False
    print("[INFO] Screen capture not available. Install with: pip install pyautogui pillow")

class VisionAssistant:
    def __init__(self, db_path='vision.db', images_dir='./vision_images'):
        self.db_path = db_path
        self.images_dir = Path(images_dir)
        self.images_dir.mkdir(exist_ok=True)
        
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
        
        # Known faces database
        self.known_faces = {}
        self.known_face_encodings = []
        self.known_face_names = []
        
        # Load known faces
        self._load_known_faces()
        
        # Processing queue
        self.processing_queue = []
        
        # Start background processing
        self.processing_active = True
        self.processing_thread = threading.Thread(target=self._background_processing, daemon=True)
        self.processing_thread.start()

    def _create_tables(self):
        """Create SQLite tables for vision data"""
        with self.conn:
            # Image storage
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    file_hash TEXT UNIQUE,
                    image_type TEXT,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    processed_at DATETIME
                )
            ''')
            
            # Vision analysis results
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS vision_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_id INTEGER,
                    analysis_type TEXT,
                    result_data TEXT,
                    confidence REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (image_id) REFERENCES images (id)
                )
            ''')
            
            # Known faces
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS known_faces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    face_encoding TEXT,
                    image_path TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Object detection results
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS object_detection (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_id INTEGER,
                    object_name TEXT,
                    confidence REAL,
                    bounding_box TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (image_id) REFERENCES images (id)
                )
            ''')
            
            # Create indexes
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_images_type ON images(image_type)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_analysis_type ON vision_analysis(analysis_type)')

    def _load_known_faces(self):
        """Load known faces from database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT name, face_encoding FROM known_faces')
            
            for row in cursor.fetchall():
                name, encoding_str = row
                encoding = np.array(json.loads(encoding_str))
                self.known_faces[name] = encoding
                self.known_face_encodings.append(encoding)
                self.known_face_names.append(name)
            
            self.logger.info(f"Loaded {len(self.known_faces)} known faces")
            
        except Exception as e:
            self.logger.error(f"Failed to load known faces: {e}")

    def add_known_face(self, name: str, image_path: str) -> bool:
        """Add a new known face"""
        try:
            if not FACE_RECOGNITION_AVAILABLE:
                return False
            
            # Load image
            image = face_recognition.load_image_file(image_path)
            face_encodings = face_recognition.face_encodings(image)
            
            if not face_encodings:
                self.logger.error("No face found in image")
                return False
            
            # Use the first face found
            face_encoding = face_encodings[0]
            
            # Store in database
            with self.conn:
                self.conn.execute('''
                    INSERT INTO known_faces (name, face_encoding, image_path)
                    VALUES (?, ?, ?)
                ''', (name, json.dumps(face_encoding.tolist()), image_path))
            
            # Add to memory
            self.known_faces[name] = face_encoding
            self.known_face_encodings.append(face_encoding)
            self.known_face_names.append(name)
            
            self.logger.info(f"Added known face: {name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add known face: {e}")
            return False

    def detect_faces(self, image_path: str) -> Dict[str, Any]:
        """Detect faces in an image"""
        try:
            if not FACE_RECOGNITION_AVAILABLE:
                return {"error": "Face recognition not available"}
            
            # Load image
            image = face_recognition.load_image_file(image_path)
            
            # Find face locations
            face_locations = face_recognition.face_locations(image)
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            results = {
                'face_count': len(face_locations),
                'faces': []
            }
            
            # Process each face
            for i, (face_location, face_encoding) in enumerate(zip(face_locations, face_encodings)):
                face_info = {
                    'face_id': i,
                    'location': face_location,
                    'known_person': 'Unknown'
                }
                
                # Check if face matches known faces
                if self.known_face_encodings:
                    matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding)
                    face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
                    
                    if True in matches:
                        best_match_index = np.argmin(face_distances)
                        if matches[best_match_index]:
                            face_info['known_person'] = self.known_face_names[best_match_index]
                            face_info['confidence'] = 1 - face_distances[best_match_index]
                
                results['faces'].append(face_info)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to detect faces: {e}")
            return {"error": str(e)}

    def recognize_objects(self, image_path: str) -> Dict[str, Any]:
        """Recognize objects in an image"""
        try:
            if not CV2_AVAILABLE:
                return {"error": "OpenCV not available"}
            
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                return {"error": "Could not load image"}
            
            # Convert to RGB for processing
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Basic object detection using color and shape analysis
            objects = []
            
            # Convert to HSV for color detection
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # Detect common colors
            color_ranges = {
                'red': ([0, 100, 100], [10, 255, 255]),
                'green': ([40, 100, 100], [80, 255, 255]),
                'blue': ([100, 100, 100], [130, 255, 255]),
                'yellow': ([20, 100, 100], [30, 255, 255])
            }
            
            for color_name, (lower, upper) in color_ranges.items():
                mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for contour in contours:
                    if cv2.contourArea(contour) > 1000:  # Minimum area
                        x, y, w, h = cv2.boundingRect(contour)
                        objects.append({
                            'type': f'{color_name} object',
                            'confidence': 0.7,
                            'bounding_box': [x, y, w, h],
                            'area': cv2.contourArea(contour)
                        })
            
            # Advanced object detection with OpenAI if available
            if self.openai_client:
                try:
                    with open(image_path, "rb") as image_file:
                        response = self.openai_client.chat.completions.create(
                            model="gpt-4-vision-preview",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": "List all objects you can see in this image. For each object, provide: 1) Object name, 2) Location (top-left, center, bottom-right, etc.), 3) Approximate size (small, medium, large), 4) Color if visible."},
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
                    
                    ai_objects = response.choices[0].message.content
                    objects.append({
                        'type': 'AI Analysis',
                        'description': ai_objects,
                        'confidence': 0.9
                    })
                    
                except Exception as e:
                    self.logger.error(f"OpenAI object detection failed: {e}")
            
            return {
                'object_count': len(objects),
                'objects': objects
            }
            
        except Exception as e:
            self.logger.error(f"Failed to recognize objects: {e}")
            return {"error": str(e)}

    def extract_text(self, image_path: str) -> Dict[str, Any]:
        """Extract text from image using OCR"""
        try:
            if not TESSERACT_AVAILABLE:
                return {"error": "Tesseract OCR not available"}
            
            # Load image
            image = Image.open(image_path)
            
            # Preprocess image for better OCR
            # Convert to grayscale
            gray_image = image.convert('L')
            
            # Apply filters to improve text recognition
            enhanced_image = gray_image.filter(ImageFilter.EDGE_ENHANCE)
            
            # Extract text
            text = pytesseract.image_to_string(enhanced_image)
            
            # Get additional information
            data = pytesseract.image_to_data(enhanced_image, output_type=pytesseract.Output.DICT)
            
            # Extract word-level information
            words = []
            for i in range(len(data['text'])):
                if data['conf'][i] > 0:  # Only include words with confidence > 0
                    words.append({
                        'text': data['text'][i],
                        'confidence': data['conf'][i],
                        'bbox': (data['left'][i], data['top'][i], data['width'][i], data['height'][i])
                    })
            
            # Advanced text extraction with OpenAI if available
            ai_text_analysis = None
            if self.openai_client and text.strip():
                try:
                    with open(image_path, "rb") as image_file:
                        response = self.openai_client.chat.completions.create(
                            model="gpt-4-vision-preview",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": "Extract and analyze all text in this image. Provide: 1) All visible text, 2) Text type (document, sign, label, etc.), 3) Key information extracted, 4) Any important details or context."},
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:image/jpeg;base64,{base64.b64encode(image_file.read()).decode('utf-8')}"
                                            }
                                        }
                                    ]
                                }
                            ],
                            max_tokens=400
                        )
                    
                    ai_text_analysis = response.choices[0].message.content
                    
                except Exception as e:
                    self.logger.error(f"OpenAI text analysis failed: {e}")
            
            return {
                'extracted_text': text.strip(),
                'word_count': len(words),
                'words': words,
                'ai_analysis': ai_text_analysis,
                'confidence': np.mean([word['confidence'] for word in words]) if words else 0
            }
            
        except Exception as e:
            self.logger.error(f"Failed to extract text: {e}")
            return {"error": str(e)}

    def analyze_image(self, image_path: str, analysis_type: str = "comprehensive") -> Dict[str, Any]:
        """Comprehensive image analysis"""
        try:
            # Store image in database
            with open(image_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO images (file_path, file_hash, image_type, metadata)
                    VALUES (?, ?, ?, ?)
                ''', (image_path, file_hash, analysis_type, json.dumps({'analysis_type': analysis_type})))
                
                image_id = cursor.lastrowid
                if not image_id:
                    cursor.execute('SELECT id FROM images WHERE file_hash = ?', (file_hash,))
                    image_id = cursor.fetchone()[0]
            
            # Perform analysis based on type
            results = {
                'image_id': image_id,
                'file_path': image_path,
                'analysis_type': analysis_type,
                'timestamp': datetime.now().isoformat()
            }
            
            if analysis_type in ["faces", "comprehensive"]:
                face_results = self.detect_faces(image_path)
                results['face_analysis'] = face_results
                
                # Store face analysis results
                with self.conn:
                    self.conn.execute('''
                        INSERT INTO vision_analysis (image_id, analysis_type, result_data, confidence)
                        VALUES (?, ?, ?, ?)
                    ''', (image_id, 'face_detection', json.dumps(face_results), 0.8))
            
            if analysis_type in ["objects", "comprehensive"]:
                object_results = self.recognize_objects(image_path)
                results['object_analysis'] = object_results
                
                # Store object detection results
                with self.conn:
                    self.conn.execute('''
                        INSERT INTO vision_analysis (image_id, analysis_type, result_data, confidence)
                        VALUES (?, ?, ?, ?)
                    ''', (image_id, 'object_detection', json.dumps(object_results), 0.7))
                
                # Store individual objects
                if 'objects' in object_results:
                    for obj in object_results['objects']:
                        if 'bounding_box' in obj:
                            self.conn.execute('''
                                INSERT INTO object_detection (image_id, object_name, confidence, bounding_box)
                                VALUES (?, ?, ?, ?)
                            ''', (image_id, obj['type'], obj.get('confidence', 0.5), json.dumps(obj['bounding_box'])))
            
            if analysis_type in ["text", "comprehensive"]:
                text_results = self.extract_text(image_path)
                results['text_analysis'] = text_results
                
                # Store text analysis results
                with self.conn:
                    self.conn.execute('''
                        INSERT INTO vision_analysis (image_id, analysis_type, result_data, confidence)
                        VALUES (?, ?, ?, ?)
                    ''', (image_id, 'text_extraction', json.dumps(text_results), text_results.get('confidence', 0.5)))
            
            # Update image as processed
            with self.conn:
                self.conn.execute('''
                    UPDATE images SET processed_at = CURRENT_TIMESTAMP WHERE id = ?
                ''', (image_id,))
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to analyze image: {e}")
            return {"error": str(e)}

    def capture_and_analyze(self, analysis_type: str = "comprehensive", capture_type: str = "camera") -> Dict[str, Any]:
        """Capture image and analyze it immediately"""
        try:
            if capture_type == "screen":
                return self.capture_screen_and_analyze(analysis_type)
            elif capture_type == "file":
                return self.analyze_file_and_analyze(analysis_type)
            else:
                return self.capture_camera_and_analyze(analysis_type)
            
        except Exception as e:
            self.logger.error(f"Failed to capture and analyze: {e}")
            return {"error": str(e)}

    def capture_camera_and_analyze(self, analysis_type: str = "comprehensive") -> Dict[str, Any]:
        """Capture image from camera and analyze it"""
        try:
            if not CV2_AVAILABLE:
                return {"error": "OpenCV not available for image capture"}
            
            # Capture image
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return {"error": "Could not open camera"}
            
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                return {"error": "Could not capture image"}
            
            # Save captured image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_path = str(self.images_dir / f"camera_{timestamp}.jpg")
            cv2.imwrite(image_path, frame)
            
            # Analyze the captured image
            return self.analyze_image(image_path, analysis_type)
            
        except Exception as e:
            self.logger.error(f"Failed to capture camera and analyze: {e}")
            return {"error": str(e)}

    def capture_screen_and_analyze(self, analysis_type: str = "comprehensive") -> Dict[str, Any]:
        """Capture screen and analyze it"""
        try:
            if not SCREEN_CAPTURE_AVAILABLE:
                return {"error": "Screen capture not available"}
            
            # Capture full screen
            screenshot = PIL.ImageGrab.grab()
            
            # Save captured image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_path = str(self.images_dir / f"screen_{timestamp}.png")
            screenshot.save(image_path)
            
            # Analyze the captured image
            return self.analyze_image(image_path, analysis_type)
            
        except Exception as e:
            self.logger.error(f"Failed to capture screen and analyze: {e}")
            return {"error": str(e)}

    def capture_window_and_analyze(self, window_title: str = None, analysis_type: str = "comprehensive") -> Dict[str, Any]:
        """Capture specific window and analyze it"""
        try:
            if not SCREEN_CAPTURE_AVAILABLE:
                return {"error": "Screen capture not available"}
            
            # Capture specific window if title provided
            if window_title:
                try:
                    window = pyautogui.getWindowsWithTitle(window_title)
                    if window:
                        window[0].activate()
                        time.sleep(0.5)  # Wait for window to activate
                        screenshot = pyautogui.screenshot(region=window[0].box)
                    else:
                        return {"error": f"Window '{window_title}' not found"}
                except Exception as e:
                    self.logger.error(f"Failed to capture window: {e}")
                    return {"error": f"Failed to capture window: {e}"}
            else:
                # Capture active window
                screenshot = pyautogui.screenshot()
            
            # Save captured image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_path = str(self.images_dir / f"window_{timestamp}.png")
            screenshot.save(image_path)
            
            # Analyze the captured image
            return self.analyze_image(image_path, analysis_type)
            
        except Exception as e:
            self.logger.error(f"Failed to capture window and analyze: {e}")
            return {"error": str(e)}

    def analyze_file_and_analyze(self, analysis_type: str = "comprehensive", file_path: str = None) -> Dict[str, Any]:
        """Analyze existing image file"""
        try:
            if not file_path:
                # Find latest image file in images directory
                image_files = list(self.images_dir.glob("*.jpg")) + list(self.images_dir.glob("*.png"))
                if not image_files:
                    return {"error": "No image files found"}
                
                # Get most recent file
                file_path = str(max(image_files, key=os.path.getctime))
            
            if not os.path.exists(file_path):
                return {"error": f"File not found: {file_path}"}
            
            # Analyze the file
            return self.analyze_image(file_path, analysis_type)
            
        except Exception as e:
            self.logger.error(f"Failed to analyze file: {e}")
            return {"error": str(e)}

    def get_available_windows(self) -> List[str]:
        """Get list of available windows"""
        try:
            if not SCREEN_CAPTURE_AVAILABLE:
                return []
            
            windows = pyautogui.getAllWindows()
            return [window.title for window in windows if window.title]
            
        except Exception as e:
            self.logger.error(f"Failed to get windows: {e}")
            return []

    def get_screen_info(self) -> Dict[str, Any]:
        """Get screen information"""
        try:
            if not SCREEN_CAPTURE_AVAILABLE:
                return {"error": "Screen capture not available"}
            
            screen_width, screen_height = pyautogui.size()
            mouse_x, mouse_y = pyautogui.position()
            
            return {
                "screen_width": screen_width,
                "screen_height": screen_height,
                "mouse_position": (mouse_x, mouse_y),
                "available_windows": self.get_available_windows()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get screen info: {e}")
            return {"error": str(e)}

    def get_known_faces(self) -> List[Dict[str, Any]]:
        """Get list of known faces"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, name, image_path, created_at
                FROM known_faces
                ORDER BY name
            ''')
            
            faces = []
            for row in cursor.fetchall():
                face_id, name, image_path, created_at = row
                faces.append({
                    'id': face_id,
                    'name': name,
                    'image_path': image_path,
                    'created_at': created_at
                })
            
            return faces
            
        except Exception as e:
            self.logger.error(f"Failed to get known faces: {e}")
            return []

    def get_analysis_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get analysis history"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT i.file_path, i.image_type, va.analysis_type, va.confidence, va.created_at
                FROM images i
                JOIN vision_analysis va ON i.id = va.image_id
                ORDER BY va.created_at DESC
                LIMIT ?
            ''', (limit,))
            
            history = []
            for row in cursor.fetchall():
                file_path, image_type, analysis_type, confidence, created_at = row
                history.append({
                    'file_path': file_path,
                    'image_type': image_type,
                    'analysis_type': analysis_type,
                    'confidence': confidence,
                    'created_at': created_at
                })
            
            return history
            
        except Exception as e:
            self.logger.error(f"Failed to get analysis history: {e}")
            return []

    def _background_processing(self):
        """Background processing thread"""
        while self.processing_active:
            try:
                # Process queued items
                if self.processing_queue:
                    task = self.processing_queue.pop(0)
                    if task['type'] == 'analyze':
                        self.analyze_image(task['image_path'], task['analysis_type'])
                    elif task['type'] == 'add_face':
                        self.add_known_face(task['name'], task['image_path'])
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                self.logger.error(f"Background processing error: {e}")
                time.sleep(5)

    def handle_voice_command(self, cmd: str) -> str:
        """Handle voice commands for vision features"""
        cmd = cmd.lower()
        
        # Camera capture commands
        if "capture and analyze" in cmd or "take photo and analyze" in cmd:
            analysis_type = "comprehensive"
            if "faces" in cmd:
                analysis_type = "faces"
            elif "objects" in cmd:
                analysis_type = "objects"
            elif "text" in cmd:
                analysis_type = "text"
            
            result = self.capture_and_analyze(analysis_type, "camera")
            if "error" not in result:
                return f"Camera image captured and analyzed. Found {result.get('face_analysis', {}).get('face_count', 0)} faces, {result.get('object_analysis', {}).get('object_count', 0)} objects."
            else:
                return f"Failed to capture and analyze: {result['error']}"
        
        # Screen capture commands
        elif "capture screen" in cmd or "screenshot" in cmd or "screen capture" in cmd:
            analysis_type = "comprehensive"
            if "text" in cmd:
                analysis_type = "text"
            elif "objects" in cmd:
                analysis_type = "objects"
            
            result = self.capture_and_analyze(analysis_type, "screen")
            if "error" not in result:
                text = result.get('text_analysis', {}).get('extracted_text', '')
                if text:
                    return f"Screen captured and analyzed. Extracted text: {text[:100]}..."
                else:
                    return "Screen captured and analyzed. No text found."
            else:
                return f"Failed to capture screen: {result['error']}"
        
        # Window capture commands
        elif "capture window" in cmd or "window capture" in cmd:
            # Extract window title from command
            window_title = None
            if "window" in cmd:
                parts = cmd.split("window")
                if len(parts) > 1:
                    window_title = parts[1].strip()
            
            result = self.capture_window_and_analyze(window_title, "text")
            if "error" not in result:
                text = result.get('text_analysis', {}).get('extracted_text', '')
                if text:
                    return f"Window captured and analyzed. Extracted text: {text[:100]}..."
                else:
                    return "Window captured and analyzed. No text found."
            else:
                return f"Failed to capture window: {result['error']}"
        
        # File analysis commands
        elif "analyze file" in cmd or "read file" in cmd:
            result = self.capture_and_analyze("text", "file")
            if "error" not in result:
                text = result.get('text_analysis', {}).get('extracted_text', '')
                if text:
                    return f"File analyzed. Extracted text: {text[:100]}..."
                else:
                    return "File analyzed. No text found."
            else:
                return f"Failed to analyze file: {result['error']}"
        
        # Specific analysis commands
        elif "detect faces" in cmd or "find faces" in cmd:
            result = self.capture_and_analyze("faces", "camera")
            if "error" not in result:
                face_count = result.get('face_analysis', {}).get('face_count', 0)
                return f"Detected {face_count} faces in the image."
            else:
                return f"Failed to detect faces: {result['error']}"
        
        elif "recognize objects" in cmd or "find objects" in cmd:
            result = self.capture_and_analyze("objects", "camera")
            if "error" not in result:
                object_count = result.get('object_analysis', {}).get('object_count', 0)
                return f"Recognized {object_count} objects in the image."
            else:
                return f"Failed to recognize objects: {result['error']}"
        
        elif "extract text" in cmd or "read text" in cmd:
            # Default to screen capture for text extraction
            result = self.capture_and_analyze("text", "screen")
            if "error" not in result:
                text = result.get('text_analysis', {}).get('extracted_text', '')
                if text:
                    return f"Extracted text: {text[:100]}..."
                else:
                    return "No text found in the image."
            else:
                return f"Failed to extract text: {result['error']}"
        
        # Screen information commands
        elif "screen info" in cmd or "screen information" in cmd:
            info = self.get_screen_info()
            if "error" not in info:
                return f"Screen size: {info['screen_width']}x{info['screen_height']}. Mouse position: {info['mouse_position']}. Available windows: {len(info['available_windows'])}"
            else:
                return f"Failed to get screen info: {info['error']}"
        
        elif "list windows" in cmd or "available windows" in cmd:
            windows = self.get_available_windows()
            if windows:
                return f"Available windows: {', '.join(windows[:5])}..."
            else:
                return "No windows found."
        
        # Face management commands
        elif "add face" in cmd or "learn face" in cmd:
            return "To add a face, I need the person's name and an image. Please specify the name and provide an image."
        
        elif "known faces" in cmd:
            faces = self.get_known_faces()
            if faces:
                names = [face['name'] for face in faces]
                return f"Known faces: {', '.join(names)}"
            else:
                return "No known faces stored."
        
        elif "analysis history" in cmd:
            history = self.get_analysis_history(limit=5)
            if history:
                return f"You have {len(history)} recent image analyses. Check the app for details."
            else:
                return "No analysis history available."
        
        else:
            return "Vision command not recognized. Try 'capture screen', 'capture window', 'extract text', 'detect faces', 'recognize objects', or 'screen info'."

    def stop_processing(self):
        """Stop background processing"""
        self.processing_active = False

    def close(self):
        """Close database connection and stop processing"""
        self.stop_processing()
        if self.conn:
            self.conn.close()

# Voice command helper functions
def format_face_info(face: Dict[str, Any]) -> str:
    """Format face information for voice output"""
    name = face.get('name', 'Unknown')
    created_at = face.get('created_at', 'Unknown')
    
    return f"Face '{name}' added on {created_at}"

def format_analysis_info(analysis: Dict[str, Any]) -> str:
    """Format analysis information for voice output"""
    analysis_type = analysis.get('analysis_type', 'unknown')
    confidence = analysis.get('confidence', 0)
    created_at = analysis.get('created_at', 'Unknown')
    
    return f"{analysis_type} analysis with {confidence:.1f} confidence on {created_at}" 