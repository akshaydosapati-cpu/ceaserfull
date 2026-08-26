from __future__ import annotations

import hashlib
import os
import re
import time
from pathlib import Path

from capabilities.registry import CapabilityRegistry
from knowledge.models import KnowledgeItem
from knowledge.trust_policy import TrustPolicy
from planning.task_planner import TaskPlanner


DOC_CATEGORY = {
    "DESKTOP_BRAIN_V2.md": "architecture",
    "WORKING_MEMORY_V1.md": "architecture",
    "WORLD_MODEL_V1.md": "architecture",
    "KNOWLEDGE_CORTEX_V1.md": "architecture",
}


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()


def deterministic_id(*parts: str) -> str:
    raw = ":".join(str(part).strip().lower() for part in parts if part)
    slug = re.sub(r"[^a-z0-9_.:/-]+", "-", raw).strip("-")
    return slug[:180]


class KnowledgeLoader:
    def __init__(self, root: str | Path, registry: CapabilityRegistry, trust_policy: TrustPolicy | None = None) -> None:
        self.root = Path(root)
        self.registry = registry
        self.trust_policy = trust_policy or TrustPolicy()
        self.load_warnings: list[str] = []

    def load_all(self) -> list[KnowledgeItem]:
        items: list[KnowledgeItem] = []
        items.extend(self.load_docs())
        items.extend(self.load_capabilities())
        items.extend(self.load_workflows())
        items.extend(self.load_safety_rules())
        return [item for item in items if self.trust_policy.allow_item(item)]

    def load_docs(self) -> list[KnowledgeItem]:
        docs_dir = self.root / "docs"
        if not docs_dir.exists():
            self.load_warnings.append(f"missing_source:{docs_dir}")
            return []
        items: list[KnowledgeItem] = []
        for path in sorted(docs_dir.glob("*.md")):
            if path.name not in DOC_CATEGORY:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if not self.trust_policy.is_safe_content(text):
                self.load_warnings.append(f"rejected_secret_like:{path}")
                continue
            for title, content in self._sections(text, path.stem):
                category = DOC_CATEGORY.get(path.name, "documentation")
                item = self._item(
                    category=category,
                    title=title,
                    content=content,
                    source_path=f"desktop/docs/{path.name}",
                    source_type="markdown",
                    trust_level="authoritative",
                    keywords=self._keywords(title + " " + content),
                )
                items.append(item)
        return items

    def load_capabilities(self) -> list[KnowledgeItem]:
        items = []
        for capability in self.registry.all():
            category = "integration" if capability.name.startswith(("github.", "notion.")) else "capability"
            content = (
                f"Capability: {capability.name}\n"
                f"Description: {capability.description}\n"
                f"Route: {capability.route}\n"
                f"Risk: {capability.risk_level}\n"
                f"Requires confirmation: {capability.requires_confirmation}\n"
                f"Requires internet: {capability.requires_internet}"
            )
            items.append(
                self._item(
                    category=category,
                    title=capability.name,
                    content=content,
                    source_path="capabilities.registry",
                    source_type="registry",
                    trust_level="authoritative",
                    keywords=self._keywords(capability.name + " " + capability.description),
                )
            )
        return items

    def load_workflows(self) -> list[KnowledgeItem]:
        workflows = {
            "github_project_viva": "Prepare project viva pack using GitHub repository summary, viva questions, revision notes, optional Notion save, and study pack.",
            "github_activity_summary": "Summarize today's repository work using commits, issues, pull requests, AI activity summary, and Notion save confirmation.",
            "notion_study_quiz": "Find Notion study notes, read the selected page, and generate a quiz without write confirmation.",
            "workflow_confirmation_resume": "When a workflow reaches a write step, CEASER creates a pending confirmation. User approval resumes the exact workflow from the paused step.",
        }
        return [
            self._item("workflow", name, content, "planning.task_planner", "workflow_metadata", "trusted", self._keywords(name + " " + content))
            for name, content in workflows.items()
        ]

    def load_safety_rules(self) -> list[KnowledgeItem]:
        rules = [
            ("confirmation_required_actions", "Notion writes, file modifications, GitHub writes, high-risk actions, and destructive actions require confirmation. Secret revelation is blocked."),
            ("planner_limits", "Workflow plans have a maximum of 6 steps, dependency depth 4, one retry per step, no recursive planning, no cycles, and no unsupported capabilities."),
        ]
        return [self._item("safety_rule", title, content, "desktop/docs/DESKTOP_BRAIN_V2.md", "safety_rules", "authoritative", self._keywords(title + " " + content)) for title, content in rules]

    def _sections(self, text: str, fallback_title: str) -> list[tuple[str, str]]:
        matches = list(re.finditer(r"^(#{1,3})\s+(.+)$", text, flags=re.MULTILINE))
        if not matches:
            return [(fallback_title, text.strip())]
        sections = []
        for idx, match in enumerate(matches):
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            title = match.group(2).strip()
            body = text[start:end].strip()
            if body:
                sections.append((title, body[:4000]))
        return sections

    def _item(self, category, title, content, source_path, source_type, trust_level, keywords) -> KnowledgeItem:
        now = time.time()
        summary = self._summary(content)
        return KnowledgeItem(
            id=deterministic_id(category, source_path, title),
            category=category,
            title=title,
            content=content,
            summary=summary,
            keywords=keywords,
            source_path=source_path,
            source_type=source_type,
            trust_level=trust_level,
            version="1",
            created_at=now,
            updated_at=now,
            content_hash=content_hash(title + "\n" + content),
            metadata={},
        )

    def _summary(self, content: str) -> str:
        clean = re.sub(r"\s+", " ", str(content or "")).strip()
        return clean[:260]

    def _keywords(self, text: str) -> list[str]:
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9_.-]{2,}", text.lower())
        stop = {"the", "and", "with", "from", "this", "that", "for", "must", "should", "will", "into", "user"}
        return sorted({word for word in words if word not in stop})[:80]
