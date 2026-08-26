from conversation.response_composer import ResponseComposer
from routing.intent_router import IntentRouter


def test_verb_last_application_command_routes_and_normalizes():
    router = IntentRouter()

    for command in ("Chrome open", "Calculator launch please"):
        intent = router.resolve(command)
        assert intent.capability == "app.open"
        assert intent.route == "desktop"
        assert ResponseComposer().command_for_execution(command, intent, {}) == f"open {intent.entities['target']}"
