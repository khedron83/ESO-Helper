"""Daily-task definitions and per-character "untrack" preferences, shared
between main.py's Dailies tab and settings_dialog.py's untracked-dailies
management section (kept out of both to avoid a circular import between
them)."""
from __future__ import annotations

import json

from PySide6.QtCore import QSettings

# Per-character daily opt-outs ("untrack"), stored account-wide in QSettings
# (a local viewing preference, same as window geometry) as
# {char_name: [daily_key, ...]}.
_UNTRACK_KEY = 'dailies/untracked'


def load_untracked() -> dict[str, set[str]]:
    raw = QSettings().value(_UNTRACK_KEY, '')
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return {char: set(keys) for char, keys in data.items()} if isinstance(data, dict) else {}


def save_untracked(untracked: dict[str, set[str]]) -> None:
    data = {char: sorted(keys) for char, keys in untracked.items() if keys}
    QSettings().setValue(_UNTRACK_KEY, json.dumps(data))


# (settings key, column label, getter(char) -> (done, extra label or None))
DAILY_DEFS = [
    ('dungeon',       'Random Dungeon',  lambda c: (c.daily_dungeon_done, None)),
    ('writs',         'Writs',           lambda c: (c.daily_writs_done, None)),
    ('riding',        'Riding',          lambda c: (c.daily_horse_training_done, None)),
    ('remainsSilent', 'Remains-Silent',  lambda c: (c.daily_remains_silent_done, None)),
    ('pledges',       'Pledges',         lambda c: (c.daily_pledges_count >= 3, f'{c.daily_pledges_count}/3')),
]

DAILY_LABELS = {key: label for key, label, _ in DAILY_DEFS}
