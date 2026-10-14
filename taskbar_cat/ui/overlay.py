"""Ein Layer-Shell-Overlay pro Monitor: Katze zeichnen, Input-Region, Maus-Events."""
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QObject, QPoint, QRect, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QRegion, QScreen
from PyQt6.QtQml import QQmlComponent, QQmlEngine

from .. import sprites
from ..cat import Cat
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
        self.mask: QRect | None = None
        self.world: World | None = None

    @property
    def origin(self) -> QPoint:
        return self.screen.geometry().topLeft()


class OverlayManager(QObject):
    petted = pyqtSignal()
    rightClicked = pyqtSignal(QPoint)
    dragStarted = pyqtSignal()
    dragMoved = pyqtSignal(float, float)
    released = pyqtSignal(float, float)

    def __init__(self, engine: QQmlEngine, atlas: Path, debug: bool):
        super().__init__()
        self._engine = engine
        self._atlas = QUrl.fromLocalFile(str(atlas))
        self._debug = debug
        qml = resource_file("ui", "overlay.qml")
        self._component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml)))
        if self._component.isError():
            raise RuntimeError("\n".join(e.toString() for e in self._component.errors()))
        self._overlays: dict[QScreen, _Overlay] = {}
        self._drag = DragTracker()
        self._rub = RubDetector()
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
        win = self._component.createWithInitialProperties({"atlas": self._atlas})
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
        win.show()
        self._overlays[screen] = ov

    def _remove(self, screen: QScreen) -> None:
        ov = self._overlays.pop(screen, None)
        self._cancel_drag()
        if ov is not None:
            ov.window.close()
            ov.window.deleteLater()

    def render(self, cat: Cat, world: World, t: float) -> None:
        anim, mood, frame, flip = cat.frame_key(t)
        sx, sy = sprites.frame_origin(anim, mood, frame)
        for ov in self._overlays.values():
            o = ov.origin
            lx, ly = cat.x - o.x(), cat.y - o.y()
            size = cat.sprite
            sprite = QRect(round(lx - size / 2), round(ly - size), size, size)
            here = cat.visible and sprite.intersects(QRect(QPoint(0, 0), ov.screen.geometry().size()))
            w = ov.window
            w.setProperty("catVisible", here)
            w.setProperty("spriteSize", size)
            if here:
                w.setProperty("catX", lx)
                w.setProperty("catY", ly)
                w.setProperty("srcX", sx)
                w.setProperty("srcY", sy)
                w.setProperty("flip", flip)
            mask = sprite.adjusted(-MASK_MARGIN, -MASK_MARGIN, MASK_MARGIN, MASK_MARGIN) if here else None
            # Während eines Drags behält das greifende Overlay seine Region (Implicit Grab).
            if mask != ov.mask and not self._drag.is_dragging:
                w.setMask(QRegion(mask) if mask else NO_INPUT)
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

    # --- Maus (lokale Koordinaten -> global) ---

    def _pressed(self, ov: _Overlay, x: float, y: float, button: int) -> None:
        gx, gy = x + ov.origin.x(), y + ov.origin.y()
        if button == Qt.MouseButton.RightButton.value:
            self.rightClicked.emit(QPoint(round(gx), round(gy)))
        elif button == Qt.MouseButton.LeftButton.value:
            self._drag.press(gx, gy, time.monotonic())

    def _moved(self, ov: _Overlay, x: float, y: float, buttons: int) -> None:
        gx, gy = x + ov.origin.x(), y + ov.origin.y()
        now = time.monotonic()
        if buttons & Qt.MouseButton.LeftButton.value:
            was = self._drag.is_dragging
            if self._drag.move(gx, gy, now):
                if not was:
                    self.dragStarted.emit()
                self.dragMoved.emit(gx, gy)
        elif self._rub.feed_motion(gx, now):
            self.petted.emit()

    def _released(self, ov: _Overlay, x: float, y: float, button: int) -> None:
        if button != Qt.MouseButton.LeftButton.value:
            return
        if self._drag.is_dragging:
            self._drag.is_dragging = False
            self.released.emit(*self._drag.velocity())
        else:
            self.petted.emit()

    def _cancel_drag(self) -> None:
        """Grab abgebrochen (Compositor, Popup, Monitor weg): Katze fallen lassen."""
        if self._drag.is_dragging:
            self._drag.is_dragging = False
            self.released.emit(0.0, 0.0)
