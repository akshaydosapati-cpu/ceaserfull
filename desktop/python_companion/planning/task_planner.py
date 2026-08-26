from __future__ import annotations

import re
import uuid
from typing import Any

from capabilities.registry import CapabilityRegistry
from core.schemas import CommandRequest, CortexDecision
from planning.models import WorkflowPlan, WorkflowStep


class TaskPlanner:
    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    def plan(self, request: CommandRequest, decision: CortexDecision, context: dict[str, Any]) -> WorkflowPlan:
        text = request.normalized_text or request.raw_text
        lowered = text.lower()
        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
        if "viva" in lowered:
            return self._viva_plan(workflow_id, request, context)
        if "save" in lowered and "notion" in lowered and re.search(r"\b(today|work|activity|summary|summarize|summarise)\b", lowered):
            return self._activity_summary_plan(workflow_id, request, context)
        if "quiz" in lowered and ("notion" in lowered or "notes" in lowered or "operating systems" in lowered):
            return self._quiz_plan(workflow_id, request, context)
        return WorkflowPlan(
            workflow_id=workflow_id,
            request_id=request.request_id,
            session_id=request.session_id,
            goal=text,
            summary="Workflow planning is not available for this request yet.",
            steps=[],
            status="FAILED",
            risk_level="low",
            requires_confirmation=False,
            planner_evidence={"workflow_type": "unsupported_workflow"},
        )

    def _viva_plan(self, workflow_id: str, request: CommandRequest, context: dict[str, Any]) -> WorkflowPlan:
        repo = self._repo_name(request, context) or "current project"
        wants_notion = "notion" in request.normalized_text.lower() or "save" in request.normalized_text.lower()
        steps = [
            self._step("resolve_repo", "github.resolve_repository", {"repository": repo}, expected="Resolved repository"),
            self._step("summarize_repo", "github.summarize_repository", {"repository": repo}, depends=["resolve_repo"], expected="Repository summary"),
            self._step("viva_questions", "study.generate_viva_questions", {"repository": repo, "count": 15}, depends=["summarize_repo"], expected="Viva questions"),
            self._step("revision_notes", "study.generate_revision_notes", {"repository": repo}, depends=["summarize_repo"], expected="Revision notes"),
        ]
        if wants_notion:
            steps.append(
                self._step(
                    "save_notion",
                    "notion.create_page",
                    {"title": f"{repo} Viva Notes"},
                    depends=["viva_questions", "revision_notes"],
                    risk="medium",
                    confirm=True,
                    optional=True,
                    expected="Notion page",
                )
            )
        steps.append(self._step("study_pack", "ai.answer", {"task": "return study pack", "repository": repo}, depends=["viva_questions", "revision_notes"], expected="Study pack"))
        return self._plan(workflow_id, request, "github_project_viva", f"Prepare viva pack for {repo}", steps, wants_notion)

    def _activity_summary_plan(self, workflow_id: str, request: CommandRequest, context: dict[str, Any]) -> WorkflowPlan:
        repo = self._repo_name(request, context) or "current project"
        steps = [
            self._step("resolve_repo", "github.resolve_repository", {"repository": repo}, expected="Resolved repository"),
            self._step("commits", "github.list_commits", {"repository": repo, "period": "today"}, depends=["resolve_repo"], expected="Commits"),
            self._step("issues", "github.list_issues", {"repository": repo, "period": "today"}, depends=["resolve_repo"], expected="Issues"),
            self._step("pull_requests", "github.list_pull_requests", {"repository": repo, "period": "today"}, depends=["resolve_repo"], expected="Pull requests"),
            self._step("summary", "ai.summarize_activity", {"repository": repo}, depends=["commits", "issues", "pull_requests"], expected="Activity summary"),
            self._step("save_notion", "notion.create_page", {"title": f"{repo} Daily Work Summary"}, depends=["summary"], risk="medium", confirm=True, expected="Notion page"),
        ]
        return self._plan(workflow_id, request, "github_activity_summary", f"Summarize today's work on {repo}", steps, True)

    def _quiz_plan(self, workflow_id: str, request: CommandRequest, context: dict[str, Any]) -> WorkflowPlan:
        topic = "Operating Systems" if "operating systems" in request.normalized_text.lower() else "study notes"
        steps = [
            self._step("search_notes", "notion.search_pages", {"query": topic}, expected="Matching notes"),
            self._step("read_notes", "notion.get_page", {"query": topic}, depends=["search_notes"], expected="Note content"),
            self._step("quiz", "study.generate_quiz", {"topic": topic}, depends=["read_notes"], expected="Quiz"),
        ]
        return self._plan(workflow_id, request, "notion_study_quiz", f"Build quiz from {topic} notes", steps, False)

    def _plan(self, workflow_id: str, request: CommandRequest, workflow_type: str, summary: str, steps: list[WorkflowStep], needs_confirmation: bool) -> WorkflowPlan:
        return WorkflowPlan(
            workflow_id=workflow_id,
            request_id=request.request_id,
            session_id=request.session_id,
            goal=request.normalized_text,
            summary=summary,
            steps=steps[:6],
            risk_level="medium" if needs_confirmation else "low",
            requires_confirmation=needs_confirmation,
            planner_evidence={"workflow_type": workflow_type, "capabilities_considered": [step.capability for step in steps]},
        )

    def _step(self, step_id: str, capability: str, arguments: dict[str, Any], depends=None, risk="low", confirm=False, optional=False, expected="") -> WorkflowStep:
        definition = self.registry.get(capability)
        return WorkflowStep(
            step_id=step_id,
            capability=capability,
            arguments=arguments,
            depends_on=depends or [],
            risk_level=risk,  # type: ignore[arg-type]
            requires_confirmation=confirm,
            timeout_seconds=definition.timeout_seconds if definition else 20,
            retry_limit=1,
            optional=optional,
            expected_output=expected,
        )

    def _repo_name(self, request: CommandRequest, context: dict[str, Any]) -> str:
        text = request.normalized_text
        world = context.get("world_model") or {}
        resolved_repo = world.get("current_repository") or {}
        for entity in [resolved_repo, world.get("current_project") or {}]:
            if entity and entity.get("name"):
                return entity["name"]
        match = re.search(r"\b([A-Za-z][A-Za-z0-9_.-]{2,})\b(?=\s+(viva|project|repo|repository))", text)
        return match.group(1) if match else ""
