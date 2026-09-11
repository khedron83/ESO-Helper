import json
from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel,
    QScrollArea, QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
)

from eso_build_manager.data_loader import load_set_details, skill_icon_url
from eso_build_manager.icon_cache import fetch_icon

_SHEET_ICON_SIZE = 42

from eso_build_manager.constants import (
    CLASS_COLORS, CP_TREE_COLORS, MYTHIC_COLOR, QUALITY_COLORS, ROLE_COLORS,
)

_SET_DETAILS: dict[str, dict] | None = None


def _fmt_updated(iso_str: str) -> str:
    if not iso_str:
        return ''
    try:
        ts = datetime.fromisoformat(iso_str)
    except ValueError:
        return ''
    delta = datetime.now(timezone.utc) - ts.astimezone(timezone.utc)
    secs = delta.total_seconds()
    if secs < 60:    return 'Updated just now'
    if secs < 3600:  return f'Updated {int(secs // 60)}m ago'
    if secs < 86400: return f'Updated {int(secs // 3600)}h ago'
    return f'Updated {int(secs // 86400)}d ago'


def _get_set_details() -> dict[str, dict]:
    global _SET_DETAILS
    if _SET_DETAILS is None:
        _SET_DETAILS = load_set_details()
    return _SET_DETAILS


def _rgba(hex_color: str, alpha: float) -> str:
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    return f"rgba({r},{g},{b},{alpha})"


class _Badge(QLabel):
    def __init__(self, text: str, color: str = "#555566", parent=None):
        super().__init__(f"  {text}  ", parent)
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        fg = "#111111" if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else "#ffffff"
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: {fg};
                border-radius: 10px;
                padding: 3px 0px;
                font-weight: 600;
                font-size: 11px;
            }}
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


