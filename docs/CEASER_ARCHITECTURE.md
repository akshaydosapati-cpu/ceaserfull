# CEASER Architecture

Inspected 2026-09-09. Paths are workspace-relative. Trace the specific caller before editing: multiple service and intelligence layers coexist and are not interchangeable.

## Component Contracts

| Location / entry point | Input -> output and dependencies | Dependents / change risk |
| --- | --- | --- |
| `ceaser/website/console/app`, `components/ceaser/pages/chat-page.tsx` | Session, user input and streamed events -> React workspace | Guest/authenticated UI, editing, history, loading and completion can regress |
| `ceaser/website/console/lib/api/client.ts` | API operation -> authenticated fetch, refresh retry, parsed SSE | All console API users; preserve incremental parsing, error and refresh semantics |
| `ceaser/website/console/lib/session.ts`, `lib/app-context.tsx` | Stored session and resource requests -> client session/application state | Startup, sign-in and account-specific data isolation |
| `ceaser/backend/app/main.py` | HTTP -> middleware, auth/routing, CORS, timing and errors | All endpoints; lifespan starts automation worker and closes shared clients |
| `app/core/security/dependencies.py:get_current_user` (backend) | Bearer -> validated local User; Supabase or desktop-token path | Protected APIs; preserve invalid-session vs infrastructure-failure distinction |
| `app/core/database/session.py` (backend) | Session operations -> database results and per-request SQL timings | Repositories and services; pooling/transaction/session ownership affect correctness |
| `app/api/ceaser/routes.py:ceaser_chat_stream` (backend) | Authenticated chat payload -> SSE response and settlement | Console chat; concurrency slots, credits, cancellation and terminal events |
| `app/services/orchestrator/orchestrator.py:CeaserOrchestrator` (backend) | Message, user, conversation, attachments -> prepared request / response | Chat, routed tools and context; large shared blast radius |
| `app/services/execution_paths`, `app/intelligence/ai` (backend) | Workload/model policy -> provider output | Fast chat and other callers; retain manual preferences and fallback contracts |
| `app/services/conversation_service.py`, `app/models/conversation.py` (backend) | Conversation/message operations -> stored transcript/state | History, follow-ups, title and persistence; do not skip ownership checks |
| `app/services/memory_service.py`, `app/services/orchestrator/memory_retriever.py`, `memory_capture.py` (backend) | User context and memories -> retrieved/captured memory | Personalization; user scope and superseded-memory semantics matter |
| `app/intelligence/knowledge` (backend) | Documents/query -> chunks, embeddings, knowledge/context | RAG, attachment and knowledge routes; deletion and access scope must stay consistent |
| `app/agents`, `app/services/workflows`, `app/services/capabilities` (backend) | Routed task -> agent/tool/workflow result | Specialist tasks; discovery must not be added to simple chat indiscriminately |
| `app/services/credit_service.py`, `usage_ledger_service.py`, `compute_wallet_service.py`, `compute_unit_service.py` (backend) | Request/workload -> reservation, usage and settlement | Billing/limits; multiple accounting layers exist, not interchangeable counters |
| `app/services/storage_service.py`, `file_service.py`, `app/api/admin`, `app/api/certificates` (backend) | Authorized documents/admin operations -> metadata, stored objects and verification | Private documents and certificate workflows; keep service-role access server-side |

In this table, paths beginning `app/` are inside `ceaser/backend`.

## Chat Lifecycle and Latency Boundaries

1. Console sends through `lib/api/client.ts`; captures browser timing and request correlation.
2. `main.py` middleware records request timing. Security dependency validates bearer identity and loads local user. Supabase remote identity caching does not eliminate the local DB lookup. Desktop tokens use their own verification path and local device/user validation.
3. `ceaser_chat_stream` checks rate/concurrency, creates a pending new conversation when needed, reserves credits and snapshots reservation data.
4. SSE generator owns its own SessionLocal session. It emits `response.started`, creates the orchestrator and calls `prepare_stream_request`.
5. Preparation resolves attachments, conversation and bounded history, follow-up intent, knowledge route, conditional context/research and model request. Read actual branch guards; integrations and memory routes can produce direct results.
6. Provider path streams content. Diagnostics distinguish request preparation, provider wait and first content. SSE yields are not proof of browser receipt.
7. User/assistant persistence, response finalization, auditing and credit settlement/release run according to success/error/cancellation flow. Preserve exact ordering and idempotency in source.
8. Browser parses fragmented/CRLF SSE incrementally. First content, React commit, completed stream and persisted message are different milestones.

