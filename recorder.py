"""
recorder.py — GPIO button-controlled audio recorder (PipeWire)
Press once to start, press again to stop and save.

Prereqs:
    pip install gpiozero

Wiring:
    Button: GPIO17 (BCM) → GND  (uses internal pull-up)

Usage:
    python recorder.py
"""

import subprocess
import signal
from pathlib import Path
from datetime import datetime
from gpiozero import Button

# ── Config ────────────────────────────────────────────────────────────────────
GPIO_PIN      = 17      # BCM pin number
PW_TARGET     = "90"    # pw-record target ID (your Boult mic)
OUTPUT_DIR    = Path("./Recordings")
# ─────────────────────────────────────────────────────────────────────────────

OUTPUT_DIR.mkdir(exist_ok=True)

recording_process = None
current_file      = None


def start_recording():
    global recording_process, current_file
    timestamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
    current_file = OUTPUT_DIR / f"recording_{timestamp}.wav"

    print(f"[REC] Starting → {current_file}")
    recording_process = subprocess.Popen([
        "pw-record",
        "--target", PW_TARGET,
        str(current_file),
    ])


def stop_recording():
    global recording_process, current_file
    if recording_process is None:
        return
    print("[REC] Stopping — saving file...")
    recording_process.send_signal(signal.SIGINT)
    recording_process.wait()
    recording_process = None
    print(f"[REC] Saved → {current_file}")
    current_file = None


def on_button_press():
    if recording_process is None:
        start_recording()
    else:
        stop_recording()


# ── Main ──────────────────────────────────────────────────────────────────────
button = Button(GPIO_PIN, pull_up=True, bounce_time=0.05)
button.when_pressed = on_button_press

print(f"Ready. Button on GPIO{GPIO_PIN}.")
print(f"Saving to: {OUTPUT_DIR.resolve()}")
print("Press button to start/stop. Ctrl+C to quit.\n")

try:
    signal.pause()
except KeyboardInterrupt:
    if recording_process:
        stop_recording()
    print("\nExiting.")