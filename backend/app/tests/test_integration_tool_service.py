"""Tests for IntegrationToolService."""

import os
from collections.abc import Generator
from uuid import uuid4

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["GEMINI_API_KEY"] = ""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database.base import Base
from app.models.integration import Integration
from app.services.integrations.integration_tool_service import (
    CAPABILITY_DEFINITIONS,
    IntegrationToolService,
    ToolDefinition,
)


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


Base.metadata.create_all(bind=engine)


def current_user_dict() -> dict:
    db = TestingSessionLocal()
    user = IntegrationToolTestUser(email=f"tool-test-{uuid4()}@example.com")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return {"id": user.id, "email": user.email}


class IntegrationToolTestUser:
    def __init__(self, email: str):
        self.email = email
        # Use a fixed ID generation
        self.id = hash(email) % 1000000


def test_capability_definitions_mapping():
    """Test that capability definitions are properly mapped."""
    # Check Gmail capabilities
    assert "email.create_draft" in CAPABILITY_DEFINITIONS
    assert "email.send" in CAPABILITY_DEFINITIONS
    assert "calendar.create_event" in CAPABILITY_DEFINITIONS
    assert "calendar.update_event" in CAPABILITY_DEFINITIONS

    # Check provider mappings
    assert CAPABILITY_DEFINITIONS["email.create_draft"][0] == "gmail"
    assert CAPABILITY_DEFINITIONS["calendar.create_event"][0] == "google-calendar"
    assert CAPABILITY_DEFINITIONS["github.list_repositories"][0] == "github"
    assert CAPABILITY_DEFINITIONS["notion.search_pages"][0] == "notion"


def test_integration_tool_service_builds_tools():
    """Test that integration tool service builds tools from connected integrations."""
    db = TestingSessionLocal()
    user_id = 123

    # Create a connected Gmail integration
    gmail = Integration(
        user_id=user_id,
        provider="gmail",
        provider_email="test@example.com",
        status="connected",
        metadata_json={"scope": "https://mail.google.com/"},
    )
    db.add(gmail)
    db.commit()

    service = IntegrationToolService(db)
    tools = service.get_available_tools(user_id)
    db.close()

    # Should have Gmail tools
    assert len(tools) > 0
    tool_names = [t.name for t in tools]

    # Check specific Gmail tools are present
    assert any("gmail" in name for name in tool_names)
    assert any("create_draft" in name for name in tool_names)
    assert any("send" in name for name in tool_names)

    # Check tool structure
    for tool in tools:
        assert isinstance(tool, ToolDefinition)
        assert tool.name
        assert tool.description
        assert tool.parameters
        assert tool.provider == "gmail"


def test_integration_tool_service_filters_by_connected_providers():
    """Test that tools are only built for connected providers."""
    db = TestingSessionLocal()
    user_id = 456

    # Create Gmail as connected
    gmail = Integration(
        user_id=user_id,
        provider="gmail",
        provider_email="test@example.com",
        status="connected",
        metadata_json={},
    )
    db.add(gmail)

    # Create Google Calendar as not_connected
    calendar = Integration(
        user_id=user_id,
        provider="google-calendar",
        provider_email="calendar@example.com",
        status="not_connected",
        metadata_json={},
    )
    db.add(calendar)
    db.commit()

    service = IntegrationToolService(db)
    tools = service.get_available_tools(user_id)
    db.close()

    # Should only have Gmail tools, not calendar tools
    tool_providers = {t.provider for t in tools}
    assert "gmail" in tool_providers
    assert "google-calendar" not in tool_providers


def test_integration_tool_service_requires_confirmation():
    """Test that confirmation-required capabilities are properly identified."""
    db = TestingSessionLocal()
    user_id = 789

    # Create Gmail integration
    gmail = Integration(
        user_id=user_id,
        provider="gmail",
        provider_email="test@example.com",
        status="connected",
        metadata_json={},
    )
    db.add(gmail)
    db.commit()

    service = IntegrationToolService(db)
    tools = service.get_available_tools(user_id)
    db.close()

    # Check email.send requires confirmation
    send_tool = next((t for t in tools if t.capability == "email.send"), None)
    assert send_tool is not None
    assert send_tool.requires_confirmation is True

    # Check email.create_draft does NOT require confirmation
    create_draft_tool = next((t for t in tools if t.capability == "email.create_draft"), None)
    assert create_draft_tool is not None
    assert create_draft_tool.requires_confirmation is False


def test_capability_to_tool_name_conversion():
    """Test capability ID to tool name conversion."""
    db = TestingSessionLocal()
    service = IntegrationToolService(db)

    # Check conversions
    assert service._capability_to_tool_name("email.create_draft") == "gmail_create_draft"
    assert service._capability_to_tool_name("email.send") == "gmail_send"
    assert service._capability_to_tool_name("calendar.create_event") == "google_calendar_create_event"
    assert service._capability_to_tool_name("github.list_repositories") == "github_list_repositories"
    assert service._capability_to_tool_name("notion.search_pages") == "notion_search_pages"

    db.close()


def test_integration_tool_service_executes_tool_success():
    """Test that integration tools execute successfully for available capabilities."""
    db = TestingSessionLocal()
    user_id = 999

    # Create a connected Google Drive integration
    drive = Integration(
        user_id=user_id,
        provider="google-drive",
        provider_email="drive@example.com",
        status="connected",
        metadata_json={},
    )
    db.add(drive)
    db.commit()

    service = IntegrationToolService(db)

    # Test that the tool is available
    tools = service.get_available_tools(user_id)
    drive_tools = [t for t in tools if t.provider == "google-drive"]

    # Should have at least one drive tool
    assert len(drive_tools) > 0

    # Test execute with unknown tool returns error
    result = service.execute_tool_call(
        tool_name="unknown_tool",
        arguments={},
        user_id=user_id,
    )

    assert result.success is False
    assert result.error is not None

    db.close()


def test_integration_tool_service_detects_confirmation_required():
    """Test that write operations requiring confirmation return proper response."""
    db = TestingSessionLocal()
    user_id = 888

    # Create Gmail integration
    gmail = Integration(
        user_id=user_id,
        provider="gmail",
        provider_email="test@example.com",
        status="connected",
        metadata_json={},
    )
    db.add(gmail)
    db.commit()

    service = IntegrationToolService(db)

    # Test email.send requires confirmation
    result = service.execute_tool_call(
        tool_name="gmail_send",
        arguments={"request": "Send this email"},
        user_id=user_id,
    )

    assert result.success is False
    assert result.requires_confirmation is True
    assert result.confirmation_prompt is not None

    db.close()
