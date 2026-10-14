"""Pixel-Art-Katze prozedural zeichnen und als Atlas cachen.

Alle Posen schauen nach rechts; Pfoten stehen auf Zeile 30, Zeile 31 bleibt
für die Kontur frei. Gespiegelt wird beim Zeichnen im Overlay.
"""
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

ATLAS_VERSION = 4
FRAME = 32
ANIMS = {"sit": 2, "walk": 4, "jump": 1, "fall": 1, "sleep": 2, "eat": 2, "purr": 2, "dragged": 2, "lie": 2, "climb": 4, "hang": 2,
         "crouch": 2, "swipe": 2, "cheer": 2}
MOODS = ("normal", "sad", "sick")

FUR_DEFAULT = "#E8913A"
EYE = QColor("#1A1A1A")
EYE_PALE = QColor("#E2DCA8")   # auf dunklem Fell sieht man schwarze Augen nicht
NOSE = QColor("#F28CA0")
BOWL = QColor("#3A7BD5")
HEART = QColor("#E8364F")
ZZZ = QColor("#DDE6FF")


def _hsv(c: QColor, dh: float = 0, fs: float = 1.0, fv: float = 1.0, h: float | None = None,
         s: float | None = None, v: float | None = None) -> QColor:
    """Farbe im HSV-Raum verschieben; dh in Grad, fs/fv als Faktoren."""
    hue, sat, val, _ = c.getHsvF()
    hue = 0.0 if hue < 0 else hue * 360        # Grau hat keinen Farbton
    hue = (hue + dh) % 360 if h is None else h % 360
    return QColor.fromHsvF(hue / 360, min(1.0, sat * fs) if s is None else s,
                           min(1.0, val * fv) if v is None else min(1.0, v))


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(*(round(x + (y - x) * t) for x, y in
                    ((a.red(), b.red()), (a.green(), b.green()), (a.blue(), b.blue()))))


class Palette:
    """Alle Katzenfarben aus einer Fellfarbe. Die Vorgabe ergibt die alten Werte."""

    def __init__(self, fur: QColor | str = FUR_DEFAULT, mood: str = "normal"):
        base = QColor(fur)
        if not base.isValid():
            base = QColor(FUR_DEFAULT)
        if mood == "sad":
            base = _hsv(base, dh=-1.5, fs=0.93, fv=0.935)
        elif mood == "sick":
            base = _hsv(base, h=84, s=max(0.40, base.saturationF() * 0.6), fv=0.823)
        self.fur = base
        val = base.valueF()
        if val < 0.3:
            # Sehr dunkles Fell: Streifen und Kontur müssen heller werden, sonst sieht man nichts
            self.dark = _hsv(base, fs=0.9, v=val + 0.12)
            self.outline = _hsv(base, fs=0.7, v=val + 0.18)
        else:
            self.dark = _hsv(base, dh=-5, fs=1.06, fv=0.595)
            self.outline = _hsv(base, dh=-5.4, fs=0.88, fv=0.254)
        # Brust und Schnauze: fast weiß mit einem Hauch Fellton, bei weißem Fell andersherum
        pale = val > 0.9 and base.saturationF() < 0.15
        self.light = _hsv(base, fs=0.12, fv=0.86) if pale else _mix(base, QColor("#FFFFFF"), 0.85)
        self.eye = EYE if val > 0.42 else EYE_PALE


def frame_origin(anim: str, mood: str, frame: int) -> tuple[int, int]:
    row = list(ANIMS).index(anim) * len(MOODS) + MOODS.index(mood)
    return (frame % ANIMS[anim]) * FRAME, row * FRAME


class _Pen:
    """Kleine Zeichenhilfe ohne Antialiasing."""

    def __init__(self, painter: QPainter, mood: str, fur: QColor | str = FUR_DEFAULT):
        self.p = painter
        self.mood = mood
        self.palette = Palette(fur, mood)
        self.fur = self.palette.fur
        self.dark = self.palette.dark
        self.light = self.palette.light
        self.eye = self.palette.eye

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
        self.rect(cx + 2, cy + 1, 4, 2, self.light)
        self.px(cx + 5, cy, NOSE)
        if eyes == "closed" or (eyes == "open" and self.mood != "normal"):
            self.rect(cx - 2, cy - 1 + (self.mood != "normal"), 2, 1, self.eye)
            self.rect(cx + 2, cy - 1 + (self.mood != "normal"), 2, 1, self.eye)
        elif eyes == "wide":
            self.rect(cx - 2, cy - 2, 2, 2, self.eye)
            self.rect(cx + 2, cy - 2, 2, 2, self.eye)
        else:
            self.rect(cx - 2, cy - 2, 1, 2, self.eye)
            self.rect(cx + 2, cy - 2, 1, 2, self.eye)
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


