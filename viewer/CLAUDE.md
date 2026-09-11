# ESO Helper Viewer

A KDE desktop app for viewing Elder Scrolls Online character, activity, and loadout
data at a glance. Built with Python and PySide6, integrating naturally with KDE
Plasma via Qt's system theme. Read-only — it displays what the WornGear addon
collects; it does not author or store builds (see "Builds tab" for the history).

Formerly a standalone project called "ESO Build Manager" — renamed 2026-09-11 when
it became one half of the composed **ESO Helper** app (the other half is
`../addon_manager/`; see `../CLAUDE.md`). This directory (`viewer/`, Python package
`eso_viewer/`) is still independently runnable (`python main.py`), but it's no
longer a separately-branded product — window title, tray tooltip, and About dialog
all say "ESO Helper" now, not "ESO Build Manager".

## What this is (and isn't)

This is a **desktop companion app**, full stop. The entire point is a second-monitor
view of your character/loadout/daily data while ESO runs fullscreen on the primary
monitor — things ESO's own UI can't comfortably show at once (all characters, all
accounts, at a glance) live here instead. Any new dashboard, checklist, tab, or
browsing feature belongs in **this desktop app** (`main.py` / `eso_viewer/`),
not in-game.

`WornGear/WornGear.lua` is a **data collector only**. Its entire job is reading the
ESO Lua API on login/events and writing that into SavedVariables, which this app
pulls directly off disk or via `scp` (see "Sync" below — no server in between). It
does not have — and should not grow — its own rich UI: no in-game windows, toolbars,
checklists, or dashboards. If a feature needs a UI (browsing, filtering, a
dashboard), it goes in the desktop app. `WornGearCompanion/` (an in-game addon UI
built 2026-07-15 on a misread of "imagine this is an app" as "build an in-game app")
is the counter-example of this rule — its code is kept around as reference but it's
unlinked from the live AddOns folder and not meant to be developed further.

**One deliberate exception: time-sensitive alerts.** A "your research just finished"
notification only matters if it's seen *at the moment*, and while playing, your
attention is on the game screen, not the second monitor the desktop app lives on —
a tray balloon on a monitor you're not looking at doesn't work for this. So
cross-character research alerts fire from WornGear.lua itself (a
plain chat line + `ZO_Alert`), not the desktop app's tray icon. This isn't a rich UI
(no window, no XML, just two native API calls), so it doesn't violate the rule
above — it's the one thing that has to happen in-game because that's where the
person actually is when it matters.

## Tech Stack

- **Python 3.11+**
- **PySide6** — UI framework (Qt6, KDE Plasma compatible)
- **dataclasses** — data models (parsed from `WornGear.lua`, held in memory only)

No external dependencies beyond PySide6. No database.

## Running

```bash
pip install PySide6
python main.py
```

## Project Layout

```
viewer/
├── main.py                          # The whole app: QMainWindow with the character/stats/activities
│                                     #   tabs plus the read-only Builds (loadout) tab
├── model.py                         # Character/SkillLine/Constellation/... dataclasses, WornGear parsing
├── parser.py                        # Generic ESO Lua SavedVariables tokenizer/parser (stdlib only)
├── requirements.txt
├── eso_viewer/
│   ├── app.py                       # QApplication setup — setApplicationName("ESO Helper Viewer")
│   │                                 # (deliberately distinct from the outer composed window's own
│   │                                 # "ESO Helper" -- see "Storage" below), one-time settings
│   │                                 # migration from the pre-rename "ESO Build Manager" identity
│   ├── constants.py                 # ESO_CLASSES, ROLES, GEAR_SLOTS, colors, etc.
│   ├── data_loader.py               # JSON data loaders (skills, sets, CP stars)
│   ├── dailies.py                   # Daily-task defs + untracked-set persistence, shared between
│   │                                 # main.py's Dailies tab and settings_dialog.py's untrack management
│   ├── gold_history.py              # Per-account gold snapshot log (~/.local/share/eso-helper/)
│   ├── icon_cache.py                # Skill-icon disk+memory cache (~/.local/share/eso-helper/icons)
│   ├── models/
│   │   ├── build.py                 # Build dataclass  ─┐ used only as render-input shapes for
│   │   ├── skill.py                 # Skill dataclass   ├─ BuildSheetWidget (see "Builds tab" below);
│   │   └── gear.py                  # GearPiece dataclass┘ no DB, most fields now vestigial
│   └── ui/
│       ├── build_sheet.py           # BuildSheetWidget — read-only loadout display (skills/CP/gear/stats/notes)
│       └── settings_dialog.py       # Save-file-source (remote/this_pc) + Untracked Dailies settings
└── data/
    ├── skills.json                  # Skill lines: category/line/base+morphs structure
    ├── skill_ids.json               # UESP ability IDs: {line: {name: ability_id}}
    ├── sets.json                    # [{id, name}] — 709 sets for autocomplete
    ├── set_details.json             # {name: {id, type, source, bonuses[]}} — tooltip data
    └── cp_skill_ids.json            # {discipline: {star_name: ability_id}} — 118 CP stars
```

