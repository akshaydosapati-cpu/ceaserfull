from app.core.stream_diagnostics import stream_diagnostics


def test_prepare_breakdown_exposes_only_known_stages_and_numeric_fields():
    result = stream_diagnostics({"prepare_stage_timings": [
        {"stage": "history_load", "duration_ms": 200, "db_queries": 1, "prompt": "private"},
        {"stage": "private-user-name", "duration_ms": 30},
    ]}, request_id="test", stage="first_content_forwarded", elapsed_ms=300, db_queries=1, db_ms=150)
    assert result["prepare_stages"] == [{"stage": "history_load", "duration_ms": 200, "db_queries": 1}]


def test_diagnostics_allowlist_excludes_private_context_and_invalid_timings():
    result = stream_diagnostics(
        {"auth_total_ms": 123.456, "provider_connect_ms": float("nan"),
         "search_ms": "secret", "first_token_ms": -1, "message": "private prompt",
         "user_id": "private-user", "access_token": "private-token", "fallback_used": True},
        request_id="test-request", stage="first_content_forwarded", elapsed_ms=150,
        db_queries=1, db_ms=20,
    )
    assert result == {"request_id": "test-request", "stage": "first_content_forwarded",
                      "elapsed_ms": 150, "db_queries": 1, "db_ms": 20,
                      "auth_total_ms": 123.46, "fallback_used": True}
