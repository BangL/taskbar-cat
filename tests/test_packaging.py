"""Paketierung: was im Baum liegt, muss auch im Wheel landen."""
from pathlib import Path

import pytest

tomllib = pytest.importorskip("tomllib")   # erst ab Python 3.11 (Ubuntu 22.04: 3.10)

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "taskbar_cat"


def _pyproject() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)


def test_every_python_package_is_listed():
    """Ein vergessenes Unterpaket fehlt sonst still im Wheel und bricht erst beim Start."""
    found = {"taskbar_cat"} | {
        f"taskbar_cat.{d.relative_to(PACKAGE).as_posix().replace('/', '.')}"
        for d in PACKAGE.rglob("*")
        if d.is_dir() and (d / "__init__.py").is_file() and "__pycache__" not in d.parts}
    assert found <= set(_pyproject()["tool"]["setuptools"]["packages"])


def test_shipped_data_files_are_covered_by_package_data():
    """Sensoren, QML und Desktop-Vorlage liegen in Verzeichnissen ohne __init__.py."""
    patterns = _pyproject()["tool"]["setuptools"]["package-data"]["taskbar_cat"]
    needed = [Path(p).relative_to("taskbar_cat").as_posix()
              for p in ("taskbar_cat/kwin/taskbar-cat-sensor.js",
                        "taskbar_cat/gnome/extension.js",
                        "taskbar_cat/gnome/metadata.json",
                        "taskbar_cat/ui/CatScene.qml",
                        "taskbar_cat/ui/overlay.qml",
                        "taskbar_cat/ui/overlay_x11.qml",
                        "taskbar_cat/data/taskbar-cat.desktop")]
    for name in needed:
        assert (PACKAGE / name).is_file(), f"fehlt im Baum: {name}"
        assert any(Path(name).match(p) for p in patterns), f"nicht im Wheel: {name}"
