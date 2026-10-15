"""Ein Layer-Shell-Overlay pro Monitor: Katze zeichnen, Input-Region, Maus-Events."""
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs

from PyQt6.QtCore import QObject, QPoint, QRect, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QImage, QRegion, QScreen
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlImageProviderBase
from PyQt6.QtQuick import QQuickImageProvider

from .. import bigtree, sprites
from ..cat import Cat
from ..furniture import BOX, Furniture, fly_path
from ..guard import guarded
from ..interaction import DragTracker, RubDetector
from ..paths import resource_file
from ..world import World

MASK_MARGIN = 8
NO_INPUT = QRegion(QRect(-10, -10, 1, 1))  # leere Region hieße "ganzes Fenster"


class _Overlay:
    def __init__(self, window, screen: QScreen):
        self.window = window
        self.screen = screen
        self.mask: tuple[QRect, ...] = ()
        self.world: World | None = None
        self.furniture: tuple[list, list] = ([], [])
        self.bigtrees: list = []
        self.fronts: list = []
        self.toys: list = []
        self.toy_angles: list = []

    @property
    def origin(self) -> QPoint:
        return self.screen.geometry().topLeft()


class BigtreeImages(QQuickImageProvider):
    """image://bigtree/<w>x<h>/<stand|hang>/<seed>[?load=<Brett>:<Pixel>&wear=<Stufen>&front=1]:
    große Kratzbäume ohne Datei, damit das Ziehen am Mausrad fließend neue Größen liefert.
    load lässt eine Hängematte tiefer durchhängen, wear zeigt Kratzspuren, front liefert nur
    den Teil vor der Katze (sprites.render_front). Ohne Bällchen, die zeichnet das QML."""

    def __init__(self):
        super().__init__(QQmlImageProviderBase.ImageType.Image)
        self._cache: dict[str, QImage] = {}

    def requestImage(self, id_: str, size):
        img = self._cache.get(id_)
        if img is None:
            path, _, query = id_.partition("?")
            q = {k: v[0] for k, v in parse_qs(query).items()}
            dims, mode, seed = (path.split("/") + ["stand", "0"])[:3]
            w, h = (int(v) for v in dims.split("x"))
            key, _, px = q.get("load", "").rpartition(":")
            load = (key, int(px)) if key else None
            front = sprites.render_front(w, h, mode == "hang", int(seed), load) \
                if q.get("front") and load is not None else None
            img = front if front is not None else sprites.render_bigtree(
                w, h, mode == "hang", int(seed), load, toys=False, wear=q.get("wear", ""))
            if len(self._cache) > 64:
                self._cache.clear()
            self._cache[id_] = img
        return img, img.size()


def bigtree_source(tree: bigtree.Tree, load: tuple[str, int] | None = None, front: bool = False) -> str:
    w, h = tree.size()
    query = []
    if load is not None and load[1] > 0:
        query.append(f"load={load[0]}:{load[1]}")
    if front:
        query.append("front=1")
    elif tree.wear_levels():
        query.append(f"wear={tree.wear_levels()}")
    src = f"image://bigtree/{w}x{h}/{'hang' if tree.hanging else 'stand'}/{tree.seed}"
    return f"{src}?{'&'.join(query)}" if query else src


