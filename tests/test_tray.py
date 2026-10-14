import random

from taskbar_cat.cat import Cat
from taskbar_cat.needs import Needs
from taskbar_cat.ui.tray import CatTray


def tray(qapp) -> CatTray:
    return CatTray(Cat(Needs(), random.Random(1)))


def test_status_window_is_not_modal(qapp):
    """Ein offenes Statusfenster darf die Maus für die Katze nicht blockieren."""
    t = tray(qapp)
    t._show_status()
    assert t._status_box is not None
    assert not t._status_box.isModal()


def test_status_window_is_reused_and_refreshed(qapp):
    t = tray(qapp)
    t._show_status()
    box = t._status_box
    t._cat.needs.satiety = 42
    t._show_status()
    assert t._status_box is box
    assert "42" in box.text()
