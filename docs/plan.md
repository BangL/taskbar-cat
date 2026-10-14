# Taskbar-Cat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pixel-Art-Tamagotchi-Katze, die auf Arbeitsflächen-Boden und Fensteroberkanten aller Monitore unter KDE Plasma 6 / Wayland lebt.

**Architecture:** KWin-JS-Script meldet Fenster + Arbeitsflächen per D-Bus an eine PyQt6-App. Reine Python-Module (`needs`, `world`, `cat`, `interaction`, `storage`, `sprites`) enthalten die Logik; `ui/` zeichnet die Katze in je einem transparenten Layer-Shell-Overlay pro Monitor und stellt ein Tray-Icon bereit.

**Tech Stack:** Python 3.14, PyQt6 6.10 (QtGui, QtQml, QtQuick, QtDBus, QtWidgets für Tray-Menü), QML `org.kde.layershell`, KWin-Scripting-JS-API (Plasma 6.6), pytest.

**Spec:** `docs/spec.md`

## Global Constraints

- Projektwurzel: `~/Projects/taskbar-cat/`, Paket `taskbar_cat/`, Start `python3 -m taskbar_cat` (aus Projektwurzel).
- Nur Systempakete, keine pip-Installation.
- **Keine Git-Commits** (kein Repo; User-Regel). Statt Commit-Schritt: Testlauf grün.
- D-Bus-Service/Interface: `de.bangl.TaskbarCat`, Objektpfad `/`, Methode `update(s json)`.
- KWin-Script-Pluginname: `taskbar-cat-sensor`.
- Zustand: `~/.local/share/taskbar-cat/state.json`; Sprite-Cache: `~/.cache/taskbar-cat/atlas.png`.
- Koordinaten: global, logische Pixel (= KWin-Koordinaten = Qt-Screen-Geometrie). Katzenposition `(x, y)` = Mitte unten (Pfoten).
- Sprite 32x32, Darstellung Skalierung 3 (96x96), Nearest Neighbour.
- Tick 30 FPS; Bedürfnis-`dt` pro Tick auf max. 5 s, Physik-`dt` auf max. 0.1 s gekappt.
- Startwerte Bedürfnisse: je 80.
- UI-Texte deutsch.

## Review Focus

1. Monitor verschwindet (Laptop abgedockt, `eDP-1` weg), während die Katze darauf ist -> Katze erscheint auf dem Boden des ersten Outputs. Test: Task 4 `test_respawn_when_output_removed`.
2. Wurf über äußeren Rand aller Monitore oder nach oben raus -> prallt seitlich ab, wird oben gekappt, landet. Test: Task 4 `test_throw_bounces_off_outer_edge`, `test_throw_clamped_at_top`.
3. Suspend/Resume liefert riesiges `dt` -> kein Bedürfnis-Absturz, kein Durchtunneln von Plattformen. Test: Task 1 `test_huge_dt_is_capped`, Task 4 `test_huge_dt_does_not_tunnel`.
4. Fenster unter der Katze wird geschlossen/minimiert -> fällt auf nächste Plattform darunter. Test: Task 4 `test_falls_when_platform_disappears`.
5. Vollbild-Fenster auf dem Monitor der Katze (Video) -> Katze unsichtbar, taucht nach Ende wieder auf. Test: Task 4 `test_hidden_on_fullscreen_output`.

---

### Task 1: Gerüst + Bedürfnisse/Stimmung (`needs.py`)

**Files:**
- Create: `taskbar_cat/__init__.py` (leer), `taskbar_cat/needs.py`, `tests/test_needs.py`, `pytest.ini` (`[pytest]\ntestpaths = tests`)

