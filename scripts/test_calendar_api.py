"""scripts/test_calendar_api.py

CLI harness to manually test Google Calendar integration.

Examples:
  python scripts/test_calendar_api.py connect
  python scripts/test_calendar_api.py list --max-results 5
  python scripts/test_calendar_api.py create --summary "Test" --start "2026-05-05T15:00:00Z" --end "2026-05-05T15:30:00Z"
  python scripts/test_calendar_api.py find --query "Test" --max-results 5
  python scripts/test_calendar_api.py delete --event-id <id>

Write operations require:
  GOOGLE_CALENDAR_SCOPE=https://www.googleapis.com/auth/calendar
and then reconnecting (disconnect + connect) to mint new tokens.
"""

from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from Google import calendar_api


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True))


def cmd_connect(_args: argparse.Namespace) -> int:
    _print(calendar_api.connect_calendar())
    return 0


def cmd_disconnect(_args: argparse.Namespace) -> int:
    _print(calendar_api.disconnect_calendar())
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    _print(calendar_api.list_upcoming_events(max_results=args.max_results))
    return 0


def cmd_find(args: argparse.Namespace) -> int:
    _print(
        calendar_api.find_events(
            query=args.query,
            time_min=args.time_min,
            time_max=args.time_max,
            max_results=args.max_results,
        )
    )
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    if args.dry_run:
        _print(
            {
                "dry_run": True,
                "action": "create_event",
                "summary": args.summary,
                "start": args.start,
                "end": args.end,
                "time_zone": args.time_zone,
                "location": args.location,
                "description": args.description,
            }
        )
        return 0

    _print(
        calendar_api.create_event(
            summary=args.summary,
            start=args.start,
            end=args.end,
            time_zone=args.time_zone,
            location=args.location,
            description=args.description,
        )
    )
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    if args.dry_run:
        _print(
            {
                "dry_run": True,
                "action": "update_event",
                "event_id": args.event_id,
                "summary": args.summary,
                "start": args.start,
                "end": args.end,
                "time_zone": args.time_zone,
                "location": args.location,
                "description": args.description,
            }
        )
        return 0

    _print(
        calendar_api.update_event(
            event_id=args.event_id,
            summary=args.summary,
            start=args.start,
            end=args.end,
            time_zone=args.time_zone,
            location=args.location,
            description=args.description,
        )
    )
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    if args.dry_run:
        _print({"dry_run": True, "action": "delete_event", "event_id": args.event_id})
        return 0

    _print(calendar_api.delete_event(event_id=args.event_id))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Test Google Calendar API for PAIGE")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("connect", help="Connect calendar via device flow")
    sp.set_defaults(func=cmd_connect)

    sp = sub.add_parser("disconnect", help="Disconnect calendar (remove tokens)")
    sp.set_defaults(func=cmd_disconnect)

    sp = sub.add_parser("list", help="List upcoming events")
    sp.add_argument("--max-results", type=int, default=5)
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("find", help="Search events and return ids")
    sp.add_argument("--query", required=True)
    sp.add_argument("--time-min", default="")
    sp.add_argument("--time-max", default="")
    sp.add_argument("--max-results", type=int, default=5)
    sp.set_defaults(func=cmd_find)

    sp = sub.add_parser("create", help="Create an event")
    sp.add_argument("--summary", required=True)
    sp.add_argument("--start", required=True)
    sp.add_argument("--end", required=True)
    sp.add_argument("--time-zone", default="")
    sp.add_argument("--location", default="")
    sp.add_argument("--description", default="")
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=cmd_create)

    sp = sub.add_parser("update", help="Update an event")
    sp.add_argument("--event-id", required=True)
    sp.add_argument("--summary", default="")
    sp.add_argument("--start", default="")
    sp.add_argument("--end", default="")
    sp.add_argument("--time-zone", default="")
    sp.add_argument("--location", default="")
    sp.add_argument("--description", default="")
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=cmd_update)

    sp = sub.add_parser("delete", help="Delete an event")
    sp.add_argument("--event-id", required=True)
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=cmd_delete)

    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
