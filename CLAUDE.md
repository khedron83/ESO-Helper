# ESO Helper

One process, one window: `main.py` builds a single `QApplication`, and
Grimoire's `MainWindow` becomes a final tab ("Addons") inside eso-build-manager's
own tab strip via the `extra_tab` constructor hook (`eso-build-manager/main.py`
`MainWindow.__init__`/`_rebuild_tabs`) — rather than the two sub-apps sitting
as two top-level tabs one level up. One row of 6 peer tabs (Character /
Activities / Storage / Collection / Builds / Addons) reads more like one app
than a mode switch between two; `ESOHelperWindow`'s central widget is just
`self._build_win` directly, no outer `QTabWidget` of its own anymore. Neither
sub-app's own entry point runs (their `if __name__ == '__main__':` blocks /
Grimoire's `main()` are never called) — only their class definitions get
imported, via `sys.path` pointing at both repo roots. This was a deliberate
pivot from an earlier launcher-that-spawns-two-processes design — see git
history if that shape is ever wanted back.

`eso-build-manager/` and `Grimoire/` are still full copies of their original
repos (no shared git history — those still live at their own GitHub
remotes), and each is still independently runnable via its own
`main.py`/`run.py` — this file doesn't touch their internals, only composes
them. Fixes belonging to one app go in that app's directory and, ideally,
back upstream to its own repo — not here.

## What the composition layer in `main.py` actually does

- **Single QApplication**: created via `eso_build_manager.app.create_app()`
  (sets `applicationName`/`organizationName` to "ESO Build Manager" /
  "CubicSerenity" — deliberately *not* renamed to "ESO Helper", since
  eso-build-manager's own code relies on bare `QSettings()` resolving to
  that exact pair; see its CLAUDE.md's "Storage" section for the bug that
  already cost debugging time once from getting this wrong).
- **Style**: `Fusion` (both sub-apps expect it). Grimoire's own hardcoded
  dark-palette override (`_apply_dark_palette()` in its `main.py`) is
  deliberately *not* applied — eso-build-manager is built to follow the
  KDE/system theme (see its CLAUDE.md's "What this is" section), and
  Grimoire's own `style.py` already uses `palette(...)` roles throughout
  rather than hardcoded colors, so it should read fine under the system
  theme too. Revisit if Grimoire's tab looks wrong under a light theme.
- **Tray icon**: each sub-app's `MainWindow` creates its own tray icon in
  `__init__` (briefly visible before we hide it) — both get hidden right
  after construction, and `ESOHelperWindow` provides the one tray icon for
  the merged app (Show/Quit only).
- **Single-instance lock**: eso-build-manager's own `QLocalServer`/
  `QLocalSocket` pattern, re-implemented under a new key
  (`eso-helper-single-instance`) rather than imported from its `main.py` —
  it's ~15 lines and re-implementing it keeps the two sub-apps' own
  single-instance locks (which still guard their own standalone
  `main.py`/`run.py` entry points) decoupled from this one.
- **Geometry**: only the outer `ESOHelperWindow` saves/restores geometry
  now (`QSettings("CubicSerenity", "ESO Helper")`) — the embedded
  sub-windows' own geometry save/restore code is simply never exercised
  (nothing calls `.close()` on a tab page in normal use), which is harmless
  dead code in this context, not a bug.

## Known rough edges (not fixed, first pass)

- Each embedded `MainWindow` is a full `QMainWindow` (not refactored out of
  being one) — Grimoire's own File/Help menu bar still renders inline within
  its "Addons" tab content whenever that tab is active, on top of
  eso-build-manager's own outer File/Help menu which is always visible. Works,
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
cross-compile — via `packaging/win/build.bat`.

The spec exists because two things about this composition layer are
invisible to PyInstaller's normal static import analysis:
- `eso-build-manager/main.py` is loaded at runtime via
  `importlib.util.spec_from_file_location` (see `_load_module` above), not a
  plain `import` — PyInstaller can't discover it, or its two bare top-level
  imports (`parser`, `model`), by walking imports from this spec's entry
  script. All three ship as raw source `datas` at the same relative path
  they occupy in the source repo, so `main.py`'s `_DIR / "eso-build-manager"
  / "main.py"` lookup (and that module's own `import parser`/`import model`,
  resolved off the sys.path entry this file inserts) keep working unmodified
  in the frozen build.
- `eso_build_manager`'s and Grimoire's own submodules (`eso_build_manager.ui.*`,
  `src.ui.*`, etc.) are only ever imported from inside those dynamically-loaded
  entry points, not from anything Analysis actually traces — the spec uses
  `collect_submodules('eso_build_manager')` / `collect_submodules('src')`
  instead of a hand-curated hiddenimports list, so a new file added under
  either package doesn't silently break the next Windows build.

Verified (2026-08-15) by building a Linux onedir bundle from the same spec
and running it under `QT_QPA_PLATFORM=offscreen`: no `ModuleNotFoundError`,
package imports and `eso-build-manager/data/*.json` all resolved correctly
in the frozen layout. (That check also exercised `storage/database.py`, which
no longer exists — the whole SQLite build subsystem was removed 2026-09-11;
see eso-build-manager's CLAUDE.md "Builds tab".) The `_pull_save_file()` "This PC" sync copy
(`shutil.copy`, no OS-specific calls) was verified directly by calling it
through the same dynamic-load path used in the real app — works. Could not
verify the full GUI reaching that call end-to-end in this sandbox: both
sub-apps create a `QSystemTrayIcon` in their own `__init__`, and tray
creation appears to hang indefinitely with no system tray / D-Bus session
available (offscreen platform, no desktop environment) — looks like a
sandbox limitation, not a code issue, but worth a real end-to-end check
(does the window actually appear, does "This PC" mode actually pull
`WornGear.lua`) on the target Windows machine before relying on it.
