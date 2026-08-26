"""
Word Controller - Microsoft Word operations via COM automation
"""

import logging
from typing import Optional, Dict, Any
from .office_control import OfficeControl

logger = logging.getLogger(__name__)

class WordController:
    """Controller for Word operations"""
    
    def __init__(self, office_control: Optional[OfficeControl] = None):
        self.office_control = office_control or OfficeControl()
        self.word_app = None
    
    def _ensure_connection(self) -> bool:
        """Ensure Word is connected"""
        if self.word_app is None:
            self.word_app = self.office_control.connect_to_word()
        return self.word_app is not None
    
    def _get_active_document(self):
        """Get the active document"""
        if not self._ensure_connection():
            return None
        
        try:
            if self.word_app.Documents.Count > 0:
                return self.word_app.ActiveDocument
            return None
        except Exception as e:
            logger.error(f"Error getting active document: {e}")
            return None
    
    def summarize_document(self, use_ai: bool = True, openai_client=None) -> Dict[str, Any]:
        """Summarize the active Word document"""
        try:
            doc = self._get_active_document()
            if not doc:
                return {
                    "success": False,
                    "error": "No document is open. Please open a Word document first."
                }
            
            # Extract all text from document
            full_text = doc.Content.Text
            
            if not full_text or len(full_text.strip()) == 0:
                return {
                    "success": False,
                    "error": "The document is empty."
                }
            
            # If AI summarization is requested and client is available
            if use_ai and openai_client:
                try:
                    response = openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that summarizes documents concisely."},
                            {"role": "user", "content": f"Please provide a concise summary of the following document:\n\n{full_text[:8000]}"}  # Limit to 8000 chars
                        ],
                        max_tokens=500,
                        temperature=0.7
                    )
                    summary = response.choices[0].message.content
                    return {
                        "success": True,
                        "summary": summary,
                        "word_count": len(full_text.split()),
                        "method": "ai"
                    }
                except Exception as e:
                    logger.error(f"AI summarization failed: {e}")
                    # Fall through to basic summary
            
            # Basic summary (first 500 characters)
            basic_summary = full_text[:500] + "..." if len(full_text) > 500 else full_text
            return {
                "success": True,
                "summary": basic_summary,
                "word_count": len(full_text.split()),
                "method": "basic"
            }
            
        except Exception as e:
            logger.error(f"Error summarizing document: {e}")
            return {
                "success": False,
                "error": f"Failed to summarize document: {str(e)}"
            }
    
    def get_word_count(self) -> Dict[str, Any]:
        """Get word count statistics for the active document"""
        try:
            doc = self._get_active_document()
            if not doc:
                return {
                    "success": False,
                    "error": "No document is open. Please open a Word document first."
                }
            
            # Get statistics from Word
            stats = {
                "words": doc.Words.Count,
                "characters": doc.Characters.Count,
                "characters_no_spaces": doc.Characters.Count - doc.Words.Count + 1,  # Approximate
                "paragraphs": doc.Paragraphs.Count,
                "pages": doc.ComputeStatistics(2)  # wdStatisticPages
            }
            
            return {
                "success": True,
                "statistics": stats
            }
            
        except Exception as e:
            logger.error(f"Error getting word count: {e}")
            return {
                "success": False,
                "error": f"Failed to get word count: {str(e)}"
            }
    
    def find_text(self, search_text: str, highlight: bool = False) -> Dict[str, Any]:
        """Find text in the active document"""
        try:
            doc = self._get_active_document()
            if not doc:
                return {
                    "success": False,
                    "error": "No document is open. Please open a Word document first."
                }
            
            # Use Word's Find functionality
            find_range = doc.Content
            find_range.Find.ClearFormatting()
            find_range.Find.Text = search_text
            
            count = 0
            while find_range.Find.Execute():
                count += 1
                if highlight:
                    find_range.HighlightColorIndex = 7  # Yellow highlight
                # Move to next occurrence
                find_range.Collapse(0)  # wdCollapseEnd
            
            return {
                "success": True,
                "count": count,
                "search_text": search_text,
                "highlighted": highlight
            }
            
        except Exception as e:
            logger.error(f"Error finding text: {e}")
            return {
                "success": False,
                "error": f"Failed to find text: {str(e)}"
            }
    
    def format_text(self, format_type: str, value: Optional[Any] = None) -> Dict[str, Any]:
        """Format selected text in Word"""
        try:
            doc = self._get_active_document()
            if not doc:
                return {
                    "success": False,
                    "error": "No document is open. Please open a Word document first."
                }
            
            selection = self.word_app.Selection
            if selection.Text.strip() == "":
                return {
                    "success": False,
                    "error": "No text is selected. Please select text first."
                }
            
            format_type_lower = format_type.lower()
            
            if format_type_lower == "bold":
                selection.Font.Bold = True
            elif format_type_lower == "italic":
                selection.Font.Italic = True
            elif format_type_lower == "underline":
                selection.Font.Underline = True
            elif format_type_lower == "font_size" and value:
                selection.Font.Size = float(value)
            elif format_type_lower == "heading" and value:
                # Set heading style (1-9)
                heading_num = int(value) if value else 1
                if 1 <= heading_num <= 9:
                    selection.Style = f"Heading {heading_num}"
            else:
                return {
                    "success": False,
                    "error": f"Unknown format type: {format_type}"
                }
            
            return {
                "success": True,
                "format_applied": format_type,
                "value": value
            }
            
        except Exception as e:
            logger.error(f"Error formatting text: {e}")
            return {
                "success": False,
                "error": f"Failed to format text: {str(e)}"
            }
    
    def insert_text(self, text: str, position: str = "cursor") -> Dict[str, Any]:
        """Insert text into the document"""
        try:
            doc = self._get_active_document()
            if not doc:
                return {
                    "success": False,
                    "error": "No document is open. Please open a Word document first."
                }
            
            selection = self.word_app.Selection
            
            if position.lower() == "beginning":
                doc.Range(0, 0).InsertBefore(text)
            elif position.lower() == "end":
                doc.Range().InsertAfter(text)
            else:  # cursor (default)
                selection.TypeText(text)
            
            return {
                "success": True,
                "text_inserted": text,
                "position": position
            }
            
        except Exception as e:
            logger.error(f"Error inserting text: {e}")
            return {
                "success": False,
                "error": f"Failed to insert text: {str(e)}"
            }
    
    def read_selected_text(self) -> Dict[str, Any]:
        """Get the currently selected text"""
        try:
            if not self._ensure_connection():
                return {
                    "success": False,
                    "error": "Could not connect to Word."
                }
            
            selection = self.word_app.Selection
            selected_text = selection.Text.strip()
            
            if not selected_text:
                return {
                    "success": False,
                    "error": "No text is selected. Please select text first."
                }
            
            return {
                "success": True,
                "text": selected_text,
                "length": len(selected_text)
            }
            
        except Exception as e:
            logger.error(f"Error reading selected text: {e}")
            return {
                "success": False,
                "error": f"Failed to read selected text: {str(e)}"
            }

