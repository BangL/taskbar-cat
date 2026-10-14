import random

import pytest

from taskbar_cat.cat import HANG_DROP, SPRITE, Cat
from taskbar_cat.config import Config
from taskbar_cat.needs import Mood, Needs
from taskbar_cat.world import Output, Rect, Win, World

DT = 1 / 30


def outputs(names=("DP-3", "DP-4")):
    return [Output(n, Rect(i * 1920, 0, 1920, 1080), Rect(i * 1920, 44, 1920, 1036))
            for i, n in enumerate(names)]


def world(*wins, names=("DP-3", "DP-4"), blocked=()):
    return World(outputs(names), list(wins), blocked)


def win(id, x, y, w=800, h=400, stack=0, fs=False, panel=False):
    return Win(id, Rect(x, y, w, h), stack, fs, False, panel)


def make_cat(cfg=None, **needs):
    return Cat(Needs(**needs), random.Random(1), cfg)


def run(cat, w, seconds, locked=False):
    for _ in range(int(seconds / DT)):
        cat.tick(DT, w, locked)


def put_on(cat, w, owner, x):
    """Katze landen lassen: knapp über die Plattform setzen und fallen lassen."""
    p = w.platform_by_owner_at(owner, x)
    cat.x, cat.y = x, p.y - 2
    cat.vx = cat.vy = 0
    cat.state = "fall"
    cat.platform = None
    cat.tick(DT, w, False)
    assert cat.platform is not None and cat.platform.owner == owner


def test_spawn_on_floor():
    w = world()
    c = make_cat()
    c.spawn(w)
    assert c.platform.owner == "floor:DP-3"
    assert c.y == 1080
    assert c.x == 960


def test_needs_frozen_when_locked():
    w = world()
    c = make_cat()
    c.spawn(w)
    run(c, w, 60, locked=True)
    assert c.needs.satiety == 80


def test_needs_decay_when_unlocked():
    w = world()
    c = make_cat()
    c.spawn(w)
    run(c, w, 60)
    assert c.needs.satiety < 80


def test_paused_freezes_everything():
    w = world()
    c = make_cat()
    c.spawn(w)
    c.set_paused(True)
    x, y = c.x, c.y
    run(c, w, 30)
    assert (c.x, c.y, c.needs.satiety) == (x, y, 80)
    assert not c.visible
    c.set_paused(False)
    assert c.visible


def test_falls_when_platform_disappears():
    w = world(win("a", 100, 500))
    c = make_cat()
    c.spawn(w)
    put_on(c, w, "a", 400)
    w2 = world()
    run(c, w2, 2)
    assert c.platform.owner == "floor:DP-3"
    assert c.y == 1080
    assert c.state != "fall"


def test_rides_moving_window():
    w = world(win("a", 100, 500))
    c = make_cat()
    c.spawn(w)
    put_on(c, w, "a", 400)
    c.state, c._timer = "idle_sit", 100
    w2 = world(win("a", 200, 550))
    c.tick(DT, w2, False)
    assert (c.x, c.y) == (500, 550)
    assert c.platform.owner == "a"


def test_follows_floor_when_panel_moves():
    w = world()
    c = make_cat()
    c.spawn(w)
    c.state, c._timer = "idle_sit", 100
    moved = World([Output(o.name, o.geometry, Rect(o.geometry.x, 0, 1920, 1036)) for o in outputs()], [])
    c.tick(DT, moved, False)
    assert c.y == 1036


def test_throw_lands_on_platform():
    w = world()
    c = make_cat()
    c.spawn(w)
    c.start_drag()
    c.drag_to(500, 600)
    c.release(300, -500)
    run(c, w, 3)
    assert c.platform is not None and c.platform.is_floor
    assert c.state not in ("thrown", "fall")


def test_throw_bounces_off_outer_edge():
    w = world()
    c = make_cat()
    c.spawn(w)
    c.start_drag()
    c.drag_to(50, 600)
    c.release(-5000, 0)
    for _ in range(90):
        c.tick(DT, w, False)
        assert c.x >= 0
    assert c.platform is not None


