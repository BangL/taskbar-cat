"""Zustand der Katze als JSON laden/speichern."""
import json
import os
import sys
import time
from pathlib import Path

from .needs import Needs


def load(path: Path) -> Needs:
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return Needs()
    except (OSError, ValueError):
        data = None
    if not isinstance(data, dict):
        broken = path.with_name(f"{path.name}.broken-{int(time.time())}")
        try:
            path.rename(broken)
        except OSError:
            pass
        print(f"taskbar-cat: {path} unlesbar, verschoben nach {broken}", file=sys.stderr)
        return Needs()
    return Needs.from_dict(data)


def save(path: Path, needs: Needs) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(needs.to_dict(), indent=2))
    os.replace(tmp, path)


def try_save(path: Path, needs: Needs) -> bool:
    try:
        save(path, needs)
    except OSError as e:
        print(f"taskbar-cat: Speichern fehlgeschlagen: {e}", file=sys.stderr)
        return False
    return True
