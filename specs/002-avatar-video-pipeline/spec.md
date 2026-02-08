# Feature Specification: Avatar Video Generation Pipeline

**Feature Branch**: `002-avatar-video-pipeline`  
**Created**: 2026-02-07  
**Status**: Draft  
**Input**: User description: "AI avatar video generation pipeline — user uploads named images per person, provides a scenario, selects video style; system moderates scenario via LLM, splits it into ≤15 segments (~5 sec each), iteratively generates images and video clips per segment, and concatenates all clips into one final video. Optimize for absolute minimum cost."

## User Scenarios & Testing *(mandatory)*

### User Story 1 – Upload Named Images & Provide Scenario (Priority: P1)

An authenticated user starts a new video project. They upload reference photos of one or more people, following a strict naming convention: `person1_1.jpg`, `person1_2.jpg`, `person2_1.jpg`, etc. The first part of the filename identifies the person (e.g., `person1`), and the second part is a sequence number for that person's photos. The user then writes a scenario describing how these persons interact in the video. Finally, the user selects a video style — either "Animation" (cartoon/stylized look) or "Movie-like" (realistic/cinematic look).

**Why this priority**: This is the entry point for the entire pipeline. Without image uploads, naming, scenario, and style selection, no video can be generated.

**Independent Test**: Can be fully tested by uploading images with correct and incorrect naming, writing a scenario referencing the uploaded persons, selecting a style, and verifying validation feedback at each step.

**Acceptance Scenarios**:

1. **Given** an authenticated user on the "New Project" page, **When** they upload files named `person1_1.jpg`, `person1_2.jpg`, and `person2_1.jpg`, **Then** the system correctly groups them into two persons: "person1" (2 photos) and "person2" (1 photo).
2. **Given** a user uploading a file with an invalid naming format (e.g., `myphoto.jpg`), **When** the upload is submitted, **Then** the system rejects it with a clear message explaining the required naming convention: `<personName>_<number>.<extension>`.
3. **Given** uploaded photos and a text scenario, **When** the scenario references persons not present in the uploads (e.g., mentions "person3" but only person1 and person2 were uploaded), **Then** the system warns the user about the mismatch.
4. **Given** all inputs are valid, **When** the user selects "Animation" or "Movie-like" and clicks submit, **Then** the project is accepted and moves to the processing pipeline.

---

### User Story 2 – Scenario Moderation & Splitting (Priority: P1)

After submission, the system first checks the scenario against the content policy (no profanity, sexuality, violence, heinous content). If approved, the system intelligently splits the scenario into smaller segments, each suitable for a ~5-second video clip. The total number of segments must not exceed 15 (yielding a maximum video length of ~75 seconds). If the scenario is too long or complex to fit in 15 segments, the system asks the user to shorten it. These two operations (moderation + splitting) should be combined into a single processing step where possible.

**Why this priority**: Moderation must happen before any expensive generation work begins. Splitting is the prerequisite for the iterative generation pipeline.

**Independent Test**: Can be fully tested by submitting scenarios of various lengths and content types, verifying moderation accepts/rejects correctly, and verifying the split produces a reasonable number of coherent segments.

**Acceptance Scenarios**:

1. **Given** a user submits a clean scenario describing a birthday party, **When** moderation runs, **Then** the scenario is approved and split into segments (e.g., 5–10 segments depending on complexity).
2. **Given** a user submits a scenario containing violent or sexual content, **When** moderation runs, **Then** the scenario is rejected with a clear explanation before any generation begins, and no cost is incurred for generation services.
3. **Given** a long and complex scenario, **When** the system attempts to split it, **Then** if it would require more than 15 segments, the system rejects it with a message asking the user to simplify or shorten the scenario.
4. **Given** a moderation-and-split operation completes successfully, **When** the user views the result, **Then** they can see the list of scenario segments and approve or edit them before generation starts.

---

### User Story 3 – Iterative Video Generation Pipeline (Priority: P1)

Once segments are approved, the system begins the generation pipeline:
1. For the first segment: generate a still image based on the uploaded person photos and the first segment's description, in the selected style (animation or realistic).
2. Convert that generated image into a ~5-second video clip using the segment description as guidance. Audio is disabled to minimize cost.
3. Extract the last frame of the generated video clip.
4. For each subsequent segment: use the last frame from the previous clip plus the next segment's description to generate the next video clip.
5. Repeat until all segments have been processed.

