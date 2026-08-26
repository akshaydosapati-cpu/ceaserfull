"""
PowerPoint Controller - Microsoft PowerPoint operations via COM automation
"""

import logging
from typing import Optional, Dict, Any
from .office_control import OfficeControl

logger = logging.getLogger(__name__)

class PowerPointController:
    """Controller for PowerPoint operations"""
    
    def __init__(self, office_control: Optional[OfficeControl] = None):
        self.office_control = office_control or OfficeControl()
        self.powerpoint_app = None
    
    def _ensure_connection(self) -> bool:
        """Ensure PowerPoint is connected"""
        if self.powerpoint_app is None:
            self.powerpoint_app = self.office_control.connect_to_powerpoint()
        return self.powerpoint_app is not None
    
    def _get_active_presentation(self):
        """Get the active presentation"""
        if not self._ensure_connection():
            return None
        
        try:
            if self.powerpoint_app.Presentations.Count > 0:
                return self.powerpoint_app.ActivePresentation
            return None
        except Exception as e:
            logger.error(f"Error getting active presentation: {e}")
            return None
    
    def _get_active_slide(self):
        """Get the active slide"""
        presentation = self._get_active_presentation()
        if not presentation:
            return None
        
        try:
            return presentation.SlideShowWindow.View.Slide if hasattr(self.powerpoint_app, 'SlideShowWindow') else presentation.Slides(self.powerpoint_app.ActiveWindow.Selection.SlideRange.SlideIndex)
        except:
            try:
                return presentation.Slides(self.powerpoint_app.ActiveWindow.Selection.SlideRange.SlideIndex)
            except:
                try:
                    return presentation.Slides(1)  # Default to first slide
                except:
                    return None
    
    def navigate_slide(self, slide_number: Optional[int] = None, direction: Optional[str] = None) -> Dict[str, Any]:
        """Navigate to a specific slide or move in a direction"""
        try:
            presentation = self._get_active_presentation()
            if not presentation:
                return {
                    "success": False,
                    "error": "No presentation is open. Please open a PowerPoint file first."
                }
            
            total_slides = presentation.Slides.Count
            
            if slide_number:
                # Navigate to specific slide
                if 1 <= slide_number <= total_slides:
                    try:
                        # Try to navigate in slide show view
                        if hasattr(self.powerpoint_app, 'SlideShowWindow'):
                            self.powerpoint_app.SlideShowWindow.View.GotoSlide(slide_number)
                        else:
                            # Normal view - select the slide
                            self.powerpoint_app.ActiveWindow.Selection.SlideRange = presentation.Slides(slide_number)
                    except:
                        # Fallback: select slide in normal view
                        self.powerpoint_app.ActiveWindow.Selection.SlideRange = presentation.Slides(slide_number)
                    
                    return {
                        "success": True,
                        "slide_number": slide_number,
                        "total_slides": total_slides,
                        "message": f"Navigated to slide {slide_number}"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Slide number {slide_number} is out of range. Total slides: {total_slides}"
                    }
            
            elif direction:
                # Navigate in direction (next/previous)
                try:
                    current_slide = self.powerpoint_app.ActiveWindow.Selection.SlideRange.SlideIndex
                except:
                    current_slide = 1
                
                if direction.lower() == "next":
                    new_slide = min(current_slide + 1, total_slides)
                elif direction.lower() == "previous" or direction.lower() == "prev":
                    new_slide = max(current_slide - 1, 1)
                else:
                    return {
                        "success": False,
                        "error": f"Unknown direction: {direction}. Use 'next' or 'previous'"
                    }
                
                try:
                    if hasattr(self.powerpoint_app, 'SlideShowWindow'):
                        self.powerpoint_app.SlideShowWindow.View.GotoSlide(new_slide)
                    else:
                        self.powerpoint_app.ActiveWindow.Selection.SlideRange = presentation.Slides(new_slide)
                except:
                    self.powerpoint_app.ActiveWindow.Selection.SlideRange = presentation.Slides(new_slide)
                
                return {
                    "success": True,
                    "slide_number": new_slide,
                    "total_slides": total_slides,
                    "direction": direction
                }
            else:
                return {
                    "success": False,
                    "error": "Please specify either slide_number or direction (next/previous)"
                }
                
        except Exception as e:
            logger.error(f"Error navigating slide: {e}")
            return {
                "success": False,
                "error": f"Failed to navigate slide: {str(e)}"
            }
    
    def read_slide_content(self, slide_number: Optional[int] = None) -> Dict[str, Any]:
        """Read content from a slide"""
        try:
            presentation = self._get_active_presentation()
            if not presentation:
                return {
                    "success": False,
                    "error": "No presentation is open. Please open a PowerPoint file first."
                }
            
            # Get slide
            if slide_number:
                if 1 <= slide_number <= presentation.Slides.Count:
                    slide = presentation.Slides(slide_number)
                else:
                    return {
                        "success": False,
                        "error": f"Slide number {slide_number} is out of range."
                    }
            else:
                slide = self._get_active_slide()
                if not slide:
                    return {
                        "success": False,
                        "error": "Could not determine active slide."
                    }
            
            # Extract text from all shapes
            slide_text = []
            for shape in slide.Shapes:
                if hasattr(shape, 'TextFrame') and shape.TextFrame.HasText:
                    slide_text.append(shape.TextFrame.TextRange.Text)
            
            full_text = "\n".join(slide_text).strip()
            
            return {
                "success": True,
                "slide_number": slide.SlideIndex,
                "text": full_text,
                "text_parts": slide_text
            }
            
        except Exception as e:
            logger.error(f"Error reading slide content: {e}")
            return {
                "success": False,
                "error": f"Failed to read slide content: {str(e)}"
            }
    
    def summarize_presentation(self, use_ai: bool = True, openai_client=None) -> Dict[str, Any]:
        """Summarize the entire presentation"""
        try:
            presentation = self._get_active_presentation()
            if not presentation:
                return {
                    "success": False,
                    "error": "No presentation is open. Please open a PowerPoint file first."
                }
            
            total_slides = presentation.Slides.Count
            
            # Extract text from all slides
            all_text = []
            for i in range(1, total_slides + 1):
                slide = presentation.Slides(i)
                slide_text = []
                for shape in slide.Shapes:
                    if hasattr(shape, 'TextFrame') and shape.TextFrame.HasText:
                        slide_text.append(shape.TextFrame.TextRange.Text)
                if slide_text:
                    all_text.append(f"Slide {i}: {' '.join(slide_text)}")
            
            full_text = "\n".join(all_text)
            
            if not full_text.strip():
                return {
                    "success": False,
                    "error": "The presentation contains no text."
                }
            
            # If AI summarization is requested
            if use_ai and openai_client:
                try:
                    response = openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that summarizes presentations concisely."},
                            {"role": "user", "content": f"Please provide a concise summary of this presentation:\n\n{full_text[:8000]}"}
                        ],
                        max_tokens=500,
                        temperature=0.7
                    )
                    summary = response.choices[0].message.content
                    return {
                        "success": True,
                        "summary": summary,
                        "total_slides": total_slides,
                        "method": "ai"
                    }
                except Exception as e:
                    logger.error(f"AI summarization failed: {e}")
            
            # Basic summary
            basic_summary = f"Presentation with {total_slides} slides. Key topics: {full_text[:500]}"
            return {
                "success": True,
                "summary": basic_summary,
                "total_slides": total_slides,
                "method": "basic"
            }
            
        except Exception as e:
            logger.error(f"Error summarizing presentation: {e}")
            return {
                "success": False,
                "error": f"Failed to summarize presentation: {str(e)}"
            }
    
    def get_slide_count(self) -> Dict[str, Any]:
        """Get the total number of slides"""
        try:
            presentation = self._get_active_presentation()
            if not presentation:
                return {
                    "success": False,
                    "error": "No presentation is open. Please open a PowerPoint file first."
                }
            
            total_slides = presentation.Slides.Count
            
            return {
                "success": True,
                "total_slides": total_slides
            }
            
        except Exception as e:
            logger.error(f"Error getting slide count: {e}")
            return {
                "success": False,
                "error": f"Failed to get slide count: {str(e)}"
            }
    
    def add_slide(self, layout: str = "blank", position: Optional[int] = None) -> Dict[str, Any]:
        """Add a new slide to the presentation"""
        try:
            presentation = self._get_active_presentation()
            if not presentation:
                return {
                    "success": False,
                    "error": "No presentation is open. Please open a PowerPoint file first."
                }
            
            # Layout mapping
            layout_map = {
                "blank": 12,  # ppLayoutBlank
                "title": 0,   # ppLayoutTitle
                "title_content": 1,  # ppLayoutTitleOnly
                "content": 2   # ppLayoutText
            }
            layout_num = layout_map.get(layout.lower(), 12)
            
            # Add slide
            if position:
                new_slide = presentation.Slides.AddSlide(position, presentation.SlideLayouts(layout_num))
            else:
                # Add at end
                new_slide = presentation.Slides.AddSlide(presentation.Slides.Count + 1, presentation.SlideLayouts(layout_num))
            
            return {
                "success": True,
                "slide_number": new_slide.SlideIndex,
                "layout": layout,
                "total_slides": presentation.Slides.Count
            }
            
        except Exception as e:
            logger.error(f"Error adding slide: {e}")
            return {
                "success": False,
                "error": f"Failed to add slide: {str(e)}"
            }

