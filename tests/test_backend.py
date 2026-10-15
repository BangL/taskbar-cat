"""Backend-Wahl: einmal beim Start, nur aus der Umgebung."""
import pytest

from taskbar_cat import backend as backends, paths
from taskbar_cat.backend.gnome import GnomeBackend
from taskbar_cat.backend.kde import KdeBackend


@pytest.mark.parametrize("env, expected", [
    ({"XDG_CURRENT_DESKTOP": "KDE"}, KdeBackend),
    ({"XDG_CURRENT_DESKTOP": "GNOME"}, GnomeBackend),
    ({"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}, GnomeBackend),
    ({"XDG_CURRENT_DESKTOP": "X-Cinnamon"}, GnomeBackend),
    # Unbekannt: unter Wayland Layer-Shell (sway, Hyprland), unter X11 freies Fenster
    ({"XDG_CURRENT_DESKTOP": "sway", "WAYLAND_DISPLAY": "wayland-0"}, KdeBackend),
    ({"XDG_CURRENT_DESKTOP": "", "DISPLAY": ":0"}, GnomeBackend),
    ({}, GnomeBackend),
])
def test_choose(env, expected):
    assert backends.choose(env) is expected


def test_forced_backend_wins():
    env = {"XDG_CURRENT_DESKTOP": "GNOME", "TASKBAR_CAT_BACKEND": "kde"}
    assert backends.choose(env) is KdeBackend


def test_unknown_forced_backend_falls_back_to_detection():
    env = {"XDG_CURRENT_DESKTOP": "GNOME", "TASKBAR_CAT_BACKEND": "quatsch"}
    assert backends.choose(env) is GnomeBackend


def test_prepare_qt_sets_the_platform_plugin():
    env = {"XDG_CURRENT_DESKTOP": "GNOME"}
    assert backends.prepare_qt(env) is GnomeBackend
    assert env["QT_QPA_PLATFORM"] == "xcb"


def test_prepare_qt_keeps_an_explicit_platform():
    env = {"XDG_CURRENT_DESKTOP": "GNOME", "QT_QPA_PLATFORM": "offscreen"}
    backends.prepare_qt(env)
    assert env["QT_QPA_PLATFORM"] == "offscreen"


def test_kde_leaves_the_platform_to_qt():
    env = {"XDG_CURRENT_DESKTOP": "KDE"}
    backends.prepare_qt(env)
    assert "QT_QPA_PLATFORM" not in env


def test_backends_name_their_own_overlay_shell():
    assert KdeBackend.overlay_qml != GnomeBackend.overlay_qml


def test_install_extension_copies_and_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert GnomeBackend.install_extension() is True     # erstes Mal: kopiert
    target = tmp_path / "gnome-shell/extensions" / paths.EXTENSION_UUID
    assert (target / "extension.js").is_file() and (target / "metadata.json").is_file()
    assert GnomeBackend.install_extension() is False    # unverändert: nichts zu tun


def test_install_extension_replaces_old_code(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    GnomeBackend.install_extension()
    js = tmp_path / "gnome-shell/extensions" / paths.EXTENSION_UUID / "extension.js"
    js.write_text("// alte Fassung", encoding="utf-8")
    assert GnomeBackend.install_extension() is True
    assert "de.bangl.TaskbarCat" in js.read_text(encoding="utf-8")


def test_remove_extension(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    GnomeBackend.install_extension()
    GnomeBackend.remove_extension()
    assert not (tmp_path / "gnome-shell/extensions" / paths.EXTENSION_UUID).exists()


def test_remove_extension_without_install_is_quiet(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    GnomeBackend.remove_extension()
