#!/usr/bin/env python3
"""ESO Helper Viewer — character/activity/loadout viewer for Elder Scrolls Online."""
import logging, os, sys, shutil, time
from datetime import datetime

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QRect, QSettings, QSortFilterProxyModel, QThread, QTimer, Signal, QFileSystemWatcher
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPixmap, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout,
    QStatusBar, QPushButton, QTabWidget, QTableView, QHeaderView,
    QSplitter, QComboBox, QLabel, QFrame, QGroupBox, QListWidget,
    QListWidgetItem, QStackedWidget, QTreeWidget, QTreeWidgetItem, QGridLayout,
    QScrollArea, QSizePolicy, QSystemTrayIcon, QMenu, QLineEdit,
    QStyle, QStyledItemDelegate, QStyleOptionViewItem,
)
from eso_viewer.app import create_app
from eso_viewer.ui.build_sheet import BuildSheetWidget
from eso_viewer.data_loader import skill_icon_url
from eso_viewer.icon_cache import fetch_icon
from eso_viewer.models.build import Build
from eso_viewer.models.skill import Skill
from eso_viewer.models.gear import GearPiece
from eso_viewer.constants import CLASS_COLORS, CP_TREE_COLORS, QUALITY_COLORS
from eso_viewer import gold_history, dailies

# Scribed skills have custom names with no UESP icon; fall back to Mages Guild grimoire book
_SCRIBING_FALLBACK_URL = skill_icon_url("Ulfsild's Contingency")
import json
import parser as lua_parser
import model
from eso_viewer.sync import server as sync_server
from eso_viewer.sync import config as sync_config
from eso_viewer.sync import events as sync_events

_DIR        = os.path.dirname(os.path.abspath(__file__))
WORN_FILE     = os.path.join(_DIR, 'ESOHelper.lua')
# Shared with the composed app now -- lives at the repo-root packaging/ dir
# since there's one icon for one app, not a per-sub-app one anymore.
TRAY_ICON_FILE = os.path.join(_DIR, '..', 'packaging', 'eso-helper.svg')

# How long to wait after the last detected SavedVariables change before actually
# re-reading it -- long enough that the game has finished writing (avoids
# reading a half-written file) and that a burst of writes during active play
# coalesces into one reload instead of one per file.
SAVE_CHANGE_DEBOUNCE_MS = 8_000

_SYNC_FILES = ['ESOHelper.lua']

# Where ESOHelper.lua lives on this machine, and (in "Sync Server" mode) the
# sync server's address -- see eso_viewer/sync/config.py for the actual
# ~/.config/eso-helper/sync.json load/save (shared with settings_dialog.py,
# which is what now lets server_url/server_token be set from the UI instead
# of only by hand-editing the file). remote_dir is still hand-edit-only, kept
# out of the UI since it's a private local filesystem path:
#   {"remote_dir": "/path/to/.../SavedVariables"}
# "This PC" mode (see settings_dialog.py) reads remote_dir straight off local
# disk (not scp -- there's no other-machine SSH option anymore).
#
# "Sync Server" mode (eso_viewer/sync/server.py) ignores remote_dir entirely
# and instead reads two more keys from the same file:
#   {"server_url": "http://my-server:8091", "server_token": "..."}
_load_sync_config = sync_config.load


def _pull_save_file() -> None:
    # 'this_pc' mode -- copies save files off local disk, for when the game
    # and the build manager are running on the same machine (e.g. streaming
    # from this PC). Set in Options…
    cfg = _load_sync_config()
    remote_dir = cfg.get('remote_dir')
    if not remote_dir:
        return  # no ~/.config/eso-helper/sync.json yet -- nothing to pull

    for fname in _SYNC_FILES:
        try:
            shutil.copy(os.path.join(remote_dir, fname), os.path.join(_DIR, fname))
        except Exception:
            pass


def load_worn_gear() -> dict[str, dict]:
    if not os.path.exists(WORN_FILE):
        return {}
    return model.extract_worn_gear(lua_parser.load(open(WORN_FILE, encoding='utf-8').read()))


def _load_local_lua_data() -> dict:
    """ESOHelper.lua's SavedVariables file has every account-wide table
    (characters, achievements, set collections, worn gear) in one place --
    parsed once here and shared across all four, straight off whatever
    _pull_save_file() just pulled onto local disk. Only used in "This PC"
    mode, from _ReloadWorker.run() -- module-level (not a MainWindow method)
    since that worker runs on its own QThread, not the GUI thread."""
    if not os.path.exists(WORN_FILE):
        return {}
    return lua_parser.load(open(WORN_FILE, encoding='utf-8').read())


class _ReloadWorker(QThread):
    """Runs _reload()'s actual I/O off the Qt GUI thread: a local file parse
    (+ optional push, "This PC" mode) or a fetch_all() round-trip ("Sync
    Server" mode). Both of those can block for seconds (sync_server.py's
    _TIMEOUT=8s per request) -- before this, _reload() ran them directly on
    whichever thread called it (Ctrl+R, the 60s timer, the save-file
    watcher's debounce, or -- see SyncEventListener -- an SSE push), which is
    the GUI thread, freezing the whole window for as long as a slow/hung
    network call took to time out. MainWindow._reload() now just starts one
    of these and returns immediately; _on_reload_succeeded/_on_reload_failed
    (connected to this worker's signals, so Qt marshals the call back onto
    the GUI thread) apply the result once it's done."""
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, mode: str, push_enabled: bool, parent=None):
        super().__init__(parent)
        self._mode = mode
        self._push_enabled = push_enabled

    def run(self):
        # Temporary timing instrumentation (2026-09-17) -- user reported lag
        # on "loading" and on switching NA/EU; this narrows down whether it's
        # this worker's own fetch/parse (the network- or disk-bound half) or
        # the GUI-thread _rebuild_tabs() that follows it (the CPU/Qt-widget-
        # construction half, which switching NA/EU also goes through even
        # though it never touches this worker at all). Remove once answered.
        _t0 = time.monotonic()
        try:
            if self._mode == 'server':
                # See MainWindow._reload()'s old comment, preserved here:
                # worn-gear loadouts ride along as each Character's own
                # gear_loadouts field (model.py), so the Builds tab's Armory
                # panel works here too; only the Skills tab's
                # __class_skills__ fallback still goes without, since that's
                # read straight off raw lua_data rather than anything carried
                # on Character.
                cfg = _load_sync_config()
                if not cfg.get('server_url'):
                    raise sync_server.SyncServerError(
                        "no server_url in ~/.config/eso-helper/sync.json")
                data = sync_server.fetch_all(cfg.get('server_url'), cfg.get('server_token'))
                chars = [model.character_from_dict(c) for c in data['characters']]
                achievements = [model.achievements_from_dict(a) for a in data['achievements']]
                set_collections = [model.set_collections_from_dict(s) for s in data['set_collections']]
                worn_data = {c.name: c.gear_loadouts for c in chars if c.gear_loadouts}
                push_error = None
            else:
                _pull_save_file()
                lua_data = _load_local_lua_data()
                chars = model.extract_from_wg(lua_data)
                achievements = model.extract_achievements(lua_data)
                set_collections = model.extract_set_collections(lua_data)
                worn_data = model.extract_worn_gear(lua_data)
                push_error = None
                if self._push_enabled:
                    push_error = _push_to_sync_server(chars, achievements, set_collections)
        except Exception as e:
            import traceback; traceback.print_exc()
            self.failed.emit(str(e))
            return
        logging.info('_ReloadWorker(%s): fetch/parse took %.0fms (%d chars)',
                      self._mode, (time.monotonic() - _t0) * 1000, len(chars))
        self.succeeded.emit({
            'chars': chars,
            'achievements': achievements,
            'set_collections': set_collections,
            'worn_data': worn_data,
            'push_error': push_error,
        })


def _push_to_sync_server(chars, achievements, set_collections) -> str | None:
    """Producer side of "This PC" mode's "Also push this PC's data to the
    Sync Server" setting (see settings_dialog.py) -- for zeus, which needs to
    both read its own local save data AND keep the sync server fresh for
    other machines' "Sync Server" mode clients. Only ever called from
    _ReloadWorker.run(), right after a successful local parse. Returns an
    error string (never raises) on failure -- a failed push shouldn't turn a
    perfectly good local reload into an error, and the next reload (60s
    timer, file watcher, Ctrl+R) will just try again."""
    cfg = _load_sync_config()
    server_url = cfg.get('server_url')
    if not server_url:
        return None
    try:
        sync_server.push_all(server_url, cfg.get('server_token'), chars, achievements, set_collections)
        return None
    except sync_server.SyncServerError as e:
        import traceback; traceback.print_exc()
        return str(e)


def _fmt_time(s: int) -> str:
    return f'{s//3600:,}h {(s%3600)//60}m'

def _n(v: int) -> str:
    return f'{v:,}' if v else '—'


def _fmt_updated(ts: int) -> str:
    if not ts:
        return 'Unknown'
    delta = int(time.time()) - ts
    if delta < 60:          return 'just now'
    if delta < 3600:        return f'{delta // 60}m ago'
    if delta < 86400:       return f'{delta // 3600}h ago'
    return f'{delta // 86400}d ago'


# ── table model with raw sort values ─────────────────────────────────────────

class CharTable(QAbstractTableModel):
    """Each cell holds (display_str, sort_value, tooltip, color|None)."""
    def __init__(self, headers: list[str], rows: list[list[tuple]],
                 col_colors: dict[int, QColor] | None = None):
        super().__init__()
        self._headers   = headers
        self._rows      = rows
        self._col_colors = col_colors or {}

    def rowCount(self, _=QModelIndex()):    return len(self._rows)
    def columnCount(self, _=QModelIndex()): return len(self._headers)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self._headers[section]
            if role == Qt.ToolTipRole:
                return self._headers[section]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        cell = self._rows[index.row()][index.column()]
        if role == Qt.DisplayRole:   return cell[0]
        if role == Qt.UserRole:      return cell[1]
        if role == Qt.ToolTipRole:   return cell[2]
        if role == Qt.ForegroundRole:
            if len(cell) > 3 and cell[3]:
                return cell[3]
            return self._col_colors.get(index.column())
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft | Qt.AlignVCenter if index.column() == 0 else Qt.AlignCenter
        return None


class SortProxy(QSortFilterProxyModel):
    def lessThan(self, left, right):
        lv = self.sourceModel().data(left,  Qt.UserRole)
        rv = self.sourceModel().data(right, Qt.UserRole)
        try:
            return (lv or 0) < (rv or 0)
        except TypeError:
            return str(lv or '') < str(rv or '')


def _cell(display, sort=None, tip=None, color=None):
    return (str(display) if display is not None else '—',
            sort if sort is not None else display,
            tip, color)


def _make_view(tbl: CharTable) -> QTableView:
    proxy = SortProxy()
    proxy.setSourceModel(tbl)

    tv = QTableView()
    tv.setModel(proxy)
    tv.setSortingEnabled(True)
    tv.setAlternatingRowColors(True)
    tv.setSelectionBehavior(QTableView.SelectRows)
    tv.verticalHeader().setVisible(False)
    # Fixed (not Stretch): Stretch forces Qt to recompute every row's height
    # to divide the viewport evenly across ALL rows on every layout pass --
    # cheap for a ~25-row character table, but the achievements table holds
    # the full in-game achievement catalog (thousands of rows) and Stretch
    # there was measured taking 3+ seconds per rebuild (see git history /
    # 2026-09-18 timing instrumentation). Fixed gives each row a constant
    # height in O(1) regardless of row count.
    tv.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
    tv.verticalHeader().setDefaultSectionSize(24)
    tv.setShowGrid(False)
    tv.setWordWrap(False)
    tv.setMouseTracking(True)
    tv.setStyleSheet("""
        QTableView { border: none; alternate-background-color: rgba(128,128,128,0.07); }
        QTableView::item { padding: 3px 8px; border-bottom: 1px solid rgba(128,128,128,0.12); }
        QTableView::item:hover { background: rgba(128,128,128,0.14); }
        QTableView::item:selected { background: rgba(96,165,250,0.18); }
    """)

    f = QFont(); f.setPointSize(9); tv.setFont(f)

    hh = tv.horizontalHeader()
    hh.setDefaultAlignment(Qt.AlignCenter)
    # Interactive + a fixed starting width (not ResizeToContents): column 0 is
    # always a short label ("Character"/"Account"/"Category"), but
    # ResizeToContents must measure every row's text to find the widest one --
    # O(n), and for the achievements table (full in-game catalog, 1000+ rows)
    # that measured at 2+ seconds per rebuild, done twice (once in this
    # function's own sortByColumn below, again when the widget is actually
    # shown). Interactive still lets the user drag-resize it by hand.
    hh.setSectionResizeMode(0, QHeaderView.Interactive)
    hh.resizeSection(0, 140)
    for i in range(1, tbl.columnCount()):
        hh.setSectionResizeMode(i, QHeaderView.Stretch)
    hh.setStretchLastSection(False)
    hh.setTextElideMode(Qt.TextElideMode.ElideRight)
    hh.setStyleSheet("QHeaderView::section { border: none; border-bottom: 2px solid palette(highlight); padding: 4px 8px; }")

    tv.sortByColumn(0, Qt.SortOrder.AscendingOrder)
    return tv


def _capture_view_state(widget) -> dict | None:
    """Snapshot a plain QTableView tab's scroll position and sort column/order so
    _rebuild_tabs() can restore it after destroying and recreating the tab on
    periodic reload -- these tabs (Dailies/Stats/Skills/...) have no search/filter
    state of their own (unlike Achievements/Sets, which stay alive across reloads
    entirely via update_data()), but still shouldn't bounce back to the top and
    reset sort every 60s."""
    if not isinstance(widget, QTableView):
        return None
    header = widget.horizontalHeader()
    return {
        'scroll': widget.verticalScrollBar().value(),
        'sort_col': header.sortIndicatorSection(),
        'sort_order': header.sortIndicatorOrder(),
    }


def _restore_view_state(widget, state: dict | None) -> None:
    if not state or not isinstance(widget, QTableView):
        return
    if state['sort_col'] >= 0:
        widget.sortByColumn(state['sort_col'], state['sort_order'])
    widget.verticalScrollBar().setValue(state['scroll'])


# ── tab builders ──────────────────────────────────────────────────────────────