def test_throw_clamped_at_top():
    w = world()
    c = make_cat()
    c.spawn(w)
    c.start_drag()
    c.drag_to(500, 600)
    c.release(0, -10000)
    for _ in range(120):
        c.tick(DT, w, False)
        assert c.y >= SPRITE
    assert c.platform is not None


def test_huge_dt_does_not_tunnel():
    w = world(win("a", 100, 500))
    c = make_cat()
    c.spawn(w)
    c.x, c.y, c.vx, c.vy = 400, 495, 0, 3000
    c.state, c.platform = "fall", None
    c.tick(10.0, w, False)
    assert c.platform is not None and c.platform.owner == "a"


def test_respawn_when_output_removed():
    w = world()
    c = make_cat()
    c.spawn(w)
    c.x = 2500
    c.platform = w.platform_by_owner_at("floor:DP-4", 2500)
    c.state, c._timer = "idle_sit", 100
    only_left = world(names=("DP-3",))
    c.tick(DT, only_left, False)
    assert c.platform.owner == "floor:DP-3"
    assert c.x == 960


def test_hidden_on_fullscreen_output():
    w = world()
    c = make_cat()
    c.spawn(w)
    fs = world(win("fs", 0, 0, 1920, 1080, stack=9, fs=True))
    c.tick(DT, fs, False)
    assert c.state == "hidden"
    assert not c.visible
    run(c, w, 2)
    assert c.visible
    assert c.platform is not None


def shake(cat, w, times, span=90):
    """Katze packen und `times` mal kräftig hin und her reißen."""
    cat.start_drag()
    x = cat.x
    for i in range(times + 1):
        cat.drag_to(x + (span if i % 2 else -span), cat.y)
        cat.tick(DT, w, False)
    cat.release(0, 0)


def test_shaking_makes_her_throw_up_and_clean_herself():
    w = world()
    c = make_cat(satiety=80)
    c.spawn(w)
    shake(c, w, 10)
    run(c, w, 1)                       # fallen und landen
    assert c.state == "vomit"
    assert c.needs.satiety == pytest.approx(55, abs=0.1)   # Verfall läuft nebenher
    run(c, w, 3)
    assert c.state == "groom"           # danach macht sie sich sauber


def test_gentle_dragging_does_not_upset_her():
    w = world()
    c = make_cat()
    c.spawn(w)
    c.start_drag()
    for i in range(40):                # ruhig quer über den Schirm tragen
        c.drag_to(c.x + 20, c.y)
        c.tick(DT, w, False)
    c.release(0, 0)
    run(c, w, 2)
    assert c.state != "vomit"


def test_shaking_slowly_is_forgotten():
    w = world()
    c = make_cat()
    c.spawn(w)
    c.start_drag()
    x = c.x
    for i in range(10):                # je ein Ruck, dann eine Sekunde Pause
        c.drag_to(x + (90 if i % 2 else -90), c.y)
        run(c, w, 1)
    c.release(0, 0)
    run(c, w, 2)
    assert c.state != "vomit"


def test_she_grooms_herself_now_and_then():
    w = world()
    c = make_cat()
    c.spawn(w)
    seen = set()
    for _ in range(int(300 / DT)):
        c.tick(DT, w, False)
        seen.add(c.state)
    assert "groom" in seen
    assert {"idle_sit", "walk"} <= seen      # putzen verdrängt die anderen Pausen nicht


def test_blocked_output_makes_her_walk_away():
    w = world(blocked=("DP-4",))
    c = make_cat()
    c.spawn(w)
    c.x = 2500          # z.B. dorthin geworfen oder Monitor nachträglich gesperrt
    run(c, w, 0.5)      # erst auf den Boden, dann los
    assert c.state == "flee" and c.facing == -1 and c.visible
    x = c.x
    run(c, w, 1)
    assert c.x < x - 100                      # zügig, nicht im Schritttempo
    run(c, w, 10)
    assert c.x < 1920 and c.state != "flee"   # angekommen und wieder normal


def test_flee_climbs_down_from_a_window_first():
    w = world(win("a", 2000, 400), blocked=("DP-4",))
    c = make_cat()
    c.spawn(w)
    put_on(c, w, "a", 2400)
    run(c, w, 1)
    assert c.platform.is_floor                # Sprung ueber die Grenze gibt es nicht
    run(c, w, 10)
    assert c.x < 1920