Current uncommitted `app/core/database/execution.py:run_serial_db` moves blocking work to a worker and drains it before cancellation propagates, preventing session cleanup while a worker still owns it. Calls remain sequential. `measured_db_call` reports queue, worker, SQL and residual time; residual is NOT synonymous with pool wait. Cursor timings exclude connection pre-ping and commit I/O. See CURRENT_STATE before changing this work.

## Authentication and Data

- `app/core/security/supabase_auth.py` is the Supabase auth client; `app/api/auth/routes.py` owns auth endpoints including refresh.
- `app/services/desktop_auth_service.py` and `app/api/desktop/routes.py` handle desktop identity/device flows. Do not merge browser and desktop token handling casually.
- SQLAlchemy models cover users/profiles, conversations/messages, projects, files, knowledge/memory, integrations, workflows/automation, commercial/growth records, desktop, certificates/admin and cloud runtime.
- `alembic` migrations describe schema evolution; live migration head and storage bucket state require environment verification.
- Supabase Auth, SQL database access and Supabase Storage are distinct operations. A successful sign-in does not prove database or storage health.

## Model, Research and Tool Layers

`app/intelligence/ai/ai_provider_service.py` composes AI access. `model_router/{router,registry,request_builder,models}.py` expresses model policy; `llm/{router,registry,base}.py` and provider adapters implement requests/streaming. OpenAI, Gemini, Groq, NVIDIA and Hugging Face adapters exist. `app/services/llm` also exists: inspect callers rather than assuming it is the same abstraction.

`app/services/orchestrator/knowledge_router.py` selects knowledge routes. `app/engines/research_engine/{engine,search_provider,source_collector,page_extractor,citation_builder}.py` handles external research. `app/services/integrations` handles connected-account actions and sync through its own registry, OAuth/token/permission and execution services. Tool results are evidence inputs; source availability and relevance still require validation.

## Desktop / AIOS

`ceaser/desktop/src/main/main.js` is Electron entry; `app-shell.js` and `preload.js` support window/IPC boundaries. `src/renderer/app.js` handles capsule/expanded UI and user events. `python_companion/desktop_voice_server.py` bridges the Python runtime. `core/command_service.py:CommandService.execute` coordinates context, ExecutiveCortex, intent routing and ExecutionEngine, returning ActionResult status/capability/verification/error data.

`routing/intent_router.py`, `natural_language_interpreter.py` and `conversation/executive_cortex.py` distinguish local actions, contextual follow-ups and AI requests. `capabilities/registry.py` and `windows_runtime.py` are local capability entry points. File and app control must use existing capability and resolution paths, not arbitrary model-generated shell execution. OS associations and permissions affect file opening.

`conversation`, `working_memory`, `long_term_memory`, `experience`, `awareness`, `prediction` and `world_model` contain contextual/proactive subsystems. CommandService wires awareness events to ProactiveRuntimeAdapter. Local SQLite/cache files exist and can hold private state; never upload them as source. Tray/process residency is not a guarantee that arbitrary tasks survive process exit.

Backend `device_gateway*`, `persistent_device_executor.py`, `desktop_cloud_service.py`, `background_task_service.py`, `services/automations` and `services/cloud_runtime` provide device/background execution paths. `scripts/run_cloud_worker.py` is a separate worker entry point. Distinguish in-process background work from persisted jobs by following the particular task service; do not assume all work is durable.

## Build / Hosting

Website `package.json` builds console then `scripts/build-site.mjs`; Vercel serves `public`. Console `next.config.ts` exports production with `/console` basePath, trailing slashes and unoptimized images. Rewrites in `website/vercel.json` cover referral and certificate routes. Changing paths can redirect users to the wrong page.

Backend `render.yaml` declares migration-before-Uvicorn startup and a cloud worker, with cloud coding disabled and sandbox unavailable. Dashboard settings may differ. Desktop `package.json` defines `dist`: prepare runtime, validate, Electron Builder Windows NSIS. Bundled `.env.runtime` must contain only distributable configuration, never backend credentials. Installer distribution is a separate website/release concern from building an EXE.
