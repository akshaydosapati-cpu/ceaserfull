import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.services.conversation_service import ConversationService


def test_conversation_titles_capture_intent_without_request_filler() -> None:
    service = ConversationService.__new__(ConversationService)

    assert service.generate_title("Explain quantum computing in simple terms") == "Quantum Computing Simple Terms"
    assert service.generate_title("Create a responsive dental clinic landing page using HTML, CSS and JavaScript") == "Responsive Dental Clinic Landing Page"
    assert service.generate_title("Please check my Google Calendar and show upcoming events") == "Google Calendar Upcoming Events"


def test_conversation_title_is_bounded() -> None:
    service = ConversationService.__new__(ConversationService)
    title = service.generate_title("Tell me about " + "verylongtopic " * 20)

    assert len(title) <= 72
    assert len(title.split()) <= 6
