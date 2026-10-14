import json

import pytest

from taskbar_cat.world import Ceiling, Output, Platform, Rect, Wall, Win, World


def two_outputs(panel="top"):
    outs = []
    for i, name in enumerate(("DP-3", "DP-4")):
        x = i * 1920
        geo = Rect(x, 0, 1920, 1080)
        if panel == "top":
            wa = Rect(x, 44, 1920, 1036)
        elif panel == "bottom":
            wa = Rect(x, 0, 1920, 1036)
        else:
            wa = geo
        outs.append(Output(name, geo, wa))
    return outs


def win(id, x, y, w, h, stack=0, fs=False, mx=False, panel=False):
    return Win(str(id), Rect(x, y, w, h), stack, fs, mx, panel)


def window_platforms(world):
    return sorted((p for p in world.platforms if not p.is_floor), key=lambda p: (p.owner, p.x1))


def floor(world, name):
    return next(p for p in world.platforms if p.owner == f"floor:{name}")


def test_floor_at_screen_bottom_when_panel_top():
    assert floor(World(two_outputs("top"), []), "DP-3").y == 1080


def test_floor_on_panel_when_panel_bottom():
    assert floor(World(two_outputs("bottom"), []), "DP-3").y == 1036


def test_floor_without_panel():
    assert floor(World(two_outputs("none"), []), "DP-4").y == 1080


def test_window_top_edge_is_platform():
    w = World(two_outputs(), [win("a", 100, 300, 800, 500)])
    assert window_platforms(w) == [Platform(100, 900, 300, "a")]


def test_window_edge_clipped_to_work_area():
    w = World(two_outputs(), [win("a", -100, 300, 800, 500)])
    assert window_platforms(w) == [Platform(0, 700, 300, "a")]


def test_maximized_top_not_walkable():
    w = World(two_outputs("top"), [win("a", 0, 44, 1920, 1036, mx=True)])
    assert window_platforms(w) == []


def test_occlusion_cuts_edge():
    w = World(two_outputs(), [win("a", 0, 300, 1000, 400, 0), win("b", 400, 200, 200, 400, 1)])
    plats = [p for p in window_platforms(w) if p.owner == "a"]
    assert [(p.x1, p.x2) for p in plats] == [(0, 400), (600, 1000)]


def test_lower_window_does_not_occlude():
    w = World(two_outputs(), [win("a", 0, 300, 1000, 400, 1), win("b", 400, 200, 200, 400, 0)])
    plats = [p for p in window_platforms(w) if p.owner == "a"]
    assert [(p.x1, p.x2) for p in plats] == [(0, 1000)]


def test_tiny_pieces_dropped():
    w = World(two_outputs(), [win("a", 0, 300, 1000, 400, 0), win("b", 30, 200, 970, 400, 1)])
    assert [p for p in window_platforms(w) if p.owner == "a"] == []


def test_fullscreen_forbids_output():
    w = World(two_outputs(), [win("a", 2100, 500, 400, 300), win("fs", 1920, 0, 1920, 1080, 5, fs=True)])
    assert "DP-4" in w.forbidden_outputs
    start = floor(w, "DP-3")
    reach = w.reachable(start, 1900)
    assert all(not (p.owner == "a" or p.owner == "floor:DP-4") for p in reach)


def test_floors_are_neighbors_across_outputs():
    w = World(two_outputs(), [])
    assert w.neighbor(floor(w, "DP-3"), +1) == floor(w, "DP-4")
    assert w.neighbor(floor(w, "DP-4"), -1) == floor(w, "DP-3")
    assert w.neighbor(floor(w, "DP-3"), -1) is None


def test_reachable_respects_jump_height():
    w = World(two_outputs(), [win("high", 100, 1080 - 350, 400, 300), win("low", 600, 1080 - 250, 400, 200)])
    owners = {p.owner for p in w.reachable(floor(w, "DP-3"), 500)}
    assert "low" in owners
    assert "high" not in owners


