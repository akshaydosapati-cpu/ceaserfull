from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from conversation.companion_models import CompanionPreferences, LanguageAnalysis, PersonalityPlan
from conversation.language_analyzer import LanguageAnalyzer
from core.schemas import ActionResult, CommandRequest, IntentResult


class CompanionPersonalityEngine:
    """Plans bounded delivery and optionally composes wording through the existing model path."""

    def __init__(self, generator: Callable[[str, str], str] | None = None) -> None:
        self.generator = generator
        self.language_analyzer = LanguageAnalyzer()

    def preferences(self, context: dict[str, Any]) -> CompanionPreferences:
        raw = dict(context.get("companion_preferences") or {})
        for item in (context.get("long_term_memory") or {}).get("memories", []) or []:
            structured = item.get("structured_data") or {}
            if structured.get("companion_preferences"):
                raw = {**structured["companion_preferences"], **raw}
        try:
            return CompanionPreferences.model_validate(raw)
        except Exception:
            return CompanionPreferences()

    def plan(self, request: CommandRequest, intent: IntentResult | None, context: dict[str, Any], result: ActionResult) -> tuple[PersonalityPlan, LanguageAnalysis]:
        preferences = self.preferences(context)
        stt = dict(context.get("stt") or request.metadata.get("stt") or {})
        language_text = str(stt.get("original_transcript") or request.raw_text)
        language = self.language_analyzer.analyze_provider(
            language_text,
            str(stt.get("detected_language") or stt.get("language") or ""),
            preferences,
        )
        destination = str(result.evidence.get("cortex_destination") or (intent.route if intent else ""))
        serious = bool(result.evidence.get("sensitive") or result.evidence.get("urgent") or result.evidence.get("safety_incident"))
        failed = result.status in {"failed", "needs_confirmation", "needs_input"}
        contextual_mode = str((context.get("conversation_state") or {}).get("conversation_mode") or context.get("conversation_mode") or "").lower()
        valid_modes = {"casual", "playful", "work", "focused", "serious", "sensitive", "urgent", "celebratory"}
        mode = contextual_mode if contextual_mode in valid_modes else "work" if destination not in {"conversation", "backend_ai"} else "casual"
        if serious:
            mode = "urgent" if result.evidence.get("urgent") else "sensitive"
        elif failed:
            mode = "serious"
        if str(context.get("session_mode") or "").lower() in {"focus", "focused"}:
            mode = "focused"
        humor_levels = {"off": 0.0, "low": 0.15, "medium": 0.4, "high": 0.7}
        roast_levels = {"off": 0.0, "light": 0.2, "medium": 0.4}
        humor = 0.0 if serious or failed or mode in {"focused", "urgent"} else humor_levels[preferences.humor]
        sarcasm = 0.0 if serious or failed else roast_levels[preferences.roasting]
        plan = PersonalityPlan(
            mode=mode,
            warmth=0.85 if mode == "sensitive" else 0.65,
            humor=humor,
            sarcasm=sarcasm,
            formality=0.7 if preferences.conversation_style == "professional" else 0.15,
            initiative=0.2 if mode in {"focused", "urgent", "sensitive"} else 0.45,
            familiarity=float((context.get("conversation_state") or {}).get("familiarity") or 0.25),
            energy=0.75 if mode == "celebratory" else 0.35 if mode in {"serious", "sensitive"} else 0.55,
            verbosity="short" if mode in {"focused", "urgent"} else "balanced",
            humor_allowed=humor > 0,
            roasting_allowed=sarcasm > 0,
        )
        return plan, language

    def compose(self, request: CommandRequest, intent: IntentResult | None, context: dict[str, Any], result: ActionResult) -> ActionResult:
        status, verified, raw_summary = result.status, result.verified, result.summary
        plan, language = self.plan(request, intent, context, result)
        result.evidence["companion"] = {"mode": plan.mode, "language": language.model_dump(), "tone": {"warmth": plan.warmth, "humor": plan.humor, "formality": plan.formality}}
        if self.generator and raw_summary:
            instructions = (
                "Present the truthful CEASER result naturally. Preserve status, facts, errors, numbers, sources, warnings, and critical technical detail. "
                "Never claim an action succeeded unless the raw result says it did. Generate directly in the requested language/register; do not translate a prewritten joke. "
                "Use a confident calm male CEASER persona. Avoid customer-support clichés. Humor is optional and bounded by the supplied plan."
            )
            payload = json.dumps({"user_message": request.raw_text, "raw_result": raw_summary, "status": status, "verified": verified, "personality": plan.model_dump(), "language": language.model_dump(), "recent_context": (context.get("session") or {}).get("recent_turns", [])[-4:]}, ensure_ascii=False)
            try:
                composed = str(self.generator(instructions, payload) or "").strip()
                if composed:
                    result.summary = composed
                    result.spoken_response = composed if len(composed) <= 220 else composed[:217].rstrip() + "..."
            except Exception:
                result.evidence["companion_fallback"] = True
        result.status, result.verified = status, verified
        return result
