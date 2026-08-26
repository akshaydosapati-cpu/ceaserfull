"""
Personal Tasks Management Feature
Handles personal task creation, management, and tracking for normal mode
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class PersonalTasks:
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
    
    def get_tasks(self, user_id: str, status: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get tasks from Supabase database"""
        try:
            if not self.supabase:
                return []
            
            query = self.supabase.table("personal_tasks").select("*").eq("user_id", user_id)
            
            if status:
                query = query.eq("status", status)
            if category:
                query = query.eq("category", category)
            
            result = query.order("created_at", desc=True).execute()
            return result.data if result.data else []
            
        except Exception as e:
            self.logger.error(f"Error getting tasks: {e}")
            return []
    
    def create_task(self, user_id: str, title: str, description: str = "", priority: str = "medium", 
                   due_date: Optional[str] = None, category: str = "general") -> Dict[str, Any]:
        """Create a new personal task"""
        try:
            if not self.supabase:
                return {}
            
            task_data = {
                "user_id": user_id,
                "title": title,
                "description": description,
                "priority": priority,
                "status": "pending",
                "category": category,
                "due_date": due_date,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            result = self.supabase.table("personal_tasks").insert(task_data).execute()
            return result.data[0] if result.data else {}
            
        except Exception as e:
            self.logger.error(f"Error creating task: {e}")
            return {}
    
    def update_task(self, task_id: str, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a personal task"""
        try:
            if not self.supabase:
                self.logger.error("Supabase client not initialized")
                return {}
            
            # Ensure updates is a dict
            if not isinstance(updates, dict):
                self.logger.error(f"Updates must be a dict, got: {type(updates)}")
                return {}
            
            # Always update updated_at
            updates["updated_at"] = datetime.now().isoformat()
            
            self.logger.info(f"Updating task {task_id} for user {user_id} with updates: {updates}")
            
            result = self.supabase.table("personal_tasks").update(updates).eq("id", task_id).eq("user_id", user_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.info(f"Task {task_id} updated successfully")
                return result.data[0]
            else:
                self.logger.warning(f"No data returned after updating task {task_id}")
                return {}
            
        except Exception as e:
            self.logger.error(f"Error updating task: {e}", exc_info=True)
            return {}
    
    def delete_task(self, task_id: str, user_id: str) -> bool:
        """Delete a personal task"""
        try:
            if not self.supabase:
                return False
            
            result = self.supabase.table("personal_tasks").delete().eq("id", task_id).eq("user_id", user_id).execute()
            return len(result.data) > 0
            
        except Exception as e:
            self.logger.error(f"Error deleting task: {e}")
            return False
    
    def get_task_stats(self, user_id: str) -> Dict[str, Any]:
        """Get task statistics"""
        try:
            if not self.supabase:
                return {}
            
            # Get all tasks for user
            result = self.supabase.table("personal_tasks").select("*").eq("user_id", user_id).execute()
            tasks = result.data if result.data else []
            
            total_tasks = len(tasks)
            completed_tasks = len([t for t in tasks if t.get("status") == "completed"])
            pending_tasks = len([t for t in tasks if t.get("status") == "pending"])
            overdue_tasks = 0
            
            # Check for overdue tasks
            today = datetime.now().date()
            for task in tasks:
                if task.get("due_date") and task.get("status") != "completed":
                    try:
                        due_date = datetime.fromisoformat(task["due_date"].replace('Z', '+00:00')).date()
                        if due_date < today:
                            overdue_tasks += 1
                    except:
                        pass
            
            return {
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "pending_tasks": pending_tasks,
                "overdue_tasks": overdue_tasks,
                "completion_rate": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"Error getting task stats: {e}")
            return {}

# Create global instance
personal_tasks = PersonalTasks()