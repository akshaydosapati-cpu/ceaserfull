#!/usr/bin/env python3
"""
Memory Cleanup and Maintenance System for Ceaser AI Assistant
- Automatic cleanup routines
- Memory optimization
- Data archiving
- Performance monitoring
"""

import os
import sqlite3
import time
import json
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import shutil
import gzip
from pathlib import Path

class MemoryCleanupManager:
    """Manages memory cleanup and optimization for Ceaser AI Assistant"""
    
    def __init__(self, db_path: str, user_id: str, business_id: Optional[str] = None, mode: str = 'normal'):
        self.db_path = db_path
        self.user_id = user_id
        self.business_id = business_id
        self.mode = mode
        
        # Cleanup configuration
        self.config = {
            'max_conversations': 1000,  # Keep last 1000 conversations
            'max_memories': 5000,       # Keep last 5000 memories
            'archive_after_days': 30,   # Archive data older than 30 days
            'cleanup_interval_hours': 24,  # Run cleanup every 24 hours
            'vacuum_interval_days': 7,  # Vacuum database every 7 days
            'backup_interval_days': 3,  # Backup every 3 days
            'compression_enabled': True,
            'archive_dir': './archives'
        }
        
        # Create archive directory
        os.makedirs(self.config['archive_dir'], exist_ok=True)
        
        # Statistics
        self.stats = {
            'last_cleanup': None,
            'conversations_cleaned': 0,
            'memories_cleaned': 0,
            'archives_created': 0,
            'space_saved_mb': 0
        }
        
        # Start background cleanup thread
        self.cleanup_thread = threading.Thread(target=self._background_cleanup, daemon=True)
        self.cleanup_thread.start()
        
        self.logger = logging.getLogger(__name__)

    def _background_cleanup(self):
        """Background thread for automatic cleanup"""
        while True:
            try:
                # Wait for cleanup interval
                time.sleep(self.config['cleanup_interval_hours'] * 3600)
                
                self.logger.info("Starting automatic memory cleanup...")
                
                # Run cleanup tasks
                self.cleanup_old_conversations()
                self.cleanup_old_memories()
                self.cleanup_expired_data()
                self.optimize_database()
                
                # Archive old data if needed
                if self._should_archive():
                    self.archive_old_data()
                
                # Backup database if needed
                if self._should_backup():
                    self.backup_database()
                
                # Update statistics
                self.stats['last_cleanup'] = datetime.now().isoformat()
                
                self.logger.info("Automatic memory cleanup completed")
                
            except Exception as e:
                self.logger.error(f"Background cleanup error: {e}")

    def cleanup_old_conversations(self) -> int:
        """Clean up old conversations, keeping only recent ones"""
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                if self.mode == 'normal':
                    # Get count of conversations to keep
                    cursor = conn.execute('''
                        SELECT COUNT(*) FROM normal_conversations 
                        WHERE user_id = ?
                    ''', (self.user_id,))
                    total_conversations = cursor.fetchone()[0]
                    
                    if total_conversations > self.config['max_conversations']:
                        # Delete oldest conversations
                        cursor = conn.execute('''
                            DELETE FROM normal_conversations 
                            WHERE user_id = ? AND id NOT IN (
                                SELECT id FROM normal_conversations 
                                WHERE user_id = ?
                                ORDER BY timestamp DESC 
                                LIMIT ?
                            )
                        ''', (self.user_id, self.user_id, self.config['max_conversations']))
                        
                        deleted_count = cursor.rowcount
                        self.stats['conversations_cleaned'] += deleted_count
                        self.logger.info(f"Cleaned up {deleted_count} old conversations")
                        return deleted_count
                
                else:  # business mode
                    cursor = conn.execute('''
                        SELECT COUNT(*) FROM business_conversations 
                        WHERE user_id = ? AND business_id = ?
                    ''', (self.user_id, self.business_id))
                    total_conversations = cursor.fetchone()[0]
                    
                    if total_conversations > self.config['max_conversations']:
                        cursor = conn.execute('''
                            DELETE FROM business_conversations 
                            WHERE user_id = ? AND business_id = ? AND id NOT IN (
                                SELECT id FROM business_conversations 
                                WHERE user_id = ? AND business_id = ?
                                ORDER BY timestamp DESC 
                                LIMIT ?
                            )
                        ''', (self.user_id, self.business_id, self.user_id, self.business_id, self.config['max_conversations']))
                        
                        deleted_count = cursor.rowcount
                        self.stats['conversations_cleaned'] += deleted_count
                        self.logger.info(f"Cleaned up {deleted_count} old conversations")
                        return deleted_count
                
                return 0
                
        finally:
            conn.close()

    def cleanup_old_memories(self) -> int:
        """Clean up old memories, keeping only important ones"""
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                if self.mode == 'normal':
                    # Get count of memories
                    cursor = conn.execute('''
                        SELECT COUNT(*) FROM normal_user_memory 
                        WHERE user_id = ?
                    ''', (self.user_id,))
                    total_memories = cursor.fetchone()[0]
                    
                    if total_memories > self.config['max_memories']:
                        # Delete least important and least accessed memories
                        cursor = conn.execute('''
                            DELETE FROM normal_user_memory 
                            WHERE user_id = ? AND id NOT IN (
                                SELECT id FROM normal_user_memory 
                                WHERE user_id = ?
                                ORDER BY importance DESC, access_count DESC, last_accessed DESC
                                LIMIT ?
                            )
                        ''', (self.user_id, self.user_id, self.config['max_memories']))
                        
                        deleted_count = cursor.rowcount
                        self.stats['memories_cleaned'] += deleted_count
                        self.logger.info(f"Cleaned up {deleted_count} old memories")
                        return deleted_count
                
                else:  # business mode
                    cursor = conn.execute('''
                        SELECT COUNT(*) FROM business_user_memory 
                        WHERE user_id = ? AND business_id = ?
                    ''', (self.user_id, self.business_id))
                    total_memories = cursor.fetchone()[0]
                    
                    if total_memories > self.config['max_memories']:
                        cursor = conn.execute('''
                            DELETE FROM business_user_memory 
                            WHERE user_id = ? AND business_id = ? AND id NOT IN (
                                SELECT id FROM business_user_memory 
                                WHERE user_id = ? AND business_id = ?
                                ORDER BY importance DESC, access_count DESC, last_accessed DESC
                                LIMIT ?
                            )
                        ''', (self.user_id, self.business_id, self.user_id, self.business_id, self.config['max_memories']))
                        
                        deleted_count = cursor.rowcount
                        self.stats['memories_cleaned'] += deleted_count
                        self.logger.info(f"Cleaned up {deleted_count} old memories")
                        return deleted_count
                
                return 0
                
        finally:
            conn.close()

    def cleanup_expired_data(self) -> int:
        """Clean up expired data"""
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                deleted_count = 0
                
                if self.mode == 'normal':
                    # Clean up expired memories
                    cursor = conn.execute('''
                        DELETE FROM normal_user_memory 
                        WHERE user_id = ? AND expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP
                    ''', (self.user_id,))
                    deleted_count += cursor.rowcount
                    
                    # Clean up old patterns
                    cursor = conn.execute('''
                        DELETE FROM normal_user_patterns 
                        WHERE user_id = ? AND last_observed < datetime('now', '-90 days')
                    ''', (self.user_id,))
                    deleted_count += cursor.rowcount
                
                else:  # business mode
                    # Clean up expired memories
                    cursor = conn.execute('''
                        DELETE FROM business_user_memory 
                        WHERE user_id = ? AND business_id = ? AND expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP
                    ''', (self.user_id, self.business_id))
                    deleted_count += cursor.rowcount
                
                if deleted_count > 0:
                    self.logger.info(f"Cleaned up {deleted_count} expired data entries")
                
                return deleted_count
                
        finally:
            conn.close()

    def optimize_database(self):
        """Optimize database performance"""
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                # Analyze tables for better query planning
                conn.execute('ANALYZE')
                
                # Rebuild indexes
                if self.mode == 'normal':
                    conn.execute('REINDEX')
                else:
                    conn.execute('REINDEX')
                
                # Vacuum database to reclaim space
                conn.execute('VACUUM')
                
                self.logger.info("Database optimization completed")
                
        finally:
            conn.close()

    def archive_old_data(self) -> str:
        """Archive old data to compressed files"""
        archive_date = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_name = f"archive_{self.user_id}_{archive_date}"
        archive_path = os.path.join(self.config['archive_dir'], archive_name)
        
        try:
            # Create archive directory
            os.makedirs(archive_path, exist_ok=True)
            
            # Archive conversations
            self._archive_table_data('conversations', archive_path)
            
            # Archive old memories
            self._archive_table_data('memories', archive_path)
            
            # Create archive manifest
            manifest = {
                'user_id': self.user_id,
                'business_id': self.business_id,
                'mode': self.mode,
                'archive_date': archive_date,
                'created_at': datetime.now().isoformat()
            }
            
            with open(os.path.join(archive_path, 'manifest.json'), 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Compress archive if enabled
            if self.config['compression_enabled']:
                self._compress_archive(archive_path)
            
            self.stats['archives_created'] += 1
            self.logger.info(f"Created archive: {archive_name}")
            
            return archive_path
            
        except Exception as e:
            self.logger.error(f"Archive creation failed: {e}")
            return None

    def _archive_table_data(self, table_type: str, archive_path: str):
        """Archive specific table data"""
        conn = sqlite3.connect(self.db_path)
        try:
            if table_type == 'conversations':
                if self.mode == 'normal':
                    cursor = conn.execute('''
                        SELECT * FROM normal_conversations 
                        WHERE user_id = ? AND timestamp < datetime('now', '-30 days')
                        ORDER BY timestamp DESC
                    ''', (self.user_id,))
                else:
                    cursor = conn.execute('''
                        SELECT * FROM business_conversations 
                        WHERE user_id = ? AND business_id = ? AND timestamp < datetime('now', '-30 days')
                        ORDER BY timestamp DESC
                    ''', (self.user_id, self.business_id))
            
            elif table_type == 'memories':
                if self.mode == 'normal':
                    cursor = conn.execute('''
                        SELECT * FROM normal_user_memory 
                        WHERE user_id = ? AND last_accessed < datetime('now', '-30 days')
                        ORDER BY last_accessed DESC
                    ''', (self.user_id,))
                else:
                    cursor = conn.execute('''
                        SELECT * FROM business_user_memory 
                        WHERE user_id = ? AND business_id = ? AND last_accessed < datetime('now', '-30 days')
                        ORDER BY last_accessed DESC
                    ''', (self.user_id, self.business_id))
            
            # Write archived data to file
            archive_file = os.path.join(archive_path, f"{table_type}.json")
            with open(archive_file, 'w') as f:
                rows = cursor.fetchall()
                if rows:
                    # Get column names
                    columns = [description[0] for description in cursor.description]
                    
                    # Convert to list of dictionaries
                    data = [dict(zip(columns, row)) for row in rows]
                    json.dump(data, f, indent=2, default=str)
                    
                    # Delete archived data from main database
                    if table_type == 'conversations':
                        if self.mode == 'normal':
                            conn.execute('''
                                DELETE FROM normal_conversations 
                                WHERE user_id = ? AND timestamp < datetime('now', '-30 days')
                            ''', (self.user_id,))
                        else:
                            conn.execute('''
                                DELETE FROM business_conversations 
                                WHERE user_id = ? AND business_id = ? AND timestamp < datetime('now', '-30 days')
                            ''', (self.user_id, self.business_id))
                    
                    elif table_type == 'memories':
                        if self.mode == 'normal':
                            conn.execute('''
                                DELETE FROM normal_user_memory 
                                WHERE user_id = ? AND last_accessed < datetime('now', '-30 days')
                            ''', (self.user_id,))
                        else:
                            conn.execute('''
                                DELETE FROM business_user_memory 
                                WHERE user_id = ? AND business_id = ? AND last_accessed < datetime('now', '-30 days')
                            ''', (self.user_id, self.business_id))
                    
                    conn.commit()
                    self.logger.info(f"Archived {len(rows)} {table_type} records")
                
        finally:
            conn.close()

    def _compress_archive(self, archive_path: str):
        """Compress archive directory"""
        try:
            # Create compressed archive
            compressed_path = f"{archive_path}.tar.gz"
            
            import tarfile
            with tarfile.open(compressed_path, 'w:gz') as tar:
                tar.add(archive_path, arcname=os.path.basename(archive_path))
            
            # Remove uncompressed directory
            shutil.rmtree(archive_path)
            
            self.logger.info(f"Compressed archive: {compressed_path}")
            
        except Exception as e:
            self.logger.error(f"Archive compression failed: {e}")

    def backup_database(self) -> str:
        """Create database backup"""
        backup_date = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_{self.user_id}_{backup_date}.db"
        backup_path = os.path.join(self.config['archive_dir'], backup_name)
        
        try:
            # Copy database file
            shutil.copy2(self.db_path, backup_path)
            
            # Compress backup if enabled
            if self.config['compression_enabled']:
                compressed_path = f"{backup_path}.gz"
                with open(self.db_path, 'rb') as f_in:
                    with gzip.open(compressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Remove uncompressed backup
                os.remove(backup_path)
                backup_path = compressed_path
            
            self.logger.info(f"Created database backup: {backup_path}")
            return backup_path
            
        except Exception as e:
            self.logger.error(f"Database backup failed: {e}")
            return None

    def _should_archive(self) -> bool:
        """Check if archiving is needed"""
        # Check if we have old data to archive
        conn = sqlite3.connect(self.db_path)
        try:
            if self.mode == 'normal':
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM normal_conversations 
                    WHERE user_id = ? AND timestamp < datetime('now', '-30 days')
                ''', (self.user_id,))
            else:
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM business_conversations 
                    WHERE user_id = ? AND business_id = ? AND timestamp < datetime('now', '-30 days')
                ''', (self.user_id, self.business_id))
            
            old_records = cursor.fetchone()[0]
            return old_records > 100  # Archive if more than 100 old records
            
        finally:
            conn.close()

    def _should_backup(self) -> bool:
        """Check if backup is needed"""
        # Check if backup directory exists and has recent backups
        backup_files = [f for f in os.listdir(self.config['archive_dir']) 
                       if f.startswith(f'backup_{self.user_id}_') and f.endswith('.db')]
        
        if not backup_files:
            return True
        
        # Check if last backup is older than backup interval
        latest_backup = max(backup_files, key=lambda f: os.path.getctime(
            os.path.join(self.config['archive_dir'], f)))
        
        backup_time = os.path.getctime(os.path.join(self.config['archive_dir'], latest_backup))
        days_since_backup = (time.time() - backup_time) / (24 * 3600)
        
        return days_since_backup > self.config['backup_interval_days']

    def get_cleanup_stats(self) -> Dict[str, Any]:
        """Get cleanup statistics"""
        return {
            'last_cleanup': self.stats['last_cleanup'],
            'conversations_cleaned': self.stats['conversations_cleaned'],
            'memories_cleaned': self.stats['memories_cleaned'],
            'archives_created': self.stats['archives_created'],
            'space_saved_mb': self.stats['space_saved_mb'],
            'config': self.config
        }

    def manual_cleanup(self):
        """Run manual cleanup immediately"""
        self.logger.info("Starting manual memory cleanup...")
        
        conversations_cleaned = self.cleanup_old_conversations()
        memories_cleaned = self.cleanup_old_memories()
        expired_cleaned = self.cleanup_expired_data()
        self.optimize_database()
        
        self.logger.info(f"Manual cleanup completed: {conversations_cleaned} conversations, "
                        f"{memories_cleaned} memories, {expired_cleaned} expired entries cleaned")
        
        return {
            'conversations_cleaned': conversations_cleaned,
            'memories_cleaned': memories_cleaned,
            'expired_cleaned': expired_cleaned
        }
