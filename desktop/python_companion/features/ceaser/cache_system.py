#!/usr/bin/env python3
"""
Advanced Caching System for Ceaser AI Assistant
- Multi-level caching (Memory, Redis, File)
- Cache invalidation strategies
- Performance monitoring
- Cache warming
"""

import time
import json
import pickle
import hashlib
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, Union
import os
import weakref
from collections import OrderedDict
import logging

# Try to import Redis for distributed caching
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

class CacheEntry:
    """Cache entry with metadata"""
    def __init__(self, value: Any, ttl: float, created_at: float, access_count: int = 0):
        self.value = value
        self.ttl = ttl
        self.created_at = created_at
        self.access_count = access_count
        self.last_accessed = created_at
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        return time.time() - self.created_at > self.ttl
    
    def touch(self):
        """Update access statistics"""
        self.access_count += 1
        self.last_accessed = time.time()

class MultiLevelCache:
    """Multi-level caching system with L1 (Memory), L2 (Redis), L3 (File)"""
    
    def __init__(self, 
                 max_memory_size: int = 1000,
                 redis_config: Optional[Dict] = None,
                 file_cache_dir: str = './cache',
                 default_ttl: float = 300):
        self.max_memory_size = max_memory_size
        self.default_ttl = default_ttl
        
        # L1 Cache: In-memory LRU cache
        self.memory_cache = OrderedDict()
        self.memory_lock = threading.RLock()
        
        # L2 Cache: Redis (if available)
        self.redis_client = None
        if REDIS_AVAILABLE and redis_config:
            try:
                self.redis_client = redis.Redis(**redis_config)
                self.redis_client.ping()  # Test connection
                print("[INFO] Redis cache initialized successfully")
            except Exception as e:
                print(f"[WARN] Redis cache failed to initialize: {e}")
                self.redis_client = None
        
        # L3 Cache: File system cache
        self.file_cache_dir = file_cache_dir
        os.makedirs(file_cache_dir, exist_ok=True)
        
        # Cache statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'memory_hits': 0,
            'redis_hits': 0,
            'file_hits': 0
        }
        
        # Background cleanup thread
        self.cleanup_thread = threading.Thread(target=self._background_cleanup, daemon=True)
        self.cleanup_thread.start()
        
        self.logger = logging.getLogger(__name__)

    def _generate_key(self, key: Union[str, tuple]) -> str:
        """Generate cache key with hashing"""
        if isinstance(key, tuple):
            key_str = '|'.join(str(k) for k in key)
        else:
            key_str = str(key)
        
        # Create hash for consistent key length
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, key: Union[str, tuple]) -> Optional[Any]:
        """Get value from cache (L1 -> L2 -> L3)"""
        cache_key = self._generate_key(key)
        
        # Try L1 Cache (Memory)
        with self.memory_lock:
            if cache_key in self.memory_cache:
                entry = self.memory_cache[cache_key]
                if not entry.is_expired():
                    entry.touch()
                    # Move to end (most recently used)
                    self.memory_cache.move_to_end(cache_key)
                    self.stats['hits'] += 1
                    self.stats['memory_hits'] += 1
                    return entry.value
                else:
                    # Remove expired entry
                    del self.memory_cache[cache_key]
        
        # Try L2 Cache (Redis)
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    entry = pickle.loads(cached_data)
                    if not entry.is_expired():
                        # Promote to L1 cache
                        with self.memory_lock:
                            self._add_to_memory_cache(cache_key, entry)
                        self.stats['hits'] += 1
                        self.stats['redis_hits'] += 1
                        return entry.value
                    else:
                        # Remove expired entry from Redis
                        self.redis_client.delete(cache_key)
            except Exception as e:
                self.logger.warning(f"Redis cache error: {e}")
        
        # Try L3 Cache (File)
        file_path = os.path.join(self.file_cache_dir, f"{cache_key}.cache")
        if os.path.exists(file_path):
            try:
                with open(file_path, 'rb') as f:
                    entry = pickle.load(f)
                if not entry.is_expired():
                    # Promote to L1 cache
                    with self.memory_lock:
                        self._add_to_memory_cache(cache_key, entry)
                    self.stats['hits'] += 1
                    self.stats['file_hits'] += 1
                    return entry.value
                else:
                    # Remove expired file
                    os.remove(file_path)
            except Exception as e:
                self.logger.warning(f"File cache error: {e}")
        
        self.stats['misses'] += 1
        return None

    def set(self, key: Union[str, tuple], value: Any, ttl: Optional[float] = None) -> bool:
        """Set value in cache (L1, L2, L3)"""
        cache_key = self._generate_key(key)
        ttl = ttl or self.default_ttl
        
        entry = CacheEntry(value, ttl, time.time())
        
        # Store in L1 Cache (Memory)
        with self.memory_lock:
            self._add_to_memory_cache(cache_key, entry)
        
        # Store in L2 Cache (Redis)
        if self.redis_client:
            try:
                serialized_entry = pickle.dumps(entry)
                self.redis_client.setex(cache_key, int(ttl), serialized_entry)
            except Exception as e:
                self.logger.warning(f"Redis cache set error: {e}")
        
        # Store in L3 Cache (File)
        try:
            file_path = os.path.join(self.file_cache_dir, f"{cache_key}.cache")
            with open(file_path, 'wb') as f:
                pickle.dump(entry, f)
        except Exception as e:
            self.logger.warning(f"File cache set error: {e}")
        
        return True

    def _add_to_memory_cache(self, cache_key: str, entry: CacheEntry):
        """Add entry to memory cache with LRU eviction"""
        if cache_key in self.memory_cache:
            # Update existing entry
            self.memory_cache[cache_key] = entry
            self.memory_cache.move_to_end(cache_key)
        else:
            # Add new entry
            self.memory_cache[cache_key] = entry
            
            # Evict if over limit
            while len(self.memory_cache) > self.max_memory_size:
                oldest_key, _ = self.memory_cache.popitem(last=False)
                self.stats['evictions'] += 1

    def delete(self, key: Union[str, tuple]) -> bool:
        """Delete value from all cache levels"""
        cache_key = self._generate_key(key)
        
        # Remove from L1 Cache
        with self.memory_lock:
            if cache_key in self.memory_cache:
                del self.memory_cache[cache_key]
        
        # Remove from L2 Cache (Redis)
        if self.redis_client:
            try:
                self.redis_client.delete(cache_key)
            except Exception as e:
                self.logger.warning(f"Redis cache delete error: {e}")
        
        # Remove from L3 Cache (File)
        file_path = os.path.join(self.file_cache_dir, f"{cache_key}.cache")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                self.logger.warning(f"File cache delete error: {e}")
        
        return True

    def clear(self):
        """Clear all cache levels"""
        # Clear L1 Cache
        with self.memory_lock:
            self.memory_cache.clear()
        
        # Clear L2 Cache (Redis)
        if self.redis_client:
            try:
                self.redis_client.flushdb()
            except Exception as e:
                self.logger.warning(f"Redis cache clear error: {e}")
        
        # Clear L3 Cache (File)
        try:
            for filename in os.listdir(self.file_cache_dir):
                if filename.endswith('.cache'):
                    os.remove(os.path.join(self.file_cache_dir, filename))
        except Exception as e:
            self.logger.warning(f"File cache clear error: {e}")

    def warm_cache(self, warmup_data: Dict[Union[str, tuple], Any], ttl: float = 3600):
        """Warm up cache with predefined data"""
        for key, value in warmup_data.items():
            self.set(key, value, ttl)
        self.logger.info(f"Cache warmed with {len(warmup_data)} entries")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'total_requests': total_requests,
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': round(hit_rate, 2),
            'memory_hits': self.stats['memory_hits'],
            'redis_hits': self.stats['redis_hits'],
            'file_hits': self.stats['file_hits'],
            'evictions': self.stats['evictions'],
            'memory_cache_size': len(self.memory_cache),
            'redis_available': self.redis_client is not None
        }

    def _background_cleanup(self):
        """Background thread for cache cleanup"""
        while True:
            try:
                time.sleep(60)  # Run every minute
                
                current_time = time.time()
                
                # Clean up expired entries from memory cache
                with self.memory_lock:
                    expired_keys = [
                        key for key, entry in self.memory_cache.items()
                        if entry.is_expired()
                    ]
                    for key in expired_keys:
                        del self.memory_cache[key]
                
                # Clean up expired files
                try:
                    for filename in os.listdir(self.file_cache_dir):
                        if filename.endswith('.cache'):
                            file_path = os.path.join(self.file_cache_dir, filename)
                            try:
                                with open(file_path, 'rb') as f:
                                    entry = pickle.load(f)
                                if entry.is_expired():
                                    os.remove(file_path)
                            except Exception:
                                # Remove corrupted files
                                os.remove(file_path)
                except Exception as e:
                    self.logger.warning(f"File cleanup error: {e}")
                
            except Exception as e:
                self.logger.error(f"Cache cleanup error: {e}")

