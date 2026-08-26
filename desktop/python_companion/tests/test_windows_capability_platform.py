from capabilities.registry import build_default_registry
from capabilities.windows_runtime import WindowsCapabilityRuntime
from core.command_service import CommandService
from core.schemas import CommandRequest
from routing.intent_router import IntentRouter


def test_registry_has_authoritative_metadata_and_truthful_discovery(monkeypatch):
    registry = build_default_registry()
    runtime = WindowsCapabilityRuntime(lambda text: {"status": "completed", "message": text, "verified": True})
    assert len(registry.all()) >= 150
    shutdown = registry.get("system.shutdown")
    assert shutdown and shutdown.requires_confirmation and shutdown.risk_level == "high"
    assert shutdown.remote_execution_allowed
    monkeypatch.setattr(runtime, "available", lambda name: (name == "app.open", "unsupported" if name != "app.open" else ""))
    status = {item["capability_id"]: item for item in registry.discovery(runtime)}
    assert status["app.open"]["status"] == "available"
    assert status["airplane.enable"]["status"] == "unsupported"


def test_natural_language_routes_to_structured_capabilities():
    router = IntentRouter()
    assert router.resolve("Open Chrome").capability == "app.open"
    assert router.resolve("Maximize VS Code").capability == "window.maximize"
    assert router.resolve("Set volume to 20%").capability == "audio.volume.set"
    assert router.resolve("Take a screenshot").capability == "screen.capture_all"
    assert router.resolve("Show which apps are running").capability == "app.list_running"


def test_structured_runtime_executes_without_model_shell(monkeypatch):
    calls = []
    service = CommandService(lambda text: calls.append(text) or {"status": "completed", "message": "Chrome opened.", "verified": True})
    result = service.execute(CommandRequest(request_id="win-1", session_id="s", user_id="u", source="typed", raw_text="Open Chrome", normalized_text="Open Chrome"))
    assert result.capability == "app.open"
    assert result.status == "completed"
    assert calls == ["open Chrome"]


def test_high_risk_power_action_requires_confirmation():
    service = CommandService(lambda _text: {"status": "completed", "message": "should not execute", "verified": True})
    result = service.execute(CommandRequest(request_id="win-2", session_id="s", user_id="u", source="typed", raw_text="Shutdown my computer", normalized_text="Shutdown my computer"))
    assert result.status in {"needs_confirmation", "needs_input"}


def test_unimplemented_hardware_capability_is_not_advertised():
    runtime = WindowsCapabilityRuntime(lambda _text: {})
    available, reason = runtime.available("airplane.enable")
    assert not available and "no production handler" in reason


def test_final_closure_contracts(monkeypatch):
    registry = build_default_registry()
    runtime = WindowsCapabilityRuntime(lambda _text: {"status": "completed", "verified": True})
    assert registry.get("window.fullscreen")
    assert registry.get("printer.print_file").requires_confirmation
    assert not registry.get("input.type_text").remote_execution_allowed
    assert {"screen.capture_monitor", "screen.capture_active_window", "screen.capture_region"} <= runtime.implemented
    assert {"wifi.enable", "wifi.disable", "display.list", "input.hotkey", "storage.drives"} <= runtime.implemented
    monitors = runtime._monitors()
    assert monitors and monitors[0]["primary"] and monitors[0]["width"] > 0
    monkeypatch.setattr(runtime, "available", lambda name: (False, "No reliable Windows API") if name.startswith("airplane.") else (True, ""))
    discovery = {item["capability_id"]: item for item in registry.discovery(runtime)}
    assert discovery["airplane.enable"]["status"] == "unsupported"