**Interfaces:**
- Produces:
  - `class Mood(enum.IntEnum): NORMAL=0, SAD=1, SICK=2`
  - `@dataclass class Needs: satiety: float = 80; affection: float = 80; energy: float = 80; low_satiety_s: float = 0; low_affection_s: float = 0; session_s: float = 0; mood: Mood = Mood.NORMAL`
  - `Needs.tick(dt: float, activity: str) -> None` - `activity` in `{"active", "rest", "sleep"}`; `dt` auf 5 s gekappt; aktualisiert Werte, Zähler, `mood`.
  - `Needs.feed() -> bool` (True = überfüttert, d.h. vorher > 60), `Needs.pet() -> None`
  - `Needs.to_dict() -> dict`, `Needs.from_dict(d: dict) -> Needs` (unbekannte Keys ignorieren, fehlende = Default, Werte auf 0..100 kappen)
  - Konstanten: `SATIETY_DECAY = 100 / (8 * 3600)`, `AFFECTION_DECAY = 100 / (4 * 3600)`, Energie pro Sekunde: active `-1/60`, rest `-0.2/60`, sleep `+2/60`; `FEED_AMOUNT = 40`, `PET_AMOUNT = 2`.

Stimmungsregel (Hysterese):
```python
def compute(prev, s, a, low_s, low_a):
    raw = SICK if (s < 10 and a < 10) or low_s > 7200 or low_a > 7200 \
          else SAD if (s < 20 or a < 20) else NORMAL
    if prev != NORMAL and not (s >= 40 and a >= 40):
        return max(prev, raw)
    return raw
```
`low_*_s` wächst um `dt`, solange der Wert < 10, sonst 0.

- [ ] **Step 1: Tests schreiben** (`tests/test_needs.py`)
  - `test_satiety_empty_after_8h`: 100 -> nach 8 h (`tick(1.0)` in Schleife oder 5-s-Schritten) ~0 (±0.5).
  - `test_affection_empty_after_4h`: analog 4 h.
  - `test_energy_rates`: 60 s active -> -1; 60 s rest -> -0.2; 60 s sleep -> +2.
  - `test_feed_adds_40_and_caps`: 70 -> 100, `feed()` liefert True; 30 -> 70, False.
  - `test_pet_adds_2`.
  - `test_sad_below_20`, `test_sick_both_below_10`, `test_sick_after_2h_below_10` (satiety 5, affection 50, 7201 s ticken -> SICK).
  - `test_recovery_needs_both_40`: SICK, dann satiety=affection=35 -> bleibt SICK; 40/40 -> NORMAL.
  - `test_huge_dt_is_capped`: `tick(3600)` senkt satiety nur um `5 * SATIETY_DECAY`.
  - `test_roundtrip_dict` und `test_from_dict_clamps_and_ignores_unknown`.
- [ ] **Step 2:** `pytest tests/test_needs.py -v` -> FAIL (Modul fehlt).
- [ ] **Step 3:** `needs.py` implementieren.
- [ ] **Step 4:** `pytest tests/test_needs.py -v` -> alle PASS.

### Task 2: Persistenz (`storage.py`)

**Files:** Create `taskbar_cat/storage.py`, `tests/test_storage.py`

**Interfaces:**
- Consumes: `Needs.to_dict/from_dict`.
- Produces: `DEFAULT_PATH = Path.home() / ".local/share/taskbar-cat/state.json"`; `load(path: Path) -> Needs`; `save(path: Path, needs: Needs) -> None` (Verzeichnis anlegen, `path.with_suffix(".tmp")` schreiben, `os.replace`).
- Kaputte Datei (JSON-Fehler oder kein dict): umbenennen nach `state.json.broken-<int(time.time())>`, `Needs()` zurückgeben, Warnung auf stderr. Fehlende Datei: `Needs()`.

- [ ] **Step 1: Tests** (mit `tmp_path`): `test_missing_file_gives_defaults`, `test_roundtrip`, `test_broken_file_is_moved_aside` (Datei `"{nope"` -> Defaults, Datei `state.json.broken-*` existiert, `state.json` existiert nicht mehr), `test_save_creates_dir`.
- [ ] **Step 2:** `pytest tests/test_storage.py -v` -> FAIL.
- [ ] **Step 3:** Implementieren.
- [ ] **Step 4:** -> PASS.

### Task 3: Weltmodell (`world.py`)

