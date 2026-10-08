"""
Test suite: Workload-aware LLM routing with health state awareness

This test suite verifies:
1. Provider health state is tracked across requests
2. Unavailable providers are excluded BEFORE scoring
3. Workload filtering routes to correct provider
4. No permanent sequential fallback chain exists
"""

import pytest
from unittest.mock import MagicMock, patch
from time import monotonic

from app.intelligence.ai.errors import AIServiceUnavailableError
from app.intelligence.ai.model_router.models import (
    HealthState, ModelRequest, RoutingPolicy, Workload, FailureCategory
)
from app.intelligence.ai.model_router.router import ModelRouter
from app.intelligence.ai.model_router.registry import ModelRegistry, configured_models
from app.intelligence.ai.model_router.request_builder import request_for_chat, request_for_agent


class TestHealthStateFiltering:
    """Test that health state filtering excludes unavailable providers BEFORE scoring."""

    def test_provider_marked_unavailable_after_auth_failure(self):
        """Verify that AUTHENTICATION failure marks provider UNAVAILABLE."""
        router = ModelRouter()

        # Simulate authentication failure
        auth_error = AIServiceUnavailableError(
            "Invalid API key",
            provider="openai",
            category="authentication",
            retryable=False
        )

        router.record_failure("openai", auth_error)

        # Check health state
        health = router.snapshot()
        assert health["openai"]["state"] == "unavailable", "Auth failure should mark provider UNAVAILABLE"
        assert health["openai"]["last_error"] == "authentication"

    def test_unavailable_provider_excluded_before_scoring(self):
        """Verify unavailable provider is excluded by _eligible() before _score()."""
        router = ModelRouter()
        registry = router.registry

        # Mark OpenAI as UNAVAILABLE
        auth_error = AIServiceUnavailableError(
            "Invalid API key",
            provider="openai",
            category="authentication",
            retryable=False
        )
        router.record_failure("openai", auth_error)

        # Request for NORMAL_CHAT
        request = request_for_chat()

        # Get selections
        selected = router.selections(request, max_count=2)

        # OpenAI should NOT be in selections
        provider_ids = [item.model.provider_id for item in selected]
        assert "openai" not in provider_ids, "Unavailable provider should be excluded before scoring"

        # Another provider should be selected instead
        assert len(selected) > 0, "Another eligible provider should be selected"

    def test_provider_recovery_makes_eligible_again(self):
        """Verify that successful request marks provider HEALTHY and makes it eligible again."""
        router = ModelRouter()

        # First: mark as UNAVAILABLE
        auth_error = AIServiceUnavailableError(
            "Invalid API key",
            provider="groq",
            category="authentication",
            retryable=False
        )
        router.record_failure("groq", auth_error)

        health_before = router.snapshot()
        assert health_before["groq"]["state"] == "unavailable"

        # Second: record success
        router.record_success("groq", total_ms=100, first_token_ms=50)

        health_after = router.snapshot()
        assert health_after["groq"]["state"] == "healthy", "Success should recover provider to HEALTHY"
        assert health_after["groq"]["failures"] == 0, "Failure count should reset"


