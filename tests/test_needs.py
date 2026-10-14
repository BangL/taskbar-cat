import pytest

from taskbar_cat.needs import AFFECTION_DECAY, SATIETY_DECAY, Mood, Needs


def run(n, seconds, activity="rest", step=5.0):
    t = 0.0
    while t < seconds:
        d = min(step, seconds - t)
        n.tick(d, activity)
        t += d


def test_satiety_empty_after_8h():
    n = Needs(satiety=100, affection=100)
    run(n, 8 * 3600)
    assert n.satiety == pytest.approx(0, abs=0.5)


def test_affection_empty_after_4h():
    n = Needs(satiety=100, affection=100)
    run(n, 4 * 3600)
    assert n.affection == pytest.approx(0, abs=0.5)


@pytest.mark.parametrize("activity,delta", [("active", -1), ("rest", -0.2), ("sleep", 2)])
def test_energy_rates(activity, delta):
    n = Needs(energy=50)
    run(n, 60, activity)
    assert n.energy == pytest.approx(50 + delta)


def test_feed_adds_40_and_caps():
    n = Needs(satiety=70)
    assert n.feed() is True
    assert n.satiety == 100
    n = Needs(satiety=30)
    assert n.feed() is False
    assert n.satiety == 70


def test_pet_adds_2():
    n = Needs(affection=50)
    n.pet()
    assert n.affection == 52


def test_sad_below_20():
    n = Needs(satiety=19, affection=80)
    n.tick(0.1, "rest")
    assert n.mood == Mood.SAD


def test_sick_both_below_10():
    n = Needs(satiety=9, affection=9)
    n.tick(0.1, "rest")
    assert n.mood == Mood.SICK


def test_sick_after_2h_below_10():
    n = Needs(satiety=5, affection=100)
    run(n, 7100)
    assert n.mood == Mood.SAD
    run(n, 101)
    assert n.mood == Mood.SICK


def test_low_counter_resets_above_10():
    n = Needs(satiety=5, affection=100)
    run(n, 100)
    assert n.low_satiety_s > 0
    n.feed()
    n.tick(0.1, "rest")
    assert n.low_satiety_s == 0


def test_recovery_needs_both_40():
    n = Needs(satiety=5, affection=5)
    n.tick(0.1, "rest")
    assert n.mood == Mood.SICK
    n.satiety = n.affection = 35
    n.tick(0.1, "rest")
    assert n.mood == Mood.SICK
    n.satiety = n.affection = 41
    n.tick(0.1, "rest")
    assert n.mood == Mood.NORMAL


def test_huge_dt_is_capped():
    n = Needs(satiety=80)
    n.tick(3600, "rest")
    assert n.satiety == pytest.approx(80 - 5 * SATIETY_DECAY)


def test_roundtrip_dict():
    n = Needs(satiety=12.5, affection=33, energy=70, low_satiety_s=10, mood=Mood.SAD)
    assert Needs.from_dict(n.to_dict()) == n


def test_from_dict_clamps_and_ignores_unknown():
    n = Needs.from_dict({"satiety": 150, "affection": -3, "bogus": 1})
    assert n.satiety == 100
    assert n.affection == 0
    assert n.energy == 80