class _SkillCard(QFrame):
    def __init__(self, slot_label: str, skill_name: str = "", accent: str = "#4a9eff",
                 show_icon: bool = False, parent=None):
        super().__init__(parent)
        filled = bool(skill_name.strip())

        if filled:
            self.setStyleSheet(f"""
                QFrame {{
                    border: 2px solid {accent};
                    border-radius: 6px;
                    background-color: {_rgba(accent, 0.07)};
                }}
                QLabel {{ border: none; background: transparent; }}
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    border: 1px solid palette(mid);
                    border-radius: 6px;
                    background-color: transparent;
                }
                QLabel { border: none; background: transparent; }
            """)

        self.setMinimumWidth(86)
        self.setFixedHeight(100 if show_icon else 48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(4, 6, 4, 6)
        vbox.setSpacing(4)

        self._icon_lbl: QLabel | None = None
        if show_icon:
            self._icon_lbl = QLabel()
            self._icon_lbl.setFixedSize(_SHEET_ICON_SIZE, _SHEET_ICON_SIZE)
            self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # No box shown until an icon actually loads
            self._icon_lbl.setStyleSheet("background: transparent;")
            vbox.addWidget(self._icon_lbl, 0, Qt.AlignmentFlag.AlignHCenter)

        lbl_slot = QLabel(slot_label)
        lbl_slot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_slot.setStyleSheet(
            f"color: {accent}; font-size: 9px; font-weight: bold; letter-spacing: 1px;"
            if filled else
            "color: palette(placeholderText); font-size: 9px; letter-spacing: 1px;"
        )

        lbl_name = QLabel(skill_name.strip() if filled else "—")
        lbl_name.setWordWrap(True)
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_name.setStyleSheet(
            "font-size: 11px; font-weight: 500;"
            if filled else
            "font-size: 11px; color: palette(placeholderText);"
        )

        vbox.addWidget(lbl_slot)
        vbox.addWidget(lbl_name, 1)

        if show_icon and filled:
            url = skill_icon_url(skill_name.strip()) or skill_icon_url("Ulfsild's Contingency")
            if url:
                fetch_icon(url, self._set_icon)

    def _set_icon(self, px: QPixmap) -> None:
        if self._icon_lbl and not px.isNull():
            self._icon_lbl.setStyleSheet(
                "border: 1px solid palette(mid); border-radius: 3px; background: palette(base);"
            )
            self._icon_lbl.setPixmap(px.scaled(
                _SHEET_ICON_SIZE, _SHEET_ICON_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))


class _GearCard(QFrame):
    def __init__(self, slot: str, piece, parent=None):
        super().__init__(parent)
        filled = piece and piece.set_name.strip()
        two_hand = piece and piece.weight == "N/A"

        if filled:
            self.setStyleSheet("""
                QFrame {
                    border: 1px solid palette(mid);
                    border-radius: 6px;
                    background-color: rgba(255,255,255,0.03);
                }
                QLabel { border: none; background: transparent; }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    border: 1px dashed palette(mid);
                    border-radius: 6px;
                    background-color: transparent;
                }
                QLabel { border: none; background: transparent; }
            """)

        self.setMinimumWidth(110)
        self.setMinimumHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(8, 6, 8, 6)
        vbox.setSpacing(2)

        slot_lbl = QLabel(slot.upper())
        slot_lbl.setStyleSheet(
            "color: palette(placeholderText); font-size: 9px; font-weight: bold; letter-spacing: 1px;"
        )
        vbox.addWidget(slot_lbl)

        if two_hand:
            na = QLabel("N/A  (two-handed)")
            na.setStyleSheet("color: palette(placeholderText); font-size: 10px; font-style: italic;")
            vbox.addWidget(na)
        elif filled:
            set_type = _get_set_details().get(piece.set_name, {}).get("type", "")
            q_color = MYTHIC_COLOR if set_type == "Mythic" else QUALITY_COLORS.get(piece.quality, "")
            set_lbl = QLabel(piece.set_name)
            set_lbl.setWordWrap(True)
            set_lbl.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: {q_color};" if q_color
                else "font-size: 12px; font-weight: 600;"
            )
            vbox.addWidget(set_lbl)

            details = "  ·  ".join(p for p in [piece.weight, piece.trait] if p)
            if details:
                det = QLabel(details)
                det.setStyleSheet("color: palette(placeholderText); font-size: 10px;")
                vbox.addWidget(det)

            enchant = piece.enchant.removeprefix("Maximum ").strip()
            if enchant:
                enc = QLabel(enchant)
                enc.setStyleSheet("color: palette(placeholderText); font-size: 10px; font-style: italic;")
                vbox.addWidget(enc)
        else:
            empty = QLabel("—")
            empty.setStyleSheet("color: palette(placeholderText); font-size: 12px;")
            vbox.addWidget(empty)

        vbox.addStretch()


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet("""
        QLabel {
            color: palette(windowText);
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 3px;
            padding-bottom: 4px;
            border-bottom: 2px solid palette(highlight);
        }
    """)
    return lbl


def _section_label_left(text: str) -> QLabel:
    """A section title meant to sit beside its content instead of on its own line above it."""
    lbl = QLabel(text.upper())
    lbl.setWordWrap(True)
    lbl.setFixedWidth(96)
    lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    lbl.setStyleSheet("""
        QLabel {
            color: palette(windowText);
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 1px;
            padding-left: 8px;
            border-left: 2px solid palette(highlight);
        }
    """)
    return lbl


def _section_row(text: str, content: QWidget) -> QWidget:
    w = QWidget()
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(12)
    row.addWidget(_section_label_left(text), 0, Qt.AlignmentFlag.AlignTop)
    row.addWidget(content, 1)
    return w


