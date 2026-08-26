from __future__ import annotations

from pathlib import Path
from typing import Any

from capabilities.registry import CapabilityRegistry
from core.schemas import ActionResult
from knowledge.knowledge_index import KnowledgeIndex
from knowledge.knowledge_loader import KnowledgeLoader
from knowledge.knowledge_query import KnowledgeQueryEngine
from knowledge.knowledge_store import KnowledgeStore
from knowledge.models import KnowledgeItem, KnowledgeQuery
from knowledge.trust_policy import TrustPolicy


class KnowledgeCortex:
    def __init__(self, root: str | Path, registry: CapabilityRegistry) -> None:
        self.root = Path(root)
        self.registry = registry
        self.trust_policy = TrustPolicy()
        self.store = KnowledgeStore()
        self.index = KnowledgeIndex(self.trust_policy)
        self.query_engine = KnowledgeQueryEngine(self.index)
        self.load_errors: list[str] = []
        self.loaded = False

    def load(self) -> None:
        loader = KnowledgeLoader(self.root, self.registry, self.trust_policy)
        items = loader.load_all()
        active_ids = set()
        changed = 0
        for item in items:
            _, did_change = self.store.upsert(item)
            active_ids.add(item.id)
            changed += 1 if did_change else 0
        self.store.mark_removed(active_ids)
        self.store.load_warnings = loader.load_warnings
        self.load_errors = loader.load_warnings
        if loader.load_warnings:
            self.loaded = False
        else:
            self.loaded = True
        self.index.rebuild(self.store.all())

    def refresh(self) -> ActionResult:
        self.load()
        status = "completed" if not self.load_errors else "partial"
        return ActionResult(
            status=status,
            capability="knowledge.refresh",
            summary=f"Knowledge Cortex refreshed {len(self.store.items)} items.",
            spoken_response="Knowledge refreshed.",
            data={"item_count": len(self.store.items), "warnings": self.load_errors},
            evidence={"sources": self.source_roots()},
            warnings=self.load_errors,
            verified=not self.load_errors,
        )

    def query(self, text: str, category=None) -> ActionResult:
        if not self.store.items:
            self.load()
        response = self.query_engine.query(KnowledgeQuery(text=text, category=category))
        if response.status == "not_found":
            return ActionResult(
                status="failed",
                capability="knowledge.query",
                summary=response.summary,
                spoken_response="I do not have trusted CEASER knowledge for that yet.",
                data={"matches": []},
                evidence={"knowledge_confidence": 0.0, "sources": [], "knowledge_reason": "not_found"},
                verified=True,
                error_code="knowledge_not_found",
            )
        matches = [self._match_dump(match) for match in response.matches]
        return ActionResult(
            status="completed" if response.status == "completed" else "partial",
            capability="knowledge.query",
            summary=response.summary,
            spoken_response=self._spoken(response.summary),
            data={"matches": matches, "ambiguity": response.ambiguity},
            evidence={
                "sources": response.sources,
                "knowledge_matches_used": [match["item"]["id"] for match in matches],
                "knowledge_confidence": response.confidence,
                "knowledge_sources": response.sources,
                "knowledge_reason": "trusted_internal_knowledge",
            },
            warnings=response.warnings + self.load_errors,
            verified=True,
        )

    def list_capabilities(self) -> ActionResult:
        return self.query("CEASER capabilities GitHub Notion Desktop AI workflow", category="capability")

    def get_workflow(self, text: str) -> ActionResult:
        return self.query(text, category="workflow")

    def get_safety_rule(self, text: str) -> ActionResult:
        return self.query(text, category="safety_rule")

    def get_architecture_summary(self, text: str) -> ActionResult:
        return self.query(text, category="architecture")

    def source_roots(self) -> list[str]:
        return ["desktop/docs/", "capabilities.registry", "planning.task_planner", "safety_rules"]

    def route_evidence(self, text: str) -> dict[str, Any]:
        if not self.store.items:
            self.load()
        response = self.query_engine.query(KnowledgeQuery(text=text, limit=3))
        return {
            "knowledge_matches_used": [match.item.id for match in response.matches],
            "knowledge_confidence": response.confidence,
            "knowledge_sources": response.sources,
            "knowledge_reason": response.status,
        }

    def _spoken(self, summary: str) -> str:
        return summary.split(".")[0][:180] + "."

    def _match_dump(self, match) -> dict[str, Any]:
        item = match.item
        try:
            item_dump = item.model_dump()
        except AttributeError:
            item_dump = item.dict()
        return {
            "item": item_dump,
            "score": match.score,
            "confidence": match.confidence,
            "matched_terms": match.matched_terms,
        }
