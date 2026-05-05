"""
PAIGE UI — ILI9486 framebuffer display (480×320, /dev/fb2)
GPIO 17 starts/stops voice notes, GPIO 22 browses older notes,
and GPIO 23 plays the selected note.
Gemini function calling routes to timer / events screens.
"""
from __future__ import annotations

import os
import subprocess
import struct
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import ui_commands
import Audio.recorder as recorder
import Gemini.ai as ai

# ── Framebuffer ────────────────────────────────────────────────────────────────
W, H = config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT
FB   = config.DISPLAY_FB
_buf = bytearray(W * H * 2)


def _px(r: int, g: int, b: int) -> bytes:
    val = ((r & 0xF8) >> 3) | ((g & 0xFC) << 3) | ((b & 0xF8) << 8)
    return struct.pack('<H', val)


BLACK  = b'\x00\x00'
WHITE  = b'\xff\xff'
GRAY   = _px(160, 160, 160)
DGRAY  = _px(50,  50,  50)
GREEN  = _px(0,   200, 80)
RED    = _px(220, 40,  40)
BLUE   = _px(40,  120, 220)
YELLOW = _px(240, 200, 0)
ORANGE = _px(240, 130, 0)
TEAL   = _px(0,   180, 180)


def _fill(x: int, y: int, w: int, h: int, color: bytes) -> None:
        # Mirror X: region [x, x+w) maps to [W-x-w, W-x) on the mirrored hardware
    mx = W - x - w
    row = color * w
    for ry in range(max(0, y), min(y + h, H)):
        i = (ry * W + mx) * 2
        _buf[i:i + len(row)] = row


def _px_set(x: int, y: int, color: bytes) -> None:
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + (W - 1 - x)) * 2  # mirror X
        _buf[i:i + 2] = color


# Physical framebuffer is portrait (320×480); we design in landscape (480×320)
# and rotate in flush(). Flip _ROTATE_CW if the image appears upside-down.
_ROTATE_CW = False

def flush() -> None:
    import numpy as np
    arr = np.frombuffer(_buf, dtype='<u2').reshape(H, W)  # (320, 480)
    portrait = np.rot90(arr, k=3) if _ROTATE_CW else np.rot90(arr, k=1)  # → (480, 320)
    with open(FB, 'wb') as f:
        f.write(portrait.tobytes())


# ── Bitmap font ────────────────────────────────────────────────────────────────
# 5×7 column-major, bit 0 = top row.
def _bm(rows: list[str]) -> list[int]:
    """Convert list of 5-char '#'/'.' strings to 5 column bitmasks."""
    cols = []
    for c in range(5):
        mask = 0
        for r, row in enumerate(rows):
            if len(row) > c and row[c] == '#':
                mask |= 1 << r
        cols.append(mask)
    return cols


