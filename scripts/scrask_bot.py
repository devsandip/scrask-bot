#!/usr/bin/env python3
"""
scrask_bot.py
Scrask Bot — Screenshot to Intent Parser

Parses screenshots (from any chat transport — Telegram, iMessage, Slack, etc.)
using Gemini or Claude vision, and emits structured intent JSON. Scrask does
not write to any calendar or task store directly — the OpenClaw agent delegates
to the user's installed destination skills (calctl, apple-reminders, things-mac,
brainz-calendar, etc.) based on the intent type.

Usage:
  python scrask_bot.py --image-path <path> [--provider auto|claude|gemini] [--timezone <tz>]
  python scrask_bot.py --image-base64 <base64> [--provider auto|claude|gemini]

Env vars:
  GEMINI_API_KEY     — required for 'auto' and 'gemini' modes
  ANTHROPIC_API_KEY  — optional; enables Claude fallback in 'auto' mode
  VISION_PROVIDER    — 'auto' (default), 'claude', or 'gemini' (overridden by --provider)

Requirements:
  pip install -r requirements.txt
"""

import argparse
import base64
import json
import os
import sys
from datetime import date
from pathlib import Path

try:
    import anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


# ─── Constants ─────────────────────────────────────────────────────────────────

MIME_TYPES = {
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".gif":  "image/gif",
    ".webp": "image/webp",
}

DEFAULT_CONFIDENCE_THRESHOLD = 0.75
FALLBACK_THRESHOLD           = 0.60
FALLBACK_IMPROVEMENT_MIN     = 0.05

CLAUDE_MODEL = "claude-opus-4-6"
GEMINI_MODEL = "gemini-2.0-flash"


# ─── Shared prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a structured data extraction assistant. "
    "Your only job is to analyze screenshots and return valid JSON — nothing else. "
    "No preamble, no explanation, no markdown fences. Only raw JSON."
)

USER_PROMPT_TEMPLATE = """Analyze this screenshot carefully. It may be a WhatsApp forward,
email screenshot, social media post, or chat message received via any chat app.

Extract ALL actionable information — calendar events AND task-like asks — and return a single JSON object:

{{
  "items": [
    {{
      "type": "event" | "reminder" | "task",
      "confidence": 0.0-1.0,
      "title": "concise title (max 60 chars)",
      "date": "YYYY-MM-DD or null",
      "time": "HH:MM (24h) or null",
      "end_time": "HH:MM (24h) or null",
      "timezone_hint": "detected timezone string or null",
      "location": "physical address or venue name or null",
      "online_link": "Zoom/Meet/Teams URL or null",
      "recurrence": "none | daily | weekly | monthly | yearly",
      "recurrence_day": "e.g. Tuesday or null",
      "description": "1-2 sentence context summary or null",
      "priority": "high | medium | low",
      "source_type": "whatsapp | email | social_media | chat | flyer | other",
      "language": "ISO 639-1 code of the screenshot text",
      "already_in_calendar_hint": true | false
    }}
  ],
  "screenshot_summary": "one sentence describing what this screenshot shows",
  "no_actionable_content": true | false,
  "parse_notes": "edge cases, ambiguities, or things to flag to the user"
}}

Classification rules:
- "event"    → specific date+time OR a venue/link; social or external gathering. Goes to a calendar.
- "reminder" → deadline/due date; personal action item with a date. Goes to a task list with a due date.
- "task"     → no date at all; pure to-do or action item (e.g. "send me your resume"). Goes to a task list.

A single screenshot may produce multiple items — e.g. "lets grab coffee at Pegasus on friday"
yields BOTH an event (the coffee meetup) AND a task (book the table).

A screenshot is "no_actionable_content" only if there is no event, reminder, or task in it.
A meme, a random photo, or pure venting with no ask is not actionable. A request like
"send me your resume" IS actionable — it is a task.

Confidence scoring:
- 0.9–1.0  All key fields present, no ambiguity
- 0.75–0.9 Most fields present, minor inference needed
- 0.5–0.75 Date or type is uncertain
- < 0.5    Very little usable info

Current date: {today}
User timezone: {timezone}

Return only JSON. No markdown. No explanation."""


# ─── Provider: Claude ──────────────────────────────────────────────────────────

