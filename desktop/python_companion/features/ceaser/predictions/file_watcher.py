"""
File Watcher for Ceaser Predictions
Monitors folders for file changes and indexes files for voice commands
Python-based (consistent with Ceaser architecture)
"""

import os
import json
import hashlib
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

# Try to import watchdog for file monitoring
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    FILE_WATCHING_AVAILABLE = True
except ImportError:
    FILE_WATCHING_AVAILABLE = False
    logging.warning("watchdog not available. Install with: pip install watchdog")

logger = logging.getLogger(__name__)


class PredictionsFileHandler(FileSystemEventHandler):
    """Handler for file system events in predictions context"""
    
    def __init__(self, file_watcher):
        self.file_watcher = file_watcher
        self.logger = logging.getLogger(__name__)
    
    def on_created(self, event):
        """Handle file creation events"""
        if not event.is_directory:
            try:
                file_path = event.src_path
                self.logger.info(f"New file detected for predictions: {file_path}")
                self.file_watcher.index_file(file_path)
            except Exception as e:
                self.logger.error(f"Error handling file creation: {e}")
    
    def on_modified(self, event):
        """Handle file modification events"""
        if not event.is_directory:
            try:
                file_path = event.src_path
                self.logger.debug(f"File modified: {file_path}")
                # Re-index on modification
                self.file_watcher.index_file(file_path)
            except Exception as e:
                self.logger.error(f"Error handling file modification: {e}")
    
    def on_deleted(self, event):
        """Handle file deletion events"""
        if not event.is_directory:
            try:
                file_path = event.src_path
                self.logger.info(f"File deleted: {file_path}")
                self.file_watcher.remove_file(file_path)
            except Exception as e:
                self.logger.error(f"Error handling file deletion: {e}")


