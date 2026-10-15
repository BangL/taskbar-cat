"""KDE Plasma / KWin unter Wayland: Layer-Shell-Overlay und KWin-Script als Sensor.

Der Weg über wlr-layer-shell ist nicht auf Plasma beschränkt; er trägt auch auf
anderen Wayland-Compositors, die das Protokoll sprechen (sway, Hyprland). Nur der
Sensor hängt an KWin.
"""
import sys

from PyQt6.QtDBus import QDBusInterface, QDBusMessage

from ..paths import sensor_script
from .base import Backend

SCRIPT_NAME = "taskbar-cat-sensor"


class KdeBackend(Backend):
    name = "kde"
    label = "KDE Plasma (KWin)"
    qt_platform = None          # Wayland-Plugin, das Qt selbst wählt
    overlay_qml = "overlay.qml"

    def _scripting(self) -> QDBusInterface:
        return QDBusInterface("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", self._conn)

    def start_sensor(self) -> None:
        s = self._scripting()
        s.call("unloadScript", SCRIPT_NAME)
        reply = s.call("loadScript", str(sensor_script()), SCRIPT_NAME)
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            print(f"taskbar-cat: loadScript fehlgeschlagen: {reply.errorMessage()}", file=sys.stderr)
            return
        s.call("start")

    def stop_sensor(self) -> None:
        self._scripting().call("unloadScript", SCRIPT_NAME)

    def sensor_loaded(self) -> bool:
        reply = self._scripting().call("isScriptLoaded", SCRIPT_NAME)
        return reply.type() == QDBusMessage.MessageType.ReplyMessage and bool(reply.arguments()[0])
