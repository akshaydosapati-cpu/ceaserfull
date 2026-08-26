# CEASER Desktop Brain v2

This document freezes the Desktop Companion architecture before the next implementation pass. It is the binding blueprint for future desktop changes.

The goal is not to rewrite the companion. The goal is to make every typed and spoken command pass through one Python-owned command and execution architecture.

## Final Ownership

```text
Electron - CEASER Face
Window, overlay, tray, hotkey, auth handoff, updates, animations,
input UI, confirmations, and audio playback.

        JSON IPC

Python - CEASER Desktop Brain
Voice, sessions, context, intent, planning, capabilities,
local actions, verification, TTS decisions, backend bridge.

        Authenticated HTTPS

CEASER Backend - Cloud Brain
User account, memory, projects, RAG, LLM, integrations,
GitHub, Notion, files, and cloud workflows.
```

Electron must not be a second command brain. Python owns command interpretation and execution. Backend owns cloud intelligence and user data.

## TTS Ownership

"Python owns TTS" means:

- Python decides what should be spoken.
- Python creates or requests audio.
- Python controls interruption, queueing, speaking state, and long-response shortening.
- Electron only plays provided audio and reports playback lifecycle events.

For the first migration, Electron browser `speechSynthesis` may remain behind a single audio adapter. It must not decide conversational state or choose what to speak.

## One Intent Schema

Create:

```text
python_companion/core/schemas.py
```

Every typed or spoken command must become the same object.

```python
from typing import Any, Literal
from pydantic import BaseModel, Field

CommandSource = Literal[
    "voice",
    "typed",
    "hotkey",
    "overlay",
    "automation",
    "integration",
]

class CommandRequest(BaseModel):
    request_id: str
    user_id: str
    session_id: str
    source: CommandSource
    raw_text: str
    normalized_text: str
    context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

class IntentResult(BaseModel):
    intent: str
    capability: str | None = None
    confidence: float
    entities: dict[str, Any] = Field(default_factory=dict)
    route: Literal[
        "desktop",
        "backend_ai",
        "integration",
        "workflow",
        "conversation",
        "unsupported",
    ]
    requires_clarification: bool = False
    clarification_question: str | None = None

class ActionResult(BaseModel):
    status: Literal[
        "completed",
        "failed",
        "partial",
        "needs_input",
        "needs_confirmation",
        "cancelled",
    ]
    capability: str | None = None
    summary: str
    spoken_response: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    verified: bool = False
    retryable: bool = False
    error_code: str | None = None
    confirmation: dict[str, Any] | None = None
```

CEASER may say "done" only when:

```text
status = completed
verified = true
```

## One Python Command Service

Create:

```text
python_companion/core/command_service.py
```

This becomes the only command entry point.

```python
class CommandService:
    async def execute(self, request: CommandRequest) -> ActionResult:
        context = await self.context_resolver.resolve(request)
        intent = await self.intent_router.resolve(request, context)

        if intent.requires_clarification:
            return ActionResult(
                status="needs_input",
                summary=intent.clarification_question or "I need a little more information.",
                spoken_response=intent.clarification_question,
                verified=True,
            )

        if intent.route == "workflow":
            return await self.workflow_runner.run(request, intent, context)

        return await self.execution_engine.execute(request, intent, context)
```

Both paths must call this:

```text
Voice -> STT -> CommandService.execute()
Typed input -> CommandService.execute()
```

Electron renderer must stop routing typed commands through its own action router once this service is connected.

## Capability Registry

Create:

```text
python_companion/capabilities/registry.py
```

Each capability has:

```python
class CapabilityDefinition(BaseModel):
    name: str
    description: str
    handler: str
    route: str
    risk_level: Literal["low", "medium", "high", "blocked"]
    requires_confirmation: bool = False
    requires_internet: bool = False
    required_permissions: list[str] = Field(default_factory=list)
    input_schema: dict = Field(default_factory=dict)
    timeout_seconds: int = 20
```

Initial desktop capabilities:

```text
desktop.open_application
desktop.close_application
desktop.open_folder
desktop.open_file
desktop.find_file
desktop.open_url
desktop.close_browser_tab
desktop.search_web
desktop.set_volume
desktop.change_volume
desktop.media_play_pause
desktop.media_next
desktop.take_screenshot
desktop.read_clipboard
desktop.write_clipboard
desktop.get_system_status
desktop.refresh_application_index
desktop.describe_screen
desktop.analyze_dropped_file
```

Backend-backed capabilities:

```text
ai.answer
ai.continue_conversation
ai.summarize_document
ai.explain_content
github.list_repositories
github.get_readme
github.list_commits
github.list_issues
github.list_pull_requests
github.summarize_repository
notion.search_pages
notion.get_page
notion.list_tasks
notion.create_page
notion.append_blocks
```

## Intent Router

Create:

```text
python_companion/routing/intent_router.py
```

Do not send everything to the LLM. Use layered routing:

```text
1. Cancellation and control
2. Deterministic desktop actions
3. Contextual/reference actions
4. Integration capabilities
5. Workflow planning
6. Backend AI
7. Unsupported response
```

Examples:

- Deterministic: open Chrome, close Calculator, open Downloads, take screenshot, set volume to 50%.
- Contextual: open it, close that, explain this, save it, continue, repeat that.
- Integration: show repositories, show CliniLocker commits, find Notion notes, save this to Notion.
- Workflow: prepare me for my viva, summarize development progress, organize study material.
- General AI: explain quantum computing, write an email, help think through a decision.

The broad fallback chain must be retired.

## Voice Engine Contract

Python voice collection and command execution must be separate.

```text
Wake engine
-> command recording
-> STT
-> CommandRequest
-> CommandService
```

Recommended modules:

```text
python_companion/voice/microphone.py
python_companion/voice/wakeword.py
python_companion/voice/recorder.py
python_companion/voice/vad.py
python_companion/voice/stt.py
python_companion/voice/state_machine.py
python_companion/voice/tts_controller.py
python_companion/voice/watchdog.py
```

Voice state machine:

```text
STARTING
-> WAKE_LISTENING
-> COMMAND_LISTENING
-> TRANSCRIBING
-> ROUTING
-> EXECUTING
-> SPEAKING
-> FOLLOW_UP_LISTENING
-> WAKE_LISTENING
```

Failure path:

```text
Any state -> RECOVERING -> WAKE_LISTENING
```

Each transition sends an event to Electron:

```json
{
  "type": "voice_state",
  "state": "TRANSCRIBING",
  "session_id": "voice_123",
  "timestamp": "..."
}
```

Production wake-word target:

```text
Persistent PCM microphone
-> Porcupine model
-> wake detected
-> command capture
-> STT
```

Transcript matching may remain only as an explicitly named fallback:

```text
CEASER_WAKE_MODE=porcupine
CEASER_WAKE_FALLBACK=transcript
```

Never label transcript matching as local wake-word detection.

## Backend Bridge

Create:

```text
python_companion/backend/client.py
```

This client owns:

- Authentication headers
- Token refresh coordination
- Timeouts
- Retry policy
- Backend availability
- Normalized error handling
- Integration calls
- Memory calls
- Chat calls

Individual feature modules must not construct random backend HTTP requests.

Suggested interface:

```python
class CeaserBackendClient:
    async def chat(self, payload: dict) -> dict: ...
    async def execute_capability(self, capability: str, arguments: dict, context: dict) -> dict: ...
    async def get_user_context(self) -> dict: ...
    async def update_memory(self, payload: dict) -> dict: ...
    async def get_integrations(self) -> dict: ...
```

Long-term backend endpoint:

```http
POST /capabilities/execute
```

Until that backend endpoint exists, the client can wrap existing chat and integration routes. The rest of Python must not know it is using a temporary adapter.

## Session and Context

Create:

```text
python_companion/conversation/session_manager.py
python_companion/conversation/context_resolver.py
python_companion/conversation/reference_resolver.py
python_companion/conversation/response_composer.py
```

Session state:

```json
{
  "session_id": "voice_123",
  "user_id": "...",
  "mode": "build",
  "active": true,
  "active_project": "CEASER",
  "active_resource": {
    "type": "file",
    "path": "python_companion/desktop_voice_server.py"
  },
  "last_intent": "open_file",
  "last_result": {},
  "pending_confirmation": null,
  "recent_turns": [],
  "expires_at": "..."
}
```

Context snapshot:

```json
{
  "foreground_app": "Visual Studio Code",
  "window_title": "desktop_voice_server.py - CEASER",
  "current_folder": "C:\\...\\ceaser\\desktop",
  "active_file": "python_companion/desktop_voice_server.py",
  "clipboard_available": true,
  "active_repository": "CEASER",
  "recent_notion_page": null
}
```

The context resolver gathers lightweight metadata by default. It must not continuously capture the screen or read private files without a direct user request.

## Planner and Workflow Runner

Create later:

```text
python_companion/planning/task_planner.py
python_companion/planning/workflow_runner.py
python_companion/planning/confirmation_manager.py
```

Rules:

- Maximum six steps.
- No recursive agent loops.
- One retry per step.
- Explicit cancellation.
- Confirm external writes.
- Verify successful actions.
- Return partial results when one step fails.

## IPC v2 Protocol

The current child-process stdin/stdout transport is acceptable. The issue is the message contract.

Keep:

```text
Electron child_process <-> Python stdin/stdout JSON
```

Electron to Python:

```json
{
  "version": "2.0",
  "id": "req_123",
  "type": "execute_command",
  "payload": {
    "source": "typed",
    "text": "open Chrome",
    "session_id": "session_123"
  }
}
```

```json
{
  "version": "2.0",
  "id": "req_124",
  "type": "start_voice_session",
  "payload": {
    "activation": "hotkey"
  }
}
```

```json
{
  "version": "2.0",
  "id": "req_125",
  "type": "confirmation_response",
  "payload": {
    "confirmation_id": "confirm_123",
    "approved": true
  }
}
```

Python to Electron:

```json
{
  "version": "2.0",
  "type": "event",
  "event": "voice_state",
  "payload": {
    "state": "LISTENING"
  }
}
```

```json
{
  "version": "2.0",
  "type": "event",
  "event": "workflow_progress",
  "payload": {
    "label": "Reading GitHub repository",
    "current": 2,
    "total": 4
  }
}
```

```json
{
  "version": "2.0",
  "type": "event",
  "event": "result",
  "payload": {
    "status": "completed",
    "summary": "Chrome opened.",
    "spoken_response": "Chrome is open.",
    "verified": true
  }
}
```

Keep `CEASER_JSON` framing temporarily if the parser depends on it.

## Security Boundary

Before any action:

```text
Intent
-> capability selected
-> permission check
-> risk classification
-> confirmation when required
-> execution
-> verification
-> audit record
```

Initial risk rules:

| Action | Risk | Confirmation |
| --- | ---: | --- |
| Open app | Low | No |
| Read page or file | Low | No, when explicitly requested |
| Create Notion page | Medium | Yes initially |
| Modify file | Medium | Yes |
| Create GitHub issue | Medium | Yes |
| Push code | High | Yes |
| Delete files | High | Yes |
| Run admin command | High | Strong confirmation |
| Reveal secrets | Blocked | Never |

Hard security rules must not be overridable by the LLM.

## Existing File Migration Matrix

### Keep

```text
src/main/main.js
src/main/preload.js
src/renderer/app.js
src/renderer/index.html
src/renderer/styles.css
src/services/app-launcher.js
src/services/system-actions.js
src/services/media-actions.js
src/services/screenshot.js
src/services/file-actions.js
src/services/clipboard.js
src/services/window-context.js
python_companion/desktop_voice_server.py
python_companion/structured_command.py
python_companion/intent_client.py
python_companion/features/ceaser/
```

"Keep" means the useful implementation remains, not that the files stay unchanged forever.

### Wrap

These become handlers behind Python capabilities:

```text
app-launcher.js
system-actions.js
media-actions.js
vision-actions.js
file-actions.js
clipboard.js
window-context.js
Python system handlers
Python file handlers
Python screenshot handlers
Python music handlers
Python backend handlers
```

Electron-side execution modules may remain as temporary native adapters, called by Python through IPC. They must not remain decision-making routers.

### Reduce

```text
python_companion/desktop_voice_server.py
python_companion/voice_assistant_main.py
```

`desktop_voice_server.py` should eventually contain only:

- Process startup
- JSON transport loop
- Dependency initialization
- Dispatch into `CommandService`
- Event output
- Graceful shutdown

`voice_assistant_main.py` must stop being the place where unrelated capabilities, routing, memory, and execution all meet.

### Retire from Active Use

```text
src/actions/actionRouter.js
src/actions/actionExecutor.js
src/controllers/command-router.js
```

They may remain temporarily for compatibility, but typed input must stop using them once Python `CommandService` is connected.

### Remove After Migration

```text
Old Electron voice/STT methods
Browser MediaRecorder paths
Electron Deepgram transcription paths
JS wake transcript gate
Old passive voice loop
Duplicate JS action routing
Legacy local database modules that conflict with backend/Supabase truth
Unused Python speaking paths
```

Delete only after tests prove there are no active callers.

## Migration Sequence

1. Add contracts without changing behavior:
   - `CommandRequest`
   - `IntentResult`
   - `ActionResult`
   - `CapabilityDefinition`
   - IPC v2 message models
   - Wrap existing outputs into `ActionResult`

2. Add `CommandService`:
   - Route typed commands through it first.
   - Test open app, open folder, screenshot, volume, general AI.

3. Move voice into the same service:
   - `transcript -> CommandRequest -> CommandService`
   - Delete voice-only routing decisions.

4. Register existing actions:
   - Wrap working Python handlers as capabilities.
   - Do not rewrite internals yet.

5. Retire Electron routing:
   - Remove active use of JS action routers.
   - Keep only native IPC helpers where necessary.

6. Split `voice_assistant_main.py` incrementally:
   - voice
   - routing
   - capabilities
   - backend client
   - conversation
   - security

7. Add sessions and context only after simple command execution is stable.

8. Add workflows, memory, and world model above capabilities.

## Next Implementation Pass

Use this bounded task next:

```text
We are implementing CEASER Desktop Brain v2 without rewriting working features.

Current architecture:
- Electron owns UI, overlay, tray, hotkey, auth handoff and Python process lifecycle.
- Python owns active voice, command execution and backend calls.
- Electron and Python communicate through child-process stdin/stdout JSON.
- Two command routers still exist.
- Electron TTS remains active.
- Python legacy assistant code is too large.

Task:
Create the shared Desktop Brain v2 contracts and command entry point.

Implement:
1. CommandRequest
2. IntentResult
3. ActionResult
4. CapabilityDefinition
5. CommandService
6. A minimal CapabilityRegistry

Requirements:
- Voice and typed input must eventually use the same CommandService.
- In this pass, connect typed input first while preserving existing behavior.
- Wrap existing working desktop handlers; do not rewrite them.
- Do not change backend API contracts.
- Do not change GitHub or Notion OAuth.
- Do not modify Electron microphone/STT code because it is already removed from the active path.
- Preserve current Python stdin/stdout IPC compatibility.
- Add structured logging with request_id, source, intent, capability, status and verified.
- Add unit tests for open application, open folder, screenshot, system volume, backend AI fallback, and unsupported command.
- Show all changed files and test results.
- Do not remove legacy routing yet; mark it as compatibility fallback and trace when it is used.
```

After that passes, route voice through the same `CommandService`.

## Frozen Phase 1 Decisions

```text
Electron is the face.
Python is the desktop brain.
Backend is the cloud brain.

One command schema.
One Python command service.
One intent router.
One capability registry.
One execution-result contract.
One TTS controller.
One backend client.
One security gate.
```

Everything already built must be kept, wrapped, reduced, retired, or removed after migration. Nothing should remain as an invisible parallel execution path.