class CacheManager:
    """Centralized cache management for Ceaser AI Assistant"""
    
    def __init__(self):
        self.caches = {}
        self.default_config = {
            'max_memory_size': 1000,
            'default_ttl': 300,
            'file_cache_dir': './cache'
        }
    
    def get_cache(self, name: str, config: Optional[Dict] = None) -> MultiLevelCache:
        """Get or create a cache instance"""
        if name not in self.caches:
            cache_config = {**self.default_config}
            if config:
                cache_config.update(config)
            
            self.caches[name] = MultiLevelCache(**cache_config)
        
        return self.caches[name]
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all caches"""
        return {
            name: cache.get_stats() 
            for name, cache in self.caches.items()
        }
    
    def clear_all_caches(self):
        """Clear all caches"""
        for cache in self.caches.values():
            cache.clear()
    
    def warm_all_caches(self, warmup_data: Dict[str, Dict[Union[str, tuple], Any]]):
        """Warm up all caches with data"""
        for cache_name, data in warmup_data.items():
            if cache_name in self.caches:
                self.caches[cache_name].warm_cache(data)

# Global cache manager instance
cache_manager = CacheManager()

# Convenience functions
def get_cache(name: str, config: Optional[Dict] = None) -> MultiLevelCache:
    """Get a cache instance"""
    return cache_manager.get_cache(name, config)

def cache_result(cache_name: str, ttl: float = 300):
    """Decorator to cache function results"""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            cache = get_cache(cache_name)
            cache_key = (func.__name__, str(args), str(sorted(kwargs.items())))
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator
