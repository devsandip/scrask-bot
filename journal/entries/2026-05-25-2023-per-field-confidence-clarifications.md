# Per-field confidence and targeted clarifications

_2026-05-25 20:23_

**Previous:** _(first entry)_

The parser used to collapse all uncertainty into one number per item. A single `confidence` field, gated against a single threshold, flipped one `needs_confirmation` flag. The Telegram bot rendered the same generic prompt for every uncertain item: "Save it? yes / edit / skip."

I sat with this and realized it cannot tell the right story. "Model is sure this is dinner at Pegasus on Friday but unsure of the time" and "model is unsure whether this is even an event" become the same low-confidence signal. The bot has to ask the same generic question for both. The user re-confirms things they already typed clearly.

Today I redid the confidence model. Three layers now.

`actionable_confidence` lives at the top of the parse result. It scores whether the screenshot is about an event or task at all. Below threshold, the bot asks "Is this actually an event or task?" before doing anything else.

`type_confidence` lives per item. It scores whether this particular item belongs on the calendar or in the task list. Below threshold, the bot asks "Should this go on your calendar or task list?" as the first clarification.

`confidences{}` lives per item as a map keyed by field name. Title, date, time, location, participants, description, priority. Each gets its own 0.0–1.0 score. For each mandatory field (title for tasks; title + date + time for events and reminders), if the value is missing or the per-field score is below threshold, the parser emits a targeted clarification: "What time is dinner with Priya?" not "is this right?"

The parser stays stateless. It emits a `clarifications[]` array. The Telegram bot (separate codebase) renders the questions and stitches replies back into the item. That keeps the parser's contract small.

I also added `participants[]` as a first-class field. Names extracted when visible, never invented, null when nothing is named. The model gets the same per-field confidence treatment for it.

A few decisions I closed:

Defaults stay downstream. The parser does not assume 30-minute duration or blank location. It reports what it saw with what confidence. The destination skill decides what to do with a null. This keeps Scrask's job narrow and lets each destination (Apple Calendar, Things, Notion) handle its own conventions.

Legacy `confidence` per item is retained. The model no longer emits it, but `shape_intent` synthesizes it from `min(confidences.values())`. Old fixtures and any downstream code that branches on `item["confidence"]` still works.

The Gemini → Claude auto-fallback now looks at the worst per-field score across all items, not a synthetic per-item number. The 0.60 trigger is more accurate now — finer-grained signal of where the model is shaky.

I have not run this against a real screenshot yet. The sandbox has no GEMINI_API_KEY and no fixture images. The shape and the post-parse pipeline are tested offline, but the question of whether the vision model actually returns the new schema (without improvising field names) is open until the first live run.

The other open question is field-by-field threshold tuning. Today every threshold is 0.70. It might want to be higher for title and lower for participants. Wait for real data.
