"""Tests for CEASER Task State V1 foundation.

This test suite validates:
1. State schema validation
2. State merge/update logic
3. Backward compatibility with legacy fields
4. Provenance and source tracking
5. Constraint/fact/assumption distinction
6. Calculation derivation tracking
7. Duplicate prevention
8. Correction/supersession handling
"""

import pytest
from datetime import datetime

from app.schemas.task_state import (
    TaskStateSchema,
    StateSource,
    StateStatus,
    create_constraint,
    create_fact,
    create_assumption,
    create_decision,
    create_calculation,
    create_goal,
    create_entity,
)
from app.services.state.state_merger import (
    merge_state,
    apply_state_change,
    update_legacy_fields,
)


class TestStateSchemaValidation:
    """Test state schema validation."""

    def test_empty_state_is_valid(self):
        """Empty state is valid for backward compatibility."""
        is_valid, errors = TaskStateSchema.validate({})
        assert is_valid
        assert len(errors) == 0

    def test_v1_empty_structure_is_valid(self):
        """V1 empty structure is valid."""
        state = TaskStateSchema.empty()
        is_valid, errors = TaskStateSchema.validate(state)
        assert is_valid
        assert len(errors) == 0

    def test_invalid_schema_version_rejected(self):
        """Invalid schema version is rejected."""
        state = {"schema_version": 99}
        is_valid, errors = TaskStateSchema.validate(state)
        assert not is_valid
        assert any("schema_version" in err for err in errors)

    def test_invalid_field_types_rejected(self):
        """Invalid field types are rejected."""
        state = {
            "schema_version": 1,
            "constraints": "not_a_list",  # Should be list
            "facts": {},  # Should be list
        }
        is_valid, errors = TaskStateSchema.validate(state)
        assert not is_valid
        assert len(errors) >= 2

    def test_legacy_only_state_is_valid(self):
        """Legacy-only state (no V1 structure) is valid."""
        legacy_state = {
            "active_topic": "Python",
            "active_subtopic": "OOP",
            "important_entities": ["Python", "OOP"],
        }
        is_valid, errors = TaskStateSchema.validate(legacy_state)
        assert is_valid
        assert TaskStateSchema.is_legacy_only(legacy_state)


class TestStateNormalization:
    """Test state normalization and initialization."""

    def test_empty_state_normalized_to_v1(self):
        """Empty state is normalized to V1 structure."""
        result = TaskStateSchema.normalize({})
        assert result["schema_version"] == 1
        assert "constraints" in result
        assert "facts" in result
        assert "meta" in result

    def test_legacy_state_normalized_preserves_fields(self):
        """Normalizing legacy state preserves legacy fields."""
        legacy = {
            "active_topic": "Python",
            "active_subtopic": "OOP",
            "important_entities": ["Class", "Instance"],
            "unfinished_goal": "Learn inheritance",
        }
        result = TaskStateSchema.normalize(legacy)
        assert result["schema_version"] == 1
        assert result["active_topic"] == "Python"
        assert result["active_subtopic"] == "OOP"
        assert result["important_entities"] == ["Class", "Instance"]
        assert result["unfinished_goal"] == "Learn inheritance"

    def test_v1_state_returned_unchanged(self):
        """V1 state is returned unchanged."""
        v1_state = TaskStateSchema.empty()
        v1_state["constraints"] = [create_constraint("Test constraint")]
        result = TaskStateSchema.normalize(v1_state)
        assert result == v1_state


