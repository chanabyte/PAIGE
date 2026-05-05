"""
config.py — Central configuration for PAIGE.
All tunable constants live here.
"""

import os

# ── GPIO ──────────────────────────────────────────────────────────────────────
GPIO_PIN = 27

# ── Audio ─────────────────────────────────────────────────────────────────────
PW_TARGET      = "90"
MAX_RECORDINGS = 3
FILE_PREFIX    = "UserAudio"

# ── Gemini ────────────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash"
VOICE        = "en-GB-SoniaNeural"

# ── Display (ILI9481 3.5" TFT LCD) ───────────────────────────────────────────
DISPLAY_WIDTH  = 480
DISPLAY_HEIGHT = 320
DISPLAY_FB     = "/dev/fb2"
