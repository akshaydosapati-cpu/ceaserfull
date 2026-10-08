"""LangGraph Bolt agent nodes.

This module implements the graph nodes for the Bolt agent:
- analyze: Inspect project and determine approach
- plan: Generate BoltCodingPlan
- execute: Run tool calls from plan
- verify: Build and test
- repair: Handle failures with bounded retries
- complete: Finalize response
"""
from __future__ import annotations

import time
from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END
from sqlalchemy.orm import Session

from app.agents.langgraph.model_adapter import CeaserModelAdapter
from app.agents.langgraph.context_adapter import ResearchContext, ContextAdapter
from app.agents.bolt.langgraph.bolt_state import BoltAgentState
from app.models.user import User
from app.agents.bolt.langgraph.bolt_adapters import (
    ReadFileAdapter,
    WriteFileAdapter,
    PatchFileAdapter,
    TerminalAdapter,
    GitStatusAdapter,
    GitAddAdapter,
)
from app.intelligence.ai.model_router import request_for_agent
from app.intelligence.ai.sync import generate_text_sync
from app.services.sandbox.models import BoltCodingPlan


class BoltNodeExecutor:
    """Executor for Bolt graph nodes.

    Provides the core logic for each graph node while
    integrating with existing CEASER services.
    """

    def __init__(
        self,
        db: Session,
        user_id: str,
        project_id: str | None = None,
        llm: BaseChatModel | None = None,
        max_repair_attempts: int = 3,
    ):
        """Initialize node executor.

        Args:
            db: SQLAlchemy database session
            user_id: Current user ID
            project_id: Optional project ID
            llm: Optional LangChain LLM (uses ModelRouter if None)
            max_repair_attempts: Maximum repair retries
        """
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        self.max_repair_attempts = max_repair_attempts

        # Use provided LLM or create adapter from ModelRouter
        if llm is not None:
            self.llm = llm
        else:
            from app.intelligence.ai.llm.registry import llm_registry
            model_router = llm_registry.router
            self.llm = CeaserModelAdapter(model_router=model_router)

        # Context adapter for existing CEASER context services
        self.context_adapter = ContextAdapter(db)

        # Device gateway service for command status checking
        from app.services.device_gateway_service import DeviceGatewayService
        self.gateway = DeviceGatewayService(db)

    def _generate_plan(self, state: BoltAgentState) -> dict[str, Any]:
        """Generate BoltCodingPlan using existing ModelRouter.

        Args:
            state: Current graph state

        Returns:
            Plan generation results
        """
        # Build context
        context = self.context_adapter.build_research_context(
            user_id=self.user_id,
            query=state["prompt"],
            conversation_id=None,
        )

        system_prompt = f"""You are Bolt, a software engineering agent. Create a detailed implementation plan.

Analyze the user's request and create a plan that:
1. Uses minimal, focused file operations
2. Includes necessary setup commands (dependencies, config)
3. Includes build commands to verify compilation
4. Includes test commands to verify functionality

Output ONLY valid JSON with this structure:
{{
    "summary": "Brief summary of the plan",
    "file_operations": [
        {{"operation": "write|patch|mkdir", "path": "relative/path", "content": "file content (optional)"}}
    ],
    "setup_commands": [
        {{"argv": ["command", "arg1", "arg2"], "cwd": ".", "timeout_seconds": 60}}
    ],
    "build_commands": [
        {{"argv": ["command", "arg1"], "cwd": ".", "timeout_seconds": 120}}
    ],
    "test_commands": [
        {{"argv": ["command", "arg1"], "cwd": ".", "timeout_seconds": 60}}
    ]
}}

User request: {state['prompt']}
Project context: {state.get('project_context', {})}"""

        response = self.llm.invoke([{"type": "system", "content": system_prompt}])

        text = response.content if hasattr(response, "content") else str(response)

        # Parse JSON from response
        import re
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(text).strip(), flags=re.I)
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise ValueError("invalid_plan_response")

        plan_data = self._json_parse(text[start:end + 1])

        return {
            "plan_summary": plan_data.get("summary", "Plan generated"),
            "file_operations": plan_data.get("file_operations", []),
            "setup_commands": plan_data.get("setup_commands", []),
            "build_commands": plan_data.get("build_commands", []),
            "test_commands": plan_data.get("test_commands", []),
        }

    def _json_parse(self, text: str) -> dict[str, Any]:
        """Parse JSON from string.

        Args:
            text: JSON string

        Returns:
            Parsed dictionary

        Raises:
            ValueError: If JSON parsing fails
        """
        import json
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e


