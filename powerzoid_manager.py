#!/usr/bin/env python3
"""PowerZoid Manager — instala, actualiza y desinstala las extensiones PowerZoid."""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

APP_ID = "cl.cleal.PowerzoidManager"
REPOS_DIR = Path.home() / "Proyectos"
EXT_INSTALL_DIR = Path.home() / ".local/share/gnome-shell/extensions"
SELF_DIR_NAME = "powerzoid-manager"
GIT_PULL_TIMEOUT = 15
SCRIPT_TIMEOUT = 300
INSTALLED_COMMIT_FILENAME = ".powerzoid-installed-commit"

# Purrr no es un PowerZoid (no es una extensión de GNOME Shell, sino una app GTK
# aparte con su propio venv), pero se vigila en la misma lista para avisar de
# actualizaciones pendientes.
PURRR_REPO = REPOS_DIR / "purrr"
PURRR_UUID = "purrr@cleal.cl"
PURRR_STATE_DIR = Path.home() / ".local/share/purrr"

DEFAULT_ICON = "application-x-addon-symbolic"
ICON_BY_UUID = {
    "powerzoid-calendar@cleal.cl": "x-office-calendar-symbolic",
    "powerzoid-claude@cleal.cl": "battery-level-50-symbolic",
    "powerzoid-color-picker@cleal.cl": "color-select-symbolic",
    "powerzoid-deploy@cleal.cl": "network-transmit-receive-symbolic",
    "powerzoid-memory@cleal.cl": "org.gnome.SystemMonitor-symbolic",
    "powerzoid-music@cleal.cl": "audio-headphones-symbolic",
    "powerzoid-screenshot@cleal.cl": "camera-photo-symbolic",
    "powerzoid-sync@cleal.cl": "folder-remote-symbolic",
    "powerzoid-todo@cleal.cl": "task-due-symbolic",
    "powerzoid-workspaces@cleal.cl": "view-grid-symbolic",
    PURRR_UUID: "io.github.christianlealreyes.Purrr",
}


@dataclass
class Extension:
    repo_path: Path
    meta_path: Path
    uuid: str
    name: str
    description: str
    source_version: int | None
    install_script: Path | None
    uninstall_script: Path | None
    source_commit: str | None = None
    installed_version: int | None = None
    installed_commit: str | None = None
    always_installed: bool = False

    @property
    def is_installed(self) -> bool:
        return self.always_installed or self.installed_version is not None

    @property
    def has_update(self) -> bool:
        if not self.is_installed:
            return False
        if (
            isinstance(self.source_version, int)
            and isinstance(self.installed_version, int)
            and self.source_version > self.installed_version
        ):
            return True
        # Sin bump de versión, pero el commit instalado no coincide con el del repo
        # (o nunca se registró un commit instalado): puede haber cambios sin liberar.
        return bool(self.source_commit) and self.source_commit != self.installed_commit


def find_metadata(repo: Path) -> Path | None:
    """Busca metadata.json dentro del repo, sin entrar a .git ni node_modules."""
    candidates = []
    for path in repo.rglob("metadata.json"):
        parts = path.relative_to(repo).parts
        if ".git" in parts or "node_modules" in parts:
            continue
        candidates.append(path)
    if not candidates:
        return None
    candidates.sort(key=lambda p: len(p.parts))
    return candidates[0]


def read_installed_version(uuid: str) -> int | None:
    meta_path = EXT_INSTALL_DIR / uuid / "metadata.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text()).get("version")
    except (json.JSONDecodeError, OSError):
        return None


def read_repo_commit(repo: Path) -> str | None:
    """Devuelve el hash del commit HEAD del repo, o None si no es un repo git."""
    if not (repo / ".git").is_dir():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=GIT_PULL_TIMEOUT,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def installed_commit_marker(uuid: str) -> Path:
    """Purrr no vive en EXT_INSTALL_DIR (no es una extensión GNOME), así que guarda su
    marcador en su propio directorio de datos."""
    if uuid == PURRR_UUID:
        return PURRR_STATE_DIR / INSTALLED_COMMIT_FILENAME
    return EXT_INSTALL_DIR / uuid / INSTALLED_COMMIT_FILENAME


