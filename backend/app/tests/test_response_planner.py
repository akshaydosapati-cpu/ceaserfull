"""Tests for conversation-aware response planning."""

import pytest
from app.services.orchestrator.response_planner import (
    ResponsePlanner,
    OperationType,
    ResponsePlan,
)


@pytest.fixture
def planner():
    return ResponsePlanner()


@pytest.fixture
def sample_artifacts():
    """Sample artifacts from a conversation."""
    return [
        {
            "id": "code-1",
            "type": "code",
            "format": "markdown",
            "content": "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n-1)",
            "language": "python",
        },
    ]


@pytest.fixture
def conversation_context():
    """Sample conversation context."""
    return {
        "messages": [
            {"role": "user", "content": "write a code for polynomials of a number in C."},
            {"role": "assistant", "content": "Here's a polynomial calculator in C..."},
        ],
    }


class TestOperationClassification:
    """Test operation type classification."""

    def test_explain_operation_from_pronoun_and_explain_verb(self, planner):
        """'explain it' should classify as EXPLAIN."""
        operation = planner._classify_operation("explain it", [{"id": "1"}])
        assert operation == OperationType.EXPLAIN

    def test_explain_step_by_step(self, planner):
        """'explain every step' should classify as EXPLAIN."""
        operation = planner._classify_operation("explain it every step", [{"id": "1"}])
        assert operation == OperationType.EXPLAIN

    def test_modify_operation_from_change_verb(self, planner):
        """'fix the second function' should classify as MODIFY/CORRECT."""
        operation = planner._classify_operation("fix the second function", [{"id": "1"}])
        assert operation == OperationType.CORRECT

    def test_transform_operation_for_language_conversion(self, planner):
        """'convert to Python' should classify as TRANSFORM."""
        operation = planner._classify_operation("convert it to Python", [{"id": "1"}])
        assert operation == OperationType.TRANSFORM

    def test_continue_operation(self, planner):
        """'continue' should classify as CONTINUE."""
        operation = planner._classify_operation("continue", [{"id": "1"}])
        assert operation == OperationType.CONTINUE

    def test_summarize_operation(self, planner):
        """'summarize this' should classify as SUMMARIZE."""
        operation = planner._classify_operation("summarize this", [{"id": "1"}])
        assert operation == OperationType.SUMMARIZE

    def test_clarify_operation(self, planner):
        """'what do you mean by that' should classify as CLARIFY."""
        operation = planner._classify_operation(
            "what do you mean by that", [{"id": "1"}]
        )
        assert operation == OperationType.CLARIFY

    def test_modify_with_addition(self, planner):
        """'also add error handling' should classify as MODIFY."""
        operation = planner._classify_operation("also add error handling", [{"id": "1"}])
        assert operation == OperationType.MODIFY


class TestReferenceResolution:
    """Test resolving what is being referenced."""

    def test_single_artifact_reference(self, planner, sample_artifacts):
        """Single artifact should be resolved as reference."""
        ref, artifact_id = planner._resolve_reference(
            "explain it", sample_artifacts, {}
        )
        assert artifact_id == "code-1"
        assert ref == "code"

    def test_multiple_artifacts_type_hint(self, planner):
        """Type hint in message should resolve to matching artifact."""
        artifacts = [
            {"id": "doc-1", "type": "document"},
            {"id": "code-1", "type": "code"},
        ]
        ref, artifact_id = planner._resolve_reference(
            "modify the code section", artifacts, {}
        )
        assert artifact_id == "code-1"
        assert ref == "code"

    def test_multiple_artifacts_no_hint_returns_most_recent(self, planner):
        """Without type hint, most recent artifact should be returned."""
        artifacts = [
            {"id": "doc-1", "type": "document"},
            {"id": "code-1", "type": "code"},
        ]
        ref, artifact_id = planner._resolve_reference("explain this", artifacts, {})
        assert artifact_id == "code-1"  # Most recent

    def test_document_type_reference(self, planner):
        """'document' keyword should resolve to document artifact."""
        artifacts = [
            {"id": "code-1", "type": "code"},
            {"id": "doc-1", "type": "document"},
        ]
        ref, artifact_id = planner._resolve_reference(
            "make the document shorter", artifacts, {}
        )
        assert artifact_id == "doc-1"
        assert ref == "document"


