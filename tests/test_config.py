from dataclasses import fields

from taskbar_cat.config import SPECS, Config


def test_every_field_has_a_spec():
    # blocked_outputs ist die Ausnahme: die Auswahl kommt aus den vorhandenen Monitoren
    assert {f.name for f in fields(Config)} - {"blocked_outputs"} == set(SPECS)


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


def test_blocked_outputs_normalised():
    c = Config()
    c.set("blocked_outputs", ["DP-2", "DP-1", "DP-1"])
    assert c.blocked_outputs == ["DP-1", "DP-2"]
    assert not c.allows("DP-1") and c.allows("HDMI-A-1")
    assert Config.from_dict(c.to_dict()).blocked_outputs == ["DP-1", "DP-2"]


def test_blocked_outputs_rejects_junk():
    c = Config()
    for junk in ("DP-1", 5, None):
        assert Config.from_dict({"blocked_outputs": junk}).blocked_outputs == []
