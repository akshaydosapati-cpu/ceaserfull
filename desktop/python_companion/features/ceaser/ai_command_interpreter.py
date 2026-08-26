"""
AI Command Interpreter - Uses OpenAI to understand natural language commands
Hybrid approach: AI first, fallback to pattern matching if AI fails
"""

import os
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
import openai

logger = logging.getLogger(__name__)

# Get OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class AICommandInterpreter:
    """
    Interprets natural language commands using OpenAI function calling.
    Maps user commands to handler functions with extracted parameters.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or OPENAI_API_KEY
        self.client = None
        if self.api_key:
            try:
                # Try standard initialization first
                self.client = openai.OpenAI(api_key=self.api_key)
                logger.info("✅ AI Command Interpreter initialized with OpenAI")
            except TypeError as e:
                # httpx version incompatibility - try with explicit http_client
                try:
                    import httpx
                    http_client = httpx.Client(timeout=30.0)
                    self.client = openai.OpenAI(api_key=self.api_key, http_client=http_client)
                    logger.info("✅ AI Command Interpreter initialized with OpenAI (httpx workaround)")
                except Exception as e2:
                    logger.warning(f"⚠️ Failed to initialize OpenAI client: {e2}")
                    self.client = None
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize OpenAI client: {e}")
                self.client = None
    
    def get_function_definitions(self) -> List[Dict]:
        """
        Returns comprehensive function definitions for all Ceaser features.
        These are used by OpenAI to understand what actions are available.
        """
        return [
            # ========== PRODUCTIVITY FEATURES ==========
            {
                "name": "create_task",
                "description": "Create a new task. Extract task title, description, due date, priority from user command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Task title or name"},
                        "description": {"type": "string", "description": "Optional task description"},
                        "due_date": {"type": "string", "description": "Due date (e.g., 'tomorrow', 'next week', '2024-12-25')"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high"], "description": "Task priority"}
                    },
                    "required": ["title"]
                }
            },
            {
                "name": "list_tasks",
                "description": "List tasks. Can filter by status, date, priority.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filter": {"type": "string", "description": "Filter: 'all', 'today', 'pending', 'completed'"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high"], "description": "Filter by priority"}
                    }
                }
            },
            {
                "name": "complete_task",
                "description": "Mark a task as completed. Extract task title or ID from command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_title": {"type": "string", "description": "Title or name of task to complete"}
                    },
                    "required": ["task_title"]
                }
            },
            {
                "name": "delete_task",
                "description": "Delete a task. Extract task title from command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_title": {"type": "string", "description": "Title of task to delete"}
                    },
                    "required": ["task_title"]
                }
            },
            {
                "name": "create_goal",
                "description": "Create a new goal. Extract goal name, description, target date, progress from command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Goal name"},
                        "description": {"type": "string", "description": "Goal description"},
                        "target_date": {"type": "string", "description": "Target completion date"},
                        "progress": {"type": "number", "description": "Initial progress (0-100)"}
                    },
                    "required": ["name"]
                }
            },
            {
                "name": "list_goals",
                "description": "List all goals or filter by status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filter": {"type": "string", "description": "Filter: 'all', 'active', 'completed'"}
                    }
                }
            },
            {
                "name": "update_goal_progress",
                "description": "Update progress on a goal. Extract goal name and new progress percentage.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "goal_name": {"type": "string", "description": "Name of goal"},
                        "progress": {"type": "number", "description": "New progress percentage (0-100)"}
                    },
                    "required": ["goal_name", "progress"]
                }
            },
            {
                "name": "create_calendar_event",
                "description": "Schedule a calendar event. Extract event title, date, time, duration, description.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Event title"},
                        "date": {"type": "string", "description": "Event date (e.g., 'tomorrow', 'next Monday', '2024-12-25')"},
                        "time": {"type": "string", "description": "Event time (e.g., '3 PM', '14:30')"},
                        "duration": {"type": "string", "description": "Event duration (e.g., '1 hour', '30 minutes')"},
                        "description": {"type": "string", "description": "Event description"}
                    },
                    "required": ["title", "date"]
                }
            },
            {
                "name": "list_calendar_events",
                "description": "List calendar events. Can filter by date range.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filter": {"type": "string", "description": "Filter: 'today', 'tomorrow', 'this week', 'all'"}
                    }
                }
            },
            {
                "name": "create_reminder",
                "description": "Set a reminder. Extract reminder message, date, time from command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Reminder message"},
                        "datetime": {"type": "string", "description": "When to remind (e.g., 'tomorrow at 3 PM', 'in 2 hours', 'next Monday')"},
                        "recurring": {"type": "string", "description": "Recurring pattern: 'daily', 'weekly', 'monthly', or None"}
                    },
                    "required": ["message", "datetime"]
                }
            },
            {
                "name": "list_reminders",
                "description": "List all reminders or filter by status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filter": {"type": "string", "description": "Filter: 'all', 'upcoming', 'past'"}
                    }
                }
            },
            {
                "name": "create_note",
                "description": "Create a note. Extract note title and content from command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Note title"},
                        "content": {"type": "string", "description": "Note content"}
                    },
                    "required": ["title"]
                }
            },
            {
                "name": "list_notes",
                "description": "List all notes or search notes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search": {"type": "string", "description": "Search query to filter notes"}
                    }
                }
            },
            {
                "name": "search_notes",
                "description": "Search notes by keyword or content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            },
            
            # ========== SYSTEM COMMANDS ==========
            {
                "name": "open_app",
                "description": "Open an application. Extract app name from command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_name": {"type": "string", "description": "Name of application to open (e.g., 'chrome', 'notepad', 'calculator')"}
                    },
                    "required": ["app_name"]
                }
            },
            {
                "name": "close_app",
                "description": "Close an application. Extract app name from command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_name": {"type": "string", "description": "Name of application to close"}
                    },
                    "required": ["app_name"]
                }
            },
            {
                "name": "lock_screen",
                "description": "Lock the computer screen.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "shutdown",
                "description": "Shutdown the computer.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "restart",
                "description": "Restart the computer.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "sleep",
                "description": "Put computer to sleep.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "screenshot",
                "description": "Take a screenshot.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "set_volume",
                "description": "Set system volume. Extract volume level (0-100) from command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "level": {"type": "number", "description": "Volume level (0-100)"}
                    },
                    "required": ["level"]
                }
            },
            {
                "name": "mute_volume",
                "description": "Mute system volume.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "unmute_volume",
                "description": "Unmute system volume.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_system_info",
                "description": "Get system information (CPU, memory, disk, battery).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["cpu", "memory", "disk", "battery", "all"], "description": "Type of system info"}
                    }
                }
            },
            
            # ========== FILE OPERATIONS ==========
            {
                "name": "list_files",
                "description": "List files in current or specified directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "description": "Directory path (optional, defaults to current)"}
                    }
                }
            },
            {
                "name": "open_file",
                "description": "Open a file. Extract file name or path from command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File name or full path"}
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "search_file",
                "description": "Search for a file by name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_name": {"type": "string", "description": "File name to search for"}
                    },
                    "required": ["file_name"]
                }
            },
            {
                "name": "create_folder",
                "description": "Create a new folder. Extract folder name from command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "folder_name": {"type": "string", "description": "Folder name"}
                    },
                    "required": ["folder_name"]
                }
            },
            {
                "name": "delete_file",
                "description": "Delete a file or folder. Extract file/folder name from command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File or folder path to delete"}
                    },
                    "required": ["file_path"]
                }
            },
            
            # ========== INFORMATION SERVICES ==========
            {
                "name": "get_weather",
                "description": "Get weather information. Extract location from command if specified.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name or location (optional, defaults to user's location)"},
                        "forecast": {"type": "boolean", "description": "Whether to get forecast (default: false for current weather)"}
                    }
                }
            },
            {
                "name": "get_news",
                "description": "Get latest news headlines. Can filter by topic.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "News topic (e.g., 'technology', 'sports', 'business')"},
                        "limit": {"type": "number", "description": "Number of headlines (default: 5)"}
                    }
                }
            },
            {
                "name": "get_time",
                "description": "Get current time.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_date",
                "description": "Get current date.",
                "parameters": {"type": "object", "properties": {}}
            },
            
            # ========== MEDIA CONTROL ==========
            {
                "name": "play_youtube",
                "description": "Play a video on YouTube. Extract video title, song name, or search query from command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Video title, song name, or search query"},
                        "action": {"type": "string", "enum": ["play", "pause", "next", "previous", "forward", "backward"], "description": "Playback action (default: play)"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "youtube_control",
                "description": "Control YouTube playback (pause, play, next, previous, forward, backward).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["play", "pause", "next", "previous", "forward", "backward", "fullscreen"], "description": "Playback control action"}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "play_spotify",
                "description": "Control Spotify playback.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["play", "pause", "next", "previous"], "description": "Playback action"},
                        "query": {"type": "string", "description": "Song or playlist name (optional)"}
                    }
                }
            },
            {
                "name": "system_media_control",
                "description": "Control system media player (play, pause, next, previous).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["play", "pause", "next", "previous", "stop"], "description": "Media control action"}
                    },
                    "required": ["action"]
                }
            },
            
            # ========== AI SERVICES ==========
            {
                "name": "ai_chat",
                "description": "Answer questions, provide explanations, have conversations. Use this for any question, explanation request, or general chat. Generate comprehensive, ChatGPT-like responses with follow-up suggestions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "User's question or statement"},
                        "mode": {"type": "string", "enum": ["comprehensive", "brief", "conversational"], "description": "Response mode (default: comprehensive for questions, brief for confirmations)"}
                    },
                    "required": ["question"]
                }
            },
            {
                "name": "analyze_image",
                "description": "Analyze an image using AI vision. Extract image path or description from command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_path": {"type": "string", "description": "Path to image file"},
                        "analysis_type": {"type": "string", "enum": ["general", "faces", "ocr", "objects"], "description": "Type of analysis"}
                    },
                    "required": ["image_path"]
                }
            },
            {
                "name": "remember",
                "description": "Store information in memory for later recall.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Memory key or topic"},
                        "value": {"type": "string", "description": "Information to remember"}
                    },
                    "required": ["key", "value"]
                }
            },
            {
                "name": "recall",
                "description": "Recall information from memory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Memory key or topic to recall"}
                    },
                    "required": ["key"]
                }
            },
            {
                "name": "search_memory",
                "description": "Search memories by keyword.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "google_search",
                "description": "Search Google for information. Extract search query from command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            },
            
            # ========== AMAZON SHOPPING ==========
            {
                "name": "amazon_search",
                "description": "Search for products on Amazon.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Product search query"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "amazon_deals",
                "description": "Get Amazon deals and offers.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "track_price",
                "description": "Track price of an Amazon product.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_url": {"type": "string", "description": "Amazon product URL or name"}
                    },
                    "required": ["product_url"]
                }
            },
            
            # ========== LANGUAGE LEARNING ==========
            {
                "name": "start_language_lesson",
                "description": "Start a language learning lesson.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "language": {"type": "string", "description": "Language to learn"},
                        "level": {"type": "string", "enum": ["beginner", "intermediate", "advanced"], "description": "Difficulty level"}
                    },
                    "required": ["language"]
                }
            },
            {
                "name": "language_practice",
                "description": "Practice speaking a language.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "language": {"type": "string", "description": "Language to practice"}
                    },
                    "required": ["language"]
                }
            },
            
            # ========== WEB AUTOMATION ==========
            {
                "name": "web_automation",
                "description": "Automate web browser actions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "description": "Action to perform"},
                        "url": {"type": "string", "description": "Website URL"}
                    }
                }
            },
            {
                "name": "fill_form",
                "description": "Fill a web form automatically.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Form URL"},
                        "data": {"type": "string", "description": "Form data as JSON string"}
                    },
                    "required": ["url"]
                }
            },
            
            # ========== VAULT ==========
            {
                "name": "vault_store",
                "description": "Store information securely in vault.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Storage key"},
                        "value": {"type": "string", "description": "Information to store"}
                    },
                    "required": ["key", "value"]
                }
            },
            {
                "name": "vault_retrieve",
                "description": "Retrieve information from vault.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Storage key"}
                    },
                    "required": ["key"]
                }
            },
            
            # ========== OFFICE CONTROL ==========
            {
                "name": "office_command",
                "description": "Control Microsoft Office applications (Word, Excel, PowerPoint). Extract app name, action, and parameters from command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app": {"type": "string", "enum": ["word", "excel", "powerpoint"], "description": "Office application"},
                        "action": {"type": "string", "description": "Action to perform (e.g., 'summarize', 'read', 'format', 'calculate')"},
                        "params": {"type": "string", "description": "Additional parameters as JSON string"}
                    },
                    "required": ["app", "action"]
                }
            },
            
            # ========== AUTOMATION ==========
            {
                "name": "create_automation",
                "description": "Create a workflow automation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Automation name"},
                        "trigger": {"type": "string", "description": "Trigger condition"},
                        "action": {"type": "string", "description": "Action to perform"}
                    },
                    "required": ["name", "trigger", "action"]
                }
            },
            {
                "name": "list_automations",
                "description": "List all automations.",
                "parameters": {"type": "object", "properties": {}}
            },
            
            # ========== MULTIMODAL ==========
            {
                "name": "multimodal_analysis",
                "description": "Perform multimodal AI analysis (text, image, audio combined).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "Input description"},
                        "type": {"type": "string", "enum": ["text", "image", "audio", "combined"], "description": "Input type"}
                    }
                }
            },
            
            # ========== PREDICTIONS ==========
            {
                "name": "analyze_file",
                "description": "Analyze a file and generate predictions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to file to analyze"}
                    },
                    "required": ["file_path"]
                }
            },
            
            # ========== CODE GENERATOR ==========
            {
                "name": "build_app",
                "description": "Build or generate an application.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_type": {"type": "string", "description": "Type of app (e.g., 'web', 'desktop', 'mobile')"},
                        "description": {"type": "string", "description": "App description or requirements"}
                    },
                    "required": ["description"]
                }
            },
            
            # ========== FUN & UTILITIES ==========
            {
                "name": "tell_joke",
                "description": "Tell a joke.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_quote",
                "description": "Get an inspirational quote.",
                "parameters": {"type": "object", "properties": {}}
            },
            
            # ========== PROACTIVE ==========
            {
                "name": "get_suggestions",
                "description": "Get proactive suggestions based on user's current context.",
                "parameters": {"type": "object", "properties": {}}
            },
        ]
    
    def interpret_command(self, command: str, conversation_history: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Interpret a natural language command using OpenAI.
        
        Returns:
            {
                "action": function_name,
                "parameters": {...},
                "handler": handler_function_name,
                "confidence": 0.0-1.0,
                "is_question": bool,
                "raw_response": str (for questions/chat)
            }
        """
        if not self.client:
            logger.warning("OpenAI client not available, returning None for AI interpretation")
            return None
        
        try:
            # Build conversation context
            messages = [
                {
                    "role": "system",
                    "content": """You are Ceaser, an intelligent voice assistant. Your job is to understand user commands and map them to specific actions.

IMPORTANT RULES:
1. If the user is asking a QUESTION or wants INFORMATION/EXPLANATION, use the "ai_chat" function with mode="comprehensive"
2. If the user wants to PERFORM AN ACTION (create task, set reminder, open app, etc.), use the appropriate action function
3. Extract ALL relevant parameters from the command
4. For ambiguous commands, infer the most likely intent based on context
5. For multi-action commands, you can call multiple functions
6. Be smart about understanding natural language variations

Examples:
- "What is quantum computing?" → ai_chat(question="What is quantum computing?", mode="comprehensive")
- "Remind me to call Sarah tomorrow" → create_reminder(message="call Sarah", datetime="tomorrow")
- "Create a task for the meeting" → create_task(title="meeting")
- "What's the weather?" → get_weather()
- "Play Despacito on YouTube" → play_youtube(query="Despacito")
- "Open Chrome" → open_app(app_name="chrome")
- "What time is it?" → get_time()
- "Tell me a joke" → tell_joke()
- "Continue" (after previous question) → ai_chat(question="continue", mode="comprehensive") with context from conversation_history"""
                }
            ]
            
            # Add conversation history for context
            if conversation_history:
                for msg in conversation_history[-5:]:  # Last 5 messages for context
                    messages.append(msg)
            
            # Add current command
            messages.append({
                "role": "user",
                "content": command
            })
            
            # Call OpenAI with function calling
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cost-effective
                messages=messages,
                functions=self.get_function_definitions(),
                function_call="auto",  # Let AI decide whether to use functions or respond directly
                temperature=0.3,  # Lower temperature for more consistent interpretations
                max_tokens=500
            )
            
            message = response.choices[0].message
            
            # Check if AI wants to call a function
            if message.function_call:
                function_name = message.function_call.name
                try:
                    parameters = json.loads(message.function_call.arguments)
                except:
                    parameters = {}
                
                # Map function name to handler
                handler_mapping = self._get_handler_mapping()
                handler_info = handler_mapping.get(function_name)
                
                if handler_info:
                    return {
                        "action": function_name,
                        "parameters": parameters,
                        "handler": handler_info["handler"],
                        "handler_func": handler_info["func"],
                        "confidence": 0.9,  # High confidence for function calls
                        "is_question": False,
                        "raw_response": None
                    }
                else:
                    logger.warning(f"Unknown function: {function_name}")
                    return None
            
            # If no function call, it's likely a question/chat
            else:
                raw_response = message.content
                return {
                    "action": "ai_chat",
                    "parameters": {"question": command, "mode": "comprehensive"},
                    "handler": "_handle_ai_chat",
                    "confidence": 0.85,
                    "is_question": True,
                    "raw_response": raw_response
                }
        
        except Exception as e:
            logger.error(f"Error interpreting command with AI: {e}")
            return None
    
    def _get_handler_mapping(self) -> Dict[str, Dict]:
        """
        Maps function names to handler functions.
        This connects AI interpretations to actual handler functions.
        Note: Actual function imports happen at runtime to avoid circular imports.
        """
        # Return mapping structure - actual functions will be resolved at runtime
        return {
            "create_task": {"handler": "_handle_personal_create_task", "func": None},
            "list_tasks": {"handler": "_handle_personal_list_tasks", "func": None},
            "complete_task": {"handler": "_handle_personal_complete_task", "func": None},
            "delete_task": {"handler": "_handle_personal_delete_task", "func": None},
            "create_goal": {"handler": "_handle_personal_create_goal", "func": None},
            "list_goals": {"handler": "_handle_personal_list_goals", "func": None},
            "update_goal_progress": {"handler": "_handle_personal_goal_progress", "func": None},
            "create_calendar_event": {"handler": "_handle_personal_schedule_event", "func": None},
            "list_calendar_events": {"handler": "_handle_personal_today_schedule", "func": None},
            "create_reminder": {"handler": "_handle_add_reminder", "func": None},
            "list_reminders": {"handler": "_handle_list_reminders", "func": None},
            "create_note": {"handler": "_handle_personal_create_note", "func": None},
            "list_notes": {"handler": "_handle_personal_list_notes", "func": None},
            "search_notes": {"handler": "_handle_personal_search_notes", "func": None},
            "open_app": {"handler": "_open_any_app", "func": None},
            "close_app": {"handler": "_close_any_app", "func": None},
            "lock_screen": {"handler": "DeviceControl.lock_workstation", "func": None},
            "shutdown": {"handler": "DeviceControl.shutdown", "func": None},
            "restart": {"handler": "DeviceControl.restart", "func": None},
            "sleep": {"handler": "DeviceControl.sleep", "func": None},
            "screenshot": {"handler": "DeviceControl.take_screenshot", "func": None},
            "set_volume": {"handler": "DeviceControl.set_volume", "func": None},
            "mute_volume": {"handler": "DeviceControl.mute_volume", "func": None},
            "unmute_volume": {"handler": "DeviceControl.unmute_volume", "func": None},
            "get_weather": {"handler": "_handle_weather_wrapper", "func": None},
            "get_news": {"handler": "_handle_news_wrapper", "func": None},
            "get_time": {"handler": "_handle_get_time_wrapper", "func": None},
            "get_date": {"handler": "_handle_get_date_wrapper", "func": None},
            "play_youtube": {"handler": "_handle_youtube_play", "func": None},
            "youtube_control": {"handler": "_youtube_key", "func": None},
            "ai_chat": {"handler": "_handle_ai_chat", "func": None},
            "remember": {"handler": "_handle_remember", "func": None},
            "recall": {"handler": "_handle_recall", "func": None},
            "search_memory": {"handler": "_handle_memory_search", "func": None},
            "google_search": {"handler": "_handle_google_search", "func": None},
            "amazon_search": {"handler": "_handle_amazon_search", "func": None},
            "amazon_deals": {"handler": "_handle_amazon_deals", "func": None},
            "track_price": {"handler": "_handle_amazon_track", "func": None},
            "start_language_lesson": {"handler": "_handle_language_lesson", "func": None},
            "language_practice": {"handler": "_handle_language_practice", "func": None},
            "web_automation": {"handler": "_handle_web_automation", "func": None},
            "fill_form": {"handler": "_handle_web_form", "func": None},
            "vault_store": {"handler": "_handle_vault_store", "func": None},
            "vault_retrieve": {"handler": "_handle_vault_retrieve", "func": None},
            "office_command": {"handler": "_handle_office_command", "func": None},
            "create_automation": {"handler": "_handle_add_automation", "func": None},
            "list_automations": {"handler": "_handle_list_automations", "func": None},
            "multimodal_analysis": {"handler": "_handle_multimodal_analysis", "func": None},
            "analyze_file": {"handler": "_handle_predictions_analyze_file", "func": None},
            "build_app": {"handler": "_handle_build_app", "func": None},
            "tell_joke": {"handler": "_handle_joke", "func": None},
            "get_quote": {"handler": "_handle_get_quote_wrapper", "func": None},
            "get_suggestions": {"handler": "_handle_proactive_suggestions", "func": None},
            "list_files": {"handler": "_handle_list_files", "func": None},
            "open_file": {"handler": "_handle_open_file", "func": None},
            "search_file": {"handler": "_handle_search_file", "func": None},
            "create_folder": {"handler": "_handle_create_folder", "func": None},
            "delete_file": {"handler": "_handle_delete_file", "func": None},
        }
        
        return {
            "create_task": {"handler": "_handle_personal_create_task", "func": _handle_personal_create_task},
            "list_tasks": {"handler": "_handle_personal_list_tasks", "func": _handle_personal_list_tasks},
            "complete_task": {"handler": "_handle_personal_complete_task", "func": _handle_personal_complete_task},
            "delete_task": {"handler": "_handle_personal_delete_task", "func": None},  # TODO: implement
            "create_goal": {"handler": "_handle_personal_create_goal", "func": _handle_personal_create_goal},
            "list_goals": {"handler": "_handle_personal_list_goals", "func": _handle_personal_list_goals},
            "update_goal_progress": {"handler": "_handle_personal_goal_progress", "func": _handle_personal_goal_progress},
            "create_calendar_event": {"handler": "_handle_personal_schedule_event", "func": _handle_personal_schedule_event},
            "list_calendar_events": {"handler": "_handle_personal_today_schedule", "func": _handle_personal_today_schedule},
            "create_reminder": {"handler": "_handle_add_reminder", "func": _handle_add_reminder},
            "list_reminders": {"handler": "_handle_list_reminders", "func": _handle_list_reminders},
            "create_note": {"handler": "_handle_personal_create_note", "func": _handle_personal_create_note},
            "list_notes": {"handler": "_handle_personal_list_notes", "func": _handle_personal_list_notes},
            "search_notes": {"handler": "_handle_personal_search_notes", "func": _handle_personal_search_notes},
            "open_app": {"handler": "_open_any_app", "func": _open_any_app},
            "close_app": {"handler": "_close_any_app", "func": _close_any_app},
            "lock_screen": {"handler": "DeviceControl.lock_workstation", "func": DeviceControl.lock_workstation},
            "shutdown": {"handler": "DeviceControl.shutdown", "func": DeviceControl.shutdown},
            "restart": {"handler": "DeviceControl.restart", "func": DeviceControl.restart},
            "sleep": {"handler": "DeviceControl.sleep", "func": DeviceControl.sleep},
            "screenshot": {"handler": "DeviceControl.take_screenshot", "func": DeviceControl.take_screenshot},
            "set_volume": {"handler": "DeviceControl.set_volume", "func": DeviceControl.set_volume},
            "mute_volume": {"handler": "DeviceControl.mute_volume", "func": DeviceControl.mute_volume},
            "unmute_volume": {"handler": "DeviceControl.unmute_volume", "func": DeviceControl.unmute_volume},
            "get_weather": {"handler": "_handle_weather", "func": _handle_weather},
            "get_news": {"handler": "_handle_news", "func": _handle_news},
            "get_time": {"handler": "_handle_get_time", "func": _handle_get_time},
            "get_date": {"handler": "_handle_get_date", "func": _handle_get_date},
            "play_youtube": {"handler": "_handle_youtube_play", "func": _handle_youtube_play},
            "youtube_control": {"handler": "_youtube_key", "func": None},  # Special handling needed
            "ai_chat": {"handler": "_handle_ai_chat", "func": _handle_ai_chat},
            "remember": {"handler": "_handle_remember", "func": _handle_remember},
            "recall": {"handler": "_handle_recall", "func": _handle_recall},
            "search_memory": {"handler": "_handle_memory_search", "func": _handle_memory_search},
            "google_search": {"handler": "_handle_google_search", "func": _handle_google_search},
            "amazon_search": {"handler": "_handle_amazon_search", "func": _handle_amazon_search},
            "amazon_deals": {"handler": "_handle_amazon_deals", "func": _handle_amazon_deals},
            "track_price": {"handler": "_handle_amazon_track", "func": _handle_amazon_track},
            "start_language_lesson": {"handler": "_handle_language_lesson", "func": _handle_language_lesson},
            "language_practice": {"handler": "_handle_language_practice", "func": _handle_language_practice},
            "web_automation": {"handler": "_handle_web_automation", "func": _handle_web_automation},
            "fill_form": {"handler": "_handle_web_form", "func": _handle_web_form},
            "vault_store": {"handler": "_handle_vault_store", "func": _handle_vault_store},
            "vault_retrieve": {"handler": "_handle_vault_retrieve", "func": _handle_vault_retrieve},
            "office_command": {"handler": "_handle_office_command", "func": _handle_office_command},
            "create_automation": {"handler": "_handle_add_automation", "func": _handle_add_automation},
            "list_automations": {"handler": "_handle_list_automations", "func": _handle_list_automations},
            "multimodal_analysis": {"handler": "_handle_multimodal_analysis", "func": _handle_multimodal_analysis},
            "analyze_file": {"handler": "_handle_predictions_analyze_file", "func": _handle_predictions_analyze_file},
            "build_app": {"handler": "_handle_build_app", "func": _handle_build_app},
            "tell_joke": {"handler": "_handle_joke", "func": _handle_joke},
            "get_quote": {"handler": "_handle_get_quote", "func": None},  # TODO: implement
            "get_suggestions": {"handler": "_handle_proactive_suggestions", "func": _handle_proactive_suggestions},
            "list_files": {"handler": "_handle_list_files", "func": _handle_list_files},
            "open_file": {"handler": "_handle_open_file", "func": _handle_open_file},
            "search_file": {"handler": "_handle_search_file", "func": _handle_search_file},
            "create_folder": {"handler": "_handle_create_folder", "func": _handle_create_folder},
            "delete_file": {"handler": "_handle_delete_file", "func": _handle_delete_file},
        }


# Global instance
_ai_interpreter = None

def get_ai_interpreter() -> Optional[AICommandInterpreter]:
    """Get or create the global AI interpreter instance"""
    global _ai_interpreter
    if _ai_interpreter is None:
        _ai_interpreter = AICommandInterpreter()
    return _ai_interpreter

