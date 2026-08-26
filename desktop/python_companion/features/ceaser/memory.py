import sqlite3
import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import hashlib
import pickle
from collections import defaultdict
import threading
import logging

# Try to import ChromaDB for advanced vector storage
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("[INFO] ChromaDB not available. Using SQLite-only memory system.")

class MemoryAssistant:
    def __init__(self, db_path='memory.db', persist_dir='./chroma_db', user_id=None, business_id=None, user_role=None, mode='normal'):
        self.db_path = db_path
        self.persist_dir = persist_dir
        self.user_id = user_id or 'default_user'
        self.business_id = business_id
        self.user_role = user_role or 'user'
        self.mode = mode  # 'normal' or 'business'
        
        # Use timeout and better connection handling to avoid database locks
        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
        self.conn.execute("PRAGMA journal_mode=WAL")  # Use WAL mode for better concurrency
        self.conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes
        self.conn.execute("PRAGMA cache_size=10000")  # Increase cache size
        self._create_tables()
        
        # Initialize ChromaDB if available
        self.chroma_client = None
        self.memory_collection = None
        self.chromadb_available = CHROMADB_AVAILABLE
        if self.chromadb_available:
            try:
                self.chroma_client = chromadb.PersistentClient(path=persist_dir)
                self.memory_collection = self.chroma_client.get_or_create_collection(
                    name="ceaser_memory",
                    metadata={"description": "Ceaser AI Assistant Memory"}
                )
                print("[INFO] ChromaDB initialized successfully")
            except Exception as e:
                print(f"[WARN] ChromaDB initialization failed: {e}")
                self.chromadb_available = False
        
        # In-memory cache for frequently accessed data
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
        self.cache_timestamps = {}
        
        # Memory categories for organization
        self.categories = {
            'preferences': 'User preferences and settings',
            'conversations': 'Conversation history and context',
            'tasks': 'Task-related information',
            'knowledge': 'General knowledge and facts',
            'patterns': 'User behavior patterns',
            'relationships': 'Information about people and relationships',
            'locations': 'Location-based information',
            'temporal': 'Time-based memories and schedules'
        }
        
        # Start background cleanup thread
        self.cleanup_thread = threading.Thread(target=self._background_cleanup, daemon=True)
        self.cleanup_thread.start()
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _create_tables(self):
        """Create SQLite tables for structured memory storage with user isolation"""
        try:
            with self.conn:
                if self.mode == 'normal':
                    self._create_normal_mode_tables()
                else:
                    self._create_business_mode_tables()
        except Exception as e:
            print(f"[WARN] Database table creation failed: {e}")
            # Continue without database tables if there's an issue

    def _create_normal_mode_tables(self):
        """Create tables for normal mode with user isolation"""
        # User Memory Table (Personal Mode)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS normal_user_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                category TEXT DEFAULT 'general',
                importance INTEGER DEFAULT 1,
                access_count INTEGER DEFAULT 0,
                last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                metadata TEXT,
                UNIQUE(user_id, key, category)
            )
        ''')
        
        # User Conversation History (Personal Mode)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS normal_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_input TEXT NOT NULL,
                assistant_response TEXT,
                context TEXT,
                sentiment REAL,
                topics TEXT,
                command_type TEXT,
                response_time_ms INTEGER,
                user_satisfaction INTEGER,
                metadata TEXT
            )
        ''')
        
        # User Patterns (Personal Mode)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS normal_user_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                pattern_type TEXT NOT NULL,
                pattern_data TEXT,
                frequency INTEGER DEFAULT 1,
                last_observed DATETIME DEFAULT CURRENT_TIMESTAMP,
                confidence REAL DEFAULT 0.5,
                context TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User Preferences (Personal Mode)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS normal_user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                preference_key TEXT NOT NULL,
                preference_value TEXT,
                category TEXT DEFAULT 'general',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, preference_key)
            )
        ''')
        
        # User Proactive Suggestions (Personal Mode)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS normal_proactive_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                suggestion_type TEXT NOT NULL,
                suggestion_data TEXT,
                context TEXT,
                priority INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_acted_upon BOOLEAN DEFAULT 0,
                action_taken TEXT,
                user_feedback INTEGER
            )
        ''')
        
        # Create indexes for normal mode
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_memory_user_id ON normal_user_memory(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_conversations_user_id ON normal_conversations(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_patterns_user_id ON normal_user_patterns(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_preferences_user_id ON normal_user_preferences(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_suggestions_user_id ON normal_proactive_suggestions(user_id)')

    def _create_business_mode_tables(self):
        """Create tables for business mode with user and role isolation"""
        # Business User Memory Table
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS business_user_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                business_id TEXT NOT NULL,
                user_role TEXT NOT NULL DEFAULT 'employee',
                key TEXT NOT NULL,
                value TEXT,
                category TEXT DEFAULT 'general',
                importance INTEGER DEFAULT 1,
                access_count INTEGER DEFAULT 0,
                last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                metadata TEXT,
                is_shared BOOLEAN DEFAULT 0,
                shared_with_roles TEXT,
                UNIQUE(business_id, user_id, key, category)
            )
        ''')
        
        # Business Conversation History
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS business_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                user_role TEXT NOT NULL DEFAULT 'employee',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_input TEXT NOT NULL,
                assistant_response TEXT,
                context TEXT,
                sentiment REAL,
                topics TEXT,
                command_type TEXT,
                response_time_ms INTEGER,
                user_satisfaction INTEGER,
                metadata TEXT,
                confidentiality_level TEXT DEFAULT 'internal',
                project_id TEXT,
                team_id TEXT
            )
        ''')
        
        # Business User Patterns
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS business_user_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                business_id TEXT NOT NULL,
                user_role TEXT NOT NULL DEFAULT 'employee',
                pattern_type TEXT NOT NULL,
                pattern_data TEXT,
                frequency INTEGER DEFAULT 1,
                last_observed DATETIME DEFAULT CURRENT_TIMESTAMP,
                confidence REAL DEFAULT 0.5,
                context TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Business Proactive Suggestions
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS business_proactive_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                business_id TEXT NOT NULL,
                user_role TEXT NOT NULL DEFAULT 'employee',
                suggestion_type TEXT NOT NULL,
                suggestion_data TEXT,
                context TEXT,
                priority INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_acted_upon BOOLEAN DEFAULT 0,
                action_taken TEXT,
                user_feedback INTEGER,
                team_visibility BOOLEAN DEFAULT 0
            )
        ''')
        
        # Create indexes for business mode
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_memory_user_id ON business_user_memory(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_memory_business_id ON business_user_memory(business_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_conversations_user_id ON business_conversations(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_conversations_business_id ON business_conversations(business_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_patterns_user_id ON business_user_patterns(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_patterns_business_id ON business_user_patterns(business_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_suggestions_user_id ON business_proactive_suggestions(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_suggestions_business_id ON business_proactive_suggestions(business_id)')

    def remember(self, key: str, value: Any, category: str = 'general', 
                importance: int = 1, expires_in_days: Optional[int] = None,
                metadata: Optional[Dict] = None) -> bool:
        """Store information in memory with categorization and importance"""
        try:
            # Serialize value to JSON
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value)
            else:
                value_str = str(value)
            
            # Calculate expiration date
            expires_at = None
            if expires_in_days:
                expires_at = datetime.now() + timedelta(days=expires_in_days)
            
            # Store in SQLite with user isolation
            with self.conn:
                if self.mode == 'normal':
                    self.conn.execute('''
                        INSERT OR REPLACE INTO normal_user_memory 
                        (user_id, key, value, category, importance, expires_at, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (self.user_id, key, value_str, category, importance, expires_at, 
                         json.dumps(metadata) if metadata else None))
                else:  # business mode
                    self.conn.execute('''
                        INSERT OR REPLACE INTO business_user_memory 
                        (user_id, business_id, user_role, key, value, category, importance, expires_at, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (self.user_id, self.business_id, self.user_role, key, value_str, category, importance, expires_at, 
                         json.dumps(metadata) if metadata else None))
            
            # Store in ChromaDB for semantic search
            if self.memory_collection and CHROMADB_AVAILABLE:
                try:
                    self.memory_collection.add(
                        documents=[value_str],
                        metadatas=[{
                            'key': key,
                            'category': category,
                            'importance': importance,
                            'timestamp': datetime.now().isoformat()
                        }],
                        ids=[f"{key}_{int(time.time())}"]
                    )
                except Exception as e:
                    self.logger.warning(f"ChromaDB storage failed: {e}")
            
            # Update cache
            cache_key = f"{category}:{key}"
            self.cache[cache_key] = value
            self.cache_timestamps[cache_key] = time.time()
            
            self.logger.info(f"Stored memory: {key} in category {category}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store memory {key}: {e}")
            return False

    def recall(self, key: str, category: str = 'general') -> Optional[Any]:
        """Retrieve information from memory"""
        try:
            # Check cache first
            cache_key = f"{category}:{key}"
            if cache_key in self.cache:
                if time.time() - self.cache_timestamps[cache_key] < self.cache_ttl:
                    # Update access count and timestamp
                    self._update_access_stats(key, category)
                    return self.cache[cache_key]
                else:
                    # Remove expired cache entry
                    del self.cache[cache_key]
                    del self.cache_timestamps[cache_key]
            
            # Query SQLite with user isolation
            cursor = self.conn.cursor()
            if self.mode == 'normal':
                cursor.execute('''
                    SELECT value, importance, access_count, expires_at, metadata
                    FROM normal_user_memory 
                    WHERE user_id = ? AND key = ? AND category = ?
                ''', (self.user_id, key, category))
            else:  # business mode
                cursor.execute('''
                    SELECT value, importance, access_count, expires_at, metadata
                    FROM business_user_memory 
                    WHERE user_id = ? AND business_id = ? AND key = ? AND category = ?
                ''', (self.user_id, self.business_id, key, category))
            
            result = cursor.fetchone()
            if not result:
                return None
            
            value_str, importance, access_count, expires_at, metadata = result
            
            # Check if expired
            if expires_at:
                expires_dt = datetime.fromisoformat(expires_at)
                if datetime.now() > expires_dt:
                    self._delete_memory(key, category)
                    return None
            
            # Update access statistics
            self._update_access_stats(key, category)
            
            # Try to deserialize JSON
            try:
                value = json.loads(value_str)
            except json.JSONDecodeError:
                value = value_str
            
            # Update cache
            self.cache[cache_key] = value
            self.cache_timestamps[cache_key] = time.time()
            
            return value
            
        except Exception as e:
            self.logger.error(f"Failed to recall memory {key}: {e}")
            return None

    def search_memories(self, query: str, category: Optional[str] = None, 
                       limit: int = 10) -> List[Dict[str, Any]]:
        """Search memories using semantic similarity"""
        results = []
        
        # Try ChromaDB semantic search first
        if self.memory_collection and CHROMADB_AVAILABLE:
            try:
                chroma_results = self.memory_collection.query(
                    query_texts=[query],
                    n_results=limit
                )
                
                for i, doc_id in enumerate(chroma_results['ids'][0]):
                    metadata = chroma_results['metadatas'][0][i]
                    document = chroma_results['documents'][0][i]
                    
                    results.append({
                        'key': metadata['key'],
                        'category': metadata['category'],
                        'value': document,
                        'importance': metadata['importance'],
                        'similarity': chroma_results['distances'][0][i] if 'distances' in chroma_results else None
                    })
            except Exception as e:
                self.logger.warning(f"ChromaDB search failed: {e}")
        
        # Fallback to SQLite text search
        if not results:
            cursor = self.conn.cursor()
            if category:
                cursor.execute('''
                    SELECT key, value, category, importance, access_count
                    FROM memory 
                    WHERE category = ? AND (key LIKE ? OR value LIKE ?)
                    ORDER BY importance DESC, access_count DESC
                    LIMIT ?
                ''', (category, f'%{query}%', f'%{query}%', limit))
            else:
                cursor.execute('''
                    SELECT key, value, category, importance, access_count
                    FROM memory 
                    WHERE key LIKE ? OR value LIKE ?
                    ORDER BY importance DESC, access_count DESC
                    LIMIT ?
                ''', (f'%{query}%', f'%{query}%', limit))
            
            for row in cursor.fetchall():
                key, value_str, cat, importance, access_count = row
                try:
                    value = json.loads(value_str)
                except json.JSONDecodeError:
                    value = value_str
                
                results.append({
                    'key': key,
                    'category': cat,
                    'value': value,
                    'importance': importance,
                    'access_count': access_count
                })
        
        return results

    def store_conversation(self, user_input: str, assistant_response: str, 
                          context: Optional[str] = None, sentiment: Optional[float] = None,
                          topics: Optional[List[str]] = None, command_type: Optional[str] = None,
                          response_time_ms: Optional[int] = None, user_satisfaction: Optional[int] = None,
                          metadata: Optional[Dict] = None) -> bool:
        """Store conversation history for context learning"""
        try:
            with self.conn:
                if self.mode == 'normal':
                    self.conn.execute('''
                        INSERT INTO normal_conversations 
                        (user_id, user_input, assistant_response, context, sentiment, topics, command_type, response_time_ms, user_satisfaction, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (self.user_id, user_input, assistant_response, context, sentiment,
                         json.dumps(topics) if topics else None, command_type, response_time_ms, user_satisfaction,
                         json.dumps(metadata) if metadata else None))
                else:  # business mode
                    self.conn.execute('''
                        INSERT INTO business_conversations 
                        (business_id, user_id, user_role, user_input, assistant_response, context, sentiment, topics, command_type, response_time_ms, user_satisfaction, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (self.business_id, self.user_id, self.user_role, user_input, assistant_response, context, sentiment,
                         json.dumps(topics) if topics else None, command_type, response_time_ms, user_satisfaction,
                         json.dumps(metadata) if metadata else None))
            
            # Extract and store key information from conversation
            self._extract_conversation_insights(user_input, assistant_response, topics)
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to store conversation: {e}")
            return False

    def get_conversation_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent conversation history"""
        cursor = self.conn.cursor()
        if self.mode == 'normal':
            cursor.execute('''
                SELECT timestamp, user_input, assistant_response, context, sentiment, topics, command_type, response_time_ms, user_satisfaction, metadata
                FROM normal_conversations
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (self.user_id, limit))
        else:  # business mode
            cursor.execute('''
                SELECT timestamp, user_input, assistant_response, context, sentiment, topics, command_type, response_time_ms, user_satisfaction, metadata, confidentiality_level, project_id, team_id
                FROM business_conversations
                WHERE user_id = ? AND business_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (self.user_id, self.business_id, limit))
        
        conversations = []
        for row in cursor.fetchall():
            if self.mode == 'normal':
                timestamp, user_input, assistant_response, context, sentiment, topics, command_type, response_time_ms, user_satisfaction, metadata = row
                conversations.append({
                    'timestamp': timestamp,
                    'user_input': user_input,
                    'assistant_response': assistant_response,
                    'context': context,
                    'sentiment': sentiment,
                    'topics': json.loads(topics) if topics else [],
                    'command_type': command_type,
                    'response_time_ms': response_time_ms,
                    'user_satisfaction': user_satisfaction,
                    'metadata': json.loads(metadata) if metadata else {}
                })
            else:  # business mode
                timestamp, user_input, assistant_response, context, sentiment, topics, command_type, response_time_ms, user_satisfaction, metadata, confidentiality_level, project_id, team_id = row
                conversations.append({
                    'timestamp': timestamp,
                    'user_input': user_input,
                    'assistant_response': assistant_response,
                    'context': context,
                    'sentiment': sentiment,
                    'topics': json.loads(topics) if topics else [],
                    'command_type': command_type,
                    'response_time_ms': response_time_ms,
                    'user_satisfaction': user_satisfaction,
                    'metadata': json.loads(metadata) if metadata else {},
                    'confidentiality_level': confidentiality_level,
                    'project_id': project_id,
                    'team_id': team_id
                })
        
        return conversations

    def store_proactive_suggestion(self, suggestion_type: str, suggestion_data: Dict[str, Any], 
                                 context: Optional[str] = None, priority: int = 1) -> bool:
        """Store proactive suggestions for the user"""
        try:
            with self.conn:
                if self.mode == 'normal':
                    self.conn.execute('''
                        INSERT INTO normal_proactive_suggestions 
                        (user_id, suggestion_type, suggestion_data, context, priority)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (self.user_id, suggestion_type, json.dumps(suggestion_data), context, priority))
                else:  # business mode
                    self.conn.execute('''
                        INSERT INTO business_proactive_suggestions 
                        (user_id, business_id, user_role, suggestion_type, suggestion_data, context, priority)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (self.user_id, self.business_id, self.user_role, suggestion_type, json.dumps(suggestion_data), context, priority))
            return True
        except Exception as e:
            self.logger.error(f"Failed to store proactive suggestion: {e}")
            return False

    def get_proactive_suggestions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get active proactive suggestions for the user"""
        cursor = self.conn.cursor()
        if self.mode == 'normal':
            cursor.execute('''
                SELECT suggestion_type, suggestion_data, context, priority, created_at, is_acted_upon
                FROM normal_proactive_suggestions
                WHERE user_id = ? AND is_acted_upon = 0
                ORDER BY priority DESC, created_at DESC
                LIMIT ?
            ''', (self.user_id, limit))
        else:  # business mode
            cursor.execute('''
                SELECT suggestion_type, suggestion_data, context, priority, created_at, is_acted_upon, team_visibility
                FROM business_proactive_suggestions
                WHERE user_id = ? AND business_id = ? AND is_acted_upon = 0
                ORDER BY priority DESC, created_at DESC
                LIMIT ?
            ''', (self.user_id, self.business_id, limit))
        
        suggestions = []
        for row in cursor.fetchall():
            if self.mode == 'normal':
                suggestion_type, suggestion_data, context, priority, created_at, is_acted_upon = row
                suggestions.append({
                    'suggestion_type': suggestion_type,
                    'suggestion_data': json.loads(suggestion_data),
                    'context': context,
                    'priority': priority,
                    'created_at': created_at,
                    'is_acted_upon': is_acted_upon
                })
            else:  # business mode
                suggestion_type, suggestion_data, context, priority, created_at, is_acted_upon, team_visibility = row
                suggestions.append({
                    'suggestion_type': suggestion_type,
                    'suggestion_data': json.loads(suggestion_data),
                    'context': context,
                    'priority': priority,
                    'created_at': created_at,
                    'is_acted_upon': is_acted_upon,
                    'team_visibility': team_visibility
                })
        
        return suggestions

    def learn_pattern(self, pattern_type: str, pattern_data: Dict[str, Any]) -> bool:
        """Learn and store user behavior patterns"""
        try:
            pattern_str = json.dumps(pattern_data)
            
            with self.conn:
                if self.mode == 'normal':
                    # Check if pattern already exists
                    cursor = self.conn.cursor()
                    cursor.execute('''
                        SELECT id, frequency FROM normal_user_patterns 
                        WHERE user_id = ? AND pattern_type = ? AND pattern_data = ?
                    ''', (self.user_id, pattern_type, pattern_str))
                    
                    result = cursor.fetchone()
                    if result:
                        # Update existing pattern
                        pattern_id, frequency = result
                        self.conn.execute('''
                            UPDATE normal_user_patterns 
                            SET frequency = ?, last_observed = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (frequency + 1, pattern_id))
                    else:
                        # Insert new pattern
                        self.conn.execute('''
                            INSERT INTO normal_user_patterns (user_id, pattern_type, pattern_data, frequency)
                            VALUES (?, ?, ?, 1)
                        ''', (self.user_id, pattern_type, pattern_str))
                else:  # business mode
                    # Check if pattern already exists
                    cursor = self.conn.cursor()
                    cursor.execute('''
                        SELECT id, frequency FROM business_user_patterns 
                        WHERE user_id = ? AND business_id = ? AND pattern_type = ? AND pattern_data = ?
                    ''', (self.user_id, self.business_id, pattern_type, pattern_str))
                    
                    result = cursor.fetchone()
                    if result:
                        # Update existing pattern
                        pattern_id, frequency = result
                        self.conn.execute('''
                            UPDATE business_user_patterns 
                            SET frequency = ?, last_observed = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (frequency + 1, pattern_id))
                    else:
                        # Insert new pattern
                        self.conn.execute('''
                            INSERT INTO business_user_patterns (user_id, business_id, user_role, pattern_type, pattern_data, frequency)
                            VALUES (?, ?, ?, ?, ?, 1)
                        ''', (self.user_id, self.business_id, self.user_role, pattern_type, pattern_str))
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to learn pattern: {e}")
            return False

    def get_patterns(self, pattern_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve learned patterns"""
        cursor = self.conn.cursor()
        if pattern_type:
            cursor.execute('''
                SELECT pattern_type, pattern_data, frequency, first_seen, last_seen
                FROM patterns
                WHERE pattern_type = ?
                ORDER BY frequency DESC
            ''', (pattern_type,))
        else:
            cursor.execute('''
                SELECT pattern_type, pattern_data, frequency, first_seen, last_seen
                FROM patterns
                ORDER BY frequency DESC
            ''')
        
        patterns = []
        for row in cursor.fetchall():
            pattern_type, pattern_data, frequency, first_seen, last_seen = row
            patterns.append({
                'pattern_type': pattern_type,
                'pattern_data': json.loads(pattern_data),
                'frequency': frequency,
                'first_seen': first_seen,
                'last_seen': last_seen
            })
        
        return patterns

    def create_association(self, source_key: str, target_key: str, 
                          association_type: str = 'related', strength: float = 1.0) -> bool:
        """Create associations between different memories"""
        try:
            with self.conn:
                self.conn.execute('''
                    INSERT OR REPLACE INTO associations 
                    (source_key, target_key, association_type, strength)
                    VALUES (?, ?, ?, ?)
                ''', (source_key, target_key, association_type, strength))
            return True
        except Exception as e:
            self.logger.error(f"Failed to create association: {e}")
            return False

    def get_associated_memories(self, key: str, association_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve memories associated with a given key"""
        cursor = self.conn.cursor()
        if association_type:
            cursor.execute('''
                SELECT a.target_key, a.association_type, a.strength, m.value, m.category
                FROM associations a
                JOIN memory m ON a.target_key = m.key
                WHERE a.source_key = ? AND a.association_type = ?
                ORDER BY a.strength DESC
            ''', (key, association_type))
        else:
            cursor.execute('''
                SELECT a.target_key, a.association_type, a.strength, m.value, m.category
                FROM associations a
                JOIN memory m ON a.target_key = m.key
                WHERE a.source_key = ?
                ORDER BY a.strength DESC
            ''', (key,))
        
        associations = []
        for row in cursor.fetchall():
            target_key, assoc_type, strength, value_str, category = row
            try:
                value = json.loads(value_str)
            except json.JSONDecodeError:
                value = value_str
            
            associations.append({
                'key': target_key,
                'association_type': assoc_type,
                'strength': strength,
                'value': value,
                'category': category
            })
        
        return associations

    def forget(self, key: str, category: str = 'general') -> bool:
        """Remove a specific memory"""
        return self._delete_memory(key, category)

    def clear_category(self, category: str) -> bool:
        """Clear all memories in a specific category"""
        try:
            with self.conn:
                self.conn.execute('DELETE FROM memory WHERE category = ?', (category,))
            
            # Clear cache entries for this category
            keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"{category}:")]
            for key in keys_to_remove:
                del self.cache[key]
                del self.cache_timestamps[key]
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to clear category {category}: {e}")
            return False

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about stored memories"""
        cursor = self.conn.cursor()
        
        # Total memories
        cursor.execute('SELECT COUNT(*) FROM memory')
        total_memories = cursor.fetchone()[0]
        
        # Memories by category
        cursor.execute('''
            SELECT category, COUNT(*) as count, AVG(importance) as avg_importance
            FROM memory GROUP BY category
        ''')
        category_stats = {}
        for row in cursor.fetchall():
            category, count, avg_importance = row
            category_stats[category] = {
                'count': count,
                'avg_importance': round(avg_importance, 2) if avg_importance else 0
            }
        
        # Most accessed memories
        cursor.execute('''
            SELECT key, category, access_count, importance
            FROM memory 
            ORDER BY access_count DESC 
            LIMIT 10
        ''')
        most_accessed = []
        for row in cursor.fetchall():
            key, category, access_count, importance = row
            most_accessed.append({
                'key': key,
                'category': category,
                'access_count': access_count,
                'importance': importance
            })
        
        # Conversation count
        cursor.execute('SELECT COUNT(*) FROM conversations')
        total_conversations = cursor.fetchone()[0]
        
        return {
            'total_memories': total_memories,
            'total_conversations': total_conversations,
            'category_stats': category_stats,
            'most_accessed': most_accessed,
            'chromadb_available': CHROMADB_AVAILABLE
        }

    def _update_access_stats(self, key: str, category: str):
        """Update access statistics for a memory"""
        try:
            with self.conn:
                if self.mode == 'normal':
                    self.conn.execute('''
                        UPDATE normal_user_memory 
                        SET access_count = access_count + 1, 
                            last_accessed = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND key = ? AND category = ?
                    ''', (self.user_id, key, category))
                else:  # business mode
                    self.conn.execute('''
                        UPDATE business_user_memory 
                        SET access_count = access_count + 1, 
                            last_accessed = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND business_id = ? AND key = ? AND category = ?
                    ''', (self.user_id, self.business_id, key, category))
        except Exception as e:
            self.logger.error(f"Failed to update access stats: {e}")

    def _delete_memory(self, key: str, category: str) -> bool:
        """Delete a memory from storage"""
        try:
            with self.conn:
                if self.mode == 'normal':
                    self.conn.execute('DELETE FROM normal_user_memory WHERE user_id = ? AND key = ? AND category = ?', (self.user_id, key, category))
                else:  # business mode
                    self.conn.execute('DELETE FROM business_user_memory WHERE user_id = ? AND business_id = ? AND key = ? AND category = ?', (self.user_id, self.business_id, key, category))
            
            # Remove from cache
            cache_key = f"{category}:{key}"
            if cache_key in self.cache:
                del self.cache[cache_key]
                del self.cache_timestamps[cache_key]
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete memory: {e}")
            return False

    def _extract_conversation_insights(self, user_input: str, assistant_response: str, topics: Optional[List[str]]):
        """Extract and store insights from conversations"""
        # Store key topics
        if topics:
            for topic in topics:
                self.remember(f"topic_{topic.lower()}", {
                    'last_discussed': datetime.now().isoformat(),
                    'frequency': 1
                }, category='topics')
        
        # Learn user preferences from conversation
        preference_keywords = ['like', 'prefer', 'favorite', 'hate', 'dislike', 'want', 'need']
        for keyword in preference_keywords:
            if keyword in user_input.lower():
                # Extract preference information
                self.learn_pattern('preference', {
                    'keyword': keyword,
                    'context': user_input,
                    'response': assistant_response
                })

    def _background_cleanup(self):
        """Background thread for memory cleanup and maintenance"""
        while True:
            try:
                time.sleep(3600)  # Run every hour
                
                # Clean up expired memories
                cursor = self.conn.cursor()
                cursor.execute('''
                    DELETE FROM memory 
                    WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP
                ''')
                expired_count = cursor.rowcount
                if expired_count > 0:
                    self.logger.info(f"Cleaned up {expired_count} expired memories")
                
                # Clean up old cache entries
                current_time = time.time()
                keys_to_remove = [
                    k for k, timestamp in self.cache_timestamps.items()
                    if current_time - timestamp > self.cache_ttl
                ]
                for key in keys_to_remove:
                    del self.cache[key]
                    del self.cache_timestamps[key]
                
                # Archive old conversations (keep last 1000)
                cursor.execute('''
                    DELETE FROM conversations 
                    WHERE id NOT IN (
                        SELECT id FROM conversations 
                        ORDER BY timestamp DESC 
                        LIMIT 1000
                    )
                ''')
                
            except Exception as e:
                self.logger.error(f"Background cleanup error: {e}")

    def close(self):
        """Close database connections"""
        if self.conn:
            self.conn.close()
        if self.chroma_client:
            try:
                # Try to persist ChromaDB data
                self.chroma_client.persist()
            except AttributeError:
                # ChromaDB client doesn't have persist method, just close
                pass

# Voice command helper functions
def format_memory_info(memory: Dict[str, Any]) -> str:
    """Format memory information for voice output"""
    key = memory.get('key', 'Unknown')
    category = memory.get('category', 'general')
    importance = memory.get('importance', 1)
    access_count = memory.get('access_count', 0)
    
    return f"Memory '{key}' in {category} category, importance {importance}, accessed {access_count} times"

def format_pattern_info(pattern: Dict[str, Any]) -> str:
    """Format pattern information for voice output"""
    pattern_type = pattern.get('pattern_type', 'Unknown')
    frequency = pattern.get('frequency', 1)
    first_seen = pattern.get('first_seen', 'Unknown')
    
    return f"Pattern '{pattern_type}' observed {frequency} times since {first_seen}" 