class _CardGridArea(QScrollArea):
    """Scroll area for a grid of cards whose column count is recomputed from
    the available viewport width (instead of a fixed constant), so a wide
    maximized window doesn't leave a dead margin the table tabs don't have."""

    _CARD_MIN_WIDTH = 320

    def __init__(self, cards: list[QFrame], parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        # Cards are meant to reflow into columns, not force a wider canvas --
        # an unwrapped long label inside a card previously could blow out a
        # column's width and drag the whole grid into horizontal scroll.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cards = cards

        container = QWidget()
        self._grid = QGridLayout(container)
        self._grid.setContentsMargins(16, 16, 16, 16)
        self._grid.setSpacing(12)
        self.setWidget(container)

        self._cols = 0
        self._relayout(force=True)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self, force: bool = False) -> None:
        width = self.viewport().width()
        cols = max(1, width // (self._CARD_MIN_WIDTH + self._grid.spacing()))
        if cols == self._cols and not force:
            return
        self._cols = cols
        while self._grid.count():
            self._grid.takeAt(0)
        for i, card in enumerate(self._cards):
            self._grid.addWidget(card, i // cols, i % cols)
        for col in range(cols):
            self._grid.setColumnStretch(col, 1)


def _rgba(hex_color: str, alpha: float) -> str:
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    return f'rgba({r},{g},{b},{alpha})'


def _status_pill(label: str, done: bool) -> QLabel:
    color = '#4dbd74' if done else '#f87171'
    lbl = QLabel(('✓ ' if done else '✗ ') + label)
    lbl.setStyleSheet(
        f'font-size: 10px; font-weight: 600; color: {color}; '
        f'background: {_rgba(color, 0.14)}; border-radius: 8px; padding: 3px 8px;'
    )
    lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return lbl


class _PillDelegate(QStyledItemDelegate):
    """Paints cell text as a rounded pill (matching _status_pill) instead of
    plain colored text, when the cell has a Qt.ForegroundRole color set."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        color = index.data(Qt.ForegroundRole)
        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        if not text:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(painter.font())
        font.setPointSize(10)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        fm = painter.fontMetrics()
        pad_h, pad_v = 8, 3
        pill = QRect(0, 0, fm.horizontalAdvance(text) + pad_h * 2, fm.height() + pad_v * 2)
        pill.moveCenter(option.rect.center())
        if isinstance(color, QColor):
            bg = QColor(color)
            bg.setAlpha(36)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)
            painter.setPen(color)
        else:
            painter.setPen(opt.palette.color(opt.palette.ColorRole.WindowText))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


def _overview_attention_count(c: model.Character) -> int:
    n = 0
    if not c.daily_dungeon_done:         n += 1
    if not c.daily_writs_done:           n += 1
    if not c.daily_horse_training_done:  n += 1
    if not c.daily_remains_silent_done:  n += 1
    return n


def _overview_card(c: model.Character) -> QFrame:
    attention = _overview_attention_count(c)
    dim = attention == 0

    card = QFrame()
    card.setObjectName('overviewCard')
    card.setStyleSheet(f"""
        QFrame#overviewCard {{
            border: 1px solid rgba(128,128,128,{0.18 if dim else 0.35});
            border-radius: 10px;
            background: rgba(255,255,255,{0.015 if dim else 0.04});
        }}
        QFrame#overviewCard QLabel {{ border: none; background: transparent; }}
    """)

    vbox = QVBoxLayout(card)
    vbox.setContentsMargins(14, 12, 14, 12)
    vbox.setSpacing(8)

    top = QHBoxLayout(); top.setSpacing(8)
    name_lbl = QLabel(c.name)
    f = name_lbl.font(); f.setPointSize(f.pointSize() + 2); f.setBold(True)
    name_lbl.setFont(f)
    if dim:
        name_lbl.setStyleSheet('color: palette(placeholderText);')
    top.addWidget(name_lbl, 1)
    if c.class_name:
        color = CLASS_COLORS.get(c.class_name, '#556677')
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        fg = '#111' if (0.299*r + 0.587*g + 0.114*b) > 140 else '#fff'
        badge = QLabel(f'  {c.class_name}  ')
        badge.setStyleSheet(f'background:{color};color:{fg};border-radius:10px;'
                            'padding:3px 0;font-size:10px;font-weight:600;')
        badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        top.addWidget(badge)
    vbox.addLayout(top)

    daily_row = QHBoxLayout(); daily_row.setSpacing(6)
    daily_row.addWidget(_status_pill('Dungeon', c.daily_dungeon_done))
    daily_row.addWidget(_status_pill('Writs', c.daily_writs_done))
    daily_row.addWidget(_status_pill('Horse', c.daily_horse_training_done))
    daily_row.addWidget(_status_pill('Remains-Silent', c.daily_remains_silent_done))
    daily_row.addStretch()
    vbox.addLayout(daily_row)

    return card


def _tab_overview(chars: list[model.Character]) -> QScrollArea:
    # Characters needing the most attention float to the top; fully-done
    # characters sink to the bottom and render dimmed (see _overview_card).
    ordered = sorted(chars, key=lambda c: (-_overview_attention_count(c), c.name))
    return _CardGridArea([_overview_card(c) for c in ordered])


def _bio_card(c: model.Character) -> QFrame:
    card = QFrame()
    card.setStyleSheet("""
        QFrame#bioCard {
            border: 1px solid rgba(128,128,128,0.3);
            border-radius: 10px;
            background: rgba(255,255,255,0.03);
        }
        QFrame#bioCard QLabel { border: none; background: transparent; }
    """)
    card.setObjectName("bioCard")

    vbox = QVBoxLayout(card)
    vbox.setContentsMargins(16, 14, 16, 14)
    vbox.setSpacing(6)

    # Name + class badge
    top = QHBoxLayout(); top.setSpacing(8)
    name_lbl = QLabel(c.name)
    f = name_lbl.font(); f.setPointSize(f.pointSize() + 4); f.setBold(True)
    name_lbl.setFont(f)
    top.addWidget(name_lbl, 1)
    if c.class_name:
        color = CLASS_COLORS.get(c.class_name, '#556677')
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        fg = '#111' if (0.299*r + 0.587*g + 0.114*b) > 140 else '#fff'
        badge = QLabel(f'  {c.class_name}  ')
        badge.setStyleSheet(f'background:{color};color:{fg};border-radius:10px;'
                            'padding:3px 0;font-size:10px;font-weight:600;')
        badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        top.addWidget(badge)
    vbox.addLayout(top)

    # Race · Faction · Last updated
    sub_row = QHBoxLayout(); sub_row.setSpacing(8)
    sub = QLabel(f'{c.race_name}  ·  {c.faction_name}')
    sub.setStyleSheet('color: palette(placeholderText); font-size: 11px;')
    sub_row.addWidget(sub, 1)
    updated_lbl = QLabel(f'Updated {_fmt_updated(c.last_updated)}')
    updated_lbl.setStyleSheet('color: palette(placeholderText); font-size: 10px;')
    updated_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if c.last_updated:
        updated_lbl.setToolTip(datetime.fromtimestamp(c.last_updated).strftime('%Y-%m-%d %H:%M:%S'))
    sub_row.addWidget(updated_lbl)
    vbox.addLayout(sub_row)

    # Divider
    hr = QFrame(); hr.setFrameShape(QFrame.Shape.HLine)
    hr.setStyleSheet('QFrame { color: rgba(128,128,128,0.25); }')
    vbox.addWidget(hr)

    # Stats as key→value rows
    cp_str = f'{c.champion_points:,} CP' if c.champion_points else f'Level {c.level}'
    rows = [
        (cp_str,                       f'{_n(c.gold)} gold'),
        (f'{_n(c.ap)} AP',             f'{_n(c.telvar)} Tel Var'),
        (f'{c.skill_points_unspent} SP unspent', f'{_n(c.writ_vouchers)} vouchers'),
        (_fmt_time(c.seconds_played),  ''),
    ]
    stat_grid = QGridLayout(); stat_grid.setSpacing(2)
    for row_i, (left, right) in enumerate(rows):
        l = QLabel(left); l.setStyleSheet('font-size: 11px;')
        stat_grid.addWidget(l, row_i, 0)
        if right:
            r = QLabel(right)
            r.setStyleSheet('font-size: 11px; color: palette(placeholderText);')
            r.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            stat_grid.addWidget(r, row_i, 1)
    stat_grid.setColumnStretch(0, 1); stat_grid.setColumnStretch(1, 1)
    vbox.addLayout(stat_grid)

    return card


def _tab_bio(chars: list[model.Character]) -> QScrollArea:
    return _CardGridArea([_bio_card(c) for c in chars])


def _mount_stat_text(value: int) -> str:
    return 'Max' if value >= model._MOUNT_STAT_MAX else str(value)


def _tab_stats(chars: list[model.Character]) -> QTableView:
    headers = ['Character',
               'Max HP', 'Max Stam', 'Max Mag',
               'HP Rec', 'Stam Rec', 'Mag Rec',
               'Spell Dmg', 'Wpn Dmg', 'Crit %',
               'Phys Res', 'Spell Res', 'Crit Res',
               'Mnt Spd', 'Mnt Stam', 'Mnt Cap']
    _HP    = QColor('#f87171')
    _STAM  = QColor('#4ade80')
    _MAG   = QColor('#60a5fa')
    _DMG   = QColor('#fb923c')
    _CRIT  = QColor('#fbbf24')
    _RES   = QColor('#94a3b8')
    _MNT   = QColor('#a78bfa')
    col_colors = {
        1: _HP,  2: _STAM,  3: _MAG,
        4: _HP,  5: _STAM,  6: _MAG,
        7: _DMG, 8: _DMG,   9: _CRIT,
        10: _RES, 11: _RES, 12: _CRIT,
        13: _MNT, 14: _STAM, 15: _MNT,
    }
    rows = []
    for c in chars:
        rows.append([
            _cell(c.name, c.name),
            _cell(f'{c.health_max:,}',       c.health_max),
            _cell(f'{c.stamina_max:,}',      c.stamina_max),
            _cell(f'{c.magicka_max:,}',      c.magicka_max),
            _cell(f'{c.health_recovery:,}',  c.health_recovery),
            _cell(f'{c.stamina_recovery:,}', c.stamina_recovery),
            _cell(f'{c.magicka_recovery:,}', c.magicka_recovery),
            _cell(f'{c.spell_damage:,}',     c.spell_damage),
            _cell(f'{c.weapon_damage:,}',    c.weapon_damage),
            _cell(f'{c.crit_chance:.1f}%',   c.crit_chance),
            _cell(f'{c.resist_physical:,}',  c.resist_physical),
            _cell(f'{c.resist_spell:,}',     c.resist_spell),
            _cell(f'{c.resist_crit:,}',      c.resist_crit),
            _cell(_mount_stat_text(c.mount_speed),    c.mount_speed),
            _cell(_mount_stat_text(c.mount_stamina),  c.mount_stamina),
            _cell(_mount_stat_text(c.mount_capacity), c.mount_capacity),
        ])
    return _make_view(CharTable(headers, rows, col_colors))


# Guild and world skill lines cap well below the usual 50 (class/weapon/armor/crafting
# lines) — hardcoding a 0-50 scale meant these could never reach the top color band.
# Values are the highest rank the addon actually reports, not the number of
# meaningful unlocks — e.g. Undaunted's last passive unlocks at rank 9, but the
# reported rank itself still goes to 10, confirmed in-game 2026-07-12.
_LINE_MAX_RANK: dict[str, int] = {
    'Fighters Guild':  10,
    'Mages Guild':     10,
    'Psijic Order':    10,
    'Undaunted':       10,
    'Thieves Guild':    12,
    'Dark Brotherhood': 12,
    'Vampire':          10,
    'Werewolf':         10,
    'Legerdemain':      20,
    'Scrying':          10,
    'Excavation':       10,
    'Soul Magic':        6,
}


def _rank_color(rank: int, max_rank: int = 50) -> QColor:
    if rank <= 0:
        return QColor(QUALITY_COLORS['Normal'])
    if rank >= max_rank:
        return QColor(QUALITY_COLORS['Legendary'])
    return QColor(QUALITY_COLORS['Fine'])


# Racial passives — exclude from all skill columns regardless of how the addon categorises them
_RACIAL_LINES: frozenset[str] = frozenset({
    'Argonian', 'Breton', 'Dark Elf', 'High Elf', 'Imperial',
    'Khajiit', 'Nord', 'Orc', 'Redguard', 'Wood Elf',
})

# Native skill lines per class — used to strip subclass lines from the class column
_NATIVE_CLASS_LINES: dict[str, frozenset[str]] = {
    'Dragonknight': frozenset({'Ardent Flame', 'Draconic Power', 'Earthen Heart'}),
    'Nightblade':   frozenset({'Assassination', 'Shadow', 'Siphoning'}),
    'Sorcerer':     frozenset({'Dark Magic', 'Daedric Summoning', 'Storm Calling'}),
    'Templar':      frozenset({'Aedric Spear', "Dawn's Wrath", 'Restoring Light'}),
    'Warden':       frozenset({'Animal Companions', 'Green Balance', "Winter's Embrace"}),
    'Necromancer':  frozenset({'Grave Lord', 'Bone Tyrant', 'Living Death'}),
    'Arcanist':     frozenset({'Herald of the Tome', 'Curative Runeforms', 'Soldier of Apocrypha'}),
}


def _tab_skills(chars: list[model.Character], worn_data: dict | None = None) -> QTableView:
    _NON_CLASS_ATTRS = ['skills_weapon', 'skills_armor', 'skills_ava']

    other_cols: list[str] = []
    seen: set[str] = set()
    for attr in _NON_CLASS_ATTRS:
        for c in chars:
            for s in getattr(c, attr):
                if s.name not in seen and s.name not in _RACIAL_LINES:
                    seen.add(s.name)
                    other_cols.append(s.name)

    headers = ['Character', 'Class 1', 'Class 2', 'Class 3'] + other_cols
    rows = []
    for c in chars:
        native = _NATIVE_CLASS_LINES.get(c.class_name, frozenset())
        class_lines = [s for s in c.skills_class if s.name in native]
        # Fall back to the addon's separate __class_skills__ block when skills_class is missing native lines
        if len(class_lines) < 3 and worn_data:
            wg_lines = (worn_data.get(c.name) or {}).get('__class_skills__') or []
            if wg_lines:
                class_lines = [model.SkillLine(name=l['name'], rank=l.get('rank', 0))
                               for l in wg_lines if isinstance(l, dict) and 'name' in l]
        row = [_cell(c.name, c.name)]
        for i in range(3):
            s = class_lines[i] if i < len(class_lines) else None
            row.append(_cell(s.rank if s else '—', s.rank if s else 0,
                             s.name if s else None,
                             _rank_color(s.rank) if s else None))
        other_lookup = {s.name: s
                        for attr in _NON_CLASS_ATTRS
                        for s in getattr(c, attr)
                        if s.name not in _RACIAL_LINES}
        for n in other_cols:
            s = other_lookup.get(n)
            row.append(_cell(s.rank if s else '—', s.rank if s else 0, None,
                             _rank_color(s.rank) if s else None))
        rows.append(row)
    return _make_view(CharTable(headers, rows))


def _tab_guilds(chars: list[model.Character]) -> QTableView:
    cols: list[str] = []
    seen: set[str] = set()
    for attr in ('skills_guild', 'skills_world'):
        for c in chars:
            for s in getattr(c, attr):
                if s.name not in seen and s.name not in _RACIAL_LINES:
                    seen.add(s.name)
                    cols.append(s.name)
    headers = ['Character'] + cols
    rows = []
    for c in chars:
        lookup = {s.name: s
                  for attr in ('skills_guild', 'skills_world')
                  for s in getattr(c, attr)
                  if s.name not in _RACIAL_LINES}
        row = [_cell(c.name, c.name)]
        for n in cols:
            s = lookup.get(n)
            row.append(_cell(s.rank if s else '—', s.rank if s else 0, None,
                             _rank_color(s.rank, _LINE_MAX_RANK.get(n, 50)) if s else None))
        rows.append(row)
    return _make_view(CharTable(headers, rows))


def _tab_crafting(chars: list[model.Character]) -> QTableView:
    craft_names: list[str] = []
    for c in chars:
        if c.skills_craft:
            craft_names = [s.name for s in c.skills_craft]
            break
    headers = ['Character'] + craft_names
    rows = []
    for c in chars:
        lookup = {s.name: s.rank for s in c.skills_craft}
        row = [_cell(c.name, c.name)]
        for n in craft_names:
            v = lookup.get(n)
            row.append(_cell(v if v is not None else '—', v or 0, None, _rank_color(v or 0)))
        rows.append(row)
    return _make_view(CharTable(headers, rows))


def _tab_dailies(chars: list[model.Character], on_change=None) -> QTableView:
    """`on_change` fires after a right-click untrack/re-track so the caller can
    rebuild this tab immediately instead of waiting for the next periodic
    refresh -- MainWindow passes its own _reload for this. Daily definitions
    and the untracked-set persistence live in eso_viewer.dailies,
    shared with settings_dialog.py's untracked-dailies management section."""
    headers = ['Character'] + [label for _, label, _ in dailies.DAILY_DEFS]
    done_color = QColor('#4dbd74')
    todo_color = QColor('#f87171')
    untracked_color = QColor('#888888')
    untracked = dailies.load_untracked()

    def _status_cell(char_name: str, key: str, done: bool, extra: str | None):
        if key in untracked.get(char_name, ()):
            return _cell('—', -1, 'Untracked — right-click to re-track', untracked_color)
        label = ('✓ Done' if done else '✗ Not yet') + (f' ({extra})' if extra else '')
        return _cell(label, 1 if done else 0, None, done_color if done else todo_color)

    rows = []
    for c in chars:
        row = [_cell(c.name, c.name)]
        for key, _label, getter in dailies.DAILY_DEFS:
            done, extra = getter(c)
            row.append(_status_cell(c.name, key, done, extra))
        rows.append(row)

    tv = _make_view(CharTable(headers, rows))
    pill_delegate = _PillDelegate(tv)
    for col in range(1, len(headers)):
        tv.setItemDelegateForColumn(col, pill_delegate)

    tv.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def _show_menu(pos):
        index = tv.indexAt(pos)
        if not index.isValid() or index.column() == 0:
            return
        source = tv.model().mapToSource(index)
        char_name = rows[source.row()][0][1]
        key, label, _getter = dailies.DAILY_DEFS[source.column() - 1]
        is_untracked = key in untracked.get(char_name, ())

        def _toggle():
            char_untracked = untracked.setdefault(char_name, set())
            if is_untracked:
                char_untracked.discard(key)
            else:
                char_untracked.add(key)
            dailies.save_untracked(untracked)
            if on_change:
                on_change()

        menu = QMenu(tv)
        action = menu.addAction(f'Re-track "{label}"' if is_untracked else f'Untrack "{label}"')
        action.triggered.connect(_toggle)
        menu.exec(tv.viewport().mapToGlobal(pos))

    tv.customContextMenuRequested.connect(_show_menu)
    return tv


def _tab_champion(chars: list[model.Character]) -> QTableView:
    headers = ['Character', 'CP Total', 'Unspent'] + model.CONSTELLATIONS

    _tree_colors = {name: QColor(hexcolor) for name, hexcolor in CP_TREE_COLORS.items()}
    col_colors = {3 + i: _tree_colors.get(name, QColor('#aaaaaa'))
                  for i, name in enumerate(model.CONSTELLATIONS)}

    rows = []
    for c in chars:
        total = c.cp_spent + c.cp_unspent
        row = [
            _cell(c.name,    c.name),
            _cell(f'{total:,}', total),
            _cell(f'{c.cp_unspent:,}', c.cp_unspent),
        ]
        for con in c.constellations:
            invested = ', '.join(str(v) for v in con.skills if v > 0)
            tip = f'{con.name} slots: [{invested}]' if invested else None
            label = f'{con.spent:,}' + (f'  ({con.unspent} free)' if con.unspent else '')
            row.append(_cell(label, con.spent, tip))
        rows.append(row)
    return _make_view(CharTable(headers, rows, col_colors))


def _tab_inventory(chars: list[model.Character]) -> QTableView:
    headers = ['Character', 'Gems Full', 'Gems Empty',
               'Lockpicks', 'Repair Kits', 'Bag Space']
    rows = []
    for c in chars:
        inv: dict[str, int] = {}
        for i in c.inventory:
            inv[i.name] = inv.get(i.name, 0) + i.count
        rows.append([
            _cell(c.name,                            c.name),
            _cell(c.soul_gems_filled,                c.soul_gems_filled),
            _cell(c.soul_gems_empty,                 c.soul_gems_empty),
            _cell(inv.get('Lockpick', '—'),          inv.get('Lockpick', 0)),
            _cell(inv.get('Equipment Repair Kit', '—'), inv.get('Equipment Repair Kit', 0)),
            _cell(f'{c.bag_used}/{c.bag_size}',      c.bag_used),
        ])
    return _make_view(CharTable(headers, rows))


def _record_gold_snapshot(chars: list[model.Character]) -> None:
    """Total gold per ESO account (on-person across all its characters + the
    account's one shared bank), logged so the Bank tab can show a 24h delta."""
    totals: dict[str, int] = {}
    bank_counted: set[str] = set()
    for c in chars:
        totals[c.account] = totals.get(c.account, 0) + c.currencies.get('Gold', 0)
        if c.account not in bank_counted:
            totals[c.account] += c.bank_currencies.get('Gold', 0)
            bank_counted.add(c.account)
    if totals:
        gold_history.record_snapshot(totals, now=int(time.time()))


