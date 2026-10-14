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

def test_starts_in_inventory():
    f = Furniture()
    assert not any(it.placed for it in f.items.values())
    assert f.position("bed", world()) is None


def test_put_on_floor_of_output_under_point():
    w = world()
    f = Furniture()
    assert f.put("bed", w, 2500, 500, HALF)
    assert f.items["bed"].output == "DP-4"
    assert f.position("bed", w) == (2500, 1080)


def test_put_keeps_inside_work_area():
    w = world()
    f = Furniture()
    f.put("bowl", w, 1919, 500, HALF)
    assert f.position("bowl", w) == (1920 - HALF, 1080)


def test_put_refuses_blocked_output():
    w = world(blocked=["DP-4"])
    f = Furniture()
    assert not f.put("bed", w, 2500, 500, HALF)
    assert not f.items["bed"].placed


def test_place_falls_back_to_free_output():
    w = world(blocked=["DP-4"])
    f = Furniture()
    assert f.place("bed", w, 2500, 500, HALF)
    assert f.items["bed"].output == "DP-3"


def test_hidden_on_fullscreen_but_position_kept():
    w = world(Win("v", Rect(0, 0, 1920, 1080), 1, True, False))
    f = Furniture()
    f.put("bed", world(), 500, 500, HALF)
    assert f.position("bed", w) is not None
    assert f.visible("bed", w) is None
    assert f.usable("bed", w) is None


def test_missing_output_makes_it_unusable():
    f = Furniture()
    f.put("bed", world(), 2500, 500, HALF)
    one = World([Output("DP-3", Rect(0, 0, 1920, 1080), Rect(0, 44, 1920, 1036))], [])
    assert f.usable("bed", one) is None
    assert f.items["bed"].placed


def test_fill_needs_usable_bowl():
    w = world()
    f = Furniture()
    assert not f.fill(w)
    f.put("bowl", w, 500, 500, HALF)
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
    f = Furniture()
    f.put("bed", w, 2500, 500, HALF)
    f.food = 2
    path = tmp_path / "furniture.json"
    storage.save(path, f)
    g = storage.load_furniture(path)
    assert g.position("bed", w) == (2500, 1080)
    assert not g.items["bowl"].placed
    assert g.food == 2


def test_from_dict_ignores_garbage():
    f = Furniture.from_dict({"bed": "x", "bowl": {"output": "DP-3", "offset": "nope"}, "food": 99})
    assert not f.items["bed"].placed
    assert not f.items["bowl"].placed
    assert f.food == BOWL_PORTIONS


# --- Katze und Napf ---

def bowl_at(w, x, food=1):
    f = Furniture()
    f.put("bowl", w, x, 500, HALF)
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

def bed_at(w, x):
    f = Furniture()
    f.put("bed", w, x, 500, HALF)
    return f


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

def settle(f, w, seconds=3):
    for _ in range(int(seconds / DT)):
        f.tick(w, DT, SPRITE)


def yarn_at(w, x, y=1000):
    f = Furniture()
    f.place("yarn", w, x, y, HALF)
    settle(f, w)
    assert f.yarn.resting
    return f


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

def tree_at(w, x):
    f = Furniture()
    f.put("tree", w, x, 500, HALF)
    return f


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
    assert [p for p in f.world_with(w, SPRITE).platforms if p.owner == "furniture:tree"][0].x1 > 1000


def tree_run(c, f, w, seconds, until=None):
    for _ in range(int(seconds / DT)):
        c.tick(DT, f.world_with(w, SPRITE), False)
        if until is not None and until(c):
            return True
    return False


def test_cat_scratches_or_climbs_tree():
    w = world()
    f = tree_at(w, 1300)
    c = cat_with(w, f)
    c.cfg = tree_cfg(1)
    seen = set()
    for _ in range(int(120 / DT)):
        c.tick(DT, f.world_with(w, SPRITE), False)
        if c.state == "scratch":
            seen.add("scratch")
            assert abs(abs(c.x - 1300) - BOWL_REACH * SPRITE / 32) < 1e-6
            assert c.facing == (1 if c.x < 1300 else -1)
        if c.platform is not None and c.platform.owner == "furniture:tree":
            seen.add("deck")
    assert seen == {"scratch", "deck"}


def test_cat_rides_tree_and_falls_when_stored():
    w = world()
    f = tree_at(w, 1300)
    c = cat_with(w, f)
    c.cfg = tree_cfg(1)
    assert tree_run(c, f, w, 120, until=lambda c: c.platform is not None
                    and c.platform.owner == "furniture:tree" and c.state not in ("jump", "fall"))
    c._set("idle_sit", 100)   # still sitzen, damit nur das Mitfahren zählt
    x = c.x
    f.put("tree", w, 1400, 500, HALF)
    tree_run(c, f, w, DT)
    assert c.platform.owner == "furniture:tree"
    assert abs(c.x - (x + 100)) < 1e-6
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

