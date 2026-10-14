# Taskbar-Cat - Design-Spec

Stand: 2026-10-14

## Ziel

Pixel-Art-Katze als Tamagotchi, die auf dem "Boden" (Unterkante der Arbeitsfläche) und auf den oberen Kanten von Fenstern lebt, auf allen Monitoren. Sie muss gefüttert und gestreichelt werden; bei Vernachlässigung wird sie traurig bzw. krank, stirbt aber nie und läuft nicht weg.

## Umgebung

- KDE Plasma 6.6, KWin Wayland, 3 Monitore nebeneinander (je 1920x1080, gleiche Höhe).
- Panel des Users liegt oben; muss aber für jede Panel-Position funktionieren.
- System-Qt 6.10, `python3-pyqt6` (+ qtqml, qtquick), `qml6-module-org-kde-layershell`, `python3-dbus`.
- Tests: `pytest` (muss installiert werden: `python3-pytest`).

## Architektur

Projekt: `~/Projects/taskbar-cat/`

```
pyproject.toml               Paket + Startbefehl `taskbar-cat`
install.sh                   Desktop-Eintrag/Icon benutzerlokal, Pfad zur Install-Zeit
packaging/build-deb.sh       .deb aus dem Wheel (Architecture: all, dist-packages)
.github/workflows/release.yml  Tag v* -> Tests, Wheel, sdist, .deb, GitHub-Release
data/taskbar-cat.desktop     Vorlage ohne festen Pfad (Exec=taskbar-cat)
taskbar_cat/
  kwin/taskbar-cat-sensor.js KWin-Script, Fenster-Sensor (Paketdatei)
  paths.py                   XDG-Verzeichnisse, mitgelieferte Dateien auflösen
  config.py                  einstellbare Werte + SPECS (Grenzen, Beschriftung)
  status.py                  Statustexte für Tray-Tooltip, Dialog und Konsole
  autostart.py               ~/.config/autostart/taskbar-cat.desktop verwalten
  data/taskbar-cat.desktop   Desktop-Vorlage (Paketdatei, kein fester Pfad)
  ui/settings.py             Einstellungsdialog, aus config.SPECS aufgebaut
  __main__.py                Start, Single-Instance, Verdrahtung
  bus.py                     D-Bus-Service, KWin-Script laden/entladen, ScreenSaver-Signal
  world.py                   Weltmodell: Plattformen aus Fenstern + Arbeitsflächen (rein, kein Qt)
  cat.py                     Bedürfnisse, Zustandsautomat, Physik (rein, kein Qt)
  storage.py                 state.json laden/speichern
  sprites.py                 Pixel-Art prozedural erzeugen -> Spritesheet-PNG
  ui/overlay.qml             Layer-Shell-Overlay je Monitor
  ui/overlay.py              Overlay-Verwaltung, Input-Region, Maus-Events
  ui/tray.py                 Tray-Icon + Menü
tests/                       pytest für world, cat, storage
autostart/taskbar-cat.desktop
```

Datenfluss: KWin-Script -> D-Bus -> `world` -> `cat.tick(dt)` mit 30 FPS -> Overlay zeichnet Sprite an Position.

### 1. KWin-Fenster-Sensor (`taskbar_cat/kwin/taskbar-cat-sensor.js`)

- Hört auf: `workspace.windowAdded`, `windowRemoved`, `windowActivated`, `currentDesktopChanged`, `screensChanged`, je Fenster `frameGeometryChanged`, `minimizedChanged`, `fullScreenChanged`, Stapeländerung (`workspace.stackingOrderChanged`).
- Sendet bei jeder Änderung (KWin-JS hat keine Timer; Drosselung/Zusammenfassen passiert in der App, die nur das neueste Update pro Tick verarbeitet) per `callDBus("de.bangl.TaskbarCat", "/", "de.bangl.TaskbarCat", "update", json)`.
- JSON: 
  - `outputs`: je Monitor `name`, `geometry` (x,y,w,h), `workArea` = `workspace.clientArea(KWin.MaximizeArea, output, currentDesktop)`.
  - `windows`: sichtbare Fenster auf aktuellem Desktop (keine Dialoge vom Typ Popup/Tooltip/Notification, keine minimierten): `id`, `x`, `y`, `w`, `h`, `stack` (Index in `stackingOrder`), `fullScreen`, `maximized`, `panel`. Enthalten sind normale Fenster (`normalWindow`) und Leisten (`dock`, nicht `hidden`, also kein eingeklapptes Auto-Hide-Panel); `panel: true` markiert letztere.
