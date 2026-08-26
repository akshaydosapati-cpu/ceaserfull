from __future__ import annotations

import pytest

from capabilities.registry import build_default_registry
from cloud.backend_client import BackendError, CloudBackendClient
from cloud.capabilities import classify_cloud_action, execute_cloud_command, is_cloud_resource_command
from conversation.executive_cortex import ExecutiveCortex
from core.command_service import CommandService
from core.schemas import CommandRequest
from routing.intent_router import IntentRouter


class FakeResponse:
    def __init__(self, status_code: int, data: dict | None = None) -> None:
        self.status_code = status_code
        self._data = data or {}
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._data


def make_request(text: str) -> CommandRequest:
    return CommandRequest(
        request_id=f"stage18-{abs(hash(text)) % 999999}",
        user_id="user-a",
        session_id="stage18",
        source="typed",
        raw_text=text,
        normalized_text=text,
        context={},
    )


def test_cloud_capabilities_registered_with_confirmation_boundaries():
    registry = build_default_registry()
    assert registry.get("cloud.list").route == "integration"
    assert registry.get("cloud.read").requires_confirmation is False
    assert registry.get("cloud.delete").requires_confirmation is True
    assert registry.get("cloud.update").requires_confirmation is True
    assert registry.get("cloud.delete").risk_level == "high"


def test_executive_cortex_routes_latest_document_to_cloud():
    request = make_request("What is my latest document?")
    decision = ExecutiveCortex().route(request, {}, IntentRouter())
    assert decision.destination == "integration"
    assert decision.intent.capability == "cloud.latest"
    assert decision.intent.entities["provider"] == "ceaser_cloud"


def test_cloud_backend_client_authenticated_request():
    calls = []

    def transport(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return FakeResponse(200, {"message": "Latest report is Launch Plan."})

    client = CloudBackendClient(base_url="https://backend.test", access_token="a" * 30, transport=transport)
    response = client.cloud_resource("latest", {"resource_type": "report"})

    assert response.data["message"] == "Latest report is Launch Plan."
    assert calls[0][0] == "POST"
    assert calls[0][1] == "https://backend.test/desktop/cloud/latest"
    assert calls[0][2]["headers"]["Authorization"] == f"Bearer {'a' * 30}"


def test_cloud_backend_client_requires_authentication():
    client = CloudBackendClient(base_url="https://backend.test", access_token="")
    with pytest.raises(BackendError) as error:
        client.cloud_resource("list", {})
    assert error.value.category == "auth_required"


def test_cloud_backend_client_normalizes_revoked_session():
    def transport(method, url, **kwargs):
        return FakeResponse(403, {})

    client = CloudBackendClient(base_url="https://backend.test", access_token="a" * 30, transport=transport)
    with pytest.raises(BackendError) as error:
        client.cloud_resource("read", {})
    assert error.value.category == "revoked"


def test_cloud_command_executes_through_backend_only():
    def transport(method, url, **kwargs):
        assert "/desktop/cloud/search" in url
        return FakeResponse(200, {"items": [{"name": "Architecture Notes", "type": "document"}]})

    client = CloudBackendClient(base_url="https://backend.test", access_token="a" * 30, transport=transport)
    result = execute_cloud_command("Search my files for architecture", client=client)

    assert result["status"] == "completed"
    assert result["cloud_action"] == "search"
    assert "Architecture Notes" in result["message"]
    assert result["evidence"]["backend_path"] == "/desktop/cloud/search"


def test_cloud_offline_mode_is_graceful():
    def transport(method, url, **kwargs):
        raise TimeoutError("slow")

    client = CloudBackendClient(base_url="https://backend.test", access_token="a" * 30, transport=transport, timeout=0.01)
    result = execute_cloud_command("Read my latest report", client=client)
    assert result["status"] == "offline"
    assert result["error_code"] == "timeout"


def test_delete_requires_confirmation_before_execution():
    executed = []

    service = CommandService(legacy_handler=lambda text: executed.append(text) or {"status": "completed", "message": "deleted"})
    result = service.execute(make_request("Delete my latest report."))

    assert result.status == "needs_confirmation"
    assert result.capability == "cloud.delete"
    assert executed == []


def test_restore_routes_to_cloud_restore():
    assert is_cloud_resource_command("Restore the deleted report")
    assert classify_cloud_action("Restore the deleted report") == "restore"


def test_document_generation_is_not_misrouted_to_cloud_resources():
    assert not is_cloud_resource_command("Prepare a document about eco-friendly batteries")
    assert not is_cloud_resource_command("Write a report about quantum computing")
    assert is_cloud_resource_command("Create a document in CEASER cloud")