class TestStateMerge:
    """Test state merge logic."""

    def test_merge_empty_states(self):
        """Merging empty states produces valid V1."""
        result = merge_state({}, {})
        assert result["schema_version"] == 1
        assert isinstance(result["constraints"], list)

    def test_merge_preserves_unrelated_state(self):
        """Merge preserves unrelated existing state."""
        previous = TaskStateSchema.empty()
        previous["constraints"] = [create_constraint("Budget: $100k")]
        previous["facts"] = [create_fact("Market size: 5M users")]

        changes = {
            "goals": [create_goal("Launch MVP")]
        }

        result = merge_state(previous, changes)
        assert len(result["constraints"]) == 1
        assert len(result["facts"]) == 1
        assert len(result["goals"]) == 1

    def test_merge_updates_changed_values(self):
        """Merge updates changed values."""
        previous = TaskStateSchema.empty()
        previous["task"] = {"objective": "Build app"}

        changes = {
            "task": {"objective": "Build mobile app", "type": "coding"}
        }

        result = merge_state(previous, changes)
        assert result["task"]["objective"] == "Build mobile app"
        assert result["task"]["type"] == "coding"

    def test_merge_updates_meta_timestamp(self):
        """Merge updates meta.updated_at."""
        previous = TaskStateSchema.empty()
        old_updated = previous["meta"]["updated_at"]

        import time
        time.sleep(0.01)

        result = merge_state(previous, {"task": {"type": "research"}})
        assert result["meta"]["updated_at"] != old_updated


class TestConstraintPersistence:
    """Test user constraint persistence."""

    def test_user_constraint_persisted(self):
        """User-provided constraint is persisted with source=user."""
        constraint = create_constraint(
            "Budget cap: $150,000",
            source=StateSource.USER,
            category="budget",
        )

        assert constraint["source"] == "user"
        assert constraint["description"] == "Budget cap: $150,000"
        assert constraint["category"] == "budget"
        assert constraint["status"] == StateStatus.ACTIVE.value
        assert "provenance" in constraint

    def test_multiple_constraints_additive(self):
        """Multiple constraints are additive, not replacing."""
        previous = TaskStateSchema.empty()
        previous["constraints"] = [create_constraint("Budget: $100k", source=StateSource.USER)]

        changes = {
            "constraints": [create_constraint("Timeline: 6 months", source=StateSource.USER)]
        }

        result = merge_state(previous, changes)
        assert len(result["constraints"]) == 2


class TestAssumptionTracking:
    """Test that assistant assumptions remain assumptions."""

    def test_assumption_not_treated_as_fact(self):
        """Assistant assumption remains source=assistant, not user."""
        assumption = create_assumption(
            "Average customer spend: $15",
            status=StateStatus.ACTIVE,
            risk_level="medium",
        )

        # Assumption has no source field - it's always assistant-generated
        assert "source" not in assumption
        assert assumption["status"] == StateStatus.ACTIVE.value
        assert assumption["validation_required"] is True

    def test_fact_vs_assumption_distinction(self):
        """Facts and assumptions are stored separately."""
        fact = create_fact("User confirmed: monthly budget $5k", source=StateSource.USER, confidence=1.0)
        assumption = create_assumption("Estimated conversion rate: 3%")

        assert fact["source"] == "user"
        assert "source" not in assumption
        assert fact["confidence"] == 1.0
        assert assumption["validation_required"] is True


class TestCalculationDerivation:
    """Test calculation derivation tracking."""

    def test_calculation_records_source_ids(self):
        """Calculation records IDs of source values."""
        calc = create_calculation(
            name="monthly_revenue",
            value=22500,
            expression="customers_per_day * days_open * avg_spend",
            source_ids=["a1", "a2", "a3"],
        )

        assert calc["name"] == "monthly_revenue"
        assert calc["value"] == 22500
        assert calc["expression"] == "customers_per_day * days_open * avg_spend"
        assert calc["source_ids"] == ["a1", "a2", "a3"]
        assert calc["status"] == StateStatus.ACTIVE.value

    def test_calculation_merge_by_key(self):
        """Calculations merge by key in dict."""
        previous = TaskStateSchema.empty()
        previous["calculations"] = {
            "revenue": create_calculation("revenue", 10000, source_ids=["c1"])
        }

        changes = {
            "calculations": {
                "revenue": create_calculation("revenue", 15000, source_ids=["c1", "c2"]),
                "profit": create_calculation("profit", 5000, source_ids=["revenue", "c3"]),
            }
        }

        result = merge_state(previous, changes)
        assert result["calculations"]["revenue"]["value"] == 15000
        assert result["calculations"]["profit"]["value"] == 5000
        assert len(result["calculations"]) == 2


