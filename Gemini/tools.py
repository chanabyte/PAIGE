"""
tools.py — Function definitions and Gemini tool schemas.
Add new capabilities here; ai.py picks them up automatically.
"""

import os

import requests
from google.genai import types

from Google import calendar_api


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
        return calendar_api.list_upcoming_events(max_results=max_results)
    except Exception as e:
        return {"error": str(e)}


def find_calendar_events(query: str, time_min: str = "", time_max: str = "", max_results: int = 5) -> dict:
    """Search calendar events and return ids for follow-up actions."""
    try:
        return calendar_api.find_events(
            query=query,
            time_min=time_min.strip() or None,
            time_max=time_max.strip() or None,
            max_results=max_results,
        )
    except Exception as e:
        return {"error": str(e)}


def create_calendar_event(
    summary: str,
    start: str,
    end: str,
    time_zone: str = "",
    location: str = "",
    description: str = "",
) -> dict:
    """Create a new calendar event."""
    try:
        return calendar_api.create_event(
            summary=summary,
            start=start,
            end=end,
            time_zone=time_zone.strip() or None,
            location=location.strip() or None,
            description=description.strip() or None,
        )
    except Exception as e:
        return {"error": str(e)}


def update_calendar_event(
    event_id: str,
    summary: str = "",
    start: str = "",
    end: str = "",
    time_zone: str = "",
    location: str = "",
    description: str = "",
) -> dict:
    """Update (patch) an existing calendar event by id."""
    try:
        return calendar_api.update_event(
            event_id=event_id,
            summary=summary.strip() or None,
            start=start.strip() or None,
            end=end.strip() or None,
            time_zone=time_zone.strip() or None,
            location=location.strip() or None,
            description=description.strip() or None,
        )
    except Exception as e:
        return {"error": str(e)}


def delete_calendar_event(event_id: str) -> dict:
    """Delete a calendar event by id."""
    try:
        return calendar_api.delete_event(event_id=event_id)
    except Exception as e:
        return {"error": str(e)}


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
            name="find_calendar_events",
            description=(
                "Search events in Google Calendar and return matching event ids. "
                "Use this before updating or deleting an event."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "query": types.Schema(
                        type="STRING",
                        description="Search query, e.g. 'dentist' or 'CS lecture'.",
                    ),
                    "time_min": types.Schema(
                        type="STRING",
                        description="Optional ISO/RFC3339 lower bound (e.g. 2026-05-04T00:00:00Z).",
                    ),
                    "time_max": types.Schema(
                        type="STRING",
                        description="Optional ISO/RFC3339 upper bound (e.g. 2026-05-11T00:00:00Z).",
                    ),
                    "max_results": types.Schema(
                        type="INTEGER",
                        description="Number of matches to return (1-10).",
                    ),
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="create_calendar_event",
            description=(
                "Create a new event on the user's primary Google Calendar. "
                "Start/end can be RFC3339 datetime or YYYY-MM-DD for all-day events."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "summary": types.Schema(type="STRING", description="Event title."),
                    "start": types.Schema(
                        type="STRING",
                        description="Start datetime (RFC3339) or date (YYYY-MM-DD).",
                    ),
                    "end": types.Schema(
                        type="STRING",
                        description="End datetime (RFC3339) or date (YYYY-MM-DD).",
                    ),
                    "time_zone": types.Schema(
                        type="STRING",
                        description="IANA timezone (e.g. Europe/London). Optional.",
                    ),
                    "location": types.Schema(type="STRING", description="Optional location."),
                    "description": types.Schema(type="STRING", description="Optional description."),
                },
                required=["summary", "start", "end"],
            ),
        ),
        types.FunctionDeclaration(
            name="update_calendar_event",
            description="Update an existing calendar event by id.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "event_id": types.Schema(type="STRING", description="Event id to update."),
                    "summary": types.Schema(type="STRING", description="New title (optional)."),
                    "start": types.Schema(
                        type="STRING",
                        description="New start datetime/date (optional).",
                    ),
                    "end": types.Schema(
                        type="STRING",
                        description="New end datetime/date (optional).",
                    ),
                    "time_zone": types.Schema(
                        type="STRING",
                        description="IANA timezone (optional).",
                    ),
                    "location": types.Schema(type="STRING", description="New location (optional)."),
                    "description": types.Schema(type="STRING", description="New description (optional)."),
                },
                required=["event_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="delete_calendar_event",
            description="Delete a calendar event by id.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "event_id": types.Schema(type="STRING", description="Event id to delete."),
                },
                required=["event_id"],
            ),
        ),
    ]
)

FUNCTIONS = {
    "get_weather": get_weather,
    "connect_calendar": connect_calendar,
    "disconnect_calendar": disconnect_calendar,
    "get_calendar_events": get_calendar_events,
    "find_calendar_events": find_calendar_events,
    "create_calendar_event": create_calendar_event,
    "update_calendar_event": update_calendar_event,
    "delete_calendar_event": delete_calendar_event,
}
