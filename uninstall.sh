#!/usr/bin/env bash
# ══════════════════════════════════════════════════════
#  PowerZoid Manager — Desinstalador
#  Uso: bash uninstall.sh
# ══════════════════════════════════════════════════════
set -euo pipefail

BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
APP_ID="cl.cleal.PowerzoidManager"

BOLD='\033[1m'; NC='\033[0m'

echo -e "\n${BOLD}=== PowerZoid Manager — Desinstalador ===${NC}\n"

rm -f "$BIN_DIR/powerzoid_manager.py" "$BIN_DIR/powerzoid-manager"
rm -f "$APPS_DIR/$APP_ID.desktop"
rm -f "$ICON_DIR/$APP_ID.svg"

update-desktop-database "$APPS_DIR" &>/dev/null || true
gtk-update-icon-cache -qtf "$HOME/.local/share/icons/hicolor" &>/dev/null || true

echo -e "  ✓  PowerZoid Manager eliminado"
echo ""
echo -e "Nota: esto NO desinstala ninguna extensión PowerZoid ya instalada,"
echo -e "solo el propio administrador."
echo ""
