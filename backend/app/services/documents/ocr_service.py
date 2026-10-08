from __future__ import annotations

from pathlib import Path

try:
    import fitz
except ImportError:
    fitz = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import pytesseract
except ImportError:
    pytesseract = None


class OCRService:
    def extract_image_text(self, path: Path) -> str:
        if Image is None or pytesseract is None:
            return "OCR unavailable: dependencies not installed"
        try:
            return pytesseract.image_to_string(Image.open(path)).strip()
        except Exception as exc:
            return f"OCR unavailable: {exc}"

    def extract_pdf_text(self, path: Path, max_pages: int = 10) -> str:
        if fitz is None or Image is None or pytesseract is None:
            return "OCR unavailable: dependencies not installed"
        try:
            document = fitz.open(path)
            chunks = []
            for page in document[:max_pages]:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
                text = pytesseract.image_to_string(image).strip()
                if text:
                    chunks.append(text)
            return "\n\n".join(chunks)
        except Exception as exc:
            return f"OCR unavailable: {exc}"

