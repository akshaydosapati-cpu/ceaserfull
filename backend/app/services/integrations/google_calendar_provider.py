from datetime import timedelta
from urllib.parse import quote

from app.services.integrations.base_provider import BaseIntegrationProvider
from app.core.config.settings import settings
from app.models.integration import Integration
from app.models.mixins import utc_now


class GoogleCalendarProvider(BaseIntegrationProvider):
    id = "google-calendar"
    name = "Google Calendar"
    category = "productivity"
    description = "Read calendars, events, upcoming schedule, and event details."
    scopes = ["https://www.googleapis.com/auth/calendar.readonly", "https://www.googleapis.com/auth/calendar.events"]
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"

    @property
    def redirect_uri(self) -> str:
        return settings.google_calendar_oauth_redirect_uri

    def get_metadata(self, integration: Integration | None) -> dict:
        if not integration or integration.status != "connected":
            return {"provider": self.id, "status": "not_connected", "items": []}
        calendars_payload = self.google_get(
            integration,
            "https://www.googleapis.com/calendar/v3/users/me/calendarList",
            {"maxResults": 250, "minAccessRole": "reader", "showHidden": "false"},
        )
        calendars = calendars_payload.get("items", [])
        now = utc_now()
        events: list[dict] = []
        seen: set[tuple[str, str, str]] = set()
        for calendar in calendars:
            calendar_id = calendar.get("id")
            if not calendar_id or calendar.get("deleted") or calendar.get("hidden"):
                continue
            events_payload = self.google_get(
                integration,
                f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events",
                {
                    "singleEvents": "true",
                    "orderBy": "startTime",
                    "timeMin": now.isoformat(),
                    "timeMax": (now + timedelta(days=366)).isoformat(),
                    "maxResults": 50,
                },
            )
            calendar_name = calendar.get("summaryOverride") or calendar.get("summary") or "Calendar"
            for item in events_payload.get("items", []):
                if item.get("status") == "cancelled":
                    continue
                start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
                title = item.get("summary", "Untitled event")
                identity = (str(calendar_id), str(item.get("id") or title), str(start or ""))
                if identity in seen:
                    continue
                seen.add(identity)
                events.append(
                    {
                        "id": item.get("id"),
                        "title": title,
                        "start": start,
                        "end": item.get("end", {}).get("dateTime") or item.get("end", {}).get("date"),
                        "all_day": bool(item.get("start", {}).get("date")),
                        "location": item.get("location"),
                        "link": item.get("htmlLink"),
                        "calendar_id": calendar_id,
                        "calendar_name": calendar_name,
                        "calendar_primary": bool(calendar.get("primary")),
                    }
                )
        events.sort(key=lambda item: str(item.get("start") or ""))
        events = events[:100]
        return {
            "provider": self.id,
            "status": integration.status,
            "account_email": integration.provider_email,
            "permissions": self.permissions,
            "summary": {
                "calendar_count": len(calendars),
                "upcoming_events": len(events),
            },
            "items": events,
        }

    def create_event(self, integration: Integration, event: dict) -> dict:
        return self.google_request(integration, "POST", "https://www.googleapis.com/calendar/v3/calendars/primary/events", payload=event)

    def update_event(self, integration: Integration, event_id: str, event: dict) -> dict:
        return self.google_request(integration, "PATCH", f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}", payload=event)
