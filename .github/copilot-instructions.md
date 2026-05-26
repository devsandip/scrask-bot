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
- Default provider is `auto`, credential-aware:
  - `GEMINI_API_KEY` set → Gemini 2.0 Flash first; if worst per-field confidence is below `FALLBACK_THRESHOLD` (0.60) and `ANTHROPIC_API_KEY` is set, Claude Opus reruns. Claude's result is kept only if `claude_avg - gemini_avg >= FALLBACK_IMPROVEMENT_MIN` (0.05); otherwise Gemini's result is retained.
  - Only `ANTHROPIC_API_KEY` set → Claude directly.
  - Neither set → defer to OpenClaw's configured vision LLM via the platform-injected env vars `OPENCLAW_VISION_PROVIDER` (`"anthropic"` or `"google"`), `OPENCLAW_VISION_KEY`, and optional `OPENCLAW_VISION_MODEL`.
- Four entry points in `scrask_bot.py`: `parse_with_gemini`, `parse_with_claude`, `parse_with_openclaw`, plus the auto routers `_parse_with_auto` (credential routing) and `_parse_with_gemini_claude_fallback` (the v4.1 Gemini→Claude path). The public router is `parse_screenshot`.
- Default model IDs: `GEMINI_MODEL = "gemini-2.0-flash"`, `CLAUDE_MODEL = "claude-opus-4-6"`. OpenClaw can override via `OPENCLAW_VISION_MODEL` per-call.

## Important constants & edit points
- Prompts: `SYSTEM_PROMPT` and `USER_PROMPT_TEMPLATE` near the top of `scrask_bot.py`. The model must return raw JSON only — keep the system prompt strict.
- Thresholds: `DEFAULT_CONFIDENCE_THRESHOLD` (0.75), `FALLBACK_THRESHOLD` (0.60), `FALLBACK_IMPROVEMENT_MIN` (0.05).
- Intent shape: `shape_intent()` produces the per-item dict the agent consumes. It sets `destination` to `"calendar"` if `type == "event"`, else `"task"`. `needs_confirmation` is `confidence < threshold`.
- Output assembly: `main()` prints a top-level JSON object with `success`, `no_actionable_content`, `provider`, `fallback_triggered`, `items[]`, `summary_text`, `parse_notes`, plus optional diagnostic fields (`gemini_avg_confidence`, `claude_avg_confidence`, `confidence_gain`).
- Human-readable preview: `format_summary()` builds `summary_text`. SKILL.md instructs the agent to send this verbatim — preserve its structure when changing.

## Environment & config
- All credential env vars are OPTIONAL since v4.2. The skill works out of the box on any OpenClaw install with a vision-capable LLM configured at the platform level.
- `GEMINI_API_KEY` — enables Gemini-first routing in `auto`, and required if pinned via `--provider gemini`.
- `ANTHROPIC_API_KEY` — enables Claude fallback in `auto` (or Claude-only if no Gemini key), and required if pinned via `--provider claude`.
- `OPENCLAW_VISION_PROVIDER` / `OPENCLAW_VISION_KEY` / `OPENCLAW_VISION_MODEL` — injected by OpenClaw. Used in `openclaw` mode and as the auto-mode fallback when no skill-level key is set.
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

CLI flags: `--image-path` or `--image-base64` (mutually exclusive, one required), `--provider {auto|openclaw|claude|gemini}`, `--api-key` (override), `--timezone`, `--confidence-threshold`, `--actionable-threshold`, `--type-threshold`, `--field-threshold`, `--media-type`.

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
  "confidence": 0.92,
  "needs_confirmation": false,
  "title": "Team Standup",
  "date": "2026-03-01",
  "time": "09:00",
  "end_time": null,
  "end_date": null,
  "timezone_hint": "Asia/Kolkata",
  "location": "Zoom",
  "online_link": "https://zoom.us/meeting/abc",
  "recurrence": "weekly",
  "recurrence_day": "Monday",
  "description": "Daily team sync",
  "priority": "medium",
  "source_type": "email",
  "language": "en",
  "already_in_calendar_hint": false
}
```

## When in doubt
- Prefer small, localized edits to prompts or thresholds, then verify by running the parser on a real screenshot and inspecting the JSON.
- Don't reintroduce a write path — Scrask's contract is parse-and-emit. Anything that writes to a calendar or task store belongs in a destination skill, not here.
