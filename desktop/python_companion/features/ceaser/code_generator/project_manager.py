"""
Project Manager - Manages code generation projects (cloud-only storage)
"""

import os
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

class ProjectManager:
    """Manages projects stored in cloud (Render backend storage)"""
    
    def __init__(self, storage_root: Optional[str] = None):
        # Storage root on Render backend (cloud-only)
        self.storage_root = storage_root or os.getenv(
            "CODE_GENERATOR_STORAGE_ROOT",
            "/tmp/code_projects"  # Default, should be set to persistent storage on Render
        )
        
        # Ensure storage directory exists
        os.makedirs(self.storage_root, exist_ok=True)
    
    def create_project(
        self,
        user_id: str,
        project_name: str,
        project_type: str,
        framework: str,
        business_id: Optional[str] = None,
        visibility: str = "private",  # 'private' | 'shared' | 'team'
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new project (cloud-only storage)
        
        Returns project metadata
        """
        try:
            project_id = str(uuid.uuid4())
            mode = "business" if business_id else "normal"
            
            # ALL projects stored in cloud
            if mode == "business":
                project_path = f"projects/business/{business_id}/{project_id}"
            elif visibility == "shared":
                project_path = f"projects/shared/{project_id}"
            else:
                # Private normal mode - still cloud
                project_path = f"projects/normal/{user_id}/{project_id}"
            
            full_path = os.path.join(self.storage_root, project_path)
            os.makedirs(full_path, exist_ok=True)
            
            project = {
                "id": project_id,
                "user_id": user_id,
                "business_id": business_id,
                "mode": mode,
                "name": project_name,
                "type": project_type,
                "framework": framework,
                "visibility": visibility,
                "storage_location": "cloud",
                "project_path": project_path,
                "full_path": full_path,
                "status": "building",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            }
            
            # Save project metadata
            metadata_file = os.path.join(full_path, ".project.json")
            with open(metadata_file, "w") as f:
                json.dump(project, f, indent=2)
            
            logger.info(f"Created project {project_id} for user {user_id}")
            return project
            
        except Exception as e:
            logger.error(f"Error creating project: {e}")
            raise
    
    def save_files(
        self,
        project_id: str,
        files: List[Dict[str, str]],
        user_id: str,
        business_id: Optional[str] = None
    ) -> bool:
        """Save generated files to project directory"""
        try:
            project = self.get_project(project_id, user_id, business_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            full_path = project["full_path"]
            
            for file_data in files:
                file_path = file_data.get("path")
                code = file_data.get("code", "")
                
                if not file_path:
                    continue
                
                # Create directory structure
                full_file_path = os.path.join(full_path, file_path)
                os.makedirs(os.path.dirname(full_file_path), exist_ok=True)
                
                # Write file
                with open(full_file_path, "w", encoding="utf-8") as f:
                    f.write(code)
            
            # Update project status
            project["status"] = "ready"
            project["updated_at"] = datetime.utcnow().isoformat()
            
            metadata_file = os.path.join(full_path, ".project.json")
            with open(metadata_file, "w") as f:
                json.dump(project, f, indent=2)
            
            logger.info(f"Saved {len(files)} files to project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving files: {e}")
            return False
    
    def get_project(
        self,
        project_id: str,
        user_id: str,
        business_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get project metadata"""
        try:
            # Try to find project in all possible locations
            search_paths = []
            
            if business_id:
                search_paths.append(f"projects/business/{business_id}/{project_id}")
            else:
                search_paths.append(f"projects/normal/{user_id}/{project_id}")
                search_paths.append(f"projects/shared/{project_id}")
            
            for rel_path in search_paths:
                full_path = os.path.join(self.storage_root, rel_path)
                metadata_file = os.path.join(full_path, ".project.json")
                
                if os.path.exists(metadata_file):
                    with open(metadata_file, "r") as f:
                        project = json.load(f)
                        # Verify access
                        if business_id and project.get("business_id") != business_id:
                            continue
                        if not business_id and project.get("user_id") != user_id and project.get("visibility") != "shared":
                            continue
                        return project
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting project: {e}")
            return None
    
    def list_projects(
        self,
        user_id: str,
        business_id: Optional[str] = None,
        visibility: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List projects for a user/business"""
        try:
            projects = []
            
            # Search in appropriate directories
            if business_id:
                search_dir = os.path.join(self.storage_root, f"projects/business/{business_id}")
            else:
                # Search normal and shared
                search_dirs = [
                    os.path.join(self.storage_root, f"projects/normal/{user_id}"),
                    os.path.join(self.storage_root, "projects/shared")
                ]
            
            search_dirs = search_dirs if not business_id else [search_dir]
            
            for search_dir in search_dirs:
                if not os.path.exists(search_dir):
                    continue
                
                for root, dirs, files in os.walk(search_dir):
                    if ".project.json" in files:
                        metadata_file = os.path.join(root, ".project.json")
                        try:
                            with open(metadata_file, "r") as f:
                                project = json.load(f)
                                
                                # Filter by visibility if specified
                                if visibility and project.get("visibility") != visibility:
                                    continue
                                
                                # Verify access
                                if business_id and project.get("business_id") != business_id:
                                    continue
                                if not business_id and project.get("user_id") != user_id and project.get("visibility") != "shared":
                                    continue
                                
                                projects.append(project)
                        except:
                            continue
            
            # Sort by updated_at
            projects.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
            
            return projects
            
        except Exception as e:
            logger.error(f"Error listing projects: {e}")
            return []
    
    def get_project_files(
        self,
        project_id: str,
        user_id: str,
        business_id: Optional[str] = None
    ) -> Dict[str, str]:
        """Get all files in a project"""
        try:
            project = self.get_project(project_id, user_id, business_id)
            if not project:
                return {}
            
            full_path = project["full_path"]
            files = {}
            
            for root, dirs, filenames in os.walk(full_path):
                # Skip hidden files and directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for filename in filenames:
                    if filename.startswith('.'):
                        continue
                    
                    file_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(file_path, full_path)
                    
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            files[rel_path] = f.read()
                    except:
                        pass
            
            return files
            
        except Exception as e:
            logger.error(f"Error getting project files: {e}")
            return {}
    
    def update_project_status(
        self,
        project_id: str,
        status: str,
        user_id: str,
        business_id: Optional[str] = None
    ) -> bool:
        """Update project status"""
        try:
            project = self.get_project(project_id, user_id, business_id)
            if not project:
                return False
            
            project["status"] = status
            project["updated_at"] = datetime.utcnow().isoformat()
            
            metadata_file = os.path.join(project["full_path"], ".project.json")
            with open(metadata_file, "w") as f:
                json.dump(project, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating project status: {e}")
            return False

