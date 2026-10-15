import random

from taskbar_cat import storage
from taskbar_cat.cat import BOWL_REACH, SPRITE, Cat
from taskbar_cat.furniture import BOWL_PORTIONS, Furniture
from taskbar_cat.needs import Mood, Needs
from taskbar_cat.world import Output, Rect, Win, World

DT = 1 / 30
HALF = 20


def world(*wins, blocked=()):
    outs = [Output(n, Rect(i * 1920, 0, 1920, 1080), Rect(i * 1920, 44, 1920, 1036))
            for i, n in enumerate(("DP-3", "DP-4"))]
    return World(outs, list(wins), blocked)


def cat_with(w, furniture=None, x=960, **needs):
    c = Cat(Needs(**needs), random.Random(1))
    c.furniture = furniture or Furniture()
    c.spawn(w)
    c.x = x
    return c


def run(c, w, seconds, until=None):
    for _ in range(int(seconds / DT)):
        c.tick(DT, w, False)
        if until is not None and until(c):
            return True
    return False


# --- Furniture ---

def settle(f, w, seconds=3):
    for _ in range(int(seconds / DT)):
        f.tick(w, DT, SPRITE)


def standing(w, kind, x, y=500, f=None):
    """Bei (x, y) aufstellen und fallen lassen, bis es steht."""
    f = f or Furniture()
    f.place(kind, w, x, y, HALF)
    settle(f, w)
    assert f.bodies[kind].resting
    return f


def test_starts_in_inventory():
    f = Furniture()
    assert not any(f.placed(k) for k in f.bodies)
    assert f.position("bed", world()) is None


def test_placed_furniture_falls_to_floor():
    w = world()
    f = standing(w, "bed", 2500)
    assert f.position("bed", w) == (2500, 1080)
    assert f.platform("bed").owner == "floor:DP-4"


def test_furniture_lands_on_window_and_rides_along():
    w = world(Win("a", Rect(300, 600, 600, 300), 1, False, False))
    f = standing(w, "bowl", 500, 300)
    assert f.position("bowl", w) == (500, 600)
    moved = world(Win("a", Rect(400, 650, 600, 300), 1, False, False))
    settle(f, moved, DT)
    assert f.position("bowl", moved) == (600, 650)


def test_furniture_falls_when_window_closes():
    w = world(Win("a", Rect(300, 600, 600, 300), 1, False, False))
    f = standing(w, "tree", 500, 300)
    assert f.platform("tree").owner == "a"
    settle(f, world())
    assert f.position("tree", world()) == (500, 1080)


def test_held_furniture_is_dropped_not_thrown():
    w = world()
    f = standing(w, "bed", 500)
    f.put("bed", w, 800, 300, HALF)
    assert f.bodies["bed"].held and f.usable("bed", w) is None
    f.release("bed", 2000, -500)
    settle(f, w)
    assert f.position("bed", w) == (800, 1080)


def test_place_falls_back_to_free_output():
    w = world(blocked=["DP-4"])
    f = Furniture()
    assert f.place("bed", w, 2500, 500, HALF)
    settle(f, w)
    assert f.platform("bed").owner == "floor:DP-3"


def test_hidden_on_fullscreen_but_position_kept():
    w = world(Win("v", Rect(0, 0, 1920, 1080), 1, True, False))
    f = standing(world(), "bed", 500)
    assert f.position("bed", w) is not None
    assert f.visible("bed", w) is None
    assert f.usable("bed", w) is None


def test_unusable_on_blocked_output():
    f = standing(world(), "bed", 2500)
    assert f.usable("bed", world(blocked=["DP-4"])) is None


def test_fill_needs_usable_bowl():
    w = world()
    f = Furniture()
    assert not f.fill(w)
    standing(w, "bowl", 500, f=f)
    for _ in range(BOWL_PORTIONS + 2):
        assert f.fill(w)
    assert f.food == BOWL_PORTIONS
    f.store("bowl")
    assert not f.fill(w)


def test_eat_takes_one_portion():
    f = Furniture()
    assert not f.eat()
    f.food = 2
    assert f.eat() and f.food == 1


def test_roundtrip(tmp_path):
    w = world()
    f = standing(w, "bed", 2500)
    f.food = 2
    path = tmp_path / "furniture.json"
    storage.save(path, f)
    g = storage.load_furniture(path)
    settle(g, w)
    assert g.position("bed", w) == (2500, 1080)
    assert not g.placed("bowl")
    assert g.food == 2


def test_old_format_lands_on_its_monitor_floor():
    w = world()
    f = Furniture.from_dict({"bed": {"output": "DP-4", "offset": 300}, "bowl": {"output": None}})
    assert f.placed("bed") and not f.placed("bowl")
    assert f.to_dict()["bed"] == {"output": "DP-4", "offset": 300}   # vor dem ersten Tick unverändert
    settle(f, w)
    assert f.position("bed", w) == (2220, 1080)


def test_from_dict_ignores_garbage():
    f = Furniture.from_dict({"bed": "x", "bowl": {"output": "DP-3", "offset": "nope"},
                             "tree": {"x": "?"}, "food": 99})
    assert not any(f.placed(k) for k in f.bodies)
    assert f.food == BOWL_PORTIONS


# --- Katze und Napf ---

def bowl_at(w, x, food=1, y=500):
    f = standing(w, "bowl", x, y)
    f.food = food
    return f


def test_hungry_cat_walks_to_bowl_and_eats():
    w = world()
    c = cat_with(w, bowl_at(w, 1400), satiety=30)
    assert run(c, w, 30, until=lambda c: c.state == "eat")
    assert c.x == 1400 - BOWL_REACH * SPRITE / 32
    assert c.facing == 1
    assert c.furniture.food == 0
    assert c.needs.satiety > 60


def test_bowl_reached_from_the_other_side():
    w = world()
    c = cat_with(w, bowl_at(w, 500), x=900, satiety=30)
    assert run(c, w, 30, until=lambda c: c.state == "eat")
    assert c.x == 500 + BOWL_REACH * SPRITE / 32
    assert c.facing == -1


def test_full_cat_ignores_bowl():
    w = world()
    c = cat_with(w, bowl_at(w, 1400), satiety=90)
    run(c, w, 30)
    assert c.furniture.food == 1


def test_empty_bowl_is_ignored():
    w = world()
    c = cat_with(w, bowl_at(w, 1400, food=0), satiety=30)
    assert not run(c, w, 30, until=lambda c: c.state == "seek")


def test_bowl_on_neighbor_monitor_reached_over_floor():
    w = world()
    c = cat_with(w, bowl_at(w, 2300), x=1700, satiety=30)
    assert run(c, w, 60, until=lambda c: c.state == "eat")
    assert c.platform.owner == "floor:DP-4"


def test_bowl_on_blocked_monitor_is_ignored():
    w = world()
    f = bowl_at(w, 2300)
    blocked = world(blocked=["DP-4"])
    c = cat_with(blocked, f, x=1700, satiety=30)
    assert not run(c, blocked, 30, until=lambda c: c.state == "seek")


def test_hungry_cat_jumps_down_from_window_to_bowl():
    w = world(Win("a", Rect(600, 500, 800, 400), 1, False, False))
    c = cat_with(w, bowl_at(w, 1600), satiety=30)
    c.x, c.y, c.state, c.platform = 1000, 498, "fall", None
    c.tick(DT, w, False)
    assert c.platform.owner == "a"
    assert run(c, w, 30, until=lambda c: c.state == "eat")
    assert c.platform.is_floor


def test_bowl_stored_on_the_way():
    w = world()
    c = cat_with(w, bowl_at(w, 1800), satiety=30)
    assert run(c, w, 30, until=lambda c: c.state == "seek")
    c.furniture.store("bowl")
    c.tick(DT, w, False)
    assert c.state != "seek"


def test_sick_cat_gets_up_for_food():
    w = world()
    c = cat_with(w, bowl_at(w, 1400), satiety=5, affection=5)
    c.needs.mood = Mood.SICK
    run(c, w, 1)
    assert c.state in ("sick_lie", "seek")
    assert run(c, w, 30, until=lambda c: c.state == "eat")


# --- Katze und Bett ---

def bed_at(w, x, y=500):
    return standing(w, "bed", x, y)


def test_tired_cat_sleeps_in_bed():
    w = world()
    c = cat_with(w, bed_at(w, 1500), energy=10)
    assert run(c, w, 30, until=lambda c: c.state == "sleep")
    assert c.x == 1500
    assert c.in_bed


