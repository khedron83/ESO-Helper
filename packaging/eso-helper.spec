# -*- mode: python ; coding: utf-8 -*-
#
# Builds the composed ESO Helper app (eso-build-manager + Grimoire in one
# window). Run from the eso-helper/ repo root:
#   pyinstaller packaging/eso-helper.spec
#
# eso-build-manager/main.py is loaded at runtime via importlib
# (spec_from_file_location), not a normal `import`, so PyInstaller's static
# analysis can't discover it or its two bare top-level module imports
# (`parser`, `model`) by following imports from this spec's entry script.
# Those three are shipped as raw source datas instead of being compiled into
# the PYZ, landing at the same relative path they occupy in the source repo
# so eso-helper/main.py's `_DIR / "eso-build-manager" / "main.py"` lookup
# (and that module's own bare `import parser` / `import model`, resolved via
# the sys.path entry eso-helper/main.py inserts) keep working unmodified.
#
# eso_build_manager's data_loader.py resolves its JSON data dir as
# `Path(__file__).parent.parent / "data"` -- since the eso_build_manager
# *package* gets collected into the bundle preserving its internal layout
# (bundle_root/eso_build_manager/...), "data" needs to land at bundle_root/data
# (a sibling of the package dir), matching its position in the source repo
# relative to the eso_build_manager package.
import sys
from pathlib import Path

# collect_submodules() below imports these packages in-process (unrelated to
# Analysis's own pathex, which only governs its static import resolution) --
# needs them importable here too.
_ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(_ROOT / 'eso-build-manager'))
sys.path.insert(0, str(_ROOT / 'Grimoire'))

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['../main.py'],
    pathex=['..', '../eso-build-manager', '../Grimoire'],
    binaries=[],
    datas=[
        ('../eso-build-manager/main.py', 'eso-build-manager'),
        ('../eso-build-manager/parser.py', 'eso-build-manager'),
        ('../eso-build-manager/model.py', 'eso-build-manager'),
        ('../eso-build-manager/data', 'data'),
        ('../eso-build-manager/packaging/eso-build-manager.svg', 'eso-build-manager/packaging'),
        ('../Grimoire/src/resources', 'Grimoire/src/resources'),
    ],
    hiddenimports=(
        collect_submodules('eso_build_manager')
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