def parse_with_claude(image_base64: str, media_type: str, api_key: str, timezone: str = "UTC") -> dict:
    if not CLAUDE_AVAILABLE:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_base64}},
                {"type": "text",  "text": USER_PROMPT_TEMPLATE.format(today=date.today().isoformat(), timezone=timezone)},
            ],
        }],
    )
    raw = message.content[0].text if message.content else ""
    return _clean_and_parse_json(raw)


# ─── Provider: Gemini ──────────────────────────────────────────────────────────

def parse_with_gemini(image_base64: str, media_type: str, api_key: str, timezone: str = "UTC") -> dict:
    if not GEMINI_AVAILABLE:
        raise RuntimeError("google-generativeai package not installed. Run: pip install google-generativeai")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name=GEMINI_MODEL, system_instruction=SYSTEM_PROMPT)

    image_bytes = base64.standard_b64decode(image_base64)
    image_part  = {"mime_type": media_type, "data": image_bytes}
    prompt      = USER_PROMPT_TEMPLATE.format(today=date.today().isoformat(), timezone=timezone)

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT:        HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH:       HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    response = model.generate_content(
        [image_part, prompt],
        safety_settings=safety_settings,
        generation_config=genai.GenerationConfig(max_output_tokens=1500, temperature=0.1),
    )

    raw = response.text if response.text else ""
    return _clean_and_parse_json(raw)


# ─── Provider router ───────────────────────────────────────────────────────────

def parse_screenshot(
    image_base64: str,
    media_type: str,
    provider: str,
    timezone: str = "UTC",
    claude_api_key: str | None = None,
    gemini_api_key: str | None = None,
) -> dict:
    provider = provider.lower().strip()

    if provider == "claude":
        result = parse_with_claude(image_base64, media_type, claude_api_key, timezone)
        result["_provider_used"]      = "claude"
        result["_fallback_triggered"] = False
        return result

    if provider == "gemini":
        result = parse_with_gemini(image_base64, media_type, gemini_api_key, timezone)
        result["_provider_used"]      = "gemini"
        result["_fallback_triggered"] = False
        return result

    if provider == "auto":
        return _parse_with_auto_fallback(
            image_base64, media_type, timezone,
            gemini_api_key=gemini_api_key,
            claude_api_key=claude_api_key,
        )

    raise ValueError(f"Unknown provider '{provider}'. Choose 'auto', 'claude', or 'gemini'.")


def _parse_with_auto_fallback(image_base64, media_type, timezone, gemini_api_key, claude_api_key):
    gemini_result = parse_with_gemini(image_base64, media_type, gemini_api_key, timezone)
    gemini_items  = gemini_result.get("items", [])
    gemini_min    = min((i.get("confidence", 0) for i in gemini_items), default=1.0)
    gemini_avg    = _avg_confidence(gemini_items)

    fallback_triggered = gemini_min < FALLBACK_THRESHOLD and bool(claude_api_key)

    if not fallback_triggered:
        gemini_result["_provider_used"]      = "gemini"
        gemini_result["_fallback_triggered"] = False
        gemini_result["_gemini_avg_conf"]    = round(gemini_avg, 3)
        return gemini_result

    try:
        claude_result = parse_with_claude(image_base64, media_type, claude_api_key, timezone)
        claude_avg    = _avg_confidence(claude_result.get("items", []))
    except Exception as e:
        gemini_result["_provider_used"]      = "gemini"
        gemini_result["_fallback_triggered"] = True
        gemini_result["_fallback_error"]     = f"Claude fallback failed: {e}"
        gemini_result["_gemini_avg_conf"]    = round(gemini_avg, 3)
        return gemini_result

    improvement = claude_avg - gemini_avg

    if improvement >= FALLBACK_IMPROVEMENT_MIN:
        claude_result["_provider_used"]      = "claude"
        claude_result["_fallback_triggered"] = True
        claude_result["_gemini_avg_conf"]    = round(gemini_avg, 3)
        claude_result["_claude_avg_conf"]    = round(claude_avg, 3)
        claude_result["_confidence_gain"]    = round(improvement, 3)
        return claude_result

    gemini_result["_provider_used"]      = "gemini"
    gemini_result["_fallback_triggered"] = True
    gemini_result["_fallback_outcome"]   = "gemini_retained"
    gemini_result["_gemini_avg_conf"]    = round(gemini_avg, 3)
    gemini_result["_claude_avg_conf"]    = round(claude_avg, 3)
    return gemini_result


