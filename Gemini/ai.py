"""
ai.py — Gemini audio processing.
Uploads a wav file, waits for a response, returns the text.
"""

import asyncio
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

import edge_tts
from dotenv import load_dotenv
from google import genai
from google.genai import types

import config
import Gemini.tools as tool_registry

load_dotenv()
_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
_CONFIG = types.GenerateContentConfig(tools=[tool_registry.TOOL])

_PROMPT = (
    "First, transcribe exactly what is said in this audio under the label 'You said:'."
    " Then, on a new line, provide a summary of the request under the label 'To summarize:'."
    " Then, on a new line, provide your response under the label 'Response:'."
    " If the request requires a tool, call it before responding."
)

_TEXT_PROMPT = (
    "The user will give you a request as text."
    " First, restate it under the label 'You said:'."
    " Then, on a new line, provide a summary of the request under the label 'To summarize:'."
    " Then, on a new line, provide your response under the label 'Response:'."
    " If the request requires a tool, call it before responding."
)

def _clean(text: str) -> str:
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-•]\s+', '', text, flags=re.MULTILINE)
    return text.strip()


def _speak(text: str) -> None:
    cleaned = _clean(text)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp = f.name
    asyncio.run(edge_tts.Communicate(cleaned, config.VOICE).save(tmp))
    subprocess.run(["mpg123", "-q", tmp], check=False)
    Path(tmp).unlink(missing_ok=True)


def process(wav_path: Path) -> str:
    print("[AI] Uploading audio...")
    uploaded = _client.files.upload(
        file=str(wav_path),
        config={"mime_type": "audio/wav"},
    )

    while uploaded.state.name == "PROCESSING":
        time.sleep(1)
        uploaded = _client.files.get(name=uploaded.name)

    print("[AI] Waiting for response...")

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part(text=_PROMPT),
                types.Part(file_data=types.FileData(
                    file_uri=uploaded.uri,
                    mime_type="audio/wav",
                )),
            ],
        )
    ]

    response = _client.models.generate_content(
        model=config.GEMINI_MODEL, contents=contents, config=_CONFIG
    )

    fn_calls = [
        p.function_call
        for p in response.candidates[0].content.parts
        if getattr(p, "function_call", None)
    ]

    if fn_calls:
        contents.append(response.candidates[0].content)
        for fc in fn_calls:
            result = tool_registry.FUNCTIONS[fc.name](**dict(fc.args))
            print(f"[TOOL] {fc.name}({dict(fc.args)}) → {result}")
            contents.append(
                types.Content(
                    parts=[types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name,
                            response={"result": result},
                        )
                    )]
                )
            )
        follow_up = _client.models.generate_content(
            model=config.GEMINI_MODEL, contents=contents, config=_CONFIG
        )
        text = follow_up.text
    else:
        text = response.text

    _client.files.delete(name=uploaded.name)

    print(f"\n[AI] {text}\n")

    if fn_calls:
        _speak(text)
    else:
        spoken_parts = []
        if "To summarize:" in text:
            summary = text.split("To summarize:", 1)[1]
            summary = summary.split("Response:", 1)[0] if "Response:" in summary else summary
            spoken_parts.append("To summarize: " + summary.strip())
        if "Response:" in text:
            spoken_parts.append("Response: " + text.split("Response:", 1)[1].strip())
        _speak(" ".join(spoken_parts) if spoken_parts else text)

    return text


def process_text(user_text: str) -> str:
    """Test helper: run Gemini tool-calling from plain text (no audio upload)."""

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part(text=_TEXT_PROMPT + "\n\nUser request: " + user_text.strip()),
            ],
        )
    ]

    response = _client.models.generate_content(
        model=config.GEMINI_MODEL, contents=contents, config=_CONFIG
    )

    fn_calls = [
        p.function_call
        for p in response.candidates[0].content.parts
        if getattr(p, "function_call", None)
    ]

    if fn_calls:
        contents.append(response.candidates[0].content)
        for fc in fn_calls:
            result = tool_registry.FUNCTIONS[fc.name](**dict(fc.args))
            print(f"[TOOL] {fc.name}({dict(fc.args)}) → {result}")
            contents.append(
                types.Content(
                    parts=[types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name,
                            response={"result": result},
                        )
                    )]
                )
            )
        follow_up = _client.models.generate_content(
            model=config.GEMINI_MODEL, contents=contents, config=_CONFIG
        )
        text = follow_up.text
    else:
        text = response.text

    print(f"\n[AI] {text}\n")
    return text
