# CEASER Development Rules

## Before Work

Read AGENTS.md and current state. Check status, diff (including staged and untracked files), remotes and recent commits in each affected repository. Read implementation and relevant tests before deciding what to change. Historical audits and this documentation can be stale.

## Change Boundaries

- Preserve architecture and existing functionality; prefer the smallest justified change.
- Do not duplicate existing routing, parsing, providers, persistence or tool systems.
- Do not delete unfinished work or overwrite unrelated changes.
- Do not introduce infrastructure, schema migrations, provider-priority changes or global caching as an incidental fix.
- Get explicit approval for destructive actions, security-policy changes, infrastructure replacement and changes outside the task.
- Preserve user/device authorization, permissions, refresh behavior and tenant isolation.
- Preserve credits, concurrency limits, ledger idempotency, reservation release and settlement; never hide accounting errors as successful completion.
- Preserve full response persistence, conversation context, memory/RAG, tools, agents and fallback contracts.
- Keep secrets server-side. Never commit .env, private keys, access tokens, user databases or unredacted production traces.
- Never assume a UI catalog item is a implemented/authorized provider or a model answer is live evidence.

## Latency and Reliability

Measure before optimizing. Separate request queueing, auth, pool/connection acquisition, SQL, commit, preparation, provider TTFT, SSE receipt and React commit. Do not subtract unrelated clocks and call the difference network latency. Do not remove correctness checks to meet a timing target. Retain cancellation/disconnect cleanup. Do not run concurrent operations against the same SQLAlchemy session. Preserve the current uncommitted cancellation-safe worker helper.

## Validation Commands

Run from the relevant directory, not the outer workspace:

- Backend: `.\.venv\Scripts\python.exe -m pytest -q` with focused test paths first; full suite when risk warrants.
- Backend syntax: source-level `ast.parse` is acceptable when Windows pyc locks make compileall unreliable.
- Console: `npm run build` in `ceaser/website/console`; this is not the complete static-site assembly.
- Full website: `npm run build` in `ceaser/website` (installs console dependencies and assembles public output).
- SSE: `node scripts/test-stream.cjs` in the console.
- Desktop: `npm run build` validates scaffold; `npm run dist` prepares/bundles Windows NSIS and must be separately authorized. Do not start Electron just to validate docs.
- `git diff --check` in each changed repository. For docs-only work validate paths, Markdown structure, whitespace and absence of secrets; no application suite/build is needed.

Do not run paid provider calls, real storage uploads, migrations or account-changing operations without task authorization. Never invent results. Record commands, counts, failures and whether testing was mocked, local, Windows, or production.

## Release and Handoff

Recheck remotes: origin and legacy-origin differ. Commit only authorized files; never blindly stage the workspace. Do not force-push. Confirm which repository owns each artifact. Root documentation currently lies outside the two working repositories and needs an explicit publication plan.

A local build is not a deployment. Production verification requires the deployed revision, authenticated request evidence, correlated logs and appropriate persistence/fallback checks. If access is unavailable, finish justified local changes, state the precise verification gap and stop.

Update CURRENT_STATE after meaningful work with active task, status, modified files, commits, tests, unresolved issues and exact next action. If interrupted before updating, the next agent must reconstruct state from source and Git, not restart or reset.
