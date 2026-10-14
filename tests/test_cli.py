import pytest

from taskbar_cat import __version__, bus, sprites
from taskbar_cat.__main__ import parse_args


def test_default_has_no_debug():
    assert parse_args(["taskbar-cat"]).debug is False


def test_debug_flag():
    assert parse_args(["taskbar-cat", "--debug"]).debug is True


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as e:
        parse_args(["taskbar-cat", "--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "--debug" in out and "Tamagotchi" in out


def test_version_prints_version(capsys):
    with pytest.raises(SystemExit) as e:
        parse_args(["taskbar-cat", "--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_unknown_option_fails(capsys):
    with pytest.raises(SystemExit) as e:
        parse_args(["taskbar-cat", "--katze"])
    assert e.value.code == 2
    assert "--katze" in capsys.readouterr().err


def test_bus_without_dump_shows_help(capsys):
    assert bus._main(["bus"]) == 2
    assert "--dump" in capsys.readouterr().out


def test_sprites_requires_a_target(capsys):
    with pytest.raises(SystemExit) as e:
        sprites._cli(["sprites"])
    assert e.value.code == 2
    assert "--icon" in capsys.readouterr().err


def test_sprites_icon_options(tmp_path, qapp):
    out = tmp_path / "icon.png"
    assert sprites._cli(["sprites", "--icon", str(out), "--size", "32", "--mood", "sick"]) == 0
    assert out.is_file()


def test_sprites_rejects_both_targets(capsys):
    with pytest.raises(SystemExit) as e:
        sprites._cli(["sprites", "--icon", "a.png", "--atlas", "b.png"])
    assert e.value.code == 2
