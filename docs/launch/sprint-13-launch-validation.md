# Sprint 13 - Launch Validation

## Objective

Transform CEASER from feature-complete into launch-reliable. A capability is not considered complete because it exists; it is complete only after it passes validation.

## Rule

Every change must answer:

> Does this increase our confidence that CEASER will work flawlessly during the demo and for first users?

If yes, validate or fix it. If no, move it to the V1.1 backlog.

## Testing Order

1. Authentication
2. First-run onboarding
3. Voice
4. Desktop
5. Overlay
6. Identity Engine
7. Research
8. Documents
9. Agents
10. Workflows
11. Automations
12. Integrations
13. Settings
14. Performance
15. Demo

## Confidence Scores

| Subsystem | Score | Status | Notes |
| --- | ---: | --- | --- |
| Authentication | 0/10 | Not validated | Signup, login, recovery, verification, MFA must be tested. |
| First-run onboarding | 0/10 | Not validated | Welcome flow must be tested with a clean browser state. |
| Voice | 0/10 | Not validated | Hotkey, wake word, speaking, and session end must be tested. |
| Desktop actions | 0/10 | Not validated | Known apps, websites, folders, windows, protected actions. |
| Overlay | 0/10 | Not validated | Compact and expanded routing, sizing, state transitions. |
| Identity Engine | 0/10 | Not validated | Who are you, capabilities, truthful limitations. |
| Research | 0/10 | Not validated | Nova, sources, Gemini response quality. |
| Documents | 0/10 | Not validated | Upload, read, summarize, notes/MCQ/flashcards where available. |
| Agents | 0/10 | Not validated | Nova, Zeus, Friday, Alex, Bolt, Atlas. |
| Workflows | 0/10 | Not validated | Multi-agent workflow start, progress, complete, history. |
| Automations | 0/10 | Not validated | Create, edit, pause, resume, delete, run now, worker, history. |
| Integrations | 0/10 | Not validated | Connected/not connected/error states, credentials missing states. |
| Settings | 0/10 | Not validated | Profile, security, voice, privacy/status, no dead controls. |
| Performance | 0/10 | Not measured | Startup, hotkey, voice latency, overlay time, memory/CPU. |
| Demo | 0/10 | Not certified | Must pass multiple consecutive runs. |

## Authentication Validation

| Test | Expected Result | Status | Priority | Notes |
| --- | --- | --- | --- | --- |
| Signup | Account created or verification message shown cleanly. | Not run | Critical |  |
| Login | User reaches onboarding/app without token errors. | Not run | Critical |  |
| Logout/sign out | User returns to welcome flow cleanly. | Not run | Critical |  |
| Forgot password | Recovery email is requested with friendly copy. | Not run | Major |  |
| Reset/update password | Signed-in user can update password. | Not run | Major |  |
| Email verification resend | Verification email request is handled cleanly. | Not run | Major |  |
| MFA enrollment | QR/secret appears or clean provider error appears. | Not run | Major |  |
| MFA verification | Code verifies or friendly error appears. | Not run | Major |  |
| Session persistence | Refresh keeps signed-in app state. | Not run | Critical |  |

## First-Run Onboarding Validation

| Test | Expected Result | Status | Priority | Notes |
| --- | --- | --- | --- | --- |
| Clean first open | Welcome screen appears. | Not run | Critical |  |
| Sign in/create account | Auth step completes cleanly. | Not run | Critical |  |
| Profile setup | Name and use case save locally. | Not run | Major |  |
| Microphone permission | Ready/blocked state is understandable. | Not run | Major |  |
| Hotkey screen | Shows Ctrl + Shift + Space. | Not run | Major |  |
| Voice selection | Available voices populate or system voice shown. | Not run | Major |  |
| Ready screen | Shows example commands and opens app. | Not run | Critical |  |

## Voice Validation

| Test | Expected Result | Status | Priority | Notes |
| --- | --- | --- | --- | --- |
| Hotkey opens overlay | Compact overlay appears top-center. | Not run | Critical |  |
| Greeting | CEASER greets and explains wake behavior. | Not run | Major |  |
| Wake word only | CEASER greets/listens without executing random speech. | Not run | Critical |  |
| Wake word + command | Command executes without extra greeting. | Not run | Critical |  |
| Voice command completes | CEASER stops listening, works, speaks result. | Not run | Critical |  |
| Session end | Goodbye/sleep command ends session. | Not run | Major |  |
| No looping | CEASER does not hear its own speech. | Not run | Critical |  |