def test_flee_falls_back_to_teleport_without_a_path():
    outs = [Output("DP-3", Rect(0, 0, 1920, 1080), Rect(0, 44, 1920, 1036)),
            Output("DP-4", Rect(3000, 0, 1920, 1080), Rect(3000, 44, 1920, 1036))]
    w = World(outs, [], ["DP-4"])
    c = make_cat()
    c.spawn(w)
    c.x = 3900
    run(c, w, 1)
    assert c.state == "flee"                  # sie versucht es erst zu Fuss
    run(c, w, 10)
    assert c.x < 1920


def test_fullscreen_on_a_blocked_output_still_hides():
    w = world(win("fs", 1920, 0, 1920, 1080, stack=9, fs=True), blocked=("DP-4",))
    c = make_cat()
    c.spawn(w)
    c.x = 2500
    c.tick(DT, w, False)
    assert c.state == "hidden"


def test_spawn_avoids_blocked_output():
    w = world(blocked=("DP-3",))
    c = make_cat()
    c.home_output = "DP-3"
    c.spawn(w)
    assert c.platform.owner == "floor:DP-4"


def test_fullscreen_still_hides_her():
    """Vollbild ist vorübergehend: verstecken, nicht umziehen."""
    w = world(win("fs", 0, 0, 1920, 1080, stack=9, fs=True))
    c = make_cat()
    c.x, c.y = 960, 1080
    c.tick(DT, w, False)
    assert c.state == "hidden"


def test_sick_cat_goes_to_floor_and_lies():
    w = world(win("a", 100, 500))
    c = make_cat(satiety=5, affection=5)
    c.spawn(w)
    put_on(c, w, "a", 400)
    run(c, w, 3)
    assert c.needs.mood == Mood.SICK
    assert c.platform.is_floor
    assert c.state == "sick_lie"


def test_feed_triggers_eat():
    w = world()
    c = make_cat(satiety=30)
    c.spawn(w)
    c.feed()
    assert c.state == "eat"
    assert c.needs.satiety == 70
    run(c, w, 3.5)
    assert c.state != "eat"


def test_overfed_sits_lazily():
    w = world()
    c = make_cat(satiety=90)
    c.spawn(w)
    c.feed()
    run(c, w, 3.5)
    assert c.state == "idle_sit"
    run(c, w, 50)
    assert c.state == "idle_sit"


def test_pet_wakes_and_purrs():
    w = world()
    c = make_cat()
    c.spawn(w)
    c.go_sleep()
    assert c.state == "sleep"
    c.pet()
    assert c.state == "purr"
    assert c.needs.affection == 82


def test_sleeps_when_tired():
    w = world()
    c = make_cat(energy=10)
    c.spawn(w)
    run(c, w, 15)
    assert c.state == "sleep"


def test_call_to_floor_ignores_windows():
    w = world(win("a", 100, 500), win("b", 100, 800, stack=1))
    c = make_cat()
    c.spawn(w)
    put_on(c, w, "a", 400)
    c.call_to_floor()
    run(c, w, 2)
    assert c.platform.is_floor


def test_walks_across_monitors_and_avoids_forbidden():
    w = world()
    c = make_cat()
    c.spawn(w)
    c.x = 1900
    c.state, c.facing, c._timer = "walk", 1, 100
    run(c, w, 1)
    assert c.x > 1920 and c.platform.owner == "floor:DP-4"
    fs = world(win("fs", 1920, 0, 1920, 1080, stack=9, fs=True))
    c.spawn(fs)
    c.x = 1900
    c.state, c.facing, c._timer = "walk", 1, 100
    run(c, fs, 1)
    assert c.x <= 1920


def test_frame_key_flip_and_mood():
    w = world()
    c = make_cat(satiety=15)
    c.spawn(w)
    c.state, c.facing = "walk", -1
    c.needs.tick(0.1, "rest")
    anim, mood, frame, flip = c.frame_key(0.5)
    assert (anim, mood, flip) == ("walk", "sad", True)
    assert frame == 3
    c.state = "sick_lie"
    assert c.frame_key(0)[0] == "lie"
    c.state = "thrown"
    assert c.frame_key(0)[0] == "fall"


