"""Backend-Auswahl: einmal beim Start, danach ist der Rest plattformunabhängig.

``TASKBAR_CAT_BACKEND=kde|gnome`` erzwingt eine Wahl (zum Testen).
"""
import os

from .base import Backend
from .gnome import GnomeBackend
from .kde import KdeBackend

BACKENDS: tuple[type[Backend], ...] = (KdeBackend, GnomeBackend)


def by_name(name: str) -> type[Backend] | None:
    return next((b for b in BACKENDS if b.name == name.strip().lower()), None)


def choose(env: dict | None = None) -> type[Backend]:
    """Backend-Klasse für diese Sitzung, nur aus der Umgebung bestimmt.

    Qt darf dabei noch nicht laufen: QT_QPA_PLATFORM muss vor der QApplication
    stehen. Unbekannte Arbeitsumgebungen entscheiden nach Sitzungsart - unter
    Wayland ist Layer-Shell der verbreitete Weg (sway, Hyprland), unter X11 das
    frei platzierbare Fenster.
    """
    env = os.environ if env is None else env
    forced = env.get("TASKBAR_CAT_BACKEND", "")
    if forced:
        chosen = by_name(forced)
        if chosen is not None:
            return chosen
        print(f"taskbar-cat: unbekanntes Backend {forced!r}, erkenne selbst")
    desktops = {d.strip().upper() for d in env.get("XDG_CURRENT_DESKTOP", "").split(":") if d.strip()}
    if "KDE" in desktops:
        return KdeBackend
    if desktops & {"GNOME", "GNOME-CLASSIC", "GNOME-FLASHBACK", "UNITY", "CINNAMON", "X-CINNAMON"}:
        return GnomeBackend
    if env.get("WAYLAND_DISPLAY"):
        return KdeBackend
    return GnomeBackend


def create(connection=None, env: dict | None = None) -> Backend:
    return choose(env)(connection)


def prepare_qt(env: dict | None = None) -> type[Backend]:
    """Backend wählen und QT_QPA_PLATFORM setzen. Vor der QApplication aufrufen."""
    env = os.environ if env is None else env
    chosen = choose(env)
    if chosen.qt_platform and not env.get("QT_QPA_PLATFORM"):
        env["QT_QPA_PLATFORM"] = chosen.qt_platform
    return chosen
