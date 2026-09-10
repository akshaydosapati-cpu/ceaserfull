# CEASER Master Guide

Source inspection snapshot: 2026-09-09. All paths below are relative to the outer workspace. Implementation presence is not evidence of a configured or healthy production capability.

## Product

CEASER combines a web AI workspace with a Windows desktop companion. The AIOS concept is an application-level assistant coordinating conversation, tools, integrations, and local actions; it is not a replacement operating-system kernel. Users interact through browser chat, attachments/projects, connected tools, and the desktop capsule/overlay using typed or voice commands.

## Major Components

| Component | Source | Role |
| --- | --- | --- |
| Public website | `ceaser/website/index.html`, `config.js`, `animations.js` | Landing page, public entry points and download experience |
| Console | `ceaser/website/console` | Next.js 16 / React 19 workspace, authentication, chat and resource screens |
| API | `ceaser/backend/app/main.py`, `app/api` | FastAPI routes, middleware, lifecycle and service composition |
| Data | `ceaser/backend/app/models`, `app/repositories`, `app/core/database/session.py` | SQLAlchemy entities, persistence and pooled database access |
| AI and orchestration | `ceaser/backend/app/services/orchestrator`, `app/intelligence` | Context, routing, provider requests and response processing |
| Desktop | `ceaser/desktop/src`, `python_companion` | Electron UI/IPC, Python command runtime, local capabilities and cloud communication |
| Alternate frontend tree | `ceaser/frontend` | Another source tree exists; do not synchronize or delete it by assumption. Active inspected website build is in `ceaser/website`. |

## Main Data Flow

Browser input -> console API client -> FastAPI authentication and request controls -> conversation/context and optional retrieval/tools -> model policy/provider -> SSE tokens -> rendered response -> persistence and usage settlement.

This is a branched flow, not a requirement to run every subsystem on every message. `KnowledgeRouter` and `CeaserOrchestrator` choose direct chat, integration, memory, research, and other paths. Coding model policy must not be confused with executing a specialist workflow. See the architecture guide for entry points.

## Implemented Surfaces

- Chat and conversation history, projects, files, documents, memories, agents and workflows have backend API modules.
- Live research has search, page extraction and citation-building code. Model pretraining alone is not live knowledge.
- Registered integrations: Gmail, Google Calendar, Drive, Tasks, Classroom, Notion and GitHub.
- Voice has STT/TTS provider abstractions; desktop has a separate voice/runtime path.
- Credits, commercial/billing services, usage ledgers, admin/internship and certificate verification have dedicated models/services/routes.
- Desktop includes contextual command routing, file resolution, local capabilities, conversation memory, awareness and proactive components. Availability still depends on OS, permissions, configuration and connected services.

## Persistence, Memory and Retrieval

ConversationService persists messages and conversation state. Orchestrator history is bounded to eight recent messages, with a smaller generation slice. MemoryService manages separate user memory records and metadata; memory retrieval/capture is separate from the message transcript. The intelligence knowledge layer supplies chunking, embeddings, repositories and context construction. Attachments and research are conditional sources, not mandatory normal-chat work.

## Runtime and Deployment

Backend uses Python/FastAPI/Uvicorn, SQLAlchemy and Alembic. Render blueprint declares web and cloud-worker services. The website build exports the Next console under `/console`, assembles static output into `public`, and supplies Vercel configuration. Desktop packaging uses Electron Builder NSIS and bundles a prepared Python runtime.

Production configuration, actual hosting plans/regions, credentials, DNS records, deployed commits and installer availability cannot be established solely from checked-in files. Public URLs in source are configuration hints, not proof of live deployment.

## Limitations and Scope

Production chat latency remains open; see CURRENT_STATE for measured baseline and unpushed changes. Do not call current local changes a production fix. Older READMEs/audits are historical context: the desktop README describes an earlier scaffold and must be checked against current source. No new feature roadmap is asserted here. Declared cloud coding is disabled/fail-closed in the Render blueprint; a worker definition does not prove sandbox availability or durable execution in production.

For detailed contracts read [architecture](CEASER_ARCHITECTURE.md), [integrations](CEASER_INTEGRATIONS.md) and [development rules](CEASER_DEVELOPMENT_RULES.md).
