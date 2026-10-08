from __future__ import annotations

import re

from sqlalchemy.orm import Session
from app.models.mixins import utc_now

from app.models.conversation import Conversation, Message
from app.intelligence.knowledge.repository import KnowledgeRepository
from app.repositories.conversation_repository import ConversationRepository


class ConversationService:
    def __init__(self, db: Session):
        self.conversations = ConversationRepository(db)
        self.db = db

    def list(self, user_id: str | None = None, limit: int = 50, offset: int = 0, archived: bool = False) -> list[Conversation]:
        return self.conversations.list(user_id=user_id, limit=limit, offset=offset, archived=archived)

    def get(self, conversation_id: str) -> Conversation | None:
        return self.conversations.get(conversation_id)

    def create(self, user_id: str, title: str | None = None) -> Conversation:
        title = title or "New Chat"
        conversation = self.conversations.create(user_id=user_id, title=title)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def rename(self, conversation: Conversation, title: str) -> Conversation:
        conversation = self.conversations.update_title(conversation=conversation, title=title)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def update(self, conversation: Conversation, title: str | None = None, pinned: bool | None = None, archived: bool | None = None, project_id: str | None = None, update_project: bool = False) -> Conversation:
        conversation = self.conversations.update(conversation=conversation, title=title, pinned=pinned, archived=archived, project_id=project_id, update_project=update_project)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def delete(self, conversation: Conversation) -> None:
        self.conversations.delete(conversation)
        self.db.commit()

    def list_messages(self, conversation_id: str | None = None, limit: int | None = 100, offset: int = 0) -> list[Message]:
        return self.conversations.list_messages(conversation_id=conversation_id, limit=limit, offset=offset)

    def list_recent_messages(self, conversation_id: str, limit: int = 24) -> list[Message]:
        return self.conversations.list_recent_messages(conversation_id=conversation_id, limit=limit)

    def update_state(self, conversation: Conversation, *, summary: str | None, state: dict) -> Conversation:
        conversation.conversation_summary = summary
        conversation.conversation_state = state
        conversation.summary_version = max(1, int(conversation.summary_version or 1))
        conversation.state_updated_at = utc_now()
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def create_pending(self, user_id: str, title: str | None = None) -> Conversation:
        """Create a conversation in the current transaction without committing."""
        return self.conversations.create(user_id=user_id, title=title or "New Chat")

    def create_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
        *,
        ingest_knowledge: bool = True,
    ) -> Message:
        message = self.conversations.create_message(conversation_id=conversation_id, role=role, content=content, metadata=metadata)
        conversation = self.conversations.get(conversation_id)
        if ingest_knowledge and conversation and role in {"user", "assistant"}:
            try:
                KnowledgeRepository(self.db).ingest_text(
                    user_id=conversation.user_id,
                    title=f"{role.title()} message - {conversation.title}",
                    content=content,
                    source_type="conversation_message",
                    conversation_id=conversation_id,
                    metadata={"role": role, "message_id": message.id, **(metadata or {})},
                )
            except Exception:
                pass
        self.db.commit()
        self.db.refresh(message)
        return message

    def begin_stream_turn(
        self,
        conversation: Conversation,
        *,
        user_content: str | None,
        user_metadata: dict | None,
        assistant_metadata: dict | None,
        title: str | None = None,
    ) -> Message:
        """Persist a deferred user turn and streaming assistant atomically."""
        if user_content is not None:
            self.conversations.create_message(
                conversation_id=conversation.id,
                role="user",
                content=user_content,
                metadata=user_metadata,
            )
        if title:
            self.conversations.update_title(conversation=conversation, title=title)
        assistant = self.conversations.create_message(
            conversation_id=conversation.id,
            role="assistant",
            content="",
            metadata=assistant_metadata,
        )
        self.db.commit()
        self.db.refresh(assistant)
        return assistant

    def generate_title(self, message: str) -> str:
        text = re.sub(r"\s+", " ", message).strip(" .!?\n\t")
        text = re.sub(
            r"^(?:(?:hey|hi)\s+ceaser[, ]+)?(?:(?:please|can you|could you|would you)\s+)?"
            r"(?:help me\s+)?(?:tell me about|tell me|explain|describe|check|show|give me|write|create|build|generate|make)\s+",
            "",
            text,
            flags=re.I,
        )
        text = re.sub(r"\b(?:and\s+)?(?:show|list|give me|tell me)\b", " ", text, flags=re.I)
        text = re.split(r"[.!?\n]", text, maxsplit=1)[0]
        text = re.sub(r"\b(?:using|with)\s+(?:html|css|javascript|typescript|python)(?:\s*(?:,|and|/|\+)\s*(?:html|css|javascript|typescript|python))*\b.*$", "", text, flags=re.I)
        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9+#.'-]*", text)
        filler = {"a", "an", "the", "my", "me", "some", "about", "for", "to", "in", "of", "that", "this", "and"}
        words = [word for word in words if word.lower() not in filler]
        if not words:
            return "New Chat"
        title = " ".join(words[:6])
        acronyms = {"ai", "api", "css", "html", "js", "llm", "seo", "sql", "ui", "ux"}
        title = " ".join(word.upper() if word.lower() in acronyms else word.capitalize() for word in title.split())
        return title[:72].strip() or "New Chat"
