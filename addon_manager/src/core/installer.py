"""Download, install, and update addons."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, Optional

from .addon import Addon, addon_from_disk, write_sidecar
from .esoui import RemoteAddonInfo, fetch_addon_details, download_zip


ProgressCB = Callable[[int, int], None]  # (bytes_done, total)


def _extract_zip(zip_path: Path, addons_dir: Path) -> list[str]:
    extracted = set()
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            top = Path(member).parts[0] if Path(member).parts else None
            if top:
                extracted.add(top)
            zf.extract(member, addons_dir)
    return list(extracted)


def install_addon(
    info: RemoteAddonInfo,
    addons_dir: Path,
    progress_cb: Optional[ProgressCB] = None,
) -> list[Addon]:
    """
    Download and install an addon. Fetches the download URL from the API if needed.
    Returns the list of Addon objects installed (zip may contain multiple folders).
    """
    download_url = info.download_url
    if not download_url:
        details = fetch_addon_details(info.addon_id)
        download_url = details.get("download_url", "")
        info.download_url = download_url
        info.filename = details.get("filename", "")
        info.md5 = details.get("md5", "")
        if not info.description:
            info.description = details.get("description", "")

    if not download_url:
        raise RuntimeError(f"No download URL available for {info.name}")

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / (info.filename or f"{info.addon_id}.zip")
        download_zip(download_url, str(zip_path), progress_cb)
        folders = _extract_zip(zip_path, addons_dir)

    addons = []
    for folder_name in folders:
        folder = addons_dir / folder_name
        if folder.is_dir():
            write_sidecar(folder, info.addon_id, info.date)
            addon = addon_from_disk(folder)
            if addon:
                addon.addon_id = info.addon_id
                addon.esoui_url = info.info_url
                addon.download_url = download_url
                addon.remote_version = info.version
                addon.install_date = info.date
                addons.append(addon)

    return addons


def install_dev_addon(source_dir: Path, addons_dir: Path) -> Addon:
    """Symlink a local addon folder (e.g. one under active development) into
    addons_dir instead of downloading it -- for addons that aren't on ESOUI at
    all. Re-running with the same source is a no-op if already linked."""
    target = addons_dir / source_dir.name
    if target.is_symlink():
        if target.resolve() != source_dir.resolve():
            raise FileExistsError(
                f"{target} is already a symlink to a different folder ({target.resolve()})."
            )
    elif target.exists():
        raise FileExistsError(f"{target} already exists and isn't a symlink — remove it first.")
    else:
        target.symlink_to(source_dir)

    addon = addon_from_disk(target)
    if addon is None:
        raise RuntimeError(f"No addon manifest (.txt/.addon) found in {source_dir}")
    return addon


def find_bundled_lib_warnings(folder: Path, addons_dir: Path) -> list[str]:
    """Warn when an addon bundles its own copy of a library also installed standalone."""
    warnings = []
    for libs_dir in folder.glob("*"):
        if not (libs_dir.is_dir() and libs_dir.name.lower() in ("libs", "lib")):
            continue
        for lib in libs_dir.iterdir():
            standalone = addons_dir / lib.name
            if lib.is_dir() and standalone.is_dir() and standalone != folder:
                warnings.append(
                    f"{folder.name} bundles its own copy of '{lib.name}' "
                    f"({libs_dir.name}/{lib.name}), which is also installed standalone — "
                    f"may cause duplicate-library conflicts."
                )
    return warnings


def remove_addon(addon: Addon) -> None:
    if not addon.folder_path:
        return
    if addon.folder_path.is_symlink():
        # shutil.rmtree() refuses to operate on a symlink (would otherwise risk
        # wiping the target's contents) -- unlink the link itself instead, e.g.
        # a dev addon symlinked into AddOns for live testing.
        addon.folder_path.unlink()
    elif addon.folder_path.exists():
        shutil.rmtree(addon.folder_path)


def remove_saved_variables(addon: Addon, saved_vars_dir: Path) -> None:
    """Delete this addon's SavedVariables/<AddonFolderName>.lua file. The file is
    always named after the addon's own folder (== addon.name here), never after
    the `## SavedVariables:` manifest entries -- those name the Lua global
    table(s) stored *inside* that one file, not separate files."""
    sv_file = saved_vars_dir / f"{addon.name}.lua"
    if sv_file.exists():
        sv_file.unlink()


def update_addon(
    addon: Addon,
    info: RemoteAddonInfo,
    addons_dir: Path,
    progress_cb: Optional[ProgressCB] = None,
) -> list[Addon]:
    remove_addon(addon)
    return install_addon(info, addons_dir, progress_cb)


def _demo():
    with tempfile.TemporaryDirectory() as tmp:
        addons_dir = Path(tmp)
        my_addon = addons_dir / "MyAddon"
        (my_addon / "Libs" / "LibStub").mkdir(parents=True)
        (my_addon / "Libs" / "LibOnlyBundled").mkdir(parents=True)
        (addons_dir / "LibStub").mkdir()

        warnings = find_bundled_lib_warnings(my_addon, addons_dir)
        assert len(warnings) == 1, warnings
        assert "LibStub" in warnings[0]
        assert "LibOnlyBundled" not in " ".join(warnings)

    with tempfile.TemporaryDirectory() as tmp:
        addons_dir = Path(tmp)
        real_target = addons_dir / "RealAddon"
        (real_target / "sub").mkdir(parents=True)
        (real_target / "sub" / "f.txt").write_text("x")
        link = addons_dir / "DevAddon"
        link.symlink_to(real_target)

        remove_addon(Addon(folder_path=link))
        assert not link.exists() and not link.is_symlink(), "symlinked addon should be unlinked"
        assert real_target.is_dir(), "symlink target must survive removal"

        remove_addon(Addon(folder_path=real_target))
        assert not real_target.exists(), "regular addon dir should be removed"

    with tempfile.TemporaryDirectory() as tmp:
        source_root = Path(tmp) / "src"
        addons_dir = Path(tmp) / "AddOns"
        addons_dir.mkdir()
        dev_addon = source_root / "MyDevAddon"
        dev_addon.mkdir(parents=True)
        (dev_addon / "MyDevAddon.txt").write_text(
            "## Title: MyDevAddon\n## DependsOn: LibFoo>=1 LibBar\n"
        )

        addon = install_dev_addon(dev_addon, addons_dir)
        assert addon.depends_on == ["LibFoo", "LibBar"], addon.depends_on
        link = addons_dir / "MyDevAddon"
        assert link.is_symlink() and link.resolve() == dev_addon.resolve()

        # re-running against the same source is a no-op, not an error
        install_dev_addon(dev_addon, addons_dir)

        # a different source folder that happens to share the same name must
        # not silently steal the existing symlink
        other_source = source_root / "elsewhere" / "MyDevAddon"
        other_source.mkdir(parents=True)
        try:
            install_dev_addon(other_source, addons_dir)
            assert False, "should refuse to relink an existing name to a different source"
        except FileExistsError:
            pass
    print("ok")


if __name__ == "__main__":
    _demo()
