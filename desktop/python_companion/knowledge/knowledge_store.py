from __future__ import annotations

from knowledge.models import KnowledgeItem


class KnowledgeStore:
    def __init__(self) -> None:
        self.items: dict[str, KnowledgeItem] = {}
        self.load_warnings: list[str] = []

    def upsert(self, item: KnowledgeItem) -> tuple[KnowledgeItem, bool]:
        previous = self.items.get(item.id)
        changed = previous is None or previous.content_hash != item.content_hash
        self.items[item.id] = item
        return item, changed

    def mark_removed(self, active_ids: set[str]) -> None:
        for item_id, item in list(self.items.items()):
            if item_id not in active_ids:
                item.trust_level = "deprecated"

    def all(self) -> list[KnowledgeItem]:
        return list(self.items.values())

    def by_id(self, item_id: str) -> KnowledgeItem | None:
        return self.items.get(item_id)
