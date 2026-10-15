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
- Ziehen und loslassen: werfen; wer sie dabei wild hin und her schüttelt, darf hinterher die Pfütze bewundern
- Mit dem Mauszeiger neben der Katze fuchteln: sie spielt und versucht zu fangen
- Rechtsklick auf Katze oder Tray-Icon: Menü (Füttern, Schlafen, Zum Boden, Pause, Autostart, Einstellungen, ...)
- Linksklick aufs Tray-Icon: füttern; steht ein Napf, kommt das Futter dort hinein (bis zu 3 Portionen)
- "Inventar ...": Katzenbett, Napf, Wollknäuel und Kratzbaum aufstellen oder einlagern; aufgestellte Möbel fallen auf den Boden oder eine Fensterkante, fahren mit dem Fenster mit und fallen herunter, wenn es verschwindet; mit der Maus lassen sie sich verschieben, Rechtsklick darauf lagert sie ein
- Mit Napf geht die Katze selbst fressen, sobald eine Portion reinpasst; steht er nah an einer Fenster- oder Kratzbaumkante, stupst sie ihn ab und zu hinunter: er landet umgedreht, das Futter liegt daneben, und so bleibt es, bis man ihn mit der Maus aufhebt (umgekippt kommt beim Füttern nichts hinein, sie bekommt es direkt); mit Bett schläft sie darin; ein Wollknäuel stupst sie ab und zu über den Boden und jagt hinterher ("Mit Wolle spielen" in den Einstellungen), das Knäuel lässt sich auch werfen und bleibt auf Fenstern liegen; am Kratzbaum kratzt sie oder springt auf die Liegefläche, die wie eine Fensterkante begehbar ist ("Kratzbaum" in den Einstellungen). Fehlt ein Möbel (eingelagert, leer, auf gesperrtem Monitor), macht sie es wie vorher
- Großer Kratzbaum (nicht im Inventar, sondern über "Große Kratzbäume" -> "Neuen aufstellen" oder "Sammlung ..."; Rechtsklick -> "Entfernen"): Aufbau aus Pfeilern, Liegebrettern mit Ästen, Hängematten, Höhle und Bällchen, der sich aus Breite und Höhe ergibt und bei jeder Größe neu gewürfelt wird. Mausrad über dem Baum ändert fließend die Höhe, seitliches Scrollen die Breite. An den oberen Bildschirmrand gezogen klebt er dort und hängt herab. Die Katze springt von Fläche zu Fläche, läuft auch auf dem Sockel, klettert an den Pfeilern hoch, kratzt daran und schläft schaukelnd in den Hängematten, die unter ihr durchhängen. In die Höhle eines stehenden Baums schlüpft sie hinein und schaut mit dem Kopf aus der Tür, schläft dort, wenn sie müde ist, und duckt sich weg oder springt heraus, wenn die Maus vorbeikommt ("Großer Kratzbaum" in den Einstellungen)
- Rechtsklick auf einen großen Kratzbaum: "Variante speichern ..." merkt sich einen gelungenen Aufbau unter einem Namen; "Sammlung ..." zeigt alle gespeicherten mit Vorschaubild zum Aufstellen, Umbenennen und Löschen; "Gespeicherte Variante übernehmen" baut den angeklickten Baum um
- "Einstellungen ..." -> "Fellfarbe": Farbwähler; Streifen, Kontur, Brust, Augen und die traurige/kranke Variante werden daraus berechnet
- "Einstellungen ..." -> "Tigerung": 0 % einfarbig, 100 % wie gewohnt, bis 200 % mit zusätzlichen Streifen
- "Einstellungen ...": Größe, Tempo, Sprungweite, Verfallszeiten, Futter-/Streichelmenge und Wahrscheinlichkeiten für Sprung, Klettern, Hängen und Putzen; Werte greifen sofort
- "Einstellungen ..." -> "Schütteln macht übel": abschalten, wenn sie wildes Herumschleudern vertragen soll; daneben steht, wie viele Richtungswechsel sie aushält
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
- Möbel (Standort, Futter im Napf, umgekippter Napf, Größe der großen Kratzbäume): `$XDG_DATA_HOME/taskbar-cat/furniture.json`
- Gespeicherte Kratzbaum-Varianten: `$XDG_DATA_HOME/taskbar-cat/bigtree-favorites.json`
- Einstellungen: `$XDG_CONFIG_HOME/taskbar-cat/config.json` (Standard `~/.config/...`)
- Autostart: `$XDG_CONFIG_HOME/autostart/taskbar-cat.desktop`
- Sprite-Cache: `$XDG_CACHE_HOME/taskbar-cat/` (Standard `~/.cache/...`), je Fellfarbe und Tigerung ein Spritesheet
- KWin-Sensor und Desktop-Vorlage: `taskbar_cat/kwin/`, `taskbar_cat/data/` (Paketdateien)
- KWin-Script-Logs: `journalctl --user -f | grep -i kwin`
- Icon neu erzeugen: `python3 -m taskbar_cat.sprites --icon ~/pfad/icon.png` (`--size`, `--mood`, `--color`, `--tabby`, `--atlas`; `--help` zeigt alles)

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
