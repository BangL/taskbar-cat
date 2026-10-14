"""Möbel: Katzenbett, Napf, Wollknäuel und Kratzbaum, je eins. Aufgestellt fallen sie
auf die nächste Kante darunter (Boden oder Fenster), fahren mit dem Fenster mit und
fallen herunter, wenn es verschwindet; sonst liegen sie im Inventar (rein, ohne Qt)."""
import math

from .world import GRAVITY, Platform, Rect, Win, World

KINDS = ("bed", "bowl", "yarn", "tree")
NAMES = {"bed": "Katzenbett", "bowl": "Napf", "yarn": "Wollknäuel", "tree": "Kratzbaum"}
# Frame-Höhe in Pixeln, wenn nicht 32 (Breite ist immer 32)
FRAME_H = {"tree": 64}
# Sichtbarer Teil im Frame (x, y, w, h): Mausfläche und Abstand zum Bildschirmrand
BOX = {"bed": (1, 21, 30, 11), "bowl": (11, 25, 10, 7), "yarn": (11, 22, 10, 10),
       "tree": (3, 8, 26, 55)}
# Liegefläche oben auf dem Kratzbaum (x, y, w, h im Frame); wird zur begehbaren Kante
TREE_DECK = (3, 8, 26, 5)
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


def half_width(kind: str, sprite: float) -> float:
    """Halbe Breite des sichtbaren Teils in px bei Sprite-Kantenlänge sprite."""
    return BOX[kind][2] / 2 * sprite / 32


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

    def kick(self, vx: float) -> None:
        if self.resting and self.bouncy:
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
        self.food = 0   # Portionen im Napf
        self._world_cache: tuple | None = None

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

    def usable(self, kind: str, world: World) -> tuple[float, float] | None:
        """Wie position, aber nur auf erlaubten Monitoren und solange es auf einer Kante steht."""
        pos = self.position(kind, world)
        if (pos is None or not self.bodies[kind].resting
                or world.output_at(pos[0], pos[1] - 1).name in world.forbidden_outputs):
            return None
        return pos

    def platform(self, kind: str) -> Platform | None:
        return self.bodies[kind].platform

    def put(self, kind: str, world: World, x: float, y: float, half: float) -> bool:
        """Mit der Maus halten (Mitte unten bei x, y), bis release es loslässt."""
        self.bodies[kind].hold(x, y)
        return True

    def release(self, kind: str, vx: float, vy: float) -> None:
        """Maus losgelassen: fällt herunter; das Knäuel fliegt mit Schwung weiter."""
        self.bodies[kind].throw(vx, vy)

    def place(self, kind: str, world: World, x: float, y: float, half: float) -> bool:
        """Aus dem Inventar aufstellen: bei (x, y) fallen lassen, sonst mitten über
        einem erlaubten Monitor."""
        o = world.output_at(x, y)
        if o is None or o.name in world.forbidden_outputs:
            o = next((o for o in world.outputs if o.name not in world.forbidden_outputs), None)
            if o is None:
                return False
            x, y = o.geometry.x + o.geometry.w / 2, o.geometry.y + o.geometry.h / 2
        self.bodies[kind].drop(x, y)
        return True

    def store(self, kind: str) -> None:
        self.bodies[kind].store()

    def kick(self, vx: float) -> None:
        """Wollknäuel anstupsen."""
        self.yarn.kick(vx)

    def world_with(self, world: World, sprite: float) -> World:
        """Welt samt Liegefläche des Kratzbaums als Kante (wie ein schmales Fenster:
        oben begehbar, unten zum Hängen). Ohne aufgestellten Kratzbaum unverändert."""
        pos = self.usable("tree", world)
        if pos is None:
            return world
        key = (world, pos, sprite)
        if self._world_cache is None or self._world_cache[0] != key:
            s = sprite / 32
            x, y, w, h = TREE_DECK
            deck = Rect(pos[0] - 16 * s + x * s, pos[1] - FRAME_H["tree"] * s + y * s, w * s, h * s)
            win = Win(TREE_ID, deck, TREE_STACK, False, False)
            self._world_cache = (key, World(world.outputs, world.windows + [win], world.blocked))
        return self._world_cache[1]

    def tick(self, world: World, dt: float, sprite: float) -> None:
        for kind, b in self.bodies.items():
            b.step(world, dt, half_width(kind, sprite))

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
        d: dict = {"food": self.food}
        for k, b in self.bodies.items():
            if not b.placed:
                d[k] = None
            elif b.pending is not None:   # Monitor noch nicht gesehen: unverändert lassen
                d[k] = {"output": b.pending[0], "offset": b.pending[1]}
            else:
                d[k] = {"x": b.x, "y": b.y}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Furniture":
        """Beim Start fällt alles auf die Kante darunter; Fenster kennt die App da noch nicht."""
        f = cls()
        for k, b in f.bodies.items():
            v = d.get(k)
            if not isinstance(v, dict):
                continue
            try:
                if "x" in v:
                    b.drop(float(v["x"]), float(v["y"]) - 1)
                elif v.get("output") is not None:   # älteres Format: Boden eines Monitors
                    b.drop(0.0, 0.0)
                    b.pending = (str(v["output"]), float(v.get("offset", 0)))
            except (KeyError, TypeError, ValueError):
                b.store()
        try:
            f.food = max(0, min(BOWL_PORTIONS, int(d.get("food", 0))))
        except (TypeError, ValueError):
            pass
        return f
