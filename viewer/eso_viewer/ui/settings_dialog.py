from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from eso_viewer import dailies

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

        self._remote_radio = QRadioButton("Remote Host (SSH)")
        self._this_pc_radio = QRadioButton("This PC")
        sync_layout.addWidget(self._remote_radio)
        sync_layout.addWidget(self._this_pc_radio)

        note = QLabel(
            "<small>Remote Host syncs save files over the network via scp, from "
            "whatever host/path is configured in "
            "<code>~/.config/eso-helper/sync.json</code>. Use This PC when "
            "the game and build manager are running on the same machine (e.g. "
            "streaming from this PC) to read save files directly from disk "
            "instead.</small>"
        )
        note.setWordWrap(True)
        sync_layout.addWidget(note)

        return group

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

        mode = s.value("sync/mode", "remote")
        self._this_pc_radio.setChecked(mode == "this_pc")
        self._remote_radio.setChecked(mode != "this_pc")

    def _save_and_accept(self):
        s = QSettings()
        s.setValue("sync/mode", "this_pc" if self._this_pc_radio.isChecked() else "remote")
        self.accept()
