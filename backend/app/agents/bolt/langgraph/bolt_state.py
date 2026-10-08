"""LangGraph Bolt state definitions.

This module defines the state structure for the LangGraph Bolt agent.
It carries user goals, conversation context, coding tasks, plans,
tool calls/results, and verification state.
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict

from app.services.sandbox.models import BoltCodingPlan


class BoltAgentState(TypedDict):
    """State for the LangGraph Bolt agent.

    This state carries information through the Bolt workflow:
    - User goal and conversation context
    - Project information
    - Code planning and execution results
    - Verification status
    - Final output

    The state is designed to be minimal and focused on Bolt's specific
    needs, reusing existing CEASER services for data storage where appropriate.
    """

    # Input fields (set at graph start)
    user_id: str
    task_id: str
    prompt: str
    project_context: dict[str, Any]  # From existing CEASER project service

    # Execution tracking
    step_index: int
    current_step: Literal["analyze", "plan", "execute", "verify", "complete", "failed", "repair"]
    status_message: str

    # Planning output
    plan_summary: str | None
    file_operations: list[dict[str, Any]]  # BoltCodingPlan structure
    setup_commands: list[dict[str, Any]]
    build_commands: list[dict[str, Any]]
    test_commands: list[dict[str, Any]]

    # Tool execution state
    tool_calls: list[dict[str, Any]]  # List of tool calls made
    tool_results: list[dict[str, Any]]  # Results from tool calls
    current_file_index: int  # Track progress through file operations

    # Verification output
    build_status: Literal["pending", "passed", "failed"] | None
    test_status: Literal["pending", "passed", "failed"] | None
    git_revision: str | None

    # Repair state
    retry_count: int
    max_repair_attempts: int
    repair_history: list[dict[str, Any]]

    # Error handling
    error: str | None

    # Timing
    start_time: float
    end_time: float | None

    # Final output
    final_response: str
