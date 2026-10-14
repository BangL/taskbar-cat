from pathlib import Path

from taskbar_cat import paths


def test_xdg_env_is_honored(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "d"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "c"))
    assert paths.data_dir() == tmp_path / "d/taskbar-cat"
    assert paths.cache_dir() == tmp_path / "c/taskbar-cat"
    assert paths.state_file() == tmp_path / "d/taskbar-cat/state.json"


def test_relative_xdg_falls_back_to_home(monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", "relativ/ungueltig")
    assert paths.data_dir() == Path.home() / ".local/share/taskbar-cat"


def test_sensor_script_is_a_readable_file():
    p = paths.sensor_script()
    assert p.is_file() and p.name == paths.SENSOR_JS
    assert "de.bangl.TaskbarCat" in p.read_text()


def test_overlay_qml_is_shipped():
    assert paths.resource_file("ui", "overlay.qml").is_file()


def test_resource_unpacks_when_not_on_disk(tmp_path, monkeypatch):
    """Zip-Import: Datei landet im Cache und ist dort ein echter Pfad."""
    class _Zipish:
        def __init__(self, text):
            self._text = text

        def joinpath(self, *parts):
            return self

        def __fspath__(self):
            raise TypeError("kein Dateisystempfad")

        def read_text(self, encoding=None):
            return self._text

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(paths.resources, "files", lambda pkg: _Zipish("// sensor"))
    out = paths.sensor_script()
    assert out == tmp_path / "taskbar-cat" / paths.SENSOR_JS
    assert out.read_text() == "// sensor"
    assert paths.sensor_script() == out  # zweiter Aufruf nutzt die Datei weiter
