from __future__ import annotations

import asyncio

from app.intelligence.orchestrator.intent_engine import intent_engine
from app.intelligence.orchestrator.models import IntentType, RequestContext
from app.services.orchestrator.knowledge_router import KnowledgeRoute, KnowledgeRouter


def context(message: str) -> RequestContext:
    return RequestContext(user_id="user-a", message=message, metadata={})


def test_simple_chat_does_not_request_memory():
    request = context("Hello")
    assert asyncio.run(intent_engine.classify(request)) == IntentType.GENERAL_QUESTION
    assert KnowledgeRouter().classify(message=request.message, has_attached_files=False, is_follow_up=False).route == KnowledgeRoute.GENERAL


def test_memory_location_question_requests_memory():
    request = context("Where do I keep my DBMS notes?")
    assert asyncio.run(intent_engine.classify(request)) == IntentType.MEMORY_QUESTION
    assert KnowledgeRouter().classify(message=request.message, has_attached_files=False, is_follow_up=False).route == KnowledgeRoute.MEMORY


def test_previous_conversation_question_requests_memory():
    request = context("What were we discussing about CEASER yesterday?")
    assert asyncio.run(intent_engine.classify(request)) == IntentType.MEMORY_QUESTION
    assert KnowledgeRouter().classify(message=request.message, has_attached_files=False, is_follow_up=False).route == KnowledgeRoute.MEMORY
