# CEASER Desktop Companion

Sprint 7 foundation for CEASER's desktop presence.

This app is a local Electron companion that owns:

- Minimal, compact, and expanded overlay UI
- Tray resident mode
- Global hotkey
- Local permissions
- Safe desktop command execution
- Agent-aware progress display
- Opening the full CEASER web app

It does not perform Office automation, browser automation, mouse control, continuous screen watching, background OCR, or destructive file actions.

## Scripts

```bash
npm install
npm run build
npm start
```

`npm run build` validates the desktop scaffold. `npm start` requires Electron to be installed.

## Environment

Copy `.env.example` to `.env` for local desktop testing.

Development defaults:

```bash
CEASER_APP_URL=http://localhost:3000
CEASER_API_URL=https://ceaser-backend-production-ur04.onrender.com
```

Production should use cloud HTTPS URLs:

```bash
CEASER_APP_URL=https://app.ceaser.ai
CEASER_API_URL=https://ceaser-backend-production-ur04.onrender.com
```
