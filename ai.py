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

load_dotenv()
_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
_MODEL  = "gemini-2.5-flash"
_VOICE  = "en-GB-SoniaNeural"

#Other options:
#------Personal favourite was Sonia, but you can choose any of these:
# _VOICE  = "en-US-EmmaMultilingualNeural"
# _VOICE  = "en-AU-WilliamMultilingualNeural"
# _VOICE  = "en-AU-NatashaNeural"
# _VOICE  = "en-CA-ClaraNeural"
# _VOICE  = "en-CA-LiamNeural"
# _VOICE  = "en-HK-YanNeural"
# _VOICE  = "en-HK-SamNeural"
# _VOICE  = "en-IN-NeerjaExpressiveNeural"
# _VOICE  = "en-IN-NeerjaNeural"
# _VOICE  = "en-IN-PrabhatNeural"
# _VOICE  = "en-IE-ConnorNeural"
# _VOICE  = "en-IE-EmilyNeural"
# _VOICE  = "en-KE-AsiliaNeural"
# _VOICE  = "en-KE-ChilembaNeural"
# _VOICE  = "en-NZ-MitchellNeural"
# _VOICE  = "en-NZ-MollyNeural"
# _VOICE  = "en-NG-AbeoNeural"
# _VOICE  = "en-NG-EzinneNeural"
# _VOICE  = "en-PH-JamesNeural"
# _VOICE  = "en-PH-RosaNeural"
# _VOICE  = "en-US-AvaNeural"
# _VOICE  = "en-US-AndrewNeural"
# _VOICE  = "en-US-EmmaNeural"
# _VOICE  = "en-US-BrianNeural"
# _VOICE  = "en-SG-LunaNeural"
# _VOICE  = "en-SG-WayneNeural"
# _VOICE  = "en-ZA-LeahNeural"
# _VOICE  = "en-ZA-LukeNeural"
# _VOICE  = "en-TZ-ElimuNeural"
# _VOICE  = "en-TZ-ImaniNeural"
# _VOICE  = "en-GB-LibbyNeural"
# _VOICE  = "en-GB-MaisieNeural"
# _VOICE  = "en-GB-RyanNeural"
# _VOICE  = "en-GB-SoniaNeural"
# _VOICE  = "en-GB-ThomasNeural"
# _VOICE  = "en-US-AnaNeural"
# _VOICE  = "en-US-AndrewMultilingualNeural"
# _VOICE  = "en-US-AriaNeural"
# _VOICE  = "en-US-AvaMultilingualNeural"
# _VOICE  = "en-US-BrianMultilingualNeural"
# _VOICE  = "en-US-ChristopherNeural"
# _VOICE  = "en-US-EmmaMultilingualNeural"
# _VOICE  = "en-US-EricNeural"
# _VOICE  = "en-US-GuyNeural"
# _VOICE  = "en-US-JennyNeural"
# _VOICE  = "en-US-MichelleNeural"
# _VOICE  = "en-US-RogerNeural"
# _VOICE  = "en-US-SteffanNeural"
#------These are all the ones I could find online, you guys can choose later



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
    asyncio.run(edge_tts.Communicate(cleaned, _VOICE).save(tmp))
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
