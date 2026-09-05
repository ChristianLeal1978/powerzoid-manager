# PowerZoid Manager — GNOME app

Administrador gráfico para instalar, actualizar y desinstalar las extensiones **PowerZoid** (`powerzoid-*`) que viven como repos independientes en `~/Proyectos`. Una sola pantalla, sin dependencias más allá de GTK4/Libadwaita.

## Qué hace

- Al abrir, recorre `~/Proyectos` buscando repos `powerzoid-*` con `extension/metadata.json` (o equivalente) y trae los últimos cambios de cada uno (`git pull --ff-only`) para saber si hay una versión más nueva disponible.
- Si **no tienes ninguna extensión instalada**, muestra la lista completa en orden alfabético para que elijas cuáles instalar.
- Si **ya tienes extensiones instaladas**, muestra su versión actual y, si el repo tiene una versión más nueva, un botón **Actualizar**.
- Cada fila tiene sus propios botones: **Instalar** / **Actualizar** / 🗑 **Eliminar**.
- Arriba hay dos casillas para acciones masivas — **Instalar todas las no instaladas** y **Eliminar todas las instaladas** — que siempre piden confirmación antes de ejecutarse.
- Instalar/actualizar/eliminar usa el propio `install.sh`/`uninstall.sh` de cada extensión (respetando daemons, systemd, etc.) y muestra su salida en vivo; si un repo no trae esos scripts, copia/borra los archivos de la extensión directamente.

## Requisitos

- GNOME Shell 45–50 (probado en GNOME Shell 50 / Fedora 44)
- Python 3 con bindings de GTK4/Libadwaita (paquete `python3-gobject`, ya viene en Fedora Workstation)
- Extensiones PowerZoid clonadas en `~/Proyectos/powerzoid-*` (cada una con su propio repo Git)

## Instalación

```bash
git clone https://github.com/ChristianLeal1978/powerzoid-manager.git
cd powerzoid-manager
bash install.sh
```

Esto instala `powerzoid-manager` en `~/.local/bin` y crea un lanzador de aplicaciones ("PowerZoid Manager") en el resumen de actividades.

## Uso

```bash
powerzoid-manager
```

O búscalo como **PowerZoid Manager** en el resumen de actividades de GNOME.

| Acción | Resultado |
|---|---|
| Botón ↻ (arriba a la derecha) | Vuelve a comprobar `~/Proyectos` y trae cambios de GitHub |
| **Instalar** en una fila | Instala esa extensión (ejecuta su `install.sh` si lo tiene) |
| **Actualizar** en una fila | Reinstala con la versión más reciente del repo local |
| 🗑 en una fila | Pide confirmación y desinstala esa extensión |
| Casilla **Instalar todas las no instaladas** | Pide confirmación e instala todo lo pendiente |
| Casilla **Eliminar todas las instaladas** | Pide confirmación y desinstala todo lo instalado |

Si un `install.sh` pide datos por teclado (por ejemplo, PowerZoid Deploy pide un token de Vercel la primera vez), la ventana de progreso de esa fila tiene un campo de texto para responderle. La instalación masiva ("Instalar todas") no interactúa con esos scripts — instala mejor esa extensión individualmente la primera vez si necesita un dato así.

## Desinstalar

```bash
bash uninstall.sh
```

Esto solo quita el propio PowerZoid Manager; no toca ninguna extensión PowerZoid ya instalada.

## Cómo funciona

Cada extensión PowerZoid vive en `~/Proyectos/powerzoid-<nombre>`, con su UUID y versión en `extension/metadata.json`. El manager compara ese número de versión con el de la copia instalada en `~/.local/share/gnome-shell/extensions/<uuid>/metadata.json` para decidir si ofrece "Instalar" o "Actualizar". No inventa lógica de instalación propia cuando puede evitarlo: si el repo trae `install.sh`/`uninstall.sh`, los ejecuta tal cual (para respetar daemons, `systemd --user`, tokens guardados, etc.); si no los trae, copia o borra directamente la carpeta de la extensión.

## Compatibilidad

| GNOME Shell | Fedora  | Estado |
|-------------|---------|--------|
| 50          | 44      | ✅ Probado |
| 45–49       | 39–43   | ✅ Compatible |

## Licencia

GPL-2.0 — ver [LICENSE](LICENSE)