def test_tired_cat_without_bed_sleeps_where_she_is():
    w = world()
    c = cat_with(w, energy=10)
    assert run(c, w, 30, until=lambda c: c.state == "sleep")
    assert not c.in_bed


def test_go_sleep_goes_to_bed():
    w = world()
    c = cat_with(w, bed_at(w, 1500), energy=50)
    c.tick(DT, w, False)
    c.go_sleep()
    assert c.state == "seek"
    assert run(c, w, 30, until=lambda c: c.state == "sleep")
    assert c.in_bed


def test_bed_stored_on_the_way_sleeps_on_the_spot():
    w = world()
    c = cat_with(w, bed_at(w, 1800), energy=50)
    c.tick(DT, w, False)
    c.go_sleep()
    run(c, w, 1)
    c.furniture.store("bed")
    c.tick(DT, w, False)
    assert c.state == "sleep"
    assert not c.in_bed


def test_bed_moved_away_while_sleeping():
    w = world()
    c = cat_with(w, bed_at(w, 1500), energy=10)
    assert run(c, w, 30, until=lambda c: c.in_bed)
    c.furniture.put("bed", w, 400, 500, HALF)
    c.tick(DT, w, False)
    assert c.state == "sleep"
    assert not c.in_bed


def test_drag_out_of_bed():
    w = world()
    c = cat_with(w, bed_at(w, 1500), energy=10)
    assert run(c, w, 30, until=lambda c: c.in_bed)
    c.start_drag()
    assert not c.in_bed


# --- Wollknäuel ---

def yarn_at(w, x, y=1000):
    return standing(w, "yarn", x, y)


def test_placed_yarn_falls_to_floor():
    w = world()
    f = yarn_at(w, 500, 300)
    assert f.position("yarn", w) == (500, 1080)
    assert f.yarn.platform.is_floor


def test_yarn_lands_on_window():
    w = world(Win("a", Rect(300, 600, 600, 300), 1, False, False))
    f = yarn_at(w, 500, 300)
    assert f.yarn.platform.owner == "a"
    assert f.position("yarn", w) == (500, 600)


def test_yarn_rides_and_falls_with_window():
    w = world(Win("a", Rect(300, 600, 600, 300), 1, False, False))
    f = yarn_at(w, 500, 300)
    moved = world(Win("a", Rect(400, 600, 600, 300), 1, False, False))
    settle(f, moved, DT)
    assert f.position("yarn", moved) == (600, 600)
    settle(f, world())
    assert f.yarn.platform.is_floor


def test_kicked_yarn_rolls_and_stops():
    w = world()
    f = yarn_at(w, 500)
    f.kick(300)
    settle(f, w)
    x = f.position("yarn", w)[0]
    assert 600 < x < 800
    assert f.yarn.vx == 0


def test_yarn_rolls_over_monitor_border():
    w = world()
    f = yarn_at(w, 1800)
    f.kick(400)
    settle(f, w)
    assert f.yarn.platform.owner == "floor:DP-4"


def test_yarn_bounces_at_outer_edge():
    w = world()
    f = yarn_at(w, 3800)
    f.kick(400)
    settle(f, w)
    assert f.position("yarn", w)[0] <= 3840 - HALF


def test_yarn_rolls_off_window_edge():
    w = world(Win("a", Rect(300, 600, 600, 300), 1, False, False))
    f = yarn_at(w, 850, 300)
    f.kick(300)
    settle(f, w)
    assert f.yarn.platform.is_floor
    assert f.position("yarn", w)[0] > 900


def test_thrown_yarn_flies_and_lands():
    w = world()
    f = yarn_at(w, 500)
    f.put("yarn", w, 600, 500, HALF)
    assert f.yarn.held and f.usable("yarn", w) is None
    f.release("yarn", 800, -600)
    settle(f, w, 5)
    assert f.yarn.resting
    assert f.position("yarn", w)[0] > 900


def test_thrown_yarn_bounces():
    w = world()
    f = yarn_at(w, 500)
    f.put("yarn", w, 500, 200, HALF)
    f.release("yarn", 0, 0)
    ups = 0
    for _ in range(int(3 / DT)):
        before = f.yarn.vy
        f.tick(w, DT, SPRITE)
        ups += before > 0 > f.yarn.vy
    assert ups >= 1
    assert f.yarn.resting


