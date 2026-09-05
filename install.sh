#!/usr/bin/env bash
# ══════════════════════════════════════════════════════
#  PowerZoid Manager — Instalador para Fedora / GNOME 45-50
#  Uso: bash install.sh
# ══════════════════════════════════════════════════════
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
LAUNCHER="$BIN_DIR/powerzoid-manager"
DESKTOP_FILE="$APPS_DIR/cl.cleal.PowerzoidManager.desktop"

G='\033[0;32m'; R='\033[0;31m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

echo -e "\n${BOLD}=== PowerZoid Manager — Instalador ===${NC}\n"

command -v python3 &>/dev/null || { echo -e "${R}Error:${NC} instala python3 primero"; exit 1; }
python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1')" 2>/dev/null \
    || { echo -e "${R}Error:${NC} faltan los bindings de GTK4/Libadwaita para Python (paquete python3-gobject)"; exit 1; }

mkdir -p "$BIN_DIR" "$APPS_DIR"

cp "$DIR/powerzoid_manager.py" "$BIN_DIR/powerzoid_manager.py"
chmod +x "$BIN_DIR/powerzoid_manager.py"

cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
exec python3 "$BIN_DIR/powerzoid_manager.py" "\$@"
EOF
chmod +x "$LAUNCHER"
echo -e "  ${G}✓${NC}  Instalado en $LAUNCHER"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=PowerZoid Manager
Comment=Instala, actualiza y desinstala las extensiones PowerZoid
Exec=$LAUNCHER
Icon=application-x-addon
Terminal=false
Categories=System;Settings;
StartupNotify=true
EOF
echo -e "  ${G}✓${NC}  Lanzador de aplicaciones creado en $DESKTOP_FILE"

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
