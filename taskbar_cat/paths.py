"""Pfade: XDG-Verzeichnisse und mitgelieferte Dateien (rein, ohne Qt)."""
import os
from importlib import resources
from pathlib import Path

APP = "taskbar-cat"
SENSOR_JS = "taskbar-cat-sensor.js"


def _xdg(var: str, fallback: str) -> Path:
    base = os.environ.get(var, "")
    return (Path(base) if os.path.isabs(base) else Path.home() / fallback) / APP


def data_dir() -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share")


def cache_dir() -> Path:
    return _xdg("XDG_CACHE_HOME", ".cache")


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config")


def config_file() -> Path:
    return config_dir() / "config.json"


def autostart_file() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME", "")
    root = Path(base) if os.path.isabs(base) else Path.home() / ".config"
    return root / "autostart" / "taskbar-cat.desktop"


def state_file() -> Path:
    return data_dir() / "state.json"


def furniture_file() -> Path:
    return data_dir() / "furniture.json"


def bigtree_variants_file() -> Path:
    """Gespeicherte Varianten großer Kratzbäume (Sammlung)."""
    return data_dir() / "bigtree-favorites.json"


def resource_file(*parts: str) -> Path:
    """Mitgelieferte Datei als echter Pfad.

    KWin (loadScript) und QQmlComponent brauchen Dateipfade, keine Streams. Liegt
    das Paket als Zip im Import-Pfad, wird die Datei einmalig in den Cache entpackt.
    """
    res = resources.files(__package__).joinpath(*parts)
    try:
        direct = Path(os.fspath(res))
    except TypeError:  # Zip-Import: kein Dateisystempfad
        direct = None
    if direct is not None and direct.is_file():
        return direct
    text = res.read_text(encoding="utf-8")
    out = cache_dir() / parts[-1]
    if not out.is_file() or out.read_text(encoding="utf-8") != text:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    return out


def sensor_script() -> Path:
    return resource_file("kwin", SENSOR_JS)
