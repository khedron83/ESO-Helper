"""Shared ~/.config/eso-helper/sync.json load/save.

Used by main.py ("This PC" mode's remote_dir, "Sync Server" mode's
server_url/server_token) and settings_dialog.py (the Sync Server URL/token
fields in Settings, which need to write server_url/server_token back without
disturbing remote_dir or anything else already in the file). Split out as its
own small module rather than importing main.py from settings_dialog.py --
main.py already imports settings_dialog.py itself (lazily, from
_open_settings), and it's a much bigger module to pull in just for this.

The file itself is deliberately kept out of source entirely (not just out of
the Settings UI): remote_dir is a private local filesystem path, and this repo
may go public someday. server_url/server_token are far less sensitive (a LAN
IP, and currently no token at all -- see viewer/CLAUDE.md's "Sync" section)
but are kept in the same file for one place to look, and so a from-scratch
setup only has to be told about one file.
"""
from __future__ import annotations

import json
import os

from eso_viewer.paths import config_dir

SYNC_CONFIG_FILE = str(config_dir() / 'eso-helper' / 'sync.json')
# Pre-rename path (this app was "ESO Build Manager" before it became ESO
# Helper's viewer). Read as a fallback so a machine's existing hand-written
# config keeps working; save() never writes here.
LEGACY_SYNC_CONFIG_FILE = str(config_dir() / 'eso-build-manager' / 'sync.json')


def load() -> dict:
    for path in (SYNC_CONFIG_FILE, LEGACY_SYNC_CONFIG_FILE):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except (OSError, ValueError):
            continue
    return {}


def save(updates: dict) -> None:
    """Merges `updates` into whatever's already in SYNC_CONFIG_FILE (loading
    from the legacy path first if that's the only one that exists yet, so a
    pre-rename setup's remote_dir survives its first save here) and writes
    the result back. A falsy value in `updates` removes that key instead of
    storing an empty string."""
    cfg = load()
    for key, value in updates.items():
        if value:
            cfg[key] = value
        else:
            cfg.pop(key, None)
    os.makedirs(os.path.dirname(SYNC_CONFIG_FILE), exist_ok=True)
    with open(SYNC_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)
        f.write('\n')
