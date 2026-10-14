"""Weltmodell: begehbare Plattformen aus Monitoren und Fenstern (rein, ohne Qt)."""
import json
from dataclasses import dataclass

MIN_PIECE = 40


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px < self.right and self.y <= py < self.bottom


@dataclass(frozen=True)
class Output:
    name: str
    geometry: Rect
    work_area: Rect


@dataclass(frozen=True)
class Win:
    id: str
    rect: Rect
    stack: int
    full_screen: bool
    maximized: bool
    panel: bool = False


@dataclass(frozen=True)
class Platform:
    x1: float
    x2: float
    y: float
    owner: str

    @property
    def is_floor(self) -> bool:
        return self.owner.startswith("floor:")


@dataclass(frozen=True)
class Wall:
    """Seitliche Fensterkante. side = -1 links, +1 rechts vom Fenster."""
    x: float
    y1: float
    y2: float
    owner: str
    side: int


@dataclass(frozen=True)
class Ceiling:
    """Fensterunterkante."""
    x1: float
    x2: float
    y: float
    owner: str


WALL_MARGIN = 30  # Katze klettert außen an der Kante, braucht Platz zum Bildschirmrand


def _subtract(pieces: list[tuple[float, float]], a: float, b: float) -> list[tuple[float, float]]:
    out = []
    for x1, x2 in pieces:
        if b <= x1 or a >= x2:
            out.append((x1, x2))
            continue
        if a > x1:
            out.append((x1, a))
        if b < x2:
            out.append((b, x2))
    return out


