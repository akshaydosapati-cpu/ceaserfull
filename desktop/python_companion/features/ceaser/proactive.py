import sqlite3
import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import threading
import logging
import schedule
import psutil
import platform
from pathlib import Path
import requests
import webbrowser

# Import proactive suggestions dataset
try:
    from features.ceaser.proactive_suggestions_dataset import get_suggestion_for_context, PROACTIVE_SUGGESTIONS_DATASET
except ImportError:
    # Fallback if dataset not available
    PROACTIVE_SUGGESTIONS_DATASET = {}
    def get_suggestion_for_context(*args, **kwargs):
        return ""

class ProactiveAssistant:
    def __init__(self, db_path='proactive.db', user_id=None, business_id=None, user_role=None, mode='normal', start_workers=True):
        self.db_path = db_path
        self.user_id = user_id or 'default_user'
        self.business_id = business_id
        self.user_role = user_role or 'user'
        self.mode = mode  # 'normal' or 'business'
        
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._db_lock = threading.RLock()
        self._create_tables()
        
        # Initialize logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # User preferences and patterns
        self.user_preferences = {}
        self.daily_patterns = {}
        self.scheduled_tasks = {}
        
        # System monitoring
        self.system_thresholds = {
            'cpu_usage': 80.0,
            'memory_usage': 85.0,
            'disk_usage': 90.0,
            'battery_level': 20.0
        }
        
        # Always active - no toggle needed
        self.monitoring_active = True
        self.always_proactive = True
        
        self.monitor_thread = None
        self.learning_thread = None
        if start_workers:
            self.monitor_thread = threading.Thread(target=self._background_monitoring, daemon=True)
            self.monitor_thread.start()
            self.learning_thread = threading.Thread(target=self._continuous_learning, daemon=True)
            self.learning_thread.start()
            self._schedule_daily_tasks()
            self._initialize_proactive_features()

    def _create_tables(self):
        """Create SQLite tables for proactive features with user isolation"""
        with self.conn:
            if self.mode == 'normal':
                self._create_normal_mode_tables()
            else:
                self._create_business_mode_tables()

    def _create_normal_mode_tables(self):
        """Create tables for normal mode with user isolation"""
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
        
        # User Scheduled Tasks (Personal Mode)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS normal_scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                task_data TEXT,
                schedule_time TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_triggered DATETIME,
                trigger_count INTEGER DEFAULT 0
            )
        ''')
        
        # User System Alerts (Personal Mode)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS normal_system_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                alert_message TEXT,
                severity TEXT DEFAULT 'info',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_resolved BOOLEAN DEFAULT 0,
                resolved_at DATETIME,
                resolution_notes TEXT
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
        
        # User Learning Insights (Personal Mode)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS normal_learning_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                insight_type TEXT NOT NULL,
                insight_data TEXT,
                confidence REAL DEFAULT 0.5,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                usage_count INTEGER DEFAULT 0
            )
        ''')
        
        # Create indexes for normal mode
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_patterns_user_id ON normal_user_patterns(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_tasks_user_id ON normal_scheduled_tasks(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_alerts_user_id ON normal_system_alerts(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_suggestions_user_id ON normal_proactive_suggestions(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_normal_insights_user_id ON normal_learning_insights(user_id)')

    def _create_business_mode_tables(self):
        """Create tables for business mode with user and role isolation"""
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
        
        # Business Scheduled Tasks
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS business_scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                business_id TEXT NOT NULL,
                user_role TEXT NOT NULL DEFAULT 'employee',
                task_type TEXT NOT NULL,
                task_data TEXT,
                schedule_time TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_triggered DATETIME,
                trigger_count INTEGER DEFAULT 0,
                business_context TEXT,
                team_assignment TEXT,
                priority_level TEXT DEFAULT 'medium'
            )
        ''')
        
        # Business System Alerts
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS business_system_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                business_id TEXT NOT NULL,
                user_role TEXT NOT NULL DEFAULT 'employee',
                alert_type TEXT NOT NULL,
                alert_message TEXT,
                severity TEXT DEFAULT 'info',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_resolved BOOLEAN DEFAULT 0,
                resolved_at DATETIME,
                resolution_notes TEXT,
                business_impact TEXT,
                escalation_level TEXT DEFAULT 'none',
                assigned_to TEXT
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
        
        # Business Learning Insights
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS business_learning_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                business_id TEXT NOT NULL,
                user_role TEXT NOT NULL DEFAULT 'employee',
                insight_type TEXT NOT NULL,
                insight_data TEXT,
                confidence REAL DEFAULT 0.5,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                usage_count INTEGER DEFAULT 0,
                shared_with TEXT
            )
        ''')
        
        # Create indexes for business mode
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_patterns_user_id ON business_user_patterns(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_patterns_business_id ON business_user_patterns(business_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_tasks_user_id ON business_scheduled_tasks(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_tasks_business_id ON business_scheduled_tasks(business_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_alerts_user_id ON business_system_alerts(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_alerts_business_id ON business_system_alerts(business_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_suggestions_user_id ON business_proactive_suggestions(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_suggestions_business_id ON business_proactive_suggestions(business_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_insights_user_id ON business_learning_insights(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_business_insights_business_id ON business_learning_insights(business_id)')

    def learn_user_pattern(self, pattern_type: str, pattern_data: Dict[str, Any], 
                          confidence: float = 0.5) -> bool:
        """Learn and store user behavior patterns"""
        try:
            pattern_str = json.dumps(pattern_data)
            
            with self._db_lock, self.conn:
                if self.mode == 'normal':
                    # Check if pattern already exists
                    cursor = self.conn.cursor()
                    cursor.execute('''
                        SELECT id, frequency, confidence FROM normal_user_patterns 
                        WHERE user_id = ? AND pattern_type = ? AND pattern_data = ?
                    ''', (self.user_id, pattern_type, pattern_str))
                    
                    result = cursor.fetchone()
                    if result:
                        # Update existing pattern
                        pattern_id, frequency, current_confidence = result
                        new_confidence = (current_confidence + confidence) / 2
                        self.conn.execute('''
                            UPDATE normal_user_patterns 
                            SET frequency = ?, confidence = ?, last_observed = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (frequency + 1, new_confidence, pattern_id))
                    else:
                        # Insert new pattern
                        self.conn.execute('''
                            INSERT INTO normal_user_patterns (user_id, pattern_type, pattern_data, frequency, confidence)
                            VALUES (?, ?, ?, 1, ?)
                        ''', (self.user_id, pattern_type, pattern_str, confidence))
                else:  # business mode
                    # Check if pattern already exists
                    cursor = self.conn.cursor()
                    cursor.execute('''
                        SELECT id, frequency, confidence FROM business_user_patterns 
                        WHERE user_id = ? AND business_id = ? AND pattern_type = ? AND pattern_data = ?
                    ''', (self.user_id, self.business_id, pattern_type, pattern_str))
                    
                    result = cursor.fetchone()
                    if result:
                        # Update existing pattern
                        pattern_id, frequency, current_confidence = result
                        new_confidence = (current_confidence + confidence) / 2
                        self.conn.execute('''
                            UPDATE business_user_patterns 
                            SET frequency = ?, confidence = ?, last_observed = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (frequency + 1, new_confidence, pattern_id))
                    else:
                        # Insert new pattern
                        self.conn.execute('''
                            INSERT INTO business_user_patterns (user_id, business_id, user_role, pattern_type, pattern_data, frequency, confidence)
                            VALUES (?, ?, ?, ?, ?, 1, ?)
                        ''', (self.user_id, self.business_id, self.user_role, pattern_type, pattern_str, confidence))
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to learn user pattern: {e}")
            return False

    def get_user_patterns(self, pattern_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve learned user patterns"""
        try:
            cursor = self.conn.cursor()
            if self.mode == 'normal':
                if pattern_type:
                    cursor.execute('''
                        SELECT pattern_type, pattern_data, frequency, confidence, last_observed
                        FROM normal_user_patterns
                        WHERE user_id = ? AND pattern_type = ?
                        ORDER BY frequency DESC, confidence DESC
                    ''', (self.user_id, pattern_type))
                else:
                    cursor.execute('''
                        SELECT pattern_type, pattern_data, frequency, confidence, last_observed
                        FROM normal_user_patterns
                        WHERE user_id = ?
                        ORDER BY frequency DESC, confidence DESC
                    ''', (self.user_id,))
            else:  # business mode
                if pattern_type:
                    cursor.execute('''
                        SELECT pattern_type, pattern_data, frequency, confidence, last_observed
                        FROM business_user_patterns
                        WHERE user_id = ? AND business_id = ? AND pattern_type = ?
                        ORDER BY frequency DESC, confidence DESC
                    ''', (self.user_id, self.business_id, pattern_type))
                else:
                    cursor.execute('''
                        SELECT pattern_type, pattern_data, frequency, confidence, last_observed
                        FROM business_user_patterns
                        WHERE user_id = ? AND business_id = ?
                        ORDER BY frequency DESC, confidence DESC
                    ''', (self.user_id, self.business_id))
            
            patterns = []
            for row in cursor.fetchall():
                pattern_type, pattern_data, frequency, confidence, last_observed = row
                patterns.append({
                    'pattern_type': pattern_type,
                    'pattern_data': json.loads(pattern_data),
                    'frequency': frequency,
                    'confidence': confidence,
                    'last_observed': last_observed
                })
            
            return patterns
        except Exception as e:
            self.logger.error(f"Failed to get user patterns: {e}")
            return []

    def schedule_task(self, task_type: str, task_data: Dict[str, Any], 
                     schedule_time: str, is_active: bool = True) -> int:
        """Schedule a proactive task"""
        try:
            with self.conn:
                cursor = self.conn.cursor()
                if self.mode == 'normal':
                    cursor.execute('''
                        INSERT INTO normal_scheduled_tasks (user_id, task_type, task_data, schedule_time, is_active)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (self.user_id, task_type, json.dumps(task_data), schedule_time, is_active))
                else:  # business mode
                    cursor.execute('''
                        INSERT INTO business_scheduled_tasks (user_id, business_id, user_role, task_type, task_data, schedule_time, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (self.user_id, self.business_id, self.user_role, task_type, json.dumps(task_data), schedule_time, is_active))
                
                task_id = cursor.lastrowid
                self.logger.info(f"Scheduled task: {task_type} (ID: {task_id})")
                return task_id
        except Exception as e:
            self.logger.error(f"Failed to schedule task: {e}")
            return -1

    def get_scheduled_tasks(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get scheduled tasks"""
        try:
            cursor = self.conn.cursor()
            if self.mode == 'normal':
                if task_type:
                    cursor.execute('''
                        SELECT id, task_type, task_data, schedule_time, is_active, created_at, last_triggered, trigger_count
                        FROM normal_scheduled_tasks
                        WHERE user_id = ? AND task_type = ? AND is_active = 1
                        ORDER BY schedule_time
                    ''', (self.user_id, task_type))
                else:
                    cursor.execute('''
                        SELECT id, task_type, task_data, schedule_time, is_active, created_at, last_triggered, trigger_count
                        FROM normal_scheduled_tasks
                        WHERE user_id = ? AND is_active = 1
                        ORDER BY schedule_time
                    ''', (self.user_id,))
            else:  # business mode
                if task_type:
                    cursor.execute('''
                        SELECT id, task_type, task_data, schedule_time, is_active, created_at, last_triggered, trigger_count, business_context, team_assignment, priority_level
                        FROM business_scheduled_tasks
                        WHERE user_id = ? AND business_id = ? AND task_type = ? AND is_active = 1
                        ORDER BY schedule_time
                    ''', (self.user_id, self.business_id, task_type))
                else:
                    cursor.execute('''
                        SELECT id, task_type, task_data, schedule_time, is_active, created_at, last_triggered, trigger_count, business_context, team_assignment, priority_level
                        FROM business_scheduled_tasks
                        WHERE user_id = ? AND business_id = ? AND is_active = 1
                        ORDER BY schedule_time
                    ''', (self.user_id, self.business_id))
            
            tasks = []
            for row in cursor.fetchall():
                if self.mode == 'normal':
                    task_id, task_type, task_data, schedule_time, is_active, created_at, last_triggered, trigger_count = row
                    tasks.append({
                        'id': task_id,
                        'task_type': task_type,
                        'task_data': json.loads(task_data),
                        'schedule_time': schedule_time,
                        'is_active': bool(is_active),
                        'created_at': created_at,
                        'last_triggered': last_triggered,
                        'trigger_count': trigger_count
                    })
                else:  # business mode
                    task_id, task_type, task_data, schedule_time, is_active, created_at, last_triggered, trigger_count, business_context, team_assignment, priority_level = row
                    tasks.append({
                        'id': task_id,
                        'task_type': task_type,
                        'task_data': json.loads(task_data),
                        'schedule_time': schedule_time,
                        'is_active': bool(is_active),
                        'created_at': created_at,
                        'last_triggered': last_triggered,
                        'trigger_count': trigger_count,
                        'business_context': business_context,
                        'team_assignment': team_assignment,
                        'priority_level': priority_level
                    })
            
            return tasks
        except Exception as e:
            self.logger.error(f"Failed to get scheduled tasks: {e}")
            return []

    def create_system_alert(self, alert_type: str, alert_message: str, 
                           severity: str = 'info') -> int:
        """Create a system alert"""
        try:
            with self._db_lock, self.conn:
                cursor = self.conn.cursor()
                if self.mode == 'normal':
                    cursor.execute('''
                        INSERT INTO normal_system_alerts (user_id, alert_type, alert_message, severity)
                        VALUES (?, ?, ?, ?)
                    ''', (self.user_id, alert_type, alert_message, severity))
                else:  # business mode
                    cursor.execute('''
                        INSERT INTO business_system_alerts (user_id, business_id, user_role, alert_type, alert_message, severity)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (self.user_id, self.business_id, self.user_role, alert_type, alert_message, severity))
                
                alert_id = cursor.lastrowid
                self.logger.info(f"Created alert: {alert_type} - {alert_message}")
                return alert_id
        except Exception as e:
            self.logger.error(f"Failed to create system alert: {e}")
            return -1

    def get_active_alerts(self, alert_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get active system alerts"""
        try:
            cursor = self.conn.cursor()
            if self.mode == 'normal':
                if alert_type:
                    cursor.execute('''
                        SELECT id, alert_type, alert_message, severity, created_at
                        FROM normal_system_alerts
                        WHERE user_id = ? AND alert_type = ? AND is_resolved = 0
                        ORDER BY created_at DESC
                    ''', (self.user_id, alert_type))
                else:
                    cursor.execute('''
                        SELECT id, alert_type, alert_message, severity, created_at
                        FROM normal_system_alerts
                        WHERE user_id = ? AND is_resolved = 0
                        ORDER BY created_at DESC
                    ''', (self.user_id,))
            else:  # business mode
                if alert_type:
                    cursor.execute('''
                        SELECT id, alert_type, alert_message, severity, created_at, business_impact, escalation_level
                        FROM business_system_alerts
                        WHERE user_id = ? AND business_id = ? AND alert_type = ? AND is_resolved = 0
                        ORDER BY created_at DESC
                    ''', (self.user_id, self.business_id, alert_type))
                else:
                    cursor.execute('''
                        SELECT id, alert_type, alert_message, severity, created_at, business_impact, escalation_level
                        FROM business_system_alerts
                        WHERE user_id = ? AND business_id = ? AND is_resolved = 0
                        ORDER BY created_at DESC
                    ''', (self.user_id, self.business_id))
            
            alerts = []
            for row in cursor.fetchall():
                if self.mode == 'normal':
                    alert_id, alert_type, alert_message, severity, created_at = row
                    alerts.append({
                        'id': alert_id,
                        'alert_type': alert_type,
                        'alert_message': alert_message,
                        'severity': severity,
                        'created_at': created_at
                    })
                else:  # business mode
                    alert_id, alert_type, alert_message, severity, created_at, business_impact, escalation_level = row
                    alerts.append({
                        'id': alert_id,
                        'alert_type': alert_type,
                        'alert_message': alert_message,
                        'severity': severity,
                        'created_at': created_at,
                        'business_impact': business_impact,
                        'escalation_level': escalation_level
                    })
            
            return alerts
        except Exception as e:
            self.logger.error(f"Failed to get active alerts: {e}")
            return []

    def resolve_alert(self, alert_id: int) -> bool:
        """Mark an alert as resolved"""
        try:
            with self.conn:
                if self.mode == 'normal':
                    self.conn.execute('''
                        UPDATE normal_system_alerts 
                        SET is_resolved = 1, resolved_at = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND id = ?
                    ''', (self.user_id, alert_id))
                else:  # business mode
                    self.conn.execute('''
                        UPDATE business_system_alerts 
                        SET is_resolved = 1, resolved_at = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND business_id = ? AND id = ?
                    ''', (self.user_id, self.business_id, alert_id))
            return True
        except Exception as e:
            self.logger.error(f"Failed to resolve alert: {e}")
            return False

    def create_suggestion(self, suggestion_type: str, suggestion_data: Dict[str, Any], 
                         context: str = "", priority: int = 1) -> int:
        """Create a contextual suggestion"""
        try:
            with self._db_lock, self.conn:
                cursor = self.conn.cursor()
                if self.mode == 'normal':
                    cursor.execute('''
                        INSERT INTO normal_proactive_suggestions (user_id, suggestion_type, suggestion_data, context, priority)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (self.user_id, suggestion_type, json.dumps(suggestion_data), context, priority))
                else:  # business mode
                    cursor.execute('''
                        INSERT INTO business_proactive_suggestions (user_id, business_id, user_role, suggestion_type, suggestion_data, context, priority)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (self.user_id, self.business_id, self.user_role, suggestion_type, json.dumps(suggestion_data), context, priority))
                
                suggestion_id = cursor.lastrowid
                self.logger.info(f"Created suggestion: {suggestion_type}")
                return suggestion_id
        except Exception as e:
            self.logger.error(f"Failed to create suggestion: {e}")
            return -1

    def get_suggestions(self, suggestion_type: Optional[str] = None, 
                       limit: int = 10) -> List[Dict[str, Any]]:
        """Get contextual suggestions"""
        try:
            cursor = self.conn.cursor()
            if self.mode == 'normal':
                if suggestion_type:
                    cursor.execute('''
                        SELECT id, suggestion_type, suggestion_data, context, priority, created_at
                        FROM normal_proactive_suggestions
                        WHERE user_id = ? AND suggestion_type = ? AND is_acted_upon = 0
                        ORDER BY priority DESC, created_at DESC
                        LIMIT ?
                    ''', (self.user_id, suggestion_type, limit))
                else:
                    cursor.execute('''
                        SELECT id, suggestion_type, suggestion_data, context, priority, created_at
                        FROM normal_proactive_suggestions
                        WHERE user_id = ? AND is_acted_upon = 0
                        ORDER BY priority DESC, created_at DESC
                        LIMIT ?
                    ''', (self.user_id, limit))
            else:  # business mode
                if suggestion_type:
                    cursor.execute('''
                        SELECT id, suggestion_type, suggestion_data, context, priority, created_at, team_visibility
                        FROM business_proactive_suggestions
                        WHERE user_id = ? AND business_id = ? AND suggestion_type = ? AND is_acted_upon = 0
                        ORDER BY priority DESC, created_at DESC
                        LIMIT ?
                    ''', (self.user_id, self.business_id, suggestion_type, limit))
                else:
                    cursor.execute('''
                        SELECT id, suggestion_type, suggestion_data, context, priority, created_at, team_visibility
                        FROM business_proactive_suggestions
                        WHERE user_id = ? AND business_id = ? AND is_acted_upon = 0
                        ORDER BY priority DESC, created_at DESC
                        LIMIT ?
                    ''', (self.user_id, self.business_id, limit))
            
            suggestions = []
            seen_messages = set()  # Track unique messages to avoid duplicates
            
            for row in cursor.fetchall():
                if self.mode == 'normal':
                    suggestion_id, suggestion_type, suggestion_data, context, priority, created_at = row
                    suggestion_dict = json.loads(suggestion_data)
                    message = suggestion_dict.get('message', '')
                    
                    # Skip duplicates
                    if message and message in seen_messages:
                        continue
                    seen_messages.add(message)
                    
                    suggestions.append({
                        'id': suggestion_id,
                        'suggestion_type': suggestion_type,
                        'suggestion_data': suggestion_dict,
                        'context': context,
                        'priority': priority,
                        'created_at': created_at
                    })
                else:  # business mode
                    suggestion_id, suggestion_type, suggestion_data, context, priority, created_at, team_visibility = row
                    suggestion_dict = json.loads(suggestion_data)
                    message = suggestion_dict.get('message', '')
                    
                    # Skip duplicates
                    if message and message in seen_messages:
                        continue
                    seen_messages.add(message)
                    
                    suggestions.append({
                        'id': suggestion_id,
                        'suggestion_type': suggestion_type,
                        'suggestion_data': suggestion_dict,
                        'context': context,
                        'priority': priority,
                        'created_at': created_at,
                        'team_visibility': team_visibility
                    })
            
            return suggestions
        except Exception as e:
            self.logger.error(f"Failed to get suggestions: {e}")
            return []

    def mark_suggestion_acted_upon(self, suggestion_id: int) -> bool:
        """Mark a suggestion as acted upon"""
        try:
            with self.conn:
                if self.mode == 'normal':
                    self.conn.execute('''
                        UPDATE normal_proactive_suggestions 
                        SET is_acted_upon = 1
                        WHERE user_id = ? AND id = ?
                    ''', (self.user_id, suggestion_id))
                else:  # business mode
                    self.conn.execute('''
                        UPDATE business_proactive_suggestions 
                        SET is_acted_upon = 1
                        WHERE user_id = ? AND business_id = ? AND id = ?
                    ''', (self.user_id, self.business_id, suggestion_id))
            return True
        except Exception as e:
            self.logger.error(f"Failed to mark suggestion acted upon: {e}")
            return False

    def monitor_system_health(self) -> Dict[str, Any]:
        """Monitor system health and create alerts if needed"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > self.system_thresholds['cpu_usage']:
                self.create_system_alert(
                    'high_cpu',
                    f"CPU usage is high: {cpu_percent:.1f}%",
                    'warning'
                )
            
            # Memory usage
            memory = psutil.virtual_memory()
            if memory.percent > self.system_thresholds['memory_usage']:
                self.create_system_alert(
                    'high_memory',
                    f"Memory usage is high: {memory.percent:.1f}%",
                    'warning'
                )
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            if disk_percent > self.system_thresholds['disk_usage']:
                self.create_system_alert(
                    'low_disk_space',
                    f"Disk space is low: {disk_percent:.1f}% used",
                    'warning'
                )
            
            # Battery status (if on laptop)
            if hasattr(psutil, 'sensors_battery'):
                battery = psutil.sensors_battery()
                if battery and battery.percent < self.system_thresholds['battery_level']:
                    self.create_system_alert(
                        'low_battery',
                        f"Battery level is low: {battery.percent:.1f}%",
                        'warning'
                    )
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': disk_percent,
                'battery_percent': battery.percent if battery else None
            }
        except Exception as e:
            self.logger.error(f"Failed to monitor system health: {e}")
            return {}

    def analyze_user_context(self, last_command: str = "", last_response: str = "") -> List[Dict[str, Any]]:
        """Analyze current context and generate suggestions using dataset"""
        suggestions = []
        current_time = datetime.now()
        current_hour = current_time.hour
        
        try:
            # Use dataset-based suggestions if available
            if PROACTIVE_SUGGESTIONS_DATASET and last_command:
                dataset_suggestion = get_suggestion_for_context(last_command, last_response, 0)
                if dataset_suggestion:
                    suggestions.append({
                        'type': 'dataset_suggestion',
                        'data': {
                            'message': dataset_suggestion,
                            'actions': []
                        },
                        'priority': 2
                    })
            
            # Time-based suggestions
            if 6 <= current_hour <= 11:  # Morning
                if 'morning' in PROACTIVE_SUGGESTIONS_DATASET:
                    morning_suggestions = PROACTIVE_SUGGESTIONS_DATASET['morning']
                    if morning_suggestions:
                        import random
                        suggestions.append({
                            'type': 'morning_routine',
                            'data': {
                                'message': random.choice(morning_suggestions),
                                'actions': ['check_calendar', 'weather_update', 'news_brief']
                            },
                            'priority': 2
                        })
            elif 18 <= current_hour <= 23:  # Evening
                if 'evening' in PROACTIVE_SUGGESTIONS_DATASET:
                    evening_suggestions = PROACTIVE_SUGGESTIONS_DATASET['evening']
                    if evening_suggestions:
                        import random
                        suggestions.append({
                            'type': 'evening_routine',
                            'data': {
                                'message': random.choice(evening_suggestions),
                                'actions': ['create_tomorrow_todo', 'backup_reminder', 'system_cleanup']
                            },
                            'priority': 2
                        })
            
            # System-based suggestions
            system_health = self.monitor_system_health()
            if system_health.get('cpu_percent', 0) > 70 or system_health.get('memory_percent', 0) > 85:
                if 'system_health' in PROACTIVE_SUGGESTIONS_DATASET:
                    health_suggestions = PROACTIVE_SUGGESTIONS_DATASET['system_health']
                    if health_suggestions:
                        import random
                        suggestions.append({
                            'type': 'performance_optimization',
                            'data': {
                                'message': random.choice(health_suggestions),
                                'actions': ['close_unused_apps', 'clear_temp_files', 'restart_suggestions']
                            },
                            'priority': 3
                        })
            
            # Pattern-based suggestions
            patterns = self.get_user_patterns('daily_activity')
            for pattern in patterns:
                if pattern['frequency'] > 3:  # Frequent pattern
                    suggestions.append({
                        'type': 'pattern_reminder',
                        'data': {
                            'message': f"Based on your patterns, you usually {pattern['pattern_data'].get('activity', 'do something')} around this time.",
                            'actions': ['remind_activity', 'auto_start_app']
                        },
                        'priority': 1
                    })
            
            return suggestions
        except Exception as e:
            self.logger.error(f"Failed to analyze user context: {e}")
            return []

    def generate_daily_insights(self) -> Dict[str, Any]:
        """Generate daily insights and recommendations"""
        try:
            insights = {
                'productivity_score': 0,
                'system_health': 'good',
                'recommendations': [],
                'patterns_observed': []
            }
            
            # Analyze patterns
            patterns = self.get_user_patterns()
            if patterns:
                insights['patterns_observed'] = [
                    f"Frequent {p['pattern_type']} activity" 
                    for p in patterns if p['frequency'] > 5
                ]
            
            # Check system health
            system_health = self.monitor_system_health()
            if any([
                system_health.get('cpu_percent', 0) > 80,
                system_health.get('memory_percent', 0) > 85,
                system_health.get('disk_percent', 0) > 90
            ]):
                insights['system_health'] = 'needs_attention'
                insights['recommendations'].append('Consider system maintenance')
            
            # Calculate productivity score (simplified)
            active_alerts = len(self.get_active_alerts())
            if active_alerts == 0:
                insights['productivity_score'] = 85
            elif active_alerts < 3:
                insights['productivity_score'] = 70
            else:
                insights['productivity_score'] = 50
            
            return insights
        except Exception as e:
            self.logger.error(f"Failed to generate daily insights: {e}")
            return {}

    def _schedule_daily_tasks(self):
        """Schedule recurring daily tasks"""
        try:
            # Morning routine check
            schedule.every().day.at("09:00").do(self._morning_routine)
            
            # Evening wrap-up
            schedule.every().day.at("17:00").do(self._evening_routine)
            
            # System health check (every 2 hours)
            schedule.every(2).hours.do(self._system_health_check)
            
            # Daily insights generation
            schedule.every().day.at("20:00").do(self._generate_daily_report)
            
            self.logger.info("Daily tasks scheduled successfully")
        except Exception as e:
            self.logger.error(f"Failed to schedule daily tasks: {e}")

    def _morning_routine(self):
        """Morning routine tasks"""
        try:
            # Create morning suggestions
            self.create_suggestion(
                'morning_check',
                {
                    'message': 'Good morning! Ready to start your day?',
                    'actions': ['check_calendar', 'weather_update', 'news_brief']
                },
                'morning_routine',
                2
            )
            
            # Check for important tasks
            self.create_suggestion(
                'task_review',
                {
                    'message': 'Would you like to review today\'s tasks?',
                    'actions': ['show_today_tasks', 'create_priority_list']
                },
                'task_management',
                2
            )
        except Exception as e:
            self.logger.error(f"Morning routine failed: {e}")

    def _evening_routine(self):
        """Evening routine tasks"""
        try:
            # Create evening suggestions
            self.create_suggestion(
                'evening_wrapup',
                {
                    'message': 'Time to wrap up! How was your day?',
                    'actions': ['create_tomorrow_todo', 'backup_reminder', 'system_cleanup']
                },
                'evening_routine',
                2
            )
            
            # System cleanup reminder
            self.create_suggestion(
                'system_maintenance',
                {
                    'message': 'Would you like me to perform system maintenance?',
                    'actions': ['clear_temp_files', 'check_updates', 'optimize_performance']
                },
                'system_health',
                1
            )
        except Exception as e:
            self.logger.error(f"Evening routine failed: {e}")

    def _system_health_check(self):
        """Regular system health check"""
        try:
            self.monitor_system_health()
        except Exception as e:
            self.logger.error(f"System health check failed: {e}")

    def _generate_daily_report(self):
        """Generate daily insights report"""
        try:
            insights = self.generate_daily_insights()
            self.create_suggestion(
                'daily_report',
                {
                    'message': 'Your daily insights are ready!',
                    'insights': insights
                },
                'daily_summary',
                1
            )
        except Exception as e:
            self.logger.error(f"Daily report generation failed: {e}")

    def _background_monitoring(self):
        """Background monitoring thread"""
        while self.monitoring_active:
            try:
                # Run scheduled tasks
                schedule.run_pending()
                
                # Analyze context and create suggestions
                suggestions = self.analyze_user_context()
                for suggestion in suggestions:
                    self.create_suggestion(
                        suggestion['type'],
                        suggestion['data'],
                        priority=suggestion['priority']
                    )
                
                # Sleep for 5 minutes
                time.sleep(300)
            except Exception as e:
                self.logger.error(f"Background monitoring error: {e}")
                time.sleep(60)  # Shorter sleep on error

    def handle_voice_command(self, cmd: str) -> str:
        """Handle voice commands for proactive features"""
        cmd = cmd.lower()
        
        if "check system" in cmd or "system health" in cmd:
            health = self.monitor_system_health()
            cpu = health.get('cpu_percent', 0)
            memory = health.get('memory_percent', 0)
            return f"System health: CPU {cpu:.1f}%, Memory {memory:.1f}%"
        
        elif "daily insights" in cmd or "daily report" in cmd:
            insights = self.generate_daily_insights()
            score = insights.get('productivity_score', 0)
            health = insights.get('system_health', 'unknown')
            return f"Daily insights: Productivity score {score}, System health {health}"
        
        elif "active alerts" in cmd or "system alerts" in cmd:
            alerts = self.get_active_alerts()
            if alerts:
                return f"You have {len(alerts)} active system alerts. Check the app for details."
            else:
                return "No active system alerts."
        
        elif "suggestions" in cmd or "recommendations" in cmd:
            suggestions = self.get_suggestions(limit=5)
            if suggestions:
                return f"You have {len(suggestions)} suggestions. Check the app for details."
            else:
                return "No suggestions at the moment."
        
        elif "learn pattern" in cmd:
            # Extract pattern information from command
            if "morning" in cmd:
                self.learn_user_pattern('daily_activity', {
                    'activity': 'morning_routine',
                    'time': 'morning',
                    'context': 'daily_start'
                })
                return "Learned your morning pattern."
            elif "evening" in cmd:
                self.learn_user_pattern('daily_activity', {
                    'activity': 'evening_routine',
                    'time': 'evening',
                    'context': 'daily_end'
                })
                return "Learned your evening pattern."
            else:
                return "Please specify what pattern to learn. Try 'learn pattern morning' or 'learn pattern evening'"
        
        else:
            return "Proactive command not recognized. Try 'check system', 'daily insights', 'active alerts', or 'suggestions'."

    def _initialize_proactive_features(self):
        """Initialize proactive features on startup"""
        try:
            # Check if welcome suggestion already exists to avoid duplicates
            existing_suggestions = self.get_suggestions(suggestion_type='welcome', limit=1)
            if not existing_suggestions:
                # Create welcome suggestion only if it doesn't exist
                self.create_suggestion(
                    'welcome',
                    {
                        'message': 'Welcome! I\'m Ceaser, your always-active AI assistant. I\'m constantly monitoring and learning to help you better.',
                        'actions': ['system_check', 'learn_preferences', 'schedule_optimization']
                    },
                    'startup',
                    3
                )
            
            # Generate contextual suggestions based on current time and system state
            current_time = datetime.now()
            hour = current_time.hour
            
            # Time-based proactive suggestions
            if 9 <= hour <= 11:  # Morning
                self.create_suggestion(
                    'morning_boost',
                    {
                        'message': 'Good morning! I notice you\'re starting your day. Would you like me to check your schedule or help optimize your productivity?',
                        'actions': ['check_calendar', 'weather_update', 'task_review']
                    },
                    'time_based',
                    2
                )
            elif 14 <= hour <= 16:  # Afternoon
                self.create_suggestion(
                    'afternoon_check',
                    {
                        'message': 'Afternoon check-in! How are you doing? I can help you stay productive or take a well-deserved break.',
                        'actions': ['productivity_check', 'break_reminder', 'task_prioritization']
                    },
                    'time_based',
                    2
                )
            elif 18 <= hour <= 20:  # Evening
                self.create_suggestion(
                    'evening_wrapup',
                    {
                        'message': 'Evening time! Ready to wrap up? I can help you organize tomorrow\'s tasks or perform system maintenance.',
                        'actions': ['tomorrow_prep', 'system_cleanup', 'backup_reminder']
                    },
                    'time_based',
                    2
                )
            
            # System-based suggestions
            system_health = self.monitor_system_health()
            if system_health.get('memory_percent', 0) > 80:
                self.create_suggestion(
                    'memory_optimization',
                    {
                        'message': 'I notice your system memory usage is high. Would you like me to suggest ways to optimize it?',
                        'actions': ['close_unused_apps', 'clear_temp_files', 'memory_analysis']
                    },
                    'system_health',
                    3
                )
            
            # Learn initial user patterns
            self.learn_user_pattern('startup_time', {
                'time': datetime.now().strftime('%H:%M'),
                'day': datetime.now().strftime('%A'),
                'context': 'first_interaction'
            }, confidence=0.8)
            
            self.logger.info("Proactive features initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize proactive features: {e}")

    def _continuous_learning(self):
        """Continuous learning thread"""
        while self.monitoring_active:
            try:
                # Learn from user interactions
                self._learn_from_context()
                
                # Update user patterns
                self._update_user_patterns()
                
                # Generate proactive insights
                self._generate_proactive_insights()
                
                # Sleep for 10 minutes
                time.sleep(600)
            except Exception as e:
                self.logger.error(f"Continuous learning error: {e}")
                time.sleep(60)

    def _learn_from_context(self):
        """Learn from current context and user behavior"""
        try:
            current_time = datetime.now()
            hour = current_time.hour
            
            # Learn time-based patterns
            if 9 <= hour <= 17:
                self.learn_user_pattern('work_hours', {
                    'activity': 'work_session',
                    'time_range': '9-17',
                    'context': 'productive_hours'
                }, confidence=0.7)
            elif 18 <= hour <= 22:
                self.learn_user_pattern('evening_hours', {
                    'activity': 'evening_activities',
                    'time_range': '18-22',
                    'context': 'relaxation_time'
                }, confidence=0.7)
            
            # Learn system usage patterns
            system_health = self.monitor_system_health()
            if system_health.get('cpu_percent', 0) > 50:
                self.learn_user_pattern('high_usage', {
                    'activity': 'intensive_work',
                    'cpu_usage': system_health.get('cpu_percent', 0),
                    'context': 'system_load'
                }, confidence=0.6)
                
        except Exception as e:
            self.logger.error(f"Failed to learn from context: {e}")

    def _update_user_patterns(self):
        """Update and refine user patterns"""
        try:
            patterns = self.get_user_patterns()
            for pattern in patterns:
                if pattern['frequency'] > 5 and pattern['confidence'] > 0.7:
                    # Create proactive suggestion based on strong pattern
                    self.create_suggestion(
                        'pattern_based',
                        {
                            'message': f"I've noticed you often {pattern['pattern_data'].get('activity', 'do this activity')} around this time. Would you like me to help optimize this?",
                            'pattern': pattern['pattern_data'],
                            'actions': ['optimize_schedule', 'create_reminder', 'suggest_improvements']
                        },
                        'pattern_recognition',
                        2
                    )
        except Exception as e:
            self.logger.error(f"Failed to update user patterns: {e}")

    def _generate_proactive_insights(self):
        """Generate proactive insights and suggestions"""
        try:
            current_time = datetime.now()
            hour = current_time.hour
            
            # Time-based proactive suggestions
            if hour == 8:  # Morning
                self.create_suggestion(
                    'morning_optimization',
                    {
                        'message': 'Good morning! I\'ve analyzed your schedule and system. Ready to optimize your day?',
                        'actions': ['check_schedule', 'system_health', 'weather_update', 'news_brief']
                    },
                    'morning_routine',
                    3
                )
            elif hour == 17:  # Evening
                self.create_suggestion(
                    'evening_wrapup',
                    {
                        'message': 'Evening time! How was your day? I can help you wrap up and prepare for tomorrow.',
                        'actions': ['day_summary', 'tomorrow_prep', 'system_cleanup', 'backup_reminder']
                    },
                    'evening_routine',
                    2
                )
            elif hour == 12:  # Lunch break
                self.create_suggestion(
                    'lunch_break',
                    {
                        'message': 'Lunch break time! Perfect moment to check in. How are you doing?',
                        'actions': ['wellness_check', 'quick_break', 'light_entertainment']
                    },
                    'break_time',
                    1
                )
                
        except Exception as e:
            self.logger.error(f"Failed to generate proactive insights: {e}")

    def get_proactive_status(self):
        """Get current proactive status"""
        return {
            'always_active': self.always_proactive,
            'monitoring_active': self.monitoring_active,
            'suggestions_count': len(self.get_suggestions()),
            'patterns_learned': len(self.get_user_patterns()),
            'system_health': self.monitor_system_health(),
            'last_activity': datetime.now().isoformat()
        }

    def stop_monitoring(self):
        """Stop background monitoring"""
        self.monitoring_active = False

    def close(self):
        """Close database connection"""
        self.stop_monitoring()
        if self.conn:
            with self._db_lock:
                self.conn.close()
                self.conn = None

# Voice command helper functions
def format_suggestion_info(suggestion: Dict[str, Any]) -> str:
    """Format suggestion information for voice output"""
    suggestion_type = suggestion.get('suggestion_type', 'Unknown')
    priority = suggestion.get('priority', 1)
    created_at = suggestion.get('created_at', 'Unknown')
    
    return f"Suggestion '{suggestion_type}' with priority {priority}, created {created_at}"

def format_alert_info(alert: Dict[str, Any]) -> str:
    """Format alert information for voice output"""
    alert_type = alert.get('alert_type', 'Unknown')
    severity = alert.get('severity', 'info')
    message = alert.get('alert_message', 'No message')
    
    return f"{severity.upper()} alert: {alert_type} - {message}" 
