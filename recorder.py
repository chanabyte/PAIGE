"""
recorder.py — audio capture logic only.
Exposes start(), stop(), is_recording(), list_recordings().
GPIO/button handling lives in app.py.
Keeps at most MAX_RECORDINGS files, deleting the oldest on each new recording.
"""

import signal
import subprocess
from pathlib import Path

PW_TARGET      = "90"
OUTPUT_DIR     = Path("./Recordings")
MAX_RECORDINGS = 3
FILE_PREFIX    = "UserAudio"

OUTPUT_DIR.mkdir(exist_ok=True)

_proc         = None
_current_file = None


def _next_path() -> Path:
    existing = sorted(OUTPUT_DIR.glob(f"{FILE_PREFIX}_*.wav"))
    while len(existing) >= MAX_RECORDINGS:
        existing.pop(0).unlink()
        existing = sorted(OUTPUT_DIR.glob(f"{FILE_PREFIX}_*.wav"))
    next_num = int(existing[-1].stem.split("_")[-1]) + 1 if existing else 1
    return OUTPUT_DIR / f"{FILE_PREFIX}_{next_num:03d}.wav"


def start() -> Path:
    global _proc, _current_file
    _current_file = _next_path()
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
