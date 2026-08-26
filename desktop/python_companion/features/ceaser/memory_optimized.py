#!/usr/bin/env python3
"""
Optimized MemoryAssistant with Performance Enhancements
- Database query optimization
- Caching mechanisms
- Memory cleanup routines
- Connection pooling
"""

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
from functools import lru_cache
import weakref
import gc

# Try to import ChromaDB for advanced vector storage
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("[INFO] ChromaDB not available. Using SQLite-only memory system.")

class OptimizedMemoryAssistant:
    def __init__(self, db_path='memory.db', persist_dir='./chroma_db', user_id=None, business_id=None, user_role=None, mode='normal'):
        self.db_path = db_path
        self.persist_dir = persist_dir
        self.user_id = user_id or 'default_user'
        self.business_id = business_id
        self.user_role = user_role or 'user'
        self.mode = mode  # 'normal' or 'business'
        
        # Performance optimizations
        self.connection_pool = []
        self.max_connections = 5
        self.connection_timeout = 30.0
        self.cache_size = 1000
        self.cache_ttl = 300  # 5 minutes
        self.query_cache = {}
        self.cache_timestamps = {}
        
        # Initialize database with optimizations
        self._initialize_database()
        
        # Initialize ChromaDB if available
        self.chroma_client = None
        self.memory_collection = None
        self.chromadb_available = CHROMADB_AVAILABLE
        if self.chromadb_available:
            try:
                self.chroma_client = chromadb.PersistentClient(path=persist_dir)
                self.memory_collection = self.chroma_client.get_or_create_collection(
                    name=f"ceaser_memory_{self.user_id}",
                    metadata={"description": f"Ceaser AI Assistant Memory for {self.user_id}"}
                )
                print("[INFO] ChromaDB initialized successfully")
            except Exception as e:
                print(f"[WARN] ChromaDB initialization failed: {e}")
                self.chromadb_available = False
        
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
        
        # Start cache cleanup thread
        self.cache_cleanup_thread = threading.Thread(target=self._cache_cleanup, daemon=True)
        self.cache_cleanup_thread.start()
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _initialize_database(self):
        """Initialize database with performance optimizations"""
        # Create connection pool
        for _ in range(self.max_connections):
            conn = sqlite3.connect(
                self.db_path, 
                check_same_thread=False, 
                timeout=self.connection_timeout
            )
            # Performance optimizations
            conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
            conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes
            conn.execute("PRAGMA cache_size=10000")  # Increase cache size
            conn.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp tables
            conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory mapping
            conn.execute("PRAGMA optimize")  # Optimize database
            self.connection_pool.append(conn)
        
        # Create tables with optimized indexes
        self._create_optimized_tables()

    def _get_connection(self):
        """Get a connection from the pool"""
        if self.connection_pool:
            return self.connection_pool.pop()
        else:
            # Create new connection if pool is empty
            conn = sqlite3.connect(
                self.db_path, 
                check_same_thread=False, 
                timeout=self.connection_timeout
            )
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            return conn

    def _return_connection(self, conn):
        """Return connection to pool"""
        if len(self.connection_pool) < self.max_connections:
            self.connection_pool.append(conn)
        else:
            conn.close()

    def _create_optimized_tables(self):
        """Create tables with optimized indexes for performance"""
        conn = self._get_connection()
        try:
            with conn:
                if self.mode == 'normal':
                    self._create_normal_mode_optimized_tables(conn)
                else:
                    self._create_business_mode_optimized_tables(conn)
        finally:
            self._return_connection(conn)

    def _create_normal_mode_optimized_tables(self, conn):
        """Create optimized tables for normal mode"""
        # User Memory Table with optimized indexes
        conn.execute('''
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
        
        # Optimized indexes for fast queries
        conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_memory_user_key ON normal_user_memory(user_id, key)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_memory_user_category ON normal_user_memory(user_id, category)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_memory_importance ON normal_user_memory(importance DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_memory_access_count ON normal_user_memory(access_count DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_memory_last_accessed ON normal_user_memory(last_accessed DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_memory_expires ON normal_user_memory(expires_at) WHERE expires_at IS NOT NULL')
        
        # User Conversation History with optimized indexes
        conn.execute('''
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
        
        # Optimized indexes for conversation queries
        conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_conversations_user_time ON normal_conversations(user_id, timestamp DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_conversations_command_type ON normal_conversations(command_type)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_conversations_sentiment ON normal_conversations(sentiment)')
        
        # User Patterns with optimized indexes
        conn.execute('''
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
        
        conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_patterns_user_type ON normal_user_patterns(user_id, pattern_type)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_patterns_frequency ON normal_user_patterns(frequency DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_patterns_confidence ON normal_user_patterns(confidence DESC)')

    def _create_business_mode_optimized_tables(self, conn):
        """Create optimized tables for business mode"""
        # Business User Memory with optimized indexes
        conn.execute('''
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
        
        # Optimized indexes for business queries
        conn.execute('CREATE INDEX IF NOT EXISTS idx_business_memory_business_user ON business_user_memory(business_id, user_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_business_memory_business_category ON business_user_memory(business_id, category)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_business_memory_user_role ON business_user_memory(user_role)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_business_memory_shared ON business_user_memory(is_shared) WHERE is_shared = 1')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_business_memory_importance ON business_user_memory(importance DESC)')
        
        # Business Conversations with optimized indexes
        conn.execute('''
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
        
        # Optimized indexes for business conversation queries
        conn.execute('CREATE INDEX IF NOT EXISTS idx_business_conversations_business_time ON business_conversations(business_id, timestamp DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_business_conversations_user_role ON business_conversations(user_role)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_business_conversations_confidentiality ON business_conversations(confidentiality_level)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_business_conversations_project ON business_conversations(project_id) WHERE project_id IS NOT NULL')

    @lru_cache(maxsize=1000)
    def _get_cached_memory(self, user_id: str, key: str, category: str) -> Optional[Any]:
        """Get memory with caching"""
        cache_key = f"{user_id}:{key}:{category}"
        if cache_key in self.query_cache:
            if time.time() - self.cache_timestamps.get(cache_key, 0) < self.cache_ttl:
                return self.query_cache[cache_key]
            else:
                # Remove expired cache entry
                del self.query_cache[cache_key]
                if cache_key in self.cache_timestamps:
                    del self.cache_timestamps[cache_key]
        return None

    def remember(self, key: str, value: Any, category: str = 'general', 
                importance: int = 1, expires_in_days: Optional[int] = None,
                metadata: Optional[Dict] = None) -> bool:
        """Store information in memory with caching and optimization"""
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
            
            # Store in SQLite with optimized query
            conn = self._get_connection()
            try:
                with conn:
                    if self.mode == 'normal':
                        conn.execute('''
                            INSERT OR REPLACE INTO normal_user_memory 
                            (user_id, key, value, category, importance, expires_at, metadata)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (self.user_id, key, value_str, category, importance, expires_at, 
                             json.dumps(metadata) if metadata else None))
                    else:  # business mode
                        conn.execute('''
                            INSERT OR REPLACE INTO business_user_memory 
                            (user_id, business_id, user_role, key, value, category, importance, expires_at, metadata)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (self.user_id, self.business_id, self.user_role, key, value_str, category, importance, expires_at, 
                             json.dumps(metadata) if metadata else None))
                
                # Update cache
                cache_key = f"{self.user_id}:{key}:{category}"
                self.query_cache[cache_key] = value
                self.cache_timestamps[cache_key] = time.time()
                
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
                
                self.logger.info(f"Stored memory: {key} in category {category}")
                return True
                
            finally:
                self._return_connection(conn)
                
        except Exception as e:
            self.logger.error(f"Failed to store memory {key}: {e}")
            return False

    def recall(self, key: str, category: str = 'general') -> Optional[Any]:
        """Retrieve information from memory with caching"""
        try:
            # Check cache first
            cache_key = f"{self.user_id}:{key}:{category}"
            cached_value = self._get_cached_memory(self.user_id, key, category)
            if cached_value is not None:
                return cached_value
            
            # Query SQLite with optimized query
            conn = self._get_connection()
            try:
                if self.mode == 'normal':
                    cursor = conn.execute('''
                        SELECT value, importance, access_count, expires_at, metadata
                        FROM normal_user_memory 
                        WHERE user_id = ? AND key = ? AND category = ?
                    ''', (self.user_id, key, category))
                else:  # business mode
                    cursor = conn.execute('''
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
                
                # Update access statistics with optimized query
                if self.mode == 'normal':
                    conn.execute('''
                        UPDATE normal_user_memory 
                        SET access_count = access_count + 1, 
                            last_accessed = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND key = ? AND category = ?
                    ''', (self.user_id, key, category))
                else:  # business mode
                    conn.execute('''
                        UPDATE business_user_memory 
                        SET access_count = access_count + 1, 
                            last_accessed = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND business_id = ? AND key = ? AND category = ?
                    ''', (self.user_id, self.business_id, key, category))
                
                # Try to deserialize JSON
                try:
                    value = json.loads(value_str)
                except json.JSONDecodeError:
                    value = value_str
                
                # Update cache
                self.query_cache[cache_key] = value
                self.cache_timestamps[cache_key] = time.time()
                
                return value
                
            finally:
                self._return_connection(conn)
                
        except Exception as e:
            self.logger.error(f"Failed to recall memory {key}: {e}")
            return None

    def search_memories(self, query: str, category: Optional[str] = None, 
                       limit: int = 10) -> List[Dict[str, Any]]:
        """Search memories using optimized queries"""
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
        
        # Fallback to optimized SQLite text search
        if not results:
            conn = self._get_connection()
            try:
                if self.mode == 'normal':
                    if category:
                        cursor = conn.execute('''
                            SELECT key, value, category, importance, access_count
                            FROM normal_user_memory 
                            WHERE user_id = ? AND category = ? AND (key LIKE ? OR value LIKE ?)
                            ORDER BY importance DESC, access_count DESC
                            LIMIT ?
                        ''', (self.user_id, category, f'%{query}%', f'%{query}%', limit))
                    else:
                        cursor = conn.execute('''
                            SELECT key, value, category, importance, access_count
                            FROM normal_user_memory 
                            WHERE user_id = ? AND (key LIKE ? OR value LIKE ?)
                            ORDER BY importance DESC, access_count DESC
                            LIMIT ?
                        ''', (self.user_id, f'%{query}%', f'%{query}%', limit))
                else:  # business mode
                    if category:
                        cursor = conn.execute('''
                            SELECT key, value, category, importance, access_count
                            FROM business_user_memory 
                            WHERE user_id = ? AND business_id = ? AND category = ? AND (key LIKE ? OR value LIKE ?)
                            ORDER BY importance DESC, access_count DESC
                            LIMIT ?
                        ''', (self.user_id, self.business_id, category, f'%{query}%', f'%{query}%', limit))
                    else:
                        cursor = conn.execute('''
                            SELECT key, value, category, importance, access_count
                            FROM business_user_memory 
                            WHERE user_id = ? AND business_id = ? AND (key LIKE ? OR value LIKE ?)
                            ORDER BY importance DESC, access_count DESC
                            LIMIT ?
                        ''', (self.user_id, self.business_id, f'%{query}%', f'%{query}%', limit))
                
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
            finally:
                self._return_connection(conn)
        
        return results

    def _background_cleanup(self):
        """Background thread for memory cleanup and maintenance"""
        while True:
            try:
                time.sleep(3600)  # Run every hour
                
                # Clean up expired memories
                conn = self._get_connection()
                try:
                    with conn:
                        if self.mode == 'normal':
                            cursor = conn.execute('''
                                DELETE FROM normal_user_memory 
                                WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP
                            ''')
                        else:  # business mode
                            cursor = conn.execute('''
                                DELETE FROM business_user_memory 
                                WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP
                            ''')
                        
                        expired_count = cursor.rowcount
                        if expired_count > 0:
                            self.logger.info(f"Cleaned up {expired_count} expired memories")
                        
                        # Clean up old conversations (keep last 1000)
                        if self.mode == 'normal':
                            conn.execute('''
                                DELETE FROM normal_conversations 
                                WHERE id NOT IN (
                                    SELECT id FROM normal_conversations 
                                    WHERE user_id = ?
                                    ORDER BY timestamp DESC 
                                    LIMIT 1000
                                )
                            ''', (self.user_id,))
                        else:  # business mode
                            conn.execute('''
                                DELETE FROM business_conversations 
                                WHERE id NOT IN (
                                    SELECT id FROM business_conversations 
                                    WHERE user_id = ? AND business_id = ?
                                    ORDER BY timestamp DESC 
                                    LIMIT 1000
                                )
                            ''', (self.user_id, self.business_id))
                        
                        # Optimize database
                        conn.execute('PRAGMA optimize')
                        
                finally:
                    self._return_connection(conn)
                
            except Exception as e:
                self.logger.error(f"Background cleanup error: {e}")

    def _cache_cleanup(self):
        """Background thread for cache cleanup"""
        while True:
            try:
                time.sleep(300)  # Run every 5 minutes
                
                current_time = time.time()
                keys_to_remove = [
                    k for k, timestamp in self.cache_timestamps.items()
                    if current_time - timestamp > self.cache_ttl
                ]
                
                for key in keys_to_remove:
                    if key in self.query_cache:
                        del self.query_cache[key]
                    if key in self.cache_timestamps:
                        del self.cache_timestamps[key]
                
                # Force garbage collection
                gc.collect()
                
            except Exception as e:
                self.logger.error(f"Cache cleanup error: {e}")

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get optimized memory statistics"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            if self.mode == 'normal':
                # Total memories
                cursor.execute('SELECT COUNT(*) FROM normal_user_memory WHERE user_id = ?', (self.user_id,))
                total_memories = cursor.fetchone()[0]
                
                # Memories by category
                cursor.execute('''
                    SELECT category, COUNT(*) as count, AVG(importance) as avg_importance
                    FROM normal_user_memory 
                    WHERE user_id = ?
                    GROUP BY category
                ''', (self.user_id,))
                
                # Most accessed memories
                cursor.execute('''
                    SELECT key, category, access_count, importance
                    FROM normal_user_memory 
                    WHERE user_id = ?
                    ORDER BY access_count DESC 
                    LIMIT 10
                ''', (self.user_id,))
                
                # Conversation count
                cursor.execute('SELECT COUNT(*) FROM normal_conversations WHERE user_id = ?', (self.user_id,))
                total_conversations = cursor.fetchone()[0]
                
            else:  # business mode
                # Total memories
                cursor.execute('SELECT COUNT(*) FROM business_user_memory WHERE user_id = ? AND business_id = ?', 
                             (self.user_id, self.business_id))
                total_memories = cursor.fetchone()[0]
                
                # Memories by category
                cursor.execute('''
                    SELECT category, COUNT(*) as count, AVG(importance) as avg_importance
                    FROM business_user_memory 
                    WHERE user_id = ? AND business_id = ?
                    GROUP BY category
                ''', (self.user_id, self.business_id))
                
                # Most accessed memories
                cursor.execute('''
                    SELECT key, category, access_count, importance
                    FROM business_user_memory 
                    WHERE user_id = ? AND business_id = ?
                    ORDER BY access_count DESC 
                    LIMIT 10
                ''', (self.user_id, self.business_id))
                
                # Conversation count
                cursor.execute('SELECT COUNT(*) FROM business_conversations WHERE user_id = ? AND business_id = ?', 
                             (self.user_id, self.business_id))
                total_conversations = cursor.fetchone()[0]
            
            category_stats = {}
            for row in cursor.fetchall():
                category, count, avg_importance = row
                category_stats[category] = {
                    'count': count,
                    'avg_importance': round(avg_importance, 2) if avg_importance else 0
                }
            
            most_accessed = []
            for row in cursor.fetchall():
                key, category, access_count, importance = row
                most_accessed.append({
                    'key': key,
                    'category': category,
                    'access_count': access_count,
                    'importance': importance
                })
            
            return {
                'total_memories': total_memories,
                'total_conversations': total_conversations,
                'category_stats': category_stats,
                'most_accessed': most_accessed,
                'cache_size': len(self.query_cache),
                'chromadb_available': CHROMADB_AVAILABLE
            }
            
        finally:
            self._return_connection(conn)

    def close(self):
        """Close all connections and cleanup"""
        # Close all connections in pool
        for conn in self.connection_pool:
            conn.close()
        self.connection_pool.clear()
        
        # Clear caches
        self.query_cache.clear()
        self.cache_timestamps.clear()
        
        if self.chroma_client:
            try:
                self.chroma_client.persist()
            except AttributeError:
                pass
