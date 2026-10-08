#!/usr/bin/env python3
"""
LLM Provider Connectivity Test
Tests all configured providers: Gemini, HuggingFace, Groq, OpenAI, Nvidia
"""

import asyncio
import sys
from app.core.config.settings import settings
from app.intelligence.ai.model_router.registry import configured_models
from app.intelligence.ai.llm.gemini_provider import GeminiFallbackProvider
from app.intelligence.ai.llm.huggingface_provider import HuggingFaceProvider
from app.intelligence.ai.llm.groq_provider import GroqProvider
from app.intelligence.ai.llm.openai_provider import OpenAIProvider
from app.intelligence.ai.llm.nvidia_provider import NvidiaProvider


async def test_provider(provider_class, provider_name: str, model_name: str) -> dict:
    """Test a single provider with a small prompt."""
    result = {
        "provider": provider_name,
        "model": model_name,
        "status": "unknown",
        "error": None,
        "response_length": 0,
    }

    try:
        print(f"\n[TEST] {provider_name} ({model_name})...", end=" ", flush=True)
        provider = provider_class()

        # Simple test prompt
        test_prompt = "Say 'Hello from provider' and nothing else."

        response = await provider.generate(
            instructions=test_prompt,
            input_text="",
            model=model_name,
            max_output_tokens=50
        )

        if response and isinstance(response, str) and len(response.strip()) > 0:
            result["status"] = "✓ WORKING"
            result["response_length"] = len(response)
            print(f"✓ WORKING (response: {len(response)} chars)")
        else:
            result["status"] = "⚠ EMPTY_RESPONSE"
            result["error"] = "Provider returned empty or non-string response"
            print(f"⚠ EMPTY_RESPONSE")

    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "auth" in error_msg.lower():
            result["status"] = "✗ AUTH_FAILED"
            result["error"] = "Authentication failed (check API key)"
        elif "404" in error_msg:
            result["status"] = "✗ NOT_FOUND"
            result["error"] = "Model or endpoint not found"
        elif "timeout" in error_msg.lower():
            result["status"] = "✗ TIMEOUT"
            result["error"] = "Request timed out"
        elif "connection" in error_msg.lower() or "network" in error_msg.lower():
            result["status"] = "✗ NETWORK_ERROR"
            result["error"] = "Network or connection error"
        else:
            result["status"] = "✗ ERROR"
            result["error"] = error_msg[:100]

        print(f"✗ {result['status']}: {result['error']}")

    return result


async def main():
    """Run all provider tests."""
    print("=" * 80)
    print("CEASER LLM PROVIDER CONNECTIVITY TEST")
    print("=" * 80)

    print("\n[CONFIG] Settings loaded:")
    print(f"  LLM_PROVIDER_ORDER: {settings.llm_provider_order_raw}")
    print(f"  GEMINI_API_KEY present: {bool(settings.gemini_api_key)}")
    print(f"  HUGGINGFACE_API_KEY present: {bool(settings.huggingface_api_key)}")
    print(f"  GROQ_API_KEY present: {bool(settings.groq_api_key)}")
    print(f"  OPENAI_API_KEY present: {bool(settings.openai_api_key)}")
    print(f"  NVIDIA_API_KEY present: {bool(settings.nvidia_api_key)}")

    print("\n[REGISTRY] Model availability:")
    models = configured_models()
    for model in models:
        print(f"  {model.model_id:40} | provider={model.provider_id:12} | available={model.available} | enabled={model.enabled}")

    print("\n" + "=" * 80)
    print("CONNECTIVITY TESTS")
    print("=" * 80)

    tests = [
        (GeminiFallbackProvider, "Gemini", settings.gemini_model),
        (HuggingFaceProvider, "HuggingFace", settings.huggingface_model),
        (GroqProvider, "Groq", settings.groq_model),
        (OpenAIProvider, "OpenAI", settings.openai_model),
        (NvidiaProvider, "Nvidia", settings.nvidia_model),
    ]

    results = []
    for provider_class, provider_name, model_name in tests:
        result = await test_provider(provider_class, provider_name, model_name)
        results.append(result)

    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    working = [r for r in results if "WORKING" in r["status"]]
    failed = [r for r in results if "WORKING" not in r["status"]]

    print(f"\n✓ Working Providers: {len(working)}")
    for r in working:
        print(f"  - {r['provider']:15} ({r['model'][:40]:40}) - {r['status']}")

    print(f"\n✗ Failed Providers: {len(failed)}")
    for r in failed:
        print(f"  - {r['provider']:15} ({r['model'][:40]:40}) - {r['status']}")
        if r['error']:
            print(f"    Error: {r['error']}")

    print("\n" + "=" * 80)
    return results


if __name__ == "__main__":
    results = asyncio.run(main())
    sys.exit(0 if any("WORKING" in r["status"] for r in results) else 1)
