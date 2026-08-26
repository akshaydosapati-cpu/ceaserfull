from __future__ import annotations

import pytest

from core.command_service import CommandService
from core.schemas import CommandRequest
from voice.state_machine import ConversationalVoiceController, VoiceStateMachine


class Clock:
    def __init__(self) -> None:
        self.value = 1000.0

    def now(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def request(text: str, *, session: str = "voice16") -> CommandRequest:
    return CommandRequest(
        request_id=f"voice16-{abs(hash((text, session))) % 999999}",
        session_id=session,
        source="voice",
        raw_text=text,
        normalized_text=text,
    )


def test_stop_during_tts_interrupts_and_returns_to_follow_up_listening():
    clock = Clock()
    controller = ConversationalVoiceController(now=clock.now)
    controller.begin_speaking("Long answer on screen.", "Short answer.")

    result = controller.interrupt("stop")

    assert result["status"] == "cancelled"
    assert controller.tts_playing is False
    assert controller.state == "FOLLOW_UP_LISTENING"
    assert controller.should_accept_without_wake() is True


def test_new_command_does_not_overlap_tts_and_capture():
    controller = ConversationalVoiceController()
    controller.begin_speaking("Overlay", "Spoken")

    assert controller.begin_capture() is False
    interrupted = controller.interrupt("open chrome")

    assert interrupted["voice_control"] == "interrupt"
    assert controller.begin_capture() is True


def test_follow_up_without_wake_word_is_accepted_inside_window():
    clock = Clock()
    controller = ConversationalVoiceController(now=clock.now)
    controller.record_execution("explain ramayana", {"message": "Ramayana summary.", "spoken_response": "Ramayana summary."})

    assert controller.should_accept_without_wake() is True
    assert controller.state == "FOLLOW_UP_LISTENING"


def test_follow_up_expiry_returns_to_idle_when_wake_is_disabled():
    clock = Clock()
    controller = ConversationalVoiceController(now=clock.now, follow_up_seconds=30)
    controller.open_follow_up_window()

    clock.advance(31)

    assert controller.should_accept_without_wake() is False
    assert controller.state == "IDLE"


def test_mid_course_correction_replaces_command_safely():
    controller = ConversationalVoiceController()
    controller.mark_pending("open Chrome")

    command, corrected = controller.normalize_correction("no, open CliniLocker instead")

    assert corrected is True
    assert command == "open CliniLocker"


def test_no_duplicate_execution_for_correction_recording():
    controller = ConversationalVoiceController()
    command, corrected = controller.normalize_correction("actually open Notion instead")
    response = controller.record_execution(command, {"message": "Opened Notion.", "spoken_response": "Opened Notion."})

    assert corrected is True
    assert response["message"] == "Opened Notion."
    assert controller.execution_count == 1


def test_repeat_last_response():
    controller = ConversationalVoiceController()
    controller.record_execution("explain this", {"message": "Detailed answer on screen.", "spoken_response": "Short answer."})

    result = controller.handle_control("say that again")

    assert result
    assert result["status"] == "completed"
    assert result["message"] == "Detailed answer on screen."
    assert result["spoken_response"] == "Short answer."


def test_cancel_pending_workflow():
    controller = ConversationalVoiceController()
    controller.mark_pending("save report to Notion")

    result = controller.handle_control("never mind")

    assert result
    assert result["status"] == "cancelled"
    assert controller.pending_command == ""


def test_self_trigger_prevention_blocks_capture_while_speaking():
    controller = ConversationalVoiceController()
    controller.begin_speaking("CEASER is speaking.", "CEASER is speaking.")

    assert controller.tts_playing is True
    assert controller.begin_capture() is False


def test_voice_state_machine_returns_to_wake_listening_after_follow_up():
    machine = VoiceStateMachine("stage16")
    machine.transition("STARTING")
    machine.transition("WAKE_LISTENING")
    machine.transition("WAKE_DETECTED")
    machine.transition("COMMAND_LISTENING")
    machine.transition("TRANSCRIBING")
    machine.transition("ROUTING")
    machine.transition("EXECUTING")
    machine.transition("SPEAKING")
    machine.transition("FOLLOW_UP_LISTENING")
    machine.transition("WAKE_LISTENING")

    assert machine.state == "WAKE_LISTENING"


def test_spoken_response_shorter_than_overlay_from_command_service():
    service = CommandService(lambda _text: {"status": "completed", "message": "Quantum computing uses qubits to represent information. It can explore many possibilities for certain problems. This longer overlay text stays available on screen.", "verified": True})

    result = service.execute(request("use simple language and explain quantum computing"))

    assert result.spoken_response
    assert len(result.spoken_response) < len(result.summary)
    assert result.status == "completed"
    assert result.verified is True


def test_invalid_overlap_transition_is_rejected():
    machine = VoiceStateMachine("stage16-invalid")
    machine.transition("STARTING")
    machine.transition("WAKE_LISTENING")
    with pytest.raises(ValueError):
        machine.transition("SPEAKING")
