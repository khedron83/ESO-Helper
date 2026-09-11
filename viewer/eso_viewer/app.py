from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

# Pre-rename identity (this app was "ESO Build Manager" before it became ESO
# Helper's viewer, 2026-09-11). Kept only to migrate settings once; nothing
# else in the app should ever construct a QSettings() with this pair again.
_LEGACY_ORG, _LEGACY_APP = "CubicSerenity", "ESO Build Manager"


def _migrate_settings() -> None:
    """One-time copy of every key from the pre-rename QSettings identity into
    the new one, so window geometry / sync mode / untracked dailies survive
    the rename instead of silently resetting. Never touches the old file --
    if this ever needs to run again on a fresh profile it still can."""
    new = QSettings()  # bare -- resolves off the app/org names set below
    if new.allKeys():
        return  # already migrated (or already has settings under the new name)
    old = QSettings(_LEGACY_ORG, _LEGACY_APP)
    for key in old.allKeys():
        new.setValue(key, old.value(key))


def create_app(argv: list[str]) -> QApplication:
    app = QApplication(argv)
    # Deliberately NOT "ESO Helper" -- the composed app's outer window (see
    # ../../main.py's ESOHelperWindow) uses that exact name/org pair for its
    # own QSettings("CubicSerenity", "ESO Helper"); sharing it here would put
    # both windows' geometry under the same "geometry" key in the same file.
    app.setApplicationName("ESO Helper Viewer")
    app.setOrganizationName("CubicSerenity")
    app.setApplicationVersion("1.0.0")
    app.setQuitOnLastWindowClosed(False)  # tray icon keeps the app alive when the window is hidden
    _migrate_settings()
    return app
