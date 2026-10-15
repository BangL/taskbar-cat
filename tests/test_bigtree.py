import json
import random

import pytest

from taskbar_cat import bigtree, storage
from taskbar_cat.bigtree import BOARD_ID, KIND, Tree, layout
from taskbar_cat.cat import SPRITE, Cat
from taskbar_cat.config import Config
from taskbar_cat.furniture import Furniture
from taskbar_cat.needs import Needs

from test_furniture import DT, settle, world

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


def test_more_trees_and_back_to_inventory():
    w = world()
    f = Furniture()
    assert f.add_tree(500, 300) == KIND                # erst der aus dem Inventar
    k2 = f.add_tree(900, 300, rng=random.Random(1))
    assert k2 == KIND + "2" and f.trees[k2].seed != 0
    settle(f, w)
    assert f.bodies[k2].resting and f.position(k2, w)[1] == 1080
    f.remove_tree(k2)
    assert k2 not in f.bodies and k2 not in f.trees
    f.remove_tree(KIND)
    assert not f.placed(KIND) and KIND in f.trees     # nur eingelagert


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
    assert owners == {f"{BOARD_ID}{KIND}:{b.key}" for b in f.trees[KIND].layout().boards}


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
    cfg.set("p_bigtree", 1)
    c.cfg = cfg
    return c


def test_cat_climbs_posts_and_uses_the_boards():
    w, f = tree_world()
    seen, anims, boards = set(), set(), set()
    for seed in range(3):
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


def test_no_bigtree_no_extra_dice():
    """Ohne aufgestellten großen Kratzbaum bleibt das übrige Verhalten gleich."""
    w = world()
    a, b = cat_near(Furniture(), w), cat_near(Furniture(), w)
    b.cfg.set("p_bigtree", 0)
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
    assert [t["kind"] for t in ov.window.property("bigtrees")] == [KIND, k2]
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
