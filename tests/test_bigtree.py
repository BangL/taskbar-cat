import json
import random

import pytest

from taskbar_cat import bigtree, sprites, storage
from taskbar_cat.bigtree import BOARD_ID, KIND, Tree, layout
from taskbar_cat import cat as cat_mod
from taskbar_cat.cat import SPRITE, Cat
from taskbar_cat.config import Config
from taskbar_cat.furniture import TREE_ID, Furniture
from taskbar_cat.needs import Needs
from PyQt6.QtCore import Qt

from test_furniture import DT, HALF, settle, world

S = SPRITE / 32
SIZES = [(w, h) for w in range(24, 129, 9) for h in range(40, 401, 23)]


# --- Aufbau ---

def test_layout_is_fixed_per_size_and_seed():
    assert layout(81, 180) == layout(81.3, 179.8)          # gerundet gleich
    assert layout(81, 180) != layout(82, 180)              # jede Größe würfelt neu
    assert layout(81, 180, seed=1) != layout(81, 180, seed=2)
    assert layout(81, 180) != layout(81, 180, hanging=True)


def test_size_is_clamped():
    lay = layout(1, 9999)
    assert (lay.w, lay.h) == (bigtree.MIN_W, bigtree.MAX_H)


@pytest.mark.parametrize("hanging", [False, True])
def test_every_post_ends_in_a_lounge_and_one_reaches_all_the_way(hanging):
    for w, h in SIZES:
        lay = layout(w, h, hanging)
        ends = [y2 if hanging else y1 for _, y1, y2 in lay.posts]
        tops = [b for b in lay.boards if b.style == "top"]
        assert (max(ends) if hanging else min(ends)) == (h - 1 - bigtree.BOARD_H if hanging else 3)
        for i, e in enumerate(ends):
            assert any(b.y == e and any(p == i for p, _ in b.posts) for b in tops), (w, h, i)


def test_neighbours_sometimes_share_one_lounge():
    shared = [any(b.style == "top" and "-" in b.key for b in layout(w, h).boards)
              for w, h in SIZES if len(layout(w, h).posts) > 1]
    assert 0.2 < sum(shared) / len(shared) < 0.6


@pytest.mark.parametrize("hanging", [False, True])
def test_boards_keep_their_distance(hanging):
    for w, h in SIZES:
        bs = layout(w, h, hanging).boards
        for i, a in enumerate(bs):
            for b in bs[i + 1:]:
                if a.x2 >= b.x1 and b.x2 >= a.x1:
                    assert abs(a.y - b.y) >= bigtree.MIN_DY, (w, h, a, b)


