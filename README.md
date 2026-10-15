# Taskbar-Cat

Pixel-Art-Katze (Tamagotchi) für KDE Plasma 6 und GNOME. Lebt am unteren Rand der Arbeitsfläche und auf Fensteroberkanten aller Monitore; freischwebende Docks und Panels ohne reservierten Platz sind ebenfalls begehbar.

## Arbeitsumgebungen

Backend-Wahl einmal beim Start über `XDG_CURRENT_DESKTOP`; erzwingen mit `TASKBAR_CAT_BACKEND=kde|gnome`.

| | KDE Plasma (und sway, Hyprland) | GNOME |
|---|---|---|
| Fenster | Layer-Shell, Overlay-Ebene | X11 über XWayland, immer oben |
| Sensor | KWin-Script | GNOME-Shell-Extension |
| Zusatzpaket | `layer-shell-qt` | keins |

Mutter kennt kein `wlr-layer-shell`, daher läuft das Overlay unter GNOME über XWayland (auch in X11-Sitzungen).

## Voraussetzungen

Arch: `python-pyqt6`, `qt6-declarative`; Tests: `python-pytest`. KDE zusätzlich `qt6-wayland`, `layer-shell-qt`; GNOME `xorg-xwayland`.
Debian/Ubuntu: z. B. `python3-pyqt6`, `qml6-module-org-kde-layershell`.

### GNOME: Extension

Die Katze richtet die Extension beim Start selbst ein (`~/.local/share/gnome-shell/extensions/`) und aktiviert sie. **Beim allerersten Mal einmal neu anmelden**, bis dahin läuft sie nur am Bildschirmboden. Ohne Extension fehlen Fensterkanten und Fangspiel.

## Start

    python3 -m taskbar_cat             # aus dem Clone
    python3 -m taskbar_cat --debug     # Wände/Decken/Plattformen als Linien
    python3 -m taskbar_cat --status    # Status in einer Zeile
    python3 -m taskbar_cat.bus --dump  # nur Fenster-Sensor testen

Außerdem `--help`, `--version`. Installiert heißt der Befehl `taskbar-cat`.

## Installation