## UI Flow

```
MainWindow (QMainWindow)  — main.py
└── QTabWidget
    ├── 🧙 Character  → Overview / Bio / Stats / Skills / Guilds / Champion   (main.py _tab_*)
    ├── 📅 Activities → Dailies / Crafting / Research
    ├── 📦 Storage    → Inventory / Bank
    ├── 🏆 Collection → Achievements / Sets
    └── 📜 Builds     → BuildsTab (main.py) — read-only loadout viewer
        ├── character picker + live-stats strip
        ├── ArmoryBuildListPanel (left, 275px)  — QTreeWidget of the character's
        │     in-game Armory loadouts, straight from the WornGear addon
        └── BuildSheetWidget (right)            — read-only: name/badges, skills
              (two bars), Champion Points, gear, stats, notes. No buttons.
```

Every tab is read-only and populated from one parse of `WornGear.lua` (see "Sync").
There is no build authoring anywhere: no saved builds, no editor, no import/export
(the SQLite build subsystem was removed 2026-09-11 — see "Builds tab" below).

## Data Model

`models/build.py`, `skill.py`, `gear.py` are plain dataclasses used **only** as the
input shape `BuildSheetWidget` renders. `BuildsTab._armory_to_objects()` (main.py)
fills them from a WornGear loadout dict. There is no database and no schema; most
`Build` fields (`role`, `content`, `source`, `mundus_stone`, `created_at`, …) are
never populated from armory data and just render as empty. The fields that do get
used: `Build.name` (loadout name), `eso_class`, `subclass_1/2`, `attribute_*`,
`cp_slots` (JSON list of 12 star names), `class_masteries`, `gear_pages` (JSON list,
always `["Main"]` here); `Skill.bar`/`slot`/`name`; `GearPiece.slot`/`set_name`/
`weight`/`trait`/`enchant`/`quality`/`page`.

## Constants (`constants.py`)

```python
ESO_CLASSES   = ["Arcanist", "Dragonknight", "Necromancer", "Nightblade",
                  "Sorcerer", "Templar", "Warden"]
ROLES         = ["Healer", "Hybrid", "MagDPS", "StamDPS", "Tank"]
CONTENT_TYPES = ["Dungeon", "Overland", "PvP", "Solo", "Trial"]
GEAR_SLOTS    = ["Head", "Shoulder", "Chest", "Hands", "Waist", "Legs", "Feet",
                 "Neck", "Ring 1", "Ring 2",
                 "Main Hand", "Off Hand", "Backup Main", "Backup Off"]
ARMOR_WEIGHTS   = ["Heavy", "Light", "Medium"]
GEAR_TRAITS     = [...]   # 20 armor traits
JEWELRY_TRAITS  = [...]   # 9 jewelry traits
WEAPON_TRAITS   = [...]   # 9 weapon traits
QUALITY_TIERS   = ["Normal", "Fine", "Superior", "Epic", "Legendary"]
MUNDUS_STONES   = ["The Apprentice", ..., "The Warrior"]  # 13 stones
GAME_PATCHES    = ["U35", ..., "U50"]
ROLE_COLORS     = {role: hex_color}
CLASS_COLORS    = {class: hex_color}
QUALITY_COLORS  = {quality: hex_color}
```

## Data Files

### `skills.json`
Structured skill data from UESP. Format:
```json
[{"category": "Dragonknight", "line": "Ardent Flame", "skills": [
    {"base": "Lava Whip", "morphs": ["Flame Lash", "Molten Whip"]}
]}]
```
Used by `load_skill_names()` to build autocomplete lists. Also has `"category": "Class Mastery"` entries for U50+ class mastery passives.

### `skill_ids.json`
UESP ability IDs from the skillTree record. Format: `{line: {skill_name: ability_id}}`.
997 named skills across 71 lines including "Scribing" (12 grimoire skills — the
in-game Scribing spell-tome item type, unrelated to the addon_manager sub-app that
also used to be named "Grimoire").
Max-rank abilityId per named skill (morphs have rank > maxRank).