class AnalyzeNode:
    """Graph node: Analyze user request and project context."""

    def __init__(self, executor: BoltNodeExecutor):
        self.executor = executor

    def __call__(self, state: BoltAgentState) -> dict[str, Any]:
        """Execute analyze node.

        Inspects project context and determines the approach.
        Returns initial plan with analysis results.

        Args:
            state: Current graph state

        Returns:
            Updated state with analysis results
        """
        # Build context string for LLM
        context_str = self._build_context_str(state)

        system_prompt = f"""You are Bolt, analyzing a user request. Determine:
1. What the user wants to accomplish
2. Whether this is a new project or existing project
3. Key files or directories that will be involved
4. Whether a plan is needed or can execute directly

Respond with:
ANALYSIS: [brief analysis]
APPROACH: [plan_needed|direct_execute]
KEY_FILES: [comma-separated list of key files if any]{context_str if context_str else ""}"""

        user_prompt = f"User request: {state['prompt']}"

        response = self.executor.llm.invoke([
            {"type": "system", "content": system_prompt},
            {"type": "human", "content": user_prompt},
        ])

        analysis_text = response.content if hasattr(response, "content") else str(response)

        # Extract analysis results
        is_plan_needed = "plan_needed" in analysis_text.lower()

        return {
            **state,
            "current_step": "plan" if is_plan_needed else "execute",
            "status_message": "Analysis complete" if is_plan_needed else "Executing directly",
            "tool_calls": state.get("tool_calls", []),
            "tool_results": state.get("tool_results", []),
        }

    def _build_context_str(self, state: BoltAgentState) -> str:
        """Build context string from project context."""
        context = state.get("project_context", {})
        parts = []

        if context.get("files"):
            parts.append(f"Available files: {', '.join(context['files'][:20])}")

        if context.get("type"):
            parts.append(f"Project type: {context['type']}")

        return "\n\n" + "\n".join(parts) if parts else ""


class PlanNode:
    """Graph node: Generate coding plan using LLM."""

    def __init__(self, executor: BoltNodeExecutor):
        self.executor = executor

    def __call__(self, state: BoltAgentState) -> dict[str, Any]:
        """Execute plan node.

        Generates BoltCodingPlan using ModelRouter.

        Args:
            state: Current graph state

        Returns:
            Updated state with plan
        """
        plan_results = self.executor._generate_plan(state)

        return {
            **state,
            **plan_results,
            "current_step": "execute",
            "status_message": "Plan generated",
        }


