# Avatarium Constitution

## Core Principles

### I. Privacy-First Architecture
All user data (photos, scenarios, generated videos) is strictly isolated per user. No user can ever view, access, or discover another user's content. Every data-access endpoint enforces ownership verification. User data is never exposed in public URLs, search indices, or shared storage without access controls.

### II. Content Safety
Every user-submitted scenario is screened for prohibited content (heinous, profane, pornographic, sexual, violent) before any processing begins. The system errs on the side of caution for borderline content. Content moderation cannot be bypassed or skipped.

### III. Security by Default
No API keys, credentials, or secrets are ever committed to version control or stored in configuration files within the repository. All sensitive configuration uses environment variables or a secure secrets management service. HTTPS is enforced for all communications. Rate limiting is applied to prevent abuse. All security-relevant events are logged.

### IV. Responsive & Accessible Design
The platform must function correctly on both desktop (1024px+ viewport) and mobile (320px+ viewport) devices. All user flows must be completable on any supported device. Ad placements must never obstruct core functionality.

### V. Test-First Development (NON-NEGOTIABLE)
TDD is mandatory: tests are written first, then approved, then must fail, then implementation proceeds. Red-Green-Refactor cycle is strictly enforced. Every functional requirement must have corresponding automated tests. Content moderation, access control, and file validation must have comprehensive test coverage.

### VI. Deployment Readiness
The application is structured for deployment on external web-accessible servers from day one. Environment-specific configuration is separated from application code. Health-check endpoints are provided. Deployment to a new environment must be achievable using documented steps in under 30 minutes.

### VII. Professional Standards
Follow industry-standard software development practices: version control, code review, meaningful commit messages, documentation, and clean architecture. Code must be maintainable, modular, and well-documented.

## Authentication & User Management

- Email/password registration and Google OAuth are both supported authentication methods.
- Accounts with the same email address across authentication methods are linked to prevent duplicates.
- Email verification is required for email/password registrations.
- Terms of Use must be presented and accepted before any platform features are accessible.
- Terms acceptance is recorded with a timestamp and not re-prompted unless terms are updated.
- Unauthenticated visitors can only see the landing/sign-in page.

## Upload & Content Constraints

- Accepted photo formats: JPEG, PNG, WebP only.
- Maximum file size: 10 MB per individual photo.
- Maximum photos per person: 10 per project.
- File type and size are validated before upload acceptance.
- Scenarios must pass content moderation before being accepted for processing.

## Video Generation

- At least two video styles are supported: "Animation" (stylized/cartoon) and "Movie-like" (realistic/cinematic).
- Video generation is asynchronous; users receive status updates.
- Users can view, replay, download, and delete their generated videos.
- Project deletion permanently removes all associated data (photos, scenario, video).

## Ad Integration

- The interface includes designated ad placement zones (sidebar, banner, interstitial).
- Ad zones are clearly separated from application content.
- Ad loading failures are handled gracefully without breaking the user interface.
- Ad placements adapt to device context (desktop vs. mobile).

## Development Workflow

- All PRs and code reviews must verify compliance with this constitution.
- Security-sensitive changes (authentication, authorization, data access) require additional scrutiny.
- No feature is shipped without passing all automated tests.
- Complexity must be justified; prefer simple, maintainable solutions (YAGNI).

## Governance

This constitution supersedes all other practices for the Avatarium project. Amendments require documentation, team approval, and a migration plan for existing code.

**Version**: 1.0.0 | **Ratified**: 2026-02-07 | **Last Amended**: 2026-02-07