def test_yarn_roundtrip_drops_on_load(tmp_path):
    w = world()
    f = yarn_at(w, 500)
    path = tmp_path / "f.json"
    storage.save(path, f)
    g = storage.load_furniture(path)
    assert g.placed("yarn") and not g.yarn.resting
    settle(g, w)
    assert g.position("yarn", w) == (500, 1080)


def test_lost_yarn_comes_back():
    w = world()
    f = Furniture()
    f.yarn.drop(99999, 500)
    f.tick(w, DT, SPRITE)
    settle(f, w)
    assert f.yarn.resting and f.position("yarn", w)[1] == 1080


def play_cfg(p):
    from taskbar_cat.config import Config
    cfg = Config()
    cfg.set("p_yarn", p)
    return cfg


def test_cat_plays_with_yarn():
    w = world()
    c = cat_with(w, yarn_at(w, 1300), affection=50)
    c.cfg = play_cfg(1)
    start = c.furniture.position("yarn", w)[0]
    assert run(c, w, 30, until=lambda c: c.state == "bat")
    assert c.furniture.yarn.vx != 0
    run(c, w, 30)
    assert c.needs.affection > 50 - 1   # Stupser gleichen den Verfall mehr als aus
    assert c.furniture.position("yarn", w)[0] != start


def test_cat_bats_several_times_then_stops():
    w = world()
    c = cat_with(w, yarn_at(w, 1300))
    c.cfg = play_cfg(1)
    bats = 0
    for _ in range(int(60 / DT)):
        was = c.state
        c.tick(DT, w, False)
        if c.state == "bat" and was != "bat":
            bats += 1
        if bats and c.state not in ("bat", "seek"):
            break
    assert 3 <= bats <= 6


def test_cat_jumps_onto_window_for_yarn():
    w = world(Win("a", Rect(700, 800, 600, 300), 1, False, False))
    c = cat_with(w, yarn_at(w, 1000, 300), x=500)
    c.cfg = play_cfg(1)
    assert c.furniture.yarn.platform.owner == "a"
    assert run(c, w, 30, until=lambda c: c.state == "bat")
    assert c.platform.owner == "a"


def test_cat_jumps_down_for_yarn():
    w = world(Win("a", Rect(700, 800, 600, 300), 1, False, False))
    c = cat_with(w, yarn_at(w, 1500), x=1000)
    c.x, c.y, c.state, c.platform = 1000, 798, "fall", None
    c.tick(DT, w, False)
    assert c.platform.owner == "a"
    c.cfg = play_cfg(1)
    assert run(c, w, 30, until=lambda c: c.state == "bat")
    assert c.platform.is_floor


def test_cat_waits_while_yarn_flies():
    w = world()
    c = cat_with(w, yarn_at(w, 1300))
    c.cfg = play_cfg(1)
    assert run(c, w, 30, until=lambda c: c.state == "seek")
    c.furniture.put("yarn", w, 1300, 300, HALF)   # Maus hält es fest
    run(c, w, 1)
    assert c.state == "seek" and c.frame_key(0)[0] == "sit"
    c.furniture.release("yarn", 0, 0)
    assert run(c, w, 30, until=lambda c: c.state == "bat")


def test_no_yarn_play_when_disabled():
    w = world()
    c = cat_with(w, yarn_at(w, 1300))
    c.cfg = play_cfg(0)
    assert not run(c, w, 60, until=lambda c: c.state == "bat")


def test_yarn_in_inventory_changes_nothing():
    """Ohne Knäuel wird nicht gewürfelt: das übrige Verhalten bleibt gleich."""
    w = world()
    a, b = cat_with(w), cat_with(w, Furniture())
    a.cfg, b.cfg = play_cfg(0), play_cfg(1)
    for _ in range(int(60 / DT)):
        a.tick(DT, w, False)
        b.tick(DT, w, False)
        assert (a.state, a.x) == (b.state, b.x)


# --- Kratzbaum ---

def tree_at(w, x, y=500):
    return standing(w, "tree", x, y)


def tree_cfg(p):
    from taskbar_cat.config import Config
    cfg = Config()
    cfg.set("p_tree", p)
    return cfg