def _tab_bank(chars: list[model.Character]) -> QWidget:
    # Character.currencies = on-person amounts (summable per character).
    # Character.bank_currencies = shared account/bank pool, same for every
    # character, so it's shown once rather than summed.
    preferred = ['Gold', 'Alliance Points', 'Tel Var Stones', 'Writ Vouchers', 'Undaunted Keys']
    names = {name for c in chars for name in c.currencies}
    per_char_names = [n for n in preferred if n in names] + sorted(names - set(preferred))

    global_names_set = {name for c in chars for name in c.bank_currencies}
    global_names = [n for n in preferred if n in global_names_set] + sorted(global_names_set - set(preferred))

    headers = ['Character'] + per_char_names
    rows = []
    totals = {n: 0 for n in per_char_names}
    for c in chars:
        row = [_cell(c.name, c.name)]
        for n in per_char_names:
            v = c.currencies.get(n, 0)
            row.append(_cell(_n(v), v))
            totals[n] += v
        rows.append(row)
    if per_char_names:
        rows.append([_cell('Total', '~Total')] +
                    [_cell(_n(totals[n]), totals[n]) for n in per_char_names])

    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(_make_view(CharTable(headers, rows)), 1)

    if global_names:
        # Bank is shared per ESO account, not globally -- when characters from
        # more than one account are shown together (e.g. "All Accounts"), each
        # account has its own separate bank and must be shown as its own row
        # rather than picking one character's value and silently dropping the
        # rest.
        by_account: dict[str, model.Character] = {}
        for c in chars:
            by_account.setdefault(c.account, c)
        show_account_labels = len(by_account) > 1

        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(0, 8, 0, 0)
        bar_row.setSpacing(10)

        for acct, rep in by_account.items():
            card = QFrame()
            card.setObjectName('bankAccountCard')
            card.setStyleSheet("""
                QFrame#bankAccountCard {
                    background-color: palette(alternateBase);
                    border: 1px solid palette(mid);
                    border-radius: 10px;
                }
                QFrame#bankAccountCard QLabel { border: none; background: transparent; }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 10, 14, 10)
            card_layout.setSpacing(6)

            if show_account_labels:
                acct_lbl = QLabel(f'@{acct}' if acct else 'Unknown Account')
                acct_lbl.setStyleSheet('font-size: 12px; font-weight: bold; color: palette(windowText);')
                card_layout.addWidget(acct_lbl)

            grid = QGridLayout()
            for col, name in enumerate(global_names):
                value = rep.bank_currencies.get(name, 0)
                lbl = QLabel(name)
                lbl.setStyleSheet('font-size: 11px; color: palette(placeholderText);')
                val = QLabel(_n(value))
                f = val.font(); f.setPointSize(f.pointSize() + 2); f.setBold(True); val.setFont(f)
                grid.addWidget(lbl, 0, col, Qt.AlignCenter)
                grid.addWidget(val, 1, col, Qt.AlignCenter)
            card_layout.addLayout(grid)

            result = gold_history.gold_gained(acct, now=int(time.time()))
            delta_lbl = QLabel()
            delta_lbl.setAlignment(Qt.AlignCenter)
            if result is None:
                delta_lbl.setText('change: gathering data…')
                delta_lbl.setStyleSheet('font-size: 10px; color: palette(placeholderText);')
            else:
                delta, window_s = result
                window = f'{window_s // 3600}h' if window_s >= 3600 else f'{max(window_s // 60, 1)}m'
                sign = '+' if delta > 0 else ''
                color = '#3bc28a' if delta > 0 else ('#f87171' if delta < 0 else 'palette(placeholderText)')
                delta_lbl.setText(f'{sign}{delta:,} gold ({window})')
                delta_lbl.setStyleSheet(f'font-size: 11px; font-weight: bold; color: {color};')
            card_layout.addWidget(delta_lbl)

            bar_row.addWidget(card, 1)

        layout.addLayout(bar_row)

    return widget


def _achievement_card(acct: model.AccountAchievements) -> QFrame:
    """Same visual language as _tab_bank's per-account cards -- achievements are
    account-wide too, so this is the analogous summary treatment."""
    card = QFrame()
    card.setObjectName('achievementAccountCard')
    card.setStyleSheet("""
        QFrame#achievementAccountCard {
            background-color: palette(alternateBase);
            border: 1px solid palette(mid);
            border-radius: 10px;
        }
        QFrame#achievementAccountCard QLabel { border: none; background: transparent; }
    """)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 10, 14, 10)
    layout.setSpacing(4)

    acct_lbl = QLabel(f'@{acct.account}' if acct.account else 'Unknown Account')
    acct_lbl.setStyleSheet('font-size: 12px; font-weight: bold; color: palette(windowText);')
    layout.addWidget(acct_lbl)

    pct = (acct.earned_points / acct.total_points * 100) if acct.total_points else 0
    pts_lbl = QLabel(f'{acct.earned_points:,} / {acct.total_points:,} pts')
    f = pts_lbl.font(); f.setPointSize(f.pointSize() + 3); f.setBold(True)
    pts_lbl.setFont(f)
    layout.addWidget(pts_lbl)

    completed = sum(1 for a in acct.achievements if a.completed)
    total = len(acct.achievements)
    sub_lbl = QLabel(f'{pct:.1f}%  ·  {completed:,}/{total:,} achievements earned')
    sub_lbl.setStyleSheet('font-size: 10px; color: palette(placeholderText);')
    layout.addWidget(sub_lbl)

    return card


class AchievementsTab(QWidget):
    """Account-wide achievement browser: summary cards up top (one per account,
    same pattern as the Bank tab's shared-currency cards) plus a searchable,
    filterable, sortable table of every individual achievement underneath."""

    def __init__(self, accounts: list, parent=None):
        super().__init__(parent)
        self._accounts = accounts
        self._multi_account = len({a.account for a in accounts}) > 1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._cards_row = QHBoxLayout()
        self._cards_row.setContentsMargins(16, 12, 16, 4)
        self._cards_row.setSpacing(10)
        layout.addLayout(self._cards_row)
        self._fill_cards()

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(16, 0, 16, 4)
        filter_row.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText('Search achievements…')
        self._search.textChanged.connect(self._rebuild_table)
        filter_row.addWidget(self._search, 1)
        self._status_filter = QComboBox()
        self._status_filter.addItems(['All', 'Unearned', 'Earned'])
        self._status_filter.setCurrentIndex(1)  # unearned-first is the actionable default
        self._status_filter.currentIndexChanged.connect(self._rebuild_table)
        filter_row.addWidget(self._status_filter)
        layout.addLayout(filter_row)

        self._table_slot = QVBoxLayout()
        self._table_slot.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._table_slot, 1)
        self._table_view: QTableView | None = None
        self._placeholder: QLabel | None = None

        self._render_table_or_placeholder()

    def _fill_cards(self) -> None:
        while self._cards_row.count():
            item = self._cards_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for acct in self._accounts:
            self._cards_row.addWidget(_achievement_card(acct), 1)

    def _render_table_or_placeholder(self) -> None:
        if not self._accounts:
            if self._table_view is not None:
                self._table_slot.removeWidget(self._table_view)
                self._table_view.deleteLater()
                self._table_view = None
            if self._placeholder is None:
                self._placeholder = QLabel('No achievement data yet — sync a character with the ESO Helper addon.')
                self._placeholder.setAlignment(Qt.AlignCenter)
                self._placeholder.setStyleSheet('color: palette(placeholderText); font-style: italic; padding: 24px;')
                self._table_slot.addWidget(self._placeholder)
        else:
            if self._placeholder is not None:
                self._table_slot.removeWidget(self._placeholder)
                self._placeholder.deleteLater()
                self._placeholder = None
            self._rebuild_table()

    def update_data(self, accounts: list) -> None:
        """Refresh achievement data in place on periodic reload, instead of
        MainWindow destroying and recreating this whole tab -- see
        SetsTab.update_data() for the same reasoning."""
        self._accounts = accounts
        self._multi_account = len({a.account for a in accounts}) > 1
        self._fill_cards()
        self._render_table_or_placeholder()

    def _rebuild_table(self) -> None:
        # Captured before teardown so a data refresh (or even just typing in the
        # search box, which also calls this) doesn't reset the user's chosen sort
        # column/order back to the hardcoded default every time.
        prev_state = _capture_view_state(self._table_view)
        if self._table_view is not None:
            self._table_slot.removeWidget(self._table_view)
            self._table_view.deleteLater()
            self._table_view = None

        query = self._search.text().strip().lower()
        status = self._status_filter.currentText()
        done_color = QColor('#4dbd74')
        todo_color = QColor('#f87171')

        headers = (['Account'] if self._multi_account else []) + \
            ['Category', 'Subcategory', 'Achievement', 'Points', 'Status']

        rows = []
        for acct in self._accounts:
            for a in acct.achievements:
                if query and query not in a.name.lower():
                    continue
                if status == 'Earned' and not a.completed:
                    continue
                if status == 'Unearned' and a.completed:
                    continue
                row = []
                if self._multi_account:
                    row.append(_cell(acct.account, acct.account))
                status_label = ('✓ Earned' if a.completed else '✗ Unearned')
                row += [
                    _cell(a.category, a.category),
                    _cell(a.subcategory or '—', a.subcategory),
                    _cell(a.name, a.name),
                    _cell(a.points, a.points),
                    _cell(status_label, 1 if a.completed else 0, None,
                          done_color if a.completed else todo_color),
                ]
                rows.append(row)

        status_col = len(headers) - 1
        _ta = time.monotonic()  # temporary timing instrumentation
        tv = _make_view(CharTable(headers, rows))
        logging.info('AchievementsTab._rebuild_table: _make_view took %.0fms (%d rows)',
                      (time.monotonic() - _ta) * 1000, len(rows))
        tv.setItemDelegateForColumn(status_col, _PillDelegate(tv))
        _ta = time.monotonic()
        if prev_state:
            _restore_view_state(tv, prev_state)
        else:
            tv.sortByColumn(headers.index('Category'), Qt.SortOrder.AscendingOrder)
        logging.info('AchievementsTab._rebuild_table: sort/restore took %.0fms',
                      (time.monotonic() - _ta) * 1000)
        _ta = time.monotonic()
        self._table_slot.addWidget(tv, 1)
        self._table_view = tv
        logging.info('AchievementsTab._rebuild_table: addWidget took %.0fms',
                      (time.monotonic() - _ta) * 1000)


def _set_card(acct: model.AccountSetCollections) -> QFrame:
    """Same visual language as _achievement_card -- set collections are
    account-wide too."""
    card = QFrame()
    card.setObjectName('setAccountCard')
    card.setStyleSheet("""
        QFrame#setAccountCard {
            background-color: palette(alternateBase);
            border: 1px solid palette(mid);
            border-radius: 10px;
        }
        QFrame#setAccountCard QLabel { border: none; background: transparent; }
    """)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 10, 14, 10)
    layout.setSpacing(4)

    acct_lbl = QLabel(f'@{acct.account}' if acct.account else 'Unknown Account')
    acct_lbl.setStyleSheet('font-size: 12px; font-weight: bold; color: palette(windowText);')
    layout.addWidget(acct_lbl)

    complete = sum(1 for s in acct.sets if s.complete)
    total_sets = len(acct.sets)
    pieces_unlocked = sum(s.unlocked for s in acct.sets)
    pieces_total = sum(s.total for s in acct.sets)
    pct = (pieces_unlocked / pieces_total * 100) if pieces_total else 0

    sets_lbl = QLabel(f'{complete:,} / {total_sets:,} sets complete')
    f = sets_lbl.font(); f.setPointSize(f.pointSize() + 3); f.setBold(True)
    sets_lbl.setFont(f)
    layout.addWidget(sets_lbl)

    sub_lbl = QLabel(f'{pct:.1f}%  ·  {pieces_unlocked:,}/{pieces_total:,} pieces collected')
    sub_lbl.setStyleSheet('font-size: 10px; color: palette(placeholderText);')
    layout.addWidget(sub_lbl)

    return card


# Coarse Dungeon/Overland/Trial/PVP/Arena/Monster/Mythic/Class/Crafted bucket order
# (SetCollectionEntry.type_bucket, derived from ESO's own Item Set Collections API)
# for the Sets tab's Type filter -- module-level so both SetsTab.__init__ and
# update_data() build the same dropdown without duplicating the list.
_SET_TYPE_BUCKET_ORDER = ['Dungeon', 'Trial', 'Arena', 'Overland', 'PVP', 'Monster',
                          'Mythic', 'Class', 'Crafted', 'Other']


class SetsTab(QWidget):
    """Account-wide set-collection browser: summary cards up top (one per account,
    same pattern as AchievementsTab) plus a searchable, area-filterable, sortable
    table of every set and how many of its pieces have been collected."""

    def __init__(self, accounts: list, parent=None):
        super().__init__(parent)
        self._accounts = accounts
        self._multi_account = len({a.account for a in accounts}) > 1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._cards_row = QHBoxLayout()
        self._cards_row.setContentsMargins(16, 12, 16, 4)
        self._cards_row.setSpacing(10)
        layout.addLayout(self._cards_row)
        self._fill_cards()

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(16, 0, 16, 4)
        filter_row.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText('Search sets…')
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._rebuild_table)
        filter_row.addWidget(self._search, 1)
        # Type: the actionable "what kind of content" filter. Area (below) stays as
        # the finer-grained specific-zone filter for narrowing within a type.
        self._type_filter = QComboBox()
        self._type_filter.currentIndexChanged.connect(self._rebuild_table)
        filter_row.addWidget(self._type_filter)
        self._area_filter = QComboBox()
        self._area_filter.currentIndexChanged.connect(self._rebuild_table)
        filter_row.addWidget(self._area_filter)
        self._fill_type_and_area_options()
        self._status_filter = QComboBox()
        self._status_filter.addItems(['All', 'Missing pieces', 'Complete'])
        self._status_filter.setCurrentIndex(1)  # missing-first is the actionable default
        self._status_filter.currentIndexChanged.connect(self._rebuild_table)
        filter_row.addWidget(self._status_filter)
        layout.addLayout(filter_row)

        self._table_slot = QVBoxLayout()
        self._table_slot.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._table_slot, 1)
        self._table_view: QTableView | None = None
        self._placeholder: QLabel | None = None

        self._render_table_or_placeholder()

    def _fill_cards(self) -> None:
        while self._cards_row.count():
            item = self._cards_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for acct in self._accounts:
            self._cards_row.addWidget(_set_card(acct), 1)

    def _fill_type_and_area_options(self) -> None:
        """(Re)populates the Type/Area dropdowns from self._accounts, preserving
        the current selection if it still exists -- used both at construction and
        from update_data() so a periodic background refresh doesn't reset the
        user's filter choice (see update_data's docstring)."""
        buckets_present = {s.type_bucket for a in self._accounts for s in a.sets}
        prev_type = self._type_filter.currentData()
        self._type_filter.blockSignals(True)
        self._type_filter.clear()
        self._type_filter.addItem('All Types', None)
        for bucket in _SET_TYPE_BUCKET_ORDER:
            if bucket in buckets_present:
                self._type_filter.addItem(bucket, bucket)
        idx = self._type_filter.findData(prev_type)
        self._type_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self._type_filter.blockSignals(False)

        areas = sorted({s.category for a in self._accounts for s in a.sets if s.category})
        prev_area = self._area_filter.currentData()
        self._area_filter.blockSignals(True)
        self._area_filter.clear()
        self._area_filter.addItem('All Areas', None)
        for area in areas:
            self._area_filter.addItem(area, area)
        idx = self._area_filter.findData(prev_area)
        self._area_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self._area_filter.blockSignals(False)

    def _render_table_or_placeholder(self) -> None:
        if not self._accounts:
            if self._table_view is not None:
                self._table_slot.removeWidget(self._table_view)
                self._table_view.deleteLater()
                self._table_view = None
            if self._placeholder is None:
                self._placeholder = QLabel('No set collection data yet — sync a character with the ESO Helper addon.')
                self._placeholder.setAlignment(Qt.AlignCenter)
                self._placeholder.setStyleSheet('color: palette(placeholderText); font-style: italic; padding: 24px;')
                self._table_slot.addWidget(self._placeholder)
        else:
            if self._placeholder is not None:
                self._table_slot.removeWidget(self._placeholder)
                self._placeholder.deleteLater()
                self._placeholder = None
            self._rebuild_table()

    def update_data(self, accounts: list) -> None:
        """Refresh set-collection data in place on periodic reload (background
        timer / manual Sync), instead of MainWindow destroying and recreating this
        whole tab -- that reset the search text and Type/Area/Status filters back
        to defaults every 60s, same problem BuildsTab.update_data() already solves
        for the Builds tab."""
        self._accounts = accounts
        self._multi_account = len({a.account for a in accounts}) > 1
        self._fill_cards()
        self._fill_type_and_area_options()
        self._render_table_or_placeholder()

    def _rebuild_table(self) -> None:
        # Captured before teardown -- see AchievementsTab._rebuild_table for why
        # (this also runs on every search/filter change, not just reload).
        prev_state = _capture_view_state(self._table_view)
        if self._table_view is not None:
            self._table_slot.removeWidget(self._table_view)
            self._table_view.deleteLater()
            self._table_view = None

        query = self._search.text().strip().lower()
        set_type = self._type_filter.currentData()
        area = self._area_filter.currentData()
        status = self._status_filter.currentText()
        done_color = QColor('#4dbd74')
        todo_color = QColor('#f87171')

        headers = (['Account'] if self._multi_account else []) + \
            ['Type', 'Area', 'Set', 'Collected', 'Status']

        rows = []
        for acct in self._accounts:
            for s in acct.sets:
                if query and query not in s.name.lower():
                    continue
                if set_type and s.type_bucket != set_type:
                    continue
                if area and s.category != area:
                    continue
                if status == 'Complete' and not s.complete:
                    continue
                if status == 'Missing pieces' and s.complete:
                    continue
                row = []
                if self._multi_account:
                    row.append(_cell(acct.account, acct.account))
                status_label = '✓ Complete' if s.complete else '✗ Missing pieces'
                row += [
                    _cell(s.type_bucket, s.type_bucket),
                    _cell(s.category or '—', s.category),
                    _cell(s.name, s.name),
                    _cell(f'{s.unlocked}/{s.total}', s.unlocked / s.total if s.total else 0),
                    _cell(status_label, 1 if s.complete else 0, None,
                          done_color if s.complete else todo_color),
                ]
                rows.append(row)

        status_col = len(headers) - 1
        _ta = time.monotonic()  # temporary timing instrumentation
        tv = _make_view(CharTable(headers, rows))
        logging.info('SetsTab._rebuild_table: _make_view took %.0fms (%d rows)',
                      (time.monotonic() - _ta) * 1000, len(rows))
        tv.setItemDelegateForColumn(status_col, _PillDelegate(tv))
        if prev_state:
            _restore_view_state(tv, prev_state)
        else:
            tv.sortByColumn(headers.index('Set'), Qt.SortOrder.AscendingOrder)
        self._table_slot.addWidget(tv, 1)
        self._table_view = tv


# ── armory slot alias ────────────────────────────────────────────────────────
# Armory uses "Shoulders"; build-manager uses "Shoulder"
_SLOT_ALIAS = {"Shoulders": "Shoulder"}


# ── armory-aware build list ───────────────────────────────────────────────────

_ARMORY_ROLE = Qt.ItemDataRole.UserRole + 1  # stores (char_name, build_name) tuple

class ArmoryBuildListPanel(QWidget):
    """Left-hand list of a character's in-game Armory loadouts, as captured by
    the ESO Helper addon. Read-only -- no saved builds, no add/edit/delete."""
    armory_selected = Signal(str, str)  # (char_name, build_name)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(275)
        self._armory_char: str = ''
        self._armory_builds: dict[str, dict] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(2)
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(14)
        self._tree.setAnimated(True)
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._tree.setColumnWidth(1, 85)
        self._tree.setStyleSheet("""
            QTreeWidget { border: none; font-size: 13px; }
            QTreeWidget::item { padding: 3px 2px; }
            QTreeWidget::item:selected { border-radius: 4px; }
        """)
        self._tree.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self._tree)

    def set_armory_data(self, char_name: str, builds: dict[str, dict]) -> None:
        self._armory_char = char_name
        self._armory_builds = {k: v for k, v in builds.items() if not k.startswith('_')}
        self._rebuild_tree()

    def current_loadout(self) -> str | None:
        item = self._tree.currentItem()
        data = item.data(0, _ARMORY_ROLE) if item else None
        return data[1] if data else None

    def _rebuild_tree(self) -> None:
        prev = self.current_loadout()
        self._tree.blockSignals(True)
        self._tree.clear()

        first_child = restore_child = None
        if self._armory_builds:
            group = QTreeWidgetItem(['  Current Builds', f'({len(self._armory_builds)})'])
            group.setFlags(Qt.ItemFlag.ItemIsEnabled)
            gf = QFont(); gf.setBold(True); gf.setPointSize(gf.pointSize() - 1)
            group.setFont(0, gf)
            sf = QFont(); sf.setItalic(True); sf.setPointSize(sf.pointSize() - 1)
            group.setFont(1, sf)
            group.setForeground(0, QColor('#88aaff'))
            group.setForeground(1, QColor('#666666'))
            self._tree.addTopLevelItem(group)
            group.setExpanded(True)
            for build_name in sorted(self._armory_builds):
                child = QTreeWidgetItem([f'  {build_name}', ''])
                child.setData(0, _ARMORY_ROLE, (self._armory_char, build_name))
                group.addChild(child)
                first_child = first_child or child
                if build_name == prev:
                    restore_child = child

        self._tree.blockSignals(False)

        target = restore_child or first_child
        if target is not None:
            self._tree.setCurrentItem(target)  # fires _on_item_changed
        else:
            self.armory_selected.emit(self._armory_char, '')  # nothing to show

    def _on_item_changed(self, current, _prev) -> None:
        armory = current.data(0, _ARMORY_ROLE) if current is not None else None
        if armory is not None:
            self.armory_selected.emit(*armory)


# ── builds tab ───────────────────────────────────────────────────────────────

class BuildsTab(QWidget):
    """Read-only view of each character's in-game Armory loadouts (skills / CP /
    gear), populated entirely from the ESO Helper addon. No build authoring: no
    saved builds, no editor, no import/export -- pick a character, pick a
    loadout, look at what it's running."""

    def __init__(self, chars: list[model.Character],
                 worn_gear: dict[str, dict],
                 parent=None):
        super().__init__(parent)
        self._chars     = {c.name: c for c in chars}
        self._worn      = worn_gear

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        # character picker row
        top = QHBoxLayout()
        top.addWidget(QLabel('Character:'))
        self._picker = QComboBox()
        for c in sorted(chars, key=lambda x: x.name):
            self._picker.addItem(c.name, c)
        self._picker.currentIndexChanged.connect(self._on_char_changed)
        top.addWidget(self._picker)
        top.addStretch()
        lay.addLayout(top)

        # live stats strip
        self._stats_strip = QLabel()
        self._stats_strip.setStyleSheet('color: #aaa; font-size: 11px; padding: 2px 4px;')
        lay.addWidget(self._stats_strip)

        line = QFrame(); line.setFrameShape(QFrame.HLine)
        lay.addWidget(line)

        # main splitter: left=builds, right=sheet+WW
        outer = QSplitter(Qt.Horizontal)
        self._build_list = ArmoryBuildListPanel()
        outer.addWidget(self._build_list)

        self._right_stack = QStackedWidget()

        self._build_sheet = BuildSheetWidget()
        self._right_stack.addWidget(self._build_sheet)

        outer.addWidget(self._right_stack)
        outer.setStretchFactor(0, 0)
        outer.setStretchFactor(1, 1)
        lay.addWidget(outer, stretch=1)

        self._build_list.armory_selected.connect(self._on_armory_selected)

        # init with first character
        self._on_char_changed(0)

    def update_data(self, chars: list[model.Character], worn_gear: dict[str, dict]) -> None:
        """Refresh character-linked data (picker list, worn gear, live stats) on
        periodic reload, without touching _build_list/_build_sheet -- those hold
        the state (selected build, scroll position) a background refresh must
        not disturb."""
        self._chars = {c.name: c for c in chars}
        self._worn = worn_gear

        prev = self._picker.currentData()
        prev_name = prev.name if prev else None
        self._picker.blockSignals(True)
        self._picker.clear()
        for c in sorted(chars, key=lambda x: x.name):
            self._picker.addItem(c.name, c)
        idx = self._picker.findText(prev_name) if prev_name else -1
        self._picker.setCurrentIndex(idx if idx >= 0 else 0)
        self._picker.blockSignals(False)

        char = self._picker.currentData()
        if char is not None:
            self._build_list.set_armory_data(char.name, self._worn.get(char.name, {}))
            self._update_stats_strip(char)

    def _on_char_changed(self, _idx: int) -> None:
        char: model.Character = self._picker.currentData()
        if char is None:
            return
        self._build_list.set_armory_data(char.name, self._worn.get(char.name, {}))
        self._update_stats_strip(char)
        self._right_stack.setCurrentIndex(0)

    def _armory_to_objects(self, build_name: str, build: dict, char
                           ) -> tuple['Build', list['Skill'], list['GearPiece']]:
        attrs = build.get('attributes', {})
        subclasses = build.get('subclasses') or []
        masteries  = build.get('masteries')  or []
        cp = build.get('cp', {})
        cp_slot_list: list[str] = []
        for discipline in ('Craft', 'Warfare', 'Fitness'):
            val = cp.get(discipline, {})
            stars = list(val.keys())[:4] if isinstance(val, dict) else []
            stars += [''] * (4 - len(stars))
            cp_slot_list.extend(stars)

        build_obj = Build(
            name=build_name,
            eso_class=char.class_name if char else '',
            attribute_health=attrs.get('health', 0),
            attribute_magicka=attrs.get('magicka', 0),
            attribute_stamina=attrs.get('stamina', 0),
            cp_slots=json.dumps(cp_slot_list),
            subclass_1=subclasses[0] if len(subclasses) > 0 else '',
            subclass_2=subclasses[1] if len(subclasses) > 1 else '',
            class_masteries=json.dumps(masteries),
        )

        skills: list[Skill] = []
        raw_skills = build.get('skills', {})
        for bar_idx, bar_name in enumerate(('Front Bar', 'Back Bar')):
            bar = raw_skills.get(bar_name, [])
            for slot_idx, item in enumerate(bar[:6]):
                name = item.get('name', item) if isinstance(item, dict) else item
                if name:
                    skills.append(Skill(build_id=0, bar=bar_idx, slot=slot_idx, name=name))

        gear: list[GearPiece] = []
        raw_gear = build.get('gear', build)  # old format: flat dict
        for slot, info in raw_gear.items():
            if not isinstance(info, dict):
                continue
            slot_mapped = _SLOT_ALIAS.get(slot, slot)
            gear.append(GearPiece(
                build_id=0, slot=slot_mapped,
                set_name=info.get('setName', ''),
                quality=info.get('quality', 'Epic'),
                enchant=info.get('enchant', '').removesuffix(' Enchantment'),
                weight=info.get('weight', ''),
                trait=info.get('trait', ''),
            ))

        return build_obj, skills, gear

    def _on_armory_selected(self, char_name: str, build_name: str) -> None:
        build = self._worn.get(char_name, {}).get(build_name, {})
        if not build:
            self._build_sheet.clear()
            return
        char  = self._chars.get(char_name)
        build_obj, skills, gear = self._armory_to_objects(build_name, build, char)
        self._build_sheet.load_direct(build_obj, skills, gear)
        self._right_stack.setCurrentIndex(0)

    def _update_stats_strip(self, char: model.Character) -> None:
        self._stats_strip.setText(
            f'Live stats — '
            f'HP: {char.health_max:,}  '
            f'Stam: {char.stamina_max:,}  '
            f'Mag: {char.magicka_max:,}  '
            f'Spell Dmg: {char.spell_damage:,}  '
            f'Wpn Dmg: {char.weapon_damage:,}  '
            f'Crit: {char.crit_chance:.1f}%  '
            f'Phys Res: {char.resist_physical:,}  '
            f'Spell Res: {char.resist_spell:,}'
        )


