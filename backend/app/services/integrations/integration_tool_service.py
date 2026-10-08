"""Integration Tool Service for CEASER.

This module provides a generic bridge between connected integrations and LLM tool calling.

Architecture:
  User Request with Integrations
    ↓
IntegrationToolService.get_available_tools(user_id)
    ↓
Build tool definitions from connected providers
    ↓
ModelRequest(tools=[...], needs_tools=True)
    ↓
LLM generates tool_calls
    ↓
execute_tool_call(tool_call)
    ↓
IntegrationExecutionEngine.execute()
    ↓
CapabilityExecutor.execute()
    ↓
Provider implementation (Gmail, Calendar, GitHub, etc.)
    ↓
Result returned
    ↓
LLM receives tool result
    ↓
Final natural-language response

Capabilities:
  - Gmail: read_emails, create_draft, update_draft, send_draft
  - Calendar: read_events, create_event, update_event
  - Drive: search_files
  - Tasks: read_tasks
  - Classroom: read_courses, read_assignments
  - Notion: search_pages, list_databases, list_pages, create_task, list_members
  - GitHub: list_repositories, list_issues, list_pull_requests, list_commits, get_readme
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.integration import Integration


# Capability definitions mapped from CapabilityExecutor.executable
# Format: capability_id -> (provider, method, read_only, description)
CAPABILITY_DEFINITIONS = {
    # Gmail capabilities
    "email.create_draft": ("gmail", "create_draft", False, "Create a draft email in the user's Gmail account"),
    "email.update_draft": ("gmail", "update_draft", False, "Update an existing draft email"),
    "email.reply_draft": ("gmail", "update_draft", False, "Create a reply draft for an existing email"),
    "email.send": ("gmail", "send_draft", False, "Send a verified draft email"),
    # Calendar capabilities
    "calendar.create_event": ("google-calendar", "create_event", False, "Create a new event on the user's calendar"),
    "calendar.update_event": ("google-calendar", "update_event", False, "Update an existing calendar event"),
    "calendar.find_event": ("google-calendar", "get_metadata", True, "Find calendar events by query"),
    # Google Drive capabilities
    "drive.search_files": ("google-drive", "get_metadata", True, "Search files in Google Drive"),
    # Google Tasks capabilities
    "tasks.read_tasks": ("google-tasks", "get_metadata", True, "Read task lists and tasks"),
    # Google Classroom capabilities
    "classroom.read_courses": ("google-classroom", "get_metadata", True, "Read user's courses and coursework"),
    # Notion capabilities
    "notion.search_pages": ("notion", "search_pages", True, "Search Notion pages by query"),
    "notion.list_pages": ("notion", "list_pages", True, "List Notion pages"),
    "notion.list_databases": ("notion", "list_databases", True, "List Notion databases"),
    "notion.create_task": ("notion", "create_task", False, "Create a new task in Notion"),
    "notion.list_members": ("notion", "list_members", True, "List Notion workspace members"),
    # GitHub capabilities
    "github.list_repositories": ("github", "list_repositories", True, "List GitHub repositories"),
    "github.resolve_repository": ("github", "resolve_repository", True, "Find a specific GitHub repository"),
    "github.summarize_repositories": ("github", "summarize_repositories", True, "Summarize GitHub repositories"),
    "github.get_readme": ("github", "get_readme", True, "Get README content from a repository"),
    "github.list_commits": ("github", "list_commits", True, "List recent commits in a repository"),
    "github.list_issues": ("github", "list_issues", True, "List open issues in a repository"),
    "github.list_pull_requests": ("github", "list_pull_requests", True, "List open pull requests"),
    "github.create_repository": ("github", "create_repository", False, "Create a new GitHub repository"),
}


@dataclass
class ToolDefinition:
    """Definition of an LLM-callable tool."""
    name: str
    description: str
    parameters: dict[str, Any]
    provider: str
    capability: str
    requires_confirmation: bool
    is_read_only: bool


@dataclass
class ToolCallResult:
    """Result of executing a tool call."""
    success: bool
    content: str | None = None
    error: str | None = None
    requires_confirmation: bool = False
    confirmation_prompt: str | None = None


class IntegrationToolService:
    """Service for managing integration tools for LLM tool calling.

    Provides a generic bridge between connected integrations and LLM capabilities.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_available_tools(self, user_id: str) -> list[ToolDefinition]:
        """Get available tools for a user based on their connected integrations.

        Args:
            user_id: The user ID

        Returns:
            List of tool definitions for available integrations
        """
        # Find connected integrations
        connected = self.db.query(Integration).filter(
            Integration.user_id == user_id,
            Integration.status == "connected"
        ).all()

        # Build tools from connected providers
        tools = []
        for integration in connected:
            provider_tools = self._get_provider_tools(integration.provider, user_id)
            tools.extend(provider_tools)

        return tools

    def _get_provider_tools(self, provider: str, user_id: str) -> list[ToolDefinition]:
        """Get tools for a specific provider.

        Args:
            provider: Provider ID (e.g., 'gmail', 'google-calendar')
            user_id: User ID

        Returns:
            List of tool definitions for this provider
        """
        tools = []

        # Filter capabilities by provider
        provider_caps = [
            (cap_id, defn) for cap_id, defn in CAPABILITY_DEFINITIONS.items()
            if defn[0] == provider
        ]

        for cap_id, (prov, method, read_only, desc) in provider_caps:
            tool_name = self._capability_to_tool_name(cap_id)
            parameters = self._build_tool_parameters(cap_id, method)
            requires_confirmation = self._requires_confirmation(cap_id)

            tools.append(ToolDefinition(
                name=tool_name,
                description=desc,
                parameters=parameters,
                provider=provider,
                capability=cap_id,
                requires_confirmation=requires_confirmation,
                is_read_only=read_only
            ))

        return tools

    def _capability_to_tool_name(self, capability: str) -> str:
        """Convert capability ID to tool name.

        Examples:
            "email.create_draft" -> "gmail_create_draft"
            "calendar.create_event" -> "google_calendar_create_event"
            "github.list_repositories" -> "github_list_repositories"
        """
        # Replace dots with underscores and normalize
        name = capability.replace(".", "_")

        # Remove provider prefix for some capabilities
        if name.startswith("email_"):
            name = "gmail_" + name[6:]
        elif name.startswith("calendar_"):
            name = "google_calendar_" + name[9:]
        elif name.startswith("drive_"):
            name = "google_drive_" + name[6:]
        elif name.startswith("tasks_"):
            name = "google_tasks_" + name[6:]
        elif name.startswith("classroom_"):
            name = "google_classroom_" + name[10:]

        return name

    def _build_tool_parameters(self, capability: str, method: str) -> dict[str, Any]:
        """Build JSON schema parameters for a tool.

        Args:
            capability: Capability ID
            method: Provider method name

        Returns:
            Tool parameters JSON schema
        """
        # Generic parameters for most capabilities
        params: dict[str, Any] = {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "Natural language request describing what the user wants"
                }
            },
            "required": ["request"]
        }

        # Specialize parameters by capability
        if "email" in capability:
            params["properties"]["to"] = {"type": "string", "description": "Recipient email address"}
            params["properties"]["subject"] = {"type": "string", "description": "Email subject"}
            params["properties"]["body"] = {"type": "string", "description": "Email body content"}

        elif "calendar" in capability:
            params["properties"]["summary"] = {"type": "string", "description": "Event summary/title"}
            params["properties"]["start"] = {"type": "string", "description": "Start time (ISO format)"}
            params["properties"]["end"] = {"type": "string", "description": "End time (ISO format)"}

        elif "github" in capability:
            params["properties"]["repository_query"] = {
                "type": "string",
                "description": "Repository name or search query"
            }

        elif "notion" in capability:
            params["properties"]["query"] = {
                "type": "string",
                "description": "Search query"
            }
            params["properties"]["task_title"] = {
                "type": "string",
                "description": "Task title for create_task"
            }

        return params

    def _requires_confirmation(self, capability: str) -> bool:
        """Check if a capability requires confirmation.

        Args:
            capability: Capability ID

        Returns:
            True if confirmation required
        """
        # Use the same list as CapabilityExecutor
        protected = {"email.send", "calendar.update_event"}
        return capability in protected

    def execute_tool_call(self, tool_name: str, arguments: dict[str, Any], user_id: str) -> ToolCallResult:
        """Execute a tool call.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            user_id: User ID

        Returns:
            ToolCallResult with success/failure and content
        """
        # Find the capability from tool name
        capability = self._tool_name_to_capability(tool_name)
        if capability is None:
            return ToolCallResult(
                success=False,
                error=f"Unknown tool: {tool_name}"
            )

        # Get provider and method
        cap_def = CAPABILITY_DEFINITIONS.get(capability)
        if cap_def is None:
            return ToolCallResult(
                success=False,
                error=f"Unknown capability: {capability}"
            )

        provider, method, _, _ = cap_def

        # Check if confirmation is required
        if self._requires_confirmation(capability):
            return ToolCallResult(
                success=False,
                requires_confirmation=True,
                confirmation_prompt=f"Please confirm you want to {capability.split('.')[-1]}",
                content=None
            )

        # Execute via IntegrationExecutionEngine
        from app.services.integrations.integration_execution_engine import IntegrationExecutionEngine
        from app.models.integration import Integration

        try:
            # Find integration for this provider
            integration = self.db.query(Integration).filter(
                Integration.user_id == user_id,
                Integration.provider == provider,
                Integration.status == "connected"
            ).first()

            if not integration:
                return ToolCallResult(
                    success=False,
                    error=f"{provider} is not connected"
                )

            # Parse arguments
            intent_args = self._parse_tool_arguments(capability, arguments)

            # Execute
            engine = IntegrationExecutionEngine(self.db)
            result = engine.execute(
                user_id=user_id,
                provider=provider,
                capability=capability,
                arguments=intent_args
            )

            if result.status == "not_connected":
                return ToolCallResult(
                    success=False,
                    error=result.summary
                )

            if result.status == "completed":
                return ToolCallResult(
                    success=True,
                    content=result.summary or str(result.data)
                )

            return ToolCallResult(
                success=False,
                error=result.summary or f"Tool execution failed: {result.status}"
            )

        except Exception as exc:
            return ToolCallResult(
                success=False,
                error=str(exc)
            )

    def _tool_name_to_capability(self, tool_name: str) -> str | None:
        """Convert tool name back to capability ID.

        Args:
            tool_name: Tool name (e.g., 'gmail_create_draft')

        Returns:
            Capability ID (e.g., 'email.create_draft') or None
        """
        # Reverse mapping from tool name to capability
        for cap_id, (provider, _, _, _) in CAPABILITY_DEFINITIONS.items():
            expected_tool = self._capability_to_tool_name(cap_id)
            if expected_tool == tool_name:
                return cap_id
        return None

    def _parse_tool_arguments(self, capability: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Parse tool arguments into provider-specific format.

        Args:
            capability: Capability ID
            arguments: Raw tool arguments

        Returns:
            Parsed arguments for provider
        """
        # Extract the request text
        request = arguments.get("request", "")

        # Build provider arguments based on capability
        intent_args: dict[str, Any] = {}

        if "email" in capability:
            intent_args = {
                "to": arguments.get("to", ""),
                "subject": arguments.get("subject", ""),
                "body": arguments.get("body", ""),
                "thread_id": arguments.get("thread_id"),
                "in_reply_to": arguments.get("in_reply_to"),
            }

        elif "calendar" in capability:
            intent_args = {
                "summary": arguments.get("summary", request[:160]),
                "start": arguments.get("start"),
                "end": arguments.get("end"),
            }

        elif "github" in capability:
            intent_args = {
                "repository_query": arguments.get("repository_query"),
                "include_readme": arguments.get("include_readme"),
            }

        elif "notion" in capability:
            intent_args = {
                "query": arguments.get("query"),
                "task_title": arguments.get("task_title"),
            }

        return intent_args
