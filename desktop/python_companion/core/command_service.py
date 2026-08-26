from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from typing import Any

from awareness.awareness_engine import AwarenessEngine
from awareness.models import AwarenessDecision, AwarenessEvent
from awareness.producers.clipboard_producer import ClipboardProducer
from awareness.producers.desktop_producer import DesktopProducer
from awareness.producers.filesystem_producer import FilesystemProducer
from awareness.producers.git_producer import GitProducer
from awareness.producers.integration_producer import IntegrationProducer
from awareness.producers.producer_manager import ProducerManager
from awareness.producers.system_producer import SystemProducer
from capabilities.registry import CapabilityRegistry, build_default_registry
from capabilities.windows_runtime import WindowsCapabilityRuntime
from conversation.context_resolver import WorldContextResolver
from conversation.executive_cortex import ExecutiveCortex
from conversation.next_action_policy import NextActionPolicy
from conversation.proactive_conversation import ProactiveConversationEngine
from conversation.proactive_runtime import ProactiveRuntimeAdapter
from conversation.companion_personality import CompanionPersonalityEngine
from conversation.response_composer import ResponseComposer
from core.schemas import ActionResult, CommandRequest, CortexDecision, IntentResult, IpcV2Event
from experience.experience_engine import ExperienceEngine
from knowledge.knowledge_cortex import KnowledgeCortex
from long_term_memory.memory_manager import LongTermMemoryManager
from planning.confirmation_manager import ConfirmationManager
from planning.plan_validator import PlanValidator
from planning.task_planner import TaskPlanner
from planning.workflow_runner import WorkflowRunner
from planning.workflow_store import WorkflowStore
from prediction.prediction_engine import PredictionEngine
from reasoning.reasoning_cortex import ReasoningCortex
from routing.intent_router import IntentRouter
from routing.unsupported_handler import UnsupportedRequestHandler


logger = logging.getLogger("ceaser.desktop_brain")


class ContextResolver:
    def resolve(self, request: CommandRequest) -> dict[str, Any]:
        return dict(request.context or {})


class ExecutionEngine:
    def __init__(self, registry: CapabilityRegistry, legacy_handler: Callable[[str], dict[str, Any]], reasoning_cortex: ReasoningCortex | None = None) -> None:
        self.registry = registry
        self.legacy_handler = legacy_handler
        self.response_composer = ResponseComposer()
        self.reasoning_cortex = reasoning_cortex or ReasoningCortex()
        self.windows_runtime = WindowsCapabilityRuntime(legacy_handler)
        self.unsupported_handler = UnsupportedRequestHandler()

    def execute(self, request: CommandRequest, intent: IntentResult, context: dict[str, Any], decision: CortexDecision | None = None) -> ActionResult:
        capability = self.registry.get(intent.capability)
        if not capability or intent.route == "unsupported":
            return self.unsupported_handler.resolve(request, intent)
        if capability.risk_level == "blocked":
            return ActionResult(
                status="failed",
                capability=capability.name,
                summary="That action is blocked for safety.",
                verified=True,
                error_code="blocked_capability",
            )
        reasoning = self.reasoning_cortex.evaluate(request, decision, intent, context, capability)
        if not reasoning.allowed_to_execute:
            return self._reasoning_result(reasoning, intent)
        try:
            execution_text = self.response_composer.command_for_execution(request.normalized_text, intent, context)
            if capability.handler == "windows_runtime":
                arguments = {**dict(intent.entities or {}), **dict(context.get("capability_arguments") or {})}
                legacy = self.windows_runtime.execute(capability.name, arguments, execution_text)
            else:
                legacy = self.legacy_handler(execution_text)
            result = ActionResult.from_legacy(legacy, capability=capability.name)
            self._attach_reasoning(result, reasoning)
            result.evidence.setdefault("handler", capability.handler)
            result.evidence.setdefault("route", intent.route)
            result.evidence.setdefault("intent", intent.intent)
            if execution_text != request.normalized_text:
                result.evidence.setdefault("context_rewritten", True)
            return result
        except Exception as exc:  # noqa: BLE001 - normalize handler failures for the overlay.
            return ActionResult(
                status="failed",
                capability=capability.name,
                summary="I could not complete that command.",
                verified=False,
                retryable=True,
                error_code=type(exc).__name__,
                evidence={"handler": capability.handler, "route": intent.route, "intent": intent.intent},
            )

    def _reasoning_result(self, reasoning, intent: IntentResult) -> ActionResult:
        status = "needs_confirmation" if reasoning.decision == "request_confirmation" else "needs_input" if reasoning.requires_clarification else "failed"
        summary = reasoning.clarification_question or reasoning.safer_alternative or "I need more information before doing that."
        result = ActionResult(
            status=status,  # type: ignore[arg-type]
            capability=intent.capability,
            summary=summary,
            spoken_response=summary,
            verified=True,
            error_code=reasoning.reason if reasoning.decision == "block" else None,
        )
        self._attach_reasoning(result, reasoning)
        return result

    def _attach_reasoning(self, result: ActionResult, reasoning) -> None:
        result.evidence.setdefault("reasoning_decision", reasoning.decision)
        result.evidence.setdefault("reasoning_confidence", reasoning.confidence)
        result.evidence.setdefault("reasoning_evidence", reasoning.evidence)
        result.evidence.setdefault("conflicts_detected", reasoning.conflicts)
        result.evidence.setdefault("safer_alternative", reasoning.safer_alternative)
        result.evidence.setdefault("clarification_reason", reasoning.reason if reasoning.requires_clarification else "")


