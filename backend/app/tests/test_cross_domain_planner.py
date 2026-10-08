"""Cross-domain tests for Response Planner: verify generic behavior across artifact types."""

import pytest
from app.services.orchestrator.response_planner import OperationType, response_planner


class TestCrossDomainOperations:
    """Verify planner works generically across different domains and artifact types."""

    def test_code_to_explanation(self):
        """Code: 'Write Python factorial code.' → 'Explain this simply.'"""
        previous_artifacts = [
            {"id": "code-1", "type": "code", "content": "```python\ndef factorial(n):\n    return n * factorial(n-1) if n > 0 else 1\n```"}
        ]
        plan = response_planner.plan(
            "Explain this simply.",
            conversation_context={"messages": []},
            previous_artifacts=previous_artifacts,
            follow_up_trace={"follow_up_detected": True, "active_topic": "factorial function"},
        )
        assert plan is not None
        assert plan.operation == OperationType.EXPLAIN
        assert plan.output_mode == "explanation"
        assert plan.allow_artifact_generation is False

    def test_business_plan_to_explanation(self):
        """Business Plan: 'Create a business plan.' → 'Explain this simply.'"""
        previous_artifacts = [
            {"id": "doc-1", "type": "document", "content": "# Business Plan\n## Market Analysis\n## Revenue Model"}
        ]
        plan = response_planner.plan(
            "Explain this simply.",
            conversation_context={"messages": []},
            previous_artifacts=previous_artifacts,
            follow_up_trace={"follow_up_detected": True, "active_topic": "business plan"},
        )
        assert plan is not None
        assert plan.operation == OperationType.EXPLAIN
        assert plan.output_mode == "explanation"
        assert plan.allow_artifact_generation is False

    def test_research_to_summarize(self):
        """Research: 'Research battery recycling.' → 'Summarize this.'"""
        previous_artifacts = [
            {"id": "doc-2", "type": "document", "content": "# Research Report\n## Findings\n## Statistics"}
        ]
        plan = response_planner.plan(
            "Summarize this.",
            conversation_context={"messages": []},
            previous_artifacts=previous_artifacts,
            follow_up_trace={"follow_up_detected": True, "active_topic": "battery recycling"},
        )
        assert plan is not None
        assert plan.operation == OperationType.SUMMARIZE
        assert plan.output_mode == "summary"
        assert plan.allow_artifact_generation is False

    def test_code_to_transform(self):
        """Code: 'Write a C program.' → 'Convert it to Python.'"""
        previous_artifacts = [
            {"id": "code-1", "type": "code", "content": "```c\nint main() { return 0; }\n```"}
        ]
        plan = response_planner.plan(
            "Convert it to Python.",
            conversation_context={"messages": []},
            previous_artifacts=previous_artifacts,
            follow_up_trace={"follow_up_detected": True, "active_topic": "C program"},
        )
        assert plan is not None
        assert plan.operation == OperationType.TRANSFORM
        assert plan.change_type == "to_python"
        assert plan.output_mode == "transformed"
        assert plan.allow_artifact_generation is True  # TRANSFORM allows generation

    def test_email_make_more_professional(self):
        """Email: 'Write this email.' → 'Make it more professional.'"""
        previous_artifacts = [
            {"id": "doc-1", "type": "document", "content": "Hi, I wanted to reach out about the project..."}
        ]
        plan = response_planner.plan(
            "Make it more professional.",
            conversation_context={"messages": []},
            previous_artifacts=previous_artifacts,
            follow_up_trace={"follow_up_detected": True, "active_topic": "email"},
        )
        assert plan is not None
        assert plan.operation == OperationType.MODIFY
        assert plan.allow_artifact_generation is True  # MODIFY allows generation

    def test_calculation_change_value(self):
        """Calculation: 'Calculate investment return.' → 'Change the investment to ₹20 lakh.'"""
        previous_artifacts = [
            {"id": "doc-1", "type": "document", "content": "Investment: ₹10 lakh\nReturn: 12%"}
        ]
        plan = response_planner.plan(
            "Change the investment to ₹20 lakh.",
            conversation_context={"messages": []},
            previous_artifacts=previous_artifacts,
            follow_up_trace={"follow_up_detected": True, "active_topic": "investment return"},
        )
        assert plan is not None
        assert plan.operation == OperationType.MODIFY
        assert plan.allow_artifact_generation is True

    def test_make_it_shorter(self):
        """Generic: 'Make it shorter.' should be MODIFY, not CREATE."""
        previous_artifacts = [
            {"id": "doc-1", "type": "document", "content": "# Very Long Document\n...content..."}
        ]
        plan = response_planner.plan(
            "Make it shorter.",
            conversation_context={"messages": []},
            previous_artifacts=previous_artifacts,
            follow_up_trace={"follow_up_detected": True, "active_topic": "document"},
        )
        assert plan is not None
        assert plan.operation == OperationType.MODIFY
        assert plan.allow_artifact_generation is True

    def test_make_it_simpler(self):
        """Generic: 'Make it simpler.' should be MODIFY."""
        previous_artifacts = [
            {"id": "doc-1", "type": "document", "content": "Complex technical content"}
        ]
        plan = response_planner.plan(
            "Make it simpler.",
            conversation_context={"messages": []},
            previous_artifacts=previous_artifacts,
            follow_up_trace={"follow_up_detected": True, "active_topic": "technical content"},
        )
        assert plan is not None
        assert plan.operation == OperationType.MODIFY

    def test_make_it_clearer(self):
        """Generic: 'Make it clearer.' should be MODIFY."""
        previous_artifacts = [
            {"id": "doc-1", "type": "document", "content": "Ambiguous content"}
        ]
        plan = response_planner.plan(
            "Make it clearer.",
            conversation_context={"messages": []},
            previous_artifacts=previous_artifacts,
            follow_up_trace={"follow_up_detected": True, "active_topic": "content"},
        )
        assert plan is not None
        assert plan.operation == OperationType.MODIFY

    def test_make_it_more_detailed(self):
        """Generic: 'Make it more detailed.' should be MODIFY."""
        previous_artifacts = [
            {"id": "doc-1", "type": "document", "content": "Brief summary"}
        ]
        plan = response_planner.plan(
            "Make it more detailed.",
            conversation_context={"messages": []},
            previous_artifacts=previous_artifacts,
            follow_up_trace={"follow_up_detected": True, "active_topic": "summary"},
        )
        assert plan is not None
        assert plan.operation == OperationType.MODIFY

    def test_multiple_artifacts_reference_resolution(self):
        """Multiple artifacts: verify correct one is resolved."""
        previous_artifacts = [
            {"id": "doc-1", "type": "document", "content": "Business Plan"},
            {"id": "code-1", "type": "code", "content": "```python\ncode here\n```"},
            {"id": "doc-2", "type": "document", "content": "Email template"},
        ]
        # Asking about "the code" should resolve to code artifact
        plan = response_planner.plan(
            "Explain the code.",
            conversation_context={"messages": []},
            previous_artifacts=previous_artifacts,
            follow_up_trace={"follow_up_detected": True, "active_topic": "code"},
        )
        assert plan is not None
        assert plan.target_artifact_id == "code-1"
        assert plan.reference == "code"


