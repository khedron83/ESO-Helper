"""Main application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QWidget,
    QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QSystemTrayIcon, QMenu,
)
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtCore import QUrl

from ..core.config import Config
from ..core.paths import detect_addons_dir
from .browse_tab import BrowseTab
from .installed_tab import InstalledTab
from .backup_tab import BackupTab
from .settings_dialog import SettingsDialog
from .workers import UpdateCheckWorker, APP_VERSION
from .style import STATUS_ERROR_STYLE, STATUS_NORMAL_STYLE, is_error_message

_ICON_PATH = Path(__file__).resolve().parent.parent / "resources" / "icon.svg"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = Config()
        self.setWindowTitle("Grimoire")
        self.setMinimumSize(900, 600)
        self._update_worker = None
        self._quitting = False
        self._tray: QSystemTrayIcon | None = None
        self._setup_ui()
        self._apply_tray_setting(self.config.tray_enabled)
        self._first_run_check()
        self._check_for_update()

    def _setup_ui(self):
        # Menu bar
        menu = self.menuBar()
        file_menu = menu.addMenu("File")
        settings_action = QAction("Settings…", self)
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._tray_quit)
        file_menu.addAction(quit_action)

        help_menu = menu.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        # Update banner (hidden until an update is found)
        self._update_banner = QWidget()
        self._update_banner.setStyleSheet(
            "background: palette(highlight); color: palette(highlightedText); padding:4px 8px;"
        )
        banner_layout = QHBoxLayout(self._update_banner)
        banner_layout.setContentsMargins(8, 4, 8, 4)
        self._update_label = QLabel()
        self._update_label.setOpenExternalLinks(False)
        dl_btn = QPushButton("Download")
        dl_btn.setFixedWidth(90)
        dl_btn.clicked.connect(self._open_releases)
        dismiss_btn = QPushButton("✕")
        dismiss_btn.setFixedWidth(28)
        dismiss_btn.clicked.connect(self._update_banner.hide)
        banner_layout.addWidget(self._update_label)
        banner_layout.addStretch()
        banner_layout.addWidget(dl_btn)
        banner_layout.addWidget(dismiss_btn)
        self._update_banner.hide()

        # Central widget: banner + tabs stacked vertically
        central = QWidget()
        from PySide6.QtWidgets import QVBoxLayout
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(self._update_banner)

        self._tabs = QTabWidget()
        self._browse_tab = BrowseTab(self.config)
        self._installed_tab = InstalledTab(self.config)
        self._backup_tab = BackupTab(self.config)
        self._tabs.addTab(self._installed_tab, "Installed")
        self._tabs.addTab(self._browse_tab, "Browse")
        self._tabs.addTab(self._backup_tab, "Backup")
        vbox.addWidget(self._tabs)
        self.setCentralWidget(central)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)

        # Cross-tab signals
        self._browse_tab.addon_installed.connect(self._on_addons_installed)
        self._browse_tab.addon_list_loaded.connect(self._on_addon_list_loaded)
        self._browse_tab.status_message.connect(self._on_status_message)
        self._installed_tab.status_message.connect(self._on_status_message)
        self._backup_tab.status_message.connect(self._on_status_message)
        self._installed_tab.addon_removed.connect(self._sync_installed_to_browse)
        # Install-status coloring in Browse depends on both the local scan and
        # the remote list, and they load independently on startup — resync
        # whichever finishes.
        self._installed_tab.installed_loaded.connect(self._sync_installed_to_browse)

    def _first_run_check(self):
        if not self.config.addons_dir:
            detected = detect_addons_dir()
            if detected:
                self.config.addons_dir = str(detected)
                self.config.save()
                self._status.showMessage(f"Auto-detected AddOns at {detected}")
            else:
                self._status.showMessage(
                    "AddOns directory not found — open Settings to configure."
                )
                self._open_settings()
                return

        self._installed_tab.refresh()
        # Fetch remote addon list in background so update info is ready immediately
        self._browse_tab.load_addon_list()

    def _on_tab_changed(self, index: int):
        if self._tabs.widget(index) is self._backup_tab:
            self._backup_tab.refresh()

    def _on_addon_list_loaded(self, all_addons: list):
        # Two-pass map: dirs first (low priority), then name (high priority).
        # Prevents addons that bundle a library in their dirs list from
        # hijacking dep lookups for that library's own ESOUI listing.
        remote_map = {}
        for info in all_addons:
            for dir_name in info.dirs:
                remote_map[dir_name] = info
        for info in all_addons:
            remote_map[info.name] = info
        self._installed_tab.set_remote_info(remote_map)
        self._sync_installed_to_browse()

    def _sync_installed_to_browse(self):
        self._browse_tab.set_installed(self._installed_tab.get_installed_map())

    def _on_status_message(self, msg: str):
        self._status.setStyleSheet(
            STATUS_ERROR_STYLE if is_error_message(msg) else STATUS_NORMAL_STYLE
        )
        self._status.showMessage(msg)

    def _check_for_update(self):
        self._update_worker = UpdateCheckWorker()
        self._update_worker.update_available.connect(self._show_update_banner)
        self._update_worker.start()

    def _show_update_banner(self, tag: str):
        self._update_label.setText(f"Update available: {tag}")
        self._update_banner.show()

    def _open_releases(self):
        QDesktopServices.openUrl(
            QUrl("https://github.com/khedron83/Grimoire/releases/latest")
        )

    def _on_addons_installed(self, addons):
        self._installed_tab.refresh()

    def _open_settings(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            self._apply_tray_setting(self.config.tray_enabled)
            self._installed_tab.refresh()

    # ── System tray ───────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if not self._quitting and self._tray is not None and self._tray.isVisible():
            event.ignore()
            self.hide()
            return
        super().closeEvent(event)

    def _apply_tray_setting(self, enabled: bool):
        if enabled and QSystemTrayIcon.isSystemTrayAvailable():
            if self._tray is None:
                self._tray = QSystemTrayIcon(QIcon(str(_ICON_PATH)), self)
                self._tray.setToolTip("Grimoire")
                menu = QMenu()
                menu.addAction(QAction("Show", self, triggered=self._tray_show))
                menu.addSeparator()
                menu.addAction(QAction("Quit", self, triggered=self._tray_quit))
                self._tray.setContextMenu(menu)
                self._tray.activated.connect(self._on_tray_activated)
            self._tray.show()
        elif self._tray is not None:
            self._tray.hide()

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

    def _show_about(self):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("About Grimoire")
        dlg.setTextFormat(Qt.TextFormat.RichText)
        dlg.setText(
            f"<b>Grimoire</b> v{APP_VERSION}<br><br>"
            "An addon manager for The Elder Scrolls Online.<br>"
            "Browse, install, and update addons from ESOUI.com<br>"
            "with automatic dependency resolution.<br><br>"
            "Works on Windows, Linux, and Steam Deck.<br><br>"
            "Licensed under the GNU General Public License v3.0."
        )
        dlg.setStandardButtons(QMessageBox.StandardButton.Ok)
        dlg.exec()
