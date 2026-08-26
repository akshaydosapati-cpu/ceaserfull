"""
Personal Analytics Management Feature
Handles personal analytics and productivity tracking for normal mode
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class PersonalAnalytics:
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
    
    def record_metric(self, user_id: str, metric_name: str, value: float, category: str = "general", 
                     metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Record a new analytics metric"""
        try:
            if not self.supabase:
                return {}
            
            if metadata is None:
                metadata = {}
            
            metric_data = {
                "user_id": user_id,
                "metric_name": metric_name,
                "value": value,
                "category": category,
                "metadata": metadata,
                "recorded_at": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            result = self.supabase.table("personal_analytics").insert(metric_data).execute()
            return result.data[0] if result.data else {}
            
        except Exception as e:
            self.logger.error(f"Error recording metric: {e}")
            return {}
    
    def get_daily_stats(self, user_id: str, date: str) -> Dict[str, Any]:
        """Get daily analytics statistics"""
        try:
            if not self.supabase:
                return {}
            
            start_date = f"{date}T00:00:00"
            end_date = f"{date}T23:59:59"
            
            result = self.supabase.table("personal_analytics").select("*").eq("user_id", user_id).gte("recorded_at", start_date).lte("recorded_at", end_date).execute()
            metrics = result.data if result.data else []
            
            # Group by metric name
            stats = {}
            for metric in metrics:
                name = metric.get("metric_name", "unknown")
                value = metric.get("value", 0)
                
                if name not in stats:
                    stats[name] = {"total": 0, "count": 0, "avg": 0}
                
                stats[name]["total"] += value
                stats[name]["count"] += 1
                stats[name]["avg"] = stats[name]["total"] / stats[name]["count"]
            
            return {
                "date": date,
                "total_metrics": len(metrics),
                "metrics": stats
            }
            
        except Exception as e:
            self.logger.error(f"Error getting daily stats: {e}")
            return {}
    
    def get_weekly_stats(self, user_id: str, week_start: str) -> Dict[str, Any]:
        """Get weekly analytics statistics"""
        try:
            if not self.supabase:
                return {}
            
            start_date = f"{week_start}T00:00:00"
            end_date = (datetime.fromisoformat(week_start) + timedelta(days=7)).isoformat()
            
            result = self.supabase.table("personal_analytics").select("*").eq("user_id", user_id).gte("recorded_at", start_date).lte("recorded_at", end_date).execute()
            metrics = result.data if result.data else []
            
            # Group by day and metric
            daily_stats = {}
            for metric in metrics:
                date = metric.get("recorded_at", "")[:10]  # Get date part
                if date not in daily_stats:
                    daily_stats[date] = {}
                
                name = metric.get("metric_name", "unknown")
                value = metric.get("value", 0)
                
                if name not in daily_stats[date]:
                    daily_stats[date][name] = {"total": 0, "count": 0}
                
                daily_stats[date][name]["total"] += value
                daily_stats[date][name]["count"] += 1
            
            return {
                "week_start": week_start,
                "total_metrics": len(metrics),
                "daily_stats": daily_stats
            }
            
        except Exception as e:
            self.logger.error(f"Error getting weekly stats: {e}")
            return {}
    
    def get_monthly_stats(self, user_id: str, month: str) -> Dict[str, Any]:
        """Get monthly analytics statistics"""
        try:
            if not self.supabase:
                return {}
            
            start_date = f"{month}-01T00:00:00"
            # Get last day of month
            if month.endswith('-02'):
                end_date = f"{month}-28T23:59:59"  # Simple approach for February
            elif month.endswith(('-04', '-06', '-09', '-11')):
                end_date = f"{month}-30T23:59:59"
            else:
                end_date = f"{month}-31T23:59:59"
            
            result = self.supabase.table("personal_analytics").select("*").eq("user_id", user_id).gte("recorded_at", start_date).lte("recorded_at", end_date).execute()
            metrics = result.data if result.data else []
            
            # Group by metric name
            stats = {}
            for metric in metrics:
                name = metric.get("metric_name", "unknown")
                value = metric.get("value", 0)
                
                if name not in stats:
                    stats[name] = {"total": 0, "count": 0, "avg": 0, "max": 0, "min": float('inf')}
                
                stats[name]["total"] += value
                stats[name]["count"] += 1
                stats[name]["max"] = max(stats[name]["max"], value)
                stats[name]["min"] = min(stats[name]["min"], value)
                stats[name]["avg"] = stats[name]["total"] / stats[name]["count"]
            
            return {
                "month": month,
                "total_metrics": len(metrics),
                "metrics": stats
            }
            
        except Exception as e:
            self.logger.error(f"Error getting monthly stats: {e}")
            return {}
    
    def get_analytics_summary(self, user_id: str) -> Dict[str, Any]:
        """Get overall analytics summary"""
        try:
            if not self.supabase:
                return {}
            
            # Get last 30 days of data
            start_date = (datetime.now() - timedelta(days=30)).isoformat()
            
            result = self.supabase.table("personal_analytics").select("*").eq("user_id", user_id).gte("recorded_at", start_date).execute()
            metrics = result.data if result.data else []
            
            # Calculate summary statistics
            total_metrics = len(metrics)
            unique_metric_names = len(set(m.get("metric_name", "") for m in metrics))
            
            # Get most active categories
            categories = {}
            for metric in metrics:
                category = metric.get("category", "general")
                categories[category] = categories.get(category, 0) + 1
            
            return {
                "total_metrics": total_metrics,
                "unique_metrics": unique_metric_names,
                "categories": categories,
                "period_days": 30,
                "avg_metrics_per_day": round(total_metrics / 30, 2) if total_metrics > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"Error getting analytics summary: {e}")
            return {}

# Create global instance
personal_analytics = PersonalAnalytics()