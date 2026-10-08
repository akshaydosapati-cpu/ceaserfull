"""LangGraph Bolt tool adapters.

These adapters provide thin wrappers around existing CEASER capabilities,
allowing the LangGraph Bolt agent to use CEASER's existing execution infrastructure.

Architecture:
  LangGraph Bolt Agent
    ↓ calls
  BoltToolAdapter (this module)
    ↓ invokes
  existing CEASER capability (via DeviceGatewayService)
    ↓
  existing execution (device/cloud)
    ↓
  result

DO NOT implement actual operations in adapters.
Always delegate to existing CEASER capabilities.
"""
from __future__ import annotations

import os
from typing import Any

from sqlalchemy.orm import Session

from app.agents.v2 import DeviceCapabilityRequest
from app.services.device_gateway_service import DeviceGatewayService
from app.models.user import User
from app.services.audit_service import AuditService


class BoltToolAdapter:
    """Base class for Bolt tool adapters.

    Each adapter:
    1. Validates/normalizes LangGraph input
    2. Calls the existing CEASER capability
    3. Returns structured results
    4. Preserves failure information
    """

    capability_id: str
    name: str

    def __init__(self, db: Session, user_id: str, project_id: str | None = None):
        """Initialize adapter.

        Args:
            db: SQLAlchemy database session
            user_id: Current user ID
            project_id: Optional project ID for project-scoped operations
        """
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        self.gateway = DeviceGatewayService(db)

    def _validate_path(self, path: str) -> bool:
        """Validate path is within project scope.

        Args:
            path: File path to validate

        Returns:
            True if path is valid
        """
        # Basic validation: no absolute paths, no traversal outside project
        if os.path.isabs(path):
            return False
        if ".." in path.split("/"):
            return False
        if path.startswith("/"):
            return False
        return True

    def _audit(self, action: str, metadata: dict[str, Any] | None = None) -> None:
        """Record audit event.

        Args:
            action: Audit action name
            metadata: Optional metadata
        """
        AuditService(self.db).record(
            user_id=self.user_id,
            action=action,
            resource_type="bolt_tool",
            resource_id=self.project_id or self.user_id,
            metadata=metadata or {},
        )


class ReadFileAdapter(BoltToolAdapter):
    """Adapter for project.read_file capability."""

    capability_id = "project.read_file"
    name = "read_file"

    def read(self, path: str) -> dict[str, Any]:
        """Read a file from the project.

        Args:
            path: Relative file path within project

        Returns:
            Dict with command reference (execution delegated to CEASER)
        """
        if not self._validate_path(path):
            return {
                "status": "error",
                "error": "invalid_path",
                "message": "Path must be relative and within project scope",
            }

        self._audit("read_file.start", {"path": path})

        # Create DeviceCapabilityRequest - CEASER will handle device execution
        request = DeviceCapabilityRequest(
            request_id=f"bolt_read_{path.replace('/', '_')[:32]}",
            task_id="",
            agent_id="bolt",
            device_id="",  # Will be resolved by gateway
            capability=self.capability_id,
            arguments={
                "project_id": self.project_id,
                "path": path,
            },
            confirmation_requirement="none",
            timeout_seconds=60,
        )

        try:
            command = self.gateway.submit(User(id=self.user_id), request)
            return {
                "status": "pending",
                "command_id": command.request_id,
            }
        except Exception as e:
            self._audit("read_file.error", {"path": path, "error": str(e)})
            return {
                "status": "error",
                "error": "capability_failed",
                "message": str(e),
            }


class WriteFileAdapter(BoltToolAdapter):
    """Adapter for project.write_file capability."""

    capability_id = "project.write_file"
    name = "write_file"

    def write(self, path: str, content: str) -> dict[str, Any]:
        """Write content to a file.

        Args:
            path: Relative file path within project
            content: File content to write

        Returns:
            Dict with command reference (execution delegated to CEASER)
        """
        if not self._validate_path(path):
            return {
                "status": "error",
                "error": "invalid_path",
                "message": "Path must be relative and within project scope",
            }

        # Check content size (existing CEASER limit)
        if len(content.encode("utf-8")) > 1048576:  # 1MB
            return {
                "status": "error",
                "error": "file_too_large",
                "message": "File exceeds 1MB limit",
            }

        self._audit("write_file.start", {"path": path})

        # Create DeviceCapabilityRequest - CEASER will handle device execution
        request = DeviceCapabilityRequest(
            request_id=f"bolt_write_{path.replace('/', '_')[:32]}",
            task_id="",
            agent_id="bolt",
            device_id="",
            capability=self.capability_id,
            arguments={
                "project_id": self.project_id,
                "path": path,
                "content": content,
            },
            confirmation_requirement="none",
            timeout_seconds=60,
        )

        try:
            command = self.gateway.submit(User(id=self.user_id), request)
            return {
                "status": "pending",
                "command_id": command.request_id,
            }
        except Exception as e:
            self._audit("write_file.error", {"path": path, "error": str(e)})
            return {
                "status": "error",
                "error": "capability_failed",
                "message": str(e),
            }


