"""Möbel: Katzenbett, Napf, Wollknäuel und Kratzbaum, je eins, dazu beliebig viele große
Kratzbäume (bigtree.py). Aufgestellt fallen sie auf die nächste Kante darunter (Boden oder
Fenster), fahren mit dem Fenster mit und fallen herunter, wenn es verschwindet; sonst
liegen sie im Inventar (große Kratzbäume nicht). Ein großer Kratzbaum, der an den oberen Rand gezogen wird, klebt
dort und hängt herab (rein, ohne Qt)."""
import math
import random

from . import bigtree
from .bigtree import Tree, is_tree
from .world import GRAVITY, Platform, Rect, Wall, Win, World

KINDS = ("bed", "bowl", "yarn", "tree", bigtree.KIND)
NAMES = {"bed": "Katzenbett", "bowl": "Napf", "yarn": "Wollknäuel", "tree": "Kratzbaum",
         bigtree.KIND: bigtree.NAME}
# Kleiner Kratzbaum: ein Frame je Verschleißstufe des Sisals (siehe bigtree.wear_level)
TREE_FRAMES = ("tree",) + tuple(f"tree_wear{n}" for n in range(1, bigtree.WEAR_LEVELS + 1))
# Frame-Höhe in Pixeln, wenn nicht 32 (Breite ist immer 32)
FRAME_H = {name: 64 for name in TREE_FRAMES}
# Sichtbarer Teil im Frame (x, y, w, h): Mausfläche und Abstand zum Bildschirmrand
BOX = {"bed": (1, 21, 30, 11), "bowl": (11, 25, 10, 7), "yarn": (11, 22, 10, 10),
       "tree": (3, 8, 26, 55)}
# Liegefläche oben auf dem Kratzbaum (x, y, w, h im Frame); wird zur begehbaren Kante.
# So dick wie ein Brett des großen Baums, damit beide gleich gezeichnet werden.
TREE_DECK = (3, 8, 26, bigtree.BOARD_H)
# Sisalpfeiler (x-Mitte, oben, unten im Frame): daran klettert und kratzt sie,
# so breit wie der eines großen Baums
TREE_POST = (16, TREE_DECK[1] + TREE_DECK[3], 57)
# Bällchen an der Liegefläche (x, Aufhängung, Fadenlänge, Farbe wie bigtree): hängt bis in
# Pfotenhöhe über dem Boden, damit sie es von dort anspielen kann (TOY_REACH)
TREE_TOY = (25, TREE_POST[1], 28, 0)
TREE_ID = "furniture:tree"
TREE_STACK = 1 << 30   # liegt im Overlay über allen Fenstern
BOUNCY = ("yarn",)     # hüpft, rollt und lässt sich werfen; der Rest wird abgesetzt
BOWL_PORTIONS = 3
ROLL_FRICTION = 250   # px/s², so schnell bleibt das rollende Knäuel liegen
ROLL_BOUNCE = 0.5     # Anteil der Geschwindigkeit nach dem Abprallen an einer Wand
DROP_BOUNCE = 0.4     # Anteil der Fallgeschwindigkeit, mit der es wieder hochspringt
REST_VY = 200         # langsamer aufgekommen: liegen bleiben statt hüpfen
MAX_THROW = 3000
MAX_SUBSTEP_PX = 20
SNAP_PX = 40          # Oberkante eines großen Kratzbaums so nah am oberen Rand: er hängt
# Bällchen am großen Kratzbaum: Pendel, das sie mit der Pfote anschubst
TOY_G = 900.0         # px/s², weicher als die echte Schwerkraft: sieht nach Faden aus
TOY_DAMP = 1.5        # 1/s, so schnell kommt es zur Ruhe
TOY_KICK = 7.0        # rad/s je Pfotenschlag
TOY_MAX = 1.3         # rad, weiter schwingt es nicht
TOY_STEP = 1 / 120    # s, Teilschritte fürs Pendel
# Fliegen über verschüttetem Futter
FLY_DELAY = 4.0       # s, so lange liegt es, bis die erste kommt
FLY_EVERY = 2.0       # s, danach kommt alle so viele Sekunden eine weitere
SPILL_DX = 10         # so weit (Frame-Pixel) neben dem umgedrehten Napf liegt das Futter


