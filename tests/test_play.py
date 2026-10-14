from taskbar_cat.play import WiggleDetector

CAT = (1000, 900)  # Mittelpunkt der Katze


def feed(det, points, t0=0.0, step=1 / 30):
    t = t0
    for x, y in points:
        det.feed(x, y, t)
        t += step
    return t - step


def zigzag(cx, cy, amp, n):
    return [(cx + (amp if i % 2 else -amp), cy) for i in range(n)]


def test_wiggle_near_detected():
    d = WiggleDetector()
    t = feed(d, zigzag(1050, 880, 60, 20))
    assert d.is_wiggling(*CAT, t)


def test_slow_movement_ignored():
    d = WiggleDetector()
    t = feed(d, [(1000 + i, 880) for i in range(30)])
    assert not d.is_wiggling(*CAT, t)


def test_straight_fast_movement_ignored():
    d = WiggleDetector()
    t = feed(d, [(700 + i * 30, 880) for i in range(25)])
    assert not d.is_wiggling(*CAT, t)


def test_far_cursor_ignored():
    d = WiggleDetector()
    t = feed(d, zigzag(1500, 880, 60, 20))
    assert not d.is_wiggling(*CAT, t)


def test_jitter_ignored():
    d = WiggleDetector()
    t = feed(d, zigzag(1000, 880, 2, 60))
    assert not d.is_wiggling(*CAT, t)


def test_stale_samples_expire():
    d = WiggleDetector()
    t = feed(d, zigzag(1050, 880, 60, 20))
    assert not d.is_wiggling(*CAT, t + 1.5)


def test_last_position():
    d = WiggleDetector()
    assert d.last is None
    d.feed(5, 6, 0.0)
    assert d.last == (5, 6)


def test_wiggle_over_cat_is_petting_not_play():
    d = WiggleDetector()
    t = feed(d, zigzag(1000, 880, 30, 30))
    assert d.is_wiggling(*CAT, t)
    assert not d.is_wiggling(*CAT, t, avoid=(952, 852, 1048, 948))
