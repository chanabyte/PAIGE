"""
tools.py — Function definitions and Gemini tool schemas.
Add new capabilities here; ai.py picks them up automatically.
"""

import os

import requests
from google.genai import types


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


TOOL = types.Tool(function_declarations=[
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
    )
])

FUNCTIONS = {"get_weather": get_weather}