def test_spawn_prefers_home_output():
    w = world()
    c = make_cat()
    c.home_output = "DP-4"
    c.spawn(w)
    assert c.platform.owner == "floor:DP-4"
    c.home_output = "gone"
    c.spawn(w)
    assert c.platform.owner == "floor:DP-3"


def test_release_below_floor_lands_on_floor_of_same_output():
    w = world()
    c = make_cat()
    c.spawn(w)
    c.start_drag()
    c.drag_to(2500, 1150)
    c.release(0, 0)
    run(c, w, 1)
    assert c.platform.owner == "floor:DP-4"
    assert c.x == 2500


def test_jump_target_vanishing_does_not_teleport():
    w = world(win("a", 2300, 900, 400, 100))
    c = make_cat()
    c.spawn(w)
    c.x = 2400
    c.platform = w.platform_by_owner_at("floor:DP-4", 2400)
    c._jump_to(w.platform_by_owner_at("a", 2400))
    c.tick(DT, w, False)
    run(c, world(), 2)
    assert c.platform.owner == "floor:DP-4"
    assert abs(c.x - 2400) < 400


def test_no_jumps_to_edges_near_top():
    w = world(win("top", 100, 100, 800, 400))
    c = make_cat()
    c.spawn(w)
    c.x, c.y = 500, 380
    c.platform = None
    assert all(p.owner != "top" for p in c._jump_targets(w, w.platform_by_owner_at("floor:DP-3", 500)))


def test_throw_speed_capped():
    c = make_cat()
    c.release(1e9, -1e9)
    assert abs(c.vx) <= 4000 and abs(c.vy) <= 4000


def test_drag_without_release_times_out():
    w = world()
    c = make_cat()
    c.spawn(w)
    c.start_drag()
    c.drag_to(500, 600)
    run(c, w, 6)
    assert c.state != "dragged"
    assert c.platform is not None


# --- Klettern, Riesensprung, Unterkanten ---

def run_until(cat, w, cond, seconds):
    """Tickt bis cond(cat) wahr ist; liefert True, falls erreicht."""
    for _ in range(int(seconds / DT)):
        cat.tick(DT, w, False)
        if cond(cat):
            return True
    return False


def wall(w, owner, side):
    return next(x for x in w.walls if x.owner == owner and x.side == side)


def on(owner):
    return lambda c: c.platform is not None and c.platform.owner == owner and c.state not in ("fall", "jump")


def test_climb_reaches_top():
    w = world(win("a", 300, 400, 400, 680))
    c = make_cat()
    c.spawn(w)
    c.x = 200
    c.start_climb(w, wall(w, "a", -1))
    assert run_until(c, w, lambda c: c.state == "climb", 3)
    assert run_until(c, w, on("a"), 15)
    assert c.y == 400


def test_climb_leaps_to_floating_wall():
    w = world(win("a", 300, 300, 400, 600))
    c = make_cat()
    c.spawn(w)
    c.x = 800
    c.start_climb(w, wall(w, "a", 1))
    assert run_until(c, w, lambda c: c.state == "climb", 5)
    assert c.x == 700 + 18
    assert run_until(c, w, on("a"), 15)


def test_climb_onto_unwalkable_top_falls():
    w = world(win("a", 300, 44, 400, 1036))
    c = make_cat()
    c.spawn(w)
    c.x = 200
    c.start_climb(w, wall(w, "a", -1))
    assert run_until(c, w, lambda c: c.state == "climb", 3)
    assert run_until(c, w, lambda c: c.state in ("fall", "jump"), 20)
    assert run_until(c, w, on("floor:DP-3"), 5)


def test_climb_rides_moving_window():
    w = world(win("a", 300, 400, 400, 680))
    c = make_cat()
    c.spawn(w)
    c.x = 200
    c.start_climb(w, wall(w, "a", -1))
    run_until(c, w, lambda c: c.state == "climb", 3)
    x = c.x
    c.tick(DT, world(win("a", 350, 400, 400, 680)), False)
    assert c.x == x + 50


