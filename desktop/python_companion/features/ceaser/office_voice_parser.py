"""
Office Voice Parser - Parse voice commands for Office operations
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class OfficeVoiceParser:
    """Parse voice commands for Office operations"""
    
    def __init__(self):
        # Office app keywords
        self.word_keywords = ['word', 'document', 'doc']
        self.excel_keywords = ['excel', 'spreadsheet', 'sheet', 'workbook']
        self.powerpoint_keywords = ['powerpoint', 'presentation', 'slide', 'ppt']
        
        # Action keywords
        self.summarize_keywords = ['summarize', 'summary', 'summarise']
        self.find_keywords = ['find', 'search', 'locate']
        self.filter_keywords = ['filter', 'show only', 'display only']
        self.sort_keywords = ['sort', 'order', 'arrange']
        self.calculate_keywords = ['calculate', 'sum', 'average', 'count', 'total']
        self.format_keywords = ['format', 'bold', 'italic', 'underline', 'style']
        self.insert_keywords = ['insert', 'add', 'type']
        self.read_keywords = ['read', 'tell me', 'what does it say']
        self.count_keywords = ['count', 'how many', 'number of']
        self.navigate_keywords = ['go to', 'navigate', 'move to', 'jump to', 'next', 'previous']
        self.chart_keywords = ['chart', 'graph', 'plot']
    
    def parse_command(self, command: str) -> Dict[str, Any]:
        """Parse a voice command and extract Office operation details"""
        command_lower = command.lower().strip()
        
        # Determine which Office app
        app_type = self._detect_app(command_lower)
        if not app_type:
            return {
                "success": False,
                "error": "Could not determine Office application. Please mention Word, Excel, or PowerPoint."
            }
        
        # Detect action
        action = self._detect_action(command_lower, app_type)
        if not action:
            return {
                "success": False,
                "error": "Could not determine action. Please specify what you want to do."
            }
        
        # Extract parameters based on action
        params = self._extract_parameters(command_lower, action, app_type)
        
        return {
            "success": True,
            "app": app_type,
            "action": action,
            "params": params,
            "original_command": command
        }
    
    def _detect_app(self, command: str) -> Optional[str]:
        """Detect which Office app is mentioned"""
        if any(keyword in command for keyword in self.word_keywords):
            return "word"
        elif any(keyword in command for keyword in self.excel_keywords):
            return "excel"
        elif any(keyword in command for keyword in self.powerpoint_keywords):
            return "powerpoint"
        return None
    
    def _detect_action(self, command: str, app: str) -> Optional[str]:
        """Detect what action to perform"""
        # Summarize
        if any(keyword in command for keyword in self.summarize_keywords):
            return "summarize"
        
        # Find/Search
        if any(keyword in command for keyword in self.find_keywords):
            return "find"
        
        # Filter (Excel only)
        if app == "excel" and any(keyword in command for keyword in self.filter_keywords):
            return "filter"
        
        # Sort (Excel only)
        if app == "excel" and any(keyword in command for keyword in self.sort_keywords):
            return "sort"
        
        # Calculate (Excel only)
        if app == "excel" and any(keyword in command for keyword in self.calculate_keywords):
            return "calculate"
        
        # Format (Word only)
        if app == "word" and any(keyword in command for keyword in self.format_keywords):
            return "format"
        
        # Insert (Word only)
        if app == "word" and any(keyword in command for keyword in self.insert_keywords):
            return "insert"
        
        # Read
        if any(keyword in command for keyword in self.read_keywords):
            return "read"
        
        # Count
        if any(keyword in command for keyword in self.count_keywords):
            if app == "word":
                return "word_count"
            elif app == "powerpoint":
                return "slide_count"
        
        # Navigate (PowerPoint only)
        if app == "powerpoint" and any(keyword in command for keyword in self.navigate_keywords):
            return "navigate"
        
        # Chart (Excel only)
        if app == "excel" and any(keyword in command for keyword in self.chart_keywords):
            return "chart"
        
        return None
    
    def _extract_parameters(self, command: str, action: str, app: str) -> Dict[str, Any]:
        """Extract parameters from command"""
        params = {}
        
        if action == "find":
            # Extract search text
            find_match = re.search(r'find\s+(.+?)(?:\s+in|\s+and|$)', command, re.IGNORECASE)
            if not find_match:
                find_match = re.search(r'search\s+for\s+(.+?)(?:\s+in|\s+and|$)', command, re.IGNORECASE)
            if find_match:
                params["search_text"] = find_match.group(1).strip()
            params["highlight"] = "highlight" in command or "mark" in command
        
        elif action == "filter" and app == "excel":
            # Extract column
            col_match = re.search(r'column\s+([A-Z])', command, re.IGNORECASE)
            if col_match:
                params["column"] = col_match.group(1).upper()
            
            # Extract condition and value
            if "greater than" in command or ">" in command:
                params["condition"] = ">"
                value_match = re.search(r'(?:greater than|>)\s*(\d+)', command, re.IGNORECASE)
                if value_match:
                    params["value"] = float(value_match.group(1))
            elif "less than" in command or "<" in command:
                params["condition"] = "<"
                value_match = re.search(r'(?:less than|<)\s*(\d+)', command, re.IGNORECASE)
                if value_match:
                    params["value"] = float(value_match.group(1))
            elif "equal" in command or "=" in command:
                params["condition"] = "="
                value_match = re.search(r'(?:equal to|=)\s*(.+)', command, re.IGNORECASE)
                if value_match:
                    params["value"] = value_match.group(1).strip()
        
        elif action == "sort" and app == "excel":
            # Extract column
            col_match = re.search(r'column\s+([A-Z])', command, re.IGNORECASE)
            if col_match:
                params["column"] = col_match.group(1).upper()
            params["ascending"] = "descending" not in command and "desc" not in command
        
        elif action == "calculate" and app == "excel":
            # Extract operation
            if "sum" in command:
                params["operation"] = "sum"
            elif "average" in command or "avg" in command:
                params["operation"] = "average"
            elif "count" in command:
                params["operation"] = "count"
            elif "max" in command:
                params["operation"] = "max"
            elif "min" in command:
                params["operation"] = "min"
            
            # Extract column
            col_match = re.search(r'column\s+([A-Z])', command, re.IGNORECASE)
            if col_match:
                params["column"] = col_match.group(1).upper()
        
        elif action == "format" and app == "word":
            # Extract format type
            if "bold" in command:
                params["format_type"] = "bold"
            elif "italic" in command:
                params["format_type"] = "italic"
            elif "underline" in command:
                params["format_type"] = "underline"
            elif "heading" in command or "header" in command:
                params["format_type"] = "heading"
                # Extract heading level
                level_match = re.search(r'heading\s+(\d+)', command, re.IGNORECASE)
                if level_match:
                    params["value"] = int(level_match.group(1))
        
        elif action == "insert" and app == "word":
            # Extract text to insert
            insert_match = re.search(r'insert\s+(.+?)(?:\s+at|\s+in|$)', command, re.IGNORECASE)
            if not insert_match:
                insert_match = re.search(r'add\s+(.+?)(?:\s+at|\s+in|$)', command, re.IGNORECASE)
            if insert_match:
                params["text"] = insert_match.group(1).strip()
            
            if "beginning" in command or "start" in command:
                params["position"] = "beginning"
            elif "end" in command:
                params["position"] = "end"
            else:
                params["position"] = "cursor"
        
        elif action == "navigate" and app == "powerpoint":
            # Extract slide number
            slide_match = re.search(r'slide\s+(\d+)', command, re.IGNORECASE)
            if slide_match:
                params["slide_number"] = int(slide_match.group(1))
            elif "next" in command:
                params["direction"] = "next"
            elif "previous" in command or "prev" in command:
                params["direction"] = "previous"
        
        elif action == "chart" and app == "excel":
            # Extract chart type
            if "line" in command:
                params["chart_type"] = "line"
            elif "pie" in command:
                params["chart_type"] = "pie"
            elif "bar" in command:
                params["chart_type"] = "bar"
            else:
                params["chart_type"] = "column"
        
        return params

