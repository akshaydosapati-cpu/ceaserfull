from __future__ import annotations

from typing import Any


class ConflictDetector:
    def detect(self, text: str, evidence: dict[str, Any]) -> list[str]:
        conflicts: list[str] = []
        active_project = str(evidence.get("active_project") or evidence.get("world_current_project") or "")
        for memory in evidence.get("long_term_memories") or []:
            if memory.get("type") == "project":
                project_name = str((memory.get("structured_data") or {}).get("project") or "")
                if active_project and project_name and active_project.lower() != project_name.lower():
                    conflicts.append("current_context_differs_from_long_term_memory")
                    break
        if evidence.get("world_ambiguity_candidates"):
            conflicts.append("multiple_projects_match")
        lowered = text.lower()
        if "do not save" in lowered and self._workflow_has_save_step(evidence):
            conflicts.append("user_requested_no_save_but_plan_contains_save")
        preview = evidence.get("preview_resource") or {}
        workflow = evidence.get("workflow_plan") or {}
        if preview and workflow:
            target = str(preview.get("name") or preview.get("title") or preview.get("id") or "").lower()
            step_targets = " ".join(str(step.get("arguments") or {}) for step in workflow.get("steps") or []).lower()
            if target and step_targets and target not in step_targets:
                conflicts.append("workflow_target_differs_from_preview")
        return conflicts

    def _workflow_has_save_step(self, evidence: dict[str, Any]) -> bool:
        workflow = evidence.get("workflow_plan") or {}
        for step in workflow.get("steps") or []:
            cap = str(step.get("capability") or "")
            if cap.startswith("notion.create") or cap.startswith("notion.append") or "save" in str(step.get("step_id") or ""):
                return True
        return False
