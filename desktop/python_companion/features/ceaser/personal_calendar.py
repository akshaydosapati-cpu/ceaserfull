"""
Personal Calendar Management Feature
Handles personal calendar event creation, management, and tracking for normal mode
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class PersonalCalendar:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        SUPABASE_URL = os.getenv("SUPABASE_URL", "https://wewajyhmniwjuqpbmkvj.supabase.co")
        SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indld2FqeWhtbml3anVxcGJta3ZqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NzQ5OTQxMywiZXhwIjoyMDczMDc1NDEzfQ.J71_DLdRMrLXsOAr1pi4gTW2pFkMtE0s7F_hrDVbc8Y")
        try:
            self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            self.logger.info("Supabase client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Supabase client: {e}")
            self.supabase = None
    
    def get_events(self, user_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get calendar events from Supabase database"""
        try:
            if not self.supabase:
                return []
            query = self.supabase.table("personal_calendar_events").select("*").eq("user_id", user_id)
            if start_date:
                query = query.gte("start_time", start_date)
            if end_date:
                query = query.lte("end_time", end_date)
            result = query.order("start_time", desc=False).execute()
            return result.data if result.data else []
        except Exception as e:
            self.logger.error(f"Error getting events: {e}")
            return []
    
    def create_event(self, user_id: str, title: str, description: str = "", start_time: str = "", 
                    end_time: str = "", location: str = "", category: str = "general", 
                    is_all_day: bool = False, priority: str = "medium") -> Dict[str, Any]:
        """Create a new calendar event"""
        try:
            if not self.supabase:
                return {"_error": "Supabase client not initialized"}
            
            # Validate required fields
            if not user_id or not title or not start_time or not end_time:
                return {"_error": "Missing required fields: user_id, title, start_time, and end_time are required"}
            
            # Validate timestamp format
            try:
                datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            except (ValueError, AttributeError) as ve:
                return {"_error": f"Invalid timestamp format: {str(ve)}"}
            
            # Build event_data dictionary with explicit field mapping
            event_data = {
                "user_id": str(user_id),
                "title": str(title),
                "description": str(description) if description else "",
                "start_time": str(start_time),  # Must be ISO timestamp
                "end_time": str(end_time),      # Must be ISO timestamp
                "location": str(location) if location else "",
                "category": str(category) if category else "general",
                "is_all_day": bool(is_all_day),
                "priority": str(priority) if priority else "medium"
            }
            
            # CRITICAL: Final validation - ensure location is NOT in timestamp fields
            if event_data["location"] == event_data["start_time"] or event_data["location"] == event_data["end_time"]:
                return {"_error": "Data validation error: location cannot match timestamp fields"}
            
            # CRITICAL: Verify timestamp fields contain 'T' (ISO format indicator)
            if 'T' not in event_data["start_time"]:
                return {"_error": f"Invalid start_time format: '{event_data['start_time']}' is not a valid ISO timestamp"}
            if 'T' not in event_data["end_time"]:
                return {"_error": f"Invalid end_time format: '{event_data['end_time']}' is not a valid ISO timestamp"}
            
            self.logger.info(f"Inserting event: user_id={user_id}, title={title}, start_time={event_data['start_time']}, end_time={event_data['end_time']}, location={event_data['location']}")
            
            # Insert into Supabase
            result = self.supabase.table("personal_calendar_events").insert(event_data).execute()
            
            # Check for errors in result
            if hasattr(result, 'error') and result.error:
                error_dict = result.error if isinstance(result.error, dict) else {"message": str(result.error)}
                error_msg = error_dict.get('message', str(result.error))
                self.logger.error(f"Supabase error: {error_msg}")
                return {"_error": error_msg}
            
            # Check if result has data
            if result.data and len(result.data) > 0:
                self.logger.info(f"Event created successfully: {result.data[0].get('id')}")
                return result.data[0]
            else:
                error_msg = "Event creation returned empty result"
                self.logger.error(error_msg)
                return {"_error": error_msg}
                
        except Exception as e:
            # CRITICAL: Extract error message from exception
            # The terminal shows: Error creating event: {'message': '...', 'code': '...'}
            # This suggests the error dict is in the exception
            error_msg = None
            
            # Method 1: Check if exception itself is a dict (unlikely but possible)
            if isinstance(e, dict) and 'message' in e:
                error_msg = e['message']
                self.logger.error(f"✅ Found error in exception dict: {error_msg}")
            
            # Method 2: Check exception args (most common)
            if not error_msg and hasattr(e, 'args') and len(e.args) > 0:
                for arg in e.args:
                    if isinstance(arg, dict) and 'message' in arg:
                        error_msg = arg['message']
                        self.logger.error(f"✅ Found error in args dict: {error_msg}")
                        break
                    elif isinstance(arg, str) and ('invalid input syntax' in arg or 'Bangalore' in arg):
                        error_msg = arg
                        self.logger.error(f"✅ Found error in args string: {error_msg}")
                        break
            
            # Method 3: Check exception message attribute
            if not error_msg and hasattr(e, 'message'):
                if isinstance(e.message, dict) and 'message' in e.message:
                    error_msg = e.message['message']
                    self.logger.error(f"✅ Found error in exception.message dict: {error_msg}")
                elif e.message:
                    error_msg = str(e.message)
                    self.logger.error(f"✅ Found error in exception.message: {error_msg}")
            
            # Method 4: Parse from string representation
            if not error_msg:
                error_str = str(e)
                error_repr = repr(e)
                
                # Look for the error message in the string representation
                if 'invalid input syntax for type timestamp' in error_str or 'invalid input syntax for type timestamp' in error_repr:
                    import re
                    # Try to extract the error message
                    match = re.search(r'invalid input syntax for type timestamp: "([^"]+)"', error_str + error_repr)
                    if match:
                        bad_value = match.group(1)
                        error_msg = f"Invalid timestamp value: '{bad_value}'. This appears to be a location, not a timestamp. Please check that start_time and end_time are valid ISO timestamps (e.g., '2025-11-09T18:30:00.000Z')."
                        self.logger.error(f"✅ Extracted from string pattern: {error_msg}")
                    else:
                        # Try to extract from dict representation
                        match = re.search(r"'message':\s*'([^']+)'", error_repr)
                        if match:
                            error_msg = match.group(1)
                            self.logger.error(f"✅ Extracted from dict repr: {error_msg}")
                        else:
                            error_msg = error_str
                            self.logger.error(f"⚠️ Using error_str: {error_msg}")
                else:
                    error_msg = error_str
                    self.logger.error(f"⚠️ Using error_str (no pattern): {error_msg}")
            
            # Final fallback
            if not error_msg:
                error_msg = "Unknown error occurred while creating event. Please check backend logs."
                self.logger.error(f"❌ No error extracted, using fallback")
            
            self.logger.error(f"Error creating event: {error_msg}", exc_info=True)
            # CRITICAL: ALWAYS return error dict, never empty dict
            return {"_error": error_msg}
    
    def update_event(self, event_id: str, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a calendar event"""
        try:
            if not self.supabase:
                return {"_error": "Supabase client not initialized"}
            
            # Map frontend field names to backend field names
            mapped_updates = {}
            field_mapping = {
                "startDate": "start_time",
                "endDate": "end_time",
                "allDay": "is_all_day",
                "type": "category"
            }
            
            for key, value in updates.items():
                if key == "user_id":
                    continue
                db_key = field_mapping.get(key, key)
                mapped_updates[db_key] = value
            
            mapped_updates["updated_at"] = datetime.now().isoformat()
            
            result = self.supabase.table("personal_calendar_events").update(mapped_updates).eq("id", event_id).eq("user_id", user_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            else:
                return {"_error": "Event update returned empty result"}
                
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Error updating event: {error_msg}", exc_info=True)
            return {"_error": error_msg}
    
    def delete_event(self, event_id: str, user_id: str) -> bool:
        """Delete a calendar event"""
        try:
            if not self.supabase:
                return False
            result = self.supabase.table("personal_calendar_events").delete().eq("id", event_id).eq("user_id", user_id).execute()
            return len(result.data) > 0
        except Exception as e:
            self.logger.error(f"Error deleting event: {e}")
            return False
    
    def get_upcoming_events(self, user_id: str, days: int = 7) -> List[Dict[str, Any]]:
        """Get upcoming events for the next N days"""
        try:
            if not self.supabase:
                return []
            start_date = datetime.now().isoformat()
            end_date = (datetime.now() + timedelta(days=days)).isoformat()
            result = self.supabase.table("personal_calendar_events").select("*").eq("user_id", user_id).gte("start_time", start_date).lte("start_time", end_date).order("start_time", desc=False).execute()
            return result.data if result.data else []
        except Exception as e:
            self.logger.error(f"Error getting upcoming events: {e}")
            return []
    
    def get_schedule_summary(self, user_id: str, date: str) -> Dict[str, Any]:
        """Get schedule summary for a specific date"""
        try:
            if not self.supabase:
                return {}
            start_date = f"{date}T00:00:00"
            end_date = f"{date}T23:59:59"
            result = self.supabase.table("personal_calendar_events").select("*").eq("user_id", user_id).gte("start_time", start_date).lte("start_time", end_date).order("start_time", desc=False).execute()
            events = result.data if result.data else []
            return {
                "date": date,
                "total_events": len(events),
                "events": events,
                "busy_hours": len(events)
            }
        except Exception as e:
            self.logger.error(f"Error getting schedule summary: {e}")
            return {}

personal_calendar = PersonalCalendar()
