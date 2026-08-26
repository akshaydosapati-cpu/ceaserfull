from __future__ import annotations

import time
from typing import Any

from core.schemas import ActionResult, CommandRequest, IntentResult
from planning.confirmation_manager import ConfirmationManager
from planning.models import StepResult, WorkflowPlan, WorkflowRun
from planning.plan_validator import PlanValidator
from planning.result_aggregator import ResultAggregator
from planning.workflow_store import WorkflowStore


class WorkflowRunner:
    def __init__(self, execution_engine, validator: PlanValidator, confirmations: ConfirmationManager | None = None, store: WorkflowStore | None = None) -> None:
        self.execution_engine = execution_engine
        self.validator = validator
        self.confirmations = confirmations or ConfirmationManager()
        self.store = store or WorkflowStore()
        self.aggregator = ResultAggregator()
        self.events: list[dict[str, Any]] = []
        self.cancelled: set[str] = set()

    def cancel(self, workflow_id: str) -> None:
        self.cancelled.add(workflow_id)

    def has_pending(self, session_id: str) -> bool:
        return self.store.pending_for_session(session_id) is not None

    def cancel_pending(self, session_id: str) -> ActionResult:
        run = self.store.pending_for_session(session_id)
        if not run:
            return ActionResult(status="failed", capability="workflow.plan", summary="There is no workflow waiting for confirmation.", verified=True, error_code="no_pending_workflow")
        run.status = "CANCELLED"
        run.cancelled = True
        self.store.save_run(run)
        self._event("workflow_cancelled", run.workflow_id, run.pending_step_id, "Cancelled by user.", 0, len(run.plan.steps), "CANCELLED")
        return ActionResult(status="cancelled", capability="workflow.plan", summary="Workflow cancelled.", spoken_response="Cancelled.", verified=True, evidence={"workflow_id": run.workflow_id, "events": self.events})

    def resume(self, request: CommandRequest, context: dict[str, Any]) -> ActionResult:
        run = self.store.pending_for_session(request.session_id)
        if not run:
            return ActionResult(status="failed", capability="workflow.plan", summary="There is no workflow waiting for confirmation.", verified=True, error_code="no_pending_workflow")
        if not self.confirmations.approve(run.pending_confirmation_id, run.workflow_id, run.pending_step_id):
            run.status = "FAILED"
            self.store.save_run(run)
            return ActionResult(status="failed", capability="workflow.plan", summary="That confirmation expired or no longer matches this workflow.", verified=True, error_code="confirmation_rejected", evidence={"workflow_id": run.workflow_id})
        run.approved_steps.append(run.pending_step_id)
        start_index = next((idx for idx, step in enumerate(run.plan.steps) if step.step_id == run.pending_step_id), 0)
        run.pending_step_id = ""
        run.pending_confirmation_id = ""
        run.status = "RUNNING"
        self.store.save_run(run)
        self._event("workflow_started", run.workflow_id, label="Confirmation approved. Resuming workflow.", current=start_index, total=len(run.plan.steps), status="RUNNING")
        return self._continue_run(request, run, context, start_index=start_index)

    def run(self, request: CommandRequest, plan: WorkflowPlan, context: dict[str, Any]) -> ActionResult:
        ok, errors = self.validator.validate(plan)
        self.store.save_plan(plan)
        self._event("workflow_planned", plan.workflow_id, label=plan.summary, current=0, total=len(plan.steps), status=plan.status)
        if not ok:
            return ActionResult(status="failed", capability="workflow.plan", summary="Workflow plan is invalid.", verified=True, error_code="invalid_workflow_plan", evidence={"validation_errors": errors})

        run = WorkflowRun(workflow_id=plan.workflow_id, plan=plan, status="RUNNING", started_at=time.time())
        self.store.save_run(run)
        self._event("workflow_started", plan.workflow_id, label=plan.summary, current=0, total=len(plan.steps), status="RUNNING")
        return self._continue_run(request, run, context, start_index=0)

    def _continue_run(self, request: CommandRequest, run: WorkflowRun, context: dict[str, Any], start_index: int = 0) -> ActionResult:
        plan = run.plan
        completed: set[str] = set()
        failed: set[str] = set()
        for item in run.step_results:
            if item.status == "completed":
                completed.add(item.step_id)
            elif item.status == "failed" and not item.skipped:
                failed.add(item.step_id)

        for index, step in list(enumerate(plan.steps, start=1))[start_index:]:
            if plan.workflow_id in self.cancelled:
                run.status = "CANCELLED"
                self._event("workflow_cancelled", plan.workflow_id, step.step_id, step.capability, index, len(plan.steps), "CANCELLED")
                return ActionResult(status="cancelled", capability="workflow.plan", summary="Workflow cancelled.", verified=True, evidence={"workflow_id": plan.workflow_id, "events": self.events})

            blocked = [dep for dep in step.depends_on if dep in failed or dep not in completed]
            if blocked:
                status = "skipped_optional" if step.optional else "blocked"
                run.step_results.append(StepResult(step_id=step.step_id, capability=step.capability, status="skipped", skipped=True, warning=f"blocked_by:{','.join(blocked)}"))
                if not step.optional:
                    failed.add(step.step_id)
                continue

            if step.requires_confirmation and step.step_id not in run.approved_steps:
                confirmation = self.confirmations.create(plan.workflow_id, step)
                run.status = "WAITING_FOR_CONFIRMATION"
                run.pending_step_id = step.step_id
                run.pending_confirmation_id = confirmation.confirmation_id
                self.store.save_run(run)
                self._event("workflow_waiting_confirmation", plan.workflow_id, step.step_id, confirmation.preview, index, len(plan.steps), "WAITING_FOR_CONFIRMATION")
                confirmation_payload = confirmation.model_dump() if hasattr(confirmation, "model_dump") else confirmation.dict()
                return ActionResult(
                    status="needs_confirmation",
                    capability="workflow.plan",
                    summary=confirmation.preview,
                    spoken_response=confirmation.preview,
                    data={"pending_confirmation": confirmation_payload},
                    evidence={"workflow_id": plan.workflow_id, "pending_step_id": step.step_id, "events": self.events, **plan.planner_evidence},
                    verified=True,
                    confirmation=confirmation_payload,
                )

            result = self._execute_step(request, step, context, index, len(plan.steps), approved=step.step_id in run.approved_steps)
            run.step_results.append(result)
            if result.status == "completed":
                completed.add(step.step_id)
            elif step.optional:
                failed.add(step.step_id)
            else:
                failed.add(step.step_id)

        workflow_result = self.aggregator.aggregate(plan, run.step_results)
        run.status = workflow_result.status
        run.completed_at = time.time()
        self.store.save_run(run)
        event_name = {"COMPLETED": "workflow_completed", "PARTIAL": "workflow_partial", "FAILED": "workflow_failed"}.get(workflow_result.status, "workflow_failed")
        self._event(event_name, plan.workflow_id, label=workflow_result.display_summary, current=len(workflow_result.completed_steps), total=len(plan.steps), status=workflow_result.status)
        action_status = "completed" if workflow_result.status == "COMPLETED" else "partial" if workflow_result.status == "PARTIAL" else "failed"
        return ActionResult(
            status=action_status,  # type: ignore[arg-type]
            capability="workflow.plan",
            summary=workflow_result.display_summary,
            spoken_response=workflow_result.spoken_response,
            data={"workflow_result": workflow_result.model_dump() if hasattr(workflow_result, "model_dump") else workflow_result.dict()},
            evidence={"workflow_id": plan.workflow_id, "events": self.events, **plan.planner_evidence},
            warnings=workflow_result.warnings,
            verified=workflow_result.verified,
        )

    def _execute_step(self, request: CommandRequest, step, context: dict[str, Any], index: int, total: int, approved: bool = False) -> StepResult:
        self._event("workflow_step_started", request.session_id, step.step_id, step.capability, index, total, "RUNNING")
        self._event("workflow_progress", request.session_id, step.step_id, step.expected_output or step.capability, index, total, "RUNNING")
        attempts = 0
        last_result = None
        while attempts <= step.retry_limit:
            attempts += 1
            update = {"normalized_text": self._step_text(step), "raw_text": self._step_text(step), "request_id": f"{request.request_id}_{step.step_id}_{attempts}"}
            step_request = request.model_copy(update=update) if hasattr(request, "model_copy") else request.copy(update=update)
            intent = IntentResult(intent=step.step_id, capability=step.capability, confidence=0.9, route=self._route_for(step.capability), entities=step.arguments)
            step_context = dict(context or {})
            if approved:
                step_context["reasoning_confirmation_approved"] = True
                step_context["approved_workflow_step_id"] = step.step_id
            last_result = self.execution_engine.execute(step_request, intent, step_context)
            if last_result.status == "completed" and last_result.verified:
                self._event("workflow_step_completed", request.session_id, step.step_id, last_result.summary, index, total, "COMPLETED")
                return StepResult(step_id=step.step_id, capability=step.capability, status="completed", result=last_result, attempts=attempts)
            if not last_result.retryable:
                break
        self._event("workflow_step_failed", request.session_id, step.step_id, last_result.summary if last_result else step.capability, index, total, "FAILED")
        return StepResult(step_id=step.step_id, capability=step.capability, status="failed", result=last_result, attempts=attempts)

    def _route_for(self, capability: str):
        if capability.startswith("github.") or capability.startswith("notion."):
            return "integration"
        if capability.startswith("desktop."):
            return "desktop"
        return "backend_ai"

    def _step_text(self, step) -> str:
        return f"{step.capability} {step.arguments}"

    def _event(self, event: str, workflow_id: str, step_id: str = "", label: str = "", current: int = 0, total: int = 0, status: str = "") -> None:
        self.events.append({"event": event, "workflow_id": workflow_id, "step_id": step_id, "label": label, "current": current, "total": total, "status": status, "summary": label})
