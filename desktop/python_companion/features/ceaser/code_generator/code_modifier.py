"""
Code Modifier - Updates existing project code based on natural language instructions
"""

import json
import logging
import os
from typing import Dict, Any, Optional, List
from openai import OpenAI

logger = logging.getLogger(__name__)

class CodeModifier:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        self.client = OpenAI(api_key=self.openai_api_key)
        self.model = "gpt-4o-mini"
    
    def modify(
        self,
        project_id: str,
        command: str,
        current_files: Dict[str, str],
        project_structure: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Modify existing project code
        
        Args:
            project_id: Project identifier
            command: Natural language modification command
            current_files: Dict of {file_path: file_content}
            project_structure: Optional project metadata
        
        Returns:
            {
                "status": "modified",
                "files": [
                    {"path": str, "code": str, "action": "modified" | "created" | "deleted"}
                ],
                "diff": List[str]
            }
        """
        try:
            system_prompt = """You are a code modification assistant. Update code files based on user commands.

Return JSON:
{
  "files": [
    {
      "path": "path/to/file.js",
      "code": "updated file content",
      "action": "modified" | "created" | "deleted"
    }
  ],
  "diff": ["summary of changes"]
}

Only modify files that need changes. Keep other files unchanged."""
            
            # Prepare context
            files_context = "\n".join([
                f"=== {path} ===\n{content}\n"
                for path, content in list(current_files.items())[:10]  # Limit context
            ])
            
            user_prompt = f"""Project: {project_id}
Command: {command}

Current files:
{files_context}

Update the code according to the command."""
            
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
            
            # Validate result
            files = result.get("files", [])
            diff = result.get("diff", [])
            
            logger.info(f"Modified project {project_id}: {len(files)} files changed")
            
            return {
                "status": "modified",
                "files": files,
                "diff": diff
            }
            
        except Exception as e:
            logger.error(f"Error modifying code: {e}")
            raise