def fly_path(t: float, i: int) -> tuple[float, float, bool]:
    """Wo Fliege i zur Zeit t ist: (dx, dy) in Frame-Pixeln ab der Mitte des Futters
    (dy nach oben negativ) und ob die Flügel gerade oben sind. Unruhige Achten, je Fliege anders."""
    a, b = 2.3 + 0.7 * i, 3.1 + 0.5 * i
    ph = 1.7 * i
    dx = 6 * math.sin(a * t + ph) + 2 * math.sin(3.7 * b * t)
    dy = -7 - 3 * math.sin(b * t + 2 * ph) - 1.5 * math.cos(5.3 * a * t)
    return dx, dy, int(t * 24 + i) % 2 == 0


def window_rects(world: World) -> list[Rect]:
    """Die Fenster der Arbeitsumgebung (ohne die Kanten, die die Möbel selbst einbringen).
    Hinter ihnen verschwindet ein Kratzbaum, der so eingestellt ist."""
    return [w.rect for w in world.windows if w.stack < TREE_STACK]


def on_tree(owner: str) -> bool:
    """Gehört die Kante (oder Wand) zu einem Kratzbaum - der Liegefläche des kleinen
    oder einer Fläche bzw. einem Pfeiler eines großen?"""
    return owner == TREE_ID or owner.startswith(bigtree.BOARD_ID)


def half_width(kind: str, sprite: float) -> float:
    """Halbe Breite des sichtbaren Teils in px bei Sprite-Kantenlänge sprite
    (große Kratzbäume: Furniture.half_width, die Breite hängt am einzelnen Baum)."""
    w = BOX[kind][2] if kind in BOX else bigtree.DEFAULT[0]
    return w / 2 * sprite / 32


class Body:
    """Ein Möbelstück mit Schwerkraft. x/y ist Mitte unten wie bei der Katze."""

    def __init__(self, bouncy: bool = False):
        self.bouncy = bouncy
        self.placed = False
        self.held = False                    # hängt gerade am Mauszeiger
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.platform: Platform | None = None   # None = in der Luft
        self._ride: Rect | None = None
        self.pending: tuple[str, float] | None = None   # altes Format: (Monitor, Abstand)

    @property
    def resting(self) -> bool:
        """Steht oder rollt auf einer Kante (die Katze kann hin)."""
        return self.placed and not self.held and self.platform is not None

    def drop(self, x: float, y: float) -> None:
        """Bei (x, y) loslassen; fällt auf die nächste Kante darunter."""
        self.placed, self.held = True, False
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.platform = self._ride = None
        self.pending = None

    def hold(self, x: float, y: float) -> None:
        self.drop(x, y)
        self.held = True

    def throw(self, vx: float, vy: float) -> None:
        if not self.held:
            return
        self.held = False
        if self.bouncy:
            self.vx = max(-MAX_THROW, min(MAX_THROW, vx))
            self.vy = max(-MAX_THROW, min(MAX_THROW, vy))

    def store(self) -> None:
        self.drop(0.0, 0.0)
        self.placed = False

    def kick(self, vx: float, vy: float = 0.0) -> None:
        """vy (negativ) lässt es abheben: so kommt es auch über eine Kante hinweg."""
        if not (self.resting and self.bouncy):
            return
        self.vx = vx
        if vy:
            self.vy = vy
            self.platform = self._ride = None

    def shove(self, vx: float) -> None:
        """Über die Kante schieben (auch was nicht rollt, rutscht dann ein Stück)."""
        if self.resting:
            self.vx = vx

    def step(self, world: World, dt: float, half: float) -> None:
        if not self.placed or self.held:
            return
        if self.pending is not None:
            self._unpack(world)
        if world.output_at(self.x, self.y - 1) is None:
            self._respawn(world)
        elif self.platform is None:
            self._fly(world, dt, half)
        else:
            self._roll(world, dt, half)

    def _unpack(self, world: World) -> None:
        name, offset = self.pending
        o = next((o for o in world.outputs if o.name == name), None)
        if o is None:
            self.pending = None
            self._respawn(world)
        else:
            self.drop(o.work_area.x + offset, o.work_area.bottom - 1)

    def _respawn(self, world: World) -> None:
        o = next((o for o in world.outputs if o.name not in world.forbidden_outputs), world.outputs[0])
        self.drop(o.work_area.x + o.work_area.w / 2, o.work_area.bottom - 1)

    def _fall(self) -> None:
        self.platform = self._ride = None
        self.vy = 0.0

    def _land(self, world: World, p: Platform) -> None:
        self.platform = p
        self.y = p.y
        self.vy = 0.0
        if not self.bouncy:
            self.vx = 0.0
        self._ride = None if p.is_floor else world.window_rect(p.owner)

    def _roll(self, world: World, dt: float, half: float) -> None:
        p = self.platform
        if not p.is_floor:   # mit dem Fenster mitfahren
            rect = world.window_rect(p.owner)
            if rect is None:
                self._fall()
                return
            if self._ride is not None:
                self.x += rect.x - self._ride.x
            self._ride = rect
        q = world.platform_by_owner_at(p.owner, self.x)
        if q is None:        # Fenster weg oder hier verdeckt
            self._fall()
            return
        self.platform, self.y = q, q.y
        if not self.vx:
            return
        self.x += self.vx * dt
        if not q.x1 <= self.x <= q.x2:
            n = world.neighbor(q, 1 if self.vx > 0 else -1)
            if n is not None:
                self.platform = n
                self._ride = None if n.is_floor else world.window_rect(n.owner)
            elif q.is_floor:     # äußerer Rand der Arbeitsfläche
                self.x = min(max(self.x, q.x1 + half), q.x2 - half)
                self.vx = -self.vx * ROLL_BOUNCE
            else:                # über die Fensterkante gerollt
                self._fall()
                return
        slow = ROLL_FRICTION * dt
        self.vx = 0.0 if abs(self.vx) <= slow else self.vx - math.copysign(slow, self.vx)

    def _fly(self, world: World, dt: float, half: float) -> None:
        b = world.bounds()
        vmax = max(abs(self.vy) + GRAVITY * dt, abs(self.vx))
        n = max(1, math.ceil(vmax * dt / MAX_SUBSTEP_PX))
        h = dt / n
        for _ in range(n):
            prev_y = self.y
            self.vy += GRAVITY * h
            self.x += self.vx * h
            self.y += self.vy * h
            if self.x < b.x + half:
                self.x, self.vx = b.x + half, abs(self.vx) * ROLL_BOUNCE
            elif self.x > b.right - half:
                self.x, self.vx = b.right - half, -abs(self.vx) * ROLL_BOUNCE
            if self.y < b.y + 2 * half:
                self.y, self.vy = b.y + 2 * half, 0.0
            if self.vy > 0:
                p = self._landing(world, prev_y)
                if p is not None:
                    if self.bouncy and self.vy > REST_VY:   # hüpft noch einmal
                        self.y, self.vy = p.y, -self.vy * DROP_BOUNCE
                    else:
                        self._land(world, p)
                        return
            if self.y > b.bottom + 4 * half:
                self._respawn(world)
                return

    def _landing(self, world: World, prev_y: float) -> Platform | None:
        best = None
        for p in world.platforms:
            if p.x1 <= self.x <= p.x2 and prev_y <= p.y <= self.y and (best is None or p.y < best.y):
                best = p
        if best is None:   # unter den Boden geraten
            floor = world.platform_below(self.x, -math.inf, floors_only=True)
            if floor is not None and self.y > floor.y:
                best = floor
        return best


