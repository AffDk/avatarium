# Feature Specification: Code Walkthrough Documentation with Mermaid Visualizations

**Feature Branch**: `004-code-walkthrough-docs`  
**Created**: 2026-02-28  
**Status**: Draft  
**Input**: User description: "Create a detailed walkthrough of the code so I can review different aspects of the code and how each part is implemented. Add some visualization using Mermaid charts to illustrate and show the data flow between different parts."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — High-Level Architecture Overview (Priority: P1)

As a developer or reviewer, I want a single document that gives me a top-down view of the entire Avatarium platform — its layers, major components, and how they connect — so I can quickly orient myself before diving into specifics.

**Why this priority**: Without a high-level map, any deeper walkthrough lacks context. This is the foundation all other sections build upon.

**Independent Test**: Can be verified by reading the document and confirming it accurately describes every top-level directory, the entry point, configuration, database setup, and middleware — with a Mermaid architecture diagram that matches the actual codebase structure.

**Acceptance Scenarios**:

1. **Given** the walkthrough document exists, **When** a reviewer reads the "Architecture Overview" section, **Then** they see a Mermaid diagram showing all layers (client, routes, services, models, external APIs) and a narrative explaining each layer's responsibility.
2. **Given** the architecture diagram is rendered, **When** a reviewer compares it to the actual codebase, **Then** every major module (main, config, database, middleware, api, services, models, schemas, templates, static) is represented.

---

### User Story 2 — Data Model & Entity Relationships (Priority: P1)

As a developer, I want a clear walkthrough of all database models, their fields, relationships, and lifecycle states (enums) — illustrated with a Mermaid entity-relationship diagram — so I can understand the data layer without reading every model file.

**Why this priority**: The data model is the structural backbone. Understanding entities and their relationships is essential for reviewing any feature.

**Independent Test**: Compare the ER diagram and field descriptions against the actual SQLAlchemy models in `backend/models/`. Every table, column, foreign key, and enum must be accurately documented.

**Acceptance Scenarios**:

1. **Given** the walkthrough document exists, **When** a reviewer reads the "Data Model" section, **Then** they see a Mermaid ER diagram covering Users, Projects, Persons, Photos, Scenarios, Segments, VideoClips, and FinalVideos with correct cardinality.
2. **Given** the ER diagram is rendered, **When** a reviewer checks foreign key relationships, **Then** all cascade rules and uniqueness constraints described match the actual model definitions.
3. **Given** enum types are documented, **When** a reviewer reads ProjectStatus and ModerationStatus descriptions, **Then** they see every valid state and understand the allowed transitions.

---

### User Story 3 — Authentication & Authorization Flow (Priority: P2)

As a reviewer, I want a detailed walkthrough of the authentication system — registration, login, Google OAuth, JWT issuance, and route protection — illustrated with a Mermaid sequence diagram — so I can evaluate the security implementation.

**Why this priority**: Auth is a critical security boundary. Understanding it in isolation is valuable for security review.

**Independent Test**: Follow the sequence diagram step-by-step and verify each step matches the actual code in `backend/api/auth.py`, `backend/services/auth_service.py`, and `backend/api/pages.py`.

**Acceptance Scenarios**:

1. **Given** the walkthrough document exists, **When** a reviewer reads the "Authentication Flow" section, **Then** they see a Mermaid sequence diagram covering email/password registration, login, JWT creation, Google OAuth redirect/callback, cookie-based session, and route protection via `get_current_user`.
2. **Given** the sequence diagram shows Google OAuth, **When** a reviewer traces the callback handler, **Then** the diagram accurately reflects user creation/linking logic and cookie setting.

---

### User Story 4 — Photo Upload & Validation Pipeline (Priority: P2)

As a reviewer, I want a walkthrough of the photo upload flow — from multipart request through validation, filename parsing, person grouping, disk storage, and database persistence — with a Mermaid flowchart — so I can verify correct file handling.

**Why this priority**: File upload is a common source of bugs and security issues. A clear flow diagram helps identify potential problems.

**Independent Test**: Trace the flowchart against `backend/api/projects.py` (upload endpoint) and `backend/services/upload_service.py`. Every validation step, branching decision, and storage operation must be present.

**Acceptance Scenarios**:

1. **Given** the walkthrough document exists, **When** a reviewer reads the "Photo Upload" section, **Then** they see a Mermaid flowchart from file receipt through MIME validation, size check, filename parsing (`<person>_<seq>.<ext>`), person record creation, photo count enforcement (max 10), disk write, and DB record creation.
2. **Given** validation failure paths are shown, **When** a reviewer checks errors for invalid MIME type, oversized files, or malformed filenames, **Then** each error response is documented in the diagram.

---

