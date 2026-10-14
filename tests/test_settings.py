import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog, QDialogButtonBox

from taskbar_cat.config import SPECS, Config
from taskbar_cat.ui.settings import GROUPS, SettingsDialog


@pytest.fixture
def pick(monkeypatch):
    """Farbwähler durch eine feste Antwort ersetzen."""
    def choose(color):
        monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor(color)))
    return choose

SCREENS = [("DP-3", "DP-3 - 1920x1080 bei (0, 0)"), ("DP-4", "DP-4 - 1920x1080 bei (1920, 0)")]


def test_groups_cover_all_fields():
    shown = [n for _, names in GROUPS for n in names]
    assert sorted(shown) == sorted(SPECS)
    assert len(shown) == len(set(shown))
    # blocked_outputs steht nicht in SPECS: die Haken entstehen erst aus den Monitoren
    assert sorted(shown + ["blocked_outputs"]) == sorted(Config().to_dict())


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


def test_monitor_boxes_write_blocked_list(qapp):
    cfg = Config()
    dlg = SettingsDialog(cfg, screens=SCREENS)
    seen = []
    dlg.changed.connect(seen.append)
    dlg._screens["DP-4"].setChecked(False)
    assert cfg.blocked_outputs == ["DP-4"]
    assert seen == ["blocked_outputs"]
    dlg._screens["DP-4"].setChecked(True)
    assert cfg.blocked_outputs == []


def test_last_monitor_cannot_be_unchecked(qapp):
    cfg = Config()
    dlg = SettingsDialog(cfg, screens=SCREENS)
    dlg._screens["DP-4"].setChecked(False)
    dlg._screens["DP-3"].setChecked(False)
    assert dlg._screens["DP-3"].isChecked()
    assert cfg.blocked_outputs == ["DP-4"]


def test_disconnected_but_blocked_monitor_stays_visible(qapp):
    cfg = Config()
    cfg.set("blocked_outputs", ["DP-9"])
    dlg = SettingsDialog(cfg, screens=[("DP-3", "DP-3")])
    assert sorted(dlg._screens) == ["DP-3", "DP-9"]
    assert not dlg._screens["DP-9"].isChecked()


def test_single_monitor_has_no_boxes(qapp):
    assert SettingsDialog(Config(), screens=[("DP-3", "DP-3")])._screens == {}


def test_restore_defaults_frees_all_monitors(qapp):
    cfg = Config()
    dlg = SettingsDialog(cfg, screens=SCREENS)
    dlg._screens["DP-4"].setChecked(False)
    dlg.restore_defaults()
    assert cfg == Config()
    assert all(b.isChecked() for b in dlg._screens.values())


def test_color_button_writes_through(qapp):
    cfg = Config()
    dlg = SettingsDialog(cfg, screens=SCREENS)
    seen = []
    dlg.changed.connect(seen.append)
    button = dlg._widgets["fur_color"]
    assert button.value() == Config().fur_color
    button.setValue("#8899aa")          # wie nach dem Farbwaehler
    button.picked.emit(button.value())
    assert cfg.fur_color == "#8899aa" and seen == ["fur_color"]
    dlg.restore_defaults()
    assert cfg.fur_color == Config().fur_color
    assert button.value() == Config().fur_color


def test_color_button_click_opens_picker(qapp, pick):
    """Echter Klick: clicked liefert ein Argument mit, der Slot muss es vertragen."""
    pick("#8899aa")
    cfg = Config()
    dlg = SettingsDialog(cfg)
    dlg._widgets["fur_color"].click()
    assert cfg.fur_color == "#8899aa"
    assert dlg._widgets["fur_color"].value() == "#8899aa"


def test_color_button_keeps_value_when_cancelled(qapp, pick):
    pick(QColor())            # ungültige Farbe = Abbruch
    cfg = Config()
    dlg = SettingsDialog(cfg)
    dlg._widgets["fur_color"].click()
    assert cfg.fur_color == Config().fur_color


def test_restore_defaults_button_click(qapp):
    cfg = Config()
    dlg = SettingsDialog(cfg)
    dlg._widgets["satiety_hours"].setValue(40)
    box = dlg.findChild(QDialogButtonBox)
    box.button(QDialogButtonBox.StandardButton.RestoreDefaults).click()
    assert cfg == Config()
