import colorsys
import random

import pytest

from taskbar_cat import ufo
from taskbar_cat.cat import Cat
from taskbar_cat.config import FUR_PRESETS
from taskbar_cat.needs import Needs
from taskbar_cat.world import Output, Rect, World

DT = 1 / 30


def world():
    return World([Output("DP-3", Rect(0, 0, 1920, 1080), Rect(0, 44, 1920, 1036))], [])


def hsv(color):
    return colorsys.rgb_to_hsv(*(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)))


@pytest.fixture
def often(monkeypatch):
    """UFO praktisch sofort statt alle paar Stunden."""
    monkeypatch.setattr(ufo, "PER_HOUR", 3600 * 1000)


def calm_cat(w):
    c = Cat(Needs(), random.Random(1))
    c.spawn(w)
    return c


def abduct(c, w, seconds=40, each=None):
    """Tickt, bis das UFO wieder weg ist; liefert die gesehenen Phasen."""
    phases = []
    for _ in range(int(seconds / DT)):
        c.tick(DT, w, False)
        phase = c.ufo.phase if c.ufo else None
        if not phases or phases[-1] != phase:
            phases.append(phase)
        if each:
            each(c)
        if phase is None and len(phases) > 1:
            break
    return phases


def test_next_fur_turns_hue_and_keeps_shade():
    rng = random.Random(3)
    for _ in range(50):
        new = ufo.next_fur("#e8913a", rng)
        h0, s0, v0 = hsv("#e8913a")
        h1, s1, v1 = hsv(new)
        turn = abs(h1 - h0) * 360
        assert ufo.MIN_HUE_STEP - 1 <= min(turn, 360 - turn)
        assert s1 == pytest.approx(s0, abs=0.01) and v1 == pytest.approx(v0, abs=0.01)


def test_next_fur_grey_or_invalid_gets_preset():
    rng = random.Random(3)
    for grey in ("#d8d8d8", "#2e2e2e"):
        for _ in range(20):
            new = ufo.next_fur(grey, rng)
            assert new in FUR_PRESETS and new != grey
    assert ufo.next_fur("kaputt", rng) in FUR_PRESETS


def test_full_abduction(often):
    w = world()
    c = calm_cat(w)
    seen = set()
    phases = abduct(c, w, each=lambda c: seen.add((c.state, c.visible)))
    assert phases == [*ufo.HOLDING, "depart", None]
    assert ("abducted", False) in seen and ("beamed", True) in seen
    assert c.platform is not None and c.platform.is_floor and c.y == 1080


def test_quiet_after_a_visit(often):
    w = world()
    c = calm_cat(w)
    abduct(c, w)
    for _ in range(int(60 / DT)):
        c.tick(DT, w, False)
    assert c.ufo is None
    c._ufo_quiet = 0
    c._set("idle_sit", 10)
    c.tick(DT, w, False)
    assert c.ufo is not None


def test_new_fur_is_handed_out_once(often):
    w = world()
    c = calm_cat(w)
    furs = []
    abduct(c, w, each=lambda c: furs.append(c.take_new_fur()))
    got = [f for f in furs if f]
    assert len(got) == 1 and got[0] != c.cfg.fur_color


def test_no_interaction_while_abducted(often):
    w = world()
    c = calm_cat(w)
    c.tick(DT, w, False)
    assert c.abducted
    satiety = c.needs.satiety
    c.start_drag()
    c.drag_to(100, 100)
    c.release(500, -500)
    c.feed()
    c.go_sleep()
    assert c.state == "beamed" and c.needs.satiety == satiety and (c.x, c.y) != (100, 100)


def test_no_ufo_when_locked_or_busy(often):
    w = world()
    c = calm_cat(w)
    for _ in range(30):
        c.tick(DT, w, True)
    assert c.ufo is None
    c.start_drag()
    for _ in range(30):
        c.tick(DT, w, False)
    assert c.ufo is None


def test_ufo_does_not_change_regular_behaviour(monkeypatch):
    """Der UFO-Würfel nutzt eigenen Zufall: ohne UFO bleibt der Ablauf gleich."""
    monkeypatch.setattr(ufo, "PER_HOUR", 0)
    w = world()
    a, b = calm_cat(w), Cat(Needs(), random.Random(1))
    b.spawn(w)
    b.ufo_rng = random.Random(99)
    for _ in range(int(60 / DT)):
        a.tick(DT, w, False)
        b.tick(DT, w, False)
    assert (a.state, a.x) == (b.state, b.x)