def _avg_confidence(items: list[dict]) -> float:
    if not items:
        return 0.0
    return sum(i.get("confidence", 0) for i in items) / len(items)


def _clean_and_parse_json(raw: str) -> dict:
    cleaned = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(cleaned)


# ─── Intent shaping ────────────────────────────────────────────────────────────

def shape_intent(item: dict, confidence_threshold: float) -> dict:
    """
    Turn one raw model item into a normalized intent the OpenClaw agent can
    route to a destination skill.

    `destination` is the *kind* of skill needed, not a specific provider:
      - "calendar"  → calctl / accli / brainz-calendar / etc.
      - "task"      → apple-reminders / things-mac / notion / etc.
    """
    confidence  = item.get("confidence", 0.0)
    item_type   = item.get("type", "task")
    destination = "calendar" if item_type == "event" else "task"

    return {
        "type":                     item_type,
        "destination":              destination,
        "confidence":               confidence,
        "needs_confirmation":       confidence < confidence_threshold,
        "title":                    item.get("title"),
        "date":                     item.get("date"),
        "time":                     item.get("time"),
        "end_time":                 item.get("end_time"),
        "timezone_hint":            item.get("timezone_hint"),
        "location":                 item.get("location"),
        "online_link":              item.get("online_link"),
        "recurrence":               item.get("recurrence", "none"),
        "recurrence_day":           item.get("recurrence_day"),
        "description":              item.get("description"),
        "priority":                 item.get("priority", "medium"),
        "language":                 item.get("language"),
        "already_in_calendar_hint": item.get("already_in_calendar_hint", False),
    }


# ─── Human-readable summary ────────────────────────────────────────────────────

