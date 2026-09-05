#!/usr/bin/env bash
# ══════════════════════════════════════════════════════
#  PowerZoid Manager — Instalador para Fedora / GNOME 45-50
#  Uso: bash install.sh
# ══════════════════════════════════════════════════════
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
APP_ID="cl.cleal.PowerzoidManager"
LAUNCHER="$BIN_DIR/powerzoid-manager"
DESKTOP_FILE="$APPS_DIR/$APP_ID.desktop"

G='\033[0;32m'; R='\033[0;31m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

echo -e "\n${BOLD}=== PowerZoid Manager — Instalador ===${NC}\n"

command -v python3 &>/dev/null || { echo -e "${R}Error:${NC} instala python3 primero"; exit 1; }
python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1')" 2>/dev/null \
    || { echo -e "${R}Error:${NC} faltan los bindings de GTK4/Libadwaita para Python (paquete python3-gobject)"; exit 1; }

mkdir -p "$BIN_DIR" "$APPS_DIR" "$ICON_DIR"

cp "$DIR/powerzoid_manager.py" "$BIN_DIR/powerzoid_manager.py"
chmod +x "$BIN_DIR/powerzoid_manager.py"

cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
exec python3 "$BIN_DIR/powerzoid_manager.py" "\$@"
EOF
chmod +x "$LAUNCHER"
echo -e "  ${G}✓${NC}  Instalado en $LAUNCHER"

cp "$DIR/data/icons/$APP_ID.svg" "$ICON_DIR/$APP_ID.svg"
echo -e "  ${G}✓${NC}  Ícono instalado en $ICON_DIR/$APP_ID.svg"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=PowerZoid Manager
Comment=Instala, actualiza y desinstala las extensiones PowerZoid
Exec=$LAUNCHER
Icon=$APP_ID
Terminal=false
Categories=System;GTK;
StartupWMClass=$APP_ID
StartupNotify=true
EOF
echo -e "  ${G}✓${NC}  Lanzador de aplicaciones creado en $DESKTOP_FILE"

update-desktop-database "$APPS_DIR" &>/dev/null || true
gtk-update-icon-cache -qtf "$HOME/.local/share/icons/hicolor" &>/dev/null || true
echo -e "  ${G}✓${NC}  Ya debería verse en el resumen de actividades → cuadrícula de apps"

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo ""
    echo -e "  ${DIM}$BIN_DIR no está en tu PATH — agrégalo a ~/.bashrc:${NC}"
    echo -e "    ${BOLD}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
fi

echo ""
echo -e "Ábrelo con:"
echo -e "  ${BOLD}powerzoid-manager${NC}"
echo -e "  ${DIM}(o búscalo como \"PowerZoid Manager\" en el resumen de actividades)${NC}"
echo ""
