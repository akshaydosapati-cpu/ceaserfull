import sqlite3
import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import hashlib
import secrets
from pathlib import Path

class MultiUserAssistant:
    def __init__(self, db_path='multiuser.db', users_dir='./users'):
        self.db_path = db_path
        self.users_dir = Path(users_dir)
        self.users_dir.mkdir(exist_ok=True)
        
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()
        
        # Initialize logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Current active user
        self.current_user = None
        self.current_user_id = None
        
        # User sessions
        self.active_sessions = {}

    def _create_tables(self):
        """Create SQLite tables for multi-user support"""
        with self.conn:
            # Users table
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    full_name TEXT,
                    role TEXT DEFAULT 'user',
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME,
                    preferences TEXT
                )
            ''')
            
            # User profiles
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    profile_type TEXT,
                    profile_data TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # User sessions
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    session_token TEXT UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # User permissions
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS user_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    permission_name TEXT,
                    permission_value TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Create indexes
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(session_token)')

    def create_user(self, username: str, password: str, email: Optional[str] = None, 
                   full_name: Optional[str] = None, role: str = 'user') -> int:
        """Create a new user account"""
        try:
            # Generate salt and hash password
            salt = secrets.token_hex(16)
            password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT INTO users (username, email, password_hash, salt, full_name, role)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (username, email, password_hash, salt, full_name, role))
                
                user_id = cursor.lastrowid
                
                # Create user directory
                user_dir = self.users_dir / str(user_id)
                user_dir.mkdir(exist_ok=True)
                
                # Set default preferences
                default_preferences = {
                    'theme': 'dark',
                    'language': 'en',
                    'notifications': True,
                    'voice_speed': 1.0,
                    'accessibility': {
                        'high_contrast': False,
                        'large_text': False
                    }
                }
                
                cursor.execute('''
                    UPDATE users SET preferences = ? WHERE id = ?
                ''', (json.dumps(default_preferences), user_id))
                
                self.logger.info(f"Created user: {username} (ID: {user_id})")
                return user_id
                
        except Exception as e:
            self.logger.error(f"Failed to create user: {e}")
            return -1

    def authenticate_user(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and return session token"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, password_hash, salt, is_active
                FROM users WHERE username = ?
            ''', (username,))
            
            result = cursor.fetchone()
            if not result:
                return None
            
            user_id, stored_hash, salt, is_active = result
            
            if not is_active:
                return None
            
            # Verify password
            password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            if password_hash != stored_hash:
                return None
            
            # Generate session token
            session_token = secrets.token_urlsafe(32)
            expires_at = datetime.now().timestamp() + (24 * 60 * 60)  # 24 hours
            
            # Store session
            with self.conn:
                self.conn.execute('''
                    INSERT INTO user_sessions (user_id, session_token, expires_at)
                    VALUES (?, ?, datetime(?, 'unixepoch'))
                ''', (user_id, session_token, expires_at))
                
                # Update last login
                self.conn.execute('''
                    UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
                ''', (user_id,))
            
            # Set current user
            self.current_user_id = user_id
            self.current_user = username
            self.active_sessions[session_token] = {
                'user_id': user_id,
                'username': username,
                'created_at': datetime.now(),
                'expires_at': datetime.fromtimestamp(expires_at)
            }
            
            self.logger.info(f"User authenticated: {username}")
            return session_token
            
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            return None

    def validate_session(self, session_token: str) -> bool:
        """Validate session token"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT user_id, expires_at, is_active
                FROM user_sessions
                WHERE session_token = ?
            ''', (session_token,))
            
            result = cursor.fetchone()
            if not result:
                return False
            
            user_id, expires_at, is_active = result
            
            if not is_active:
                return False
            
            # Check if session expired
            if datetime.fromisoformat(expires_at) < datetime.now():
                return False
            
            # Set current user
            cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
            username = cursor.fetchone()[0]
            
            self.current_user_id = user_id
            self.current_user = username
            
            return True
            
        except Exception as e:
            self.logger.error(f"Session validation failed: {e}")
            return False

    def logout_user(self, session_token: str) -> bool:
        """Logout user and invalidate session"""
        try:
            with self.conn:
                self.conn.execute('''
                    UPDATE user_sessions 
                    SET is_active = 0
                    WHERE session_token = ?
                ''', (session_token,))
            
            # Remove from active sessions
            if session_token in self.active_sessions:
                del self.active_sessions[session_token]
            
            # Clear current user
            if self.current_user_id:
                self.current_user_id = None
                self.current_user = None
            
            return True
            
        except Exception as e:
            self.logger.error(f"Logout failed: {e}")
            return False

    def get_user_profile(self, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get user profile information"""
        try:
            if not user_id:
                user_id = self.current_user_id
            
            if not user_id:
                return None
            
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, username, email, full_name, role, created_at, last_login, preferences
                FROM users WHERE id = ?
            ''', (user_id,))
            
            result = cursor.fetchone()
            if not result:
                return None
            
            user_id, username, email, full_name, role, created_at, last_login, preferences = result
            
            return {
                'id': user_id,
                'username': username,
                'email': email,
                'full_name': full_name,
                'role': role,
                'created_at': created_at,
                'last_login': last_login,
                'preferences': json.loads(preferences) if preferences else {}
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get user profile: {e}")
            return None

    def update_user_preferences(self, preferences: Dict[str, Any], user_id: Optional[int] = None) -> bool:
        """Update user preferences"""
        try:
            if not user_id:
                user_id = self.current_user_id
            
            if not user_id:
                return False
            
            with self.conn:
                self.conn.execute('''
                    UPDATE users 
                    SET preferences = ?
                    WHERE id = ?
                ''', (json.dumps(preferences), user_id))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update preferences: {e}")
            return False

    def get_user_permissions(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get user permissions"""
        try:
            if not user_id:
                user_id = self.current_user_id
            
            if not user_id:
                return []
            
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT permission_name, permission_value
                FROM user_permissions
                WHERE user_id = ?
            ''', (user_id,))
            
            permissions = []
            for row in cursor.fetchall():
                permission_name, permission_value = row
                permissions.append({
                    'name': permission_name,
                    'value': permission_value
                })
            
            return permissions
            
        except Exception as e:
            self.logger.error(f"Failed to get permissions: {e}")
            return []

    def set_user_permission(self, permission_name: str, permission_value: str, 
                          user_id: Optional[int] = None) -> bool:
        """Set user permission"""
        try:
            if not user_id:
                user_id = self.current_user_id
            
            if not user_id:
                return False
            
            with self.conn:
                self.conn.execute('''
                    INSERT OR REPLACE INTO user_permissions (user_id, permission_name, permission_value)
                    VALUES (?, ?, ?)
                ''', (user_id, permission_name, permission_value))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set permission: {e}")
            return False

    def switch_user_profile(self, profile_type: str) -> bool:
        """Switch to a different user profile"""
        try:
            if not self.current_user_id:
                return False
            
            # Get profile data
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT profile_data
                FROM user_profiles
                WHERE user_id = ? AND profile_type = ?
            ''', (self.current_user_id, profile_type))
            
            result = cursor.fetchone()
            if result:
                profile_data = json.loads(result[0])
                # Apply profile settings
                self.update_user_preferences(profile_data.get('preferences', {}))
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to switch profile: {e}")
            return False

    def create_user_profile(self, profile_type: str, profile_data: Dict[str, Any]) -> bool:
        """Create a new user profile"""
        try:
            if not self.current_user_id:
                return False
            
            with self.conn:
                self.conn.execute('''
                    INSERT OR REPLACE INTO user_profiles (user_id, profile_type, profile_data)
                    VALUES (?, ?, ?)
                ''', (self.current_user_id, profile_type, json.dumps(profile_data)))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create profile: {e}")
            return False

    def get_all_users(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """Get all users (admin function)"""
        try:
            cursor = self.conn.cursor()
            if include_inactive:
                cursor.execute('''
                    SELECT id, username, email, full_name, role, is_active, created_at, last_login
                    FROM users
                    ORDER BY created_at DESC
                ''')
            else:
                cursor.execute('''
                    SELECT id, username, email, full_name, role, is_active, created_at, last_login
                    FROM users
                    WHERE is_active = 1
                    ORDER BY created_at DESC
                ''')
            
            users = []
            for row in cursor.fetchall():
                user_id, username, email, full_name, role, is_active, created_at, last_login = row
                users.append({
                    'id': user_id,
                    'username': username,
                    'email': email,
                    'full_name': full_name,
                    'role': role,
                    'is_active': bool(is_active),
                    'created_at': created_at,
                    'last_login': last_login
                })
            
            return users
            
        except Exception as e:
            self.logger.error(f"Failed to get users: {e}")
            return []

    def handle_voice_command(self, cmd: str) -> str:
        """Handle voice commands for multi-user features"""
        cmd = cmd.lower()
        
        if "switch user" in cmd or "change user" in cmd:
            # Extract username
            username_start = cmd.find("to") + 3 if "to" in cmd else cmd.find("user") + 5
            username = cmd[username_start:].strip()
            if username:
                return f"To switch to user '{username}', please provide the password."
            else:
                return "Please specify the username. Say 'switch user to [username]'"
        
        elif "create user" in cmd or "add user" in cmd:
            return "To create a new user, I need: username, password, and optionally email and full name."
        
        elif "my profile" in cmd or "user profile" in cmd:
            profile = self.get_user_profile()
            if profile:
                return f"Your profile: {profile['username']}, role: {profile['role']}, created: {profile['created_at']}"
            else:
                return "No user profile found. Please log in first."
        
        elif "my preferences" in cmd:
            profile = self.get_user_profile()
            if profile and profile.get('preferences'):
                prefs = profile['preferences']
                return f"Your preferences: theme {prefs.get('theme', 'default')}, language {prefs.get('language', 'en')}"
            else:
                return "No preferences found. Please log in first."
        
        elif "logout" in cmd or "sign out" in cmd:
            if self.current_user:
                # This would need session token from context
                return f"Logging out {self.current_user}. Please confirm."
            else:
                return "No user is currently logged in."
        
        elif "user list" in cmd or "all users" in cmd:
            users = self.get_all_users()
            if users:
                usernames = [user['username'] for user in users[:5]]  # Show first 5
                return f"Users: {', '.join(usernames)}"
            else:
                return "No users found."
        
        else:
            return "Multi-user command not recognized. Try 'switch user to [username]', 'my profile', or 'logout'."

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

# Voice command helper functions
def format_user_info(user: Dict[str, Any]) -> str:
    """Format user information for voice output"""
    username = user.get('username', 'Unknown')
    role = user.get('role', 'user')
    created_at = user.get('created_at', 'Unknown')
    
    return f"User '{username}' with role {role}, created {created_at}"

def format_profile_info(profile: Dict[str, Any]) -> str:
    """Format profile information for voice output"""
    profile_type = profile.get('profile_type', 'Unknown')
    created_at = profile.get('created_at', 'Unknown')
    
    return f"Profile '{profile_type}' created {created_at}" 