### `sets.json`
`[{"id": int, "name": str}]` — 709 sets for gear autocomplete.

### `set_details.json`
`{set_name: {"id": int, "type": str, "source": str, "bonuses": [str, ...]}}` — 711 sets.
Used for the tooltip on gear set cells (shows type, source, and per-piece bonus text).

### `cp_skill_ids.json`
`{"Craft": {star_name: ability_id}, "Warfare": {...}, "Fitness": {...}}`.
118 total CP v2 stars from UESP cp2Skills record.
Discipline mapping: id=1→Warfare, id=2→Fitness, id=3→Craft.

## Key Implementation Notes

### Builds tab (`main.py` `BuildsTab` / `ArmoryBuildListPanel`)
Read-only. Shows each character's in-game Armory loadouts (skills / CP / gear)
straight from the WornGear addon — pick a character, pick a loadout, see what it's
running via `BuildSheetWidget`. Deliberately has **no** build-authoring: no saved
builds, no editor, no import/export/"Save as Build".

**2026-09-11 strip.** This tab used to also list SQLite-backed saved builds and open
a full `BuildEditorDialog` (name/role/class/subclass/source form + Build/Stats/
Passives/Notes tabs, 400ms debounced autosave, drag-drop skill/CP widgets, multi-page
gear tables). All of that was cut. Deleted outright — nothing imported them any more:
`ui/build_list.py`, `ui/build_editor.py`, `ui/build_editor_dialog.py`, `ui/cp_widget.py`,
`ui/class_mastery_widget.py`, `ui/loadout_pages_widget.py`, `ui/gear_table_widget.py`,
`ui/skill_bar_widget.py`, `ui/stats_widget.py`, `exporter.py`,
`storage/database.py`, `tests/test_database.py`. `app.py`'s `create_app()` no longer
calls `init_db()`, so `~/.local/share/eso-helper/builds.db` is no longer created or
touched (an old one from before the rename may still sit at
`~/.local/share/eso-build-manager/builds.db` — harmless, safe to delete). All
recoverable from git history if ever wanted back. Kept: `models/` (as render
shapes), `build_sheet.py`, the `data/*.json` files, `set_details.json` tooltips
(`build_sheet.py` reads them directly now).

Same session, same directory was also renamed off "ESO Build Manager" entirely
(`eso-build-manager/` → `viewer/`, `eso_build_manager` package → `eso_viewer`) — see
"Storage" below for how that avoided silently losing saved settings.

### Set tooltips
`build_sheet.py` reads `set_details.json` and shows an HTML tooltip (type, source,
per-piece bonuses) on each gear set cell.

### Color palette rules
- Readable text: `palette(windowText)`
- Secondary/muted text: `palette(placeholderText)`
- Decorative borders only: `palette(mid)` (too dark for text in KDE dark themes)
- Avoid `palette(mid)` for any text — invisible in KDE dark theme

## Storage

No database. The only persisted state is `QSettings` — window geometry, `sync/mode`,
and `dailies/untracked` (see `eso_viewer/dailies.py`), saved via bare `QSettings()`
in both `main.py` and `settings_dialog.py` — resolves to
`~/.config/CubicSerenity/ESO Helper Viewer.conf`. `main.py` used to construct
`self._settings` with explicit `QSettings('CubicSerenity', 'ESOBuildManager')` (no
space) for geometry only, which silently wrote to a *different* file than everything
else and cost real debugging time — fixed to bare `QSettings()` for consistency.

