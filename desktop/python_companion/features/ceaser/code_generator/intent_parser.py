"""
Intent Parser - Converts natural language prompts into structured project plans
"""

import json
import logging
import os
from typing import Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

class IntentParser:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        self.client = OpenAI(api_key=self.openai_api_key)
        self.model = "gpt-4o-mini"  # Fast and cost-effective
    
    def parse(self, prompt: str, user_id: str) -> Dict[str, Any]:
        """
        Parse user prompt into structured project plan
        
        Returns:
            {
                "project_name": str,
                "description": str,
                "type": "web_app" | "api" | "mobile_app" | "desktop_app",
                "stack": {
                    "frontend": str,
                    "backend": str | None,
                    "database": str | None
                },
                "features": List[str],
                "theme": str,
                "requirements": List[str],
                "estimated_time": str
            }
        """
        try:
            system_prompt = """You are an expert software architect. Parse user prompts into structured project plans.

Return a JSON object with:
- project_name: Short, descriptive name (2-4 words)
- description: Brief description
- type: "web_app" | "api" | "mobile_app" | "desktop_app"
- stack: {frontend: string, backend: string|null, database: string|null}
- features: List of feature names
- theme: "light" | "dark" | "auto"
- requirements: List of technical requirements
- estimated_time: "quick" | "medium" | "long"

Be specific about frameworks (e.g., "React", "Next.js", "Vue", "Express", "FastAPI")."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validate and set defaults
            result.setdefault("project_name", "Untitled Project")
            result.setdefault("type", "web_app")
            result.setdefault("stack", {"frontend": "React", "backend": None, "database": None})
            result.setdefault("features", [])
            result.setdefault("theme", "dark")
            result.setdefault("requirements", [])
            result.setdefault("estimated_time", "medium")
            
            logger.info(f"Parsed intent for user {user_id}: {result.get('project_name')}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing intent: {e}")
            raise

