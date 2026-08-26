"""
Backend Builder - Generates backend API code
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

class BackendBuilder:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        self.client = OpenAI(api_key=self.openai_api_key)
        self.model = "gpt-4o-mini"
    
    def build(
        self,
        project_name: str,
        stack: str,
        features: List[str],
        frontend_stack: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate backend code files
        
        Returns:
            {
                "files": [
                    {"path": str, "code": str},
                    ...
                ],
                "dependencies": List[str],
                "api_endpoints": List[str]
            }
        """
        try:
            if stack.lower() == "none" or not stack:
                return {
                    "files": [],
                    "dependencies": [],
                    "api_endpoints": []
                }
            
            # Generate backend code using AI
            files = []
            
            if "fastapi" in stack.lower() or "python" in stack.lower():
                files = self._generate_fastapi_backend(project_name, features)
            elif "express" in stack.lower() or "node" in stack.lower():
                files = self._generate_express_backend(project_name, features)
            elif "firebase" in stack.lower():
                files = self._generate_firebase_backend(project_name, features)
            else:
                # Default to FastAPI
                files = self._generate_fastapi_backend(project_name, features)
            
            # Extract dependencies
            dependencies = []
            api_endpoints = []
            
            for file in files:
                if "package.json" in file["path"] or "requirements.txt" in file["path"]:
                    try:
                        if file["path"] == "requirements.txt":
                            deps = [line.strip() for line in file["code"].split("\n") if line.strip() and not line.startswith("#")]
                            dependencies = deps
                        elif file["path"] == "package.json":
                            pkg = json.loads(file["code"])
                            deps = pkg.get("dependencies", {})
                            dependencies = list(deps.keys())
                    except:
                        pass
                
                # Extract API endpoints from route files
                if "routes" in file["path"] or "api" in file["path"]:
                    # Simple extraction - could be improved
                    if "@app." in file["code"] or "router." in file["code"]:
                        # Extract endpoint patterns
                        lines = file["code"].split("\n")
                        for line in lines:
                            if "@app.get" in line or "@app.post" in line or "router.get" in line or "router.post" in line:
                                # Extract path
                                if '"' in line:
                                    endpoint = line.split('"')[1]
                                    api_endpoints.append(endpoint)
            
            return {
                "files": files,
                "dependencies": dependencies,
                "api_endpoints": api_endpoints,
                "stack": stack
            }
            
        except Exception as e:
            logger.error(f"Error building backend: {e}")
            raise
    
    def _generate_fastapi_backend(
        self,
        project_name: str,
        features: List[str]
    ) -> List[Dict[str, str]]:
        """Generate FastAPI backend"""
        try:
            system_prompt = """Generate a FastAPI backend with the following structure:

1. main.py - FastAPI app entry point
2. requirements.txt - Python dependencies
3. routes/ - API route files

Return JSON:
{
  "files": [
    {"path": "main.py", "code": "..."},
    {"path": "requirements.txt", "code": "..."},
    {"path": "routes/api.py", "code": "..."}
  ]
}"""
            
            user_prompt = f"""Project: {project_name}
Features: {', '.join(features)}

Generate a FastAPI backend with endpoints for these features."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get("files", [])
            
        except Exception as e:
            logger.error(f"Error generating FastAPI backend: {e}")
            return []
    
    def _generate_express_backend(
        self,
        project_name: str,
        features: List[str]
    ) -> List[Dict[str, str]]:
        """Generate Express.js backend"""
        try:
            system_prompt = """Generate an Express.js backend with:

1. package.json
2. server.js - Express app entry point
3. routes/ - API route files

Return JSON with files array."""
            
            user_prompt = f"""Project: {project_name}
Features: {', '.join(features)}

Generate Express.js backend."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get("files", [])
            
        except Exception as e:
            logger.error(f"Error generating Express backend: {e}")
            return []
    
    def _generate_firebase_backend(
        self,
        project_name: str,
        features: List[str]
    ) -> List[Dict[str, str]]:
        """Generate Firebase functions backend"""
        try:
            system_prompt = """Generate Firebase Functions backend with:

1. package.json
2. functions/index.js - Firebase functions

Return JSON with files array."""
            
            user_prompt = f"""Project: {project_name}
Features: {', '.join(features)}

Generate Firebase Functions."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get("files", [])
            
        except Exception as e:
            logger.error(f"Error generating Firebase backend: {e}")
            return []

