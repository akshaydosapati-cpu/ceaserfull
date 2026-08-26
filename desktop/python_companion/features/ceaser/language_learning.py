import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import threading
import sqlite3
from pathlib import Path
import random
import hashlib

# Try to import language learning libraries
try:
    import speech_recognition as sr
    import pyttsx3
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False
    print("[INFO] Speech recognition not available for language learning.")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("[INFO] Requests not available for language API calls.")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("[INFO] OpenAI not available for advanced language features.")

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

class LanguageLearningAssistant:
    def __init__(self, db_path='language_learning.db', lessons_dir='./language_lessons'):
        self.db_path = db_path
        self.lessons_dir = Path(lessons_dir)
        self.lessons_dir.mkdir(exist_ok=True)
        
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
        
        # Supported languages
        self.supported_languages = {
            'spanish': {
                'name': 'Spanish',
                'code': 'es',
                'difficulty': 'intermediate',
                'lessons_available': True
            },
            'french': {
                'name': 'French',
                'code': 'fr',
                'difficulty': 'intermediate',
                'lessons_available': True
            },
            'german': {
                'name': 'German',
                'code': 'de',
                'difficulty': 'advanced',
                'lessons_available': True
            },
            'italian': {
                'name': 'Italian',
                'code': 'it',
                'difficulty': 'intermediate',
                'lessons_available': True
            },
            'portuguese': {
                'name': 'Portuguese',
                'code': 'pt',
                'difficulty': 'intermediate',
                'lessons_available': True
            },
            'japanese': {
                'name': 'Japanese',
                'code': 'ja',
                'difficulty': 'advanced',
                'lessons_available': False
            },
            'chinese': {
                'name': 'Chinese',
                'code': 'zh',
                'difficulty': 'advanced',
                'lessons_available': False
            }
        }
        
        # Initialize default lessons
        self._initialize_default_lessons()

    def _create_tables(self):
        """Create SQLite tables for language learning"""
        with self.conn:
            # User progress
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS user_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT DEFAULT 'default',
                    language TEXT NOT NULL,
                    level TEXT DEFAULT 'beginner',
                    total_lessons_completed INTEGER DEFAULT 0,
                    vocabulary_words_learned INTEGER DEFAULT 0,
                    pronunciation_score REAL DEFAULT 0.0,
                    last_practice_date DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Lessons
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    language TEXT NOT NULL,
                    level TEXT NOT NULL,
                    lesson_number INTEGER,
                    title TEXT NOT NULL,
                    content TEXT,
                    vocabulary TEXT,
                    exercises TEXT,
                    cultural_notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Vocabulary
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS vocabulary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    language TEXT NOT NULL,
                    word TEXT NOT NULL,
                    translation TEXT NOT NULL,
                    part_of_speech TEXT,
                    example_sentence TEXT,
                    difficulty_level TEXT DEFAULT 'beginner',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Practice sessions
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS practice_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT DEFAULT 'default',
                    language TEXT NOT NULL,
                    session_type TEXT,
                    duration_minutes INTEGER,
                    score REAL,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Pronunciation attempts
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS pronunciation_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT DEFAULT 'default',
                    language TEXT NOT NULL,
                    word TEXT NOT NULL,
                    user_pronunciation TEXT,
                    accuracy_score REAL,
                    feedback TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_progress_language ON user_progress(language)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_lessons_language ON lessons(language)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_vocabulary_language ON vocabulary(language)')

    def _initialize_default_lessons(self):
        """Initialize default lessons for supported languages"""
        default_lessons = {
            'spanish': [
                {
                    'level': 'beginner',
                    'lesson_number': 1,
                    'title': 'Basic Greetings',
                    'content': 'Learn how to greet people in Spanish',
                    'vocabulary': {
                        'hola': 'hello',
                        'buenos días': 'good morning',
                        'buenas tardes': 'good afternoon',
                        'buenas noches': 'good night',
                        'adiós': 'goodbye',
                        'por favor': 'please',
                        'gracias': 'thank you',
                        'de nada': 'you\'re welcome'
                    },
                    'exercises': [
                        'Practice saying "hola" and "gracias"',
                        'Learn to respond to greetings',
                        'Practice basic conversation'
                    ],
                    'cultural_notes': 'In Spanish-speaking countries, it\'s common to greet with a kiss on the cheek or a handshake.'
                },
                {
                    'level': 'beginner',
                    'lesson_number': 2,
                    'title': 'Numbers 1-10',
                    'content': 'Learn to count from 1 to 10 in Spanish',
                    'vocabulary': {
                        'uno': 'one',
                        'dos': 'two',
                        'tres': 'three',
                        'cuatro': 'four',
                        'cinco': 'five',
                        'seis': 'six',
                        'siete': 'seven',
                        'ocho': 'eight',
                        'nueve': 'nine',
                        'diez': 'ten'
                    },
                    'exercises': [
                        'Practice counting from 1 to 10',
                        'Learn to ask "¿Cuántos años tienes?" (How old are you?)',
                        'Practice saying phone numbers'
                    ],
                    'cultural_notes': 'Numbers are used in many contexts, from telling time to giving your age.'
                }
            ],
            'french': [
                {
                    'level': 'beginner',
                    'lesson_number': 1,
                    'title': 'Basic Greetings',
                    'content': 'Learn how to greet people in French',
                    'vocabulary': {
                        'bonjour': 'hello/good morning',
                        'bonsoir': 'good evening',
                        'au revoir': 'goodbye',
                        's\'il vous plaît': 'please',
                        'merci': 'thank you',
                        'de rien': 'you\'re welcome',
                        'comment allez-vous?': 'how are you?',
                        'ça va': 'it\'s going well'
                    },
                    'exercises': [
                        'Practice saying "bonjour" and "merci"',
                        'Learn to ask and respond to "how are you?"',
                        'Practice formal and informal greetings'
                    ],
                    'cultural_notes': 'French people often greet with "la bise" (cheek kisses) among friends and family.'
                }
            ]
        }
        
        # Insert default lessons
        for language, lessons in default_lessons.items():
            for lesson in lessons:
                self._add_lesson(
                    language=language,
                    level=lesson['level'],
                    lesson_number=lesson['lesson_number'],
                    title=lesson['title'],
                    content=lesson['content'],
                    vocabulary=lesson['vocabulary'],
                    exercises=lesson['exercises'],
                    cultural_notes=lesson['cultural_notes']
                )

    def _add_lesson(self, language: str, level: str, lesson_number: int, title: str,
                   content: str, vocabulary: Dict[str, str], exercises: List[str],
                   cultural_notes: str) -> bool:
        """Add a lesson to the database"""
        try:
            with self.conn:
                self.conn.execute('''
                    INSERT OR IGNORE INTO lessons 
                    (language, level, lesson_number, title, content, vocabulary, exercises, cultural_notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (language, level, lesson_number, title, content, 
                     json.dumps(vocabulary), json.dumps(exercises), cultural_notes))
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to add lesson: {e}")
            return False

    def get_supported_languages(self) -> List[Dict[str, Any]]:
        """Get list of supported languages"""
        return [
            {
                'code': code,
                'name': info['name'],
                'difficulty': info['difficulty'],
                'lessons_available': info['lessons_available']
            }
            for code, info in self.supported_languages.items()
        ]

    def get_user_progress(self, user_id: str = 'default', language: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get user progress in language learning"""
        try:
            cursor = self.conn.cursor()
            if language:
                cursor.execute('''
                    SELECT language, level, total_lessons_completed, vocabulary_words_learned,
                           pronunciation_score, last_practice_date, updated_at
                    FROM user_progress
                    WHERE user_id = ? AND language = ?
                ''', (user_id, language))
            else:
                cursor.execute('''
                    SELECT language, level, total_lessons_completed, vocabulary_words_learned,
                           pronunciation_score, last_practice_date, updated_at
                    FROM user_progress
                    WHERE user_id = ?
                    ORDER BY updated_at DESC
                ''', (user_id,))
            
            progress = []
            for row in cursor.fetchall():
                language, level, lessons_completed, vocab_learned, pronunciation_score, last_practice, updated_at = row
                progress.append({
                    'language': language,
                    'level': level,
                    'lessons_completed': lessons_completed,
                    'vocabulary_learned': vocab_learned,
                    'pronunciation_score': pronunciation_score,
                    'last_practice': last_practice,
                    'updated_at': updated_at
                })
            
            return progress
            
        except Exception as e:
            self.logger.error(f"Failed to get user progress: {e}")
            return []

    def get_lessons(self, language: str, level: str = 'beginner') -> List[Dict[str, Any]]:
        """Get lessons for a specific language and level"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, lesson_number, title, content, vocabulary, exercises, cultural_notes
                FROM lessons
                WHERE language = ? AND level = ?
                ORDER BY lesson_number
            ''', (language, level))
            
            lessons = []
            for row in cursor.fetchall():
                lesson_id, lesson_number, title, content, vocabulary, exercises, cultural_notes = row
                lessons.append({
                    'id': lesson_id,
                    'lesson_number': lesson_number,
                    'title': title,
                    'content': content,
                    'vocabulary': json.loads(vocabulary),
                    'exercises': json.loads(exercises),
                    'cultural_notes': cultural_notes
                })
            
            return lessons
            
        except Exception as e:
            self.logger.error(f"Failed to get lessons: {e}")
            return []

    def get_vocabulary(self, language: str, level: str = 'beginner', limit: int = 20) -> List[Dict[str, Any]]:
        """Get vocabulary words for a language and level"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT word, translation, part_of_speech, example_sentence, difficulty_level
                FROM vocabulary
                WHERE language = ? AND difficulty_level = ?
                ORDER BY RANDOM()
                LIMIT ?
            ''', (language, level, limit))
            
            vocabulary = []
            for row in cursor.fetchall():
                word, translation, part_of_speech, example_sentence, difficulty_level = row
                vocabulary.append({
                    'word': word,
                    'translation': translation,
                    'part_of_speech': part_of_speech,
                    'example_sentence': example_sentence,
                    'difficulty_level': difficulty_level
                })
            
            return vocabulary
            
        except Exception as e:
            self.logger.error(f"Failed to get vocabulary: {e}")
            return []

    def start_lesson(self, language: str, lesson_number: int, user_id: str = 'default') -> Dict[str, Any]:
        """Start a specific lesson"""
        try:
            # Get lesson details
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, title, content, vocabulary, exercises, cultural_notes
                FROM lessons
                WHERE language = ? AND lesson_number = ?
            ''', (language, lesson_number))
            
            result = cursor.fetchone()
            if not result:
                return {"error": "Lesson not found"}
            
            lesson_id, title, content, vocabulary, exercises, cultural_notes = result
            
            lesson_data = {
                'lesson_id': lesson_id,
                'title': title,
                'content': content,
                'vocabulary': json.loads(vocabulary),
                'exercises': json.loads(exercises),
                'cultural_notes': cultural_notes,
                'session_start': datetime.now().isoformat()
            }
            
            # Record practice session
            with self.conn:
                self.conn.execute('''
                    INSERT INTO practice_sessions (user_id, language, session_type, duration_minutes)
                    VALUES (?, ?, ?, 0)
                ''', (user_id, language, f'lesson_{lesson_number}'))
            
            return lesson_data
            
        except Exception as e:
            self.logger.error(f"Failed to start lesson: {e}")
            return {"error": str(e)}

    def practice_pronunciation(self, language: str, word: str, user_id: str = 'default') -> Dict[str, Any]:
        """Practice pronunciation of a word"""
        try:
            if not SPEECH_AVAILABLE or not self.microphone:
                return {"error": "Speech recognition not available"}
            
            # Get word details
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT translation, example_sentence
                FROM vocabulary
                WHERE language = ? AND word = ?
            ''', (language, word))
            
            result = cursor.fetchone()
            if not result:
                return {"error": "Word not found in vocabulary"}
            
            translation, example_sentence = result
            
            # Speak the word for user to hear
            if self.tts_engine:
                self.tts_engine.say(word)
                self.tts_engine.runAndWait()
            
            # Listen for user pronunciation
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source)
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=3)
            
            # Recognize user pronunciation
            try:
                user_pronunciation = self.recognizer.recognize_google(audio, language=self.supported_languages[language]['code'])
                
                # Simple accuracy scoring (word similarity)
                accuracy = self._calculate_pronunciation_accuracy(word.lower(), user_pronunciation.lower())
                
                # Generate feedback
                feedback = self._generate_pronunciation_feedback(word, user_pronunciation, accuracy)
                
                # Store attempt
                with self.conn:
                    self.conn.execute('''
                        INSERT INTO pronunciation_attempts 
                        (user_id, language, word, user_pronunciation, accuracy_score, feedback)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user_id, language, word, user_pronunciation, accuracy, feedback))
                
                return {
                    'word': word,
                    'translation': translation,
                    'user_pronunciation': user_pronunciation,
                    'accuracy_score': accuracy,
                    'feedback': feedback,
                    'example_sentence': example_sentence
                }
                
            except sr.UnknownValueError:
                return {"error": "Could not understand pronunciation. Please try again."}
            except sr.RequestError as e:
                return {"error": f"Speech recognition service error: {e}"}
            
        except Exception as e:
            self.logger.error(f"Failed to practice pronunciation: {e}")
            return {"error": str(e)}

    def translate_text(self, text: str, target_language: str, source_language: str = 'en') -> Dict[str, Any]:
        """Translate text to target language"""
        try:
            if not REQUESTS_AVAILABLE:
                return {"error": "Translation service not available"}
            
            # Use Google Translate API (free tier)
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                'client': 'gtx',
                'sl': source_language,
                'tl': target_language,
                'dt': 't',
                'q': text
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                translation = ''.join([part[0] for part in data[0] if part[0]])
                
                return {
                    'original_text': text,
                    'translated_text': translation,
                    'source_language': source_language,
                    'target_language': target_language
                }
            else:
                return {"error": "Translation service unavailable"}
            
        except Exception as e:
            self.logger.error(f"Failed to translate text: {e}")
            return {"error": str(e)}

    def generate_conversation_practice(self, language: str, topic: str = 'general', level: str = 'beginner') -> Dict[str, Any]:
        """Generate conversation practice scenarios"""
        try:
            if not self.openai_client:
                return {"error": "AI not available for conversation generation"}
            
            prompt = f"""
            Generate a simple conversation practice scenario in {language} for a {level} level learner.
            Topic: {topic}
            
            Include:
            1. A brief scenario description
            2. 5-8 simple dialogue exchanges
            3. Key vocabulary words used
            4. Cultural notes if relevant
            
            Format as JSON with keys: scenario, dialogue, vocabulary, cultural_notes
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )
            
            try:
                conversation_data = json.loads(response.choices[0].message.content)
                return conversation_data
            except json.JSONDecodeError:
                return {"error": "Failed to parse conversation data"}
            
        except Exception as e:
            self.logger.error(f"Failed to generate conversation: {e}")
            return {"error": str(e)}

    def complete_lesson(self, language: str, lesson_number: int, user_id: str = 'default', score: float = 0.8) -> bool:
        """Mark a lesson as completed"""
        try:
            with self.conn:
                # Update user progress
                self.conn.execute('''
                    INSERT OR REPLACE INTO user_progress 
                    (user_id, language, total_lessons_completed, updated_at)
                    VALUES (
                        ?, ?, 
                        COALESCE((SELECT total_lessons_completed FROM user_progress WHERE user_id = ? AND language = ?), 0) + 1,
                        CURRENT_TIMESTAMP
                    )
                ''', (user_id, language, user_id, language))
                
                # Update practice session
                self.conn.execute('''
                    UPDATE practice_sessions 
                    SET duration_minutes = 15, score = ?
                    WHERE user_id = ? AND language = ? AND session_type = ?
                    ORDER BY created_at DESC LIMIT 1
                ''', (score, user_id, language, f'lesson_{lesson_number}'))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to complete lesson: {e}")
            return False

    def get_learning_recommendations(self, user_id: str = 'default') -> List[Dict[str, Any]]:
        """Get personalized learning recommendations"""
        try:
            recommendations = []
            
            # Get user progress
            progress = self.get_user_progress(user_id)
            
            for prog in progress:
                language = prog['language']
                level = prog['level']
                lessons_completed = prog['lessons_completed']
                
                # Recommend next lesson
                next_lesson = lessons_completed + 1
                recommendations.append({
                    'type': 'next_lesson',
                    'language': language,
                    'message': f'Continue with lesson {next_lesson} in {language}',
                    'priority': 'high'
                })
                
                # Recommend vocabulary practice if needed
                if prog['vocabulary_learned'] < 50:
                    recommendations.append({
                        'type': 'vocabulary_practice',
                        'language': language,
                        'message': f'Practice vocabulary in {language}',
                        'priority': 'medium'
                    })
                
                # Recommend pronunciation practice if score is low
                if prog['pronunciation_score'] < 0.7:
                    recommendations.append({
                        'type': 'pronunciation_practice',
                        'language': language,
                        'message': f'Practice pronunciation in {language}',
                        'priority': 'medium'
                    })
            
            # Recommend new languages if user has mastered current ones
            if len(progress) < 3:
                available_languages = [lang for lang in self.supported_languages.keys() 
                                     if lang not in [p['language'] for p in progress]]
                if available_languages:
                    recommendations.append({
                        'type': 'new_language',
                        'language': available_languages[0],
                        'message': f'Try learning {self.supported_languages[available_languages[0]]["name"]}',
                        'priority': 'low'
                    })
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Failed to get recommendations: {e}")
            return []

    def _calculate_pronunciation_accuracy(self, target: str, user_input: str) -> float:
        """Calculate pronunciation accuracy score"""
        try:
            # Simple similarity calculation
            if target == user_input:
                return 1.0
            
            # Calculate character similarity
            target_chars = set(target)
            user_chars = set(user_input)
            
            intersection = target_chars.intersection(user_chars)
            union = target_chars.union(user_chars)
            
            if union:
                char_similarity = len(intersection) / len(union)
            else:
                char_similarity = 0.0
            
            # Calculate length similarity
            length_diff = abs(len(target) - len(user_input))
            max_length = max(len(target), len(user_input))
            length_similarity = 1.0 - (length_diff / max_length) if max_length > 0 else 0.0
            
            # Combined score
            accuracy = (char_similarity * 0.7) + (length_similarity * 0.3)
            return min(accuracy, 1.0)
            
        except Exception as e:
            self.logger.error(f"Failed to calculate accuracy: {e}")
            return 0.0

    def _generate_pronunciation_feedback(self, target: str, user_input: str, accuracy: float) -> str:
        """Generate feedback for pronunciation attempt"""
        if accuracy >= 0.9:
            return "Excellent pronunciation! Well done!"
        elif accuracy >= 0.7:
            return "Good pronunciation! Try to focus on the correct sounds."
        elif accuracy >= 0.5:
            return "Fair pronunciation. Practice the word slowly and clearly."
        else:
            return "Keep practicing! Listen to the correct pronunciation and try again."

    def handle_voice_command(self, cmd: str) -> str:
        """Handle voice commands for language learning"""
        cmd = cmd.lower()
        
        if "start lesson" in cmd or "begin lesson" in cmd:
            # Extract language and lesson number
            language = None
            lesson_number = 1
            
            for lang_code in self.supported_languages.keys():
                if lang_code in cmd:
                    language = lang_code
                    break
            
            if not language:
                return "Please specify a language. Try 'start lesson spanish' or 'begin lesson french'"
            
            # Extract lesson number if specified
            import re
            lesson_match = re.search(r'lesson (\d+)', cmd)
            if lesson_match:
                lesson_number = int(lesson_match.group(1))
            
            result = self.start_lesson(language, lesson_number)
            if "error" not in result:
                return f"Started lesson {lesson_number} in {language}: {result['title']}"
            else:
                return f"Failed to start lesson: {result['error']}"
        
        elif "practice pronunciation" in cmd:
            # Extract language and word
            language = None
            word = None
            
            for lang_code in self.supported_languages.keys():
                if lang_code in cmd:
                    language = lang_code
                    break
            
            if not language:
                return "Please specify a language. Try 'practice pronunciation spanish hello'"
            
            # Extract word (simplified)
            words = cmd.split()
            for i, word_cmd in enumerate(words):
                if word_cmd in ['pronunciation', 'of', 'the', 'word'] and i + 1 < len(words):
                    word = words[i + 1]
                    break
            
            if not word:
                return "Please specify a word to practice. Try 'practice pronunciation spanish hello'"
            
            result = self.practice_pronunciation(language, word)
            if "error" not in result:
                return f"Pronunciation practice: {result['feedback']}"
            else:
                return f"Failed to practice pronunciation: {result['error']}"
        
        elif "translate" in cmd:
            # Extract text and target language
            text_start = cmd.find("translate") + 10
            text_end = cmd.find("to")
            if text_start < text_end:
                text = cmd[text_start:text_end].strip()
                target_lang = cmd[text_end + 3:].strip()
                
                # Find language code
                language_code = None
                for lang_code, info in self.supported_languages.items():
                    if info['name'].lower() in target_lang or lang_code in target_lang:
                        language_code = lang_code
                        break
                
                if language_code and text:
                    result = self.translate_text(text, language_code)
                    if "error" not in result:
                        return f"Translation: {result['translated_text']}"
                    else:
                        return f"Translation failed: {result['error']}"
            
            return "Please specify text and target language. Try 'translate hello to spanish'"
        
        elif "my progress" in cmd or "learning progress" in cmd:
            progress = self.get_user_progress()
            if progress:
                summary = []
                for prog in progress[:3]:  # Show top 3 languages
                    summary.append(f"{prog['language']}: {prog['lessons_completed']} lessons completed")
                return f"Your progress: {', '.join(summary)}"
            else:
                return "No learning progress found. Start your first lesson!"
        
        elif "recommendations" in cmd or "what should i learn" in cmd:
            recommendations = self.get_learning_recommendations()
            if recommendations:
                top_rec = recommendations[0]
                return f"Recommendation: {top_rec['message']}"
            else:
                return "No recommendations available. Start learning a new language!"
        
        elif "supported languages" in cmd:
            languages = self.get_supported_languages()
            lang_names = [lang['name'] for lang in languages if lang['lessons_available']]
            return f"Supported languages with lessons: {', '.join(lang_names)}"
        
        else:
            return "Language learning command not recognized. Try 'start lesson spanish', 'practice pronunciation', 'translate hello to spanish', or 'my progress'."

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

# Voice command helper functions
def format_lesson_info(lesson: Dict[str, Any]) -> str:
    """Format lesson information for voice output"""
    title = lesson.get('title', 'Untitled')
    lesson_number = lesson.get('lesson_number', 0)
    vocab_count = len(lesson.get('vocabulary', {}))
    
    return f"Lesson {lesson_number}: {title} with {vocab_count} vocabulary words"

def format_progress_info(progress: Dict[str, Any]) -> str:
    """Format progress information for voice output"""
    language = progress.get('language', 'Unknown')
    level = progress.get('level', 'beginner')
    lessons = progress.get('lessons_completed', 0)
    
    return f"{language} progress: {level} level, {lessons} lessons completed" 