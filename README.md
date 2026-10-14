# Taskbar-Cat

Pixel-Art-Katze (Tamagotchi) für KDE Plasma 6 / Wayland. Lebt am unteren Rand der Arbeitsfläche und auf Fensteroberkanten aller Monitore; freischwebende Docks und Panels, die keinen Platz reservieren, sind ebenfalls begehbar.

## Voraussetzungen

Systempakete (Arch): `python-pyqt6` (enthält QtCore, QtDBus, QtGui, QtQml, QtWidgets), `qt6-declarative`, `qt6-wayland`, `layer-shell-qt` (liefert das QML-Modul `org.kde.layershell`). Für die Tests: `python-pytest`.

Auf anderen Distributionen heißen die Pakete anders, etwa `python3-pyqt6` und
`qml6-module-org-kde-layershell` unter Debian/Ubuntu.

## Start

Aus dem Clone, ohne Installation:

    python3 -m taskbar_cat             # normal
    python3 -m taskbar_cat --debug     # Plattformen, Wände und Decken als Linien einblenden
    python3 -m taskbar_cat --help      # Optionen anzeigen
    python3 -m taskbar_cat --version   # Version
    python3 -m taskbar_cat --status     # Status in einer Zeile, dann beenden
    python3 -m taskbar_cat.bus --dump  # nur Fenster-Sensor testen

Installiert (siehe unten) zusätzlich als `taskbar-cat`.

## Installation

Arch Linux (AUR), baut aus dem aktuellen Stand von `main`:

    paru -S taskbar-cat-git     # oder yay -S taskbar-cat-git

Damit liegt der Startbefehl `taskbar-cat` in `/usr/bin`, der Startmenü-Eintrag
und das Icon sind mit installiert; der Autostart läuft über den Haken im Menü
der Katze.

Debian und Ubuntu: `.deb` aus den
[Releases](https://github.com/BangL/taskbar-cat/releases) herunterladen und

    sudo apt install ./taskbar-cat_*_all.deb

Es braucht Plasma 6 mit KWin unter Wayland, also Debian 13 oder Ubuntu 24.10
und neuer. Selbst bauen geht auch:

    python3 -m build --wheel
    packaging/build-deb.sh

### Aus dem Clone

Desktop-Eintrag und Icon für den aktuellen Benutzer, ohne root:

    ./install.sh              # Startmenü-Eintrag + Icon
    ./install.sh --autostart  # zusätzlich beim Anmelden starten
    ./install.sh --uninstall  # wieder entfernen

Den Autostart kann man danach jederzeit über den Haken im Menü der Katze
umschalten; bei Installation über ein Paket ist das der einzige nötige Weg.

Das Skript ermittelt das Startkommando selbst: ist das Paket installiert, wird
`taskbar-cat` benutzt, sonst `python3 -m taskbar_cat` aus diesem Verzeichnis.
In der Vorlage `taskbar_cat/data/taskbar-cat.desktop` steht deshalb kein fester Pfad.

Als Python-Paket (eigenes venv oder `--user`):

    pip install .      # legt den Startbefehl `taskbar-cat` an

## Bedienung

- Klick oder Maus über der Katze hin- und herreiben: streicheln
- Ziehen und loslassen: werfen
- Mit dem Mauszeiger neben der Katze fuchteln: sie spielt und versucht zu fangen
- Rechtsklick auf Katze oder Tray-Icon: Menü (Füttern, Schlafen, Zum Boden, Pause, Autostart, Einstellungen, ...)
- Linksklick aufs Tray-Icon: füttern
- "Einstellungen ..." -> "Fellfarbe": Farbwähler; Streifen, Kontur, Brust, Augen und die traurige/kranke Variante werden daraus berechnet
- "Einstellungen ...": Größe, Tempo, Verfallszeiten, Futter-/Streichelmenge und Wahrscheinlichkeiten für Sprung, Klettern und Hängen; Werte greifen sofort
- "Einstellungen ..." -> "Monitore": je ein Haken pro Monitor legt fest, wo die Katze laufen darf (mindestens einer bleibt an); von einem gesperrten Monitor läuft sie selbst hinüber
- "Beim Anmelden starten": Haken verwaltet `~/.config/autostart/taskbar-cat.desktop`

## Status abfragen

    taskbar-cat --status
    Sättigung 72% | Zuneigung 56% | Energie 80% | zufrieden

    taskbar-cat --status --json
    {"satiety": 72.4, ..., "mood": "zufrieden", "state": "idle_sit", "paused": false, "running": true}

Die Werte kommen live über D-Bus aus der laufenden Katze. Läuft keine, wird der
gespeicherte Zustand gelesen und die Ausgabe mit `(nicht gestartet)` markiert;
der Exit-Code ist in beiden Fällen 0.

Einbau in fastfetch (`~/.config/fastfetch/config.jsonc`):

```jsonc
{
  "type": "command",
  "key": "Katze",
  "text": "taskbar-cat --status"
}
```

## Dateien

- Zustand: `$XDG_DATA_HOME/taskbar-cat/state.json` (Standard `~/.local/share/...`)
- Einstellungen: `$XDG_CONFIG_HOME/taskbar-cat/config.json` (Standard `~/.config/...`)
- Autostart: `$XDG_CONFIG_HOME/autostart/taskbar-cat.desktop`
- Sprite-Cache: `$XDG_CACHE_HOME/taskbar-cat/` (Standard `~/.cache/...`), je Fellfarbe ein Spritesheet
- KWin-Sensor und Desktop-Vorlage: `taskbar_cat/kwin/`, `taskbar_cat/data/` (Paketdateien)
- KWin-Script-Logs: `journalctl --user -f | grep -i kwin`
- Icon neu erzeugen: `python3 -m taskbar_cat.sprites --icon ~/pfad/icon.png` (`--size`, `--mood`, `--color`, `--atlas`; `--help` zeigt alles)

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

## Release bauen

Ein Tag mit `v`-Präfix startet den Workflow `.github/workflows/release.yml`:
Tests, Wheel, sdist und `.deb` werden gebaut und als GitHub-Release mit
automatisch erzeugten Notes veröffentlicht.

    # Version in pyproject.toml anheben, committen, dann:
    git tag -a v1.4.0 -m "Taskbar-Cat 1.4.0"
    git push origin v1.4.0

Der Workflow bricht ab, wenn der Tag nicht zur Version in `pyproject.toml` passt.
