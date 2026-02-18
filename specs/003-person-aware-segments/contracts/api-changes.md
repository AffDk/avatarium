# API Contract Changes: Person-Aware Segment Splitting

**Date**: 2026-02-18  
**Feature**: 003-person-aware-segments

## Overview

This feature modifies INTERNAL service interfaces only. No public API endpoint signatures change — the `PUT /api/projects/{id}/scenario` request body remains the same. The response gains richer segment descriptions and may optionally expose the `characters` manifest.

## Modified Internal Interface

### `moderate_and_split()`

**Before**:
```python
async def moderate_and_split(scenario_text: str) -> dict[str, Any]:
```

**After**:
```python
async def moderate_and_split(
    scenario_text: str,
    person_names: list[str] | None = None,
) -> dict[str, Any]:
```

**Input changes**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `scenario_text` | `str` | Yes | Scenario text to moderate and split |
| `person_names` | `list[str] \| None` | No (default: None) | Lowercase person names from uploaded photos |

**Output changes**:

When `person_names` is provided and scenario is approved:
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
            "description": "Alice, a tall woman with curly red hair and a green dress, walks into the park.",
            "persons": ["alice"]
        },
        {
            "sequence_number": 2,
            "description": "Alice, the tall redhead in the green dress, waves to Bob, a stocky man with round glasses and a blue denim jacket, who approaches from across the path.",
            "persons": ["alice", "bob"]
        }
    ]
}
```

When `person_names` is `None` or empty (backward compatible):
```json
{
    "approved": true,
    "rejection_reason": null,
    "characters": {},
    "segments": [
        {
            "sequence_number": 1,
            "description": "A person walks into the park.",
            "persons": []
        }
    ]
}
```

When rejected:
```json
{
    "approved": false,
    "rejection_reason": "Content contains explicit violence",
    "characters": {},
    "segments": []
}
```

## Modified Caller: `scenarios.py`

### `submit_scenario()` endpoint

**Change**: Load project persons and pass their names to `moderate_and_split()`.

**Before**:
```python
project = await get_user_project(project_id, current_user.id, db, load_persons=False)
gemini_result = await moderate_and_split(body.text)
```

**After**:
```python
project = await get_user_project(project_id, current_user.id, db, load_persons=True)
person_names = [p.name for p in project.persons] if project.persons else []
gemini_result = await moderate_and_split(body.text, person_names=person_names)
```

## Modified Consumer: `pipeline_service.py`

### `run_pipeline()` usage

**Change**: Use `characters` manifest from moderation result for initial image prompt instead of bare person names.

**Before**:
```python
person_str = ", ".join(person_names) if person_names else ""
initial_prompt = f"{first_segment['description']}. Characters: {person_str}"
```

**After**:
```python
# Characters manifest is now embedded in segment descriptions by the splitting AI.
# The description already contains visual traits, so no manual concatenation needed.
initial_prompt = first_segment['description']
```

## Response Parsing Changes: `parse_gemini_response()`

**Added validations**:
1. If `characters` field present: validate it's a dict with string keys and string values.
2. For each segment: validate `persons` field exists and is a list of strings.
3. Normalize all `persons` entries to lowercase.
4. Filter `persons` entries to only include names from the provided input list (if available).

## No Public API Schema Changes Required

The `SegmentResponse` Pydantic schema currently exposes `id`, `sequence_number`, `description`, `estimated_duration`, `generation_status`. The `persons` data is consumed internally by the pipeline and does not need to be exposed in the REST API response at this time.

If future UI features need to display which persons appear in each segment, a `persons: list[str]` field can be added to `SegmentResponse` as a non-breaking addition.
