"""
ai.py — Gemini audio processing.
Uploads a wav file, waits for a response, returns the text.
"""

import os
import time
from pathlib import Path

import subprocess

from dotenv import load_dotenv
from google import genai

load_dotenv()
_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
_MODEL  = "gemini-2.5-flash"


def _speak(text: str) -> None:
    subprocess.run(["espeak-ng", text], check=False)


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
    response = _client.models.generate_content(
        model=_MODEL,
        contents=[
            (
                "First, transcribe exactly what is said in this audio under the label 'You said:'."
                " Then, on a new line, provide a summary of the request under the label 'To summarize:'."
                " Then, on a new line, provide your response under the label 'Response:'."
            ),
            uploaded,
        ],
    )

    _client.files.delete(name=uploaded.name)
    text = response.text
    print(f"\n[AI] {text}\n")

    spoken = text.split("Response:", 1)[1].strip() if "Response:" in text else text
    _speak(spoken)

    return text
