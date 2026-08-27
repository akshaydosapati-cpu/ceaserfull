# CEASER Desktop Companion

CEASER Desktop Companion is the Windows execution and voice surface for CEASER. It combines an Electron overlay with a packaged Python runtime so users can speak or type commands, control their computer, and continue AI conversations without keeping the web console in focus.

## What It Does

- Opens, focuses, switches, minimizes, maximizes, and closes Windows applications.
- Opens common folders, explicit files, File Explorer locations, and Recycle Bin.
- Controls browser tabs and navigation across supported browsers.
- Handles media play, pause, resume, stop, seek, next, previous, and volume controls.
- Captures screenshots, reads the clipboard, and accepts explicit drag-and-drop file context.
- Executes local capabilities without sending obvious desktop commands through the AI path.
- Routes conversational and knowledge requests to the authenticated CEASER backend.
- Supports voice transcription, spoken responses, follow-up listening, and interruption controls.
- Connects to the user's web-console account and authenticated device gateway.
- Shows live runtime diagnostics and writes safe local logs for troubleshooting.
- Receives authorized device capability requests from CEASER Brain and returns correlated results.

## Runtime Architecture

```text
Keyboard hotkey / typed input / drag and drop / device request
                              |
                              v
                    Electron main process
                  src/main/main.js
                 /         |          \
                v          v           v
        Overlay renderer  Auth/link  Device Gateway
                |          |           |
                +----------+-----------+
                           |
                           v
                 Packaged Python companion
             desktop_voice_server.py (JSON IPC)
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
     Voice/STT       Command routing   Working context
          |                |                |
          +--------+-------+----------------+
                   |
          +--------+-------------------+
          |                            |
          v                            v
 Local Windows capabilities      CEASER backend AI
          |                            |
          +-------------+--------------+
                        v
             Result, overlay, and TTS
```

## Main Components

### Electron Host

`desktop/src/main/main.js` owns the Windows application lifecycle, global hotkey, overlay window, tray behavior, account linking, Python child process, request correlation, runtime recovery, logging, and device-gateway connection.

### Overlay Renderer

`desktop/src/renderer` displays the compact capsule and expanded response surfaces. It reflects listening, transcribing, routing, executing, speaking, completion, recovery, and attention states. The renderer communicates through the preload bridge rather than direct Node access.

### Python Companion

`desktop/python_companion/desktop_voice_server.py` is the IPC entry point. It receives JSON requests from Electron, maintains voice-session state, routes local commands, invokes registered capabilities, calls backend AI when needed, and emits structured status and result events.

### Voice Pipeline

```text
Hotkey
  -> microphone capture
  -> speech activity/silence detection
  -> configured STT provider and fallback
  -> normalized transcript
  -> shared command router
  -> local action or backend AI
  -> concise spoken response
  -> follow-up listening when applicable
```

Voice configuration is prepared through `desktop/scripts/prepare-runtime-env.mjs`. API keys and tokens are never printed by safe diagnostics.

### Local Command Path

Deterministic commands use the local capability and routing layers under `desktop/python_companion/capabilities`, `routing`, and `core`. Local execution is preferred for application control, media keys, browser/tab operations, files, clipboard, screenshots, and Windows controls. This keeps common commands fast and available without unnecessary model usage.

### Backend AI Path

Requests requiring explanation, generation, cloud memory, connected resources, or model reasoning use the configured CEASER backend. The current user session is forwarded from Electron to the Python process. Authentication failures are reported as account-linking states rather than disguised as desktop-command failures.

### Device Gateway

`desktop/src/services/device-gateway-client.js` maintains the authenticated realtime connection between CEASER Brain and the correct user's device. It advertises supported capabilities, correlates requests and results, reconnects safely, refreshes authentication, and stops accepting commands when the device is revoked.

## State And Context

The companion maintains bounded working context for recent commands, active applications/resources, pending confirmations, follow-up references, and suggested actions. Durable cloud memory remains owned by the backend. Raw secrets, unlimited transcripts, and unrelated filesystem contents are not stored as working memory.

## Security Boundaries

- Account and device authentication are required for protected cloud/device operations.
- Device ownership and authorization are validated by the backend gateway.
- Destructive or sensitive actions use confirmation rules.
- File context must originate from explicit selection, attachment, drop, or path input.
- Protected credential files are rejected by file-context policies.
- Environment files, access tokens, API keys, and authorization headers must never enter logs.
- Local capabilities remain constrained to their registered contracts.

## Packaging

`npm run dist` performs the production Windows build:

1. Prepare the runtime environment.
2. Package Python companion sources and required dependencies.
3. Build the self-contained Python voice runtime.
4. Validate Electron and desktop assets.
5. Build the Windows x64 NSIS installer with `electron-builder`.

The installer includes the Electron application, packaged Python runtime, companion modules, and required public assets. Local `.env` files, source virtual environments, caches, logs, and development dependencies must not be committed or uploaded.

## Diagnostics

Desktop logs are written under the user's CEASER application-data directory, normally:

```text
%APPDATA%\ceaser\logs\ceaser-desktop.log
```

Live diagnostics expose safe readiness, process, gateway, voice-state, routing, capability, and error-category information. They intentionally omit credentials and raw authorization data.

## Development Commands

From `ceaser/desktop`:

```powershell
npm start
npm run build
npm run dist
```

`npm start` launches the development Electron host. `npm run build` runs desktop validation. `npm run dist` creates the self-contained Windows installer in `desktop/release`.

## External Boundaries

The Desktop Companion does not own CEASER's model routing, cloud memory, billing, plugins, or web-console UI. Those remain backend/web responsibilities. The desktop layer owns local interaction, device presence, Windows execution, voice capture/playback, and the secure bridge to those services.
