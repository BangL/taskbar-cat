"""Pixel-Art-Katze prozedural zeichnen und als Atlas cachen.

Alle Posen schauen nach rechts; Pfoten stehen auf Zeile 30, Zeile 31 bleibt
für die Kontur frei. Gespiegelt wird beim Zeichnen im Overlay.
"""
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

ATLAS_VERSION = 3
FRAME = 32
ANIMS = {"sit": 2, "walk": 4, "jump": 1, "fall": 1, "sleep": 2, "eat": 2, "purr": 2, "dragged": 2, "lie": 2, "climb": 4, "hang": 2,
         "crouch": 2, "swipe": 2, "cheer": 2}
MOODS = ("normal", "sad", "sick")

PALETTES = {
    "normal": {"fur": "#E8913A", "dark": "#8A4A1C"},
    "sad": {"fur": "#D98A42", "dark": "#7A4420"},
    "sick": {"fur": "#9DBF6A", "dark": "#5E7A3A"},
}
EYE = QColor("#1A1A1A")
NOSE = QColor("#F28CA0")
WHITE = QColor("#FFFFFF")
BOWL = QColor("#3A7BD5")
HEART = QColor("#E8364F")
ZZZ = QColor("#DDE6FF")


def frame_origin(anim: str, mood: str, frame: int) -> tuple[int, int]:
    row = list(ANIMS).index(anim) * len(MOODS) + MOODS.index(mood)
    return (frame % ANIMS[anim]) * FRAME, row * FRAME


class _Pen:
    """Kleine Zeichenhilfe ohne Antialiasing."""

    def __init__(self, painter: QPainter, mood: str):
        self.p = painter
        self.mood = mood
        pal = PALETTES[mood]
        self.fur = QColor(pal["fur"])
        self.dark = QColor(pal["dark"])

    def ell(self, cx, cy, rx, ry, color=None):
        self.p.setPen(Qt.PenStyle.NoPen)
        self.p.setBrush(color or self.fur)
        self.p.drawEllipse(QRectF(cx - rx, cy - ry, 2 * rx, 2 * ry))

    def rect(self, x, y, w, h, color=None):
        self.p.fillRect(x, y, w, h, color or self.fur)

    def px(self, x, y, color):
        self.p.fillRect(x, y, 1, 1, color)

    def poly(self, pts, color=None):
        self.p.setPen(Qt.PenStyle.NoPen)
        self.p.setBrush(color or self.fur)
        self.p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))

    def line(self, pts, width=2, color=None):
        self.p.setPen(QPen(color or self.fur, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap))
        for a, b in zip(pts, pts[1:]):
            self.p.drawLine(QPointF(*a), QPointF(*b))

    def tail(self, pts):
        self.line(pts, 2)
        x, y = pts[-1]
        self.rect(int(x) - 1, int(y) - 1, 2, 2, self.dark)

    def head(self, cx, cy, eyes="open"):
        """Kopf im Dreiviertelprofil nach rechts. eyes: open|closed|wide."""
        if self.mood == "normal":
            self.poly([(cx - 5, cy - 2), (cx - 4, cy - 8), (cx - 1, cy - 4)])
            self.poly([(cx + 1, cy - 4), (cx + 4, cy - 8), (cx + 5, cy - 2)])
            self.px(cx - 4, cy - 5, NOSE)
            self.px(cx + 3, cy - 5, NOSE)
        else:  # Ohren hängen seitlich
            self.poly([(cx - 4, cy - 3), (cx - 9, cy - 1), (cx - 4, cy)])
            self.poly([(cx + 4, cy - 3), (cx + 9, cy - 1), (cx + 4, cy)])
        self.ell(cx, cy, 6, 5)
        self.rect(cx + 2, cy + 1, 4, 2, WHITE)
        self.px(cx + 5, cy, NOSE)
        if eyes == "closed" or (eyes == "open" and self.mood != "normal"):
            self.rect(cx - 2, cy - 1 + (self.mood != "normal"), 2, 1, EYE)
            self.rect(cx + 2, cy - 1 + (self.mood != "normal"), 2, 1, EYE)
        elif eyes == "wide":
            self.rect(cx - 2, cy - 2, 2, 2, EYE)
            self.rect(cx + 2, cy - 2, 2, 2, EYE)
        else:
            self.rect(cx - 2, cy - 2, 1, 2, EYE)
            self.rect(cx + 2, cy - 2, 1, 2, EYE)
        # Schnurrhaare
        self.px(cx + 7, cy + 1, self.dark)
        self.px(cx + 7, cy + 3, self.dark)

    def stripes(self, pts):
        for x, y in pts:
            self.rect(x, y, 1, 2, self.dark)

    def heart(self, x, y):
        for dx, dy in [(1, 0), (3, 0), (0, 1), (1, 1), (2, 1), (3, 1), (4, 1),
                       (1, 2), (2, 2), (3, 2), (2, 3)]:
            self.px(x + dx, y + dy, HEART)

    def z(self, x, y, size):
        for i in range(size):
            self.px(x + i, y, ZZZ)
            self.px(x + size - 1 - i, y + i, ZZZ)
            self.px(x + i, y + size - 1, ZZZ)