def test_tree_deck_becomes_platform():
    w = world()
    f = tree_at(w, 1000)
    tw = f.world_with(w, SPRITE)
    deck = [p for p in tw.platforms if p.owner == "furniture:tree"]
    assert len(deck) == 1
    s = SPRITE / 32
    assert deck[0].y == 1080 - (64 - 8) * s
    assert deck[0].x1 < 1000 < deck[0].x2
    assert any(c.owner == "furniture:tree" for c in tw.ceilings)   # zum Hängen


def test_world_unchanged_without_tree():
    w = world()
    assert Furniture().world_with(w, SPRITE) is w


def test_tree_world_is_cached():
    w = world()
    f = tree_at(w, 1000)
    assert f.world_with(w, SPRITE) is f.world_with(w, SPRITE)
    f.put("tree", w, 1200, 500, HALF)
    assert f.world_with(w, SPRITE) is w   # in der Hand: keine Liegefläche
    f.release("tree", 0, 0)
    settle(f, w)
    assert [p for p in f.world_with(w, SPRITE).platforms if p.owner == "furniture:tree"][0].x1 > 1000


def tree_run(c, f, w, seconds, until=None):
    for _ in range(int(seconds / DT)):
        c.tick(DT, f.world_with(w, SPRITE), False)
        if until is not None and until(c):
            return True
    return False


def test_cat_scratches_or_climbs_tree():
    seen = set()
    for seed in range(6):     # je Besuch gewürfelt: notfalls ein paar Katzen mehr
        if seen == {"scratch", "deck"}:
            break
        w = world()
        f = tree_at(w, 1300)
        c = cat_with(w, f)
        c.rng = random.Random(seed)
        c.cfg = tree_cfg(1)
        scratches_or_climbs(c, f, w, seen)
    assert seen == {"scratch", "deck"}


def scratches_or_climbs(c, f, w, seen):
    for _ in range(int(120 / DT)):
        c.tick(DT, f.world_with(w, SPRITE), False)
        if c.state == "scratch":
            seen.add("scratch")
            assert abs(abs(c.x - 1300) - BOWL_REACH * SPRITE / 32) < 1e-6
            assert c.facing == (1 if c.x < 1300 else -1)
        if c.platform is not None and c.platform.owner == "furniture:tree":
            seen.add("deck")


def test_cat_rides_tree_and_falls_when_stored():
    w = world()
    f = tree_at(w, 1300)
    c = cat_with(w, f)
    c.cfg = tree_cfg(1)
    assert tree_run(c, f, w, 120, until=lambda c: c.platform is not None
                    and c.platform.owner == "furniture:tree" and c.state not in ("jump", "fall"))
    c.cfg = tree_cfg(0)
    f.store("tree")
    assert tree_run(c, f, w, 5, until=lambda c: c.platform is not None and c.platform.is_floor)


def test_yarn_lands_on_tree():
    w = world()
    f = tree_at(w, 1000)
    f.place("yarn", w, 1000, 300, HALF)
    for _ in range(int(3 / DT)):
        f.tick(f.world_with(w, SPRITE), DT, SPRITE)
    assert f.yarn.platform.owner == "furniture:tree"


def test_no_tree_visits_when_disabled():
    w = world()
    f = tree_at(w, 1300)
    c = cat_with(w, f)
    c.cfg = tree_cfg(0)
    assert not tree_run(c, f, w, 60, until=lambda c: c.state == "scratch")



def test_cat_rides_tree_standing_on_moving_window():
    w = world(Win("a", Rect(1000, 700, 800, 380), 1, False, False))
    f = tree_at(w, 1300, 300)
    assert f.platform("tree").owner == "a"
    c = cat_with(w, f)
    c.cfg = tree_cfg(1)
    assert tree_run(c, f, w, 120, until=lambda c: c.platform is not None
                    and c.platform.owner == "furniture:tree" and c.state not in ("jump", "fall"))
    c._set("idle_sit", 100)   # still sitzen, damit nur das Mitfahren zählt
    x = c.x
    moved = world(Win("a", Rect(1100, 700, 800, 380), 1, False, False))
    tree_run(c, f, moved, 0.2)
    assert f.position("tree", moved)[0] == 1400
    assert c.platform.owner == "furniture:tree"
    assert abs(c.x - (x + 100)) < 1e-6


