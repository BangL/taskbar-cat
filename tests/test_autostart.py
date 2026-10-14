import shutil

from taskbar_cat import autostart, paths


def test_enable_creates_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert autostart.is_enabled() is False
    assert autostart.set_enabled(True) is True
    f = paths.autostart_file()
    assert f.is_file()
    text = f.read_text()
    assert "Exec=" in text and autostart.MARKER in text and "Type=Application" in text


def test_disable_removes_entry_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    autostart.enable()
    assert autostart.set_enabled(False) is False
    assert not paths.autostart_file().exists()
    autostart.disable()  # zweites Mal wirft nicht


def test_uses_installed_binary(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/taskbar-cat")
    text = autostart.entry_text()
    assert "Exec=/usr/bin/taskbar-cat" in text
    assert "Path=" not in text


def test_falls_back_to_module_start(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(shutil, "which", lambda _: None)
    text = autostart.entry_text()
    assert "-m taskbar_cat" in text
    assert "Path=" in text
