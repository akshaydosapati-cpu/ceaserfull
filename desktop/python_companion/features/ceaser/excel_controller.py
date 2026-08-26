"""
Excel Controller - Microsoft Excel operations via COM automation
"""

import logging
from typing import Optional, Dict, Any, List
from .office_control import OfficeControl

logger = logging.getLogger(__name__)

class ExcelController:
    """Controller for Excel operations"""
    
    def __init__(self, office_control: Optional[OfficeControl] = None):
        self.office_control = office_control or OfficeControl()
        self.excel_app = None
    
    def _ensure_connection(self) -> bool:
        """Ensure Excel is connected"""
        if self.excel_app is None:
            self.excel_app = self.office_control.connect_to_excel()
        return self.excel_app is not None
    
    def _get_active_workbook(self):
        """Get the active workbook"""
        if not self._ensure_connection():
            return None
        
        try:
            if self.excel_app.Workbooks.Count > 0:
                return self.excel_app.ActiveWorkbook
            return None
        except Exception as e:
            logger.error(f"Error getting active workbook: {e}")
            return None
    
    def _get_active_sheet(self):
        """Get the active worksheet"""
        workbook = self._get_active_workbook()
        if not workbook:
            return None
        
        try:
            return workbook.ActiveSheet
        except Exception as e:
            logger.error(f"Error getting active sheet: {e}")
            return None
    
    def filter_data(self, column: str, condition: str, value: Any) -> Dict[str, Any]:
        """Filter data in Excel column"""
        try:
            sheet = self._get_active_sheet()
            if not sheet:
                return {
                    "success": False,
                    "error": "No worksheet is open. Please open an Excel file first."
                }
            
            # Convert column letter to number (A=1, B=2, etc.)
            if column.isalpha():
                col_num = ord(column.upper()) - ord('A') + 1
            else:
                col_num = int(column)
            
            # Get the used range
            used_range = sheet.UsedRange
            if not used_range:
                return {
                    "success": False,
                    "error": "The worksheet is empty."
                }
            
            # Apply filter
            used_range.AutoFilter(Field=col_num, Criteria1=f"{condition}{value}")
            
            # Count visible rows
            visible_count = 0
            for row in range(2, used_range.Rows.Count + 1):  # Skip header
                if not sheet.Rows(row).Hidden:
                    visible_count += 1
            
            return {
                "success": True,
                "column": column,
                "condition": condition,
                "value": value,
                "visible_rows": visible_count
            }
            
        except Exception as e:
            logger.error(f"Error filtering data: {e}")
            return {
                "success": False,
                "error": f"Failed to filter data: {str(e)}"
            }
    
    def sort_data(self, column: str, ascending: bool = True) -> Dict[str, Any]:
        """Sort data by column"""
        try:
            sheet = self._get_active_sheet()
            if not sheet:
                return {
                    "success": False,
                    "error": "No worksheet is open. Please open an Excel file first."
                }
            
            # Convert column letter to number
            if column.isalpha():
                col_num = ord(column.upper()) - ord('A') + 1
            else:
                col_num = int(column)
            
            # Get the used range
            used_range = sheet.UsedRange
            if not used_range:
                return {
                    "success": False,
                    "error": "The worksheet is empty."
                }
            
            # Sort by column
            sort_order = 1 if ascending else 2  # xlAscending = 1, xlDescending = 2
            used_range.Sort(Key1=sheet.Cells(1, col_num), Order1=sort_order, Header=1)
            
            return {
                "success": True,
                "column": column,
                "order": "ascending" if ascending else "descending"
            }
            
        except Exception as e:
            logger.error(f"Error sorting data: {e}")
            return {
                "success": False,
                "error": f"Failed to sort data: {str(e)}"
            }
    
    def calculate(self, operation: str, column: Optional[str] = None, range_ref: Optional[str] = None) -> Dict[str, Any]:
        """Calculate sum, average, count, etc."""
        try:
            sheet = self._get_active_sheet()
            if not sheet:
                return {
                    "success": False,
                    "error": "No worksheet is open. Please open an Excel file first."
                }
            
            # Determine range
            if range_ref:
                calc_range = sheet.Range(range_ref)
            elif column:
                # Use entire column (skip header)
                col_num = ord(column.upper()) - ord('A') + 1 if column.isalpha() else int(column)
                used_range = sheet.UsedRange
                if used_range:
                    last_row = used_range.Rows.Count
                    calc_range = sheet.Range(sheet.Cells(2, col_num), sheet.Cells(last_row, col_num))
                else:
                    return {"success": False, "error": "The worksheet is empty."}
            else:
                # Use selected range
                calc_range = self.excel_app.Selection
                if not calc_range:
                    return {"success": False, "error": "No range selected. Please select a range or specify a column."}
            
            operation_lower = operation.lower()
            
            if operation_lower == "sum":
                result = self.excel_app.WorksheetFunction.Sum(calc_range)
            elif operation_lower == "average" or operation_lower == "avg":
                result = self.excel_app.WorksheetFunction.Average(calc_range)
            elif operation_lower == "count":
                result = self.excel_app.WorksheetFunction.Count(calc_range)
            elif operation_lower == "max":
                result = self.excel_app.WorksheetFunction.Max(calc_range)
            elif operation_lower == "min":
                result = self.excel_app.WorksheetFunction.Min(calc_range)
            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}. Supported: sum, average, count, max, min"
                }
            
            return {
                "success": True,
                "operation": operation,
                "result": float(result) if result else 0,
                "range": str(calc_range.Address) if calc_range else None
            }
            
        except Exception as e:
            logger.error(f"Error calculating: {e}")
            return {
                "success": False,
                "error": f"Failed to calculate: {str(e)}"
            }
    
    def find_data(self, search_value: str, highlight: bool = False) -> Dict[str, Any]:
        """Find data in Excel"""
        try:
            sheet = self._get_active_sheet()
            if not sheet:
                return {
                    "success": False,
                    "error": "No worksheet is open. Please open an Excel file first."
                }
            
            used_range = sheet.UsedRange
            if not used_range:
                return {
                    "success": False,
                    "error": "The worksheet is empty."
                }
            
            # Search for value
            found_cells = []
            for cell in used_range:
                if str(cell.Value).lower() == search_value.lower() or search_value.lower() in str(cell.Value).lower():
                    found_cells.append({
                        "address": cell.Address,
                        "value": str(cell.Value),
                        "row": cell.Row,
                        "column": cell.Column
                    })
                    if highlight:
                        cell.Interior.Color = 65535  # Yellow
            
            return {
                "success": True,
                "search_value": search_value,
                "count": len(found_cells),
                "cells": found_cells[:10],  # Limit to first 10
                "highlighted": highlight
            }
            
        except Exception as e:
            logger.error(f"Error finding data: {e}")
            return {
                "success": False,
                "error": f"Failed to find data: {str(e)}"
            }
    
    def summarize_data(self, use_ai: bool = True, openai_client=None) -> Dict[str, Any]:
        """Summarize data in the active sheet"""
        try:
            sheet = self._get_active_sheet()
            if not sheet:
                return {
                    "success": False,
                    "error": "No worksheet is open. Please open an Excel file first."
                }
            
            used_range = sheet.UsedRange
            if not used_range:
                return {
                    "success": False,
                    "error": "The worksheet is empty."
                }
            
            # Get data summary
            row_count = used_range.Rows.Count
            col_count = used_range.Columns.Count
            
            # Get column headers
            headers = []
            if row_count > 0:
                for col in range(1, min(col_count + 1, 10)):  # Limit to 10 columns
                    header_cell = sheet.Cells(1, col)
                    if header_cell.Value:
                        headers.append(str(header_cell.Value))
            
            # Get sample data (first few rows)
            sample_data = []
            for row in range(2, min(row_count + 1, 6)):  # First 5 data rows
                row_data = []
                for col in range(1, min(col_count + 1, 6)):  # First 5 columns
                    cell_value = sheet.Cells(row, col).Value
                    row_data.append(str(cell_value) if cell_value else "")
                sample_data.append(row_data)
            
            summary_text = f"Excel sheet with {row_count} rows and {col_count} columns. "
            summary_text += f"Columns: {', '.join(headers[:5])}. "
            summary_text += f"Sample data: {sample_data}"
            
            # If AI summarization is requested
            if use_ai and openai_client:
                try:
                    response = openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that analyzes Excel data and provides insights."},
                            {"role": "user", "content": f"Analyze and summarize this Excel data:\n\n{summary_text}"}
                        ],
                        max_tokens=300,
                        temperature=0.7
                    )
                    ai_summary = response.choices[0].message.content
                    return {
                        "success": True,
                        "summary": ai_summary,
                        "rows": row_count,
                        "columns": col_count,
                        "headers": headers,
                        "method": "ai"
                    }
                except Exception as e:
                    logger.error(f"AI summarization failed: {e}")
            
            return {
                "success": True,
                "summary": summary_text,
                "rows": row_count,
                "columns": col_count,
                "headers": headers,
                "method": "basic"
            }
            
        except Exception as e:
            logger.error(f"Error summarizing data: {e}")
            return {
                "success": False,
                "error": f"Failed to summarize data: {str(e)}"
            }
    
    def create_chart(self, chart_type: str = "column", data_range: Optional[str] = None) -> Dict[str, Any]:
        """Create a chart from data"""
        try:
            sheet = self._get_active_sheet()
            if not sheet:
                return {
                    "success": False,
                    "error": "No worksheet is open. Please open an Excel file first."
                }
            
            used_range = sheet.UsedRange
            if not used_range:
                return {
                    "success": False,
                    "error": "The worksheet is empty."
                }
            
            # Determine data range
            if data_range:
                chart_range = sheet.Range(data_range)
            else:
                chart_range = used_range
            
            # Create chart
            chart = sheet.ChartObjects().Add(100, 100, 400, 250).Chart
            chart.SetSourceData(chart_range)
            
            # Set chart type
            chart_type_map = {
                "column": 51,  # xlColumnClustered
                "line": 4,    # xlLine
                "pie": 5,     # xlPie
                "bar": 57     # xlBarClustered
            }
            chart_type_num = chart_type_map.get(chart_type.lower(), 51)
            chart.ChartType = chart_type_num
            
            return {
                "success": True,
                "chart_type": chart_type,
                "message": f"Chart created successfully"
            }
            
        except Exception as e:
            logger.error(f"Error creating chart: {e}")
            return {
                "success": False,
                "error": f"Failed to create chart: {str(e)}"
            }