class PatchFileAdapter(BoltToolAdapter):
    """Adapter for project.patch_file capability."""

    capability_id = "project.patch_file"
    name = "patch_file"

    def patch(self, path: str, diff: str) -> dict[str, Any]:
        """Apply a patch to a file.

        Args:
            path: Relative file path within project
            diff: Diff content to apply

        Returns:
            Dict with command reference (execution delegated to CEASER)
        """
        if not self._validate_path(path):
            return {
                "status": "error",
                "error": "invalid_path",
                "message": "Path must be relative and within project scope",
            }

        self._audit("patch_file.start", {"path": path})

        request = DeviceCapabilityRequest(
            request_id=f"bolt_patch_{path.replace('/', '_')[:32]}",
            task_id="",
            agent_id="bolt",
            device_id="",
            capability=self.capability_id,
            arguments={
                "project_id": self.project_id,
                "path": path,
                "diff": diff,
            },
            confirmation_requirement="none",
            timeout_seconds=60,
        )

        try:
            command = self.gateway.submit(User(id=self.user_id), request)
            return {
                "status": "pending",
                "command_id": command.request_id,
            }
        except Exception as e:
            self._audit("patch_file.error", {"path": path, "error": str(e)})
            return {
                "status": "error",
                "error": "capability_failed",
                "message": str(e),
            }


class TerminalAdapter(BoltToolAdapter):
    """Adapter for terminal.run_scoped capability."""

    capability_id = "terminal.run_scoped"
    name = "terminal_run"

    def run(self, command: str, cwd: str | None = None) -> dict[str, Any]:
        """Run a command in the project scope.

        Args:
            command: Command to run
            cwd: Optional working directory

        Returns:
            Dict with command reference (execution delegated to CEASER)
        """
        self._audit("terminal.start", {"command": command[:100]})

        request = DeviceCapabilityRequest(
            request_id=f"bolt_term_{hash(command) & 0xFFFFFFFF:08x}",
            task_id="",
            agent_id="bolt",
            device_id="",
            capability=self.capability_id,
            arguments={
                "project_id": self.project_id,
                "command": command,
                "cwd": cwd or ".",
            },
            confirmation_requirement="none",
            timeout_seconds=60,
        )

        try:
            command_obj = self.gateway.submit(User(id=self.user_id), request)
            return {
                "status": "pending",
                "command_id": command_obj.request_id,
            }
        except Exception as e:
            self._audit("terminal.error", {"command": command, "error": str(e)})
            return {
                "status": "error",
                "error": "capability_failed",
                "message": str(e),
            }


class GitStatusAdapter(BoltToolAdapter):
    """Adapter for git.status capability."""

    capability_id = "git.status"
    name = "git_status"

    def status(self, path: str | None = None) -> dict[str, Any]:
        """Get git repository status.

        Args:
            path: Optional path to check

        Returns:
            Dict with command reference (execution delegated to CEASER)
        """
        self._audit("git.status.start", {"path": path})

        request = DeviceCapabilityRequest(
            request_id="bolt_git_status",
            task_id="",
            agent_id="bolt",
            device_id="",
            capability=self.capability_id,
            arguments={
                "project_id": self.project_id,
                "path": path,
            },
            confirmation_requirement="none",
            timeout_seconds=60,
        )

        try:
            command = self.gateway.submit(User(id=self.user_id), request)
            return {
                "status": "pending",
                "command_id": command.request_id,
            }
        except Exception as e:
            self._audit("git.status.error", {"path": path, "error": str(e)})
            return {
                "status": "error",
                "error": "capability_failed",
                "message": str(e),
            }


class GitAddAdapter(BoltToolAdapter):
    """Adapter for git.add capability."""

    capability_id = "git.add"
    name = "git_add"

    def add(self, paths: list[str]) -> dict[str, Any]:
        """Stage files for git commit.

        Args:
            paths: List of file paths to stage

        Returns:
            Dict with command reference (execution delegated to CEASER)
        """
        self._audit("git.add.start", {"paths": paths})

        request = DeviceCapabilityRequest(
            request_id="bolt_git_add",
            task_id="",
            agent_id="bolt",
            device_id="",
            capability=self.capability_id,
            arguments={
                "project_id": self.project_id,
                "paths": paths,
            },
            confirmation_requirement="none",
            timeout_seconds=60,
        )

        try:
            command = self.gateway.submit(User(id=self.user_id), request)
            return {
                "status": "pending",
                "command_id": command.request_id,
            }
        except Exception as e:
            self._audit("git.add.error", {"paths": paths, "error": str(e)})
            return {
                "status": "error",
                "error": "capability_failed",
                "message": str(e),
            }
