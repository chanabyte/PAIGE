"""
ai.py — Gemini audio processing.
Uploads a wav file, waits for a response, returns the text.
"""

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv()
_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
_MODEL  = "gemini-2.5-flash"


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
                " Then, on a new line, provide your response under the label 'Response:'."
            ),
            uploaded,
        ],
    )

    _client.files.delete(name=uploaded.name)
    return response.text