class TestDuplicatePrevention:
    """Test duplicate entry prevention."""

    def test_identical_constraint_not_duplicated(self):
        """Identical constraint with same ID updates, not duplicates."""
        constraint1 = create_constraint("Budget: $100k")
        constraint1["id"] = "c1"

        previous = TaskStateSchema.empty()
        previous["constraints"] = [constraint1]

        constraint2 = dict(constraint1)
        constraint2["description"] = "Budget: $120k"

        changes = {"constraints": [constraint2]}
        result = merge_state(previous, changes)

        assert len(result["constraints"]) == 1
        assert result["constraints"][0]["description"] == "Budget: $120k"


class TestCorrectionHandling:
    """Test correction/supersession handling."""

    def test_correction_marks_old_as_deprecated(self):
        """Correction marks old entry as deprecated."""
        old_fact = create_fact("Austin rent: $3,500", source=StateSource.ASSISTANT)
        old_fact["id"] = "f1"

        previous = TaskStateSchema.empty()
        previous["facts"] = [old_fact]

        # User corrects the fact
        corrected = create_fact("Austin rent: $4,500", source=StateSource.USER)
        corrected["id"] = "f1"
        corrected["status"] = StateStatus.ACTIVE.value

        result = apply_state_change(previous, "update", "facts", corrected)

        # Should have 2 entries: deprecated old + new active
        assert len(result["facts"]) == 2
        deprecated = [f for f in result["facts"] if f["status"] == StateStatus.DEPRECATED.value]
        active = [f for f in result["facts"] if f["status"] == StateStatus.ACTIVE.value]
        assert len(deprecated) == 1
        assert len(active) == 1
        assert active[0]["content"] == "Austin rent: $4,500"


class TestLegacyFieldCompatibility:
    """Test backward compatibility with legacy fields."""

    def test_legacy_fields_preserved_on_merge(self):
        """Legacy fields are preserved during merge."""
        previous = {
            "active_topic": "Python",
            "active_subtopic": "OOP",
            "important_entities": ["Class", "Object"],
            "unfinished_goal": "Learn inheritance",
        }

        changes = {
            "constraints": [create_constraint("Use Python 3.11+")]
        }

        result = merge_state(previous, changes)
        assert result["active_topic"] == "Python"
        assert result["active_subtopic"] == "OOP"
        assert result["important_entities"] == ["Class", "Object"]
        assert result["unfinished_goal"] == "Learn inheritance"
        assert len(result["constraints"]) == 1

    def test_legacy_fields_updated_when_provided(self):
        """Legacy fields update when new values provided."""
        previous = TaskStateSchema.normalize({
            "active_topic": "Python",
            "active_subtopic": "OOP",
        })

        changes = {
            "active_topic": "JavaScript",
            "active_subtopic": "Promises",
        }

        result = merge_state(previous, changes)
        assert result["active_topic"] == "JavaScript"
        assert result["active_subtopic"] == "Promises"

    def test_update_legacy_fields_helper(self):
        """update_legacy_fields helper updates only legacy fields."""
        state = TaskStateSchema.empty()
        state["constraints"] = [create_constraint("Test")]

        result = update_legacy_fields(
            state,
            active_topic="Database Design",
            important_entities=["PostgreSQL", "Schema"],
        )

        assert result["active_topic"] == "Database Design"
        assert result["important_entities"] == ["PostgreSQL", "Schema"]
        assert len(result["constraints"]) == 1  # V1 structure preserved


class TestProvenance:
    """Test provenance tracking."""

    def test_user_source_tracked(self):
        """User source is tracked in constraint."""
        constraint = create_constraint(
            "Must support offline mode",
            source=StateSource.USER,
            provenance=["message_001"],
        )

        assert constraint["source"] == "user"
        assert constraint["provenance"] == ["message_001"]

    def test_document_source_tracked(self):
        """Document source is tracked in fact."""
        fact = create_fact(
            "Company policy: Max budget $50k",
            source=StateSource.DOCUMENT,
            provenance=["file_id_123", "page_5"],
        )

        assert fact["source"] == "document"
        assert "file_id_123" in fact["provenance"]

    def test_derived_source_for_calculation(self):
        """Derived source for calculations."""
        calc = create_calculation(
            "total_cost",
            value=50000,
            source_ids=["cost1", "cost2"],
            provenance=["message_010"],
        )

        assert calc["source_ids"] == ["cost1", "cost2"]
        assert calc["provenance"] == ["message_010"]


