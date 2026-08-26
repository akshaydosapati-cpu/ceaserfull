import os
import shutil
import subprocess
import glob
from pathlib import Path
from typing import List, Optional, Dict, Any

class FileManager:
    # Track current working directory for voice commands
    current_dir = os.getcwd()
    
    @staticmethod
    def list_dir(path=None):
        """List files and folders in a directory."""
        try:
            if path is None:
                path = FileManager.current_dir
            files = os.listdir(path)
            return "\n".join(files) if files else f"No files in {path}"
        except Exception as e:
            return f"Failed to list directory: {e}"

    @staticmethod
    def create_folder(path):
        """Create a new folder."""
        try:
            os.makedirs(path, exist_ok=True)
            return f"Folder created: {path}"
        except Exception as e:
            return f"Failed to create folder: {e}"

    @staticmethod
    def delete_path(path):
        """Delete a file or folder."""
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return f"Deleted: {path}"
        except Exception as e:
            return f"Failed to delete: {e}"

    @staticmethod
    def move_path(src, dst):
        """Move a file or folder."""
        try:
            shutil.move(src, dst)
            return f"Moved {src} to {dst}"
        except Exception as e:
            return f"Failed to move: {e}"

    @staticmethod
    def copy_path(src, dst):
        """Copy a file or folder."""
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            return f"Copied {src} to {dst}"
        except Exception as e:
            return f"Failed to copy: {e}"

    @staticmethod
    def rename_path(src, dst):
        """Rename a file or folder."""
        try:
            os.rename(src, dst)
            return f"Renamed {src} to {dst}"
        except Exception as e:
            return f"Failed to rename: {e}"

    @staticmethod
    def open_folder(path=None):
        """Open a folder in Windows Explorer."""
        try:
            if path is None:
                path = FileManager.current_dir
            abs_path = os.path.abspath(path)
            subprocess.Popen(f'explorer "{abs_path}"')
            return f"Opened folder: {abs_path}"
        except Exception as e:
            return f"Failed to open folder: {e}"
    
    @staticmethod
    def open_file(file_path: str):
        """Open a file with its default application."""
        try:
            if not os.path.exists(file_path):
                return f"File not found: {file_path}"
            os.startfile(file_path)
            return f"Opened file: {file_path}"
        except Exception as e:
            return f"Failed to open file: {e}"
    
    @staticmethod
    def search_files(filename: str, search_path: Optional[str] = None, max_results: int = 10) -> List[str]:
        """
        Search for files by name across the file system.
        
        Args:
            filename: Name or partial name of file to search for
            search_path: Root directory to search (defaults to user's home)
            max_results: Maximum number of results to return
            
        Returns:
            List of file paths matching the search
        """
        if search_path is None:
            # Default to user's home directory and common locations
            search_paths = [
                os.path.expanduser("~"),
                os.path.join(os.path.expanduser("~"), "Documents"),
                os.path.join(os.path.expanduser("~"), "Desktop"),
                os.path.join(os.path.expanduser("~"), "Downloads"),
            ]
        else:
            search_paths = [search_path]
        
        found_files = []
        
        # Clean filename for glob pattern
        pattern = filename.lower()
        if not pattern.startswith('*'):
            pattern = f"*{pattern}*"
        
        for root_path in search_paths:
            if not os.path.exists(root_path):
                continue
            
            try:
                # Search recursively
                for root, dirs, files in os.walk(root_path):
                    # Skip hidden/system directories
                    dirs[:] = [d for d in dirs if not d.startswith('.') and not d.startswith('$')]
                    
                    for file in files:
                        if pattern.lower() in file.lower():
                            full_path = os.path.join(root, file)
                            found_files.append(full_path)
                            if len(found_files) >= max_results:
                                return found_files
            except (PermissionError, OSError):
                # Skip directories we can't access
                continue
        
        return found_files
    
    @staticmethod
    def find_file(filename: str) -> Optional[str]:
        """
        Find a single file by name. Returns first match or None.
        
        Args:
            filename: Name of file to find
            
        Returns:
            Full path to file or None if not found
        """
        results = FileManager.search_files(filename, max_results=1)
        return results[0] if results else None
    
    @staticmethod
    def change_directory(path: str) -> str:
        """
        Change current working directory.
        
        Args:
            path: Path to change to
            
        Returns:
            Success message or error
        """
        try:
            abs_path = os.path.abspath(path)
            if not os.path.exists(abs_path):
                return f"Path does not exist: {abs_path}"
            if not os.path.isdir(abs_path):
                return f"Not a directory: {abs_path}"
            
            FileManager.current_dir = abs_path
            os.chdir(abs_path)
            return f"Changed to directory: {abs_path}"
        except Exception as e:
            return f"Failed to change directory: {e}"
    
    @staticmethod
    def get_current_directory() -> str:
        """Get current working directory."""
        return FileManager.current_dir 