- Beim Laden sendet das Script sofort ein vollständiges Update.

### 2. Weltmodell (`world.py`)

- Eingabe: Outputs + Fenster. Ausgabe: Liste von Plattformen `(x1, x2, y, owner)`, `owner` = Fenster-ID oder `floor:<output>`.
- Gesperrte Monitore aus `blocked_outputs` landen in `World.blocked` und damit in `forbidden_outputs`. Namen, die es gerade nicht gibt, werden ignoriert; wären alle Monitore gesperrt, gilt keine Sperre. Steht die Katze auf einem gesperrten Monitor (Wurf, nachträglich gesperrt), zieht sie um (`spawn`), statt sich wie bei Vollbild nur zu verstecken - Vollbild ist vorübergehend, eine Sperre nicht.
- Boden je Monitor: Unterkante der `workArea`, über die Breite der `workArea`. Folge: Panel unten -> Katze läuft auf dem Panel; Panel oben/seitlich/fehlt -> Katze läuft am unteren Bildschirmrand.
- Fensterkante: Oberkante des Rahmens, nur der Teil innerhalb der `workArea` des Monitors. Nicht begehbar, wenn die Kante auf/über der Oberkante der `workArea` liegt (z.B. maximierte Fenster).
- Leisten (`panel: true`) liefern nur ihre Oberkante als Plattform, keine Wände und keine Decken. Leisten, die Platz reservieren, fallen durch die Regeln oben heraus (ihre Oberkante ist dann schon der Boden bzw. liegt auf der `workArea`-Oberkante); begehbar werden dadurch vor allem freischwebende Docks und Panels mit "Fenster können abdecken".
- Verdeckung: Teilstücke einer Kante, die von einem höher gestapelten Fenster überdeckt sind (Kante liegt innerhalb dessen Rechteck), werden herausgeschnitten. Stücke < 40 px werden verworfen.
- Vollbild-Fenster auf einem Monitor -> Monitor gilt als "verboten"; Katze darf ihn nicht betreten; ist sie dort, versteckt sie sich (unsichtbar, Logik läuft weiter).
- Wände: linke/rechte Fensterkante (`Wall(x, y1, y2, owner, side)`), auf Arbeitsfläche geschnitten, mind. 30 px Abstand zum Arbeitsflächenrand, Verdeckung durch höhere Fenster herausgeschnitten, Stücke < 40 px verworfen.
- Decken: Fensterunterkanten (`Ceiling(x1, x2, y, owner)`), nur wenn oberhalb des Bodens; Verdeckung wie bei Plattformen.
- Abfragen: `platform_below(x, y)`, `reachable(from, x, max_up, max_side=400)`, `walls_near(...)`, `ceilings_near(...)`.

### 3. Katze (`cat.py`)

Bedürfnisse (0-100, Start je 80), Zeit läuft nur bei laufender App und entsperrtem Bildschirm:

| Wert | Verfall | Auffüllen |
|------|---------|-----------|
| Hunger (Sättigung) | 100 -> 0 in 8 h | Füttern +40 (Fressanimation 3 s); >100 gedeckelt, dann 60 s "satt-träge" |
| Zuneigung | 100 -> 0 in 4 h | Streichelbewegung oder Klick +2 (Schnurren + Herzchen) |
| Energie | -1/min beim Laufen/Springen, -0.2/min sonst | +2/min beim Schlafen |

Stimmung:
- **normal**: Sättigung >= 20 und Zuneigung >= 20.
- **traurig**: Sättigung < 20 oder Zuneigung < 20. Ohren hängend, halbe Laufgeschwindigkeit, gelegentlich "Miau"-Sprechblase.
- **krank**: beide < 10, oder einer der Werte länger als 2 h (Session-Zeit) < 10. Grünliche Färbung, bleibt auf dem Boden, springt nicht auf Fenster, liegt meist.
- Erholung: traurig/krank endet, sobald beide Werte >= 40.

