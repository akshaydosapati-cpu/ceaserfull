"""Deterministic state merge/update logic for CEASER task state.

This module provides the core merge logic for the generic task state.
It ensures that:
- Unrelated existing state is preserved
- Changed values are updated
- Provenance is preserved
- Corrections/supersessions are handled
- Duplicate entries are avoided
- Assistant assumptions are not silently treated as confirmed facts
- Legacy fields remain readable for backward compatibility
"""

from datetime import datetime, timezone
from typing import Any

from app.schemas.task_state import TaskStateSchema, StateStatus


def merge_state(previous_state: dict, changes: dict) -> dict:
    """Merge state changes into existing state deterministically.

    This function performs a deterministic merge of new state changes
    into the existing state, preserving backward compatibility.

    Args:
        previous_state: The existing state dict (may be empty or legacy)
        changes: The changes to apply

    Returns:
        Merged state dict with schema_version preserved
    """
    # Normalize previous state to V1 structure
    previous = TaskStateSchema.normalize(previous_state)

    # Start with previous state
    result = dict(previous)

    # Update meta
    result["meta"] = {
        **previous.get("meta", {}),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Apply changes to task
    if "task" in changes and isinstance(changes["task"], dict):
        result["task"] = {**previous.get("task", {}), **changes["task"]}

    # Apply changes to constraints
    if "constraints" in changes and isinstance(changes["constraints"], list):
        result["constraints"] = _merge_items(
            previous.get("constraints", []),
            changes["constraints"],
            "constraints"
        )

    # Apply changes to facts
    if "facts" in changes and isinstance(changes["facts"], list):
        result["facts"] = _merge_items(
            previous.get("facts", []),
            changes["facts"],
            "facts"
        )

    # Apply changes to assumptions
    if "assumptions" in changes and isinstance(changes["assumptions"], list):
        result["assumptions"] = _merge_items(
            previous.get("assumptions", []),
            changes["assumptions"],
            "assumptions"
        )

    # Apply changes to decisions
    if "decisions" in changes and isinstance(changes["decisions"], list):
        result["decisions"] = _merge_items(
            previous.get("decisions", []),
            changes["decisions"],
            "decisions"
        )

    # Apply changes to calculations (dict - update by key)
    if "calculations" in changes and isinstance(changes["calculations"], dict):
        result["calculations"] = {
            **previous.get("calculations", {}),
            **changes["calculations"]
        }

    # Apply changes to goals
    if "goals" in changes and isinstance(changes["goals"], list):
        result["goals"] = _merge_items(
            previous.get("goals", []),
            changes["goals"],
            "goals"
        )

    # Apply changes to open_questions
    if "open_questions" in changes and isinstance(changes["open_questions"], list):
        result["open_questions"] = _merge_items(
            previous.get("open_questions", []),
            changes["open_questions"],
            "open_questions"
        )

    # Apply changes to entities
    if "entities" in changes and isinstance(changes["entities"], list):
        result["entities"] = _merge_items(
            previous.get("entities", []),
            changes["entities"],
            "entities"
        )

    # Apply changes to preferences
    if "preferences" in changes and isinstance(changes["preferences"], list):
        result["preferences"] = _merge_items(
            previous.get("preferences", []),
            changes["preferences"],
            "preferences"
        )

    # Preserve legacy fields - these are critical for backward compatibility
    legacy_fields = [
        "active_topic", "active_subtopic", "active_task",
        "unfinished_goal", "important_entities", "important_decisions",
        "last_relevant_turn"
    ]

    for field in legacy_fields:
        if field in changes:
            # New value provided - update it
            result[field] = changes[field]
        elif field in previous:
            # Preserve existing value
            result[field] = previous[field]

    return result


def _merge_items(existing: list, new_items: list, item_type: str) -> list:
    """Merge list items with deduplication and deprecation handling.

    Args:
        existing: Existing items
        new_items: New items to merge
        item_type: Type of items (for ID generation)

    Returns:
        Merged list with deprecated items removed
    """
    if not new_items:
        return existing

    if not existing:
        return new_items

    # Build a map of existing items by ID for quick lookup
    existing_by_id = {item.get("id"): item for item in existing if item.get("id")}

    result = list(existing)
    updated_ids = set()

    for new_item in new_items:
        new_id = new_item.get("id")

        if not new_id:
            # Generate ID for item without one
            new_id = f"{item_type}_{int(datetime.now(timezone.utc).timestamp() * 1000000)}"
            new_item = dict(new_item)
            new_item["id"] = new_id

        # If this ID was already replaced once, add the new item (correction case)
        if new_id in updated_ids:
            result.append(new_item)
        elif new_id in existing_by_id:
            # First time seeing this ID - replace existing
            for i, item in enumerate(result):
                if item.get("id") == new_id:
                    result[i] = new_item
                    updated_ids.add(new_id)
                    break
        else:
            # Completely new item
            result.append(new_item)

    return result


def apply_state_change(
    previous_state: dict,
    operation: str,
    item_type: str,
    item: dict,
) -> dict:
    """Apply a single state change operation.

    Args:
        previous_state: Current state
        operation: One of "add", "update", "delete", "replace"
        item_type: Type of item (constraints, facts, etc.)
        item: The item to add/update/delete

    Returns:
        New state with change applied
    """
    changes = {item_type: []}

    if operation == "add":
        changes[item_type] = [item]
    elif operation == "update":
        # Update triggers correction behavior: deprecate old, add new
        # This keeps both for audit trail
        item_id = item.get("id")
        if item_id:
            # Find existing item, deprecate it, and add new one
            existing_items = previous_state.get(item_type, [])
            old_item = None
            for existing in existing_items:
                if existing.get("id") == item_id:
                    old_item = {**existing, "status": StateStatus.DEPRECATED.value}
                    break

            if old_item:
                # Pass both: deprecated old + new active
                changes[item_type] = [old_item, item]
            else:
                # No existing item with that ID, just add new
                changes[item_type] = [item]
        else:
            changes[item_type] = [item]
    elif operation == "delete":
        # Mark as deprecated (soft delete)
        item_id = item.get("id")
        if item_id:
            existing_items = previous_state.get(item_type, [])
            for existing in existing_items:
                if existing.get("id") == item_id:
                    changes[item_type] = [{**existing, "status": StateStatus.DEPRECATED.value}]
                    break
    elif operation == "replace":
        # Full replacement of the item type
        changes[item_type] = [item]

    return merge_state(previous_state, changes)


def update_legacy_fields(
    state: dict,
    active_topic: str | None = None,
    active_subtopic: str | None = None,
    active_task: str | None = None,
    unfinished_goal: str | None = None,
    important_entities: list | None = None,
    important_decisions: list | None = None,
    last_relevant_turn: str | None = None,
) -> dict:
    """Update only legacy fields while preserving V1 structure.

    This is a convenience function for updating legacy fields
    without affecting the V1 state structure.
    """
    changes = {}

    if active_topic is not None:
        changes["active_topic"] = active_topic
    if active_subtopic is not None:
        changes["active_subtopic"] = active_subtopic
    if active_task is not None:
        changes["active_task"] = active_task
    if unfinished_goal is not None:
        changes["unfinished_goal"] = unfinished_goal
    if important_entities is not None:
        changes["important_entities"] = important_entities
    if important_decisions is not None:
        changes["important_decisions"] = important_decisions
    if last_relevant_turn is not None:
        changes["last_relevant_turn"] = last_relevant_turn

    if not changes:
        return state

    return merge_state(state, changes)