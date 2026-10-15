"""Start: python3 -m taskbar_cat [--debug] bzw. taskbar-cat"""
import argparse
import random
import signal
import sys
import time

from PyQt6.QtCore import QTimer
from PyQt6.QtQml import QQmlEngine
from PyQt6.QtWidgets import QApplication, QInputDialog, QMenu

from . import __version__, backend as backends, paths, sprites, status, storage
from .guard import guarded
from .bus import CatBus, query_status as bus_query
from .cat import Cat
from .furniture import BOWL_PORTIONS
from .bigtree import is_tree
from .play import WiggleDetector
from .ui.collection import CollectionDialog
from .ui.inventory import InventoryDialog
from .ui.overlay import OverlayManager
from .ui.settings import SettingsDialog
from .ui.tray import CatTray
from .world import Rect, World

TICK_MS = 33
SAVE_MS = 60_000
TRAY_MS = 1_000
DRAG_GRAB_FACTOR = 0.78  # Cursor greift die Katze am Nacken


def _rect(r) -> Rect:
    return Rect(r.x(), r.y(), r.width(), r.height())


def fallback_world(app: QApplication, blocked: list[str] | tuple = ()) -> World:
    return World.from_screens([(s.name(), _rect(s.geometry()), _rect(s.availableGeometry()))
                               for s in app.screens()], blocked)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="taskbar-cat",
        description="Pixel-Art-Tamagotchi-Katze, die auf dem Boden der Arbeitsfläche "
                    "und auf Fensteroberkanten lebt (KDE Plasma 6 / Wayland, GNOME).",
        epilog="Zustand: $XDG_DATA_HOME/taskbar-cat/state.json. "
               "Fenster-Sensor einzeln testen: python3 -m taskbar_cat.bus --dump")
    p.add_argument("--debug", action="store_true",
                   help="Plattformen (gelb/magenta), Wände (cyan) und Decken (rot) als Linien einblenden")
    p.add_argument("--status", action="store_true",
                   help="Status der laufenden Katze ausgeben und beenden (für fastfetch o.ä.)")
    p.add_argument("--json", action="store_true", help="mit --status: Ausgabe als JSON")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p.parse_args(argv[1:])