**2026-09-11 rename** (off "ESO Build Manager", `~/.config/CubicSerenity/ESO Build
Manager.conf`): deliberately did **not** rename to plain "ESO Helper" — the outer
composed window (`../main.py`'s `ESOHelperWindow`) already uses
`QSettings("CubicSerenity", "ESO Helper")` explicitly for its own geometry, and
giving this window's bare `QSettings()` the same app name would resolve to that same
file, so both windows' geometry would collide on the same `"geometry"` key — the
exact class of bug the paragraph above is about, just from the opposite direction.
Used "ESO Helper Viewer" instead. `app.py`'s `_migrate_settings()` copies every key
from the old identity into the new one on first run under the new name (checked via
`QSettings().allKeys()` being empty), so geometry/sync-mode/untracked-dailies survive
the rename instead of resetting. `ESOBuildManager.conf` (no space, from the
even-earlier bug) and `ESO Build Manager.conf` may both still exist on already-
deployed machines as orphans; harmless, safe to ignore or delete once migrated.

Two other files got the same pre-rename → new-path treatment, each with the same
"read new, fall back to old, only ever write new" pattern, never destructive:
- `gold_history.py`: `~/.local/share/eso-build-manager/gold_history.json` →
  `~/.local/share/eso-helper/gold_history.json`.
- `icon_cache.py`: `~/.local/share/eso-build-manager/icons/` →
  `~/.local/share/eso-helper/icons/` (a pure cache — losing it would just mean a
  one-time re-download from UESP, but the fallback avoids even that).

## Sync

This app runs on one computer, alongside (or reachable via SSH from) the one computer that
actually plays ESO — no dedicated server, no cross-machine merge, no mobile app. The dedicated
FastAPI sync server (`server/`), its client (`eso_viewer/sync/server.py`), the Android
app (`mobile/`), the Steam Deck's `scripts/addon_sync.py`, and the old Nextcloud/WebDAV backend
(`sync/nextcloud.py`, itself already-dead code left over from an even earlier migration) were
**all retired 2026-07-15** as unneeded complexity once the "many producers merging through a
central server" model stopped being the actual use case. All of that is gone from the repo; see
git history if any of it is ever needed for reference. If you manually deployed the old FastAPI
service on a remote box, it's still running there and needs stopping by hand (this repo change
doesn't reach it). The Steam Deck producer specifically is deferred, not forgotten — worth
revisiting once there's an actual second-machine need again, probably as another host entry
rather than its own bespoke mechanism.

### How data gets from the game to this app

`_pull_save_file()` (main.py) pulls `WornGear.lua`'s SavedVariables file onto local disk, one of
two ways depending on `sync/mode` (Settings → Save file source):

- **"This PC"** — game and desktop app on the same machine: a plain local file copy.
- **"Remote Host (SSH)"** — game runs on a different machine: `scp <host>:<remote_dir>/WornGear.lua`.
  Any SSH-reachable host works, keyed purely off what's in the config file below — nothing in
  source assumes a specific machine.

Either way, the host/path themselves are **not in source** — they're read from
`~/.config/eso-helper/sync.json` (`{"host": "...", "remote_dir": "/path/to/.../
SavedVariables"}`), a private, non-versioned file outside the repo. This is deliberate: an SSH
hostname and a local filesystem path are exactly the kind of thing that shouldn't end up baked
into source that might go public someday — `_load_sync_config()` just returns `{}` (and
`_pull_save_file()` silently no-ops) if that file doesn't exist yet on a fresh checkout.
`_load_sync_config()` also falls back to reading the pre-rename path
(`~/.config/eso-build-manager/sync.json`) if the new one doesn't exist, so an
already-configured machine keeps working without hand-editing anything — but it
never writes to the old path, so move the file over yourself whenever convenient.

Once `WornGear.lua` is local, `MainWindow._reload()` parses it exactly once
(`_load_local_data()`) and derives characters/achievements/set collections/worn-gear from that
single parse via `model.extract_from_wg()` / `extract_achievements()` / `extract_set_collections()`
/ `extract_worn_gear()` — no server round-trip, no `*_from_dict()` JSON reconstruction (those
were removed along with the server; they only ever existed to rebuild a dataclass from a
`dataclasses.asdict()`-shaped server response). `extract_worn_gear()` returns
`{char_name: {loadout_name: {slot: {...}, "skills": {...}, "cp": {...}, "attributes": {...}}}}`
— the exact shape `BuildsTab` renders in the Builds tab.

Reload happens on the 60s auto-refresh timer, on demand (Ctrl+R), after Settings closes, and
(in "This PC" mode) shortly after `QFileSystemWatcher` notices the game actually wrote new data
(`_init_save_watcher()`/`_on_save_file_changed()`/`_on_save_dir_changed()`, debounced via
`SAVE_CHANGE_DEBOUNCE_MS`).

## Notes

### Crit chance was stored wrong by the addon (fixed)
`WornGear.lua` used to store `GetPlayerStat(STAT_SPELL_CRITICAL, ...)` — the raw
critical *rating* (thousands) — directly as `critChance`, so the UI showed things
like "9885.0%". Fixed at source by wrapping it in ESOUI's `GetCriticalStrikeChance
(ratingValue)`. `model.py`'s parsing was always correct (the other data source,
`LeoAltholic`, already stored a proper percentage); only the addon needed the fix.
Needs an in-game addon reload to take effect for new data.

### Gear card quality coloring
`_GearCard` in `build_sheet.py` deliberately does **not** color Epic-quality items
(`_QUALITY_COLOR` has no Epic entry) — nearly all endgame gear is Epic, so coloring
all of it the same purple was noise. Legendary still gets its gold highlight.
