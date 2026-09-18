"""Cross-platform per-user directories for viewer state that isn't QSettings (gold
history, icon cache, sync.json) -- QSettings already resolves to the right place on
each OS on its own, but these three are hand-rolled JSON/PNG files under the old
Linux-only `~/.config` / `~/.local/share` split. Mirrors the same
`sys.platform == "win32"` -> `%APPDATA%` check addon_manager/src/core/config.py
already uses, kept as its own tiny module here since viewer/ is still independently
runnable and shouldn't import from addon_manager.
"""
import os
import sys
from pathlib import Path


def config_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home()))
    return Path.home() / ".config"


def data_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home()))
    return Path.home() / ".local" / "share"