@pytest.mark.parametrize("hanging", [False, True])
def test_toys_hang_free(hanging):
    """Kein Faden durch ein Brett, kein Bällchen vor einem Pfeiler oder im Boden."""
    for w, h in SIZES:
        lay = layout(w, h, hanging)
        for x, y, n, _ in lay.toys:
            bottom = y + n + 3
            assert all(abs(x - px) > bigtree.POST_W // 2 for px, _, _ in lay.posts), (w, h, x)
            assert bottom <= (h - 1 if hanging else lay.base_y), (w, h)
            for b in lay.boards:
                top = b.y - (b.sag + 1 if b.style == "hammock" else 2 if b.style == "top" else 0)
                assert not (b.x1 - 1 <= x <= b.x2 + 1 and y < top <= bottom), (w, h, x, y, b)


def test_bigger_trees_get_more_posts_and_levels():
    small, big = layout(30, 60), layout(128, 400)
    assert len(small.posts) == 1 and len(big.posts) >= 3
    assert len(big.boards) > len(small.boards)


def test_hanging_tree_hangs_from_a_plate_at_the_top():
    lay = layout(81, 180, hanging=True)
    assert lay.base_y == 0
    assert all(y1 == bigtree.BASE_H for _, y1, _ in lay.posts)


# --- Zustand und Speichern ---

def test_tree_roundtrip_and_variant():
    t = Tree(70.5, 150.25, seed=7, hanging=True, top=44)
    u = Tree.from_dict(json.loads(json.dumps(t.to_dict())))
    assert (u.w, u.h, u.seed, u.hanging, u.top) == (70.5, 150.25, 7, True, 44)
    v = t.variant("Lieblingsbaum")
    other = Tree()
    other.apply(v)
    assert other.layout() == Tree(70, 150, seed=7).layout()


def test_wheel_changes_height_or_width():
    t = Tree(48, 100)
    w, h = t.wheeled(0, 240)
    assert w == 48 and h > 110
    w, h = t.wheeled(-120, 0)
    assert w < 48 and h == 100


def test_variants_file(tmp_path):
    path = tmp_path / "v.json"
    good = Tree(50, 120, seed=3).variant("A")
    path.write_text(json.dumps({"favorites": [good, {"name": ""}, "kaputt", {"name": "B", "w": 1}]}))
    assert storage.load_variants(path) == [good]
    assert storage.save_variants(path, [good, Tree().variant("C")])
    assert [v["name"] for v in storage.load_variants(path)] == ["A", "C"]


def test_more_trees_and_removing():
    w = world()
    f = Furniture()
    assert f.add_tree(500, 300) == KIND                # erst der erste
    k2 = f.add_tree(900, 300, rng=random.Random(1))
    assert k2 == KIND + "2" and f.trees[k2].seed != 0
    settle(f, w)
    assert f.bodies[k2].resting and f.position(k2, w)[1] == 1080
    f.remove_tree(k2)
    assert k2 not in f.bodies and k2 not in f.trees
    f.remove_tree(KIND)
    assert not f.placed(KIND) and KIND in f.trees     # nur weggeräumt


def test_trees_are_saved():
    w = world()
    f = Furniture()
    f.add_tree(500, 300)
    k2 = f.add_tree(900, 300, rng=random.Random(1))
    f.resize_tree(k2, 70, 210)
    settle(f, w)
    g = Furniture.from_dict(json.loads(json.dumps(f.to_dict())))
    assert set(g.trees) == {KIND, k2}
    assert g.trees[k2].size() == (70, 210) and g.trees[k2].seed == f.trees[k2].seed
    settle(g, w)
    assert g.position(k2, w) == f.position(k2, w)


def test_variant_on_another_tree():
    f = Furniture()
    a = f.add_tree(500, 300)
    b = f.add_tree(900, 300, rng=random.Random(1))
    f.resize_tree(a, 90, 230)
    f.apply_variant(b, f.trees[a].variant("x"))
    assert f.trees[b].layout() == f.trees[a].layout()


# --- hängend ---

def hang_at_top(f, w, kind=KIND):
    f.world_with(w, SPRITE)
    h = f.trees[kind].size()[1] * S
    f.put(kind, w, 1000, 44 + h + 10, 0)               # Oberkante 10 px unter dem Rand
    assert f.trees[kind].hanging                       # Vorschau schon beim Ziehen
    f.release(kind, 0, 0)


def test_dragged_to_the_top_it_hangs_there():
    w = world()
    f = Furniture()
    f.add_tree(1000, 500)
    hang_at_top(f, w)
    settle(f, w)
    t, b = f.trees[KIND], f.bodies[KIND]
    assert t.hanging and t.top == 44 and b.y - t.size()[1] * S == 44
    assert f.usable(KIND, w) is not None
    f.resize_tree(KIND, 60, 160)
    f.world_with(w, SPRITE)
    assert b.y - 160 * S == 44                         # Oberkante bleibt, unten wandert


def test_hanging_survives_saving():
    w = world()
    f = Furniture()
    f.add_tree(1000, 500)
    hang_at_top(f, w)
    g = Furniture.from_dict(json.loads(json.dumps(f.to_dict())))
    g.world_with(w, SPRITE)
    settle(g, w)
    assert g.trees[KIND].hanging and g.bodies[KIND].y == f.bodies[KIND].y


def test_dragged_down_again_it_falls():
    w = world()
    f = Furniture()
    f.add_tree(1000, 500)
    hang_at_top(f, w)
    f.put(KIND, w, 1000, 800, 0)
    assert not f.trees[KIND].hanging
    f.release(KIND, 0, 0)
    settle(f, w)
    assert f.bodies[KIND].y == 1080


# --- Welt ---

def tree_world(w=None, size=(81, 180), x=1000, hanging=False):
    w = w or world()
    f = Furniture()
    f.trees[KIND] = Tree(*size)
    f.add_tree(x, 500)
    if hanging:
        hang_at_top(f, w)
    settle(f, w)
    return w, f


def test_every_board_is_a_walkable_edge():
    w, f = tree_world()
    ww = f.world_with(w, SPRITE)
    owners = {p.owner for p in ww.platforms if p.owner.startswith(BOARD_ID)}
    assert owners == {f"{BOARD_ID}{KIND}:{b.key}" for b in f.trees[KIND].layout().boards} | \
        {f"{BOARD_ID}{KIND}:{bigtree.BASE_KEY}"}


def test_the_base_is_walkable_but_not_when_hanging():
    w, f = tree_world()
    base = next(p for p in f.world_with(w, SPRITE).platforms if p.owner.endswith(":" + bigtree.BASE_KEY))
    assert base.y == pytest.approx(1080 - (bigtree.BASE_H + 1) * S) and base.x2 - base.x1 > 40 * S
    w, f = tree_world(hanging=True)
    assert not any(p.owner.endswith(":" + bigtree.BASE_KEY) for p in f.world_with(w, SPRITE).platforms)


def test_posts_are_walls_up_to_their_boards():
    w, f = tree_world()
    ww = f.world_with(w, SPRITE)
    walls = [wl for wl in ww.walls if wl.owner.startswith(BOARD_ID)]
    assert walls
    for wl in walls:
        assert wl.y2 == pytest.approx(1080 - (bigtree.BASE_H + 1) * S)   # Fuß auf dem Sockel
        assert any(p.owner == wl.owner and abs(p.y - wl.y1) < 1e-6 for p in ww.platforms)


def test_tree_does_not_land_on_its_own_boards():
    w, f = tree_world()
    for _ in range(30):
        f.tick(f.world_with(w, SPRITE), DT, SPRITE)
    assert f.bodies[KIND].y == 1080


def test_yarn_can_land_on_a_board():
    w, f = tree_world(size=(48, 100))
    top = next(b for b in f.trees[KIND].layout().boards if b.key.startswith("top"))
    left = 1000 - 24 * S
    f.place("yarn", w, left + (top.x1 + top.x2) / 2 * S, 100, 0)
    for _ in range(120):
        f.tick(f.world_with(w, SPRITE), DT, SPRITE)
    assert f.bodies["yarn"].platform.owner.startswith(BOARD_ID)


# --- Katze ---

def cat_near(f, w, x=800, seed=0, **needs):
    c = Cat(Needs(**{"satiety": 100, "energy": 100, "affection": 100, **needs}), random.Random(seed))
    c.furniture = f
    c.spawn(w)
    c.x = x
    cfg = Config()
    cfg.set("p_tree", 1)
    c.cfg = cfg
    return c


def test_cat_climbs_posts_and_uses_the_boards():
    w, f = tree_world()
    seen, anims, boards = set(), set(), set()
    for seed in range(8):     # die Höhle kostet Zeit, also notfalls ein paar Katzen mehr
        if {"climb", "scratch"} <= seen and "climb_post" in anims and len(boards) >= 3:
            break
        c = cat_near(f, w, seed=seed)
        for i in range(int(180 / DT)):
            c.tick(DT, f.world_with(w, SPRITE), False)
            seen.add(c.state)
            anims.add(c.frame_key(i * DT)[0])
            if c.platform is not None and c.platform.owner.startswith(BOARD_ID):
                boards.add(c.platform.owner)
    assert {"climb", "scratch"} <= seen
    assert "climb_post" in anims
    assert len(boards) >= 3


def test_cat_reaches_a_hanging_tree():
    w, f = tree_world(hanging=True)
    c = cat_near(f, w)
    for _ in range(int(240 / DT)):
        c.tick(DT, f.world_with(w, SPRITE), False)
        if c.platform is not None and c.platform.owner.startswith(BOARD_ID):
            return
    pytest.fail("nie auf dem hängenden Baum")


def hammock_tree():
    """Baum mit Hängematte (gesucht, da der Aufbau zufällig ist)."""
    for w_, h_ in SIZES:
        if any(b.style == "hammock" for b in layout(w_, h_).boards):
            return tree_world(size=(w_, h_))
    raise AssertionError("kein Baum mit Hängematte")


def test_tired_cat_sleeps_swinging_in_the_hammock():
    w, f = hammock_tree()
    ww = f.world_with(w, SPRITE)
    hm = next(p for p in ww.platforms if bigtree.in_hammock(p.owner))
    c = cat_near(f, w, energy=40)
    c.x = (hm.x1 + hm.x2) / 2
    c._land(ww, hm)
    c._choose(ww)
    assert c.state == "sleep"
    keys = {c.frame_key(t / 10) for t in range(20)}
    assert {k[0] for k in keys} == {"hammock_sleep"} and len({k[2] % 4 for k in keys}) == 4


def test_rested_cat_lounges_in_the_hammock_for_a_while():
    w, f = hammock_tree()
    ww = f.world_with(w, SPRITE)
    hm = next(p for p in ww.platforms if bigtree.in_hammock(p.owner))
    lounged = 0
    for seed in range(10):
        c = cat_near(f, w, seed=seed)
        c.x = (hm.x1 + hm.x2) / 2
        c._land(ww, hm)
        c._choose(ww)
        lounged += c.state == "idle_sit" and c.frame_key(0)[0] == "hammock"
    assert lounged >= 3



def test_hammock_sags_under_the_cat():
    w, f = hammock_tree()
    ww = f.world_with(w, SPRITE)
    hm = next(p for p in ww.platforms if bigtree.in_hammock(p.owner))
    c = cat_near(f, w, energy=40)
    c.x = (hm.x1 + hm.x2) / 2
    c._land(ww, hm)
    c._choose(ww)
    kind, key = bigtree.hammock_of(c.hammock())
    assert kind in f.trees and any(b.key == key and b.style == "hammock" for b in f.trees[kind].layout().boards)
    assert [bigtree.load_sag(t) for t in (0, bigtree.LOAD_TIME / 2, 5)] == [0, bigtree.LOAD_SAG // 2,
                                                                            bigtree.LOAD_SAG]
    c._set("walk", 1)
    assert c.hammock() is None


def cave_tree():
    """Stehender Baum mit Höhle (gesucht, da der Aufbau zufällig ist)."""
    for w_, h_ in SIZES:
        if bigtree.cave_of(layout(w_, h_)) is not None:
            return tree_world(size=(w_, h_))
    raise AssertionError("kein Baum mit Höhle")


def run_until(c, f, w, states, seconds=30.0):
    for _ in range(int(seconds / DT)):
        c.tick(DT, f.world_with(w, SPRITE), False)
        if c.state in states:
            return True
    return False


def test_caves_fit_the_cat_and_hanging_trees_have_none():
    some = False
    for w_, h_ in SIZES:
        assert bigtree.cave_of(layout(w_, h_, True)) is None
        b = bigtree.cave_of(layout(w_, h_))
        if b is not None:
            some = True
            assert b.x2 - b.x1 >= bigtree.CAVE_MIN_W
    assert some


def test_sometimes_her_butt_sticks_out_instead():
    w, f = cave_tree()
    states = set()
    for seed in range(40):
        c = cat_near(f, w, seed=seed)
        c._seek_cave(KIND, "peek", f.world_with(w, SPRITE))
        assert run_until(c, f, w, ("cave", "cave_butt"))
        states.add(c.state)
        if c.state == "cave_butt":
            assert c.frame_key(0)[0] == "cave_butt" and c.behind() is None
            c.tick(DT, f.world_with(w, SPRITE), False, cursor=(c.x + 40, c.y - 20))
            assert c.state == "cave_butt"                    # sieht die Maus ja nicht
            assert run_until(c, f, w, ("cave_out",), 11)
    assert states == {"cave", "cave_butt"}


def test_cat_goes_into_the_cave_peeks_and_comes_out():
    w, f = cave_tree()
    c = cat_near(f, w)
    ww = f.world_with(w, SPRITE)
    door, _ = c._cave_door(ww, KIND)
    assert c._seek_cave(KIND, "peek", ww)
    assert run_until(c, f, w, ("cave_in",))
    assert c.x == pytest.approx(door) and c.behind() == (KIND, "cave") and c.opacity > 0.9
    assert run_until(c, f, w, ("cave",), 2)
    assert c.behind() is None and c.frame_key(0)[0] == "cave_peek"
    looks = set()
    for _ in range(int(5 / DT)):
        c.tick(DT, f.world_with(w, SPRITE), False)
        looks.add(c.facing)
    assert looks == {-1, 1}                                    # schaut sich um
    assert run_until(c, f, w, ("cave_out",), 30) and c.frame_key(0)[0] == "crawl"
    for _ in range(int(1 / DT)):
        c.tick(DT, f.world_with(w, SPRITE), False)
    assert c.state not in cat_mod.CAVE_STATES and c._cave is None


def test_mouse_at_the_door_makes_her_duck_or_jump_out():
    w, f = cave_tree()
    reactions = set()
    for seed in range(10):
        c = cat_near(f, w, seed=seed)
        ww = f.world_with(w, SPRITE)
        c._seek_cave(KIND, "peek", ww)
        assert run_until(c, f, w, ("cave", "cave_butt"))
        if c.state == "cave_butt":     # selten verkehrt herum, dann sieht sie die Maus nicht
            continue
        c.tick(DT, f.world_with(w, SPRITE), False, cursor=(c.x + 40, c.y - 20))
        reactions.add(c.state)
    assert reactions == {"cave_duck", "cave_out"}


def test_tired_cat_sleeps_in_the_cave():
    w, f = cave_tree()
    slept = 0
    for seed in range(10):
        c = cat_near(f, w, seed=seed, energy=10)
        c._choose(f.world_with(w, SPRITE))
        if c._cave_plan == "sleep" and run_until(c, f, w, ("cave_sleep",)):
            slept += 1
            assert c._activity() == "sleep" and c.frame_key(0)[0] == "cave_sleep"
            c.needs.energy = 85
            assert run_until(c, f, w, ("cave",), 1)
    assert slept >= 2


def test_tree_moved_away_she_leaves_the_cave():
    w, f = cave_tree()
    c = cat_near(f, w)
    c._seek_cave(KIND, "peek", f.world_with(w, SPRITE))
    assert run_until(c, f, w, ("cave", "cave_butt"))
    f.resize_tree(KIND, bigtree.MIN_W, bigtree.MIN_H)        # Höhle verschwindet
    c.tick(DT, f.world_with(w, SPRITE), False)
    assert c.state not in cat_mod.CAVE_STATES

def test_no_bigtree_no_extra_dice():
    """Ohne aufgestellten großen Kratzbaum bleibt das übrige Verhalten gleich."""
    w = world()
    a, b = cat_near(Furniture(), w), cat_near(Furniture(), w)
    b.cfg.set("p_tree", 0)
    for _ in range(int(60 / DT)):
        a.tick(DT, w, False)
        b.tick(DT, w, False)
        assert (a.state, a.x) == (b.state, b.x)


# --- Bilder und Oberfläche ---

def test_rendered_tree_matches_its_layout(qapp):
    from taskbar_cat import sprites
    for hanging in (False, True):
        img = sprites.render_bigtree(81, 180, hanging, 5)
        lay = layout(81, 180, hanging, 5)
        assert (img.width(), img.height()) == (lay.w, lay.h)
        for x, y1, y2 in lay.posts:
            assert img.pixelColor(x, (y1 + y2) // 2) == sprites.SISAL or \
                img.pixelColor(x, (y1 + y2) // 2) == sprites.SISAL_DARK



def test_loaded_hammock_hangs_lower(qapp):
    from taskbar_cat import sprites
    for (w_, h_) in SIZES:
        hm = next((b for b in layout(w_, h_).boards if b.style == "hammock"), None)
        if hm is not None:
            break
    x = (hm.x1 + hm.x2) // 2
    def bottom(img):
        return max(y for y in range(hm.y, img.height()) if img.pixelColor(x, y) == sprites.HAMMOCK)
    free = sprites.render_bigtree(w_, h_)
    loaded = sprites.render_bigtree(w_, h_, load=(hm.key, bigtree.LOAD_SAG))
    assert bottom(loaded) - bottom(free) >= bigtree.LOAD_SAG - 1
    lay = layout(w_, h_)
    assert bigtree.front_part(lay, hm.key, 0) is None
    fx, fy, fw, fh = bigtree.front_part(lay, hm.key, bigtree.LOAD_SAG)
    assert fx == hm.x1 and fy < hm.y <= fy + fh and fy + fh <= lay.h
    front = loaded.copy(fx, fy, fw, fh)     # die ganze Matte liegt im Ausschnitt
    assert bottom(loaded) - fy < front.height()

def test_collection_dialog(qapp, tmp_path):
    from taskbar_cat.ui.collection import CollectionDialog, rename
    path = tmp_path / "v.json"
    storage.save_variants(path, [Tree(48, 100, seed=1).variant("A"), Tree(90, 300, 2, True).variant("B")])
    dlg = CollectionDialog(path)
    assert not dlg.isModal()
    asked = []
    dlg.placeRequested.connect(asked.append)
    from PyQt6.QtWidgets import QPushButton
    place = [b for b in dlg.findChildren(QPushButton) if b.text() == "Aufstellen"]
    assert len(place) == 2
    place[1].click()
    assert asked and asked[0]["name"] == "B" and asked[0]["hanging"]
    assert [v["name"] for v in rename(storage.load_variants(path), "A", "B")] == ["B"]


def test_tray_has_the_bigtree_menu(qapp):
    from taskbar_cat.ui.tray import CatTray
    t = CatTray(Cat(Needs(), random.Random(0)))
    sub = next(a.menu() for a in t.menu().actions() if a.menu() and a.text() == "Große Kratzbäume")
    asked = []
    t.bigtreeRequested.connect(lambda: asked.append("neu"))
    t.collectionRequested.connect(lambda: asked.append("sammlung"))
    for a in sub.actions():
        a.trigger()
    assert asked == ["neu", "sammlung"]


@pytest.fixture
def overlay(qapp, tmp_path):
    from PyQt6.QtQml import QQmlEngine
    from taskbar_cat import sprites
    from taskbar_cat.ui.overlay import OverlayManager
    try:
        om = OverlayManager(QQmlEngine(), sprites.ensure_atlas(tmp_path), False, None,
                            sprites.ensure_furniture(tmp_path))
    except RuntimeError as e:   # ohne org.kde.layershell
        pytest.skip(str(e))
    ov = next(iter(om._overlays.values()))
    return om, ov


def test_overlay_draws_trees_and_takes_the_wheel(overlay):
    from PyQt6.QtCore import QPoint, QPointF, Qt
    from PyQt6.QtGui import QGuiApplication, QWheelEvent
    from taskbar_cat.world import Output, Rect, World
    om, ov = overlay
    g = ov.screen.geometry()
    w = World([Output("x", Rect(0, 0, g.width(), g.height()), Rect(0, 0, g.width(), g.height()))], [])
    f = Furniture()
    f.add_tree(300, 100)
    k2 = f.add_tree(600, 100, rng=random.Random(3))
    c = Cat(Needs(), random.Random(0))
    c.furniture = f
    c.spawn(w)
    c.x = 50
    settle(f, w)
    om.render(c, f.world_with(w, c.sprite), 0, f)
    assert [t["kind"] for t in ov.scene.property("bigtrees")] == [KIND, k2]
    post = om._furn_parts[k2][1].center()
    assert om._hit(post.x(), post.y()) == k2
    gap = om._furn_parts[k2][0].center() - QPoint(0, 2 * c.sprite)   # Luft über dem Sockel
    assert om._hit(gap.x(), gap.y()) in (None, k2)
    asked = []
    om.furnitureWheel.connect(lambda k, dx, dy: asked.append((k, dx, dy)))
    pos = QPointF(post.x(), post.y())
    QGuiApplication.sendEvent(ov.window, QWheelEvent(pos, pos, QPoint(), QPoint(0, 120), Qt.MouseButton.NoButton,
                                                     Qt.KeyboardModifier.NoModifier,
                                                     Qt.ScrollPhase.NoScrollPhase, False))
    assert asked == [(k2, 0.0, 120.0)]


def test_overlay_hides_her_behind_the_cave_wall(overlay):
    from taskbar_cat import sprites
    from taskbar_cat.world import Output, Rect, World
    om, ov = overlay
    g = ov.screen.geometry()
    w = World([Output("x", Rect(0, 0, g.width(), g.height()), Rect(0, 0, g.width(), g.height()))], [])
    size = next((s for s in SIZES if bigtree.cave_of(layout(*s)) is not None))
    f = Furniture()
    f.trees[KIND] = Tree(*size)
    f.add_tree(g.width() / 2, 100)
    settle(f, w)
    c = Cat(Needs(), random.Random(0))
    c.furniture = f
    c.spawn(w)
    ww = f.world_with(w, c.sprite)
    x, q = c._cave_door(ww, KIND)
    c.x = x
    c._land(ww, q)
    c._cave = KIND
    c._set("cave_in", cat_mod.CAVE_IN_S / 2)
    om.render(c, ww, 0, f)
    fronts = ov.scene.property("bigtreeFronts")
    assert [fr["src"].endswith("?load=cave:1&front=1") for fr in fronts] == [True]
    assert ov.scene.property("catOpacity") == pytest.approx(0.5)
    wall = sprites.render_front(*size, False, 0, ("cave", 1))
    b = bigtree.cave_of(layout(*size))
    assert wall.pixelColor(wall.width() // 2, wall.height() - 3).alpha() == 0    # Tür offen
    assert wall.pixelColor(1, wall.height() - 3) == sprites.CAVE                 # Wand daneben
    assert (wall.width(), wall.height()) == (b.x2 - b.x1, b.sag)
    c._set("cave", 5)
    om.render(c, ww, 0, f)
    assert ov.scene.property("bigtreeFronts") == [] and ov.scene.property("catOpacity") == 1


# --- Bällchen, Kratzspuren, Jagd über die Etagen ---

def toy_tree():
    """Stehender Baum, bei dem ein Bällchen über einem Brett in Pfotenhöhe hängt."""
    for w_, h_ in SIZES:
        lay = layout(w_, h_)
        if any(k != bigtree.BASE_KEY for _, k in bigtree.reachable_toys(lay)):
            return tree_world(size=(w_, h_))
    raise AssertionError("kein Baum mit erreichbarem Bällchen")


def test_reachable_toys_hang_just_above_their_board():
    for w_, h_ in SIZES[::3]:
        lay = layout(w_, h_)
        for i, key in bigtree.reachable_toys(lay):
            x, y, n, _ = lay.toys[i]
            surf = lay.base_y if key == bigtree.BASE_KEY else next(b.y for b in lay.boards if b.key == key)
            assert bigtree.TOY_REACH[0] <= surf - (y + n + 3) <= bigtree.TOY_REACH[1]


def test_batted_toy_swings_and_comes_to_rest():
    w, f = toy_tree()
    f.bat_toy(KIND, 0, 1)
    angles = []
    for _ in range(int(8 / DT)):
        f.tick(f.world_with(w, SPRITE), DT, SPRITE)
        angles.append(f.toy_angle(KIND, 0))
    assert max(angles) > 0.3 and min(angles) < -0.05         # pendelt hin und her
    assert (KIND, 0) not in f.toy_swing                        # und kommt zur Ruhe
    f.bat_toy(KIND, 0, -1)
    f.resize_tree(KIND, 120, 380)
    f.tick(f.world_with(w, SPRITE), DT, SPRITE)
    assert all(i < len(f.trees[KIND].layout().toys) for _, i in f.toy_swing)


def test_toy_does_not_stick_at_the_stop():
    """Gemeldet: mehrere Schläge an langem Faden - es blieb lange oben am Anschlag."""
    from taskbar_cat.furniture import TOY_MAX
    f = Furniture()
    f.toys_of = lambda kind: ((0, 0, 28, 0),)
    top = 0
    for i in range(int(4 / DT)):
        if i in (0, int(0.5 / DT), int(1 / DT)):
            f.bat_toy("x", 0, -1)
        f._swing_toys(DT, SPRITE)
        top += abs(f.toy_angle("x", 0)) >= TOY_MAX - 1e-6
    assert top * DT < 0.15


def test_cat_bats_a_toy_from_the_board_below():
    w, f = toy_tree()
    ww = f.world_with(w, SPRITE)
    kind_key = next((i, k) for i, k in bigtree.reachable_toys(f.trees[KIND].layout()) if k != bigtree.BASE_KEY)
    p = next(q for q in ww.platforms if q.owner == f"{BOARD_ID}{KIND}:{kind_key[1]}")
    batted = 0
    for seed in range(10):
        c = cat_near(f, w, seed=seed)
        c.x = (p.x1 + p.x2) / 2
        c._land(ww, p)
        for _ in range(int(20 / DT)):
            c.tick(DT, f.world_with(w, SPRITE), False)
            if c.state == "swat":
                assert c.frame_key(0)[0] == "swipe" and f.toy_swing   # das Bällchen pendelt
                batted += 1
                break
    assert batted >= 3


def test_scratching_frays_the_post():
    w, f = tree_world()
    c = cat_near(f, w)
    ww = f.world_with(w, SPRITE)
    assert c._seek(KIND, ww)
    assert run_until(c, f, w, ("scratch",))
    post = c._post[1]
    t = f.trees[KIND]
    assert t.wear[post] == pytest.approx(1 / 5)                 # Vorgabe: nach 5 Mal ganz zerfranst
    assert t.wear_levels() == "0" * post + "1"                  # schon das erste Mal sichtbar
    levels = []
    for _ in range(5):
        t.scratch(post, 1 / 5)
        levels.append(t.wear_levels()[-1])
    assert levels == ["2", "2", "3", "3", "3"] and t.wear[post] == 1.0
    c.cfg.set("sisal_scratches", 2)
    t.wear = []
    c._set("idle_sit", 1)
    assert c._seek(KIND, f.world_with(w, SPRITE))
    assert run_until(c, f, w, ("scratch",))
    assert t.wear[c._post[1]] == pytest.approx(0.5)
    back = Tree.from_dict(json.loads(json.dumps(t.to_dict())))
    assert back.wear_levels() == t.wear_levels() and "wear" not in t.variant("x")
    assert "wear" not in Tree().to_dict()


def test_frayed_posts_look_different(qapp):
    from taskbar_cat import sprites
    plain = sprites.render_bigtree(81, 180, False, 5)
    frayed = sprites.render_bigtree(81, 180, False, 5, wear="3")
    assert plain != frayed and plain.size() == frayed.size()
    assert sprites.render_bigtree(81, 180, False, 5, toys=False) != plain or not layout(81, 180, False, 5).toys


def test_play_hops_from_board_to_board_after_the_cursor():
    w, f = tree_world()
    ww = f.world_with(w, SPRITE)
    boards = sorted((q for q in ww.platforms if q.owner.startswith(BOARD_ID)), key=lambda q: -q.y)
    c = cat_near(f, w, x=boards[0].x1 - 60)
    reached = set()
    for target in boards[1:4]:
        cx, cy = (target.x1 + target.x2) / 2, target.y - 40
        for _ in range(int(6 / DT)):
            c.tick(DT, f.world_with(w, SPRITE), False, cursor=(cx, cy), wiggling=True)
            if c.platform is not None and c.platform.owner == target.owner:
                reached.add(target.owner)
                break
    assert len(reached) >= 2


def test_overlay_draws_swinging_toys(overlay):
    from taskbar_cat.world import Output, Rect, World
    om, ov = overlay
    g = ov.screen.geometry()
    w = World([Output("x", Rect(0, 0, g.width(), g.height()), Rect(0, 0, g.width(), g.height()))], [])
    f = Furniture()
    f.trees[KIND] = Tree(81, 180)
    f.add_tree(g.width() / 2, 100)
    settle(f, w)
    c = Cat(Needs(), random.Random(0))
    c.furniture = f
    c.spawn(w)
    om.render(c, f.world_with(w, c.sprite), 0, f)
    toys = ov.scene.property("bigtreeToys")
    assert len(toys) == len(f.trees[KIND].layout().toys) > 0
    assert ov.scene.property("toyAngles") == [0.0] * len(toys)
    f.trees[KIND].wear = [1.0]
    f.bat_toy(KIND, 0, 1)
    f.tick(f.world_with(w, c.sprite), DT, c.sprite)
    om.render(c, f.world_with(w, c.sprite), 0, f)
    assert ov.scene.property("toyAngles")[0] > 0
    assert "wear=3" in ov.scene.property("bigtrees")[0]["src"]


def test_ctrl_wheel_changes_the_width():
    """Nicht jede Maus kann seitlich scrollen: mit Strg zählt hoch/runter zur Breite."""
    t = Tree(48, 100)
    assert t.wheeled(0, 120) == (48, pytest.approx(100 * bigtree.WHEEL_STEP))
    assert t.wheeled(0, 120, ctrl=True) == (pytest.approx(48 * bigtree.WHEEL_STEP), 100)
    assert t.wheeled(120, 0, ctrl=True) == t.wheeled(120, 0)


def test_locked_tree_keeps_its_size_and_place():
    w, f = toy_tree()
    before = f.trees[KIND].size()
    x = f.bodies[KIND].x
    f.set_locked(KIND, True)
    assert f.locked(KIND)
    f.resize_tree(KIND, 120, 300)
    assert not f.put(KIND, w, x + 500, 200, 20)
    assert f.trees[KIND].size() == before and f.bodies[KIND].x == x
    f.set_locked(KIND, False)
    f.resize_tree(KIND, 120, 300)
    assert f.trees[KIND].size() == (120, 300)


def test_lock_survives_a_restart(tmp_path):
    w, f = toy_tree()
    f.set_locked(KIND, True)
    path = tmp_path / "furniture.json"
    storage.save(path, f)
    assert storage.load_furniture(path).locked(KIND)


def test_overlay_does_not_drag_a_locked_tree(overlay):
    from taskbar_cat.world import Output, Rect, World
    om, ov = overlay
    g = ov.screen.geometry()
    w = World([Output("x", Rect(0, 0, g.width(), g.height()), Rect(0, 0, g.width(), g.height()))], [])
    f = Furniture()
    f.add_tree(g.width() / 2, 100)
    settle(f, w)
    c = Cat(Needs(), random.Random(0))
    c.furniture = f
    c.spawn(w)
    c.x = 20                                  # nicht vor dem Baum: sie geht sonst vor
    f.set_locked(KIND, True)
    om.render(c, f.world_with(w, c.sprite), 0, f)
    moved = []
    om.furnitureMoved.connect(lambda *a: moved.append(a))
    x, y = f.usable(KIND, w)
    om._pressed(ov, x - ov.origin.x(), y - 10 - ov.origin.y(), Qt.MouseButton.LeftButton.value)
    om._moved(ov, x - ov.origin.x() + 100, y - ov.origin.y(), Qt.MouseButton.LeftButton.value)
    assert om._grabbed is None and moved == []


# --- hinter Fenstern ---

def hidden_tree_world(kind=KIND):
    """Baum aufgestellt, danach geht ein Fenster davor auf."""
    from taskbar_cat.world import Win, Rect
    w = world()
    f = Furniture()
    if kind == KIND:
        f.add_tree(1000, 100)
        f.trees[KIND].resize(60, 200)
    else:
        f.place("tree", w, 1000, 100, 20)
    settle(f, w, 10)
    f.set_behind(kind, True)
    before = f.usable(kind, w)
    covered = world(Win("a", Rect(before[0] - 300, before[1] - 300, 600, 400), 5, False, False))
    return covered, f


def test_window_covers_the_tree_and_her_in_it():
    from taskbar_cat.furniture import window_rects
    from taskbar_cat.world import Rect, overlap, uncovered
    w, f = hidden_tree_world()
    ww = f.world_with(w, SPRITE)
    board = next(p for p in ww.platforms if p.owner.startswith(BOARD_ID)
                 and any(overlap(Rect(p.x1, p.y, p.x2 - p.x1, 2), r) for r in window_rects(w)))
    c = cat_near(f, w)
    c._land(ww, board)
    c.x = (board.x1 + board.x2) / 2
    assert c.hidden_behind(ww)                      # im Baum hinter dem Fenster
    rest = uncovered(c.sprite_rect(), window_rects(w))
    assert sum(p.w * p.h for p in rest) < c.sprite * c.sprite    # verdeckt gezeichnet
    f.set_behind(KIND, False)
    assert not c.hidden_behind(ww)                  # Baum wieder davor, sie auch


def test_down_from_the_tree_she_is_visible_again_at_once():
    from taskbar_cat.furniture import window_rects
    w, f = hidden_tree_world()
    ww = f.world_with(w, SPRITE)
    board = next(p for p in ww.platforms if p.owner.startswith(BOARD_ID))
    c = cat_near(f, w)
    c._land(ww, board)
    assert c.hidden_behind(ww)
    floor = next(p for p in ww.platforms if p.is_floor)      # sie springt herunter
    c._land(ww, floor)
    c.x = window_rects(w)[0].x + 50              # noch vor dem Fenster, aber nicht im Baum
    assert not c.hidden_behind(ww)


def covered_piece(p, w):
    """Verschwindet diese Fläche hinter einem Fenster (Sprite-Höhe darüber)?"""
    from taskbar_cat.furniture import window_rects
    from taskbar_cat.world import Rect, overlap
    return any(overlap(Rect(p.x1, p.y - SPRITE, p.x2 - p.x1, SPRITE), r) for r in window_rects(w))


def test_she_avoids_the_boards_behind_a_window():
    w, f = hidden_tree_world()
    ww = f.world_with(w, SPRITE)
    c = cat_near(f, w)
    floor = next(p for p in ww.platforms if p.is_floor)
    c._land(ww, floor)
    c.x = f.usable(KIND, w)[0]
    assert [p for p in ww.platforms if p.owner.startswith(BOARD_ID) and covered_piece(p, w)]
    assert not [q for q in c._jump_targets(ww, floor) if covered_piece(q, w)]
    assert [q for q in c._jump_targets(ww, floor) if q.owner.startswith(BOARD_ID)]  # oben drüber schon
    f.set_behind(KIND, False)
    assert [q for q in c._jump_targets(ww, floor) if covered_piece(q, w)]   # davor nutzt sie sie


def test_she_avoids_a_cave_behind_a_window():
    from taskbar_cat.world import Rect, Win
    w, f = cave_tree()
    c = cat_near(f, w)
    pos = f.usable(KIND, w)
    assert c._cave_door(f.world_with(w, SPRITE), KIND) is not None
    f.set_behind(KIND, True)
    ww = f.world_with(world(Win("a", Rect(pos[0] - 300, pos[1] - 300, 600, 400), 5, False, False)), SPRITE)
    assert c._cave_door(ww, KIND) is None


def test_she_avoids_the_small_tree_behind_a_window():
    w, f = hidden_tree_world("tree")
    ww = f.world_with(w, SPRITE)
    c = cat_near(f, w, x=f.bodies["tree"].x)
    c.cfg.set("p_toy", 0)
    c.cfg.set("p_scratch", 0)
    c._land(ww, next(p for p in ww.platforms if p.is_floor))
    deck = next(p for p in ww.platforms if p.owner == TREE_ID)
    assert covered_piece(deck, w)
    for _ in range(20):
        c._use_tree(ww, c.x)
        assert c.state == "scratch"          # weder hinauf noch am Pfeiler hoch
    f.set_behind("tree", False)
    states = set()
    for _ in range(20):
        c._land(ww, next(p for p in ww.platforms if p.is_floor))
        c._use_tree(ww, c.x)
        states.add(c.state)
    assert states - {"scratch"}              # davor geht sie wieder hinauf


def test_on_top_of_the_window_she_is_in_front_again():
    w, f = hidden_tree_world()
    ww = f.world_with(w, SPRITE)
    c = cat_near(f, w)
    c._land(ww, next(p for p in ww.platforms if p.owner.startswith(BOARD_ID)))
    assert c.hidden_behind(ww)
    c._land(ww, next(p for p in ww.platforms if p.owner == "a"))
    assert not c.hidden_behind(ww)               # auf der Fensterkante steht sie davor


def test_dragged_she_is_always_visible():
    w, f = hidden_tree_world()
    ww = f.world_with(w, SPRITE)
    c = cat_near(f, w)
    c._land(ww, next(p for p in ww.platforms if p.owner.startswith(BOARD_ID)))
    assert c.hidden_behind(ww)
    c.state = "dragged"
    assert not c.hidden_behind(ww)


def test_behind_survives_a_restart(tmp_path):
    w, f = hidden_tree_world()
    f.set_behind("tree", True)
    path = tmp_path / "furniture.json"
    storage.save(path, f)
    g = storage.load_furniture(path)
    assert g.behind(KIND) and g.behind("tree")


def drop_on_trees(f, w, seconds=10):
    """Fallen lassen in der Welt samt Baumkanten - sonst landet alles auf dem Boden."""
    for _ in range(int(seconds / DT)):
        f.tick(f.world_with(w, SPRITE), DT, SPRITE)


def test_things_on_a_hidden_tree_are_hidden_too():
    """Napf und Knäuel auf einem versteckten Baum verschwinden mit ihm, und nur solange
    sie darauf liegen."""
    w = world()
    f = Furniture()
    f.add_tree(1000, 100)
    f.trees[KIND].resize(100, 200)
    settle(f, w, 10)
    base = f.usable(KIND, w)
    f.place("bowl", w, base[0], base[1] - 400, HALF)
    drop_on_trees(f, w)
    assert f.bodies["bowl"].platform.owner.startswith(BOARD_ID)   # steht auf dem Baum
    assert not f.hidden("bowl")
    f.set_behind(KIND, True)
    assert f.hidden(KIND) and f.hidden("bowl")
    f.place("bowl", w, 100, 500, HALF)        # herunter auf den Boden
    drop_on_trees(f, w)
    assert not f.hidden("bowl") and f.hidden(KIND)


def test_hidden_carries_through_a_stack():
    """Kleiner Kratzbaum auf dem großen, Napf auf dem kleinen: alle drei verschwinden."""
    w = world()
    f = Furniture()
    f.add_tree(1000, 100)
    f.trees[KIND].resize(100, 260)
    settle(f, w, 10)
    deck = max((p for p in f.world_with(w, SPRITE).platforms if p.owner.startswith(BOARD_ID)),
               key=lambda p: p.x2 - p.x1)
    f.place("tree", w, (deck.x1 + deck.x2) / 2, deck.y - 300, HALF)
    drop_on_trees(f, w)
    assert f.bodies["tree"].platform.owner.startswith(BOARD_ID)
    f.place("bowl", w, f.usable("tree", w)[0], deck.y - 600, HALF)
    drop_on_trees(f, w)
    assert f.bodies["bowl"].platform.owner == "furniture:tree"
    f.set_behind(KIND, True)
    assert f.hidden("tree") and f.hidden("bowl")


def test_hanging_tree_does_not_loop():
    """Ein hängender Baum steht auf seiner eigenen Kante - das darf sich nicht aufschaukeln."""
    w = world()
    f = Furniture()
    f.add_tree(1000, 100)
    f.world_with(w, SPRITE)
    f.put(KIND, w, 1000, 50, HALF)
    f.release(KIND, 0, 0)
    assert f.trees[KIND].hanging
    assert not f.hidden(KIND)
    f.set_behind(KIND, True)
    assert f.hidden(KIND)


def test_cat_on_something_that_stands_on_a_hidden_tree():
    """Sie sitzt auf dem kleinen Kratzbaum, der auf dem versteckten großen steht."""
    w = world()
    f = Furniture()
    f.add_tree(1000, 100)
    f.trees[KIND].resize(100, 260)
    settle(f, w, 10)
    deck = max((p for p in f.world_with(w, SPRITE).platforms if p.owner.startswith(BOARD_ID)),
               key=lambda p: p.x2 - p.x1)
    f.place("tree", w, (deck.x1 + deck.x2) / 2, deck.y - 300, HALF)
    drop_on_trees(f, w)
    ww = f.world_with(w, SPRITE)
    c = cat_near(f, w)
    c._land(ww, next(p for p in ww.platforms if p.owner == "furniture:tree"))
    assert not c.hidden_behind(ww)
    f.set_behind(KIND, True)
    assert c.hidden_behind(ww)


def test_overlay_cuts_what_stands_on_a_hidden_tree(overlay):
    from taskbar_cat.world import Output, Rect, Win, World
    om, ov = overlay
    g = ov.screen.geometry()
    out = [Output("x", Rect(0, 0, g.width(), g.height()), Rect(0, 0, g.width(), g.height()))]
    w = World(out, [])
    f = Furniture()
    f.add_tree(g.width() / 2, 20)
    f.trees[KIND].resize(100, 120)
    settle(f, w, 10)
    board = max((p for p in f.world_with(w, SPRITE).platforms if p.owner.startswith(BOARD_ID)),
                key=lambda p: p.x2 - p.x1)
    f.place("bowl", w, (board.x1 + board.x2) / 2, board.y - 200, 20)
    drop_on_trees(f, w)
    assert f.bodies["bowl"].platform.owner.startswith(BOARD_ID)
    c = Cat(Needs(), random.Random(0))
    c.furniture = f
    c.spawn(w)
    c.x = 10
    bowl_x, bowl_y = f.usable("bowl", w)
    covered = World(out, [Win("a", Rect(0, 0, g.width(), bowl_y - 10), 5, False, False)])
    f.set_behind(KIND, True)
    om.render(c, f.world_with(covered, c.sprite), 0, f)
    pieces = [p for t in ov.scene.property("furnitureBack") for p in t["clip"]]
    assert pieces and all(p["y"] >= bowl_y - 10 - ov.origin.y() for p in pieces)


@pytest.mark.parametrize("kind", [KIND, "tree"])
def test_overlay_cuts_the_hidden_tree_into_pieces(overlay, kind):
    """Hinter einem Fenster bleiben nur die Streifen daneben stehen - und keine Klicks."""
    from taskbar_cat.world import Output, Rect, Win, World
    om, ov = overlay
    g = ov.screen.geometry()
    out = [Output("x", Rect(0, 0, g.width(), g.height()), Rect(0, 0, g.width(), g.height()))]
    w = World(out, [])
    f = Furniture()
    if kind == KIND:
        f.add_tree(g.width() / 2, 50)
        f.trees[KIND].resize(60, 120)
    else:
        f.place("tree", w, g.width() / 2, 50, 20)
    settle(f, w, 10)
    c = Cat(Needs(), random.Random(0))
    c.furniture = f
    c.spawn(w)
    c.x = 10
    om.render(c, f.world_with(w, c.sprite), 0, f)
    whole = len(om._furn_parts.get(kind, om._furn_rects.get(kind, ())))
    assert whole > 0
    x, y = f.usable(kind, w)
    covered = World(out, [Win("a", Rect(0, 0, g.width(), y - 40), 5, False, False)])
    f.set_behind(kind, True)
    om.render(c, f.world_with(covered, c.sprite), 0, f)
    drawn = ov.scene.property("bigtrees" if kind == KIND else "furnitureBack")
    pieces = [p for t in drawn for p in t["clip"]]
    assert 0 < len(pieces) < sum(1 for _ in drawn) + 2        # zerschnitten, nicht am Stück
    assert all(p["h"] > 0 and p["w"] > 0 for p in pieces)
    assert len(om._furn_parts.get(kind, om._furn_rects.get(kind, ()))) != whole  # Maus zieht mit


def test_she_lies_in_the_middle_of_the_hammock():
    """Sie ist breiter als die Matte - am Rand haengt sie seitlich heraus."""
    w, f = hammock_tree()
    ww = f.world_with(w, SPRITE)
    mat = next(p for p in ww.platforms if bigtree.in_hammock(p.owner))
    c = cat_near(f, w, energy=10)
    c._land(ww, mat)
    c.x = mat.x1 + 2
    c._set("idle_sit", 0.0)
    c.tick(DT, ww, False)
    assert c.x == pytest.approx((mat.x1 + mat.x2) / 2)
    assert c.hammock() == mat.owner


def test_overlay_draws_the_yarn_in_front_while_she_hugs_it(overlay):
    from taskbar_cat.world import Output, Rect, World
    om, ov = overlay
    g = ov.screen.geometry()
    w = World([Output("x", Rect(0, 0, g.width(), g.height()), Rect(0, 0, g.width(), g.height()))], [])
    f = Furniture()
    f.place("yarn", w, g.width() / 2, 50, 20)
    settle(f, w, 10)
    c = Cat(Needs(), random.Random(0))
    c.furniture = f
    c.spawn(w)
    om.render(c, w, 0, f)
    assert ov.scene.property("furnitureBack") and not ov.scene.property("furnitureFront")
    c._set("hug", 1)
    om.render(c, w, 0, f)
    assert ov.scene.property("furnitureFront") and not ov.scene.property("furnitureBack")


def test_overlay_draws_the_small_tree_with_its_ball(overlay):
    """Der kleine Kratzbaum: Bällchen wie am großen, Frame nach Verschleiß."""
    from taskbar_cat.furniture import TREE_TOY
    from taskbar_cat.world import Output, Rect, World
    om, ov = overlay
    g = ov.screen.geometry()
    w = World([Output("x", Rect(0, 0, g.width(), g.height()), Rect(0, 0, g.width(), g.height()))], [])
    f = Furniture()
    f.place("tree", w, g.width() / 2, 100, 20)
    settle(f, w)
    c = Cat(Needs(), random.Random(0))
    c.furniture = f
    c.spawn(w)
    om.render(c, f.world_with(w, c.sprite), 0, f)
    toys = ov.scene.property("bigtreeToys")
    assert len(toys) == 1
    assert toys[0]["len"] == TREE_TOY[2] * c.sprite / 32
    assert toys[0]["x"] == f.toy_x("tree", 0, w, c.sprite) - ov.origin.x()
    back = ov.scene.property("furnitureBack")
    assert [b["sx"] for b in back] == [sprites.furniture_origin("tree")[0]]
    f.scratch("tree", 0, 1.0)
    om.render(c, f.world_with(w, c.sprite), 0, f)
    assert [b["sx"] for b in ov.scene.property("furnitureBack")] == \
        [sprites.furniture_origin("tree_wear3")[0]]


@pytest.mark.parametrize("name, state", [("p_scratch", "scratch"), ("p_cave", "cave_in"), ("p_toy", "swat")])
def test_each_tree_activity_can_be_switched_off(name, state):
    """Auf 0 kommt die Tätigkeit nicht mehr vor, auf 1 schon."""
    w, f = toy_tree() if name == "p_toy" else cave_tree()
    for p, expected in ((0.0, False), (1.0, True)):
        seen = False
        for seed in range(4):
            c = cat_near(f, w, seed=seed)
            c.cfg.set(name, p)
            if name == "p_toy":      # gleich auf die Fläche unter dem Bällchen
                ww = f.world_with(w, SPRITE)
                key = next(k for _, k in bigtree.reachable_toys(f.trees[KIND].layout()) if k != bigtree.BASE_KEY)
                c._land(ww, next(q for q in ww.platforms if q.owner == f"{BOARD_ID}{KIND}:{key}"))
            seen |= run_until(c, f, w, (state,), 60)
            if seen:
                break
        assert seen == expected, (name, p)


def test_overlay_draws_flies_over_spilled_food(overlay):
    from taskbar_cat.world import Output, Rect, Win, World
    om, ov = overlay
    g = ov.screen.geometry()
    w = World([Output("x", Rect(0, 0, g.width(), g.height()), Rect(0, 0, g.width(), g.height()))], [])
    f = Furniture()
    f.place("bowl", w, 300, 100, 20)
    settle(f, w)
    f.tipped, f.spill = True, 3
    settle(f, w, 10)
    c = Cat(Needs(), random.Random(0))
    c.furniture = f
    c.spawn(w)
    om.render(c, w, 1.0, f)
    pos = ov.scene.property("flyPos")
    assert ov.scene.property("flyCount") == 3 and len(pos) == 9
    assert all(abs(pos[3 * i] - 300) < 3 * c.sprite / 32 * 20 for i in range(3))
    assert all(pos[3 * i + 1] < f.bodies["bowl"].y for i in range(3))
    f.spill_age += 0.2                                         # ihre Uhr: so lange liegt es da
    om.render(c, w, 1.2, f)
    assert ov.scene.property("flyPos") != pos                 # sie fliegen herum
    f.tipped = False
    om.render(c, w, 1.4, f)
    assert ov.scene.property("flyCount") == 0
