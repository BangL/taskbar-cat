"""Start: python3 -m taskbar_cat [--debug] bzw. taskbar-cat"""
import argparse
import random
import signal
import sys
import time

from PyQt6.QtCore import QTimer
from PyQt6.QtQml import QQmlEngine
from PyQt6.QtWidgets import QApplication

from . import __version__, paths, sprites, storage
from .guard import guarded
from .bus import CatBus
from .cat import SPRITE, Cat
from .play import WiggleDetector
from .ui.overlay import OverlayManager
from .ui.tray import CatTray
from .world import Rect, World

TICK_MS = 33
SAVE_MS = 60_000
TRAY_MS = 1_000
DRAG_GRAB_OFFSET = 75  # Cursor greift die Katze am Nacken


def _rect(r) -> Rect:
    return Rect(r.x(), r.y(), r.width(), r.height())


def fallback_world(app: QApplication) -> World:
    return World.from_screens([(s.name(), _rect(s.geometry()), _rect(s.availableGeometry()))
                               for s in app.screens()])


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="taskbar-cat",
        description="Pixel-Art-Tamagotchi-Katze, die auf dem Boden der Arbeitsfläche "
                    "und auf Fensteroberkanten lebt (KDE Plasma 6 / Wayland).",
        epilog="Zustand: $XDG_DATA_HOME/taskbar-cat/state.json. "
               "Fenster-Sensor einzeln testen: python3 -m taskbar_cat.bus --dump")
    p.add_argument("--debug", action="store_true",
                   help="Plattformen (gelb/magenta), Wände (cyan) und Decken (rot) als Linien einblenden")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p.parse_args(argv[1:])


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    args = parse_args(argv)
    debug = args.debug
    app = QApplication(argv[:1])
    app.setApplicationName("taskbar-cat")
    app.setQuitOnLastWindowClosed(False)

    bus = CatBus()
    if not bus.register():
        print("taskbar-cat: läuft bereits", file=sys.stderr)
        return 0

    state_file = paths.state_file()
    cat = Cat(storage.load(state_file), random.Random())
    cat.home_output = app.primaryScreen().name()
    state = {"world": fallback_world(app), "last": time.monotonic()}
    wiggle = WiggleDetector()
    cat.spawn(state["world"])
    bus.load_sensor()

    engine = QQmlEngine()
    overlays = OverlayManager(engine, sprites.ensure_atlas(paths.cache_dir()), debug)
    tray = CatTray(cat)

    overlays.petted.connect(guarded(cat.pet))
    overlays.rightClicked.connect(guarded(lambda pos: tray.menu().popup(pos)))
    overlays.dragStarted.connect(guarded(cat.start_drag))
    def drag_moved(x, y):
        if cat.state != "dragged":  # nach Drag-Timeout wieder aufnehmen
            cat.start_drag()
        cat.drag_to(x, y + DRAG_GRAB_OFFSET)

    overlays.dragMoved.connect(guarded(drag_moved))
    overlays.released.connect(guarded(cat.release))
    tray.feedRequested.connect(guarded(cat.feed))
    tray.petRequested.connect(guarded(cat.pet))
    tray.sleepRequested.connect(guarded(cat.go_sleep))
    tray.floorRequested.connect(guarded(cat.call_to_floor))
    tray.pauseToggled.connect(guarded(cat.set_paused))
    tray.quitRequested.connect(guarded(app.quit))

    def tick():
        now = time.monotonic()
        dt, state["last"] = now - state["last"], now
        world = bus.latest_world()
        if world is not None:
            state["world"] = world
        for x, y, t in bus.take_cursor_samples():
            wiggle.feed(x, y, t)
        sprite = (cat.x - SPRITE / 2, cat.y - SPRITE, cat.x + SPRITE / 2, cat.y)
        wiggling = wiggle.is_wiggling(cat.x, cat.y - SPRITE / 2, now, avoid=sprite)
        cat.tick(dt, state["world"], bus.locked, cursor=wiggle.last, wiggling=wiggling)
        overlays.render(cat, state["world"], now)

    def save():
        storage.try_save(state_file, cat.needs)

    def quit_():
        save()
        bus.unload_sensor()

    timers = []
    for ms, fn in ((TICK_MS, tick), (SAVE_MS, save), (TRAY_MS, lambda: tray.refresh(bus.sensor_ok))):
        t = QTimer()
        t.timeout.connect(guarded(fn))
        t.start(ms)
        timers.append(t)
    tray.refresh(True)
    app.aboutToQuit.connect(guarded(quit_))
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: app.quit())
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
