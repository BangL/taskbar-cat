"""Silhouetten der Sprites: die undurchsichtigen Flächen eines Atlas-Frames.

Damit folgt die Input-Region der Katze und den Möbeln ihrer Form statt einem
Kasten - auf durchsichtige Stellen geklickt, landet der Klick im Fenster
darunter. Gilt für beide Backends: das eine macht daraus eine Qt-Maske, das
andere eine XShape-Region.

Gerechnet wird in Frame-Koordinaten (32 Pixel breit); erst beim Abruf werden
die Flächen auf die Sprite-Größe skaliert und an ihren Platz geschoben.
"""
from pathlib import Path

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QImage

ALPHA_MIN = 24   # ab dieser Deckkraft gilt ein Pixel als anfassbar


def _runs(image: QImage, sx: int, sy: int, w: int, h: int) -> list[list[tuple[int, int]]]:
    """Je Zeile die waagerechten Läufe (x1, x2) undurchsichtiger Pixel."""
    rows = []
    for y in range(h):
        runs: list[tuple[int, int]] = []
        start = None
        for x in range(w):
            solid = (image.pixel(sx + x, sy + y) >> 24) & 0xFF >= ALPHA_MIN
            if solid and start is None:
                start = x
            elif not solid and start is not None:
                runs.append((start, x))
                start = None
        if start is not None:
            runs.append((start, w))
        rows.append(runs)
    return rows


def boxes(image: QImage, sx: int, sy: int, w: int, h: int) -> tuple[tuple[int, int, int, int], ...]:
    """Flächen (x, y, w, h) in Frame-Koordinaten.

    Aufeinanderfolgende Zeilen mit gleichen Läufen werden zusammengefasst; bei
    Pixel-Art bleiben so ein paar Dutzend Rechtecke statt Hunderten übrig.
    """
    out = []
    previous: list[tuple[int, int]] = []
    start_y = 0
    for y, runs in enumerate([*_runs(image, sx, sy, w, h), []]):
        if runs != previous:
            out.extend((x1, start_y, x2 - x1, y - start_y) for x1, x2 in previous)
            previous, start_y = runs, y
    return tuple(out)


def place(shape: tuple[tuple[int, int, int, int], ...], left: int, top: int,
          scale: float, frame_width: int = 0) -> tuple[QRect, ...]:
    """Silhouette auf Sprite-Größe bringen und an (left, top) setzen.

    frame_width > 0 spiegelt waagerecht (die Katze schaut nach links).
    Die Kanten werden gemeinsam gerundet, damit zwischen den Flächen keine
    Lücken aufreißen, durch die ein Klick fiele.
    """
    out = []
    for x, y, w, h in shape:
        x1, x2 = (frame_width - x - w, frame_width - x) if frame_width else (x, x + w)
        left_px, right_px = round(x1 * scale), round(x2 * scale)
        top_px, bottom_px = round(y * scale), round((y + h) * scale)
        out.append(QRect(left + left_px, top + top_px, right_px - left_px, bottom_px - top_px))
    return tuple(out)


class Silhouettes:
    """Silhouetten eines Atlas, einmal je Frame berechnet."""

    def __init__(self, atlas: Path | None = None):
        self._image = QImage()
        self._shapes: dict[tuple[int, int, int, int], tuple] = {}
        self.load(atlas)

    def load(self, atlas: Path | None) -> None:
        self._shapes.clear()
        self._image = QImage(str(atlas)) if atlas is not None else QImage()

    def shape(self, sx: int, sy: int, w: int, h: int) -> tuple[tuple[int, int, int, int], ...]:
        key = (sx, sy, w, h)
        if key not in self._shapes:
            if self._image.isNull():
                self._shapes[key] = ((0, 0, w, h),)    # ohne Atlas lieber der ganze Kasten
            else:
                self._shapes[key] = boxes(self._image, sx, sy, w, h)
        return self._shapes[key]

    def rects(self, sx: int, sy: int, w: int, h: int, left: int, top: int,
              scale: float, flip: bool = False) -> tuple[QRect, ...]:
        return place(self.shape(sx, sy, w, h), left, top, scale, w if flip else 0)
