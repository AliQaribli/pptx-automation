"""Palette, grid geometry and typography constants for the offline PPTX engine.

All coordinates are computed here via :func:`grid`.  No other module hard-codes
inches: layout goes through the 6-column x 8-row grid defined in
``docs/pptx_fallback.md``.
"""
from __future__ import annotations

import re
from typing import Tuple

from pptx.dml.color import RGBColor
from pptx.util import Inches

# ---------------------------------------------------------------- slide size
# 16:9 exactly: 13.3333 x 7.5 in == 12192000 x 6858000 EMU.
SLIDE_W: int = 12192000
SLIDE_H: int = 6858000

MARGIN: int = int(Inches(0.6))   # 548640
GUTTER: int = int(Inches(0.12))  # 109728

COLS: int = 6
ROWS: int = 8
SAFE_W: int = SLIDE_W - 2 * MARGIN       # 11094720
SAFE_H: int = SLIDE_H - 2 * MARGIN       # 5760720
COL_W: float = SAFE_W / COLS             # 1849120.0
ROW_H: float = SAFE_H / ROWS             # 720090.0

# ------------------------------------------------------------------ palette
DEFAULT_COLORS = {
    "color_primary": "#1F6FEB",
    "color_secondary": "#F2A900",
    "neutral_dark": "#12141A",
    "white": "#FFFFFF",
    "grey": "#6B7280",
}

DEFAULT_FONTS = {
    "font_heading": "Aptos Display",
    "font_body": "Aptos",
}

# Locally stable families; renderers must not silently substitute.
FONT_ALLOWLIST = {
    "Aptos", "Aptos Display", "Aptos Narrow", "Calibri", "Cambria",
    "Carlito", "Arial", "Liberation Sans", "DejaVu Sans", "Segoe UI",
    "Helvetica Neue", "Verdana", "Tahoma",
}

FONT_SIZES = {
    "kicker": 11,
    "title": 34,
    "title_small": 30,
    "subtitle": 18,
    "body": 18,
    "label": 12,
    "big_number": 54,
    "slide_number": 11,
    "sources": 11,
}

# Named grid boxes reused by the renderer so every shape is grid-aligned.
BOX = {
    "kicker": (0, 0.40, 6, 0.50),
    "title_kicker": (0, 0.95, 6, 1.60),
    "title": (0, 0.50, 6, 1.60),
    "accent": (0, 2.60, 1.10, 0.28),      # ~0.10 in thick, ~2.1 in long
    "body": (0, 3.05, 6, 3.90),
    "footer_line": (0, 7.95, 6, 0.16),
    "slide_number": (5, 8.05, 1, 0.45),
    "note": (0, 7.40, 6, 0.50),
}

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def is_hex_color(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX_RE.match(value))


def rgb(value: str) -> RGBColor:
    """Convert ``#RRGGBB`` to an ``RGBColor``."""
    h = value.lstrip("#")
    if len(h) != 6 or not all(c in "0123456789abcdefABCDEF" for c in h):
        raise ValueError("invalid #RRGGBB colour: %r" % value)
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def luminance(value: str) -> float:
    h = value.lstrip("#")
    channels = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
              for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def grid(x0: float, y0: float, cols: float, rows: float) -> Tuple[int, int, int, int]:
    """Map a grid span to ``(left, top, width, height)`` in EMU.

    ``cols``/``rows`` may be fractional (e.g. ``1.1`` columns for the accent
    bar) but must be positive and large enough that the gutter subtraction
    leaves a positive extent.
    """
    if cols <= 0 or rows <= 0:
        raise ValueError("grid span must be positive: %r x %r" % (cols, rows))
    left = MARGIN + int(round(x0 * COL_W))
    top = MARGIN + int(round(y0 * ROW_H))
    width = int(round(cols * COL_W)) - GUTTER
    height = int(round(rows * ROW_H)) - GUTTER
    if width < 1 or height < 1:
        raise ValueError("grid span smaller than the gutter: %r x %r" % (cols, rows))
    return left, top, width, height


def snap_unit_x() -> float:
    return COL_W * 0.01


def snap_unit_y() -> float:
    return ROW_H * 0.01
