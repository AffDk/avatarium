# Data Model: Avatar Video Generation Pipeline

**Date**: 2026-02-07
**Feature**: 002-avatar-video-pipeline

## Entity Relationship Diagram (Text)

```
User 1──────* Project
Project 1──────* Person
Person 1──────* Photo
Project 1──────1 Scenario
Scenario 1──────* Segment
Project 1──────* VideoClip
Project 1──────0..1 FinalVideo
```

## Entities

### User

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | Unique identifier |
| email | String(255) | Unique, not null | User's email address |
| display_name | String(100) | Not null | Display name |
| hashed_password | String(255) | Nullable | Null for Google-only accounts |
| google_id | String(255) | Nullable, unique | Google OAuth subject ID |
| email_verified | Boolean | Default: false | Whether email is verified |
| terms_accepted_at | DateTime | Nullable | Timestamp of terms acceptance |
| created_at | DateTime | Not null, auto | Account creation timestamp |
| updated_at | DateTime | Not null, auto | Last update timestamp |

**Validation rules**:
- Email must be valid format
- Either `hashed_password` or `google_id` must be non-null (at least one auth method)
- `terms_accepted_at` must be set before accessing any platform features

---

### Project

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | Unique identifier |
| user_id | UUID | FK → User.id, not null | Owner of the project |
| title | String(200) | Not null | Project title |
| video_style | Enum | Not null | "animation" or "movie_like" |
| status | Enum | Not null, default: "draft" | Project lifecycle state |
| estimated_cost | Decimal(6,4) | Nullable | Estimated generation cost |
| actual_cost | Decimal(6,4) | Nullable | Actual generation cost |
| created_at | DateTime | Not null, auto | Creation timestamp |
| updated_at | DateTime | Not null, auto | Last update timestamp |

**Status transitions**:
```
draft → submitted → moderating → splitting → reviewing → generating → concatenating → completed
                  → rejected (from moderating)
                  → failed (from generating or concatenating)
```

**Validation rules**:
- `user_id` enforced on every query (privacy isolation)
- `video_style` must be one of: `animation`, `movie_like`

---

### Person

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | Unique identifier |
| project_id | UUID | FK → Project.id, not null | Parent project |
| name | String(100) | Not null | Derived from filename prefix (e.g., "person1") |
| created_at | DateTime | Not null, auto | Creation timestamp |

**Validation rules**:
- `name` is extracted from the filename prefix (case-insensitive, normalized to lowercase)
- Unique constraint on (`project_id`, `name`)

---

### Photo

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | Unique identifier |
| person_id | UUID | FK → Person.id, not null | Parent person |
| original_filename | String(255) | Not null | Original uploaded filename |
| sequence_number | Integer | Not null | Sequence from filename (e.g., 1, 2, 3) |
| file_path | String(500) | Not null | Server-side storage path |
| file_size | Integer | Not null | Size in bytes |
| mime_type | String(50) | Not null | MIME type (image/jpeg, image/png, image/webp) |
| created_at | DateTime | Not null, auto | Upload timestamp |

**Validation rules**:
- `file_size` ≤ 10,485,760 (10 MB)
- `mime_type` must be one of: `image/jpeg`, `image/png`, `image/webp`
- `sequence_number` ≥ 1
- Unique constraint on (`person_id`, `sequence_number`)
- Maximum 10 photos per person

---

### Scenario

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | Unique identifier |
| project_id | UUID | FK → Project.id, unique, not null | One scenario per project |
| text | Text | Not null | Raw scenario text |
| moderation_status | Enum | Not null, default: "pending" | Moderation state |
| rejection_reason | Text | Nullable | Explanation if rejected |
| created_at | DateTime | Not null, auto | Submission timestamp |
| moderated_at | DateTime | Nullable | When moderation completed |

**Status values**: `pending`, `approved`, `rejected`

**Validation rules**:
- `text` length ≥ 1, ≤ 10,000 characters
- One-to-one relationship with Project

---

### Segment

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | Unique identifier |
| scenario_id | UUID | FK → Scenario.id, not null | Parent scenario |
| sequence_number | Integer | Not null | Order in the video (1-based) |
| description | Text | Not null | Scene description for this segment |
| estimated_duration | Float | Default: 5.0 | Target duration in seconds |
| generation_status | Enum | Not null, default: "pending" | Generation state |
| created_at | DateTime | Not null, auto | Creation timestamp |

**Status values**: `pending`, `generating`, `completed`, `failed`

**Validation rules**:
- `sequence_number` ≥ 1, ≤ 15
- Unique constraint on (`scenario_id`, `sequence_number`)

---

### VideoClip

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | Unique identifier |
| project_id | UUID | FK → Project.id, not null | Parent project |
| segment_id | UUID | FK → Segment.id, not null | Corresponding segment |
| sequence_number | Integer | Not null | Order matching segment |
| input_image_path | String(500) | Not null | Path to the input image (generated or last-frame) |
| video_file_path | String(500) | Nullable | Path to the generated video clip |
| last_frame_path | String(500) | Nullable | Path to extracted last frame |
| duration | Float | Nullable | Actual duration in seconds |
| generation_cost | Decimal(6,4) | Nullable | Actual cost of this clip |
| status | Enum | Not null, default: "pending" | Generation state |
| retry_count | Integer | Default: 0 | Number of retry attempts |
| error_message | Text | Nullable | Error details if failed |
| created_at | DateTime | Not null, auto | Creation timestamp |
| completed_at | DateTime | Nullable | Completion timestamp |

**Status values**: `pending`, `generating`, `completed`, `failed`

**Validation rules**:
- `retry_count` ≤ 1 (one automatic retry)
- `sequence_number` matches corresponding segment

---

### FinalVideo

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | Unique identifier |
| project_id | UUID | FK → Project.id, unique, not null | One final video per project |
| file_path | String(500) | Not null | Path to concatenated video |
| total_duration | Float | Not null | Total duration in seconds |
| total_cost | Decimal(6,4) | Not null | Sum of all generation costs |
| file_size | Integer | Not null | Size in bytes |
| created_at | DateTime | Not null, auto | Creation timestamp |

**Validation rules**:
- One-to-one relationship with Project
- Only created when all clips are in `completed` status

---

## Design Note: Generated Image

The spec's Key Entities section lists "Generated Image" as a conceptual entity. In the data model, this is **not a separate table**. The generated image for the first segment is tracked via `VideoClip.input_image_path` and stored on disk at `generated/{user_id}/{project_id}/images/`. Subsequent segments use the last frame of the previous clip (`VideoClip.last_frame_path`) as their input image. This avoids an extra join and simplifies the pipeline query pattern.
