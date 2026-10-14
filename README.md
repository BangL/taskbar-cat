# Taskbar-Cat

Pixel-Art-Katze (Tamagotchi) für KDE Plasma 6 / Wayland. Lebt am unteren Rand der Arbeitsfläche und auf Fensteroberkanten aller Monitore.

## Voraussetzungen

Systempakete (Arch): `python-pyqt6`, `pyside6`/`qt6-declarative` (QtQml/QtQuick), `qt6-wayland`, `layer-shell-qt` bzw. `qml6-module-org-kde-layershell`, `python-dbus`. Tests: `python-pytest`.

## Start

Aus dem Clone, ohne Installation:

    python3 -m taskbar_cat             # normal
    python3 -m taskbar_cat --debug     # Plattformen, Wände und Decken als Linien einblenden
    python3 -m taskbar_cat --help       # Optionen anzeigen
    python3 -m taskbar_cat --version
    python3 -m taskbar_cat.bus --dump  # nur Fenster-Sensor testen

Installiert (siehe unten) zusätzlich als `taskbar-cat`.

## Installation

Desktop-Eintrag und Icon für den aktuellen Benutzer, ohne root:

    ./install.sh              # Startmenü-Eintrag + Icon
    ./install.sh --autostart  # zusätzlich beim Anmelden starten
    ./install.sh --uninstall  # wieder entfernen

Den Autostart kann man danach jederzeit über den Haken im Menü der Katze
umschalten; bei Installation über ein Paket ist das der einzige nötige Weg.

Das Skript ermittelt das Startkommando selbst: ist das Paket installiert, wird
`taskbar-cat` benutzt, sonst `python3 -m taskbar_cat` aus diesem Verzeichnis.
In `data/taskbar-cat.desktop` steht deshalb kein fester Pfad.

Als Python-Paket (eigenes venv oder `--user`):

    pip install .      # legt den Startbefehl `taskbar-cat` an

## Bedienung

- Klick oder Maus über der Katze hin- und herreiben: streicheln
- Ziehen und loslassen: werfen
- Mit dem Mauszeiger neben der Katze fuchteln: sie spielt und versucht zu fangen
- Rechtsklick auf Katze oder Tray-Icon: Menü (Füttern, Schlafen, Zum Boden, Pause, Autostart, Einstellungen, ...)
- Linksklick aufs Tray-Icon: füttern
- "Einstellungen ...": Größe, Tempo, Verfallszeiten, Futter-/Streichelmenge und Wahrscheinlichkeiten für Sprung, Klettern und Hängen; Werte greifen sofort
- "Beim Anmelden starten": Haken verwaltet `~/.config/autostart/taskbar-cat.desktop`

## Dateien

- Zustand: `$XDG_DATA_HOME/taskbar-cat/state.json` (Standard `~/.local/share/...`)
- Einstellungen: `$XDG_CONFIG_HOME/taskbar-cat/config.json` (Standard `~/.config/...`)
- Autostart: `$XDG_CONFIG_HOME/autostart/taskbar-cat.desktop`
- Sprite-Cache: `$XDG_CACHE_HOME/taskbar-cat/` (Standard `~/.cache/...`)
- KWin-Sensor und Desktop-Vorlage: `taskbar_cat/kwin/`, `taskbar_cat/data/` (Paketdateien)
- KWin-Script-Logs: `journalctl --user -f | grep -i kwin`
- Icon neu erzeugen: `python3 -m taskbar_cat.sprites --icon ~/pfad/icon.png` (`--size`, `--mood`, `--atlas`; `--help` zeigt alles)

## Tests

    python3 -m pytest

## Bekannte offene Punkte

- "Miau"-Sprechblase bei traurig fehlt (steht in der Spec).
- Seitliche Panels: Katze kann am Bodenrand abprallen, durchfallen und wird neu gesetzt.
- "Schlafen schicken" wirkt nicht, wenn die Energie >= 80 ist.
- Füttern im Sprung macht sie beim nächsten Fressen 60 s träge, obwohl nicht überfüttert.
- Laufen nutzt ungekapptes dt; nach einem Hänger der App läuft sie ein Stück zu weit.
- KWin-Script sendet bei jeder Fenstergeometrie-Änderung das komplette JSON (unkritisch).

## Lizenz

MIT, siehe `LICENSE`.
