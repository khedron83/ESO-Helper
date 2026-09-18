from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from eso_viewer import dailies
from eso_viewer.sync import config as sync_config

# Distinct accent per group: QGroupBox::title selector only, so it doesn't
# cascade into child widgets.
_SYNC_ACCENT = "#60a5fa"
_DAILIES_ACCENT = "#f97316"


def _accent_group_box_style(accent: str) -> str:
    return f"""
        QGroupBox {{
            border: 1px solid palette(mid);
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 6px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 6px;
            color: {accent};
            font-weight: bold;
        }}
    """


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(self._build_sync_group())
        layout.addWidget(self._build_dailies_group())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_sync_group(self) -> QGroupBox:
        group = QGroupBox("Save file source")
        group.setStyleSheet(_accent_group_box_style(_SYNC_ACCENT))
        sync_layout = QVBoxLayout(group)
        sync_layout.setSpacing(6)

        self._this_pc_radio = QRadioButton("This PC")
        self._server_radio = QRadioButton("Sync Server")
        self._this_pc_radio.toggled.connect(self._update_server_fields_enabled)
        self._server_radio.toggled.connect(self._update_server_fields_enabled)
        sync_layout.addWidget(self._this_pc_radio)
        sync_layout.addWidget(self._server_radio)

        note = QLabel(
            "<small>Use This PC when the game and build manager are running "
            "on the same machine (e.g. streaming from this PC) to read save "
            "files directly from disk. Sync Server instead pulls characters/"
            "achievements/set collections straight from a standalone sync "
            "server below — no local save file parsed at all, so Armory "
            "loadouts aren't available in this mode.</small>"
        )
        note.setWordWrap(True)
        sync_layout.addWidget(note)

        # For a machine that runs the game AND wants other machines' "Sync
        # Server" clients to see fresh data (e.g. zeus) -- reads locally as
        # normal, and additionally pushes that same data up to the server on
        # every reload. Only meaningful in This PC mode: there's no local
        # data to push while this window is itself just a Sync Server client.
        self._push_checkbox = QCheckBox("Also push this PC's data to the Sync Server")
        self._push_checkbox.setToolTip(
            "For the machine that runs the game (e.g. zeus), if you also want "
            "other machines running in \"Sync Server\" mode to see fresh data. "
            "Pushes characters/achievements/set collections to the server "
            "below after every local reload."
        )
        self._push_checkbox.toggled.connect(self._update_server_fields_enabled)
        push_row = QHBoxLayout()
        push_row.setContentsMargins(20, 0, 0, 0)
        push_row.addWidget(self._push_checkbox)
        sync_layout.addLayout(push_row)

        server_form = QFormLayout()
        server_form.setContentsMargins(20, 4, 0, 0)
        self._server_url_edit = QLineEdit()
        self._server_url_edit.setPlaceholderText("http://192.168.1.x:8091")
        server_form.addRow("Server address:", self._server_url_edit)
        self._server_token_edit = QLineEdit()
        self._server_token_edit.setPlaceholderText("(leave blank if the server has no auth)")
        server_form.addRow("Token:", self._server_token_edit)
        sync_layout.addLayout(server_form)

        return group

    def _update_server_fields_enabled(self):
        self._push_checkbox.setEnabled(self._this_pc_radio.isChecked())
        needs_server = self._server_radio.isChecked() or (
            self._this_pc_radio.isChecked() and self._push_checkbox.isChecked()
        )
        self._server_url_edit.setEnabled(needs_server)
        self._server_token_edit.setEnabled(needs_server)

    def _build_dailies_group(self) -> QGroupBox:
        group = QGroupBox("Untracked Dailies")
        group.setStyleSheet(_accent_group_box_style(_DAILIES_ACCENT))
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        note = QLabel(
            "<small>Right-click a daily in the Dailies tab to untrack it for a "
            "character. Re-track it here, or from the same right-click menu.</small>"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        self._untracked_list = QListWidget()
        self._untracked_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self._untracked_list)

        buttons_row = QHBoxLayout()
        retrack_btn = QPushButton("Re-track Selected")
        retrack_btn.clicked.connect(self._retrack_selected)
        buttons_row.addWidget(retrack_btn)
        retrack_all_btn = QPushButton("Re-track All")
        retrack_all_btn.clicked.connect(self._retrack_all)
        buttons_row.addWidget(retrack_all_btn)
        layout.addLayout(buttons_row)

        self._refresh_untracked_list()
        return group

    def _refresh_untracked_list(self):
        self._untracked_list.clear()
        untracked = dailies.load_untracked()
        entries = [
            (char_name, key)
            for char_name, keys in sorted(untracked.items())
            for key in sorted(keys)
        ]
        if not entries:
            item = QListWidgetItem("Nothing untracked.")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self._untracked_list.addItem(item)
            return
        for char_name, key in entries:
            label = dailies.DAILY_LABELS.get(key, key)
            item = QListWidgetItem(f"{char_name} — {label}")
            item.setData(Qt.ItemDataRole.UserRole, (char_name, key))
            self._untracked_list.addItem(item)

    def _retrack_selected(self):
        untracked = dailies.load_untracked()
        for item in self._untracked_list.selectedItems():
            pair = item.data(Qt.ItemDataRole.UserRole)
            if not pair:
                continue
            char_name, key = pair
            untracked.get(char_name, set()).discard(key)
        dailies.save_untracked(untracked)
        self._refresh_untracked_list()

    def _retrack_all(self):
        dailies.save_untracked({})
        self._refresh_untracked_list()

    def _load(self):
        s = QSettings()

        mode = s.value("sync/mode", "this_pc")
        self._server_radio.setChecked(mode == "server")
        self._this_pc_radio.setChecked(mode != "server")
        self._push_checkbox.setChecked(bool(s.value("sync/push_enabled", False, type=bool)))
        self._update_server_fields_enabled()

        cfg = sync_config.load()
        self._server_url_edit.setText(cfg.get("server_url", ""))
        self._server_token_edit.setText(cfg.get("server_token", ""))

    def _save_and_accept(self):
        s = QSettings()
        mode = "server" if self._server_radio.isChecked() else "this_pc"
        s.setValue("sync/mode", mode)
        s.setValue("sync/push_enabled", self._this_pc_radio.isChecked() and self._push_checkbox.isChecked())
        sync_config.save({
            "server_url": self._server_url_edit.text().strip(),
            "server_token": self._server_token_edit.text().strip(),
        })
        self.accept()
