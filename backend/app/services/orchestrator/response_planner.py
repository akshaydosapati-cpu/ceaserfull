"""Conversation-aware response planning for CEASER.

This module provides a general, domain-agnostic mechanism to understand user
intent relative to previous conversation state and determine the appropriate
response operation (EXPLAIN, MODIFY, CONTINUE, TRANSFORM, etc.) instead of
blindly regenerating the same format.

The planner resolves references (pronouns, previous artifacts), determines
operation type, and selects appropriate output mode based on conversation context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal


class OperationType(str, Enum):
    """Types of response operations based on user intent."""
    CREATE = "CREATE"  # New artifact/response from scratch
    EXPLAIN = "EXPLAIN"  # Explain existing artifact step-by-step
    MODIFY = "MODIFY"  # Change specific part of artifact
    CORRECT = "CORRECT"  # Fix error or issue in artifact
    TRANSFORM = "TRANSFORM"  # Convert to different format/language
    CONTINUE = "CONTINUE"  # Extend or continue where it left off
    SUMMARIZE = "SUMMARIZE"  # Condense or abstract existing content
    CLARIFY = "CLARIFY"  # Request clarification instead of guessing
    VERIFY = "VERIFY"  # Check correctness or validity


@dataclass
class ResponsePlan:
    """Lightweight representation of planned response."""
    operation: OperationType
    reference: str | None  # What is being referenced ("it", "that code", etc)
    target_artifact_id: str | None  # ID of artifact being referenced
    preserve_format: bool  # Whether to keep same format/structure
    output_mode: str  # "code", "explanation", "markdown", "plain", etc
    change_type: str | None  # "addition", "subtraction", "conversion", etc
    constraints: dict[str, Any]  # Domain-specific constraints
    confidence: float  # 0.0-1.0 how confident in this plan
    allow_artifact_generation: bool = True  # Whether agents should generate/modify artifacts


class ResponsePlanner:
    """Plans conversation-aware responses without LLM calls."""

    # Patterns for reference resolution
    PRONOUN_PATTERN = re.compile(r"\b(it|this|that|these|those|the|this one)\b", re.I)
    REFERENCE_WORDS = {
        "explain", "show", "describe", "walk through", "step", "break down",
        "how", "why", "what does", "understand", "learn", "teach"
    }
    MODIFICATION_WORDS = {
        "change", "fix", "update", "modify", "adjust", "edit", "remove", "add",
        "replace", "swap", "convert", "rewrite", "shorten", "expand", "simplify",
        "make", "improve", "enhance"
    }
    CONTINUATION_WORDS = {
        "continue", "next", "then", "after", "more", "further", "also",
        "additionally", "extend", "keep going", "don't stop"
    }
    CLARIFICATION_WORDS = {
        "what do you mean", "clarify", "explain that", "i don't understand",
        "unclear", "confused", "lost", "what is", "which one"
    }

    def plan(
        self,
        current_message: str,
        conversation_context: dict[str, Any] | None = None,
        previous_artifacts: list[dict[str, Any]] | None = None,
        follow_up_trace: dict[str, Any] | None = None,
    ) -> ResponsePlan | None:
        """Plan the response based on conversation context.

        Args:
            current_message: User's current message
            conversation_context: Previous messages and conversation state
            previous_artifacts: List of artifacts from this conversation
            follow_up_trace: Follow-up intent resolution from orchestrator

        Returns:
            ResponsePlan if a follow-up pattern is detected, None for new request
        """
        # Empty or new conversation - no planning needed
        if not previous_artifacts:
            return None

        follow_up_detected = (follow_up_trace or {}).get("follow_up_detected", False)
        if not follow_up_detected and not self._is_reference_to_previous(current_message):
            return None

        # Determine operation type from message patterns
        operation = self._classify_operation(current_message, previous_artifacts)
        if operation is OperationType.CLARIFY:
            # Don't regenerate; ask for clarification instead
            return ResponsePlan(
                operation=operation,
                reference=None,
                target_artifact_id=None,
                preserve_format=False,
                output_mode="clarification",
                change_type=None,
                constraints={},
                confidence=0.9,
                allow_artifact_generation=False,
            )

        # Resolve what artifact/content is being referenced
        reference, target_id = self._resolve_reference(
            current_message,
            previous_artifacts,
            conversation_context or {},
        )

        if target_id is None:
            # Ambiguous reference; ask for clarification
            return ResponsePlan(
                operation=OperationType.CLARIFY,
                reference=reference,
                target_artifact_id=None,
                preserve_format=False,
                output_mode="clarification",
                change_type=None,
                constraints={"reason": "ambiguous_reference"},
                confidence=0.6,
            )

        # Determine output mode based on operation and target
        output_mode = self._determine_output_mode(operation, previous_artifacts, target_id)

        # Extract constraints/changes from message
        change_type = self._extract_change_type(current_message, operation)
        constraints = self._extract_constraints(current_message, operation)

        preserve_format = operation not in {
            OperationType.TRANSFORM,
            OperationType.SUMMARIZE,
            OperationType.CLARIFY,
        }

        # Non-generative operations should not produce artifacts
        allow_artifact_generation = operation not in {
            OperationType.EXPLAIN,
            OperationType.SUMMARIZE,
            OperationType.CLARIFY,
            OperationType.VERIFY,
        }

        return ResponsePlan(
            operation=operation,
            reference=reference,
            target_artifact_id=target_id,
            preserve_format=preserve_format,
            output_mode=output_mode,
            change_type=change_type,
            constraints=constraints,
            confidence=0.85,
            allow_artifact_generation=allow_artifact_generation,
        )

    def _is_reference_to_previous(self, message: str) -> bool:
        """Check if message contains references to previous content."""
        lower = message.lower()

        # Check for pronouns or reference words
        has_pronoun = bool(self.PRONOUN_PATTERN.search(message))
        has_reference_word = any(word in lower for word in self.REFERENCE_WORDS)
        has_modification_word = any(word in lower for word in self.MODIFICATION_WORDS)
        has_continuation_word = any(word in lower for word in self.CONTINUATION_WORDS)
        has_clarification_word = any(word in lower for word in self.CLARIFICATION_WORDS)

        return bool(
            has_pronoun
            and (
                has_reference_word
                or has_modification_word
                or has_continuation_word
                or has_clarification_word
            )
        )

    def _classify_operation(
        self,
        message: str,
        previous_artifacts: list[dict[str, Any]],
    ) -> OperationType:
        """Classify the type of operation requested."""
        lower = message.lower()

        # Check for clarification requests first
        if any(word in lower for word in self.CLARIFICATION_WORDS):
            return OperationType.CLARIFY

        # Check for explanation requests
        if any(word in lower for word in self.REFERENCE_WORDS):
            return OperationType.EXPLAIN

        # Check for modification requests
        if any(word in lower for word in self.MODIFICATION_WORDS):
            # Distinguish between types of modifications
            # Check for CORRECT (fix/bug/error) but exclude "also add" which should be MODIFY
            if (
                any(verb in lower for verb in {"fix", "bug", "error", "wrong"})
                and "also add" not in lower
                and "add more" not in lower
            ):
                return OperationType.CORRECT
            if any(verb in lower for verb in {"convert", "change to", "rewrite in", "as"}):
                return OperationType.TRANSFORM
            return OperationType.MODIFY

        # Check for continuation
        if any(word in lower for word in self.CONTINUATION_WORDS):
            return OperationType.CONTINUE

        # Check for summarization
        if any(word in lower for word in {"summarize", "summary", "tldr", "brief", "short"}):
            return OperationType.SUMMARIZE

        # Default: treat as modification if there's a change indicator
        if self._has_specific_change_indicator(message):
            return OperationType.MODIFY

        return OperationType.CREATE

    def _has_specific_change_indicator(self, message: str) -> bool:
        """Check if message indicates a specific change or addition."""
        lower = message.lower()
        return any(
            pattern in lower
            for pattern in {
                "also add", "add more", "and add", "include", "also include",
                "remove", "delete", "take out", "without the", "skip the",
                "second", "first", "last", "function", "line", "part",
            }
        )

    def _resolve_reference(
        self,
        message: str,
        previous_artifacts: list[dict[str, Any]],
        conversation_context: dict[str, Any],
    ) -> tuple[str | None, str | None]:
        """Resolve what is being referenced.

        Returns:
            (reference_text, artifact_id) tuple
        """
        if not previous_artifacts:
            return None, None

        # Most recent artifact is typically the reference
        if len(previous_artifacts) == 1:
            artifact = previous_artifacts[0]
            return artifact.get("type", "content"), artifact.get("id")

        # Multiple artifacts: try to disambiguate
        # Look for content-type hints in the message
        lower = message.lower()

        # Check for explicit type references
        type_hints = {
            "code": {"code", "function", "script", "html", "javascript", "python", "js"},
            "document": {"document", "text", "writing", "draft", "content"},
            "plan": {"plan", "outline", "schedule", "timeline"},
            "image": {"image", "picture", "visual", "graphic"},
        }

        for hint_type, keywords in type_hints.items():
            if any(kw in lower for kw in keywords):
                # Find matching artifact
                for artifact in previous_artifacts:
                    if artifact.get("type") == hint_type:
                        return hint_type, artifact.get("id")

        # No clear type hint; return the most recent
        artifact = previous_artifacts[-1]
        return artifact.get("type", "content"), artifact.get("id")

    def _determine_output_mode(
        self,
        operation: OperationType,
        previous_artifacts: list[dict[str, Any]],
        target_id: str | None,
    ) -> str:
        """Determine the output mode based on operation and target."""
        if operation == OperationType.CLARIFY:
            return "clarification"
        if operation == OperationType.EXPLAIN:
            return "explanation"
        if operation == OperationType.SUMMARIZE:
            return "summary"

        # For modifications and transformations, preserve format unless
        # the operation explicitly changes it
        if operation == OperationType.TRANSFORM:
            return "transformed"

        # Find target artifact to get its format
        if target_id and previous_artifacts:
            for artifact in previous_artifacts:
                if artifact.get("id") == target_id:
                    original_format = artifact.get("format", "markdown")
                    if operation == OperationType.CONTINUE:
                        return original_format
                    return original_format

        return "markdown"

    def _extract_change_type(
        self,
        message: str,
        operation: OperationType,
    ) -> str | None:
        """Extract what type of change is being requested."""
        lower = message.lower()

        if operation == OperationType.MODIFY:
            if any(w in lower for w in {"add", "also add", "include"}):
                return "addition"
            if any(w in lower for w in {"remove", "delete", "without"}):
                return "subtraction"
            if any(w in lower for w in {"change", "fix", "update"}):
                return "replacement"

        if operation == OperationType.TRANSFORM:
            if "python" in lower:
                return "to_python"
            if "javascript" in lower or "js" in lower:
                return "to_javascript"
            if "java" in lower:
                return "to_java"
            if "go" in lower or "golang" in lower:
                return "to_go"
            if "rust" in lower:
                return "to_rust"
            return "format_change"

        return None

    def _extract_constraints(
        self,
        message: str,
        operation: OperationType,
    ) -> dict[str, Any]:
        """Extract constraints or requirements from the message."""
        constraints: dict[str, Any] = {}
        lower = message.lower()

        # Length constraints
        if any(w in lower for w in {"short", "brief", "concise", "minimal"}):
            constraints["length"] = "short"
        elif any(w in lower for w in {"long", "detailed", "thorough", "comprehensive"}):
            constraints["length"] = "long"

        # Style constraints
        if any(w in lower for w in {"simple", "beginner", "easy"}):
            constraints["complexity"] = "simple"
        elif any(w in lower for w in {"advanced", "complex", "expert"}):
            constraints["complexity"] = "advanced"

        # Format/style hints
        if "every step" in lower or "step by step" in lower:
            constraints["verbosity"] = "detailed"
        if "tldr" in lower:
            constraints["verbosity"] = "minimal"

        return constraints


# Global instance for use across the service layer
response_planner = ResponsePlanner()
