"""LangGraph Bolt agent - main implementation.

This module provides the LangGraph Bolt agent that orchestrates
the coding workflow using the approved Phase 1 design.

Architecture:
  LangGraph Bolt Agent
    ↓
  Graph (StateGraph with nodes)
    ↓
  Nodes (analyze, plan, execute, verify, repair, complete)
    ↓
  Tool Adapters (thin wrappers around CEASER capabilities)
    ↓
  Existing CEASER Execution (device/cloud)
"""
from __future__ import annotations

import time
from typing import Any

from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from app.agents.bolt.langgraph.bolt_state import BoltAgentState
from app.agents.bolt.langgraph.bolt_nodes import (
    BoltNodeExecutor,
    AnalyzeNode,
    PlanNode,
    ExecuteNode,
    VerifyNode,
    RepairNode,
    CompleteNode,
    FailedNode,
)


class BoltAgent:
    """LangGraph-based Bolt agent for software engineering tasks.

    Uses official LangGraph API to create a coding workflow that:
    1. Analyzes user request and project context
    2. Generates a BoltCodingPlan via LLM
    3. Executes tool calls (file operations, commands)
    4. Verifies build and test results
    5. Handles failures with bounded repair attempts
    6. Produces final response

    The agent reuses existing CEASER capability infrastructure
    for actual file/terminal/git operations.
    """

    def __init__(
        self,
        db: Session,
        user_id: str,
        project_id: str | None = None,
        llm: BaseChatModel | None = None,
        max_repair_attempts: int = 3,
        initial_context: dict[str, Any] | None = None,
    ):
        """Initialize the Bolt agent.

        Args:
            db: SQLAlchemy database session
            user_id: Current user ID for capability execution
            project_id: Optional project ID for project-scoped operations
            llm: Optional LangChain-compatible LLM.
                 If None, uses CEASER's ModelRouter via adapter.
            max_repair_attempts: Maximum repair retry attempts (default 3)
            initial_context: Optional project context from CEASER services
        """
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        self.max_repair_attempts = max_repair_attempts
        self.initial_context = initial_context or {}

        # Create node executor (handles LLM and context)
        self.executor = BoltNodeExecutor(
            db=db,
            user_id=user_id,
            project_id=project_id,
            llm=llm,
            max_repair_attempts=max_repair_attempts,
        )

        # Build the graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph Bolt workflow.

        Graph structure:
          START
            ↓
          analyze → (plan → execute → verify) → complete
                             ↓ (failure)
                           repair → execute → verify
                                          ↓
                                        complete/failed

        Returns:
            Compiled StateGraph
        """
        graph = StateGraph(BoltAgentState)

        # Create node instances
        analyze_node = AnalyzeNode(self.executor)
        plan_node = PlanNode(self.executor)
        execute_node = ExecuteNode(self.executor)
        verify_node = VerifyNode(self.executor)
        repair_node = RepairNode(self.executor)
        complete_node = CompleteNode(self.executor)
        failed_node = FailedNode(self.executor)

        # Define nodes
        graph.add_node("analyze", analyze_node)
        graph.add_node("plan", plan_node)
        graph.add_node("execute", execute_node)
        graph.add_node("verify", verify_node)
        graph.add_node("repair", repair_node)
        graph.add_node("complete", complete_node)
        graph.add_node("failed", failed_node)

        # Define conditional edges for flow control
        graph.add_conditional_edges(
            "analyze",
            self._should_plan,
            {
                "plan": "plan",
                "execute": "execute",
            },
        )

        graph.add_edge("plan", "execute")

        graph.add_conditional_edges(
            "execute",
            self._should_verify,
            {
                "verify": "verify",
                "repair": "repair",
            },
        )

        graph.add_conditional_edges(
            "verify",
            self._should_complete,
            {
                "complete": "complete",
                "repair": "repair",
            },
        )

        graph.add_edge("repair", "execute")

        graph.add_edge("complete", END)
        graph.add_edge("failed", END)

        # Set entry point
        graph.set_entry_point("analyze")

        return graph

    def _should_plan(self, state: BoltAgentState) -> str:
        """Determine if plan node should run after analyze."""
        # If direct execute was selected in analyze node
        if state.get("current_step") == "execute":
            return "execute"
        return "plan"

    def _should_verify(self, state: BoltAgentState) -> str:
        """Determine if verify should run after execute."""
        # Always go to verify after execute
        return "verify"

    def _should_complete(self, state: BoltAgentState) -> str:
        """Determine if complete or repair after verify."""
        build_ok = state.get("build_status") == "passed"
        test_ok = state.get("test_status") in ("passed", None)

        if build_ok and test_ok:
            return "complete"

        # Check if we can retry
        retry_count = state.get("retry_count", 0)
        if retry_count < state.get("max_repair_attempts", self.max_repair_attempts):
            return "repair"

        # Max retries reached - fail
        return "repair"  # Will trigger failed node after max retries

    def invoke(self, prompt: str, project_context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run the Bolt agent on a user prompt.

        Args:
            prompt: User request
            project_context: Optional project context from CEASER

        Returns:
            Final state with results
        """
        initial_state: BoltAgentState = {
            "user_id": self.user_id,
            "task_id": f"bolt_{int(time.time())}",
            "prompt": prompt,
            "project_context": project_context or self.initial_context,
            "step_index": 0,
            "current_step": "analyze",
            "status_message": "Starting",
            "plan_summary": None,
            "file_operations": [],
            "setup_commands": [],
            "build_commands": [],
            "test_commands": [],
            "tool_calls": [],
            "tool_results": [],
            "current_file_index": 0,
            "build_status": None,
            "test_status": None,
            "git_revision": None,
            "retry_count": 0,
            "max_repair_attempts": self.max_repair_attempts,
            "repair_history": [],
            "error": None,
            "start_time": time.time(),
            "end_time": None,
            "final_response": "",
        }

        # Compile and run the graph
        compiled_graph = self.graph.compile()
        final_state = compiled_graph.invoke(initial_state)

        return final_state


def create_bolt_agent(
    db: Session,
    user_id: str,
    project_id: str | None = None,
    llm: BaseChatModel | None = None,
    max_repair_attempts: int = 3,
) -> BoltAgent:
    """Factory function to create a Bolt agent.

    Args:
        db: SQLAlchemy database session
        user_id: Current user ID
        project_id: Optional project ID
        llm: Optional LangChain LLM
        max_repair_attempts: Maximum repair retries

    Returns:
        Configured BoltAgent
    """
    return BoltAgent(
        db=db,
        user_id=user_id,
        project_id=project_id,
        llm=llm,
        max_repair_attempts=max_repair_attempts,
    )
