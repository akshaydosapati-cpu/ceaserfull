from __future__ import annotations

from planning.models import StepResult, WorkflowPlan, WorkflowResult


class ResultAggregator:
    def aggregate(self, plan: WorkflowPlan, step_results: list[StepResult]) -> WorkflowResult:
        completed = [item.step_id for item in step_results if item.status == "completed"]
        failed = [item.step_id for item in step_results if item.status == "failed"]
        skipped = [item.step_id for item in step_results if item.skipped]
        required_failed = [step.step_id for step in plan.steps if not step.optional and step.step_id in failed]
        optional_failed = [step.step_id for step in plan.steps if step.optional and step.step_id in failed]
        if required_failed:
            status = "FAILED"
        elif optional_failed or skipped:
            status = "PARTIAL"
        else:
            status = "COMPLETED"
        partial_results = []
        created_resources = []
        modified_resources = []
        for item in step_results:
            if item.result:
                partial_results.append({"step_id": item.step_id, "summary": item.result.summary, "status": item.result.status})
                if item.result.data.get("created_resource"):
                    created_resources.append(item.result.data["created_resource"])
                if item.result.data.get("modified_resource"):
                    modified_resources.append(item.result.data["modified_resource"])
        return WorkflowResult(
            status=status,
            goal=plan.goal,
            completed_steps=completed,
            failed_steps=failed,
            skipped_steps=skipped,
            partial_results=partial_results,
            created_resources=created_resources,
            modified_resources=modified_resources,
            evidence={"workflow_id": plan.workflow_id, "step_count": len(plan.steps)},
            warnings=[item.warning for item in step_results if item.warning],
            spoken_response=self._spoken(status, plan, completed, failed),
            display_summary=self._display(status, plan, completed, failed),
            verified=status == "COMPLETED" and len(completed) == len(plan.steps),
        )

    def _spoken(self, status: str, plan: WorkflowPlan, completed: list[str], failed: list[str]) -> str:
        if status == "COMPLETED":
            return f"I completed {len(completed)} steps for {plan.summary}."
        if status == "PARTIAL":
            return f"I completed part of {plan.summary}. Some optional steps need attention."
        return f"I could not complete {plan.summary}. {len(failed)} step failed."

    def _display(self, status: str, plan: WorkflowPlan, completed: list[str], failed: list[str]) -> str:
        return f"{plan.summary}\nStatus: {status}\nCompleted steps: {len(completed)}\nFailed steps: {len(failed)}"