# ── main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, extra_tab: tuple[QWidget, str] | None = None):
        super().__init__()
        self.setWindowTitle('ESO Helper')
        self._quitting = False
        # Composition hook for eso-helper (../main.py): an extra top-level tab
        # (currently the addon manager's own MainWindow, titled "Addons") to sit
        # alongside Character/Activities/Storage/Collection below, instead of
        # being a separate outer tab one level up. Standalone runs of this app
        # pass nothing and get the same 4 tabs as always. Kept alive across
        # _rebuild_tabs() the same way _kept_tabs are -- it isn't ours to
        # destroy, the composition layer owns it.
        self._extra_tab = extra_tab

        # Bare QSettings() -- must match settings_dialog.py's usage so geometry and
        # server/sync settings live in the same file. Explicit-args QSettings('Cubic
        # Serenity', 'ESOBuildManager') (no space) used to be used here, which
        # silently wrote to a DIFFERENT file than everything else and cost real
        # debugging time -- worth never repeating. As of the 2026-09-11 rename off
        # "ESO Build Manager", app.py's create_app() sets applicationName="ESO Helper
        # Viewer" (distinct from the outer composed window's own "ESO Helper", to
        # avoid the same class of bug the other way -- see eso-helper/main.py's
        # comment on this) and migrates values from the old "ESO Build Manager"
        # identity on first run.
        self._settings = QSettings()
        if geo := self._settings.value('geometry'):
            self.restoreGeometry(geo)
        else:
            self.resize(1300, 820)

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)
        self.setCentralWidget(central)

        self._setup_menu()

        # Account/Server pickers: each hidden individually unless characters from
        # more than one ESO account / more than one megaserver (NA vs EU -- see
        # model.py's Character.server) show up in the data, since most setups
        # only ever have one of each. The row itself stays visible as long as
        # either one has something to filter.
        acct_row = QHBoxLayout()
        self._account_label = QLabel('Account:')
        acct_row.addWidget(self._account_label)
        self._account_picker = QComboBox()
        self._account_picker.addItem('All Accounts', None)
        self._account_picker.currentIndexChanged.connect(self._on_account_changed)
        acct_row.addWidget(self._account_picker)
        self._server_label = QLabel('Server:')
        acct_row.addWidget(self._server_label)
        self._server_picker = QComboBox()
        self._server_picker.addItem('All Servers', None)
        self._server_picker.currentIndexChanged.connect(self._on_server_changed)
        acct_row.addWidget(self._server_picker)
        acct_row.addStretch()
        self._account_row = QWidget()
        self._account_row.setLayout(acct_row)
        self._account_row.setVisible(False)
        lay.addWidget(self._account_row)

        self._tabs = QTabWidget()
        lay.addWidget(self._tabs)

        self._status = QStatusBar()
        self.setStatusBar(self._status)

        # Kept across reloads (see _rebuild_tabs) so periodic refresh doesn't blow
        # away the Builds tab's own state -- selected build, scroll position, any
        # open editor. Achievements/Sets get the same treatment for their search
        # text and filter dropdowns (see AchievementsTab/SetsTab.update_data()).
        self._builds_tab: BuildsTab | None = None
        self._achievements_tab: AchievementsTab | None = None
        self._sets_tab: SetsTab | None = None

        # Only asked once, ever -- a machine that already has a sync/mode
        # saved (from a previous run, or from Settings) keeps using it
        # silently instead of popping this up over whatever else is on
        # screen (e.g. the game, full-screen, on zeus) every single launch.
        # Change modes via Settings if needed.
        if not self._settings.contains('sync/mode'):
            from eso_viewer.ui.startup_dialog import StartupModeDialog
            dlg = StartupModeDialog(self)
            if dlg.exec() and dlg.mode:
                self._settings.setValue('sync/mode', dlg.mode)

        self._reload_worker: _ReloadWorker | None = None
        self._event_listener: sync_events.SyncEventListener | None = None
        # Belt-and-braces alongside _tray_quit()'s own stop() call: the
        # composed app (eso-helper's own main.py) has its own outer tray
        # Quit action that calls QApplication.quit() directly rather than
        # going through this window's _tray_quit(), so this is the one path
        # guaranteed to run before the SyncEventListener QThread would
        # otherwise get destroyed while still running (a Qt warning at best,
        # a crash at worst) no matter which "Quit" actually fired.
        QApplication.instance().aboutToQuit.connect(self._stop_background_threads)
        self._reload()

        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.timeout.connect(self._reload)
        self._apply_refresh_strategy()

        # Reloads shortly (debounced) after the game actually writes new
        # SavedVariables data in "This PC" mode, instead of waiting on the 60s
        # auto-refresh timer above.
        self._save_change_debounce = QTimer(self)
        self._save_change_debounce.setSingleShot(True)
        self._save_change_debounce.setInterval(SAVE_CHANGE_DEBOUNCE_MS)
        self._save_change_debounce.timeout.connect(self._reload)

        self._save_watcher = QFileSystemWatcher(self)
        self._save_watcher.directoryChanged.connect(self._on_save_dir_changed)
        self._save_watcher.fileChanged.connect(self._on_save_file_changed)
        self._init_save_watcher()

        self._setup_tray()

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(QIcon(TRAY_ICON_FILE), self)
        self._tray.setToolTip('ESO Helper')

        menu = QMenu()
        menu.addAction(QAction('Show', self, triggered=self._tray_show))
        menu.addSeparator()
        menu.addAction(QAction('Quit', self, triggered=self._tray_quit))
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
        self._stop_background_threads()
        self.close()
        QApplication.quit()

    def _stop_background_threads(self):
        if self._event_listener is not None:
            self._event_listener.stop()
            self._event_listener.wait(2000)
            self._event_listener = None

    def _init_save_watcher(self):
        """(Re)establish the SavedVariables watch for "This PC" mode -- reads
        the same ~/.config/eso-helper/sync.json remote_dir
        _pull_save_file() copies from. Safe to call again later if sync mode
        changes (addPath()/removePath() on an already-(un)watched path are
        no-ops).

        Watches both the directory *and* the individual save file, since neither
        alone is reliable: a directory-level inotify watch (what QFileSystemWatcher
        uses on Linux) only reports entries being created/deleted/renamed/attrib-
        changed within it -- confirmed via /proc/<pid>/fdinfo, the watch mask has
        no IN_MODIFY bit -- so a plain in-place write to an existing file's
        *content* never reaches it. A file-level watch catches that (it does carry
        IN_MODIFY), but the OS watch is tied to the file's inode, so it's silently
        dropped if the game replaces the file via write-then-rename instead of
        writing in place. Between the two, one of them fires regardless of which
        write style the addon uses."""
        for path in self._save_watcher.directories() + self._save_watcher.files():
            self._save_watcher.removePath(path)

        if QSettings().value('sync/mode', 'this_pc') != 'this_pc':
            return
        remote_dir = _load_sync_config().get('remote_dir')
        if not remote_dir or not os.path.isdir(remote_dir):
            return

        self._save_watcher.addPath(remote_dir)
        for fname in _SYNC_FILES:
            fpath = os.path.join(remote_dir, fname)
            if os.path.exists(fpath):
                self._save_watcher.addPath(fpath)

    def _on_save_file_changed(self, path: str):
        # Re-add: if this fired because the file was replaced (write-then-rename)
        # rather than modified in place, Qt has already dropped it from the watch
        # list (the old inode is gone) -- addPath() on a file that still exists
        # re-arms the watch on the new inode. A no-op if the file was modified in
        # place, since it's already watched.
        if os.path.exists(path):
            self._save_watcher.addPath(path)
        self._save_change_debounce.start()

    def _on_save_dir_changed(self, path: str):
        # A directory-level watch survives the game replacing ESOHelper.lua
        # wholesale (write-to-temp-then-rename) -- a file-level QFileSystemWatcher
        # would silently stop firing after the first such change, since the
        # original inode it was watching is gone. Debounced (SAVE_CHANGE_DEBOUNCE_MS)
        # so this fires once after the game has actually finished writing, not
        # mid-write and not once per file in a burst of saves.
        self._save_change_debounce.start()

    def _setup_menu(self):
        # File
        self._reload_action = QAction('&Reload Data', self)
        self._reload_action.setShortcut('Ctrl+R')
        self._reload_action.setStatusTip('Sync save files (see Settings…) and reload character data')
        self._reload_action.triggered.connect(self._reload)
        file_menu = self.menuBar().addMenu('&File')
        file_menu.addAction(self._reload_action)
        file_menu.addSeparator()
        file_menu.addAction(QAction('&Settings…', self, triggered=self._open_settings))
        file_menu.addSeparator()
        file_menu.addAction(QAction('E&xit', self, triggered=self.close))

        # Help
        help_menu = self.menuBar().addMenu('&Help')
        help_menu.addAction(QAction('About…', self, triggered=self._about))

    def closeEvent(self, event):
        if not self._quitting:
            event.ignore()
            self.hide()
            return
        self._settings.setValue('geometry', self.saveGeometry())
        super().closeEvent(event)

    def _open_settings(self):
        from eso_viewer.ui.settings_dialog import SettingsDialog
        SettingsDialog(self).exec()
        # Picks up a changed sync mode (This PC / Sync Server) or any
        # untracked-dailies changes made in the dialog without waiting for the
        # 60s auto-refresh timer to fire.
        self._init_save_watcher()
        self._apply_refresh_strategy()
        self._reload()

    def _about(self):
        QMessageBox.about(self, 'About ESO Helper',
            '<b>ESO Helper</b><br><br>'
            'Character, activity, and loadout viewer for Elder Scrolls Online.<br><br>'
            'Built with Python &amp; PySide6.<br>'
            '&copy; CubicSerenity')

    def _reload(self):
        # Guards against overlapping reloads -- Ctrl+R, the 60s timer/SSE
        # push, and the save-file watcher's debounce can all fire close
        # together, and _ReloadWorker instances aren't safe to run two of at
        # once against the same self._all_chars etc. The one already in
        # flight will apply its own (fresher-or-equal) result shortly; this
        # request is simply dropped rather than queued.
        if self._reload_worker is not None and self._reload_worker.isRunning():
            return
        self._reload_action.setEnabled(False)
        self._status.showMessage('Loading…')
        mode = QSettings().value('sync/mode', 'this_pc')
        push_enabled = mode != 'server' and QSettings().value('sync/push_enabled', False, type=bool)
        worker = _ReloadWorker(mode, push_enabled, self)
        worker.succeeded.connect(self._on_reload_succeeded)
        worker.failed.connect(self._on_reload_failed)
        self._reload_worker = worker
        worker.start()

    def _on_reload_succeeded(self, result: dict):
        self._all_chars = result['chars']
        self._all_achievements = result['achievements']
        self._all_set_collections = result['set_collections']
        self._worn_data = result['worn_data']
        self._update_account_picker()
        self._rebuild_tabs()
        _record_gold_snapshot(self._all_chars)
        if result['push_error']:
            self._status.showMessage(f"Local data loaded, but push to sync server failed: {result['push_error']}")
        else:
            self._status.clearMessage()
        self._reload_action.setEnabled(True)

    def _on_reload_failed(self, message: str):
        self._status.showMessage(f'Error: {message}')
        self._reload_action.setEnabled(True)

    def _apply_refresh_strategy(self):
        """Called once at startup and again after Settings closes (sync mode
        or server_url may have just changed). "Sync Server" mode gets an
        `SyncEventListener` (see eso_viewer/sync/events.py) instead of relying
        on the 60s timer -- the sync server pushes a `characters_updated`/etc.
        SSE event within seconds of any other machine's push, rather than
        this client finding out up to a minute later. The 60s timer is kept
        running as a much-longer-interval backstop (5 min) in either mode:
        for "This PC" it's the original always-on poll (belt-and-braces
        alongside the save-file watcher), and for "Sync Server" it's a safety
        net in case the SSE connection is silently stuck reconnecting."""
        mode = QSettings().value('sync/mode', 'this_pc')
        self._auto_refresh_timer.setInterval(60_000 if mode != 'server' else 300_000)
        if not self._auto_refresh_timer.isActive():
            self._auto_refresh_timer.start()

        if self._event_listener is not None:
            self._event_listener.event_received.disconnect(self._on_sync_event)
            self._event_listener.stop()
            self._event_listener.wait(2000)
            self._event_listener = None

        if mode == 'server':
            cfg = _load_sync_config()
            server_url = cfg.get('server_url')
            if server_url:
                listener = sync_events.SyncEventListener(server_url, cfg.get('server_token'), self)
                listener.event_received.connect(self._on_sync_event)
                listener.start()
                self._event_listener = listener

    def _on_sync_event(self, _event: str):
        # Every resource event (characters_updated/achievements_updated/
        # set_collections_updated) triggers the same full _reload() --
        # fetch_all() always pulls all three together anyway (see
        # _ReloadWorker.run()), so there's no cheaper partial-refresh to do.
        self._reload()

    def _update_account_picker(self):
        accounts = sorted({c.account for c in self._all_chars if c.account})
        servers = sorted({c.server for c in self._all_chars if c.server})
        previous = self._account_picker.currentData()
        prev_server = self._server_picker.currentData()

        self._account_picker.blockSignals(True)
        self._account_picker.clear()
        self._account_picker.addItem('All Accounts', None)
        for acct in accounts:
            self._account_picker.addItem(acct, acct)
        restore_idx = self._account_picker.findData(previous)
        self._account_picker.setCurrentIndex(restore_idx if restore_idx >= 0 else 0)
        self._account_picker.blockSignals(False)

        self._server_picker.blockSignals(True)
        self._server_picker.clear()
        self._server_picker.addItem('All Servers', None)
        for srv in servers:
            self._server_picker.addItem(srv, srv)
        restore_idx = self._server_picker.findData(prev_server)
        self._server_picker.setCurrentIndex(restore_idx if restore_idx >= 0 else 0)
        self._server_picker.blockSignals(False)

        self._account_label.setVisible(len(accounts) > 1)
        self._account_picker.setVisible(len(accounts) > 1)
        self._server_label.setVisible(len(servers) > 1)
        self._server_picker.setVisible(len(servers) > 1)
        self._account_row.setVisible(len(accounts) > 1 or len(servers) > 1)

    def _on_account_changed(self, _idx: int) -> None:
        self._rebuild_tabs()

    def _on_server_changed(self, _idx: int) -> None:
        self._rebuild_tabs()

    def _rebuild_tabs(self):
        _t0 = time.monotonic()  # temporary timing instrumentation, see _ReloadWorker.run()
        selected_account = self._account_picker.currentData()
        selected_server = self._server_picker.currentData()

        def _filtered(items):
            if selected_account is not None:
                items = [i for i in items if i.account == selected_account]
            if selected_server is not None:
                items = [i for i in items if i.server == selected_server]
            return items

        chars = _filtered(self._all_chars)
        achievement_accounts = _filtered(self._all_achievements)
        set_accounts = _filtered(self._all_set_collections)
        worn_data = self._worn_data

        # Tabs are nested two levels deep (see `groups` below) -- remember which
        # category *and* which sub-tab within it were selected so a reload
        # doesn't bounce the user back to the first tab of the first category.
        cur_cat = self._tabs.currentIndex()
        cur_sub = self._tabs.currentWidget().currentIndex() \
            if isinstance(self._tabs.currentWidget(), QTabWidget) else 0

        # BuildsTab/AchievementsTab/SetsTab all carry their own state (selected
        # build & open editor; search text & filter dropdowns) that has nothing to
        # do with character-data freshness -- update them in place instead of
        # destroying/recreating every reload, or a background refresh bounces the
        # user back to defaults (top of list, filters reset) every 60s.
        _t1 = time.monotonic()  # temporary timing instrumentation
        if self._builds_tab is None:
            self._builds_tab = BuildsTab(chars, worn_data)
        else:
            self._builds_tab.update_data(chars, worn_data)
        logging.info('_rebuild_tabs: builds_tab took %.0fms', (time.monotonic() - _t1) * 1000)

        _t1 = time.monotonic()
        if self._achievements_tab is None:
            self._achievements_tab = AchievementsTab(achievement_accounts)
        else:
            self._achievements_tab.update_data(achievement_accounts)
        logging.info('_rebuild_tabs: achievements_tab took %.0fms', (time.monotonic() - _t1) * 1000)

        _t1 = time.monotonic()
        if self._sets_tab is None:
            self._sets_tab = SetsTab(set_accounts)
        else:
            self._sets_tab.update_data(set_accounts)
        logging.info('_rebuild_tabs: sets_tab took %.0fms', (time.monotonic() - _t1) * 1000)

        _kept_tabs = (self._builds_tab, self._achievements_tab, self._sets_tab)

        # The remaining tabs are plain read-only tables with no filter state of
        # their own -- destroyed/recreated every reload same as before, but their
        # scroll position and sort column/order are captured here (keyed by tab
        # title, unique across the whole set) and reapplied below so a
        # background refresh doesn't visually jump. Category sub-QTabWidgets
        # themselves carry no state worth keeping -- they're rebuilt fresh below.
        prev_states = {}
        for i in range(self._tabs.count()):
            sub = self._tabs.widget(i)
            if isinstance(sub, QTabWidget):
                for j in range(sub.count()):
                    prev_states[sub.tabText(j)] = _capture_view_state(sub.widget(j))

        for i in range(self._tabs.count()):
            sub = self._tabs.widget(i)
            if not isinstance(sub, QTabWidget):
                continue  # e.g. the injected Addons tab -- not ours to destroy
            for j in range(sub.count()):
                w = sub.widget(j)
                if w not in _kept_tabs:
                    w.deleteLater()
        self._tabs.clear()

        # Grouped from the previous flat 14-tab strip (which needed the
        # scroll-button arrows to reach the last few tabs) into categories a
        # character sheet actually breaks down into. Emoji prefixes stand in
        # for real tab icons (no icon asset pipeline exists in this project --
        # see icon_cache.py, which only fetches *skill* icons off UESP -- so
        # this is the zero-asset option, not a placeholder for a future icon
        # set). Builds lives as its own top-level tab rather than inside
        # Collection -- it's the tab actually opened most, so it gets equal
        # billing with Character/Activities/Storage/Collection instead of
        # being a click deeper.
        def _timed(label, fn, *a):  # temporary timing instrumentation
            _tt0 = time.monotonic()
            result = fn(*a)
            logging.info('_rebuild_tabs: %s took %.0fms', label, (time.monotonic() - _tt0) * 1000)
            return result

        groups = [
            ('🧙 Character', [
                (_timed('_tab_overview', _tab_overview, chars),          '🏠 Overview'),
                (_timed('_tab_bio', _tab_bio, chars),               '👤 Bio'),
                (_timed('_tab_stats', _tab_stats, chars),             '📊 Stats'),
                (_timed('_tab_skills', _tab_skills, chars, worn_data), '⚔️ Skills'),
                (_timed('_tab_guilds', _tab_guilds, chars),            '🏰 Guilds'),
                (_timed('_tab_champion', _tab_champion, chars),          '🌟 Champion'),
            ]),
            ('📅 Activities', [
                (_timed('_tab_dailies', _tab_dailies, chars, self._reload), '✅ Dailies'),
                (_timed('_tab_crafting', _tab_crafting, chars),          '🔨 Crafting'),
            ]),
            ('📦 Storage', [
                (_timed('_tab_inventory', _tab_inventory, chars),         '🎒 Inventory'),
                (_timed('_tab_bank', _tab_bank, chars),            '🏦 Bank'),
            ]),
            ('🏆 Collection', [
                (self._achievements_tab,        '🏆 Achievements'),
                (self._sets_tab,                '🛡️ Sets'),
            ]),
        ]

        for cat_title, tabs in groups:
            sub = QTabWidget()
            for widget, title in tabs:
                sub.addTab(widget, title)
                _restore_view_state(widget, prev_states.get(title))
            self._tabs.addTab(sub, cat_title)

        self._tabs.addTab(self._builds_tab, '📜 Builds')

        if self._extra_tab is not None:
            widget, title = self._extra_tab
            self._tabs.addTab(widget, title)

        self._tabs.setCurrentIndex(max(cur_cat, 0))
        if isinstance(self._tabs.currentWidget(), QTabWidget):
            self._tabs.currentWidget().setCurrentIndex(max(cur_sub, 0))
        self._status.showMessage(f'{len(chars)} characters loaded.')
        logging.info('_rebuild_tabs: took %.0fms (%d chars, on GUI thread -- this is the same cost whether the data came from network or local disk)',
                      (time.monotonic() - _t0) * 1000, len(chars))


