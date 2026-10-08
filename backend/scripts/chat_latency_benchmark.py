"""Authenticated endpoint benchmark; creates real billable test conversations.

Supply CEASER_BENCHMARK_ACCESS_TOKEN securely in the process environment.
This measures HTTP/SSE delivery, not browser rendering or provider-only latency.
"""
import argparse
import asyncio
import json
import os
import uuid
from pathlib import Path
from time import perf_counter

import httpx

from llm_provider_benchmark import summary

PROMPTS = {
    "simple": "Hello",
    "general": "What is recursion?",
    "memory": "What did we discuss in this conversation?",
    "research": "What's the latest GPT model?",
}


async def run(args):
    token = os.environ.get("CEASER_BENCHMARK_ACCESS_TOKEN")
    if not token:
        raise SystemExit("Missing CEASER_BENCHMARK_ACCESS_TOKEN; no requests sent.")
    rows = []
    async with httpx.AsyncClient(base_url=args.url, headers={"Authorization": f"Bearer {token}"}, timeout=60) as client:
        conversation = None
        for workload in ("admin", *PROMPTS):
            for index in range(args.samples):
                rid = uuid.uuid4().hex
                row = dict(workload=workload, sample=index, request_id=rid, first_sse_line_ms=None,
                           first_content_ms=None, completed=False, phase="initial" if index == 0 else "warm")
                started = perf_counter()
                try:
                    async with asyncio.timeout(90):
                        if workload == "admin":
                            response = await client.get("/admin/me", headers={"X-Request-Id": rid})
                            row.update(http_status=response.status_code, completed=response.is_success)
                            row["server_timing"] = response.headers.get("server-timing")
                        else:
                            payload = {"message": PROMPTS[workload], "request_id": rid}
                            if workload == "memory" and conversation:
                                payload["conversation_id"] = conversation
                            async with client.stream("POST", "/ceaser/chat/stream", json=payload, headers={"X-Request-Id": rid}) as response:
                                row.update(http_status=response.status_code, server_timing=response.headers.get("server-timing"))
                                row["response_request_id"] = response.headers.get("x-request-id")
                                if response.is_success:
                                    event, data = "", []
                                    async for line in response.aiter_lines():
                                        if row["first_sse_line_ms"] is None:
                                            row["first_sse_line_ms"] = round((perf_counter() - started) * 1000, 2)
                                        if line.startswith("event:"):
                                            event = line[6:].strip()
                                        elif line.startswith("data:"):
                                            data.append(line[5:].lstrip())
                                        elif not line and data:
                                            value = json.loads("\n".join(data))
                                            if event == "token" and value and row["first_content_ms"] is None:
                                                row["first_content_ms"] = round((perf_counter() - started) * 1000, 2)
                                            if event == "response.started":
                                                conversation = value.get("conversation_id", conversation)
                                            if event == "complete":
                                                row["completed"] = True
                                            data, event = [], ""
                except Exception as exc:
                    row["error_type"] = type(exc).__name__
                row["total_ms"] = round((perf_counter() - started) * 1000, 2)
                rows.append(row)
                print(workload, index, row.get("http_status"), row["first_content_ms"], flush=True)
                if row.get("http_status") in (401, 403, 429):
                    break
    stats = {name: {"ttft": summary([r["first_content_ms"] for r in rows if r["workload"] == name and r["completed"]]),
                    "total": summary([r["total_ms"] for r in rows if r["workload"] == name and r["completed"]])}
             for name in ("admin", *PROMPTS)}
    Path(args.output).write_text(json.dumps({"scope": "HTTP client, not browser paint", "requests": rows, "summary": stats}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--samples", type=int, choices=range(1, 6), default=5)
    args = parser.parse_args()
    if not args.url.startswith("https://"):
        parser.error("Use HTTPS to protect the access token")
    asyncio.run(run(args))
