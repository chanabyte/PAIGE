"""
ai.py — Gemini audio processing.
Uploads a wav file, waits for a response, returns the text.
"""

import os
import re
import subprocess
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv()
_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
_MODEL  = "gemini-2.5-flash"


def _clean(text: str) -> str:
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-•]\s+', '', text, flags=re.MULTILINE)
    return text.strip()


def _speak(text: str) -> None:
    subprocess.run(["espeak-ng", "-s", "130", _clean(text)], check=False)


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

    parts = []
    if "To summarize:" in text:
        summary = text.split("To summarize:", 1)[1]
        summary = summary.split("Response:", 1)[0] if "Response:" in summary else summary
        parts.append("To summarize: " + summary.strip())
    if "Response:" in text:
        parts.append("Response: " + text.split("Response:", 1)[1].strip())

    _speak(" ".join(parts) if parts else text)
    return text
