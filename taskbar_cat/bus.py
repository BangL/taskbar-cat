"""D-Bus: Service für den KWin-Sensor, KWin-Script laden/entladen, Bildschirmsperre."""
import os
import sys
import time
from PyQt6.QtCore import QObject, QTimer, pyqtClassInfo, pyqtSignal, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

from .guard import guarded
from .paths import sensor_script
from .world import World

SERVICE = "de.bangl.TaskbarCat"
SCRIPT_NAME = "taskbar-cat-sensor"
WATCHDOG_MS = 10_000
RELOAD_MIN_INTERVAL = 60


@pyqtClassInfo("D-Bus Interface", SERVICE)
class _Adaptor(QObject):
    def __init__(self, owner: "CatBus"):
        super().__init__(owner)
        self._owner = owner

    @pyqtSlot(str)
    def update(self, text: str) -> None:
        self._owner._pending = text

    @pyqtSlot(str)
    def cursor(self, text: str) -> None:
        try:
            x, y = (float(v) for v in text.split())
        except ValueError:
            return
        self._owner._cursor_samples.append((x, y, time.monotonic()))


class CatBus(QObject):
    lockChanged = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.adaptor = _Adaptor(self)
        self._pending: str | None = None
        self._cursor_samples: list[tuple[float, float, float]] = []
        self._received = False
        self._last_load = 0.0
        self.locked = False
        self._bus = QDBusConnection.sessionBus()
        self._watchdog = QTimer(self)
        self._watchdog.timeout.connect(guarded(self._check_sensor))

    @property
    def sensor_ok(self) -> bool:
        return self._received

    def register(self) -> bool:
        if not self._bus.registerService(SERVICE):
            return False
        self._bus.registerObject("/", self.adaptor, QDBusConnection.RegisterOption.ExportAllSlots)
        self._bus.connect("org.freedesktop.ScreenSaver", "/ScreenSaver", "org.freedesktop.ScreenSaver",
                          "ActiveChanged", self._on_lock)
        reply = QDBusInterface("org.freedesktop.ScreenSaver", "/ScreenSaver",
                               "org.freedesktop.ScreenSaver", self._bus).call("GetActive")
        if reply.type() == QDBusMessage.MessageType.ReplyMessage and reply.arguments():
            self.locked = bool(reply.arguments()[0])
        return True

    @pyqtSlot(bool)
    def _on_lock(self, active: bool) -> None:
        self.locked = active
        self.lockChanged.emit(active)

    def latest_world(self) -> World | None:
        text, self._pending = self._pending, None
        if text is None:
            return None
        try:
            world = World.from_json(text, ignore_pid=os.getpid())
        except ValueError as e:
            print(f"taskbar-cat: {e}", file=sys.stderr)
            return None
        self._received = True
        return world

    def take_cursor_samples(self) -> list[tuple[float, float, float]]:
        """Cursor-Positionen (x, y, monotonic) seit dem letzten Aufruf."""
        samples, self._cursor_samples = self._cursor_samples, []
        return samples

    def _scripting(self) -> QDBusInterface:
        return QDBusInterface("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", self._bus)

    def load_sensor(self) -> None:
        self._last_load = time.monotonic()
        self._watchdog.start(WATCHDOG_MS)
        s = self._scripting()
        s.call("unloadScript", SCRIPT_NAME)
        reply = s.call("loadScript", str(sensor_script()), SCRIPT_NAME)
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            print(f"taskbar-cat: loadScript fehlgeschlagen: {reply.errorMessage()}", file=sys.stderr)
            return
        s.call("start")

    def unload_sensor(self) -> None:
        self._watchdog.stop()
        self._scripting().call("unloadScript", SCRIPT_NAME)

    def _check_sensor(self) -> None:
        reply = self._scripting().call("isScriptLoaded", SCRIPT_NAME)
        loaded = reply.type() == QDBusMessage.MessageType.ReplyMessage and bool(reply.arguments()[0])
        if (not loaded or not self._received) and time.monotonic() - self._last_load >= RELOAD_MIN_INTERVAL:
            print("taskbar-cat: Sensor fehlt, lade neu", file=sys.stderr)
            self._received = False
            self.load_sensor()


def _dump() -> None:
    import signal

    from PyQt6.QtCore import QCoreApplication

    app = QCoreApplication(sys.argv)
    bus = CatBus()
    if not bus.register():
        sys.exit("taskbar-cat: Service belegt (läuft schon eine Instanz?)")
    bus.load_sensor()
    app.aboutToQuit.connect(bus.unload_sensor)
    signal.signal(signal.SIGINT, lambda *_: app.quit())

    def poll():
        w = bus.latest_world()
        if w is None:
            return
        print(f"--- {len(w.windows)} Fenster, gesperrt={bus.locked}, verboten={sorted(w.forbidden_outputs)}")
        for o in w.outputs:
            print(f"  output {o.name} geo={o.geometry} work={o.work_area}")
        for p in sorted(w.platforms, key=lambda p: (p.y, p.x1)):
            print(f"  {p.owner[:12]:12} y={p.y:6.0f} x={p.x1:6.0f}..{p.x2:6.0f}")
        sys.stdout.flush()

    t = QTimer()
    t.timeout.connect(poll)
    t.start(500)
    app.exec()


if __name__ == "__main__" and "--dump" in sys.argv:
    _dump()
