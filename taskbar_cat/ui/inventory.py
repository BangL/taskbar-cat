"""Inventar: Möbel aufstellen oder einlagern (je eins, siehe furniture.KINDS)."""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QGridLayout, QLabel, QPushButton,
                             QVBoxLayout, QWidget)

from .. import sprites
from ..furniture import BOWL_PORTIONS, KINDS, NAMES, Furniture
from ..guard import guarded

ICON_PX = 64


class InventoryDialog(QDialog):
    placeRequested = pyqtSignal(str)
    storeRequested = pyqtSignal(str)

    def __init__(self, furniture: Furniture, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Taskbar-Cat - Inventar")
        self.setWindowModality(Qt.WindowModality.NonModal)   # darf die Katze nicht blockieren
        self._furniture = furniture
        self._status: dict[str, QLabel] = {}
        self._buttons: dict[str, QPushButton] = {}
        layout = QVBoxLayout(self)
        grid = QGridLayout()
        layout.addLayout(grid)
        for row, kind in enumerate(KINDS):
            icon = QLabel()
            img = sprites.furniture_icon(kind)   # gleicher Maßstab für alle, hohe werden höher
            icon.setPixmap(QPixmap.fromImage(img.scaled(
                img.width() * ICON_PX // sprites.FRAME, img.height() * ICON_PX // sprites.FRAME,
                transformMode=Qt.TransformationMode.FastTransformation)))
            grid.addWidget(icon, row, 0)
            grid.addWidget(QLabel(f"<b>{NAMES[kind]}</b>"), row, 1)
            self._status[kind] = QLabel()
            grid.addWidget(self._status[kind], row, 2)
            button = self._buttons[kind] = QPushButton()
            button.clicked.connect(guarded(lambda checked=False, k=kind: self._toggle(k)))
            grid.addWidget(button, row, 3)
        hint = QLabel("Aufgestellte Möbel lassen sich auf dem Desktop mit der Maus verschieben, "
                      "das Wollknäuel auch werfen; Rechtsklick lagert sie wieder ein.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.hide)
        layout.addWidget(buttons)
        self.refresh()

    def _toggle(self, kind: str) -> None:
        if self._furniture.placed(kind):
            self.storeRequested.emit(kind)
        else:
            self.placeRequested.emit(kind)
        self.refresh()

    def refresh(self) -> None:
        for kind in KINDS:
            placed = self._furniture.placed(kind)
            text = "aufgestellt" if placed else "im Inventar"
            if kind == "bowl":
                text += f", Futter {self._furniture.food}/{BOWL_PORTIONS}"
            self._status[kind].setText(text)
            self._buttons[kind].setText("Einlagern" if placed else "Aufstellen")
