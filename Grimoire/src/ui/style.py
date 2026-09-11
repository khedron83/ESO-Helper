"""Shared style constants — a single source of truth for the few visual
choices repeated across tabs, instead of one-off copies per file."""

from __future__ import annotations

from PySide6.QtGui import QColor

# Fusion's default light-palette alternate-base is nearly indistinguishable
# from plain white base, so zebra striping (setAlternatingRowColors(True))
# is effectively invisible without an explicit override.
TABLE_STYLE = "QTableWidget { alternate-background-color: rgba(128,128,128,0.08); }"

# One "update available" color shared between the Installed and Browse tabs
# (previously a muted QColor(200,140,0) in one tab and Qt.yellow — low
# contrast on white — in the other).
UPDATE_COLOR = QColor(200, 140, 0)

# Muted green for "installed and up to date" — replaces pure Qt.green, which
# reads far more saturated than every other accent color in the app.
INSTALLED_COLOR = QColor(90, 180, 90)

# Single source of truth for error color — tuned against the app's actual
# dark palette (base ~#1e1e1e, panels ~#2d2d2d/#4b4b4b); #b91c1c was chosen
# against a light background and drops as low as 1.35:1 contrast here.
ERROR_COLOR = "#f87171"

# Status bar message severity styling — errors get red text instead of
# looking identical to routine info messages.
STATUS_ERROR_STYLE = f"QStatusBar {{ color: {ERROR_COLOR}; }}"
STATUS_NORMAL_STYLE = ""

# Shared "primary action" style for the one enabled/highlighted button in a
# panel (matches the update banner's highlight styling in main_window.py).
PRIMARY_BUTTON_STYLE = "background: palette(highlight); color: palette(highlightedText);"


def is_error_message(msg: str) -> bool:
    lowered = msg.lower()
    return "error" in lowered or "failed" in lowered
