"""LangGraph-based research agent for CEASER.

Implements the "Alex" research specialist using LangGraph.
This is an isolated, experimental agent that does not affect production paths.

Architecture:
  LangGraph Research Agent (Alex)
    ↓ uses
  CEASER Research Tool (adapter)
    ↓ calls
  existing WorkflowCapabilityExecutor
    ↓
  existing ResearchEngine
"""
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from app.services.workflows.capability_executor import WorkflowCapabilityExecutor, CapabilityOutcome
from app.agents.langgraph.context_adapter import ResearchContext


class ResearchAgentState(TypedDict):
    """State for the research agent graph.

    Carries research goal, execution messages, context from CEASER,
    research results, and final response.
    """
    user_goal: str
    messages: list[dict[str, str]]
    relevant_context: ResearchContext | None
    research_result: dict[str, Any] | None
    final_response: str


class CeaserResearchTool:
    """Adapter that exposes existing CEASER research capability as a LangGraph tool.

    Calls the existing WorkflowCapabilityExecutor.execute("research.execute")
    rather than directly instantiating ResearchEngine, preserving existing behavior.
    """

    def __init__(self, db: Session, user_id: str):
        self.executor = WorkflowCapabilityExecutor(db)
        self.db = db
        self.user_id = user_id

    def research(self, query: str) -> dict[str, Any]:
        """Call existing CEASER research capability via WorkflowCapabilityExecutor.

        Args:
            query: User research goal/query

        Returns:
            Research result with sources, citations, key findings
        """
        outcome: CapabilityOutcome = self.executor.execute(
            capability="research.execute",
            user_id=self.user_id,
            request=query,
            inputs={},
            confirmed=False,
        )

        if outcome.state == "COMPLETED" and outcome.output:
            return outcome.output
        return {
            "query": query,
            "summary": outcome.message,
            "sources": [],
            "key_findings": [],
            "citations": [],
        }


class ResearchAgent:
    """LangGraph-based research agent.

    Uses official LangGraph API to create a research workflow that:
    1. Receives a research-oriented user goal
    2. Reasons about whether research is required
    3. Calls CEASER research tool when appropriate
    4. Produces a research-oriented answer
    """

    def __init__(self, llm: BaseChatModel, db: Session, user_id: str, initial_context: ResearchContext | None = None):
        """Initialize the research agent.

        Args:
            llm: LangChain-compatible language model
            db: SQLAlchemy database session
            user_id: Current user ID for capability execution
            initial_context: Optional context from existing CEASER services
        """
        self.llm = llm
        self.db = db
        self.user_id = user_id
        self.initial_context = initial_context
        self.research_tool = CeaserResearchTool(db=db, user_id=user_id)
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph research workflow."""
        graph = StateGraph(ResearchAgentState)

        # Define nodes
        graph.add_node("analyze", self._analyze_node)
        graph.add_node("research", self._research_node)
        graph.add_node("synthesize", self._synthesize_node)

        # Define edges
        graph.add_edge("analyze", "research")
        graph.add_edge("research", "synthesize")
        graph.add_edge("synthesize", END)

        # Set entry point
        graph.set_entry_point("analyze")

        return graph

    def _analyze_node(self, state: ResearchAgentState) -> dict[str, Any]:
        """Analyze whether research is needed for the user goal."""
        # Build context string if available
        context_str = ""
        if state.get("relevant_context"):
            context_str = ResearchContext.format_for_llm(state["relevant_context"])
            if context_str:
                context_str = f"\n\n{context_str}"

        system_prompt = f"""You are a research assistant. Analyze the user's goal and determine:
1. Whether research is required
2. What specific query to research (if needed)
3. Confidence in your analysis

Respond with:
RESEARCH_NEEDED: yes/no
QUERY: [specific research query if needed, or "none"]
REASONING: [brief explanation]{context_str if context_str else ""}"""

        response = self.llm.invoke(
            [
                {"type": "system", "content": system_prompt},
                {"type": "human", "content": f"User goal: {state['user_goal']}"},
            ]
        )

        analysis_text = response.content if hasattr(response, "content") else str(response)

        return {
            **state,
            "messages": [
                *state.get("messages", []),
                {"role": "system", "content": f"Analysis: {analysis_text}"},
            ],
        }

    def _research_node(self, state: ResearchAgentState) -> dict[str, Any]:
        """Execute research using CEASER research capability."""
        # Extract query from analysis
        analysis_text = state["messages"][-1]["content"] if state.get("messages") else ""

        # Simple extraction (in production, use more robust parsing)
        if "QUERY: none" in analysis_text or "RESEARCH_NEEDED: no" in analysis_text:
            return {**state, "research_result": None}

        # Extract query from QUERY: line
        query = state["user_goal"]  # Default to user goal
        for line in analysis_text.split("\n"):
            if line.startswith("QUERY:"):
                query = line.replace("QUERY:", "").strip()
                if query and query != "none":
                    break

        if not query or query == "none":
            return {**state, "research_result": None}

        # Call existing CEASER research capability via WorkflowCapabilityExecutor
        research_result = self.research_tool.research(query)

        return {
            **state,
            "research_result": research_result,
            "messages": [
                *state.get("messages", []),
                {
                    "role": "system",
                    "content": f"Research completed: {len(research_result.get('sources', []))} sources found",
                },
            ],
        }

    def _synthesize_node(self, state: ResearchAgentState) -> dict[str, Any]:
        """Synthesize final research-oriented answer."""
        # Build context string if available
        context_str = ""
        if state.get("relevant_context"):
            context_str = ResearchContext.format_for_llm(state["relevant_context"])
            if context_str:
                context_str = f"\n\n{context_str}"

        system_prompt = f"""You are a research synthesis expert. Based on the research results provided,
create a comprehensive, well-sourced research answer to the user's goal.

Include:
- Clear summary of findings
- Key sources and citations
- Recommendations or next steps
- Confidence level{context_str if context_str else ""}"""

        context_info = ""
        if state.get("research_result"):
            context_info = f"""Research Results:
Summary: {state['research_result'].get('summary')}
Key Findings: {state['research_result'].get('key_findings')}
Source Count: {len(state['research_result'].get('sources', []))}"""

        response = self.llm.invoke(
            [
                {"type": "system", "content": system_prompt},
                {
                    "type": "human",
                    "content": f"""User Goal: {state['user_goal']}

{context_info}

Please provide a research-oriented answer.""",
                },
            ]
        )

        final_response = response.content if hasattr(response, "content") else str(response)

        return {
            **state,
            "final_response": final_response,
            "messages": [
                *state.get("messages", []),
                {"role": "assistant", "content": final_response},
            ],
        }

    def invoke(self, user_goal: str) -> dict[str, Any]:
        """Run the research agent on a user goal.

        Args:
            user_goal: Research-oriented goal from user

        Returns:
            Final state with research_result and final_response
        """
        initial_state: ResearchAgentState = {
            "user_goal": user_goal,
            "messages": [{"role": "human", "content": user_goal}],
            "relevant_context": self.initial_context,
            "research_result": None,
            "final_response": "",
        }

        # Compile and run the graph
        compiled_graph = self.graph.compile()
        final_state = compiled_graph.invoke(initial_state)

        return final_state
