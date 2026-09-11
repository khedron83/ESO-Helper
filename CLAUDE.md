# ESO Helper

One process, one window: `main.py` builds a single `QApplication`, and the addon
manager's `MainWindow` becomes a final tab ("Addons") inside the viewer's own tab
strip via the `extra_tab` constructor hook (`viewer/main.py`
`MainWindow.__init__`/`_rebuild_tabs`) — rather than the two sub-apps sitting
as two top-level tabs one level up. One row of 6 peer tabs (Character /
Activities / Storage / Collection / Builds / Addons) reads more like one app
than a mode switch between two; `ESOHelperWindow`'s central widget is just
`self._viewer_win` directly, no outer `QTabWidget` of its own anymore. Neither
sub-app's own entry point runs (their `if __name__ == '__main__':` blocks /
the addon manager's `main()` are never called) — only their class definitions
get imported, via `sys.path` pointing at both sub-app directories. This was a
deliberate pivot from an earlier launcher-that-spawns-two-processes design —
see git history if that shape is ever wanted back.

`viewer/` and `addon_manager/` began as copies of separate repos (`ESO Build
Manager` and `Grimoire`), but this whole tree (`~/Projects/eso-helper/`) is now
a single git repo → `khedron83/ESO-Helper` (renamed from `ESO-Build-Manager`;
history force-reset 2026-09-11). The old `ESO-Build-Manager` name redirects
here. **2026-09-11**: both sub-apps were also de-branded/renamed off their old
product names as part of making this read as one app, ESO Helper, rather than
two things stitched together:

