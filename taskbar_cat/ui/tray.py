"""Tray-Icon mit Status-Tooltip und Menü (auch fürs Rechtsklick-Menü der Katze)."""
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

from .. import autostart, sprites, status
from ..cat import MOOD_NAME, Cat
from ..guard import guarded


class CatTray(QObject):
    feedRequested = pyqtSignal()
    petRequested = pyqtSignal()
    sleepRequested = pyqtSignal()
    floorRequested = pyqtSignal()
    pauseToggled = pyqtSignal(bool)
    settingsRequested = pyqtSignal()
    quitRequested = pyqtSignal()

    def __init__(self, cat: Cat):
        super().__init__()
        self._cat = cat
        self._mood = None
        self._icons = {m: QIcon(QPixmap.fromImage(sprites.head_icon(m).scaled(
            64, 64, transformMode=Qt.TransformationMode.FastTransformation))) for m in sprites.MOODS}
        self._menu = QMenu()
        self._menu.addAction("Füttern", self.feedRequested.emit)
        self._menu.addAction("Streicheln", self.petRequested.emit)
        self._menu.addAction("Schlafen schicken", self.sleepRequested.emit)
        self._menu.addAction("Zum Boden rufen", self.floorRequested.emit)
        self._menu.addAction("Status ...", guarded(self._show_status))
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
        QMessageBox.information(None, "Taskbar-Cat", self.status_text())