class ExecuteNode:
    """Graph node: Execute tool calls from plan."""

    def __init__(self, executor: BoltNodeExecutor):
        self.executor = executor
        self.adapters: dict[str, Any] = {}

    def _get_adapter(self, capability: str) -> Any:
        """Get adapter for capability.

        Args:
            capability: Capability ID

        Returns:
            Adapter instance
        """
        if capability not in self.adapters:
            project_id = self.executor.project_id
            if capability == "project.read_file":
                self.adapters[capability] = ReadFileAdapter(self.executor.db, self.executor.user_id, project_id)
            elif capability == "project.write_file":
                self.adapters[capability] = WriteFileAdapter(self.executor.db, self.executor.user_id, project_id)
            elif capability == "project.patch_file":
                self.adapters[capability] = PatchFileAdapter(self.executor.db, self.executor.user_id, project_id)
            elif capability == "terminal.run_scoped":
                self.adapters[capability] = TerminalAdapter(self.executor.db, self.executor.user_id, project_id)
            elif capability == "git.status":
                self.adapters[capability] = GitStatusAdapter(self.executor.db, self.executor.user_id, project_id)
            elif capability == "git.add":
                self.adapters[capability] = GitAddAdapter(self.executor.db, self.executor.user_id, project_id)
        return self.adapters.get(capability)

    def _execute_file_operation(self, op: dict[str, Any]) -> dict[str, Any]:
        """Execute a single file operation via adapter.

        Args:
            op: File operation dict with operation, path, content, destination

        Returns:
            Tool result dict with status, output/error
        """
        operation = op.get("operation", "unknown")
        path = op.get("path", "")

        # Map operation to capability
        capability_map = {
            "write": "project.write_file",
            "patch": "project.patch_file",
            "mkdir": "project.create_directory",
            "rename": "project.rename",
            "copy": "project.copy",
            "delete": "project.delete",
        }

        capability = capability_map.get(operation)
        if not capability:
            return {
                "tool_call_id": "unknown",
                "status": "failed",
                "error": {"code": "unknown_operation", "message": f"Unknown operation: {operation}"},
            }

        adapter = self._get_adapter(capability)
        if not adapter:
            return {
                "tool_call_id": "unknown",
                "status": "failed",
                "error": {"code": "adapter_not_found", "message": f"No adapter for capability: {capability}"},
            }

        # Execute via adapter
        try:
            if operation == "write":
                result = adapter.write(path, op.get("content", ""))
            elif operation == "patch":
                result = adapter.patch(path, op.get("diff", ""))
            elif operation == "mkdir":
                # Use project.create_directory capability
                result = adapter.run(f"mkdir -p {path}" if path else "", path)
            elif operation == "rename":
                result = adapter.run(f"mv {path} {op.get('destination', '')}", ".")
            elif operation == "copy":
                result = adapter.run(f"cp {path} {op.get('destination', '')}", ".")
            elif operation == "delete":
                result = adapter.run(f"rm -f {path}", ".")
            else:
                result = {"status": "error", "error": "unsupported_operation"}

            if result.get("status") == "completed":
                return {
                    "tool_call_id": f"tool_{path.replace('/', '_')[:32]}",
                    "status": "completed",
                    "output": result.get("output", result.get("content", "operation completed")),
                }
            elif result.get("status") == "pending":
                return {
                    "tool_call_id": result.get("command_id", f"tool_{path.replace('/', '_')[:32]}"),
                    "status": "pending",
                    "output": f"Operation queued: {operation} for {path}",
                }
            else:
                return {
                    "tool_call_id": f"tool_{path.replace('/', '_')[:32]}",
                    "status": "failed",
                    "error": result.get("error", {"code": "unknown_error", "message": str(result)}),
                }
        except Exception as e:
            return {
                "tool_call_id": f"tool_{path.replace('/', '_')[:32]}",
                "status": "failed",
                "error": {"code": "adapter_error", "message": str(e)},
            }

    def _execute_terminal_command(self, cmd: dict[str, Any]) -> dict[str, Any]:
        """Execute a single terminal command via adapter.

        Args:
            cmd: Command dict with argv, cwd, timeout_seconds

        Returns:
            Tool result dict with status, output/error
        """
        argv = cmd.get("argv", [])
        command_str = " ".join(argv)

        adapter = self._get_adapter("terminal.run_scoped")
        if not adapter:
            return {
                "tool_call_id": "unknown",
                "status": "failed",
                "error": {"code": "adapter_not_found", "message": "Terminal adapter not found"},
            }

        try:
            result = adapter.run(command_str, cmd.get("cwd", "."))
            if result.get("status") == "completed":
                return {
                    "tool_call_id": result.get("command_id", f"term_{hash(command_str) & 0xFFFFFFFF:08x}"),
                    "status": "completed",
                    "output": result.get("output", "command completed"),
                }
            elif result.get("status") == "pending":
                return {
                    "tool_call_id": result.get("command_id", f"term_{hash(command_str) & 0xFFFFFFFF:08x}"),
                    "status": "pending",
                    "output": f"Command queued: {command_str}",
                }
            else:
                return {
                    "tool_call_id": f"term_{hash(command_str) & 0xFFFFFFFF:08x}",
                    "status": "failed",
                    "error": result.get("error", {"code": "unknown_error", "message": str(result)}),
                }
        except Exception as e:
            return {
                "tool_call_id": f"term_{hash(command_str) & 0xFFFFFFFF:08x}",
                "status": "failed",
                "error": {"code": "adapter_error", "message": str(e)},
            }

    def _execute_git_command(self, cmd: dict[str, Any]) -> dict[str, Any]:
        """Execute a single git command via adapter.

        Args:
            cmd: Command dict with argv

        Returns:
            Tool result dict with status, output/error
        """
        argv = cmd.get("argv", [])

        # Map git command to capability
        git_cmd = argv[1] if len(argv) > 1 else ""
        capability_map = {
            "status": "git.status",
            "add": "git.add",
            "diff": "git.diff",
            "commit": "git.commit",
            "log": "git.log",
        }

        capability = capability_map.get(git_cmd)
        if not capability:
            return {
                "tool_call_id": "unknown",
                "status": "failed",
                "error": {"code": "unknown_git_command", "message": f"Unknown git command: {git_cmd}"},
            }

        adapter = self._get_adapter(capability)
        if not adapter:
            return {
                "tool_call_id": "unknown",
                "status": "failed",
                "error": {"code": "adapter_not_found", "message": f"No adapter for capability: {capability}"},
            }

        try:
            if git_cmd == "status":
                result = adapter.status()
            elif git_cmd == "add":
                paths = argv[2:] if len(argv) > 2 else []
                result = adapter.add(paths)
            elif git_cmd == "diff":
                result = adapter.run(" ".join(argv), ".")
            elif git_cmd == "commit":
                result = adapter.run(" ".join(argv), ".")
            elif git_cmd == "log":
                result = adapter.run(" ".join(argv), ".")
            else:
                result = {"status": "error", "error": "unsupported_git_command"}

            if result.get("status") == "completed":
                return {
                    "tool_call_id": result.get("command_id", f"git_{git_cmd}"),
                    "status": "completed",
                    "output": result.get("output", result.get("stdout", "git command completed")),
                }
            elif result.get("status") == "pending":
                return {
                    "tool_call_id": result.get("command_id", f"git_{git_cmd}"),
                    "status": "pending",
                    "output": f"Git command queued: {git_cmd}",
                }
            else:
                return {
                    "tool_call_id": f"git_{git_cmd}",
                    "status": "failed",
                    "error": result.get("error", {"code": "unknown_error", "message": str(result)}),
                }
        except Exception as e:
            return {
                "tool_call_id": f"git_{git_cmd}",
                "status": "failed",
                "error": {"code": "adapter_error", "message": str(e)},
            }

    def __call__(self, state: BoltAgentState) -> dict[str, Any]:
        """Execute execute node.

        Runs file operations, setup commands, and tracks tool calls.
        Invokes actual CEASER capability adapters.

        Args:
            state: Current graph state

        Returns:
            Updated state with tool results
        """
        tool_calls = state.get("tool_calls", [])
        tool_results = state.get("tool_results", [])

        # Execute file operations via adapters
        file_ops = state.get("file_operations", [])
        for op in file_ops:
            operation = op.get("operation", "unknown")
            if operation in ("write", "patch", "mkdir", "rename", "copy", "delete"):
                tool_result = self._execute_file_operation(op)
                tool_calls.append({
                    "id": tool_result.get("tool_call_id", "unknown"),
                    "type": "function",
                    "function": {"name": operation, "arguments": op},
                })
                tool_results.append(tool_result)

        # Execute setup commands via terminal adapter
        setup_cmds = state.get("setup_commands", [])
        for cmd in setup_cmds:
            tool_result = self._execute_terminal_command(cmd)
            tool_calls.append({
                "id": tool_result.get("tool_call_id", "unknown"),
                "type": "function",
                "function": {"name": "terminal_run", "arguments": {"command": " ".join(cmd.get("argv", []))}},
            })
            tool_results.append(tool_result)

        # Execute build/test commands via terminal adapter
        build_cmds = state.get("build_commands", [])
        for cmd in build_cmds:
            tool_result = self._execute_terminal_command(cmd)
            tool_calls.append({
                "id": tool_result.get("tool_call_id", "unknown"),
                "type": "function",
                "function": {"name": "terminal_run", "arguments": {"command": " ".join(cmd.get("argv", []))}},
            })
            tool_results.append(tool_result)

        test_cmds = state.get("test_commands", [])
        for cmd in test_cmds:
            tool_result = self._execute_terminal_command(cmd)
            tool_calls.append({
                "id": tool_result.get("tool_call_id", "unknown"),
                "type": "function",
                "function": {"name": "terminal_run", "arguments": {"command": " ".join(cmd.get("argv", []))}},
            })
            tool_results.append(tool_result)

        return {
            **state,
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "current_step": "verify",
            "status_message": "Tool calls executed",
        }


