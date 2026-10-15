"""Verhalten und Physik der Katze (rein, ohne Qt)."""
import dataclasses
import math
import random

from . import ufo
from .bigtree import BASE_KEY, BOARD_ID, DOOR_W, cave_of, in_hammock, is_tree, reachable_toys
from .config import Config
from .furniture import ROLL_FRICTION, TREE_ID, Furniture
from .needs import Mood, Needs
from .world import GRAVITY, Ceiling, Platform, Rect, Wall, World

_DEFAULTS = Config()
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
CHASE_MIN_DX = 20    # darunter nicht nachlaufen, sonst zappelt sie um den Cursor herum
POUNCE_RANGE = 200
SWIPE_MAX_UP = 350
DIVE_MIN_DROP = 40   # so weit unter den Pfoten lohnt der Sprung nach unten
MAX_POUNCE_VX = 900
PLAY_REWARD = 3
SHAKE_MIN_PX = 60    # Strecke, die ein Richtungswechsel wert ist
SHAKE_DECAY = 1.2    # Wechsel pro Sekunde, die wieder vergessen werden
VOMIT_S = 2.5
VOMIT_SATIETY = 25   # so viel kommt wieder hoch
JUMP_MAX_SIDE = _DEFAULTS.jump_max_side
FLEE_FACTOR = 4      # so viel schneller als sonst läuft sie vom gesperrten Monitor
FLEE_TIMEOUT = 30.0  # kommt sie nicht weg (Monitore nicht benachbart), doch umsetzen
# Frame-Pixel von der Katzenmitte bis zur Möbelmitte: Napf in der Fress-Pose,
# Knäuel an der ausgestreckten Pfote
REACH = {"bowl": 11, "yarn": 18, "tree": 11}
BOWL_REACH = REACH["bowl"]
YARN_KICK = (150, 350)   # px/s, so fest stupst sie das Knäuel an
YARN_BATS = (3, 6)       # so oft hintereinander, dann reicht es
YARN_REWARD = 1          # Zuneigung pro Stupser
BIGTREE_NEAR = 400       # px neben dem großen Kratzbaum: in seiner Nähe
BIGTREE_HOP = 0.6        # auf dem großen Kratzbaum: weiter zur nächsten Fläche
HAMMOCK_REST = ("idle_sit", "sleep", "purr", "groom")
HAMMOCK_SWAY_FPS = 3     # langsamer als die übrigen Animationen: schaukeln
# Höhle des großen Kratzbaums: hinein (verblasst), Kopf rausstrecken / wegducken / schlafen, raus
CAVE_STATES = ("cave_in", "cave", "cave_duck", "cave_sleep", "cave_butt", "cave_out")
CAVE_IN_S = 0.8
CAVE_OUT_S = 0.5
CAVE_STAY = (8.0, 25.0)  # so lange schaut sie heraus
CAVE_LOOK_S = 1.5        # im Schnitt so oft schaut sie in die andere Richtung
CAVE_SPOOK = 150         # Maus so nah an der Tür: wegducken oder herausspringen
P_CAVE = 0.3             # Anteil der Baumbesuche, die in die Höhle führen
P_CAVE_SLEEP = 0.5       # müde und Höhle in der Nähe: lieber dort schlafen als im Bett
P_CAVE_BUTT = 0.08       # selten verkehrt herum drin: der Hintern schaut heraus
# Napf nah an einer Kante (Fenster, Kratzbaum): ab und an schubst sie ihn herunter
P_BOWL_PUSH = 0.25       # je Entscheidung, solange er so steht
BOWL_EDGE = 1.0          # Sprites: so nah steht der Napf an der Kante
BOWL_NUDGES = (1, 3)     # so oft stupst sie, der letzte Stups wirft ihn hinunter
BOWL_NUDGE_S = 0.6
# Bällchen am großen Kratzbaum: von der Fläche darunter mit erhobener Pfote anschlagen
P_TOY = 0.35             # Anteil der Entscheidungen auf einer Fläche mit erreichbarem Bällchen
TOY_PAW = 6              # Frame-Pixel von ihrer Mitte bis unter das Bällchen
TOY_SWATS = (2, 4)
SWAT_S = 0.5
# Jagd am großen Kratzbaum: auf die Fläche direkt unter dem Mauszeiger springen
TREE_CHASE_UP = 120      # px: so weit darf der Zeiger über dieser Fläche sein

