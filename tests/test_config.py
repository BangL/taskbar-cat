from dataclasses import fields

from taskbar_cat.config import SPECS, Config


def test_every_field_has_a_spec():
    assert {f.name for f in fields(Config)} == set(SPECS)


def test_derived_values():
    c = Config()
    assert c.sprite_px == 96
    assert c.satiety_decay == 100 / (8 * 3600)
    assert c.affection_decay == 100 / (4 * 3600)
    c.set("sprite_scale", 2)
    assert c.sprite_px == 64


def test_set_clamps_to_spec():
    c = Config()
    c.set("walk_speed", 10_000)
    assert c.walk_speed == SPECS["walk_speed"].hi
    c.set("walk_speed", -50)
    assert c.walk_speed == SPECS["walk_speed"].lo
    c.set("sprite_scale", 3.7)
    assert c.sprite_scale == 4 and isinstance(c.sprite_scale, int)
    c.set("play_enabled", 0)
    assert c.play_enabled is False


def test_roundtrip_and_bad_values():
    c = Config()
    c.set("satiety_hours", 12)
    back = Config.from_dict({**c.to_dict(), "unbekannt": 1, "walk_speed": "keine Zahl"})
    assert back.satiety_hours == 12
    assert back.walk_speed == c.walk_speed


def test_defaults_when_file_had_nothing():
    assert Config.from_dict({}) == Config()
