"""
Minimal framebuffer GUI for the ILI9481 TFT HAT (/dev/fb2).
Draws directly to the framebuffer using the validated RGB565 encoding.
Mouse input via /dev/input/event2 (relative motion events).
"""

import sys, os, struct, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

W, H = config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT  # 480 x 320
FB   = config.DISPLAY_FB                             # /dev/fb2

# Validated RGB565 byte pairs for this board
def _px(r, g, b):
    """Convert 8-bit RGB to the board's 2-byte pixel format."""
    val = ((r & 0xF8) >> 3) | ((g & 0xFC) << 3) | ((b & 0xF8) << 8)
    return struct.pack('<H', val)

BLACK  = _px(0,   0,   0)
WHITE  = b'\xff\xff'
GRAY   = _px(180, 180, 180)
DGRAY  = _px(80,  80,  80)
CURSOR = WHITE

# Framebuffer as a flat bytearray
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
    """Tiny 5×7 bitmap font — only printable ASCII."""
    FONT = {
        'H': [0x7F,0x08,0x08,0x08,0x7F], 'e': [0x38,0x54,0x54,0x54,0x18],
        'l': [0x00,0x41,0x7F,0x40,0x00], 'o': [0x38,0x44,0x44,0x44,0x38],
        ' ': [0x00,0x00,0x00,0x00,0x00], 'W': [0x3F,0x40,0x38,0x40,0x3F],
        'r': [0x7C,0x08,0x04,0x04,0x08], 'd': [0x38,0x44,0x44,0x48,0x7F],
    }
    char_w, char_h = 5, 7
    total_w = len(text) * (char_w + 1)
    sx = cx - total_w // 2
    sy = cy - char_h // 2
    for ch in text:
        cols = FONT.get(ch, FONT[' '])
        for col_i, col in enumerate(cols):
            for row_i in range(char_h):
                if col & (1 << row_i):
                    set_pixel(sx + col_i, sy + row_i, px)
        sx += char_w + 1


def flush():
    with open(FB, 'wb') as f:
        f.write(buf)


# ── Button ────────────────────────────────────────────────────────────────────
BTN_X, BTN_Y, BTN_W, BTN_H = 165, 130, 150, 50


def draw(cursor_x, cursor_y, pressed):
    fill_rect(0, 0, W, H, BLACK)

    hovering = (BTN_X <= cursor_x < BTN_X + BTN_W and
                BTN_Y <= cursor_y < BTN_Y + BTN_H)
    btn_color = DGRAY if (hovering and pressed) else GRAY
    fill_rect(BTN_X, BTN_Y, BTN_W, BTN_H, btn_color)
    draw_text("Hello World", BTN_X + BTN_W // 2, BTN_Y + BTN_H // 2, BLACK)

    # cursor crosshair
    for dx in range(-4, 5):
        set_pixel(cursor_x + dx, cursor_y, CURSOR)
    for dy in range(-4, 5):
        set_pixel(cursor_x, cursor_y + dy, CURSOR)

    flush()


# ── Mouse input ───────────────────────────────────────────────────────────────
# /dev/input event packet: 16 bytes — timeval(8) + type(2) + code(2) + value(4)
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
                    hovering = (BTN_X <= cx < BTN_X + BTN_W and
                                BTN_Y <= cy < BTN_Y + BTN_H)
                    if hovering:
                        print("Hello World")
                prev_pressed = pressed

            draw(cx, cy, pressed)


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        fill_rect(0, 0, W, H, BLACK)
        flush()
