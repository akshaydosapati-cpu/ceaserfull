from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from capabilities.registry import CapabilityRegistry
from core.schemas import ActionResult


@dataclass(frozen=True)
class NextActionSuggestion:
    label: str
    command: str
    capability: str
    confidence: float
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class NextActionPolicy:
    """Offers capability-backed next actions after an already-finished result."""

    ACTIVE_KEY = "active_suggested_action"
    ACTIVE_TTL_SECONDS = 120
    AFFIRMATIVE = {"yes", "yeah", "yep", "do it", "go ahead", "please do"}
    NEGATIVE = {"no", "not now", "never mind"}
    SIMPLE_CAPABILITIES = {"desktop.set_volume", "desktop.get_battery", "desktop.media_play_pause"}

    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    def suggest(self, result: ActionResult, context: dict[str, Any]) -> list[NextActionSuggestion]:
        if self._suppressed(result, context):
            return []

        candidate = self._predicted_candidate(context) or self._mapped_candidate(result, context)
        if not candidate or candidate.confidence < 0.55 or not self.registry.get(candidate.capability):
            return []
        return [candidate]

    def attach(self, result: ActionResult, context: dict[str, Any]) -> list[dict[str, Any]]:
        suggestions = self.suggest(result, context)
        if not suggestions:
            return []

        overlay = [item.as_dict() for item in suggestions[:2]]
        result.evidence["next_actions"] = overlay
        result.evidence["next_action_source"] = "prediction" if self._predicted_candidate(context) else "deterministic"
        best = suggestions[0]
        if best.confidence >= 0.80:
            spoken = f"Want me to {best.label.lower()}?"
            existing = (result.spoken_response or result.summary or "").strip()
            result.spoken_response = f"{existing} {spoken}".strip()
            result.evidence["spoken_next_action"] = best.as_dict()
        self.store_active(context, best)
        return overlay

    def active(self, context: dict[str, Any]) -> dict[str, Any] | None:
        manager = self._working_memory_manager(context)
        if not manager:
            return None
        value = manager.store.get("conversation", self.ACTIVE_KEY)
        return value if isinstance(value, dict) else None

    def store_active(self, context: dict[str, Any], suggestion: NextActionSuggestion) -> None:
        manager = self._working_memory_manager(context)
        if manager:
            manager.store.set(
                "conversation",
                self.ACTIVE_KEY,
                suggestion.as_dict(),
                ttl_seconds=self.ACTIVE_TTL_SECONDS,
                source="next_action_policy",
            )

    def clear_active(self, context: dict[str, Any]) -> None:
        manager = self._working_memory_manager(context)
        if manager:
            manager.store.set("conversation", self.ACTIVE_KEY, None, ttl_seconds=1, source="next_action_policy")

    def is_affirmative(self, text: str) -> bool:
        return str(text or "").strip().lower() in self.AFFIRMATIVE

    def is_negative(self, text: str) -> bool:
        return str(text or "").strip().lower() in self.NEGATIVE

    def _suppressed(self, result: ActionResult, context: dict[str, Any]) -> bool:
        profile = str(result.evidence.get("adaptive_response_profile") or context.get("response_profile") or "").lower()
        if profile == "focus" or context.get("suggestion_follow_up"):
            return True
        if self._has_pending_confirmation(context):
            return True
        if result.status == "failed":
            return not result.retryable or not result.capability
        if not (result.status == "completed" and result.verified):
            return True
        if result.capability in self.SIMPLE_CAPABILITIES:
            return True
        if result.capability in {"desktop.open_application", "app.open"} and "calculator" in result.summary.lower():
            return True
        return False

    def _predicted_candidate(self, context: dict[str, Any]) -> NextActionSuggestion | None:
        for prediction in (context.get("prediction") or {}).get("predictions", []) or []:
            confidence = float(prediction.get("confidence") or 0)
            capability = str(prediction.get("likely_capability") or "")
            command = str(prediction.get("likely_command") or "")
            if not capability and command:
                capability = self._capability_for_command(command)
            if confidence >= 0.80 and capability and command and self.registry.get(capability):
                return NextActionSuggestion(
                    label=str(prediction.get("label") or command),
                    command=command,
                    capability=capability,
                    confidence=confidence,
                    reason="high_confidence_prediction",
                )
        return None

    def _mapped_candidate(self, result: ActionResult, context: dict[str, Any]) -> NextActionSuggestion | None:
        capability = result.capability or ""
        text = f"{result.summary} {result.data}".lower()
        if result.status == "failed" and result.retryable and capability:
            return NextActionSuggestion("Try again", str(context.get("last_command") or "Try again"), capability, 0.62, "safe_retry_after_failure")
        if capability in {"desktop.take_screenshot", "screen.capture_all"}:
            return NextActionSuggestion("Analyze the screenshot", "Analyze the screenshot I just took.", "ai.answer", 0.82, "screenshot_captured")
        if capability in {"cloud.read", "study.generate_revision_notes"} or "document summary" in text or "pdf summary" in text:
            return NextActionSuggestion("Create a short quiz", "Create a short quiz from the document summary.", "study.generate_quiz", 0.84, "document_study_follow_up")
        if capability.startswith("github.") or "github" in capability:
            if self.registry.get("notion.append_blocks"):
                return NextActionSuggestion("Save the summary to Notion", "Save this GitHub summary to Notion.", "notion.append_blocks", 0.82, "github_activity_follow_up")
            return NextActionSuggestion("Summarize repository activity", "Summarize the repository activity.", "ai.summarize_activity", 0.70, "github_activity_follow_up")
        if capability in {"desktop.open_application", "app.open"} and any(term in text for term in ("repository", "project", "ceaser")):
            return NextActionSuggestion("Show recent commits", "Show recent commits for the active repository.", "github.list_commits", 0.82, "repository_opened")
        if capability in {"cloud.create", "notion.create_page"} or "file created" in text or "document created" in text:
            return NextActionSuggestion("Open the file", "Open the file I just created.", "desktop.open_file", 0.70, "file_created")
        return None

    def _capability_for_command(self, command: str) -> str:
        lowered = command.lower()
        if "commit" in lowered:
            return "github.list_commits"
        if "repository" in lowered:
            return "github.summarize_repository"
        if "notion" in lowered:
            return "notion.search_pages"
        return ""

    def _has_pending_confirmation(self, context: dict[str, Any]) -> bool:
        working = context.get("working_memory") or context.get("context_snapshot") or {}
        return bool(context.get("pending_confirmation") or working.get("pending_confirmation"))

    def _working_memory_manager(self, context: dict[str, Any]):
        return context.get("_working_memory_manager")
