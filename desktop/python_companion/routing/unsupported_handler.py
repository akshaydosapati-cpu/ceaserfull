from __future__ import annotations

from core.schemas import ActionResult, CommandRequest, IntentResult


class UnsupportedRequestHandler:
    """Return truthful, useful alternatives without claiming execution."""

    def resolve(self, request: CommandRequest, intent: IntentResult) -> ActionResult:
        category = str(intent.entities.get("unsupported_category") or "unknown")
        alternatives = {
            "physical_upgrade": ("That requires a physical hardware upgrade. I can show your current memory and system usage instead.", "system.memory_info"),
            "missing_messaging_plugin": ("Direct WhatsApp sending is not connected. I can open WhatsApp Web instead.", "desktop.open_url"),
            "travel_booking": ("Direct flight booking is not available. I can open a browser search for available flights instead.", "desktop.open_url"),
            "missing_mail_plugin": ("Email sending needs a connected mail plugin. I can help draft the message now.", "ai.answer"),
        }
        summary, nearest = alternatives.get(category, ("That action isn't available yet, but we're adding more controls. I have not changed anything.", None))
        return ActionResult(
            status="failed",
            capability="unsupported",
            summary=summary,
            spoken_response=summary,
            verified=True,
            error_code="unsupported_request",
            evidence={
                "unsupported_category": category,
                "closest_capability": nearest,
                "fallback_capability": nearest,
                "retry_allowed": False,
                "confidence": intent.confidence,
                "source": request.source,
            },
        )
