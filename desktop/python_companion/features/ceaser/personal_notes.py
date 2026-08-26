"""
Personal Notes Management Feature
Handles personal note creation, management, and tracking for normal mode
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class PersonalNotes:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Supabase configuration
        SUPABASE_URL = os.getenv("SUPABASE_URL", "https://wewajyhmniwjuqpbmkvj.supabase.co")
        SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indld2FqeWhtbml3anVxcGJta3ZqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NzQ5OTQxMywiZXhwIjoyMDczMDc1NDEzfQ.J71_DLdRMrLXsOAr1pi4gTW2pFkMtE0s7F_hrDVbc8Y")
        
        try:
            self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            self.logger.info("Supabase client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Supabase client: {e}")
            self.supabase = None
    
    def get_notes(self, user_id: str, category: Optional[str] = None, pinned: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Get notes from Supabase database"""
        try:
            if not self.supabase:
                return []
            
            query = self.supabase.table("personal_notes").select("*").eq("user_id", user_id)
            
            if category:
                query = query.eq("category", category)
            if pinned is not None:
                query = query.eq("pinned", pinned)
            
            result = query.order("created_at", desc=True).execute()
            return result.data if result.data else []
            
        except Exception as e:
            self.logger.error(f"Error getting notes: {e}")
            return []
    
    def create_note(self, user_id: str, title: str, content: str = "", category: str = "general", 
                   tags: List[str] = None, pinned: bool = False) -> Dict[str, Any]:
        """Create a new personal note"""
        try:
            if not self.supabase:
                return {}
            
            if tags is None:
                tags = []
            
            note_data = {
                "user_id": user_id,
                "title": title,
                "content": content,
                "category": category,
                "tags": tags,
                "pinned": pinned,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            result = self.supabase.table("personal_notes").insert(note_data).execute()
            return result.data[0] if result.data else {}
            
        except Exception as e:
            self.logger.error(f"Error creating note: {e}")
            return {}
    
    def update_note(self, note_id: str, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a personal note"""
        try:
            if not self.supabase:
                return {}
            
            updates["updated_at"] = datetime.now().isoformat()
            
            result = self.supabase.table("personal_notes").update(updates).eq("id", note_id).eq("user_id", user_id).execute()
            return result.data[0] if result.data else {}
            
        except Exception as e:
            self.logger.error(f"Error updating note: {e}")
            return {}
    
    def delete_note(self, note_id: str, user_id: str) -> bool:
        """Delete a personal note"""
        try:
            if not self.supabase:
                return False
            
            result = self.supabase.table("personal_notes").delete().eq("id", note_id).eq("user_id", user_id).execute()
            return len(result.data) > 0
            
        except Exception as e:
            self.logger.error(f"Error deleting note: {e}")
            return False
    
    def search_notes(self, user_id: str, query: str) -> List[Dict[str, Any]]:
        """Search notes by title or content"""
        try:
            if not self.supabase:
                return []
            
            # Search in title and content
            result = self.supabase.table("personal_notes").select("*").eq("user_id", user_id).or_(f"title.ilike.%{query}%,content.ilike.%{query}%").order("created_at", desc=True).execute()
            return result.data if result.data else []
            
        except Exception as e:
            self.logger.error(f"Error searching notes: {e}")
            return []
    
    def get_notes_summary(self, user_id: str) -> Dict[str, Any]:
        """Get notes summary statistics"""
        try:
            if not self.supabase:
                return {}
            
            # Get all notes for user
            result = self.supabase.table("personal_notes").select("*").eq("user_id", user_id).execute()
            notes = result.data if result.data else []
            
            total_notes = len(notes)
            pinned_notes = len([n for n in notes if n.get("pinned", False)])
            
            # Count by category
            categories = {}
            for note in notes:
                category = note.get("category", "general")
                categories[category] = categories.get(category, 0) + 1
            
            return {
                "total_notes": total_notes,
                "pinned_notes": pinned_notes,
                "categories": categories,
                "recent_notes": len([n for n in notes if datetime.fromisoformat(n.get("created_at", "").replace('Z', '+00:00')) > datetime.now() - timedelta(days=7)])
            }
            
        except Exception as e:
            self.logger.error(f"Error getting notes summary: {e}")
            return {}

# Create global instance
personal_notes = PersonalNotes()