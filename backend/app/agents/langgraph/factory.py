"""Factory for creating LangGraph agents with CEASER integrations."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

from app.agents.langgraph.research_agent import ResearchAgent
from app.agents.langgraph.model_adapter import CeaserModelAdapter
from app.agents.langgraph.context_adapter import ResearchContext


def create_research_agent(
    db: Session,
    user_id: str,
    llm: BaseChatModel | None = None,
    initial_context: ResearchContext | None = None,
) -> ResearchAgent:
    """Create a LangGraph-based research agent.

    Args:
        db: SQLAlchemy database session (required for capability execution and context)
        user_id: Current user ID (required for capability execution)
        llm: Optional LangChain-compatible LLM.
             If None, uses CEASER's ModelRouter via adapter.
        initial_context: Optional ResearchContext from CEASER services.
                        Provides conversation history and relevant memories.

    Returns:
        Configured ResearchAgent ready for use
    """
    if llm is None:
        # Use CEASER's existing ModelRouter
        from app.intelligence.ai.llm.registry import llm_registry

        # Get the ModelRouter instance from the registry
        model_router = llm_registry.router
        llm = CeaserModelAdapter(model_router=model_router)

    return ResearchAgent(llm=llm, db=db, user_id=user_id, initial_context=initial_context)

