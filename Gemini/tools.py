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
    ]
)

FUNCTIONS = {
    "get_weather": get_weather,
    "connect_calendar": connect_calendar,
    "disconnect_calendar": disconnect_calendar,
    "get_calendar_events": get_calendar_events,
}