def test_climb_window_gone_falls():
    w = world(win("a", 300, 400, 400, 680))
    c = make_cat()
    c.spawn(w)
    c.x = 200
    c.start_climb(w, wall(w, "a", -1))
    run_until(c, w, lambda c: c.state == "climb", 3)
    assert run_until(c, world(), on("floor:DP-3"), 3)


def test_call_to_floor_while_climbing():
    w = world(win("a", 300, 400, 400, 680))
    c = make_cat()
    c.spawn(w)
    c.x = 200
    c.start_climb(w, wall(w, "a", -1))
    run_until(c, w, lambda c: c.state == "climb", 3)
    c.call_to_floor()
    assert run_until(c, w, on("floor:DP-3"), 3)


def test_giant_jump_reaches_high_edge():
    w = world(win("a", 300, 200, 400, 300))
    c = make_cat()
    c.spawn(w)
    c.x = 500
    assert any(p.owner == "a" for p in c._jump_targets(w, c.platform))


def test_hang_then_fall():
    w = world(win("a", 300, 400, 400, 450))
    c = make_cat()
    c.spawn(w)
    c.x = 500
    c.start_hang(w, next(x for x in w.ceilings if x.owner == "a"))
    assert run_until(c, w, lambda c: c.state == "hang", 2)
    assert c.y == 850 + HANG_DROP
    assert c.frame_key(0)[0] == "hang"
    assert run_until(c, w, on("floor:DP-3"), 5)


def test_climb_frame_and_facing():
    w = world(win("a", 300, 400, 400, 680))
    c = make_cat()
    c.spawn(w)
    c.x = 800
    c.start_climb(w, wall(w, "a", 1))
    run_until(c, w, lambda c: c.state == "climb", 5)
    anim, _, _, flip = c.frame_key(0)
    assert anim == "climb" and flip


def test_sick_never_climbs_or_hangs():
    w = world(win("a", 300, 400, 400, 680), win("b", 1000, 400, 400, 450))
    c = make_cat(satiety=5, affection=5)
    c.spawn(w)
    for _ in range(int(60 / DT)):
        c.tick(DT, w, False)
        assert c.state not in ("climb", "hang", "jump", "approach")


def test_cat_uses_new_moves_on_its_own():
    w = world(win("a", 300, 300, 400, 780), win("b", 1000, 400, 400, 450))
    seen = set()
    for seed in range(5):
        c = Cat(Needs(), random.Random(seed))
        c.spawn(w)
        c.x = 900
        for _ in range(int(120 / DT)):
            c.tick(DT, w, False)
            seen.add(c.state)
    assert {"climb", "hang"} <= seen


# --- Spielen: Mauszeiger jagen ---

def play(cat, w, seconds, cursor, wiggling=True, until=None):
    """Tickt mit festem Cursor; cursor als Funktion(cat) oder Tupel."""
    for _ in range(int(seconds / DT)):
        pos = cursor(cat) if callable(cursor) else cursor
        cat.tick(DT, w, False, cursor=pos, wiggling=wiggling)
        if until and until(cat):
            return True
    return False


def floor_cat(**needs):
    w = world()
    c = make_cat(**needs)
    c.spawn(w)  # x=960, y=1080
    return w, c


def test_play_chases_far_cursor():
    w, c = floor_cat()
    assert play(c, w, 0.5, (1260, 1060), until=lambda c: c.state == "chase")
    x = c.x
    play(c, w, 0.5, (1260, 1060))
    assert c.x > x + 50


def test_play_crouches_then_pounces():
    w, c = floor_cat()
    assert play(c, w, 0.5, (1080, 1030), until=lambda c: c.state == "crouch")
    assert c.facing == 1
    assert play(c, w, 1.5, (1080, 1030), until=lambda c: c.state == "jump")
    assert c.frame_key(0)[0] == "jump"


def test_pounce_catch_rewards_and_cheers():
    w, c = floor_cat(affection=50)
    assert play(c, w, 4, (1060, 1000), until=lambda c: c.state == "cheer")
    assert c.needs.affection >= 52.9
    assert c.frame_key(0)[0] == "cheer"