class World:
    def __init__(self, outputs: list[Output], windows: list[Win]):
        self.outputs = outputs
        self.windows = windows
        self.forbidden_outputs: set[str] = set()
        self.platforms: list[Platform] = []
        self.walls: list[Wall] = []
        self.ceilings: list[Ceiling] = []
        self._build()

    def _output_containing(self, px: float, py: float) -> Output | None:
        for o in self.outputs:
            if o.geometry.contains(px, py):
                return o
        return None

    def _build(self) -> None:
        for o in self.outputs:
            wa = o.work_area
            self.platforms.append(Platform(wa.x, wa.right, wa.bottom, f"floor:{o.name}"))
        for w in self.windows:
            cx, cy = w.rect.x + w.rect.w / 2, w.rect.y + w.rect.h / 2
            out = self._output_containing(cx, cy)
            if out is None:
                continue
            if w.full_screen:
                self.forbidden_outputs.add(out.name)
                continue
            wa = out.work_area
            above = [o for o in self.windows if o.stack > w.stack]
            self._build_top(w, wa, above)
            if w.panel:
                continue  # Panels tragen nur oben, kein Klettern und Hängen
            self._build_walls(w, wa, above)
            self._build_ceiling(w, wa, above)

    def _horizontal(self, w: Win, wa: Rect, above: list[Win], y: float) -> list[tuple[float, float]]:
        pieces = [(max(w.rect.x, wa.x), min(w.rect.right, wa.right))]
        for other in above:
            if other.rect.y < y < other.rect.bottom:
                pieces = _subtract(pieces, other.rect.x, other.rect.right)
        return [(x1, x2) for x1, x2 in pieces if x2 - x1 >= MIN_PIECE]

    def _build_top(self, w: Win, wa: Rect, above: list[Win]) -> None:
        y = w.rect.y
        if y <= wa.y + 1 or y >= wa.bottom:
            return
        for x1, x2 in self._horizontal(w, wa, above, y):
            self.platforms.append(Platform(x1, x2, y, w.id))

    def _build_walls(self, w: Win, wa: Rect, above: list[Win]) -> None:
        for side, x in ((-1, w.rect.x), (1, w.rect.right)):
            if not wa.x + WALL_MARGIN <= x <= wa.right - WALL_MARGIN:
                continue
            pieces = [(max(w.rect.y, wa.y), min(w.rect.bottom, wa.bottom))]
            for other in above:
                if other.rect.x < x < other.rect.right:
                    pieces = _subtract(pieces, other.rect.y, other.rect.bottom)
            for y1, y2 in pieces:
                if y2 - y1 >= MIN_PIECE:
                    self.walls.append(Wall(x, y1, y2, w.id, side))

    def _build_ceiling(self, w: Win, wa: Rect, above: list[Win]) -> None:
        y = w.rect.bottom
        if y >= wa.bottom - 1 or y <= wa.y:
            return
        for x1, x2 in self._horizontal(w, wa, above, y):
            self.ceilings.append(Ceiling(x1, x2, y, w.id))

    @classmethod
    def from_json(cls, text: str, ignore_pid: int | None = None) -> "World":
        """ignore_pid: Fenster dieses Prozesses (eigene Overlays) überspringen."""
        try:
            data = json.loads(text)
            if not isinstance(data, dict) or not data.get("outputs"):
                raise ValueError("keine Outputs")

            def rect(d):
                return Rect(float(d["x"]), float(d["y"]), float(d["w"]), float(d["h"]))

            outputs = []
            for o in data["outputs"]:
                if not isinstance(o["name"], str):
                    raise ValueError("Output-Name")
                outputs.append(Output(o["name"], rect(o["geometry"]), rect(o["workArea"])))
            windows = [Win(str(w["id"]), rect(w), int(w["stack"]), bool(w.get("fullScreen")),
                           bool(w.get("maximized")), bool(w.get("panel")))
                       for w in data.get("windows", [])
                       if ignore_pid is None or w.get("pid") != ignore_pid]
        except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as e:
            raise ValueError(f"ungültiges Update: {e}") from e
        return cls(outputs, windows)

    @classmethod
    def from_screens(cls, screens: list[tuple[str, Rect, Rect]]) -> "World":
        return cls([Output(n, g, a) for n, g, a in screens], [])

    def output_at(self, x: float, y: float) -> Output | None:
        hits = [o for o in self.outputs if o.geometry.x <= x < o.geometry.right]
        if len(hits) == 1:
            return hits[0]
        for o in hits:
            if o.geometry.y <= y < o.geometry.bottom:
                return o
        return hits[0] if hits else None

    def platform_below(self, x: float, y: float, floors_only: bool = False) -> Platform | None:
        best = None
        for p in self.platforms:
            if floors_only and not p.is_floor:
                continue
            if p.x1 <= x <= p.x2 and p.y >= y - 1 and (best is None or p.y < best.y):
                best = p
        return best

    def platform_by_owner_at(self, owner: str, x: float) -> Platform | None:
        for p in self.platforms:
            if p.owner == owner and p.x1 <= x <= p.x2:
                return p
        return None

    def neighbor(self, p: Platform, direction: int) -> Platform | None:
        for q in self.platforms:
            if q == p or abs(q.y - p.y) > 2:
                continue
            if direction > 0 and abs(q.x1 - p.x2) <= 2:
                return q
            if direction < 0 and abs(q.x2 - p.x1) <= 2:
                return q
        return None

    def _platform_output(self, p: Platform) -> Output | None:
        return self._output_containing((p.x1 + p.x2) / 2, p.y - 1)

    def reachable(self, p: Platform, x: float, max_up: float = 300, max_side: float = 400) -> list[Platform]:
        out = []
        for q in self.platforms:
            if q == p or p.y - q.y > max_up:
                continue
            dist = 0 if q.x1 <= x <= q.x2 else min(abs(x - q.x1), abs(x - q.x2))
            if dist > max_side:
                continue
            o = self._platform_output(q)
            if o is not None and o.name in self.forbidden_outputs:
                continue
            out.append(q)
        return out

    def _forbidden_at(self, x: float, y: float) -> bool:
        o = self._output_containing(x, y)
        return o is None or o.name in self.forbidden_outputs

    def walls_near(self, p: Platform, x: float, stand_offset: float,
                   max_side: float = 400, max_gap: float = 300) -> list[Wall]:
        """Wände, an deren Fuß die Katze auf p stehen (oder hochspringen) und hochklettern kann."""
        out = []
        for w in self.walls:
            stand = w.x + w.side * stand_offset
            if not p.x1 <= stand <= p.x2 or abs(stand - x) > max_side:
                continue
            if w.y1 >= p.y - MIN_PIECE or w.y2 < p.y - max_gap:
                continue
            if self._forbidden_at(stand, p.y - 1):
                continue
            out.append(w)
        return out

    def ceilings_near(self, p: Platform, x: float, min_gap: float, max_gap: float,
                      max_side: float = 200) -> list[Ceiling]:
        """Unterkanten über p, an die die Katze hochspringen kann."""
        out = []
        for c in self.ceilings:
            if not min_gap <= p.y - c.y <= max_gap:
                continue
            if c.x2 - 20 < x - max_side or c.x1 + 20 > x + max_side:
                continue
            if self._forbidden_at((c.x1 + c.x2) / 2, c.y + 1):
                continue
            out.append(c)
        return out

    def window_rect(self, win_id: str) -> Rect | None:
        for w in self.windows:
            if w.id == win_id:
                return w.rect
        return None

    def bounds(self) -> Rect:
        x1 = min(o.geometry.x for o in self.outputs)
        y1 = min(o.geometry.y for o in self.outputs)
        x2 = max(o.geometry.right for o in self.outputs)
        y2 = max(o.geometry.bottom for o in self.outputs)
        return Rect(x1, y1, x2 - x1, y2 - y1)