class BuildSheetWidget(QWidget):
    """Read-only display of a loadout's skills / CP / gear / stats / notes."""

    def __init__(self, parent=None):
        super().__init__(parent)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._inner = QWidget()
        self._vbox = QVBoxLayout(self._inner)
        self._vbox.setContentsMargins(20, 16, 20, 16)
        self._vbox.setSpacing(18)
        scroll.setWidget(self._inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._placeholder_card = self._build_placeholder_card()
        self._vbox.addStretch()
        self._vbox.addWidget(self._placeholder_card, 0, Qt.AlignmentFlag.AlignHCenter)
        self._vbox.addStretch()

    @staticmethod
    def _build_placeholder_card() -> QFrame:
        card = QFrame()
        card.setObjectName("sheetEmptyCard")
        card.setStyleSheet("""
            QFrame#sheetEmptyCard {
                background-color: palette(alternateBase);
                border: 1px solid palette(mid);
                border-radius: 8px;
            }
        """)
        card.setMaximumWidth(340)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(8)

        icon = QLabel("📜")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 32px;")
        layout.addWidget(icon)

        text = QLabel("Select a loadout from the sidebar.")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setWordWrap(True)
        text.setStyleSheet("color: palette(placeholderText); font-size: 14px;")
        layout.addWidget(text)

        return card

    # ── Public API ────────────────────────────────────────────────────────

    def load_direct(self, build, skills, gear) -> None:
        """Display a loadout (name, attributes, skills, CP, gear)."""
        self._rebuild(build, skills, gear)

    def clear(self) -> None:
        self._clear_inner()
        self._vbox.addStretch()
        self._placeholder_card.show()
        self._vbox.addWidget(self._placeholder_card, 0, Qt.AlignmentFlag.AlignHCenter)
        self._vbox.addStretch()

    # ── Internal helpers ──────────────────────────────────────────────────

    def _clear_inner(self) -> None:
        while self._vbox.count():
            item = self._vbox.takeAt(0)
            if w := item.widget():
                if w is not self._placeholder_card:
                    w.deleteLater()

    def _rebuild(self, build, skills, gear) -> None:
        self._placeholder_card.hide()
        self._clear_inner()

        self._vbox.addWidget(self._build_header(build))

        gear_pages = json.loads(build.gear_pages) if build.gear_pages else ["Main"]
        self._vbox.addWidget(self._loadout_section(skills, gear, gear_pages))

        cp_slots = json.loads(build.cp_slots) if build.cp_slots else []
        if any(s.strip() for s in cp_slots):
            self._vbox.addWidget(self._cp_section(cp_slots))

        self._vbox.addWidget(self._stats_section(build))

        if build.notes.strip():
            self._vbox.addWidget(self._notes_section(build.notes))

        self._vbox.addStretch()

    # ── Section builders ──────────────────────────────────────────────────

    def _build_header(self, build) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(12)

        # Name row
        top = QHBoxLayout()
        name_lbl = QLabel(build.name)
        f = name_lbl.font()
        f.setPointSize(f.pointSize() + 10)
        f.setBold(True)
        name_lbl.setFont(f)
        top.addWidget(name_lbl, 1)

        updated_text = _fmt_updated(build.updated_at)
        if updated_text:
            updated_lbl = QLabel(updated_text)
            updated_lbl.setStyleSheet('color: palette(placeholderText); font-size: 11px;')
            updated_lbl.setToolTip(build.updated_at)
            top.addWidget(updated_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        vbox.addLayout(top)

        # Badge row
        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        if build.eso_class:
            badge_row.addWidget(_Badge(build.eso_class, CLASS_COLORS.get(build.eso_class, "#556677")))
        if build.subclass_1:
            badge_row.addWidget(_Badge(build.subclass_1, "#445566"))
        if build.subclass_2:
            badge_row.addWidget(_Badge(build.subclass_2, "#445566"))
        if build.role:
            badge_row.addWidget(_Badge(build.role, ROLE_COLORS.get(build.role, "#556677")))
        if build.content:
            badge_row.addWidget(_Badge(build.content, "#446655"))
        if build.game_patch:
            badge_row.addWidget(_Badge(build.game_patch, "#334455"))
        has_attrs = any([build.attribute_health, build.attribute_magicka, build.attribute_stamina])
        if has_attrs:
            badge_row.addStretch()
            for label, val, color in [
                ("HP", build.attribute_health, "#f87171"),
                ("Mag", build.attribute_magicka, "#60a5fa"),
                ("Stam", build.attribute_stamina, "#4ade80"),
            ]:
                sep = QLabel("·"); sep.setStyleSheet("color:palette(placeholderText);margin:0 2px;")
                v = QLabel(f"{label}: {val}")
                v.setStyleSheet(f"color:{color};font-size:11px;font-weight:bold;")
                badge_row.addWidget(sep); badge_row.addWidget(v)
        else:
            badge_row.addStretch()
        vbox.addLayout(badge_row)

        if build.source.strip():
            src = build.source.strip()
            src_lbl = QLabel()
            src_lbl.setOpenExternalLinks(True)
            if src.startswith("http"):
                src_lbl.setText(f'<a href="{src}" style="color:#60a5fa;">{src}</a>')
            else:
                src_lbl.setText(f'<span style="color:palette(windowText);">Source: {src}</span>')
            src_lbl.setStyleSheet("font-size: 12px;")
            vbox.addWidget(src_lbl)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("QFrame { color: palette(windowText); margin: 0; }")
        vbox.addWidget(line)

        return w

    def _skills_page_widget(self, skills: list) -> QWidget:
        by_slot = {(s.bar, s.slot): s.name for s in skills}

        content = QWidget()
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)

        bars = [
            (0, "Front Bar", "#4a9eff"),
            (1, "Back Bar",  "#f97316"),
        ]
        for bar_idx, bar_label, accent in bars:
            row = QHBoxLayout()
            row.setSpacing(6)

            bar_lbl = QLabel(bar_label)
            bar_lbl.setFixedWidth(68)
            bar_lbl.setStyleSheet(f"color:{accent};font-weight:bold;font-size:11px;")
            row.addWidget(bar_lbl)

            for slot in range(5):
                name = by_slot.get((bar_idx, slot), "")
                row.addWidget(_SkillCard(str(slot + 1), name, accent, show_icon=True))

            ult = by_slot.get((bar_idx, 5), "")
            row.addWidget(_SkillCard("ULT", ult, "#fbbf24", show_icon=True))

            vbox.addLayout(row)

        return _section_row("Skills", content)

    def _cp_section(self, slots: list[str]) -> QWidget:
        while len(slots) < 12:
            slots.append("")

        trees = [
            ("Craft",    CP_TREE_COLORS["Craft"], 0),
            ("Warfare",  CP_TREE_COLORS["Warfare"], 4),
            ("Fitness",  CP_TREE_COLORS["Fitness"], 8),
        ]

        def _rgba(hex_color: str, alpha: float) -> str:
            r, g, b = int(hex_color[1:3],16), int(hex_color[3:5],16), int(hex_color[5:7],16)
            return f"rgba({r},{g},{b},{alpha})"

        content = QWidget()
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)

        for tree_name, color, offset in trees:
            row = QHBoxLayout(); row.setSpacing(6)
            lbl = QLabel(tree_name)
            lbl.setFixedWidth(68)
            lbl.setStyleSheet(f"color:{color};font-weight:bold;font-size:11px;")
            row.addWidget(lbl)
            for i in range(4):
                name = slots[offset + i]
                card = QFrame()
                card.setStyleSheet(
                    f"QFrame{{border:1px solid {color};border-radius:6px;"
                    f"background:{_rgba(color,0.05)};}} "
                    "QLabel{border:none;background:transparent;}"
                )
                card.setFixedHeight(46)
                card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                cl = QVBoxLayout(card); cl.setContentsMargins(4,4,4,4); cl.setSpacing(1)
                name_l = QLabel(name or "—")
                name_l.setWordWrap(True)
                name_l.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                name_l.setStyleSheet(
                    "font-size:10px;font-weight:500;" if name else
                    "font-size:10px;color:palette(placeholderText);"
                )
                cl.addWidget(name_l, 1)
                row.addWidget(card)
            row.addStretch()
            rw = QWidget(); rw.setLayout(row)
            vbox.addWidget(rw)

        return _section_row("Champion Points", content)

    def _gear_page_widget(self, gear: list) -> QWidget:
        by_slot = {g.slot: g for g in gear}

        # One shared grid (label column + 4 slot columns) for every row below,
        # rather than each row picking its own column count -- that's what
        # keeps card edges lined up vertically across armor/jewelry/weapon
        # rows instead of each section drifting to its own column widths.
        _ROWS = [
            ("Armor",     None,      ["Head", "Shoulder", "Chest", "Hands"]),
            ("",          None,      ["Waist", "Legs", "Feet"]),
            ("Jewelry",   None,      ["Neck", "Ring 1", "Ring 2"]),
            ("Front Bar", "#4a9eff", ["Main Hand", "Off Hand"]),
            ("Back Bar",  "#f97316", ["Backup Main", "Backup Off"]),
        ]
        _COLUMNS = 4

        content = QWidget()
        grid = QGridLayout(content)
        grid.setSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)

        for row_i, (row_label, accent, slots) in enumerate(_ROWS):
            lbl = QLabel(row_label)
            lbl.setFixedWidth(68)
            color = accent or "palette(placeholderText)"
            weight = "bold" if accent else "normal"
            lbl.setStyleSheet(f"color:{color};font-weight:{weight};font-size:11px;")
            grid.addWidget(lbl, row_i, 0)

            for col_i, slot in enumerate(slots):
                grid.addWidget(_GearCard(slot, by_slot.get(slot)), row_i, col_i + 1)

        for col in range(1, _COLUMNS + 1):
            grid.setColumnStretch(col, 1)

        return _section_row("Gear", content)

    def _loadout_page_widget(self, skills: list, gear: list) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(24)
        row.addWidget(self._skills_page_widget(skills), 2)
        row.addWidget(self._gear_page_widget(gear), 3)
        return w

    def _loadout_section(self, skills: list, gear: list, page_names: list | None = None) -> QWidget:
        page_names = page_names or ["Main"]

        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(12)

        if len(page_names) <= 1:
            vbox.addWidget(self._loadout_page_widget(skills, gear))
            return w

        skills_by_page: dict = {}
        for s in skills:
            skills_by_page.setdefault(s.page, []).append(s)
        gear_by_page: dict = {}
        for g in gear:
            gear_by_page.setdefault(g.page, []).append(g)

        tabs = QTabWidget()
        for i, name in enumerate(page_names):
            tabs.addTab(
                self._loadout_page_widget(skills_by_page.get(i, []), gear_by_page.get(i, [])),
                name,
            )
        vbox.addWidget(tabs)

        return w

    def _stats_section(self, build) -> QWidget:
        food = (build.food_buff or "").strip()
        mundus = (build.mundus_stone or "").strip()
        if not food and not mundus:
            w = QWidget(); w.setFixedHeight(0); return w

        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(10)
        vbox.addWidget(_section_label("Food & Mundus"))

        row = QHBoxLayout(); row.setSpacing(32)
        for label_text, value in [("Food / Drink", food), ("Mundus Stone", mundus)]:
            if not value:
                continue
            cell = QWidget()
            cell_l = QVBoxLayout(cell)
            cell_l.setContentsMargins(0, 0, 0, 0); cell_l.setSpacing(2)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size:10px;font-weight:bold;letter-spacing:1px;")
            val = QLabel(value)
            val.setStyleSheet("font-size:13px;font-weight:500;")
            cell_l.addWidget(lbl); cell_l.addWidget(val)
            row.addWidget(cell)
        row.addStretch()
        vbox.addLayout(row)
        return w

    def _notes_section(self, notes: str) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(10)
        vbox.addWidget(_section_label("Notes"))
        lbl = QLabel(notes.strip())
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 13px; line-height: 160%;")
        vbox.addWidget(lbl)
        return w
