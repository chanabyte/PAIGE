"""
Framebuffer GUI for PAIGE: record audio and create calendar events.
Mouse input via /dev/input/event2 (Logitech USB mouse).
"""

import sys, os, struct, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import Audio.recorder as recorder
import Gemini.ai as ai
from Google import calendar_api

W, H = config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT
FB   = config.DISPLAY_FB

def _px(r, g, b):
    val = ((r & 0xF8) >> 3) | ((g & 0xFC) << 3) | ((b & 0xF8) << 8)
    return struct.pack('<H', val)

BLACK  = _px(0,   0,   0)
WHITE  = b'\xff\xff'
GRAY   = _px(180, 180, 180)
DGRAY  = _px(80,  80,  80)
GREEN  = _px(0,   200, 0)
RED    = _px(200, 0,   0)
CURSOR = WHITE

buf = bytearray(W * H * 2)

def set_pixel(x, y, px):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 2
        buf[i:i+2] = px

def fill_rect(x, y, w, h, px):
    row = px * w
    for ry in range(y, min(y + h, H)):
        i = (ry * W + x) * 2
        buf[i:i + len(row)] = row

def draw_text(text, cx, cy, px):
    FONT = {
        'H': [0x7F,0x08,0x08,0x08,0x7F], 'e': [0x38,0x54,0x54,0x54,0x18],
        'l': [0x00,0x41,0x7F,0x40,0x00], 'o': [0x38,0x44,0x44,0x44,0x38],
        ' ': [0x00,0x00,0x00,0x00,0x00], 'W': [0x3F,0x40,0x38,0x40,0x3F],
        'r': [0x7C,0x08,0x04,0x04,0x08], 'd': [0x38,0x44,0x44,0x48,0x7F],
        'R': [0x7E,0x24,0x24,0x7E,0x44], 'c': [0x38,0x44,0x40,0x44,0x38],
        'D': [0x7E,0x42,0x42,0x42,0x7E], 'i': [0x00,0x41,0x7F,0x41,0x00],
        'C': [0x3E,0x42,0x40,0x42,0x3E], 't': [0x08,0x3E,0x08,0x08,0x08],
        'n': [0x42,0x64,0x54,0x4C,0x44], 'g': [0x30,0x4A,0x4A,0x4A,0x30],
        'N': [0x42,0x63,0x55,0x4D,0x47], 'w': [0x44,0x54,0x54,0x54,0x38],
        'K': [0x7F,0x08,0x14,0x22,0x41], 's': [0x30,0x48,0x30,0x08,0x70],
    }
    char_w, char_h = 5, 7
    total_w = len(text) * (char_w + 1)
    sx = cx - total_w // 2
    sy = cy - char_h // 2
    for ch in text:
        cols = FONT.get(ch, FONT.get(' ', [0]*5))
        for col_i, col in enumerate(cols):
            for row_i in range(char_h):
                if col & (1 << row_i):
                    set_pixel(sx + col_i, sy + row_i, px)
        sx += char_w + 1

def flush():
    with open(FB, 'wb') as f:
        f.write(buf)

# ── Buttons ────────────────────────────────────────────────────────────────────
REC_BTN     = (20, 20, 100, 40)     # Record button
CONNECT_BTN = (140, 20, 100, 40)    # Connect Calendar button
STATUS_Y    = 80

calendar_connected = False
recording = False
processing = False

def is_calendar_connected():
    try:
        token = calendar_api._load_token_if_any(calendar_api.load_config())
        return token and token.get("refresh_token") is not None
    except:
        return False

