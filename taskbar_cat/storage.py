"""Zustand und Einstellungen als JSON laden/speichern."""
import json
import os
import sys
import time
from pathlib import Path

from .bigtree import valid_variant
from .config import Config
from .furniture import Furniture
from .needs import Needs


def _move_aside(path: Path) -> None:
    broken = path.with_name(f"{path.name}.broken-{int(time.time())}")
    try:
        path.rename(broken)
    except OSError:
        pass
    print(f"taskbar-cat: {path} unlesbar, verschoben nach {broken}", file=sys.stderr)


def read_dict(path: Path) -> dict:
    """Inhalt als dict; fehlt die Datei oder ist sie kaputt (dann beiseitegelegt), kommt {}."""
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        data = None
    if not isinstance(data, dict):
        _move_aside(path)
        return {}
    return data


def load(path: Path) -> Needs:
    return Needs.from_dict(read_dict(path))


def load_config(path: Path) -> Config:
    return Config.from_dict(read_dict(path))


def load_furniture(path: Path) -> Furniture:
    return Furniture.from_dict(read_dict(path))


def load_variants(path: Path) -> list[dict]:
    """Gespeicherte Kratzbaum-Varianten; kaputte Einträge fallen weg."""
    return [v for v in read_dict(path).get("favorites", []) if valid_variant(v)]


def save_variants(path: Path, variants: list[dict]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"favorites": variants}, indent=2, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    except OSError as e:
        print(f"taskbar-cat: Speichern fehlgeschlagen: {e}", file=sys.stderr)
        return False
    return True


def save(path: Path, obj: Needs | Config | Furniture) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj.to_dict(), indent=2))
    os.replace(tmp, path)


def try_save(path: Path, obj: Needs | Config | Furniture) -> bool:
    try:
        save(path, obj)
    except OSError as e:
        print(f"taskbar-cat: Speichern fehlgeschlagen: {e}", file=sys.stderr)
        return False
    return True
