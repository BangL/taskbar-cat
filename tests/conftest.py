import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    # QApplication (nicht QGuiApplication): der Einstellungsdialog braucht QtWidgets
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
