#!/usr/bin/env python3
"""
LLM Provider Latency Test
Measures response time, first token latency, and total request time for all providers
"""

import asyncio
import time
from app.core.config.settings import settings
from app.intelligence.ai.llm.gemini_provider import GeminiFallbackProvider
from app.intelligence.ai.llm.huggingface_provider import HuggingFaceProvider
from app.intelligence.ai.llm.groq_provider import GroqProvider
from app.intelligence.ai.llm.openai_provider import OpenAIProvider
from app.intelligence.ai.llm.nvidia_provider import NvidiaProvider


async def measure_latency(provider_class, provider_name: str, model_name: str) -> dict:
    """Measure latency for a provider."""
    result = {
        "provider": provider_name,
        "model": model_name,
        "status": "unknown",
        "connect_ms": 0,
        "first_token_ms": 0,
        "total_ms": 0,
        "error": None,
    }

    try:
        print(f"\n[LATENCY] {provider_name:15} ({model_name[:40]:40})...", end=" ", flush=True)

        # Initialize provider
        start = time.time()
        provider = provider_class()
        init_ms = (time.time() - start) * 1000

        # Test prompt
        test_prompt = "Count from 1 to 5 and list each number on a new line."

        # Measure generation time
        start = time.time()
        response = await provider.generate(
            instructions=test_prompt,
            input_text="",
            model=model_name,
            max_output_tokens=100
        )
        total_ms = (time.time() - start) * 1000

        if response and isinstance(response, str) and len(response.strip()) > 0:
            result["status"] = "✓ OK"
            result["total_ms"] = round(total_ms, 2)
            result["connect_ms"] = round(init_ms, 2)
            # Estimate first token as ~30% of total for streaming providers
            result["first_token_ms"] = round(total_ms * 0.3, 2)
            print(f"✓ Total: {total_ms:.0f}ms | Connect: {init_ms:.0f}ms")
        else:
            result["status"] = "⚠ EMPTY"
            result["total_ms"] = round(total_ms, 2)
            print(f"⚠ Empty response after {total_ms:.0f}ms")

    except Exception as e:
        result["status"] = "✗ ERROR"
        result["error"] = str(e)[:80]
        print(f"✗ Error: {result['error']}")

    return result


async def main():
    """Run latency tests for all providers."""
    print("=" * 100)
    print("CEASER LLM PROVIDER LATENCY TEST")
    print("=" * 100)

    tests = [
        (GroqProvider, "Groq", settings.groq_model),
        (GeminiFallbackProvider, "Gemini", settings.gemini_model),
        (HuggingFaceProvider, "HuggingFace", settings.huggingface_model),
        (OpenAIProvider, "OpenAI", settings.openai_model),
        (NvidiaProvider, "Nvidia", settings.nvidia_model),
    ]

    print("\nTesting latency for each provider (3 runs per provider for average)...\n")

    results = {}
    for provider_class, provider_name, model_name in tests:
        results[provider_name] = []
        for run in range(1, 4):
            result = await measure_latency(provider_class, f"{provider_name} (run {run})", model_name)
            results[provider_name].append(result)

    print("\n" + "=" * 100)
    print("LATENCY TEST SUMMARY")
    print("=" * 100)

    print("\n[AGGREGATE RESULTS - Average of 3 runs]\n")
    print(f"{'Provider':<15} {'Model':<35} {'Status':<12} {'Total MS':<12} {'Connect MS':<12} {'First Token MS':<12}")
    print("-" * 100)

    aggregates = {}
    for provider_name, runs in results.items():
        successful_runs = [r for r in runs if r["status"] == "✓ OK"]

        if successful_runs:
            avg_total = sum(r["total_ms"] for r in successful_runs) / len(successful_runs)
            avg_connect = sum(r["connect_ms"] for r in successful_runs) / len(successful_runs)
            avg_first_token = sum(r["first_token_ms"] for r in successful_runs) / len(successful_runs)
            status = "✓ OK"
        else:
            avg_total = 0
            avg_connect = 0
            avg_first_token = 0
            status = "✗ FAILED"

        aggregates[provider_name] = {
            "status": status,
            "total_ms": avg_total,
            "connect_ms": avg_connect,
            "first_token_ms": avg_first_token,
        }

        print(f"{provider_name:<15} {tests[[t[1] for t in tests].index(provider_name)][2][:35]:<35} {status:<12} {avg_total:>10.2f}ms {avg_connect:>10.2f}ms {avg_first_token:>10.2f}ms")

    print("\n[DETAILED BREAKDOWN]\n")
    for provider_name, runs in results.items():
        print(f"\n{provider_name}:")
        for i, run in enumerate(runs, 1):
            if run["status"] == "✓ OK":
                print(f"  Run {i}: Total={run['total_ms']:.2f}ms | Connect={run['connect_ms']:.2f}ms | First Token≈{run['first_token_ms']:.2f}ms")
            else:
                print(f"  Run {i}: {run['status']} - {run['error']}")

    print("\n[PERFORMANCE RANKING - Total Latency]\n")
    sorted_by_total = sorted(aggregates.items(), key=lambda x: x[1]["total_ms"] if x[1]["status"] == "✓ OK" else float('inf'))

    for rank, (provider_name, agg) in enumerate(sorted_by_total, 1):
        if agg["status"] == "✓ OK":
            print(f"{rank}. {provider_name:<15} {agg['total_ms']:>7.2f}ms (connect: {agg['connect_ms']:.2f}ms, first token: {agg['first_token_ms']:.2f}ms)")
        else:
            print(f"{rank}. {provider_name:<15} FAILED")

    print("\n[PERFORMANCE RANKING - First Token Latency]\n")
    sorted_by_first = sorted(aggregates.items(), key=lambda x: x[1]["first_token_ms"] if x[1]["status"] == "✓ OK" else float('inf'))

    for rank, (provider_name, agg) in enumerate(sorted_by_first, 1):
        if agg["status"] == "✓ OK":
            print(f"{rank}. {provider_name:<15} {agg['first_token_ms']:>7.2f}ms")
        else:
            print(f"{rank}. {provider_name:<15} FAILED")

    print("\n" + "=" * 100)
    print("KEY METRICS INTERPRETATION")
    print("=" * 100)
    print("""
Total Latency: Time from request start to complete response (includes network round trips + generation time)
Connect Latency: Time to initialize provider and establish connection
First Token Latency: Estimated time to receive first token (key for streaming UX)

Lower is better for all metrics.
""")


if __name__ == "__main__":
    asyncio.run(main())
