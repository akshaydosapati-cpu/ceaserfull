# Launch Blockers

No issue is allowed here without a priority.

## Priority Definitions

| Priority | Meaning | Launch Rule |
| --- | --- | --- |
| Critical | Blocks July 9 demo or core launch journey. | Must fix before demo. |
| Major | Should be fixed before public launch. | Fix before public release unless consciously accepted. |
| Minor | Acceptable for V1. | Can ship if documented. |
| Cosmetic | Pure polish. | Fix only after higher priorities. |

## Critical

| ID | Module | Blocker | Status | Owner | Notes |
| --- | --- | --- | --- | --- | --- |
| LB-001 | Validation | First Sprint 13 validation pass not yet run. | Open | Codex/User | Unknown blockers remain until tests are executed. |

## Major

| ID | Module | Blocker | Status | Owner | Notes |
| --- | --- | --- | --- | --- | --- |
| LB-002 | Frontend Build | Last `npm run build` hit Windows `.next` file lock. | Open | User/Codex | Stop dev server and rerun build. TypeScript passed. |
| LB-003 | Backend Tests | One existing workflow test expects old response wording. | Open | Codex | 34 passed, 1 failed. Needs test/update or response decision. |

## Minor

| ID | Module | Issue | Status | Owner | Notes |
| --- | --- | --- | --- | --- | --- |

## Cosmetic

| ID | Module | Issue | Status | Owner | Notes |
| --- | --- | --- | --- | --- | --- |
