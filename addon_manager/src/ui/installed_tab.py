"""Installed addons tab — list, remove, update."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QAbstractItemView, QMessageBox,
    QProgressBar, QStackedLayout, QFileDialog, QCheckBox,
)

from ..core.addon import Addon
from ..core.esoui import RemoteAddonInfo
from ..core.dependency import missing_dependencies
from ..core.paths import detect_saved_vars_dir
from .workers import ScanWorker, UpdateWorker, InstallWorker
from .style import TABLE_STYLE, UPDATE_COLOR, ERROR_COLOR


class _SortItem(QTableWidgetItem):
    def __init__(self, text: str, key: int):
        super().__init__(text)
        self._key = key

    def __lt__(self, other):
        if isinstance(other, _SortItem):
            return self._key < other._key
        return super().__lt__(other)


def _semver(s: str) -> tuple[int, ...] | None:
    parts = re.split(r'[\s.\-_]+', s.strip())
    nums = []
    for p in parts:
        p = re.sub(r'^[a-zA-Z]+', '', p)
        if p.isdigit():
            nums.append(int(p))
    return tuple(nums) if nums else None


def _has_update(addon: Addon, remote: RemoteAddonInfo) -> bool:
    if addon.install_date and remote.date:
        return remote.date > addon.install_date
    if addon.version and remote.version:
        av = _semver(addon.version)
        rv = _semver(remote.version)
        if av and rv and len(av) == len(rv):
            return rv > av
    return False


class InstalledTab(QWidget):
    addon_removed = Signal(str)
    status_message = Signal(str)
    installed_loaded = Signal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._addons: list[Addon] = []
        self._remote: dict[str, RemoteAddonInfo] = {}
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self._btn_refresh = QPushButton("Refresh")
        self._btn_update_all = QPushButton("Update All")
        self._btn_remove = QPushButton("Remove Selected")
        self._btn_remove.setEnabled(False)
        self._btn_install_dev = QPushButton("Install Dev Addon…")
        toolbar.addWidget(self._btn_refresh)
        toolbar.addWidget(self._btn_update_all)
        toolbar.addWidget(self._btn_remove)
        toolbar.addWidget(self._btn_install_dev)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Name", "Installed", "Latest", "Author", "Status"])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(TABLE_STYLE)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setSectionsClickable(True)

        self._empty_label = QLabel("No addons found in your AddOns folder.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: palette(placeholderText); font-size: 12px;")

        self._error_label = QLabel()
        self._error_label.setAlignment(Qt.AlignCenter)
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet(f"color: {ERROR_COLOR}; font-size: 12px;")

        self._table_stack = QStackedLayout()
        self._table_stack.addWidget(self._table)
        self._table_stack.addWidget(self._empty_label)
        self._table_stack.addWidget(self._error_label)
        table_area = QWidget()
        table_area.setLayout(self._table_stack)
        layout.addWidget(table_area, 1)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress_label = QLabel("")
        layout.addWidget(self._progress_label)
        layout.addWidget(self._progress)

        self._btn_refresh.clicked.connect(self.refresh)
        self._btn_update_all.clicked.connect(self._update_all)
        self._btn_remove.clicked.connect(self._remove_selected)
        self._btn_install_dev.clicked.connect(self._install_dev_addon)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

    # ── Public API ────────────────────────────────────────────────

    def set_addons(self, addons: list[Addon]):
        self._addons = addons
        self._populate_table()
        self.installed_loaded.emit()

    def _on_scan_error(self, error: str):
        # Clear stale table contents rather than leaving a prior successful
        # scan's data on screen looking normal while the configured
        # directory is actually missing/unreadable.
        self._addons = []
        self._table.setRowCount(0)
        self._error_label.setText(
            f"Couldn't scan the AddOns directory:\n{error}\n\nCheck the path in Settings."
        )
        self._table_stack.setCurrentWidget(self._error_label)
        self.status_message.emit(f"Scan error: {error}")
        self.installed_loaded.emit()

    def set_remote_info(self, remote: dict[str, RemoteAddonInfo]):
        self._remote = remote
        self._populate_table()

    def get_installed_map(self) -> dict[str, Addon]:
        return {a.name: a for a in self._addons}

    # ── Table ─────────────────────────────────────────────────────

    def _populate_table(self):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for addon in self._addons:
            row = self._table.rowCount()
            self._table.insertRow(row)

            remote = self._remote.get(addon.name)
            has_upd = remote is not None and _has_update(addon, remote)

            title_item = QTableWidgetItem(addon.title or addon.name)
            title_item.setData(Qt.UserRole, addon.name)
            self._table.setItem(row, 0, title_item)
            self._table.setItem(row, 1, QTableWidgetItem(addon.version or "—"))
            self._table.setItem(row, 2, QTableWidgetItem(remote.version if remote else "—"))
            self._table.setItem(row, 3, QTableWidgetItem(addon.author))

            if has_upd:
                status_item = _SortItem("Update available", 0)
            elif remote:
                status_item = _SortItem("Up to date", 1)
            else:
                status_item = _SortItem("", 2)
            self._table.setItem(row, 4, status_item)

            if has_upd:
                for col in range(self._table.columnCount()):
                    item = self._table.item(row, col)
                    if item:
                        item.setForeground(UPDATE_COLOR)

        self._table.setSortingEnabled(True)
        self._table.sortItems(4, Qt.AscendingOrder)
        self._table_stack.setCurrentWidget(self._table if self._addons else self._empty_label)

    # ── Refresh ───────────────────────────────────────────────────

    def refresh(self):
        addons_dir = self.config.addons_dir
        if not addons_dir:
            self.status_message.emit("AddOns directory not set — check Settings.")
            return
        self._worker = ScanWorker(Path(addons_dir))
        self._worker.finished.connect(self.set_addons)
        self._worker.error.connect(self._on_scan_error)
        self._worker.start()

    # ── Selection / Remove ────────────────────────────────────────

    def _on_selection_changed(self):
        self._btn_remove.setEnabled(bool(self._table.selectionModel().selectedRows()))

    def _remove_selected(self):
        selected_rows = sorted(
            {idx.row() for idx in self._table.selectionModel().selectedRows()},
            reverse=True,
        )
        if not selected_rows:
            return
        addons_to_remove = []
        for row in selected_rows:
            item = self._table.item(row, 0)
            if not item:
                continue
            name = item.data(Qt.UserRole)
            addon = next((a for a in self._addons if a.name == name), None)
            if addon:
                addons_to_remove.append(addon)
        if not addons_to_remove:
            return
        sv_dir = Path(self.config.saved_vars_dir) if self.config.saved_vars_dir else None
        if sv_dir is None and self.config.addons_dir:
            sv_dir = detect_saved_vars_dir(Path(self.config.addons_dir))

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Remove Addons")
        box.setText(
            f"Remove {len(addons_to_remove)} addon(s)?\n"
            + "\n".join(a.title or a.name for a in addons_to_remove)
        )
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)

        sv_checkbox = None
        if sv_dir:
            sv_checkbox = QCheckBox("Also remove saved variables for these addon(s)")
            box.setCheckBox(sv_checkbox)
            box.setInformativeText(
                "Deleting saved variables removes their settings/data — "
                "undo by restoring from a backup."
            )

        if box.exec() != QMessageBox.Yes:
            return

        remove_sv = bool(sv_checkbox and sv_checkbox.isChecked())

        from ..core.installer import remove_addon, remove_saved_variables
        for addon in addons_to_remove:
            remove_addon(addon)
            if remove_sv and sv_dir:
                remove_saved_variables(addon, sv_dir)
            self.addon_removed.emit(addon.name)
        self.refresh()

    # ── Install Dev Addon ────────────────────────────────────────────

    def _install_dev_addon(self):
        addons_dir = self.config.addons_dir
        if not addons_dir:
            self.status_message.emit("AddOns directory not set — check Settings.")
            return
        source = QFileDialog.getExistingDirectory(self, "Select addon folder to install")
        if not source:
            return

        from ..core.installer import install_dev_addon
        try:
            addon = install_dev_addon(Path(source), Path(addons_dir))
        except (FileExistsError, RuntimeError) as e:
            self.status_message.emit(str(e))
            return

        installed = self.get_installed_map()
        installed[addon.name] = addon
        missing = missing_dependencies(addon, installed)
        dep_infos = [self._remote[name] for name in missing if name in self._remote]
        unknown = [name for name in missing if name not in self._remote]

        self.refresh()
        if unknown:
            self.status_message.emit(
                f"Installed {addon.title or addon.name} — couldn't find these dependencies "
                f"on ESOUI, install manually: {', '.join(unknown)}"
            )
        elif dep_infos:
            self.status_message.emit(
                f"Installed {addon.title or addon.name} — fetching dependencies "
                f"({', '.join(d.name for d in dep_infos)})…"
            )
        else:
            self.status_message.emit(f"Installed {addon.title or addon.name}.")

        self._install_deps_sequential(dep_infos, Path(addons_dir))

    def _install_deps_sequential(self, queue: list[RemoteAddonInfo], addons_dir: Path):
        if not queue:
            self.refresh()
            return
        info = queue.pop(0)
        worker = InstallWorker(info, addons_dir, self.get_installed_map(), self._remote)
        worker.progress.connect(self.status_message.emit)
        worker.finished.connect(lambda _: self._install_deps_sequential(queue, addons_dir))
        worker.error.connect(lambda e: self.status_message.emit(f"Dependency install error: {e}"))
        worker.start()
        self._worker = worker

    # ── Update All ────────────────────────────────────────────────

    def _update_all(self):
        updates = [
            a for a in self._addons
            if a.name in self._remote and _has_update(a, self._remote[a.name])
        ]
        if not updates:
            self.status_message.emit("All addons are up to date.")
            return
        self._run_updates(list(updates), Path(self.config.addons_dir))

    def _run_updates(self, queue: list[Addon], addons_dir: Path):
        if not queue:
            self.status_message.emit("Updates complete.")
            self._progress.setVisible(False)
            self.refresh()
            return
        addon = queue.pop(0)
        info = self._remote.get(addon.name)
        if not info:
            self._run_updates(queue, addons_dir)
            return
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        worker = UpdateWorker(addon, info, addons_dir)
        worker.progress.connect(self._progress_label.setText)
        worker.finished.connect(lambda _: self._run_updates(queue, addons_dir))
        worker.error.connect(lambda e: self.status_message.emit(f"Update error: {e}"))
        worker.start()
        self._worker = worker
