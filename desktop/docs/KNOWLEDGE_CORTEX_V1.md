# CEASER Knowledge Cortex V1

## Purpose

The Knowledge Cortex is CEASER's internal structured knowledge layer.

It answers the question:

```text
What does CEASER already know?
```

This is different from Working Memory, the Semantic World Model, and Long-Term Memory.

## Brain Region Boundary

```text
Executive Cortex
Decides where a request should go.

Working Memory
Knows exact live state.

Semantic World Model
Knows relationships between current runtime entities.

Planner
Turns bounded goals into verified workflows.

Knowledge Cortex
Knows CEASER facts, capabilities, documentation, workflows, schemas, and product knowledge.

Long-Term Memory
Will remember user-specific preferences and durable personal facts.
```

## What Counts As Knowledge

Knowledge Cortex may contain structured facts about:

- CEASER architecture
- Desktop Brain modules
- capability names and descriptions
- command examples
- workflow definitions
- safety rules
- IPC schemas
- planning rules
- integration capabilities
- documentation summaries
- product FAQs
- user-facing help content
- supported file types
- available desktop actions
- available backend actions
- known limitations

Examples:

```text
github.list_commits
supports reading recent commits from a connected GitHub repository.
```

```text
Workflow continuation
means a pending workflow resumes from the exact paused confirmation step after user approval.
```

```text
Working Memory
is temporary current-session state and does not persist after restart.
```

## What Is Not Knowledge

Knowledge Cortex must not store:

- user preferences
- personal memories
- private conversations
- temporary active app state
- current clipboard values
- raw files
- raw documents
- raw repository contents
- screenshots
- audio
- auth tokens
- API keys
- passwords
- private integration payloads

Those belong elsewhere:

- Working Memory: temporary live state
- Semantic World Model: runtime relationships
- Long-Term Memory: curated user-specific facts, future stage
- Backend/RAG: private user documents and project data

## Difference From Semantic World Model

Semantic World Model:

```text
Current session is working on CEASER.
CEASER project is linked to CEASER repository.
Desktop Brain Roadmap is connected to CEASER project.
```

Knowledge Cortex:

```text
CEASER has a Planner.
The Planner supports max 6 workflow steps.
Notion writes require confirmation.
GitHub read capabilities do not require confirmation.
```

World Model is about current relationships.
Knowledge Cortex is about known product/system facts.

## Difference From Long-Term Memory

Knowledge Cortex:

```text
CEASER supports Notion page search.
WorkflowRunner emits workflow_step_completed events.
```

Long-Term Memory:

```text
Akshay prefers concise reports.
Akshay is building CEASER for launch.
Akshay often works on GitHub and Notion workflows.
```

Long-Term Memory is user-specific and must be curated.
Knowledge Cortex is system/product/domain knowledge.

## Executive Cortex Query Rules

The Executive Cortex may ask the Knowledge Cortex:

- What can CEASER do with GitHub?
- What can CEASER do with Notion?
- Is this capability registered?
- Does this request require confirmation?
- Is this command supported?
- Which workflow matches this goal?
- What are examples of desktop commands?
- Which module owns this responsibility?
- Does CEASER already know enough to answer without backend AI?

The Knowledge Cortex returns structured facts and confidence, not free-form hidden reasoning.

## Synchronization Rules

Knowledge Cortex should stay synchronized with:

- `CapabilityRegistry`
- architecture docs
- workflow definitions
- command examples
- safety rules
- IPC schemas
- product documentation

When capabilities change, Knowledge Cortex should update its capability facts.

When docs change, Knowledge Cortex should rebuild doc summaries or indexes.

No source should bypass it by creating duplicate knowledge stores.

## Trust Rules

Each knowledge item should track:

- id
- type
- title
- summary
- source
- confidence
- updated_at
- tags
- optional examples

Knowledge from source code and frozen docs has higher confidence than generated summaries.

LLM-generated knowledge must be marked as generated and lower confidence unless verified against source files.

## Privacy Boundaries

Allowed:

- product facts
- module names
- capability names
- schemas
- workflow templates
- public/safe documentation summaries
- command examples

Not allowed:

- tokens
- credentials
- passwords
- full private user documents
- private repository contents
- complete user conversations
- personal user preferences
- private memory facts

## Stage 10 Implementation Boundary

Stage 10 should implement the smallest useful Knowledge Cortex:

- in-memory knowledge store
- capability knowledge source
- docs knowledge source
- workflow knowledge source
- query interface
- confidence scoring
- Executive Cortex read-only integration

Do not implement:

- long-term memory
- prediction
- proactive behavior
- autonomous learning
- vector database
- backend persistence
- user-specific memory

## Acceptance Target

CEASER should be able to answer locally structured questions such as:

```text
What can you do with Notion?
How does workflow planning work?
What desktop commands are supported?
Does creating a Notion page require confirmation?
What is Working Memory?
```

without guessing and without confusing product knowledge with user memory.
