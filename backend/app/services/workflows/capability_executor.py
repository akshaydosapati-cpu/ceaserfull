from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.engines.research_engine import ResearchEngine
from app.models.file import File
from app.models.integration import Integration
from app.services.document_generation import DocumentGenerator
from app.services.document_generation.export_manager import ExportManager
from app.services.integrations.gmail_provider import GmailProvider
from app.services.integrations.google_calendar_provider import GoogleCalendarProvider
from app.services.storage_service import StorageService


@dataclass
class CapabilityOutcome:
    state: str
    output: dict[str, Any] | None = None
    message: str = ""
    verified: bool = False


class WorkflowCapabilityExecutor:
    """Production handlers used by the authoritative WorkflowExecutor."""

    executable = {
        "research.execute", "document.create", "presentation.create",
        "email.create_draft", "email.update_draft", "email.reply_draft", "email.send",
        "calendar.create_event", "calendar.update_event", "reminder.create",
    }

    def __init__(self, db: Session):
        self.db = db

    def availability(self, capability: str, user_id: str) -> str:
        if capability not in self.executable:
            return "UNAVAILABLE"
        if capability.startswith("email."):
            if not self._integration(user_id, "gmail"):
                return "REQUIRES_INTEGRATION"
            return "REQUIRES_CONFIRMATION" if capability == "email.send" else "EXECUTABLE"
        if capability.startswith("calendar."):
            if not self._integration(user_id, "google-calendar"):
                return "REQUIRES_INTEGRATION"
            return "REQUIRES_CONFIRMATION" if capability == "calendar.update_event" else "EXECUTABLE"
        return "EXECUTABLE"

    def execute(self, capability: str, *, user_id: str, request: str, inputs: dict[str, Any], confirmed: bool = False) -> CapabilityOutcome:
        availability = self.availability(capability, user_id)
        if availability == "REQUIRES_INTEGRATION":
            return CapabilityOutcome("WAITING_FOR_USER", message=f"Connect {self._provider_name(capability)} to continue.")
        if availability == "UNAVAILABLE":
            return CapabilityOutcome("FAILED", message=f"Capability unavailable: {capability}")
        if capability in {"email.send", "calendar.update_event"} and not confirmed:
            return CapabilityOutcome("WAITING_FOR_USER", message="Confirmation required.")
        if capability == "research.execute":
            result = ResearchEngine().research(request, include_images=False).model_dump(mode="json")
            return CapabilityOutcome("COMPLETED", result, "Research completed.", bool(result.get("sources")))
        if capability in {"document.create", "presentation.create"}:
            return self._artifact(capability, user_id, request, inputs)
        if capability.startswith("email."):
            return self._email(capability, user_id, request, inputs)
        if capability.startswith("calendar."):
            return self._calendar(capability, user_id, request, inputs)
        if capability.startswith("reminder."):
            return self._reminder(capability, user_id, request, inputs)
        return CapabilityOutcome("FAILED", message=f"Capability unavailable: {capability}")

    def _artifact(self, capability: str, user_id: str, request: str, inputs: dict[str, Any]) -> CapabilityOutcome:
        research = inputs.get("research_result") or {}
        source_content = self._research_text(research) if research else None
        kind = "pptx" if capability == "presentation.create" else "docx"
        template = "research-presentation" if kind == "pptx" else None
        result = DocumentGenerator().generate(prompt=request, kind=kind, template_id=template, agent_id="nova" if kind == "pptx" else "atlas", source_content=source_content)
        storage_path = StorageService().store(user_id=user_id, filename=result.filename, content=result.bytes_data, content_type=result.content_type)
        file = File(user_id=user_id, project_id=None, name=result.filename, file_type=result.kind, storage_path=storage_path)
        file.extracted_content = result.content
        file.extraction_metadata = {"generated": True, "generated_by_agent": result.agent_id, "template_id": result.template.id, "title": result.title, "workflow": True, "sources": research.get("sources", [])}
        self.db.add(file)
        self.db.flush()
        generated = ExportManager(self.db).record_generated(file_id=file.id, user_id=user_id, agent_id=result.agent_id, template_id=result.template.id, export_format=result.kind, prompt=request)
        return CapabilityOutcome("COMPLETED", {"file_id": file.id, "generated_document_id": generated.id, "name": file.name, "kind": kind, "storage_path": storage_path, "sources": research.get("sources", [])}, f"{kind.upper()} artifact created.", bool(file.id and storage_path))

    def _email(self, capability: str, user_id: str, request: str, inputs: dict[str, Any]) -> CapabilityOutcome:
        integration = self._integration(user_id, "gmail")
        provider = GmailProvider()
        draft = inputs.get("email_draft") or {}
        recipient = str(draft.get("to") or self._recipient(request) or "")
        if capability != "email.send" and not recipient:
            return CapabilityOutcome("WAITING_FOR_USER", message="Which email address should receive the draft?")
        subject = str(draft.get("subject") or self._subject(request))
        body = str(draft.get("body") or self._email_body(request, inputs))

        attachment_bytes = None
        attachment_filename = None
        if draft.get("attachment"):
            attachment_ref = draft.get("attachment")
            try:
                storage_path = attachment_ref.get("storage_path") if isinstance(attachment_ref, dict) else str(attachment_ref)
                filename = attachment_ref.get("filename", "attachment") if isinstance(attachment_ref, dict) else "attachment"
                attachment_bytes = StorageService().read_bytes(storage_path)
                attachment_filename = filename
            except Exception:
                return CapabilityOutcome("FAILED", message="Could not resolve attachment file.")

        if capability == "email.send":
            draft_id = str(draft.get("id") or draft.get("draft_id") or "")
            if not draft_id:
                return CapabilityOutcome("FAILED", message="The verified Gmail draft is missing.")
            payload = provider.send_draft(integration, draft_id)
            return CapabilityOutcome("COMPLETED", {"message_id": payload.get("id"), "thread_id": payload.get("threadId"), "draft_id": draft_id, "delivery_status": "submitted"}, "Email sent.", bool(payload.get("id")))

        if capability == "email.update_draft":
            payload = provider.update_draft(integration, str(draft.get("id") or ""), to=recipient, subject=subject, body=body, attachment_bytes=attachment_bytes, attachment_filename=attachment_filename)
        else:
            payload = provider.create_draft(integration, to=recipient, subject=subject, body=body, thread_id=draft.get("thread_id"), in_reply_to=draft.get("message_id") if capability == "email.reply_draft" else None)
        return CapabilityOutcome("COMPLETED", {"id": payload.get("id"), "draft_id": payload.get("id"), "to": recipient, "subject": subject, "body": body, "message": payload.get("message"), "attachment": attachment_filename}, "Draft ready.", bool(payload.get("id")))

    def _calendar(self, capability: str, user_id: str, request: str, inputs: dict[str, Any]) -> CapabilityOutcome:
        integration = self._integration(user_id, "google-calendar")
        provider = GoogleCalendarProvider()
        event = dict(inputs.get("calendar_event") or {})
        event.setdefault("summary", request[:160])
        if not event.get("start") or not event.get("end"):
            return CapabilityOutcome("WAITING_FOR_USER", message="What date and time should I use for the event?")
        if capability == "calendar.update_event":
            event_id = str(event.pop("id", ""))
            if not event_id:
                return CapabilityOutcome("WAITING_FOR_USER", message="Which calendar event should I update?")
            payload = provider.update_event(integration, event_id, event)
        else:
            payload = provider.create_event(integration, event)
        return CapabilityOutcome("COMPLETED", {"id": payload.get("id"), "status": payload.get("status"), "html_link": payload.get("htmlLink"), **event}, "Calendar event saved.", bool(payload.get("id")))

    def _reminder(self, capability: str, user_id: str, request: str, inputs: dict[str, Any]) -> CapabilityOutcome:
        integration = self._integration(user_id, "google-calendar")
        provider = GoogleCalendarProvider()
        reminder_config = dict(inputs.get("reminder") or {})
        event_id = str(reminder_config.get("event_id") or "")
        if not event_id:
            return CapabilityOutcome("WAITING_FOR_USER", message="Which calendar event should I add a reminder to?")
        minutes_before = int(reminder_config.get("minutes_before") or 1440)
        method = str(reminder_config.get("method") or "notification")
        try:
            event_update = {
                "reminders": {
                    "useDefault": False,
                    "overrides": [{"method": method, "minutes": minutes_before}]
                }
            }
            payload = provider.update_event(integration, event_id, event_update)
            return CapabilityOutcome("COMPLETED", {"event_id": event_id, "reminder_minutes": minutes_before, "reminder_method": method, "status": payload.get("status")}, f"Reminder set for {minutes_before} minutes before the event.", bool(payload.get("id")))
        except Exception as exc:
            return CapabilityOutcome("FAILED", message=f"Could not set reminder: {str(exc)}")

    def _integration(self, user_id: str, provider: str) -> Integration | None:
        return self.db.query(Integration).filter(Integration.user_id == user_id, Integration.provider == provider, Integration.status == "connected").first()

    @staticmethod
    def _provider_name(capability: str) -> str:
        return "Gmail" if capability.startswith("email.") else "Google Calendar"

    @staticmethod
    def _recipient(request: str) -> str | None:
        match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", request)
        return match.group(0) if match else None

    @staticmethod
    def _subject(request: str) -> str:
        return "CEASER research summary" if "research" in request.lower() else "CEASER draft"

    @classmethod
    def _email_body(cls, request: str, inputs: dict[str, Any]) -> str:
        research = inputs.get("research_result") or {}
        lines = [str(research.get("summary") or request)] + [str(item) for item in research.get("key_findings", [])]
        artifacts = [value.get("name") for value in inputs.values() if isinstance(value, dict) and value.get("name")]
        if artifacts:
            lines.append("Artifacts: " + ", ".join(artifacts))
        return "\n\n".join(filter(None, lines))

    @staticmethod
    def _research_text(research: dict) -> str:
        lines = [research.get("query", "Research"), research.get("summary", "")]
        lines.extend(research.get("key_findings", []))
        lines.append("Sources")
        lines.extend(f"{item.get('title', 'Source')}: {item.get('url', '')}" for item in research.get("sources", []))
        return "\n\n".join(str(item) for item in lines if item)