class TestStateContextBuilder:
    """Test _build_state_context helper in ResponsePipeline."""

    def test_empty_state_returns_empty_string(self):
        """Empty or legacy-only state returns empty string."""
        from app.services.orchestrator.response_pipeline import ResponsePipeline
        assert ResponsePipeline._build_state_context({}) == ""
        assert ResponsePipeline._build_state_context({"active_topic": "Python"}) == ""

    def test_v1_state_with_constraints_renders(self):
        """V1 state with active constraints is included in context."""
        from app.services.orchestrator.response_pipeline import ResponsePipeline
        state = TaskStateSchema.empty()
        state["constraints"] = [
            create_constraint("Budget: 15 lakhs", source=StateSource.USER, category="budget")
        ]
        result = ResponsePipeline._build_state_context(state)
        assert "User constraints" in result
        assert "Budget: 15 lakhs" in result

    def test_deprecated_items_excluded(self):
        """Deprecated items are not shown in state context."""
        from app.services.orchestrator.response_pipeline import ResponsePipeline
        state = TaskStateSchema.empty()
        c = create_constraint("Old budget", source=StateSource.USER, category="budget")
        c["status"] = "deprecated"
        state["constraints"] = [c]
        result = ResponsePipeline._build_state_context(state)
        assert "Old budget" not in result

    def test_provenance_ids_not_exposed(self):
        """Raw provenance IDs are not present in state context output."""
        from app.services.orchestrator.response_pipeline import ResponsePipeline
        state = TaskStateSchema.empty()
        state["constraints"] = [
            create_constraint("Budget cap", source=StateSource.USER, provenance=["msg_abc123xyz"])
        ]
        result = ResponsePipeline._build_state_context(state)
        assert "msg_abc123xyz" not in result

    def test_state_context_deterministic(self):
        """_build_state_context produces the same output for the same input."""
        from app.services.orchestrator.response_pipeline import ResponsePipeline
        state = TaskStateSchema.empty()
        state["constraints"] = [create_constraint("Test constraint")]
        state["goals"] = [create_goal("Ship v1")]
        r1 = ResponsePipeline._build_state_context(state)
        r2 = ResponsePipeline._build_state_context(state)
        assert r1 == r2


class TestNoNetworkCallsDuringPersistence:
    """Test that no model/network calls occur during state persistence."""

    def test_merge_is_deterministic(self):
        """merge_state is deterministic (no LLM/network calls)."""
        previous = TaskStateSchema.empty()
        previous["constraints"] = [create_constraint("Test")]

        changes = {"goals": [create_goal("Deploy to prod")]}

        # This should complete instantly without any I/O
        import time
        start = time.perf_counter()
        result = merge_state(previous, changes)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1  # Should be < 100ms (no network)
        assert len(result["constraints"]) == 1
        assert len(result["goals"]) == 1

    def test_apply_state_change_is_deterministic(self):
        """apply_state_change is deterministic."""
        previous = TaskStateSchema.empty()

        import time
        start = time.perf_counter()
        result = apply_state_change(
            previous,
            "add",
            "constraints",
            create_constraint("Test constraint"),
        )
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1
        assert len(result["constraints"]) == 1


class TestStateVersionPreservation:
    """Test state version is preserved/updated correctly."""

    def test_empty_state_gets_version_1(self):
        """Empty state gets schema_version 1."""
        state = TaskStateSchema.empty()
        assert state["schema_version"] == 1

    def test_merge_preserves_version(self):
        """Merge preserves schema_version."""
        previous = TaskStateSchema.empty()
        changes = {"task": {"type": "research"}}

        result = merge_state(previous, changes)
        assert result["schema_version"] == 1

    def test_legacy_state_gets_version_on_normalize(self):
        """Legacy state gets version on normalize."""
        legacy = {"active_topic": "Test"}
        result = TaskStateSchema.normalize(legacy)
        assert result["schema_version"] == 1
