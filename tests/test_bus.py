import json

from taskbar_cat.bus import CatBus
from taskbar_cat.config import Config

UPDATE = {
    "outputs": [{"name": "DP-3", "geometry": {"x": 0, "y": 0, "w": 1920, "h": 1080},
                 "workArea": {"x": 0, "y": 44, "w": 1920, "h": 1036}}],
    "windows": [],
}


def test_latest_world_coalesces(qapp):
    bus = CatBus()
    for h in (900, 1000, 1036):
        d = json.loads(json.dumps(UPDATE))
        d["outputs"][0]["workArea"]["h"] = h
        bus.adaptor.update(json.dumps(d))
    w = bus.latest_world()
    assert w.outputs[0].work_area.h == 1036
    assert bus.latest_world() is None
    assert bus.sensor_ok


def test_invalid_json_ignored(qapp):
    bus = CatBus()
    bus.adaptor.update("{kaputt")
    assert bus.latest_world() is None
    assert not bus.sensor_ok


class _FailingScripting:
    def call(self, method, *args):
        from PyQt6.QtDBus import QDBusMessage
        return QDBusMessage.createError("org.example.Fail", "nope")


def test_watchdog_runs_even_if_load_fails(qapp):
    bus = CatBus()
    bus._scripting = lambda: _FailingScripting()
    bus.load_sensor()
    assert bus._watchdog.isActive()


def test_cursor_samples(qapp):
    bus = CatBus()
    bus.adaptor.cursor("10 20")
    bus.adaptor.cursor("kaputt")
    bus.adaptor.cursor("30.5 40")
    samples = bus.take_cursor_samples()
    assert [(x, y) for x, y, _ in samples] == [(10, 20), (30.5, 40)]
    assert bus.take_cursor_samples() == []


def test_blocked_outputs_from_config_and_refresh(qapp):
    two = json.loads(json.dumps(UPDATE))
    two["outputs"].append({"name": "DP-4", "geometry": {"x": 1920, "y": 0, "w": 1920, "h": 1080},
                           "workArea": {"x": 1920, "y": 44, "w": 1920, "h": 1036}})
    bus = CatBus()
    bus.cfg = Config()
    bus.adaptor.update(json.dumps(two))
    assert bus.latest_world().forbidden_outputs == set()
    bus.cfg.set("blocked_outputs", ["DP-4"])
    assert bus.latest_world() is None        # ohne neues Sensor-Update passiert nichts
    bus.refresh()
    assert bus.latest_world().forbidden_outputs == {"DP-4"}