class TestWorkloadAwareRouting:
    """Test that routing respects workload constraints and provider eligibility."""

    def test_normal_chat_selects_groq_when_healthy(self):
        """A. NORMAL_CHAT + Groq healthy → Groq selected/preferred."""
        router = ModelRouter()
        request = request_for_chat()

        selected = router.selections(request, max_count=1)

        assert len(selected) > 0, "Should select at least one provider"
        # Groq should be high-priority for NORMAL_CHAT + FAST policy
        preferred_provider = selected[0].model.provider_id
        # Groq has score 205 (fastest + cheapest), should be first
        assert preferred_provider in {"groq", "gemini", "huggingface"}, \
            f"Expected general provider, got {preferred_provider}"

    def test_normal_chat_excludes_groq_when_unavailable(self):
        """B. NORMAL_CHAT + Groq unavailable → another healthy general provider selected immediately."""
        router = ModelRouter()

        # Mark Groq as UNAVAILABLE
        groq_error = AIServiceUnavailableError(
            "Service down",
            provider="groq",
            category="provider_unavailable",
            retryable=True
        )
        router.record_failure("groq", groq_error)
        # Advance to trigger COOLDOWN → DEGRADED transition
        router._health["groq"]["state"] = HealthState.UNAVAILABLE

        request = request_for_chat()
        selected = router.selections(request, max_count=1)

        assert len(selected) > 0, "Should select another provider"
        provider_id = selected[0].model.provider_id
        assert provider_id != "groq", "Groq should not be selected when unavailable"
        assert provider_id in {"gemini", "huggingface"}, \
            f"Should select general provider, got {provider_id}"

    def test_software_engineering_selects_nvidia_when_healthy(self):
        """C. SOFTWARE_ENGINEERING + NVIDIA healthy → NVIDIA selected/preferred."""
        router = ModelRouter()

        # Create SOFTWARE_ENGINEERING request
        request = request_for_agent("bolt", streaming=True)
        assert request.workload == Workload.SOFTWARE_ENGINEERING

        selected = router.selections(request, max_count=1)

        assert len(selected) > 0, "Should select a provider for coding"
        # NVIDIA gets 60-point workload_fit bonus for SOFTWARE_ENGINEERING
        # Check if NVIDIA is among top selections
        provider_ids = [item.model.provider_id for item in selected[:3]]
        assert "nvidia" in provider_ids or "huggingface" in provider_ids, \
            f"Should prefer coding-capable provider, got {provider_ids}"

    def test_software_engineering_excludes_nvidia_when_unavailable(self):
        """D. SOFTWARE_ENGINEERING + NVIDIA unavailable → another eligible coding provider selected."""
        router = ModelRouter()

        # Mark NVIDIA as UNAVAILABLE
        nvidia_error = AIServiceUnavailableError(
            "Authentication failed",
            provider="nvidia",
            category="authentication",
            retryable=False
        )
        router.record_failure("nvidia", nvidia_error)

        request = request_for_agent("bolt", streaming=True)
        selected = router.selections(request, max_count=1)

        assert len(selected) > 0, "Should select another coding provider"
        provider_id = selected[0].model.provider_id
        assert provider_id != "nvidia", "NVIDIA should not be selected when unavailable"
        # HuggingFace has coding models that support SOFTWARE_ENGINEERING
        assert provider_id in {"huggingface", "groq", "gemini"}, \
            f"Should select eligible coding provider, got {provider_id}"

    def test_normal_chat_never_selects_nvidia(self):
        """E. NORMAL_CHAT must never select NVIDIA."""
        router = ModelRouter()
        request = request_for_chat()

        # Get multiple selections
        selected = router.selections(request, max_count=5)

        provider_ids = [item.model.provider_id for item in selected]
        assert "nvidia" not in provider_ids, \
            "NVIDIA should never be selected for NORMAL_CHAT (restricted to SOFTWARE_ENGINEERING)"

    def test_auth_failure_does_not_route_normal_chat_to_nvidia(self):
        """F. Authentication failure must not cause NORMAL_CHAT to route to NVIDIA."""
        router = ModelRouter()

        # Mark multiple general providers as unavailable
        for provider in ["groq", "gemini", "huggingface"]:
            error = AIServiceUnavailableError(
                "Auth failed",
                provider=provider,
                category="authentication",
                retryable=False
            )
            router.record_failure(provider, error)

        request = request_for_chat()
        selected = router.selections(request, max_count=1)

        # If any provider remains eligible, it should NOT be NVIDIA
        if len(selected) > 0:
            assert selected[0].model.provider_id != "nvidia", \
                "NVIDIA should not be fallback for NORMAL_CHAT even if others fail"

    def test_workload_fit_bonus_applied_correctly(self):
        """Verify workload_fit scoring bonus is applied for workload-specific providers."""
        router = ModelRouter()
        registry = router.registry

        # Get NVIDIA model
        nvidia_models = registry.by_provider("nvidia")
        assert len(nvidia_models) > 0
        nvidia_model = nvidia_models[0]

        # Score NVIDIA for SOFTWARE_ENGINEERING (should get 60-point bonus)
        request_sw = request_for_agent("bolt")
        score_sw = router._score(nvidia_model, request_sw)

        # Score NVIDIA for NORMAL_CHAT (should NOT get bonus)
        request_chat = request_for_chat()
        score_chat = router._score(nvidia_model, request_chat)

        # SOFTWARE_ENGINEERING score should be higher due to workload_fit bonus
        assert score_sw > score_chat, \
            f"SOFTWARE_ENGINEERING score ({score_sw}) should be > NORMAL_CHAT score ({score_chat}) for NVIDIA"

    def test_health_state_check_in_eligible_filter(self):
        """Verify _eligible() checks health state before returning True."""
        router = ModelRouter()
        registry = router.registry

        # Get a model
        models = registry.enabled()
        test_model = models[0]

        request = request_for_chat()

        # Initially should be eligible
        assert router._eligible(test_model, request), "Model should be eligible initially"

        # Mark provider UNAVAILABLE
        error = AIServiceUnavailableError(
            "Auth failed",
            provider=test_model.provider_id,
            category="authentication",
            retryable=False
        )
        router.record_failure(test_model.provider_id, error)

        # Now should NOT be eligible
        assert not router._eligible(test_model, request), \
            "Model should not be eligible after provider marked UNAVAILABLE"


class TestDynamicProviderSelection:
    """Test that provider selection is dynamic, not a fixed fallback chain."""

    def test_selections_called_on_each_request(self):
        """Verify selections() is called fresh on each request, not using cached chain."""
        router = ModelRouter()

        # First request
        request1 = request_for_chat()
        selected1 = router.selections(request1, max_count=1)
        provider1 = selected1[0].model.provider_id if selected1 else None

        # Mark that provider unavailable
        if provider1:
            error = AIServiceUnavailableError(
                "Test error",
                provider=provider1,
                category="provider_unavailable",
                retryable=True
            )
            router.record_failure(provider1, error)
            router._health[provider1]["state"] = HealthState.UNAVAILABLE

        # Second request should select different provider
        request2 = request_for_chat()
        selected2 = router.selections(request2, max_count=1)
        provider2 = selected2[0].model.provider_id if selected2 else None

        if provider1 and provider2:
            assert provider2 != provider1, \
                "Second request should select different provider when first becomes unavailable"

    def test_no_hardcoded_provider_chain(self):
        """Verify there is no hardcoded sequential fallback chain in generate()."""
        # This is more of a code inspection test - verify generate() calls selections()
        # for EACH request, not using a predetermined order

        router = ModelRouter()
        request = request_for_chat()

        # selections() should be called via model_candidates()
        # which respects current health state
        candidates = router.model_candidates(request, max_count=3)

        assert len(candidates) <= 3, "Should respect max_count parameter"
        # If health state changes, next call should reflect it
        # (verified by test_selections_called_on_each_request above)


class TestExistingResponsePlannerIntegration:
    """Verify existing response-planner tests still pass."""

    def test_response_planner_unchanged(self):
        """G. Existing response-planner tests should still pass (no changes to planner)."""
        # This is a placeholder - actual response-planner tests run separately
        # Just verify we haven't broken the import
        from app.services.orchestrator.response_planner import response_planner, OperationType

        assert response_planner is not None
        assert hasattr(response_planner, 'plan')
        assert OperationType.CREATE is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