### User Story 5 — AI Content Moderation & Scenario Splitting (Priority: P2)

As a reviewer, I want a walkthrough of how user-submitted scenarios are moderated and split into segments by Google Gemini — covering prompt construction, API call, response parsing, and error handling — with a Mermaid sequence diagram.

**Why this priority**: This is an AI-dependent feature with complex prompt engineering and response parsing that benefits from clear visual documentation.

**Independent Test**: Compare the sequence diagram against `backend/services/moderation_service.py` and `backend/api/scenarios.py`. Verify prompt structure, validation rules (max 15 segments, character manifest), and error paths.

**Acceptance Scenarios**:

1. **Given** the walkthrough document exists, **When** a reviewer reads the "Moderation & Splitting" section, **Then** they see a Mermaid sequence diagram showing: scenario submission → person name extraction → Gemini prompt construction → API call → JSON response parsing → validation → Scenario/Segment record creation.
2. **Given** the moderation content policy is described, **When** a reviewer reads rejection categories, **Then** all categories (violence, sexual content, hate speech, etc.) are listed.

---

### User Story 6 — Video Generation Pipeline (Priority: P1)

As a reviewer, I want a walkthrough of the iterative video generation pipeline — initial image generation, per-segment video clip creation, last-frame extraction, and the chaining mechanism — with a Mermaid flowchart showing the iterative loop — so I can understand the core product feature.

**Why this priority**: This is the platform's core value proposition. Understanding the generation pipeline is essential for any code review.

**Independent Test**: Walk through the flowchart against `backend/services/pipeline_service.py`, `backend/services/image_gen_service.py`, and `backend/services/video_gen_service.py`. Every step, retry logic, and external API call must match.

**Acceptance Scenarios**:

1. **Given** the walkthrough document exists, **When** a reviewer reads the "Video Generation Pipeline" section, **Then** they see a Mermaid flowchart showing: start → generate initial image (fal.ai Qwen) → for each segment: generate video clip (fal.ai LTX Video) → extract last frame (FFmpeg) → use as next input → end.
2. **Given** retry logic is documented, **When** a reviewer reads the error handling section, **Then** they understand that failed clips are retried once (MAX_RETRIES = 1) and the retry mechanism is illustrated.
3. **Given** the style system is documented, **When** a reviewer reads style handling, **Then** both "animation" and "movie_like" prompt prefixes are described.

---

### User Story 7 — API Route Map & Request/Response Schemas (Priority: P3)

As a reviewer, I want a comprehensive reference of all API endpoints grouped by domain — with HTTP methods, paths, auth requirements, request/response schemas — so I can evaluate the API surface.

**Why this priority**: Useful as reference material but less critical than understanding the core flows.

**Independent Test**: Compare every listed endpoint against the actual route files in `backend/api/`. Verify paths, methods, and schema references.

**Acceptance Scenarios**:

1. **Given** the walkthrough document exists, **When** a reviewer reads the "API Reference" section, **Then** every endpoint across auth, projects, scenarios, generation, health, and pages is listed with method, path, auth requirement, and request/response schema names.
2. **Given** the API map includes a Mermaid diagram, **When** rendered, **Then** it shows the route groupings and their connections to underlying services.

---

### User Story 8 — Frontend & Template Architecture (Priority: P3)

As a reviewer, I want a walkthrough of the server-rendered frontend — Jinja2 template inheritance, client-side JavaScript behavior, and how templates interact with API endpoints — so I can understand the full request lifecycle.

**Why this priority**: Important for completeness but secondary to backend architecture understanding.

**Independent Test**: Verify template descriptions against files in `backend/templates/` and `static/js/app.js`.

**Acceptance Scenarios**:

1. **Given** the walkthrough document exists, **When** a reviewer reads the "Frontend Architecture" section, **Then** they see the template inheritance hierarchy (base.html → child templates), and key JS behaviors (file upload drag/drop, filename validation, polling, token management).

---

### User Story 9 — Project Status State Machine (Priority: P2)

As a reviewer, I want a Mermaid state diagram showing all possible project statuses and the transitions between them — so I can verify that status management is correct and complete.

**Why this priority**: The project status drives UI rendering and determines which actions are available. A state diagram is the clearest way to verify correctness.

**Independent Test**: Compare every state and transition in the diagram against `ProjectStatus` enum usage across all route handlers and services.

**Acceptance Scenarios**:

1. **Given** the walkthrough document exists, **When** a reviewer reads the "Project Lifecycle" section, **Then** they see a Mermaid state diagram with states: draft → submitted → moderating → splitting → reviewing → generating → concatenating → completed, plus branching to rejected and failed states.

---

### Edge Cases