**Files:** Create `taskbar_cat/world.py`, `tests/test_world.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Rect: x: float; y: float; w: float; h: float` mit Properties `right`, `bottom`, `contains(px, py) -> bool`.
  - `@dataclass(frozen=True) class Output: name: str; geometry: Rect; work_area: Rect`
  - `@dataclass(frozen=True) class Win: id: str; rect: Rect; stack: int; full_screen: bool; maximized: bool`
  - `@dataclass(frozen=True) class Platform: x1: float; x2: float; y: float; owner: str` (`owner` = Fenster-ID oder `"floor:<output>"`), Property `is_floor`.
  - `class World`: `__init__(outputs: list[Output], windows: list[Win])`; Attribute `outputs`, `windows`, `platforms: list[Platform]`, `forbidden_outputs: set[str]`.
  - `World.from_json(text: str) -> World` (wirft `ValueError` bei ungültigem Format). Format wie Spec Abschnitt 1: `{"outputs":[{"name","geometry":{x,y,w,h},"workArea":{...}}], "windows":[{"id","x","y","w","h","stack","fullScreen","maximized"}]}`.
  - `World.from_screens(screens: list[tuple[str, Rect, Rect]]) -> World` (Fallback ohne Fenster).
  - `output_at(x: float, y: float) -> Output | None` (x im Bereich `[geometry.x, geometry.right)`, y egal, wenn nur ein Output passt).
  - `platform_below(x: float, y: float, floors_only: bool = False) -> Platform | None`: Plattform mit kleinstem `p.y >= y - 1`, `x1 <= x <= x2`.
  - `platform_by_owner_at(owner: str, x: float) -> Platform | None`
  - `neighbor(p: Platform, direction: int) -> Platform | None`: Plattform mit `|y - p.y| <= 2`, die an `p.x2` (dir=+1) bzw. `p.x1` (dir=-1) mit Lücke <= 2 anschließt.
  - `reachable(p: Platform, x: float, max_up: float = 300, max_side: float = 400) -> list[Platform]`: alle anderen Plattformen mit `p.y - q.y <= max_up` (nach unten unbegrenzt) und horizontalem Abstand von `x` zum Intervall `[q.x1, q.x2]` <= `max_side`; ohne Plattformen auf `forbidden_outputs`.
  - `window_rect(win_id: str) -> Rect | None`
  - `bounds() -> Rect` (Hülle aller Output-Geometrien).

Plattform-Bau:
1. Boden je Output: `(wa.x, wa.right, wa.bottom, "floor:<name>")`.
2. Je Fenster: Kante `y = rect.y`, `[rect.x, rect.right]` geschnitten mit `work_area` des Outputs, der den Fenstermittelpunkt enthält; verwerfen, wenn `y <= wa.y + 1` oder `y >= wa.bottom`.
3. Verdeckung: von der Kante jedes Intervall abziehen, das von einem Fenster mit höherem `stack` überdeckt wird (`other.rect.y < y < other.rect.bottom` -> Intervall `[other.x, other.right]` entfernen).
4. Stücke < 40 px verwerfen.
5. `forbidden_outputs` = Outputs, deren Geometrie den Mittelpunkt eines `full_screen`-Fensters enthält. Plattformen dort bleiben in `platforms`, werden aber von `reachable` ausgeschlossen.

- [ ] **Step 1: Tests** - Hilfsfunktion `two_outputs(panel)` baut DP-3 (0,0,1920,1080) + DP-4 (1920,0,1920,1080); `panel="top"`: workArea `(x, 44, 1920, 1036)`; `panel="bottom"`: `(x, 0, 1920, 1036)`.
  - `test_floor_at_screen_bottom_when_panel_top`: Boden-y == 1080.
  - `test_floor_on_panel_when_panel_bottom`: Boden-y == 1036.
  - `test_floor_without_panel`: workArea == geometry -> 1080.
  - `test_window_top_edge_is_platform`: Fenster (100,300,800,500) -> Plattform (100, 900, 300).
  - `test_maximized_top_not_walkable`: Fenster y == 44 bei Panel oben -> keine Fensterplattform.
  - `test_occlusion_cuts_edge`: A (0,300,1000,400, stack 0), B (400,200,200,400, stack 1) -> A ergibt `[0,400]` und `[600,1000]`.
  - `test_tiny_pieces_dropped`: Verdeckung lässt 30-px-Stück -> verworfen.
  - `test_fullscreen_forbids_output`: Vollbildfenster auf DP-4 -> `"DP-4" in forbidden_outputs`, `reachable` enthält keine DP-4-Plattform.
  - `test_floors_are_neighbors_across_outputs`: `neighbor(floor DP-3, +1)` == floor DP-4.
  - `test_reachable_respects_jump_height`: Plattform 350 px höher nicht erreichbar, 250 px höher erreichbar.
  - `test_platform_below`.
  - `test_from_json_roundtrip_and_invalid` (`"[]"` -> `ValueError`).