def read_installed_commit(marker: Path) -> str | None:
    try:
        return marker.read_text().strip() or None
    except OSError:
        return None


def write_installed_commit(marker: Path, commit: str | None) -> None:
    """Registra qué commit del repo quedó instalado, para detectar cambios futuros aunque no se suba la versión."""
    if not commit:
        return
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(commit + "\n")
    except OSError:
        pass


def discover_extensions() -> list[Extension]:
    extensions: list[Extension] = []
    if not REPOS_DIR.is_dir():
        return extensions

    for repo in sorted(REPOS_DIR.iterdir()):
        if not repo.is_dir() or repo.name == SELF_DIR_NAME:
            continue
        if not repo.name.startswith("powerzoid-"):
            continue

        meta_path = find_metadata(repo)
        if meta_path is None:
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        uuid = meta.get("uuid")
        if not uuid:
            continue

        install_script = repo / "install.sh"
        uninstall_script = repo / "uninstall.sh"

        extensions.append(
            Extension(
                repo_path=repo,
                meta_path=meta_path,
                uuid=uuid,
                name=meta.get("name", repo.name),
                description=meta.get("description", ""),
                source_version=meta.get("version"),
                install_script=install_script if install_script.exists() else None,
                uninstall_script=uninstall_script if uninstall_script.exists() else None,
                source_commit=read_repo_commit(repo),
            )
        )

    if (PURRR_REPO / ".git").is_dir():
        extensions.append(
            Extension(
                repo_path=PURRR_REPO,
                meta_path=PURRR_REPO / "pyproject.toml",
                uuid=PURRR_UUID,
                name="Purrr",
                description=(
                    "Reproductor de música GTK4/libadwaita (no es un PowerZoid, "
                    "pero se vigila igual)"
                ),
                source_version=None,
                install_script=None,
                uninstall_script=None,
                source_commit=read_repo_commit(PURRR_REPO),
                always_installed=True,
            )
        )

    for ext in extensions:
        ext.installed_version = read_installed_version(ext.uuid)
        marker = installed_commit_marker(ext.uuid)
        ext.installed_commit = read_installed_commit(marker)
        if ext.uuid == PURRR_UUID and ext.installed_commit is None and ext.source_commit:
            # Primera vez que se detecta Purrr: toma el commit actual como línea base
            # en vez de mostrar una "actualización disponible" falsa de entrada.
            write_installed_commit(marker, ext.source_commit)
            ext.installed_commit = ext.source_commit

    extensions.sort(key=lambda e: e.name.casefold())
    return extensions


def git_pull(repo: Path) -> None:
    """Trae los últimos cambios del repo (fast-forward only, no toca cambios locales)."""
    if not (repo / ".git").is_dir():
        return
    try:
        subprocess.run(
            ["git", "-C", str(repo), "pull", "--ff-only", "--quiet"],
            capture_output=True,
            timeout=GIT_PULL_TIMEOUT,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        pass


def generic_install(ext: Extension) -> None:
    """Instala copiando los archivos de la extensión, para repos sin install.sh."""
    if ext.uuid == PURRR_UUID:
        # Instalación editable: el `git pull` ya deja el código en vivo, solo falta
        # sincronizar dependencias nuevas del pyproject.toml.
        venv_pip = ext.repo_path / ".venv/bin/pip"
        if venv_pip.exists():
            subprocess.run(
                [str(venv_pip), "install", "-e", ".", "--quiet"],
                cwd=str(ext.repo_path),
                capture_output=True,
                timeout=SCRIPT_TIMEOUT,
                check=False,
            )
        return
    source = ext.meta_path.parent
    target = EXT_INSTALL_DIR / ext.uuid
    # Algunos repos symlinkean su carpeta de extensión directamente dentro de
    # EXT_INSTALL_DIR para desarrollo; en ese caso copiar sería copiarla sobre sí misma.
    if not (target.exists() and target.resolve() == source.resolve()):
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, dirs_exist_ok=True)
    subprocess.run(["gnome-extensions", "enable", ext.uuid], capture_output=True, check=False)


