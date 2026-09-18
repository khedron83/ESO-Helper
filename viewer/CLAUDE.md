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
pulls directly off disk, or reads secondhand from the sync server (see "Sync" below).
It
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
    ├── 📅 Activities → Dailies / Crafting
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

This app runs on whichever machine needs it — the one that plays ESO (zeus; "This PC" mode)
or any other machine that just wants to look at the data (client-only, "Sync Server" mode; see
the startup dialog below). The dedicated FastAPI sync server, its client
(`eso_viewer/sync/server.py`), the Android app (`mobile/`), the Steam Deck's
`scripts/addon_sync.py`, and the old Nextcloud/WebDAV backend (`sync/nextcloud.py`, itself
already-dead code left over from an even earlier migration) were **all retired 2026-07-15**
as unneeded complexity once the "many producers merging through a central server" model
stopped being the actual use case. The manually-deployed FastAPI service on `server` kept
running the whole time — unstopped, and (2026-09-17) confirmed still serving real
character/achievement/set-collection data pushed before the retirement.

**2026-09-17: the desktop client side came back**, scoped deliberately narrower than what was
retired — `eso_viewer/sync/server.py` is a read-only client for that same still-running
FastAPI server. The server's own source is now also checked into this project (not this repo)
at `../../eso-sync-server/` (`../../` from here = `ESO/eso-sync-server/`), cloned straight off
`server` for reference/redeploy — it is not run from there, the live one on `server`'s Docker
container (`eso-sync`) is still the one actually serving requests, and this app's client talks
to that over the network, never to the local copy. Auth is off (`SYNC_TOKEN` empty in that
box's `.env`) since this is a private LAN and it doesn't need to be secure.

"Sync Server" is a second "Save file source" (`settings_dialog.py`) alongside "This PC":
it bypasses `ESOHelper.lua` entirely and instead GETs `/characters`, `/achievements`,
`/set-collections`, reconstructed via `model.py`'s `character_from_dict`/
`achievements_from_dict`/`set_collections_from_dict` (the inverse of `extract_from_wg()`/etc.,
tolerant of schema drift — unknown keys like a stale `research` field from before the
2026-09-12 dailies rework are just dropped). `server_url`/`server_token` live in
`~/.config/eso-helper/sync.json` (same "not in source" reasoning as `remote_dir`) —
`server_token` can just be left unset now that the server has no auth.

A first-run-only startup dialog (`eso_viewer/ui/startup_dialog.py`, shown from
`MainWindow.__init__` before the first `_reload()`, gated on `not self._settings.contains(
'sync/mode')`) offers the same This PC / Sync Server choice as a quick two-button picker —
pick "Read Local Data" on zeus, "Sync Server (client only)" everywhere else. **2026-09-17:
changed from every-launch to first-run-only** — popping this up on top of whatever's on
screen on every single launch was disruptive on zeus specifically, where the app can get
restarted while the game is running full-screen; every later launch now just reuses
whatever `sync/mode` was last saved (from this dialog or from Settings) with no prompt.
Change modes later via Settings, same as before.

**2026-09-17: pushing came back too**, for zeus's actual need — it has to both read its own
local save data (it's the machine running the game) *and* keep the sync server fresh so other
machines' "Sync Server" clients aren't stuck on stale data. `settings_dialog.py`'s Sync group
has a third control, "Also push this PC's data to the Sync Server" (a checkbox, only enabled in
This PC mode — `sync/push_enabled` in QSettings), independent of the This PC/Sync Server radio:
the radio picks where *this* window reads its own data from, the checkbox is purely about
whether it also acts as a producer. When it's on, `main.py`'s `_reload()` calls
`eso_viewer.sync.server.push_all()` right after every successful local parse — `dataclasses.
asdict()` on each `Character`/`AccountAchievements`/`AccountSetCollections` and a `PUT` to the
same `/characters/bulk`, `/achievements/bulk`, `/set-collections/bulk` endpoints the
many-producers model originally used (see `../../eso-sync-server/app.py`'s existing
last_updated-staleness-rejection and, for characters, field-level-merge logic — written back
then, untouched now, needed no server-side changes for this). A failed push is caught
(`SyncServerError`), logged, and shown briefly in the status bar, but never blocks or errors out
the local reload that already succeeded — the next reload (60s timer, file watcher, Ctrl+R)
just tries again.

Still out of scope: the Android app / Steam Deck producer / Nextcloud backend are still fully
retired — the push side above is this desktop app pushing its own local reads, not a revival of
those. The Skills tab's `__class_skills__` fallback still needs raw `ESOHelperSV` data the server
never stored, so it still just goes without for any machine reading in Sync Server mode — no
server-side equivalent to fall back to.

**2026-09-17 (later same day): the Builds tab's Armory panel came back too**, once it was noticed
(user report: "character builds are not showing up") that it was going without in Sync Server
mode. Rather than adding a dedicated server table for this, `Character` itself grew a
`gear_loadouts: dict[str, dict]` field (`model.py`) carrying the same raw
`{loadout_name: {slot: {name, setName, link}}}` shape `extract_worn_gear()` already produced per
character — set in `_parse_wg_char()` from `char_data`'s non-`__char__`/non-`dailyTracking` sibling
keys, i.e. exactly what used to feed a separate `_parse_wg_loadout()` conversion (deleted; it built
a since-removed `exporter.export_build_dict()`-shaped dict that had no remaining consumer after the
2026-09-11 strip above). Because `gear_loadouts` lives on `Character`, it rides along for free
through the existing `push_all()`/`character_from_dict()` round-trip with no server or client-sync
changes needed — `_reload()`'s Sync Server branch just builds `self._worn_data` from
`{c.name: c.gear_loadouts for c in self._all_chars if c.gear_loadouts}` instead of the old `{}`.
The Steam Deck producer is still deferred, not forgotten — worth revisiting once there's an actual
second-machine need again.

**2026-09-17: NA/EU megaserver tagging**, added alongside the push feature above once it became
clear `account` alone (the `@handle`) isn't a unique key for achievements/set collections: ESO has
two independent megaservers, and the same `@handle` has fully separate achievement points and set
collection progress on each one — pushing both under `account` alone would let an NA push and an
EU push for the same handle clobber each other on the sync server.

The first attempt at this inferred the megaserver from the ESO client's own install-folder naming
convention (`.../live/...` = NA, `.../liveeu/...` = EU) in `main.py`'s `_detect_megaserver()` —
**wrong, corrected same day**: a Steam install only ever has one `live` folder, shared by both
megaservers (there's no `liveeu` at all), so a single local save file can contain both NA and EU
characters and the path-based guess collapsed them all to the same value. `_detect_megaserver()`
was removed. The real fix is in the addon: `ESOHelper.lua` now calls `GetWorldName()` itself
(`GetMegaserver()`, matching `"NA"`/`"EU"` by substring) and writes the result as ground truth —
`bio.server` on every character snapshot, and `ESOHelperAchievementsSV`/`ESOHelperSetCollectionsSV`
restructured from flat `SV[account] = {...}` to nested `SV[account][server] = {...}` (otherwise an
NA session's snapshot and an EU session's snapshot for the same account would still just overwrite
each other one level up, independent of the character-level fix). `model.py`'s `extract_from_wg()`
now reads `Character.server` straight from `bio.server`; `extract_achievements()`/
`extract_set_collections()` iterate the new nested shape, with a fallback that treats a pre-fix
flat entry (detected by an `earnedPoints`/`sets` key one level up from where it now lives) as a
single `server=''` record so old, not-yet-relogged data still loads without crashing. None of this
takes a `server` parameter from the caller anymore — `main.py`'s `_reload()` calls all three
`extract_*` functions with no `server=` arg now. `push_all()` needed no changes either time —
`dataclasses.asdict()` already carries whatever fields exist automatically. The sync server
(`../../eso-sync-server/app.py`) still keys `achievements`/`set_collections` by `(account, server)`
instead of `account` alone (that part of the original design was fine); `characters` stays keyed by
`name` (megaserver-independent — see the module docstring's own record of that decision). A
same-shaped migration (`_migrate_account_only_to_account_server()`, idempotent — checks for the
`server` column via `PRAGMA table_info` and no-ops once it's there) rebuilds each table from its
pre-existing single-key shape on first run against an old DB, defaulting every already-stored row
to `server=''` since there was nothing to tell NA/EU apart before this. Deployed to the live
`server` box's `eso-sync` container the same way any other `app.py` change is (see the container
notes above) — the migration runs automatically the first time the updated container starts, no
manual DB surgery needed.

**Backfill note**: every character/achievement/set-collection snapshot taken before this addon fix
has no `bio.server` (or is still in the old flat `SV[account] = {...}` shape) and reads as
`server=''` until it's refreshed. Since the fix is addon-side, actually populating real `NA`/`EU`
values requires relogging — once per character for `bio.server` (any zone change re-triggers
`EVENT_PLAYER_ACTIVATED`, which calls `Snapshot()`), and at least once per megaserver you play on
for the achievements/set-collections nesting to split apart (whichever one you logged into last
before this fix would otherwise have been the only one recorded, under the old flat shape).

`main.py`'s top-level "Account:" picker got a "Server:" sibling in the same row
(`_server_picker`/`_server_label`, next to `_account_picker`/`_account_label`) — same pattern,
each one independently hidden unless the current character list actually has more than one
account / more than one server (`_update_account_picker()`), and the whole row stays visible if
either does. `_rebuild_tabs()`'s account-filter logic became a small `_filtered()` closure that
now applies both the account and server selections (AND, not OR) before handing
chars/achievements/set_collections off to the tabs.

### How data gets from the game to this app

`_pull_save_file()` (main.py) pulls `WornGear.lua`'s SavedVariables file onto local disk when
`sync/mode` (Settings → Save file source) is **"This PC"** — game and desktop app on the same
machine, a plain local file copy. **2026-09-17: the "Remote Host (SSH)" `scp` mode was removed**
— every machine that needs the game's own save data runs the app directly on that machine now
(zeus), and every other machine reads the sync server instead, so there was no longer a case
that needed pulling `WornGear.lua` over SSH from a second machine.

The path itself is still **not in source** — read from `~/.config/eso-helper/sync.json`
(`{"remote_dir": "/path/to/.../SavedVariables"}`), a private, non-versioned file outside the
repo. This is deliberate: a local filesystem path is exactly the kind of thing that shouldn't
end up baked into source that might go public someday — `_load_sync_config()` just returns `{}`
(and `_pull_save_file()` silently no-ops) if that file doesn't exist yet on a fresh checkout.
`_load_sync_config()` also falls back to reading the pre-rename path
(`~/.config/eso-build-manager/sync.json`) if the new one doesn't exist, so an
already-configured machine keeps working without hand-editing anything — but it
never writes to the old path, so move the file over yourself whenever convenient.

Once `WornGear.lua` is local, `MainWindow._reload()` parses it exactly once
(`_load_local_lua_data()`) and derives characters/achievements/set collections/worn-gear from that
single parse via `model.extract_from_wg()` / `extract_achievements()` / `extract_set_collections()`
/ `extract_worn_gear()` — no server round-trip, no `*_from_dict()` JSON reconstruction in "This PC"
mode (only "Sync Server" mode uses those, to rebuild a dataclass from a
`dataclasses.asdict()`-shaped server response). `extract_worn_gear()` returns
`{char_name: {loadout_name: {slot: {...}, "skills": {...}, "cp": {...}, "attributes": {...}}}}`
— the exact shape `BuildsTab` renders in the Builds tab.

Reload happens on the 60s auto-refresh timer (5min in "Sync Server" mode, see below), on demand
(Ctrl+R), after Settings closes, and (in "This PC" mode) shortly after `QFileSystemWatcher`
notices the game actually wrote new data (`_init_save_watcher()`/`_on_save_file_changed()`/
`_on_save_dir_changed()`, debounced via `SAVE_CHANGE_DEBOUNCE_MS`).

**2026-09-17: reload moved off the GUI thread, and "Sync Server" mode got a push instead of a
poll.** Two related fixes, both from the same user report ("the entire desktop window freezes"
during `requests.get`/`put`, plus a general want for faster cross-machine sync):

- `MainWindow._reload()` no longer does any network/file I/O itself — it just starts a
  `_ReloadWorker` (a `QThread` subclass, `main.py`) and returns immediately. The worker does the
  actual local parse (+ push, "This PC" mode) or `fetch_all()` round-trip ("Sync Server" mode) and
  emits `succeeded(dict)`/`failed(str)`; `MainWindow._on_reload_succeeded`/`_on_reload_failed`
  (connected to those signals, so Qt marshals the call back onto the GUI thread) apply the result.
  `_reload()` is a no-op if a worker from a previous call is still running, rather than starting a
  second one against the same `self._all_chars` etc. — Ctrl+R/the timer/an SSE push/the file
  watcher's debounce can all fire close together.
- "Sync Server" mode also gets `eso_viewer/sync/events.py`'s `SyncEventListener` — another
  `QThread`, holding one long-lived `requests.get(.../events, stream=True)` connection to the sync
  server's new `GET /events` endpoint (`../../eso-sync-server/app.py`: an in-memory
  `queue.Queue`-per-client fan-out, `_broadcast()` called after every successful
  `/characters/bulk`, `/achievements/bulk`, `/set-collections/bulk` commit). Any `data:
  <resource>_updated` line received calls `_reload()` — so a "Sync Server" client picks up
  another machine's push within about a second instead of waiting up to 60s. `_apply_refresh_strategy()`
  (called at startup and again after Settings closes, since mode/`server_url` may have changed)
  owns creating/tearing down the listener and lengthening the auto-refresh timer to 5min in this
  mode — kept running, not removed, as a backstop in case the SSE connection is stuck reconnecting
  (auto-retries every 5s on any `requests.RequestException`, with no bound on how long it stays
  down). Both `QThread`s are stopped (`stop()` + `wait(2000)`) from `MainWindow._stop_background_threads()`,
  wired to both `_tray_quit()` and the whole `QApplication`'s `aboutToQuit` (the composed
  `eso-helper/main.py` app has its own outer tray Quit action that calls `QApplication.quit()`
  directly, never reaching this window's own `_tray_quit()` — `aboutToQuit` is the one path
  guaranteed to run before either thread would otherwise get destroyed while still running).
  Verified live against the real `server` box (2026-09-17): a zeus push and a t480 "Sync Server"
  client's reaction both show up in `docker logs eso-sync` within under a second of each other,
  repeatedly, over one held-open `/events` connection (no reconnect between pushes).

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