def _sit(c: _Pen, f: int, eyes="open"):
    sway = (0, 1)[f % 2]
    c.tail([(10, 29), (4, 29), (2, 26 - sway), (3, 22 - sway)])
    c.ell(12, 26, 7, 4)
    c.ell(14, 21, 5, 7)
    c.rect(16, 23, 2, 8)
    c.rect(19, 23, 2, 8)
    c.stripes([(11, 17), (13, 16)])
    c.head(18, 11, eyes)


def _walk(c: _Pen, f: int):
    lift = [(0, 1, 0, 1), (1, 0, 0, 0), (0, 1, 1, 0), (0, 0, 0, 1)][f]
    shift = [0, 1, 0, -1][f]
    for i, (x, l) in enumerate(zip((7, 10, 19, 22), lift)):
        c.rect(x + (shift if i % 2 else -shift), 24, 2, 7 - l)
    c.tail([(6, 20), (3, 15), (3 + shift, 10)])
    c.ell(14, 21, 10, 5)
    c.stripes([(9, 17), (12, 16), (15, 16)])
    c.head(24, 14)


def _jump(c: _Pen, f: int):
    c.rect(23, 20, 7, 2)
    c.rect(1, 22, 7, 2)
    c.tail([(5, 19), (2, 14), (1, 10)])
    c.ell(15, 20, 10, 4)
    c.stripes([(10, 17), (13, 16), (16, 16)])
    c.head(25, 13, "wide")


def _fall(c: _Pen, f: int):
    c.rect(4, 13, 3, 2)
    c.rect(24, 13, 3, 2)
    c.rect(7, 23, 2, 5)
    c.rect(21, 23, 2, 5)
    c.tail([(6, 18), (4, 12), (6, 8)])
    c.ell(15, 19, 9, 5)
    c.stripes([(11, 15), (14, 15)])
    c.head(23, 12, "wide")


def _sleep(c: _Pen, f: int):
    c.ell(15, 25, 11, 6)
    c.stripes([(9, 20), (12, 19), (15, 19)])
    c.tail([(5, 29), (14, 30), (21, 30)])
    c.head(21, 24, "closed")
    if f == 0:
        c.z(24, 11, 3)
    else:
        c.z(25, 5, 5)


def _eat(c: _Pen, f: int):
    c.rect(23, 26, 8, 4, BOWL)
    c.rect(24, 25, 6, 1, QColor("#8B5A2B"))
    c.tail([(6, 29), (2, 27), (2, 22)])
    c.ell(11, 25, 7, 5)
    c.rect(15, 24, 2, 7)
    c.rect(18, 24, 2, 7)
    c.stripes([(8, 21), (11, 20)])
    c.head(20, 19 + f, "closed")


def _purr(c: _Pen, f: int):
    _sit(c, f, "closed")
    c.heart(25, 3 - f)


def _dragged(c: _Pen, f: int):
    wig = (0, 1)[f]
    c.rect(11, 13, 2, 6)
    c.rect(20, 13, 2, 6)
    c.rect(12 - wig, 24, 2, 6)
    c.rect(19 + wig, 24, 2, 6)
    c.tail([(16, 24), (16 + wig * 2, 30)])
    c.ell(16, 18, 5, 8)
    c.stripes([(14, 14), (17, 14)])
    c.head(16, 7, "wide")


def _lie(c: _Pen, f: int):
    c.tail([(5, 29), (1, 30 - f)])
    c.ell(14, 27, 10, 4)
    c.rect(24, 29, 6, 2)
    c.stripes([(9, 24), (12, 24), (15, 24)])
    c.head(24, 25, "closed")


def _climb(c: _Pen, f: int):
    """Senkrecht an einer Wand rechts, Kopf oben."""
    front = (0, -2, 0, 2)[f]
    hind = (0, 2, 0, -2)[f]
    c.tail([(12, 25), (9, 29), (10, 30)])
    c.ell(15, 18, 5, 9)
    c.rect(19, 12 + front, 3, 2)
    c.rect(19, 16 - front, 3, 2)
    c.rect(18, 24 + hind, 4, 2)
    c.stripes([(11, 15), (11, 19)])
    c.head(15, 8, "open")


