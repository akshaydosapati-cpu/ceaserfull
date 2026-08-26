from __future__ import annotations

import re
from typing import Any, Literal

from core.schemas import ActionResult, CommandRequest, IntentResult


ResponseProfile = Literal["standard", "study", "build", "founder", "focus"]


class AdaptiveResponsePolicy:
    """Adapts response shape without changing facts, execution or security state."""

    PROFILES: set[str] = {"standard", "study", "build", "founder", "focus"}

    def __init__(self) -> None:
        self.session_profiles: dict[str, ResponseProfile] = {}

    def apply(self, request: CommandRequest, intent: IntentResult | None, context: dict[str, Any], result: ActionResult) -> ActionResult:
        original_status = result.status
        original_verified = result.verified
        profile, reason = self.select_profile(request, intent, context)
        overlay = result.summary or result.spoken_response or ""
        spoken_source = result.spoken_response or overlay
        result.summary = self._overlay_response(profile, overlay)
        result.spoken_response = self._spoken_response(profile, spoken_source)
        result.evidence.setdefault("adaptive_response_profile", profile)
        result.evidence.setdefault("adaptive_response_reason", reason)
        result.status = original_status
        result.verified = original_verified
        return result

    def select_profile(self, request: CommandRequest, intent: IntentResult | None, context: dict[str, Any]) -> tuple[ResponseProfile, str]:
        explicit = self._explicit_profile(request.normalized_text or request.raw_text)
        if explicit:
            self.session_profiles[request.session_id] = explicit
            return explicit, "explicit_user_preference"
        memory_profile = self._memory_profile(context.get("long_term_memory") or {})
        if memory_profile:
            return memory_profile, "long_term_memory_preference"
        session_profile = self._session_profile(request, context)
        if session_profile:
            return session_profile, "current_session_mode"
        inferred = self._inferred_profile(request, intent, context)
        if inferred:
            return inferred, "inferred_from_context"
        return "standard", "default_standard"

    def _explicit_profile(self, text: str) -> ResponseProfile | None:
        lowered = str(text or "").lower()
        if re.search(r"\b(be brief|briefly|short answer|keep it short|focus mode|switch to focus mode)\b", lowered):
            return "focus"
        if re.search(r"\b(use simple language|explain simply|study mode|switch to study mode|teach me)\b", lowered):
            return "study"
        if re.search(r"\b(build mode|switch to build mode|technical mode|developer mode)\b", lowered):
            return "build"
        if re.search(r"\b(founder mode|startup mode|business mode)\b", lowered):
            return "founder"
        if re.search(r"\b(explain more|more detail|detailed answer|expand this)\b", lowered):
            return "standard"
        return None

    def _memory_profile(self, long_term_memory: dict[str, Any]) -> ResponseProfile | None:
        for item in long_term_memory.get("memories", []) or []:
            data = item.get("structured_data") or {}
            content = str(item.get("content") or "").lower()
            value = str(data.get("response_profile") or data.get("response_length") or "").lower()
            combined = f"{value} {content}"
            if "brief" in combined or "short" in combined:
                return "focus"
            if "simple" in combined or "study" in combined:
                return "study"
            if "technical" in combined or "build" in combined or "developer" in combined:
                return "build"
            if "founder" in combined or "business" in combined:
                return "founder"
        return None

    def _session_profile(self, request: CommandRequest, context: dict[str, Any]) -> ResponseProfile | None:
        explicit = str(context.get("response_profile") or context.get("session_mode") or "").lower()
        if explicit in self.PROFILES:
            profile = explicit  # type: ignore[assignment]
            self.session_profiles[request.session_id] = profile
            return profile
        return self.session_profiles.get(request.session_id)

    def _inferred_profile(self, request: CommandRequest, intent: IntentResult | None, context: dict[str, Any]) -> ResponseProfile | None:
        working = context.get("working_memory") or context.get("context_snapshot") or {}
        active_app = f"{working.get('active_app', '')} {working.get('active_window', '')} {working.get('current_editor', '')}".lower()
        project = f"{working.get('current_project', '')} {working.get('repository', '')} {working.get('github_repository', '')}".lower()
        text = f"{request.normalized_text} {intent.intent if intent else ''} {intent.capability if intent else ''}".lower()
        if re.search(r"\b(code|vscode|visual studio code|terminal|github|repo|commit|api|test|debug|python|react)\b", f"{active_app} {text}"):
            return "build"
        if re.search(r"\b(study|exam|quiz|lesson|learn|student|syllabus|homework)\b", f"{project} {text}"):
            return "study"
        if re.search(r"\b(startup|founder|pitch|investor|business|marketing|revenue|customer|launch)\b", f"{project} {text}"):
            return "founder"
        return None

    def _overlay_response(self, profile: ResponseProfile, text: str) -> str:
        content = str(text or "").strip()
        if not content:
            return content
        if profile == "focus":
            return self._first_sentence(content)
        if profile == "study":
            return self._ensure_sections(content, ["Simple explanation", "Steps", "Example", "Quick recap"])
        if profile == "build":
            return self._ensure_sections(content, ["Technical summary", "Implementation notes", "Tests or checks", "Trade-offs"])
        if profile == "founder":
            return self._ensure_sections(content, ["Priority", "Business impact", "Blockers", "Next action"])
        return content

    def _spoken_response(self, profile: ResponseProfile, text: str) -> str:
        content = str(text or "").strip()
        if not content:
            return content
        if profile == "focus":
            return self._first_sentence(content, max_chars=120)
        if profile in {"study", "founder", "build"}:
            return self._first_sentence(content, max_chars=180)
        return content if len(content) <= 220 else self._first_sentence(content, max_chars=220)

    def _ensure_sections(self, content: str, labels: list[str]) -> str:
        if any(label.lower() in content.lower() for label in labels):
            return content
        compact = content.strip()
        sections = [f"{labels[0]}: {compact}"]
        for label in labels[1:]:
            sections.append(f"{label}: Use the same information above for this view.")
        return "\n".join(sections)

    def _first_sentence(self, content: str, max_chars: int = 160) -> str:
        match = re.search(r"(.+?[.!?])(?:\s|$)", content.strip(), re.DOTALL)
        sentence = (match.group(1) if match else content).strip()
        if len(sentence) <= max_chars:
            return sentence
        return sentence[: max_chars - 1].rstrip() + "."
