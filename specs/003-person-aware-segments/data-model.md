# Data Model: Person-Aware Segment Splitting

**Date**: 2026-02-18  
**Feature**: 003-person-aware-segments

## Overview

This feature does NOT introduce new database entities or schema migrations. It modifies the **transit data structures** (prompt input → AI response → pipeline consumption) to include person information. The existing `Person`, `Segment`, and `Scenario` models remain unchanged.

## Existing Entities (unchanged)

### Person
- **Table**: `persons`
- **Fields**: `id` (UUID PK), `project_id` (FK → projects), `name` (String, unique per project), `created_at`
- **Relationships**: belongs to Project, has many Photos
- **Relevance**: The `name` field is the source of person names passed to the splitting prompt.

### Segment
- **Table**: `segments`
- **Fields**: `id` (UUID PK), `scenario_id` (FK → scenarios), `sequence_number` (int), `description` (text), `estimated_duration` (float), `generation_status` (enum)
- **Relationships**: belongs to Scenario
- **Note**: The `description` field will now contain person-aware text with visual traits (no schema change — just richer content from the AI).

### Scenario
- **Table**: `scenarios`
- **Fields**: `id`, `project_id`, `text`, `moderation_status`, `rejection_reason`, `created_at`, `moderated_at`
- **Relationships**: belongs to Project, has many Segments

## Modified Transit Data Structures

### Moderation/Splitting Input

**Before** (current):
```
moderate_and_split(scenario_text: str) → dict
```

**After**:
```
moderate_and_split(scenario_text: str, person_names: list[str] | None = None) → dict
```

The `person_names` parameter provides the list of lowercase character names from uploaded photos.

### Moderation/Splitting Response

**Before** (current):
```json
{
    "approved": true,
    "rejection_reason": null,
    "segments": [
        {"sequence_number": 1, "description": "Scene description..."}
    ]
}
```

**After**:
```json
{
    "approved": true,
    "rejection_reason": null,
    "characters": {
        "alice": "tall woman with curly red hair and a green dress",
        "bob": "stocky man with round glasses and a blue denim jacket"
    },
    "segments": [
        {
            "sequence_number": 1,
            "description": "Alice, a tall woman with curly red hair and a green dress, stands at the doorway greeting Bob, a stocky man with round glasses and a blue denim jacket.",
            "persons": ["alice"]
        }
    ]
}
```

**New fields**:
| Field | Type | Location | Description |
|-------|------|----------|-------------|
| `characters` | `dict[str, str]` | Top-level response | Maps each person name → short visual trait description |
| `persons` | `list[str]` | Per segment | List of person names who appear in that segment |

**Rules**:
- `characters` is present when `approved=true` and `person_names` was provided with ≥1 entry
- `characters` keys must match the input `person_names` (case-insensitive, stored lowercase)
- `persons` entries must be a subset of input `person_names`
- When `approved=false`, `characters` is an empty dict and `segments` is an empty array
- When no `person_names` provided, `characters` is an empty dict and `persons` per segment is an empty array

### Validation Rules

1. `characters` must be a dict with string keys and string values
2. `characters` must contain an entry for every name in `person_names` (when approved)
3. Each segment's `persons` must be a list of strings
4. Each entry in `persons` must exist in the input `person_names` list (case-insensitive)
5. `persons` entries are normalized to lowercase

## State Transitions

No state transition changes. The existing flow remains:

```
Upload photos → Persons created (existing)
                    ↓
Submit scenario → moderate_and_split(text, person_names) → approved/rejected (modified)
                    ↓
If approved → Segments created with person-aware descriptions (modified content)
                    ↓
Pipeline → run_pipeline(segments, style, output_dir, person_names) → uses characters manifest for initial_prompt (modified)
```