- [ ] **Step 2:** `pytest tests/test_world.py -v` -> FAIL.
- [ ] **Step 3:** Implementieren.
- [ ] **Step 4:** -> PASS.

### Task 4: Katzenverhalten + Physik (`cat.py`)

**Files:** Create `taskbar_cat/cat.py`, `tests/test_cat.py`

**Interfaces:**
- Consumes: `Needs`, `Mood` (Task 1); `World`, `Platform`, `Rect` (Task 3).
- Produces:
  - Zustände als Strings: `"idle_sit", "walk", "jump", "fall", "sleep", "eat", "purr", "dragged", "thrown", "sick_lie", "hidden"`.
  - `class Cat`: `__init__(needs: Needs, rng: random.Random)`; Attribute `x, y, vx, vy, facing (+1/-1), state, platform: Platform | None, paused: bool, needs`.
  - `spawn(world: World) -> None`: auf Boden des ersten Outputs, Mitte.
  - `tick(dt: float, world: World, locked: bool) -> None`: `needs.tick(dt, activity)` nur wenn `not locked and not paused`; Physik/Verhalten nur wenn nicht `paused`.
  - `feed() -> None`, `pet() -> None`, `go_sleep() -> None`, `call_to_floor() -> None`, `set_paused(p: bool) -> None`
  - `start_drag() -> None`, `drag_to(x: float, y: float) -> None`, `release(vx: float, vy: float) -> None`
  - `frame_key(t: float) -> tuple[str, str, int, bool]` = `(anim, mood_name, frame_index, flip)`; `anim` in den Sprite-Animationen aus Task 5; `mood_name` in `{"normal","sad","sick"}`; `flip = facing < 0`.
    Mapping Zustand -> Animation: `idle_sit->sit`, `sick_lie->lie`, `thrown->fall`, `hidden->sit`, sonst gleichnamig.
  - `visible -> bool` (False bei `hidden`/`paused`).
  - Konstanten: `GRAVITY = 2500`, `WALK_SPEED = 60`, Traurig halbe Geschwindigkeit, `SPRITE = 96`.

Verhaltensregeln:
- Aktivität für `needs.tick`: `walk/jump/fall/thrown/dragged` -> `"active"`, `sleep` -> `"sleep"`, sonst `"rest"`.
- Geerdete Zustände wählen nach Ablauf eines Timers neu: `idle_sit` 3-10 s, `walk` 2-8 s; Auswahl: Energie < 20 -> `sleep` (bis Energie >= 80); sonst 30 % Sprung (falls `reachable` nicht leer, Ziel zufällig), sonst 50/50 sitzen/laufen.
- `walk`: am Plattformende `neighbor` weiterlaufen, sonst umdrehen.
- Sprung: Ziel-Punkt `tx` zufällig in `[q.x1+20, q.x2-20]`; Scheitelhöhe `h = max(0, y - q.y) + 60`; `vy = -sqrt(2*GRAVITY*h)`; Flugzeit bis `q.y` aus Wurfgleichung, `vx = (tx - x) / t`.
- `jump/fall/thrown`: Integration mit Physik-`dt` <= 0.1 s, in Teilschritten so, dass `|vy*dt| <= 20` (kein Durchtunneln). Landen auf erster Plattform, die zwischen altem und neuem y gekreuzt wird (nur bei `vy > 0`, `x1 <= x <= x2`; bei `call_to_floor` nur Böden). Seitlich an `world.bounds()` abprallen (`vx = -vx * 0.5`), oben auf `bounds.y + SPRITE` kappen (`vy = 0`).
- Mitfahren: geerdet auf Fensterplattform -> pro Tick `world.window_rect(owner)` mit gespeichertem Rect vergleichen, Delta auf `x, y` addieren; neue Plattform per `platform_by_owner_at`. Keine Plattform mehr unter `x` -> `fall`.
- Kein Output an `x` mehr (Monitor weg) -> `spawn(world)`.
- Output der Katze in `world.forbidden_outputs` -> `hidden`; sonst aus `hidden` zurück nach `fall`.
- Stimmung SICK: geerdet auf Fensterplattform -> `call_to_floor()`; auf Boden -> `sick_lie`, keine Sprünge. SAD: Laufgeschwindigkeit halb.
- `feed()`: `needs.feed()`; geerdet -> `eat` 3 s. `pet()`: `needs.pet()`; geerdet -> `purr` 1.5 s. Während `sleep`: aufwecken.
- `release()`: `thrown` mit gegebener Geschwindigkeit.

