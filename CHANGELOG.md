# Changelog

All notable changes to Scrask are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.1.0] - 2026-05-25

### Added

- **Per-field confidence scoring.** Each extracted field (`title`, `date`,
  `time`, `location`, `participants`, `description`, `priority`, etc.) now
  carries its own 0.0-1.0 confidence score in a new `confidences{}` map per
  item. Replaces the single-confidence-per-item model.
- **Two top-level decision confidences.** `actionable_confidence` (is this
  screenshot about an event or task at all?) at the result level, and
  `type_confidence` (calendar event or task list?) per item.
- **`clarifications[]` array on each item.** Pre-formatted, targeted
  clarification questions the bot asks the user when a field is missing or
  low-confidence. Example: `"What time is dinner with Priya?"` instead of a
  generic `"is this right?"` prompt.
- **`needs_actionable_confirmation` flag** at the result level. When the
  parser is unsure the screenshot is actionable at all, the bot asks before
  dispatching.
- **`participants[]` field.** Names extracted when visible. Never invented.
- **Three new threshold constants** (`ACTIONABLE_THRESHOLD`,
  `TYPE_THRESHOLD`, `FIELD_THRESHOLD`, all 0.70) with matching CLI flags
  (`--actionable-threshold`, `--type-threshold`, `--field-threshold`).
- **New documentation:**
  - `docs/ARCHITECTURE_OVERVIEW.md` — how Scrask is built, written for both
    technical and non-technical readers.
  - `docs/decision-flow.md` — Mermaid flowcharts of the parser and bot
    decision flow, plus the threshold reference table.
  - `docs/decision-flow.html` — interactive version of the same with
    clickable nodes (detail popups for every decision and threshold).
  - `docs/example-walkthrough.md` — a concrete USER ↔ BOT ↔ PARSER
    transcript.

### Changed

- **`shape_intent` rewritten** to build the clarifications list by walking
  mandatory fields per item type. `needs_confirmation` is now derived from
  the presence of outstanding clarifications, not a single threshold
  comparison.
- **Gemini → Claude auto-fallback** triggers on the worst per-field score
  across all items, not a synthetic per-item number. Finer-grained signal,
  catches cases where the model is broadly confident but missed a single
  critical field.
- **`format_summary`** renders clarifications as a bullet list with
  targeted questions, leads with the actionable-gate prompt when relevant.
- **Docs sweep:** `README.md`, `SKILL.md`, and
  `.github/copilot-instructions.md` rewritten to reflect the new schema and
  flow. Removed lingering Scrask v3 references (direct Google Calendar
  writes, `--dry-run`, `GOOGLE_CREDENTIALS`, and several functions that no
  longer exist).

### Compatibility

- **Backward compatible.** Items in the legacy single-confidence schema (no
  `confidences{}` block) still route correctly via the legacy
  `DEFAULT_CONFIDENCE_THRESHOLD` (0.75) gate. Anything reading
  `item["confidence"]` still works — synthesized as
  `min(confidences.values())` when not directly provided by the model.

## [4.0.0]

### Changed

- **Refactored from direct Google Calendar / Tasks writes into a
  parse-and-delegate skill.** Scrask now emits structured intent JSON and
  the OpenClaw agent delegates writes to whichever destination skill the
  user has installed (`calctl`, `accli`, `apple-calendar`,
  `brainz-calendar`, `gcal-pro`, `apple-reminders`, `things-mac`, `notion`,
  etc.).
- **Removed direct Google API dependencies.** No `GOOGLE_CREDENTIALS`, no
  service-account JSON, no Calendar / Tasks client construction inside
  Scrask.

### Added

- **Provider routing:** `auto` (Gemini first, Claude fallback when needed),
  `gemini` (Gemini only), `claude` (Claude only).
- **`screenshot_summary`, `end_date`, `source_type`** surfaced in the parse
  output for downstream destination skills.

## [3.x] - prior

Direct integration with Google Calendar and Google Tasks via service-account
credentials. Superseded by the v4 parse-and-delegate architecture.
