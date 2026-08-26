from __future__ import annotations

import threading

from awareness.awareness_engine import AwarenessEngine
from awareness.event_sources import EventFactory
from awareness.producers.filesystem_producer import FilesystemProducer
from conversation.companion_models import CompanionPreferences
from conversation.companion_personality import CompanionPersonalityEngine
from conversation.language_analyzer import LanguageAnalyzer
from conversation.proactive_conversation import ProactiveConversationEngine
from conversation.proactive_runtime import ProactiveRuntimeAdapter
from features.ceaser.proactive import ProactiveAssistant
from long_term_memory.memory_manager import LongTermMemoryManager
from long_term_memory.memory_store import LocalJsonMemoryStore


def test_trusted_event_delivery_and_cooldown_suppression():
    delivered = []
    personality = CompanionPersonalityEngine(lambda _instructions, _payload: "The CEASER build finished successfully.")
    adapter = ProactiveRuntimeAdapter(ProactiveConversationEngine(cooldown_seconds=60), personality, lambda _context: CompanionPreferences(proactive_mode="companion"))
    adapter.configure(delivery=delivered.append, user_id_provider=lambda: "user-a", context_provider=lambda: {})
    awareness = AwarenessEngine()
    awareness.subscribe(adapter.receive)
    factory = EventFactory()
    event = factory.development("build_completed", "Build completed", "The verified build completed.", {"confidence": 1.0})
    event.importance = 0.9
    first = adapter.receive(event, awareness.decisions.decide(event, {}))
    second = adapter.receive(event, awareness.decisions.decide(event, {}))
    assert first["delivered"] is True and delivered[0]["verified"] is True
    assert second == {"delivered": False, "reason": "cooldown"}


def test_untrusted_event_never_delivers():
    adapter = ProactiveRuntimeAdapter(ProactiveConversationEngine(), CompanionPersonalityEngine(), lambda _context: CompanionPreferences(proactive_mode="companion"))
    adapter.configure(delivery=lambda _payload: (_ for _ in ()).throw(AssertionError("must not deliver")), user_id_provider=lambda: "user-a")
    event = EventFactory().system("model_invented", "Invented", "Not authoritative.")
    assert adapter.receive(event, AwarenessEngine().decisions.decide(event, {}))["reason"] == "untrusted_trigger"


def test_preferences_persist_reload_and_isolate_users(tmp_path):
    store = LocalJsonMemoryStore(tmp_path / "memory.json")
    manager = LongTermMemoryManager(store)
    manager.save_companion_preferences("user-a", {"humor": "high", "proactive_mode": "companion", "language": "Telugu"})
    reloaded = LongTermMemoryManager(LocalJsonMemoryStore(tmp_path / "memory.json"))
    assert reloaded.companion_preferences("user-a")["language"] == "Telugu"
    assert reloaded.companion_preferences("user-b") == {}


def test_provider_language_beats_latin_script_guess_and_preserves_code_switch():
    analysis = LanguageAnalyzer().analyze_provider("Chrome open cheyyi", "te-IN", CompanionPreferences())
    assert analysis.primary_language == "Telugu"
    assert "English" in analysis.secondary_languages
    assert analysis.code_switched is True


def test_filesystem_first_poll_is_baseline_not_download_event(tmp_path):
    file_path = tmp_path / "existing.pdf"
    file_path.write_bytes(b"existing")
    producer = FilesystemProducer(watched_folders=[str(tmp_path)])
    producer.start()
    assert producer.poll_or_watch({}) == []
    new_path = tmp_path / "new.pdf"
    new_path.write_bytes(b"new")
    assert len(producer.poll_or_watch({})) == 1


def test_legacy_store_workers_disabled_and_writes_serialized(tmp_path):
    assistant = ProactiveAssistant(db_path=str(tmp_path / "proactive.db"), user_id="user-a", start_workers=False)
    assert assistant.monitor_thread is None and assistant.learning_thread is None
    threads = [threading.Thread(target=assistant.create_suggestion, args=(f"test-{index}", {"index": index})) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(assistant.get_suggestions(limit=20)) == 8
    assistant.close()