def test_cat_sleeps_in_bed_on_window():
    w = world(Win("a", Rect(1000, 800, 800, 280), 1, False, False))
    f = bed_at(w, 1300, 300)
    assert f.platform("bed").owner == "a"
    c = cat_with(w, f, energy=10)
    assert run(c, w, 30, until=lambda c: c.in_bed)
    assert c.platform.owner == "a"


def test_cat_waits_while_bowl_falls():
    w = world(Win("a", Rect(1000, 600, 800, 300), 1, False, False))
    f = bowl_at(w, 1300, y=300)
    c = cat_with(w, f, satiety=30)
    assert run(c, w, 30, until=lambda c: c.state == "seek")
    run(c, world(), DT)   # Fenster weg: der Napf fällt
    assert c.state == "seek" and c.frame_key(0)[0] == "sit"
    assert run(c, world(), 30, until=lambda c: c.state == "eat")


# --- Napf herunterschubsen ---

def bowl_at_edge(food=2):
    """Napf auf einem Fenster, nah an dessen rechter Kante; die Katze daneben."""
    w = world(Win("a", Rect(600, 600, 400, 300), 1, False, False))
    f = standing(w, "bowl", 1000 - SPRITE * 0.6, 500)
    f.food = food
    c = cat_with(w, f, x=760, satiety=100, energy=100, affection=100)
    c.x, c.y = 760, 600
    c._land(w, next(p for p in w.platforms if p.owner == "a"))
    return w, f, c


def test_cat_pushes_the_bowl_off_the_edge_and_it_lands_upside_down():
    w, f, c = bowl_at_edge()
    assert c._bowl_edge(w) == 1
    assert c._seek_push(1, w, fresh=True)
    assert run(c, w, 30, until=lambda c: f.tipped)
    b = f.bodies["bowl"]
    assert b.platform.is_floor and b.x > 1000                    # heruntergefallen
    assert (f.food, f.spill, f.spill_side) == (0, 2, 1)          # Futter liegt daneben
    assert f.usable("bowl", w) is None and not f.fill(w)          # taugt so nicht
    run(c, w, 20)
    assert f.tipped and f.bodies["bowl"].x == b.x                 # bleibt so liegen


def test_nudges_until_it_falls():
    shoves = []
    for seed in range(6):
        w, f, c = bowl_at_edge()
        c.rng = random.Random(seed)
        c._seek_push(1, w, fresh=True)
        n, was = 0, None
        for _ in range(int(30 / DT)):
            c.tick(DT, w, False)
            if c.state == "nudge" and was != "nudge":
                n += 1
            was = c.state
            if f.tipped:
                break
        assert f.tipped
        shoves.append(n)
    assert set(shoves) <= {1, 2, 3} and len(set(shoves)) > 1


def test_picking_it_up_rights_it_and_clears_the_mess():
    w, f, c = bowl_at_edge()
    c._seek_push(1, w, fresh=True)
    run(c, w, 30, until=lambda c: f.tipped)
    f.put("bowl", w, 500, 300, HALF)
    f.release("bowl", 0, 0)
    settle(f, w)
    assert not f.tipped and f.spill == 0 and f.usable("bowl", w) is not None
    assert f.fill(w) and f.food == 1


def test_bowl_in_the_middle_or_on_the_floor_stays():
    w = world(Win("a", Rect(600, 600, 400, 300), 1, False, False))
    f = standing(w, "bowl", 800, 500)
    c = cat_with(w, f)
    assert c._bowl_edge(w) == 0
    f2 = standing(w, "bowl", 300, 500)
    assert cat_with(w, f2)._bowl_edge(w) == 0


def test_tipped_bowl_is_saved():
    w, f, c = bowl_at_edge(food=3)
    c._seek_push(1, w, fresh=True)
    run(c, w, 30, until=lambda c: f.tipped)
    g = Furniture.from_dict(f.to_dict())
    assert (g.tipped, g.spill, g.spill_side) == (True, 3, 1)
    assert not Furniture.from_dict({}).tipped


def test_cat_pushes_it_now_and_then_on_her_own():
    pushed = 0
    for seed in range(6):
        w, f, c = bowl_at_edge()
        c.rng = random.Random(seed)
        pushed += run(c, w, 120, until=lambda c: f.tipped)
    assert pushed >= 2
