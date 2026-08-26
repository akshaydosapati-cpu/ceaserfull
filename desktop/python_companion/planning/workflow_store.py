from __future__ import annotations

from planning.models import WorkflowPlan, WorkflowRun


class WorkflowStore:
    def __init__(self) -> None:
        self.plans: dict[str, WorkflowPlan] = {}
        self.runs: dict[str, WorkflowRun] = {}

    def save_plan(self, plan: WorkflowPlan) -> WorkflowPlan:
        self.plans[plan.workflow_id] = plan
        return plan

    def save_run(self, run: WorkflowRun) -> WorkflowRun:
        self.runs[run.workflow_id] = run
        return run

    def get_plan(self, workflow_id: str) -> WorkflowPlan | None:
        return self.plans.get(workflow_id)

    def get_run(self, workflow_id: str) -> WorkflowRun | None:
        return self.runs.get(workflow_id)

    def pending_for_session(self, session_id: str) -> WorkflowRun | None:
        for run in sorted(self.runs.values(), key=lambda item: item.started_at or 0, reverse=True):
            if run.plan.session_id == session_id and run.status == "WAITING_FOR_CONFIRMATION" and run.pending_confirmation_id:
                return run
        return None
