#!/usr/bin/env python3
"""ESO Helper — the character/loadout viewer and the addon manager in one window,
as tabs.

Both sub-apps' `MainWindow` classes are reused completely unmodified (imported
straight from their own vendored directories below) — this file is only a
composition layer: one shared QApplication, one outer window, one tray icon,
one single-instance lock. Neither sub-app's own entry point (viewer's `main.py`
`if __name__ == '__main__':` block / addon manager's `main()`) ever runs, so
their own app-creation/tray/single-instance code never executes — only their
class definitions get imported.
"""
import importlib.util
import logging
import sys
from pathlib import Path

_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_DIR / "addon_manager"))
sys.path.insert(0, str(_DIR / "viewer"))

# Log to a file, not just stderr -- when launched from a desktop icon/tray
# autostart (the normal way this app runs) there's no terminal to catch a
# traceback, so an uncaught exception otherwise vanishes with no trace of
# what happened. Also mirrored to stderr for when it *is* run from a shell.
_LOG_DIR = Path.home() / ".local" / "share" / "eso-helper"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "eso-helper.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.FileHandler(_LOG_FILE), logging.StreamHandler()],
)
sys.excepthook = lambda exc_type, exc_value, exc_tb: logging.critical(
    "Unhandled exception", exc_info=(exc_type, exc_value, exc_tb)
)
logging.info("ESO Helper starting (log file: %s)", _LOG_FILE)

from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QSystemTrayIcon

from eso_viewer.app import create_app
from src.ui.main_window import MainWindow as AddonManagerWindow


def _load_module(name: str, path: Path):
    # viewer's entry point is also named main.py — a plain `import main` would
    # collide with sys.modules depending on how *this* file was itself
    # invoked/imported. Loading by explicit path sidesteps that regardless of
    # invocation style. Its class defs only get imported this way — the
    # `if __name__ == '__main__':` guard at the bottom of that file never
    # runs, since this isn't executing it as __main__.
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


viewer_main = _load_module("_eso_viewer_main", _DIR / "viewer" / "main.py")

_SINGLE_INSTANCE_KEY = "eso-helper-single-instance"
_TRAY_ICON_FILE = _DIR / "packaging" / "eso-helper.svg"


def _notify_running_instance() -> bool:
    socket = QLocalSocket()
    socket.connectToServer(_SINGLE_INSTANCE_KEY)
    if socket.waitForConnected(200):
        socket.write(b"show")
        socket.flush()
        socket.waitForBytesWritten(200)
        socket.disconnectFromServer()
        return True
    return False


def _start_single_instance_server(on_show) -> QLocalServer:
    QLocalServer.removeServer(_SINGLE_INSTANCE_KEY)
    server = QLocalServer()
    server.listen(_SINGLE_INSTANCE_KEY)

    def _on_new_connection():
        conn = server.nextPendingConnection()
        if conn is None:
            return
        conn.readyRead.connect(lambda: (conn.readAll(), on_show()))
        conn.disconnected.connect(conn.deleteLater)

    server.newConnection.connect(_on_new_connection)
    return server


class ESOHelperWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ESO Helper")
        self._quitting = False
        self._settings = QSettings("CubicSerenity", "ESO Helper")
        if geo := self._settings.value("geometry"):
            self.restoreGeometry(geo)
        else:
            self.resize(1400, 900)

        # Addon manager built first: viewer_win's own tab strip (Character/
        # Activities/Storage/Collection) takes it as a 5th "Addons" tab via the
        # extra_tab hook, rather than the two sub-apps sitting as two
        # top-level tabs one level up -- one row of 5 peer tabs reads more
        # like one app than a mode switch between two.
        self._addon_manager_win = AddonManagerWindow()
        self._viewer_win = viewer_main.MainWindow(extra_tab=(self._addon_manager_win, "Addons"))
        # Each sub-app manages its own tray icon assuming it's a standalone
        # top-level window; embedded here that would mean two tray icons for
        # what's supposed to read as one app — hide both and give the merged
        # window a single tray icon below instead.
        for sub in (self._viewer_win, self._addon_manager_win):
            tray = getattr(sub, "_tray", None)
            if tray is not None:
                tray.hide()

        self.setCentralWidget(self._viewer_win)

        self._setup_tray()

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(QIcon(str(_TRAY_ICON_FILE)), self)
        self._tray.setToolTip("ESO Helper")
        menu = QMenu()
        menu.addAction(QAction("Show", self, triggered=self._tray_show))
        menu.addSeparator()
        menu.addAction(QAction("Quit", self, triggered=self._tray_quit))
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # left-click
            self._tray_show() if not self.isVisible() else self.hide()

    def _tray_show(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_quit(self):
        self._quitting = True
        self.close()
        QApplication.quit()

    def closeEvent(self, event):
        if not self._quitting:
            event.ignore()
            self.hide()
            return
        self._settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)


def main():
    # eso_viewer.app.create_app() sets applicationName="ESO Helper Viewer" /
    # organizationName="CubicSerenity" -- deliberately NOT "ESO Helper" (this outer
    # window's own QSettings("CubicSerenity", "ESO Helper") above), even though the
    # viewer's own code relies on bare QSettings() resolving off whatever name is
    # set here for its geometry/sync/dailies settings. Using the exact same name as
    # the outer window would mean both windows' bare/explicit QSettings resolve to
    # the same file and fight over the same "geometry" key. create_app() migrates
    # values from the pre-rename "ESO Build Manager" identity on first run under the
    # new name -- see eso_viewer/app.py and viewer/CLAUDE.md's "Storage" section.
    app = create_app(sys.argv)
    app.setStyle("Fusion")
    if _notify_running_instance():
        sys.exit(0)
    win = ESOHelperWindow()
    _instance_server = _start_single_instance_server(win._tray_show)
    if "--tray" not in sys.argv:
        win.showMaximized()
    exit_code = app.exec()
    logging.info("ESO Helper exiting (code %d)", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