# ── Single instance ──────────────────────────────────────────────────────────
# Running two copies (e.g. one from --tray autostart, one launched by hand)
# would mean two writers pulling/watching the same SavedVariables file and two
# independent reload timers racing each other. A QLocalServer/QLocalSocket
# handshake is the standard Qt way to detect and defer to an already-running
# instance instead. (Only exercised standalone -- the composed eso-helper app
# has its own separate single-instance lock, see ../main.py.)
_SINGLE_INSTANCE_KEY = 'eso-helper-viewer-single-instance'


def _notify_running_instance() -> bool:
    """True if another instance answered (and was asked to raise its window),
    meaning this process should exit instead of starting a second one."""
    socket = QLocalSocket()
    socket.connectToServer(_SINGLE_INSTANCE_KEY)
    if socket.waitForConnected(200):
        socket.write(b'show')
        socket.flush()
        socket.waitForBytesWritten(200)
        socket.disconnectFromServer()
        return True
    return False


def _start_single_instance_server(on_show) -> QLocalServer:
    # A prior crash can leave a stale socket behind on Linux, which would
    # otherwise make listen() below fail as if a real instance still owned it.
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


if __name__ == '__main__':
    app = create_app(sys.argv)
    app.setStyle('Fusion')
    if _notify_running_instance():
        sys.exit(0)
    win = MainWindow()
    _instance_server = _start_single_instance_server(win._tray_show)
    if '--tray' not in sys.argv:
        win.showMaximized()
    sys.exit(app.exec())
