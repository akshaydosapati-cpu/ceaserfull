"""
Shared response completeness validation for long outputs.

Extracts structural requirements from user requests, tracks completion,
detects incomplete responses, and ensures honest status reporting.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StructuralRequirement:
    """Represents an explicit structural requirement from the user request."""
    type: str  # "scenes", "sections", "steps", "questions", "chapters", "acts"
    count: int | None  # None means "at least one" or "complete"
    min_count: int = 1


@dataclass
class CompletenessResult:
    """Result of completeness validation."""
    is_complete: bool
    requirements_satisfied: bool
    is_truncated: bool
    is_mid_sentence: bool
    has_duplicates: bool
    issues: list[str] = field(default_factory=list)
    partial_status: str | None = None  # "truncated", "incomplete", "partial"
    required_count: int | None = None
    found_count: int | None = None


class CompletenessValidator:
    """
    Validates response completeness against explicit user requirements.

    Extracts requirements like "50 scenes" or "5 sections" from the request,
    then validates the response satisfies those requirements.
    """

    # Patterns to extract explicit structural requirements
    REQUIREMENT_PATTERNS = [
        # Scene/act patterns
        (r"(\d+)\s*(?:scenes?|acts?|chapters?)\b", "scenes"),
        (r"(?:scenes?|acts?|chapters?)\s*(\d+)\b", "scenes"),
        # Section/step patterns
        (r"(\d+)\s*(?:sections?|steps?|parts?|phases?|segments?)\b", "sections"),
        (r"(?:sections?|steps?|parts?|phases?|segments?)\s*(\d+)\b", "sections"),
        # Question patterns
        (r"(\d+)\s*(?:questions?|points?|items?)\b", "questions"),
        (r"(?:questions?|points?|items?)\s*(\d+)\b", "questions"),
        # List patterns
        (r"(?:a|an)?\s*(\d+)\s*(?:item|list|entry|element)", "items"),
    ]

    # Markers that indicate structured content
    STRUCTURE_MARKERS = {
        "scenes": [r"###?\s*SCENE\s*\d+", r"###?\s*ACT\s+[IVX]+", r"Scene\s+\d+", r"Act\s+[IVX]+"],
        "sections": [r"##\s+\w+", r"###\s+\w+", r"^\d+\.\s+", r"^\[.+\]"],
        "steps": [r"^\d+[.)]\s+", r"Step\s+\d+", r"Phase\s+\d+", r"Stage\s+\d+"],
        "questions": [r"^\d+[?.\s]", r"Q\d+[:\s]", r"Question\s+\d+"],
    }

    # Truncation indicators
    TRUNCATION_PATTERNS = [
        r"\.\.\.$",
        r"…$",
        r"continue[ds]?\s+in\s+(next|following|subsequent)",
        r"(will|would)\s+(be|have)\s+(continue|more)",
        r"(?:and|but)\s+then$",
        r"(?:to\s+)?be\s+(continued|expanded|elaborated)",
        r"(?:please|feel free to)\s+(ask|let me know|contact)",
        r"\s*\(truncated\)\s*$",  # Explicit truncation marker
    ]

    # Mid-sentence truncation patterns (incomplete sentences)
    MID_SENTENCE_PATTERNS = [
        r"[,\-:;]\s*$",  # Ends with punctuation but no period
        r"\b(the|a|an|this|that|is|are|was|were|has|have|had|will|would|can|could|should|may|might)\s*$",  # Ends mid-sentence
        r"\b(and|or|but|so|yet|for|nor)\s*$",  # Conjunction at end
        r"\b(in|on|at|to|from|with|by|for|of|as|is|are|was|were|been|being)\s*$",  # Preposition at end
    ]

    @classmethod
    def extract_requirements(cls, message: str) -> list[StructuralRequirement]:
        """Extract explicit structural requirements from user message."""
        requirements = []
        normalized = message.lower()

        for pattern, req_type in cls.REQUIREMENT_PATTERNS:
            matches = re.findall(pattern, normalized, re.IGNORECASE)
            for match in matches:
                try:
                    count = int(match) if match else None
                    if count and count > 0:
                        requirements.append(StructuralRequirement(
                            type=req_type,
                            count=count,
                            min_count=max(1, count - 2)  # Allow some flexibility
                        ))
                except (ValueError, TypeError):
                    continue

        return requirements

    @classmethod
    def count_structures(cls, content: str, req_type: str) -> int:
        """Count occurrences of a specific structure type in content."""
        if req_type not in cls.STRUCTURE_MARKERS:
            return 0

        count = 0
        for marker in cls.STRUCTURE_MARKERS[req_type]:
            count += len(re.findall(marker, content, re.MULTILINE | re.IGNORECASE))

        return count

    @classmethod
    def detect_truncation(cls, content: str) -> bool:
        """Detect if content appears to be truncated."""
        stripped = content.strip()

        for pattern in cls.TRUNCATION_PATTERNS:
            if re.search(pattern, stripped, re.IGNORECASE):
                return True

        return False

    @classmethod
    def detect_mid_sentence(cls, content: str) -> bool:
        """Detect if content ends mid-sentence."""
        stripped = content.strip()

        for pattern in cls.MID_SENTENCE_PATTERNS:
            if re.search(pattern, stripped, re.IGNORECASE):
                return True

        # Also check if last character is not a sentence terminator
        if stripped and stripped[-1] not in ".!?":
            # Check if there's an incomplete sentence structure
            sentences = re.split(r"[.!?]+", stripped)
            if sentences and sentences[-1].strip():
                # Last "sentence" has content but no terminator
                return True

        return False

    @classmethod
    def detect_duplicates(cls, content: str, req_type: str) -> list[str]:
        """Detect duplicate sections, scenes, etc."""
        if req_type not in cls.STRUCTURE_MARKERS:
            return []

        duplicates = []
        seen = {}

        for marker in cls.STRUCTURE_MARKERS[req_type]:
            matches = re.finditer(marker, content, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                # Extract the header/title
                header = match.group(0).strip()
                if header in seen:
                    duplicates.append(header)
                else:
                    seen[header] = match.start()

        return duplicates

    @classmethod
    def validate(cls, message: str, content: str, continuation_count: int = 0, max_continuations: int = 2) -> CompletenessResult:
        """
        Validate response completeness against extracted requirements.

        Returns a CompletenessResult with:
        - is_complete: True if all requirements are satisfied
        - requirements_satisfied: True if extracted requirements are met
        - is_truncated: True if truncation detected
        - is_mid_sentence: True if content ends mid-sentence
        - has_duplicates: True if duplicate structures found
        - partial_status: Set when response is incomplete
        """
        issues = []

        # Extract requirements from message
        requirements = cls.extract_requirements(message)

        # Check each requirement
        requirements_satisfied = True
        required_count = None
        found_count = None

        for req in requirements:
            found = cls.count_structures(content, req.type)
            found_count = found
            required_count = req.count

            if req.count and found < req.min_count:
                requirements_satisfied = False
                issues.append(f"Expected at least {req.min_count} {req.type}, found {found}")

        # Detect truncation
        is_truncated = cls.detect_truncation(content)
        if is_truncated:
            issues.append("Content appears truncated")

        # Detect mid-sentence
        is_mid_sentence = cls.detect_mid_sentence(content)
        if is_mid_sentence:
            issues.append("Content ends mid-sentence")

        # Check for duplicates (if we have requirements)
        has_duplicates = False
        if requirements:
            for req in requirements:
                dups = cls.detect_duplicates(content, req.type)
                if dups:
                    has_duplicates = True
                    issues.append(f"Duplicate {req.type} detected: {dups[:3]}")

        # Determine completion status
        is_complete = requirements_satisfied and not is_truncated and not is_mid_sentence and not has_duplicates

        # Determine partial status
        partial_status = None
        if not is_complete:
            if is_truncated and continuation_count >= max_continuations:
                partial_status = "truncated"
            elif is_mid_sentence:
                partial_status = "incomplete"
            elif not requirements_satisfied:
                partial_status = "partial"
            else:
                partial_status = "incomplete"

        return CompletenessResult(
            is_complete=is_complete,
            requirements_satisfied=requirements_satisfied,
            is_truncated=is_truncated,
            is_mid_sentence=is_mid_sentence,
            has_duplicates=has_duplicates,
            issues=issues,
            partial_status=partial_status,
            required_count=required_count,
            found_count=found_count,
        )

    @classmethod
    def get_continuation_hint(cls, message: str, content: str) -> str | None:
        """
        Generate a hint for continuation if response appears incomplete.

        Returns a continuation instruction string or None if not needed.
        """
        result = cls.validate(message, content)

        if result.is_complete:
            return None

        requirements = cls.extract_requirements(message)

        if not requirements:
            return None

        hints = []
        for req in requirements:
            found = cls.count_structures(content, req.type)
            if req.count and found < req.count:
                remaining = req.count - found
                hints.append(f"Continue until you have completed {remaining} more {req.type}")

        if result.is_mid_sentence:
            hints.append("Complete the current sentence before adding more content")

        if result.has_duplicates:
            hints.append("Do not repeat sections that already exist")

        if hints:
            return " ".join(hints)

        return None