- `eso-build-manager/` → `viewer/` (Python package `eso_build_manager` →
  `eso_viewer`), app identity `"ESO Build Manager"` → `"ESO Helper Viewer"`
  (see `viewer/CLAUDE.md`'s "Storage" section for why it's not plain "ESO
  Helper" — that would collide with this window's own QSettings identity).
  Every renamed on-disk path (config dir, sync.json, gold history, icon cache)
  kept a non-destructive read-fallback to its pre-rename location — see that
  same CLAUDE.md.
- `Grimoire/` → `addon_manager/`; its standalone repo `khedron83/Grimoire` is
  being deleted, so this is its only home now — no more Flatpak/AppStream/
  `.desktop`/its-own-CI-release files (all deleted, they built a separately-
  distributed product that no longer exists), and its self-update-checker
  (which polled that repo's GitHub releases) was removed since it would just
  404 forever. See `addon_manager/CLAUDE.md` for the full rename/removal list,
  including the same non-destructive read-fallback treatment for its config
  dir, backup filename prefix, and per-addon sidecar files.

Each sub-app is still independently runnable via its own `main.py`/`run.py`,
and this file doesn't touch their internals, only composes them. Fixes
belonging to one sub-app still go in that sub-app's directory.

## What the composition layer in `main.py` actually does

- **Single QApplication**: created via `eso_viewer.app.create_app()` (sets
  `applicationName`/`organizationName` to `"ESO Helper Viewer"` /
  `"CubicSerenity"` — deliberately *not* `"ESO Helper"`, since this outer
  window already uses `QSettings("CubicSerenity", "ESO Helper")` explicitly
  for its own geometry; giving the viewer's bare `QSettings()` the identical
  app name would resolve to the same file and collide on the same
  `"geometry"` key. See `viewer/CLAUDE.md`'s "Storage" section — this is the
  same class of bug that section already documents once, just avoided this
  time by picking a distinct-but-still-de-branded name instead of reusing
  the old "ESO Build Manager" one).
- **Style**: `Fusion` (both sub-apps expect it). The addon manager's own
  hardcoded dark-palette override (`_apply_dark_palette()` in its `main.py`,
  only exercised standalone) is deliberately *not* applied here — the viewer
  is built to follow the KDE/system theme (see its CLAUDE.md's "What this is"
  section), and the addon manager's own `style.py` already uses
  `palette(...)` roles throughout rather than hardcoded colors, so it should
  read fine under the system theme too. Revisit if its tab looks wrong under
  a light theme.
- **Tray icon**: each sub-app's `MainWindow` creates its own tray icon in
  `__init__` (briefly visible before we hide it) — both get hidden right
  after construction, and `ESOHelperWindow` provides the one tray icon for
  the merged app (Show/Quit only), using the one shared icon at
  `packaging/eso-helper.svg`.
- **Single-instance lock**: the viewer's own `QLocalServer`/`QLocalSocket`
  pattern, re-implemented under a new key (`eso-helper-single-instance`)
  rather than imported from its `main.py` — it's ~15 lines and
  re-implementing it keeps the two sub-apps' own single-instance locks
  (which still guard their own standalone `main.py`/`run.py` entry points)
  decoupled from this one.
- **Geometry**: only the outer `ESOHelperWindow` saves/restores geometry
  now (`QSettings("CubicSerenity", "ESO Helper")`) — the embedded
  sub-windows' own geometry save/restore code is simply never exercised
  (nothing calls `.close()` on a tab page in normal use), which is harmless
  dead code in this context, not a bug.

## Known rough edges (not fixed, first pass)

- Each embedded `MainWindow` is a full `QMainWindow` (not refactored out of
  being one) — the addon manager's own File/Help menu bar still renders inline
  within its "Addons" tab content whenever that tab is active, on top of the
  viewer's own outer File/Help menu which is always visible. Works,
  just not visually seamless.
- The tray-icon flash on startup (each sub-app briefly shows its own tray
  icon before we hide it) is cosmetic only.
- No unified "Settings" — each tab still opens its own Settings dialog via
  its own menu.

Don't grow this further (shared settings dialog, one merged menu bar, a
single unified config) unless asked — it's a real risk area precisely
because both sub-apps have their own well-established, independently
documented behavior (see each one's own CLAUDE.md) that's easy to quietly
break by refactoring their internals instead of composing them as-is.

## Windows packaging (`packaging/`)

`packaging/eso-helper.spec` (PyInstaller, onedir) builds the whole composed
app, run from this directory: `pyinstaller packaging/eso-helper.spec`. On
Windows, build it on an actual Windows machine — PyInstaller doesn't
cross-compile — via `packaging/win/build.bat`. The app icon
(`packaging/eso-helper.svg`, also used by `packaging/install.sh`'s XDG
desktop entry) lives here rather than inside either sub-app now — there's one
icon for one app, not a per-sub-app one anymore.

The spec exists because two things about this composition layer are
invisible to PyInstaller's normal static import analysis:
- `viewer/main.py` is loaded at runtime via
  `importlib.util.spec_from_file_location` (see `_load_module` above), not a
  plain `import` — PyInstaller can't discover it, or its two bare top-level
  imports (`parser`, `model`), by walking imports from this spec's entry
  script. All three ship as raw source `datas` at the same relative path
  they occupy in the source repo, so `main.py`'s `_DIR / "viewer" /
  "main.py"` lookup (and that module's own `import parser`/`import model`,
  resolved off the sys.path entry this file inserts) keep working unmodified
  in the frozen build.
- The viewer's and addon manager's own submodules (`eso_viewer.ui.*`,
  `src.ui.*`, etc.) are only ever imported from inside those dynamically-loaded
  entry points, not from anything Analysis actually traces — the spec uses
  `collect_submodules('eso_viewer')` / `collect_submodules('src')`
  instead of a hand-curated hiddenimports list, so a new file added under
  either package doesn't silently break the next Windows build.

Verified (2026-08-15) by building a Linux onedir bundle from the same spec
and running it under `QT_QPA_PLATFORM=offscreen`: no `ModuleNotFoundError`,
package imports and `eso-build-manager/data/*.json` (now `viewer/data/*.json`)
all resolved correctly in the frozen layout. (That check also exercised
`storage/database.py`, which no longer exists — the whole SQLite build
subsystem was removed 2026-09-11; see `viewer/CLAUDE.md`'s "Builds tab".) The
`_pull_save_file()` "This PC" sync copy (`shutil.copy`, no OS-specific calls)
was verified directly by calling it through the same dynamic-load path used
in the real app — works. Could not verify the full GUI reaching that call
end-to-end in this sandbox: both sub-apps create a `QSystemTrayIcon` in their
own `__init__`, and tray creation appears to hang indefinitely with no system
tray / D-Bus session available (offscreen platform, no desktop environment) —
looks like a sandbox limitation, not a code issue, but worth a real
end-to-end check (does the window actually appear, does "This PC" mode
actually pull `WornGear.lua`) on the target Windows machine before relying on
it. Re-verify against the 2026-09-11 directory rename before trusting this
note blindly — it predates it.
