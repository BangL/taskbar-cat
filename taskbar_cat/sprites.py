"""Pixel-Art-Katze prozedural zeichnen und als Atlas cachen.

Alle Posen schauen nach rechts; Pfoten stehen auf Zeile 30, Zeile 31 bleibt
für die Kontur frei. Gespiegelt wird beim Zeichnen im Overlay.
"""
import random
import zlib
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF

from . import bigtree
from .furniture import FRAME_H, TREE_DECK, TREE_FRAMES, TREE_POST

ATLAS_VERSION = 12
UFO_VERSION = 1
FURNITURE_VERSION = 6
FRAME = 32
ANIMS = {"sit": 2, "groom": 2, "vomit": 2, "walk": 4, "crawl": 4, "jump": 1, "fall": 1, "sleep": 2, "eat": 2, "purr": 2, "dragged": 2, "lie": 2, "climb": 4, "hang": 2,
         "crouch": 2, "swipe": 2, "cheer": 2, "bat": 2, "scratch": 2, "climb_post": 4,
         "hammock": 4, "hammock_sleep": 4, "cave_in": 2, "cave_peek": 8, "cave_duck": 2, "cave_sleep": 2,
         "cave_butt": 4}
MOODS = ("normal", "sad", "sick")

FUR_DEFAULT = "#E8913A"
TABBY_DEFAULT = 100       # Prozent: 0 einfarbig, 100 wie gezeichnet, 200 mit allen Zusatzstreifen
EYE = QColor("#1A1A1A")
EYE_PALE = QColor("#E2DCA8")   # auf dunklem Fell sieht man schwarze Augen nicht
NOSE = QColor("#F28CA0")
BOWL = QColor("#3A7BD5")
BOWL_DARK = QColor("#2A5CA8")
HEART = QColor("#E8364F")
PUKE = QColor("#9FB04A")
ZZZ = QColor("#DDE6FF")
FOOD = QColor("#8B5A2B")
FOOD_LIGHT = QColor("#C08A50")   # einzelne Körner im verschütteten Häufchen
BED = QColor("#B04A5A")
BED_DARK = QColor("#7A2E3C")
CUSHION = QColor("#E8D9B8")
YARN = QColor("#D8486A")
YARN_DARK = QColor("#9A2846")
SISAL = QColor("#D9C08A")
SISAL_DARK = QColor("#A88B52")
SISAL_LIGHT = QColor("#F0E2BC")   # zerkratzte, aufgefaserte Stellen
CARPET = QColor("#8C7B6B")
CARPET_DARK = QColor("#6A5B4E")
FURNITURE_OUTLINE = QColor("#2A1A14")
HAMMOCK = QColor("#6C8FD8")
HAMMOCK_DARK = QColor("#4A68A8")
CAVE = QColor("#B07A4A")
CAVE_HOLE = QColor("#3A2618")
TOY_COLORS = (YARN, QColor("#5AC8FF"), QColor("#FFE15A"), QColor("#7CD67C"), QColor("#B47CFF"))


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


def _spread(pts, part: float) -> list:
    """Anteil einer Streifenliste gleichmäßig verteilt auswählen: 0 nichts, 1 alles."""
    n = round(len(pts) * max(0.0, min(1.0, part)))
    return [pts[int((i + 0.5) * len(pts) / n)] for i in range(n)] if n else []


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
        self.eye = EYE if val > 0.42 else EYE_PALE
        # Schnauzenstriche und Schnurrhaare: auf hellem Fell dunkel, auf dunklem
        # aufgehellt (nicht reinweiß, sonst sieht die schwarze Katze aus wie ein Walross)
        self.whisker = self.dark if val > 0.5 else _mix(base, QColor("#FFFFFF"), 0.55)


def frame_origin(anim: str, mood: str, frame: int) -> tuple[int, int]:
    row = list(ANIMS).index(anim) * len(MOODS) + MOODS.index(mood)
    return (frame % ANIMS[anim]) * FRAME, row * FRAME


