"""
Display/color.py — Framebuffer color writer for the Inland TFT35 HAT (ILI9486).

Pixel encoding is empirically determined: each pixel is 2 bytes in a non-standard
channel order. The buffer must be written in full (4 quadrants × 320×120 pixels)
due to the display being shifted from prior framebuffer data.

Validated byte pairs:
  RED   = b'\x01\x00'
  GREEN = b'\x00\x08'
  BLUE  = b'\x04\x00'
  BLACK = b'\x00\x00'
  WHITE = b'\xff\xff'
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# Display dimensions from config
_W = config.DISPLAY_WIDTH   # 480
_H = config.DISPLAY_HEIGHT  # 320
_FB = config.DISPLAY_FB     # /dev/fb2

# Each quadrant is half the height: 4 quadrants × (W × H/4) pixels fill the screen
_QUARTER = _W * (_H // 4)  # 480 * 80 = 38400 pixels per quadrant

# Empirically validated pixel byte pairs for ILI9486 on this board
RED   = b'\x01\x00'
GREEN = b'\x00\x08'
BLUE  = b'\x04\x00'
BLACK = b'\x00\x00'
WHITE = b'\xff\xff'


def _fill(color_bytes: bytes) -> bytes:
    """Tile a 2-byte pixel value across the full framebuffer."""
    return color_bytes * (_W * _H)


def write_color(color_bytes: bytes) -> None:
    """Write a solid color to the entire display."""
    with open(_FB, 'wb') as f:
        f.write(_fill(color_bytes))


def write_solid(color_bytes: bytes) -> None:
    """Alias for write_color — fills the display with one color."""
    write_color(color_bytes)


def write_raw(data: bytes) -> None:
    """Write raw pixel data directly to the framebuffer (must be W*H*2 bytes)."""
    with open(_FB, 'wb') as f:
        f.write(data)

write_color(GREEN)  # Example usage: fill the display with blue on import