class TestOutputModeIndependence:
    """Verify output_mode is independent of artifact_type."""

    def test_code_artifact_explain_outputs_explanation_not_code(self):
        """Code artifact + EXPLAIN should output 'explanation', not 'code'."""
        previous_artifacts = [
            {"id": "code-1", "type": "code", "format": "markdown"}
        ]
        plan = response_planner.plan(
            "Explain this.",
            conversation_context={"messages": []},
            previous_artifacts=previous_artifacts,
            follow_up_trace={"follow_up_detected": True, "active_topic": "code"},
        )
        assert plan.output_mode == "explanation"  # NOT "markdown" or "code"

    def test_document_artifact_summarize_outputs_summary_not_document(self):
        """Document artifact + SUMMARIZE should output 'summary', not original format."""
        previous_artifacts = [
            {"id": "doc-1", "type": "document", "format": "markdown"}
        ]
        plan = response_planner.plan(
            "Summarize this.",
            conversation_context={"messages": []},
            previous_artifacts=previous_artifacts,
            follow_up_trace={"follow_up_detected": True, "active_topic": "document"},
        )
        assert plan.output_mode == "summary"  # NOT "markdown"


class TestArchitecturalInvariants:
    """Test architectural invariants that must always hold."""

    def test_non_generative_disallow_artifacts(self):
        """EXPLAIN, SUMMARIZE, CLARIFY must not allow artifact generation."""
        previous_artifacts = [{"id": "doc-1", "type": "document"}]

        for operation_type in ["Explain this.", "Summarize this.", "Clarify what you mean."]:
            plan = response_planner.plan(
                operation_type,
                conversation_context={"messages": []},
                previous_artifacts=previous_artifacts,
                follow_up_trace={"follow_up_detected": True, "active_topic": "something"},
            )
            assert plan.allow_artifact_generation is False, f"Failed for: {operation_type}"

    def test_generative_allow_artifacts(self):
        """CREATE, MODIFY, TRANSFORM must allow artifact generation."""
        previous_artifacts = [{"id": "code-1", "type": "code"}]

        for operation_type in ["Change this.", "Convert to Python."]:
            plan = response_planner.plan(
                operation_type,
                conversation_context={"messages": []},
                previous_artifacts=previous_artifacts,
                follow_up_trace={"follow_up_detected": True, "active_topic": "code"},
            )
            assert plan.allow_artifact_generation is True, f"Failed for: {operation_type}"

    def test_response_plan_preserves_fields(self):
        """ResponsePlan must preserve all fields from creation to use."""
        previous_artifacts = [{"id": "doc-1", "type": "document"}]
        plan = response_planner.plan(
            "Explain this simply.",
            conversation_context={"messages": []},
            previous_artifacts=previous_artifacts,
            follow_up_trace={"follow_up_detected": True, "active_topic": "business plan"},
        )

        # Verify all fields are present and populated
        assert plan.operation is not None
        assert plan.reference is not None
        assert plan.target_artifact_id is not None
        assert plan.output_mode is not None
        assert hasattr(plan, 'allow_artifact_generation')
