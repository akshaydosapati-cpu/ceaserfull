from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re


class KnowledgeRoute(StrEnum):
    GENERAL = "general"
    FOLLOW_UP = "follow_up"
    RESEARCH = "research"
    FILE = "file"
    MEMORY = "memory"
    CALENDAR = "calendar"
    INTEGRATION = "integration"
    DESKTOP = "desktop"


@dataclass(frozen=True)
class RouteDecision:
    route: KnowledgeRoute
    reason: str

    @property
    def requires_retrieval(self) -> bool:
        return self.route in {KnowledgeRoute.FILE, KnowledgeRoute.MEMORY}

    @property
    def is_direct_llm(self) -> bool:
        return self.route is KnowledgeRoute.GENERAL


class KnowledgeRouter:
    """Cheap deterministic routing before any costly context or model work."""

    def classify(self, *, message: str, has_attached_files: bool, is_follow_up: bool) -> RouteDecision:
        text = message.lower().strip()
        if has_attached_files or any(term in text for term in ("this pdf", "this document", "uploaded file", "attached file")):
            return RouteDecision(KnowledgeRoute.FILE, "user file or document request")
        if any(term in text for term in (
            "my calendar", "my meetings", "meetings do i have", "meetings today",
            "meeting today", "calendar today", "calendar tomorrow", "events today",
            "my upcoming events", "upcoming events", "upcoming meetings",
            "events do i have", "what's on my calendar", "what is on my calendar",
            "next meeting", "my availability", "am i free",
        )):
            return RouteDecision(KnowledgeRoute.CALENDAR, "personal calendar request")
        if any(term in text for term in (
            "my emails", "my email", "read gmail", "read my gmail", "my inbox", "unread email", "unread mail",
            "my drive", "google drive", "my files in drive", "drive files", "drive documents",
            "my tasks", "google tasks", "my todo", "my to-do", "pending tasks",
            "google classroom", "classroom assignments", "my assignments", "my coursework", "my courses",
            "notion", "my notion", "notion page", "notion pages", "notion database", "notion databases", "notion workspace", "notion docs", "notion members", "notion users", "workspace members", "workspace users",
            "github", "git hub", "my repos", "my repositories", "my repository", "github repos", "github repositories", "github commits", "github issues", "github pull requests", "readme", "codebase",
        )):
            return RouteDecision(KnowledgeRoute.INTEGRATION, "connected personal data request")
        if any(term in text for term in ("repositories related", "repository related", "repos related", "repo related", "repositories in my account", "repos in my account", "my account repositories", "visible repositories", "visible repos")):
            return RouteDecision(KnowledgeRoute.INTEGRATION, "connected personal data request")
        if any(term in text for term in ("commit", "commits", "issue", "issues", "pull request", "pull requests", "readme")) and any(term in text for term in ("repository", "repositories", "repo", "repos", "project", "projects", "codebase")):
            return RouteDecision(KnowledgeRoute.INTEGRATION, "connected repository activity request")
        if any(text.startswith(prefix) for prefix in ("add task", "add a task", "create task", "create a task", "make task", "make a task", "new task")):
            return RouteDecision(KnowledgeRoute.INTEGRATION, "connected task creation request")
        if "project" in text and any(term in text for term in ("member", "members", "team", "collaborator", "collaborators", "who is working", "who are working")):
            return RouteDecision(KnowledgeRoute.MEMORY, "project membership request")
        if any(term in text for term in ("remember", "what do you know about me", "my preferences", "saved memory", "my memory", "my name is", "call me ", "i mentioned months ago", "i told you months ago", "years ago", "startup idea i mentioned", "where do i keep", "where is my", "what were we discussing")):
            return RouteDecision(KnowledgeRoute.MEMORY, "personal memory request")
        emerging_model = re.search(r"\b(?:gpt|got|gemini|claude|llama|grok|nemotron)\s*-?\s*\d+(?:\.\d+)?\b", text)
        corporate_event = bool(
            re.search(
                r"\b(?:acquisition|aquisition|buyout)\s+of\b|"
                r"\b(?:merger|merged)\s+with\b|"
                r"\b(?:acquired|acquire)\s+(?!mean\b|means\b|accounting\b)[a-z0-9]",
                text,
            )
        )
        if emerging_model or corporate_event or any(term in text for term in ("latest", "current", "today", "yesterday", "news", "live update", "recent", "this week", "this month", "this year", "stock price", "weather", "who won", "score", "stats", "statistics", "centuries", "records", "web search", "search the web", "look up online", "internet", "sources", "citations", "competitor", "market research", "knowledge cutoff", "till which year", "up to date")):
            return RouteDecision(KnowledgeRoute.RESEARCH, "fresh information request")
        if any(text.startswith(prefix) for prefix in ("open ", "launch ", "start ", "create folder ", "take screenshot", "read clipboard")):
            return RouteDecision(KnowledgeRoute.DESKTOP, "desktop command")
        if is_follow_up and not has_attached_files:
            return RouteDecision(KnowledgeRoute.FOLLOW_UP, "conversation continuation")
        return RouteDecision(KnowledgeRoute.GENERAL, "stable general knowledge")