The user can see progress as each clip completes. If a clip fails, the system retries once before reporting the failure.

**Why this priority**: This is the core value proposition — the actual video generation engine. Without it, there is no product.

**Independent Test**: Can be fully tested by submitting a small project (2–3 segments), verifying each clip is generated sequentially, confirming last-frame extraction works, and checking that the style (animation vs. movie-like) is reflected in the output.

**Acceptance Scenarios**:

1. **Given** an approved scenario with 5 segments and "Animation" style selected, **When** generation begins, **Then** the system generates a stylized/cartoon image from the uploaded photos and first segment, then produces a ~5-second video from it.
2. **Given** the first clip has been generated, **When** the pipeline proceeds to segment 2, **Then** the system extracts the last frame of clip 1, uses it with segment 2's description to generate clip 2, maintaining visual continuity.
3. **Given** all 5 clips have been generated, **When** the pipeline completes, **Then** progress shows 5/5 segments completed and each clip is individually previewable.
4. **Given** a clip generation fails on the first attempt, **When** the system retries, **Then** if the retry succeeds the pipeline continues; if it fails again the user is notified and can retry the failed segment manually.
5. **Given** "Movie-like" style is selected, **When** images and videos are generated, **Then** the output has a realistic/cinematic look rather than a cartoon style.

---

### User Story 4 – Video Concatenation & Final Output (Priority: P2)

After all clips are generated, the system concatenates them in order into a single continuous video. The final video is made available for preview, download, and is stored in the user's private dashboard.

**Why this priority**: This completes the user's journey — they receive one cohesive video rather than fragmented clips. It depends on all clips being generated first.

**Independent Test**: Can be fully tested by generating a multi-segment project and verifying the final concatenated video plays smoothly, is downloadable, and appears in the dashboard.

**Acceptance Scenarios**:

1. **Given** all clips for a project are successfully generated, **When** concatenation runs, **Then** a single video file is produced containing all clips in sequential order.
2. **Given** a concatenated video is ready, **When** the user views it on their dashboard, **Then** they can play it inline and download it to their device.
3. **Given** clips were generated at ~5 seconds each with 10 segments, **When** the final video is assembled, **Then** it is approximately 50 seconds long.
4. **Given** a user on a mobile device, **When** they view the final video, **Then** the video player is responsive and fully functional.

---

### User Story 5 – Cost-Optimized Processing (Priority: P2)

The system uses the most cost-effective AI models available for each step of the pipeline, while maintaining acceptable quality. Audio generation is disabled by default to reduce per-clip cost. The system selects lower-resolution options where appropriate. Users see an estimated cost before starting generation.

**Why this priority**: Cost efficiency is critical for the business model. Without it, per-project costs could make the service unsustainable.

**Independent Test**: Can be fully tested by generating a project and verifying the cost estimate is shown, the actual cost stays within the estimate, and audio is not generated unless explicitly requested.

**Acceptance Scenarios**:

1. **Given** a user is about to submit a project with 10 segments, **When** they review before submitting, **Then** they see an estimated generation cost based on the number of segments.
2. **Given** audio is disabled by default, **When** a video clip is generated, **Then** it contains only the visual track with no audio, and the cost is lower than the audio-enabled option.
3. **Given** the system selects models for generation, **When** a project completes, **Then** the total cost per project stays within the estimated range shown to the user.

---

### User Story 6 – Segment Review & Editing (Priority: P3)

Before generation begins, the user can review the scenario segments produced by the splitting step. They can edit individual segment descriptions, reorder segments, or remove segments. After editing, they re-confirm and proceed to generation.

**Why this priority**: Gives users creative control over the pipeline, but the core flow works without it.

**Independent Test**: Can be fully tested by splitting a scenario, editing a segment's text, removing a segment, and confirming the generation uses the modified segment list.

**Acceptance Scenarios**:

1. **Given** a scenario has been split into 8 segments, **When** the user views the segment list, **Then** each segment is displayed with its description and a sequence number.
2. **Given** the user edits segment 3's description, **When** they confirm and start generation, **Then** the pipeline uses the edited description for segment 3.
3. **Given** the user removes segment 5, **When** generation runs, **Then** only 7 clips are produced and the remaining segments are renumbered correctly.

---

### Edge Cases

- What happens when a user uploads only one photo per person? Is that sufficient for generation? → **MVP: Yes, 1 photo is sufficient. No minimum enforced.**
- How does the system handle a scenario that is only one sentence long (produces only 1 segment)? → **MVP: Valid — produces 1 clip, then concatenates to a single-clip video.**
- What happens if the last-frame extraction fails or produces a corrupted image? → **MVP: Treated as clip failure; triggers 1 retry per FR-024.**
- How does the system handle generation when fal.ai rate limits are hit or the service is temporarily down? → *Deferred to post-MVP.*
- What happens if the user closes their browser mid-generation? Can they resume later? → *Deferred to post-MVP. Pipeline runs server-side; user can check status on return.*
- How does the system handle naming like `PERSON1_1.JPG` (uppercase) or `person1_01.jpg` (zero-padded numbers)? → **MVP: FR-003 covers case-insensitivity. Zero-padded numbers (01→01) are parsed as integers.**
- What if the concatenated video exceeds a maximum playable file size for mobile devices? → *Deferred to post-MVP. 15 segments × 5s @ 480p unlikely to exceed mobile limits.*
- What happens if the LLM moderation service is unavailable? Does the project queue or fail? → *Deferred to post-MVP. MVP: returns 502/503 error.*
- How does the system handle scenarios written in languages other than English? → *Deferred to post-MVP. MVP: English only; non-English may produce unpredictable results.*

> **Deferral Policy**: Items marked *Deferred to post-MVP* will be tracked as future enhancement issues after initial launch.

## Requirements *(mandatory)*

### Functional Requirements

#### Image Upload & Naming

- **FR-001**: System MUST require uploaded image files to follow the naming convention `<personName>_<sequenceNumber>.<extension>` (e.g., `person1_1.jpg`, `person1_2.png`).
- **FR-002**: System MUST parse filenames to automatically group photos by person name.
- **FR-003**: System MUST accept the naming convention case-insensitively (e.g., `Person1_1.JPG` is treated the same as `person1_1.jpg`).
- **FR-004**: System MUST reject files that do not match the naming convention with a clear error message showing the expected format.
- **FR-005**: System MUST enforce the same file-size and format constraints defined in the platform spec (max 10 MB per photo; JPEG, PNG, WebP formats).

#### Scenario Input

- **FR-006**: System MUST provide a text area for users to write a video scenario describing how the named persons interact.
- **FR-007**: System MUST support scenarios up to 10,000 characters in length.
- **FR-008**: System MUST validate person references in both directions: (a) warn if an uploaded person name is not mentioned in the scenario, and (b) warn if the scenario references a person name not present in the uploads.

#### Video Style Selection

- **FR-009**: System MUST offer at least two style options: "Animation" (stylized/cartoon) and "Movie-like" (realistic/cinematic).
- **FR-010**: System MUST pass the selected style as a directive to both the image generation and video generation steps.

#### Content Moderation

- **FR-011**: System MUST screen every scenario against content policies (no heinous, profane, pornographic, sexual, or violent content) using an LLM-based moderation service before any generation begins.
- **FR-012**: System MUST reject prohibited scenarios with a clear explanation and not incur any generation costs.
- **FR-013**: System MUST combine moderation and scenario splitting into a single processing step where technically feasible, to reduce latency and cost.

#### Scenario Splitting

- **FR-014**: System MUST split an approved scenario into discrete segments, each representing approximately 5 seconds of video content.
- **FR-015**: System MUST NOT produce more than 15 segments from any single scenario (maximum ~75 seconds of final video).
- **FR-016**: System MUST reject scenarios that require more than 15 segments and prompt the user to simplify.
- **FR-017**: System MUST present the resulting segments to the user for review before generation begins.

#### Iterative Generation Pipeline

