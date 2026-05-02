"""GPIO button-controlled audio recorder for Raspberry Pi.

Behavior:
- First button press starts recording from the configured ALSA input.
- Second button press stops the recording and saves a .wav file in ./Recordings.

Prereqs on Raspberry Pi OS:
- A working ALSA capture source (your Bluetooth mic must appear as an ALSA device).
- `arecord` available (package: alsa-utils).
- `gpiozero` available (usually preinstalled).

Wiring note:
- Default expects a momentary button from GPIO17 (BCM) to GND.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Config:
	gpio_pin_bcm: int = int(os.getenv("GPIO_PIN_BCM", "17"))
	bounce_time_s: float = float(os.getenv("BOUNCE_TIME_S", "0.15"))

	recordings_dir: Path = Path(__file__).resolve().parent / "Recordings"

	alsa_device: str | None = os.getenv("ALSA_DEVICE") or None
	sample_rate_hz: int = int(os.getenv("SAMPLE_RATE_HZ", "16000"))
	channels: int = int(os.getenv("CHANNELS", "1"))
	sample_format: str = os.getenv("SAMPLE_FORMAT", "S16_LE")

	arecord_path: str = os.getenv("ARECORD", "arecord")
	stop_timeout_s: float = float(os.getenv("STOP_TIMEOUT_S", "5"))


class Recorder:
	def __init__(self, config: Config) -> None:
		self._config = config
		self._lock = threading.Lock()
		self._proc: subprocess.Popen[bytes] | None = None
		self._current_path: Path | None = None

	@property
	def is_recording(self) -> bool:
		proc = self._proc
		return proc is not None and proc.poll() is None

	def toggle(self) -> None:
		with self._lock:
			if self.is_recording:
				self._stop_locked()
			else:
				self._start_locked()

	def _start_locked(self) -> None:
		self._config.recordings_dir.mkdir(parents=True, exist_ok=True)
		timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
		out_path = self._config.recordings_dir / f"recording_{timestamp}.wav"

		cmd: list[str] = [
			self._config.arecord_path,
			"-t",
			"wav",
			"-f",
			self._config.sample_format,
			"-r",
			str(self._config.sample_rate_hz),
			"-c",
			str(self._config.channels),
		]
		if self._config.alsa_device:
			cmd += ["-D", self._config.alsa_device]
		cmd.append(str(out_path))

		try:
			proc = subprocess.Popen(
				cmd,
				stdin=subprocess.DEVNULL,
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL,
				start_new_session=True,
			)
		except FileNotFoundError as e:
			raise SystemExit(
				"`arecord` not found. Install it with: sudo apt-get install alsa-utils"
			) from e

		self._proc = proc
		self._current_path = out_path
		print(f"Recording started: {out_path}")

	def _stop_locked(self) -> None:
		proc = self._proc
		out_path = self._current_path

		if proc is None:
			return

		if proc.poll() is None:
			try:
				os.killpg(proc.pid, signal.SIGINT)
			except ProcessLookupError:
				pass

			deadline = time.monotonic() + self._config.stop_timeout_s
			while time.monotonic() < deadline and proc.poll() is None:
				time.sleep(0.05)

		if proc.poll() is None:
			try:
				os.killpg(proc.pid, signal.SIGTERM)
			except ProcessLookupError:
				pass

		self._proc = None
		self._current_path = None
		print(f"Recording stopped: {out_path}")


def main() -> None:
	config = Config()
	print("Button-controlled audio recorder")
	print(f"GPIO pin (BCM): {config.gpio_pin_bcm}")
	print(f"Recordings dir: {config.recordings_dir}")
	print(f"ALSA device: {config.alsa_device or '(default)'}")

	try:
		from gpiozero import Button  # type: ignore
		from signal import pause
	except Exception as e:
		raise SystemExit(
			"gpiozero not available. On Raspberry Pi OS: sudo apt-get install python3-gpiozero"
		) from e

	recorder = Recorder(config)
	button = Button(config.gpio_pin_bcm, pull_up=True, bounce_time=config.bounce_time_s)

	def _on_press() -> None:
		try:
			recorder.toggle()
		except Exception as exc:
			print(f"Error toggling recorder: {exc}")

	button.when_pressed = _on_press

	print("Ready. Press button to start/stop recording.")
	pause()


if __name__ == "__main__":
	main()
