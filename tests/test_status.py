import json
import random

from taskbar_cat import __main__ as app
from taskbar_cat import bus, status
from taskbar_cat.cat import Cat
from taskbar_cat.needs import Mood, Needs


def cat(**kw):
    return Cat(Needs(**kw), random.Random(1))


def test_one_line_is_compact():
    line = status.one_line(status.snapshot(cat(satiety=72.4, affection=55.6, energy=80)))
    assert line == "Sättigung 72% | Zuneigung 56% | Energie 80% | zufrieden"


def test_flags_are_shown():
    c = cat(satiety=5, affection=5)
    c.needs.mood = Mood.SICK
    c.paused = True
    line = status.one_line(status.snapshot(c))
    assert "krank" in line and "(pausiert)" in line


def test_stored_state_is_marked_as_not_running():
    d = status.from_needs(Needs())
    assert d["running"] is False
    assert "(nicht gestartet)" in status.one_line(d)


def test_lines_warn_about_missing_sensor():
    out = status.lines(status.snapshot(cat(), sensor_ok=False))
    assert any("Fenster-Sensor" in line for line in out)
    assert len(out) == 5


def test_json_keeps_raw_values():
    d = json.loads(status.as_json(status.snapshot(cat(satiety=72.4))))
    assert d["satiety"] == 72.4 and d["mood"] == "zufrieden"


def test_adaptor_serves_provider(qapp):
    b = bus.CatBus()
    assert json.loads(b.adaptor.status()) == {}
    b.status_provider = lambda: {"satiety": 1}
    assert json.loads(b.adaptor.status()) == {"satiety": 1}


def test_query_returns_none_without_service(qapp, monkeypatch):
    monkeypatch.setattr(bus, "SERVICE", "de.bangl.NichtDa")
    assert bus.query_status(timeout_ms=200) is None


def test_cli_flags():
    args = app.parse_args(["taskbar-cat", "--status", "--json"])
    assert args.status and args.json
    assert app.parse_args(["taskbar-cat"]).status is False


def test_print_status_uses_live_data(capsys, monkeypatch):
    monkeypatch.setattr(app, "bus_query", lambda: {"satiety": 10, "affection": 20,
                                                   "energy": 30, "mood": "traurig"})
    assert app.print_status(False) == 0
    assert capsys.readouterr().out.strip() == "Sättigung 10% | Zuneigung 20% | Energie 30% | traurig"


def test_print_status_falls_back_to_state_file(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(app, "bus_query", lambda: None)
    assert app.print_status(True) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["running"] is False and d["satiety"] == 80
