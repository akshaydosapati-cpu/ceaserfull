from app.services.execution_paths import FastChatRequest, FastChatService
from app.services.orchestrator.knowledge_router import KnowledgeRoute, RouteDecision


def decision(route: KnowledgeRoute) -> RouteDecision:
    return RouteDecision(route=route, reason="test")


def test_fast_chat_accepts_only_plain_general_chat():
    service = FastChatService()
    assert service.accepts(FastChatRequest(route=decision(KnowledgeRoute.GENERAL)))
    assert not service.accepts(FastChatRequest(route=decision(KnowledgeRoute.RESEARCH)))
    assert not service.accepts(FastChatRequest(route=decision(KnowledgeRoute.GENERAL), has_attachments=True))
    assert not service.accepts(FastChatRequest(route=decision(KnowledgeRoute.GENERAL), live_web_requested=True))


def test_fast_chat_builds_bounded_follow_up_context_without_deep_context():
    service = FastChatService()
    calls = {"minimal": 0, "follow_up": 0}

    def minimal():
        calls["minimal"] += 1
        return {"mode": "minimal"}

    def follow_up(trace):
        calls["follow_up"] += 1
        return {"mode": "follow_up", "topic": trace["active_topic"]}

    context = service.build_context(
        route=decision(KnowledgeRoute.FOLLOW_UP),
        follow_up_trace={"active_topic": "recursion"},
        minimal_factory=minimal,
        follow_up_factory=follow_up,
    )
    assert context == {"mode": "follow_up", "topic": "recursion"}
    assert calls == {"minimal": 0, "follow_up": 1}