- What happens when a walkthrough section references code that has been refactored since the document was written? The document should include a "Last verified against commit" reference.
- How does the document handle features that are partially implemented (e.g., `launch_pipeline()` is a placeholder)? Placeholder/incomplete features should be explicitly marked as such.
- What if a Mermaid diagram becomes too complex to read? Break complex flows into sub-diagrams with cross-references.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The walkthrough document MUST include a high-level architecture diagram (Mermaid) showing all system layers: client browser, static assets, page routes, API routes, services, models, database, and external APIs (fal.ai, Gemini, Google OAuth).
- **FR-002**: The walkthrough MUST include a Mermaid entity-relationship diagram covering all 8 database tables (users, projects, persons, photos, scenarios, segments, video_clips, final_videos) with correct cardinalities and foreign key relationships.
- **FR-003**: The walkthrough MUST document all enum types (VideoStyle, ProjectStatus, ModerationStatus, GenerationStatus, ClipStatus) with every valid value listed.
- **FR-004**: The walkthrough MUST include a Mermaid state diagram for the ProjectStatus lifecycle showing all transitions including error/rejection paths.
- **FR-005**: The walkthrough MUST include a Mermaid sequence diagram for the authentication flow covering email/password registration, email/password login, Google OAuth, JWT issuance, and cookie-based route protection.
- **FR-006**: The walkthrough MUST include a Mermaid flowchart for the photo upload pipeline showing validation gates (MIME type, file size, filename format), person grouping, and storage.
- **FR-007**: The walkthrough MUST include a Mermaid sequence diagram for the AI moderation and scenario splitting flow, covering prompt construction, Gemini API interaction, response parsing, and segment creation.
- **FR-008**: The walkthrough MUST include a Mermaid flowchart for the iterative video generation pipeline showing initial image generation, per-segment video clip creation, last-frame extraction, chaining, and retry logic.
- **FR-009**: The walkthrough MUST provide a complete API endpoint reference table covering all routes across auth, projects, scenarios, generation, health, and pages — including HTTP method, path, authentication requirement, and associated schemas.
- **FR-010**: The walkthrough MUST describe the frontend template inheritance hierarchy (base.html → child templates) and key client-side JavaScript behaviors.
- **FR-011**: The walkthrough MUST describe the configuration system — how environment variables are loaded, grouped, and accessed across the application.
- **FR-012**: The walkthrough MUST describe the database connection management — async engine, session lifecycle, and the `get_db` dependency injection pattern.
- **FR-013**: The walkthrough MUST describe the middleware layer — rate limiting setup and session middleware for OAuth state.
- **FR-014**: The walkthrough MUST describe the logging system — per-session log files, log levels, and format.
- **FR-015**: The walkthrough MUST describe the test infrastructure — fixtures, database isolation strategy, and test organization (unit, integration, contract).
- **FR-016**: The walkthrough MUST describe the migration system — Alembic setup, async runner, and existing migration history.
- **FR-017**: Each Mermaid diagram MUST be syntactically valid and render correctly in standard Mermaid-compatible viewers (GitHub, VS Code Mermaid preview, Mermaid Live Editor).
- **FR-018**: The walkthrough MUST explicitly mark any placeholder or incomplete features (e.g., `launch_pipeline()` background task wiring, empty contract tests directory).
- **FR-019**: The walkthrough MUST include a table of contents with links to each section for quick navigation.
- **FR-020**: Every code file in the backend MUST be referenced at least once in the walkthrough, ensuring complete coverage of the 27 Python backend files.

### Assumptions

- The walkthrough targets developers and reviewers who have general programming knowledge but may not be familiar with the specific tech stack (FastAPI, SQLAlchemy async, fal.ai).
- Mermaid is the preferred diagram format because it is text-based, version-controllable, and renders natively on GitHub and in VS Code.
- The walkthrough is a living document that should be updated when the codebase changes significantly.
- The audience reads English; no localization is required.
- The document will be stored as a Markdown file within the specs directory alongside the feature specification.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new developer can read the walkthrough and correctly describe the end-to-end flow of creating a project and generating a video within 30 minutes, without reading source code.
- **SC-002**: 100% of backend Python files (27 files) are referenced in at least one section of the walkthrough.
- **SC-003**: All Mermaid diagrams (minimum 7: architecture, ER, state machine, auth sequence, upload flowchart, moderation sequence, pipeline flowchart) render correctly in GitHub Markdown preview.
- **SC-004**: A reviewer can identify all API endpoints and their authentication requirements by reading only the API reference section, without consulting source code.
- **SC-005**: The walkthrough accurately reflects the current codebase — no documented behavior contradicts actual implementation.
- **SC-006**: The document loads and renders in under 5 seconds in a standard Markdown viewer, despite containing multiple Mermaid diagrams.
