"""
tools.py — Function definitions and Gemini tool schemas.
Add new capabilities here; ai.py picks them up automatically.
"""

import os

import requests
from google.genai import types

from Google import calendar_api
import ui_commands


def get_weather(city: str) -> dict:
    resp = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={
            "q": city,
            "appid": os.environ["OPENWEATHER_API_KEY"],
            "units": "metric",
        },
    )
    data = resp.json()
    if resp.status_code != 200:
        return {"error": data.get("message", "Could not fetch weather")}
    return {
        "city": data["name"],
        "temperature_c": round(data["main"]["temp"]),
        "feels_like_c": round(data["main"]["feels_like"]),
        "description": data["weather"][0]["description"],
        "humidity_pct": data["main"]["humidity"],
    }


def connect_calendar() -> dict:
    """Start/continue the Google OAuth device flow and store tokens on success."""
    try:
        return calendar_api.connect_calendar()
    except Exception as e:
        return {"error": str(e)}


def disconnect_calendar() -> dict:
    try:
        return calendar_api.disconnect_calendar()
    except Exception as e:
        return {"error": str(e)}


def get_calendar_events(max_results: int = 5) -> dict:
    """Return upcoming events from the user's primary Google Calendar."""
    try:
        result = calendar_api.list_upcoming_events(max_results=max_results)
        if "events" in result:
            ui_commands.CMD.put({"action": "events", "events": result["events"]})
        return result
    except Exception as e:
        return {"error": str(e)}


def start_timer(minutes: float) -> dict:
    """Start a countdown timer for the given number of minutes."""
    minutes = max(0.1, float(minutes))
    ui_commands.CMD.put({"action": "timer", "minutes": minutes})
    return {"status": "timer_started", "minutes": minutes}


def create_calendar_event(
    title: str,
    description: str = "",
    start_datetime: str = "",
    end_datetime: str = "",
) -> dict:
    """Create an event on the user's primary Google Calendar."""
    try:
        return calendar_api.create_event(title, description, start_datetime, end_datetime)
    except Exception as e:
        return {"error": str(e)}


def create_task(title: str, notes: str = "", due_date: str = "") -> dict:
    """Create a task in the user's Google Tasks list."""
    try:
        return calendar_api.create_task(title, notes, due_date)
    except Exception as e:
        return {"error": str(e)}


def show_pomodoro() -> dict:
    """Open the Pomodoro timer selection screen on the display."""
    ui_commands.CMD.put({"action": "pomodoro_select"})
    return {"status": "pomodoro_screen_shown"}


def start_pomodoro(preset: str = "Classic") -> dict:
    """Start a Pomodoro session with the named preset (Classic, Short, Extended, Marathon)."""
    ui_commands.CMD.put({"action": "start_pomodoro", "preset": preset})
    return {"status": "pomodoro_started", "preset": preset}


TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_weather",
            description="Get the current weather for a given city.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "city": types.Schema(
                        type="STRING",
                        description="City name, e.g. London, New York",
                    )
                },
                required=["city"],
            ),
        ),
        types.FunctionDeclaration(
            name="connect_calendar",
            description=(
                "Connect Google Calendar for the current device user using a limited-input device flow. "
                "Returns a URL and code to complete sign-in if not already connected."
            ),
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="disconnect_calendar",
            description="Disconnect Google Calendar (sign out) for this device.",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="get_calendar_events",
            description="List upcoming events from the connected user's primary Google Calendar.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "max_results": types.Schema(
                        type="INTEGER",
                        description="Number of events to return (1-10).",
                    )
                },
                required=[],
            ),
        ),
        types.FunctionDeclaration(
            name="create_calendar_event",
            description="Create a new event on the user's primary Google Calendar.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "title": types.Schema(
                        type="STRING",
                        description="Event title (required).",
                    ),
                    "description": types.Schema(
                        type="STRING",
                        description="Event description (optional).",
                    ),
                    "start_datetime": types.Schema(
                        type="STRING",
                        description='Start date and time in ISO 8601 format, e.g. "2026-05-05T14:00:00". Defaults to 1 hour from now.',
                    ),
                    "end_datetime": types.Schema(
                        type="STRING",
                        description='End date and time in ISO 8601 format, e.g. "2026-05-05T15:00:00". Defaults to 1 hour after start.',
                    ),
                },
                required=["title"],
            ),
        ),
        types.FunctionDeclaration(
            name="start_timer",
            description="Start a countdown timer on the display for a given number of minutes.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "minutes": types.Schema(
                        type="NUMBER",
                        description="Duration of the timer in minutes (e.g. 30 for a 30-minute timer).",
                    )
                },
                required=["minutes"],
            ),
        ),
        types.FunctionDeclaration(
            name="create_task",
            description="Create a task in the user's Google Tasks list.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "title": types.Schema(type="STRING", description="Task title (required)."),
                    "notes": types.Schema(type="STRING", description="Optional notes or description."),
                    "due_date": types.Schema(type="STRING", description='Optional due date as ISO 8601 date, e.g. "2026-05-10".'),
                },
                required=["title"],
            ),
        ),
        types.FunctionDeclaration(
            name="show_pomodoro",
            description="Open the Pomodoro timer selection screen so the user can browse and start a session.",
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="start_pomodoro",
            description="Start a Pomodoro focus session with a named preset.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "preset": types.Schema(
                        type="STRING",
                        description='Preset name: "Classic" (25/5/4), "Short" (15/3/6), "Extended" (50/10/3), "Marathon" (90/20/2).',
                    )
                },
                required=["preset"],
            ),
        ),
    ]
)

FUNCTIONS = {
    "get_weather": get_weather,
    "connect_calendar": connect_calendar,
    "disconnect_calendar": disconnect_calendar,
    "get_calendar_events": get_calendar_events,
    "create_calendar_event": create_calendar_event,
    "start_timer": start_timer,
    "create_task": create_task,
    "show_pomodoro": show_pomodoro,
    "start_pomodoro": start_pomodoro,
}