def generic_uninstall(ext: Extension) -> None:
    """Desinstala genéricamente, para repos sin uninstall.sh."""
    if ext.uuid == PURRR_UUID:
        # Purrr es una app aparte, no una extensión: este manager no la desinstala.
        return
    subprocess.run(["gnome-extensions", "disable", ext.uuid], capture_output=True, check=False)
    shutil.rmtree(EXT_INSTALL_DIR / ext.uuid, ignore_errors=True)


class RunDialog(Adw.Dialog):
    """Ventana de progreso que ejecuta un install.sh/uninstall.sh y muestra su salida en vivo."""

    def __init__(self, title: str, script: Path, on_done):
        super().__init__(title=title, content_width=640, content_height=440)
        self._on_done = on_done
        self._proc: subprocess.Popen | None = None

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar(show_end_title_buttons=True)
        toolbar_view.add_top_bar(header)

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_top=8,
            margin_bottom=8,
            margin_start=8,
            margin_end=8,
        )

        self.status_label = Gtk.Label(label="Ejecutando…", xalign=0)
        box.append(self.status_label)

        scroller = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scroller.add_css_class("card")
        self.textview = Gtk.TextView(
            editable=False,
            monospace=True,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            top_margin=6,
            bottom_margin=6,
            left_margin=6,
            right_margin=6,
        )
        self.buffer = self.textview.get_buffer()
        scroller.set_child(self.textview)
        box.append(scroller)

        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.entry = Gtk.Entry(hexpand=True, placeholder_text="Si el script pide datos, escríbelos aquí…")
        self.entry.connect("activate", self._on_send)
        send_btn = Gtk.Button(label="Enviar")
        send_btn.connect("clicked", self._on_send)
        input_box.append(self.entry)
        input_box.append(send_btn)
        box.append(input_box)

        close_box = Gtk.Box(halign=Gtk.Align.END)
        self.close_btn = Gtk.Button(label="Cerrar")
        self.close_btn.connect("clicked", lambda *_: self.close())
        close_box.append(self.close_btn)
        box.append(close_box)

        toolbar_view.set_content(box)
        self.set_child(toolbar_view)

        self._start(script)

    def _append(self, text: str) -> bool:
        end = self.buffer.get_end_iter()
        self.buffer.insert(end, text)
        self.textview.scroll_to_iter(self.buffer.get_end_iter(), 0, False, 0, 0)
        return False

    def _start(self, script: Path) -> None:
        def worker():
            try:
                proc = subprocess.Popen(
                    ["bash", str(script)],
                    cwd=str(script.parent),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
            except OSError as exc:
                GLib.idle_add(self._append, f"\nError al ejecutar {script.name}: {exc}\n")
                GLib.idle_add(self._finish, 1)
                return

            self._proc = proc
            for line in proc.stdout:
                GLib.idle_add(self._append, line)
            proc.wait()
            GLib.idle_add(self._finish, proc.returncode)

        threading.Thread(target=worker, daemon=True).start()

    def _on_send(self, *_args) -> None:
        if self._proc is None or self._proc.stdin.closed:
            return
        text = self.entry.get_text()
        self.entry.set_text("")
        try:
            self._proc.stdin.write(text + "\n")
            self._proc.stdin.flush()
        except OSError:
            pass
        self._append("› (enviado)\n")

    def _finish(self, code: int) -> bool:
        if code == 0:
            self.status_label.set_label("✓ Completado correctamente")
        else:
            self.status_label.set_label(f"✗ Terminó con errores (código {code})")
        self._proc = None
        self.entry.set_sensitive(False)
        if self._on_done:
            self._on_done(code == 0)
        return False


class PowerzoidManagerWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, default_width=560, default_height=680)
        self.extensions: list[Extension] = []
        self.install_all_check: Gtk.CheckButton | None = None
        self.remove_all_check: Gtk.CheckButton | None = None
        self._rows: dict[str, Adw.ActionRow] = {}
        self._suffixes: dict[str, Gtk.Box] = {}

        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(title="PowerZoid Manager")
        header.set_title_widget(self.window_title)
        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Buscar actualizaciones")
        refresh_btn.connect("clicked", lambda *_: self.refresh(pull=True))
        header.pack_end(refresh_btn)
        self.update_all_btn = Gtk.Button(label="Actualizar todas")
        self.update_all_btn.add_css_class("suggested-action")
        self.update_all_btn.connect("clicked", self._on_update_all_clicked)
        self.update_all_btn.set_visible(False)
        header.pack_end(self.update_all_btn)
        toolbar_view.add_top_bar(header)

        self.status_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
            margin_top=8,
            margin_bottom=8,
            margin_start=14,
            margin_end=14,
        )
        self.status_label = Gtk.Label(label="Buscando actualizaciones…", xalign=0)
        self.status_progress = Gtk.ProgressBar(hexpand=True, valign=Gtk.Align.CENTER)
        self.status_box.append(self.status_label)
        self.status_box.append(self.status_progress)
        self.status_box.set_visible(False)
        toolbar_view.add_top_bar(self.status_box)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        clamp = Adw.Clamp(maximum_size=640, margin_top=16, margin_bottom=16, margin_start=12, margin_end=12)
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        clamp.set_child(self.content_box)
        scroller.set_child(clamp)
        toolbar_view.set_content(scroller)

        self.set_content(toolbar_view)

        self.refresh(pull=True)

    # ---------------------------------------------------------------- scan

    def refresh(self, pull: bool = False) -> None:
        self._rebuild()
        if not pull:
            return

        repos = sorted({e.repo_path for e in self.extensions if (e.repo_path / ".git").is_dir()})
        total = len(repos)
        if total == 0:
            return

        self.status_label.set_label("Buscando actualizaciones…")
        self.status_progress.set_fraction(0.0)
        self.status_box.set_visible(True)

        def worker():
            for i, repo in enumerate(repos, start=1):
                git_pull(repo)
                commit = read_repo_commit(repo)
                GLib.idle_add(self._on_repo_pulled, repo, commit, i, total)
            GLib.idle_add(self._on_pull_done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_repo_pulled(self, repo: Path, commit: str | None, done: int, total: int) -> bool:
        self.status_progress.set_fraction(done / total)

        meta_path = find_metadata(repo)
        meta = None
        if meta_path is not None:
            try:
                meta = json.loads(meta_path.read_text())
            except (json.JSONDecodeError, OSError):
                meta = None

        for ext in self.extensions:
            if ext.repo_path != repo:
                continue
            ext.source_commit = commit
            if meta:
                ext.source_version = meta.get("version", ext.source_version)
            self._refresh_row_suffix(ext)
        return False

    def _on_pull_done(self) -> bool:
        self.status_box.set_visible(False)
        return False

    def _refresh_row_suffix(self, ext: Extension) -> None:
        row = self._rows.get(ext.uuid)
        if row is None:
            return
        old_suffix = self._suffixes.get(ext.uuid)
        if old_suffix is not None:
            old_suffix.unparent()
        new_suffix = self._build_suffix(ext)
        row.add_suffix(new_suffix)
        self._suffixes[ext.uuid] = new_suffix

    def _rebuild(self) -> None:
        self.extensions = discover_extensions()
        self._rows = {}
        self._suffixes = {}

        child = self.content_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.content_box.remove(child)
            child = next_child

        if not self.extensions:
            self.window_title.set_subtitle("")
            status = Adw.StatusPage(
                title="No se encontraron extensiones PowerZoid",
                description=f"No hay repositorios powerzoid-* con metadata.json en {REPOS_DIR}",
                icon_name="folder-symbolic",
            )
            self.content_box.append(status)
            return

        installed = [e for e in self.extensions if e.is_installed]
        not_installed = [e for e in self.extensions if not e.is_installed]
        outdated = [e for e in self.extensions if e.has_update]
        # Purrr no es una extensión GNOME: este manager la actualiza pero no la
        # instala ni la elimina, así que queda fuera de esos flujos masivos.
        removable_installed = [e for e in installed if e.uuid != PURRR_UUID]

        self.window_title.set_subtitle(
            f"{len(installed)} instalada(s) de {len(self.extensions)}"
            if installed
            else "Ninguna instalada — elige cuáles instalar"
        )

        self.update_all_btn.set_label(f"Actualizar todas ({len(outdated)})")
        self.update_all_btn.set_visible(bool(outdated))
        self.update_all_btn.set_sensitive(True)

        group = Adw.PreferencesGroup(title="Extensiones PowerZoid")
        for ext in self.extensions:
            group.add(self._build_row(ext))
        self.content_box.append(group)

        bulk_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=4)

        self.install_all_check = Gtk.CheckButton(
            label=f"Instalar todas las no instaladas ({len(not_installed)})"
        )
        self.install_all_check.set_visible(bool(not_installed))
        self.install_all_check.connect("toggled", self._on_install_all)
        bulk_box.append(self.install_all_check)

        self.remove_all_check = Gtk.CheckButton(
            label=f"Eliminar todas las instaladas ({len(removable_installed)})"
        )
        self.remove_all_check.set_visible(bool(removable_installed))
        self.remove_all_check.connect("toggled", self._on_remove_all)
        bulk_box.append(self.remove_all_check)

        if not_installed or installed:
            self.content_box.append(bulk_box)

    def _build_row(self, ext: Extension) -> Adw.ActionRow:
        row = Adw.ActionRow(title=ext.name, subtitle=ext.description)
        row.set_title_lines(1)
        row.set_subtitle_lines(2)

        icon = Gtk.Image.new_from_icon_name(ICON_BY_UUID.get(ext.uuid, DEFAULT_ICON))
        icon.set_pixel_size(24)
        row.add_prefix(icon)

        suffix = self._build_suffix(ext)
        row.add_suffix(suffix)

        self._rows[ext.uuid] = row
        self._suffixes[ext.uuid] = suffix
        return row

    def _build_suffix(self, ext: Extension) -> Gtk.Box:
        suffix = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, valign=Gtk.Align.CENTER)
        is_purrr = ext.uuid == PURRR_UUID

        if ext.is_installed:
            if ext.has_update:
                if (
                    isinstance(ext.source_version, int)
                    and isinstance(ext.installed_version, int)
                    and ext.source_version > ext.installed_version
                ):
                    label = f"v{ext.installed_version} → v{ext.source_version}"
                elif is_purrr:
                    label = "actualización disponible"
                else:
                    label = f"v{ext.installed_version} (actualización disponible)"
                status = Gtk.Label(label=label)
                status.add_css_class("warning")
            elif is_purrr:
                status = Gtk.Label(label="al día")
                status.add_css_class("dim-label")
            else:
                status = Gtk.Label(label=f"v{ext.installed_version}")
                status.add_css_class("dim-label")
            suffix.append(status)

        if is_purrr:
            # No es una extensión GNOME: este manager solo la actualiza, no la
            # instala ni la elimina.
            if ext.has_update:
                update_btn = Gtk.Button(label="Actualizar")
                update_btn.add_css_class("suggested-action")
                update_btn.connect("clicked", lambda *_, e=ext: self._do_install(e))
                suffix.append(update_btn)
        elif not ext.is_installed:
            install_btn = Gtk.Button(label="Instalar")
            install_btn.add_css_class("suggested-action")
            install_btn.connect("clicked", lambda *_, e=ext: self._do_install(e))
            suffix.append(install_btn)
        else:
            if ext.has_update:
                update_btn = Gtk.Button(label="Actualizar")
                update_btn.add_css_class("suggested-action")
                update_btn.connect("clicked", lambda *_, e=ext: self._do_install(e))
                suffix.append(update_btn)

            del_btn = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Eliminar")
            del_btn.add_css_class("destructive-action")
            del_btn.connect("clicked", lambda *_, e=ext: self._confirm_remove_one(e))
            suffix.append(del_btn)

        return suffix

    # ------------------------------------------------------------ confirm

    def _confirm(self, heading: str, body: str, ok_label: str, destructive: bool, on_ok, on_cancel=None) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("ok", ok_label)
        dialog.set_response_appearance(
            "ok", Adw.ResponseAppearance.DESTRUCTIVE if destructive else Adw.ResponseAppearance.SUGGESTED
        )
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def _on_response(d, result):
            response = d.choose_finish(result)
            if response == "ok":
                on_ok()
            elif on_cancel:
                on_cancel()

        dialog.choose(self, None, _on_response)

    # ---------------------------------------------------------- one-by-one

    def _do_install(self, ext: Extension) -> None:
        if ext.install_script:
            action = "Actualizando" if ext.has_update else "Instalando"

            def on_done(ok: bool) -> None:
                if ok:
                    write_installed_commit(installed_commit_marker(ext.uuid), read_repo_commit(ext.repo_path))
                self.refresh(pull=False)

            dlg = RunDialog(f"{action} {ext.name}", ext.install_script, on_done=on_done)
            dlg.present(self)
        else:
            def worker():
                error = None
                try:
                    generic_install(ext)
                    write_installed_commit(installed_commit_marker(ext.uuid), read_repo_commit(ext.repo_path))
                except OSError as exc:
                    error = str(exc)
                GLib.idle_add(self._on_generic_done, error)

            threading.Thread(target=worker, daemon=True).start()

    def _on_generic_done(self, error: str | None) -> bool:
        self._rebuild()
        if error:
            self._show_info("No se pudo completar la acción", error)
        return False

    def _confirm_remove_one(self, ext: Extension) -> None:
        self._confirm(
            heading=f"¿Eliminar {ext.name}?",
            body=(
                "Se desactivará y eliminará la extensión de GNOME Shell"
                + (" y su servicio en segundo plano" if ext.uninstall_script else "")
                + ". Esta acción no se puede deshacer."
            ),
            ok_label="Eliminar",
            destructive=True,
            on_ok=lambda: self._do_remove(ext),
        )

    def _do_remove(self, ext: Extension) -> None:
        if ext.uninstall_script:
            dlg = RunDialog(f"Eliminando {ext.name}", ext.uninstall_script, on_done=lambda ok: self.refresh(pull=False))
            dlg.present(self)
        else:
            def worker():
                error = None
                try:
                    generic_uninstall(ext)
                except OSError as exc:
                    error = str(exc)
                GLib.idle_add(self._on_generic_done, error)

            threading.Thread(target=worker, daemon=True).start()

    # --------------------------------------------------------------- bulk

    def _on_install_all(self, check: Gtk.CheckButton) -> None:
        if not check.get_active():
            return
        pending = [e for e in self.extensions if not e.is_installed]
        if not pending:
            check.set_active(False)
            return
        names = ", ".join(e.name for e in pending)
        self._confirm(
            heading="Instalar todas",
            body=f"Se instalarán {len(pending)} extensiones: {names}.",
            ok_label="Instalar todas",
            destructive=False,
            on_ok=lambda: self._run_bulk(
                pending,
                install=True,
                on_finish=lambda: self._reset_bulk_check(check),
                check=check,
                verb="Instalando",
            ),
            on_cancel=lambda: check.set_active(False),
        )

    def _on_remove_all(self, check: Gtk.CheckButton) -> None:
        if not check.get_active():
            return
        installed = [e for e in self.extensions if e.is_installed and e.uuid != PURRR_UUID]
        if not installed:
            check.set_active(False)
            return
        names = ", ".join(e.name for e in installed)
        self._confirm(
            heading="Eliminar todas",
            body=f"Se eliminarán {len(installed)} extensiones instaladas: {names}. Esta acción no se puede deshacer.",
            ok_label="Eliminar todas",
            destructive=True,
            on_ok=lambda: self._run_bulk(
                installed,
                install=False,
                on_finish=lambda: self._reset_bulk_check(check),
                check=check,
                verb="Eliminando",
            ),
            on_cancel=lambda: check.set_active(False),
        )

    def _reset_bulk_check(self, check: Gtk.CheckButton) -> None:
        check.set_active(False)
        check.set_sensitive(True)

    def _on_update_all_clicked(self, *_args) -> None:
        outdated = [e for e in self.extensions if e.has_update]
        if not outdated:
            return
        names = ", ".join(e.name for e in outdated)
        self._confirm(
            heading="Actualizar todas",
            body=f"Se actualizarán {len(outdated)} extensiones: {names}.",
            ok_label="Actualizar todas",
            destructive=False,
            on_ok=lambda: self._run_bulk(
                outdated, install=True, on_finish=None, check=self.update_all_btn, verb="Actualizando"
            ),
        )

    def _run_bulk(
        self,
        items: list[Extension],
        install: bool,
        on_finish,
        check: Gtk.Widget | None = None,
        verb: str = "Procesando",
    ) -> None:
        if check is not None:
            check.set_sensitive(False)

        total = len(items)
        self.status_label.set_label(f"{verb} 0/{total}…")
        self.status_progress.set_fraction(0.0)
        self.status_box.set_visible(True)

        def worker():
            failures: list[str] = []
            for i, ext in enumerate(items, start=1):
                ok = True
                try:
                    script = ext.install_script if install else ext.uninstall_script
                    if script is not None:
                        try:
                            result = subprocess.run(
                                ["bash", str(script)],
                                cwd=str(script.parent),
                                stdin=subprocess.DEVNULL,
                                capture_output=True,
                                timeout=SCRIPT_TIMEOUT,
                                check=False,
                            )
                            ok = result.returncode == 0
                        except (subprocess.TimeoutExpired, OSError):
                            ok = False
                        if install and ok:
                            write_installed_commit(installed_commit_marker(ext.uuid), read_repo_commit(ext.repo_path))
                    else:
                        (generic_install if install else generic_uninstall)(ext)
                        if install:
                            write_installed_commit(installed_commit_marker(ext.uuid), read_repo_commit(ext.repo_path))
                except OSError:
                    # No dejamos que una extensión rota (p. ej. un symlink de desarrollo
                    # que rompe la copia) tumbe el hilo y deje sin procesar al resto.
                    ok = False
                if not ok:
                    failures.append(ext.name)
                GLib.idle_add(self._on_bulk_item_done, ext, i, total, verb)
            GLib.idle_add(self._finish_bulk, on_finish, failures)

        threading.Thread(target=worker, daemon=True).start()

    def _on_bulk_item_done(self, ext: Extension, done: int, total: int, verb: str) -> bool:
        self.status_progress.set_fraction(done / total)
        self.status_label.set_label(f"{verb} {done}/{total}: {ext.name}")
        ext.installed_version = read_installed_version(ext.uuid)
        ext.installed_commit = read_installed_commit(installed_commit_marker(ext.uuid))
        self._refresh_row_suffix(ext)
        return False

    def _finish_bulk(self, on_finish, failures: list[str]) -> bool:
        self.status_box.set_visible(False)
        if on_finish:
            on_finish()
        self._rebuild()
        if failures:
            self._show_info(
                heading="Algunas extensiones no se pudieron procesar",
                body="Fallaron: " + ", ".join(failures) + ". Prueba con esa extensión individualmente para ver el error.",
            )
        return False

    def _show_info(self, heading: str, body: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("ok", "Entendido")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.present(self)


class PowerzoidManagerApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self) -> None:
        win = self.props.active_window
        if not win:
            win = PowerzoidManagerWindow(self)
        win.present()


def main() -> None:
    app = PowerzoidManagerApp()
    app.run(None)


if __name__ == "__main__":
    main()
