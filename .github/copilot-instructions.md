## Goal
Help contributors and AI agents quickly understand and modify the Scrask skill (screenshot→Claude→Google Calendar/Tasks).

## Big picture
- This repo implements an OpenClaw "skill" that parses screenshots with Claude Vision and saves detected events/reminders/tasks to Google Calendar or Google Tasks.
- Core flow: Telegram image → `scrask_bot.py` parses image with Anthropic/Claude → decision engine classifies item (event/reminder/task) → high-confidence items saved automatically via Google APIs → low-confidence items produce a Telegram preview requiring confirmation.

## Key files
- `scrask_bot.py` — single-file implementation of the parser, decision engine, Google helpers, and Telegram reply formatter. Edit prompts and parsing rules here.
- `SKILL.md` — OpenClaw skill manifest and operator instructions used by the platform.
- `requirements.txt` — runtime dependencies (Anthropic + Google client libs).
- `README.md` — onboarding + example commands (dry-run shown below).

## Important constants & edit points
- Prompts: `SYSTEM_PROMPT` and `USER_PROMPT_TEMPLATE` in `scrask_bot.py`. The script expects Claude to return raw JSON; keep the system prompt strict (JSON-only).
- Thresholds: `CONFIDENCE_THRESHOLD`, `DEFAULT_EVENT_DURATION`, `DEFAULT_REMINDER_LEAD` constants are declared near the top of `scrask_bot.py`.
- Google behavior: `get_google_services()` builds Calendar + Tasks clients. Google libs are optional at import-time; missing Google libs produce a helpful runtime error.

## Environment & config
- Required env vars for normal operation: `ANTHROPIC_API_KEY`, `GOOGLE_CREDENTIALS` (path to service-account JSON). These are referenced by `scrask_bot.py` and described in `SKILL.md`/`README.md`.
- Skill-level config in `SKILL.md` includes `timezone`, `confidence_threshold`, and `reminder_minutes_before` — keep these consistent with constants in `scrask_bot.py` when changing behavior.

## Developer workflows (commands to run)
- Install: `pip install -r requirements.txt` (or as shown in `README.md` if installed inside OpenClaw skill path).
- Dry-run parser (no Google writes):
```
python3 scrask_bot.py \
  --image-path /path/to/screenshot.png \
  --api-key $ANTHROPIC_API_KEY \
  --timezone "Asia/Kolkata" \
  --dry-run
```
- To test Google write flows, ensure `GOOGLE_CREDENTIALS` points to a valid service-account JSON with Calendar+Tasks access.

## Patterns and conventions to follow
- The parser expects Claude to return a strict JSON object with `items[]`, `screenshot_summary`, `no_actionable_content`, and `parse_notes` (see `USER_PROMPT_TEMPLATE`). When changing the prompt, preserve that schema.
- Confidence-driven behavior: Items with `confidence < CONFIDENCE_THRESHOLD` must surface a clear confirmation message via `format_telegram_reply()` rather than being saved silently.
- When adding fields to the parsed schema, update both `USER_PROMPT_TEMPLATE` and the downstream handlers: `process_item()`, `execute_item()`, `create_calendar_event()`, and `create_task()`.

## Integration points & failure modes
- Claude (Anthropic) model: `parse_with_claude()` calls `anthropic.Anthropic(...).messages.create()` with `model="claude-opus-4-6"` — changes to model names or client usage must be reflected here.
- Google APIs: insert operations use `calendar.events().insert(...)` and `tasks().insert(...)`. API failures are caught and returned as `error` in the item result.
- Missing `anthropic` package causes immediate exit with a JSON error payload; missing Google libs raise helpful RuntimeError on Google calls.

## Small examples (copyable)
- Example parsed item (what the agent should produce / expect in JSON `items[]`):
```
{
  "type": "event",
  "confidence": 0.92,
  "title": "Team Standup",
  "date": "2026-03-01",
  "time": "09:00",
  "timezone_hint": "Asia/Kolkata",
  "location": "Zoom",
  "online_link": "https://zoom.us/meeting/abc",
  "recurrence": "weekly"
}
```

## When in doubt
- Prefer small, localized edits: change prompts or thresholds in `scrask_bot.py` and test with the dry-run command.
- Keep the JSON contract stable — other components (OpenClaw, Telegram handlers) expect the exact fields.

---
If anything here is unclear or you want sections expanded (e.g., message-flow diagrams, more examples, or tests), tell me which part to iterate on.
