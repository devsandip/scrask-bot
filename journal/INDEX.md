# Scrask Bot — Journal Index

_Last refreshed: 2026-05-25 20:23_

**Latest entry:** [entries/2026-05-25-2023-per-field-confidence-clarifications.md](entries/2026-05-25-2023-per-field-confidence-clarifications.md)

## Where we are now

Scrask is a screenshot-to-intent parser. Send it a screenshot, it returns structured JSON describing the event / reminder / task inside, and the OpenClaw agent routes each item to whichever destination skill the user has installed. The parser does not write to any store directly.

The confidence model just got a substantial rework. The parser used to emit a single 0.0–1.0 confidence per item, which gated a binary needs-confirmation flag. That number could not say whether the model was unsure about the whole item or only one field, so the Telegram bot always asked "Save it? yes / edit / skip" — even when the only missing piece was the time.

The new model has three confidence layers. `actionable_confidence` at the top decides whether the screenshot is about an event or task at all. `type_confidence` per item decides whether it goes to the calendar or task list. `confidences{}` per item scores each extracted field on its own. Below threshold on any mandatory field, the parser emits a targeted clarification question — "What time is dinner with Priya?" — instead of a generic re-confirm.

Participants are now a first-class field. Defaults like 30-minute duration stay downstream in destination skills.

## Recent entries

- 2026-05-25 20:23 — [Per-field confidence and targeted clarifications](entries/2026-05-25-2023-per-field-confidence-clarifications.md)

## Recent weekly summaries

_None yet._

## Working hypotheses

- Per-field clarification questions reduce the friction of low-confidence items. The user only answers what is actually missing rather than re-confirming the whole item.
- Keeping the parser stateless (clarifications are emitted, not asked) means the Telegram bot owns the conversation loop without round-tripping through the parser.
- The downstream destination skills are the right place for defaults like 30-min duration. The parser should report what was seen, not what to assume.

## Open questions

- Does the vision model reliably emit the new schema (per-field confidences, type_confidence, actionable_confidence) without improvising field names? Needs a live run.
- Are the 0.70 thresholds correct in practice, or do they need to be tuned per field (e.g. higher for title, lower for participants)? Wait for real-world data.
- What does the Telegram bot side actually do with `clarifications[]`? Ask one question at a time? Render all bullets and parse a free-text reply? Out of scope for this repo, but the parser contract should not constrain that decision.

## Things ruled out

- _Bundling all confidence into one number._ The original model. Cannot distinguish "missing the time" from "missing everything." Replaced by per-field.
- _Applying defaults (30-min duration, blank location) in the parser._ Considered, rejected. Defaults belong with the destination skill that knows how its store handles them.
