from __future__ import annotations

from pathlib import Path

from awareness.awareness_engine import AwarenessEngine
from awareness.models import AwarenessEvent
from awareness.producers.base import EventProducer
from awareness.producers.clipboard_producer import ClipboardProducer
from awareness.producers.desktop_producer import DesktopProducer
from awareness.producers.filesystem_producer import FilesystemProducer
from awareness.producers.git_producer import GitProducer
from awareness.producers.integration_producer import IntegrationProducer
from awareness.producers.producer_manager import ProducerManager
from awareness.producers.system_producer import SystemProducer
from core.command_service import CommandService


def test_active_window_event_debounce():
    engine = AwarenessEngine()
    producer = DesktopProducer(emit=engine.observe, probe=lambda: {"app": "Code.exe", "title": "CEASER - VS Code"})
    producer.start()

    producer.poll_or_watch({})
    producer.poll_or_watch({})

    events = engine.queue.recent(10)
    assert len([event for event in events if event.type == "active_application_changed"]) == 1
    assert len([event for event in events if event.type == "active_window_changed"]) == 1


def test_clipboard_metadata_only_privacy():
    engine = AwarenessEngine()
    producer = ClipboardProducer(emit=engine.observe, probe=lambda: {"content_type": "text", "approx_size": 32, "item_count": 1, "text": "secret clipboard"})
    producer.start()

    producer.poll_or_watch({})

    payload = engine.queue.recent(1)[0].payload
    assert payload == {"content_type": "text", "approx_size": 32, "item_count": 1}
    assert "secret clipboard" not in str(payload)