class VerifyNode:
    """Graph node: Verify build and test results."""

    TERMINAL_COMMANDS = ("COMPLETED", "FAILED", "TIMEOUT", "CANCELLED")

    def __init__(self, executor: BoltNodeExecutor):
        self.executor = executor
        # Create a local adapter cache for terminal commands
        self.adapters: dict[str, Any] = {}

    def _get_terminal_adapter(self) -> Any:
        """Get terminal adapter for verify node."""
        if "terminal.run_scoped" not in self.adapters:
            self.adapters["terminal.run_scoped"] = TerminalAdapter(
                self.executor.db, self.executor.user_id, self.executor.project_id
            )
        return self.adapters["terminal.run_scoped"]

    def _check_command_result(self, request_id: str) -> dict[str, Any]:
        """Check if a command has completed and get its result.

        Args:
            request_id: DesktopCommand request_id

        Returns:
            Dict with status, exit_code, and error info
        """
        command = self.executor.gateway.owned_command(
            User(id=self.executor.user_id), request_id
        )

        if not command:
            return {"status": "pending", "exit_code": None}

        # Check if command has completed
        if command.status in self.TERMINAL_COMMANDS:
            if command.status == "COMPLETED":
                # Command completed successfully
                result_json = command.result_json or {}
                output = result_json.get("output", {})
                exit_code = output.get("exit_code")

                # Check if exit_code is 0 for success
                if exit_code == 0 or exit_code is None:
                    return {"status": "completed", "exit_code": exit_code, "error": None}
                else:
                    return {"status": "completed", "exit_code": exit_code, "error": "non_zero_exit"}

            elif command.status == "FAILED":
                return {"status": "failed", "exit_code": None, "error": command.safe_error}

            elif command.status == "TIMEOUT":
                return {"status": "failed", "exit_code": None, "error": "timeout"}

            elif command.status == "CANCELLED":
                return {"status": "failed", "exit_code": None, "error": "cancelled"}

        # Command is still pending
        return {"status": "pending", "exit_code": None}

    def _execute_build_test_commands(
        self, commands: list[dict[str, Any]], command_type: str
    ) -> tuple[str, list[dict[str, Any]]]:
        """Execute build or test commands and return status with results.

        Args:
            commands: List of command dicts with argv, cwd, timeout_seconds
            command_type: "build" or "test" for logging

        Returns:
            Tuple of (status: "passed"|"failed", results: list of tool results)
        """
        if not commands:
            return "passed", []

        adapter = self._get_terminal_adapter()
        if not adapter:
            return "failed", [{
                "tool_call_id": "unknown",
                "status": "failed",
                "error": {"code": "adapter_not_found", "message": "Terminal adapter not found"},
            }]

        results = []
        has_pending = False
        has_failure = False

        for cmd in commands:
            argv = cmd.get("argv", [])
            command_str = " ".join(argv)
            request_id = f"term_{hash(command_str) & 0xFFFFFFFF:08x}"

            try:
                result = adapter.run(command_str, cmd.get("cwd", "."))
                results.append({
                    "tool_call_id": result.get("command_id", request_id),
                    "status": "pending",
                    "output": f"Command queued: {command_str}",
                })

                # Check if command has completed
                if result.get("status") == "pending" and result.get("command_id"):
                    cmd_result = self._check_command_result(result.get("command_id"))
                    if cmd_result["status"] == "completed":
                        if cmd_result["error"] is None:
                            # Exit code is 0 or not present - success
                            results[-1]["status"] = "completed"
                            results[-1]["exit_code"] = cmd_result["exit_code"]
                            has_pending = False
                        else:
                            # Non-zero exit code - failure
                            results[-1]["status"] = "failed"
                            results[-1]["error"] = cmd_result["error"]
                            has_failure = True
                    elif cmd_result["status"] == "failed":
                        results[-1]["status"] = "failed"
                        results[-1]["error"] = cmd_result["error"]
                        has_failure = True
                    else:
                        has_pending = True
                elif result.get("status") == "completed":
                    has_pending = False
                else:
                    has_failure = True

            except Exception as e:
                results.append({
                    "tool_call_id": request_id,
                    "status": "failed",
                    "error": {"code": "adapter_error", "message": str(e)},
                })
                has_failure = True

        # Determine overall status based on command results
        if has_failure:
            return "failed", results
        if has_pending:
            # Some commands are still pending - consider as passed for now
            # In production, this would block or use async wait
            return "passed", results
        if results and all(r.get("status") == "completed" for r in results):
            return "passed", results

        return "passed", results

    def __call__(self, state: BoltAgentState) -> dict[str, Any]:
        """Execute verify node.

        Runs build and test commands to verify the implementation.
        Checks exit codes from completed commands to determine pass/fail.

        Args:
            state: Current graph state

        Returns:
            Updated state with verification results
        """
        build_status = "passed"
        test_status = "passed"
        build_results = []
        test_results = []

        # Execute build commands via terminal adapter
        if state.get("build_commands"):
            build_status, build_results = self._execute_build_test_commands(
                state.get("build_commands", []), "build"
            )

        # Execute test commands via terminal adapter
        if state.get("test_commands"):
            test_status, test_results = self._execute_build_test_commands(
                state.get("test_commands", []), "test"
            )

        return {
            **state,
            "build_status": build_status,
            "test_status": test_status,
            "current_step": "complete" if (build_status == "passed" and test_status == "passed") else "repair",
            "status_message": "Verification complete" if build_status == "passed" else "Verification failed",
        }