_FONT: dict[str, list[int]] = {
    '0': _bm(['.###.', '#...#', '#...#', '#.#.#', '#...#', '#...#', '.###.']),
    '1': _bm(['..#..', '.##..', '..#..', '..#..', '..#..', '..#..', '.###.']),
    '2': _bm(['.###.', '#...#', '....#', '..##.', '.#...', '#....', '#####']),
    '3': _bm(['.###.', '#...#', '....#', '.###.', '....#', '#...#', '.###.']),
    '4': _bm(['#...#', '#...#', '#...#', '#####', '....#', '....#', '....#']),
    '5': _bm(['#####', '#....', '#....', '####.', '....#', '#...#', '.###.']),
    '6': _bm(['.###.', '#....', '#....', '####.', '#...#', '#...#', '.###.']),
    '7': _bm(['#####', '....#', '...#.', '..#..', '.#...', '.#...', '.#...']),
    '8': _bm(['.###.', '#...#', '#...#', '.###.', '#...#', '#...#', '.###.']),
    '9': _bm(['.###.', '#...#', '#...#', '.####', '....#', '#...#', '.###.']),
    ':': _bm(['...',   '.##.', '.##.',  '....',  '.##.', '.##.', '...']),
    ' ': _bm(['.....',  '.....',  '.....',  '.....',  '.....',  '.....',  '.....']),
    'A': _bm(['.###.', '#...#', '#...#', '#####', '#...#', '#...#', '#...#']),
    'B': _bm(['####.', '#...#', '#...#', '####.', '#...#', '#...#', '####.']),
    'C': _bm(['.###.', '#...#', '#....', '#....', '#....', '#...#', '.###.']),
    'D': _bm(['####.', '#...#', '#...#', '#...#', '#...#', '#...#', '####.']),
    'E': _bm(['#####', '#....', '#....', '####.', '#....', '#....', '#####']),
    'F': _bm(['#####', '#....', '#....', '####.', '#....', '#....', '#....']),
    'G': _bm(['.###.', '#...#', '#....', '#.###', '#...#', '#...#', '.####']),
    'H': _bm(['#...#', '#...#', '#...#', '#####', '#...#', '#...#', '#...#']),
    'I': _bm(['.###.', '..#..', '..#..', '..#..', '..#..', '..#..', '.###.']),
    'L': _bm(['#....', '#....', '#....', '#....', '#....', '#....', '#####']),
    'M': _bm(['#...#', '##.##', '#.#.#', '#...#', '#...#', '#...#', '#...#']),
    'N': _bm(['#...#', '##..#', '#.#.#', '#..##', '#...#', '#...#', '#...#']),
    'O': _bm(['.###.', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.']),
    'P': _bm(['####.', '#...#', '#...#', '####.', '#....', '#....', '#....']),
    'R': _bm(['####.', '#...#', '#...#', '####.', '#.#..', '#..#.', '#...#']),
    'S': _bm(['.###.', '#...#', '#....', '.###.', '....#', '#...#', '.###.']),
    'T': _bm(['#####', '..#..', '..#..', '..#..', '..#..', '..#..', '..#..']),
    'U': _bm(['#...#', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.']),
    'V': _bm(['#...#', '#...#', '#...#', '#...#', '#...#', '.#.#.', '..#..']),
    'W': _bm(['#...#', '#...#', '#...#', '#.#.#', '#.#.#', '##.##', '#...#']),
    'Y': _bm(['#...#', '#...#', '.#.#.', '..#..', '..#..', '..#..', '..#..']),
    'a': _bm(['.....',  '.###.',  '....#',  '.####',  '#...#',  '#..##',  '.##.#']),
    'b': _bm(['#....', '#....', '####.', '#...#', '#...#', '#...#', '####.']),
    'c': _bm(['.....',  '.###.',  '#....',  '#....',  '#....',  '#...#',  '.###.']),
    'd': _bm(['....#', '....#', '.####', '#...#', '#...#', '#...#', '.####']),
    'e': _bm(['.....',  '.###.',  '#...#',  '#####',  '#....',  '#...#',  '.###.']),
    'f': _bm(['..##.', '.#...', '.#...', '####.', '.#...', '.#...', '.#...']),
    'g': _bm(['.....',  '.####',  '#...#',  '#...#',  '.####',  '....#',  '.###.']),
    'h': _bm(['#....', '#....', '####.', '#...#', '#...#', '#...#', '#...#']),
    'i': _bm(['..#..', '.....', '..#..', '..#..', '..#..', '..#..', '..#..']),
    'k': _bm(['#....', '#..#.', '#.#..', '##...', '#.#..', '#..#.', '#...#']),
    'l': _bm(['.##..', '..#..', '..#..', '..#..', '..#..', '..#..', '.###.']),
    'm': _bm(['.....',  '#.#..',  '##.##',  '#.#.#',  '#...#',  '#...#',  '#...#']),
    'n': _bm(['.....',  '####.',  '#...#',  '#...#',  '#...#',  '#...#',  '#...#']),
    'o': _bm(['.....',  '.###.',  '#...#',  '#...#',  '#...#',  '#...#',  '.###.']),
    'p': _bm(['.....',  '####.',  '#...#',  '#...#',  '####.',  '#....',  '#....']),
    'r': _bm(['.....',  '.###.',  '#....',  '#....',  '#....',  '#....',  '.....']),
    's': _bm(['.....',  '.###.',  '#....',  '.###.',  '....#',  '#...#',  '.###.']),
    't': _bm(['..#..', '#####', '..#..', '..#..', '..#..', '..#..', '..###']),
    'u': _bm(['.....',  '#...#',  '#...#',  '#...#',  '#...#',  '#..##',  '.##.#']),
    'v': _bm(['.....',  '#...#',  '#...#',  '#...#',  '#...#',  '.#.#.',  '..#..']),
    'w': _bm(['.....',  '#...#',  '#...#',  '#.#.#',  '#.#.#',  '##.##',  '#...#']),
    'y': _bm(['.....',  '#...#',  '#...#',  '.####',  '....#',  '#...#',  '.###.']),
    '!': _bm(['..#..', '..#..', '..#..', '..#..', '..#..', '.....', '..#..']),
    '.': _bm(['.....',  '.....',  '.....',  '.....',  '.....',  '.##..',  '.##..']),
    ',': _bm(['.....',  '.....',  '.....',  '.....',  '.##..',  '.#...',  '#....']),
    '-': _bm(['.....',  '.....',  '.....',  '#####',  '.....',  '.....',  '.....']),
    '/': _bm(['....#', '...#.', '..#..', '.#...', '#....', '#....', '.....']),
    "'": _bm(['..#..', '..#..', '.#...', '.....', '.....', '.....', '.....']),
}


def _draw_text(text: str, cx: int, cy: int, color: bytes, scale: int = 1) -> None:
    """Draw text centered at (cx, cy). scale multiplies each pixel."""
    cw = 5 * scale
    gap = max(1, scale)
    total_w = len(text) * (cw + gap) - gap
    sx = cx - total_w // 2
    sy = cy - (7 * scale) // 2
    for ch in text:
        cols = _FONT.get(ch, _FONT.get(' ', [0] * 5))
        for ci, col_bits in enumerate(cols):
            for ri in range(7):
                if col_bits & (1 << ri):
                    for bx in range(scale):
                        for by in range(scale):
                            _px_set(sx + ci * scale + bx, sy + ri * scale + by, color)
        sx += cw + gap


def _draw_text_left(text: str, x: int, y: int, color: bytes, scale: int = 1) -> None:
    """Draw text left-aligned at (x, y = top of text)."""
    cw = 5 * scale
    gap = max(1, scale)
    sx = x
    sy = y
    for ch in text:
        cols = _FONT.get(ch, _FONT.get(' ', [0] * 5))
        for ci, col_bits in enumerate(cols):
            for ri in range(7):
                if col_bits & (1 << ri):
                    for bx in range(scale):
                        for by in range(scale):
                            _px_set(sx + ci * scale + bx, sy + ri * scale + by, color)
        sx += cw + gap


def _draw_rect_outline(x: int, y: int, w: int, h: int, color: bytes) -> None:
    _fill(x, y, w, 2, color)
    _fill(x, y + h - 2, w, 2, color)
    _fill(x, y, 2, h, color)
    _fill(x + w - 2, y, 2, h, color)


def _draw_mic_icon(cx: int, cy: int, color: bytes, scale: int = 1) -> None:
    body_w = 18 * scale
    body_h = 28 * scale
    stem_w = 6 * scale
    stem_h = 12 * scale
    base_w = 24 * scale
    base_h = 4 * scale

    _fill(cx - body_w // 2, cy - body_h // 2, body_w, body_h, color)
    _fill(cx - stem_w // 2, cy + body_h // 2 - 2 * scale, stem_w, stem_h, color)
    _fill(cx - base_w // 2, cy + body_h // 2 + stem_h - scale, base_w, base_h, color)
    _fill(cx - body_w // 2, cy - body_h // 2 - 4 * scale, body_w, 4 * scale, color)


def _sync_recordings() -> list[Path]:
    recordings = recorder.list_recordings()
    selected = _state["selected_recording"]
    if recordings:
        if selected >= len(recordings):
            selected = len(recordings) - 1
    else:
        selected = 0
    _state["recordings"] = recordings
    _state["selected_recording"] = selected
    return recordings


def _selected_recording() -> Path | None:
    recordings = _state["recordings"]
    if not recordings:
        return None
    index = max(0, min(_state["selected_recording"], len(recordings) - 1))
    return recordings[index]


def _set_status(message: str) -> None:
    with _lock:
        _state["status"] = message


def _play_wav(path: Path) -> None:
    for command in (("pw-play", str(path)), ("aplay", str(path))):
        try:
            subprocess.run(command, check=False)
            return
        except FileNotFoundError:
            continue
    print(f"[UI] No audio player found for {path}")


def _start_recording() -> None:
    if recorder.is_recording():
        return
    recorder.start()
    with _lock:
        _state["recording"] = True
        _state["screen"] = "recording"
        _state["status"] = "Record voice notes"


def _stop_recording() -> Path | None:
    if not recorder.is_recording():
        return None
    wav = recorder.stop()
    with _lock:
        _state["recording"] = False
        _state["screen"] = "processing"
        _state["status"] = "Saved voice note"
    if wav:
        _sync_recordings()
        with _lock:
            recordings = _state["recordings"]
            if wav in recordings:
                _state["selected_recording"] = recordings.index(wav)
    return wav


def _cycle_previous_recording() -> None:
    _sync_recordings()
    with _lock:
        recordings = _state["recordings"]
        if not recordings:
            return
        _state["selected_recording"] = (_state["selected_recording"] - 1) % len(recordings)
        _state["status"] = f"Selected {recordings[_state['selected_recording']].name}"


def _play_selected_recording() -> None:
    _sync_recordings()
    recording = _selected_recording()
    if recording is None:
        _set_status("No saved voice notes yet")
        return

    def _runner() -> None:
        with _lock:
            _state["screen"] = "playing"
            _state["status"] = f"Playing {recording.name}"
        _play_wav(recording)
        with _lock:
            if _state["screen"] == "playing":
                _state["screen"] = "home"

    threading.Thread(target=_runner, daemon=True).start()


def _draw_play_icon(cx: int, cy: int, color: bytes, scale: int = 1) -> None:
    width = 8 * scale
    for offset in range(width):
        height = max(1, offset // 2 + 1)
        for row in range(-height, height + 1):
            _px_set(cx - width // 2 + offset, cy + row, color)


def _draw_recording_strip() -> None:
    recordings = _sync_recordings()
    tiles = 1 + len(recordings)
    tile_w = 92
    tile_h = 46
    gap = 8
    total_w = tiles * tile_w + (tiles - 1) * gap
    start_x = max(10, (W - total_w) // 2)
    y = 262

    for index in range(tiles):
        x = start_x + index * (tile_w + gap)
        selected = index == _state["selected_recording"] + 1
        tile_color = BLUE if selected else DGRAY
        _fill(x, y, tile_w, tile_h, tile_color)
        _draw_rect_outline(x, y, tile_w, tile_h, TEAL if selected else GRAY)

        if index == 0:
            _draw_mic_icon(x + tile_w // 2, y + 15, WHITE, scale=1)
            _draw_text("NEW", x + tile_w // 2, y + 35, WHITE, scale=1)
        else:
            recording = recordings[index - 1]
            _draw_play_icon(x + 20, y + 18, WHITE, scale=1)
            suffix = recording.stem.split("_")[-1]
            _draw_text(suffix[-2:], x + 58, y + 17, WHITE, scale=1)



# ── State ──────────────────────────────────────────────────────────────────────
GPIO_RECORD = 26
GPIO_NEXT   = 27
GPIO_PREV   = 22
GPIO_ACTION = 6
GPIO_HOME   = 23

PAGES = ["home", "calendar", "pomodoro_select"]

POMODORO_PRESETS = [
    {"name": "Classic",   "work": 25, "break": 5,  "reps": 4},
    {"name": "Short",     "work": 15, "break": 3,  "reps": 6},
    {"name": "Extended",  "work": 50, "break": 10, "reps": 3},
    {"name": "Marathon",  "work": 90, "break": 20, "reps": 2},
]

_state = {
    "screen": "home",
    "recording": False,
    "selected_recording": 0,
    "recordings": [],
    "timer_end": None,
    "timer_mins": 0,
    "events": [],           # Gemini-triggered events overlay
    "dot_phase": 0,
    "status": "",
    # Calendar page
    "cal_events": [],
    "cal_scroll": 0,
    "cal_loading": False,
    # Pomodoro
    "pomo_preset": 0,
    "pomo_phase": "work",   # "work" | "break" | "done"
    "pomo_rep": 1,
    "pomo_end": None,
}

_lock = threading.Lock()


# ── Screen renderers ───────────────────────────────────────────────────────────
def _screen_home() -> None:
    _fill(0, 0, W, H, BLACK)
    now = datetime.now()
    _draw_text(now.strftime("%H:%M"), W // 2, 108, WHITE, scale=6)
    _draw_text(now.strftime(":%S"), W // 2 + 82, 148, GRAY, scale=3)
    _draw_text(now.strftime("%A  %d %b %Y"), W // 2, 196, GRAY, scale=2)
    _fill(40, 218, W - 80, 1, DGRAY)
    _draw_text("PAIGE", W // 2, 246, TEAL, scale=2)
    status = _state["status"] or "27 calendar  24 record  23 home"
    _draw_text(status[:36], W // 2, 295, DGRAY, scale=1)


def _screen_recording() -> None:
    _fill(0, 0, W, H, BLACK)
    phase = _state["dot_phase"]
    border_color = RED if (phase % 6) < 3 else _px(140, 20, 20)
    _fill(0, 0, W, 4, border_color)
    _fill(0, H - 4, W, 4, border_color)
    _fill(0, 0, 4, H, border_color)
    _fill(W - 4, 0, 4, H, border_color)
    _draw_mic_icon(W // 2, 82, RED, scale=3)
    _draw_text("Record voice notes", W // 2, 146, RED, scale=3)

    dots = "." * ((phase % 3) + 1)
    _draw_text(f"Recording{dots}", W // 2, 200, WHITE, scale=2)
    _draw_text("24 stop and save", W // 2, 286, GRAY, scale=1)


def _screen_processing() -> None:
    _fill(0, 0, W, H, BLACK)
    phase = _state["dot_phase"]
    dots = "." * ((phase % 3) + 1)
    _draw_text("Saved", W // 2, 120, YELLOW, scale=3)
    _draw_text("voice note", W // 2, 160, WHITE, scale=2)
    _draw_text(dots, W // 2, 205, YELLOW, scale=4)
    _draw_text("23 play selected note", W // 2, 286, GRAY, scale=1)


def _screen_playing() -> None:
    _fill(0, 0, W, H, BLACK)
    _draw_play_icon(W // 2, 84, GREEN, scale=3)
    _draw_text("Playing note", W // 2, 150, WHITE, scale=3)

    recording = _selected_recording()
    label = recording.name if recording else "No note selected"
    _draw_text(label[:24], W // 2, 192, GRAY, scale=2)
    _draw_text("22 prev  25 play", W // 2, 286, DGRAY, scale=1)


def _screen_timer() -> None:
    _fill(0, 0, W, H, BLACK)

    _draw_text("TIMER", W // 2, 30, TEAL, scale=2)
    _fill(40, 50, W - 80, 1, DGRAY)

    end = _state["timer_end"]
    if end is None:
        _draw_text("--:--", W // 2, 155, WHITE, scale=5)
        return

    remaining = end - datetime.now()
    if remaining.total_seconds() <= 0:
        _draw_text("00:00", W // 2, 155, GREEN, scale=5)
        _draw_text("Timer done!", W // 2, 245, GREEN, scale=2)
        _draw_text("press button to dismiss", W // 2, 295, DGRAY, scale=1)
        return

    total_secs = int(remaining.total_seconds())
    mins  = total_secs // 60
    secs  = total_secs % 60

    if mins >= 60:
        hrs = mins // 60
        mins = mins % 60
        label = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        scale = 3
    else:
        label = f"{mins:02d}:{secs:02d}"
        scale = 5

    color = RED if total_secs <= 60 else (YELLOW if total_secs <= 300 else WHITE)
    _draw_text(label, W // 2, 155, color, scale=scale)

    # Progress bar
    total_mins = _state["timer_mins"]
    if total_mins > 0:
        progress = max(0.0, 1.0 - remaining.total_seconds() / (total_mins * 60))
        bar_x, bar_y, bar_w, bar_h = 40, 220, W - 80, 12
        _fill(bar_x, bar_y, bar_w, bar_h, DGRAY)
        _fill(bar_x, bar_y, int(bar_w * progress), bar_h, color)

    _draw_text("press button to dismiss", W // 2, 295, DGRAY, scale=1)


def _screen_events() -> None:
    _fill(0, 0, W, H, BLACK)

    _draw_text("UPCOMING EVENTS", W // 2, 22, TEAL, scale=2)
    _fill(20, 42, W - 40, 1, DGRAY)

    events = _state["events"]
    if not events:
        _draw_text("No upcoming events", W // 2, 160, GRAY, scale=2)
    else:
        y = 56
        for ev in events[:4]:
            title = ev.get("summary", "Untitled")[:24]
            start = ev.get("start", "")
            # Trim long titles
            _draw_text_left(title, 20, y, WHITE, scale=2)
            y += 18
            _draw_text_left(start[:28], 24, y, GRAY, scale=1)
            y += 12
            _fill(20, y + 2, W - 40, 1, DGRAY)
            y += 10
            if y > 270:
                break

    _draw_text("press button to dismiss", W // 2, 305, DGRAY, scale=1)


def _screen_calendar() -> None:
    _fill(0, 0, W, H, BLACK)
    _draw_text("CALENDAR", W // 2, 20, TEAL, scale=2)
    _fill(16, 38, W - 32, 1, DGRAY)

    if _state["cal_loading"]:
        _draw_text("Loading...", W // 2, 160, GRAY, scale=2)
        _draw_text("27 next page  23 home", W // 2, 308, DGRAY, scale=1)
        return

    events = _state["cal_events"]
    if not events:
        _draw_text("No events found", W // 2, 150, GRAY, scale=2)
        _draw_text("Say 'connect calendar' to sign in", W // 2, 185, DGRAY, scale=1)
    else:
        scroll = _state["cal_scroll"]
        visible = events[scroll:scroll + 4]
        y = 46
        for ev in visible:
            title = ev.get("summary", "Untitled")
            if len(title) > 22:
                title = title[:21] + "."
            start_raw = ev.get("start", "")
            if isinstance(start_raw, dict):
                dt_str = start_raw.get("dateTime") or start_raw.get("date", "")
            else:
                dt_str = start_raw or ""
            try:
                dt = datetime.fromisoformat(dt_str)
                time_label = dt.strftime("%a %d %b  %I:%M %p")
            except (ValueError, TypeError):
                time_label = dt_str[:18] if dt_str else "All day"
            _draw_text_left(title, 16, y, WHITE, scale=2)
            y += 18
            _draw_text_left(time_label, 20, y, TEAL, scale=1)
            y += 8
            _fill(16, y + 2, W - 32, 1, DGRAY)
            y += 8

        total = len(events)
        scroll = _state["cal_scroll"]
        if scroll > 0:
            _draw_text("22 up", 16, 296, GRAY, scale=1)
        if scroll + 4 < total:
            _draw_text("27 down", W - 60, 296, GRAY, scale=1)
        _draw_text(f"{scroll+1}-{min(scroll+4, total)} of {total}", W // 2, 296, DGRAY, scale=1)

    _draw_text("27 next page  23 home", W // 2, 310, DGRAY, scale=1)


def _screen_pomodoro_select() -> None:
    _fill(0, 0, W, H, BLACK)
    _draw_text("POMODORO", W // 2, 20, TEAL, scale=2)
    _fill(16, 38, W - 32, 1, DGRAY)

    preset_idx = _state["pomo_preset"]
    for i, preset in enumerate(POMODORO_PRESETS):
        cy = 72 + i * 56
        selected = (i == preset_idx)
        if selected:
            _fill(12, cy - 20, W - 24, 44, DGRAY)
            _draw_rect_outline(12, cy - 20, W - 24, 44, TEAL)
        name_color = WHITE if selected else GRAY
        detail_color = TEAL if selected else _px(80, 80, 80)
        _draw_text_left(preset["name"], 24, cy - 12, name_color, scale=2)
        detail = f"{preset['work']}min work / {preset['break']}min break / x{preset['reps']}"
        _draw_text_left(detail, 24, cy + 8, detail_color, scale=1)

    _draw_text("22 up  27 down  25 start  23 home", W // 2, 308, DGRAY, scale=1)


def _screen_pomodoro_run() -> None:
    _fill(0, 0, W, H, BLACK)
    preset = POMODORO_PRESETS[_state["pomo_preset"]]
    rep = _state["pomo_rep"]
    phase = _state["pomo_phase"]

    header = f"{preset['name']}  Rep {rep}/{preset['reps']}"
    _draw_text(header, W // 2, 22, TEAL, scale=2)
    _fill(16, 40, W - 32, 1, DGRAY)

    if phase == "done":
        _draw_text("DONE!", W // 2, 140, GREEN, scale=5)
        _draw_text("All reps complete", W // 2, 218, GRAY, scale=2)
        _draw_text("23 home", W // 2, 295, DGRAY, scale=1)
        return

    phase_color = TEAL if phase == "work" else ORANGE
    _draw_text("WORK" if phase == "work" else "BREAK", W // 2, 80, phase_color, scale=3)

    end = _state["pomo_end"]
    if end:
        remaining = max(timedelta(0), end - datetime.now())
        total_secs = int(remaining.total_seconds())
        mins, secs = total_secs // 60, total_secs % 60
        color = RED if total_secs <= 30 else (YELLOW if total_secs <= 120 else WHITE)
        _draw_text(f"{mins:02d}:{secs:02d}", W // 2, 158, color, scale=5)
        phase_mins = preset["work"] if phase == "work" else preset["break"]
        progress = max(0.0, 1.0 - remaining.total_seconds() / (phase_mins * 60))
        _fill(20, 228, W - 40, 10, DGRAY)
        _fill(20, 228, int((W - 40) * progress), 10, phase_color)
    else:
        _draw_text("--:--", W // 2, 158, WHITE, scale=5)

    _draw_text("23 cancel session", W // 2, 300, DGRAY, scale=1)


def _draw_screen() -> None:
    s = _state["screen"]
    if s == "home":
        _screen_home()
    elif s == "recording":
        _screen_recording()
    elif s == "processing":
        _screen_processing()
    elif s == "playing":
        _screen_playing()
    elif s == "timer":
        _screen_timer()
    elif s == "events":
        _screen_events()
    elif s == "calendar":
        _screen_calendar()
    elif s == "pomodoro_select":
        _screen_pomodoro_select()
    elif s == "pomodoro_run":
        _screen_pomodoro_run()
    flush()


# ── Command handling ───────────────────────────────────────────────────────────
def _handle_commands() -> None:
    while True:
        try:
            cmd = ui_commands.CMD.get_nowait()
        except Exception:
            break
        action = cmd.get("action")
        if action == "timer":
            minutes = float(cmd.get("minutes", 1))
            with _lock:
                _state["screen"]     = "timer"
                _state["timer_mins"] = minutes
                _state["timer_end"]  = datetime.now() + timedelta(minutes=minutes)
        elif action == "events":
            with _lock:
                _state["screen"] = "events"
                _state["events"] = cmd.get("events", [])
        elif action == "home":
            _go_home()
        elif action == "pomodoro_select":
            with _lock:
                _state["screen"] = "pomodoro_select"
        elif action == "start_pomodoro":
            preset_name = cmd.get("preset", "Classic")
            idx = next((i for i, p in enumerate(POMODORO_PRESETS)
                        if p["name"].lower() == preset_name.lower()), 0)
            with _lock:
                _state["pomo_preset"] = idx
            _start_pomodoro_session()


def _process(wav) -> None:
    try:
        ai.process(wav)
    except Exception as e:
        print(f"[UI] AI error: {e}")
    finally:
        # Only go home if no tool command moved us to another screen
        with _lock:
            if _state["screen"] == "processing":
                _state["screen"] = "home"


# ── Navigation helpers ─────────────────────────────────────────────────────────
def _go_home() -> None:
    if recorder.is_recording():
        recorder.stop()
    with _lock:
        _state["screen"] = "home"
        _state["recording"] = False
        _state["status"] = ""


def _cycle_page(direction: int) -> None:
    with _lock:
        screen = _state["screen"]
    if screen not in PAGES:
        return
    idx = (PAGES.index(screen) + direction) % len(PAGES)
    new_screen = PAGES[idx]
    with _lock:
        _state["screen"] = new_screen
        _state["status"] = ""
    if new_screen == "calendar":
        threading.Thread(target=_fetch_calendar, daemon=True).start()


def _fetch_calendar() -> None:
    with _lock:
        _state["cal_loading"] = True
        _state["cal_events"] = []
    try:
        from Google import calendar_api
        result = calendar_api.list_upcoming_events(max_results=10)
        events = result.get("events", [])
        with _lock:
            _state["cal_events"] = events
            _state["cal_scroll"] = 0
    except Exception as e:
        print(f"[UI] Calendar fetch: {e}")
        with _lock:
            _state["cal_events"] = []
    finally:
        with _lock:
            _state["cal_loading"] = False


def _start_pomodoro_session() -> None:
    preset_idx = _state["pomo_preset"]
    with _lock:
        _state["screen"]     = "pomodoro_run"
        _state["pomo_phase"] = "work"
        _state["pomo_rep"]   = 1
        _state["pomo_end"]   = None
    threading.Thread(target=_pomodoro_tick, args=(preset_idx,), daemon=True).start()


def _pomodoro_tick(preset_idx: int) -> None:
    preset = POMODORO_PRESETS[preset_idx]
    for rep in range(1, preset["reps"] + 1):
        for phase, mins_key in [("work", "work"), ("break", "break")]:
            if phase == "break" and rep == preset["reps"]:
                continue  # no break after last rep
            with _lock:
                if _state["screen"] != "pomodoro_run":
                    return
                _state["pomo_rep"]   = rep
                _state["pomo_phase"] = phase
                _state["pomo_end"]   = datetime.now() + timedelta(minutes=preset[mins_key])
            while True:
                time.sleep(0.5)
                with _lock:
                    if _state["screen"] != "pomodoro_run":
                        return
                    end = _state["pomo_end"]
                if end and datetime.now() >= end:
                    break
    with _lock:
        if _state["screen"] == "pomodoro_run":
            _state["pomo_phase"] = "done"
            _state["pomo_end"]   = None
    time.sleep(5)
    with _lock:
        if _state["screen"] == "pomodoro_run":
            _state["screen"] = "home"


# ── GPIO handlers ──────────────────────────────────────────────────────────────
def _on_record_button() -> None:
    with _lock:
        screen    = _state["screen"]
        recording = _state["recording"]
    if screen in ("recording",) or recording:
        wav = _stop_recording()
        if wav:
            threading.Thread(target=_process, args=(wav,), daemon=True).start()
    elif screen not in ("processing", "playing", "pomodoro_run"):
        _start_recording()


def _on_next_button() -> None:
    with _lock:
        screen = _state["screen"]
    if screen == "calendar":
        with _lock:
            total  = len(_state["cal_events"])
            scroll = _state["cal_scroll"]
        if scroll + 4 < total:
            with _lock:
                _state["cal_scroll"] = scroll + 1
        else:
            _cycle_page(+1)
    elif screen == "pomodoro_select":
        with _lock:
            _state["pomo_preset"] = (_state["pomo_preset"] + 1) % len(POMODORO_PRESETS)
    elif screen in PAGES:
        _cycle_page(+1)
    else:
        _go_home()


def _on_prev_button() -> None:
    with _lock:
        screen = _state["screen"]
    if screen == "calendar":
        with _lock:
            scroll = _state["cal_scroll"]
        if scroll > 0:
            with _lock:
                _state["cal_scroll"] = scroll - 1
        else:
            _cycle_page(-1)
    elif screen == "pomodoro_select":
        with _lock:
            _state["pomo_preset"] = (_state["pomo_preset"] - 1) % len(POMODORO_PRESETS)
    elif screen in PAGES:
        _cycle_page(-1)
    else:
        _go_home()


def _on_action_button() -> None:
    with _lock:
        screen = _state["screen"]
    if screen == "home":
        _play_selected_recording()
    elif screen == "pomodoro_select":
        _start_pomodoro_session()
    else:
        _go_home()


def _on_home_button() -> None:
    _go_home()


# ── Main loop ──────────────────────────────────────────────────────────────────
def run() -> None:
    # Force gpiozero to use RPi.GPIO backend — avoids lgpio "GPIO busy" errors
    # when pins weren't cleanly released by a previous run.
    os.environ.setdefault("GPIOZERO_PIN_FACTORY", "rpigpio")

    import RPi.GPIO as _RPIGPIO
    _RPIGPIO.setwarnings(False)

    from gpiozero import Button

    btns = []
    try:
        btns = [
            Button(GPIO_RECORD, pull_up=True, bounce_time=0.1),
            Button(GPIO_NEXT,   pull_up=True, bounce_time=0.1),
            Button(GPIO_PREV,   pull_up=True, bounce_time=0.1),
            Button(GPIO_ACTION, pull_up=True, bounce_time=0.1),
            Button(GPIO_HOME,   pull_up=True, bounce_time=0.1),
        ]
        btns[0].when_pressed = _on_record_button
        btns[1].when_pressed = _on_next_button
        btns[2].when_pressed = _on_prev_button
        btns[3].when_pressed = _on_action_button
        btns[4].when_pressed = _on_home_button

        _sync_recordings()
        print("[PAIGE] Running. GPIO24=record, GPIO27=next, GPIO22=prev, GPIO25=action, GPIO23=home")

        tick = 0
        while True:
            _handle_commands()
            with _lock:
                _state["dot_phase"] = tick
            _draw_screen()
            tick += 1
            time.sleep(0.25)
    finally:
        for b in btns:
            try:
                b.close()
            except Exception:
                pass
        try:
            _RPIGPIO.cleanup()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        _fill(0, 0, W, H, BLACK)
        flush()
        print("\n[PAIGE] Exited.")
