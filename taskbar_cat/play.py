"""Erkennt, ob mit dem Mauszeiger in der Nähe der Katze herumgefuchtelt wird (rein, ohne Qt)."""
import math

WINDOW_S = 1.0
NEAR_PX = 300
MIN_PATH_PX = 500
MIN_REVERSALS = 2
MIN_STEP_PX = 4


class WiggleDetector:
    def __init__(self):
        self._samples: list[tuple[float, float, float]] = []

    @property
    def last(self) -> tuple[float, float] | None:
        return self._samples[-1][:2] if self._samples else None

    def feed(self, x: float, y: float, t: float) -> None:
        self._samples = [s for s in self._samples if s[2] >= t - WINDOW_S] + [(x, y, t)]

    def is_wiggling(self, cat_x: float, cat_y: float, t: float,
                    avoid: tuple[float, float, float, float] | None = None) -> bool:
        """avoid = (x1, y1, x2, y2): Cursor dort = Streicheln, kein Spiel."""
        recent = [s for s in self._samples if s[2] >= t - WINDOW_S]
        if len(recent) < 3:
            return False
        x, y, _ = recent[-1]
        if math.hypot(x - cat_x, y - cat_y) > NEAR_PX:
            return False
        if avoid and avoid[0] <= x <= avoid[2] and avoid[1] <= y <= avoid[3]:
            return False
        path = 0.0
        reversals = 0
        dirs = [0, 0]  # letzte Richtung in x und y
        for (x0, y0, _), (x1, y1, _) in zip(recent, recent[1:]):
            path += math.hypot(x1 - x0, y1 - y0)
            for i, d in enumerate((x1 - x0, y1 - y0)):
                if abs(d) < MIN_STEP_PX:
                    continue
                sign = 1 if d > 0 else -1
                if dirs[i] and sign != dirs[i]:
                    reversals += 1
                dirs[i] = sign
        return path >= MIN_PATH_PX and reversals >= MIN_REVERSALS
