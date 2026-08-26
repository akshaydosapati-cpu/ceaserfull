from __future__ import annotations

import re

from knowledge.knowledge_index import KnowledgeIndex
from knowledge.models import KnowledgeQuery, KnowledgeResponse


class KnowledgeQueryEngine:
    def __init__(self, index: KnowledgeIndex) -> None:
        self.index = index

    def query(self, query: KnowledgeQuery) -> KnowledgeResponse:
        matches = self.index.search(query)
        if not matches:
            return KnowledgeResponse(status="not_found", query=query.text, summary="No trusted CEASER knowledge matched that request.", matches=[], confidence=0.0)
        confidence = matches[0].confidence
        query_terms = {
            term
            for term in re.findall(r"[a-zA-Z][a-zA-Z0-9_.-]{2,}", query.text.lower())
            if term not in {"what", "can", "does", "with", "about", "explain", "show", "tell", "which", "actions", "use", "you", "the", "how", "why", "ceaser", "support", "supports", "supported"}
        }
        matched_terms = set(matches[0].matched_terms)
        if len(query_terms) >= 3 and len(matched_terms) / len(query_terms) < 0.5:
            return KnowledgeResponse(status="not_found", query=query.text, summary="No trusted CEASER knowledge matched that request.", matches=[], confidence=confidence)
        if confidence < 0.3:
            return KnowledgeResponse(status="not_found", query=query.text, summary="No trusted CEASER knowledge matched that request.", matches=[], confidence=confidence)
        status = "completed" if confidence >= 0.35 else "partial"
        sources = sorted({match.item.source_path for match in matches})
        summary = self._summary(matches)
        return KnowledgeResponse(
            status=status,
            query=query.text,
            summary=summary,
            matches=matches,
            confidence=confidence,
            sources=sources,
            ambiguity=len(matches) > 1 and abs(matches[0].confidence - matches[1].confidence) < 0.08,
        )

    def _summary(self, matches) -> str:
        first = matches[0].item
        if first.summary:
            return first.summary
        return first.content[:260]
