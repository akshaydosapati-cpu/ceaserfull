import sqlite3
import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import re
import threading
import logging
from pathlib import Path
import hashlib

class NoteTakingAssistant:
    def __init__(self, db_path='notes.db', notes_dir='./notes'):
        self.db_path = db_path
        self.notes_dir = Path(notes_dir)
        self.notes_dir.mkdir(exist_ok=True)
        
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()
        
        # Note categories and tags
        self.categories = {
            'personal': 'Personal notes and thoughts',
            'work': 'Work-related notes and tasks',
            'meeting': 'Meeting notes and minutes',
            'idea': 'Ideas and brainstorming',
            'todo': 'To-do lists and tasks',
            'research': 'Research notes and findings',
            'journal': 'Daily journal entries',
            'learning': 'Learning notes and tutorials',
            'project': 'Project-specific notes',
            'general': 'General notes'
        }
        
        # Initialize logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Start background tasks
        self.cleanup_thread = threading.Thread(target=self._background_cleanup, daemon=True)
        self.cleanup_thread.start()

    def _create_tables(self):
        """Create SQLite tables for note storage"""
        with self.conn:
            # Main notes table
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT,
                    category TEXT DEFAULT 'general',
                    tags TEXT,
                    importance INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    accessed_count INTEGER DEFAULT 0,
                    last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
                    file_path TEXT,
                    metadata TEXT
                )
            ''')
            
            # Note versions for history
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS note_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id INTEGER,
                    content TEXT,
                    version_number INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (note_id) REFERENCES notes (id)
                )
            ''')
            
            # Note relationships
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS note_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_note_id INTEGER,
                    target_note_id INTEGER,
                    relationship_type TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_note_id) REFERENCES notes (id),
                    FOREIGN KEY (target_note_id) REFERENCES notes (id)
                )
            ''')
            
            # Note templates
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS note_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    content TEXT,
                    category TEXT,
                    tags TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_notes_category ON notes(category)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes(created_at)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_notes_title ON notes(title)')

    def create_note(self, title: str, content: str = "", category: str = "general", 
                   tags: Optional[List[str]] = None, importance: int = 1,
                   metadata: Optional[Dict] = None) -> int:
        """Create a new note"""
        try:
            # Generate file path for the note
            safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_title}_{timestamp}.md"
            file_path = self.notes_dir / filename
            
            # Save note content to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# {title}\n\n")
                f.write(f"**Category:** {category}\n")
                f.write(f"**Created:** {datetime.now().isoformat()}\n")
                if tags:
                    f.write(f"**Tags:** {', '.join(tags)}\n")
                f.write(f"**Importance:** {importance}\n\n")
                f.write("---\n\n")
                f.write(content)
            
            # Store in database
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT INTO notes (title, content, category, tags, importance, file_path, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (title, content, category, json.dumps(tags) if tags else None, 
                     importance, str(file_path), json.dumps(metadata) if metadata else None))
                
                note_id = cursor.lastrowid
                
                # Create initial version
                cursor.execute('''
                    INSERT INTO note_versions (note_id, content, version_number)
                    VALUES (?, ?, 1)
                ''', (note_id, content))
            
            self.logger.info(f"Created note: {title} (ID: {note_id})")
            return note_id
            
        except Exception as e:
            self.logger.error(f"Failed to create note: {e}")
            return -1

    def get_note(self, note_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a note by ID"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, title, content, category, tags, importance, 
                       created_at, updated_at, accessed_count, file_path, metadata
                FROM notes WHERE id = ?
            ''', (note_id,))
            
            result = cursor.fetchone()
            if not result:
                return None
            
            note_id, title, content, category, tags, importance, created_at, updated_at, accessed_count, file_path, metadata = result
            
            # Update access statistics
            self._update_access_stats(note_id)
            
            return {
                'id': note_id,
                'title': title,
                'content': content,
                'category': category,
                'tags': json.loads(tags) if tags else [],
                'importance': importance,
                'created_at': created_at,
                'updated_at': updated_at,
                'accessed_count': accessed_count + 1,
                'file_path': file_path,
                'metadata': json.loads(metadata) if metadata else {}
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get note {note_id}: {e}")
            return None

    def update_note(self, note_id: int, title: Optional[str] = None, content: Optional[str] = None,
                   category: Optional[str] = None, tags: Optional[List[str]] = None,
                   importance: Optional[int] = None) -> bool:
        """Update an existing note"""
        try:
            # Get current note
            current_note = self.get_note(note_id)
            if not current_note:
                return False
            
            # Prepare update data
            update_data = {}
            if title is not None:
                update_data['title'] = title
            if content is not None:
                update_data['content'] = content
            if category is not None:
                update_data['category'] = category
            if tags is not None:
                update_data['tags'] = json.dumps(tags)
            if importance is not None:
                update_data['importance'] = importance
            
            if not update_data:
                return True  # No changes
            
            # Update database
            with self.conn:
                set_clause = ', '.join([f"{k} = ?" for k in update_data.keys()])
                values = list(update_data.values()) + [note_id]
                
                self.conn.execute(f'''
                    UPDATE notes 
                    SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', values)
                
                # Create new version if content changed
                if content is not None:
                    cursor = self.conn.cursor()
                    cursor.execute('''
                        SELECT MAX(version_number) FROM note_versions WHERE note_id = ?
                    ''', (note_id,))
                    max_version = cursor.fetchone()[0] or 0
                    
                    cursor.execute('''
                        INSERT INTO note_versions (note_id, content, version_number)
                        VALUES (?, ?, ?)
                    ''', (note_id, content, max_version + 1))
            
            # Update file
            if content is not None or title is not None:
                self._update_note_file(note_id, title or current_note['title'], 
                                     content or current_note['content'],
                                     category or current_note['category'],
                                     tags or current_note['tags'],
                                     importance or current_note['importance'])
            
            self.logger.info(f"Updated note: {note_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update note {note_id}: {e}")
            return False

    def delete_note(self, note_id: int) -> bool:
        """Delete a note"""
        try:
            # Get note file path
            cursor = self.conn.cursor()
            cursor.execute('SELECT file_path FROM notes WHERE id = ?', (note_id,))
            result = cursor.fetchone()
            
            if result:
                file_path = result[0]
                # Delete file if it exists
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            
            # Delete from database
            with self.conn:
                self.conn.execute('DELETE FROM note_versions WHERE note_id = ?', (note_id,))
                self.conn.execute('DELETE FROM note_relationships WHERE source_note_id = ? OR target_note_id = ?', 
                                (note_id, note_id))
                self.conn.execute('DELETE FROM notes WHERE id = ?', (note_id,))
            
            self.logger.info(f"Deleted note: {note_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete note {note_id}: {e}")
            return False

    def search_notes(self, query: str, category: Optional[str] = None, 
                    tags: Optional[List[str]] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Search notes by content, title, or tags"""
        try:
            cursor = self.conn.cursor()
            
            # Build search conditions
            conditions = []
            params = []
            
            # Text search
            if query:
                conditions.append("(title LIKE ? OR content LIKE ?)")
                params.extend([f'%{query}%', f'%{query}%'])
            
            # Category filter
            if category:
                conditions.append("category = ?")
                params.append(category)
            
            # Tags filter
            if tags:
                tag_conditions = []
                for tag in tags:
                    tag_conditions.append("tags LIKE ?")
                    params.append(f'%{tag}%')
                conditions.append(f"({' OR '.join(tag_conditions)})")
            
            # Build query
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            cursor.execute(f'''
                SELECT id, title, content, category, tags, importance, 
                       created_at, updated_at, accessed_count
                FROM notes 
                WHERE {where_clause}
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
            ''', params + [limit])
            
            notes = []
            for row in cursor.fetchall():
                note_id, title, content, category, tags, importance, created_at, updated_at, accessed_count = row
                
                # Truncate content for preview
                content_preview = content[:200] + "..." if len(content) > 200 else content
                
                notes.append({
                    'id': note_id,
                    'title': title,
                    'content_preview': content_preview,
                    'category': category,
                    'tags': json.loads(tags) if tags else [],
                    'importance': importance,
                    'created_at': created_at,
                    'updated_at': updated_at,
                    'accessed_count': accessed_count
                })
            
            return notes
            
        except Exception as e:
            self.logger.error(f"Failed to search notes: {e}")
            return []

    def get_notes_by_category(self, category: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get all notes in a specific category"""
        return self.search_notes("", category=category, limit=limit)

    def get_recent_notes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recently created or updated notes"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, title, content, category, tags, importance, 
                       created_at, updated_at, accessed_count
                FROM notes 
                ORDER BY updated_at DESC
                LIMIT ?
            ''', (limit,))
            
            notes = []
            for row in cursor.fetchall():
                note_id, title, content, category, tags, importance, created_at, updated_at, accessed_count = row
                
                content_preview = content[:150] + "..." if len(content) > 150 else content
                
                notes.append({
                    'id': note_id,
                    'title': title,
                    'content_preview': content_preview,
                    'category': category,
                    'tags': json.loads(tags) if tags else [],
                    'importance': importance,
                    'created_at': created_at,
                    'updated_at': updated_at,
                    'accessed_count': accessed_count
                })
            
            return notes
            
        except Exception as e:
            self.logger.error(f"Failed to get recent notes: {e}")
            return []

    def get_note_history(self, note_id: int) -> List[Dict[str, Any]]:
        """Get version history of a note"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT version_number, content, created_at
                FROM note_versions
                WHERE note_id = ?
                ORDER BY version_number DESC
            ''', (note_id,))
            
            versions = []
            for row in cursor.fetchall():
                version_number, content, created_at = row
                versions.append({
                    'version_number': version_number,
                    'content': content,
                    'created_at': created_at
                })
            
            return versions
            
        except Exception as e:
            self.logger.error(f"Failed to get note history: {e}")
            return []

    def create_template(self, name: str, content: str, category: str = "general", 
                       tags: Optional[List[str]] = None) -> int:
        """Create a note template"""
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT INTO note_templates (name, content, category, tags)
                    VALUES (?, ?, ?, ?)
                ''', (name, content, category, json.dumps(tags) if tags else None))
                
                template_id = cursor.lastrowid
                self.logger.info(f"Created template: {name} (ID: {template_id})")
                return template_id
                
        except Exception as e:
            self.logger.error(f"Failed to create template: {e}")
            return -1

    def get_templates(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get available note templates"""
        try:
            cursor = self.conn.cursor()
            if category:
                cursor.execute('''
                    SELECT id, name, content, category, tags, created_at
                    FROM note_templates
                    WHERE category = ?
                    ORDER BY name
                ''', (category,))
            else:
                cursor.execute('''
                    SELECT id, name, content, category, tags, created_at
                    FROM note_templates
                    ORDER BY name
                ''')
            
            templates = []
            for row in cursor.fetchall():
                template_id, name, content, cat, tags, created_at = row
                templates.append({
                    'id': template_id,
                    'name': name,
                    'content': content,
                    'category': cat,
                    'tags': json.loads(tags) if tags else [],
                    'created_at': created_at
                })
            
            return templates
            
        except Exception as e:
            self.logger.error(f"Failed to get templates: {e}")
            return []

    def create_note_from_template(self, template_id: int, title: str, 
                                custom_content: Optional[str] = None) -> int:
        """Create a new note from a template"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT content, category, tags
                FROM note_templates
                WHERE id = ?
            ''', (template_id,))
            
            result = cursor.fetchone()
            if not result:
                return -1
            
            template_content, category, tags = result
            
            # Use custom content if provided, otherwise use template content
            content = custom_content if custom_content else template_content
            
            # Create note from template
            note_id = self.create_note(
                title=title,
                content=content,
                category=category,
                tags=json.loads(tags) if tags else None
            )
            
            return note_id
            
        except Exception as e:
            self.logger.error(f"Failed to create note from template: {e}")
            return -1

    def link_notes(self, source_note_id: int, target_note_id: int, 
                  relationship_type: str = "related") -> bool:
        """Create a relationship between two notes"""
        try:
            with self.conn:
                self.conn.execute('''
                    INSERT OR REPLACE INTO note_relationships 
                    (source_note_id, target_note_id, relationship_type)
                    VALUES (?, ?, ?)
                ''', (source_note_id, target_note_id, relationship_type))
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to link notes: {e}")
            return False

    def get_related_notes(self, note_id: int, relationship_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get notes related to a specific note"""
        try:
            cursor = self.conn.cursor()
            if relationship_type:
                cursor.execute('''
                    SELECT n.id, n.title, n.category, r.relationship_type
                    FROM notes n
                    JOIN note_relationships r ON n.id = r.target_note_id
                    WHERE r.source_note_id = ? AND r.relationship_type = ?
                    ORDER BY n.updated_at DESC
                ''', (note_id, relationship_type))
            else:
                cursor.execute('''
                    SELECT n.id, n.title, n.category, r.relationship_type
                    FROM notes n
                    JOIN note_relationships r ON n.id = r.target_note_id
                    WHERE r.source_note_id = ?
                    ORDER BY n.updated_at DESC
                ''', (note_id,))
            
            related_notes = []
            for row in cursor.fetchall():
                related_id, title, category, rel_type = row
                related_notes.append({
                    'id': related_id,
                    'title': title,
                    'category': category,
                    'relationship_type': rel_type
                })
            
            return related_notes
            
        except Exception as e:
            self.logger.error(f"Failed to get related notes: {e}")
            return []

    def get_note_statistics(self) -> Dict[str, Any]:
        """Get statistics about notes"""
        try:
            cursor = self.conn.cursor()
            
            # Total notes
            cursor.execute('SELECT COUNT(*) FROM notes')
            total_notes = cursor.fetchone()[0]
            
            # Notes by category
            cursor.execute('''
                SELECT category, COUNT(*) as count
                FROM notes GROUP BY category
            ''')
            category_stats = {}
            for row in cursor.fetchall():
                category, count = row
                category_stats[category] = count
            
            # Most accessed notes
            cursor.execute('''
                SELECT title, accessed_count, category
                FROM notes 
                ORDER BY accessed_count DESC 
                LIMIT 10
            ''')
            most_accessed = []
            for row in cursor.fetchall():
                title, accessed_count, category = row
                most_accessed.append({
                    'title': title,
                    'accessed_count': accessed_count,
                    'category': category
                })
            
            # Recent activity
            cursor.execute('''
                SELECT COUNT(*) FROM notes 
                WHERE updated_at >= datetime('now', '-7 days')
            ''')
            recent_activity = cursor.fetchone()[0]
            
            return {
                'total_notes': total_notes,
                'category_stats': category_stats,
                'most_accessed': most_accessed,
                'recent_activity': recent_activity
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get note statistics: {e}")
            return {}

    def handle_voice_command(self, cmd: str) -> str:
        """Handle voice commands for note taking"""
        cmd = cmd.lower()
        
        if "create note" in cmd or "new note" in cmd:
            # Extract title from command
            title_start = cmd.find("title") + 6 if "title" in cmd else cmd.find("note") + 5
            title = cmd[title_start:].strip()
            if title:
                note_id = self.create_note(title=title, content="")
                if note_id > 0:
                    return f"Created new note: {title}. You can now add content to it."
                else:
                    return "Failed to create note. Please try again."
            else:
                return "Please specify a title for the note. Say 'create note title [title]'"
        
        elif "search notes" in cmd or "find notes" in cmd:
            query_start = cmd.find("for") + 4 if "for" in cmd else cmd.find("notes") + 6
            query = cmd[query_start:].strip()
            if query:
                notes = self.search_notes(query, limit=5)
                if notes:
                    return f"Found {len(notes)} notes matching '{query}'. Check the app for details."
                else:
                    return f"No notes found matching '{query}'."
            else:
                return "Please specify what to search for. Say 'search notes for [query]'"
        
        elif "recent notes" in cmd or "latest notes" in cmd:
            notes = self.get_recent_notes(limit=5)
            if notes:
                return f"You have {len(notes)} recent notes. Check the app for details."
            else:
                return "You have no notes yet."
        
        elif "note statistics" in cmd or "note stats" in cmd:
            stats = self.get_note_statistics()
            total = stats.get('total_notes', 0)
            recent = stats.get('recent_activity', 0)
            return f"You have {total} total notes with {recent} updated in the last week."
        
        else:
            return "Note command not recognized. Try 'create note title [title]', 'search notes for [query]', or 'recent notes'."

    def _update_access_stats(self, note_id: int):
        """Update access statistics for a note"""
        try:
            with self.conn:
                self.conn.execute('''
                    UPDATE notes 
                    SET accessed_count = accessed_count + 1, 
                        last_accessed = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (note_id,))
        except Exception as e:
            self.logger.error(f"Failed to update access stats: {e}")

    def _update_note_file(self, note_id: int, title: str, content: str, 
                         category: str, tags: List[str], importance: int):
        """Update the markdown file for a note"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT file_path FROM notes WHERE id = ?', (note_id,))
            result = cursor.fetchone()
            
            if result and result[0]:
                file_path = result[0]
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {title}\n\n")
                    f.write(f"**Category:** {category}\n")
                    f.write(f"**Updated:** {datetime.now().isoformat()}\n")
                    if tags:
                        f.write(f"**Tags:** {', '.join(tags)}\n")
                    f.write(f"**Importance:** {importance}\n\n")
                    f.write("---\n\n")
                    f.write(content)
        except Exception as e:
            self.logger.error(f"Failed to update note file: {e}")

    def _background_cleanup(self):
        """Background thread for cleanup tasks"""
        while True:
            try:
                time.sleep(86400)  # Run daily
                
                # Archive old note versions (keep last 10 versions per note)
                cursor = self.conn.cursor()
                cursor.execute('''
                    DELETE FROM note_versions 
                    WHERE id NOT IN (
                        SELECT id FROM (
                            SELECT id FROM note_versions 
                            WHERE note_id = ? 
                            ORDER BY version_number DESC 
                            LIMIT 10
                        )
                    )
                ''')
                
            except Exception as e:
                self.logger.error(f"Background cleanup error: {e}")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

# Voice command helper functions
def format_note_info(note: Dict[str, Any]) -> str:
    """Format note information for voice output"""
    title = note.get('title', 'Untitled')
    category = note.get('category', 'general')
    importance = note.get('importance', 1)
    created_at = note.get('created_at', 'Unknown')
    
    return f"Note '{title}' in {category} category, importance {importance}, created {created_at}"

def format_template_info(template: Dict[str, Any]) -> str:
    """Format template information for voice output"""
    name = template.get('name', 'Untitled')
    category = template.get('category', 'general')
    created_at = template.get('created_at', 'Unknown')
    
    return f"Template '{name}' in {category} category, created {created_at}" 