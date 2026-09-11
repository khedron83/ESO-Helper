# -*- mode: python ; coding: utf-8 -*-
#
# Builds the composed ESO Helper app (viewer + addon_manager in one window).
# Run from the eso-helper/ repo root:
#   pyinstaller packaging/eso-helper.spec
#
# viewer/main.py is loaded at runtime via importlib
# (spec_from_file_location), not a normal `import`, so PyInstaller's static
# analysis can't discover it or its two bare top-level module imports
# (`parser`, `model`) by following imports from this spec's entry script.
# Those three are shipped as raw source datas instead of being compiled into
# the PYZ, landing at the same relative path they occupy in the source repo
# so eso-helper/main.py's `_DIR / "viewer" / "main.py"` lookup (and that
# module's own bare `import parser` / `import model`, resolved via the
# sys.path entry eso-helper/main.py inserts) keep working unmodified.
#
# eso_viewer's data_loader.py resolves its JSON data dir as
# `Path(__file__).parent.parent / "data"` -- since the eso_viewer *package*
# gets collected into the bundle preserving its internal layout
# (bundle_root/eso_viewer/...), "data" needs to land at bundle_root/data
# (a sibling of the package dir), matching its position in the source repo
# relative to the eso_viewer package.
import sys
from pathlib import Path

# collect_submodules() below imports these packages in-process (unrelated to
# Analysis's own pathex, which only governs its static import resolution) --
# needs them importable here too.
_ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(_ROOT / 'viewer'))
sys.path.insert(0, str(_ROOT / 'addon_manager'))

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['../main.py'],
    pathex=['..', '../viewer', '../addon_manager'],
    binaries=[],
    datas=[
        ('../viewer/main.py', 'viewer'),
        ('../viewer/parser.py', 'viewer'),
        ('../viewer/model.py', 'viewer'),
        ('../viewer/data', 'data'),
        ('../packaging/eso-helper.svg', 'packaging'),
        ('../addon_manager/src/resources', 'addon_manager/src/resources'),
    ],
    hiddenimports=(
        collect_submodules('eso_viewer')
        + collect_submodules('src')
        + ['lxml.etree', 'lxml._elementpath']
    ),
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'unittest'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='eso-helper',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    argv_emulation=False,
    icon='win/eso-helper.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='eso-helper',
)
