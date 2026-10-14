"""Verhalten und Physik der Katze (rein, ohne Qt)."""
import dataclasses
import math
import random

from . import ufo
from .config import Config
from .needs import Mood, Needs
from .world import Ceiling, Platform, Rect, Wall, World

_DEFAULTS = Config()
GRAVITY = 2500
SPRITE = _DEFAULTS.sprite_px
MAX_PHYS_DT = 0.1
MAX_SUBSTEP_PX = 20
ANIM_FPS = 6
MAX_THROW = 4000
DRAG_TIMEOUT = 5.0
CLIMB_OFFSET = 18   # Abstand Sprite-Mitte zur Wand (Pfoten liegen an der Kante)
MOUNT_ABOVE = 40    # Pfoten so weit unter der Oberkante -> hochziehen
HANG_DROP = 93      # Pfoten an der Unterkante, Füße so weit darunter
HANG_MIN_GAP = HANG_DROP + 20
HANG_MAX_GAP = 300
PLAY_LINGER = 2.0    # so lange wird nach dem letzten Fuchteln weitergespielt
CHASE_SPEED = 150
POUNCE_RANGE = 200
SWIPE_MAX_UP = 350
DIVE_MIN_DROP = 40   # so weit unter den Pfoten lohnt der Sprung nach unten
MAX_POUNCE_VX = 900
PLAY_REWARD = 3
P_GROOM = 0.35       # Anteil der Ruhepausen, in denen sie sich putzt
FLEE_FACTOR = 4      # so viel schneller als sonst läuft sie vom gesperrten Monitor
FLEE_TIMEOUT = 30.0  # kommt sie nicht weg (Monitore nicht benachbart), doch umsetzen

AIRBORNE = ("jump", "fall", "thrown")
CLINGING = ("climb", "hang")
NO_PLAY = ("sleep", "dragged", "climb", "hang", "hidden", "eat", "sick_lie")
ANIM_FOR_STATE = {"chase": "walk", "approach": "walk", "flee": "walk", "idle_sit": "sit", "sick_lie": "lie", "thrown": "fall", "hidden": "sit",
                  "beamed": "dragged", "abducted": "sit"}
MOOD_NAME = {Mood.NORMAL: "normal", Mood.SAD: "sad", Mood.SICK: "sick"}


def _free(world: World) -> list:
    """Monitore, auf denen die Katze sein darf."""
    return [o for o in world.outputs if o.name not in world.forbidden_outputs]


