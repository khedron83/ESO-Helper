# ESO Helper — Addons

An addon manager for **The Elder Scrolls Online**, built with Python and PySide6. Browse, install, update, and back up your addons directly from [ESOUI.com](https://www.esoui.com) — no browser required.

This used to be a standalone project ("Grimoire"). It's now vendored here as the "Addons" tab of [ESO Helper](../CLAUDE.md) — there's no separate repo, release page, or Flatpak build for it anymore; see the top-level CLAUDE.md's "What the composition layer does" for how it's embedded.

Works on **Windows**, **Linux**, and **Steam Deck**.

---

## Features

- **Browse** the full ESOUI addon catalogue (~3,000 addons) with live search, category filter, and sortable columns
- **Install** addons in one click — dependencies resolved and installed automatically
- **Update** installed addons — detects newer versions and updates in bulk
- **Bundled-library conflict warnings** — flags when an addon bundles its own copy of a library (e.g. LibStub) that's also installed standalone, which can cause duplicate-library conflicts
- **Remove** addons cleanly from the AddOns directory
- **Backup & restore** your AddOns folder and optionally your SavedVariables (character data, settings)
- **Auto-detect** your AddOns directory on first launch (Windows, Linux, Steam Deck / Proton paths all covered)
- Dark theme designed to match ESO's aesthetic (standalone run only — inside ESO Helper it follows the composed app's Fusion/system theme instead)

---

## Running

Normally this runs embedded as ESO Helper's "Addons" tab (`python ../main.py` from the repo root). To run just this piece standalone for development:

```bash
cd addon_manager
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

### First run

It will attempt to auto-detect your AddOns directory. If it can't find it, the Settings dialog opens automatically. Set the path to:

| Platform | Default path |
|---|---|
| Windows | `C:\Users\<you>\Documents\Elder Scrolls Online\live\AddOns` |
| Linux (native) | `~/Documents/Elder Scrolls Online/live/AddOns` |
| Steam Deck / Proton | `~/.steam/steam/steamapps/compatdata/306130/pfx/drive_c/users/steamuser/Documents/Elder Scrolls Online/live/AddOns` |

---

## Usage

### Installed tab

Lists every addon currently in your AddOns directory. Addons with available updates are highlighted in amber.

| Button | Action |
|---|---|
| **Refresh** | Rescan the AddOns directory |
| **Update Selected** | Download and install updates for selected addons |
| **Update All** | Update every addon that has a newer version available |
| **Remove** | Delete the selected addon folder |

### Browse tab

Fetches the full addon list from ESOUI on launch (runs in the background). Sorted by downloads by default.

- **Search** — filter by name, author, or category in real time
- **Category** — filter by addon category (e.g. Unit Frames, Maps, Combat)
- **Sort** — click any column header
- **Detail panel** — select any addon to see its description, changelog, and install status
- **Install** — installs the addon and all missing dependencies in one step

### Backup tab

- **Create backup** — zip your entire AddOns folder (and optionally SavedVariables) to a chosen location
- **Restore** — extract a previous backup, replacing current files

---

## License

This project is licensed under the **GNU General Public License v3.0**. See [LICENSE](LICENSE) for details.

Addon metadata is sourced from [ESOUI.com](https://www.esoui.com) via the MMOUI JSON API.