class OverlayManager(QObject):
    petted = pyqtSignal()
    rightClicked = pyqtSignal(QPoint)
    dragStarted = pyqtSignal()
    dragMoved = pyqtSignal(float, float)
    released = pyqtSignal(float, float)
    furnitureMoved = pyqtSignal(str, float, float)   # Art, neue Mitte unten (global)
    furnitureReleased = pyqtSignal(str, float, float)  # Art, Wurfgeschwindigkeit
    furnitureMenu = pyqtSignal(str, QPoint)
    furnitureWheel = pyqtSignal(str, float, float)    # großer Kratzbaum, Mausrad x/y

    def __init__(self, engine: QQmlEngine, atlas: Path, debug: bool,
                 ufo: tuple[Path, Path] | None = None, furniture: Path | None = None):
        """ufo: Bilder für UFO und Traktorstrahl (sprites.ensure_ufo);
        furniture: Möbel-Atlas (sprites.ensure_furniture)."""
        super().__init__()
        self._engine = engine
        self._atlas = QUrl.fromLocalFile(str(atlas))
        self._ufo = tuple(QUrl.fromLocalFile(str(p)) for p in ufo) if ufo else (QUrl(), QUrl())
        self._furniture_atlas = QUrl.fromLocalFile(str(furniture)) if furniture else QUrl()
        self._debug = debug
        if engine.imageProvider("bigtree") is None:
            self._bigtree_images = BigtreeImages()   # Engine hält keine eigene Referenz
            engine.addImageProvider("bigtree", self._bigtree_images)
        qml = resource_file("ui", "overlay.qml")
        self._component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml)))
        if self._component.isError():
            raise RuntimeError("\n".join(e.toString() for e in self._component.errors()))
        self._overlays: dict[QScreen, _Overlay] = {}
        self._drag = DragTracker()
        self._rub = RubDetector()
        self._cat_rect = QRect()                # global, mit Rand
        self._furn_rects: dict[str, QRect] = {}  # global, sichtbare Möbel
        self._furn_parts: dict[str, list[QRect]] = {}   # große Kratzbäume: Teile ohne Lücken
        self._bigtrees: list[dict] = []          # global, links oben, fürs QML
        self._fronts: list[dict] = []            # Hängematte vor der Katze (wie _bigtrees)
        self._toys: list[dict] = []              # Bällchen der großen Kratzbäume (global)
        self._toy_angles: list[float] = []       # deren Auslenkung (rad), gleiche Reihenfolge
        self._pile: tuple[float, float] | None = None   # verschüttetes Futter (Mitte unten, global)
        self._furn_pos: dict[str, tuple[float, float]] = {}
        self._lying: tuple[str, float] | None = None   # (Hängematte, seit wann sie drin liegt)
        self._sink: tuple[str, str, int] | None = None  # (Baum, Brett, Pixel) Durchhängen
        self._grabbed: str | None = None         # "cat", Möbelart oder None
        self._grab_d = (0.0, 0.0)
        app = QGuiApplication.instance()
        for s in app.screens():
            self._add(s)
        app.screenAdded.connect(guarded(self._add))
        app.screenRemoved.connect(guarded(self._remove))

    def set_atlas(self, atlas: Path) -> None:
        """Nach einem Farbwechsel das neue Spritesheet in alle Overlays geben."""
        self._atlas = QUrl.fromLocalFile(str(atlas))
        for ov in self._overlays.values():
            ov.window.setProperty("atlas", self._atlas)

    def set_debug(self, on: bool) -> None:
        self._debug = on
        for ov in self._overlays.values():
            ov.world = None  # erzwingt Neuzeichnen beim nächsten render
            if not on:
                ov.window.setProperty("platforms", [])

    def _add(self, screen: QScreen) -> None:
        win = self._component.createWithInitialProperties(
            {"atlas": self._atlas, "ufoSource": self._ufo[0], "beamSource": self._ufo[1],
             "furnitureAtlas": self._furniture_atlas})
        if win is None:
            print("taskbar-cat: Overlay nicht erstellt:", self._component.errors(), file=sys.stderr)
            return
        win.setScreen(screen)
        win.setGeometry(screen.geometry())
        ov = _Overlay(win, screen)
        win.setMask(NO_INPUT)
        win.catPressed.connect(guarded(lambda x, y, b, ov=ov: self._pressed(ov, x, y, b)))
        win.catMoved.connect(guarded(lambda x, y, b, ov=ov: self._moved(ov, x, y, b)))
        win.catReleased.connect(guarded(lambda x, y, b, ov=ov: self._released(ov, x, y, b)))
        win.catCanceled.connect(guarded(self._cancel_drag))
        win.bigtreeWheel.connect(guarded(lambda k, dx, dy: self.furnitureWheel.emit(k, dx, dy)))
        win.show()
        self._overlays[screen] = ov

    def _remove(self, screen: QScreen) -> None:
        ov = self._overlays.pop(screen, None)
        self._cancel_drag()
        if ov is not None:
            ov.window.close()
            ov.window.deleteLater()

    def _furniture_frames(self, cat: Cat, world: World,
                          furniture: Furniture | None) -> list[tuple[str, float, float, str, str | None]]:
        """(Art, x, y, Frame hinter der Katze, Frame vor der Katze) je sichtbarem Möbel;
        merkt sich nebenbei die Mausflächen."""
        self._furn_rects = {}
        self._furn_pos = {}
        self._furn_parts = {}
        self._bigtrees = []
        self._fronts = []
        self._toys = []
        self._toy_angles = []
        self._pile = None
        if furniture is None:
            return []
        out = []
        size = cat.sprite
        for kind in furniture.bodies:
            pos = furniture.visible(kind, world)
            if pos is None:
                continue
            x, y = self._furn_pos[kind] = pos
            if kind in furniture.trees:
                tree = furniture.trees[kind]
                left, top, s, lay = bigtree.geometry(tree, pos, size)
                self._furn_parts[kind] = [QRect(round(r.x), round(r.y), round(r.w), round(r.h))
                                          for r in bigtree.parts(tree, pos, size)]
                load = self._sink[1:] if self._sink is not None and self._sink[0] == kind else None
                src = bigtree_source(tree, load)
                self._bigtrees.append({"kind": kind, "src": src,
                                       "x": left, "y": top, "w": lay.w * s, "h": lay.h * s})
                for i, (tx, ty, n, col) in enumerate(lay.toys):   # pendeln, also nicht im Bild
                    self._toys.append({"x": left + (tx + 0.5) * s, "y": top + ty * s, "len": n * s, "s": s,
                                       "color": sprites.TOY_COLORS[col % len(sprites.TOY_COLORS)].name(),
                                       "string": sprites.SISAL_DARK.name(),
                                       "outline": sprites.FURNITURE_OUTLINE.name()})
                    self._toy_angles.append(furniture.toy_angle(kind, i))
                behind = cat.behind()
                for part in (load, (behind[1], 1) if behind is not None and behind[0] == kind else None):
                    front = bigtree.front_part(lay, *part) if part is not None else None
                    if front is not None:
                        fx, fy, fw, fh = front
                        self._fronts.append({"src": bigtree_source(tree, part, front=True),
                                             "x": left + fx * s, "y": top + fy * s, "w": fw * s, "h": fh * s})
                continue
            s = size / sprites.FRAME
            bx, by, bw, bh = (v * s for v in BOX[kind])
            top = y - sprites.furniture_height(kind) * s
            self._furn_rects[kind] = QRect(round(x - size / 2 + bx), round(top + by),
                                           round(bw), round(bh))
            if kind == "bed":
                out.append((kind, x, y, "bed_back", "bed_front" if cat.in_bed else None))
            elif kind == "tree":
                out.append((kind, x, y, "tree", None))
            elif kind == "yarn":   # Fadenlinien wechseln alle Achtel-Sprite beim Rollen
                out.append((kind, x, y, ("yarn", "yarn_roll")[int(x / (size / 8)) % 2], None))
            elif furniture.bowl_upside_down:
                out.append((kind, x, y, "bowl_tipped", None))
                if furniture.spill and furniture.tipped:
                    self._pile = furniture.pile(size)
                    out.append((kind, *self._pile, f"spill_{min(furniture.spill, sprites.BOWL_LEVELS)}", None))
            else:
                level = min(furniture.food, sprites.BOWL_LEVELS)
                out.append((kind, x, y, f"bowl_{level}", None))
        return out

    def _flies(self, furniture: Furniture | None, size: int) -> list[float]:
        """Fliegen über dem verschütteten Futter, flach je Fliege: x, y (global), Flügel oben.
        Ihre Uhr ist furniture.spill_age, damit die Katze sie dort fängt, wo man sie sieht."""
        if furniture is None or self._pile is None:
            return []
        out = []
        for i in furniture.fly_ids:
            x, y = furniture.fly_at(i, size)
            out += [x, y, float(fly_path(furniture.spill_age, i)[2])]
        return out

    def _hammock_sink(self, cat: Cat, t: float) -> float:
        """Liegt sie in einer Hängematte, hängt die langsam tiefer durch (self._sink) und
        sie sinkt in den Stoff ein; liefert, wie viel tiefer (Bildschirmpixel) sie gezeichnet wird."""
        owner = cat.hammock() if cat.visible else None
        if owner is None:
            self._lying = self._sink = None
            return 0.0
        if self._lying is None or self._lying[0] != owner:
            self._lying = (owner, t)
        px = bigtree.load_sag(t - self._lying[1])
        self._sink = (*bigtree.hammock_of(owner), px)
        return px * bigtree.CAT_SINK / bigtree.LOAD_SAG * cat.sprite / sprites.FRAME

    def render(self, cat: Cat, world: World, t: float, furniture: Furniture | None = None) -> None:
        anim, mood, frame, flip = cat.frame_key(t)
        sx, sy = sprites.frame_origin(anim, mood, frame)
        size = cat.sprite
        sink = self._hammock_sink(cat, t)
        self._cat_rect = (QRect(round(cat.x - size / 2), round(cat.y - size), size, size)
                          .adjusted(-MASK_MARGIN, -MASK_MARGIN, MASK_MARGIN, MASK_MARGIN)
                          if cat.visible else QRect())
        furn = self._furniture_frames(cat, world, furniture)
        flies = self._flies(furniture, size)
        for ov in self._overlays.values():
            o = ov.origin
            lx, ly = cat.x - o.x(), cat.y - o.y() + sink
            sprite = QRect(round(lx - size / 2), round(ly - size), size, size)
            screen = QRect(QPoint(0, 0), ov.screen.geometry().size())
            here = cat.visible and sprite.intersects(screen)
            w = ov.window
            w.setProperty("catVisible", here)
            w.setProperty("spriteSize", size)
            if here:
                w.setProperty("catX", lx)
                w.setProperty("catY", ly)
                w.setProperty("catOpacity", cat.opacity)
                w.setProperty("srcX", sx)
                w.setProperty("srcY", sy)
                w.setProperty("flip", flip)
            self._render_ufo(w, cat, o)
            back, front = [], []
            for kind, x, y, b, f in furn:
                for name, layer in ((b, back), (f, front)):
                    if name is not None:
                        fx, fy = sprites.furniture_origin(name)
                        layer.append({"x": x - o.x(), "y": y - o.y(), "sx": fx, "sy": fy,
                                      "h": sprites.furniture_height(name)})
            if (back, front) != ov.furniture:   # Repeater nur bei Änderung neu aufbauen
                ov.furniture = (back, front)
                w.setProperty("furnitureBack", back)
                w.setProperty("furnitureFront", front)
            trees = [{**t, "x": t["x"] - o.x(), "y": t["y"] - o.y()} for t in self._bigtrees]
            if trees != ov.bigtrees:
                ov.bigtrees = trees
                w.setProperty("bigtrees", trees)
            toys = [{**t, "x": t["x"] - o.x(), "y": t["y"] - o.y()} for t in self._toys]
            if toys != ov.toys:
                ov.toys = toys
                w.setProperty("bigtreeToys", toys)
            if self._toy_angles != ov.toy_angles:   # nur die Winkel: Repeater bleibt stehen
                ov.toy_angles = list(self._toy_angles)
                w.setProperty("toyAngles", ov.toy_angles)
            local_flies = [v - (o.x(), o.y(), 0)[k % 3] for k, v in enumerate(flies)]
            w.setProperty("flySize", size / sprites.FRAME)
            w.setProperty("flyPos", local_flies)
            w.setProperty("flyCount", len(flies) // 3)
            fronts = [{**t, "x": t["x"] - o.x(), "y": t["y"] - o.y()} for t in self._fronts]
            if fronts != ov.fronts:
                ov.fronts = fronts
                w.setProperty("bigtreeFronts", fronts)
            local = [r.translated(-o.x(), -o.y()) for r in self._furn_rects.values()]
            local += [r.translated(-o.x(), -o.y()) for rs in self._furn_parts.values() for r in rs]
            if here:
                local.append(sprite.adjusted(-MASK_MARGIN, -MASK_MARGIN, MASK_MARGIN, MASK_MARGIN))
            mask = tuple(r for r in local if r.intersects(screen))
            # Während eines Drags behält das greifende Overlay seine Region (Implicit Grab).
            if mask != ov.mask and not self._drag.is_dragging:
                region = QRegion()
                for r in mask:
                    region = region.united(r)
                w.setMask(region if mask else NO_INPUT)
                ov.mask = mask
            if self._debug and world is not ov.world:
                ov.world = world
                ox, oy = o.x(), o.y()
                lines = [{"x": p.x1 - ox, "y": p.y - oy - 2, "w": p.x2 - p.x1, "h": 2,
                          "color": "#80ffff00" if p.is_floor else "#80ff00ff"} for p in world.platforms]
                lines += [{"x": wl.x - ox - 1, "y": wl.y1 - oy, "w": 2, "h": wl.y2 - wl.y1,
                           "color": "#8000ffff"} for wl in world.walls]
                lines += [{"x": c.x1 - ox, "y": c.y - oy, "w": c.x2 - c.x1, "h": 2,
                           "color": "#80ff3030"} for c in world.ceilings]
                w.setProperty("platforms", lines)

    @staticmethod
    def _render_ufo(w, cat: Cat, o: QPoint) -> None:
        u = cat.ufo
        w.setProperty("ufoVisible", u is not None)
        if u is None:
            return
        w.setProperty("ufoX", u.x - o.x())
        w.setProperty("ufoY", u.y - o.y())
        w.setProperty("ufoWidth", round(u.width))
        w.setProperty("ufoTime", u.t)
        w.setProperty("beamOn", u.beam_on)
        w.setProperty("beamTop", u.bottom - o.y())
        w.setProperty("beamBottom", u.ground_y - o.y())
        w.setProperty("beamWidth", cat.sprite * 1.3)

    # --- Maus (lokale Koordinaten -> global) ---

    def _hit(self, gx: float, gy: float) -> str | None:
        """Was liegt unter dem Zeiger? Die Katze geht vor."""
        p = QPoint(round(gx), round(gy))
        if self._cat_rect.contains(p):
            return "cat"
        return next((k for k, r in self._furn_rects.items() if r.contains(p)),
                    next((k for k, rs in self._furn_parts.items() if any(r.contains(p) for r in rs)), None))

    def _pressed(self, ov: _Overlay, x: float, y: float, button: int) -> None:
        gx, gy = x + ov.origin.x(), y + ov.origin.y()
        hit = self._hit(gx, gy)
        if button == Qt.MouseButton.RightButton.value:
            pos = QPoint(round(gx), round(gy))
            if hit in (None, "cat"):
                self.rightClicked.emit(pos)
            else:
                self.furnitureMenu.emit(hit, pos)
        elif button == Qt.MouseButton.LeftButton.value and hit is not None:
            self._grabbed = hit
            if hit != "cat":   # Abstand Zeiger zum Möbel, damit es nicht springt
                x, y = self._furn_pos[hit]
                self._grab_d = (gx - x, gy - y)
            self._drag.press(gx, gy, time.monotonic())

    def _moved(self, ov: _Overlay, x: float, y: float, buttons: int) -> None:
        gx, gy = x + ov.origin.x(), y + ov.origin.y()
        now = time.monotonic()
        if buttons & Qt.MouseButton.LeftButton.value:
            if self._grabbed is None:
                return
            was = self._drag.is_dragging
            if self._drag.move(gx, gy, now):
                if self._grabbed != "cat":
                    self.furnitureMoved.emit(self._grabbed, gx - self._grab_d[0], gy - self._grab_d[1])
                    return
                if not was:
                    self.dragStarted.emit()
                self.dragMoved.emit(gx, gy)
        elif self._hit(gx, gy) == "cat" and self._rub.feed_motion(gx, now):
            self.petted.emit()

    def _released(self, ov: _Overlay, x: float, y: float, button: int) -> None:
        if button != Qt.MouseButton.LeftButton.value:
            return
        grabbed, self._grabbed = self._grabbed, None
        if self._drag.is_dragging:
            self._drag.is_dragging = False
            if grabbed == "cat":
                self.released.emit(*self._drag.velocity())
            elif grabbed is not None:
                self.furnitureReleased.emit(grabbed, *self._drag.velocity())
        elif grabbed == "cat":
            self.petted.emit()

    def _cancel_drag(self) -> None:
        """Grab abgebrochen (Compositor, Popup, Monitor weg): Katze fallen lassen."""
        grabbed, self._grabbed = self._grabbed, None
        if self._drag.is_dragging:
            self._drag.is_dragging = False
            if grabbed == "cat":
                self.released.emit(0.0, 0.0)
            elif grabbed is not None:
                self.furnitureReleased.emit(grabbed, 0.0, 0.0)
