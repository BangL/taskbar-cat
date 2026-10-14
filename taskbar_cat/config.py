"""Einstellbare Werte (rein, ohne Qt). SPECS beschreibt Grenzen und Beschriftung;
Validierung und Dialog bauen beide darauf auf."""
from dataclasses import asdict, dataclass, fields


@dataclass(frozen=True)
class Spec:
    label: str
    kind: str          # "bool" | "int" | "float"
    lo: float = 0
    hi: float = 0
    step: float = 1
    unit: str = ""
    hint: str = ""


SPECS: dict[str, Spec] = {
    "sprite_scale": Spec("Größe", "int", 1, 6, 1, "x", "Kantenlänge = 32 Pixel x Faktor"),
    "play_enabled": Spec("Mauszeiger fangen", "bool"),
    "debug_lines": Spec("Plattformen einblenden", "bool", hint="Kanten, Wände und Decken als Linien"),
    "walk_speed": Spec("Laufgeschwindigkeit", "float", 5, 400, 5, "px/s"),
    "climb_speed": Spec("Klettergeschwindigkeit", "float", 5, 400, 5, "px/s"),
    "satiety_hours": Spec("Sättigung leer nach", "float", 0.5, 72, 0.5, "h"),
    "affection_hours": Spec("Zuneigung leer nach", "float", 0.5, 72, 0.5, "h"),
    "feed_amount": Spec("Füttern gibt", "float", 1, 100, 1, "%"),
    "pet_amount": Spec("Streicheln gibt", "float", 0.5, 50, 0.5, "%"),
    "p_jump": Spec("Sprung", "float", 0, 1, 0.05, "", "Wahrscheinlichkeit pro Entscheidung"),
    "p_climb": Spec("Klettern", "float", 0, 1, 0.05),
    "p_hang": Spec("An Unterkante hängen", "float", 0, 1, 0.05),
}


@dataclass
class Config:
    sprite_scale: int = 3
    play_enabled: bool = True
    debug_lines: bool = False
    walk_speed: float = 60
    climb_speed: float = 80
    satiety_hours: float = 8
    affection_hours: float = 4
    feed_amount: float = 40
    pet_amount: float = 2
    p_jump: float = 0.15
    p_climb: float = 0.15
    p_hang: float = 0.10

    @property
    def sprite_px(self) -> int:
        return 32 * self.sprite_scale

    @property
    def satiety_decay(self) -> float:
        return 100 / (self.satiety_hours * 3600)

    @property
    def affection_decay(self) -> float:
        return 100 / (self.affection_hours * 3600)

    def set(self, name: str, value) -> None:
        """Einzelwert setzen, auf die Grenzen aus SPECS begrenzt."""
        spec = SPECS[name]
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