## Desktop Validation

| Area | Tests | Expected Result | Status | Priority |
| --- | --- | --- | --- | --- |
| Apps | Chrome, Edge, VS Code, Word, Excel, PowerPoint, Calculator, Notepad, Spotify | Known apps open reliably. | Not run | Critical |
| Unknown app | Random app name | Says "I couldn't find that app yet." | Not run | Critical |
| Websites | YouTube, Gmail, Drive, GitHub, LinkedIn, Spotify Web | Opens correct URL. | Not run | Major |
| Folders | Downloads, Desktop, Documents, Pictures, Videos, Music | Opens folder. | Not run | Major |
| Windows | Focus, minimize, restore, maximize, close | Works or fails gracefully. | Not run | Major |
| System | Time, date, battery, disk, network | Gives useful response. | Not run | Major |
| Protected | Screenshot, lock, restart app, clear clipboard | Confirmation appears first. | Not run | Critical |

## Overlay Validation

| Test | Expected Result | Status | Priority | Notes |
| --- | --- | --- | --- | --- |
| Compact default | Simple commands stay compact. | Not run | Critical |  |
| Expanded routing | Research/workflows/docs/automations/calendar/email/music/news expand. | Not run | Critical |  |
| State transitions | Idle/listening/transcribing/thinking/working/completed/error are clean. | Not run | Major |  |
| Text fit | Compact text is readable or scrollable where needed. | Not run | Major |  |
| No dead controls | Buttons visible and functional. | Not run | Critical |  |

## AI, Agents, Workflows, Automations

| Subsystem | Tests | Expected Result | Status | Priority |
| --- | --- | --- | --- | --- |
| Identity | Who are you, what can you do, help me | Dynamic, truthful, concise. | Not run | Critical |
| Nova | Research, news, sources | Useful answer with sources where available. | Not run | Critical |
| Zeus | Strategy, planning, business | Useful business output. | Not run | Major |
| Friday | Content, marketing, writing | Useful content output. | Not run | Major |
| Alex | Study, learning, assignments | Useful learning output. | Not run | Major |
| Bolt | Automation, tasks, execution | Useful execution output. | Not run | Major |
| Atlas | Technical questions, architecture | Useful technical output. | Not run | Major |
| Workflows | Research, Research + Strategy, Startup, Technical | Starts, progresses, completes, saves history. | Not run | Critical |
| Automations | Create, edit, pause, resume, delete, run now, worker, history | Works or fails gracefully. | Not run | Critical |

## Integrations And Settings

| Test | Expected Result | Status | Priority | Notes |
| --- | --- | --- | --- | --- |
| Integrations list | Shows providers without ugly errors. | Not run | Major |  |
| Credentials missing | Shows credentials required state. | Not run | Major |  |
| Connect flow | Opens OAuth when configured. | Not run | Major |  |
| Disconnect/reconnect | Works or cleanly communicates state. | Not run | Major |  |
| Settings system status | No fake connected tools. | Not run | Major |  |
| Security settings | Password and MFA controls behave cleanly. | Not run | Major |  |

## Performance Measurements

| Metric | Target | Actual | Status | Notes |
| --- | --- | --- | --- | --- |
| Web app first load | Under 5s locally | Not measured | Not run |  |
| Backend startup | Under 10s locally | Not measured | Not run |  |
| Desktop overlay hotkey | Under 1s | Not measured | Not run |  |
| Voice transcription start | Under 2s after speech | Not measured | Not run |  |
| Desktop command execution | Under 3s for known apps | Not measured | Not run |  |
| Research workflow start | Under 5s | Not measured | Not run |  |
| Idle CPU/memory | No obvious spike | Not measured | Not run |  |

## Current Sprint 13 Status

Planning: Complete

Validation: Not started

Critical blockers: Unknown until first validation pass

Next action: Start authentication validation, then first-run onboarding.
