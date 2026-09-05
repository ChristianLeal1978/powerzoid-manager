#!/usr/bin/env bash
# ══════════════════════════════════════════════════════
#  PowerZoid Manager — Desinstalador
#  Uso: bash uninstall.sh
# ══════════════════════════════════════════════════════
set -euo pipefail

BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"

BOLD='\033[1m'; NC='\033[0m'

echo -e "\n${BOLD}=== PowerZoid Manager — Desinstalador ===${NC}\n"

rm -f "$BIN_DIR/powerzoid_manager.py" "$BIN_DIR/powerzoid-manager"
rm -f "$APPS_DIR/cl.cleal.PowerzoidManager.desktop"

echo -e "  ✓  PowerZoid Manager eliminado"
echo ""
echo -e "Nota: esto NO desinstala ninguna extensión PowerZoid ya instalada,"
echo -e "solo el propio administrador."
echo ""
