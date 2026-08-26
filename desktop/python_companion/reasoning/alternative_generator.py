from __future__ import annotations

import re


class AlternativeGenerator:
    def safer_alternative(self, text: str, conflicts: list[str], missing: list[str]) -> str:
        lowered = text.lower()
        if re.search(r"\b(delete|remove)\b", lowered) and re.search(r"\b(project|folder|file|this|it)\b", lowered):
            return "Archive it or move it to the Recycle Bin instead."
        if re.search(r"\boverwrite\b|\breplace existing\b", lowered):
            return "Save a copy instead of overwriting the existing file."
        if "push" in lowered and ("protected" in lowered or "protected_branch" in conflicts):
            return "Create a branch and prepare a pull request instead."
        if re.search(r"\b(close|quit|exit)\b", lowered) and ("unsaved_document" in conflicts or "unsaved" in lowered):
            return "Save the document first, then close it."
        if "repository" in missing:
            return "Select or name the repository first."
        if "active_resource" in missing:
            return "Select the file or resource first."
        return ""