def render_atlas(fur: QColor | str = FUR_DEFAULT) -> QImage:
    img = QImage(FRAME * max(ANIMS.values()), FRAME * len(ANIMS) * len(MOODS), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    for anim, n in ANIMS.items():
        for mood in MOODS:
            for f in range(n):
                x0, y0 = frame_origin(anim, mood, f)
                p = QPainter(img)
                p.translate(x0, y0)
                p.setClipRect(0, 0, FRAME, FRAME)
                pen = _Pen(p, mood, fur)
                POSES[anim](pen, f)
                p.end()
                _outline(img, x0, y0, pen.palette.outline)
    return img


def ensure_atlas(cache_dir: Path, fur: QColor | str = FUR_DEFAULT) -> Path:
    """Atlas je Fellfarbe zwischenspeichern (Name enthält die Farbe)."""
    tint = QColor(fur)
    if not tint.isValid():
        tint = QColor(FUR_DEFAULT)
    path = cache_dir / f"atlas-v{ATLAS_VERSION}-{tint.name()[1:]}.png"
    for old in cache_dir.glob("atlas-v*.png"):
        if not old.name.startswith(f"atlas-v{ATLAS_VERSION}-"):
            old.unlink(missing_ok=True)       # Spritesheets älterer Versionen
    if not path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        render_atlas(tint).save(str(path))
    return path


def head_icon(mood: str, fur: QColor | str = FUR_DEFAULT) -> QImage:
    small = QImage(16, 16, QImage.Format.Format_ARGB32)
    small.fill(Qt.GlobalColor.transparent)
    p = QPainter(small)
    _Pen(p, mood, fur).head(7, 9, "open")
    p.end()
    big = QImage(FRAME, FRAME, QImage.Format.Format_ARGB32)
    big.fill(Qt.GlobalColor.transparent)
    p = QPainter(big)
    p.drawImage(QRectF(0, 0, FRAME, FRAME), small)
    p.end()
    return big


def save_icon(path: Path, size: int = 256, mood: str = "normal",
              fur: QColor | str = FUR_DEFAULT) -> None:
    """App-Icon für Desktop-Dateien/Icon-Theme schreiben (Nearest Neighbour)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    icon = head_icon(mood, fur).scaled(size, size, transformMode=Qt.TransformationMode.FastTransformation)
    if not icon.save(str(path)):
        raise OSError(f"Icon nicht schreibbar: {path}")


def _cli(argv: list[str]) -> int:
    import argparse
    import os
    import sys

    from . import __version__

    p = argparse.ArgumentParser(
        prog="python3 -m taskbar_cat.sprites",
        description="Pixel-Art prozedural erzeugen: App-Icon oder komplettes Spritesheet.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--icon", metavar="DATEI", help="Katzenkopf als PNG schreiben (256x256)")
    g.add_argument("--atlas", metavar="DATEI", help="komplettes Spritesheet als PNG schreiben")
    p.add_argument("--mood", choices=MOODS, default="normal", help="Stimmung des Icons (Standard: normal)")
    p.add_argument("--size", type=int, default=256, help="Kantenlänge des Icons in Pixel (Standard: 256)")
    p.add_argument("--color", default=FUR_DEFAULT, metavar="#RRGGBB",
                   help=f"Fellfarbe (Standard: {FUR_DEFAULT})")
    p.add_argument("--version", action="version", version=f"taskbar-cat {__version__}")
    args = p.parse_args(argv[1:])

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # vor QGuiApplication setzen
    from PyQt6.QtGui import QGuiApplication  # QImage/QPainter brauchen eine App

    QGuiApplication.instance() or QGuiApplication(argv[:1])  # nur eine pro Prozess
    if not QColor(args.color).isValid():
        print(f"taskbar-cat: keine Farbe: {args.color}", file=sys.stderr)
        return 2
    if args.icon:
        save_icon(Path(args.icon), args.size, args.mood, args.color)
    elif not render_atlas(args.color).save(args.atlas):
        print(f"taskbar-cat: Atlas nicht schreibbar: {args.atlas}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_cli(sys.argv))