- Arch (AUR, baut aus `main`): `paru -S taskbar-cat-git` (Menü-Eintrag und Icon inklusive)
- Debian 13 / Ubuntu 24.10+: `.deb` aus den [Releases](https://github.com/BangL/taskbar-cat/releases), dann `sudo apt install ./taskbar-cat_*_all.deb`. Selbst bauen: `python3 -m build --wheel && packaging/build-deb.sh`
- Python-Paket: `pip install .`
- Aus dem Clone (ohne root): `./install.sh [--autostart|--uninstall]` legt Menü-Eintrag und Icon an; das Startkommando wird automatisch ermittelt

Autostart lässt sich jederzeit über den Haken im Menü der Katze umschalten (`~/.config/autostart/taskbar-cat.desktop`).

## Bedienung

- Klick / Maus hin- und herreiben: streicheln
- Ziehen und loslassen: werfen; zu wildes Schütteln macht ihr übel
- Mauszeiger neben der Katze bewegen: sie spielt und versucht zu fangen
- Rechtsklick auf Katze oder Tray-Icon: Menü (Füttern, Schlafen, Zum Boden, Pause, Autostart, Einstellungen, ...)
- Linksklick aufs Tray-Icon: füttern (mit Napf: bis zu 3 Portionen dort hinein)
- "Inventar ...": Katzenbett, Napf, Wollknäuel, Kratzbaum aufstellen/einlagern. Möbel fallen auf Boden oder Fensterkante, fahren mit dem Fenster mit, fallen bei dessen Verschwinden herunter, sind per Maus verschiebbar; Rechtsklick lagert ein

### Möbel und Verhalten

- **Napf:** sie frisst selbst, sobald eine Portion passt. Nah an einer Kante stupst sie ihn ab und zu hinunter: er landet umgedreht, das Futter daneben (dann Fliegen, die sie jagt und frisst - manchmal wird ihr davon schlecht). Bleibt so, bis man ihn aufhebt; umgekippt bekommt sie Futter direkt.
- **Bett:** sie schläft darin.
- **Wollknäuel:** sie stupst es über den Boden und jagt es ("Mit Wolle spielen"), oder umschlingt und tritt es weg ("Umschlingen und treten"; in einer Ecke immer). Es lässt sich werfen und bleibt auf Fenstern liegen.
- **Kratzbaum:** sie kratzt (Sisal franst sichtbar aus; Rechtsklick -> "Neuen Sisal"), klettert am Pfeiler, springt auf die begehbare Liegefläche und schlägt nach dem pendelnden Bällchen (Einstellungen -> "Kratzbaum").
- Fehlt ein Möbel (eingelagert, leer, gesperrter Monitor), verhält sie sich wie ohne.

### Große Kratzbäume

Über "Große Kratzbäume" -> "Neuen aufstellen" oder "Sammlung ..." (nicht im Inventar); Rechtsklick -> "Entfernen".

- Aufbau aus Pfeilern, Brettern mit Ästen, Hängematten, Höhle und Bällchen; ergibt sich aus Breite und Höhe und wird bei jeder Größe neu gewürfelt.
- Größe: Mausrad = Höhe, seitliches Scrollen = Breite (Strg + Rad ebenfalls Breite). "Festgestellt" sperrt Größe und Platz. Am oberen Bildschirmrand klebt er und hängt herab.
- Katze: springt von Fläche zu Fläche, läuft auf dem Sockel, klettert, kratzt (nach 5 Kratzern Pfeiler zerfranst; einstellbar "Sisal zerfranst nach"), schlägt nach Bällchen, jagt beim Spielen die Maus Etage für Etage, schläft in Hängematten (hängen durch) und in der Höhle (schaut aus der Tür, duckt sich oder springt heraus, wenn die Maus kommt). Einstellungen -> "Kratzbaum": "Hingehen", "Kratzen", "Höhle", "Bällchen".
- **"Hinter Fenstern"** (pro Baum): Fenster davor verdecken den Baum und die Katze darin (Höhle, Hängematte, Brett); heruntergegangen ist sie sofort wieder sichtbar. Verdeckte Stellen meidet sie und sie nehmen keine Klicks an; darauf Stehendes (Napf, Knäuel, anderer Baum, ...) wird mit verdeckt.
- **Varianten:** "Variante speichern ..." merkt sich einen Aufbau, "Sammlung ..." zeigt alle mit Vorschau (aufstellen, umbenennen, löschen), "Gespeicherte Variante übernehmen" baut den Baum um.

### Einstellungen

- "Fellfarbe": Farbwähler; Streifen, Kontur, Brust, Augen und traurige/kranke Variante werden berechnet
- "Tigerung": 0 % einfarbig, 100 % normal, bis 200 % zusätzliche Streifen
- Größe, Tempo, Sprungweite, Verfallszeiten, Futter-/Streichelmenge, Wahrscheinlichkeiten für Sprung, Klettern, Hängen, Putzen (wirken sofort)
- "Schütteln macht übel": abschaltbar, mit Schwelle für Richtungswechsel
- "Monitore": Haken pro Monitor, wo sie laufen darf (mindestens einer); von gesperrten läuft sie selbst weg
- "Beim Anmelden starten": verwaltet den Autostart-Eintrag

## Status abfragen

    $ taskbar-cat --status
    Sättigung 72% | Zuneigung 56% | Energie 80% | zufrieden

    $ taskbar-cat --status --json
    {"satiety": 72.4, ..., "mood": "zufrieden", "state": "idle_sit", "paused": false, "running": true}

Live per D-Bus aus der laufenden Katze; sonst wird der gespeicherte Zustand gelesen und mit `(nicht gestartet)` markiert. Exit-Code immer 0.

fastfetch (`~/.config/fastfetch/config.jsonc`):

```jsonc
{
  "type": "command",
  "key": "Katze",
  "text": "taskbar-cat --status"
}
```

## Dateien

- Zustand: `$XDG_DATA_HOME/taskbar-cat/state.json` (Standard `~/.local/share/...`)
- Möbel: `.../furniture.json`; gespeicherte Kratzbaum-Varianten: `.../bigtree-favorites.json`
- Einstellungen: `$XDG_CONFIG_HOME/taskbar-cat/config.json` (Standard `~/.config/...`)
- Sprite-Cache: `$XDG_CACHE_HOME/taskbar-cat/` (je Fellfarbe und Tigerung ein Spritesheet)
- Sensoren und Desktop-Vorlage: `taskbar_cat/kwin/`, `taskbar_cat/gnome/`, `taskbar_cat/data/`
- GNOME-Extension (eingerichtet): `~/.local/share/gnome-shell/extensions/taskbar-cat@bangl.github.io/`
- Sensor-Logs: `journalctl --user -f | grep -iE 'kwin|gnome-shell'`
- Weltmodell prüfen: `python3 -m taskbar_cat.bus --dump` (laufende Katze vorher beenden)
- Icon erzeugen: `python3 -m taskbar_cat.sprites --icon ~/pfad/icon.png` (`--help` für `--size`, `--mood`, `--color`, `--tabby`, `--atlas`)

## Tests

    python3 -m pytest

## Bekannte offene Punkte

- "Miau"-Sprechblase bei traurig fehlt.
- Seitliche Panels: Katze kann am Bodenrand abprallen, durchfallen und wird neu gesetzt.
- "Schlafen schicken" wirkt nicht bei Energie >= 80.
- Füttern im Sprung macht sie beim nächsten Fressen 60 s träge, obwohl nicht überfüttert.
- Laufen nutzt ungekapptes dt; nach einem Hänger läuft sie ein Stück zu weit.
- Der Sensor sendet bei jeder Geometrie-Änderung das komplette JSON (unkritisch).
- GNOME: Skalierung ungleich 100 % ungetestet.

## Lizenz

MIT, siehe `LICENSE`.

## Release bauen

Ein Tag mit `v`-Präfix startet `.github/workflows/release.yml` (Tests, Wheel, sdist, `.deb`, GitHub-Release). Bricht ab, wenn Tag und Version in `pyproject.toml` nicht übereinstimmen.

    # Version in pyproject.toml anheben, committen, dann:
    git tag -a v1.4.0 -m "Taskbar-Cat 1.4.0"
    git push origin v1.4.0
