from __future__ import annotations

import re

from capabilities.registry import CapabilityRegistry
from planning.models import WorkflowPlan


SECRET_PATTERN = re.compile(r"(secret|token|password|api[_-]?key|access[_-]?token|refresh[_-]?token|private[_-]?key)", re.IGNORECASE)


class PlanValidator:
    MAX_STEPS = 6
    MAX_DEPTH = 4

    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    def validate(self, plan: WorkflowPlan) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if len(plan.steps) > self.MAX_STEPS:
            errors.append("too_many_steps")
        step_ids = {step.step_id for step in plan.steps}
        for step in plan.steps:
            capability = self.registry.get(step.capability)
            if not capability:
                errors.append(f"unknown_capability:{step.capability}")
                continue
            if step.retry_limit > 1:
                errors.append(f"retry_limit_too_high:{step.step_id}")
            if capability.requires_confirmation and not step.requires_confirmation:
                errors.append(f"confirmation_required:{step.step_id}")
            if capability.risk_level in {"high", "medium"} and capability.requires_confirmation and not step.requires_confirmation:
                errors.append(f"risk_confirmation_required:{step.step_id}")
            for key in step.arguments:
                if SECRET_PATTERN.search(str(key)):
                    errors.append(f"secret_argument:{step.step_id}:{key}")
            for dependency in step.depends_on:
                if dependency not in step_ids:
                    errors.append(f"unknown_dependency:{step.step_id}:{dependency}")
        if self._has_cycle(plan):
            errors.append("cyclic_dependencies")
        if self._max_depth(plan) > self.MAX_DEPTH:
            errors.append("dependency_depth_exceeded")
        return not errors, errors

    def _has_cycle(self, plan: WorkflowPlan) -> bool:
        graph = {step.step_id: set(step.depends_on) for step in plan.steps}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for dep in graph.get(node, set()):
                if visit(dep):
                    return True
            visiting.remove(node)
            visited.add(node)
            return False

        return any(visit(node) for node in graph)

    def _max_depth(self, plan: WorkflowPlan) -> int:
        graph = {step.step_id: list(step.depends_on) for step in plan.steps}

        def depth(node: str, seen: set[str] | None = None) -> int:
            seen = seen or set()
            if node in seen:
                return self.MAX_DEPTH + 1
            deps = graph.get(node, [])
            if not deps:
                return 1
            return 1 + max(depth(dep, seen | {node}) for dep in deps)

        return max((depth(step.step_id) for step in plan.steps), default=0)