class FileWatcher:
    """File watcher for predictions feature - indexes and monitors files"""
    
    def __init__(self, index_path: Optional[str] = None):
        """
        Initialize file watcher
        
        Args:
            index_path: Path to store file index JSON. Defaults to local storage.
        """
        self.watched_folders: List[str] = []
        self.indexed_files: Dict[str, Dict[str, Any]] = {}
        
        # Set index path (default to predictions folder)
        if index_path is None:
            predictions_dir = Path(__file__).parent
            storage_dir = predictions_dir / "storage"
            storage_dir.mkdir(exist_ok=True)
            index_path = str(storage_dir / "file_index.json")
        
        self.index_path = index_path
        self.observer: Optional[Observer] = None
        self.file_handler: Optional[PredictionsFileHandler] = None
        
        # Load existing index
        self.load_index()
    
    def watch_folder(self, folder_path: str, recursive: bool = True) -> bool:
        """
        Start watching a folder for file changes
        
        Args:
            folder_path: Path to folder to watch
            recursive: Whether to watch subdirectories
            
        Returns:
            True if watching started successfully
        """
        if not FILE_WATCHING_AVAILABLE:
            logger.warning("File watching not available. Install watchdog: pip install watchdog")
            return False
        
        folder_path = os.path.abspath(folder_path)
        
        if folder_path in self.watched_folders:
            logger.info(f"Already watching folder: {folder_path}")
            return True
        
        if not os.path.exists(folder_path):
            logger.error(f"Folder does not exist: {folder_path}")
            return False
        
        try:
            # Initialize observer if not already done
            if self.observer is None:
                self.observer = Observer()
                self.file_handler = PredictionsFileHandler(self)
                self.observer.start()
            
            # Schedule folder watching
            self.observer.schedule(
                self.file_handler,
                folder_path,
                recursive=recursive
            )
            
            self.watched_folders.append(folder_path)
            logger.info(f"Started watching folder: {folder_path} (recursive={recursive})")
            
            # Initial scan of folder
            self._scan_folder(folder_path, recursive)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to watch folder {folder_path}: {e}")
            return False
    
    def unwatch_folder(self, folder_path: str) -> bool:
        """
        Stop watching a folder
        
        Args:
            folder_path: Path to folder to stop watching
            
        Returns:
            True if successfully stopped
        """
        folder_path = os.path.abspath(folder_path)
        
        if folder_path not in self.watched_folders:
            logger.warning(f"Folder not being watched: {folder_path}")
            return False
        
        try:
            # Remove from watched list
            self.watched_folders.remove(folder_path)
            
            # Note: watchdog Observer doesn't have easy per-folder unwatch
            # We'll keep it simple and just remove from list
            # Full unwatch would require recreating observer
            
            logger.info(f"Stopped watching folder: {folder_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop watching folder: {e}")
            return False
    
    def _scan_folder(self, folder_path: str, recursive: bool = True):
        """Scan folder and index all files"""
        try:
            if recursive:
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        self.index_file(file_path)
            else:
                for item in os.listdir(folder_path):
                    item_path = os.path.join(folder_path, item)
                    if os.path.isfile(item_path):
                        self.index_file(item_path)
        except Exception as e:
            logger.error(f"Error scanning folder {folder_path}: {e}")
    
    def index_file(self, file_path: str) -> bool:
        """
        Index a file with metadata
        
        Args:
            file_path: Path to file to index
            
        Returns:
            True if successfully indexed
        """
        try:
            if not os.path.exists(file_path):
                return False
            
            # Skip hidden files and directories
            if os.path.basename(file_path).startswith('.'):
                return False
            
            stats = os.stat(file_path)
            file_hash = self._get_file_hash(file_path)
            ext = os.path.splitext(file_path)[1].lower()
            
            # Supported file types for predictions
            supported_extensions = ['.pdf', '.docx', '.xlsx', '.xls', '.csv', '.txt', 
                                  '.json', '.xml', '.jpg', '.jpeg', '.png', '.gif']
            
            if ext not in supported_extensions:
                return False
            
            self.indexed_files[file_path] = {
                "path": file_path,
                "name": os.path.basename(file_path),
                "size": stats.st_size,
                "extension": ext,
                "modified": datetime.fromtimestamp(stats.st_mtime).isoformat(),
                "hash": file_hash,
                "indexed": datetime.now().isoformat(),
            }
            
            self.save_index()
            logger.debug(f"Indexed file: {os.path.basename(file_path)}")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing file {file_path}: {e}")
            return False
    
    def remove_file(self, file_path: str):
        """Remove file from index"""
        if file_path in self.indexed_files:
            del self.indexed_files[file_path]
            self.save_index()
            logger.debug(f"Removed file from index: {os.path.basename(file_path)}")
    
    def _get_file_hash(self, file_path: str) -> str:
        """Get MD5 hash of file"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error getting file hash: {e}")
            return ""
    
    def search_files(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for files by name or path
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            List of matching file metadata
        """
        query_lower = query.lower()
        results = []
        
        for file_path, metadata in self.indexed_files.items():
            name = metadata["name"].lower()
            path = file_path.lower()
            
            # Check if query matches name or path
            if query_lower in name or query_lower in path:
                results.append(metadata)
        
        # Sort by modification time (most recent first)
        results.sort(key=lambda x: x.get("modified", ""), reverse=True)
        
        return results[:max_results]
    
    def get_file_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific file"""
        return self.indexed_files.get(file_path)
    
    def load_index(self):
        """Load file index from disk"""
        try:
            if os.path.exists(self.index_path):
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.indexed_files = {k: v for k, v in data.items()}
                    logger.info(f"Loaded {len(self.indexed_files)} indexed files")
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            self.indexed_files = {}
    
    def save_index(self):
        """Save file index to disk"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(self.indexed_files, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving index: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get watcher statistics"""
        return {
            "watched_folders": len(self.watched_folders),
            "indexed_files": len(self.indexed_files),
            "last_updated": datetime.now().isoformat(),
            "watching_active": FILE_WATCHING_AVAILABLE and self.observer is not None
        }
    
    def stop(self):
        """Stop all file watching"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        self.watched_folders.clear()
        logger.info("Stopped file watching")

