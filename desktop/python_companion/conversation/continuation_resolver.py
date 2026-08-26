from __future__ import annotations

import re
from typing import Any


class ConversationContinuationResolver:
    """Resolve short conversational turns before command routing.

    This intentionally uses only active session and working context. Long-term
    memory is not a fallback for an ambiguous reference to the current chat.
    """

    EXPLICIT_COMMAND = re.compile(
        r"^\s*(?:open|launch|start|run|close|quit|exit|search|google|look up|set volume|mute|unmute|take (?:a )?screenshot|remember|forget|show my memories|list memories)\b",
        re.IGNORECASE,
    )
    SELF_CONTAINED_REQUEST = re.compile(
        r"^\s*(?:prepare|create|generate|build|draft|write|plan|organize|analy[sz]e)\b",
        re.IGNORECASE,
    )
    CONTINUATION = re.compile(
        r"^(?:summari[sz](?:e|ed)|make (?:it )?(?:shorter|longer)|explain (?:that|this|it|the (?:second|previous) point)|"
        r"why\??|continue|tell me more|what about\b.*|rewrite (?:this|that|it)|"
        r"make (?:this|that|it)? ?(?:professional|casual)|translate (?:this|that|it)|save (?:this|that|it)|do that)$|"
        r"\b(?:this|that|it|them|previous|last|second point|previous point)\b",
        re.IGNORECASE,
    )
    AFFIRMATIVE = re.compile(r"^(?:yes|yeah|yep|confirm|go ahead|do it|please do|approve)$", re.IGNORECASE)
    NEGATIVE = re.compile(r"^(?:no|not now|never mind|cancel|stop|abort)$", re.IGNORECASE)

    def resolve(self, text: str, session: dict[str, Any], working: dict[str, Any]) -> dict[str, Any]:
        command = re.sub(r"\s+", " ", str(text or "").strip())
        # A complete new task can contain words such as "it" (for example,
        # "prepare a viva pack and save it to Notion"). It must be planned as
        # a new workflow rather than treated as a dangling reference.
        if not command or self.EXPLICIT_COMMAND.search(command) or self.SELF_CONTAINED_REQUEST.search(command):
            return {"follow_up_detected": False, "resolved_reference": None}

        pending = working.get("pending_confirmation") or working.get("pending_memory_confirmation")
        if (self.AFFIRMATIVE.fullmatch(command) or self.NEGATIVE.fullmatch(command)) and pending:
            return {
                "follow_up_detected": True,
                "continuation_kind": "pending_confirmation",
                "resolved_reference": {"pending_confirmation": pending},
            }

        if session.get("last_intent") == "proactive_event" and re.fullmatch(
            r"(?:seriously|really|is that so|what happened|how so|tell me about it|go on|and then|okay|ok)\??",
            command,
            re.IGNORECASE,
        ):
            last_result = session.get("last_result") or {}
            return {
                "follow_up_detected": True,
                "continuation_kind": "proactive_thread",
                "resolved_reference": {
                    "last_intent": "proactive_event",
                    "last_capability": session.get("last_capability"),
                    "last_summary": str(last_result.get("summary") or ""),
                    "recent_turns": list(session.get("recent_turns") or [])[-6:],
                },
            }

        if not self.CONTINUATION.search(command):
            return {"follow_up_detected": False, "resolved_reference": None}

        last_result = session.get("last_result") or {}
        last_summary = str(last_result.get("summary") or working.get("previous_response") or "").strip()
        active_resource = working.get("active_resource") or session.get("active_resource") or {}
        active_project = working.get("current_project") or session.get("active_project") or ""
        recent_turns = list(session.get("recent_turns") or [])[-6:]
        has_context = bool(last_summary or active_resource or active_project or recent_turns)
        if not has_context:
            return {
                "follow_up_detected": False,
                "clarification_required": True,
                "clarification_question": "What should I continue from?",
                "resolved_reference": None,
            }

        return {
            "follow_up_detected": True,
            "continuation_kind": self._kind(command),
            "resolved_reference": {
                "last_intent": session.get("last_intent"),
                "last_capability": session.get("last_capability") or working.get("last_capability"),
                "last_summary": last_summary,
                "active_resource": active_resource,
                "active_project": active_project,
                "recent_turns": recent_turns,
            },
        }

    @staticmethod
    def _kind(command: str) -> str:
        lowered = command.lower()
        if "summar" in lowered:
            return "summarize"
        if "shorter" in lowered:
            return "shorten"
        if "longer" in lowered or "tell me more" in lowered:
            return "expand"
        if lowered.startswith("why"):
            return "why"
        if "rewrite" in lowered or "professional" in lowered or "casual" in lowered:
            return "rewrite"
        if "translate" in lowered:
            return "translate"
        if "save" in lowered:
            return "save"
        if "continue" in lowered:
            return "continue"
        return "reference"