class _Pen:
    """Kleine Zeichenhilfe ohne Antialiasing."""

    def __init__(self, painter: QPainter, mood: str, fur: QColor | str = FUR_DEFAULT,
                 tabby: float = TABBY_DEFAULT):
        self.p = painter
        self.mood = mood
        self.tabby = tabby
        self.palette = Palette(fur, mood)
        self.fur = self.palette.fur
        self.dark = self.palette.dark
        self.eye = self.palette.eye
        self.whisker = self.palette.whisker

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
        self.muzzle(cx, cy)
        if eyes == "closed" or (eyes == "open" and self.mood != "normal"):
            self.rect(cx - 2, cy - 1 + (self.mood != "normal"), 2, 1, self.eye)
            self.rect(cx + 2, cy - 1 + (self.mood != "normal"), 2, 1, self.eye)
        elif eyes == "wide":
            self.rect(cx - 2, cy - 2, 2, 2, self.eye)
            self.rect(cx + 2, cy - 2, 2, 2, self.eye)
        else:
            self.rect(cx - 2, cy - 2, 1, 2, self.eye)
            self.rect(cx + 2, cy - 2, 1, 2, self.eye)

    def muzzle(self, cx, cy):
        """Rosa Nase, darunter drei kurze Striche als Mund, dazu zwei Schnurrhaare.
        Die Mundwinkel liegen höher als die Mitte, sonst guckt sie dauertraurig.
        Keine helle Fläche: die macht aus der Katze einen Fuchs."""
        self.rect(cx, cy, 2, 1, NOSE)
        self.px(cx, cy + 1, self.whisker)
        self.px(cx + 2, cy + 1, self.whisker)
        self.px(cx + 1, cy + 2, self.whisker)
        self.rect(cx + 5, cy - 1, 2, 1, self.whisker)
        self.rect(cx + 5, cy + 1, 2, 1, self.whisker)

    def stripes(self, pts, extra=()):
        """pts sind die normalen Streifen, extra die zusätzlichen ab 100 % Tigerung.
        Darunter wird aus pts ausgedünnt, bei 0 bleibt das Fell einfarbig."""
        for x, y in _spread(pts, self.tabby / 100) + _spread(extra, self.tabby / 100 - 1):
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
    c.tail([(10, 30), (4, 30), (2, 26 - sway), (3, 22 - sway)])
    c.ell(12, 26.5, 7, 4.5)
    c.ell(14, 21, 5, 7)
    # Vorderbeine als ein Block mit angedeuteter Trennung: zwei getrennte Rechtecke
    # lassen unten eine Lücke, durch die der Hintergrund scheint
    c.rect(16, 23, 5, 8)
    c.rect(18, 24, 1, 5, c.dark)
    c.stripes([(11, 17), (13, 16)], [(10, 20), (15, 15)])
    c.head(18, 11, eyes)


def _groom(c: _Pen, f: int):
    """Fellpflege: Kopf gesenkt, eine Vorderpfote angehoben, Zungenspitze raus."""
    d = f % 2
    c.tail([(10, 30), (4, 30), (2, 26), (3, 22)])
    c.ell(12, 26.5, 7, 4.5)
    c.ell(14, 21, 5, 7)
    c.rect(16, 23, 5, 8)
    c.rect(18, 24, 1, 5, c.dark)
    c.stripes([(11, 17), (13, 16)], [(10, 20), (15, 15)])
    c.head(16, 15 + d, "closed")
    c.rect(18, 18 + d, 4, 2)            # angehobene Pfote
    c.rect(18, 20 + d, 4, 1, c.dark)    # grenzt sie vom Körper ab
    c.px(18, 17 + d, NOSE)              # Zungenspitze


def _vomit(c: _Pen, f: int):
    """Es kommt hoch: geduckt, Kopf tief, Pfütze davor. Frame 0 würgt, Frame 1 spuckt."""
    d = f % 2
    c.tail([(10, 30), (4, 30), (2, 27), (4, 24)])
    c.ell(12, 26.5, 7, 4.5)
    c.ell(14, 22, 5, 6)
    c.rect(16, 24, 5, 7)
    c.rect(18, 25, 1, 4, c.dark)
    c.stripes([(11, 18), (13, 17)], [(10, 21), (15, 17)])
    c.head(17, 19 - d, "closed")
    if d:
        c.rect(22, 22, 2, 4, PUKE)          # Schwall aus dem Maul
    c.rect(23, 28, 5, 1, PUKE)              # Pfütze davor
    c.rect(22, 29, 7, 2, PUKE)


def _walk(c: _Pen, f: int):
    lift = [(0, 1, 0, 1), (1, 0, 0, 0), (0, 1, 1, 0), (0, 0, 0, 1)][f]
    shift = [0, 1, 0, -1][f]
    for i, (x, l) in enumerate(zip((7, 10, 19, 22), lift)):
        c.rect(x + (shift if i % 2 else -shift), 24, 2, 7 - l)
    c.tail([(6, 20), (3, 15), (3 + shift, 10)])
    c.ell(14, 21, 10, 5)
    c.stripes([(9, 17), (12, 16), (15, 16)], [(6, 19), (18, 17)])
    c.head(24, 14)


def _crawl(c: _Pen, f: int):
    """Geduckt laufen: unter niedrigen Fensterkanten passt sie sonst nicht durch."""
    lift = [(0, 1, 0, 1), (1, 0, 0, 0), (0, 1, 1, 0), (0, 0, 0, 1)][f]
    shift = [0, 1, 0, -1][f]
    for i, (x, l) in enumerate(zip((7, 10, 19, 22), lift)):
        c.rect(x + (shift if i % 2 else -shift), 28, 2, 3 - l)
    c.tail([(6, 26), (2, 24), (2 + shift, 21)])
    c.ell(14, 26, 10, 4)
    c.stripes([(9, 23), (12, 22), (15, 22)], [(6, 24), (18, 23)])
    c.head(24, 24)


