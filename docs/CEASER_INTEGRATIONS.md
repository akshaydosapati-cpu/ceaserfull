# CEASER External Services

Inspected 2026-09-09. These are source integrations, not a live account-health report. Configuration names refer to settings/env mechanisms, never secret values. Backend paths in this table are relative to `ceaser/backend`.

| Service | Purpose and source | Configuration / flow | Criticality and limitations |
| --- | --- | --- | --- |
| Supabase Auth | `app/core/security/supabase_auth.py`, `app/api/auth/routes.py` | Supabase URL and configured auth credentials; browser bearer -> auth client -> local user | Critical to normal sign-in; local DB validation is separate |
| PostgreSQL / Supabase database | `app/core/database/session.py`, `app/models`, `alembic` | DATABASE_URL -> SQLAlchemy pool -> transactions | Critical persistence/accounting; live region/head not established |
| Supabase Storage | `app/services/storage_service.py` | SUPABASE_URL, service-role credential, SUPABASE_STORAGE_BUCKET; backend -> object API | Critical for stored-file features; keep private access authenticated |
| Google Calendar, Gmail, Drive, Tasks, Classroom | `app/services/integrations/*_provider.py`, `provider_registry.py` | Google client ID/secret, provider callback settings, encrypted connected tokens; OAuth -> provider API/sync | Feature-critical; only authorized scopes/calendars/files available. Docs/Sheets are not separate registered providers |
| Notion | `notion_provider.py`, `oauth_manager.py`, integration routes | Notion OAuth client/callback and webhook verification configuration | Workspace sharing and token permissions constrain returned data |
| GitHub | `github_provider.py`, `github_project_service.py`, integration routes | GitHub App/client configuration, private key, callback and scopes | App installation/access matters; never log private key or broaden permissions casually |
| OpenAI | `app/intelligence/ai/llm/openai_provider.py`, `ai/embeddings/openai_embedding_provider.py` | Provider key/model configuration -> generation/embedding APIs | Selected routes/RAG depend on it; model availability and quota external |
| Gemini | `app/intelligence/ai/llm/gemini_provider.py` | API key and model settings -> provider requests | Current observed production provider, not a guaranteed global selection |
| Groq | `app/intelligence/ai/llm/groq_provider.py` | API key/model settings | Generation option; not automatically live-grounded |
| NVIDIA | `app/intelligence/ai/llm/nvidia_provider.py` | Key, base URL and model policy | Nemotron/coding eligibility depends on policy and availability |
| Hugging Face | `app/intelligence/ai/llm/huggingface_provider.py`, `app/services/image_generation.py`, `huggingface_dataset_service.py` | Configured credentials/models -> inference or dataset operations | Separate generation/image/data capabilities; success of one does not verify others |
| Serper / configured search API | `app/engines/research_engine/search_provider.py` | Search settings/key/base URL -> results -> extraction/citations | Live-research dependency; relevance and failures must be handled |
| DuckDuckGo | Same search provider | Public instant-answer/HTML fallback paths | External availability/quality not guaranteed |
| RapidAPI Google News / NewsAPI | `app/services/news` | Provider key, host/base URL configuration -> news briefs | Conditional research/news; not the same as complete web search |
| OpenWeather | `app/services/weather/openweather_provider.py` | Weather API configuration -> weather response | Conditional weather feature |
| Deepgram | `app/services/voice/providers/deepgram_provider.py` | Configured STT credential -> audio transcription | Voice only; verify consent and audio handling |
| ElevenLabs | `app/services/voice/providers/elevenlabs_provider.py` | ELEVENLABS_API_KEY, voice selection -> streamed speech | TTS quota/voice access required; text chat does not imply TTS invocation |
| Razorpay | `app/services/billing_service.py`, billing routes | Key ID/secret, webhook secret and plan mapping -> billing API/webhooks | Billing-critical; preserve signature checks and idempotency |
| Resend | `app/services/email/resend_service.py` | Configured sender/API credential -> email | Email feature; delivery/domain verification external |
| Google Analytics 4 | `ceaser/website/console/lib/analytics.ts` and website sources | Public measurement configuration -> browser analytics | Not chat-critical; preserve privacy, avoid duplicate events |
| Render | `render.yaml` | Git deployment -> Python web/worker services | Hosting-critical; actual dashboard overrides/regions unknown |
| Vercel | `ceaser/website/vercel.json`, build scripts | Static website/console build -> hosting | Hosting-critical; DNS and deployed revision require external verification |
| GitHub repositories / releases | Git remotes; website build/download sources | Source publication and installer distribution | Do not confuse OAuth integration with release hosting; verify installer bytes/hash separately |

## Integration Contracts

`app/services/integrations/provider_registry.py` registers exactly seven connected-tool providers: Calendar, Gmail, Drive, Tasks, Classroom, Notion, GitHub. Catalog cards are not proof of executable providers. OAuthManager, TokenManager, IntegrationPermissions, IntegrationSyncService and IntegrationExecutionEngine are separate responsibilities in that directory. Preserve user ownership and secret encryption when changing sync or retrieval.

Use `app/core/config/settings.py` and the relevant client as configuration source of truth. Do not copy local .env contents into this guide. Deployment-specific OAuth callbacks, scopes, billing webhooks, service-role rights, account balances and live connectivity were not verified by this documentation task.

No verified Hostinger control-plane/DNS integration was established during source inspection. Do not assume domain registrar, nameservers or hosting ownership from a website URL. Dependencies or optional feature directories may expose additional services; inspect the selected call path before asserting that a service is active in production.
