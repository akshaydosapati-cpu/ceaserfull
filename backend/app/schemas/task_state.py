"""Generic conversation/task state schema for CEASER.

This module defines a task-agnostic state structure that can represent
business planning, coding, research, study, writing, travel, and other
multi-turn tasks through the same generic concepts.

IMPORTANT: This is a generic schema. Do NOT add feature-specific fields
like 'financial_planning', 'coding_task', etc. Use the generic structures
(constraints, facts, assumptions, decisions, etc.) for all domains.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal


def _utc_now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


class StateSource(str, Enum):
    """Source of a state entry."""
    USER = "user"  # User-provided information
    ASSISTANT = "assistant"  # Model-generated assumption/suggestion
    DOCUMENT = "document"  # Extracted from uploaded document
    TOOL = "tool"  # From tool execution (web search, API, etc.)
    SYSTEM = "system"  # System-generated (title generation, etc.)
    DERIVED = "derived"  # Calculated from other state


class StateStatus(str, Enum):
    """Status of a state entry."""
    ACTIVE = "active"  # Currently valid
    DEPRECATED = "deprecated"  # Superseded by newer entry
    PROVISIONAL = "provisional"  # Tentative, needs confirmation


class TaskStateSchema:
    """Validation and utilities for task state V1."""

    VERSION = 1

    @staticmethod
    def empty() -> dict:
        """Return an empty valid V1 state."""
        return {
            "schema_version": TaskStateSchema.VERSION,
            "task": {},
            "constraints": [],
            "facts": [],
            "assumptions": [],
            "decisions": [],
            "calculations": {},
            "goals": [],
            "open_questions": [],
            "entities": [],
            "preferences": [],
            "meta": {
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
            },
            # Legacy fields preserved for backward compatibility
            "active_topic": None,
            "active_subtopic": None,
            "active_task": None,
            "unfinished_goal": None,
            "important_entities": [],
            "important_decisions": [],
            "last_relevant_turn": None,
        }

    @staticmethod
    def validate(state: dict) -> tuple[bool, list[str]]:
        """Validate state against V1 schema.

        Returns:
            (is_valid, errors)
        """
        errors = []

        if not isinstance(state, dict):
            return False, ["State must be a dictionary"]

        # Empty state is valid (backward compat)
        if not state:
            return True, []

        # If schema_version exists, validate it
        if "schema_version" in state:
            version = state.get("schema_version")
            if not isinstance(version, int):
                errors.append("schema_version must be an integer")
            elif version != TaskStateSchema.VERSION:
                errors.append(f"Unsupported schema_version: {version}")

        # Validate top-level structure if present
        if "constraints" in state and not isinstance(state["constraints"], list):
            errors.append("constraints must be a list")

        if "facts" in state and not isinstance(state["facts"], list):
            errors.append("facts must be a list")

        if "assumptions" in state and not isinstance(state["assumptions"], list):
            errors.append("assumptions must be a list")

        if "decisions" in state and not isinstance(state["decisions"], list):
            errors.append("decisions must be a list")

        if "calculations" in state and not isinstance(state["calculations"], dict):
            errors.append("calculations must be a dictionary")

        if "goals" in state and not isinstance(state["goals"], list):
            errors.append("goals must be a list")

        if "open_questions" in state and not isinstance(state["open_questions"], list):
            errors.append("open_questions must be a list")

        if "entities" in state and not isinstance(state["entities"], list):
            errors.append("entities must be a list")

        if "preferences" in state and not isinstance(state["preferences"], list):
            errors.append("preferences must be a list")

        if "task" in state and not isinstance(state["task"], dict):
            errors.append("task must be a dictionary")

        if "meta" in state and not isinstance(state["meta"], dict):
            errors.append("meta must be a dictionary")

        return len(errors) == 0, errors

    @staticmethod
    def is_legacy_only(state: dict) -> bool:
        """Check if state contains only legacy fields (no V1 structure)."""
        if not state:
            return True

        v1_fields = {
            "schema_version", "task", "constraints", "facts",
            "assumptions", "decisions", "calculations", "goals",
            "open_questions", "entities", "preferences", "meta"
        }

        return not any(field in state for field in v1_fields)

    @staticmethod
    def normalize(state: dict) -> dict:
        """Normalize state to V1 structure while preserving legacy fields.

        If state is empty or legacy-only, initializes V1 structure.
        If state already has V1 structure, returns as-is.
        """
        if not state:
            return TaskStateSchema.empty()

        # Already V1
        if "schema_version" in state:
            return state

        # Legacy only - initialize V1 structure while preserving legacy
        normalized = TaskStateSchema.empty()

        # Preserve all existing legacy fields
        legacy_fields = [
            "active_topic", "active_subtopic", "active_task",
            "unfinished_goal", "important_entities", "important_decisions",
            "last_relevant_turn"
        ]

        for field in legacy_fields:
            if field in state:
                normalized[field] = state[field]

        return normalized


def create_constraint(
    description: str,
    source: StateSource = StateSource.USER,
    category: str = "general",
    status: StateStatus = StateStatus.ACTIVE,
    provenance: list[str] | None = None,
) -> dict:
    """Create a constraint entry."""
    return {
        "id": f"c_{str(hash(__import__("time").time()))[:12]}",
        "category": category,
        "description": description,
        "source": source.value,
        "status": status.value,
        "created_at": _utc_now(),
        "provenance": provenance or [],
    }


def create_fact(
    content: str,
    source: StateSource = StateSource.ASSISTANT,
    status: StateStatus = StateStatus.PROVISIONAL,
    confidence: float = 0.8,
    provenance: list[str] | None = None,
) -> dict:
    """Create a fact entry."""
    return {
        "id": f"f_{str(hash(__import__("time").time()))[:12]}",
        "content": content,
        "source": source.value,
        "status": status.value,
        "confidence": max(0.0, min(1.0, confidence)),
        "created_at": _utc_now(),
        "provenance": provenance or [],
    }


def create_assumption(
    content: str,
    status: StateStatus = StateStatus.ACTIVE,
    risk_level: Literal["low", "medium", "high"] = "medium",
    validation_required: bool = True,
    provenance: list[str] | None = None,
) -> dict:
    """Create an assumption entry."""
    return {
        "id": f"a_{str(hash(__import__("time").time()))[:12]}",
        "content": content,
        "status": status.value,
        "risk_level": risk_level,
        "validation_required": validation_required,
        "created_at": _utc_now(),
        "provenance": provenance or [],
    }


def create_decision(
    content: str,
    rationale: str = "",
    status: StateStatus = StateStatus.ACTIVE,
    constraints_applied: list[str] | None = None,
    provenance: list[str] | None = None,
) -> dict:
    """Create a decision entry."""
    return {
        "id": f"d_{str(hash(__import__("time").time()))[:12]}",
        "content": content,
        "rationale": rationale,
        "status": status.value,
        "constraints_applied": constraints_applied or [],
        "created_at": _utc_now(),
        "provenance": provenance or [],
    }


def create_calculation(
    name: str,
    value: Any,
    expression: str = "",
    source_ids: list[str] | None = None,
    status: StateStatus = StateStatus.ACTIVE,
    provenance: list[str] | None = None,
) -> dict:
    """Create a calculation entry."""
    return {
        "id": f"calc_{str(hash(__import__("time").time()))[:12]}",
        "name": name,
        "value": value,
        "expression": expression,
        "source_ids": source_ids or [],
        "status": status.value,
        "created_at": _utc_now(),
        "provenance": provenance or [],
    }


def create_goal(
    content: str,
    priority: int = 1,
    status: Literal["pending", "in_progress", "completed", "blocked"] = "pending",
    provenance: list[str] | None = None,
) -> dict:
    """Create a goal entry."""
    return {
        "id": f"g_{str(hash(__import__("time").time()))[:12]}",
        "content": content,
        "priority": priority,
        "status": status,
        "created_at": _utc_now(),
        "provenance": provenance or [],
    }


def create_entity(
    entity_type: str,
    name: str,
    attributes: dict | None = None,
    provenance: list[str] | None = None,
) -> dict:
    """Create an entity entry."""
    return {
        "id": f"e_{str(hash(__import__("time").time()))[:12]}",
        "type": entity_type,
        "name": name,
        "attributes": attributes or {},
        "created_at": _utc_now(),
        "provenance": provenance or [],
    }
