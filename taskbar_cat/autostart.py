"""Autostart-Eintrag in ~/.config/autostart verwalten (rein, ohne Qt)."""
import os
import shutil
import sys
from pathlib import Path

from . import paths

MARKER = "X-TaskbarCat-Generated=true"


def _start_command() -> tuple[str, str | None]:
    """(Exec-Zeile, Path-Zeile): installiertes Startprogramm, sonst Modulstart aus dem Quellbaum."""
    binary = shutil.which("taskbar-cat")
    if binary:
        return f"Exec={binary}", None
    root = Path(__file__).resolve().parent.parent
    return f"Exec={sys.executable} -m taskbar_cat", f"Path={root}"


def entry_text() -> str:
    """Desktop-Eintrag aus der mitgelieferten Vorlage, mit passendem Startkommando."""
    exec_line, path_line = _start_command()
    template = paths.resource_file("data", "taskbar-cat.desktop").read_text(encoding="utf-8")
    lines = [exec_line if line.startswith("Exec=") else line
             for line in template.splitlines() if not line.startswith("Path=")]
    if path_line:
        lines.append(path_line)
    lines.append(MARKER)
    return "\n".join(lines) + "\n"


def is_enabled() -> bool:
    return paths.autostart_file().is_file()


def enable() -> None:
    f = paths.autostart_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(entry_text(), encoding="utf-8")
    os.replace(tmp, f)


def disable() -> None:
    try:
        paths.autostart_file().unlink()
    except FileNotFoundError:
        pass


def set_enabled(on: bool) -> bool:
    """Schaltet den Autostart; gibt den Zustand danach zurück (False bei Fehler)."""
    try:
        enable() if on else disable()
    except OSError as e:
        print(f"taskbar-cat: Autostart nicht geändert: {e}", file=sys.stderr)
    return is_enabled()
