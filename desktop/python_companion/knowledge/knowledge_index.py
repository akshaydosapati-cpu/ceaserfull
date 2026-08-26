from __future__ import annotations

import re

from knowledge.models import KnowledgeItem, KnowledgeMatch, KnowledgeQuery
from knowledge.trust_policy import TrustPolicy


class KnowledgeIndex:
    def __init__(self, trust_policy: TrustPolicy | None = None) -> None:
        self.items: dict[str, KnowledgeItem] = {}
        self.trust_policy = trust_policy or TrustPolicy()

    def rebuild(self, items: list[KnowledgeItem]) -> None:
        self.items = {item.id: item for item in items}

    def search(self, query: KnowledgeQuery) -> list[KnowledgeMatch]:
        terms = self._terms(query.text)
        matches: list[KnowledgeMatch] = []
        for item in self.items.values():
            if query.category and item.category != query.category:
                continue
            if item.trust_level == "deprecated" and not query.include_deprecated:
                continue
            score, matched_terms = self._score(item, terms, query.text)
            if score <= 0:
                continue
            weighted = score * self.trust_policy.trust_weight(item)
            matches.append(KnowledgeMatch(item=item, score=weighted, confidence=min(1.0, weighted / 8.0), matched_terms=matched_terms))
        return sorted(matches, key=lambda match: (match.confidence, self.trust_policy.trust_weight(match.item), match.score), reverse=True)[: query.limit]

    def _score(self, item: KnowledgeItem, terms: list[str], raw_query: str) -> tuple[float, list[str]]:
        hay_title = item.title.lower()
        hay_content = item.content.lower()
        hay_keywords = set(item.keywords)
        matched = []
        score = 0.0
        raw = raw_query.lower()
        normalized_title = hay_title.replace("_", " ").replace("-", " ")
        normalized_source = item.source_path.lower().replace("_", " ").replace("-", " ")
        if raw and raw in hay_title:
            score += 5
        if "desktop brain" in raw and ("desktop brain" in normalized_title or "desktop brain" in normalized_source):
            score += 8
        if "working memory" in raw and ("working memory" in normalized_title or "working memory" in normalized_source):
            score += 8
        if "world model" in raw and ("world model" in normalized_title or "world model" in normalized_source):
            score += 8
        for term in terms:
            if term in hay_title:
                score += 3
                matched.append(term)
            elif term in hay_keywords:
                score += 2
                matched.append(term)
            elif term in hay_content:
                score += 1
                matched.append(term)
        return score, sorted(set(matched))

    def _terms(self, text: str) -> list[str]:
        stop = {"what", "can", "does", "with", "about", "explain", "show", "tell", "which", "actions", "use", "you", "the", "how", "why", "ceaser", "support", "supports", "supported"}
        return [term for term in re.findall(r"[a-zA-Z][a-zA-Z0-9_.-]{2,}", str(text or "").lower()) if term not in stop]
