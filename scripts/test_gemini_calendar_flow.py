"""scripts/test_gemini_calendar_flow.py

Runs Gemini function-calling from *text*, which is useful for quickly
iterating on calendar tools without recording audio.

Example:
  python scripts/test_gemini_calendar_flow.py "Create a calendar event tomorrow at 3pm called Dentist"
"""

from __future__ import annotations

from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from Gemini import ai


def main(argv: list[str]) -> int:
    if not argv:
        print("Usage: python scripts/test_gemini_calendar_flow.py \"<request>\"")
        return 2
    user_text = " ".join(argv).strip()
    ai.process_text(user_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
