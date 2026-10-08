"""Opt-in live provider diagnostics. Run from the backend root; never imported by production."""
import argparse
import asyncio
import json
import logging
import statistics
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.intelligence.ai.model_router.router import ModelRouter
from app.intelligence.ai.model_router.registry import configured_models


PROMPTS = {
    "basic": "Reply with exactly: CEASER LLM TEST OK",
    "normal": "Explain what CEASER is in two short sentences.",
    "quality": "A user asks: What is the difference between RAM and storage? Explain clearly for a college student in three short points.",
    "stream": "Explain how an operating system manages applications, memory, files, and processes.",
}


def summary(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    def percentile(p):
        index = (len(values) - 1) * p
        lo = int(index)
        hi = min(lo + 1, len(values) - 1)
        return round(values[lo] + (values[hi] - values[lo]) * (index - lo), 2)
    return dict(n=len(values), min=round(values[0], 2), max=round(values[-1], 2),
                average=round(statistics.mean(values), 2), p50=percentile(.5), p95=percentile(.95))


async def attempt(provider, model, kind, deadline):
    started = perf_counter()
    result = dict(kind=kind, success=False, http_status=None, first_chunk_ms=None,
                  connection_ms=None, first_byte_ms=None, finish_reason=None, chunks=0)
    trace = {}
    chunks = []
    try:
        async with asyncio.timeout(deadline):
            args = dict(instructions="Answer concisely and accurately.", input_text=PROMPTS[kind],
                        model=model.provider_model_name, max_output_tokens=256)
            if kind == "stream":
                stream = provider.stream(**args, trace=trace)
                try:
                    async for chunk in stream:
                        if chunk:
                            if result["first_chunk_ms"] is None:
                                result["first_chunk_ms"] = round((perf_counter() - started) * 1000, 2)
                            chunks.append(chunk)
                finally:
                    await stream.aclose()
                content = "".join(chunks)
                result["chunks"] = len(chunks)
            else:
                content = await provider.generate(**args)
            result.update(success=bool(content.strip()), response=content, response_length=len(content),
                          exact_match=content.strip() == "CEASER LLM TEST OK" if kind == "basic" else None,
                          finish_reason=trace.get("finish_reason"))
            if not content.strip():
                result["error_category"] = "empty_response"
    except Exception as exc:
        # Never serialize exception messages, bodies, URLs, or request headers.
        response = getattr(exc, "response", None)
        result.update(error_type=type(exc).__name__,
                      error_category=getattr(exc, "category", "timeout" if isinstance(exc, TimeoutError) else "unknown"),
                      http_status=getattr(response, "status_code", getattr(exc, "status_code", None)))
    result["total_ms"] = round((perf_counter() - started) * 1000, 2)
    return result


async def run(args):
    router = ModelRouter()
    report = {"scope": "direct provider adapters, not production chat TTFT",
              "cold_definition": "fresh local HTTP client; provider cold start not controllable",
              "unobservable": ["provider queue time", "connection time", "raw first byte", "HTTP status on successful adapter calls"],
              "models": []}
    try:
        for model in configured_models():
            item = dict(provider=model.provider_id, model=model.provider_model_name,
                        model_id=model.model_id, registry_available=model.available, tests=[])
            report["models"].append(item)
            if not model.available or not model.enabled:
                item.update(status="NOT_TESTED", reason="registry unavailable or disabled", model_available=None)
                continue
            factory = router.provider_factories.get(model.provider_id)
            if factory is None:
                item.update(status="MISCONFIGURED", model_available=None)
                continue
            provider = factory()
            try:
                for kind in PROMPTS:
                    result = await attempt(provider, model, kind, args.deadline)
                    item["tests"].append(result)
                    if not result["success"] and kind == "basic":
                        break
                if item["tests"][0]["success"]:
                    for phase, count in (("fresh_client", args.cold), ("warm_client", args.warm)):
                        for _ in range(count):
                            for kind in ("basic", "stream"):
                                if phase == "fresh_client":
                                    await provider.aclose()
                                result = await attempt(provider, model, kind, args.deadline)
                                result["phase"] = phase
                                item["tests"].append(result)
            finally:
                await provider.aclose()
            tests = item["tests"]
            successful = [t for t in tests if t["success"]]
            item["model_available"] = True if successful else None
            category = tests[0].get("error_category")
            item["status"] = "HEALTHY" if len(successful) == len(tests) else "DEGRADED" if successful else "UNAVAILABLE"
            if category == "model_unavailable":
                item.update(status="INVALID_MODEL", model_available=False)
            for phase in ("fresh_client", "warm_client"):
                rows = [t for t in successful if t.get("phase") == phase]
                item[phase] = dict(generation=summary([t["total_ms"] for t in rows if t["kind"] == "basic"]),
                                   ttft=summary([t["first_chunk_ms"] for t in rows if t["kind"] == "stream"]),
                                   stream_total=summary([t["total_ms"] for t in rows if t["kind"] == "stream"]))
            print(model.provider_id, model.model_id, item["status"], flush=True)
    finally:
        await router.aclose()
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cold", type=int, choices=range(0, 4), default=3)
    parser.add_argument("--warm", type=int, choices=range(0, 6), default=5)
    parser.add_argument("--deadline", type=float, default=20)
    args = parser.parse_args()
    if not 0 < args.deadline <= 60:
        parser.error("deadline must be between 0 and 60 seconds")
    logging.disable(logging.CRITICAL)
    asyncio.run(run(args))
