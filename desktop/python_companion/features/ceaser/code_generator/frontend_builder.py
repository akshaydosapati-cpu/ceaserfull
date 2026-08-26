"""
Frontend Builder - Generates frontend code files
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
from openai import OpenAI

from .template_library import TemplateLibrary

logger = logging.getLogger(__name__)

class FrontendBuilder:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        self.client = OpenAI(api_key=self.openai_api_key)
        self.model = "gpt-4o-mini"
        self.template_library = TemplateLibrary()
    
    def build(
        self,
        project_name: str,
        framework: str,
        features: List[str],
        theme: str = "dark",
        intent: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate frontend code files
        
        Returns:
            {
                "files": [
                    {"path": str, "code": str},
                    ...
                ],
                "dependencies": List[str],
                "entry_point": str
            }
        """
        try:
            # Get base template
            template = self.template_library.get_template(framework)
            
            # Generate custom code using AI
            files = []
            
            # Start with template files
            for file_path, content in template.items():
                if isinstance(content, dict):
                    # JSON files (like package.json)
                    content_str = json.dumps(content, indent=2)
                else:
                    content_str = content
                
                # Replace placeholders
                code = content_str.replace("{project_name}", project_name)
                
                files.append({
                    "path": file_path,
                    "code": code
                })
            
            # Generate additional features using AI
            if features:
                feature_code = self._generate_features(
                    project_name=project_name,
                    framework=framework,
                    features=features,
                    theme=theme
                )
                files.extend(feature_code)
            
            # Extract dependencies from package.json
            dependencies = []
            for file in files:
                if file["path"] == "package.json":
                    try:
                        pkg = json.loads(file["code"])
                        deps = pkg.get("dependencies", {})
                        dependencies = list(deps.keys())
                    except:
                        pass
            
            # Determine entry point
            entry_point = "src/main.jsx" if framework.lower() in ["react", "nextjs"] else "src/main.js"
            
            return {
                "files": files,
                "dependencies": dependencies,
                "entry_point": entry_point,
                "framework": framework
            }
            
        except Exception as e:
            logger.error(f"Error building frontend: {e}")
            raise
    
    def _generate_features(
        self,
        project_name: str,
        framework: str,
        features: List[str],
        theme: str
    ) -> List[Dict[str, str]]:
        """Generate code for specific features"""
        try:
            system_prompt = f"""Generate {framework} components and code for the following features: {', '.join(features)}.

Return JSON with format:
{{
  "files": [
    {{"path": "src/components/ComponentName.jsx", "code": "..."}},
    ...
  ]
}}

Use modern React/Vue patterns. Keep code concise and functional."""
            
            user_prompt = f"""Project: {project_name}
Theme: {theme}
Features: {', '.join(features)}

Generate component files for these features."""
            
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
            logger.error(f"Error generating features: {e}")
            return []