def _hang(c: _Pen, f: int):
    """Mit den Vorderpfoten an einer Kante oben hängend, Hinterbeine zappeln."""
    c.rect(10, 0, 3, 3)
    c.rect(19, 0, 3, 3)
    c.rect(11, 2, 2, 7)
    c.rect(19, 2, 2, 7)
    c.tail([(16, 26), (18 + 2 * f, 30)])
    c.ell(16, 19, 5, 7)
    c.rect(12 - f, 24, 2, 5 + f)
    c.rect(19 + f, 24, 2, 6 - f)
    c.stripes([(14, 15), (17, 15)])
    c.head(16, 10, "wide")


def _crouch(c: _Pen, f: int):
    """Lauern: tief geduckt, Hinterteil wackelt."""
    c.tail([(5, 24 - f), (2, 19), (3 + 2 * f, 15)])
    c.ell(8, 25 - f, 5, 4)
    c.ell(15, 27, 10, 3)
    c.rect(21, 28, 6, 2)
    c.rect(6 + f, 28, 3, 2)
    c.stripes([(10, 23), (13, 24)])
    c.head(24, 24, "wide")


def _swipe(c: _Pen, f: int):
    """Hochgereckt mit erhobener Pfote."""
    c.tail([(12, 27), (8, 30)])
    c.ell(15, 20, 5, 8)
    c.rect(12, 26, 2, 5)
    c.rect(17, 26, 2, 5)
    c.rect(19, 1 + 2 * f, 2, 11)
    c.rect(20, 0 + 2 * f, 3, 2)
    c.rect(10, 12, 2, 6)
    c.stripes([(12, 16), (12, 20)])
    c.head(15, 10, "wide")


def _cheer(c: _Pen, f: int):
    _sit(c, f, "closed")
    c.heart(25, 3 - f)
    c.heart(2, 5 + f)


POSES = {"sit": _sit, "walk": _walk, "jump": _jump, "fall": _fall, "sleep": _sleep,
         "eat": _eat, "purr": _purr, "dragged": _dragged, "lie": _lie,
         "climb": _climb, "hang": _hang,
         "crouch": _crouch, "swipe": _swipe, "cheer": _cheer}


def _outline(img: QImage, x0: int, y0: int, color: QColor) -> None:
    """Konturpixel um alle deckenden Pixel des Frames setzen."""
    solid = {(x, y) for y in range(FRAME) for x in range(FRAME)
             if img.pixelColor(x0 + x, y0 + y).alpha() > 0}
    for x, y in {(x + dx, y + dy) for x, y in solid for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}:
        if 0 <= x < FRAME and 0 <= y < FRAME and (x, y) not in solid:
            img.setPixelColor(x0 + x, y0 + y, color)


def render_atlas() -> QImage:
    img = QImage(FRAME * max(ANIMS.values()), FRAME * len(ANIMS) * len(MOODS), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    for anim, n in ANIMS.items():
        for mood in MOODS:
            for f in range(n):
                x0, y0 = frame_origin(anim, mood, f)
                p = QPainter(img)
                p.translate(x0, y0)
                p.setClipRect(0, 0, FRAME, FRAME)
                pen = _Pen(p, mood)
                POSES[anim](pen, f)
                p.end()
                _outline(img, x0, y0, QColor("#3B2414"))
    return img


def ensure_atlas(cache_dir: Path) -> Path:
    path = cache_dir / f"atlas-v{ATLAS_VERSION}.png"
    if not path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        render_atlas().save(str(path))
    return path


def head_icon(mood: str) -> QImage:
    small = QImage(16, 16, QImage.Format.Format_ARGB32)
    small.fill(Qt.GlobalColor.transparent)
    p = QPainter(small)
    _Pen(p, mood).head(7, 9, "open")
    p.end()
    big = QImage(FRAME, FRAME, QImage.Format.Format_ARGB32)
    big.fill(Qt.GlobalColor.transparent)
    p = QPainter(big)
    p.drawImage(QRectF(0, 0, FRAME, FRAME), small)
    p.end()
    return big


def save_icon(path: Path, size: int = 256, mood: str = "normal") -> None:
    """App-Icon für Desktop-Dateien/Icon-Theme schreiben (Nearest Neighbour)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    icon = head_icon(mood).scaled(size, size, transformMode=Qt.TransformationMode.FastTransformation)
    if not icon.save(str(path)):
        raise OSError(f"Icon nicht schreibbar: {path}")


def _cli(argv: list[str]) -> int:
    """python3 -m taskbar_cat.sprites --icon <datei> | --atlas <datei>"""
    import os
    import sys

    from PyQt6.QtGui import QGuiApplication  # QImage/QPainter brauchen eine App

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QGuiApplication(argv[:1])
    if len(argv) == 3 and argv[1] == "--icon":
        save_icon(Path(argv[2]))
    elif len(argv) == 3 and argv[1] == "--atlas":
        render_atlas().save(argv[2])
    else:
        print(_cli.__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_cli(sys.argv))
