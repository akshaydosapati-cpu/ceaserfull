from __future__ import annotations

import re
import time
from typing import Any

from world_model.models import EntityType, RelationshipType, WorldEntity, WorldRelationship


SECRET_PATTERN = re.compile(r"(secret|token|password|api[_-]?key|access[_-]?token|refresh[_-]?token|private[_-]?key)", re.IGNORECASE)


def identity_key(entity_type: str, name: str, source: str = "") -> str:
    clean_name = re.sub(r"[^a-z0-9_.:/-]+", "-", str(name or "").strip().lower()).strip("-")
    clean_source = re.sub(r"[^a-z0-9_.:/-]+", "-", str(source or "").strip().lower()).strip("-")
    return f"{entity_type}:{clean_source}:{clean_name}" if clean_source else f"{entity_type}:{clean_name}"


def relationship_key(source_id: str, relationship_type: str, target_id: str) -> str:
    return f"{source_id}->{relationship_type}->{target_id}"


def safe_attributes(attributes: dict[str, Any] | None) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in dict(attributes or {}).items():
        if SECRET_PATTERN.search(str(key)):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[key] = value
        elif isinstance(value, list):
            safe[key] = [item for item in value if isinstance(item, (str, int, float, bool))][:20]
        elif isinstance(value, dict):
            nested = {k: v for k, v in value.items() if not SECRET_PATTERN.search(str(k)) and isinstance(v, (str, int, float, bool))}
            safe[key] = nested
    return safe


class GraphStore:
    def __init__(self) -> None:
        self.entities: dict[str, WorldEntity] = {}
        self.relationships: dict[str, WorldRelationship] = {}

    def upsert_entity(
        self,
        entity_type: EntityType,
        name: str,
        *,
        attributes: dict[str, Any] | None = None,
        source: str = "",
        confidence: float = 1.0,
        ttl_seconds: int | None = None,
        entity_id: str | None = None,
    ) -> WorldEntity:
        now = time.time()
        key = entity_id or identity_key(entity_type, name, source)
        expires_at = now + ttl_seconds if ttl_seconds else None
        current = self.entities.get(key)
        if current:
            current.name = name or current.name
            current.attributes.update(safe_attributes(attributes))
            current.source = source or current.source
            current.confidence = max(current.confidence, confidence)
            current.updated_at = now
            current.expires_at = expires_at or current.expires_at
            return current
        entity = WorldEntity(
            id=key,
            type=entity_type,
            name=name,
            attributes=safe_attributes(attributes),
            source=source,
            confidence=confidence,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        self.entities[key] = entity
        return entity

    def upsert_relationship(
        self,
        source_id: str,
        relationship_type: RelationshipType,
        target_id: str,
        *,
        source: str = "",
        confidence: float = 1.0,
        ttl_seconds: int | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> WorldRelationship:
        now = time.time()
        key = relationship_key(source_id, relationship_type, target_id)
        expires_at = now + ttl_seconds if ttl_seconds else None
        current = self.relationships.get(key)
        if current:
            current.updated_at = now
            current.confidence = max(current.confidence, confidence)
            current.expires_at = expires_at or current.expires_at
            current.evidence.update(safe_attributes(evidence))
            return current
        relationship = WorldRelationship(
            id=key,
            source_id=source_id,
            target_id=target_id,
            type=relationship_type,
            source=source,
            confidence=confidence,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            evidence=safe_attributes(evidence),
        )
        self.relationships[key] = relationship
        return relationship

    def expire(self) -> None:
        now = time.time()
        expired_entities = {key for key, entity in self.entities.items() if entity.expires_at and entity.expires_at <= now}
        for key in expired_entities:
            self.entities.pop(key, None)
        for key, relationship in list(self.relationships.items()):
            if relationship.expires_at and relationship.expires_at <= now:
                self.relationships.pop(key, None)
            elif relationship.source_id in expired_entities or relationship.target_id in expired_entities:
                self.relationships.pop(key, None)

    def find_by_type(self, entity_type: EntityType) -> list[WorldEntity]:
        self.expire()
        return [entity for entity in self.entities.values() if entity.type == entity_type]

    def find_by_name(self, name: str, entity_type: EntityType | None = None) -> list[WorldEntity]:
        self.expire()
        needle = str(name or "").strip().lower()
        if not needle:
            return []
        matches = []
        for entity in self.entities.values():
            if entity_type and entity.type != entity_type:
                continue
            aliases = [str(alias).lower() for alias in entity.attributes.get("aliases", []) if isinstance(alias, str)]
            if needle == entity.name.lower() or needle in entity.name.lower() or needle in aliases:
                matches.append(entity)
        return sorted(matches, key=lambda item: item.updated_at, reverse=True)

    def outgoing(self, entity_id: str, relationship_type: RelationshipType | None = None) -> list[WorldRelationship]:
        self.expire()
        return [
            rel
            for rel in self.relationships.values()
            if rel.source_id == entity_id and (relationship_type is None or rel.type == relationship_type)
        ]

    def incoming(self, entity_id: str, relationship_type: RelationshipType | None = None) -> list[WorldRelationship]:
        self.expire()
        return [
            rel
            for rel in self.relationships.values()
            if rel.target_id == entity_id and (relationship_type is None or rel.type == relationship_type)
        ]

    def entity(self, entity_id: str | None) -> WorldEntity | None:
        self.expire()
        return self.entities.get(entity_id or "")