- [ ] **Step 1: Tests** (`rng = random.Random(1)`, Welt via Task-3-Konstruktor; Hilfsfunktion `run(cat, world, seconds, locked=False)` tickt in 1/30-s-Schritten):
  - `test_spawn_on_floor`.
  - `test_needs_frozen_when_locked`: 1 h `locked=True` -> satiety unverändert.
  - `test_paused_freezes_everything`.
  - `test_falls_when_platform_disappears`: Katze auf Fenster, neue Welt ohne Fenster -> nach 2 s auf Boden, `state != "fall"`.
  - `test_rides_moving_window`: Fenster um (+100, +50) verschoben -> Katze ebenso.
  - `test_throw_lands_on_platform`, `test_throw_bounces_off_outer_edge` (vx=-5000 am linken Rand -> `x >= bounds.x`), `test_throw_clamped_at_top` (vy=-10000 -> `y >= bounds.y + 96` jederzeit).
  - `test_huge_dt_does_not_tunnel`: Fall über Fensterplattform, `tick(10.0)` -> landet auf Fenster, nicht auf Boden.
  - `test_respawn_when_output_removed`.
  - `test_hidden_on_fullscreen_output` und wieder sichtbar nach Wegfall.
  - `test_sick_cat_goes_to_floor_and_lies`.
  - `test_feed_triggers_eat`, `test_pet_wakes_and_purrs`.
  - `test_sleeps_when_tired`: energy 10 -> innerhalb 15 s `sleep`.
  - `test_frame_key_flip_and_mood`.
- [ ] **Step 2:** `pytest tests/test_cat.py -v` -> FAIL.
- [ ] **Step 3:** Implementieren.
- [ ] **Step 4:** `pytest -v` -> alle PASS.

### Task 5: Sprites (`sprites.py`)

**Files:** Create `taskbar_cat/sprites.py`, `tests/test_sprites.py`

**Interfaces:**
- Produces:
  - `ANIMS: dict[str, int]` (Name -> Framezahl, je 6 FPS abgespielt): `sit 2, walk 4, jump 1, fall 1, sleep 2, eat 2, purr 2, dragged 2, lie 2`.
  - `MOODS = ("normal", "sad", "sick")`
  - `frame_origin(anim: str, mood: str, frame: int) -> tuple[int, int]` - Pixelursprung im Atlas (unskaliert, Vielfaches von 32); `frame %= ANIMS[anim]`.
  - `ensure_atlas(cache_dir: Path) -> Path` - erzeugt `atlas.png` (QImage, ARGB32), wenn nicht vorhanden oder `ATLAS_VERSION` in Dateiname geändert; Layout: Zeile = `(anim, mood)`, Spalte = Frame.
  - `head_icon(mood: str) -> QImage` - 32x32 Katzenkopf für Tray.
- Zeichnung: Pixelmatrizen als Strings im Modul (z.B. `"..XX.."`), Palette: Fell orange `#E8913A`, dunkel `#8A4A1C`, Augen `#1A1A1A`, Nase `#F28CA0`, Weiß `#FFFFFF`. `sad`: Ohren-Pixel 2 Zeilen tiefer, Augen als Striche. `sick`: Fell nach `#9DBF6A`/`#5E7A3A` getönt. Zusätze: Zzz (sleep), Napf (eat), Herz (purr). Die Haltung für `jump/fall/dragged` darf von `walk` abgeleitet sein.
- QImage benötigt eine `QGuiApplication`; Tests nutzen `QT_QPA_PLATFORM=offscreen` (in `tests/conftest.py` setzen + Session-Fixture mit `QGuiApplication`).

