"""Easter Egg: Ganz selten kommt ein UFO, holt die Katze mit dem Traktorstrahl ab und
bringt sie ein paar Sekunden später mit anderer Fellfarbe zurück (rein, ohne Qt)."""
import colorsys
import math
import random

from .config import FUR_PRESETS

PER_HOUR = 0.25        # im Schnitt alle 4 h ruhiger Zeit
COOLDOWN_S = 3600      # nach einem Besuch mindestens so lange Ruhe
FLY_SPEED = 450
BEAM_SPEED = 110
HOVER_ABOVE = 260      # so hoch über den Pfoten schwebt es
WIDTH_FACTOR = 1.6     # UFO-Breite relativ zur Sprite-Größe
AWAY_S = (4.0, 7.0)
MIN_HUE_STEP = 60      # Grad; die neue Farbe soll deutlich anders sein
GRAY_SATURATION = 0.15 # darunter hat das Fell keinen brauchbaren Farbton
CALM = ("idle_sit", "walk", "sleep", "purr", "cheer")
# Phasen, in denen die Katze dem UFO gehört (keine Interaktion, keine eigene Logik)
HOLDING = ("arrive", "beam_up", "leave", "away", "return", "beam_down")


def next_fur(current: str, rng: random.Random) -> str:
    """Farbton um MIN_HUE_STEP..360-MIN_HUE_STEP Grad drehen, Sättigung und Helligkeit
    behalten. Graues Fell hat keinen Farbton: dann eine andere Vorgabe-Farbe."""
    try:
        r, g, b = (int(current[i:i + 2], 16) / 255 for i in (1, 3, 5))
    except (TypeError, ValueError):
        r = g = b = 0.0
        current = ""
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < GRAY_SATURATION:
        return rng.choice([c for c in FUR_PRESETS if c != current.lower()])
    h = (h + rng.uniform(MIN_HUE_STEP, 360 - MIN_HUE_STEP) / 360) % 1.0
    return "#" + "".join(f"{round(c * 255):02x}" for c in colorsys.hsv_to_rgb(h, s, v))


class Ufo:
    """Ablauf: arrive -> beam_up -> leave -> away -> return -> beam_down -> depart -> done.

    x/y ist die Mitte des UFOs, ground_y die Unterkante des Strahls (Pfoten der Katze)."""

    def __init__(self, cat, world, rng: random.Random):
        b = world.bounds()
        self.rng = rng
        self.phase = "arrive"
        self.t = 0.0
        self.width = cat.sprite * WIDTH_FACTOR
        self.target_x = cat.x
        self.ground_y = cat.y
        self.hover_y = max(b.y + self.width / 2, cat.y - HOVER_ABOVE)
        self.side = rng.choice((-1, 1))
        self._bounds = b
        self.x, self.y = self._exit_x(), self.hover_y - 120
        self.beam_on = False
        self.new_fur: str | None = None
        self._wait = 0.0

    @property
    def holds_cat(self) -> bool:
        return self.phase in HOLDING

    @property
    def bottom(self) -> float:
        return self.y + self.width * 0.2

    def _exit_x(self) -> float:
        b = self._bounds
        return b.x - self.width * 1.5 if self.side < 0 else b.right + self.width * 1.5

    def _fly_to(self, tx: float, ty: float, dt: float) -> bool:
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy)
        step = FLY_SPEED * dt
        if d <= step:
            self.x, self.y = tx, ty
            return True
        self.x += dx / d * step
        self.y += dy / d * step
        return False

    def tick(self, dt: float, cat, world, fur: str) -> None:
        """fur: aktuelle Fellfarbe; die neue landet in new_fur, sobald das UFO zurückkommt."""
        self.t += dt
        if self.phase == "arrive":
            if self._fly_to(self.target_x, self.hover_y, dt):
                self.phase, self.beam_on = "beam_up", True
                cat.platform = None
        elif self.phase == "beam_up":
            cat.x += (self.x - cat.x) * min(1.0, dt * 3)
            cat.y -= BEAM_SPEED * dt
            if cat.y - cat.sprite * 0.5 <= self.bottom:
                self.phase, self.beam_on = "leave", False
                cat.state = "abducted"
        elif self.phase == "leave":
            if self._fly_to(self._exit_x(), self.hover_y - 200, dt):
                self.phase, self._wait = "away", self.rng.uniform(*AWAY_S)
        elif self.phase == "away":
            self._wait -= dt
            if self._wait <= 0:
                self.new_fur = next_fur(fur, self.rng)
                self.side = -self.side
                self.x, self.y = self._exit_x(), self.hover_y - 120
                self.phase = "return"
        elif self.phase == "return":
            if self._fly_to(self.target_x, self.hover_y, dt):
                floor = world.platform_below(self.x, -math.inf, floors_only=True)
                if floor is not None:
                    self.ground_y = floor.y
                self.phase, self.beam_on = "beam_down", True
                cat.x, cat.y = self.x, self.bottom + cat.sprite * 0.5
                cat.state = "beamed"
        elif self.phase == "beam_down":
            cat.y += BEAM_SPEED * dt
            floor = world.platform_below(cat.x, -math.inf, floors_only=True)
            if floor is None:
                cat.spawn(world)
            elif cat.y >= floor.y:
                cat._land(world, floor)
            else:
                return
            self.phase, self.beam_on = "depart", False
        elif self.phase == "depart":
            if self._fly_to(self._exit_x(), self.hover_y - 250, dt):
                self.phase = "done"