class TestOutputModeSelection:
    """Test output mode determination."""

    def test_explain_outputs_explanation(self, planner, sample_artifacts):
        """EXPLAIN operation should use explanation mode."""
        mode = planner._determine_output_mode(
            OperationType.EXPLAIN, sample_artifacts, "code-1"
        )
        assert mode == "explanation"

    def test_summarize_outputs_summary(self, planner, sample_artifacts):
        """SUMMARIZE operation should use summary mode."""
        mode = planner._determine_output_mode(
            OperationType.SUMMARIZE, sample_artifacts, "code-1"
        )
        assert mode == "summary"

    def test_transform_outputs_transformed(self, planner, sample_artifacts):
        """TRANSFORM operation should use transformed mode."""
        mode = planner._determine_output_mode(
            OperationType.TRANSFORM, sample_artifacts, "code-1"
        )
        assert mode == "transformed"

    def test_continue_preserves_format(self, planner, sample_artifacts):
        """CONTINUE should preserve original format."""
        mode = planner._determine_output_mode(
            OperationType.CONTINUE, sample_artifacts, "code-1"
        )
        assert mode == "markdown"  # Artifact's format

    def test_clarify_outputs_clarification(self, planner, sample_artifacts):
        """CLARIFY operation should use clarification mode."""
        mode = planner._determine_output_mode(
            OperationType.CLARIFY, sample_artifacts, "code-1"
        )
        assert mode == "clarification"


class TestChangeTypeExtraction:
    """Test extracting change types from messages."""

    def test_addition_change_type(self, planner):
        """'also add' should extract addition change."""
        change = planner._extract_change_type("also add error handling", OperationType.MODIFY)
        assert change == "addition"

    def test_subtraction_change_type(self, planner):
        """'remove' should extract subtraction change."""
        change = planner._extract_change_type("remove the loop", OperationType.MODIFY)
        assert change == "subtraction"

    def test_replacement_change_type(self, planner):
        """'fix' should extract replacement change."""
        change = planner._extract_change_type("fix the bug", OperationType.MODIFY)
        assert change == "replacement"

    def test_language_transform_type(self, planner):
        """'convert to Python' should extract language transform."""
        change = planner._extract_change_type("convert it to Python", OperationType.TRANSFORM)
        assert change == "to_python"

    def test_javascript_transform_type(self, planner):
        """'convert to JavaScript' should extract JS transform."""
        change = planner._extract_change_type(
            "convert to javascript", OperationType.TRANSFORM
        )
        assert change == "to_javascript"


class TestConstraintExtraction:
    """Test extracting constraints from messages."""

    def test_short_length_constraint(self, planner):
        """'short' should extract length constraint."""
        constraints = planner._extract_constraints("make it short", OperationType.EXPLAIN)
        assert constraints.get("length") == "short"

    def test_long_length_constraint(self, planner):
        """'detailed' should extract long length constraint."""
        constraints = planner._extract_constraints("be detailed", OperationType.EXPLAIN)
        assert constraints.get("length") == "long"

    def test_verbosity_detailed(self, planner):
        """'every step' should mark verbosity as detailed."""
        constraints = planner._extract_constraints(
            "explain every step", OperationType.EXPLAIN
        )
        assert constraints.get("verbosity") == "detailed"

    def test_verbosity_minimal(self, planner):
        """'tldr' should mark verbosity as minimal."""
        constraints = planner._extract_constraints("tldr", OperationType.EXPLAIN)
        assert constraints.get("verbosity") == "minimal"

    def test_complexity_simple(self, planner):
        """'simple' should extract simple complexity."""
        constraints = planner._extract_constraints("make it simple", OperationType.EXPLAIN)
        assert constraints.get("complexity") == "simple"

    def test_complexity_advanced(self, planner):
        """'advanced' should extract advanced complexity."""
        constraints = planner._extract_constraints("advanced explanation", OperationType.EXPLAIN)
        assert constraints.get("complexity") == "advanced"