- [ ] **Step 1: Tests:** `test_atlas_dimensions` (Breite = 32 * max Frames, Höhe = 32 * len(ANIMS) * len(MOODS)), `test_every_frame_has_pixels` (jeder Frame hat >= 50 nicht transparente Pixel), `test_frames_differ_within_walk`, `test_sick_differs_from_normal`, `test_cached_atlas_reused` (zweiter Aufruf ändert mtime nicht).
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implementieren.
- [ ] **Step 4:** PASS. Zusätzlich manuell: `python3 -c "from taskbar_cat.sprites import ensure_atlas; ..."` und `atlas.png` mit 4x-Vergrößerung ansehen (Read-Tool auf PNG) - Katze erkennbar.

### Task 6: KWin-Sensor + D-Bus (`kwin/taskbar-cat-sensor.js`, `bus.py`)

**Files:** Create `kwin/taskbar-cat-sensor.js`, `taskbar_cat/bus.py`, `tests/test_bus.py`

**Interfaces:**
- Consumes: `World.from_json` (Task 3).
- Produces (`bus.py`):
  - `class CatBus(QObject)`: Signale `worldUpdated(object)` (World), `lockChanged(bool)`; `register() -> bool` (False = Name belegt -> zweite Instanz); `load_sensor() -> None`; `unload_sensor() -> None`; `latest_world() -> World | None` (holt und leert den zuletzt empfangenen Stand; Parsing erst hier -> Zusammenfassen pro Tick); `sensor_ok -> bool`.
  - Watchdog per `QTimer` 10 s: `isScriptLoaded("taskbar-cat-sensor")` false oder noch kein Update -> `load_sensor()`, höchstens 1x/60 s.
  - Adaptor-Klasse mit `@pyqtClassInfo("D-Bus Interface", "de.bangl.TaskbarCat")` und `@pyqtSlot(str) def update(self, text)`; Export über `QDBusConnection.sessionBus().registerObject("/", obj, ExportAllSlots)`.
  - KWin: `org.kde.KWin`, Pfad `/Scripting`, Interface `org.kde.kwin.Scripting`: `unloadScript(name)`, `loadScript(abs_path, name)`, danach `start()`.
  - Sperre: `sessionBus().connect("org.freedesktop.ScreenSaver", "/ScreenSaver", "org.freedesktop.ScreenSaver", "ActiveChanged", slot)`; Initialwert per `GetActive`.