def draw(cursor_x, cursor_y, pressed):
    global calendar_connected
    calendar_connected = is_calendar_connected()

    fill_rect(0, 0, W, H, BLACK)

    # Record button
    rec_x, rec_y, rec_w, rec_h = REC_BTN
    rec_hover = (rec_x <= cursor_x < rec_x + rec_w and rec_y <= cursor_y < rec_y + rec_h)
    rec_color = RED if recording else (DGRAY if (rec_hover and pressed) else GRAY)
    fill_rect(rec_x, rec_y, rec_w, rec_h, rec_color)
    draw_text("Rec" if not recording else "Stop", rec_x + rec_w // 2, rec_y + rec_h // 2, BLACK)

    # Connect button
    con_x, con_y, con_w, con_h = CONNECT_BTN
    con_hover = (con_x <= cursor_x < con_x + con_w and con_y <= cursor_y < con_y + con_h)
    con_color = GREEN if calendar_connected else (DGRAY if (con_hover and pressed) else GRAY)
    fill_rect(con_x, con_y, con_w, con_h, con_color)
    draw_text("Cal" if not calendar_connected else "OK", con_x + con_w // 2, con_y + con_h // 2, BLACK)

    # Status text
    status_text = ""
    if processing:
        status_text = "Processing..."
    elif recording:
        status_text = "Recording"
    else:
        status_text = "Ready"
    draw_text(status_text, W // 2, STATUS_Y, WHITE)

    # Cursor
    for dx in range(-4, 5):
        set_pixel(cursor_x + dx, cursor_y, CURSOR)
    for dy in range(-4, 5):
        set_pixel(cursor_x, cursor_y + dy, CURSOR)

    flush()

def on_rec_click():
    global recording, processing
    if recording:
        print("[GUI] Stopping recording...")
        saved = recorder.stop()
        recording = False
        if saved:
            print(f"[GUI] Processing audio: {saved}")
            processing = True
            def process_audio():
                global processing
                try:
                    ai.process(saved)
                except Exception as e:
                    print(f"[GUI] Error processing audio: {e}")
                finally:
                    processing = False
            threading.Thread(target=process_audio, daemon=True).start()
    else:
        print("[GUI] Starting recording...")
        recorder.start()
        recording = True

def on_connect_click():
    global calendar_connected
    print("[GUI] Connecting to Google Calendar...")
    result = calendar_api.connect_calendar()
    print(f"[GUI] Calendar result: {result}")
    if result.get("status") == "pending":
        print(f"  Go to: {result.get('verification_url')}")
        print(f"  Code: {result.get('user_code')}")
    calendar_connected = is_calendar_connected()

EV_KEY, EV_REL    = 0x01, 0x02
BTN_LEFT_CODE     = 0x110
REL_X, REL_Y      = 0x00, 0x01
EVENT_FMT         = 'llHHi'
EVENT_SIZE        = struct.calcsize(EVENT_FMT)
MOUSE_DEV         = '/dev/input/event2'

def run():
    cx, cy  = W // 2, H // 2
    pressed = False
    prev_pressed = False

    draw(cx, cy, pressed)

    with open(MOUSE_DEV, 'rb') as f:
        while True:
            data = f.read(EVENT_SIZE)
            if not data:
                break
            _, _, etype, code, value = struct.unpack(EVENT_FMT, data)

            if etype == EV_REL:
                if code == REL_X:
                    cx = max(0, min(W - 1, cx + value))
                elif code == REL_Y:
                    cy = max(0, min(H - 1, cy + value))

            elif etype == EV_KEY and code == BTN_LEFT_CODE:
                pressed = bool(value)
                if prev_pressed and not pressed:
                    rec_x, rec_y, rec_w, rec_h = REC_BTN
                    con_x, con_y, con_w, con_h = CONNECT_BTN
                    if rec_x <= cx < rec_x + rec_w and rec_y <= cy < rec_y + rec_h:
                        on_rec_click()
                    elif con_x <= cx < con_x + con_w and con_y <= cy < con_y + con_h:
                        on_connect_click()
                prev_pressed = pressed

            draw(cx, cy, pressed)

if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        if recorder.is_recording():
            recorder.stop()
        fill_rect(0, 0, W, H, BLACK)
        flush()
