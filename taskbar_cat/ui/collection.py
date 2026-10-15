"""Sammlung: gespeicherte Varianten großer Kratzbäume mit Vorschaubild aufstellen,
umbenennen oder löschen (gespeichert wird per Rechtsklick auf einen Baum)."""
import html
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout, QInputDialog,
                             QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from .. import sprites, storage
from ..guard import guarded

THUMB_W, THUMB_H = 120, 170
COLUMNS = 3


def thumbnail(variant: dict) -> QPixmap:
    """Vorschau in Pixel-Optik: ganzzahlig vergrößert, zu große Bäume verkleinert."""
    img = sprites.render_bigtree(float(variant["w"]), float(variant["h"]), bool(variant.get("hanging")),
                                 int(variant["seed"]))
    k = min(THUMB_W // img.width(), THUMB_H // img.height())
    if k >= 1:
        img = img.scaled(img.width() * k, img.height() * k,
                         transformMode=Qt.TransformationMode.FastTransformation)
    else:
        img = img.scaled(THUMB_W, THUMB_H, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    return QPixmap.fromImage(img)


def rename(variants: list[dict], old: str, new: str) -> list[dict]:
    """Trägt schon eine andere Variante den neuen Namen, wird sie ersetzt."""
    out = [v for v in variants if v["name"] != new or new == old]
    return [{**v, "name": new} if v["name"] == old else v for v in out]


class CollectionDialog(QDialog):
    placeRequested = pyqtSignal(dict)

    def __init__(self, path: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Taskbar-Cat - Kratzbaum-Sammlung")
        self.setWindowModality(Qt.WindowModality.NonModal)   # darf die Katze nicht blockieren
        self.resize(COLUMNS * 220 + 60, 2 * THUMB_H + 300)    # drei Karten ohne Querscrollen
        self._path = path
        layout = QVBoxLayout(self)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        layout.addWidget(self._scroll)
        hint = QLabel("Neue Varianten speicherst du per Rechtsklick auf einen großen Kratzbaum "
                      "-> \"Variante speichern ...\".")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.hide)
        layout.addWidget(buttons)
        self.refresh()

    def variants(self) -> list[dict]:
        return storage.load_variants(self._path)

    def refresh(self) -> None:
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        variants = self.variants()
        if not variants:
            grid.addWidget(QLabel("Noch keine Varianten gespeichert."), 0, 0)
        for i, v in enumerate(variants):
            grid.addWidget(self._card(v), i // COLUMNS, i % COLUMNS)
        self._scroll.setWidget(inner)

    def _card(self, v: dict) -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        box = QVBoxLayout(card)
        pic = QLabel()
        pic.setPixmap(thumbnail(v))
        pic.setFixedSize(THUMB_W + 8, THUMB_H + 8)
        # hängende hängen oben, stehende stehen unten
        pic.setAlignment(Qt.AlignmentFlag.AlignHCenter | (Qt.AlignmentFlag.AlignTop if v.get("hanging")
                                                         else Qt.AlignmentFlag.AlignBottom))
        box.addWidget(pic, alignment=Qt.AlignmentFlag.AlignHCenter)
        for text in (f"<b>{html.escape(v['name'])}</b>",
                     f"{v['w']} x {v['h']}, {'hängend' if v.get('hanging') else 'stehend'}"):
            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            box.addWidget(label)
        place = QPushButton("Aufstellen")
        place.clicked.connect(guarded(lambda _c=False: self.placeRequested.emit(v)))
        box.addWidget(place)
        row = QHBoxLayout()
        for text, fn in (("Umbenennen", self._rename), ("Löschen", self._delete)):
            b = QPushButton(text)
            b.clicked.connect(guarded(lambda _c=False, fn=fn: fn(v)))
            row.addWidget(b)
        box.addLayout(row)
        return card

    def _rename(self, v: dict) -> None:
        name, ok = QInputDialog.getText(self, "Variante umbenennen", "Neuer Name:", text=v["name"])
        name = name.strip()
        if ok and name and name != v["name"]:
            storage.save_variants(self._path, rename(self.variants(), v["name"], name))
            self.refresh()

    def _delete(self, v: dict) -> None:
        if QMessageBox.question(self, "Variante löschen", f"\"{v['name']}\" aus der Sammlung löschen?") \
                == QMessageBox.StandardButton.Yes:
            storage.save_variants(self._path, [x for x in self.variants() if x["name"] != v["name"]])
            self.refresh()