def format_summary(items: list[dict], parse_data: dict, provider: str) -> str:
    """
    Chat-agnostic preview the agent can relay back to the user via whatever
    transport they came in on. The agent should send this verbatim.
    """
    if not items:
        return (
            "🤷 I couldn't find any event, reminder, or task in that screenshot.\n"
            "Could you describe what you'd like to add?"
        )

    lines = []
    silent  = [i for i in items if not i["needs_confirmation"]]
    confirm = [i for i in items if i["needs_confirmation"]]

    for i in silent:
        if i["destination"] == "calendar":
            when = f"{i.get('date', '')} at {i['time']}" if i.get("time") else i.get("date", "")
            lines.append(f"📅 Event: **{i['title']}** — {when}")
        else:
            due  = f" (due {i['date']})" if i.get("date") else ""
            icon = "🔔" if i.get("date") else "✅"
            lines.append(f"{icon} Task: **{i['title']}**{due}")

    for i in confirm:
        lines.append(f"\n🤔 Not sure about this one (confidence: {int(i['confidence']*100)}%)")
        if i["destination"] == "calendar":
            lines.append("📅 **Event detected**")
            lines.append(f"  Title: {i['title']}")
            lines.append(f"  Date:  {i.get('date') or '?'}")
            lines.append(f"  Time:  {i.get('time') or '?'}")
            if i.get("location"):
                lines.append(f"  Where: {i['location']}")
            if i.get("online_link"):
                lines.append(f"  Link:  {i['online_link']}")
        else:
            icon  = "🔔" if i.get("date") else "✅"
            label = "Reminder" if i.get("date") else "Task"
            lines.append(f"{icon} **{label} detected**")
            lines.append(f"  Title: {i['title']}")
            if i.get("date"):
                lines.append(f"  Due:   {i['date']}")
        if i.get("description"):
            lines.append(f"  Note:  {i['description']}")
        lines.append("\nSave it? Reply **yes**, **edit**, or **skip**.")

    if parse_data.get("parse_notes"):
        lines.append(f"\n_ℹ️ {parse_data['parse_notes']}_")

    lines.append(f"\n_Parsed by Scrask using {provider.capitalize()}_")
    return "\n".join(lines).strip()


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrask Bot — parse screenshots into structured calendar/task intent."
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--image-path",   help="Path to the screenshot file")
    group.add_argument("--image-base64", help="Base64-encoded image data")

    parser.add_argument(
        "--provider",
        choices=["auto", "claude", "gemini"],
        default=os.environ.get("VISION_PROVIDER", "auto"),
        help="'auto' (default) = Gemini first, Claude fallback if confidence < 0.6.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Override API key. Defaults to ANTHROPIC_API_KEY / GEMINI_API_KEY env vars.",
    )
    parser.add_argument(
        "--timezone",
        default=os.environ.get("USER_TIMEZONE", "UTC"),
        help="IANA timezone (e.g. Asia/Kolkata)",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD,
        help="Items below this score are flagged needs_confirmation=true (default 0.75).",
    )
    parser.add_argument(
        "--media-type",
        default=None,
        help="Override media type (auto-detected from file extension if omitted)",
    )

    args = parser.parse_args()

    claude_api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    gemini_api_key = args.api_key or os.environ.get("GEMINI_API_KEY")

    if args.provider == "claude" and not claude_api_key:
        exit_error("Missing ANTHROPIC_API_KEY for Claude provider.")
    if args.provider == "gemini" and not gemini_api_key:
        exit_error("Missing GEMINI_API_KEY for Gemini provider.")
    if args.provider == "auto" and not gemini_api_key:
        exit_error("Auto mode requires GEMINI_API_KEY at minimum. ANTHROPIC_API_KEY enables Claude fallback.")
    if args.provider == "auto" and not claude_api_key:
        print(
            "⚠️  ANTHROPIC_API_KEY not set. Auto mode will use Gemini only (no Claude fallback).",
            file=sys.stderr,
        )

    try:
        if args.image_path:
            p = Path(args.image_path)
            if not p.exists():
                exit_error(f"Image not found: {args.image_path}")
            media_type   = args.media_type or MIME_TYPES.get(p.suffix.lower(), "image/png")
            image_base64 = base64.standard_b64encode(p.read_bytes()).decode()
        else:
            image_base64 = args.image_base64
            media_type   = args.media_type or "image/png"
    except Exception as e:
        exit_error(f"Failed to load image: {e}")

    try:
        parse_data = parse_screenshot(
            image_base64, media_type, args.provider, args.timezone,
            claude_api_key=claude_api_key,
            gemini_api_key=gemini_api_key,
        )
    except json.JSONDecodeError as e:
        exit_error(f"Provider returned invalid JSON: {e}")
    except Exception as e:
        exit_error(f"Error during parsing: {e}")

    provider_used = parse_data.get("_provider_used", args.provider)
    raw_items     = parse_data.get("items", [])

    if parse_data.get("no_actionable_content") or not raw_items:
        print(json.dumps({
            "success":               True,
            "no_actionable_content": True,
            "provider":              provider_used,
            "fallback_triggered":    parse_data.get("_fallback_triggered", False),
            "screenshot_summary":    parse_data.get("screenshot_summary", ""),
            "items":                 [],
            "summary_text": (
                "🤷 I couldn't find any event, reminder, or task in that screenshot.\n"
                "Could you describe what you'd like to add?"
            ),
        }, indent=2, ensure_ascii=False))
        return

    items = [shape_intent(it, args.confidence_threshold) for it in raw_items]

    print(json.dumps({
        "success":                    True,
        "no_actionable_content":      False,
        "provider":                   provider_used,
        "fallback_triggered":         parse_data.get("_fallback_triggered", False),
        "gemini_avg_confidence":      parse_data.get("_gemini_avg_conf"),
        "claude_avg_confidence":      parse_data.get("_claude_avg_conf"),
        "confidence_gain":            parse_data.get("_confidence_gain"),
        "screenshot_summary":         parse_data.get("screenshot_summary", ""),
        "items_found":                len(items),
        "items_needing_confirmation": sum(1 for i in items if i["needs_confirmation"]),
        "items":                      items,
        "summary_text":               format_summary(items, parse_data, provider_used),
        "parse_notes":                parse_data.get("parse_notes"),
    }, indent=2, ensure_ascii=False))


def exit_error(message: str) -> None:
    sys.stderr.write(
        json.dumps({
            "success":      False,
            "error":        True,
            "message":      message,
            "summary_text": f"⚠️ Something went wrong: {message}",
        }) + "\n"
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
