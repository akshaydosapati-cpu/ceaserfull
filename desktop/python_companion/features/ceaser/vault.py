import sqlite3
import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import hashlib
import secrets
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pathlib import Path

class VaultAssistant:
    def __init__(self, db_path='vault.db', vault_dir='./vault'):
        self.db_path = db_path
        self.vault_dir = Path(vault_dir)
        self.vault_dir.mkdir(exist_ok=True)
        
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()
        
        # Initialize logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Encryption key
        self.master_key = None
        self.cipher = None
        self.is_unlocked = False
        
        # Vault categories
        self.categories = {
            'passwords': 'Website and application passwords',
            'notes': 'Secure notes and documents',
            'cards': 'Credit card and payment information',
            'identities': 'Personal identification documents',
            'licenses': 'Software licenses and keys',
            'accounts': 'Bank and financial accounts',
            'general': 'General secure information'
        }

    def _create_tables(self):
        """Create SQLite tables for vault storage"""
        with self.conn:
            # Vault items
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS vault_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    encrypted_data TEXT NOT NULL,
                    tags TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_accessed DATETIME,
                    access_count INTEGER DEFAULT 0
                )
            ''')
            
            # Vault access logs
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS vault_access_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER,
                    action TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT,
                    user_agent TEXT,
                    FOREIGN KEY (item_id) REFERENCES vault_items (id)
                )
            ''')
            
            # Vault settings
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS vault_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting_key TEXT UNIQUE,
                    setting_value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_items_category ON vault_items(category)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_items_title ON vault_items(title)')

    def initialize_vault(self, master_password: str) -> bool:
        """Initialize vault with master password"""
        try:
            # Generate salt and derive key
            salt = secrets.token_bytes(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
            
            # Store salt
            with self.conn:
                self.conn.execute('''
                    INSERT OR REPLACE INTO vault_settings (setting_key, setting_value)
                    VALUES (?, ?)
                ''', ('salt', base64.b64encode(salt).decode()))
            
            self.master_key = key
            self.cipher = Fernet(key)
            self.is_unlocked = True
            
            self.logger.info("Vault initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize vault: {e}")
            return False

    def unlock_vault(self, master_password: str) -> bool:
        """Unlock vault with master password"""
        try:
            # Get stored salt
            cursor = self.conn.cursor()
            cursor.execute('SELECT setting_value FROM vault_settings WHERE setting_key = ?', ('salt',))
            result = cursor.fetchone()
            
            if not result:
                return False
            
            salt = base64.b64decode(result[0])
            
            # Derive key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
            
            self.master_key = key
            self.cipher = Fernet(key)
            self.is_unlocked = True
            
            self.logger.info("Vault unlocked successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to unlock vault: {e}")
            return False

    def lock_vault(self):
        """Lock the vault"""
        self.master_key = None
        self.cipher = None
        self.is_unlocked = False
        self.logger.info("Vault locked")

    def _encrypt_data(self, data: str) -> str:
        """Encrypt data"""
        if not self.cipher:
            raise ValueError("Vault is not unlocked")
        return self.cipher.encrypt(data.encode()).decode()

    def _decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt data"""
        if not self.cipher:
            raise ValueError("Vault is not unlocked")
        return self.cipher.decrypt(encrypted_data.encode()).decode()

    def add_password(self, title: str, username: str, password: str, url: str = "", 
                    notes: str = "", category: str = "passwords") -> int:
        """Add a password to the vault"""
        try:
            if not self.is_unlocked:
                return -1
            
            password_data = {
                'username': username,
                'password': password,
                'url': url,
                'notes': notes,
                'created_at': datetime.now().isoformat()
            }
            
            encrypted_data = self._encrypt_data(json.dumps(password_data))
            
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT INTO vault_items (category, title, encrypted_data)
                    VALUES (?, ?, ?)
                ''', (category, title, encrypted_data))
                
                item_id = cursor.lastrowid
                self.logger.info(f"Added password: {title}")
                return item_id
                
        except Exception as e:
            self.logger.error(f"Failed to add password: {e}")
            return -1

    def get_password(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get password by ID"""
        try:
            if not self.is_unlocked:
                return None
            
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT title, encrypted_data, created_at, updated_at
                FROM vault_items WHERE id = ?
            ''', (item_id,))
            
            result = cursor.fetchone()
            if not result:
                return None
            
            title, encrypted_data, created_at, updated_at = result
            
            # Decrypt data
            decrypted_data = json.loads(self._decrypt_data(encrypted_data))
            
            # Update access statistics
            with self.conn:
                self.conn.execute('''
                    UPDATE vault_items 
                    SET last_accessed = CURRENT_TIMESTAMP, access_count = access_count + 1
                    WHERE id = ?
                ''', (item_id,))
            
            return {
                'id': item_id,
                'title': title,
                'username': decrypted_data['username'],
                'password': decrypted_data['password'],
                'url': decrypted_data.get('url', ''),
                'notes': decrypted_data.get('notes', ''),
                'created_at': created_at,
                'updated_at': updated_at
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get password: {e}")
            return None

    def search_passwords(self, query: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search passwords"""
        try:
            if not self.is_unlocked:
                return []
            
            cursor = self.conn.cursor()
            if category:
                cursor.execute('''
                    SELECT id, title, encrypted_data, created_at
                    FROM vault_items
                    WHERE category = ? AND title LIKE ?
                    ORDER BY title
                ''', (category, f'%{query}%'))
            else:
                cursor.execute('''
                    SELECT id, title, encrypted_data, created_at
                    FROM vault_items
                    WHERE title LIKE ?
                    ORDER BY title
                ''', (f'%{query}%',))
            
            results = []
            for row in cursor.fetchall():
                item_id, title, encrypted_data, created_at = row
                try:
                    decrypted_data = json.loads(self._decrypt_data(encrypted_data))
                    results.append({
                        'id': item_id,
                        'title': title,
                        'username': decrypted_data['username'],
                        'url': decrypted_data.get('url', ''),
                        'created_at': created_at
                    })
                except Exception as e:
                    self.logger.error(f"Failed to decrypt item {item_id}: {e}")
                    continue
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to search passwords: {e}")
            return []

    def add_secure_note(self, title: str, content: str, category: str = "notes") -> int:
        """Add a secure note to the vault"""
        try:
            if not self.is_unlocked:
                return -1
            
            note_data = {
                'content': content,
                'created_at': datetime.now().isoformat()
            }
            
            encrypted_data = self._encrypt_data(json.dumps(note_data))
            
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT INTO vault_items (category, title, encrypted_data)
                    VALUES (?, ?, ?)
                ''', (category, title, encrypted_data))
                
                item_id = cursor.lastrowid
                self.logger.info(f"Added secure note: {title}")
                return item_id
                
        except Exception as e:
            self.logger.error(f"Failed to add secure note: {e}")
            return -1

    def get_secure_note(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get secure note by ID"""
        try:
            if not self.is_unlocked:
                return None
            
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT title, encrypted_data, created_at, updated_at
                FROM vault_items WHERE id = ?
            ''', (item_id,))
            
            result = cursor.fetchone()
            if not result:
                return None
            
            title, encrypted_data, created_at, updated_at = result
            
            # Decrypt data
            decrypted_data = json.loads(self._decrypt_data(encrypted_data))
            
            return {
                'id': item_id,
                'title': title,
                'content': decrypted_data['content'],
                'created_at': created_at,
                'updated_at': updated_at
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get secure note: {e}")
            return None

    def add_credit_card(self, title: str, card_number: str, expiry_date: str, 
                       cvv: str, cardholder_name: str, notes: str = "") -> int:
        """Add credit card information to vault"""
        try:
            if not self.is_unlocked:
                return -1
            
            card_data = {
                'card_number': card_number,
                'expiry_date': expiry_date,
                'cvv': cvv,
                'cardholder_name': cardholder_name,
                'notes': notes,
                'created_at': datetime.now().isoformat()
            }
            
            encrypted_data = self._encrypt_data(json.dumps(card_data))
            
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT INTO vault_items (category, title, encrypted_data)
                    VALUES (?, ?, ?)
                ''', ('cards', title, encrypted_data))
                
                item_id = cursor.lastrowid
                self.logger.info(f"Added credit card: {title}")
                return item_id
                
        except Exception as e:
            self.logger.error(f"Failed to add credit card: {e}")
            return -1

    def generate_strong_password(self, length: int = 16, include_symbols: bool = True) -> str:
        """Generate a strong password"""
        try:
            characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            if include_symbols:
                characters += "!@#$%^&*()_+-=[]{}|;:,.<>?"
            
            password = ''.join(secrets.choice(characters) for _ in range(length))
            return password
            
        except Exception as e:
            self.logger.error(f"Failed to generate password: {e}")
            return ""

    def get_vault_statistics(self) -> Dict[str, Any]:
        """Get vault statistics"""
        try:
            cursor = self.conn.cursor()
            
            # Total items
            cursor.execute('SELECT COUNT(*) FROM vault_items')
            total_items = cursor.fetchone()[0]
            
            # Items by category
            cursor.execute('''
                SELECT category, COUNT(*) as count
                FROM vault_items GROUP BY category
            ''')
            category_stats = {}
            for row in cursor.fetchall():
                category, count = row
                category_stats[category] = count
            
            # Most accessed items
            cursor.execute('''
                SELECT title, access_count, category
                FROM vault_items 
                ORDER BY access_count DESC 
                LIMIT 10
            ''')
            most_accessed = []
            for row in cursor.fetchall():
                title, access_count, category = row
                most_accessed.append({
                    'title': title,
                    'access_count': access_count,
                    'category': category
                })
            
            return {
                'total_items': total_items,
                'category_stats': category_stats,
                'most_accessed': most_accessed,
                'is_unlocked': self.is_unlocked
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get vault statistics: {e}")
            return {}

    def export_vault(self, export_path: str) -> bool:
        """Export vault data (encrypted)"""
        try:
            if not self.is_unlocked:
                return False
            
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT category, title, encrypted_data, created_at, updated_at
                FROM vault_items
                ORDER BY category, title
            ''')
            
            export_data = {
                'export_date': datetime.now().isoformat(),
                'items': []
            }
            
            for row in cursor.fetchall():
                category, title, encrypted_data, created_at, updated_at = row
                export_data['items'].append({
                    'category': category,
                    'title': title,
                    'encrypted_data': encrypted_data,
                    'created_at': created_at,
                    'updated_at': updated_at
                })
            
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            self.logger.info(f"Vault exported to: {export_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export vault: {e}")
            return False

    def import_vault(self, import_path: str) -> bool:
        """Import vault data"""
        try:
            if not self.is_unlocked:
                return False
            
            with open(import_path, 'r') as f:
                import_data = json.load(f)
            
            with self.conn:
                for item in import_data.get('items', []):
                    self.conn.execute('''
                        INSERT OR IGNORE INTO vault_items 
                        (category, title, encrypted_data, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (item['category'], item['title'], item['encrypted_data'],
                         item['created_at'], item['updated_at']))
            
            self.logger.info(f"Vault imported from: {import_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to import vault: {e}")
            return False

    def handle_voice_command(self, cmd: str) -> str:
        """Handle voice commands for vault features"""
        cmd = cmd.lower()
        
        if "add password" in cmd:
            return "To add a password, I need: title, username, password, and optionally URL and notes."
        
        elif "search password" in cmd or "find password" in cmd:
            # Extract search query
            query_start = cmd.find("for") + 4 if "for" in cmd else cmd.find("password") + 9
            query = cmd[query_start:].strip()
            if query:
                results = self.search_passwords(query)
                if results:
                    return f"Found {len(results)} passwords matching '{query}'. Check the app for details."
                else:
                    return f"No passwords found matching '{query}'."
            else:
                return "Please specify what to search for. Say 'search password for [query]'"
        
        elif "generate password" in cmd:
            length = 16
            if "length" in cmd:
                try:
                    length_text = cmd.split("length")[1].split()[0]
                    length = int(length_text)
                except:
                    pass
            
            password = self.generate_strong_password(length)
            if password:
                return f"Generated password: {password}"
            else:
                return "Failed to generate password."
        
        elif "vault statistics" in cmd or "vault stats" in cmd:
            stats = self.get_vault_statistics()
            total = stats.get('total_items', 0)
            unlocked = "unlocked" if stats.get('is_unlocked', False) else "locked"
            return f"Vault contains {total} items and is currently {unlocked}."
        
        elif "lock vault" in cmd:
            self.lock_vault()
            return "Vault locked successfully."
        
        elif "unlock vault" in cmd:
            return "To unlock the vault, please provide the master password."
        
        elif "export vault" in cmd:
            # This would need a file path
            return "To export the vault, please specify the export file path."
        
        else:
            return "Vault command not recognized. Try 'add password', 'search password', 'generate password', or 'lock vault'."

    def close(self):
        """Close database connection and lock vault"""
        self.lock_vault()
        if self.conn:
            self.conn.close()

# Voice command helper functions
def format_vault_item_info(item: Dict[str, Any]) -> str:
    """Format vault item information for voice output"""
    title = item.get('title', 'Untitled')
    category = item.get('category', 'general')
    created_at = item.get('created_at', 'Unknown')
    
    return f"Vault item '{title}' in {category} category, created {created_at}"

def format_password_info(password: Dict[str, Any]) -> str:
    """Format password information for voice output"""
    title = password.get('title', 'Untitled')
    username = password.get('username', 'Unknown')
    url = password.get('url', '')
    
    return f"Password for '{title}', username: {username}{', URL: ' + url if url else ''}" 