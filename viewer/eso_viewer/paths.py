"""Cross-platform per-user directories for viewer state that isn't QSettings (gold
history, icon cache, sync.json) -- QSettings already resolves to the right place on
each OS on its own, but these three are hand-rolled JSON/PNG files under the old
Linux-only `~/.config` / `~/.local/share` split. Mirrors the same
`sys.platform == "win32"` -> `%APPDATA%` check addon_manager/src/core/config.py
already uses, kept as its own tiny module here since viewer/ is still independently
runnable and shouldn't import from addon_manager.
"""
import os
import re
import sys
from pathlib import Path
from typing import Optional


def config_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home()))
    return Path.home() / ".config"


def data_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home()))
    return Path.home() / ".local" / "share"


# Best-guess "This PC" sync mode SavedVariables directory (where ESOHelper.lua
# gets written by the in-game addon) -- duplicated from addon_manager/src/core/
# paths.py's detect_addons_dir()/detect_saved_vars_dir() rather than imported
# (see this file's own module docstring: viewer/ shouldn't import from
# addon_manager). remote_dir itself is still never written to source (see
# eso_viewer/sync/config.py) -- this only fills in the Settings UI field with
# a first guess, same as addon_manager already does for its own AddOns/
# SavedVariables fields.
_ESO_STEAM_APP_ID = "306130"
_PROTON_SAVED_VARS_REL = Path(
    "pfx/drive_c/users/steamuser/Documents/Elder Scrolls Online/live/SavedVariables"
)


def _steam_library_paths() -> list[Path]:
    base = Path.home() / ".local/share/Steam"
    libraries = [base]
    vdf = base / "steamapps/libraryfolders.vdf"
    if vdf.exists():
        text = vdf.read_text(errors="replace")
        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            libraries.append(Path(match.group(1)))
    return libraries


def _find_proton_saved_vars() -> Optional[Path]:
    for lib in _steam_library_paths():
        compat = lib / "steamapps/compatdata" / _ESO_STEAM_APP_ID
        if compat.exists():
            candidate = compat / _PROTON_SAVED_VARS_REL
            if candidate.exists():
                return candidate
    return None


def detect_saved_vars_dir() -> Optional[Path]:
    """Return the best-guess ESO SavedVariables directory for the current
    platform, or None if nothing is found (user browses manually)."""
    if sys.platform == "win32":
        candidate = Path.home() / "Documents/Elder Scrolls Online/live/SavedVariables"
        return candidate if candidate.exists() else None

    proton = _find_proton_saved_vars()
    if proton:
        return proton

    native = Path.home() / "Documents/Elder Scrolls Online/live/SavedVariables"
    return native if native.exists() else None