def _jump(c: _Pen, f: int):
    c.rect(23, 20, 7, 2)
    c.rect(1, 22, 7, 2)
    c.tail([(5, 19), (2, 14), (1, 10)])
    c.ell(15, 20, 10, 4)
    c.stripes([(10, 17), (13, 16), (16, 16)], [(7, 18), (19, 17)])
    c.head(25, 13, "wide")


def _fall(c: _Pen, f: int):
    c.rect(4, 13, 3, 2)
    c.rect(24, 13, 3, 2)
    c.rect(7, 23, 2, 5)
    c.rect(21, 23, 2, 5)
    c.tail([(6, 18), (4, 12), (6, 8)])
    c.ell(15, 19, 9, 5)
    c.stripes([(11, 15), (14, 15)], [(8, 17), (17, 15)])
    c.head(23, 12, "wide")


def _sleep(c: _Pen, f: int):
    c.ell(15, 25, 11, 6)
    c.stripes([(9, 20), (12, 19), (15, 19)], [(6, 22), (18, 20)])
    c.tail([(5, 29), (14, 30), (21, 30)])
    c.head(21, 24, "closed")
    if f == 0:
        c.z(24, 11, 3)
    else:
        c.z(25, 5, 5)


def _bowl(c: _Pen, x: int, food: int = 2):
    """Napf mit der linken Kante bei x; auch das Möbel benutzt ihn, damit sie deckungsgleich sind.
    Unterkante auf Zeile 30 wie die Pfoten, die Kontur steht dann auf dem Boden.
    food: 0 leer, 1 ein Häufchen, 2 eben voll, 3 gehäuft."""
    c.rect(x, 27, 8, 4, BOWL)
    if food == 1:
        c.rect(x + 3, 26, 2, 1, FOOD)
    elif food >= 2:
        c.rect(x + 1, 26, 6, 1, FOOD)
    if food >= 3:
        c.rect(x + 2, 25, 4, 1, FOOD)
        c.rect(x + 3, 24, 2, 1, FOOD)


def _bowl_tipped(c: _Pen, x: int = 12):
    """Umgedrehter Napf: Boden mit schmalem Fuß oben, ein paar Krümel drumherum."""
    c.rect(x, 28, 8, 3, BOWL)
    c.rect(x + 2, 27, 4, 1, BOWL_DARK)
    c.rect(x + 1, 30, 6, 1, BOWL_DARK)