class Furniture:
    def __init__(self):
        self.bodies = {k: Body(k in BOUNCY) for k in KINDS}
        # große Kratzbäume: "bigtree" bleibt entfernt als Vorlage liegen, weitere ("bigtree2" ...) kommen dazu
        self.trees: dict[str, Tree] = {bigtree.KIND: Tree()}
        self.tree_wear = 0.0   # kleiner Kratzbaum: 0..1, so zerkratzt ist sein Sisal
        self.tree_behind = False   # kleiner Kratzbaum: steht hinter den Fenstern
        self.food = 0   # Portionen im Napf
        # Von der Katze heruntergeschubst: liegt umgedreht, das Futter daneben, bis man ihn
        # mit der Maus wieder aufhebt
        self.tipped = False
        self.spill = 0          # verschüttete Portionen
        self.spill_side = 1     # auf dieser Seite des Napfs liegt das Futter
        self.spill_age = 0.0    # s, so lange liegt es schon da (lockt Fliegen an; ihre Flugzeit)
        self.fly_ids: list[int] = []   # Fliegen, die gerade da sind (Nummer für fly_path), älteste zuerst
        self.flies_eaten = 0    # von der Katze gefangen; neue kommen nach
        self._fly_wait = FLY_DELAY   # s bis zur nächsten Fliege
        self._shoved = False    # rutscht oder fällt gerade, weil sie ihn geschubst hat
        self.toy_swing: dict[tuple[str, int], list[float]] = {}   # (Baum, Bällchen) -> [Winkel, rad/s]
        self._world_cache: tuple | None = None
        self._tree_cache: tuple | None = None   # (Schlüssel, Welt ohne, Welt mit Bäumen)
        self._world: World | None = None         # letzte Welt aus world_with
        self._sprite: float | None = None

    def half_width(self, kind: str, sprite: float) -> float:
        if kind in self.trees:
            return self.trees[kind].size()[0] / 2 * sprite / 32
        return half_width(kind, sprite)

    @property
    def yarn(self) -> Body:
        return self.bodies["yarn"]

    def placed(self, kind: str) -> bool:
        return self.bodies[kind].placed

    def position(self, kind: str, world: World) -> tuple[float, float] | None:
        """Mitte unten (wie bei der Katze); None im Inventar oder außerhalb aller Monitore."""
        b = self.bodies[kind]
        if not b.placed or b.pending is not None or world.output_at(b.x, b.y - 1) is None:
            return None
        return b.x, b.y

    def visible(self, kind: str, world: World) -> tuple[float, float] | None:
        """Wie position, aber nicht über einem Vollbildfenster (dort ist auch die Katze weg)."""
        pos = self.position(kind, world)
        if pos is None or world.output_at(pos[0], pos[1] - 1).name in world.fullscreen_outputs:
            return None
        return pos

    @property
    def bowl_upside_down(self) -> bool:
        """Umgedreht: liegt so da oder fällt gerade, nachdem sie ihn geschubst hat."""
        return self.tipped or (self._shoved and self.bodies["bowl"].platform is None)

    def usable(self, kind: str, world: World) -> tuple[float, float] | None:
        """Wie position, aber nur auf erlaubten Monitoren und solange es auf einer Kante steht
        (der umgedrehte Napf taugt nicht zum Fressen)."""
        pos = self.position(kind, world)
        if (pos is None or not self.bodies[kind].resting or (kind == "bowl" and self.tipped)
                or world.output_at(pos[0], pos[1] - 1).name in world.forbidden_outputs):
            return None
        return pos

    def platform(self, kind: str) -> Platform | None:
        return self.bodies[kind].platform

    def put(self, kind: str, world: World, x: float, y: float, half: float) -> bool:
        """Mit der Maus halten (Mitte unten bei x, y), bis release es loslässt;
        ein festgestellter großer Kratzbaum bleibt stehen."""
        if self.locked(kind):
            return False
        self.bodies[kind].hold(x, y)
        if kind == "bowl":
            self._right_bowl()   # aufgehoben: wieder richtig herum, das Verschüttete ist weg
        if kind in self.trees:   # Vorschau: hängend, solange er oben dran ist
            self.trees[kind].hanging = self._near_top(kind, world, self._sprite) is not None
        return True

    def release(self, kind: str, vx: float, vy: float) -> None:
        """Maus losgelassen: fällt herunter; das Knäuel fliegt mit Schwung weiter,
        ein großer Kratzbaum am oberen Rand bleibt dort hängen."""
        self.bodies[kind].throw(vx, vy)
        if kind in self.trees:
            top = self._near_top(kind, self._world, self._sprite)
            if top is not None:
                self._hang(kind, top)
            else:
                self.trees[kind].hanging = False

    def place(self, kind: str, world: World, x: float, y: float, half: float) -> bool:
        """Aus dem Inventar aufstellen: bei (x, y) fallen lassen, sonst mitten über
        einem erlaubten Monitor."""
        o = world.output_at(x, y)
        if o is None or o.name in world.forbidden_outputs:
            o = next((o for o in world.outputs if o.name not in world.forbidden_outputs), None)
            if o is None:
                return False
            x, y = o.geometry.x + o.geometry.w / 2, o.geometry.y + o.geometry.h / 2
        if kind in self.trees:
            self.trees[kind].hanging = False
        self.bodies[kind].drop(x, y)
        return True

    def _right_bowl(self) -> None:
        self.tipped = self._shoved = False
        self.spill = 0
        self.spill_age = 0.0
        self.fly_ids = []
        self.flies_eaten = 0
        self._fly_wait = FLY_DELAY

    @property
    def flies(self) -> int:
        """So viele Fliegen schwirren gerade über dem verschütteten Futter."""
        return len(self.fly_ids)

    def _lure_flies(self, dt: float) -> None:
        """Nach FLY_DELAY kommt eine, dann alle FLY_EVERY eine weitere, höchstens eine je
        Portion; ist eine gefressen, kommt nach FLY_EVERY die nächste."""
        if not (self.tipped and self.spill):
            self.spill_age = 0.0
            return
        self.spill_age += dt
        if len(self.fly_ids) >= self.spill:
            self._fly_wait = FLY_EVERY
            return
        self._fly_wait -= dt
        if self._fly_wait <= 0:
            self.fly_ids.append(max(self.fly_ids, default=self.flies_eaten - 1) + 1)
            self._fly_wait = FLY_EVERY

    def pile(self, sprite: float) -> tuple[float, float] | None:
        """Mitte unten des verschütteten Futters (global)."""
        b = self.bodies["bowl"]
        if not (self.tipped and self.spill and b.placed):
            return None
        return b.x + self.spill_side * SPILL_DX * sprite / 32, b.y

    def fly_at(self, fly: int, sprite: float) -> tuple[float, float] | None:
        """Wo Fliege fly gerade ist (global)."""
        pile = self.pile(sprite)
        if pile is None or fly not in self.fly_ids:
            return None
        dx, dy, _ = fly_path(self.spill_age, fly)
        return pile[0] + dx * sprite / 32, pile[1] + dy * sprite / 32

    def eat_fly(self) -> None:
        """Die älteste Fliege ist gefressen."""
        if self.fly_ids:
            self.fly_ids.pop(0)
            self.flies_eaten += 1

    def toys_of(self, kind: str) -> tuple:
        """Bällchen eines Kratzbaums als (x, Aufhängung, Fadenlänge, Farbe) im Frame bzw.
        im Aufbau des großen Baums."""
        if kind in self.trees:
            return self.trees[kind].layout().toys
        return (TREE_TOY,) if kind == "tree" else ()

    def toy_x(self, kind: str, toy: int, world: World, sprite: float) -> float | None:
        """Wo das Bällchen hängt (global, Fadenmitte); None, wenn Baum oder Bällchen weg sind."""
        pos = self.usable(kind, world)
        toys = self.toys_of(kind) if pos is not None else ()
        if toy >= len(toys):
            return None
        left = pos[0] - (self.trees[kind].layout().w if kind in self.trees else 32) / 2 * sprite / 32
        return left + (toys[toy][0] + 0.5) * sprite / 32

    def bat_toy(self, kind: str, toy: int, direction: int) -> None:
        """Mit der Pfote nach einem Bällchen schlagen: es pendelt in diese Richtung."""
        swing = self.toy_swing.setdefault((kind, toy), [0.0, 0.0])
        swing[1] += direction * TOY_KICK

    def toy_angle(self, kind: str, toy: int) -> float:
        swing = self.toy_swing.get((kind, toy))
        return swing[0] if swing is not None else 0.0

    def _swing_toys(self, dt: float, sprite: float) -> None:
        for key, swing in list(self.toy_swing.items()):
            toys = self.toys_of(key[0])
            if key[1] >= len(toys):                 # Baum weg oder neu gewürfelt
                del self.toy_swing[key]
                continue
            length = max(4, toys[key[1]][2] + 1.5) * sprite / 32   # bis zur Mitte der Kugel
            n = max(1, math.ceil(dt / TOY_STEP))
            for _ in range(n):
                h = dt / n
                swing[1] += (-TOY_G / length * math.sin(swing[0]) - TOY_DAMP * swing[1]) * h
                swing[0] = max(-TOY_MAX, min(TOY_MAX, swing[0] + swing[1] * h))
            if abs(swing[0]) < 0.01 and abs(swing[1]) < 0.05:
                del self.toy_swing[key]

    def shove_bowl(self, vx: float) -> None:
        """Die Katze schubst den Napf an; fällt er dabei herunter, landet er umgedreht."""
        self.bodies["bowl"].shove(vx)
        self._shoved = True
        self.spill_side = 1 if vx >= 0 else -1

    def store(self, kind: str) -> None:
        if kind == "bowl":
            self._right_bowl()
        if kind in self.trees:
            self.trees[kind].hanging = False
        self.bodies[kind].store()

    # --- große Kratzbäume ---

    def add_tree(self, x: float, y: float, variant: dict | None = None,
                 rng: random.Random | None = None) -> str:
        """Großen Kratzbaum bei (x, y) fallen lassen; ist der erste entfernt,
        kommt der wieder, sonst ein weiterer mit eigenem Zufall. Liefert seine Art."""
        if not self.placed(bigtree.KIND):
            kind = bigtree.KIND
        else:
            n = 2
            while f"{bigtree.KIND}{n}" in self.bodies:
                n += 1
            kind = f"{bigtree.KIND}{n}"
            self.bodies[kind] = Body()
            self.trees[kind] = Tree(seed=(rng or random).randrange(1, 1 << 30))
        self.trees[kind].hanging = False
        self.bodies[kind].drop(x, y)
        if variant is not None:
            self.apply_variant(kind, variant)
        return kind

    def scratch(self, kind: str, post: int, amount: float) -> None:
        """Einmal am Pfeiler gekratzt; der kleine Kratzbaum hat nur einen."""
        if kind in self.trees:
            self.trees[kind].scratch(post, amount)
        elif kind == "tree":
            self.tree_wear = min(1.0, self.tree_wear + amount)

    def new_sisal(self, kind: str) -> None:
        """Kratzspuren weg: alle Pfeiler wie neu."""
        if kind in self.trees:
            self.trees[kind].wear = []
        elif kind == "tree":
            self.tree_wear = 0.0

    def frayed(self, kind: str) -> bool:
        """Ist überhaupt etwas zu sehen (für "Neuen Sisal" im Menü)?"""
        return bool(self.trees[kind].wear_levels()) if kind in self.trees \
            else bigtree.wear_level(self.tree_wear) > 0

    def tree_frame(self) -> str:
        """Frame des kleinen Kratzbaums, je nachdem wie zerfranst sein Sisal ist."""
        level = bigtree.wear_level(self.tree_wear)
        return TREE_FRAMES[level]

    def behind(self, kind: str) -> bool:
        """Verschwindet dieser Kratzbaum hinter Fenstern (und die Katze darin mit ihm)?"""
        if kind in self.trees:
            return self.trees[kind].behind
        return kind == "tree" and self.tree_behind

    def set_behind(self, kind: str, on: bool) -> None:
        if kind in self.trees:
            self.trees[kind].behind = on
        elif kind == "tree":
            self.tree_behind = on

    def owner_kind(self, owner: str) -> str | None:
        """Welchem Kratzbaum gehört diese Kante (oder Wand)? None: einem Fenster, dem
        Boden oder einem Baum, den es nicht mehr gibt."""
        if owner == TREE_ID:
            return "tree"
        if owner.startswith(bigtree.BOARD_ID):
            kind = owner[len(bigtree.BOARD_ID):].split(":")[0]
            return kind if kind in self.trees else None
        return None

    def hidden_owner(self, owner: str, seen: set | None = None) -> bool:
        """Gehört die Kante (oder Wand) zu einem Kratzbaum, der gerade hinter den Fenstern
        liegt? Wer darauf steht, verschwindet mit ihm - die Katze ist ja im Baum."""
        kind = self.owner_kind(owner)
        return kind is not None and self.hidden(kind, seen)

    def hidden(self, kind: str, seen: set | None = None) -> bool:
        """Liegt dieses Möbel gerade hinter den Fenstern? Entweder ist es ein Kratzbaum,
        der so eingestellt ist, oder es steht (für den Moment) auf einem, der es ist -
        der Napf auf dem Brett, das Knäuel auf dem Sockel, ein Baum auf dem anderen.
        seen bricht Ringe ab: ein hängender Baum steht auf seiner eigenen Kante."""
        if self.behind(kind):
            return True
        if seen is None:
            seen = set()
        if kind in seen or kind not in self.bodies:
            return False
        seen.add(kind)
        b = self.bodies[kind]
        return b.platform is not None and not b.held and self.hidden_owner(b.platform.owner, seen)

    def locked(self, kind: str) -> bool:
        return kind in self.trees and self.trees[kind].locked

    def set_locked(self, kind: str, on: bool) -> None:
        """Festgestellt lässt er sich weder mit dem Mausrad verstellen noch verschieben."""
        if kind in self.trees:
            self.trees[kind].locked = on

    def remove_tree(self, kind: str) -> None:
        """Der erste wird nur weggeräumt (kommt beim nächsten wieder), weitere verschwinden ganz."""
        if kind == bigtree.KIND:
            self.store(kind)
        else:
            self.bodies.pop(kind, None)
            self.trees.pop(kind, None)

    def resize_tree(self, kind: str, w: float, h: float) -> None:
        """Stehend bleibt der Fuß, hängend die Oberkante, wo sie ist; gesperrt gar nichts."""
        t = self.trees[kind]
        if t.locked:
            return
        t.resize(w, h)
        if t.hanging:
            self._hang(kind, t.top)

    def apply_variant(self, kind: str, variant: dict) -> None:
        """Gespeicherte Variante übernehmen; hängend nur, wenn ein oberer Rand da ist."""
        t = self.trees[kind]
        t.apply(variant)
        b = self.bodies[kind]
        top = self._top_edge(self._world, b.x) if variant.get("hanging") else None
        if top is not None:
            self._hang(kind, top)
        elif t.hanging:              # war hängend, soll stehen: fällt herunter
            t.hanging = False
            b.drop(b.x, b.y)

    def _hang(self, kind: str, top: float, sprite: float | None = None) -> None:
        """Oben bei top festmachen; die Mitte unten (Body-Position) folgt aus der Höhe.
        Ohne bekannten Maßstab (beim Laden) bleibt y, wie es gespeichert war."""
        t = self.trees[kind]
        t.hanging, t.top = True, top
        b = self.bodies[kind]
        b.held = False
        b.vx = b.vy = 0.0
        sprite = sprite or self._sprite
        if sprite:
            b.y = top + t.size()[1] * sprite / 32
        b.platform = Platform(b.x - 1, b.x + 1, b.y, f"{bigtree.BOARD_ID}{kind}:anchor")

    @staticmethod
    def _top_edge(world: World | None, x: float) -> float | None:
        if world is None:
            return None
        o = next((o for o in world.outputs if o.geometry.x <= x < o.geometry.x + o.geometry.w), None)
        return None if o is None else o.work_area.y

    def _near_top(self, kind: str, world: World | None, sprite: float | None) -> float | None:
        """Oberer Rand, wenn die Oberkante beim Ziehen höchstens SNAP_PX darunter liegt."""
        if not sprite:
            return None
        b = self.bodies[kind]
        top = self._top_edge(world, b.x)
        if top is None:
            return None
        return top if b.y - self.trees[kind].size()[1] * sprite / 32 <= top + SNAP_PX else None

    def kick(self, vx: float, vy: float = 0.0) -> None:
        """Wollknäuel anstupsen; mit vy getreten, dann hüpft es los."""
        self.yarn.kick(vx, vy)

    def world_with(self, world: World, sprite: float) -> World:
        """Welt samt Liegeflächen der Kratzbäume. Kleiner Kratzbaum: wie ein schmales Fenster
        (oben begehbar, unten zum Hängen); große: jede Fläche eine Kante, jeder Pfeiler eine
        Wand zum Hochklettern. Ohne aufgestellte Kratzbäume unverändert."""
        self._world, self._sprite = world, sprite
        for kind, t in self.trees.items():
            if t.hanging and self.bodies[kind].placed and not self.bodies[kind].held:
                self._hang(kind, t.top, sprite)   # Höhe oder Maßstab geändert: oben bleiben
        base = self._with_small_tree(world, sprite)
        used = [(k, pos) for k in self.trees if (pos := self.usable(k, world)) is not None]
        if not used:
            return base
        key = (base, tuple((k, pos, self.trees[k].size(), self.trees[k].hanging, self.trees[k].seed)
                           for k, pos in used), sprite)
        if self._tree_cache is None or self._tree_cache[0] != key:
            wins, walls = [], []
            for i, (kind, pos) in enumerate(used):
                w, wl = bigtree.structures(kind, self.trees[kind], pos, sprite, bigtree.STACK + i)
                wins += w
                walls += wl
            out = World(base.outputs, base.windows + wins, base.blocked)
            out.walls.extend(walls)
            self._tree_cache = (key, base, out)
        return self._tree_cache[2]

    def _without_trees(self, world: World) -> World:
        """Welt ohne die Bretter der großen Kratzbäume: auf denen landen sie nicht selbst."""
        c = self._tree_cache
        return c[1] if c is not None and c[2] is world else world

    def _with_small_tree(self, world: World, sprite: float) -> World:
        pos = self.usable("tree", world)
        if pos is None:
            return world
        key = (world, pos, sprite)
        if self._world_cache is None or self._world_cache[0] != key:
            s = sprite / 32
            x, y, w, h = TREE_DECK
            left, top = pos[0] - 16 * s, pos[1] - FRAME_H["tree"] * s
            deck = Rect(left + x * s, top + y * s, w * s, h * s)
            win = Win(TREE_ID, deck, TREE_STACK, False, False)
            out = World(world.outputs, world.windows + [win], world.blocked)
            out.walls.extend(self._post_walls(left, top, s))
            self._world_cache = (key, out)
        return self._world_cache[1]

    @staticmethod
    def _post_walls(left: float, top: float, s: float) -> list[Wall]:
        """Beide Seiten des Sisalpfeilers, wie beim großen Kratzbaum: oben angekommen zieht
        sie sich auf die Liegefläche (TREE_ID). Reicht von deren Oberkante bis zum Sockel."""
        px, _, y2 = TREE_POST
        return [Wall(left + (px - side * bigtree.POST_W / 2) * s, top + TREE_DECK[1] * s,
                     top + y2 * s, TREE_ID, -side) for side in (-1, 1)]

    def tick(self, world: World, dt: float, sprite: float) -> None:
        base = self._without_trees(world)
        bowl = self.bodies["bowl"]
        falling = bowl.placed and bowl.platform is None
        for kind, b in self.bodies.items():
            if kind in self.trees:
                if self.trees[kind].hanging and not b.held:
                    continue                     # klebt oben, keine Schwerkraft
                b.step(base, dt, self.half_width(kind, sprite))
            else:
                b.step(world, dt, half_width(kind, sprite))
        self._swing_toys(dt, sprite)
        self._lure_flies(dt)
        if self._shoved:
            if bowl.held or not bowl.placed:
                self._shoved = False
            elif bowl.platform is not None and falling:   # heruntergefallen: umgedreht
                self._shoved = False
                self.tipped = True
                self.spill, self.food = self.food, 0
            elif bowl.platform is not None and not bowl.vx:   # an der Kante liegen geblieben
                self._shoved = False

    def fill(self, world: World) -> bool:
        """Futter in den Napf kippen. False = kein erreichbarer Napf, direkt füttern."""
        if self.usable("bowl", world) is None:
            return False
        self.food = min(BOWL_PORTIONS, self.food + 1)
        return True

    def eat(self) -> bool:
        if self.food <= 0:
            return False
        self.food -= 1
        return True

    def to_dict(self) -> dict:
        d: dict = {"food": self.food, "bowl_tipped": self.tipped, "spill": self.spill,
                   "spill_side": self.spill_side, "tree_wear": round(self.tree_wear, 4),
                   "tree_behind": self.tree_behind}
        for k, b in self.bodies.items():
            if not b.placed:
                d[k] = None
            elif b.pending is not None:   # Monitor noch nicht gesehen: unverändert lassen
                d[k] = {"output": b.pending[0], "offset": b.pending[1]}
            else:
                d[k] = {"x": b.x, "y": b.y}
        d[bigtree.KIND + "_trees"] = {k: t.to_dict() for k, t in self.trees.items()}
        return d

    @staticmethod
    def _load_body(b: "Body", v) -> None:
        if not isinstance(v, dict):
            return
        try:
            if "x" in v:
                b.drop(float(v["x"]), float(v["y"]) - 1)
            elif v.get("output") is not None:   # älteres Format: Boden eines Monitors
                b.drop(0.0, 0.0)
                b.pending = (str(v["output"]), float(v.get("offset", 0)))
        except (KeyError, TypeError, ValueError):
            b.store()

    @classmethod
    def from_dict(cls, d: dict) -> "Furniture":
        """Beim Start fällt alles auf die Kante darunter; Fenster kennt die App da noch nicht."""
        f = cls()
        for k, b in f.bodies.items():
            f._load_body(b, d.get(k))
        trees = d.get(bigtree.KIND + "_trees")
        for kind, v in (trees.items() if isinstance(trees, dict) else ()):
            if not is_tree(kind) or not isinstance(v, dict):
                continue
            if kind not in f.bodies:            # weiterer Baum: nur mit Standort
                b = Body()
                f._load_body(b, d.get(kind))
                if not b.placed:
                    continue
                f.bodies[kind] = b
            f.trees[kind] = t = Tree.from_dict(v)
            if t.hanging and f.bodies[kind].placed:
                f.bodies[kind].y += 1           # klebt oben, statt 1 px darüber zu fallen
                f._hang(kind, t.top)
        try:
            f.food = max(0, min(BOWL_PORTIONS, int(d.get("food", 0))))
            f.spill = max(0, min(BOWL_PORTIONS, int(d.get("spill", 0))))
            f.spill_side = -1 if d.get("spill_side", 1) == -1 else 1
            f.tree_wear = max(0.0, min(1.0, float(d.get("tree_wear", 0.0))))
            f.tree_behind = d.get("tree_behind") is True
        except (TypeError, ValueError):
            pass
        f.tipped = d.get("bowl_tipped") is True and f.bodies["bowl"].placed
        return f
