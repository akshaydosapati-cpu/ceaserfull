"""Allowlisted timing metadata for the authenticated stream's own caller."""
import math

TIMING_FIELDS = (
    "auth_total_ms", "auth_remote_ms", "auth_db_validation_ms",
    "rate_check_ms", "concurrency_check_ms", "credit_reservation_ms",
    "conversation_create_ms", "prepare_stream_request_ms", "routing_ms",
    "retrieval_time_ms", "context_build_ms", "search_ms", "extraction_ms",
    "research_total_ms", "model_selection_ms", "prompt_build_ms",
    "provider_connect_ms", "first_token_ms", "llm_request_sent_ms",
    "endpoint_ttft_ms", "first_token_forwarding_ms", "persistence_ms",
    "route_entry_ms", "pre_stream_ms", "prepare_started_ms", "prepare_completed_ms",
    "reservation_snapshot_ms",
    "auth_db_query_ms", "prepare_worker_ms",
    "prepare_logging_ms", "prepare_unattributed_ms",
)
PREPARE_STAGES = frozenset({"attached_documents", "conversation_lookup", "history_load",
    "knowledge_classification", "agent_or_workflow_selection", "context_mode_and_rag_decision",
    "memory_decision", "web_and_tool_decision", "dataset_decision", "prompt_context_assembly"})


def stream_diagnostics(trace, *, request_id, stage, elapsed_ms, db_queries, db_ms):
    result = {"request_id": request_id, "stage": stage, "elapsed_ms": round(elapsed_ms, 2),
              "db_queries": db_queries, "db_ms": db_ms}
    for key in TIMING_FIELDS:
        value = trace.get(key)
        if type(value) in (int, float) and math.isfinite(value) and value >= 0:
            result[key] = round(value, 2)
    # Never copy arbitrary context, prompts, user IDs, errors, or provider bodies.
    result["fallback_used"] = trace.get("fallback_used") is True
    stages = []
    for item in trace.get("prepare_stage_timings", [])[:32]:
        if not isinstance(item, dict) or item.get("stage") not in PREPARE_STAGES:
            continue
        safe = {"stage": item["stage"]}
        for key in ("duration_ms", "db_queries", "db_ms"):
            value = item.get(key)
            if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                safe[key] = value
        stages.append(safe)
    if stages:
        result["prepare_stages"] = stages
    return result
