"""State services for CEASER conversation/task state management.

This package provides generic state management infrastructure for CEASER.
All components are task-agnostic and work with the generic state schema.
"""

from app.schemas.task_state import (
    StateSource,
    StateStatus,
    TaskStateSchema,
    create_constraint,
    create_fact,
    create_assumption,
    create_decision,
    create_calculation,
    create_goal,
    create_entity,
)

from app.services.state.state_merger import merge_state, apply_state_change

__all__ = [
    # Schema
    "StateSource",
    "StateStatus",
    "TaskStateSchema",
    "create_constraint",
    "create_fact",
    "create_assumption",
    "create_decision",
    "create_calculation",
    "create_goal",
    "create_entity",
    # Merger
    "merge_state",
    "apply_state_change",
]