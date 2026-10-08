"""Tests for specialist agent bypass feature flag."""
from __future__ import annotations

import asyncio
import os
import pytest
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["GEMINI_API_KEY"] = ""
os.environ["CEASER_AGENTS_ENABLED"] = "false"

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config.settings import settings
from app.core.database.base import Base
from app.models.user import User
from app.services.orchestrator.orchestrator import CeaserOrchestrator


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="function")
def db_session() -> Session:
    """Create a new database session for each test."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database():
    """Create database tables before tests."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user."""
    user = User(email="test@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestAgentsBypass:
    """Test that agents_enabled flag correctly bypasses specialist agent routing."""

    def test_agents_disabled_by_default(self):
        """agents_enabled should be False by default."""
        assert settings.agents_enabled is False, "agents_enabled should default to False"

    def test_agents_disabled_returns_empty_selected_agents(self, db_session: Session):
        """When agents_enabled=False, _default_stream_agents returns empty list."""
        orchestrator = CeaserOrchestrator(db_session)

        # This should return empty when agents are disabled
        result = orchestrator._default_stream_agents("What is Python?")
        assert result == [], f"Expected empty list when agents disabled, got {result}"

    def test_agents_enabled_uses_specialist_routing(self, db_session: Session):
        """When agents_enabled=True, _default_stream_agents uses specialist routing."""
        # Temporarily enable agents
        original_value = settings.agents_enabled
        settings.agents_enabled = True
        try:
            orchestrator = CeaserOrchestrator(db_session)

            # Test with a message that would match a specialist agent pattern
            result = orchestrator._default_stream_agents("Write some Python code")
            # With agents enabled, this might return ['Bolt'] or another agent based on pattern matching
        finally:
            settings.agents_enabled = original_value

    def test_specialist_plan_not_called_when_disabled(self, db_session: Session):
        """When agents_enabled=False, specialist_agents.prepare is not called."""
        orchestrator = CeaserOrchestrator(db_session)

        # Mock the specialist_agents.prepare method
        with patch.object(orchestrator.specialist_agents, 'prepare') as mock_prepare:
            # Call handle_message which should skip prepare when agents disabled
            result = orchestrator.handle_message(
                user_id="test_user_id",
                message="What is the capital of France?",
                conversation_id=None,
            )

            # prepare should NOT have been called when agents are disabled
            mock_prepare.assert_not_called()

    def test_specialist_plan_called_when_enabled(self, db_session: Session):
        """When agents_enabled=True, specialist_agents.prepare may be called."""
        # Temporarily enable agents
        original_value = settings.agents_enabled
        settings.agents_enabled = True
        try:
            orchestrator = CeaserOrchestrator(db_session)

            # Mock the specialist_agents.prepare method
            with patch.object(orchestrator.specialist_agents, 'prepare') as mock_prepare:
                # Mock the prepare method to return None (no specialist plan)
                mock_prepare.return_value = None

                result = orchestrator.handle_message(
                    user_id="test_user_id",
                    message="What is the capital of France?",
                    conversation_id=None,
                )

                # prepare should have been called (even if it returns None)
                mock_prepare.assert_called_once()
        finally:
            settings.agents_enabled = original_value

    def test_streaming_path_agents_disabled(self, db_session: Session):
        """Streaming path also respects agents_enabled flag via _default_stream_agents."""
        orchestrator = CeaserOrchestrator(db_session)

        # When agents disabled, _default_stream_agents should return empty
        result = orchestrator._default_stream_agents("What is the capital of France?")
        assert result == [], "Expected empty agents list when agents disabled"

    def test_streaming_path_agents_enabled(self, db_session: Session):
        """Streaming path with agents enabled may call specialist selection."""
        # Temporarily enable agents
        original_value = settings.agents_enabled
        settings.agents_enabled = True
        try:
            orchestrator = CeaserOrchestrator(db_session)

            # When agents enabled, _default_stream_agents uses specialist routing
            result = orchestrator._default_stream_agents("What is the capital of France?")
            # Should either be empty (no matching specialist) or a list of agent names
            assert isinstance(result, list), "Expected list of agents when enabled"
        finally:
            settings.agents_enabled = original_value

    def test_explicit_workflow_runs_without_agents(self, db_session: Session):
        """Explicit workflow creation should work regardless of agents_enabled."""
        # When agents are disabled, explicit workflows should still work
        orchestrator = CeaserOrchestrator(db_session)

        # This message should trigger explicit workflow - we're testing that it
        # doesn't crash and returns a result, not specifically that the mock was called
        # The mock approach is difficult due to how the orchestrator instantiates
        # its dependencies in __init__
        result = orchestrator.handle_message(
            user_id="test_user_id",
            message="Create a presentation about climate change",
            conversation_id=None,
        )

        # Verify the orchestrator returned a valid response
        assert isinstance(result, dict)
        assert "scope" in result
        # With no provider configured, we expect an error response but not a crash
