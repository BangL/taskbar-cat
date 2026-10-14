"""Tray-Icon mit Status-Tooltip und Menü (auch fürs Rechtsklick-Menü der Katze)."""
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

from .. import sprites
from ..cat import MOOD_NAME, Cat
from ..guard import guarded

MOOD_TEXT = {"normal": "zufrieden", "sad": "traurig", "sick": "krank"}


class CatTray(QObject):
    feedRequested = pyqtSignal()
    petRequested = pyqtSignal()
    sleepRequested = pyqtSignal()
    floorRequested = pyqtSignal()
    pauseToggled = pyqtSignal(bool)
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
        self._menu.addAction("Beenden", self.quitRequested.emit)
        self._tray = QSystemTrayIcon(self._icons["normal"])
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(guarded(self._activated))
        self._tray.show()
        self._sensor_ok = True

    def menu(self) -> QMenu:
        return self._menu

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.feedRequested.emit()

    def status_text(self) -> str:
        n = self._cat.needs
        lines = [f"Sättigung {n.satiety:.0f} %", f"Zuneigung {n.affection:.0f} %",
                 f"Energie {n.energy:.0f} %", f"Stimmung: {MOOD_TEXT[MOOD_NAME[n.mood]]}"]
        if self._cat.paused:
            lines.append("Pausiert")
        if not self._sensor_ok:
            lines.append("Warnung: Fenster-Sensor fehlt")
        return "\n".join(lines)

    def refresh(self, sensor_ok: bool) -> None:
        self._sensor_ok = sensor_ok
        mood = MOOD_NAME[self._cat.needs.mood]
        if mood != self._mood:
            self._mood = mood
            self._tray.setIcon(self._icons[mood])
        self._tray.setToolTip(self.status_text())

    def _show_status(self) -> None:
        QMessageBox.information(None, "Taskbar-Cat", self.status_text())
