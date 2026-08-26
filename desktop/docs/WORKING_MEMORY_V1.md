# CEASER Working Memory V1

## Purpose

Working Memory V1 is the current-session context layer for the CEASER Desktop Companion. It gives the Executive Cortex one clean snapshot of what the user is currently doing, without making the cortex read directly from desktop APIs, integrations, clipboard, or conversation internals.

This stage is infrastructure only. It does not add planning, prediction, autonomous behavior, long-term memory, or backend synchronization.

## Core Rule

Working memory is temporary, local, and non-persistent.

It stores only lightweight state needed to route and understand the next request. It must never store secrets, tokens, passwords, raw audio, raw images, full documents, full repositories, or full conversation transcripts.

## Architecture

```text
Voice / Typed Request
        |
        v
WorkingMemoryManager
        |
        v
ContextSnapshot
        |
        v
Executive Cortex
        |
        v
CommandService -> CapabilityRegistry -> ExecutionEngine
```

The Executive Cortex is a reader only. It receives `context_snapshot` / `working_memory` from the resolver and decides where the request should go.

## Memory Categories

### Desktop

- active app
- active window title
- active process
- monitor
- workspace

### Project

- current project
- current folder
- repository
- branch
- selected file
- language
- editor

### Conversation

- conversation summary
- previous response
- last command
- last capability
- pending clarification
- pending confirmation
- current goal

### Resource

- current PDF, web page, image, dropped file, or selected file metadata
- clipboard type and safe preview metadata
- current selection metadata

### Integration

- connected integrations
- active integration
- GitHub repository
- Notion page

## Expiration

Working memory items expire automatically:

- desktop context: about 90 seconds
- clipboard and selection previews: under 2 minutes
- project context: about 5 minutes
- integration context: 5-10 minutes
- conversation context: current session, with bounded summaries

The store expires stale items before each request and before every snapshot.

## Reference Resolution

The working-memory reference resolver handles vague references such as:

- it
- this
- that
- those
- continue
- again
- same
- previous
- last one

Resolution priority:

1. active resource
2. previous assistant response
3. selected file
4. active integration/project context

If no safe target exists, CEASER should ask for clarification instead of inventing context.

## Privacy Boundaries

Allowed:

- names, IDs, file paths, titles, small previews, counts, and current routing state

Not allowed:

- API keys
- auth tokens
- passwords
- full documents
- full repositories
- full conversations
- raw OCR text
- audio recordings
- images or screenshots
- persistent user data

## Stage 7 Scope

Implemented:

- `WorkingMemoryManager`
- in-memory store
- context snapshot
- source adapters
- reference resolver
- integration with `WorldContextResolver`
- tests for desktop, resource, integration, and conversation continuity

Deferred:

- planner
- prediction engine
- long-term memory
- autonomous actions
- backend memory sync
- continuous OS polling
- OAuth or integration permission changes
