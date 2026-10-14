"""Maus-Gesten: Streicheln durch Reiben, Drag mit Wurfgeschwindigkeit (rein, ohne Qt)."""

RUB_MIN_PX = 4
RUB_REVERSALS = 3
RUB_WINDOW_S = 1.0
DRAG_THRESHOLD_PX = 6
VELOCITY_WINDOW_S = 0.1


class RubDetector:
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self._ext: float | None = None
        self._dir = 0
        self._strokes: list[float] = []

    def feed_motion(self, x: float, t: float) -> bool:
        if self._ext is None:
            self._ext = x
            return False
        d = x - self._ext
        if self._dir and (d > 0) == (self._dir > 0):
            self._ext = x
            return False
        if abs(d) < RUB_MIN_PX:
            return False
        self._dir = 1 if d > 0 else -1
        self._ext = x
        self._strokes = [s for s in self._strokes if s >= t - RUB_WINDOW_S] + [t]
        if len(self._strokes) > RUB_REVERSALS:
            self.reset()
            return True
        return False


class DragTracker:
    def __init__(self):
        self.is_dragging = False
        self._origin = (0.0, 0.0)
        self._samples: list[tuple[float, float, float]] = []

    def press(self, x: float, y: float, t: float) -> None:
        self.is_dragging = False
        self._origin = (x, y)
        self._samples = [(x, y, t)]

    def move(self, x: float, y: float, t: float) -> bool:
        self._samples = [s for s in self._samples if s[2] >= t - 1.0] + [(x, y, t)]
        if not self.is_dragging:
            ox, oy = self._origin
            if (x - ox) ** 2 + (y - oy) ** 2 > DRAG_THRESHOLD_PX ** 2:
                self.is_dragging = True
        return self.is_dragging

    def velocity(self) -> tuple[float, float]:
        x1, y1, t1 = self._samples[-1]
        recent = [s for s in self._samples if s[2] >= t1 - VELOCITY_WINDOW_S - 1e-9]
        x0, y0, t0 = recent[0]
        if t1 - t0 <= 0:
            return 0.0, 0.0
        return (x1 - x0) / (t1 - t0), (y1 - y0) / (t1 - t0)
