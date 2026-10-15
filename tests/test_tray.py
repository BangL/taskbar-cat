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


def test_check_entry_reports_its_state(qapp):
    """Haken-Einträge melden an/aus. triggered gibt den Haken an guarded() (nimmt *args)
    nicht mit - der Rückruf bekäme gar kein Argument und liefe auf einen TypeError."""
    from PyQt6.QtWidgets import QMenu
    from taskbar_cat.ui.tray import add_check
    seen = []
    menu = QMenu()
    a = add_check(menu, "Hinter Fenstern", False, seen.append, "Hinweis")
    assert a.isCheckable() and not a.isChecked() and a.toolTip() == "Hinweis"
    assert seen == []          # das Setzen des Anfangszustands meldet noch nichts
    a.trigger()
    a.trigger()
    assert seen == [True, False]


def test_check_entry_starts_checked_without_reporting(qapp):
    from PyQt6.QtWidgets import QMenu
    from taskbar_cat.ui.tray import add_check
    seen = []
    menu = QMenu()          # das Menü muss leben, sonst nimmt es den Eintrag mit
    a = add_check(menu, "Festgestellt", True, seen.append)
    assert a.isChecked() and seen == []
