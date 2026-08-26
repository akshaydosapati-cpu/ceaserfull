"""
Personal Goals Management Feature
Handles personal goal creation, management, and tracking for normal mode
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class PersonalGoals:
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
    
    def get_goals(self, user_id: str, status: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get goals from Supabase database"""
        try:
            if not self.supabase:
                return []
            
            query = self.supabase.table("personal_goals").select("*").eq("user_id", user_id)
            
            if status:
                query = query.eq("status", status)
            if category:
                query = query.eq("category", category)
            
            result = query.order("created_at", desc=True).execute()
            return result.data if result.data else []
            
        except Exception as e:
            self.logger.error(f"Error getting goals: {e}")
            return []
    
    def create_goal(self, user_id: str, title: str, description: str = "", target_value: float = 100.0, 
                   current_value: float = 0.0, unit: str = "", category: str = "general", 
                   target_date: Optional[str] = None, priority: str = "medium") -> Dict[str, Any]:
        """Create a new personal goal"""
        try:
            if not self.supabase:
                return {}
            
            goal_data = {
                "user_id": user_id,
                "title": title,
                "description": description,
                "target_value": target_value,
                "current_value": current_value,
                "category": category,
                "target_date": target_date,
                "status": "active",
                "priority": priority,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # Note: 'unit' column doesn't exist in personal_goals table, so we don't include it
            
            result = self.supabase.table("personal_goals").insert(goal_data).execute()
            return result.data[0] if result.data else {}
            
        except Exception as e:
            self.logger.error(f"Error creating goal: {e}")
            return {}
    
    def update_goal(self, goal_id: str, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a personal goal"""
        try:
            if not self.supabase:
                return {}
            
            updates["updated_at"] = datetime.now().isoformat()
            
            result = self.supabase.table("personal_goals").update(updates).eq("id", goal_id).eq("user_id", user_id).execute()
            return result.data[0] if result.data else {}
            
        except Exception as e:
            self.logger.error(f"Error updating goal: {e}")
            return {}
    
    def delete_goal(self, goal_id: str, user_id: str) -> bool:
        """Delete a personal goal"""
        try:
            if not self.supabase:
                return False
            
            result = self.supabase.table("personal_goals").delete().eq("id", goal_id).eq("user_id", user_id).execute()
            return len(result.data) > 0
            
        except Exception as e:
            self.logger.error(f"Error deleting goal: {e}")
            return False
    
    def get_goal_stats(self, user_id: str) -> Dict[str, Any]:
        """Get goal statistics"""
        try:
            if not self.supabase:
                return {}
            
            # Get all goals for user
            result = self.supabase.table("personal_goals").select("*").eq("user_id", user_id).execute()
            goals = result.data if result.data else []
            
            total_goals = len(goals)
            active_goals = len([g for g in goals if g.get("status") == "active"])
            completed_goals = len([g for g in goals if g.get("status") == "completed"])
            
            # Calculate average progress
            total_progress = 0
            for goal in goals:
                if goal.get("target_value", 0) > 0:
                    progress = (goal.get("current_value", 0) / goal.get("target_value", 1)) * 100
                    total_progress += min(progress, 100)
            
            avg_progress = (total_progress / total_goals) if total_goals > 0 else 0
            
            return {
                "total_goals": total_goals,
                "active_goals": active_goals,
                "completed_goals": completed_goals,
                "average_progress": round(avg_progress, 2),
                "completion_rate": (completed_goals / total_goals * 100) if total_goals > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"Error getting goal stats: {e}")
            return {}

# Create global instance
personal_goals = PersonalGoals()