- Script (KWin-6-API, prüfen gegen https://develop.kde.org/docs/plasma/kwin/api/):
  - `send()`: baut JSON aus `workspace.screens` (`name`, `geometry`, `workspace.clientArea(KWin.MaximizeArea, output, workspace.currentDesktop)`) und `workspace.stackingOrder` (Index = `stack`), gefiltert auf `normalWindow && !minimized && (onAllDesktops || desktops.includes(currentDesktop))`; `id = internalId.toString()`, Geometrie aus `frameGeometry`; dann `callDBus("de.bangl.TaskbarCat", "/", "de.bangl.TaskbarCat", "update", json)`.
  - `send()` aufrufen bei: Script-Start, `windowAdded` (+ Fenster-Signale verbinden), `windowRemoved`, `windowActivated`, `currentDesktopChanged`, `screensChanged`, `stackingOrderChanged`, je Fenster `frameGeometryChanged`, `minimizedChanged`, `fullScreenChanged`, `maximizedChanged`. Bestehende Fenster beim Start verbinden.
- Unterstützung für manuelle Prüfung: `python3 -m taskbar_cat.bus --dump` registriert Service, lädt Script, gibt jede `World` als Plattformliste auf stdout aus.

- [ ] **Step 1: Test** `test_latest_world_coalesces`: Adaptor-`update` dreimal mit gültigem JSON aufrufen (ohne echten Bus, Methode direkt) -> `latest_world()` liefert den letzten Stand, danach `None`; `test_invalid_json_ignored` -> `None`, kein Absturz.
- [ ] **Step 2:** FAIL. **Step 3:** Implementieren. **Step 4:** PASS.
- [ ] **Step 5: Manuell:** `python3 -m taskbar_cat.bus --dump`; Fenster verschieben, minimieren, Desktop wechseln -> Ausgabe ändert sich passend; Panel-Position prüfen (Boden-y = 1080 bei Panel oben). Bei Script-Fehlern: `journalctl --user -f | grep -i kwin`. Beenden (Ctrl+C) entlädt das Script (`qdbus6 org.kde.KWin /Scripting isScriptLoaded taskbar-cat-sensor` -> false).

### Task 7: Overlay + Interaktion (`ui/overlay.qml`, `ui/overlay.py`, `interaction.py`)

**Files:** Create `taskbar_cat/interaction.py`, `tests/test_interaction.py`, `taskbar_cat/ui/__init__.py`, `taskbar_cat/ui/overlay.qml`, `taskbar_cat/ui/overlay.py`

**Interfaces:**
- Consumes: `Cat.frame_key/visible/x/y`, `sprites.frame_origin/ensure_atlas`, `World.platforms`.
- Produces:
  - `interaction.RubDetector`: `feed_motion(x: float, t: float) -> bool` (True = eine Streichelbewegung erkannt: >= 3 Richtungswechsel der x-Bewegung, je >= 4 px, innerhalb 1 s; danach Reset); `reset()`.
  - `interaction.DragTracker`: `press(x, y, t)`, `move(x, y, t) -> bool` (True, sobald > 6 px vom Press-Punkt = Drag begonnen), `velocity() -> tuple[float, float]` (aus Samples der letzten 100 ms), `is_dragging`.
  - `overlay.OverlayManager(QObject)`: `__init__(engine: QQmlApplicationEngine, atlas: Path, debug: bool)`; erzeugt je `QGuiApplication.screens()` ein Overlay (neu bei `screenAdded/screenRemoved`); `render(cat: Cat, world: World, t: float) -> None`; Signale `petted()`, `rightClicked(QPoint)` (global), `dragStarted()`, `dragMoved(float, float)` (global), `released(float, float)` (vx, vy).
  - QML-Fenster: `LayerShell.Window.layer: LayerShell.Window.LayerOverlay`, `anchors: AnchorTop|AnchorBottom|AnchorLeft|AnchorRight`, `exclusionZone: -1`, `keyboardInteractivity: KeyboardInteractivityNone`, `scope: "taskbar-cat"`, `color: "transparent"`, `screen` = jeweiliger Screen. Inhalt: `Image` mit Atlas, `sourceClipRect` = Frame, `smooth: false`, Breite/Höhe 96, `mirror`; `MouseArea` über der Katze (Links/Rechts, `hoverEnabled`). Debug: Plattformen als 2-px-Rechtecke.
  - Input-Region: nach jedem `render` `window.setMask(QRegion(katzenrechteck lokal, +8 px Rand))`; auf Overlays ohne Katze leere 1x1-Region außerhalb des Bildschirms. Nur bei Positionsänderung neu setzen.
  - Maus: Press links -> `DragTracker.press`; Move -> wenn Drag, `dragMoved` (lokale Koordinaten + Screen-Offset = global; Wayland-Implicit-Grab liefert Events auch außerhalb des Overlays); sonst `RubDetector.feed_motion` (bei Hover) -> `petted`; Release ohne Drag = Klick -> `petted`; Release nach Drag -> `released(*velocity())`. Rechts -> `rightClicked`.

- [ ] **Step 1: Tests** (`interaction.py`, rein): `test_rub_needs_three_reversals`, `test_rub_ignores_jitter_below_4px`, `test_rub_window_1s`, `test_drag_threshold_6px`, `test_velocity_last_100ms`.
- [ ] **Step 2:** FAIL. **Step 3:** `interaction.py` implementieren. **Step 4:** PASS.
- [ ] **Step 5:** `overlay.qml` + `overlay.py` implementieren; Testlauf manuell über Task 8.

### Task 8: Tray, Verdrahtung, Autostart (`ui/tray.py`, `__main__.py`)

**Files:** Create `taskbar_cat/ui/tray.py`, `taskbar_cat/__main__.py`, `autostart/taskbar-cat.desktop`, `README.md` (kurz: Start, Debug, Autostart-Installation)

**Interfaces:**
- Consumes: alles Vorherige.
- Produces:
  - `tray.CatTray(QObject)`: `__init__(cat: Cat)`; `refresh(sensor_ok: bool)` (Icon `head_icon(mood)` skaliert, Tooltip: `"Sättigung 72 %\nZuneigung 55 %\nEnergie 80 %\nStimmung: traurig"` + bei `not sensor_ok` Zeile `"Warnung: Fenster-Sensor fehlt"`); `menu() -> QMenu`; Signale `feedRequested, petRequested, sleepRequested, floorRequested, pauseToggled(bool), quitRequested`. Linksklick (`activated` mit `Trigger`) -> `feedRequested`.
  - Menüeinträge: "Füttern", "Streicheln", "Schlafen schicken", "Zum Boden rufen", "Status ..." (QMessageBox mit Tooltip-Text), "Pausieren" (checkbar), "Beenden". Dasselbe Menü öffnet sich bei Rechtsklick auf die Katze (`menu().popup(globalPos)`).
- `__main__.py`: `QApplication` (wegen QMenu/QSystemTrayIcon), `setQuitOnLastWindowClosed(False)`; `CatBus.register()` false -> Meldung auf stderr, Exit 0; `storage.load`; `Cat(needs, random.Random())`, `spawn`; `bus.load_sensor()`; Welt-Fallback `World.from_screens(...)` aus `QScreen.geometry/availableGeometry`, bis erstes Update kommt; `QTimer` 33 ms: `world = bus.latest_world() or world`, `cat.tick(dt, world, locked)`, `overlays.render(...)`, Tray alle 1 s; Speichern alle 60 s; `aboutToQuit` -> `storage.save`, `bus.unload_sensor()`; SIGINT/SIGTERM -> `app.quit()`. Argument `--debug`.
- `.desktop`: `Exec=sh -c 'cd ~/Projects/taskbar-cat && exec python3 -m taskbar_cat'`, `X-KDE-autostart-after=panel`.

- [ ] **Step 1:** Implementieren.
- [ ] **Step 2:** `pytest -v` -> alle PASS.
- [ ] **Step 3: Manuell (E2E) mit `python3 -m taskbar_cat --debug`:**
  - Katze erscheint unten auf dem ersten Monitor, Klicks neben der Katze erreichen darunterliegende Fenster.
  - Plattform-Linien liegen auf Fensteroberkanten; Fenster verschieben -> Linien folgen, Katze fährt mit.
  - Katze springt auf Fenster, läuft über Monitorgrenzen.
  - Klick/Reiben -> Herz + Zuneigung im Tooltip steigt; Rechtsklick -> Menü; Drag über Monitorgrenze + Wurf.
  - Video im Vollbild -> Katze weg, danach wieder da.
  - Bildschirm sperren 1 min -> Werte unverändert.
  - Zweiter Start -> beendet sich sofort.
  - Beenden -> `state.json` geschrieben, Script entladen.
- [ ] **Step 4:** Autostart nur nach Rückfrage beim User nach `~/.config/autostart/` kopieren.

---

## Spec-Abdeckung

| Spec-Abschnitt | Task |
|---|---|
| KWin-Sensor | 6 |
| Weltmodell, Boden je Panel-Position, Verdeckung, Vollbild | 3 |
| Bedürfnisse, Stimmung | 1 |
| Verhalten, Physik, Mitfahren, Monitorwechsel | 4 |
| Overlay, Input-Region, Interaktion | 7 |
| Sprites | 5 |
| Tray, Menü | 8 |
| Lebenszyklus, Single-Instance, Sperre, Watchdog | 6, 8 |
| Persistenz | 2 |
| `--debug` | 7, 8 |

Abweichung zur Spec-Dateiliste: Bedürfnisse liegen in `needs.py`, Maus-Gesten in `interaction.py` (beides rein und testbar), `cat.py` enthält nur Verhalten/Physik.