class CommandService:
    def __init__(
        self,
        legacy_handler: Callable[[str], dict[str, Any]],
        registry: CapabilityRegistry | None = None,
        intent_router: IntentRouter | None = None,
        context_resolver: ContextResolver | None = None,
        executive_cortex: ExecutiveCortex | None = None,
    ) -> None:
        self.registry = registry or build_default_registry()
        self.intent_router = intent_router or IntentRouter()
        self.context_resolver = context_resolver or WorldContextResolver()
        self.executive_cortex = executive_cortex or ExecutiveCortex()
        self.awareness_engine = AwarenessEngine()
        self.producer_manager = ProducerManager(
            self.awareness_engine,
            [
                DesktopProducer(),
                ClipboardProducer(),
                FilesystemProducer(),
                GitProducer(),
                IntegrationProducer(),
                SystemProducer(),
            ],
        )
        if hasattr(self.context_resolver, "awareness_engine"):
            self.context_resolver.awareness_engine = self.awareness_engine
        self.experience_engine = ExperienceEngine()
        if hasattr(self.context_resolver, "experience_engine"):
            self.context_resolver.experience_engine = self.experience_engine
        self.prediction_engine = PredictionEngine()
        if hasattr(self.context_resolver, "prediction_engine"):
            self.context_resolver.prediction_engine = self.prediction_engine
        self.reasoning_cortex = ReasoningCortex()
        self.execution_engine = ExecutionEngine(self.registry, legacy_handler, self.reasoning_cortex)
        self.next_action_policy = NextActionPolicy(self.registry)
        self.proactive_conversation = ProactiveConversationEngine()
        companion = self.execution_engine.response_composer.companion_engine
        proactive_personality = CompanionPersonalityEngine()
        self.proactive_runtime = ProactiveRuntimeAdapter(self.proactive_conversation, proactive_personality, companion.preferences)
        self.awareness_engine.subscribe(self.proactive_runtime.receive)
        self.long_term_memory = LongTermMemoryManager()
        if hasattr(self.context_resolver, "long_term_memory"):
            self.context_resolver.long_term_memory = self.long_term_memory
        self.knowledge_cortex = KnowledgeCortex(root=".", registry=self.registry)
        self.knowledge_cortex.load()
        self.task_planner = TaskPlanner(self.registry)
        self.workflow_runner = WorkflowRunner(
            self.execution_engine,
            PlanValidator(self.registry),
            ConfirmationManager(),
            WorkflowStore(),
        )

    def execute(self, request: CommandRequest) -> ActionResult:
        started = time.perf_counter()
        intent: IntentResult | None = None
        decision: CortexDecision | None = None
        fallback_used = False
        result: ActionResult | None = None
        context: dict[str, Any] = {}
        try:
            preflight_intent = self.intent_router.resolve(request.normalized_text, dict(request.context or {}))
            fast_local = preflight_intent.route == "desktop" and preflight_intent.confidence >= 0.8
            try:
                context = self.context_resolver.resolve(request, fast_local=fast_local)
            except TypeError:
                context = self.context_resolver.resolve(request)
            if fast_local:
                context["fast_local_context"] = True
            if self.workflow_runner.has_pending(request.session_id) and self._is_confirmation_reply(request.normalized_text):
                if self._is_negative_confirmation(request.normalized_text):
                    result = self.workflow_runner.cancel_pending(request.session_id)
                else:
                    result = self.workflow_runner.resume(request, context)
                intent = IntentResult(intent="workflow_confirmation_reply", capability="workflow.plan", confidence=0.96, route="workflow")
                decision = CortexDecision(destination="workflow", intent=intent, reason="pending_workflow_confirmation", signals={"planner_selected": True})
                result.evidence.setdefault("planner_selected", True)
                result.evidence.setdefault("workflow_resumed", result.status != "cancelled")
                result.evidence.setdefault("confirmation_reply", request.normalized_text)
                record_turn = getattr(self.context_resolver, "record_turn", None)
                if callable(record_turn):
                    record_turn(request, intent, result)
                return result
            if fast_local:
                # Concrete native commands do not need preference, memory,
                # prediction, or proactive processing before execution.
                intent = preflight_intent
                decision = CortexDecision(destination="desktop", intent=intent, reason="fast_local_preflight", signals={"desktop": True, "fast_local": True})
                result = self.execution_engine.execute(request, intent, context, decision)
                result.evidence.setdefault("cortex_destination", "desktop")
                result.evidence.setdefault("cortex_reason", "fast_local_preflight")
                record_turn = getattr(self.context_resolver, "record_turn", None)
                if callable(record_turn):
                    record_turn(request, intent, result)
                return result
            preference_updates = self.proactive_runtime.observe_user_message(request.user_id, request.normalized_text)
            if preference_updates:
                current = self.long_term_memory.companion_preferences(request.user_id)
                saved = self.long_term_memory.save_companion_preferences(request.user_id, {**current, **preference_updates})
                context["companion_preferences"] = saved.model_dump()
                stopped = not saved.social_proactivity
                intent = IntentResult(intent="social_preference_update", capability="conversation.proactive", confidence=0.96, route="conversation")
                decision = CortexDecision(destination="conversation", intent=intent, reason="explicit_social_preference")
                summary = "I will stop starting casual conversations." if stopped else "Understood. I can be a little more conversational."
                result = ActionResult(status="completed", capability="conversation.proactive", summary=summary, spoken_response=summary, verified=True)
                record_turn = getattr(self.context_resolver, "record_turn", None)
                if callable(record_turn):
                    record_turn(request, intent, result)
                return result
            if self.next_action_policy.is_negative(request.normalized_text):
                if self.next_action_policy.active(context):
                    self.next_action_policy.clear_active(context)
                    intent = IntentResult(intent="next_action_declined", confidence=0.96, route="conversation")
                    decision = CortexDecision(destination="conversation", intent=intent, reason="active_suggestion_declined")
                    result = ActionResult(status="completed", summary="Okay, I will leave that aside.", spoken_response="Okay.", verified=True)
                    return result
            if self.next_action_policy.is_affirmative(request.normalized_text):
                active_suggestion = self.next_action_policy.active(context)
                if active_suggestion:
                    self.next_action_policy.clear_active(context)
                    suggested_command = str(active_suggestion.get("command") or "").strip()
                    if suggested_command:
                        request = request.model_copy(update={
                            "raw_text": suggested_command,
                            "normalized_text": suggested_command,
                            "metadata": {**request.metadata, "suggestion_follow_up": True, "suggestion_origin": active_suggestion},
                        })
                        context["suggestion_follow_up"] = True
            references = context.get("references") or {}
            if references.get("clarification_required"):
                summary = str(references.get("clarification_question") or "What should I continue from?")
                intent = IntentResult(intent="continuation_clarification", capability="ai.answer", confidence=0.9, route="conversation", requires_clarification=True, clarification_question=summary)
                decision = CortexDecision(destination="conversation", intent=intent, reason="continuation_context_missing")
                result = ActionResult(status="needs_input", capability="ai.answer", summary=summary, spoken_response=summary, verified=True)
                record_turn = getattr(self.context_resolver, "record_turn", None)
                if callable(record_turn):
                    record_turn(request, intent, result)
                return result
            memory_result = self.long_term_memory.handle_command(request)
            if memory_result:
                intent = IntentResult(intent="memory_command", capability=memory_result.capability, confidence=0.96, route="memory")
                decision = CortexDecision(destination="memory", intent=intent, reason="memory_command", signals={"memory": True})
                result = memory_result
                result.evidence.setdefault("cortex_destination", "memory")
                result.evidence.setdefault("cortex_reason", "memory_command")
                record_turn = getattr(self.context_resolver, "record_turn", None)
                if callable(record_turn):
                    record_turn(request, intent, result)
                return result
            decision = self.executive_cortex.route(request, context, self.intent_router)
            intent = decision.intent
            if decision.destination == "workflow":
                plan = self.task_planner.plan(request, decision, context)
                workflow_reasoning = self.reasoning_cortex.evaluate(request, decision, decision.intent, context, self.registry.get(decision.intent.capability), plan)
                if not workflow_reasoning.allowed_to_execute and workflow_reasoning.decision in {"block", "clarify", "suggest_alternative"}:
                    result = self.execution_engine._reasoning_result(workflow_reasoning, decision.intent)
                    result.evidence.setdefault("planner_selected", True)
                    result.evidence.setdefault("workflow_type", plan.planner_evidence.get("workflow_type"))
                    return result
                result = self.workflow_runner.run(request, plan, context)
                result.evidence.setdefault("planner_selected", True)
                result.evidence.setdefault("workflow_type", plan.planner_evidence.get("workflow_type"))
                result.evidence.setdefault("capabilities_considered", plan.planner_evidence.get("capabilities_considered", []))
            elif decision.destination == "knowledge":
                result = self._execute_knowledge(request, intent)
            elif decision.destination == "memory":
                result = self.long_term_memory.handle_command(request) or ActionResult(
                    status="needs_input",
                    capability=intent.capability or "memory.remember",
                    summary="Tell me exactly what you want me to remember or forget.",
                    verified=True,
                )
            else:
                result = self.execution_engine.execute(request, intent, context, decision)
            result.evidence.setdefault("cortex_destination", decision.destination)
            result.evidence.setdefault("cortex_reason", decision.reason)
            result.evidence.setdefault("cortex_signals", decision.signals)
            record_turn = getattr(self.context_resolver, "record_turn", None)
            if callable(record_turn):
                record_turn(request, intent, result)
            return result
        finally:
            latency_ms = int((time.perf_counter() - started) * 1000)
            if result is not None and intent is not None:
                self.execution_engine.response_composer.adapt_result(request, intent, context, result)
                self.next_action_policy.attach(result, context)
                self.experience_engine.record_outcome(request, intent, result, latency_ms=latency_ms, context=context)
                self._observe_verified_result(request, intent, result, context)
            safe_text = request.raw_text[:160].replace("\n", " ")
            logger.info(
                "request_id=%s session_id=%s input_source=%s normalized_text=%r route_stage=executive_cortex destination=%s reason=%s intent=%s capability=%s route=%s status=%s verified=%s fallback_used=%s latency_ms=%s",
                request.request_id,
                request.session_id,
                request.source,
                safe_text,
                decision.destination if decision else "",
                decision.reason if decision else "",
                intent.intent if intent else "",
                intent.capability if intent else "",
                intent.route if intent else "",
                result.status if result else "failed",
                result.verified if result else False,
                fallback_used,
                latency_ms,
            )

    def _is_confirmation_reply(self, text: str) -> bool:
        lowered = str(text or "").strip().lower()
        return bool(re.fullmatch(r"(yes|yeah|yep|confirm|confirmed|go ahead|do it|please do|approve|cancel|no|not now|stop|abort)", lowered))

    def _observe_verified_result(self, request: CommandRequest, intent: IntentResult, result: ActionResult, context: dict[str, Any]) -> None:
        if not request.user_id or result.status not in {"completed", "failed"}:
            return
        event_type = ""
        category = "system"
        if result.evidence.get("planner_selected") or result.capability == "workflow.plan":
            event_type = "workflow_completed" if result.status == "completed" else "task_failed"
        elif (result.capability or "").startswith("task."):
            event_type = "task_completed" if result.status == "completed" else "task_failed"
        elif (result.capability or "").startswith("build.") or result.evidence.get("workload") == "software_engineering":
            event_type = "build_completed" if result.status == "completed" else "build_failed"
            category = "development"
        if not event_type:
            return
        event = self.awareness_engine.factory.create(
            category=category,
            event_type=event_type,
            source="command_service",
            title=str(result.data.get("title") or intent.intent or event_type).replace("_", " ").strip().title(),
            summary=result.summary[:300],
            payload={"confidence": 1.0, "failed": result.status == "failed"},
        )
        self.awareness_engine.observe(event, context)

    def _is_negative_confirmation(self, text: str) -> bool:
        return bool(re.fullmatch(r"(cancel|no|not now|stop|abort)", str(text or "").strip().lower()))

    def _execute_knowledge(self, request: CommandRequest, intent: IntentResult) -> ActionResult:
        capability = intent.capability or "knowledge.query"
        if capability == "knowledge.refresh":
            return self.knowledge_cortex.refresh()
        if capability == "knowledge.list_capabilities":
            return self.knowledge_cortex.list_capabilities()
        if capability == "knowledge.get_workflow":
            return self.knowledge_cortex.get_workflow(request.normalized_text)
        if capability == "knowledge.get_safety_rule":
            return self.knowledge_cortex.get_safety_rule(request.normalized_text)
        if capability == "knowledge.get_architecture_summary":
            return self.knowledge_cortex.get_architecture_summary(request.normalized_text)
        return self.knowledge_cortex.query(request.normalized_text)

    def observe_event(self, event: AwarenessEvent, context: dict[str, Any] | None = None) -> AwarenessDecision:
        return self.awareness_engine.observe(event, context)

    def evaluate_proactive_event(self, user_id: str, event: dict[str, Any], context: dict[str, Any] | None = None):
        companion = self.execution_engine.response_composer.companion_engine
        preferences = companion.preferences(context or {})
        return self.proactive_conversation.evaluate(user_id, event, preferences, context)

    def configure_proactive_runtime(self, **kwargs) -> None:
        self.proactive_runtime.configure(**kwargs)

    def dismiss_proactive(self) -> None:
        self.proactive_runtime.dismiss()

    def record_proactive_thread(self, user_id: str, payload: dict[str, Any]) -> None:
        if not user_id:
            return
        message = str(payload.get("message") or "").strip()
        if not message:
            return
        trigger = str(payload.get("social_trigger") or payload.get("event_type") or "proactive_event")
        request = CommandRequest(
            request_id=f"proactive_thread_{int(time.time() * 1000)}",
            user_id=user_id,
            session_id="desktop_session",
            source="automation",
            raw_text=f"Proactive context: {trigger}",
            normalized_text=f"proactive context {trigger}",
            metadata={"proactive": True, "social_trigger": trigger},
        )
        intent = IntentResult(intent="proactive_event", capability="conversation.proactive", confidence=0.99, route="conversation")
        result = ActionResult(
            status="completed",
            capability="conversation.proactive",
            summary=message,
            spoken_response=str(payload.get("spoken_response") or message),
            verified=True,
            evidence={"proactive_kind": payload.get("proactive_kind"), "social_trigger": trigger},
        )
        record_turn = getattr(self.context_resolver, "record_turn", None)
        if callable(record_turn):
            record_turn(request, intent, result)

    def awareness_context(self) -> dict[str, Any]:
        return self.awareness_engine.as_context()

    def start_awareness_producers(self) -> None:
        self.producer_manager.start()

    def stop_awareness_producers(self) -> None:
        self.producer_manager.stop()

    def poll_awareness_producers(self, context: dict[str, Any] | None = None) -> list[AwarenessDecision]:
        return self.producer_manager.poll_once(context)

    def awareness_health(self) -> dict[str, Any]:
        return self.producer_manager.health()

    def awareness_ipc_events(self) -> list[IpcV2Event]:
        events: list[IpcV2Event] = []
        for card in self.awareness_context().get("notification_cards", []):
            events.append(
                IpcV2Event(
                    event="ceaser:awareness-card",
                    payload={
                        "event_id": card.get("event_id", ""),
                        "category": card.get("category", ""),
                        "title": card.get("title", ""),
                        "short_message": card.get("short_message", ""),
                        "importance": card.get("importance", 0),
                        "timestamp": card.get("timestamp", 0),
                        "suggested_action_label": card.get("suggested_action_label", ""),
                    },
                )
            )
        return events

    def experience_context(self) -> dict[str, Any]:
        return self.experience_engine.as_context()

    def prediction_context(self, request: CommandRequest) -> dict[str, Any]:
        context = self.context_resolver.resolve(request)
        return context.get("prediction", {})
