"""Context adapter for integrating CEASER context services with LangGraph.

This adapter provides a small boundary between existing CEASER context services
and the LangGraph Alex agent, allowing the agent to access conversation history,
relevant memories, and user context without duplicating those services.

Architecture:
  Existing CEASER context services
    ↓
  ContextAdapter (this module)
    ↓
  LangGraph Alex state (relevant_context field)
    ↓
  LLM via ModelRouter
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.services.orchestrator.memory_retriever import MemoryRetriever
from app.services.conversation_service import ConversationService


@dataclass
class ResearchContext:
    """Minimal context container for LangGraph research agent.

    Carries only the information needed by Alex for research execution.
    Does NOT duplicate CEASER's memory/context storage.
    """
    conversation_history: list[dict[str, str]]
    relevant_memories: list[dict[str, Any]]
    user_id: str
    conversation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for LangGraph state."""
        return {
            "conversation_history": self.conversation_history,
            "relevant_memories": self.relevant_memories,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
        }

    @staticmethod
    def format_for_llm(context: ResearchContext | None) -> str:
        """Format context for inclusion in LLM prompts."""
        if not context:
            return ""

        parts = []

        if context.conversation_history:
            parts.append("## Recent Conversation")
            for msg in context.conversation_history[-5:]:  # Last 5 messages
                role = msg.get("role", "unknown").upper()
                content = msg.get("content", "")
                parts.append(f"{role}: {content}")

        if context.relevant_memories:
            parts.append("\n## Relevant Context")
            for memory in context.relevant_memories[:3]:  # Top 3 memories
                memory_type = memory.get("memory_type", "note")
                content = memory.get("content", "")
                score = memory.get("score", 0)
                parts.append(f"[{memory_type} - relevance: {score:.1f}] {content}")

        return "\n".join(parts) if parts else ""


class ContextAdapter:
    """Adapter providing CEASER context to LangGraph agents.

    Reuses existing MemoryRetriever and ConversationService to populate
    research context without duplicating those systems.

    Pattern:
      1. Caller provides conversation_id (optional) and user query
      2. Adapter fetches conversation history from ConversationService
      3. Adapter ranks relevant memories from MemoryRetriever
      4. Adapter returns ResearchContext with both
      5. LangGraph state includes context
      6. LLM receives formatted context in prompts
    """

    def __init__(self, db: Session):
        """Initialize adapter with database session.

        Args:
            db: SQLAlchemy database session for accessing CEASER services
        """
        self.db = db
        self.memory_retriever = MemoryRetriever(db)
        self.conversation_service = ConversationService(db)

    def build_research_context(
        self,
        user_id: str,
        query: str,
        conversation_id: str | None = None,
        message_limit: int = 10,
        memory_limit: int = 5,
    ) -> ResearchContext:
        """Build research context from existing CEASER services.

        Retrieves conversation history and relevant memories to provide
        context for the research agent without duplicating those services.

        Args:
            user_id: Current user ID
            query: Current research query/goal
            conversation_id: Optional existing conversation ID
            message_limit: Max messages to include (default 10)
            memory_limit: Max memories to include (default 5)

        Returns:
            ResearchContext with conversation history and relevant memories
        """
        # Fetch conversation history if conversation_id provided
        conversation_history = []
        if conversation_id:
            try:
                messages = self.conversation_service.list_recent_messages(
                    conversation_id=conversation_id,
                    limit=message_limit,
                )
                conversation_history = [
                    {
                        "role": msg.role,
                        "content": msg.content,
                    }
                    for msg in messages
                ]
            except Exception:
                # Silently continue if conversation fetch fails
                # (conversation_id may not be valid, service may be unavailable)
                pass

        # Fetch relevant memories
        relevant_memories = []
        try:
            relevant_memories = self.memory_retriever.retrieve_relevant_memories(
                user_id=user_id,
                query=query,
                limit=memory_limit,
            )
        except Exception:
            # Silently continue if memory retrieval fails
            # (user may have no memories, service may be temporarily unavailable)
            pass

        return ResearchContext(
            conversation_history=conversation_history,
            relevant_memories=relevant_memories,
            user_id=user_id,
            conversation_id=conversation_id,
        )
