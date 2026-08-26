from __future__ import annotations

import hashlib
import re
import time
from typing import Any

from core.schemas import CommandRequest
from prediction.models import Prediction, PredictionContext, PreparationTask
from prediction.preparation_cache import PreparationCache


class PredictionEngine:
    """Minimal Stage 14 predictor.

    It may recommend and prepare read-only context, but it never executes,
    mutates user data, speaks, or starts workflows.
    """

    MIN_CONFIDENCE = 0.6

    def __init__(self, cache: PreparationCache | None = None, ttl_seconds: int = 300) -> None:
        self.cache = cache or PreparationCache()
        self.ttl_seconds = ttl_seconds

    def as_context(
        self,
        request: CommandRequest,
        working_memory: dict[str, Any] | None = None,
        world_model: dict[str, Any] | None = None,
        awareness: dict[str, Any] | None = None,
        experience: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        working_memory = working_memory or {}
        world_model = world_model or {}
        awareness = awareness or {}
        experience = experience or {}
        predictions: list[Prediction] = []
        preparations: dict[str, Any] = {}

        for prediction, task in self._rules(request, working_memory, world_model, awareness, experience):
            if prediction.confidence < self.MIN_CONFIDENCE:
                continue
            predictions.append(prediction)
            if task:
                preparations[task.key] = self.cache.prepare(task).model_dump()

        return PredictionContext(
            predictions=[self._dump(item) for item in predictions],
            preparation=preparations,
            cache=self.cache.stats(),
            summary=self._summary(predictions),
        ).as_context()

    def _rules(
        self,
        request: CommandRequest,
        working_memory: dict[str, Any],
        world_model: dict[str, Any],
        awareness: dict[str, Any],
        experience: dict[str, Any],
    ) -> list[tuple[Prediction, PreparationTask | None]]:
        rules: list[tuple[Prediction, PreparationTask | None]] = []
        repo = self._active_repository(working_memory, world_model, awareness)
        active_app = self._active_app(working_memory, awareness)
        if repo and self._is_vscode(active_app):
            key = f"git_activity:{repo.lower()}"
            rules.append(
                (
                    self._prediction(
                        type="next_capability",
                        label="Prepare Git activity",
                        confidence=0.82,
                        evidence=["active_app_is_vscode", "active_repository_detected"],
                        likely_capability="github.list_commits",
                        preparation_key=key,
                    ),
                    PreparationTask(
                        key=key,
                        kind="git_activity",
                        description="Prepare Git status and recent commits for the active repository.",
                        provider="github",
                        payload={"repository": repo},
                        ttl_seconds=self.ttl_seconds,
                    ),
                )
            )

        for workflow in experience.get("repeated_workflows", []) or []:
            workflow_type = str((workflow.get("metadata") or {}).get("workflow_type") or "")
            label = str(workflow.get("label") or "")
            count = int(workflow.get("count") or 0)
            confidence = min(0.9, 0.55 + (count * 0.08))
            if self._is_github_summary_workflow(workflow_type, label):
                workflow_repo = repo or str((workflow.get("metadata") or {}).get("active_project") or "")
                key = f"repository_activity:{workflow_repo.lower() or 'default'}"
                rules.append(
                    (
                        self._prediction(
                            type="next_workflow",
                            label="Prepare repository activity",
                            confidence=confidence,
                            evidence=["repeated_github_summary_workflow", f"workflow_count={count}"],
                            likely_workflow="github_activity_summary",
                            preparation_key=key,
                        ),
                        PreparationTask(
                            key=key,
                            kind="repository_activity",
                            description="Prepare repository activity for a likely GitHub summary workflow.",
                            provider="github",
                            payload={"repository": workflow_repo},
                            ttl_seconds=self.ttl_seconds,
                        ),
                    )
                )
            if self._is_notion_study_workflow(workflow_type, label):
                key = "notion_study_metadata:recent"
                rules.append(
                    (
                        self._prediction(
                            type="next_workflow",
                            label="Prepare Notion study metadata",
                            confidence=confidence,
                            evidence=["repeated_notion_study_workflow", f"workflow_count={count}"],
                            likely_workflow="notion_study_review",
                            preparation_key=key,
                        ),
                        PreparationTask(
                            key=key,
                            kind="notion_study_metadata",
                            description="Prepare recent Notion study page metadata.",
                            provider="notion",
                            payload={"workspace": self._workspace_name(world_model)},
                            ttl_seconds=self.ttl_seconds,
                        ),
                    )
                )

        repeated_commands = experience.get("repeated_commands", []) or []
        if repeated_commands:
            command = repeated_commands[0]
            count = int(command.get("count") or 0)
            confidence = min(0.85, 0.45 + (count * 0.1))
            rules.append(
                (
                    self._prediction(
                        type="next_command",
                        label="Recommend next command",
                        confidence=confidence,
                        evidence=["repeated_command_sequence", f"command_count={count}"],
                        likely_command=str(command.get("label") or ""),
                    ),
                    None,
                )
            )

        return rules

    def _prediction(self, **kwargs: Any) -> Prediction:
        now = time.time()
        stable = f"{kwargs.get('type')}:{kwargs.get('label')}:{kwargs.get('likely_capability')}:{kwargs.get('likely_workflow')}:{kwargs.get('likely_command')}"
        return Prediction(id="pred_" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16], expires_at=now + self.ttl_seconds, created_at=now, **kwargs)

    def _active_app(self, working_memory: dict[str, Any], awareness: dict[str, Any]) -> str:
        if working_memory.get("active_app"):
            return str(working_memory.get("active_app"))
        if working_memory.get("foreground_app"):
            return str(working_memory.get("foreground_app"))
        for event in awareness.get("recent_events", []) or []:
            payload = event.get("payload") or {}
            app_name = payload.get("active_app") or payload.get("app") or payload.get("process")
            if app_name:
                return str(app_name)
        return ""

    def _active_repository(self, working_memory: dict[str, Any], world_model: dict[str, Any], awareness: dict[str, Any]) -> str:
        candidates = [
            working_memory.get("repository"),
            working_memory.get("github_repository"),
            working_memory.get("current_repository"),
            working_memory.get("current_project"),
            world_model.get("active_repository"),
            world_model.get("current_repository"),
        ]
        for event in awareness.get("recent_events", []) or []:
            payload = event.get("payload") or {}
            candidates.append(payload.get("repository"))
            candidates.append(payload.get("repo"))
        for candidate in candidates:
            if candidate:
                if isinstance(candidate, dict):
                    return str(candidate.get("name") or candidate.get("full_name") or "")
                return str(candidate)
        return ""

    def _workspace_name(self, world_model: dict[str, Any]) -> str:
        workspace = world_model.get("active_workspace") or world_model.get("current_workspace") or ""
        if isinstance(workspace, dict):
            return str(workspace.get("name") or "")
        return str(workspace)

    def _is_vscode(self, active_app: str) -> bool:
        return bool(re.search(r"\b(code|vscode|visual studio code)\b", active_app, re.IGNORECASE))

    def _is_github_summary_workflow(self, workflow_type: str, label: str) -> bool:
        text = f"{workflow_type} {label}".lower()
        return "github" in text and any(word in text for word in ("summary", "summarize", "activity", "commits"))

    def _is_notion_study_workflow(self, workflow_type: str, label: str) -> bool:
        text = f"{workflow_type} {label}".lower()
        return "notion" in text and any(word in text for word in ("study", "notes", "quiz", "learning", "review"))

    def _summary(self, predictions: list[Prediction]) -> str:
        if not predictions:
            return "no_prediction"
        return ", ".join(prediction.label for prediction in predictions[:3])

    def _dump(self, item: Prediction) -> dict[str, Any]:
        return item.model_dump() if hasattr(item, "model_dump") else item.dict()
