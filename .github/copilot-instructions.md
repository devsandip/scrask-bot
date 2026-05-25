## Goal
Quick orientation for contributors and AI agents working on the Scrask skill (screenshot → vision LLM → structured intent JSON). Long-form docs live in [README.md](../README.md) and [SKILL.md](../SKILL.md); this file is the short version.

## Big picture
- Scrask is an OpenClaw skill that parses screenshots and emits structured intent JSON. **It does not write to any calendar or task store itself.** The OpenClaw agent reads the JSON and delegates each item to whichever destination skill the user has installed (`calctl`, `accli`, `apple-calendar`, `brainz-calendar`, `gcal-pro`, `apple-reminders`, `things-mac`, `notion`, etc.).
- Flow: chat surface (Telegram / iMessage / Slack / …) sends an image → `scripts/scrask_bot.py` parses with Gemini and optionally Claude → prints JSON to stdout → OpenClaw routes each `items[]` entry by its `destination` field.

## Key files
- `scripts/scrask_bot.py` — the entire implementation: prompts, provider routing, auto-fallback logic, intent shaping, summary formatting. Single file. Edit prompts and thresholds here.
- `SKILL.md` — OpenClaw skill manifest plus the step-by-step instructions the agent follows (acknowledge → run parser → route items → confirm).
- `README.md` — user-facing onboarding and the provider-strategy diagram.
- `scripts/requirements.txt` — runtime deps (`anthropic`, `google-generativeai`).

## Providers and auto-fallback
- Default provider is `auto`: Gemini 2.0 Flash runs first; if any item's confidence is below `FALLBACK_THRESHOLD` (0.60) and `ANTHROPIC_API_KEY` is set, Claude Opus reruns the parse. Claude's result is kept only if `claude_avg - gemini_avg >= FALLBACK_IMPROVEMENT_MIN` (0.05); otherwise Gemini's result is retained.
- Three entry points in `scrask_bot.py`: `parse_with_gemini`, `parse_with_claude`, `_parse_with_auto_fallback`. The router is `parse_screenshot`.
- Model IDs: `GEMINI_MODEL = "gemini-2.0-flash"`, `CLAUDE_MODEL = "claude-opus-4-6"`. Change these constants if upgrading.

## Important constants & edit points
<<<<<<< Updated upstream
- Prompts: `SYSTEM_PROMPT` and `USER_PROMPT_TEMPLATE` in `scrask_bot.py`. The script expects Claude to return raw JSON; keep the system prompt strict (JSON-only).
- Thresholds: `DEFAULT_CONFIDENCE_THRESHOLD` (legacy per-item gate), `FALLBACK_THRESHOLD` (Gemini→Claude trigger), `FALLBACK_IMPROVEMENT_MIN`, `ACTIONABLE_THRESHOLD`, `TYPE_THRESHOLD`, and `FIELD_THRESHOLD` are declared near the top of `scrask_bot.py`. The last three drive clarification generation; below each threshold the parser asks a targeted question rather than confirming the whole item.
- Mandatory fields per type live in `MANDATORY_FIELDS_BY_TYPE`; clarification question templates live in `CLARIFICATION_QUESTIONS`. Both are next to the threshold constants.
- Google behavior: `get_google_services()` builds Calendar + Tasks clients. Google libs are optional at import-time; missing Google libs produce a helpful runtime error.
=======
- Prompts: `SYSTEM_PROMPT` and `USER_PROMPT_TEMPLATE` near the top of `scrask_bot.py`. The model must return raw JSON only — keep the system prompt strict.
- Thresholds: `DEFAULT_CONFIDENCE_THRESHOLD` (0.75), `FALLBACK_THRESHOLD` (0.60), `FALLBACK_IMPROVEMENT_MIN` (0.05).
- Intent shape: `shape_intent()` produces the per-item dict the agent consumes. It sets `destination` to `"calendar"` if `type == "event"`, else `"task"`. `needs_confirmation` is `confidence < threshold`.
- Output assembly: `main()` prints a top-level JSON object with `success`, `no_actionable_content`, `provider`, `fallback_triggered`, `items[]`, `summary_text`, `parse_notes`, plus optional diagnostic fields (`gemini_avg_confidence`, `claude_avg_confidence`, `confidence_gain`).
- Human-readable preview: `format_summary()` builds `summary_text`. SKILL.md instructs the agent to send this verbatim — preserve its structure when changing.
>>>>>>> Stashed changes

