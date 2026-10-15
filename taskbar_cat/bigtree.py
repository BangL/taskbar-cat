"""Großer Kratzbaum (rein, ohne Qt): frei in Breite und Höhe, der Aufbau ergibt sich daraus.

Mehr Breite -> mehr Pfeiler, mehr Höhe -> mehr Etagen. Jeder Pfeiler endet auf eigener
Höhe mit einer Liegefläche (manchmal teilen sich Nachbarn eine), dazwischen Liegebretter
mit Ästen, Hängematten, eine Höhle und Bällchen an Fäden. Der Aufbau ist zufällig, aber je
Größe und Seed fest: jede Größenänderung würfelt neu, Neuzeichnen nicht. Hängend klebt
der Baum am oberen Bildschirmrand und wächst nach unten.

Maße in Sprite-Pixeln (32 = Kantenlänge der Katze), Ursprung links oben, Boden bei H.
In der Welt wird jede Fläche zu einer schmalen Kante (wie ein Panel: nur oben begehbar)
und jeder Pfeiler zu einer Wand, an der die Katze hochklettert.
"""
import functools
import math
import random
from dataclasses import dataclass, field

from .world import Rect, Wall, Win

KIND = "bigtree"           # der erste Baum (bleibt entfernt erhalten); weitere heißen bigtree2, bigtree3, ...
NAME = "Großer Kratzbaum"
BOARD_ID = "furniture:bigtree:"
BASE_KEY = "base"          # Kante des Sockels (stehend)
STACK = (1 << 30) + 1      # über allen Fenstern und dem kleinen Kratzbaum
MIN_W, MAX_W = 24, 128
MIN_H, MAX_H = 40, 400
DEFAULT = (48, 100)
BASE_H = 5                 # Sockel bzw. Deckenplatte
POST_W = 6
BOARD_H = 4
LEVEL_GAP = 34             # Wunschabstand der Etagen (Katze passt dazwischen)
POST_SPACING = 40          # ab so viel Breite je Pfeiler
MIN_BOARD = 15
MIN_DY = 14                # Mindestabstand übereinanderliegender Flächen
MIN_WALL = 40              # kürzere Kletterstrecken lohnen nicht (wie world.MIN_PIECE)
TOY_COLORS = 5             # Farbindex der Bällchen, Farben in sprites
WHEEL_STEP = 1.06          # Größenfaktor je Mausrad-Rastung (120)
LOAD_SAG = 4               # so viel tiefer hängt eine Hängematte, in der die Katze liegt
LOAD_TIME = 0.4            # so lange (s) sinkt sie ein
CAT_SINK = 6               # so tief liegt die Katze dann im Stoff (Matte davor)
DOOR_W = 12                # Tür der Höhle: ihr Kopf passt hindurch
CAVE_MIN_W = 28            # schmaler wird keine Höhle (geduckt ist sie so lang)
WEAR_LEVELS = 3            # sichtbare Stufen der Kratzspuren
TOY_REACH = (4, 24)        # Bällchen so weit (Sprite-px) über ihrer Fläche: mit der Pfote erreichbar


def is_tree(kind) -> bool:
    return isinstance(kind, str) and kind.startswith(KIND) and (kind == KIND or kind[len(KIND):].isdigit())


def clamp_size(w: float, h: float) -> tuple[float, float]:
    return min(max(w, MIN_W), MAX_W), min(max(h, MIN_H), MAX_H)


# --- Aufbau ---

@dataclass(frozen=True)
class Board:
    key: str        # Name der Kante in der Welt (je Baum eindeutig)
    x1: int
    x2: int
    y: int          # Oberkante = Lauffläche
    style: str      # "board", "top" (Liegefläche am Pfeilerende), "hammock", "cave"
    sag: int = 5    # Hängematte: so tief hängt sie durch; Höhle: so tief ist sie
    posts: tuple = ()   # (Pfeiler, Seite des Bretts von dort aus) zum Hochklettern