AIRBORNE = ("jump", "fall", "thrown")
CLINGING = ("climb", "hang")
NO_PLAY = ("sleep", "dragged", "climb", "hang", "hidden", "eat", "sick_lie", "vomit", "bat", "nudge") + CAVE_STATES
ANIM_FOR_STATE = {"chase": "walk", "approach": "walk", "flee": "walk", "seek": "walk", "idle_sit": "sit", "sick_lie": "lie", "thrown": "fall", "hidden": "sit",
                  "beamed": "dragged", "abducted": "sit", "cave_in": "cave_in", "cave": "cave_peek",
                  "cave_duck": "cave_duck", "cave_sleep": "cave_sleep", "cave_butt": "cave_butt",
                  "cave_out": "crawl", "nudge": "bat",
                  "to_toy": "walk", "swat": "swipe"}
MOOD_NAME = {Mood.NORMAL: "normal", Mood.SAD: "sad", Mood.SICK: "sick"}
# Unter einer niedrigen Fensterkante passt sie nicht aufrecht durch
CRAMPED_ANIM = {"walk": "crawl", "sit": "lie", "groom": "lie"}


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
        self._shakes = 0.0
        self._shake_dir = 0
        self._shake_px = 0.0
        self._queasy = False
        self._cramped = False
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
        self.furniture = Furniture()
        self._goal: str | None = None   # Möbel, zu dem sie gerade läuft ("seek")
        self._world: World | None = None  # letzte Welt aus tick, für Befehle von außen
        self._in_bed = False
        self._bats_left = 0
        self._waiting = False   # "seek", aber das Knäuel fliegt gerade: sitzen und zuschauen
        self._post_x = 0.0      # Pfeiler des großen Kratzbaums, an dem sie kratzen will
        self._cave: str | None = None        # großer Kratzbaum, in dessen Höhle sie ist
        self._cave_plan: str | None = None   # auf dem Weg dorthin: "peek" oder "sleep"
        self._spooked = False   # Maus war schon nah an der Tür (nur einmal reagieren)
        self._push_dir = 0      # Napf zu dieser Kante hin herunterschubsen (0 = nicht)
        self._nudges_left = 0
        self._post: tuple[str, int] | None = None   # (großer Kratzbaum, Pfeiler), an dem sie kratzt
        self._toy: tuple[str, int] | None = None    # (großer Kratzbaum, Bällchen), nach dem sie schlägt
        self._swats_left = 0

    # --- Zustand von außen ---

    @property
    def sprite(self) -> int:
        return self.cfg.sprite_px

    @property
    def visible(self) -> bool:
        return self.state not in ("hidden", "abducted") and not self.paused

    @property
    def opacity(self) -> float:
        """Durch die Tür der Höhle verblasst sie im Dunkeln bzw. taucht wieder auf."""
        if self.state == "cave_in":
            return max(0.0, min(1.0, self._timer / CAVE_IN_S))
        if self.state == "cave_out":
            return 1.0 - max(0.0, min(1.0, self._timer / CAVE_OUT_S))
        return 1.0

    def behind(self) -> tuple[str, str] | None:
        """(Baumart, Brett), hinter dessen Wand sie gerade ist: beim Hineinschlüpfen
        sieht man sie nur durch die Tür."""
        return (self._cave, "cave") if self.state == "cave_in" and self._cave else None

    @property
    def in_bed(self) -> bool:
        return self.state == "sleep" and self._in_bed

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
        if self.grounded and self.state not in CAVE_STATES:   # in der Höhle bleibt sie
            self._set("purr", 1.5)

    def go_sleep(self) -> None:
        """Ins Bett, falls eins erreichbar ist, sonst gleich hier."""
        if self.grounded and not self.abducted:
            if self.state in ("cave", "cave_duck"):
                self._set("cave_sleep", math.inf)
            elif self._world is None or not self._seek("bed", self._world):
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
        self._shakes = 0.0
        self._shake_dir = 0
        self._shake_px = 0.0
        self.state = "dragged"
        self.platform = None
        self.vx = self.vy = 0
        self._drag_idle = 0.0
        self._grab = None
        self._pounce = None
        self._goal = None

    def drag_to(self, x: float, y: float) -> None:
        if self.state != "dragged":  # z.B. während der Entführung
            return
        if x != self.x:
            d = 1 if x > self.x else -1
            if d != self._shake_dir:
                if self._shake_px >= SHAKE_MIN_PX:   # ein ordentlicher Ruck, kein Zittern
                    self._shakes += 1
                    self._queasy = self._queasy or (self.cfg.shake_enabled
                                                    and self._shakes >= self.cfg.shake_limit)
                self._shake_dir, self._shake_px = d, 0.0
            self._shake_px += abs(x - self.x)
            self.facing = d
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

    def hammock(self) -> str | None:
        """Kante der Hängematte, in der sie gerade liegt."""
        if self.state in HAMMOCK_REST and self.platform is not None and in_hammock(self.platform.owner):
            return self.platform.owner
        return None

    def frame_key(self, t: float) -> tuple[str, str, int, bool]:
        anim = ANIM_FOR_STATE.get(self.state, self.state)
        frame = int(t * ANIM_FPS)
        if self.state == "jump" and self._pounce == "swipe":
            anim = "swipe"
        elif self.state == "seek" and self._waiting:
            anim = "sit"
        elif self.state == "climb" and self._wall is not None and self._wall.owner.startswith(BOARD_ID):
            anim = "climb_post"   # umgreift den Pfeiler des großen Kratzbaums
        elif self.hammock() is not None:
            anim = "hammock_sleep" if self.state == "sleep" else "hammock"
            frame = int(t * HAMMOCK_SWAY_FPS)
        if self._cramped:
            anim = CRAMPED_ANIM.get(anim, anim)
        return anim, MOOD_NAME[self.needs.mood], frame, self.facing < 0

    # --- Simulation ---

    def _activity(self) -> str:
        if self.state in AIRBORNE + CLINGING + ("walk", "approach", "dragged", "chase", "crouch", "flee", "seek", "bat",
                                                "to_toy", "swat"):
            return "active"
        return "sleep" if self.state in ("sleep", "cave_sleep") else "rest"

    def tick(self, dt: float, world: World, locked: bool,
             cursor: tuple[float, float] | None = None, wiggling: bool = False) -> None:
        if self.paused:
            return
        self._cursor = cursor
        self._world = world
        self.furniture.tick(world, min(dt, MAX_PHYS_DT), self.sprite)
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
            self._shakes = max(0.0, self._shakes - SHAKE_DECAY * dt)
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
        self._cramped = (self.grounded and self.platform is not None
                         and self.platform.y - out.work_area.y < self.sprite)
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
        self._in_bed = False
        self._waiting = False

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
        if self._queasy:          # zu wild geschüttelt
            self._queasy = False
            self._shakes = 0.0
            self.needs.satiety = max(0.0, self.needs.satiety - VOMIT_SATIETY)
            self._set("vomit", VOMIT_S)
        elif self._goal is not None and self.state == "idle_sit":
            self.state = "seek"   # zum Möbel heruntergesprungen: weiterlaufen

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
            if self.state == "sick_lie" and self._hungry() and self._seek("bowl", world):
                return
            if self.state not in ("eat", "purr", "sick_lie", "seek"):
                self._set("sick_lie", math.inf)
        elif self.state == "sick_lie":
            self._choose(world)

        if self.state in CAVE_STATES:
            self._in_cave(dt, world)
            return
        if self._play_left > 0 and self._cursor is not None and self.state not in NO_PLAY + ("purr", "cheer"):
            self._play(dt, world)
            return
        if self.state in ("chase", "crouch", "flee"):
            self._choose(world)
            return

        if self.state == "seek":
            self._go(dt, world)
            return
        self._timer -= dt
        if self.state == "walk":
            self._walk(dt, world)
        if self.state == "approach":
            self._approach(dt, world)
            return
        if self.state == "to_toy":
            self._to_toy(dt, world)
            return
        if self.state == "scratch" and self._post is not None and self._post[0] in self.furniture.trees:
            self.furniture.trees[self._post[0]].scratch(self._post[1], dt)   # Sisal franst aus
        if self.state == "sleep":
            bed = self.furniture.usable("bed", world)
            if self._in_bed and (bed is None or abs(bed[0] - self.x) > 1 or abs(bed[1] - self.y) > 1):
                self._in_bed = False   # Bett weggezogen, eingelagert oder runtergefallen
            if self.needs.energy >= 80:
                self._choose(world)
            return
        if self._timer <= 0:
            if self.state == "eat" and self._lazy_after_eat:
                self._lazy_after_eat = False
                self._set("idle_sit", 60)
            elif self.state == "vomit":
                self._set("groom", self.rng.uniform(4, 7))   # danach macht sie sich sauber
            elif self.state == "nudge":
                self._after_nudge(world)
            elif self.state == "swat":
                self._swat(world)
            elif self.state == "bat":   # hinterher oder erst mal verschnaufen
                if self._bats_left <= 0 or not self._seek("yarn", world):
                    self._set("idle_sit", self.rng.uniform(3, 10))
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
        hop = self._tree_hop(world, cx, cy)
        if hop is not None:
            self._jump_to(hop, cx)   # Fläche für Fläche hinter dem Zeiger her
            return
        if abs(dx) < 120 and 120 < above <= SWIPE_MAX_UP:
            self._pounce_at(cx, cy, "swipe")
        elif abs(dx) < CHASE_MIN_DX or (abs(dx) < POUNCE_RANGE if self._can_dive(cy)
                                       else math.hypot(dx, cy - (self.y - self.sprite / 2)) < POUNCE_RANGE):
            # unter der Kante zählt nur der seitliche Abstand, die Tiefe macht die Schwerkraft
            self._set("crouch", self.rng.uniform(0.5, 1.0))
        else:
            self.state = "chase"
            self.x += self.facing * min(CHASE_SPEED * dt, abs(dx))   # nie über den Cursor hinaus
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
        if p is None and w.owner.startswith(BOARD_ID):   # schmale Fläche am Pfeiler: so weit es geht
            p = next((q for q in world.platforms if q.owner == w.owner and abs(q.y - w.y1) <= 2), None)
            if p is not None:
                inside = min(max(inside, p.x1), p.x2)
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
        self._goal = None
        self._cave = self._cave_plan = None
        self._push_dir = 0
        self._post = self._toy = None
        if self.platform is not None and in_hammock(self.platform.owner) and self.needs.mood != Mood.SICK:
            if self.needs.energy < 60:          # in der Hängematte erst mal ausruhen
                self._set("sleep", math.inf)
                return
            if self.rng.random() < 0.6:
                self._set("idle_sit", self.rng.uniform(8, 20))
                return
        if self.needs.energy < 20:
            near = self._bigtree_near(world)
            if (near is not None and self._cave_door(world, near) is not None
                    and self.rng.random() < P_CAVE_SLEEP and self._seek_cave(near, "sleep", world)):
                return
            if not self._seek("bed", world):
                self._set("sleep", math.inf)
            return
        if self.needs.mood == Mood.SICK:
            if not (self._hungry() and self._seek("bowl", world)):
                self._set("sick_lie", math.inf)
            return
        if self._hungry() and self._seek("bowl", world):
            return
        edge = self._bowl_edge(world)   # Würfel nur, wenn der Napf an einer Kante steht
        if edge and self.rng.random() < P_BOWL_PUSH and self._seek_push(edge, world, fresh=True):
            return
        # Würfel nur mit Knäuel bzw. Kratzbaum, sonst verschiebt sich der Zufall für alles andere
        if (self.furniture.usable("yarn", world) is not None
                and self.rng.random() < self.cfg.p_yarn and self._seek("yarn", world)):
            self._bats_left = self.rng.randint(*YARN_BATS)
            return
        if (self.furniture.usable("tree", world) is not None and self.platform.is_floor
                and self.rng.random() < self.cfg.p_tree and self._seek("tree", world)):
            return
        near = self._bigtree_near(world)
        if near is not None:
            on = self.platform.owner.startswith(BOARD_ID)
            if self.rng.random() < (BIGTREE_HOP if on else self.cfg.p_bigtree) and self._use_bigtree(world, near, on):
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
            if self.rng.random() < self.cfg.p_groom:
                self._set("groom", self.rng.uniform(3, 7))
            else:
                self._set("idle_sit", self.rng.uniform(3, 10))
        else:
            self.facing = self.rng.choice((-1, 1))
            self._set("walk", self.rng.uniform(2, 8))

    def _jump_targets(self, world: World, p: Platform) -> list[Platform]:
        # Scheitel liegt 60 px über dem Ziel; Sprite muss darunter noch auf den Schirm passen
        top = world.bounds().y + self.sprite + 60
        reach = world.reachable(p, self.x, max_up=math.inf, max_side=self.cfg.jump_max_side)
        return [q for q in reach if q.y >= top]

    def _jump_to(self, q: Platform, aim: float | None = None) -> None:
        """aim: möglichst dort landen (sonst zufällig in Reichweite)."""
        # Nur in Reichweite landen: breite Plattformen (der Boden des Nachbarmonitors)
        # liefern sonst Ziele quer über den Schirm und damit absurde Geschwindigkeiten
        lo = max(q.x1 + 20, self.x - self.cfg.jump_max_side)
        hi = min(q.x2 - 20, self.x + self.cfg.jump_max_side)
        if lo >= hi:
            tx = min(max(self.x, q.x1), q.x2)
        elif aim is not None:
            tx = min(max(aim, lo), hi)
        else:
            tx = self.rng.uniform(lo, hi)
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

    # --- Möbel ---

    def _bigtree_near(self, world: World) -> str | None:
        """Nächster aufgestellter großer Kratzbaum, wenn sie auf oder neben ihm ist."""
        on = self.platform.owner[len(BOARD_ID):].split(":")[0] if self.platform.owner.startswith(BOARD_ID) else None
        best = None
        for kind in self.furniture.trees:
            pos = self.furniture.usable(kind, world)
            if pos is None:
                continue
            d = abs(pos[0] - self.x) - self.furniture.half_width(kind, self.sprite)
            if (kind == on or d < BIGTREE_NEAR) and (best is None or d < best[1]):
                best = (kind, d)
        return best[0] if best is not None else None

    def _use_bigtree(self, world: World, kind: str, on: bool) -> bool:
        """Auf eine andere Fläche springen, am Pfeiler hochklettern, daran kratzen oder in
        die Höhle gehen."""
        if (not on and self._cave_door(world, kind) is not None and self.rng.random() < P_CAVE
                and self._seek_cave(kind, "peek", world)):
            return True
        toys = self._toys_here(world) if on else []
        if toys and self.rng.random() < P_TOY:
            self._toy = self.rng.choice(toys)
            self._swats_left = self.rng.randint(*TOY_SWATS)
            self._set("to_toy", math.inf)
            return True
        ups = [q for q in self._jump_targets(world, self.platform)
               if q.owner.startswith(BOARD_ID) and q != self.platform]
        walls = [] if on else [w for w in world.walls_near(self.platform, self.x, CLIMB_OFFSET)
                               if w.owner.startswith(f"{BOARD_ID}{kind}:")]
        r = self.rng.random()
        if walls and r < 0.4:
            self.start_climb(world, self.rng.choice(walls))
            return True
        if ups and (on or r < 0.75):
            self._jump_to(self.rng.choice(ups))
            return True
        return not on and self._seek(kind, world)

    def _hungry(self) -> bool:
        """Erst wenn eine ganze Portion reinpasst, sonst wäre sie danach träge."""
        return self.needs.satiety < max(20.0, 100 - self.cfg.feed_amount)

    def _route(self, world: World, p: Platform | None, from_x: float, x: float) -> Platform | None:
        """Plattform bei x, die von p aus zu Fuß erreichbar ist (Nachbarn gleicher Höhe,
        auch über Monitorgrenzen)."""
        d = 1 if x >= from_x else -1
        while p is not None and not p.x1 <= x <= p.x2:
            p = world.neighbor(p, d)
            if p is not None and not self._allowed(world, p):
                return None
        return p if p is not None and self._allowed(world, p) else None

    def _spot(self, kind: str, world: World) -> tuple[float, Platform] | None:
        """Wo sie stehen muss, um das Möbel zu benutzen: im Bett mittig, sonst daneben
        (bevorzugt auf ihrer Seite), auf seiner Kante oder deren Nachbarn."""
        pos = self.furniture.usable(kind, world)
        if pos is None:
            return None
        if is_tree(kind):
            return self._cave_door(world, kind) if self._cave_plan else self._post_spot(kind, pos, world)
        if kind == "bed":
            spots = [pos[0]]
        elif kind == "bowl" and self._push_dir:   # auf der Innenseite, mit der Pfote dran
            spots = [pos[0] - self._push_dir * REACH["yarn"] * self.sprite / 32]
        else:
            reach = REACH[kind] * self.sprite / 32
            side = -1 if self.x < pos[0] else 1
            spots = [pos[0] + side * reach, pos[0] - side * reach]
        for x in spots:
            q = self._route(world, self.furniture.platform(kind), pos[0], x)
            if q is not None:
                return x, q
        return None

    def _toys_here(self, world: World) -> list[tuple[str, int]]:
        """Bällchen, die über ihrer Fläche des großen Kratzbaums in Pfotenhöhe hängen."""
        owner = self.platform.owner if self.platform is not None else ""
        if not owner.startswith(BOARD_ID):
            return []
        kind, _, key = owner[len(BOARD_ID):].partition(":")
        if kind not in self.furniture.trees:
            return []
        return [(kind, i) for i, k in reachable_toys(self.furniture.trees[kind].layout()) if k == key]

    def _toy_x(self, world: World) -> float | None:
        """Wo das Bällchen hängt (global, Fadenmitte); None, wenn Baum oder Bällchen weg sind."""
        kind, i = self._toy
        pos = self.furniture.usable(kind, world) if kind in self.furniture.trees else None
        if pos is None:
            return None
        lay = self.furniture.trees[kind].layout()
        if i >= len(lay.toys):
            return None
        return pos[0] + (lay.toys[i][0] + 0.5 - lay.w / 2) * self.sprite / 32

    def _to_toy(self, dt: float, world: World) -> None:
        """Unter das Bällchen laufen (von der Seite, auf der sie ist) und losschlagen."""
        gx = self._toy_x(world)
        p = self.platform
        if gx is None or not p.x1 <= gx <= p.x2:
            self._choose(world)
            return
        side = 1 if gx >= self.x else -1
        tx = min(max(gx - side * TOY_PAW * self.sprite / 32, p.x1), p.x2)
        step = self._speed(self.cfg.walk_speed) * dt
        if abs(tx - self.x) > step:
            self.facing = 1 if tx > self.x else -1
            self.x += self.facing * step
            return
        self.x = tx
        self.facing = side
        self._swat(world)

    def _swat(self, world: World) -> None:
        """Ein Pfotenschlag; danach noch einer oder zuschauen, wie es pendelt."""
        if self._swats_left <= 0 or self._toy_x(world) is None:
            self._toy = None
            self._set("idle_sit", self.rng.uniform(2, 5))
            return
        self._swats_left -= 1
        self.furniture.bat_toy(*self._toy, self.facing)
        self._set("swat", SWAT_S)

    def _tree_hop(self, world: World, cx: float, cy: float) -> Platform | None:
        """Beim Spielen am großen Kratzbaum: Fläche direkt unter dem Mauszeiger, auf die sie
        springen kann; None, wenn sie schon dort ist oder keine passt."""
        p = self.platform
        if p is None:
            return None
        on = p.owner.startswith(BOARD_ID)

        def under(q: Platform) -> bool:
            return q.x1 - 8 <= cx <= q.x2 + 8 and 0 <= q.y - cy <= TREE_CHASE_UP
        if under(p):
            return None
        cands = [q for q in self._jump_targets(world, p)
                 if q != p and under(q) and (q.owner.startswith(BOARD_ID) or (on and q.is_floor))]
        return min(cands, key=lambda q: q.y - cy, default=None)

    def _bowl_edge(self, world: World) -> int:
        """Richtung der Kante, an der der Napf steht und von der er herunterfallen kann (0: keine)."""
        pos = self.furniture.usable("bowl", world)
        p = self.furniture.platform("bowl")
        if pos is None or p is None or p.is_floor:
            return 0
        for d in (-1, 1):
            edge = p.x2 if d > 0 else p.x1
            if abs(edge - pos[0]) <= BOWL_EDGE * self.sprite and world.neighbor(p, d) is None:
                return d
        return 0

    def _seek_push(self, d: int, world: World, fresh: bool = False) -> bool:
        if fresh:
            self._nudges_left = self.rng.randint(*BOWL_NUDGES)
        self._push_dir = d
        if self._seek("bowl", world):
            return True
        self._push_dir = 0
        return False

    def _nudge(self, world: World) -> None:
        """Mit der Pfote anstupsen: erst ein Stück, beim letzten Mal über die Kante."""
        d = self._push_dir
        p = self.furniture.platform("bowl")
        bx = self.furniture.bodies["bowl"].x
        self.facing = d
        self._nudges_left -= 1
        to_edge = abs((p.x2 if d > 0 else p.x1) - bx) + 2
        travel = to_edge * (1.0 if self._nudges_left <= 0 else self.rng.uniform(0.25, 0.45))
        self.furniture.shove_bowl(d * math.sqrt(2 * ROLL_FRICTION * travel) * (1.15 if self._nudges_left <= 0 else 1))
        self._set("nudge", BOWL_NUDGE_S)

    def _after_nudge(self, world: World) -> None:
        d = self._push_dir
        if self._nudges_left > 0 and self._bowl_edge(world) == d and self._seek_push(d, world):
            return   # hinterher und nochmal
        self._push_dir = 0
        self.facing = d or self.facing
        self._set("idle_sit", self.rng.uniform(2, 4))   # zuschauen

    def _cave_door(self, world: World, kind: str) -> tuple[float, Platform] | None:
        """Vor der Tür der Höhle (Mitte) auf dem Sockel; None ohne Höhle."""
        pos = self.furniture.usable(kind, world)
        if pos is None:
            return None
        lay = self.furniture.trees[kind].layout()
        b = cave_of(lay)
        if b is None:
            return None
        s = self.sprite / 32
        x = pos[0] + (b.x1 + (b.x2 - b.x1 - DOOR_W) // 2 + DOOR_W / 2 - lay.w / 2) * s
        q = world.platform_by_owner_at(f"{BOARD_ID}{kind}:{BASE_KEY}", x)
        return (x, q) if q is not None and self._allowed(world, q) else None

    def _seek_cave(self, kind: str, plan: str, world: World) -> bool:
        self._cave_plan = plan
        if self._seek(kind, world):
            return True
        self._cave_plan = None
        return False

    def _in_cave(self, dt: float, world: World) -> None:
        door = self._cave_door(world, self._cave) if self._cave else None
        if door is None or abs(door[0] - self.x) > 2:   # Baum weg, verschoben oder ohne Höhle
            self._choose(world)
            return
        s = self.sprite / 32
        cursor = self._cursor
        near = cursor is not None and math.hypot(cursor[0] - self.x, cursor[1] - (self.y - 8 * s)) < CAVE_SPOOK
        if self.state == "cave" and near and not self._spooked:
            if (self.cfg.play_enabled and self.needs.mood != Mood.SICK and self.needs.energy >= 20
                    and self.rng.random() < 0.5):
                self._set("cave_out", CAVE_OUT_S / 2)   # raus und hinterher
                self._play_left = PLAY_LINGER
            else:
                self._set("cave_duck", self.rng.uniform(1.5, 3))
        self._spooked = near
        if self.state == "cave" and self.rng.random() < dt / CAVE_LOOK_S:
            self.facing = -self.facing   # umschauen
        if self.state == "cave_sleep":
            if self.needs.energy >= 80:
                self._set("cave", self.rng.uniform(3, 6))   # aufgewacht: kurz schauen, dann raus
            return
        self._timer -= dt
        if self._timer > 0:
            return
        if self.state == "cave_in":
            if self._cave_plan == "sleep" or self.needs.energy < 40:
                self._set("cave_sleep", math.inf)
            elif self.rng.random() < P_CAVE_BUTT:
                self._set("cave_butt", self.rng.uniform(4, 10))
            else:
                self._set("cave", self.rng.uniform(*CAVE_STAY))
            self._cave_plan = None
        elif self.state == "cave_duck":
            self._set("cave", self.rng.uniform(3, 8))
        elif self.state in ("cave", "cave_butt"):
            self._set("cave_out", CAVE_OUT_S)
        else:
            self._choose(world)

    def _post_spot(self, kind: str, pos, world: World) -> tuple[float, Platform] | None:
        """Neben dem nächsten Pfeiler, der bis zum Boden reicht (hängend reicht keiner)."""
        tree = self.furniture.trees[kind]
        if tree.hanging:
            return None
        s = self.sprite / 32
        lay = tree.layout()
        left = pos[0] - lay.w / 2 * s
        reach = REACH["tree"] * s
        posts = sorted(((left + x * s, i) for i, (x, _, _) in enumerate(lay.posts)), key=lambda p: abs(p[0] - self.x))
        for gx, i in posts:
            side = -1 if self.x < gx else 1
            for x in (gx + side * reach, gx - side * reach):
                q = self._route(world, self.furniture.platform(kind), pos[0], x)
                if q is not None:
                    self._post_x = gx
                    self._post = (kind, i)
                    return x, q
        return None

    def _way(self, world: World, x: float, q: Platform) -> str | None:
        """Wie sie zu x auf q kommt: "walk", "jump", "fall" (zum Boden) oder gar nicht."""
        p = self.platform
        if p is None:
            return None
        here = self._route(world, p, self.x, x)
        if here is not None and abs(here.y - q.y) <= 2:
            return "walk"
        if q in self._jump_targets(world, p):
            return "jump"
        if q.is_floor and not p.is_floor:
            return "fall"
        return None

    def _target(self, kind: str, world: World) -> tuple[float, Platform, str] | None:
        """Standplatz, seine Kante und der Weg dorthin; None = nicht erreichbar oder sinnlos."""
        if kind == "bowl" and self.furniture.food <= 0 and not self._push_dir:
            return None
        spot = self._spot(kind, world)
        way = self._way(world, *spot) if spot is not None else None
        return (*spot, way) if way is not None else None

    def _seek(self, kind: str, world: World) -> bool:
        if self._target(kind, world) is None:
            return False
        self._goal = kind
        self._set("seek", math.inf)
        return True

    def _go(self, dt: float, world: World) -> None:
        kind = self._goal
        goal = self._target(kind, world) if kind else None
        body = self.furniture.bodies[kind] if kind else None
        if goal is None and body is not None and body.placed and not body.resting:
            self._waiting = True   # fällt, fliegt oder hängt an der Maus: zuschauen
            self.facing = 1 if body.x >= self.x else -1
            return
        self._waiting = False
        if goal is None:   # eingelagert, leer, unerreichbar, Monitor gesperrt: wie ohne Möbel
            if kind == "bed":
                self._goal = None
                self._set("sleep", math.inf)
            else:
                self._choose(world)
            return
        tx, q, way = goal
        if way == "jump":
            self._jump_to(q, tx)
            return
        if way == "fall":
            self._start_fall(floors_only=True)
            return
        step = (CHASE_SPEED if kind == "yarn" else self._speed(self.cfg.walk_speed)) * dt
        if abs(tx - self.x) <= step:
            self.x = tx
            self._arrive(kind, world)
            return
        self.facing = 1 if tx > self.x else -1
        self.x += self.facing * step
        p = self.platform
        if not p.x1 <= self.x <= p.x2:
            n = world.neighbor(p, self.facing)
            if n is not None and self._allowed(world, n):
                self.platform = n
                self._ride_rect = None if n.is_floor else world.window_rect(n.owner)
            else:   # sollte _route verhindern; nicht festlaufen
                self.x = min(max(self.x, p.x1), p.x2)
                self._goal = None
                self._set("idle_sit", self.rng.uniform(3, 10))

    def _arrive(self, kind: str, world: World) -> None:
        self._goal = None
        if kind == "bed":
            self._set("sleep", math.inf)
            self._in_bed = True
            return
        if kind == "bowl" and self._push_dir:
            self._nudge(world)
            return
        if is_tree(kind) and self._cave_plan:
            self._cave = kind
            self._set("cave_in", CAVE_IN_S)
            return
        bx = self.furniture.usable(kind, world)[0]
        if is_tree(kind):
            bx = self._post_x   # zum Pfeiler, nicht zur Mitte des Baums
        self.facing = 1 if bx >= self.x else -1
        if is_tree(kind):
            self._set("scratch", self.rng.uniform(2.5, 5))
        elif kind == "tree":
            deck = next((p for p in world.platforms if p.owner == TREE_ID), None)
            if deck is not None and self.rng.random() < 0.5:
                self._jump_to(deck, bx)   # hinauf auf die Liegefläche
            else:
                self._set("scratch", self.rng.uniform(2.5, 5))
        elif kind == "yarn":
            self._bats_left -= 1
            self.furniture.kick(self.facing * self.rng.uniform(*YARN_KICK))
            self.needs.affection = min(100.0, self.needs.affection + YARN_REWARD)
            self._set("bat", 0.5)
        elif self.furniture.eat():
            self._lazy_after_eat = self.needs.feed(self.cfg)
            self._set("eat", 3)
