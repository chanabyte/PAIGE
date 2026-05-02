"""
recorder.py — audio capture logic only.
Exposes start(), stop(), is_recording(), list_recordings().
GPIO/button handling lives in app.py.
"""

import signal
import subprocess
from datetime import datetime
from pathlib import Path

PW_TARGET  = "90"
OUTPUT_DIR = Path("./Recordings")
OUTPUT_DIR.mkdir(exist_ok=True)

_proc         = None
_current_file = None


def start() -> Path:
    global _proc, _current_file
    timestamp     = datetime.now().strftime("%Y%m%d_%H%M%S")
    _current_file = OUTPUT_DIR / f"recording_{timestamp}.wav"
    print(f"[REC] Starting → {_current_file}")
    _proc = subprocess.Popen(["pw-record", "--target", PW_TARGET, str(_current_file)])
    return _current_file


def stop() -> Path | None:
    global _proc, _current_file
    if _proc is None:
        return None
    print("[REC] Stopping — saving file...")
    _proc.send_signal(signal.SIGINT)
    _proc.wait()
    saved  = _current_file
    _proc  = None
    _current_file = None
    print(f"[REC] Saved → {saved}")
    return saved


def is_recording() -> bool:
    return _proc is not None


def list_recordings() -> list[Path]:
    return sorted(OUTPUT_DIR.glob("*.wav"), reverse=True)
