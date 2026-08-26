# CEASER Desktop Native Packaging Plan

## Target Architecture

CEASER V1 should use a hybrid architecture:

- Cloud backend: auth, Supabase, Google OAuth, integrations, Gemini, memory, files, projects, workflows, audit logs.
- Desktop app: Electron shell, tray companion, overlay, hotkey, local desktop actions, voice capture, local media/window/app control.

The installer should not require users to install Python, Node, or run a backend locally.

## Production Runtime

```text
CEASER Installer
-> Electron desktop app
-> Built frontend shell
-> Tray companion
-> Overlay and hotkey
-> Cloud backend API
-> Supabase and integrations
```

## Required Production URLs

Use real HTTPS URLs before public packaging:

```text
CEASER_APP_URL=https://app.ceaser.ai
CEASER_API_URL=https://api.ceaser.ai
NEXT_PUBLIC_API_URL=https://api.ceaser.ai
NEXT_PUBLIC_APP_URL=https://app.ceaser.ai
```

Google OAuth callbacks should point to the cloud backend:

```text
https://api.ceaser.ai/integrations/google-calendar/callback
https://api.ceaser.ai/integrations/gmail/callback
https://api.ceaser.ai/integrations/google-drive/callback
https://api.ceaser.ai/integrations/google-tasks/callback
https://api.ceaser.ai/integrations/google-classroom/callback
```

## Desktop Responsibilities

- Global hotkey.
- Tray resident mode.
- Compact overlay.
- Voice capture and TTS playback.
- Open and close apps.
- Open URLs.
- Music/media key controls.
- Window and file actions that are safe for V1.
- Send cloud requests for chat, calendar, documents, memory, and integrations.

## Cloud Backend Responsibilities

- Login/signup/session validation.
- Profile and memory persistence.
- Conversations and chat orchestration.
- Generated documents and file metadata.
- Google OAuth token storage and refresh.
- Calendar/Gmail/Drive/Tasks/Classroom metadata.
- Gemini calls.
- News/weather/live APIs.
- Audit logs.

## Installer Checklist

- Build frontend for production.
- Package Electron with tray and overlay.
- Point desktop to production `CEASER_API_URL`.
- Confirm login session handoff to desktop companion.
- Confirm app can run hidden in tray after main window closes.
- Confirm hotkey opens overlay after reboot.
- Confirm OAuth redirect URLs are cloud HTTPS URLs.
- Test on a clean Windows laptop.

## Current State

- Tray companion foundation: added.
- Startup setting hook: added.
- Overlay hotkey: already exists.
- Local backend bundling: intentionally not used for production.
- Production installer tooling: pending.
- Cloud deployment: pending.
