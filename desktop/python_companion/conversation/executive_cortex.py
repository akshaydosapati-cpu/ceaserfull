from __future__ import annotations

import re

from core.schemas import CommandRequest, CortexDecision, IntentResult


class ExecutiveCortex:
    """Routing-only front door for CEASER Desktop Brain.

    It decides where a request should go. It never executes actions.
    """

    DESKTOP_PATTERN = re.compile(
        r"\b(open|launch|start|run|close|quit|exit|delete|remove|downloads|documents|folder|file|screenshot|screen\s*shot|volume|mute|unmute|battery|charge|charging|weather|temperature|forecast|play|pause|resume|next|previous|skip|rewind|forward|backward|settings|calculator|chrome|edge|notepad|google|search|look up|lookup|bluetooth|wi-?fi|wireless|brightness|recycle bin|file explorer|explorer|maximize|minimize|switch)\b",
        re.IGNORECASE,
    )
    GITHUB_PATTERN = re.compile(r"\b(github|repo|repository|repositories|commit|commits|issue|issues|pull request|pull requests|readme|branch|branches)\b", re.IGNORECASE)
    NOTION_PATTERN = re.compile(r"\b(notion|workspace|page|database|task|tasks|notes|meeting|meetings)\b", re.IGNORECASE)
    CLOUD_PATTERN = re.compile(
        r"\b(my\s+(?:latest\s+)?(?:document|documents|file|files|report|reports|proposal)|ceaser\s+(?:cloud|document|documents|file|files|report|reports|proposal)|cloud|latest\s+(?:document|documents|file|files|report|reports|proposal)|document|documents|file|files|report|reports|proposal|upload|download|rename|restore|deleted|search my files|search files)\b",
        re.IGNORECASE,
    )
    WORKFLOW_PATTERN = re.compile(r"\b(workflow|plan my|prepare me|viva|quiz me|roadmap|checklist|multi[- ]?step|automate this|organize my|save it to notion|save .* to notion|today.*work)\b", re.IGNORECASE)
    AI_PATTERN = re.compile(
        r"\b(explain|tell me|what is|what's|who is|why|how|write|draft|create|generate|"
        r"summarize|summarise|compare|research|brief|teach|translate|define|"
        r"can you|could you|would you|give me|i want to know|what do you think|"
        r"do you think|your opinion|your thoughts|thoughts on|talk about|discuss|describe)\b|\?$",
        re.IGNORECASE,
    )
    KNOWLEDGE_PATTERN = re.compile(
        r"\b(ceaser|desktop brain|working memory|world model|semantic world|planner|workflow confirmation|confirmation workflow|capabilit(?:y|ies)|available commands|what can you do|notion write|github capability|safety rule|requires confirmation|require confirmation|actions require confirmation|porcupine|ipc|architecture)\b",
        re.IGNORECASE,
    )
    MEMORY_PATTERN = re.compile(
        r"\b(remember that|remember this|forget that|forget my|clear my .*memory|what do you remember about me|show my memories|list memories|do not remember this session|disable memory for this session)\b",
        re.IGNORECASE,
    )

    def route(self, request: CommandRequest, context: dict, intent_router) -> CortexDecision:
        text = request.normalized_text or request.raw_text or ""
        lowered = text.lower()
        references = context.get("references") or {}
        world_model = context.get("_world_model")
        world_evidence = {}
        if world_model and hasattr(world_model, "evidence_for_text"):
            world_evidence = world_model.evidence_for_text(text, session_id=request.session_id)
        prediction = context.get("prediction") or {}
        signals = {
            "desktop": bool(self.DESKTOP_PATTERN.search(text)),
            "github": bool(self.GITHUB_PATTERN.search(text)),
            "notion": bool(self.NOTION_PATTERN.search(text)),
            "cloud": bool(self.CLOUD_PATTERN.search(text)),
            "workflow": bool(self.WORKFLOW_PATTERN.search(text)),
            "ai": bool(self.AI_PATTERN.search(text)),
            "knowledge": bool(self.KNOWLEDGE_PATTERN.search(text)),
            "memory": bool(self.MEMORY_PATTERN.search(text)),
            "follow_up": bool(references.get("follow_up_detected")),
            "world_entities_used": world_evidence.get("world_entities_used", []),
            "world_relationships_used": world_evidence.get("world_relationships_used", []),
            "world_resolution_reason": world_evidence.get("world_resolution_reason", ""),
            "prediction_summary": prediction.get("summary", ""),
            "prediction_evidence": prediction.get("predictions", [])[:3],
        }

        if not text.strip():
            return CortexDecision(
                destination="unsupported",
                intent=IntentResult(intent="empty", capability="unsupported", confidence=1.0, route="unsupported"),
                reason="empty_input",
                signals=signals,
            )

        if signals["memory"]:
            return CortexDecision(
                destination="memory",
                intent=IntentResult(intent="memory_command", capability=self._memory_capability(lowered), confidence=0.94, route="memory"),
                reason="memory_signal",
                signals=signals,
            )

        if signals["knowledge"] and not self._is_integration_action(lowered) and not signals["workflow"] and not signals["desktop"]:
            return CortexDecision(
                destination="knowledge",
                intent=IntentResult(intent="knowledge_query", capability="knowledge.query", confidence=0.82, route="knowledge"),
                reason="knowledge_signal",
                signals=signals,
            )

        if signals["workflow"]:
            return CortexDecision(
                destination="workflow",
                intent=IntentResult(intent="workflow_request", capability="workflow.plan", confidence=0.72, route="workflow"),
                reason="workflow_signal",
                signals=signals,
            )

        resolved_intent = intent_router.resolve(text, context)

        # Device controls are concrete native capabilities. They must win
        # before conversational wording such as "what is" can redirect a
        # request to cloud AI. App keywords in a diagnostic question still
        # stay conversational (for example, "Chrome is not opening, why?").
        explicit_native_action = re.match(
            r"^\s*(?:(?:can|could|would)\s+you\s+|please\s+)?(?:open|launch|start|run|close|quit|exit|set|pause|resume|play|stop|take|capture|switch|turn|enable|disable|increase|decrease|minimize|maximize)\b",
            lowered,
        )
        is_native_status_query = resolved_intent.capability in {"desktop.get_battery", "ai.weather"}
        if (
            resolved_intent.route == "desktop"
            and resolved_intent.confidence >= 0.85
            and (not signals["ai"] or is_native_status_query or explicit_native_action)
        ):
            return CortexDecision(destination="desktop", intent=resolved_intent, reason="desktop_intent", signals=signals)

        # Explicit local imperatives remain fast even when polite wording such
        # as "can you" also matches the conversational signal set.
        if resolved_intent.route == "desktop" and re.match(
            r"^\s*(?:(?:can|could|would)\s+you\s+|please\s+)?(?:open|launch|start|run|close|quit|exit|set|pause|resume|play|stop|take|capture|switch|minimize|maximize)\b",
            lowered,
        ):
            return CortexDecision(destination="desktop", intent=resolved_intent, reason="desktop_signal", signals=signals)
        if resolved_intent.route == "desktop" and resolved_intent.intent == "battery_status":
            return CortexDecision(destination="desktop", intent=resolved_intent, reason="desktop_signal", signals=signals)

        # A provider or desktop keyword inside a question is context, not an
        # execution request. Only explicit integration operations or personal
        # connected-account queries should outrank conversational AI.
        if signals["ai"] and not self._is_integration_action(lowered) and not self._is_personal_integration_query(lowered):
            return CortexDecision(
                destination="backend_ai",
                intent=IntentResult(intent="general_ai", capability="ai.answer", confidence=0.78, route="backend_ai"),
                reason="ai_signal",
                signals=signals,
            )

        if signals["github"]:
            intent = self._github_intent(lowered, references)
            self._apply_world_evidence(intent, world_evidence)
            return CortexDecision(destination="integration", intent=intent, reason="github_signal", signals=signals)

        if signals["notion"]:
            intent = self._notion_intent(lowered)
            self._apply_world_evidence(intent, world_evidence)
            return CortexDecision(destination="integration", intent=intent, reason="notion_signal", signals=signals)

        if resolved_intent.route == "desktop":
            return CortexDecision(destination="desktop", intent=resolved_intent, reason="desktop_intent", signals=signals)

        if signals["cloud"] and not (
            re.search(r"\b(write|draft|prepare|generate)\b", lowered)
            and not re.search(r"\b(ceaser\s+cloud|cloud|upload|save|store)\b", lowered)
        ):
            intent = self._cloud_intent(lowered)
            self._apply_world_evidence(intent, world_evidence)
            return CortexDecision(destination="integration", intent=intent, reason="cloud_resource_signal", signals=signals)

        if signals["follow_up"]:
            intent = intent_router.resolve(text, context)
            intent = self.evaluate(intent, context)
            return CortexDecision(destination=intent.route, intent=intent, reason="conversation_follow_up", signals=signals)

        if signals["desktop"]:
            intent = intent_router.resolve(text, context)
            if intent.route == "desktop":
                return CortexDecision(destination=intent.route, intent=intent, reason="desktop_signal", signals=signals)
            if len(text.split()) >= 2:
                return CortexDecision(
                    destination="backend_ai",
                    intent=IntentResult(intent="general_ai", capability="ai.answer", confidence=0.66, route="backend_ai"),
                    reason="desktop_mention_not_command",
                    signals=signals,
                )
            return CortexDecision(destination=intent.route, intent=intent, reason="desktop_signal", signals=signals)

        if signals["ai"]:
            return CortexDecision(
                destination="backend_ai",
                intent=IntentResult(intent="general_ai", capability="ai.answer", confidence=0.74, route="backend_ai"),
                reason="ai_signal",
                signals=signals,
            )

        intent = intent_router.resolve(text, context)
        if intent.route == "unsupported" and intent.entities.get("unsupported_category"):
            return CortexDecision(destination="unsupported", intent=intent, reason="known_unsupported_request", signals=signals)
        if (
            intent.route == "unsupported"
            and len(re.findall(r"[a-zA-Z0-9]+", text)) >= 2
            and not re.search(r"\b(this|that|thing|it)\b", lowered)
        ):
            return CortexDecision(
                destination="backend_ai",
                intent=IntentResult(intent="general_ai", capability="ai.answer", confidence=0.62, route="backend_ai"),
                reason="natural_language_default",
                signals=signals,
            )
        return CortexDecision(destination=intent.route, intent=intent, reason="router_default", signals=signals)

    def evaluate(self, intent: IntentResult, context: dict) -> IntentResult:
        if context.get("references", {}).get("follow_up_detected") and intent.route == "unsupported":
            return IntentResult(
                intent="follow_up",
                capability="ai.answer",
                confidence=0.68,
                entities={"resolved_reference": context.get("references", {}).get("resolved_reference")},
                route="backend_ai",
            )
        return intent

    def _github_intent(self, lowered: str, references: dict) -> IntentResult:
        if "commit" in lowered:
            capability = "github.list_commits"
            intent = "github_list_commits"
        elif "issue" in lowered:
            capability = "github.list_issues"
            intent = "github_list_issues"
        elif "pull request" in lowered or "pull requests" in lowered:
            capability = "github.list_pull_requests"
            intent = "github_list_pull_requests"
        elif "readme" in lowered or "summarize" in lowered or "summary" in lowered:
            capability = "github.summarize_repository"
            intent = "github_summarize_repository"
        else:
            capability = "github.list_repositories"
            intent = "github_list_repositories"
        return IntentResult(intent=intent, capability=capability, confidence=0.86, route="integration", entities={"provider": "github"})

    def _notion_intent(self, lowered: str) -> IntentResult:
        if "task" in lowered:
            capability = "notion.list_tasks"
            intent = "notion_list_tasks"
        elif "database" in lowered:
            capability = "notion.search_pages"
            intent = "notion_search_databases"
        elif "create" in lowered or "add" in lowered or "append" in lowered:
            capability = "notion.create_page"
            intent = "notion_write_request"
        else:
            capability = "notion.search_pages"
            intent = "notion_search_pages"
        return IntentResult(intent=intent, capability=capability, confidence=0.84, route="integration", entities={"provider": "notion"})

    def _cloud_intent(self, lowered: str) -> IntentResult:
        if re.search(r"\b(delete|remove)\b", lowered):
            action = "delete"
        elif "restore" in lowered:
            action = "restore"
        elif "upload" in lowered:
            action = "upload"
        elif "download" in lowered:
            action = "download"
        elif re.search(r"\b(rename|update)\b", lowered):
            action = "update"
        elif re.search(r"\b(create|new)\b", lowered):
            action = "create"
        elif re.search(r"\b(search|find)\b", lowered):
            action = "search"
        elif "latest" in lowered:
            action = "latest"
        elif re.search(r"\b(read|open|show)\b", lowered):
            action = "read"
        else:
            action = "list"
        return IntentResult(
            intent=f"cloud_{action}",
            capability=f"cloud.{action}",
            confidence=0.82,
            route="integration",
            entities={"provider": "ceaser_cloud", "cloud_action": action},
        )

    def _apply_world_evidence(self, intent: IntentResult, world_evidence: dict) -> None:
        repository = world_evidence.get("resolved_repository") or {}
        project = world_evidence.get("resolved_project") or {}
        active_resource = world_evidence.get("active_resource") or {}
        if repository:
            intent.entities.setdefault("repository", repository.get("name"))
            intent.entities.setdefault("repository_entity_id", repository.get("id"))
        if project:
            intent.entities.setdefault("project", project.get("name"))
            intent.entities.setdefault("project_entity_id", project.get("id"))
        if active_resource:
            intent.entities.setdefault("active_resource", active_resource)
        if world_evidence.get("ambiguity_candidates"):
            intent.requires_clarification = True
            intent.clarification_question = "Which project should I use?"
            intent.entities.setdefault("ambiguity_candidates", world_evidence.get("ambiguity_candidates"))

    def _is_integration_action(self, lowered: str) -> bool:
        return bool(re.search(r"\b(show|list|sync|get|read|summarize|summarise|find|search|create|add)\b", lowered) and re.search(r"\b(commit|commits|repo|repository|repositories|issue|issues|pull request|pull requests|notion page|notion task|notion database)\b", lowered))

    def _is_personal_integration_query(self, lowered: str) -> bool:
        return bool(
            re.search(r"\b(my|our|connected)\b", lowered)
            and re.search(r"\b(github|repo|repository|repositories|commit|commits|notion|workspace|page|database|task|tasks|cloud|document|documents|file|files|report|reports)\b", lowered)
        )

    def _memory_capability(self, lowered: str) -> str:
        if "do not remember this session" in lowered or "disable memory for this session" in lowered:
            return "memory.disable_session"
        if lowered.startswith("forget") or lowered.startswith("clear my"):
            return "memory.forget"
        if "what do you remember" in lowered or "show my memories" in lowered or "list memories" in lowered:
            return "memory.list"
        return "memory.remember"