class TestFullResponsePlanning:
    """Integration tests for full planning flow."""

    def test_code_to_explanation_plan(self, planner, sample_artifacts, conversation_context):
        """'explain it every step' after code should produce EXPLAIN plan."""
        plan = planner.plan(
            "explain it every step",
            conversation_context=conversation_context,
            previous_artifacts=sample_artifacts,
            follow_up_trace={"follow_up_detected": True},
        )

        assert plan is not None
        assert plan.operation == OperationType.EXPLAIN
        assert plan.reference == "code"
        assert plan.target_artifact_id == "code-1"
        assert plan.output_mode == "explanation"
        assert plan.preserve_format is True  # EXPLAIN keeps structure, just changes mode
        assert plan.constraints.get("verbosity") == "detailed"
        assert plan.confidence > 0.8

    def test_code_to_python_transform_plan(self, planner, sample_artifacts):
        """'convert to Python' should produce TRANSFORM plan."""
        plan = planner.plan(
            "convert it to Python",
            previous_artifacts=sample_artifacts,
            follow_up_trace={"follow_up_detected": True},
        )

        assert plan is not None
        assert plan.operation == OperationType.TRANSFORM
        assert plan.reference == "code"
        assert plan.target_artifact_id == "code-1"
        assert plan.output_mode == "transformed"
        assert plan.change_type == "to_python"
        assert plan.preserve_format is False

    def test_code_to_modification_plan(self, planner, sample_artifacts):
        """'fix the second function' should produce CORRECT plan."""
        plan = planner.plan(
            "fix the second function",
            previous_artifacts=sample_artifacts,
            follow_up_trace={"follow_up_detected": True},
        )

        assert plan is not None
        assert plan.operation == OperationType.CORRECT
        assert plan.target_artifact_id == "code-1"
        assert plan.preserve_format is True

    def test_ambiguous_reference_requests_clarification(self, planner):
        """Ambiguous 'it' with no previous artifact should request clarification."""
        plan = planner.plan(
            "explain it",
            previous_artifacts=[],
        )

        assert plan is None  # No artifacts to reference

    def test_new_unrelated_request_returns_none(self, planner, sample_artifacts):
        """Completely new request should return None (not a follow-up)."""
        plan = planner.plan(
            "build a website for my startup",
            previous_artifacts=sample_artifacts,
            follow_up_trace={"follow_up_detected": False},
        )

        assert plan is None

    def test_clarification_plan(self, planner, sample_artifacts):
        """'what do you mean' should produce CLARIFY plan."""
        plan = planner.plan(
            "what do you mean by recursion",
            previous_artifacts=sample_artifacts,
            follow_up_trace={"follow_up_detected": True},
        )

        assert plan is not None
        assert plan.operation == OperationType.CLARIFY
        assert plan.output_mode == "clarification"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_message(self, planner, sample_artifacts):
        """Empty message should not cause errors."""
        plan = planner.plan(
            "",
            previous_artifacts=sample_artifacts,
        )
        assert plan is None

    def test_none_artifacts(self, planner):
        """None artifacts should return None plan."""
        plan = planner.plan(
            "explain it",
            previous_artifacts=None,
        )
        assert plan is None

    def test_empty_artifacts_list(self, planner):
        """Empty artifacts list should return None plan."""
        plan = planner.plan(
            "explain it",
            previous_artifacts=[],
        )
        assert plan is None

    def test_case_insensitive_matching(self, planner, sample_artifacts):
        """Operation classification should be case-insensitive."""
        plan1 = planner.plan(
            "EXPLAIN IT",
            previous_artifacts=sample_artifacts,
            follow_up_trace={"follow_up_detected": True},
        )
        plan2 = planner.plan(
            "explain it",
            previous_artifacts=sample_artifacts,
            follow_up_trace={"follow_up_detected": True},
        )

        assert plan1.operation == plan2.operation

    def test_multiple_constraints_extracted(self, planner):
        """Multiple constraints in message should all be extracted."""
        constraints = planner._extract_constraints(
            "explain it briefly but in simple terms",
            OperationType.EXPLAIN,
        )

        assert constraints.get("length") == "short"
        assert constraints.get("complexity") == "simple"
