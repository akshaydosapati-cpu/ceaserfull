from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.services.orchestrator.knowledge_router import KnowledgeRoute, RouteDecision


@dataclass(frozen=True)
class FastChatRequest:
    route: RouteDecision
    has_attachments: bool = False
    has_file_ids: bool = False
    report_requested: bool = False
    rich_context_required: bool = False
    live_web_requested: bool = False


class FastChatService:
    """Owns eligibility and minimal context assembly for direct chat."""

    @staticmethod
    def accepts(request: FastChatRequest) -> bool:
        return (
            request.route.route is KnowledgeRoute.GENERAL
            and not request.has_attachments
            and not request.has_file_ids
            and not request.report_requested
            and not request.rich_context_required
            and not request.live_web_requested
        )

    @staticmethod
    def build_context(
        *,
        route: RouteDecision,
        follow_up_trace: dict[str, Any],
        minimal_factory: Callable[[], dict[str, Any]],
        follow_up_factory: Callable[[dict[str, Any]], dict[str, Any]],
        allow_minimal: bool = False,
    ) -> dict[str, Any] | None:
        if route.route is KnowledgeRoute.FOLLOW_UP:
            return follow_up_factory(follow_up_trace)
        if route.route is KnowledgeRoute.GENERAL or allow_minimal:
            return minimal_factory()
        return None
