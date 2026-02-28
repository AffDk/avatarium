# Data Model: Walkthrough Document Structure

**Feature**: 004-code-walkthrough-docs  
**Date**: 2026-02-28

This feature produces a documentation artifact, not database entities. The "data model" describes the structure and content map of the walkthrough document itself.

## Document Entity: `walkthrough.md`

**Location**: `specs/004-code-walkthrough-docs/walkthrough.md`  
**Format**: Markdown with embedded Mermaid code blocks  
**Estimated Size**: ~2,000–3,000 lines

## Section Structure

```
walkthrough.md
├── Table of Contents (FR-019)
├── Section 1: Architecture Overview
│   ├── Narrative: layer descriptions
│   └── Mermaid: graph TD architecture diagram (FR-001)
├── Section 2: Configuration System
│   └── Narrative: env vars, settings groups, singleton pattern (FR-011)
├── Section 3: Database Layer
│   ├── Narrative: async engine, session lifecycle, get_db (FR-012)
│   └── Mermaid: erDiagram for all 8 tables (FR-002)
├── Section 4: Data Model & Enums
│   ├── Narrative: all tables with field descriptions
│   ├── Enum tables: VideoStyle, ProjectStatus, ModerationStatus, GenerationStatus, ClipStatus (FR-003)
│   └── Mermaid: stateDiagram-v2 for ProjectStatus lifecycle (FR-004)
├── Section 5: Authentication Flow
│   ├── Narrative: registration, login, OAuth, JWT, cookies
│   ├── Mermaid: sequenceDiagram for email auth (FR-005)
│   └── Mermaid: sequenceDiagram for Google OAuth (FR-005)
├── Section 6: Photo Upload Pipeline
│   ├── Narrative: validation, filename parsing, person grouping, storage
│   └── Mermaid: flowchart TD for upload flow (FR-006)
├── Section 7: AI Moderation & Scenario Splitting
│   ├── Narrative: prompt construction, Gemini interaction, response parsing
│   └── Mermaid: sequenceDiagram for moderation flow (FR-007)
├── Section 8: Video Generation Pipeline
│   ├── Narrative: initial image, iterative clips, retry logic
│   └── Mermaid: flowchart TD with loop and retry (FR-008)
├── Section 9: API Reference
│   ├── Tables: all endpoints by domain (FR-009)
│   └── Mermaid: graph TD showing route→service connections
├── Section 10: Frontend & Templates
│   ├── Narrative: template inheritance, JS behaviors (FR-010)
│   └── Template hierarchy diagram
├── Section 11: Middleware
│   └── Narrative: rate limiting, session middleware (FR-013)
├── Section 12: Logging
│   └── Narrative: per-session files, levels, format (FR-014)
├── Section 13: Test Infrastructure
│   └── Narrative: fixtures, isolation, organization (FR-015)
├── Section 14: Migrations
│   └── Narrative: Alembic setup, async runner, history (FR-016)
├── Section 15: Implementation Status
│   └── Placeholder/incomplete feature inventory (FR-018)
└── Section 16: File Reference Index
    └── Table mapping all 27 backend files to sections (FR-020)
```

## Entity-to-Section Coverage Map

Each database entity documented in the walkthrough maps to specific sections:

| Entity | Primary Section | Also Referenced In |
|--------|----------------|-------------------|
| `User` | Section 4 (Data Model) | Section 5 (Auth Flow) |
| `Project` | Section 4 (Data Model) | Section 4 (State Machine), Section 9 (API) |
| `Person` | Section 4 (Data Model) | Section 6 (Upload), Section 7 (Moderation) |
| `Photo` | Section 4 (Data Model) | Section 6 (Upload) |
| `Scenario` | Section 4 (Data Model) | Section 7 (Moderation) |
| `Segment` | Section 4 (Data Model) | Section 7 (Moderation), Section 8 (Pipeline) |
| `VideoClip` | Section 4 (Data Model) | Section 8 (Pipeline) |
| `FinalVideo` | Section 4 (Data Model) | Section 15 (Implementation Status — not yet implemented) |

## File-to-Section Coverage Map (FR-020 verification)

All 27 backend Python files and where they are documented:

| # | File | Section(s) |
|---|------|-----------|
| 1 | `backend/main.py` | 1 (Architecture), 11 (Middleware) |
| 2 | `backend/config.py` | 2 (Configuration) |
| 3 | `backend/database.py` | 3 (Database Layer) |
| 4 | `backend/logging_config.py` | 12 (Logging) |
| 5 | `backend/models/__init__.py` | 4 (Data Model) |
| 6 | `backend/models/user.py` | 4 (Data Model), 5 (Auth) |
| 7 | `backend/models/project.py` | 4 (Data Model) |
| 8 | `backend/models/scenario.py` | 4 (Data Model) |
| 9 | `backend/models/video.py` | 4 (Data Model) |
| 10 | `backend/schemas/auth.py` | 5 (Auth), 9 (API Reference) |
| 11 | `backend/schemas/project.py` | 6 (Upload), 9 (API Reference) |
| 12 | `backend/schemas/scenario.py` | 7 (Moderation), 9 (API Reference) |
| 13 | `backend/schemas/video.py` | 8 (Pipeline), 9 (API Reference) |
| 14 | `backend/api/dependencies.py` | 9 (API Reference) |
| 15 | `backend/api/auth.py` | 5 (Auth Flow), 9 (API Reference) |
| 16 | `backend/api/projects.py` | 6 (Upload), 9 (API Reference) |
| 17 | `backend/api/scenarios.py` | 7 (Moderation), 9 (API Reference) |
| 18 | `backend/api/generation.py` | 8 (Pipeline), 9 (API Reference) |
| 19 | `backend/api/health.py` | 9 (API Reference) |
| 20 | `backend/api/pages.py` | 10 (Frontend), 9 (API Reference) |
| 21 | `backend/services/auth_service.py` | 5 (Auth Flow) |
| 22 | `backend/services/upload_service.py` | 6 (Upload) |
| 23 | `backend/services/moderation_service.py` | 7 (Moderation) |
| 24 | `backend/services/pipeline_service.py` | 8 (Pipeline) |
| 25 | `backend/services/image_gen_service.py` | 8 (Pipeline) |
| 26 | `backend/services/video_gen_service.py` | 8 (Pipeline) |
| 27 | `backend/middleware/rate_limit.py` | 11 (Middleware) |

## Mermaid Diagram Inventory (FR-017 verification)

| # | Diagram | Type | Section | Estimated Nodes |
|---|---------|------|---------|----------------|
| 1 | Architecture Overview | `graph TD` | 1 | ~20 nodes, 6 subgraphs |
| 2 | Entity-Relationship | `erDiagram` | 3 | 8 entities |
| 3 | ProjectStatus Lifecycle | `stateDiagram-v2` | 4 | 10 states + composite |
| 4 | Email Auth Sequence | `sequenceDiagram` | 5 | ~20 messages |
| 5 | Google OAuth Sequence | `sequenceDiagram` | 5 | ~15 messages |
| 6 | Photo Upload Flow | `flowchart TD` | 6 | ~15 nodes |
| 7 | Moderation & Splitting | `sequenceDiagram` | 7 | ~12 messages |
| 8 | Video Generation Pipeline | `flowchart TD` | 8 | ~15 nodes + subgraph |
| 9 | Route-to-Service Map | `graph TD` | 9 | ~15 nodes |

**Total: 9 diagrams** (exceeds minimum of 7 from SC-003).