## Environment & config
- Required: `GEMINI_API_KEY` (for `auto` and `gemini` modes).
- Optional: `ANTHROPIC_API_KEY` (enables Claude fallback in `auto`, required for `claude`).
- Other env vars: `VISION_PROVIDER` (default `auto`), `USER_TIMEZONE` (default `UTC`).
- Skill-level config in `SKILL.md`: `vision_provider`, `fallback_threshold`, `timezone`, `confidence_threshold`. Keep these defaults in sync with the constants in `scrask_bot.py` when changing behavior.

## Developer workflows
Install dependencies:
```
pip install -r scripts/requirements.txt
```

Run the parser directly (prints JSON to stdout — there is no `--dry-run` flag because the script never writes to any store):
```
python3 scripts/scrask_bot.py \
  --image-path /path/to/screenshot.png \
  --provider auto \
  --timezone "Asia/Kolkata"
```

CLI flags: `--image-path` or `--image-base64` (mutually exclusive, one required), `--provider {auto|claude|gemini}`, `--api-key` (override), `--timezone`, `--confidence-threshold`, `--media-type`.

## Conventions when extending
- The model contract is defined in `USER_PROMPT_TEMPLATE`. When you add a field, update both the prompt schema **and** `shape_intent()` so the field reaches the downstream agent. If it should appear in the chat preview, also touch `format_summary()`.
- Keep `destination` mapping in `shape_intent()` the source of truth — don't let routing logic leak elsewhere in the script.
- The script's output schema is consumed by the OpenClaw agent and by destination skills. Renaming top-level keys (`items`, `summary_text`, `no_actionable_content`, `success`) is a breaking change.
- Errors exit non-zero via `exit_error()`, which writes a JSON error payload to stderr. Keep that format if you add new failure paths.

## Failure modes
- Missing `anthropic` or `google-generativeai` package → corresponding provider call raises `RuntimeError` with the `pip install` hint.
- Provider returns non-JSON / wrapped fences → `_clean_and_parse_json()` strips ```json fences; anything still unparseable surfaces as a `JSONDecodeError` and exits with a structured error.
- Auto mode with Claude fallback that itself throws → falls back to the Gemini result and adds `_fallback_error` to the payload, rather than failing the whole run.

## Example item (what `items[]` looks like after `shape_intent`)
```json
{
  "type": "event",
  "destination": "calendar",
<<<<<<< Updated upstream
  "confidence": 0.90,
  "type_confidence": 0.95,
=======
  "confidence": 0.92,
  "needs_confirmation": false,
>>>>>>> Stashed changes
  "title": "Team Standup",
  "date": "2026-03-01",
  "time": "09:00",
  "end_time": null,
  "end_date": null,
  "timezone_hint": "Asia/Kolkata",
  "location": "Zoom",
  "online_link": "https://zoom.us/meeting/abc",
<<<<<<< Updated upstream
  "participants": ["Priya", "Anika"],
  "recurrence": "weekly",
  "confidences": {
    "title": 0.95,
    "date": 0.92,
    "time": 0.90,
    "location": 0.88,
    "participants": 0.75
  },
  "clarifications": [],
  "needs_confirmation": false
}
```
And one that triggers a clarification:
```
{
  "type": "event",
  "destination": "calendar",
  "title": "Coffee at Pegasus",
  "date": "2026-03-06",
  "time": null,
  "confidences": { "title": 0.85, "date": 0.80, "time": 0.0 },
  "clarifications": [
    { "field": "time", "question": "What time is Coffee at Pegasus?", "reason": "missing" }
  ],
  "needs_confirmation": true
=======
  "recurrence": "weekly",
  "recurrence_day": "Monday",
  "description": "Daily team sync",
  "priority": "medium",
  "source_type": "email",
  "language": "en",
  "already_in_calendar_hint": false
>>>>>>> Stashed changes
}
```

## When in doubt
- Prefer small, localized edits to prompts or thresholds, then verify by running the parser on a real screenshot and inspecting the JSON.
- Don't reintroduce a write path — Scrask's contract is parse-and-emit. Anything that writes to a calendar or task store belongs in a destination skill, not here.
