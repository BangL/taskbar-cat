"""GNOME Shell / Mutter: X11-Overlay und eine Shell-Extension als Sensor.

Mutter kennt kein wlr-layer-shell, und native Wayland-Clients dürfen sich nicht
selbst positionieren. Das Overlay läuft deshalb als X11-Fenster über XWayland;
das lässt sich frei platzieren und liegt über allen Fenstern.

Die Fenstergeometrie liefert eine GNOME-Shell-Extension. Sie spricht dasselbe
D-Bus-Protokoll wie das KWin-Script und wird hier bei Bedarf eingerichtet und
eingeschaltet. Fehlt sie, läuft die Katze trotzdem - dann nur auf dem Boden der
Monitore, die Qt meldet.

GNOME 45 hat auf ES-Module umgestellt. Für ältere Shells (40-44) wird aus
derselben extension.js eine imports.gi-Fassung erzeugt, siehe legacy_extension().
"""
import json
import os
import re
import subprocess
import sys

from PyQt6.QtDBus import QDBusInterface, QDBusMessage

from ..paths import EXTENSION_UUID, extension_dir, extension_sources
from . import _x11
from .base import Backend

SERVICE = "org.gnome.Shell.Extensions"
OBJECT = "/org/gnome/Shell/Extensions"
# Zustände der Shell; Einschalten läuft asynchron, ENABLING ist also in Ordnung
STATE_UNKNOWN = 0        # die Shell kennt die Erweiterung nicht (erst nach Anmeldung)
STATE_ENABLED = 1
STATE_ERROR = 3
STATE_OUT_OF_DATE = 4
STATE_ENABLING = 8
MODULES_SINCE = 45       # ab hier ES-Module, davor imports.gi
LEGACY_SHELLS = ["40", "41", "42", "43", "44"]


def shell_version() -> int | None:
    """Hauptversion der installierten GNOME Shell, None wenn unbekannt."""
    try:
        out = subprocess.run(["gnome-shell", "--version"], capture_output=True,
                             text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"(\d+)\.", out)
    return int(m.group(1)) if m else None


def legacy_extension(js: str, metadata: str) -> dict[str, str]:
    """extension.js/metadata.json für GNOME 40-44 umschreiben.

    Die Klasse nutzt nichts aus der Basisklasse Extension; es reicht, die
    Imports zu ersetzen und init() anzuhängen, das die alte Shell aufruft.
    """
    lines = js.splitlines()
    imports = [i for i, line in enumerate(lines) if line.startswith("import ")]
    head = "export default class TaskbarCatSensor extends Extension {"
    if not imports or lines.count(head) != 1:
        raise ValueError("extension.js hat nicht den erwarteten Aufbau")
    out = []
    for i, line in enumerate(lines):
        if i == imports[0]:
            out.append("const {Gio, GLib, Meta} = imports.gi;")
        elif i in imports:
            continue
        elif line == head:
            out.append("class TaskbarCatSensor {")
        else:
            out.append(line)
    out += ["", "function init() {", "    return new TaskbarCatSensor();", "}", ""]
    meta = json.loads(metadata)
    meta["shell-version"] = LEGACY_SHELLS
    return {"extension.js": re.sub(r"\n{3,}", "\n\n", "\n".join(out)),
            "metadata.json": json.dumps(meta, indent=4, ensure_ascii=False) + "\n"}


def extension_texts(shell: int | None = None) -> dict[str, str]:
    """Inhalt der Extension-Dateien passend zur Shell; unbekannt -> aktuelle Fassung."""
    texts = {name: src.read_text(encoding="utf-8") for name, src in extension_sources().items()}
    if shell is not None and shell < MODULES_SINCE:
        return legacy_extension(texts["extension.js"], texts["metadata.json"])
    return texts


class GnomeBackend(Backend):
    name = "gnome"
    label = "GNOME Shell (Mutter)"
    qt_platform = "xcb"            # über XWayland, siehe Modulkommentar
    overlay_qml = "overlay_x11.qml"

    def __init__(self, connection=None):
        super().__init__(connection)
        self._hint: str | None = None

    def _extensions(self) -> QDBusInterface:
        return QDBusInterface(SERVICE, OBJECT, SERVICE, self._conn)

    # --- Extension einrichten ---

    @staticmethod
    def install_extension(shell: int | None = None) -> bool:
        """Mitgelieferte Extension (passend zur Shell-Version) nach ~/.local/share kopieren.

        Gibt True zurück, wenn sich dabei etwas geändert hat; der Shell-Code wird
        beim Aktivieren eingelesen, geänderter Code braucht also ein Reload.
        """
        target = extension_dir()
        changed = False
        target.mkdir(parents=True, exist_ok=True)
        for name, text in extension_texts(shell).items():
            dest = target / name
            if not dest.is_file() or dest.read_text(encoding="utf-8") != text:
                dest.write_text(text, encoding="utf-8")
                changed = True
        return changed

    @staticmethod
    def remove_extension() -> None:
        target = extension_dir()
        for name in ("metadata.json", "extension.js"):
            try:
                (target / name).unlink()
            except FileNotFoundError:
                pass
        try:
            target.rmdir()
        except OSError:
            pass

    def _state(self) -> int:
        reply = self._extensions().call("GetExtensionInfo", EXTENSION_UUID)
        if reply.type() != QDBusMessage.MessageType.ReplyMessage or not reply.arguments():
            return 0
        info = reply.arguments()[0]
        if not isinstance(info, dict) or "state" not in info:
            return 0
        try:
            return int(info["state"])
        except (TypeError, ValueError):
            return 0

    # --- Sensor ---

    def start_sensor(self) -> None:
        self._hint = None
        try:
            changed = self.install_extension(shell_version())
        except (OSError, ValueError) as e:
            self._hint = f"Extension nicht eingerichtet: {e}"
            print(f"taskbar-cat: {self._hint}", file=sys.stderr)
            return
        ext = self._extensions()
        if changed and self._state() != 0:
            ext.call("ReloadExtension", EXTENSION_UUID)   # alter Code hängt sonst im Cache
        ext.call("EnableExtension", EXTENSION_UUID)
        state = self._state()
        # vor GNOME 45 lädt ReloadExtension nichts nach, die Shell kennt noch die alte Fassung
        if state == STATE_UNKNOWN or (changed and state in (STATE_ERROR, STATE_OUT_OF_DATE)):
            self._hint = ("GNOME-Extension eingerichtet, aber noch nicht geladen - bitte einmal "
                          "neu anmelden. Bis dahin läuft die Katze nur auf dem Bildschirmboden.")
        elif state in (STATE_ERROR, STATE_OUT_OF_DATE):
            self._hint = f"GNOME-Extension meldet einen Fehler (Zustand {state})."
        if self._hint:
            print(f"taskbar-cat: {self._hint}", file=sys.stderr)

    def stop_sensor(self) -> None:
        """Die Extension bleibt eingeschaltet; sie sendet nur, solange die Katze läuft."""

    def sensor_loaded(self) -> bool:
        return self._state() in (STATE_ENABLED, STATE_ENABLING)

    # --- Overlay ---

    def set_input_region(self, window, rects) -> None:
        """XShape statt Qt-Maske: die beschnitte auf X11 auch das Bild."""
        boxes = [(r.x(), r.y(), r.width(), r.height()) for r in rects]
        if not _x11.set_input_region(int(window.winId()), boxes):
            super().set_input_region(window, rects)   # ohne XShape wenigstens das

    def hint(self) -> str | None:
        return self._hint
