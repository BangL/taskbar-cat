"""Schnittstelle der Desktop-Backends.

Ein Backend kapselt alles, was sich zwischen den Arbeitsumgebungen unterscheidet:
das Qt-Plattform-Plugin, das Overlay-Fenster (QML-Datei samt Input-Region) und
der Sensor, der Monitore und Fenster meldet. Alles andere im Programm baut nur noch darauf auf -
neue Funktionen brauchen deshalb keinen Code pro Arbeitsumgebung.

Das Sensor-Protokoll ist für alle Backends dasselbe: der Sensor ruft über D-Bus
``de.bangl.TaskbarCat.update`` mit dem JSON, das ``World.from_json`` liest, und
``cursor`` mit "x y". Ein Backend muss also nur dafür sorgen, dass sein Sensor
läuft; auswerten tut es immer derselbe Code.
"""


from PyQt6.QtCore import QRect
from PyQt6.QtGui import QRegion

NO_INPUT = QRegion(QRect(-10, -10, 1, 1))  # leere Region hieße "ganzes Fenster"


class Backend:
    name = "?"            # Kurzname, auch für TASKBAR_CAT_BACKEND
    label = "?"           # Anzeigename für Statusmeldungen
    qt_platform: str | None = None   # Wert für QT_QPA_PLATFORM, None = Qt entscheidet
    overlay_qml = "overlay.qml"      # Fenster-Hülle in taskbar_cat/ui/

    def __init__(self, connection=None):
        """connection: QDBusConnection der Sitzung, oder None für Tests."""
        self._conn = connection

    # --- Sensor ---

    def start_sensor(self) -> None:
        """Sensor starten (KWin-Script laden, GNOME-Extension einschalten)."""

    def stop_sensor(self) -> None:
        """Sensor beenden; wird beim Verlassen des Programms gerufen."""

    def sensor_loaded(self) -> bool:
        """Läuft der Sensor noch? Der Watchdog in CatBus fragt damit nach."""
        return True

    # --- Overlay ---

    def set_input_region(self, window, rects) -> None:
        """Flächen des Overlays, die Mausereignisse bekommen; der Rest ist durchlässig.

        rects: QRect in Fensterkoordinaten, leer = gar keine. Unter Wayland macht
        das die Qt-Maske; sie beschneidet dort nur den Input, nicht das Bild.
        """
        region = QRegion()
        for r in rects:
            region = region.united(r)
        window.setMask(region if rects else NO_INPUT)

    def hint(self) -> str | None:
        """Fehlt eine Voraussetzung, hier der Hinweis dafür; sonst None."""
        return None