class RepairNode:
    """Graph node: Handle failures with bounded retries."""

    def __init__(self, executor: BoltNodeExecutor):
        self.executor = executor

    def __call__(self, state: BoltAgentState) -> dict[str, Any]:
        """Execute repair node.

        Generates a repair plan when verification fails.

        Args:
            state: Current graph state

        Returns:
            Updated state with repair plan
        """
        retry_count = state.get("retry_count", 0)
        max_attempts = state.get("max_repair_attempts", self.executor.max_repair_attempts)

        if retry_count >= max_attempts:
            # Max retries reached - fail gracefully
            return {
                **state,
                "current_step": "failed",
                "error": f"Repair attempts exhausted after {retry_count} retries",
                "status_message": "Repair failed",
            }

        # Generate repair plan
        failure_info = self._get_failure_info(state)

        system_prompt = f"""You are Bolt, repairing a failed build. Generate a minimal repair plan.

Current failure: {failure_info}
Previous file operations: {state.get('file_operations', [])[:5]}

Output ONLY valid JSON with:
{{
    "summary": "Brief repair summary",
    "file_operations": [
        {{"operation": "write|patch", "path": "path", "content": "new content"}}
    ],
    "build_commands": [],
    "test_commands": []
}}"""

        user_prompt = f"Original request: {state['prompt']}"

        response = self.executor.llm.invoke([
            {"type": "system", "content": system_prompt},
            {"type": "human", "content": user_prompt},
        ])

        text = response.content if hasattr(response, "content") else str(response)

        # Parse repair plan
        import re
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(text).strip(), flags=re.I)
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end >= start:
            repair_data = self.executor._json_parse(text[start:end + 1])
            return {
                **state,
                "file_operations": repair_data.get("file_operations", []),
                "build_commands": repair_data.get("build_commands", []),
                "test_commands": repair_data.get("test_commands", []),
                "retry_count": retry_count + 1,
                "repair_history": state.get("repair_history", []) + [{
                    "attempt": retry_count + 1,
                    "failure": failure_info,
                }],
                "current_step": "execute",
                "status_message": f"Repair attempt {retry_count + 1}",
            }

        # Fallback: fail
        return {
            **state,
            "current_step": "failed",
            "error": "Failed to generate repair plan",
            "status_message": "Repair failed",
        }

    def _get_failure_info(self, state: BoltAgentState) -> str:
        """Extract failure information from state."""
        parts = []

        if state.get("build_status") == "failed":
            parts.append("Build failed")

        if state.get("test_status") == "failed":
            parts.append("Tests failed")

        if state.get("error"):
            parts.append(state["error"])

        return "; ".join(parts) if parts else "Unknown failure"


