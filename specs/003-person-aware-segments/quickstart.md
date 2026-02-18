# Quickstart: Person-Aware Segment Splitting

**Feature**: 003-person-aware-segments  
**Prerequisites**: Python 3.12+, `uv` installed, `.env` with `GEMINI_API_KEY` set

## What Changed

The moderation/splitting system now accepts person names and produces:
1. **Person-aware segment descriptions** — each segment explicitly names characters with visual traits
2. **A `characters` manifest** — top-level dict mapping person names to visual trait descriptions 
3. **A `persons` array per segment** — structured list of which characters appear in each segment

## Quick Verification

### 1. Run all tests
```bash
uv run pytest -x -q
```
All existing tests should pass. New tests for person-aware splitting are included.

### 2. Manual test via Python REPL
```python
import asyncio
from backend.services.moderation_service import moderate_and_split

result = asyncio.run(moderate_and_split(
    "Alice and Bob meet at a coffee shop. Alice waves. Bob sits down. They talk and laugh.",
    person_names=["alice", "bob"]
))

# Check characters manifest
print(result["characters"])
# → {"alice": "...", "bob": "..."}

# Check segments have persons
for seg in result["segments"]:
    print(f"Segment {seg['sequence_number']}: persons={seg['persons']}")
    print(f"  {seg['description'][:80]}...")
```

### 3. Test backward compatibility (no persons)
```python
result = asyncio.run(moderate_and_split("A cat sits on a windowsill watching birds."))
assert result["characters"] == {}
for seg in result["segments"]:
    assert seg["persons"] == []
```

## Key Files Modified

| File | Change |
|------|--------|
| `backend/services/moderation_service.py` | Updated prompt, function signature, response parsing |
| `backend/api/scenarios.py` | Pass person names to `moderate_and_split()` |
| `backend/services/pipeline_service.py` | Use enriched descriptions (characters in text) |
| `tests/unit/test_moderation_service.py` | New tests for person-aware splitting |

## Architecture Summary

```
Upload photos → Person names extracted (existing)
                    ↓
Submit scenario → moderate_and_split(text, person_names=["alice","bob"])
                    ↓
                  Gemini returns:
                    - characters: {"alice": "tall, red hair", "bob": "short, glasses"}
                    - segments with persons: ["alice"] or ["alice","bob"]
                    - descriptions with visual traits woven in
                    ↓
Pipeline → uses enriched descriptions directly (traits already embedded)
```
