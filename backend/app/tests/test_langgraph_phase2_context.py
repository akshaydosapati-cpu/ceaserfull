"""Tests for Phase 2: Context integration with LangGraph research agent.

Verifies that:
1. ContextAdapter retrieves existing CEASER context services
2. LangGraph agent accepts and uses context in reasoning
3. Context flows into LLM prompts
4. Mock context can be injected for testing
5. Phase 1 tests continue passing
"""
from __future__ import annotations

import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Any

from app.agents.langgraph.research_agent import (
    ResearchAgent,
    CeaserResearchTool,
    ResearchAgentState,
)
from app.agents.langgraph.context_adapter import (
    ContextAdapter,
    ResearchContext,
)
from app.agents.langgraph.factory import create_research_agent
from app.agents.langgraph.model_adapter import CeaserModelAdapter


class MockLLM:
    """Mock LLM for testing without real API calls."""

    def invoke(self, messages: list[dict[str, str]]) -> Mock:
        """Return mock response with content attribute."""
        response = Mock()
        # Analyze node: return decision about research
        if "Analyze the user's goal" in str(messages):
            response.content = """RESEARCH_NEEDED: yes
QUERY: what is machine learning
REASONING: The user wants to understand ML fundamentals"""
        # Synthesize node: return final answer
        elif "research synthesis" in str(messages).lower():
            response.content = """Based on the research gathered, machine learning is...

Key findings:
- ML uses algorithms to learn from data
- Applications span from recommendation systems to healthcare

Recommended sources:
- [Source 1: Machine Learning Basics](https://example.com/ml-basics)
- [Source 2: ML Applications](https://example.com/ml-apps)

Next steps: Consider specific ML algorithms like supervised/unsupervised learning."""
        else:
            response.content = "Response"
        return response


@pytest.fixture
def mock_db():
    """Fixture with mock SQLAlchemy session."""
    return Mock()


@pytest.fixture
def mock_research_result() -> dict[str, Any]:
    """Fixture with mock research result."""
    return {
        "query": "machine learning",
        "summary": "Collected 5 ranked sources for 'machine learning'",
        "key_findings": [
            "ML is a subset of AI that learns from data",
            "Common types: supervised, unsupervised, reinforcement",
        ],
        "sources": [
            {
                "title": "ML Fundamentals",
                "url": "https://example.com/ml-fundamentals",
                "snippet": "Machine learning enables systems to learn from data...",
            },
            {
                "title": "ML Applications",
                "url": "https://example.com/ml-applications",
                "snippet": "ML is used in recommendation systems, NLP, computer vision...",
            },
        ],
        "citations": ["[1] https://example.com/ml-fundamentals", "[2] https://example.com/ml-applications"],
        "images": [],
        "timings": {"research_total_ms": 2500.0},
    }


@pytest.fixture
def mock_context() -> ResearchContext:
    """Fixture with mock research context from CEASER."""
    return ResearchContext(
        conversation_history=[
            {"role": "user", "content": "We're researching AI agents for our CEASER project"},
            {
                "role": "assistant",
                "content": "I can help you research AI agents. What specific aspects are you interested in?",
            },
        ],
        relevant_memories=[
            {
                "id": "mem_1",
                "user_id": "user123",
                "memory_type": "project",
                "content": "CEASER project: Building intelligent orchestration system",
                "metadata": {"importance": 8},
                "created_at": "2026-09-30T00:00:00.000Z",
                "score": 42.5,
                "matched_terms": 3,
            },
            {
                "id": "mem_2",
                "user_id": "user123",
                "memory_type": "research",
                "content": "We discussed multi-agent architectures yesterday",
                "metadata": {"importance": 6},
                "created_at": "2026-09-29T00:00:00.000Z",
                "score": 35.0,
                "matched_terms": 2,
            },
        ],
        user_id="user123",
        conversation_id="conv_abc123",
    )


