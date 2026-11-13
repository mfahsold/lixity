#!/usr/bin/env bash
# Per-user Linux XDG desktop launcher installer for Lixity (no root required).
# Usage:
#   ./scripts/install-desktop-linux.sh            Install launcher and icon
#   ./scripts/install-desktop-linux.sh --uninstall Remove launcher and icon (keeps all manuscripts)
set -euo pipefail

APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
DESKTOP_FILE="$APP_DIR/lixity.desktop"
ICON_FILE="$ICON_DIR/lixity.svg"

if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$DESKTOP_FILE" "$ICON_FILE"
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
    fi
    echo "Removed Lixity desktop launcher and icon. All manuscripts and project data remain untouched."
    exit 0
fi

LIXITY_BIN=""
if command -v lixity >/dev/null 2>&1; then
    LIXITY_BIN="$(command -v lixity)"
elif [ -x "$HOME/.local/bin/lixity" ]; then
    LIXITY_BIN="$HOME/.local/bin/lixity"
else
    echo "[ERR] Could not find 'lixity' on PATH or in ~/.local/bin/lixity." >&2
    echo "Install Lixity first (e.g. uv tool install lixity), then re-run this script." >&2
    exit 1
fi

mkdir -p "$APP_DIR" "$ICON_DIR"

cat >"$ICON_FILE" <<'EOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <rect width="64" height="64" rx="14" fill="#1e2430"/>
  <path d="M18 18h11c3 0 5 2 5 5v24c-2-2-4-3-7-3H18V18zm28 0H35c-3 0-5 2-5 5v24c2-2 4-3 7-3h9V18z" fill="none" stroke="#e8e2d5" stroke-width="3" stroke-linejoin="round"/>
  <path d="M22 26h6M22 32h6M36 26h6M36 32h6" stroke="#7aa2f7" stroke-width="2.5" stroke-linecap="round"/>
</svg>
EOF

cat >"$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Lixity
GenericName=Manuscript Analysis Workbench
GenericName[de]=Manuskript-Analysewerkbank
Comment=Local offline manuscript analysis, writing and revision workbench
Comment[de]=Lokale Offline-Werkbank für Manuskriptanalyse, Schreiben und Überarbeitung
Exec=sh -c '"$LIXITY_BIN" service start && xdg-open http://127.0.0.1:8765/'
Icon=lixity
Terminal=false
Categories=Office;Publishing;TextEditor;
StartupNotify=true
EOF

chmod 644 "$DESKTOP_FILE" "$ICON_FILE"
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

echo "Installed Lixity desktop launcher: $DESKTOP_FILE"
echo "You can now launch Lixity directly from your application menu without opening a terminal."