- **FR-018**: For the first segment, system MUST generate a still image by constructing a text prompt that incorporates the uploaded person names and the segment description in the selected visual style. (Note: the chosen model, Qwen Image, is text-to-image; person names from uploads are included in the prompt rather than raw photos.)
- **FR-019**: System MUST convert the generated image into a ~5-second video clip guided by the segment description.
  > **Duration tolerance**: Target 5 seconds per clip; acceptable range 3–7 seconds. Actual duration is model-dependent and varies with fal.ai output.
- **FR-020**: System MUST extract the last frame of each generated video clip for use as the starting image of the next clip.
- **FR-021**: For each subsequent segment, system MUST generate the next video clip using the last frame from the previous clip and the current segment description.
- **FR-022**: System MUST disable audio generation by default to minimize per-clip cost.
- **FR-023**: System MUST display progress to the user as each clip completes (e.g., "Generating clip 3 of 10").
- **FR-024**: System MUST retry a failed clip generation once automatically before reporting failure to the user.

#### Video Concatenation

- **FR-025**: System MUST concatenate all generated clips in order into a single continuous video file after all clips are complete.
- **FR-026**: System MUST make the final video available for inline preview, playback, and download. The video player MUST be responsive and functional on mobile viewports (320px+).
- **FR-026a**: System SHOULD allow users to delete an individual generated video without requiring full project deletion. Project deletion MUST cascade-delete all associated videos. Constitution: "Users can view, replay, download, and delete their generated videos."

#### Cost Optimization

- **FR-027**: System MUST use the lowest-cost AI models available that meet minimum quality requirements for each pipeline step (image generation, video generation).
- **FR-028**: System MUST display an estimated cost to the user before generation starts, based on the number of segments.
- **FR-029**: System MUST default to 480p resolution (854×480) for video generation to minimize cost while maintaining acceptable visual quality.

#### Segment Review (Optional Enhancement)

- **FR-030**: System SHOULD allow users to edit individual segment descriptions before generation.
- **FR-031**: System SHOULD allow users to remove or reorder segments before generation.

### Key Entities

- **Project**: A user's video creation workspace. Contains uploaded person images, a scenario, a selected style, and generated outputs. Owned by a single user.
- **Person**: A named individual extracted from file naming conventions. Key attributes: name (derived from filename prefix), collection of reference photos.
- **Scenario**: The user-provided text describing the video. Key attributes: raw text, moderation status (Pending, Approved, Rejected), rejection reason.
- **Segment**: A portion of the scenario produced by the splitting step. Key attributes: sequence number, description text, estimated duration (~5 seconds), generation status.
- **Generated Image**: A still image produced for the first segment. Key attributes: source person photos, segment description, visual style, file reference.
- **Video Clip**: A ~5-second video generated from an image and segment description. Key attributes: sequence number, starting image (generated or last-frame), segment reference, generation status, file reference.
- **Final Video**: The concatenated output of all clips. Key attributes: total duration, file reference, creation date, download URL.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can go from image upload to final video delivery in under 20 minutes for a 10-segment project (excluding generation queue wait time).
- **SC-002**: 100% of scenarios containing clearly prohibited content are rejected before any generation cost is incurred.
- **SC-003**: The iterative pipeline maintains visual continuity — the first frame of clip N+1 visually matches the last frame of clip N in 90%+ of generated projects.
- **SC-004**: Total generation cost per project does not exceed $1.00 for a typical 10-segment project at the lowest cost tier.
- **SC-005**: The file naming convention is correctly parsed and validated for 100% of uploads, with clear error messages for invalid names.
- **SC-006**: The scenario splitting produces coherent, self-contained segment descriptions that each represent a distinct ~5-second scene.
- **SC-007**: 95% of generation pipeline runs complete without requiring manual retry of any segment.
- **SC-008**: Final concatenated video plays smoothly without visible glitches or gaps between clips on both desktop and mobile.
- **SC-009**: Users can preview the segment list and understand what each segment will depict before committing to generation.
- **SC-010**: The pipeline works end-to-end for both "Animation" and "Movie-like" styles, with visually distinct outputs per style.

## Assumptions