@dataclass(frozen=True)
class Layout:
    w: int
    h: int
    hanging: bool
    base_y: int            # Sockel (stehend unten) bzw. Deckenplatte (hängend oben)
    posts: tuple           # (x-Mitte, y oben, y unten)
    boards: tuple          # Board
    struts: tuple          # ((x1, y1), (x2, y2)) Äste zwischen Pfeiler und Brett
    toys: tuple            # (x, y-Aufhängung, Fadenlänge, Farbindex)


def layout(w: float, h: float, hanging: bool = False, seed: int = 0) -> Layout:
    W, H = (int(round(v)) for v in clamp_size(w, h))
    return _layout(W, H, bool(hanging), int(seed))


@functools.lru_cache(maxsize=512)
def _layout(W: int, H: int, hanging: bool, seed: int) -> Layout:
    r = random.Random(f"bigtree:{W}x{H}:{int(hanging)}" + (f":{seed}" if seed else ""))
    if hanging:
        base_y, lounge_y = 0, H - 1 - BOARD_H
        upper, lower = BASE_H, lounge_y          # dazwischen die Etagen
    else:
        base_y, lounge_y = H - 1 - BASE_H, 3
        upper, lower = lounge_y, base_y
    n = max(1, min(4, round(W / POST_SPACING)))
    slot = W / n
    xs = [min(W - 5, max(4, round(slot * (i + 0.5) + r.uniform(-0.2, 0.2) * slot))) for i in range(n)]
    # jeder Pfeiler hat seinen Bereich bis zur Mitte zum Nachbarn: Bretter überlappen nicht
    lim = [(1 if i == 0 else (xs[i - 1] + xs[i]) // 2 + 1,
            W - 1 if i == n - 1 else (xs[i] + xs[i + 1]) // 2 - 1) for i in range(n)]
    levels = max(1, round((lower - upper) / LEVEL_GAP))
    gap = (lower - upper) / levels
    lo_y, hi_y = upper + 12, lower - 12
    boards, struts, toys, wanted = [], [], [], []

    # Ende jedes Pfeilers: einer reicht ganz hin, die anderen enden früher
    tall = r.randrange(n)
    sign = 1 if not hanging else -1
    ends = [lounge_y if i == tall or n == 1 else round(lounge_y + sign * r.uniform(0.15, 0.65) * (lower - upper))
            for i in range(n)]
    # manchmal tragen Nachbarpfeiler gemeinsam eine durchgehende Liegefläche
    groups = [(i, i) for i in range(n)]
    if n >= 2 and r.random() < 0.4:
        a = r.randrange(n - 1)
        b = r.randrange(a + 1, n)
        e = (min if not hanging else max)(ends[a:b + 1])
        ends[a:b + 1] = [e] * (b - a + 1)
        groups = [(i, i) for i in range(a)] + [(a, b)] + [(i, i) for i in range(b + 1, n)]

    def reaches(i, y) -> bool:
        return y - ends[i] >= MIN_DY if not hanging else ends[i] - y >= MIN_DY

    def free(x1, x2, y) -> bool:
        return all(b.x2 < x1 or x2 < b.x1 or abs(b.y - y) >= MIN_DY for b in boards)

    def pick_y(base, spread, x1, x2, posts=()):
        for _ in range(4):
            y = min(hi_y, max(lo_y, round(base + r.uniform(-spread, spread) * gap)))
            if free(x1, x2, y) and all(reaches(i, y) for i in posts):
                return y
        return None

    for a, b in groups:   # Liegeflächen zuerst, alles andere hält Abstand zu ihnen
        half = r.randint(10, max(10, min(W - 2, 34) // 2)) if n == 1 else r.randint(7, 14)
        x1, x2 = max(lim[a][0], xs[a] - half), min(lim[b][1], xs[b] + half)
        posts = tuple((i, s) for i in range(a, b + 1) for s in (-1, 1))
        boards.append(Board(f"top{a}" if a == b else f"top{a}-{b}", x1, x2, ends[a], "top", posts=posts))
        if not hanging and r.random() < 0.6:
            wanted.append((x1, x2, ends[a] + BOARD_H))

    for k in range(1, levels):
        base = lower - k * gap
        busy = set()
        for i in range(n - 1):                 # Hängematten zwischen Nachbarpfeilern
            if i in busy or xs[i + 1] - xs[i] - 6 < MIN_BOARD or r.random() >= 0.35:
                continue
            y = pick_y(base + 4, 0.25, xs[i] + 3, xs[i + 1] - 3, (i, i + 1))
            if y is None:
                continue
            boards.append(Board(f"{k}:h{i}", xs[i] + 3, xs[i + 1] - 3, y, "hammock", r.randint(3, 7),
                                ((i, 1), (i + 1, -1))))
            busy |= {i, i + 1}
        for i in range(n):
            if i in busy or r.random() >= (0.85 if n == 1 else 0.65):
                continue
            sides = (-1, 1) if r.random() < 0.2 else (r.choice((-1, 1)),)
            for side in sides:
                length = r.randint(14, 30)
                x1, x2 = (xs[i] - 4, xs[i] + length) if side > 0 else (xs[i] - length, xs[i] + 4)
                x1, x2 = max(lim[i][0], x1), min(lim[i][1], x2)
                y = pick_y(base, 0.3, x1, x2, (i,)) if x2 - x1 >= MIN_BOARD else None
                if y is None:
                    continue
                boards.append(Board(f"{k}:{i}:{side}", x1, x2, y, "board", posts=((i, side),)))
                outer = x2 - 2 if side > 0 else x1 + 2
                if abs(outer - xs[i]) > 8 and r.random() < 0.75:
                    if not hanging and y + BOARD_H + 12 < base_y:      # Stütze darunter
                        struts.append(((xs[i], y + BOARD_H + r.randint(5, 11)), (outer, y + BOARD_H)))
                    elif hanging and y - 12 > BASE_H:                  # Ast darüber trägt es
                        struts.append(((xs[i], y - r.randint(5, 11)), (outer, y)))
                if r.random() < 0.45:
                    wanted.append((x1, x2, y + BOARD_H))

    # Höhle an einem zufälligen Pfeiler auf dem Sockel (hängende Bäume haben keine)
    if not hanging and levels >= 2 and gap >= 26 and r.random() < 0.7:
        i = r.randrange(n)
        width = r.randint(28, 36)             # die Katze passt hinein (geduckt 28 px)
        side = r.choice((-1, 1))
        cx1, cx2 = (xs[i] + 3, xs[i] + 3 + width) if side > 0 else (xs[i] - 3 - width, xs[i] - 3)
        cx1, cx2 = max(1, cx1), min(W - 1, cx2)
        depth = r.randint(16, 19)
        if cx2 - cx1 >= CAVE_MIN_W and free(cx1, cx2, base_y - depth):
            boards.append(Board("cave", cx1, cx2, base_y - depth, "cave", depth, ((i, side),)))

    # Bällchen: nicht vor einem Pfeiler, Faden endet über dem nächsten Hindernis darunter
    def below(x, y) -> int:
        tops = [base_y if not hanging else H - 1]
        for b in boards:
            if b.x1 - 1 <= x <= b.x2 + 1 and b.y > y:
                tops.append(b.y - (b.sag + 2 if b.style == "hammock" else 3 if b.style == "top" else 0))
        return min(t for t in tops if t > y)

    for x1, x2, y in wanted:
        for _ in range(4):
            if x2 - 2 < x1 + 2:
                break
            x = r.randint(x1 + 2, x2 - 2)
            if any(abs(x - px) <= POST_W // 2 + 2 for px in xs):
                continue
            room = below(x, y) - y - 3 - 2       # Kugel 3 px, 2 px Luft
            if room >= 4:
                toys.append((x, y, r.randint(4, min(14, room)), r.randrange(TOY_COLORS)))
            break

    posts = tuple((x, BASE_H, e) if hanging else (x, e, base_y) for x, e in zip(xs, ends))
    return Layout(W, H, hanging, base_y, posts, tuple(boards), tuple(struts), tuple(toys))


# --- Zustand je Baum ---

@dataclass
class Tree:
    w: float = DEFAULT[0]      # Kommazahlen: kleine Touchpad-Schritte summieren sich
    h: float = DEFAULT[1]
    seed: int = 0
    hanging: bool = False
    top: float = 0.0           # hängend: Oberkante (global)
    wear: list = field(default_factory=list)   # je Pfeiler 0..1: so zerkratzt ist der Sisal

    def size(self) -> tuple[int, int]:
        return int(round(self.w)), int(round(self.h))

    def resize(self, w: float, h: float) -> None:
        self.w, self.h = clamp_size(w, h)

    def layout(self) -> Layout:
        return layout(self.w, self.h, self.hanging, self.seed)

    def wheeled(self, dx: float, dy: float) -> tuple[float, float]:
        """Neue Größe nach dem Mausrad: hoch/runter = Höhe, seitlich = Breite."""
        return self.w * WHEEL_STEP ** (dx / 120), self.h * WHEEL_STEP ** (dy / 120)

    def to_dict(self) -> dict:
        d = {"size": [round(self.w, 2), round(self.h, 2)], "seed": self.seed}
        if self.hanging:
            d["hang_top"] = self.top
        if any(self.wear):
            d["wear"] = [round(v, 4) for v in self.wear]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Tree":
        t = cls()
        try:
            t.seed = int(d.get("seed", 0))
            t.resize(float(d["size"][0]), float(d["size"][1]))
        except (KeyError, TypeError, ValueError, IndexError):
            pass
        top = d.get("hang_top")
        if isinstance(top, (int, float)) and not isinstance(top, bool):
            t.hanging, t.top = True, float(top)
        wear = d.get("wear")
        if isinstance(wear, list):
            t.wear = [max(0.0, min(1.0, float(v))) if isinstance(v, (int, float)) else 0.0 for v in wear]
        return t

    def scratch(self, post: int, amount: float) -> None:
        """Einmal am Pfeiler gekratzt (amount = 1 / Kratzer bis ganz zerfranst)."""
        self.wear += [0.0] * (post + 1 - len(self.wear))
        self.wear[post] = min(1.0, self.wear[post] + amount)

    def wear_levels(self) -> str:
        """Sichtbare Stufe je Pfeiler als Ziffern ("" = nirgends zerkratzt); fürs Bild.
        Schon der erste Kratzer ist zu sehen, ganz zerfranst ist die höchste Stufe."""
        levels = "".join(str(min(WEAR_LEVELS, math.ceil(round(v * WEAR_LEVELS, 6)))) for v in self.wear)
        return levels.rstrip("0")

    def variant(self, name: str) -> dict:
        """Gespeicherte Variante: alles, was den Aufbau festlegt."""
        w, h = self.size()
        return {"name": name, "w": w, "h": h, "seed": self.seed, "hanging": self.hanging}

    def apply(self, variant: dict) -> None:
        self.seed = int(variant["seed"])
        self.resize(float(variant["w"]), float(variant["h"]))


def valid_variant(v) -> bool:
    try:
        return isinstance(v, dict) and isinstance(v["name"], str) and v["name"] != "" and \
            all(isinstance(v[k], (int, float)) for k in ("w", "h", "seed"))
    except KeyError:
        return False


# --- Welt und Maus ---

def geometry(tree: Tree, pos: tuple[float, float], sprite: float) -> tuple[float, float, float, Layout]:
    """Linke obere Ecke (global), Maßstab und Aufbau; pos ist Mitte unten wie bei jedem Möbel."""
    s = sprite / 32
    lay = tree.layout()
    return pos[0] - lay.w / 2 * s, pos[1] - lay.h * s, s, lay


def structures(kind: str, tree: Tree, pos, sprite: float) -> tuple[list[Win], list[Wall]]:
    """Kanten (jede Fläche, stehend auch der Sockel) und Wände (Pfeiler, an denen sie zu einer
    Fläche hochklettert). Eine Wand reicht vom Ende des Pfeilers bis zur Fläche und gehört zu
    deren Kante: oben angekommen, zieht sich die Katze dorthin hoch."""
    left, top, s, lay = geometry(tree, pos, sprite)
    wins, walls = [], []
    if not lay.hanging:   # hängend ist der Sockel die Deckenplatte am oberen Rand
        wins.append(Win(f"{BOARD_ID}{kind}:{BASE_KEY}",
                        Rect(left + s, top + lay.base_y * s, (lay.w - 2) * s, BASE_H * s),
                        STACK, False, False, True))
    for b in lay.boards:
        owner = f"{BOARD_ID}{kind}:{b.key}"
        wins.append(Win(owner, Rect(left + b.x1 * s, top + b.y * s, (b.x2 - b.x1) * s, BOARD_H * s),
                        STACK, False, False, True))
        for i, side in b.posts:
            x, _, foot = lay.posts[i]                  # foot: unteres Ende des Pfeilers
            if (foot - b.y) * s < MIN_WALL:
                continue
            # Brett rechts vom Pfeiler -> sie klettert links daran hoch (wie an einer
            # linken Fensterkante) und zieht sich nach rechts hinauf
            walls.append(Wall(left + (x - side * POST_W / 2) * s, top + b.y * s, top + foot * s,
                              owner, -side))
    return wins, walls


def parts(tree: Tree, pos, sprite: float) -> list[Rect]:
    """Sichtbare Teile (für Maus und Input-Region), nicht die Lücken dazwischen; [0] = Sockel."""
    left, top, s, lay = geometry(tree, pos, sprite)

    def r(x, y, w, h):
        return Rect(left + x * s, top + y * s, max(1.0, w * s), max(1.0, h * s))

    out = [r(1, lay.base_y, lay.w - 2, BASE_H)]
    out += [r(x - POST_W // 2, y1, POST_W, y2 - y1) for x, y1, y2 in lay.posts]
    for b in lay.boards:
        hb = b.sag if b.style == "cave" else BOARD_H + (2 if b.style == "top" else 0)
        out.append(r(b.x1, b.y - (2 if b.style in ("top", "hammock") else 0), b.x2 - b.x1, hb))
    return out


def in_hammock(owner: str | None) -> bool:
    return bool(owner) and owner.startswith(BOARD_ID) and ":h" in owner[len(BOARD_ID):]


def hammock_of(owner: str | None) -> tuple[str, str] | None:
    """(Baumart, Brett) der Hängematte zu einem Kantennamen."""
    if not in_hammock(owner):
        return None
    kind, key = owner[len(BOARD_ID):].split(":", 1)
    return kind, key


def load_sag(lying: float) -> int:
    """Zusätzliches Durchhängen, nachdem sie so lange (s) in der Hängematte liegt."""
    return min(LOAD_SAG, max(0, int(lying / LOAD_TIME * LOAD_SAG)))


def front_part(lay: Layout, key: str, px: int) -> tuple[int, int, int, int] | None:
    """Ausschnitt (x, y, w, h) des Baumbilds, der vor der Katze liegt: die durchhängende
    Matte (darüber ist das Bild leer, also bleibt sie von der Mitte aufwärts sichtbar) oder
    die Wand der Höhle (ohne Tür, sprites.render_front), hinter der sie verschwindet."""
    b = next((b for b in lay.boards if b.key == key and b.style in ("hammock", "cave")), None)
    if b is None or px <= 0:
        return None
    if b.style == "cave":
        return b.x1, b.y, b.x2 - b.x1, b.sag
    y = b.y - 3
    return b.x1, y, b.x2 - b.x1, min(lay.h - y, b.sag + px + 5)


def reachable_toys(lay: Layout) -> list[tuple[int, str]]:
    """Bällchen (Index in lay.toys), nach denen sie von einer Fläche darunter mit der Pfote
    schlagen kann, samt Schlüssel dieser Fläche (Brett oder BASE_KEY)."""
    out = []
    for i, (x, y, n, _) in enumerate(lay.toys):
        ball = y + n + 3
        below = [(b.y, b.key) for b in lay.boards if b.x1 <= x <= b.x2 and b.y > ball]
        if not lay.hanging and 1 <= x < lay.w - 1:
            below.append((lay.base_y, BASE_KEY))
        if below:
            surf, key = min(below)
            if TOY_REACH[0] <= surf - ball <= TOY_REACH[1]:
                out.append((i, key))
    return out


def cave_of(lay: Layout) -> Board | None:
    """Höhle (nur stehende Bäume haben eine, sie steht auf dem Sockel)."""
    return next((b for b in lay.boards if b.style == "cave"), None)