class TestContextAdapter:
    """Tests for the ContextAdapter."""

    def test_adapter_creation(self, mock_db):
        """Test that ContextAdapter can be created."""
        adapter = ContextAdapter(db=mock_db)
        assert adapter.db is not None
        assert adapter.memory_retriever is not None
        assert adapter.conversation_service is not None

    @patch("app.agents.langgraph.context_adapter.ConversationService")
    @patch("app.agents.langgraph.context_adapter.MemoryRetriever")
    def test_adapter_builds_context_from_conversation(
        self, mock_retriever_class, mock_service_class, mock_db
    ):
        """Test that adapter retrieves conversation history."""
        # Mock conversation service
        mock_message_1 = Mock()
        mock_message_1.role = "user"
        mock_message_1.content = "Research AI agents"

        mock_message_2 = Mock()
        mock_message_2.role = "assistant"
        mock_message_2.content = "I can help with that"

        mock_service = Mock()
        mock_service.list_recent_messages.return_value = [mock_message_1, mock_message_2]
        mock_service_class.return_value = mock_service

        # Mock memory retriever
        mock_memory = Mock()
        mock_memory.id = "mem_1"
        mock_memory.memory_type = "project"
        mock_memory.content = "CEASER project"
        mock_memory.extra_metadata = {}

        mock_retriever = Mock()
        mock_retriever.retrieve_relevant_memories.return_value = []
        mock_retriever_class.return_value = mock_retriever

        adapter = ContextAdapter(db=mock_db)
        context = adapter.build_research_context(
            user_id="user123",
            query="AI agents",
            conversation_id="conv_abc",
        )

        assert context.user_id == "user123"
        assert context.conversation_id == "conv_abc"
        assert len(context.conversation_history) == 2
        assert context.conversation_history[0]["role"] == "user"
        mock_service.list_recent_messages.assert_called_once()

    @patch("app.agents.langgraph.context_adapter.ConversationService")
    @patch("app.agents.langgraph.context_adapter.MemoryRetriever")
    def test_adapter_retrieves_relevant_memories(
        self, mock_retriever_class, mock_service_class, mock_db
    ):
        """Test that adapter retrieves and ranks relevant memories."""
        # Mock conversation service (empty)
        mock_service = Mock()
        mock_service.list_recent_messages.return_value = []
        mock_service_class.return_value = mock_service

        # Mock memory retriever
        mock_retriever = Mock()
        mock_retriever.retrieve_relevant_memories.return_value = [
            {
                "id": "mem_1",
                "memory_type": "project",
                "content": "CEASER project",
                "score": 42.5,
            },
            {
                "id": "mem_2",
                "memory_type": "research",
                "content": "Multi-agent discussion",
                "score": 35.0,
            },
        ]
        mock_retriever_class.return_value = mock_retriever

        adapter = ContextAdapter(db=mock_db)
        context = adapter.build_research_context(
            user_id="user123",
            query="AI agents",
        )

        assert len(context.relevant_memories) == 2
        mock_retriever.retrieve_relevant_memories.assert_called_once_with(
            user_id="user123",
            query="AI agents",
            limit=5,
        )

    def test_context_format_for_llm(self, mock_context):
        """Test that context can be formatted for LLM prompts."""
        formatted = ResearchContext.format_for_llm(mock_context)

        assert "## Recent Conversation" in formatted
        assert "## Relevant Context" in formatted
        assert "CEASER project" in formatted
        assert "multi-agent" in formatted.lower()

    def test_context_to_dict(self, mock_context):
        """Test that context converts to dictionary for state."""
        context_dict = mock_context.to_dict()

        assert context_dict["user_id"] == "user123"
        assert context_dict["conversation_id"] == "conv_abc123"
        assert len(context_dict["conversation_history"]) == 2
        assert len(context_dict["relevant_memories"]) == 2


class TestResearchAgentWithContext:
    """Tests for research agent with context integration."""

    def test_agent_creation_with_context(self, mock_db, mock_context):
        """Test that research agent accepts initial context."""
        llm = MockLLM()
        agent = ResearchAgent(
            llm=llm,
            db=mock_db,
            user_id="user123",
            initial_context=mock_context,
        )
        assert agent.initial_context is mock_context
        assert agent.initial_context.user_id == "user123"

    def test_agent_creation_without_context(self, mock_db):
        """Test that research agent works without context."""
        llm = MockLLM()
        agent = ResearchAgent(
            llm=llm,
            db=mock_db,
            user_id="user123",
            initial_context=None,
        )
        assert agent.initial_context is None

    def test_agent_analyze_node_receives_context(self, mock_db, mock_context):
        """Test that analyze node receives context in LLM prompt."""
        llm = MockLLM()
        agent = ResearchAgent(
            llm=llm,
            db=mock_db,
            user_id="user123",
            initial_context=mock_context,
        )

        initial_state: ResearchAgentState = {
            "user_goal": "Focus on competitors in the AI agent space",
            "messages": [{"role": "human", "content": "Focus on competitors in the AI agent space"}],
            "relevant_context": mock_context,
            "research_result": None,
            "final_response": "",
        }

        result = agent._analyze_node(initial_state)

        # Verify context was included in the state
        assert result["relevant_context"] is mock_context
        assert len(result["messages"]) > 1

    @patch("app.agents.langgraph.research_agent.WorkflowCapabilityExecutor")
    def test_agent_research_node_with_context(
        self, mock_executor_class, mock_db, mock_context, mock_research_result
    ):
        """Test that research node works with context in state."""
        mock_outcome = Mock()
        mock_outcome.state = "COMPLETED"
        mock_outcome.output = mock_research_result

        mock_executor = Mock()
        mock_executor.execute.return_value = mock_outcome
        mock_executor_class.return_value = mock_executor

        llm = MockLLM()
        agent = ResearchAgent(
            llm=llm,
            db=mock_db,
            user_id="user123",
            initial_context=mock_context,
        )

        state: ResearchAgentState = {
            "user_goal": "AI agents for competitors",
            "messages": [
                {"role": "human", "content": "AI agents for competitors"},
                {"role": "system", "content": "QUERY: competitor AI agents"},
            ],
            "relevant_context": mock_context,
            "research_result": None,
            "final_response": "",
        }

        result = agent._research_node(state)

        # Verify context is preserved
        assert result["relevant_context"] is mock_context
        # Verify research was executed
        assert result["research_result"] is not None

    def test_agent_synthesize_node_with_context(self, mock_db, mock_context):
        """Test that synthesize node uses context in final response."""
        llm = MockLLM()
        agent = ResearchAgent(
            llm=llm,
            db=mock_db,
            user_id="user123",
            initial_context=mock_context,
        )

        state: ResearchAgentState = {
            "user_goal": "AI agents for competitors",
            "messages": [{"role": "human", "content": "AI agents for competitors"}],
            "relevant_context": mock_context,
            "research_result": {
                "query": "competitor AI agents",
                "sources": [{"title": "AI Agent Guide", "url": "https://example.com"}],
            },
            "final_response": "",
        }

        result = agent._synthesize_node(state)

        # Verify context is preserved
        assert result["relevant_context"] is mock_context
        # Verify final response was generated
        assert result["final_response"] != ""

    @patch("app.agents.langgraph.research_agent.WorkflowCapabilityExecutor")
    def test_agent_invoke_full_flow_with_context(
        self, mock_executor_class, mock_db, mock_context, mock_research_result
    ):
        """Test full agent flow preserves context through all nodes."""
        mock_outcome = Mock()
        mock_outcome.state = "COMPLETED"
        mock_outcome.output = mock_research_result

        mock_executor = Mock()
        mock_executor.execute.return_value = mock_outcome
        mock_executor_class.return_value = mock_executor

        llm = MockLLM()
        agent = ResearchAgent(
            llm=llm,
            db=mock_db,
            user_id="user123",
            initial_context=mock_context,
        )

        result = agent.invoke("Tell me about competitor AI agents")

        assert result["relevant_context"] is mock_context
        assert result["final_response"] != ""
        assert result["research_result"] is not None


