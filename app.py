"""
app.py — Flask hub + GPIO button listener.
Button press toggles recording via recorder.py.
"""

import signal
import threading
from flask import Flask, jsonify
from gpiozero import Button
import config
import Audio.recorder as recorder
import Gemini.ai as ai

app = Flask(__name__)


def _send_to_ai(wav_path):
    ai.process(wav_path)


def on_button_press():
    if recorder.is_recording():
        saved = recorder.stop()
        if saved:
            threading.Thread(target=_send_to_ai, args=(saved,), daemon=True).start()
    else:
        recorder.start()


button = Button(config.GPIO_PIN, pull_up=True, bounce_time=0.05)
button.when_pressed = on_button_press


@app.route("/api/status")
def status():
    return jsonify({"recording": recorder.is_recording()})


@app.route("/api/recordings")
def recordings():
    files = recorder.list_recordings()
    return jsonify([str(f) for f in files])


if __name__ == "__main__":
    print(f"PAIGE ready. Button on GPIO{config.GPIO_PIN}.")
    try:
        app.run(host="0.0.0.0", port=5000)
    except KeyboardInterrupt:
        if recorder.is_recording():
            recorder.stop()
        print("\nExiting.")
