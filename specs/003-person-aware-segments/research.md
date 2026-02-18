# Research: Person-Aware Segment Splitting

**Date**: 2026-02-18  
**Feature**: 003-person-aware-segments

## Decision 1: Prompt Structure for Consistent Character Traits

**Decision**: Use "define first, then reference" — instruct the AI to emit a `characters` manifest before `segments` in JSON output, then reuse the exact traits from that manifest in each segment description.

**Rationale**: LLMs are autoregressive — once character descriptions are generated early in the output, they become part of the context window for subsequent tokens. By placing `characters` before `segments` in the JSON, the AI naturally self-references those descriptions. This is the "anchor then propagate" prompt pattern.

**Alternatives considered**:
- Separate API call for character creation, then inject into splitting prompt — more reliable but doubles cost and latency. Rejected per single-call constraint.
- Post-processing to replace character descriptions — fragile and error-prone. Rejected.

## Decision 2: JSON Output Reliability

**Decision**: Use Gemini's `response_mime_type="application/json"` with `response_schema` for structural guarantees, combined with a concrete example in the prompt for content quality guidance.

**Rationale**: Gemini 2.5 Flash supports controlled generation via `GenerationConfig(response_mime_type="application/json", response_schema=...)`. This constrains token sampling to only produce valid JSON matching the schema, eliminating the need for regex-based code-fence stripping. For nested structures (characters dict + segments array with persons arrays), schema enforcement is far more reliable than prompt-only instruction.

**Alternatives considered**:
- Prompt-only JSON instruction (current approach) — works ~90% of the time but still requires code-fence stripping and can produce malformed JSON on complex nested structures. Acceptable as fallback if `response_schema` has SDK issues.
- Pydantic schema via SDK — supported in newer versions, cleaner but ties schema to Python types. Worth considering for future iteration.

**Caveat**: If `additionalProperties` for the characters dict is not cleanly supported by the SDK version in use, fall back to prompt-only with `response_mime_type="application/json"` for at least a valid-JSON guarantee, keeping the existing code-fence stripping as defense-in-depth.

## Decision 3: Gemini 2.5 Flash Adequacy for Persona Consistency

**Decision**: Gemini 2.5 Flash is adequate for ≤5 characters across ≤15 segments. Explicit prompt reinforcement is required to prevent paraphrasing.

**Rationale**: Flash has a 1M-token context window; the full output (characters + 15 segments) is well under 2K tokens. Trait drift from token-distance is not a concern. Flash-tier models prioritize speed but handle simple trait reuse (hair color, clothing) reliably.

**Mitigations**:
- Keep character descriptions short (2–3 traits max) to reduce paraphrasing risk.
- Use high-contrast traits between characters (e.g., "red hair" vs "blonde hair").
- Add explicit instruction: "Use the EXACT wording from the characters manifest — do not paraphrase or add traits."

## Decision 4: Handling Contradictory Traits

**Decision**: Accept the risk of minor paraphrasing drift and mitigate with prompt constraints + post-parse validation (FR-005, FR-010). Do NOT add retry logic initially.

**Known failure modes**:
1. Paraphrasing drift ("curly red hair" → "wavy auburn hair") — most common.
2. Trait omission — later segments use just the name without traits. Benign for `persons` array, degrades image prompts.
3. Trait invention — adds traits not in manifest. Less common.
4. Character bleed — traits swap between similar characters. Rare with ≤5 characters.

**Mitigations**:
- Emit `characters` first in JSON to anchor all segments.
- Explicit "Do NOT add, change, or omit" instruction.
- Post-parse: validate `persons` entries against input names (FR-005/FR-010). Normalize to lowercase.

**Alternatives considered**:
- Retry on inconsistency — adds latency/cost. Reserved as future enhancement.
- Template injection (replace names with traits programmatically) — too rigid, loses narrative quality.

## Decision 5: Backward Compatibility Strategy

**Decision**: The `moderate_and_split()` function signature changes from `(scenario_text: str)` to `(scenario_text: str, person_names: list[str] | None = None)` with a default of `None`. When `person_names` is None or empty, the prompt omits the character section entirely, maintaining backward compatibility.

**Rationale**: The caller (`scenarios.py`) currently passes only `body.text`. Adding an optional parameter preserves the existing API for any callers that don't have person context, while allowing the scenario route to pass person names when available.

**Alternatives considered**:
- Create a new function `moderate_and_split_with_persons()` — unnecessary duplication given a single call site.
- Always require person_names — would break existing callers and tests.

## Decision 6: Segment DB Model Impact

**Decision**: Do NOT add a `persons` column to the Segment DB model. Store the `persons` list only in the returned/transit data. The `characters` manifest is used by the pipeline at generation time and does not need to be persisted separately.

**Rationale**: The `persons` field per segment and `characters` manifest are consumed immediately by the pipeline for image/video generation prompts. Persisting them in the DB would add schema migration complexity with minimal benefit — the segment `description` already contains the person references in natural language. If persistence becomes needed later, it's a simple migration to add a JSON column.

**Alternatives considered**:
- Add `persons_json` TEXT column to Segment model — premature; adds migration overhead that may never be needed.
- Add `characters_json` TEXT column to Scenario model — same reasoning; defer until proven necessary.
