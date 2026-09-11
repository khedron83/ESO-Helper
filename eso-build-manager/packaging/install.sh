#!/usr/bin/env bash
# Installs ESO Build Manager into the current user's application menu (XDG).
# Run from anywhere: bash packaging/install.sh
# Pass --autostart to also launch it minimized to the system tray on login (XDG
# autostart) -- for a machine that should always be pushing its local addon data in
# the background (see eso_build_manager/sync/addon.py), not just be launchable.
set -euo pipefail

APP_ID="eso-build-manager"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
AUTOSTART_DIR="$HOME/.config/autostart"

mkdir -p "$DESKTOP_DIR" "$ICON_DIR"

cp "$PROJECT_DIR/packaging/$APP_ID.svg" "$ICON_DIR/$APP_ID.svg"

cat > "$DESKTOP_DIR/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ESO Build Manager
Comment=Character stats viewer and build editor for Elder Scrolls Online
Exec=python3 "$PROJECT_DIR/main.py"
Path=$PROJECT_DIR
Icon=$APP_ID
Terminal=false
Categories=Game;
EOF

chmod +x "$DESKTOP_DIR/$APP_ID.desktop"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DESKTOP_DIR" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
command -v kbuildsycoca5 >/dev/null 2>&1 && kbuildsycoca5 --noincremental >/dev/null 2>&1 || true

echo "Installed — ESO Build Manager should now appear in your application menu."

if [[ "${1:-}" == "--autostart" ]]; then
    mkdir -p "$AUTOSTART_DIR"
    cat > "$AUTOSTART_DIR/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ESO Build Manager (tray)
Comment=Background sync -- character stats viewer and build editor for Elder Scrolls Online
Exec=python3 "$PROJECT_DIR/main.py" --tray
Path=$PROJECT_DIR
Icon=$APP_ID
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
    chmod +x "$AUTOSTART_DIR/$APP_ID.desktop"
    echo "Autostart installed — will launch minimized to the tray on next login."
fi