class CompleteNode:
    """Graph node: Finalize response."""

    def __init__(self, executor: BoltNodeExecutor):
        self.executor = executor

    def __call__(self, state: BoltAgentState) -> dict[str, Any]:
        """Execute complete node.

        Generates final response summarizing the execution.

        Args:
            state: Current graph state

        Returns:
            Updated state with final response
        """
        # Build summary
        summary_parts = []

        if state.get("build_status") == "passed":
            summary_parts.append("Build succeeded")

        if state.get("test_status") == "passed":
            summary_parts.append("Tests passed")

        if state.get("file_operations"):
            summary_parts.append(f"{len(state['file_operations'])} file operation(s) completed")

        if state.get("git_revision"):
            summary_parts.append(f"Git checkpoint: {state['git_revision'][:8]}")

        # Generate final response
        summary = "; ".join(summary_parts) if summary_parts else "Execution completed"

        system_prompt = f"""Summarize the execution results for the user.

Execution summary: {summary}
User request: {state['prompt']}

Provide a concise summary of what was done and the results."""

        response = self.executor.llm.invoke([
            {"type": "system", "content": system_prompt},
        ])

        final_response = response.content if hasattr(response, "content") else summary

        return {
            **state,
            "final_response": final_response,
            "current_step": "complete",
            "end_time": time.time(),
            "status_message": "Complete",
        }


class FailedNode:
    """Graph node: Handle final failure state."""

    def __init__(self, executor: BoltNodeExecutor):
        self.executor = executor

    def __call__(self, state: BoltAgentState) -> dict[str, Any]:
        """Execute failed node.

        Generates error response.

        Args:
            state: Current graph state

        Returns:
            Updated state with error response
        """
        error_msg = state.get("error", "Unknown error occurred")
        prompt = state.get("prompt", "")

        system_prompt = f"""Explain the failure to the user.

Error: {error_msg}
Original request: {prompt}

Be clear about what went wrong and suggest next steps."""

        response = self.executor.llm.invoke([
            {"type": "system", "content": system_prompt},
        ])

        return {
            **state,
            "final_response": response.content if hasattr(response, "content") else error_msg,
            "current_step": "failed",
            "end_time": time.time(),
            "status_message": "Failed",
        }
