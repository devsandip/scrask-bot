# 🦞 Scrask Bot

**OpenClaw Skill** — Send a screenshot to your OpenClaw agent. Scrask parses it and routes
events to your calendar, tasks to your task app — using whichever destination skills you
already have installed.

**Scrask** = Screenshot + Task

---

## What It Does

1. You take a screenshot on your phone (WhatsApp forward, email, social post, chat).
2. You send it to your OpenClaw bot via whatever chat surface you have wired up — Telegram, iMessage, Slack, etc.
3. Scrask parses it with vision AI.
4. It emits structured intent — calendar event, reminder, or task — and the OpenClaw agent
   delegates writes to your installed destination skill (`calctl`, `apple-reminders`, `things-mac`, etc.).

Scrask itself never writes to any store. No service account JSON, no OAuth, no Google dev keys.

| Detected type | Destination kind | Example destination skills |
|---|---|---|
| Event (date + time / venue / invite link) | `calendar` | `calctl`, `accli`, `apple-calendar`, `brainz-calendar`, `gcal-pro` |
| Reminder (deadline, due date) | `task` (with due date) | `apple-reminders`, `things-mac`, `notion` |
| Task (no date, action item) | `task` (no due date) | `apple-reminders`, `things-mac`, `notion` |

Every extracted field carries its own confidence (0.0–1.0), and there are two top-level
decision confidences too:

- `actionable_confidence` — is this screenshot actually about an event or task at all?
- `type_confidence` — is this item a calendar event, or does it belong on the task list?
- `confidences.{field}` — how sure are we about each individual field (`title`, `date`,
  `time`, `location`, `participants`, …)

When every mandatory field is confidently extracted, Scrask routes silently and confirms in
chat. When something is missing or shaky, it surfaces targeted clarification questions — "What
time is dinner with Priya?" instead of a blanket "is this right?" The bot asks only what it
actually needs to ask.

A single screenshot can produce multiple items. "Let's grab coffee at Pegasus on Friday"
yields both a calendar event (the coffee) and a prep reminder (book the table, due Thursday).
Prep reminders are inferred — they get lower per-field confidences and usually trigger
clarifications (typically `time` and `date`) before saving.

Multi-day events (trips, conferences) carry `end_date` in addition to `date` so the
destination calendar skill can set the full date range. Reschedules and cancellations are
detected and flagged in `parse_notes`.

---

## Provider Strategy

By default, Scrask uses **auto mode**: Gemini first, Claude fallback.

```
Screenshot arrives
      ↓
  Gemini 2.0 Flash (fast, cheap)
      ↓
  Worst per-field confidence < 0.60?
  ├── No  → Done ✓
  └── Yes → Claude Opus reruns the parse
              ↓
          Claude avg confidence > Gemini + 0.05?
          ├── Yes → Use Claude result ✓
          └── No  → Gemini result was fine, keep it ✓
```

You can override this per-use with `--provider claude` or `--provider gemini`.

`ANTHROPIC_API_KEY` is optional. Without it, auto mode runs Gemini only with no fallback.

---

## Installation

```bash
# 1. Copy to OpenClaw skills directory
cp -r scrask-bot ~/.openclaw/skills/

# 2. Install dependencies
pip install -r ~/.openclaw/skills/scrask-bot/scripts/requirements.txt

# 3. Install at least one calendar skill and one task skill
#    (Scrask delegates writes to whatever you have installed.)
#
#    Examples (macOS native, no API keys):
openclaw install calctl           # Apple Calendar via icalBuddy + AppleScript
openclaw install apple-reminders  # Apple Reminders via remindctl
openclaw install things-mac       # Things 3 via the things CLI
#
#    Or, for Google Calendar without a dev key:
openclaw install brainz-calendar  # wraps gcalcli — user OAuths once

# 4. Add scrask to openclaw.json (see below)

# 5. Restart OpenClaw
openclaw restart
```

### openclaw.json config

```json
{
  "skills": {
    "entries": {
      "scrask-bot": {
        "enabled": true,
        "env": {
          "GEMINI_API_KEY": "AIza-your-gemini-key",
          "ANTHROPIC_API_KEY": "sk-ant-your-key-here"
        },
        "config": {
          "vision_provider": "auto",
          "fallback_threshold": 0.60,
          "timezone": "Asia/Kolkata",
          "confidence_threshold": 0.75,
          "actionable_threshold": 0.70,
          "type_threshold": 0.70,
          "field_threshold": 0.70
        }
      }
    }
  }
}
```

`ANTHROPIC_API_KEY` is optional. The calendar / task destination skills handle their
own auth — typically a one-time CLI login, no dev key.

---

## Testing the parser directly

```bash
# Auto mode (Gemini + Claude fallback)
python3 scripts/scrask_bot.py \
  --image-path /path/to/screenshot.png \
  --provider auto \
  --timezone "Asia/Kolkata"

# Force a specific provider
python3 scripts/scrask_bot.py \
  --image-path /path/to/screenshot.png \
  --provider gemini \
  --timezone "Asia/Kolkata"
```

The script prints JSON to stdout. Inspect `items[]` to see what it extracted and where
the agent would route each one.

---

## File Structure

```
scrask-bot/
├── SKILL.md                          # OpenClaw skill instructions
├── README.md                         # This file
├── docs/
│   ├── ARCHITECTURE_OVERVIEW.md      # How Scrask is built (start here)
│   ├── decision-flow.md              # Mermaid diagrams of the parser + bot flow
│   ├── decision-flow.html            # Same, interactive (clickable nodes)
│   └── example-walkthrough.md        # A real conversation, end to end
└── scripts/
    ├── scrask_bot.py                 # Vision-AI parser → structured intent JSON
    └── requirements.txt              # Python dependencies (anthropic, google-generativeai)
```

New to the codebase? Start with
[`docs/ARCHITECTURE_OVERVIEW.md`](docs/ARCHITECTURE_OVERVIEW.md) — the first
half is written for any reader, the second half is the code-level detail.

For a step-by-step picture of what happens when a screenshot lands —
including the confidence thresholds, the Gemini→Claude fallback, the
top-level actionable gate, and the per-field clarification loop — see
[`docs/decision-flow.md`](docs/decision-flow.md). For a concrete
USER ↔ BOT ↔ PARSER transcript, see
[`docs/example-walkthrough.md`](docs/example-walkthrough.md).

---

## Built by

Sandip

---

## License

MIT
