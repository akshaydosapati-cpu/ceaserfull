from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.ceaser import routes
from app.core.security.dependencies import _validate_desktop_user
from app.schemas.ceaser import CeaserChatRequest, CeaserChatResponse


class _Query:
    def __init__(self, row):
        self.row = row
        self.first_calls = 0

    def outerjoin(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        self.first_calls += 1
        return self.row


class _Database:
    def __init__(self, row):
        self.query_object = _Query(row)
        self.query_calls = 0

    def query(self, *_args, **_kwargs):
        self.query_calls += 1
        return self.query_object


def test_desktop_auth_validates_user_and_device_in_one_query():
    user = SimpleNamespace(id="user-1")
    db = _Database((user, None))

    assert _validate_desktop_user(db, "user-1", "device-1") is user
    assert db.query_calls == 1
    assert db.query_object.first_calls == 1


def test_desktop_auth_still_rejects_revoked_device():
    db = _Database((SimpleNamespace(id="user-1"), "revoked-at"))

    with pytest.raises(HTTPException) as exc_info:
        _validate_desktop_user(db, "user-1", "device-1")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Desktop device revoked"


def test_desktop_fast_response_preserves_generated_fallback_text(monkeypatch):
    trace_values = {
        "provider": "gemini",
        "model": "gemini-primary",
        "fallback_used": True,
        "first_token_ms": 120,
        "final_status": "success",
    }

    def generated(**kwargs):
        kwargs["trace"].update(trace_values)
        return "The fallback provider generated this answer."

    monkeypatch.setattr(routes, "generate_text_sync", generated)
    payload = CeaserChatRequest(
        message="Explain TCP simply",
        original_message="Explain TCP simply",
        source="desktop_companion",
        voice=True,
        request_id="desktop-test",
    )

    result = routes._maybe_desktop_fast_response(payload)
    serialized = CeaserChatResponse.model_validate(result).model_dump()

    assert serialized["response"] == "The fallback provider generated this answer."
    assert serialized["context_summary"]["provider"] == "gemini"
    assert serialized["context_summary"]["fallback_used"] is True