class TestFactoryWithContext:
    """Tests for factory with context support."""

    def test_factory_accepts_initial_context(self, mock_db, mock_context):
        """Test that factory accepts initial context parameter."""
        llm = MockLLM()
        agent = create_research_agent(
            db=mock_db,
            user_id="user123",
            llm=llm,
            initial_context=mock_context,
        )

        assert isinstance(agent, ResearchAgent)
        assert agent.initial_context is mock_context

    def test_factory_works_without_context(self, mock_db):
        """Test that factory works without context (backward compatible)."""
        llm = MockLLM()
        agent = create_research_agent(
            db=mock_db,
            user_id="user123",
            llm=llm,
        )

        assert isinstance(agent, ResearchAgent)
        assert agent.initial_context is None


class TestContextIntegrationFlow:
    """Tests for complete context integration flow."""

    @patch("app.agents.langgraph.context_adapter.ConversationService")
    @patch("app.agents.langgraph.context_adapter.MemoryRetriever")
    @patch("app.agents.langgraph.research_agent.WorkflowCapabilityExecutor")
    def test_end_to_end_context_flow(
        self,
        mock_executor_class,
        mock_retriever_class,
        mock_service_class,
        mock_db,
        mock_research_result,
    ):
        """Test complete flow: context adapter -> agent -> LLM -> research -> response."""
        # Setup mock services
        mock_message = Mock()
        mock_message.role = "user"
        mock_message.content = "Previous research request"

        mock_service = Mock()
        mock_service.list_recent_messages.return_value = [mock_message]
        mock_service_class.return_value = mock_service

        mock_retriever = Mock()
        mock_retriever.retrieve_relevant_memories.return_value = [
            {
                "id": "mem_1",
                "memory_type": "research",
                "content": "We discussed this last week",
                "score": 40.0,
            }
        ]
        mock_retriever_class.return_value = mock_retriever

        # Setup research executor
        mock_outcome = Mock()
        mock_outcome.state = "COMPLETED"
        mock_outcome.output = mock_research_result

        mock_executor = Mock()
        mock_executor.execute.return_value = mock_outcome
        mock_executor_class.return_value = mock_executor

        # Build context from services
        adapter = ContextAdapter(db=mock_db)
        context = adapter.build_research_context(
            user_id="user123",
            query="research topic",
            conversation_id="conv_xyz",
        )

        # Verify context was built
        assert context.user_id == "user123"
        assert len(context.conversation_history) == 1
        assert len(context.relevant_memories) == 1

        # Create agent with context
        llm = MockLLM()
        agent = ResearchAgent(
            llm=llm,
            db=mock_db,
            user_id="user123",
            initial_context=context,
        )

        # Run agent
        result = agent.invoke("Research competitors")

        # Verify flow completed
        assert result["relevant_context"] == context
        assert result["research_result"] is not None
        assert result["final_response"] != ""
        # Verify research was called
        mock_executor.execute.assert_called()
