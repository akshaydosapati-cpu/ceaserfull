"""Tests for the LangGraph-based research agent.

Verifies that:
1. The agent can be constructed
2. Research tool calls existing CEASER capability (WorkflowCapabilityExecutor)
3. The agent produces final responses
4. ModelRouter adapter is wired and callable
5. No real network calls are made (mocked)
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
from app.agents.langgraph.model_adapter import CeaserModelAdapter
from app.agents.langgraph.factory import create_research_agent


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


class TestCeaserResearchTool:
    """Tests for the research tool adapter."""

    def test_research_tool_creation(self, mock_db):
        """Test that research tool can be created."""
        tool = CeaserResearchTool(db=mock_db, user_id="user123")
        assert tool.executor is not None
        assert tool.research is not None

    @patch("app.agents.langgraph.research_agent.WorkflowCapabilityExecutor")
    def test_research_tool_calls_capability_executor(self, mock_executor_class, mock_db):
        """Test that research tool calls WorkflowCapabilityExecutor with research.execute capability."""
        # Setup mock executor
        mock_outcome = Mock()
        mock_outcome.state = "COMPLETED"
        mock_outcome.output = {
            "query": "test query",
            "summary": "Research complete",
            "sources": [],
            "key_findings": [],
            "citations": [],
        }

        mock_executor = Mock()
        mock_executor.execute.return_value = mock_outcome
        mock_executor_class.return_value = mock_executor

        tool = CeaserResearchTool(db=mock_db, user_id="user123")
        result = tool.research("test query")

        # Verify it called execute with research.execute capability
        mock_executor.execute.assert_called_once()
        call_kwargs = mock_executor.execute.call_args[1]
        assert call_kwargs["capability"] == "research.execute"
        assert call_kwargs["user_id"] == "user123"
        assert call_kwargs["request"] == "test query"

        # Verify result is returned correctly
        assert isinstance(result, dict)
        assert "query" in result

    @patch("app.agents.langgraph.research_agent.WorkflowCapabilityExecutor")
    def test_research_tool_returns_capability_result(self, mock_executor_class, mock_db, mock_research_result):
        """Test that research tool returns capability executor result."""
        mock_outcome = Mock()
        mock_outcome.state = "COMPLETED"
        mock_outcome.output = mock_research_result

        mock_executor = Mock()
        mock_executor.execute.return_value = mock_outcome
        mock_executor_class.return_value = mock_executor

        tool = CeaserResearchTool(db=mock_db, user_id="user123")
        result = tool.research("machine learning")

        assert isinstance(result, dict)
        assert result["query"] == "machine learning"
        assert "sources" in result
        assert len(result["sources"]) > 0


class TestResearchAgent:
    """Tests for the LangGraph research agent."""

    def test_agent_creation(self, mock_db):
        """Test that research agent can be created."""
        llm = MockLLM()
        agent = ResearchAgent(llm=llm, db=mock_db, user_id="user123")
        assert agent.llm is not None
        assert agent.research_tool is not None
        assert agent.graph is not None

    def test_agent_graph_compilation(self, mock_db):
        """Test that agent graph can be compiled."""
        llm = MockLLM()
        agent = ResearchAgent(llm=llm, db=mock_db, user_id="user123")
        compiled_graph = agent.graph.compile()
        assert compiled_graph is not None

    def test_agent_analyze_node(self, mock_db):
        """Test the analyze node produces reasoning."""
        llm = MockLLM()
        agent = ResearchAgent(llm=llm, db=mock_db, user_id="user123")

        initial_state: ResearchAgentState = {
            "user_goal": "Explain machine learning",
            "messages": [{"role": "human", "content": "Explain machine learning"}],
            "research_result": None,
            "final_response": "",
        }

        result = agent._analyze_node(initial_state)

        assert "messages" in result
        assert len(result["messages"]) > len(initial_state["messages"])
        assert result["user_goal"] == "Explain machine learning"

    @patch("app.agents.langgraph.research_agent.WorkflowCapabilityExecutor")
    def test_agent_research_node_calls_capability(self, mock_executor_class, mock_db, mock_research_result):
        """Test the research node calls WorkflowCapabilityExecutor capability."""
        mock_outcome = Mock()
        mock_outcome.state = "COMPLETED"
        mock_outcome.output = mock_research_result

        mock_executor = Mock()
        mock_executor.execute.return_value = mock_outcome
        mock_executor_class.return_value = mock_executor

        llm = MockLLM()
        agent = ResearchAgent(llm=llm, db=mock_db, user_id="user123")

        state: ResearchAgentState = {
            "user_goal": "machine learning",
            "messages": [
                {"role": "human", "content": "machine learning"},
                {"role": "system", "content": "QUERY: machine learning"},
            ],
            "research_result": None,
            "final_response": "",
        }

        result = agent._research_node(state)

        # Verify research_result was populated from capability
        assert result["research_result"] is not None
        assert "sources" in result["research_result"]
        # Verify the capability executor was called
        mock_executor.execute.assert_called_once()

    def test_agent_synthesize_node(self, mock_db):
        """Test the synthesize node produces final response."""
        llm = MockLLM()
        agent = ResearchAgent(llm=llm, db=mock_db, user_id="user123")

        state: ResearchAgentState = {
            "user_goal": "machine learning",
            "messages": [{"role": "human", "content": "machine learning"}],
            "research_result": {
                "query": "machine learning",
                "sources": [{"title": "ML Guide", "url": "https://example.com"}],
            },
            "final_response": "",
        }

        result = agent._synthesize_node(state)

        assert result["final_response"] != ""
        assert len(result["messages"]) > len(state["messages"])

    @patch("app.agents.langgraph.research_agent.WorkflowCapabilityExecutor")
    def test_agent_invoke_full_flow(self, mock_executor_class, mock_db, mock_research_result):
        """Test agent invoke runs full flow with capability executor."""
        mock_outcome = Mock()
        mock_outcome.state = "COMPLETED"
        mock_outcome.output = mock_research_result

        mock_executor = Mock()
        mock_executor.execute.return_value = mock_outcome
        mock_executor_class.return_value = mock_executor

        llm = MockLLM()
        agent = ResearchAgent(llm=llm, db=mock_db, user_id="user123")

        result = agent.invoke("Tell me about machine learning")

        assert "user_goal" in result
        assert "messages" in result
        assert "final_response" in result
        assert result["final_response"] != ""
        assert "research_result" in result
        # Verify capability executor was called during flow
        mock_executor.execute.assert_called()


class TestModelAdapter:
    """Tests for the CeaserModelAdapter."""

    def test_adapter_creation_with_router(self):
        """Test model adapter can be created with router."""
        mock_router = Mock()
        adapter = CeaserModelAdapter(model_router=mock_router)
        assert adapter.model_router is not None
        assert adapter._llm_type == "ceaser_model_router"

    def test_adapter_error_without_router(self):
        """Test adapter raises error if router is None."""
        with pytest.raises(ValueError, match="model_router is required"):
            CeaserModelAdapter(model_router=None)

    def test_adapter_generate_with_messages(self):
        """Test adapter can generate responses from messages."""
        from langchain_core.messages import HumanMessage, SystemMessage

        mock_router = Mock()
        # Mock the async generate method
        import asyncio

        async def mock_generate(*args, **kwargs):
            response = Mock()
            response.content = "Generated response"
            return response

        mock_router.generate = mock_generate

        adapter = CeaserModelAdapter(model_router=mock_router)

        messages = [
            SystemMessage(content="You are helpful"),
            HumanMessage(content="Hello"),
        ]

        result = adapter._generate(messages)

        assert result is not None
        assert len(result.generations) > 0
        assert len(result.generations[0]) > 0

    def test_adapter_error_without_initialized_router(self):
        """Test adapter raises error if router becomes None during generate."""
        from langchain_core.messages import HumanMessage

        adapter = CeaserModelAdapter(model_router=Mock())
        adapter.model_router = None  # Simulate uninitialized router

        messages = [HumanMessage(content="test")]

        with pytest.raises(RuntimeError, match="ModelRouter not initialized"):
            adapter._generate(messages)


class TestFactory:
    """Tests for the agent factory."""

    def test_create_research_agent_with_explicit_llm(self, mock_db):
        """Test factory creates agent with explicit LLM."""
        llm = MockLLM()
        agent = create_research_agent(db=mock_db, user_id="user123", llm=llm)

        assert isinstance(agent, ResearchAgent)
        assert agent.llm is llm

    @patch("app.intelligence.ai.llm.registry.llm_registry")
    def test_create_research_agent_with_model_router(self, mock_registry, mock_db):
        """Test factory creates agent with ModelRouter when no LLM provided."""
        # Mock the registry and model router
        mock_router = Mock()
        mock_registry.router = mock_router

        # Import after patch is in place
        from app.agents.langgraph.factory import create_research_agent

        agent = create_research_agent(db=mock_db, user_id="user123")

        assert isinstance(agent, ResearchAgent)
        assert isinstance(agent.llm, CeaserModelAdapter)
        assert agent.llm.model_router is mock_router