def test_downloads_file_completion(tmp_path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    engine = AwarenessEngine()
    producer = FilesystemProducer(emit=engine.observe, watched_folders=[str(downloads)])
    producer.start()
    producer.poll_or_watch({})

    file_path = downloads / "ceaser-installer.exe"
    file_path.write_text("ok", encoding="utf-8")

    producer.poll_or_watch({})

    assert engine.queue.recent(1)[0].type == "download_completed"


def test_temporary_download_suppression(tmp_path):
    temp_file = tmp_path / "video.mp4.crdownload"
    temp_file.write_text("partial", encoding="utf-8")
    engine = AwarenessEngine()
    producer = FilesystemProducer(emit=engine.observe, watched_folders=[str(tmp_path)])
    producer.start()

    producer.poll_or_watch({})

    assert engine.queue.recent(10) == []


def test_battery_low_threshold():
    states = [{"network_connected": True, "battery_percent": 18, "battery_charging": False, "disk_free_percent": 50}]
    engine = AwarenessEngine()
    producer = SystemProducer(emit=engine.observe, probe=lambda: states[0])
    producer.start()

    producer.poll_or_watch({})

    assert engine.queue.recent(1)[0].type == "battery_low"


def test_network_disconnect_reconnect():
    states = [
        {"network_connected": True, "battery_percent": 80, "battery_charging": True, "disk_free_percent": 50},
        {"network_connected": False, "battery_percent": 80, "battery_charging": True, "disk_free_percent": 50},
        {"network_connected": True, "battery_percent": 80, "battery_charging": True, "disk_free_percent": 50},
    ]
    index = {"i": 0}
    engine = AwarenessEngine()
    producer = SystemProducer(emit=engine.observe, probe=lambda: states[index["i"]])
    producer.start()

    producer.poll_or_watch({})
    index["i"] = 1
    producer.poll_or_watch({})
    index["i"] = 2
    producer.poll_or_watch({})

    types = [event.type for event in engine.queue.recent(10)]
    assert "network_down" in types
    assert "network_changed" in types


def test_git_branch_change(tmp_path):
    states = [{"branch": "main", "dirty": False, "commit": "a" * 40}, {"branch": "feature", "dirty": False, "commit": "a" * 40}]
    index = {"i": 0}
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir(exist_ok=True)
    producer = GitProducer(repo_path=str(repo), status_probe=lambda _repo: states[index["i"]])
    engine = AwarenessEngine()
    producer.emit = engine.observe
    producer.start()

    producer.poll_or_watch({})
    index["i"] = 1
    producer.poll_or_watch({})

    assert engine.queue.recent(1)[0].type == "git_branch_changed"


def test_git_dirty_state_deduplication(tmp_path):
    state = {"branch": "main", "dirty": True, "commit": "a" * 40}
    engine = AwarenessEngine()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir(exist_ok=True)
    producer = GitProducer(emit=engine.observe, repo_path=str(repo), status_probe=lambda _repo: state)
    producer.start()

    producer.poll_or_watch({})
    producer._last_dirty = False
    producer.poll_or_watch({})
    producer.poll_or_watch({})

    assert len([event for event in engine.queue.recent(10) if event.type == "git_dirty_state_changed"]) == 1


def test_integration_sync_failure_event():
    statuses = [{"provider": "github", "status": "failed", "summary": "GitHub sync failed.", "error": "timeout"}]
    engine = AwarenessEngine()
    producer = IntegrationProducer(emit=engine.observe, status_probe=lambda: statuses)
    producer.start()

    producer.poll_or_watch({})

    event = engine.queue.recent(1)[0]
    assert event.type == "github_sync_failed"
    assert "token" not in str(event.payload).lower()


class FailingProducer(EventProducer):
    name = "failing"

    def normalize_event(self, raw):
        return None

    def _poll(self, context):
        raise RuntimeError("boom")


def test_producer_failure_recovery():
    engine = AwarenessEngine()
    manager = ProducerManager(engine, [FailingProducer()])
    manager.start()

    manager.poll_once({})

    health = manager.health()
    assert health["restarts"]["failing"] == 1
    assert manager.producers["failing"].running is True


def test_duplicate_suppression_for_same_event():
    engine = AwarenessEngine()
    event = engine.factory.system("battery_low", "Battery low", "Battery is at 18%.", {"battery_percent": 18})
    same = event.model_copy(update={"id": "evt_second"}) if hasattr(event, "model_copy") else event.copy(update={"id": "evt_second"})

    engine.observe(event)
    engine.observe(same)

    assert len(engine.queue.recent(10)) == 1


def test_producer_clean_shutdown():
    engine = AwarenessEngine()
    manager = ProducerManager(engine, [DesktopProducer()])

    manager.start()
    manager.stop()

    assert manager.started is False
    assert all(not producer.running for producer in manager.producers.values())


def test_privacy_field_rejection_from_payload():
    seen: list[AwarenessEvent] = []
    producer = ClipboardProducer(emit=seen.append, probe=lambda: {"content_type": "text", "approx_size": 10, "token": "abc", "clipboard_text": "secret"})
    producer.start()

    producer.poll_or_watch({})

    assert "token" not in seen[0].payload
    assert "clipboard_text" not in seen[0].payload


def test_low_idle_overhead_configuration():
    engine = AwarenessEngine()
    manager = ProducerManager(engine, [DesktopProducer(), SystemProducer(), GitProducer(), IntegrationProducer()])
    manager.start()

    overhead = manager.health()["estimated_idle_polling"]

    assert overhead["polls_per_minute"] < 120
    assert "under 1-2%" in overhead["cpu_target"]


def test_notification_cards_are_safe_for_ipc():
    service = CommandService(lambda text: {"status": "completed", "message": text, "verified": True})
    service.observe_event(service.awareness_engine.factory.development("build_failed", "Build failed", "Validation failed.", {"failed": True, "token": "hidden"}))

    ipc = service.awareness_ipc_events()[0]

    assert ipc.event == "ceaser:awareness-card"
    assert "token" not in str(ipc.payload).lower()
    assert {"event_id", "category", "title", "short_message", "importance", "timestamp", "suggested_action_label"} <= set(ipc.payload)
