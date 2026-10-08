import os
from collections.abc import Generator

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GOOGLE_CLIENT_SECRET"] = ""
os.environ["NOTION_CLIENT_ID"] = ""
os.environ["NOTION_CLIENT_SECRET"] = ""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database.base import Base
from app.core.database.session import get_db
from app.core.config.settings import settings
from app.core.security.dependencies import get_current_user
from app.main import create_app
from app.models.integration import Integration
from app.models.user import User
from app.services.integrations.integration_manager import IntegrationManager
from app.services.integrations.integration_intent_resolver import IntegrationIntentResolver
from app.services.integrations.notion_provider import NotionProvider
from app.services.orchestrator.orchestrator import CeaserOrchestrator
from app.services.orchestrator.knowledge_router import KnowledgeRoute, KnowledgeRouter


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def override_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_current_user() -> User:
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "integration@example.com").first()
    if not user:
        user = User(email="integration@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)
    db.close()
    return user


Base.metadata.create_all(bind=engine)
app = create_app()
app.dependency_overrides[get_db] = override_db
app.dependency_overrides[get_current_user] = override_current_user
client = TestClient(app)


def test_integration_provider_registry_and_dashboard_records() -> None:
    providers_response = client.get("/integrations/providers")
    assert providers_response.status_code == 200
    providers = providers_response.json()
    assert {provider["id"] for provider in providers} == {
        "google-calendar",
        "gmail",
        "google-drive",
        "google-tasks",
        "google-classroom",
        "notion",
        "github",
    }
    assert all(provider["read_only"] for provider in providers)

    integrations_response = client.get("/integrations")
    assert integrations_response.status_code == 200
    integrations = integrations_response.json()
    assert len(integrations) == 7
    assert all(not item["connected"] for item in integrations)


def test_connect_without_oauth_credentials_marks_provider_actionable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_client_id", None)
    monkeypatch.setattr(settings, "google_client_secret", None)
    response = client.post("/integrations/google-calendar/connect", json={})
    assert response.status_code == 200
    assert response.json()["provider"] == "google-calendar"
    assert response.json()["requires_credentials"] is True

    integrations = client.get("/integrations").json()
    calendar = next(item for item in integrations if item["id"] == "google-calendar")
    assert calendar["status"] == "credentials_required"
    assert calendar["connected"] is False


def test_integration_tokens_are_encrypted_at_model_layer() -> None:
    integration = Integration(user_id=override_current_user().id, provider="gmail", status="connected", metadata_json={})
    integration.access_token = "access-secret"
    integration.refresh_token = "refresh-secret"

    assert integration.access_token_encrypted != "access-secret"
    assert integration.refresh_token_encrypted != "refresh-secret"
    assert integration.access_token == "access-secret"
    assert integration.refresh_token == "refresh-secret"


def test_metadata_endpoint_is_read_only_and_safe_when_disconnected() -> None:
    response = client.get("/integrations/notion/metadata")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "notion"
    assert payload["status"] == "not_connected"
    assert payload["items"] == []


def test_beta_integration_requests_reach_connected_data_routes() -> None:
    router = KnowledgeRouter()
    calendar_prompts = [
        "Show my upcoming events",
        "What meetings do I have?",
        "What is on my calendar tomorrow?",
    ]
    integration_prompts = [
        "Show my unread emails",
        "List my Google Drive files",
        "What are my Google Tasks?",
        "Show my Classroom assignments",
        "List my Notion pages",
        "Show my GitHub repositories",
    ]

    for prompt in calendar_prompts:
        decision = router.classify(message=prompt, has_attached_files=False, is_follow_up=False)
        assert decision.route is KnowledgeRoute.CALENDAR, prompt
    for prompt in integration_prompts:
        decision = router.classify(message=prompt, has_attached_files=False, is_follow_up=False)
        assert decision.route is KnowledgeRoute.INTEGRATION, prompt

    orchestrator = CeaserOrchestrator.__new__(CeaserOrchestrator)
    assert orchestrator._is_explicit_google_calendar_request("show my upcoming events")
    assert orchestrator._is_explicit_gmail_request("show my unread emails")
    assert orchestrator._is_explicit_google_drive_request("list my google drive files")
    assert orchestrator._is_explicit_google_tasks_request("what are my google tasks")
    assert orchestrator._is_explicit_google_classroom_request("show my classroom assignments")


def test_upcoming_calendar_events_are_grouped_by_date_and_preserve_all_day(monkeypatch) -> None:
    orchestrator = CeaserOrchestrator(TestingSessionLocal())
    metadata = {
        "status": "connected",
        "items": [
            {"id": "one", "title": "Happy birthday!", "start": "2026-08-29", "end": "2026-08-30", "all_day": True},
            {"id": "duplicate", "title": "Happy birthday!", "start": "2026-08-29", "end": "2026-08-30", "all_day": True},
            {"id": "two", "title": "Project review", "start": "2026-08-30T10:00:00+05:30", "end": "2026-08-30T11:00:00+05:30"},
        ],
    }

    monkeypatch.setattr(IntegrationManager, "sync", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(IntegrationManager, "metadata", lambda *_args, **_kwargs: metadata)

    response = orchestrator._maybe_calendar_response("user-1", "Check Google Calendar and show upcoming events")
    orchestrator.db.close()

    assert response is not None
    assert "**Saturday, August 29, 2026**" in response
    assert "**Sunday, August 30, 2026**" in response
    assert response.count("Happy birthday!") == 1
    assert "**All day** - Happy birthday!" in response
    assert "**10:00 AM - 11:00 AM** - Project review" in response


def test_notion_member_request_uses_members_capability() -> None:
    intent = IntegrationIntentResolver().resolve("Check Notion and give me the members list")

    assert intent is not None
    assert intent.provider == "notion"
    assert intent.capability == "notion.list_members"


def test_notion_task_database_detection_uses_schema_not_only_title() -> None:
    provider = NotionProvider()

    assert provider._is_task_database(
        {"object": "database", "title": "Team Board", "properties": ["Name", "Assignee", "Status", "Due date"]}
    )
    assert not provider._is_task_database(
        {"object": "database", "title": "Knowledge Base", "properties": ["Name", "Category", "Notes"]}
    )
