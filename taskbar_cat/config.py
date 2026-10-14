"""Einstellbare Werte (rein, ohne Qt). SPECS beschreibt Grenzen und Beschriftung;
Validierung und Dialog bauen beide darauf auf."""
import re
from dataclasses import asdict, dataclass, field, fields

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
# Katzenfarben: Standardfarben im Farbwähler und Auswahl für graues Fell nach dem UFO
FUR_PRESETS = ("#e8913a", "#5c3a21", "#2e2e2e", "#d8d8d8", "#8899aa", "#f2ebdd", "#c44b3a", "#6b8e6b")


@dataclass(frozen=True)
class Spec:
    label: str
    kind: str          # "bool" | "int" | "float" | "color"
    lo: float = 0
    hi: float = 0
    step: float = 1
    unit: str = ""
    hint: str = ""


SPECS: dict[str, Spec] = {
    "sprite_scale": Spec("Größe", "int", 1, 6, 1, "x", "Kantenlänge = 32 Pixel x Faktor"),
    "fur_color": Spec("Fellfarbe", "color", hint="Streifen, Kontur und die kranke Katze "
                                                 "werden daraus abgeleitet"),
    "tabby": Spec("Tigerung", "int", 0, 200, 10, "%",
                  "0 = einfarbig, 100 = normal, darüber zusätzliche Streifen"),
    "play_enabled": Spec("Mauszeiger fangen", "bool"),
    "shake_enabled": Spec("Schütteln macht übel", "bool",
                          hint="Wird sie beim Ziehen zu wild geschüttelt, kotzt sie"),
    "debug_lines": Spec("Plattformen einblenden", "bool", hint="Kanten, Wände und Decken als Linien"),
    "walk_speed": Spec("Laufgeschwindigkeit", "float", 5, 400, 5, "px/s"),
    "climb_speed": Spec("Klettergeschwindigkeit", "float", 5, 400, 5, "px/s"),
    "jump_max_side": Spec("Sprungweite", "float", 50, 600, 10, "px",
                          "Weiter entfernte Kanten springt sie nicht an"),
    "shake_limit": Spec("Schütteln verträgt", "int", 3, 20, 1, "Wechsel",
                        "So viele Richtungswechsel am Stück, dann wird ihr schlecht"),
    "satiety_hours": Spec("Sättigung leer nach", "float", 0.5, 72, 0.5, "h"),
    "affection_hours": Spec("Zuneigung leer nach", "float", 0.5, 72, 0.5, "h"),
    "feed_amount": Spec("Füttern gibt", "float", 1, 100, 1, "%"),
    "pet_amount": Spec("Streicheln gibt", "float", 0.5, 50, 0.5, "%"),
    "p_jump": Spec("Sprung", "float", 0, 1, 0.05, "", "Wahrscheinlichkeit pro Entscheidung"),
    "p_climb": Spec("Klettern", "float", 0, 1, 0.05),
    "p_hang": Spec("An Unterkante hängen", "float", 0, 1, 0.05),
    "p_groom": Spec("Putzen", "float", 0, 1, 0.05, "", "Anteil der Ruhepausen, in denen sie sich putzt"),
    "p_yarn": Spec("Mit Wolle spielen", "float", 0, 1, 0.05, "",
                   "Wahrscheinlichkeit pro Entscheidung, wenn ein Wollknäuel aufgestellt ist"),
    "p_tree": Spec("Kratzbaum", "float", 0, 1, 0.05, "",
                   "Wahrscheinlichkeit pro Entscheidung, zum Kratzbaum zu gehen (kratzen oder hinauf)"),
}


@dataclass
class Config:
    sprite_scale: int = 3
    fur_color: str = "#e8913a"
    tabby: int = 100
    play_enabled: bool = True
    shake_enabled: bool = True
    debug_lines: bool = False
    walk_speed: float = 60
    climb_speed: float = 80
    jump_max_side: float = 320
    shake_limit: int = 8
    satiety_hours: float = 8
    affection_hours: float = 4
    feed_amount: float = 40
    pet_amount: float = 2
    p_jump: float = 0.15
    p_climb: float = 0.15
    p_hang: float = 0.10
    p_groom: float = 0.35
    p_yarn: float = 0.2
    p_tree: float = 0.15
    # Monitore, auf denen die Katze nicht laufen soll (KWin-Namen wie "DP-1").
    # Nicht in SPECS: die Auswahl entsteht erst zur Laufzeit aus den vorhandenen Monitoren.
    blocked_outputs: list[str] = field(default_factory=list)

    @property
    def sprite_px(self) -> int:
        return 32 * self.sprite_scale

    @property
    def satiety_decay(self) -> float:
        return 100 / (self.satiety_hours * 3600)

    @property
    def affection_decay(self) -> float:
        return 100 / (self.affection_hours * 3600)

    def allows(self, output: str) -> bool:
        return output not in self.blocked_outputs

    def set(self, name: str, value) -> None:
        """Einzelwert setzen, auf die Grenzen aus SPECS begrenzt."""
        if name == "blocked_outputs":
            if isinstance(value, str) or not hasattr(value, "__iter__"):
                raise TypeError("blocked_outputs braucht eine Liste von Monitornamen")
            self.blocked_outputs = sorted({str(v) for v in value})
            return
        spec = SPECS[name]
        if spec.kind == "color":
            text = str(value).strip()
            if not HEX_COLOR.match(text):
                raise ValueError(f"keine Farbe: {value!r}")
            setattr(self, name, text.lower())
            return
        if spec.kind == "bool":
            setattr(self, name, bool(value))
            return
        v = max(spec.lo, min(spec.hi, float(value)))
        setattr(self, name, int(round(v)) if spec.kind == "int" else v)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Config":
        c = cls()
        for f in fields(cls):
            if f.name in d:
                try:
                    c.set(f.name, d[f.name])
                except (TypeError, ValueError):
                    pass
        return c
