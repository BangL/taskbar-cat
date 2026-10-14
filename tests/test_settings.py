from taskbar_cat.config import Config
from taskbar_cat.ui.settings import GROUPS, SettingsDialog


def test_groups_cover_all_fields():
    shown = [n for _, names in GROUPS for n in names]
    assert sorted(shown) == sorted(Config().to_dict())
    assert len(shown) == len(set(shown))


def test_widgets_write_through_and_signal(qapp):
    cfg = Config()
    dlg = SettingsDialog(cfg)
    seen = []
    dlg.changed.connect(seen.append)
    dlg._widgets["walk_speed"].setValue(120)
    dlg._widgets["play_enabled"].setChecked(False)
    assert (cfg.walk_speed, cfg.play_enabled) == (120, False)
    assert seen == ["walk_speed", "play_enabled"]


def test_restore_defaults(qapp):
    cfg = Config()
    dlg = SettingsDialog(cfg)
    dlg._widgets["satiety_hours"].setValue(40)
    dlg.restore_defaults()
    assert cfg == Config()
    assert dlg._widgets["satiety_hours"].value() == Config().satiety_hours
