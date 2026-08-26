"""
Office Control Module - COM Automation for Microsoft Office
Provides connection management and base functionality for Word, Excel, and PowerPoint
"""

import os
import sys
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class OfficeControl:
    """Main controller for Office COM automation"""
    
    def __init__(self):
        self.word_app = None
        self.excel_app = None
        self.powerpoint_app = None
        self._com_available = None
        
    def _check_com_available(self) -> bool:
        """Check if COM/win32com is available"""
        if self._com_available is not None:
            return self._com_available
            
        try:
            import win32com.client
            self._com_available = True
            return True
        except ImportError:
            logger.warning("pywin32 not installed. Office control requires pywin32.")
            self._com_available = False
            return False
    
    def connect_to_word(self, create_if_missing: bool = True) -> Optional[Any]:
        """Connect to Microsoft Word application"""
        if not self._check_com_available():
            return None
            
        try:
            import win32com.client
            
            # Try to get existing Word instance
            try:
                self.word_app = win32com.client.GetActiveObject("Word.Application")
                logger.info("Connected to existing Word instance")
                return self.word_app
            except:
                # Word not running, create new instance if requested
                if create_if_missing:
                    self.word_app = win32com.client.Dispatch("Word.Application")
                    self.word_app.Visible = True
                    logger.info("Created new Word instance")
                    return self.word_app
                else:
                    logger.warning("Word is not running and create_if_missing is False")
                    return None
                    
        except Exception as e:
            logger.error(f"Error connecting to Word: {e}")
            return None
    
    def connect_to_excel(self, create_if_missing: bool = True) -> Optional[Any]:
        """Connect to Microsoft Excel application"""
        if not self._check_com_available():
            return None
            
        try:
            import win32com.client
            
            # Try to get existing Excel instance
            try:
                self.excel_app = win32com.client.GetActiveObject("Excel.Application")
                logger.info("Connected to existing Excel instance")
                return self.excel_app
            except:
                # Excel not running, create new instance if requested
                if create_if_missing:
                    self.excel_app = win32com.client.Dispatch("Excel.Application")
                    self.excel_app.Visible = True
                    logger.info("Created new Excel instance")
                    return self.excel_app
                else:
                    logger.warning("Excel is not running and create_if_missing is False")
                    return None
                    
        except Exception as e:
            logger.error(f"Error connecting to Excel: {e}")
            return None
    
    def connect_to_powerpoint(self, create_if_missing: bool = True) -> Optional[Any]:
        """Connect to Microsoft PowerPoint application"""
        if not self._check_com_available():
            return None
            
        try:
            import win32com.client
            
            # Try to get existing PowerPoint instance
            try:
                self.powerpoint_app = win32com.client.GetActiveObject("PowerPoint.Application")
                logger.info("Connected to existing PowerPoint instance")
                return self.powerpoint_app
            except:
                # PowerPoint not running, create new instance if requested
                if create_if_missing:
                    self.powerpoint_app = win32com.client.Dispatch("PowerPoint.Application")
                    self.powerpoint_app.Visible = True
                    logger.info("Created new PowerPoint instance")
                    return self.powerpoint_app
                else:
                    logger.warning("PowerPoint is not running and create_if_missing is False")
                    return None
                    
        except Exception as e:
            logger.error(f"Error connecting to PowerPoint: {e}")
            return None
    
    def get_office_status(self) -> Dict[str, bool]:
        """Get status of all Office applications"""
        status = {
            "word": False,
            "excel": False,
            "powerpoint": False,
            "com_available": self._check_com_available()
        }
        
        if not status["com_available"]:
            return status
        
        try:
            import win32com.client
            
            # Check Word
            try:
                win32com.client.GetActiveObject("Word.Application")
                status["word"] = True
            except:
                pass
            
            # Check Excel
            try:
                win32com.client.GetActiveObject("Excel.Application")
                status["excel"] = True
            except:
                pass
            
            # Check PowerPoint
            try:
                win32com.client.GetActiveObject("PowerPoint.Application")
                status["powerpoint"] = True
            except:
                pass
                
        except Exception as e:
            logger.error(f"Error checking Office status: {e}")
        
        return status
    
    def disconnect_all(self):
        """Disconnect from all Office applications (but don't close them)"""
        self.word_app = None
        self.excel_app = None
        self.powerpoint_app = None
        logger.info("Disconnected from all Office applications")

