from __future__ import annotations

import re

from conversation.adaptive_response import AdaptiveResponsePolicy
from conversation.companion_personality import CompanionPersonalityEngine


class ResponseComposer:
    def __init__(self, adaptive_policy: AdaptiveResponsePolicy | None = None, companion_engine: CompanionPersonalityEngine | None = None) -> None:
        self.adaptive_policy = adaptive_policy or AdaptiveResponsePolicy()
        self.companion_engine = companion_engine or CompanionPersonalityEngine()

    def command_for_execution(self, raw_command: str, intent, context: dict) -> str:
        execution_command = str((getattr(intent, "entities", None) or {}).get("execution_command") or "").strip()
        if execution_command:
            return execution_command
        references = context.get("references") or {}
        if not references.get("follow_up_detected"):
            return raw_command
        resolved = references.get("resolved_reference") or {}
        last_summary = str(resolved.get("last_summary") or "").strip()
        if not last_summary:
            return raw_command
        command = str(raw_command or "").strip()
        lowered = command.lower()
        if re.search(r"\b(open it|save it|copy it|send it|close it)\b", lowered):
            return command
        if re.search(r"\b(summarize|summarise|brief|shorten|make (?:it )?shorter)\b", lowered):
            action = "Summarize the previous CEASER result clearly."
        elif re.search(r"\b(make (?:it )?longer|explain|expand|more detail|brief me more|tell me more|what about|why)\b", lowered):
            action = "Explain the previous CEASER result with more useful detail and examples."
        elif re.search(r"\b(rewrite|professional|casual|translate)\b", lowered):
            action = f"Transform the previous CEASER result according to this request: {command}."
        elif re.search(r"\b(continue|go on|keep going|next)\b", lowered):
            action = "Continue the previous CEASER answer naturally without restarting."
        elif re.search(r"\b(table|chart|checklist|list)\b", lowered):
            action = f"Transform the previous CEASER result according to this request: {command}."
        else:
            action = f"Answer this follow-up request using the previous CEASER result: {command}."
        return (
            f"{action}\n\n"
            f"Previous CEASER result:\n{last_summary}\n\n"
            f"Current user follow-up:\n{command}"
        )

    def adapt_result(self, request, intent, context: dict, result):
        result = self._friendly_failure(result)
        adapted = self.adaptive_policy.apply(request, intent, context, result)
        return self.companion_engine.compose(request, intent, context, adapted)

    @staticmethod
    def _friendly_failure(result):
        """Normalize launch-facing failures without changing execution truth."""
        if getattr(result, "status", "") not in {"failed", "needs_input"}:
            return result
        code = str(getattr(result, "error_code", "") or "execution_failed").lower()
        messages = {
            "capability_unavailable": "That control is not available on this device yet. I have not changed anything.",
            "hardware_unsupported": "This laptop does not expose that control. I have not changed anything.",
            "permission_required": "Windows needs permission for that action. I have not changed anything.",
            "device_offline": "That device is offline right now. Try again when it reconnects.",
            "target_not_found": "I could not find that target. Tell me its exact name and I will try again.",
            "ambiguous_target": "I found more than one match. Which one did you mean?",
            "verification_failed": "The command was sent, but I could not verify the change. I will not claim it completed.",
            "timeout": "That took too long and stopped safely. You can try again.",
            "network_unavailable": "The network is unavailable right now. Local desktop controls still work.",
            "service_unavailable": "That service is temporarily unavailable. You can try again shortly.",
            "microphone_unavailable": "I cannot access the microphone right now. Check the selected input device and try again.",
        }
        friendly = messages.get(code)
        if code in {"device_offline", "timeout", "network_unavailable", "service_unavailable", "microphone_unavailable", "execution_failed"}:
            result.retryable = True
        if friendly:
            result.summary = friendly
            result.spoken_response = friendly
        return result
