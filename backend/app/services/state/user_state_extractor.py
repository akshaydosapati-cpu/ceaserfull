"""Conservative deterministic extraction of explicit user-provided state.

This module extracts ONLY clearly explicit information the USER has stated.
It does NOT parse assistant responses.
It does NOT use LLM calls.
It does NOT make network requests.
It does NOT attempt semantic understanding.

SAFETY RULES:
- Only user messages are processed.
- All extracted items have source=USER.
- Uncertain/hedged language reduces to PROVISIONAL status or ASSUMPTION.
- Assistant-generated assumptions are NEVER extracted here.
- Corrections supersede prior values (via apply_state_change "update").
"""

from __future__ import annotations

import re

from app.schemas.task_state import (
    StateSource,
    StateStatus,
    TaskStateSchema,
    create_constraint,
    create_entity,
    create_fact,
)
from app.services.state.state_merger import apply_state_change, merge_state


# ---------------------------------------------------------------------------
# Patterns for explicit numeric/budget constraints
# ---------------------------------------------------------------------------

# Budget/investment/capital patterns (INR focused but generic)
_BUDGET_PATTERNS = [
    # "my budget is X lakhs / crores / k / thousand"
    re.compile(
        r"\b(?:my |the |our )?"
        r"(?:budget|investment|capital|funding|cost|spend|spending|expense|limit|cap)\b"
        r".*?\b([\d,.]+)\s*"
        r"(?:lakh|lakhs|crore|crores|k|thousand|million|cr|L)\b",
        re.IGNORECASE,
    ),
    # "₹ X lakh" or "Rs X lakh" or "INR X lakh"
    re.compile(
        r"(?:₹|rs\.?|inr|rupees?)\s*([\d,.]+)\s*"
        r"(?:lakh|lakhs|crore|crores|k|thousand|million)?\b",
        re.IGNORECASE,
    ),
    # "$X" or "X dollars"
    re.compile(
        r"\$\s*([\d,.]+)\s*(?:million|k|thousand)?\b",
        re.IGNORECASE,
    ),
]

# Location/place patterns
_LOCATION_PATTERNS = [
    re.compile(
        r"\b(?:in|at|from|near|around|based in|located in|starting in|open in)\s+"
        r"([A-Z][a-zA-Z\s]{2,30})(?:\s*[,.]|\s*$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:my|our)\s+(?:town|city|location|area|place|region)\s+(?:is|will be|would be)\s+"
        r"([A-Z][a-zA-Z\s]{2,30})(?:\s*[,.]|\s*$)",
        re.IGNORECASE,
    ),
]

# Explicit correction markers
_CORRECTION_MARKERS = re.compile(
    r"\b(actually|wait|no[,.]|correction|update|change it to|changed to|"
    r"not .+ but|scratch that|instead it|revised|revised to)\b",
    re.IGNORECASE,
)

# Uncertainty markers (these make something an assumption, not a user fact)
_UNCERTAINTY_MARKERS = re.compile(
    r"\b(i think|maybe|perhaps|probably|approximately|roughly|around|"
    r"could be|might be|i guess|i assume|possibly|not sure|unsure|"
    r"estimate|roughly|about|more or less)\b",
    re.IGNORECASE,
)


def extract_user_state(message: str, previous_state: dict) -> dict:
    """Extract explicit user-provided state from a user message.

    Returns updated state dict. Does NOT call LLM or any network service.

    Args:
        message: The user's message text.
        previous_state: The current conversation state.

    Returns:
        Updated state with any new/corrected user-provided entries.
    """
    state = dict(previous_state)

    # Detect correction intent
    is_correction = bool(_CORRECTION_MARKERS.search(message))

    # Extract budget/investment constraints
    state = _extract_budget(message, state, is_correction)

    # Extract location entities
    state = _extract_location(message, state, is_correction)

    return state


def _is_uncertain(text: str) -> bool:
    """Return True if message text contains uncertainty markers."""
    return bool(_UNCERTAINTY_MARKERS.search(text))


def _extract_budget(message: str, state: dict, is_correction: bool) -> dict:
    """Extract explicit budget/investment constraints from user message."""
    for pattern in _BUDGET_PATTERNS:
        match = pattern.search(message)
        if not match:
            continue

        raw_value = match.group(0).strip()

        # Don't extract uncertain budget estimates
        # Check context around the match for uncertainty markers
        if _is_uncertain(message[:match.start() + 30]):
            continue

        # Look for existing budget constraint in state
        existing = _find_existing_constraint(state, "budget")

        if existing and is_correction:
            # User is correcting a previous budget
            corrected = create_constraint(
                description=f"Budget: {raw_value}",
                source=StateSource.USER,
                category="budget",
                status=StateStatus.ACTIVE,
                provenance=["user_message"],
            )
            corrected["id"] = existing["id"]
            state = apply_state_change(state, "update", "constraints", corrected)
        elif not existing:
            # New budget constraint
            state = apply_state_change(
                state,
                "add",
                "constraints",
                create_constraint(
                    description=f"Budget: {raw_value}",
                    source=StateSource.USER,
                    category="budget",
                    status=StateStatus.ACTIVE,
                    provenance=["user_message"],
                ),
            )
        # If budget exists and no correction marker, keep existing (user just repeated it)

    return state


def _extract_location(message: str, state: dict, is_correction: bool) -> dict:
    """Extract explicit location/place from user message."""
    for pattern in _LOCATION_PATTERNS:
        match = pattern.search(message)
        if not match:
            continue

        location = match.group(1).strip().rstrip(".,")
        if not location or len(location) < 2:
            continue

        # Avoid generic words that aren't real places
        _generic = {"home", "here", "there", "anywhere", "somewhere", "mine", "my"}
        if location.lower() in _generic:
            continue

        existing = _find_existing_entity(state, "location")

        if existing and is_correction:
            corrected = create_entity(
                entity_type="location",
                name=location,
                provenance=["user_message"],
            )
            corrected["id"] = existing["id"]
            state = apply_state_change(state, "update", "entities", corrected)
        elif not existing:
            state = apply_state_change(
                state,
                "add",
                "entities",
                create_entity(
                    entity_type="location",
                    name=location,
                    provenance=["user_message"],
                ),
            )

    return state


def _find_existing_constraint(state: dict, category: str) -> dict | None:
    """Find the first active constraint with the given category."""
    constraints = state.get("constraints") or []
    for c in constraints:
        if (
            isinstance(c, dict)
            and c.get("category") == category
            and c.get("status") != StateStatus.DEPRECATED.value
        ):
            return c
    return None


def _find_existing_entity(state: dict, entity_type: str) -> dict | None:
    """Find the first entity with the given type."""
    entities = state.get("entities") or []
    for e in entities:
        if isinstance(e, dict) and e.get("type") == entity_type:
            return e
    return None