def _spill(c: _Pen, portions: int):
    """Verschüttetes Futter: ein Häufchen, je Portion größer (einzelne Körner wären mit
    Kontur nur Striche)."""
    w = 2 + 2 * portions
    c.rect(16 - w // 2, 30, w, 1, FOOD)
    c.rect(16 - w // 2 + 1, 29, w - 2, 1, FOOD)
    if portions >= 3:
        c.rect(15, 28, 2, 1, FOOD)
    for x, y in ((15, 30), (17, 29), (13, 30), (19, 30))[:1 + portions]:   # liegen alle im Häufchen
        c.px(x, y, FOOD_LIGHT)


def _eat(c: _Pen, f: int):
    _bowl(c, 23)
    c.tail([(6, 29), (2, 27), (2, 22)])
    c.ell(11, 25, 7, 5)
    c.rect(15, 24, 2, 7)
    c.rect(18, 24, 2, 7)
    c.stripes([(8, 21), (11, 20)], [(5, 23), (14, 21)])
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
    c.stripes([(14, 14), (17, 14)], [(14, 18), (17, 18)])
    c.head(16, 7, "wide")


def _lie(c: _Pen, f: int):
    c.tail([(5, 29), (1, 30 - f)])
    c.ell(14, 27, 10, 4)
    c.rect(24, 29, 6, 2)
    c.stripes([(9, 24), (12, 24), (15, 24)], [(6, 25), (18, 25)])
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
    c.stripes([(11, 15), (11, 19)], [(12, 12), (11, 22)])
    c.head(15, 8, "open")


def _climb_post(c: _Pen, f: int):
    """Am Pfeiler des großen Kratzbaums (rechts): die Pfoten greifen um ihn herum."""
    front = (0, -2, 0, 2)[f]
    hind = (0, 2, 0, -2)[f]
    c.tail([(12, 25), (9, 29), (10, 30)])
    c.ell(15, 18, 5, 9)
    c.rect(19, 12 + front, 6, 2)
    c.rect(19, 16 - front, 6, 2)
    c.rect(18, 24 + hind, 6, 2)
    c.stripes([(11, 15), (11, 19)], [(12, 12), (11, 22)])
    c.head(15, 8, "open")


def _hammock_lip(c: _Pen, d: int):
    """Vorderer Rand der Hängematte über dem Körper, schaukelt mit."""
    c.ell(16 + d, 30, 13, 2.5, HAMMOCK)
    c.rect(4 + d, 29, 24, 1, HAMMOCK_DARK)


def _hammock(c: _Pen, f: int, sleep: bool = False):
    """Liegt in der Hängematte (Boden = Unterkante der Matte), Schwanz und Pfote hängen raus."""
    d = (-1, 0, 1, 0)[f]
    c.tail([(7 + d, 26), (4 + d, 29), (4 + 2 * d, 31)])
    c.ell(15 + d, 25, 10, 4)
    c.stripes([(10 + d, 22), (13 + d, 21), (16 + d, 21)], [(7 + d, 23), (19 + d, 22)])
    c.rect(20 - d, 27, 2, 4)
    c.head(22 + d, 23, "closed")
    _hammock_lip(c, d)
    if sleep:
        c.z(25, 10 - f % 2 * 2, 3 + f % 2)


# Höhle des großen Kratzbaums: Tür mittig im Frame (bigtree.DOOR_W breit), Boden = Höhlenboden

def _cave_in(c: _Pen, f: int):
    """Von hinten, geduckt: schlüpft durch die Tür hinein (verblasst im Dunkeln)."""
    sway = (0, 1)[f]
    c.ell(16, 28, 6, 3.5)
    c.ell(16, 23, 4, 3.5)
    c.poly([(12, 22), (13, 17), (15, 21)])
    c.poly([(17, 21), (19, 17), (20, 22)])
    c.line([(16, 31), (16, 27), (17 + sway, 24)], 2, c.dark)   # Schwanz hoch, über dem Rücken


def _cave_peek(c: _Pen, f: int):
    """Nur der Kopf schaut aus der Tür, ab und zu blinzelt sie."""
    c.head(16, 26, "closed" if f == 7 else "open")


def _cave_duck(c: _Pen, f: int):
    """Weggeduckt: nur die Ohren schauen noch heraus (hängende Ohren: auch die Augen)."""
    c.head(16, (34 if c.mood == "normal" else 31) - f, "open")


def _cave_butt(c: _Pen, f: int):
    """Selten: verkehrt herum drin, der Hintern mit kleinem x schaut heraus, Schwanz wedelt."""
    sway = (0, 1, 0, -1)[f]
    c.ell(16, 27, 6, 5)
    c.rect(11, 29, 3, 3)
    c.rect(18, 29, 3, 3)
    c.tail([(16, 23), (16, 19), (17 + sway, 15), (16 + 2 * sway, 12)])
    for dx, dy in ((-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)):
        c.px(16 + dx, 26 + dy, c.dark)


def _cave_sleep(c: _Pen, f: int):
    c.head(16, 27, "closed")
    c.z(23, 10 - f * 2, 3 + f)


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
    c.stripes([(14, 15), (17, 15)], [(14, 19), (17, 19)])
    c.head(16, 10, "wide")


def _crouch(c: _Pen, f: int):
    """Lauern: tief geduckt, Hinterteil wackelt."""
    c.tail([(5, 24 - f), (2, 19), (3 + 2 * f, 15)])
    c.ell(8, 25 - f, 5, 4)
    c.ell(15, 27.5, 10, 3.5)
    c.rect(21, 28, 6, 3)
    c.rect(6 + f, 28, 3, 3)
    c.stripes([(10, 23), (13, 24)], [(6, 24), (18, 26)])
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
    c.stripes([(12, 16), (12, 20)], [(13, 13), (12, 23)])
    c.head(15, 10, "wide")


def _bat(c: _Pen, f: int):
    """Wollknäuel anstupsen: geduckt, Frame 1 schnellt die Pfote flach nach vorn."""
    c.tail([(5, 24), (2, 19), (3 + 2 * f, 15)])
    c.ell(8, 25, 5, 4)
    c.ell(15, 27.5, 10, 3.5)
    c.rect(6, 28, 3, 3)
    if f:
        c.rect(21, 29, 9, 2)
    else:
        c.rect(21, 28, 4, 3)
        c.rect(24, 24, 2, 4)
    c.stripes([(10, 23), (13, 24)])
    c.head(22, 23, "wide")


def _scratch(c: _Pen, f: int):
    """Am Kratzbaum: aufgerichtet, Vorderpfoten am Pfosten, die ziehen abwechselnd runter."""
    d = 2 * f
    c.tail([(10, 29), (5, 30), (3, 26)])
    c.rect(11, 25, 2, 6)
    c.rect(15, 25, 2, 6)
    c.ell(14, 19, 5, 8)
    c.rect(17, 11 + d, 7, 2)
    c.rect(18, 15 - d, 6, 2)
    c.stripes([(11, 17), (11, 21)])
    c.head(15, 9, "closed")


def _cheer(c: _Pen, f: int):
    _sit(c, f, "closed")
    c.heart(25, 3 - f)
    c.heart(2, 5 + f)


POSES = {"sit": _sit, "groom": _groom, "vomit": _vomit, "walk": _walk, "crawl": _crawl, "jump": _jump, "fall": _fall, "sleep": _sleep,
         "eat": _eat, "purr": _purr, "dragged": _dragged, "lie": _lie,
         "climb": _climb, "hang": _hang,
         "crouch": _crouch, "swipe": _swipe, "cheer": _cheer, "bat": _bat, "scratch": _scratch,
         "climb_post": _climb_post, "hammock": _hammock,
         "hammock_sleep": lambda c, f: _hammock(c, f, sleep=True),
         "cave_in": _cave_in, "cave_peek": _cave_peek, "cave_duck": _cave_duck, "cave_sleep": _cave_sleep,
         "cave_butt": _cave_butt}


def _fill_holes(img: QImage, x0: int, y0: int) -> None:
    """Eingeschlossene Luecken schliessen: einzelne durchsichtige Pixel mitten im Sprite
    lassen sonst den Hintergrund durchblitzen. Gefuellt wird mit der haeufigsten Nachbarfarbe."""
    from collections import deque

    solid = [[img.pixelColor(x0 + x, y0 + y).alpha() > 0 for y in range(FRAME)] for x in range(FRAME)]
    outside = [[False] * FRAME for _ in range(FRAME)]
    q = deque((x, y) for x in range(FRAME) for y in range(FRAME)
              if (x in (0, FRAME - 1) or y in (0, FRAME - 1)) and not solid[x][y])
    for x, y in q:
        outside[x][y] = True
    while q:
        x, y = q.popleft()
        for a, b in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= a < FRAME and 0 <= b < FRAME and not solid[a][b] and not outside[a][b]:
                outside[a][b] = True
                q.append((a, b))
    for x in range(FRAME):
        for y in range(FRAME):
            if solid[x][y] or outside[x][y]:
                continue
            around = [img.pixelColor(x0 + a, y0 + b) for a, b in
                      ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                      if 0 <= a < FRAME and 0 <= b < FRAME and solid[a][b]]
            if around:
                img.setPixelColor(x0 + x, y0 + y, max(around, key=lambda c: around.count(c)))


def _outline(img: QImage, x0: int, y0: int, color: QColor, h: int = FRAME) -> None:
    """Konturpixel um alle deckenden Pixel des Frames setzen (h = Frame-Höhe)."""
    solid = {(x, y) for y in range(h) for x in range(FRAME)
             if img.pixelColor(x0 + x, y0 + y).alpha() > 0}
    for x, y in {(x + dx, y + dy) for x, y in solid for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}:
        if 0 <= x < FRAME and 0 <= y < h and (x, y) not in solid:
            img.setPixelColor(x0 + x, y0 + y, color)


def render_atlas(fur: QColor | str = FUR_DEFAULT, tabby: float = TABBY_DEFAULT) -> QImage:
    img = QImage(FRAME * max(ANIMS.values()), FRAME * len(ANIMS) * len(MOODS), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    for anim, n in ANIMS.items():
        for mood in MOODS:
            for f in range(n):
                x0, y0 = frame_origin(anim, mood, f)
                p = QPainter(img)
                p.translate(x0, y0)
                p.setClipRect(0, 0, FRAME, FRAME)
                pen = _Pen(p, mood, fur, tabby)
                POSES[anim](pen, f)
                p.end()
                _fill_holes(img, x0, y0)     # Lücken im Fell
                _outline(img, x0, y0, pen.palette.outline)
                _fill_holes(img, x0, y0)     # und was die Kontur gerade eingeschlossen hat
    return img


def ensure_atlas(cache_dir: Path, fur: QColor | str = FUR_DEFAULT,
                 tabby: float = TABBY_DEFAULT) -> Path:
    """Atlas je Fellfarbe und Tigerung zwischenspeichern (Name enthält beides)."""
    tint = QColor(fur)
    if not tint.isValid():
        tint = QColor(FUR_DEFAULT)
    # Posen-Liste im Namen: eine neue Pose ohne hochgesetzte Version lädt sonst ein
    # altes Spritesheet, in dem sie fehlt (die Katze wird dann unsichtbar)
    prefix = f"atlas-v{ATLAS_VERSION}-{zlib.crc32(repr(ANIMS).encode()):08x}-"
    path = cache_dir / f"{prefix}{tint.name()[1:]}-{round(tabby)}.png"
    for old in cache_dir.glob("atlas-v*.png"):
        if not old.name.startswith(prefix):
            old.unlink(missing_ok=True)       # Spritesheets älterer Versionen
    if not path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        render_atlas(tint, tabby).save(str(path))
    return path


# Bett in zwei Ebenen: die Katze liegt zwischen Rückwand und vorderem Rand
FURNITURE_FRAMES = ("bed_back", "bed_front", "bowl_0", "bowl_1", "bowl_2", "bowl_3", "yarn", "yarn_roll",
                    "bowl_tipped", "spill_1", "spill_2", "spill_3") + TREE_FRAMES
FURNITURE_ROWS = max(FRAME_H.values()) // FRAME   # Atlas-Höhe in Frames; kleine stehen unten
BOWL_LEVELS = 3   # Frames bowl_0 .. bowl_3, je Portion im Napf eins; spill_1 .. spill_3 verschüttet
# Frames fürs Inventarbild, übereinander gezeichnet
FURNITURE_ICON = {"bed": ("bed_back", "bed_front"), "bowl": ("bowl_3",), "yarn": ("yarn",), "tree": ("tree",)}


def furniture_height(name: str) -> int:
    return FRAME_H.get(name, FRAME)


def furniture_origin(name: str) -> tuple[int, int]:
    """Linke obere Ecke im Atlas; alle Frames enden an der Atlas-Unterkante."""
    return FURNITURE_FRAMES.index(name) * FRAME, FURNITURE_ROWS * FRAME - furniture_height(name)


def _bed_back(c: _Pen):
    c.ell(16, 26, 15, 6, BED)
    c.ell(16, 27, 12, 4, CUSHION)


def _bed_front(c: _Pen):
    c.rect(2, 28, 28, 3, BED)
    c.rect(4, 29, 24, 1, BED_DARK)


def _yarn(c: _Pen, roll: int):
    """Knäuel; roll verschiebt die Fadenlinien, das sieht nach Rollen aus."""
    c.ell(16, 27, 4, 4, YARN)
    for dx in ((-2, 1), (-1, 2))[roll]:
        c.rect(16 + dx, 24, 1, 6, YARN_DARK)
    c.rect(13, 26 + roll, 6, 1, YARN_DARK)


def _tree(c: _Pen, wear: int = 0):
    """Kratzbaum 32x64: Teppichsockel, Sisalpfosten und Liegefläche mit Rand (wie die
    Liegeflächen der großen, _bigboard). wear: Stufe der Kratzspuren am Pfeiler.
    Liegefläche und Pfeiler müssen zu furniture.TREE_DECK bzw. TREE_POST passen;
    das Bällchen zeichnet das Overlay, damit es pendelt."""
    px, y1, y2 = TREE_POST
    half = bigtree.POST_W // 2
    c.rect(4, y2, 24, 6, CARPET)
    c.rect(4, y2, 24, 1, CARPET_DARK)
    c.rect(px - half, y1, bigtree.POST_W, y2 - y1, SISAL)
    for y in range(y1 + 2, y2 - 1, 3):
        c.rect(px - half, y, bigtree.POST_W, 1, SISAL_DARK)
    if wear:
        _fray(c.p, px, y1, y2, wear, 0)
    _bigboard(c.p, *TREE_DECK[:3], top=True)


def render_furniture() -> QImage:
    img = QImage(FRAME * len(FURNITURE_FRAMES), FRAME * FURNITURE_ROWS, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    draw = {"bed_back": _bed_back, "bed_front": _bed_front,
            **{f"bowl_{n}": lambda c, n=n: _bowl(c, 12, n) for n in range(BOWL_LEVELS + 1)},
            "yarn": lambda c: _yarn(c, 0), "yarn_roll": lambda c: _yarn(c, 1),
            **{name: lambda c, n=n: _tree(c, n) for n, name in enumerate(TREE_FRAMES)},
            "bowl_tipped": _bowl_tipped, **{f"spill_{n}": lambda c, n=n: _spill(c, n) for n in (1, 2, 3)}}
    for name in FURNITURE_FRAMES:
        x0, y0 = furniture_origin(name)
        h = furniture_height(name)
        p = QPainter(img)
        p.translate(x0, y0)
        p.setClipRect(0, 0, FRAME, h)
        pen = _Pen(p, "normal")
        draw[name](pen)
        p.end()
        _outline(img, x0, y0, FURNITURE_OUTLINE, h)
    return img


def ensure_furniture(cache_dir: Path) -> Path:
    """Möbel-Atlas zwischenspeichern. Wie bei ensure_atlas steht die Frame-Liste im Namen,
    damit ein neues Möbel auch ohne hochgesetzte Version frisch gerendert wird."""
    sig = zlib.crc32(repr((FURNITURE_FRAMES, FRAME_H)).encode())
    path = cache_dir / f"furniture-v{FURNITURE_VERSION}-{sig:08x}.png"
    for old in cache_dir.glob("furniture-v*.png"):
        if old != path:
            old.unlink(missing_ok=True)       # ältere Stände
    if not path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        render_furniture().save(str(path))
    return path


def _outline_all(img: QImage, color: QColor) -> None:
    """Kontur um alle deckenden Pixel eines beliebig großen Bildes."""
    w, h = img.width(), img.height()
    solid = {(x, y) for y in range(h) for x in range(w) if img.pixelColor(x, y).alpha() > 0}
    rgb = color.rgba()
    for x, y in solid:
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in solid:
                img.setPixel(nx, ny, rgb)


def _bigboard(p: QPainter, x: int, y: int, w: int, top: bool = False) -> None:
    """Brett (Teppich mit dunkler Unterkante); als Liegefläche mit Rand und Mulde:
    die Katze liegt zwischen den Wülsten links und rechts."""
    p.fillRect(x, y, w, bigtree.BOARD_H, CARPET)
    p.fillRect(x, y + bigtree.BOARD_H - 1, w, 1, CARPET_DARK)
    if top:
        p.fillRect(x, y - 2, 2, 2, BED)
        p.fillRect(x + w - 2, y - 2, 2, 2, BED)
        p.fillRect(x + 2, y, w - 4, 1, CUSHION)


def _fray(p: QPainter, x: int, y1: int, y2: int, level: int, post: int) -> None:
    """Zerkratzter Sisal unten am Pfeiler (wo sie kratzt): helle Stellen und abstehende
    Fasern, je Stufe mehr; fest je Pfeiler, damit nichts flackert."""
    r = random.Random(post * 7919 + level)
    half = bigtree.POST_W // 2
    top = max(y1, y2 - 26)
    for _ in range(4 * level):
        p.fillRect(x - half + r.randrange(bigtree.POST_W), r.randrange(top, y2), 1, 1, SISAL_LIGHT)
    for _ in range(3 * level):
        side = r.choice((-1, 1))
        p.fillRect(x + (half if side > 0 else -half - 1), r.randrange(top, y2 - 1), 1, r.choice((1, 2)), SISAL)


def render_bigtree(w: float, h: float, hanging: bool = False, seed: int = 0,
                   load: tuple[str, int] | None = None, toys: bool = True, wear: str = "") -> QImage:
    """Großer Kratzbaum (bigtree.layout) in Sprite-Pixeln, so groß wie sein Aufbau;
    load = (Brett, Pixel): diese Hängematte hängt so viel tiefer durch (Katze liegt drin);
    toys=False: ohne Bällchen (die zeichnet das Overlay, damit sie pendeln);
    wear: Kratzspuren je Pfeiler (Tree.wear_levels)."""
    lay = bigtree.layout(w, h, hanging, seed)
    img = QImage(lay.w, lay.h, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setPen(QPen(SISAL_DARK, 2))
    for (x1, y1), (x2, y2) in lay.struts:        # Äste hinter allem
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    for x, y1, y2 in lay.posts:
        p.fillRect(x - bigtree.POST_W // 2, y1, bigtree.POST_W, y2 - y1, SISAL)
        for y in range(y1 + 2, y2, 3):
            p.fillRect(x - bigtree.POST_W // 2, y, bigtree.POST_W, 1, SISAL_DARK)
    for i, ch in enumerate(wear[:len(lay.posts)]):
        if ch != "0":
            _fray(p, *lay.posts[i], int(ch), i)
    for x, y, n, col in lay.toys if toys else ():   # Bällchen an Fäden
        p.fillRect(x, y, 1, n, SISAL_DARK)
        p.fillRect(x - 1, y + n, 3, 3, TOY_COLORS[col % len(TOY_COLORS)])
    p.setPen(Qt.PenStyle.NoPen)
    for b in lay.boards:
        bw = b.x2 - b.x1
        if b.style == "hammock":
            dip = load[1] if load is not None and load[0] == b.key else 0
            if dip:   # unter der Katze hängen Rand und Bauch tiefer durch
                mid, rim = (b.x1 + b.x2) / 2, b.y - 1.5
                path = QPainterPath(QPointF(b.x1, rim))
                path.quadTo(QPointF(mid, rim + 2 * dip), QPointF(b.x2, rim))
                path.quadTo(QPointF(mid, b.y - 1 + 2 * (b.sag + dip)), QPointF(b.x1, rim))
                p.setBrush(HAMMOCK)
                p.drawPath(path)
                p.setPen(QPen(HAMMOCK_DARK, 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
                edge = QPainterPath(QPointF(b.x1, rim))
                edge.quadTo(QPointF(mid, rim + 2 * dip), QPointF(b.x2, rim))
                p.drawPath(edge)
                p.setPen(Qt.PenStyle.NoPen)
            else:
                p.setBrush(HAMMOCK)
                p.drawChord(b.x1, b.y - b.sag - 1, bw, 2 * b.sag, 180 * 16, 180 * 16)
                p.fillRect(b.x1, b.y - 2, bw, 1, HAMMOCK_DARK)
        elif b.style == "cave":
            p.fillRect(b.x1, b.y, bw, b.sag, CAVE)
            p.fillRect(b.x1, b.y, bw, 2, CARPET)
            p.setBrush(CAVE_HOLE)
            d = bigtree.DOOR_W
            p.drawEllipse(b.x1 + (bw - d) // 2, b.y + 4, d, d)
            p.fillRect(b.x1 + (bw - d) // 2, b.y + 4 + d // 2, d, b.sag - 4 - d // 2, CAVE_HOLE)
        else:
            _bigboard(p, b.x1, b.y, bw, b.style == "top")
    p.fillRect(1, lay.base_y, lay.w - 2, bigtree.BASE_H, CARPET)
    p.fillRect(1, lay.base_y + (bigtree.BASE_H - 1 if lay.hanging else 0), lay.w - 2, 1, CARPET_DARK)
    p.end()
    _outline_all(img, FURNITURE_OUTLINE)
    return img


def render_front(w: float, h: float, hanging: bool, seed: int, load: tuple[str, int]) -> QImage | None:
    """Teil des Baums vor der Katze (bigtree.front_part): die Wand der Höhle ohne Tür
    oder die durchhängende Hängematte; None, wenn es den nicht gibt."""
    lay = bigtree.layout(w, h, hanging, seed)
    rect = bigtree.front_part(lay, *load)
    if rect is None:
        return None
    img = render_bigtree(w, h, hanging, seed, load, toys=False).copy(*rect)
    if any(b.key == load[0] and b.style == "cave" for b in lay.boards):
        hole = CAVE_HOLE.rgba()
        for y in range(img.height()):
            for x in range(img.width()):
                if img.pixel(x, y) == hole:   # durch die Tür sieht man sie
                    img.setPixel(x, y, 0)
    return img


def furniture_icon(kind: str) -> QImage:
    """Bild fürs Inventar (FURNITURE_ICON), so hoch wie der Frame."""
    h = max(furniture_height(n) for n in FURNITURE_ICON[kind])
    img = QImage(FRAME, h, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    sheet = render_furniture()
    p = QPainter(img)
    for name in FURNITURE_ICON[kind]:
        x0, y0 = furniture_origin(name)
        fh = furniture_height(name)
        p.drawImage(0, h - fh, sheet, x0, y0, FRAME, fh)
    p.end()
    return img


def render_ufo() -> QImage:
    """Untertasse 32x16: Glaskuppel, graue Scheibe, bunte Lichter."""
    img = QImage(32, 16, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setPen(QColor("#2A2F3A"))
    p.setBrush(QColor("#9FE8FF"))
    p.drawEllipse(10, 1, 11, 9)
    p.fillRect(13, 3, 2, 2, QColor("#FFFFFF"))
    p.setBrush(QColor("#A9B2C3"))
    p.drawEllipse(1, 6, 29, 7)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#6C7690"))
    p.drawRect(4, 10, 24, 2)
    for i, c in enumerate(("#FF5A5A", "#FFE15A", "#5AFF8C", "#5AC8FF", "#FF5AE6")):
        p.fillRect(5 + i * 5, 9, 2, 2, QColor(c))
    p.end()
    return img


def render_beam() -> QImage:
    """Traktorstrahl: Trapez, oben schmal, nach unten durchsichtiger. Wird gestreckt."""
    img = QImage(64, 128, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    g = QLinearGradient(0, 0, 0, 128)
    g.setColorAt(0, QColor(200, 255, 170, 230))
    g.setColorAt(1, QColor(200, 255, 170, 90))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(g)
    p.drawPolygon(QPolygonF([QPointF(22, 0), QPointF(42, 0), QPointF(64, 128), QPointF(0, 128)]))
    p.end()
    return img


def ensure_ufo(cache_dir: Path) -> tuple[Path, Path]:
    """UFO und Strahl als PNG zwischenspeichern."""
    out = (cache_dir / f"ufo-v{UFO_VERSION}.png", cache_dir / f"beam-v{UFO_VERSION}.png")
    for path, render in zip(out, (render_ufo, render_beam)):
        if not path.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
            render().save(str(path))
    return out


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
    p.add_argument("--tabby", type=int, default=TABBY_DEFAULT, metavar="PROZENT",
                   help=f"Tigerung 0-200 (Standard: {TABBY_DEFAULT})")
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
    elif not render_atlas(args.color, args.tabby).save(args.atlas):
        print(f"taskbar-cat: Atlas nicht schreibbar: {args.atlas}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_cli(sys.argv))