def test_swipe_up_at_cursor_above():
    w, c = floor_cat()
    assert play(c, w, 1.5, (970, 830), until=lambda c: c.state == "jump")
    assert c.frame_key(0)[0] == "swipe"


def test_no_play_when_sick():
    w, c = floor_cat(satiety=5, affection=5)
    play(c, w, 3, (1080, 1030))
    assert c.state == "sick_lie"


def test_no_play_when_sleeping_or_tired():
    w, c = floor_cat(energy=50)  # bei >= 80 wacht sie sofort auf
    c.go_sleep()
    play(c, w, 2, (1080, 1030))
    assert c.state == "sleep"
    w, c = floor_cat(energy=10)
    for _ in range(int(3 / DT)):
        c.tick(DT, w, False, cursor=(1080, 1030), wiggling=True)
        assert c.state not in ("crouch", "chase")


def test_play_ends_without_wiggle():
    w, c = floor_cat()
    play(c, w, 0.3, (1260, 1060), until=lambda c: c.state == "chase")
    play(c, w, 2.5, (1260, 1060), wiggling=False)
    assert c.state not in ("chase", "crouch")


def test_play_dives_off_window_edge():
    w = world(win("a", 400, 600))
    c = make_cat()
    c.spawn(w)
    put_on(c, w, "a", 800)
    assert c.y == 600
    assert play(c, w, 4, (820, 800), until=lambda c: c.platform is not None and c.platform.is_floor)


def test_play_dives_off_panel_to_floor():
    w = world(win("dock", 600, 1016, 692, 64, stack=10, panel=True))
    c = make_cat()
    c.spawn(w)
    put_on(c, w, "dock", 900)
    assert c.y == 1016
    assert play(c, w, 4, (920, 1060), until=lambda c: c.platform is not None and c.platform.is_floor)


def test_play_never_dives_through_the_floor():
    w, c = floor_cat()
    for _ in range(int(4 / DT)):
        c.tick(DT, w, False, cursor=(990, 1140), wiggling=True)
        assert c.y <= 1080


def test_play_does_not_interrupt_climb():
    w = world(win("a", 300, 400, 400, 680))
    c = make_cat()
    c.spawn(w)
    c.x = 200
    c.start_climb(w, wall(w, "a", -1))
    run_until(c, w, lambda c: c.state == "climb", 3)
    play(c, w, 1, (250, 900))
    assert c.state == "climb"


def test_every_state_has_a_sprite_animation():
    import re
    from pathlib import Path

    from taskbar_cat import sprites

    src = Path(__file__).resolve().parent.parent.joinpath("taskbar_cat/cat.py").read_text()
    states = set(re.findall(r'self\.state = "(\w+)"', src)) | set(re.findall(r'self\._set\("(\w+)"', src))
    c = make_cat()
    for s in states | {"thrown", "hidden"}:
        c.state = s
        assert c.frame_key(0)[0] in sprites.ANIMS, s


def test_walk_speed_from_config():
    cfg = Config()
    cfg.set("walk_speed", 120)
    w = world()
    c = make_cat(cfg)
    c.spawn(w)
    c.facing = 1
    c._set("walk", 10)
    start = c.x
    run(c, w, 1)
    assert c.x - start == pytest.approx(120, abs=6)   # Standard waere 60 px/s


def test_sprite_size_follows_config():
    cfg = Config()
    c = make_cat(cfg)
    assert c.sprite == SPRITE
    cfg.set("sprite_scale", 5)
    assert c.sprite == 160


def test_play_can_be_switched_off():
    cfg = Config()
    cfg.set("play_enabled", False)
    w = world()
    c = make_cat(cfg)
    c.spawn(w)
    for _ in range(30):
        c.tick(DT, w, False, cursor=(c.x + 60, c.y - 40), wiggling=True)
    assert c.state not in ("chase", "crouch", "jump")


def test_jump_probability_zero_keeps_her_grounded():
    cfg = Config()
    for name in ("p_jump", "p_climb", "p_hang"):
        cfg.set(name, 0)
    w = world(win("a", 200, 700))
    c = make_cat(cfg)
    c.spawn(w)
    run(c, w, 120)
    assert c.platform.is_floor