def print_status(as_json: bool) -> int:
    """Live über D-Bus, sonst aus dem gespeicherten Zustand."""
    data = bus_query()
    if data is None:
        data = status.from_needs(storage.load(paths.state_file()))
    print(status.as_json(data) if as_json else status.one_line(data))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    args = parse_args(argv)
    if args.status:
        return print_status(args.json)
    debug = args.debug
    backends.prepare_qt()   # Backend wählen und QT_QPA_PLATFORM setzen, vor der QApplication
    app = QApplication(argv[:1])
    app.setApplicationName("taskbar-cat")
    app.setQuitOnLastWindowClosed(False)

    bus = CatBus()
    if not bus.register():
        print("taskbar-cat: läuft bereits", file=sys.stderr)
        return 0

    state_file = paths.state_file()
    cfg_file = paths.config_file()
    cfg = storage.load_config(cfg_file)
    furniture_file = paths.furniture_file()
    cat = Cat(storage.load(state_file), random.Random(), cfg)
    cat.furniture = furniture = storage.load_furniture(furniture_file)
    bus.cfg = cfg
    bus.status_provider = lambda: status.snapshot(cat, bus.sensor_ok)
    cat.home_output = app.primaryScreen().name()
    state = {"world": fallback_world(app, cfg.blocked_outputs), "last": time.monotonic()}
    wiggle = WiggleDetector()
    cat.spawn(state["world"])
    bus.load_sensor()

    engine = QQmlEngine()
    overlays = OverlayManager(engine, sprites.ensure_atlas(paths.cache_dir(), cfg.fur_color, cfg.tabby),
                              debug or cfg.debug_lines, sprites.ensure_ufo(paths.cache_dir()),
                              sprites.ensure_furniture(paths.cache_dir()),
                              backend=bus.backend)
    tray = CatTray(cat, cfg.fur_color)

    overlays.petted.connect(guarded(cat.pet))
    overlays.rightClicked.connect(guarded(lambda pos: tray.menu().popup(pos)))
    overlays.dragStarted.connect(guarded(cat.start_drag))
    def drag_moved(x, y):
        if cat.state != "dragged":  # nach Drag-Timeout wieder aufnehmen
            cat.start_drag()
        cat.drag_to(x, y + cat.sprite * DRAG_GRAB_FACTOR)

    overlays.dragMoved.connect(guarded(drag_moved))
    overlays.released.connect(guarded(cat.release))

    def half_width(kind: str) -> float:
        return furniture.half_width(kind, cat.sprite)

    def furniture_changed() -> None:
        storage.try_save(furniture_file, furniture)
        if state.get("inventory") is not None:
            state["inventory"].refresh()

    def feed() -> None:
        """Steht ein erreichbarer Napf, kommt das Futter dort hinein."""
        if furniture.fill(state["world"]):
            furniture_changed()
        else:
            cat.feed()

    def place(kind: str) -> None:
        # neben die Katze, auf der Seite, in die sie schaut; fällt von dort auf die Kante darunter
        furniture.place(kind, state["world"], cat.x + cat.facing * cat.sprite, cat.y - cat.sprite,
                        half_width(kind))
        furniture_changed()

    def store(kind: str) -> None:
        furniture.store(kind)
        furniture_changed()

    def move_furniture(kind: str, x: float, y: float) -> None:
        # Gespeichert wird mit dem nächsten save(), nicht bei jedem Mausschritt
        furniture.put(kind, state["world"], x, y, half_width(kind))

    def show_inventory() -> None:
        dlg = state.get("inventory")
        if dlg is None:
            dlg = state["inventory"] = InventoryDialog(furniture)
            dlg.placeRequested.connect(guarded(place))
            dlg.storeRequested.connect(guarded(store))
        dlg.refresh()
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    variants_file = paths.bigtree_variants_file()

    def add_bigtree(variant: dict | None = None, x: float | None = None, y: float | None = None) -> None:
        """Neben die Katze (bzw. bei x, y) fallen lassen."""
        if x is None:
            x, y = cat.x + cat.facing * cat.sprite * 1.5, cat.y - cat.sprite * 2
        furniture.add_tree(x, y, variant)
        furniture_changed()

    def show_collection() -> None:
        dlg = state.get("collection")
        if dlg is None:
            dlg = state["collection"] = CollectionDialog(variants_file)
            dlg.placeRequested.connect(guarded(add_bigtree))
        dlg.refresh()
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def save_variant(kind: str) -> None:
        variants = storage.load_variants(variants_file)
        name, ok = QInputDialog.getText(None, "Kratzbaum-Variante speichern", "Name:",
                                        text=f"Kratzbaum {len(variants) + 1}")
        name = name.strip()
        if not ok or not name or kind not in furniture.trees:
            return
        variants = [v for v in variants if v["name"] != name] + [furniture.trees[kind].variant(name)]
        storage.save_variants(variants_file, variants)
        if state.get("collection") is not None:
            state["collection"].refresh()

    def apply_variant(kind: str, variant: dict) -> None:
        if kind in furniture.trees:
            furniture.apply_variant(kind, variant)
            furniture_changed()

    def remove_bigtree(kind: str) -> None:
        furniture.remove_tree(kind)
        furniture_changed()

    def bigtree_wheel(kind: str, dx: float, dy: float) -> None:
        tree = furniture.trees.get(kind)
        if tree is not None:
            furniture.resize_tree(kind, *tree.wheeled(dx, dy))
            furniture_changed()

    def new_sisal(kind: str) -> None:
        """Kratzspuren weg: alle Pfeiler wie neu."""
        furniture.trees[kind].wear = []
        furniture_changed()

    furniture_menu = QMenu()
    def show_furniture_menu(kind: str, pos) -> None:
        furniture_menu.clear()
        if is_tree(kind):
            furniture_menu.addAction("Variante speichern ...", guarded(lambda: save_variant(kind)))
            furniture_menu.addAction("Sammlung ...", guarded(show_collection))
            sub = furniture_menu.addMenu("Gespeicherte Variante übernehmen")
            for v in storage.load_variants(variants_file):
                sub.addAction(v["name"], guarded(lambda _c=False, v=v: apply_variant(kind, v)))
            sub.setEnabled(bool(sub.actions()))
            furniture_menu.addAction("Neuen Sisal", guarded(lambda: new_sisal(kind))).setEnabled(
                bool(furniture.trees[kind].wear_levels()))
            furniture_menu.addSeparator()
            b = furniture.bodies[kind]
            furniture_menu.addAction("Weiteren Kratzbaum aufstellen", guarded(
                lambda: add_bigtree(None, b.x + 2 * half_width(kind) + 40, b.y - 400)))
            furniture_menu.addAction("Entfernen", guarded(lambda: remove_bigtree(kind)))
            furniture_menu.popup(pos)
            return
        if kind == "bowl":   # wie Linksklick aufs Tray-Icon; voll passt nichts mehr hinein
            full = not furniture.tipped and furniture.food >= BOWL_PORTIONS
            furniture_menu.addAction("Füttern (Napf voll)" if full else "Füttern",
                                     guarded(feed)).setEnabled(not full)
            furniture_menu.addSeparator()
        furniture_menu.addAction("Einlagern", guarded(lambda: store(kind)))
        furniture_menu.addAction("Inventar ...", guarded(show_inventory))
        furniture_menu.popup(pos)

    overlays.furnitureMoved.connect(guarded(move_furniture))
    overlays.furnitureReleased.connect(guarded(furniture.release))
    overlays.furnitureMenu.connect(guarded(show_furniture_menu))
    overlays.furnitureWheel.connect(guarded(bigtree_wheel))
    tray.bigtreeRequested.connect(guarded(add_bigtree))
    tray.collectionRequested.connect(guarded(show_collection))
    tray.inventoryRequested.connect(guarded(show_inventory))
    tray.feedRequested.connect(guarded(feed))
    tray.petRequested.connect(guarded(cat.pet))
    tray.sleepRequested.connect(guarded(cat.go_sleep))
    tray.floorRequested.connect(guarded(cat.call_to_floor))
    tray.pauseToggled.connect(guarded(cat.set_paused))
    tray.quitRequested.connect(guarded(app.quit))

    def config_changed(name: str) -> None:
        if name == "debug_lines":
            overlays.set_debug(debug or cfg.debug_lines)
        elif name in ("fur_color", "tabby"):
            overlays.set_atlas(sprites.ensure_atlas(paths.cache_dir(), cfg.fur_color, cfg.tabby))
            if name == "fur_color":
                tray.set_color(cfg.fur_color)
        elif name == "blocked_outputs":
            state["world"] = fallback_world(app, cfg.blocked_outputs)
            bus.refresh()  # echtes Weltmodell kommt mit dem nächsten Sensor-Update
        storage.try_save(cfg_file, cfg)

    def show_settings() -> None:
        dlg = state.get("dialog")
        if dlg is None:
            dlg = state["dialog"] = SettingsDialog(cfg)
            dlg.changed.connect(guarded(config_changed))
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    tray.settingsRequested.connect(guarded(show_settings))

    def tick():
        now = time.monotonic()
        dt, state["last"] = now - state["last"], now
        world = bus.latest_world()
        if world is not None:
            state["world"] = world
        for x, y, t in bus.take_cursor_samples():
            wiggle.feed(x, y, t)
        size = cat.sprite
        sprite = (cat.x - size / 2, cat.y - size, cat.x + size / 2, cat.y)
        wiggling = wiggle.is_wiggling(cat.x, cat.y - size / 2, now, avoid=sprite)
        world = furniture.world_with(state["world"], cat.sprite)   # samt Kratzbaum-Liegefläche
        cat.tick(dt, world, bus.locked, cursor=wiggle.last, wiggling=wiggling)
        fur = cat.take_new_fur()
        if fur is not None:  # vom UFO umgefärbt: wie eine Änderung im Dialog behandeln
            cfg.set("fur_color", fur)
            config_changed("fur_color")
            if state.get("dialog") is not None:
                state["dialog"].show_value("fur_color")
        overlays.render(cat, world, now, furniture)

    def save():
        storage.try_save(state_file, cat.needs)
        storage.try_save(furniture_file, furniture)

    def quit_():
        save()
        bus.unload_sensor()

    timers = []
    def refresh():
        tray.refresh(bus.sensor_ok)
        if state.get("inventory") is not None:   # Futterstand ändert sich, wenn sie frisst
            state["inventory"].refresh()

    for ms, fn in ((TICK_MS, tick), (SAVE_MS, save), (TRAY_MS, refresh)):
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
