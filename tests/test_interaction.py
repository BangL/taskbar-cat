import pytest

from taskbar_cat.interaction import DragTracker, RubDetector


def rub(det, xs, t0=0.0, step=0.1):
    return [det.feed_motion(x, t0 + i * step) for i, x in enumerate(xs)]


def test_rub_needs_three_reversals():
    d = RubDetector()
    res = rub(d, [0, 10, 0, 10, 0])
    assert res == [False, False, False, False, True]


def test_rub_resets_after_detection():
    d = RubDetector()
    rub(d, [0, 10, 0, 10, 0])
    assert not any(rub(d, [10, 0, 10], t0=1.0))


def test_rub_ignores_jitter_below_4px():
    d = RubDetector()
    assert not any(rub(d, [0, 2, 0, 2, 0, 2, 0, 2]))


def test_rub_window_1s():
    d = RubDetector()
    assert not any(rub(d, [0, 10, 0, 10, 0], step=0.4))


def test_drag_threshold_6px():
    d = DragTracker()
    d.press(100, 100, 0.0)
    assert d.move(104, 103, 0.01) is False
    assert not d.is_dragging
    assert d.move(107, 100, 0.02) is True
    assert d.is_dragging


def test_velocity_last_100ms():
    d = DragTracker()
    d.press(0, 0, 0.0)
    d.move(500, 0, 0.5)
    d.move(510, 0, 0.55)
    d.move(520, -10, 0.6)
    vx, vy = d.velocity()
    assert vx == pytest.approx(200, rel=0.01)
    assert vy == pytest.approx(-100, rel=0.01)


def test_velocity_zero_without_motion():
    d = DragTracker()
    d.press(0, 0, 0.0)
    assert d.velocity() == (0.0, 0.0)
