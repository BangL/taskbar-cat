from taskbar_cat import storage
from taskbar_cat.config import Config
from taskbar_cat.needs import Needs


def test_missing_file_gives_defaults(tmp_path):
    assert storage.load(tmp_path / "state.json") == Needs()


def test_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    n = Needs(satiety=12, affection=34, energy=56)
    storage.save(p, n)
    assert storage.load(p) == n


def test_broken_file_is_moved_aside(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("{nope")
    assert storage.load(p) == Needs()
    assert not p.exists()
    assert len(list(tmp_path.glob("state.json.broken-*"))) == 1


def test_non_dict_is_broken(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("[1, 2]")
    assert storage.load(p) == Needs()
    assert len(list(tmp_path.glob("state.json.broken-*"))) == 1


def test_save_creates_dir(tmp_path):
    p = tmp_path / "a" / "b" / "state.json"
    storage.save(p, Needs())
    assert p.exists()


def test_try_save_swallows_errors(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert storage.try_save(blocker / "state.json", Needs()) is False
    assert storage.try_save(tmp_path / "ok.json", Needs()) is True


def test_config_roundtrip(tmp_path):
    cfg = Config()
    cfg.set("walk_speed", 90)
    cfg.set("debug_lines", True)
    path = tmp_path / "config.json"
    assert storage.try_save(path, cfg)
    assert storage.load_config(path) == cfg


def test_broken_config_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{kaputt")
    assert storage.load_config(path) == Config()
    assert not path.exists()
    assert list(tmp_path.glob("config.json.broken-*"))
