# CEASER Agent Entry Point

Publication note: in the full GitHub repository, `backend/`, `website/`, and `desktop/` are at the repository root. The documentation describes the original local workspace, where those directories are under `ceaser/`. When working in the full repository, drop the `ceaser/` prefix from source paths and Git commands. Statements about the outer workspace not being a Git worktree describe that local workspace, not this published repository. Always inspect the current checkout before acting.

Read this first in Codex, Antigravity, or another coding agent. These are workspace instructions, not a substitute for source inspection.

## Read Before Editing

1. [Current state](docs/CEASER_CURRENT_STATE.md): active work, validation, blockers.
2. [Master guide](docs/CEASER_MASTER.md): product and source map.
3. [Architecture](docs/CEASER_ARCHITECTURE.md): component contracts and flows.
4. [Integrations](docs/CEASER_INTEGRATIONS.md): external dependencies and configuration boundaries.
5. [Development rules](docs/CEASER_DEVELOPMENT_RULES.md): security, testing, release constraints.

Also read applicable nested AGENTS.md files. The website console has Next.js-specific instructions.

## Recover Interrupted Work

Before continuing interrupted work:
- Run git status in each affected repository.
- Inspect git diff, git diff --cached, and recent commits.
- Identify modified AND untracked files; ordinary git diff omits untracked contents.
- Read the relevant implementation and tests/failures.
- Compare the current implementation against the active task.
- Determine what was completed and what remains.
- NEVER reset, revert, or discard uncommitted work unless explicitly instructed.
- Continue from the existing implementation. Never restart a partially completed task unnecessarily.

Do not assume CEASER_CURRENT_STATE.md was updated before an interruption. Resolve conflicts using actual source, working-tree changes, recent commits, and test evidence first; then repair the documentation.

## Repository Boundaries

As inspected on 2026-09-09, this outer workspace and `ceaser/` do not resolve as Git worktrees. `ceaser/backend` and `ceaser/website` are separate working repositories. Run Git commands with an explicit directory, for example `git -C ceaser/backend status --short`. Check remotes before any publish operation; legacy-origin also exists. Do not assume root documentation will be included in a backend or website push. Do not initialize or repair root Git metadata without approval.

## Mandatory Rules

- Inspect before changing; preserve existing architecture and product functionality.
- Never expose secrets from .env, logs, tokens, private keys, runtime databases, or credentials.
- Preserve authentication, ownership, credits/accounting, persistence, memory, retrieval, tools, and fallback behavior.
- Run relevant tests after application changes; documentation-only work needs only documentation checks.
- Never claim a production fix from local tests. Record unverified deployment and production behavior explicitly.
- Update CEASER_CURRENT_STATE.md after meaningful work or intentional handoff, including exact next steps and unfinished work.
- Do not commit, push, deploy, migrate, or rebuild installers unless the current task authorizes it.
