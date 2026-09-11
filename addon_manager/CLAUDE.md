# ESO Helper Addons — dev notes (formerly "Grimoire")

This was a standalone project called Grimoire; `khedron83/Grimoire` is being deleted
and it's now vendored as plain files at `addon_manager/` inside `khedron83/ESO-Helper`
(2026-09-11 rename — see the top-level CLAUDE.md). Consequences:

- No more standalone distribution: the Flatpak manifest/`.desktop`/AppStream metainfo,
  its own PyInstaller spec, and its own GitHub Actions release workflow were all
  deleted (they built/published a separately-branded app that no longer exists).
- The in-app self-update checker (`workers.py`'s old `UpdateCheckWorker`, the update
  banner in `main_window.py`) was removed along with it — it polled
  `api.github.com/repos/khedron83/Grimoire/releases/latest`, which 404s once that
  repo is gone, and there's no replacement release channel for this vendored copy.
- Renamed identifiers/paths, each kept backward-compatible with data from before the
  rename (never destructive): config dir `~/.config/grimoire/` → `~/.config/eso-helper-addons/`
  (one-time migration on first load, `src/core/config.py`); per-addon sidecar
  `.grimoire.json` → `.eso-helper-addon.json` (`src/core/addon.py`, reads the old name
  as a fallback); backup zip prefix `grimoire_` → `eso-helper-addons_`
  (`src/core/backup.py`'s `list_backups()` still matches both prefixes); default
  backup folder `~/grimoire-backups` → `~/eso-helper-addon-backups`
  (`backup_tab.py::_backup_dir()` keeps using the old default if it's the one that
  actually has backups in it).
- Window title / tray tooltip / About dialog / `setApplicationName()` all say
  "ESO Helper Addons" now instead of "Grimoire". `setApplicationName()` only matters
  when running standalone (`run.py`) — embedded in the composed app, this class's own
  app-identity call never executes (see eso-helper's own CLAUDE.md).

## Version bumps

When bumping the version, update **both** of these:

1. `pyproject.toml` — `version = "x.y.z"`
2. `src/ui/workers.py` — `APP_VERSION = "x.y.z"`

The About dialog in `src/ui/main_window.py` reads `APP_VERSION` automatically. There's
no release/tag/CI flow to push it to anymore — see the note above.

## UI/UX review — 2026-07-09

Offscreen-rendered review (Fusion style, light palette — judge layout/density/consistency, not
exact colors) of `01_installed_tab.png`, `02_browse_tab_loaded.png`, `03_browse_tab_detail.png`,
`04_backup_tab.png`, `05_settings_dialog.png`. Findings below, most impactful first. Assumption:
single-developer personal tool, so these are scoped as straightforward fixes to existing widgets,
not a rearchitecture.

1. ✅ DONE — **Browse tab never learns what's already installed until an install/removal happens in that
   session** — a real functional bug, not just cosmetic. `main_window.py::_first_run_check()`
   calls `self._installed_tab.refresh()`, which populates the Installed tab asynchronously via
   `ScanWorker` (`installed_tab.py:159-167`), but nothing wires that result into
   `self._browse_tab.set_installed(...)`. The only two call sites for `set_installed` are
   `_on_addons_installed` (fires after a fresh in-app install) and the `addon_removed` lambda
   (`main_window.py:100-104`) — neither fires on ordinary startup. Net effect, confirmed by the
   screenshots: Installed tab (`01_installed_tab.png`) shows Combat Metrics has an update
   (1.7.7 → 1.7.8, orange row) and LoreBooks is installed at v105, but Browse tab
   (`02_browse_tab_loaded.png` row 7, `03_browse_tab_detail.png`) shows Combat Metrics in plain
   black text with no "↑" update marker, and selecting LoreBooks shows a plain "Install" button
   (`browse_tab.py:400-410`) instead of "Installed" or "Update (105 → 107)". A user browsing the
   catalogue on a fresh launch has no way to tell what they already have. Fix: have
   `InstalledTab` emit a signal (or reuse `set_addons`/`set_remote_info` completion) that
   `main_window.py` forwards into `browse_tab.set_installed(self._installed_tab.get_installed_map())`,
   and re-run it once `_on_addon_list_loaded` fires too (install-status coloring depends on both
   the local scan and the remote list, which load independently).
   Added `InstalledTab.installed_loaded` (emitted from `set_addons()` and `_on_scan_error()`),
   wired in `main_window.py` to a new `_sync_installed_to_browse()` helper called from that
   signal, from `_on_addon_list_loaded()`, and from `addon_removed` — replacing the three
   separate one-off call sites. As a side effect this also fixed a latent race in the old
   `_on_addons_installed()`, which called `set_installed()` synchronously right after
   `refresh()` even though `refresh()` only *starts* the async scan — it now waits for the
   real `installed_loaded` signal instead.

2. ✅ DONE — **Error states are visually identical to success/info messages** — every tab wires
   `status_message` straight into the same plain `QStatusBar.showMessage()`
   (`main_window.py:97-99`), e.g. `installed_tab.py:166`
   `self._worker.error.connect(lambda e: self.status_message.emit(f"Scan error: {e}"))`. All
   four main-window screenshots show the identical black-on-gray
   `Scan error: [Errno 2] No such file or directory: '/home/kane/Desktop/AddOns'` bar — same
   weight as a routine "Auto-detected AddOns at …" message, even though this particular error
   means the entire Installed tab is non-functional (misconfigured/missing AddOns directory).
   Add severity-based styling (red text/icon for errors) and consider a persistent banner
   (the app already has one pattern for this — the update banner in `main_window.py:50-69`)
   rather than a transient status-bar message that scrolls away and is easy to miss.
   Added `main_window._on_status_message()`, now the single connection point for all three
   tabs' `status_message` signals, which colors the status bar red
   (`style.STATUS_ERROR_STYLE`) when `style.is_error_message()` matches ("error"/"failed" in
   the text). Combined with #3's inline error page for the specific Installed-tab case that
   motivated this finding, rather than only relying on the status bar.

3. ✅ DONE — **A failed scan leaves stale table contents with no "this may be wrong" cue** —
   `installed_tab.py::refresh()`'s error path only emits a status message; `set_addons` is never
   called, so whatever was already in `self._addons`/the table (from a prior successful scan, or
   the synthetic seed data used for this review) stays displayed looking perfectly normal. A user
   would have no visual reason to doubt a fully populated, ordinarily-styled table even though the
   configured directory doesn't currently exist. Combine with #2's fix, or explicitly clear the
   table and show an inline "AddOns directory not found" state when a scan fails.
   `installed_tab.py` now has a `QStackedLayout` (`_table_stack`) between the table, an
   `_empty_label` ("No addons found…"), and a new `_error_label`. `refresh()`'s worker now
   connects to `_on_scan_error()`, which clears `self._addons`/the table and switches to the
   red-styled error page showing the actual exception text, instead of leaving stale rows
   looking normal.

4. ✅ DONE — **Zebra striping is enabled in code but invisible in practice** —
   `setAlternatingRowColors(True)` is actually set on all three tables
   (`installed_tab.py:92`, `browse_tab.py:150`, `backup_tab.py:51`), contrary to what you'd guess
   from the screenshots: Fusion's default light-palette `alternate-base` is nearly indistinguishable
   from plain white `base`, so `02_browse_tab_loaded.png`'s ~23 visible rows of dense 6-column data
   read as a flat, hard-to-track grid despite the flag being on. This will only get worse across
   the full 3088-row catalogue. Needs an explicit stylesheet/QPalette override for `alternate-base`
   (a few percent darker gray) rather than relying on the Fusion default — same class of fix
   already logged for the sibling project's `_make_view()` zebra-striping finding.
   New `src/ui/style.py` module with `TABLE_STYLE = "QTableWidget { alternate-background-color:
   rgba(128,128,128,0.08); }"`, applied to all three tables via `setStyleSheet()`.

5. **No visual identity anywhere in the app** — worth calling out as its own root-cause finding
   rather than only patching symptoms below. Every widget across `installed_tab.py`,
   `browse_tab.py`, `backup_tab.py`, `settings_dialog.py`, and `main_window.py` is stock Fusion
   with zero custom QSS: no card/section styling, no consistent status-color language (the amber
   "Update available" text is the only accent color used anywhere), no empty-state treatment (see
   #8). Contrast with the sibling `viewer` project's `build_sheet.py`, which uses
   colored section labels, `CLASS_COLORS`/`ROLE_COLORS` badges, and card-style `QFrame`s
   throughout. Fine for a v1, but several items below (undifferentiated status messages,
   dead-feeling empty states, a generic settings dialog) are all downstream of this one gap and
   would benefit from one shared style pass instead of one-off fixes.
   Not actioned as a single change — addressed piecemeal through the other findings below
   (#2/#3's status/error styling, #4/#14's `style.py`, #8's empty states, #12's inline
   validation), which is exactly the "one shared style pass instead of one-off fixes" this
   finding asked for. A dedicated visual-identity pass (colored section labels, card-style
   `QFrame`s matching `viewer`) is still open if wanted later.

6. ✅ DONE — **Browse detail panel's metadata line misuses `placeholderText` for real content** —
   `browse_tab.py:167`: `self._detail_meta.setStyleSheet("color: palette(placeholderText); font-size: 11px;")`.
   `placeholderText` is a deliberately low-contrast color meant for empty-field hint text, not for
   the author/version/category/downloads/updated line a user reads on every single row selection
   (`03_browse_tab_detail.png`). Combined with the 11px size this is the hardest-to-read text in
   the app. Use `palette(windowText)` (full contrast) — per the sibling project's own documented
   rule, avoid `palette(mid)`-class colors for actual text, not just in dark themes.
   Switched to `palette(windowText)`.

7. ✅ DONE — **Browse tab's Title column is too narrow for its content, with no tooltip fallback** — of the
   6 columns, only Title (`browse_tab.py:140`) is `Stretch`; the other five
   (Version/Author/Category/Downloads/Updated, lines 141-145) are all `ResizeToContents`, and the
   initial splitter split (`splitter.setSizes([600, 320])`, line 179) hands roughly a third of the
   window to a detail panel that's empty until a row is clicked. Net effect in
   `02_browse_tab_loaded.png`: Title ends up ~200px wide, so entries like "Srendarr - Aura, Buff &
   Debu…" (row 19) get ellipsis-truncated with no way to recover the full name — `_fill_row()`
   (`browse_tab.py:301-315`) never calls `setToolTip()` on the title item. Fix both: bias the
   initial splitter split toward the table, and add a hover tooltip with the untruncated name.
   Splitter split changed to `[760, 260]` (was `[600, 320]`), and `_fill_row()` now calls
   `title_item.setToolTip(info.name)`.

8. ✅ DONE — **No empty-state treatment anywhere** — `04_backup_tab.png` (zero backups) shows a bare table
   with just column headers and a large dead white area below the action row; the Browse detail
   panel before any selection (`02_browse_tab_loaded.png`) is similarly blank apart from a grayed
   Install button. Neither explains what to do next. Same category as the sibling project's
   already-logged `class_mastery_widget.py` empty state / `BuildsTab` "Select a build…" label —
   apply the same light card/banner-with-icon treatment here ("No backups yet — Create Backup to
   make your first one" / "Select an addon to see its details").
   Both added via `QStackedLayout`: `backup_tab.py`'s `_empty_label` swaps in for the table
   when `list_backups()` returns nothing, and `browse_tab.py`'s `_detail_empty` ("Select an
   addon to see its details.") is the default page of `_detail_stack`, swapped out for
   `_detail_content` in `_on_row_changed()` and back in `_clear_detail()`.

9. ✅ DONE — **Row-number column on every table adds no value** — none of `installed_tab.py`,
   `browse_tab.py`, or `backup_tab.py` call `verticalHeader().setVisible(False)`, so all three
   tables show a raw incrementing index (visible as "1"–"5" in `01_installed_tab.png`, "1"–"23"
   in `02_browse_tab_loaded.png`) that isn't used for selection, drag-reorder, or anything else in
   the app. Reads as an unfinished/debug leftover and costs ~20px of width per table for nothing —
   hide it.
   `verticalHeader().setVisible(False)` added to all three tables.

10. ✅ DONE — **Backup tab's "Include SavedVariables" checkbox silently reverts on every tab visit** —
    `backup_tab.py::refresh()` (lines 84-86) unconditionally does
    `self._chk_sv.setChecked(self.config.backup_include_saved_vars)`, and `main_window.py`'s
    `_on_tab_changed` (lines 124-126) calls this `refresh()` every single time the Backup tab
    becomes active — not just once on first load. `_create_backup()` (`backup_tab.py:121-140`)
    reads the checkbox's current state but never writes it back to `config`. A user who checks the
    box, switches to another tab, and switches back will find it silently unchecked again with no
    indication their choice was discarded. Either persist the in-tab toggle back to config on
    change, or stop re-syncing from config after the first load.
    Took the second option: added `self._sv_initialized` flag, so `refresh()` only seeds the
    checkbox from `config.backup_include_saved_vars` once. The checkbox is now purely a
    per-session, per-backup choice (see #13), never overwritten by later tab visits.

11. ✅ DONE — **Backup table has no sorting, inconsistent with the other two tabs** —
    `installed_tab.py:93` and `browse_tab.py:147` both call `setSortingEnabled(True)`;
    `backup_tab.py`'s table (`backup_tab.py:42-52`) never does. Clicking the Filename/Size/Date
    headers does nothing — currently unnoticeable since `04_backup_tab.png` is empty, but an
    undiscoverable dead end once a user accumulates more than a screenful of backups.
    `backup_tab.py` now has `_SizeItem`/`_DateItem` sort-key classes (mirroring `browse_tab.py`'s
    `_NumericItem`/`_DateItem`) so Size/Date sort numerically instead of as text, plus
    `setSortingEnabled(True)` with the populate loop wrapped in disable/re-enable to avoid
    resorting mid-insert.

12. ✅ DONE — **Settings dialog gives no feedback on an invalid AddOns path** — `settings_dialog.py:30`'s
    AddOns-directory `QLineEdit` renders identically whether or not the path exists, even though
    this exact field (`/home/kane/Desktop/AddOns`, `05_settings_dialog.png`) is the direct cause
    of the scan error shown in every other screenshot. Add inline validation (red border / small
    warning label) when the entered path doesn't exist on disk, so the user doesn't have to
    correlate a status-bar message on a different tab back to this field.
    Added `_validate_addons_dir()` (wired to `textChanged` and run once at dialog open): red
    border on the field plus a "This path doesn't exist." label when the entered path is
    non-empty and not a directory.

13. ✅ DONE — **Two near-duplicate "include SavedVariables" toggles with no visual link, easy to conflate**
    — `settings_dialog.py:50` ("Include SavedVariables in backups", the persistent default) and
    `backup_tab.py:34` ("Include SavedVariables", the per-backup override) use almost identical
    label text for different scopes, which combined with #10's revert bug makes the relationship
    confusing. Differentiate the wording ("...by default" vs. "...for this backup only").
    Reworded to "Include SavedVariables in backups by default" (Settings) and "Include
    SavedVariables for this backup" (Backup tab).

14. ✅ DONE — **Two different colors used for the same "update available" concept** — `browse_tab.py:322`
    marks an installed-but-outdated addon with `item.setForeground(Qt.yellow)` (pure yellow on
    white — low contrast, and can't be visually confirmed in these screenshots since #1 means this
    code path never actually fired during capture, but it's confirmed by reading the source);
    `installed_tab.py:20` uses a separate, deliberately muted `QColor(200, 140, 0)` amber for the
    identical concept in the Installed tab. Share one constant, contrast-checked against a white
    background, between both tabs.
    Both now use `style.UPDATE_COLOR` (`QColor(200, 140, 0)`, the pre-existing muted amber) —
    `browse_tab.py`'s `Qt.yellow` is gone.

15. ✅ DONE — **Backup directory's default location isn't surfaced anywhere in the UI** —
    `backup_tab.py`'s `_backup_dir()` silently falls back to a default when `config.backup_dir` is
    empty, but `settings_dialog.py`'s placeholder text just said "Where to save backups…" with
    no mention of that default. A user who never touches this field has no way to know where their
    backups are actually landing short of clicking "Open Backup Folder". Mention the default path
    in the placeholder or as inline hint text.
    `settings_dialog.py`'s backup-dir placeholder now reads `f"Default: {Path.home() /
    'eso-helper-addon-backups'}"` (was `'grimoire-backups'` before the 2026-09-11 rename —
    `_backup_dir()` still prefers the old default path if that's the one with backups in it,
    see the rename note at the top of this file).

16. ~~Not actioned — Update banner not visually verifiable this pass~~ MOOT — the whole
    self-update-checker (`UpdateCheckWorker`, the banner, `_check_for_update()`) was removed
    2026-09-11 along with the Grimoire→ESO-Helper-Addons rename (see the note at the top of this
    file) — it checked `khedron83/Grimoire`'s releases, which no longer exist.
