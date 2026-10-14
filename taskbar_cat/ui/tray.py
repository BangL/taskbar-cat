"""Tray-Icon mit Status-Tooltip und Menü (auch fürs Rechtsklick-Menü der Katze)."""
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

from .. import autostart, sprites, status
from ..cat import MOOD_NAME, Cat
from ..guard import guarded


def _icons(fur: str) -> dict:
    return {m: QIcon(QPixmap.fromImage(sprites.head_icon(m, fur).scaled(
        64, 64, transformMode=Qt.TransformationMode.FastTransformation))) for m in sprites.MOODS}


class CatTray(QObject):
    feedRequested = pyqtSignal()
    petRequested = pyqtSignal()
    sleepRequested = pyqtSignal()
    floorRequested = pyqtSignal()
    pauseToggled = pyqtSignal(bool)
    settingsRequested = pyqtSignal()
    inventoryRequested = pyqtSignal()
    quitRequested = pyqtSignal()

    def __init__(self, cat: Cat, fur: str = sprites.FUR_DEFAULT):
        super().__init__()
        self._cat = cat
        self._mood = None
        self._status_box: QMessageBox | None = None
        self._icons = _icons(fur)
        self._menu = QMenu()
        self._menu.addAction("Füttern", self.feedRequested.emit)
        self._menu.addAction("Streicheln", self.petRequested.emit)
        self._menu.addAction("Schlafen schicken", self.sleepRequested.emit)
        self._menu.addAction("Zum Boden rufen", self.floorRequested.emit)
        self._menu.addAction("Status ...", guarded(self._show_status))
        self._menu.addAction("Inventar ...", self.inventoryRequested.emit)
        self._menu.addSeparator()
        self._pause = self._menu.addAction("Pausieren")
        self._pause.setCheckable(True)
        self._pause.toggled.connect(self.pauseToggled.emit)
        self._autostart = self._menu.addAction("Beim Anmelden starten")
        self._autostart.setCheckable(True)
        self._autostart.toggled.connect(guarded(self._toggle_autostart))
        self._menu.addAction("Einstellungen ...", self.settingsRequested.emit)
        self._menu.aboutToShow.connect(guarded(self._sync_autostart))
        self._menu.addSeparator()
        self._menu.addAction("Beenden", self.quitRequested.emit)
        self._tray = QSystemTrayIcon(self._icons["normal"])
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(guarded(self._activated))
        self._tray.show()
        self._sensor_ok = True

    def menu(self) -> QMenu:
        return self._menu

    def set_color(self, fur: str) -> None:
        self._icons = _icons(fur)
        self._mood = None          # erzwingt das Setzen beim nächsten refresh
        self.refresh(self._sensor_ok)

    def _sync_autostart(self) -> None:
        """Haken am Dateizustand ausrichten (kann von außen geändert worden sein)."""
        self._autostart.blockSignals(True)
        self._autostart.setChecked(autostart.is_enabled())
        self._autostart.blockSignals(False)

    def _toggle_autostart(self, on: bool) -> None:
        if autostart.set_enabled(on) != on:
            self._sync_autostart()

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.feedRequested.emit()

    def status_text(self) -> str:
        return "\n".join(status.lines(status.snapshot(self._cat, self._sensor_ok)))

    def refresh(self, sensor_ok: bool) -> None:
        self._sensor_ok = sensor_ok
        mood = MOOD_NAME[self._cat.needs.mood]
        if mood != self._mood:
            self._mood = mood
            self._tray.setIcon(self._icons[mood])
        self._tray.setToolTip(self.status_text())

    def _show_status(self) -> None:
        """Nicht modal: ein offenes Statusfenster darf die Katze nicht blockieren."""
        box = self._status_box
        if box is None:
            box = self._status_box = QMessageBox(QMessageBox.Icon.Information,
                                                 "Taskbar-Cat", "")
            box.setWindowModality(Qt.WindowModality.NonModal)
        box.setText(self.status_text())
        box.show()
        box.raise_()
        box.activateWindow()
