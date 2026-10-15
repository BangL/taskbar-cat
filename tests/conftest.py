import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Backend fest, damit kein Test die echte GNOME-Extension anfasst
os.environ.setdefault("TASKBAR_CAT_BACKEND", "kde")


@pytest.fixture(scope="session")
def qapp():
    # QApplication (nicht QGuiApplication): der Einstellungsdialog braucht QtWidgets
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
