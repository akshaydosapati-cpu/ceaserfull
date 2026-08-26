# CEASER Semantic World Model V1

## Purpose

The Semantic World Model is CEASER Desktop Brain's relationship layer.

Working Memory knows what is active right now. The World Model knows how the active things relate to each other.

This document freezes the Stage 8 architecture before implementation. It is a contract for future Planner, Long-Term Memory, Prediction, and Adaptive Intelligence stages.

## Core Difference

```text
Working Memory
Temporary current state
Example: active file is command_service.py

Semantic World Model
Structured relationship graph
Example: command_service.py belongs to CEASER Desktop, which belongs to the CEASER project, which is linked to a GitHub repository, current goal, conversations, and tasks.
```

Working Memory is live state. The World Model is relationship knowledge.

## Architecture

```text
Voice / Typed Input
        |
        v
Executive Cortex
        |
        v
Semantic World Model
        |
        v
Working Memory / ContextSnapshot
        |
        v
CommandService -> CapabilityRegistry -> ExecutionEngine
```

The Executive Cortex queries the World Model for relationship context. The World Model may read the latest `ContextSnapshot`, but it does not execute actions.

## Entity Types

### User Session

Represents the currently connected desktop session.

Fields:

- session id
- user id
- active project id or name
- current goal
- active workspace
- last meaningful activity

### Project

Represents a user project or work area.

Fields:

- project name
- aliases
- current goal
- linked repositories
- linked folders
- linked Notion pages/databases
- linked conversations
- linked resources

### Repository

Represents a GitHub repository or local repository.

Fields:

- owner
- name
- URL
- local folder
- branch
- language
- linked project
- recent activity summary

### Resource

Represents a file, document, webpage, image, PDF, spreadsheet, presentation, or dropped item.

Fields:

- resource name
- resource type
- path or safe identifier
- linked project
- linked conversation
- lightweight summary
- last accessed time

### Conversation

Represents the current conversation context.

Fields:

- conversation id
- topic
- short summary
- last user request
- last assistant response summary
- linked project/resource/repository
- unresolved question or pending confirmation

### Task

Represents a task from CEASER, Notion, GitHub issues, or future integrations.

Fields:

- title
- status
- assignee
- due date
- source
- linked project
- linked resource

### Integration

Represents connected external systems.

Fields:

- provider
- connection status
- account label
- last sync time
- visible scopes
- linked entities

### Goal

Represents the user's current objective.

Fields:

- goal text
- source command
- status
- linked project
- linked resources
- linked tasks

## Relationship Types

The graph should support these relationship edges:

- `belongs_to`
- `linked_to`
- `opened_from`
- `discussed_in`
- `summarized_by`
- `assigned_to`
- `depends_on`
- `created_from`
- `updated_by`
- `same_as`
- `alias_of`
- `active_for_session`

Examples:

```text
Project: CEASER
  belongs_to User Session
  linked_to Repository: Ceaser_frontend_production
  linked_to Repository: Ceaser_backend_production
  linked_to Notion Page: Product Roadmap
  discussed_in Conversation: Desktop Companion Fixes
  has Goal: Prepare RC1
```

## Working Memory vs World Model

### Working Memory owns

- active app
- active window
- active file
- current clipboard metadata
- latest user command
- previous response
- current active resource
- temporary selected repo/page

### World Model owns

- project relationships
- repository-to-project mapping
- document-to-conversation mapping
- Notion/GitHub/project links
- aliases
- current goal relationships
- task/project/resource relationships

## Update Rules

Only source adapters should update the World Model.

Allowed future sources:

- DesktopSource
- ConversationSource
- GitHubSource
- NotionSource
- BrowserSource
- VisionSource
- ClipboardSource
- VoiceSource
- WorkflowSource
- NotificationSource

The Executive Cortex must not write directly to the World Model.

## Synchronization with Working Memory

The World Model reads `ContextSnapshot` to detect changes such as:

- active project changed
- active repository changed
- selected file changed
- active integration changed
- resource dropped/opened
- conversation topic changed

Then it creates or updates lightweight graph relationships.

Example:

```text
ContextSnapshot says:
active_app = VS Code
repository = ceaser
selected_file = desktop/python_companion/core/command_service.py

World Model infers:
selected_file belongs_to Repository: ceaser
Repository: ceaser linked_to Project: CEASER
Conversation linked_to Project: CEASER
```

## Query Rules

The Executive Cortex may ask the World Model:

- What project is active?
- What does "this project" refer to?
- Which repo belongs to the current project?
- Which Notion pages are linked to this project?
- Which resource is the user discussing?
- What goal is currently active?
- Which task or repository does "last one" refer to?

The World Model returns relationship context only. It does not generate answers or execute actions.

## Privacy Boundaries

Allowed:

- entity names
- safe IDs
- file paths
- repository names
- page/database names
- short summaries
- relationship edges
- timestamps

Not allowed:

- API keys
- auth tokens
- passwords
- raw documents
- raw screenshots
- raw audio
- full conversations
- full repository contents
- private integration payloads beyond safe metadata

## Persistence Policy

Stage 8 freeze does not implement persistence.

Future implementation may use:

- in-memory graph for current desktop session
- optional encrypted local cache
- optional backend sync after explicit privacy review

No persistence should be added until the World Model schema and privacy review are approved.

## Stage 8 Scope

This stage freezes the architecture only.

Implemented in this stage:

- `WORLD_MODEL_V1.md`
- entity definitions
- relationship definitions
- Working Memory boundary
- update rules
- query rules
- privacy rules

Deferred:

- actual graph store
- source adapters
- planner
- prediction engine
- long-term memory
- autonomous behavior
- backend synchronization
- UI changes