def test_reachable_side_distance():
    w = World(two_outputs(), [win("far", 1500, 900, 300, 100)])
    assert all(p.owner != "far" for p in w.reachable(floor(w, "DP-3"), 500))
    assert any(p.owner == "far" for p in w.reachable(floor(w, "DP-3"), 1200))


def test_platform_below():
    w = World(two_outputs(), [win("a", 100, 300, 800, 500)])
    assert w.platform_below(500, 100).owner == "a"
    assert w.platform_below(500, 400).owner == "floor:DP-3"
    assert w.platform_below(500, 100, floors_only=True).owner == "floor:DP-3"
    assert w.platform_below(5000, 100) is None


def test_output_at():
    w = World(two_outputs(), [])
    assert w.output_at(100, 500).name == "DP-3"
    assert w.output_at(1920, 500).name == "DP-4"
    assert w.output_at(-5, 500) is None


def test_window_rect_and_bounds():
    w = World(two_outputs(), [win("a", 100, 300, 800, 500)])
    assert w.window_rect("a") == Rect(100, 300, 800, 500)
    assert w.window_rect("x") is None
    assert w.bounds() == Rect(0, 0, 3840, 1080)


def test_platform_by_owner_at():
    w = World(two_outputs(), [win("a", 0, 300, 1000, 400, 0), win("b", 400, 200, 200, 400, 1)])
    assert w.platform_by_owner_at("a", 700).x1 == 600
    assert w.platform_by_owner_at("a", 500) is None


def test_from_json_roundtrip_and_invalid():
    data = {
        "outputs": [{"name": "DP-3", "geometry": {"x": 0, "y": 0, "w": 1920, "h": 1080},
                     "workArea": {"x": 0, "y": 44, "w": 1920, "h": 1036}}],
        "windows": [{"id": "a", "x": 100, "y": 300, "w": 800, "h": 500, "stack": 3,
                     "fullScreen": False, "maximized": False}],
    }
    w = World.from_json(json.dumps(data))
    assert w.outputs[0].work_area == Rect(0, 44, 1920, 1036)
    assert window_platforms(w) == [Platform(100, 900, 300, "a")]
    for bad in ("[]", "{nope", '{"outputs": [{"name": 1}]}', '{"outputs": []}'):
        with pytest.raises(ValueError):
            World.from_json(bad)


def test_from_screens():
    w = World.from_screens([("DP-3", Rect(0, 0, 1920, 1080), Rect(0, 44, 1920, 1036))])
    assert floor(w, "DP-3").y == 1080


# --- Wände und Decken ---

def walls_of(world, owner):
    return sorted((w for w in world.walls if w.owner == owner), key=lambda w: (w.side, w.y1))


def test_window_has_two_walls():
    w = World(two_outputs(), [win("a", 300, 200, 800, 500)])
    assert walls_of(w, "a") == [Wall(300, 200, 700, "a", -1), Wall(1100, 200, 700, "a", 1)]


def test_wall_clipped_to_work_area():
    w = World(two_outputs("top"), [win("a", 300, 10, 800, 2000)])
    assert walls_of(w, "a")[0] == Wall(300, 44, 1080, "a", -1)


def test_wall_at_screen_border_dropped():
    w = World(two_outputs(), [win("a", 10, 200, 800, 500)])
    assert [x.side for x in walls_of(w, "a")] == [1]


def test_wall_occluded_by_higher_window():
    w = World(two_outputs(), [win("a", 300, 200, 800, 500, 0), win("b", 200, 300, 200, 100, 1)])
    left = [x for x in walls_of(w, "a") if x.side == -1]
    assert [(x.y1, x.y2) for x in left] == [(200, 300), (400, 700)]


def test_ceiling_is_bottom_edge():
    w = World(two_outputs(), [win("a", 300, 200, 800, 500)])
    assert [c for c in w.ceilings if c.owner == "a"] == [Ceiling(300, 1100, 700, "a")]


def test_ceiling_at_floor_dropped():
    w = World(two_outputs(), [win("a", 300, 200, 800, 880)])
    assert [c for c in w.ceilings if c.owner == "a"] == []


