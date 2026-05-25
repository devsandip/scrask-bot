# Scrask Bot — Worklog

## 2026-05-25 — Per-field confidence + targeted clarifications

**Did:**
- Reworked the parser output schema: per-field `confidences{}`, `type_confidence`, top-level `actionable_confidence`, and a new `participants[]` field. The legacy single `confidence` is now derived from `min(confidences.values())` for backward compat.
- Rewrote `shape_intent` to build a `clarifications[]` list keyed off mandatory fields per item type. Type-level clarifications lead the list when `type_confidence < 0.70`. `needs_confirmation` is now derived from the clarifications list, not a single threshold.
- Added three new thresholds (`ACTIONABLE_THRESHOLD`, `TYPE_THRESHOLD`, `FIELD_THRESHOLD`, all 0.70) and three matching CLI flags. Kept `DEFAULT_CONFIDENCE_THRESHOLD` as a legacy fallback for callers without per-field info.
- Updated `_min_confidence` / `_avg_confidence` to aggregate across all per-field and per-decision scores. Gemini→Claude fallback now triggers off the worst per-field score, finer-grained than before.
- Rewrote `format_summary` to render specific clarification questions ("What time is dinner with Priya?") rather than a generic "Save it?" prompt. Top-level actionable gate renders first when relevant.
- Updated SKILL.md (config block, step-by-step flow), README.md (intro paragraph and fallback diagram), and the schema bits of `.github/copilot-instructions.md`.
- Wrote eight offline unit + integration checks. All pass.

**State now:**
- All changes live on branch `claude/laughing-agnesi-31e9e8`. Not committed yet.
- Files touched: `scripts/scrask_bot.py`, `SKILL.md`, `README.md`, `.github/copilot-instructions.md`. Net +402 / -74 lines.
- Python parses cleanly. `--help` lists the three new flags. Offline integration tests passed.
- Live end-to-end test against real screenshots has NOT been run from this sandbox (no GEMINI_API_KEY in shell, no fixture images in the repo).

**Next:**
- Run the parser against a real screenshot to confirm the model actually returns the new schema (per-field `confidences{}`, `type_confidence`, `actionable_confidence`, `participants`). Use the smoke command from `~/.claude/plans/this-is-how-i-joyful-kay.md`. Likely needs a tweak to the prompt if the model improvises field names.
- Decide whether to commit on this branch and open a PR, or stack more work first.
- Optional: a separate cleanup pass on `.github/copilot-instructions.md`. The file still references v3 architecture (direct Google Calendar writes, `--dry-run`, `GOOGLE_CREDENTIALS`, functions that don't exist). I flagged a spawn-task chip for this.

**Decisions:**
- Per-field confidence over per-item confidence. The single-confidence number couldn't distinguish "model is sure about the dinner but unsure of the time" from "model is unsure about everything." Per-field lets the bot ask targeted clarifications.
- Defaults (30-min duration, blank location) stay downstream in destination skills. The parser only reports what it saw with what certainty.
- Parser stays stateless. It emits a `clarifications[]` array; the Telegram bot (separate codebase) renders and handles replies.
- Kept the legacy per-item `confidence` and `DEFAULT_CONFIDENCE_THRESHOLD` so older callers and any future fixtures with the old schema still route correctly.