Verhaltenszustände: `idle_sit`, `walk`, `approach`, `jump`, `fall`, `climb`, `hang`, `sleep`, `eat`, `purr`, `dragged`, `thrown`, `sick_lie`, `hidden`.
- Zufällige Wahl zwischen sitzen, laufen, Sprung zu erreichbarer Plattform; bei Energie < 20 schlafen bis 80.
- Plattform verschwindet/bewegt sich: fährt mit, wenn das Fenster bewegt wird (Delta der Fensterposition übernehmen); verschwindet die Kante unter ihr -> `fall`.
- Physik: Schwerkraft 2500 px/s², Sprünge als ballistische Kurve, Landung auf erster Plattform, deren y überquert wird.
- Neue Aktion wählen: 15 % Sprung, 15 % Klettern, 10 % Unterkante, sonst 50/50 sitzen/laufen (jeweils nur, wenn ein Ziel existiert).
- **Riesensprung:** jede sichtbare Oberkante ist erreichbar, Höhe unbegrenzt, seitlich max. 400 px; Ziele, deren Scheitel das Sprite über den Bildschirm schieben würde, sind ausgeschlossen.
- **Klettern:** zur Wand laufen (max. 400 px), Fuß der Wand max. 300 px über der Katze (sonst Sprung an die Wand), mit 80 px/s (traurig 40) hochklettern, oben auf die Oberkante desselben Fensters steigen. Ist die Oberkante verdeckt oder nicht begehbar -> abspringen. Fährt mit dem Fenster mit; Fenster weg -> fallen.
- **Unterkante:** Unterkante 113-300 px über der Katze -> hochspringen, 1,5-3 s zappelnd hängen, dann fallen.
- **Spielen (Mauszeiger fangen):** KWin-Sensor meldet `workspace.cursorPos` (max. ~30/s, D-Bus-Methode `cursor(s "x y")`). Fuchteln = Cursor <= 300 px um die Katzenmitte, >= 500 px Weg und >= 2 Richtungswechsel in 1 s, nicht direkt über dem Sprite (das ist Streicheln). Spielmodus hält 2 s nach dem letzten Fuchteln. Cursor über ihr (|dx| < 120, 120-350 px höher) -> Sprung mit Pfotenhieb; Cursor < 200 px -> 0,5-1 s lauern, dann Sprung mit Scheitel am Cursor; sitzt sie auf einer Kante und der Cursor ist mehr als 40 px unter ihren Pfoten, zählt nur der seitliche Abstand (< 200 px) und sie springt hinunter (die eigene Kante wird beim Landen übersprungen, vom Boden aus gibt es keinen Sprung nach unten); sonst hinrennen (150 px/s). Cursor im Sprite während des Sprungs = gefangen: Zuneigung +3, nach Landung 1,2 s Jubel. Kein Spiel bei krank, Energie < 20, schlafen, fressen, gezogen, klettern, hängen.
- Krank: kein Springen, Klettern, Hängen; beim Erkranken während Klettern/Hängen -> fallen.
- Monitorwechsel: über benachbarte Plattformen (Boden ist über Monitorgrenzen zusammenhängend, da gleiche Höhe; falls nicht, Sprung).

### 4. UI

- **Overlay** (`ui/overlay.qml` + `overlay.py`): je Monitor ein `LayerShell.Window`, Layer `overlay`, Anker alle Seiten, `exclusionZone: -1` (ignoriert Panels, Overlay deckt ganzen Monitor), keine Tastatur-Interaktivität, transparent. Input-Region (`QWindow.setMask`) nur das Katzen-Rechteck (+8 px), sonst gehen Klicks durch. Nur das Overlay des Monitors, auf dem die Katze ist, zeigt sie (beim Übergang beide).
- **Sprites** (`sprites.py`): 32x32-Pixel-Art, Darstellung 3x skaliert (Nearest Neighbour). Animationen: sitzen, laufen (4 Frames), springen, fallen, schlafen (Zzz), fressen (Napf), schnurren (Herz), zappeln, liegen (krank), klettern (4 Frames), hängen (2 Frames), lauern, Pfotenhieb, Jubel (je 2 Frames), Varianten für traurig (Ohren) und krank (Tönung). Blickrichtung durch Spiegeln. PNG wird beim ersten Start erzeugt und gecacht.
- **Interaktion:**
  - Linksklick: streicheln (+2 Zuneigung).
  - Reiben: >= 3 Richtungswechsel der Maus über der Katze innerhalb 1 s = eine Streichelbewegung.
  - Drag (Maus gedrückt + > 6 px Bewegung): `dragged`, Katze folgt Cursor (auch über Monitore); Loslassen -> `thrown` mit Mausgeschwindigkeit der letzten 100 ms.
  - Rechtsklick-Menü: Füttern, Streicheln, Schlafen schicken, Zum Boden rufen, Status, Pausieren (versteckt + Zeit eingefroren), "Beim Anmelden starten" (Haken, verwaltet die Autostart-Datei), "Einstellungen ...", Beenden.
  - **Einstellungen** (`ui/settings.py`): Dialog aus `config.SPECS` erzeugt, Werte greifen sofort und werden in `config.json` gespeichert; Knopf für Standardwerte. Einstellbar: Sprite-Größe, Plattformlinien, Mauszeiger fangen, Lauf- und Klettergeschwindigkeit, Stunden bis Sättigung/Zuneigung leer, Futter- und Streichelmenge, Wahrscheinlichkeiten für Sprung/Klettern/Hängen.
  - **Monitore**: eigene Gruppe, ein Haken je angeschlossenem Monitor (Name, Auflösung, Position, Modell aus `QScreen`), gespeichert als Negativliste `blocked_outputs` (nicht in `SPECS`, da erst zur Laufzeit bekannt). Der letzte Haken lässt sich nicht abwählen; gesperrte, aber nicht mehr angeschlossene Monitore bleiben als Haken sichtbar, damit man sie wieder freigeben kann. Die Gruppe fehlt bei nur einem Monitor.
