# Bug Tracker

## Status Values

Open, In Progress, Fixed, Verified, Won't Fix, V1.1

## Bugs

| ID | Module | Description | Steps To Reproduce | Expected Result | Actual Result | Severity | Status | Owner | Date Fixed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BUG-001 | Frontend Build | Next build cannot remove locked `.next/server/app/index.segments`. | Run `npm run build` while frontend/dev process may be active. | Build completes. | Windows EPERM unlink error. | Major | Open | User/Codex |  |
| BUG-002 | Backend Tests | Workflow test expects old "Execution Workflow" response wording. | Run backend pytest. | All tests pass. | 1 workflow metadata assertion fails. | Major | Open | Codex |  |

## Bug Entry Template

| ID | Module | Description | Steps To Reproduce | Expected Result | Actual Result | Severity | Status | Owner | Date Fixed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BUG-XXX |  |  |  |  |  |  | Open |  |  |