class Cat:
    def __init__(self, needs: Needs, rng: random.Random, cfg: Config | None = None):
        self.needs = needs
        self.rng = rng
        self.cfg = cfg or _DEFAULTS
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.facing = 1
        self.state = "idle_sit"
        self.platform: Platform | None = None
        self.paused = False
        self.home_output: str | None = None
        self._timer = 0.0
        self._ride_rect: Rect | None = None
        self._floors_only = False
        self._ignore: Platform | None = None
        self._lazy_after_eat = False
        self._drag_idle = 0.0
        self._flee_s = 0.0
        self.ufo: ufo.Ufo | None = None
        self._ufo_quiet = 0.0
        # Eigener Zufall fürs UFO, damit der Würfel pro Tick das übrige Verhalten nicht verschiebt
        self.ufo_rng = random.Random()
        self.ufo_rng.setstate(rng.getstate())
        self._new_fur: str | None = None
        self._grab: str | None = None
        self._wall: Wall | None = None
        self._ceiling: Ceiling | None = None
        self._target_x = 0.0
        self._cursor: tuple[float, float] | None = None
        self._play_left = 0.0
        self._pounce: str | None = None   # "pounce" | "swipe" während eines Spielsprungs
        self._hit_cursor = False
        self._caught = False

    # --- Zustand von außen ---

    @property
    def sprite(self) -> int:
        return self.cfg.sprite_px

    @property
    def visible(self) -> bool:
        return self.state not in ("hidden", "abducted") and not self.paused

    @property
    def abducted(self) -> bool:
        """Gehört gerade dem UFO: keine Interaktion, kein eigenes Verhalten."""
        return self.ufo is not None and self.ufo.holds_cat

    def take_new_fur(self) -> str | None:
        """Vom UFO gewählte Fellfarbe, einmalig abholen (übernimmt die App in die Einstellungen)."""
        fur, self._new_fur = self._new_fur, None
        return fur

    @property
    def grounded(self) -> bool:
        return self.platform is not None and self.state not in AIRBORNE + ("dragged", "hidden")

    def spawn(self, world: World) -> None:
        free = _free(world) or world.outputs
        o = next((o for o in free if o.name == self.home_output), free[0])
        self._land(world, Platform(o.work_area.x, o.work_area.right, o.work_area.bottom, f"floor:{o.name}"))
        self.x = o.work_area.x + o.work_area.w / 2

    def set_paused(self, p: bool) -> None:
        self.paused = p

    def feed(self) -> None:
        if self.abducted:
            return
        self._lazy_after_eat = self.needs.feed(self.cfg)
        if self.grounded:
            self._set("eat", 3)

    def pet(self) -> None:
        if self.abducted:
            return
        self.needs.pet(self.cfg)
        if self.grounded:
            self._set("purr", 1.5)

    def go_sleep(self) -> None:
        if self.grounded and not self.abducted:
            self._set("sleep", math.inf)

    def call_to_floor(self) -> None:
        if self.abducted:
            return
        if self.state in CLINGING:
            self._start_fall(floors_only=True)
        elif self.grounded and not self.platform.is_floor:
            self._start_fall(floors_only=True)

    def start_drag(self) -> None:
        if self.abducted:
            return
        self.state = "dragged"
        self.platform = None
        self.vx = self.vy = 0
        self._drag_idle = 0.0
        self._grab = None
        self._pounce = None

    def drag_to(self, x: float, y: float) -> None:
        if self.state != "dragged":  # z.B. während der Entführung
            return
        if x != self.x:
            self.facing = 1 if x > self.x else -1
        self.x, self.y = x, y
        self._drag_idle = 0.0

    def release(self, vx: float, vy: float) -> None:
        if self.abducted:
            return
        self.state = "thrown"
        self.vx = max(-MAX_THROW, min(MAX_THROW, vx))
        self.vy = max(-MAX_THROW, min(MAX_THROW, vy))
        self._ignore = None
        self._floors_only = False

    def start_climb(self, world: World, wall: Wall) -> None:
        """Zum Fuß der Wand laufen, dann (ggf. nach Sprung) hochklettern."""
        if not self.grounded:
            return
        self._wall = wall
        self._target_x = wall.x + wall.side * CLIMB_OFFSET
        self.facing = 1 if self._target_x >= self.x else -1
        self._set("approach", math.inf)

    def start_hang(self, world: World, c: Ceiling) -> None:
        """An die Unterkante hochspringen, kurz hängen, dann fallen."""
        if not self.grounded:
            return
        tx = min(max(self.x, c.x1 + 20), c.x2 - 20)
        h = self.y - (c.y + HANG_DROP)
        vy0 = -math.sqrt(2 * GRAVITY * h)
        t = -vy0 / GRAVITY
        self._ceiling = c
        self._leap("ceiling", (tx - self.x) / t, vy0)

    def frame_key(self, t: float) -> tuple[str, str, int, bool]:
        anim = ANIM_FOR_STATE.get(self.state, self.state)
        if self.state == "jump" and self._pounce == "swipe":
            anim = "swipe"
        return anim, MOOD_NAME[self.needs.mood], int(t * ANIM_FPS), self.facing < 0

    # --- Simulation ---

    def _activity(self) -> str:
        if self.state in AIRBORNE + CLINGING + ("walk", "approach", "dragged", "chase", "crouch", "flee"):
            return "active"
        return "sleep" if self.state == "sleep" else "rest"

    def tick(self, dt: float, world: World, locked: bool,
             cursor: tuple[float, float] | None = None, wiggling: bool = False) -> None:
        if self.paused:
            return
        self._cursor = cursor
        if wiggling and cursor is not None and self._can_play():
            self._play_left = PLAY_LINGER
        else:
            self._play_left = max(0.0, self._play_left - dt)
        if not locked:
            self.needs.tick(dt, self._activity(), self.cfg)
        if self.ufo is not None:
            holding = self.ufo.holds_cat
            self.ufo.tick(min(dt, MAX_PHYS_DT), self, world, self.cfg.fur_color)
            if self.ufo.new_fur:
                self._new_fur, self.ufo.new_fur = self.ufo.new_fur, None
            if self.ufo.phase == "done":
                self.ufo = None
                self._ufo_quiet = ufo.COOLDOWN_S
            if holding:
                return
        if self.state == "dragged":
            # Release verloren (Grab vom Compositor abgebrochen) -> fallen lassen
            self._drag_idle += dt
            if self._drag_idle > DRAG_TIMEOUT:
                self.release(0, 0)
            return
        out = world.output_at(self.x, self.y - 1)
        if out is None:
            self.spawn(world)
            return
        if out.name in world.forbidden_outputs:
            if (out.name in world.blocked and out.name not in world.fullscreen_outputs
                    and _free(world)):
                self._flee(dt, world)    # gesperrter Monitor: selbst weglaufen
                return
            if self.state != "hidden":
                self.state = "hidden"
                self.platform = None
            return
        self._flee_s = 0.0
        if self.state == "hidden":
            self._start_fall()
        if self.state in CLINGING:
            self._cling(dt, world)
            return
        if self.state in AIRBORNE:
            self._integrate(min(dt, MAX_PHYS_DT), world)
            return
        if not self._ride(world):
            self._start_fall()
            return
        if not locked and self._ufo_arrives(dt):
            self.ufo = ufo.Ufo(self, world, self.ufo_rng)
            self._set("beamed", math.inf)
            return
        self._behave(dt, world)

    def _ufo_arrives(self, dt: float) -> bool:
        """Zufall pro Tick; nur bei ruhiger Katze, wenn keins unterwegs ist und nicht kurz
        nach dem letzten Besuch."""
        self._ufo_quiet = max(0.0, self._ufo_quiet - dt)
        return (self.ufo is None and self._ufo_quiet == 0 and self.state in ufo.CALM
                and self.ufo_rng.random() < ufo.PER_HOUR / 3600 * dt)

    def _set(self, state: str, duration: float) -> None:
        self.state = state
        self._timer = duration

    def _start_fall(self, floors_only: bool = False) -> None:
        self.state = "fall"
        self.platform = None
        self.vx = self.vy = 0
        self._floors_only = floors_only
        self._ignore = None
        self._grab = None

    def _land(self, world: World, p: Platform) -> None:
        self.platform = p
        self.y = p.y
        self.vx = self.vy = 0
        self._floors_only = False
        self._ignore = None
        self._grab = None
        self._pounce = None
        self._ride_rect = None if p.is_floor else world.window_rect(p.owner)
        self._set("idle_sit", self.rng.uniform(3, 10))
        if self._caught:
            self._caught = False
            self._set("cheer", 1.2)

    def _ride(self, world: World) -> bool:
        """Plattform nachführen (Fenster bewegt, Panel verschoben). False = Boden weg."""
        p = self.platform
        if p is None:
            return False
        if not p.is_floor:
            rect = world.window_rect(p.owner)
            if rect is None:
                return False
            if self._ride_rect is not None:
                self.x += rect.x - self._ride_rect.x
            self._ride_rect = rect
        q = world.platform_by_owner_at(p.owner, self.x)
        if q is None:
            return False
        self.platform = q
        self.y = q.y
        return True

    def _integrate(self, dt: float, world: World) -> None:
        vmax = max(abs(self.vy) + GRAVITY * dt, abs(self.vx))
        n = max(1, math.ceil(vmax * dt / MAX_SUBSTEP_PX))
        h = dt / n
        b = world.bounds()
        for _ in range(n):
            prev_y = self.y
            self.vy += GRAVITY * h
            self.x += self.vx * h
            self.y += self.vy * h
            if self.x < b.x:
                self.x, self.vx = b.x, abs(self.vx) * 0.5
            elif self.x > b.right - 1:
                self.x, self.vx = b.right - 1, -abs(self.vx) * 0.5
            if self.y < b.y + self.sprite:
                self.y, self.vy = b.y + self.sprite, 0
            if self.vx:
                self.facing = 1 if self.vx > 0 else -1
            if self._pounce and not self._caught and self._touches_cursor():
                self._caught = True
                self.needs.affection = min(100.0, self.needs.affection + PLAY_REWARD)
            if self._grab and self.vy >= 0:
                self._attach(world)
                return
            if self.vy > 0:
                p = self._landing(world, prev_y)
                if p is None:
                    # Unter den Boden geraten (Ablegen am Rand, ignorierte Startkante)
                    floor = world.platform_below(self.x, -math.inf, floors_only=True)
                    if floor is not None and self.y > floor.y:
                        p = floor
                if p is not None:
                    self._land(world, p)
                    return
            if self.y > b.bottom + self.sprite:
                self.spawn(world)
                return

    def _landing(self, world: World, prev_y: float) -> Platform | None:
        best = None
        for p in world.platforms:
            if p == self._ignore or (self._floors_only and not p.is_floor):
                continue
            if p.x1 <= self.x <= p.x2 and prev_y <= p.y <= self.y and (best is None or p.y < best.y):
                best = p
        return best

    def _behave(self, dt: float, world: World) -> None:
        mood = self.needs.mood
        if mood == Mood.SICK:
            if not self.platform.is_floor:
                self._start_fall(floors_only=True)
                return
            if self.state not in ("eat", "purr", "sick_lie"):
                self._set("sick_lie", math.inf)
        elif self.state == "sick_lie":
            self._choose(world)

        if self._play_left > 0 and self._cursor is not None and self.state not in NO_PLAY + ("purr", "cheer"):
            self._play(dt, world)
            return
        if self.state in ("chase", "crouch", "flee"):
            self._choose(world)
            return

        self._timer -= dt
        if self.state == "walk":
            self._walk(dt, world)
        if self.state == "approach":
            self._approach(dt, world)
            return
        if self.state == "sleep":
            if self.needs.energy >= 80:
                self._choose(world)
            return
        if self._timer <= 0:
            if self.state == "eat" and self._lazy_after_eat:
                self._lazy_after_eat = False
                self._set("idle_sit", 60)
            else:
                self._choose(world)

    def _walk(self, dt: float, world: World) -> None:
        speed = self._speed(self.cfg.walk_speed)
        self.x += self.facing * speed * dt
        p = self.platform
        edge = p.x2 if self.facing > 0 else p.x1
        if (self.facing > 0 and self.x <= p.x2) or (self.facing < 0 and self.x >= p.x1):
            return
        n = world.neighbor(p, self.facing)
        if n is not None and self._allowed(world, n):
            self.platform = n
            self._ride_rect = None if n.is_floor else world.window_rect(n.owner)
        else:
            self.x = edge
            self.facing = -self.facing

    def _nearest_free(self, world: World) -> float | None:
        """Mitte des nächstgelegenen erlaubten Monitors."""
        free = _free(world)
        if not free:
            return None
        o = min(free, key=lambda o: abs(o.geometry.x + o.geometry.w / 2 - self.x))
        return o.geometry.x + o.geometry.w / 2

    def _flee(self, dt: float, world: World) -> None:
        """Gesperrter Monitor: zügig hinunter und über die Grenze laufen, nicht springen."""
        self._flee_s += dt
        target = self._nearest_free(world)
        if self._flee_s > FLEE_TIMEOUT or target is None:
            self.spawn(world)
            return
        if self.state in CLINGING:
            self._start_fall(floors_only=True)
            return
        if self.state in AIRBORNE:
            self._integrate(min(dt, MAX_PHYS_DT), world)
            return
        if not self._ride(world):
            self._start_fall(floors_only=True)
            return
        if not self.platform.is_floor:
            self._start_fall(floors_only=True)   # der Boden verbindet die Monitore
            return
        self.state = "flee"
        self.facing = 1 if target > self.x else -1
        self.x += self.facing * self._speed(self.cfg.walk_speed) * FLEE_FACTOR * dt
        p = self.platform
        if p.x1 <= self.x <= p.x2:
            return
        n = world.neighbor(p, self.facing)
        if n is None:                            # Monitore liegen nicht nebeneinander
            self.x = min(max(self.x, p.x1), p.x2)
            self.spawn(world)
            return
        self.platform = n
        self._ride_rect = None if n.is_floor else world.window_rect(n.owner)

    # --- Spielen ---

    def _can_play(self) -> bool:
        return (self.cfg.play_enabled and self.needs.mood != Mood.SICK and self.needs.energy >= 20
                and self.state not in NO_PLAY)

    def _touches_cursor(self) -> bool:
        cx, cy = self._cursor
        return abs(cx - self.x) <= self.sprite / 2 and self.y - self.sprite <= cy <= self.y

    def _play(self, dt: float, world: World) -> None:
        cx, cy = self._cursor
        dx = cx - self.x
        above = self.y - cy
        if abs(dx) > 2:
            self.facing = 1 if dx > 0 else -1
        if self.state == "crouch":
            self._timer -= dt
            if self._timer <= 0:
                self._pounce_at(cx, cy, "pounce")
            return
        if abs(dx) < 120 and 120 < above <= SWIPE_MAX_UP:
            self._pounce_at(cx, cy, "swipe")
        elif (abs(dx) < POUNCE_RANGE if self._can_dive(cy)
              else math.hypot(dx, cy - (self.y - self.sprite / 2)) < POUNCE_RANGE):
            # unter der Kante zählt nur der seitliche Abstand, die Tiefe macht die Schwerkraft
            self._set("crouch", self.rng.uniform(0.5, 1.0))
        else:
            self.state = "chase"
            self.x += self.facing * CHASE_SPEED * dt
            p = self.platform
            if not p.x1 <= self.x <= p.x2:
                n = world.neighbor(p, self.facing)
                if n is not None and self._allowed(world, n):
                    self.platform = n
                    self._ride_rect = None if n.is_floor else world.window_rect(n.owner)
                else:  # Kante: von hier aus springen
                    self.x = min(max(self.x, p.x1), p.x2)
                    self._set("crouch", self.rng.uniform(0.3, 0.6))

    def _can_dive(self, cy: float) -> bool:
        """Cursor deutlich unter der Kante: runterspringen statt davor zu hüpfen.
        Vom Boden aus nicht, da ginge es durch den Bildschirmrand."""
        return cy - self.y > DIVE_MIN_DROP and self.platform is not None and not self.platform.is_floor

    def _pounce_at(self, cx: float, cy: float, kind: str) -> None:
        """Sprung, dessen Scheitel (Pfoten) beim Cursor liegt."""
        dive = self._can_dive(cy)
        apex = self.y - 40 if dive else min(self.y - 40, cy + 60)
        vy0 = -math.sqrt(2 * GRAVITY * (self.y - apex))
        dy = cy - self.y if dive else 0.0
        t = (-vy0 + math.sqrt(vy0 * vy0 + 2 * GRAVITY * dy)) / GRAVITY
        vx = max(-MAX_POUNCE_VX, min(MAX_POUNCE_VX, (cx - self.x) / t))
        here = self.platform
        self._leap(None, vx, vy0)
        if dive:
            self._ignore = here   # sonst landet sie sofort wieder auf der eigenen Kante
        self._pounce = kind

    def _speed(self, base: float) -> float:
        return base / 2 if self.needs.mood == Mood.SAD else base

    def _approach(self, dt: float, world: World) -> None:
        step = self._speed(self.cfg.walk_speed) * dt
        if abs(self._target_x - self.x) <= step:
            self.x = self._target_x
            self._begin_climb(world)
            return
        self.x += self.facing * step
        if not self.platform.x1 <= self.x <= self.platform.x2:
            self.x = min(max(self.x, self.platform.x1), self.platform.x2)
            self._choose(world)

    def _begin_climb(self, world: World) -> None:
        old = self._wall
        cands = [w for w in world.walls if w.owner == old.owner and w.side == old.side
                 and w.y1 < self.y - 40 and w.y2 >= self.y - HANG_MAX_GAP]
        if not cands:
            self._choose(world)
            return
        w = min(cands, key=lambda w: abs(w.y2 - self.y))
        self._wall = w
        self.x = w.x + w.side * CLIMB_OFFSET
        self.facing = -w.side
        if w.y2 < self.y - 5:
            self._leap("wall", 0.0, -math.sqrt(2 * GRAVITY * (self.y - (w.y2 - 10))))
        else:
            self._grab = "wall"
            self._attach(world)

    def _leap(self, grab: str, vx: float, vy: float) -> None:
        self._grab = grab
        self._ignore = None
        self.platform = None
        self.state = "jump"
        self.vx, self.vy = vx, vy
        if vx:
            self.facing = 1 if vx > 0 else -1

    def _attach(self, world: World) -> None:
        kind, self._grab = self._grab, None
        self.vx = self.vy = 0
        self.platform = None
        if kind == "wall":
            self.x = self._wall.x + self._wall.side * CLIMB_OFFSET
            self.facing = -self._wall.side
            self._ride_rect = world.window_rect(self._wall.owner)
            self._set("climb", math.inf)
        else:
            self.y = self._ceiling.y + HANG_DROP
            self._ride_rect = world.window_rect(self._ceiling.owner)
            self._set("hang", self.rng.uniform(1.5, 3))

    def _cling(self, dt: float, world: World) -> None:
        if self.needs.mood == Mood.SICK:
            self._start_fall(floors_only=True)
            return
        owner = self._wall.owner if self.state == "climb" else self._ceiling.owner
        rect = world.window_rect(owner)
        if rect is None:
            self._start_fall()
            return
        if self._ride_rect is not None:
            dx, dy = rect.x - self._ride_rect.x, rect.y - self._ride_rect.y
            self.x += dx
            self.y += dy
            if self.state == "climb":
                w = self._wall
                self._wall = dataclasses.replace(w, x=w.x + dx, y1=w.y1 + dy, y2=w.y2 + dy)
            else:
                c = self._ceiling
                self._ceiling = dataclasses.replace(c, x1=c.x1 + dx, x2=c.x2 + dx, y=c.y + dy)
        self._ride_rect = rect
        if self.state == "hang":
            self._timer -= dt
            if self._timer <= 0:
                self._start_fall()
            return
        self.y -= self._speed(self.cfg.climb_speed) * dt
        if self.y <= self._wall.y1 + MOUNT_ABOVE:
            self._mount(world)

    def _mount(self, world: World) -> None:
        w = self._wall
        inside = w.x - w.side * 30
        p = world.platform_by_owner_at(w.owner, inside)
        if p is not None and abs(p.y - w.y1) <= 2 and self._allowed(world, p):
            self.x = inside
            self._land(world, p)
        else:  # Oberkante verdeckt oder nicht begehbar -> abspringen
            self._start_fall()
            self.vx = w.side * 150
            self.facing = w.side

    def _allowed(self, world: World, p: Platform) -> bool:
        o = world.output_at((p.x1 + p.x2) / 2, p.y - 1)
        return o is not None and o.name not in world.forbidden_outputs

    def _choose(self, world: World) -> None:
        if self.needs.energy < 20:
            self._set("sleep", math.inf)
            return
        if self.needs.mood == Mood.SICK:
            self._set("sick_lie", math.inf)
            return
        p = self.platform
        r = self.rng.random()
        p_jump = self.cfg.p_jump
        p_climb = p_jump + self.cfg.p_climb
        p_hang = p_climb + self.cfg.p_hang
        reach = self._jump_targets(world, p) if r < p_jump else []
        walls = world.walls_near(p, self.x, CLIMB_OFFSET) if p_jump <= r < p_climb else []
        ceils = world.ceilings_near(p, self.x, HANG_MIN_GAP, HANG_MAX_GAP) if p_climb <= r < p_hang else []
        if reach:
            self._jump_to(self.rng.choice(reach))
        elif walls:
            self.start_climb(world, self.rng.choice(walls))
        elif ceils:
            self.start_hang(world, self.rng.choice(ceils))
        elif self.rng.random() < 0.5:
            if self.rng.random() < P_GROOM:
                self._set("groom", self.rng.uniform(3, 7))
            else:
                self._set("idle_sit", self.rng.uniform(3, 10))
        else:
            self.facing = self.rng.choice((-1, 1))
            self._set("walk", self.rng.uniform(2, 8))

    def _jump_targets(self, world: World, p: Platform) -> list[Platform]:
        # Scheitel liegt 60 px über dem Ziel; Sprite muss darunter noch auf den Schirm passen
        top = world.bounds().y + self.sprite + 60
        return [q for q in world.reachable(p, self.x, max_up=math.inf) if q.y >= top]

    def _jump_to(self, q: Platform) -> None:
        tx = self.rng.uniform(q.x1 + 20, q.x2 - 20)
        dy = q.y - self.y
        h = max(0.0, -dy) + 60
        vy0 = -math.sqrt(2 * GRAVITY * h)
        t = (-vy0 + math.sqrt(vy0 * vy0 + 2 * GRAVITY * dy)) / GRAVITY
        self._ignore = self.platform
        self.platform = None
        self.state = "jump"
        self.vx = (tx - self.x) / t
        self.vy = vy0
        self.facing = 1 if self.vx >= 0 else -1