- **Statusabfrage:** `taskbar-cat --status` (optional `--json`) fragt die laufende Instanz über die D-Bus-Methode `status()` ab (JSON mit Bedürfnissen, Stimmung, Verhaltenszustand, Pause, Sensorzustand) und fällt ohne laufende Instanz auf `state.json` zurück (Markierung `running: false`). Formatierung in `status.py`, von Tray-Tooltip und Status-Dialog mitbenutzt.
- **Tray** (`ui/tray.py`): Icon = Katzenkopf in Stimmungsvariante; Tooltip mit Sättigung/Zuneigung/Energie und Stimmung; Linksklick = Füttern; Menü wie oben.

## Lebenszyklus

- Start über `~/.config/autostart/taskbar-cat.desktop`; `install.sh` setzt dort `taskbar-cat` (installiert) oder `python3 -m taskbar_cat` + `Path=<Clone>` ein. Kein Pfad ist eingecheckt.
- Single-Instance: D-Bus-Name `de.bangl.TaskbarCat` belegt -> zweite Instanz beendet sich.
- Beim Start: KWin-Script `taskbar-cat-sensor` entladen falls geladen, dann `loadScript` + `start` über `org.kde.KWin /Scripting`.
- Beim Beenden: Zustand speichern, Script entladen.
- Sperre: `org.freedesktop.ScreenSaver.ActiveChanged(true)` -> Zeit eingefroren, bis `false`.

## Persistenz

Einstellungen: `$XDG_CONFIG_HOME/taskbar-cat/config.json`, geschrieben bei jeder Änderung im Dialog, unbekannte Keys werden ignoriert, Werte auf die Grenzen aus `SPECS` begrenzt.

`$XDG_DATA_HOME/taskbar-cat/state.json` (Standard `~/.local/share/...`): Bedürfnisse, Zeit unter 10 je Wert, Gesamt-Session-Zeit. Speichern alle 60 s und beim Beenden (atomar: temp + rename). Nicht lesbar -> Datei nach `state.json.broken-<timestamp>` verschieben, Start mit Standardwerten. Position wird nicht gespeichert (Start immer auf dem Boden des primären Monitors).

## Fehlerbehandlung

- Watchdog: alle 10 s `isScriptLoaded("taskbar-cat-sensor")`; false oder noch nie ein Update erhalten -> Script neu laden (max. 1x pro Minute). Bis dahin nur Boden aus `QScreen.availableGeometry` (Fallback), Tray-Tooltip zeigt Warnung.
- Ungültiges JSON vom Script -> Update ignorieren, Log nach stderr.

## Tests

- `pytest` mit fester, injizierter Uhr.
- `world.py`: Boden bei Panel unten/oben/fehlend, Leisten-Oberkante als Plattform ohne Wände/Decken, maximierte Fenster nicht begehbar, Verdeckung schneidet Kanten, Mini-Stücke verworfen, Vollbild sperrt Monitor, Erreichbarkeit.
- `cat.py`: Verfallsraten, Füttern/Streicheln, Stimmungswechsel inkl. 2-h-Regel und Erholung, Einfrieren bei Sperre, Mitfahren mit Fenster, Fallen bei Kantenverlust, Wurf landet auf Plattform.
- `storage.py`: Roundtrip, kaputte Datei.
- Manuell: Overlay, Input-Durchreichung, KWin-Script, Tray. Argumente über `argparse` (`--help`, `--version`, `--debug`; unbekannte Optionen -> Exit 2), ebenso `taskbar_cat.bus` und `taskbar_cat.sprites`. Debug-Flag `--debug` zeichnet Plattformen (gelb/magenta), Wände (cyan) und Decken (rot) als Linien ins Overlay.

## Nicht im Umfang

Tod/Weglaufen, Offline-Verfall, mehrere Katzen, Sound.