- The image-to-video generation service (fal.ai) provides models capable of accepting a reference image + text prompt to produce a ~5-second video clip.
- The LLM service (e.g., Google Gemini) can reliably moderate content and split scenarios in a single API call.
- Extracting the last frame of a generated video clip is technically straightforward (standard video processing operation).
- The naming convention `<personName>_<sequenceNumber>.<extension>` is sufficiently intuitive for users with brief instructions.
- A maximum of 15 segments (~75 seconds of video) is a reasonable cap for the initial release.
- Disabling audio reduces per-clip generation cost significantly.
- Users are willing to wait several minutes for the iterative pipeline to complete (it is not real-time).
- The cheapest viable models at time of development are approximately: ~$0.02 per generated image, ~$0.04 per ~5-second video clip — yielding ~$0.62 total for a 15-segment project.
- Video concatenation can be done server-side using standard video processing without a paid external service.
- The platform may add audio generation as an optional paid upgrade in a future release.

## Appendix: API Setup Instructions & Cost Analysis

> **Note**: This section provides implementation guidance for the development team. It is not part of the business specification.

### Recommended Models (Minimum Cost)

| Pipeline Step | Recommended Service | Model | Cost |
|---|---|---|---|
| Content Moderation + Scenario Splitting | Google Gemini | Gemini 2.0 Flash | Free tier: 15 RPM / 1M tokens/day; Paid: ~$0.10 per 1M input tokens |
| Image Generation (text-to-image with reference) | fal.ai | Qwen Image (`fal-ai/qwen-image`) | ~$0.02 per 1MP image |
| Video Generation (image-to-video) | fal.ai | LTX Video 13B Distilled (`fal-ai/ltx-video-13b-distilled/image-to-video`) | ~$0.04 per video clip (~5 sec) |
| Video Concatenation | Server-side | FFmpeg (free, open-source) | $0.00 |

### Cost Estimate Per Project

| Segments | Image Gen (1×) | Video Gen (N×) | LLM Calls | Total |
|---|---|---|---|---|
| 5 segments | $0.02 | $0.20 | ~$0.001 | **~$0.22** |
| 10 segments | $0.02 | $0.40 | ~$0.001 | **~$0.42** |
| 15 segments (max) | $0.02 | $0.60 | ~$0.001 | **~$0.62** |

### How to Get API Keys

#### fal.ai (Image & Video Generation)
1. Go to [https://fal.ai](https://fal.ai) and create an account (or sign in with GitHub/Google).
2. Navigate to [https://fal.ai/dashboard/keys](https://fal.ai/dashboard/keys).
3. Click "Create Key" and copy the generated API key.
4. Store the key in your environment variables as `FAL_KEY` — **never commit it to source code**.
5. fal.ai uses pay-per-use billing; add a payment method in Dashboard → Billing.

#### Google Gemini (LLM for Moderation & Splitting)
1. Go to [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey).
2. Sign in with your Google account.
3. Click "Create API Key" and select or create a Google Cloud project.
4. Copy the generated API key.
5. Store the key in your environment variables as `GEMINI_API_KEY` — **never commit it to source code**.
6. The free tier includes 15 requests per minute and 1 million tokens per day — sufficient for development and low-volume production.
7. For higher volume, enable billing in your Google Cloud project.

### Alternative Video Models (Cost Comparison)

| Model | ID on fal.ai | Cost | Notes |
|---|---|---|---|
| **LTX Video 13B Distilled** ⭐ | `fal-ai/ltx-video-13b-distilled/image-to-video` | **$0.04/video** | Cheapest. Fixed price per clip. Best for budget. |
| Wan 2.2 A14B | `fal-ai/wan/v2.2-a14b/image-to-video` | $0.04–$0.08/sec | Better quality; 480p=$0.04/s, 720p=$0.08/s. 5 sec = $0.20–$0.40. |
| Wan 2.5 | `fal-ai/wan/v2.5` | $0.05/sec | Higher quality. 5 sec = $0.25. |
| Kling 2.5 Turbo Pro | `fal-ai/kling-video/v2.5-turbo/pro/image-to-video` | $0.07/sec | Premium quality. 5 sec = $0.35. |

**Recommendation**: Start with **LTX Video 13B Distilled** ($0.04/clip flat rate) for minimum cost. If quality is insufficient, upgrade to **Wan 2.2 A14B at 480p** ($0.20/clip) as the next cheapest option.