def test_ceiling_occluded():
    w = World(two_outputs(), [win("a", 0, 200, 1000, 500, 0), win("b", 400, 600, 200, 200, 1)])
    assert [(c.x1, c.x2) for c in w.ceilings if c.owner == "a"] == [(0, 400), (600, 1000)]


def test_walls_near_requires_reachable_foot():
    w = World(two_outputs(), [win("tall", 300, 200, 400, 880), win("float", 1000, 100, 400, 400)])
    f = floor(w, "DP-3")
    owners = {x.owner for x in w.walls_near(f, 500, stand_offset=18)}
    assert "tall" in owners          # reicht bis zum Boden
    assert "float" not in owners     # Unterkante 580 px über dem Boden


def test_walls_near_excludes_forbidden_output():
    w = World(two_outputs(), [win("a", 2300, 200, 400, 880), win("fs", 1920, 0, 1920, 1080, 9, fs=True)])
    assert w.walls_near(floor(w, "DP-4"), 2200, stand_offset=18) == []


def test_ceilings_near():
    w = World(two_outputs(), [win("a", 300, 400, 800, 450)])
    f = floor(w, "DP-3")
    assert [c.owner for c in w.ceilings_near(f, 500, min_gap=100, max_gap=400)] == ["a"]
    assert w.ceilings_near(f, 1600, min_gap=100, max_gap=400) == []
    assert w.ceilings_near(f, 500, min_gap=300, max_gap=400) == []


def test_from_json_ignores_own_overlay_windows():
    data = {
        "outputs": [{"name": "DP-3", "geometry": {"x": 0, "y": 0, "w": 1920, "h": 1080},
                     "workArea": {"x": 0, "y": 44, "w": 1920, "h": 1036}}],
        "windows": [
            {"id": "a", "x": 100, "y": 300, "w": 800, "h": 500, "stack": 3, "pid": 111},
            {"id": "overlay", "x": 0, "y": 0, "w": 1920, "h": 1080, "stack": 9, "pid": 222},
        ],
    }
    w = World.from_json(json.dumps(data), ignore_pid=222)
    assert [x.id for x in w.windows] == ["a"]
    assert any(p.owner == "a" for p in w.platforms)
    assert any(x.owner == "a" for x in w.walls)


# --- Panels und Docks ---

def dock(id="dock", x=600, y=1016, w=692, h=64, stack=10):
    return win(id, x, y, w, h, stack, panel=True)


def test_dock_top_edge_is_platform():
    w = World(two_outputs("none"), [dock()])
    assert window_platforms(w) == [Platform(600, 1292, 1016, "dock")]


def test_dock_has_no_walls_or_ceilings():
    w = World(two_outputs("none"), [dock()])
    assert w.walls == [] and w.ceilings == []


def test_reserved_bottom_panel_adds_no_second_platform():
    """Reserviert die Leiste Platz, ist ihre Oberkante schon der Boden."""
    w = World(two_outputs("bottom"), [dock(y=1036, h=44)])
    assert window_platforms(w) == []
    assert floor(w, "DP-3").y == 1036


def test_top_panel_is_not_walkable():
    w = World(two_outputs("top"), [dock(x=0, y=0, w=1920, h=44)])
    assert window_platforms(w) == []


def test_dock_occludes_window_edge_below_it():
    w = World(two_outputs("none"), [win("a", 620, 1030, 880, 50, 2), dock(stack=10)])
    plats = [p for p in window_platforms(w) if p.owner == "a"]
    assert [(p.x1, p.x2) for p in plats] == [(1292, 1500)]


def test_from_json_reads_panel_flag():
    data = {
        "outputs": [{"name": "DP-3", "geometry": {"x": 0, "y": 0, "w": 1920, "h": 1080},
                     "workArea": {"x": 0, "y": 0, "w": 1920, "h": 1080}}],
        "windows": [{"id": "d", "x": 600, "y": 1016, "w": 692, "h": 64, "stack": 10,
                     "panel": True}],
    }
    w = World.from_json(json.dumps(data))
    assert w.windows[0].panel is True
    assert window_platforms(w) == [Platform(600, 1292, 1016, "d")]
