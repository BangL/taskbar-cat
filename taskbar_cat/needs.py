"""Bedürfnisse und Stimmung der Katze (rein, ohne Qt)."""
import enum
from dataclasses import asdict, dataclass, fields

from .config import Config

_DEFAULTS = Config()
SATIETY_DECAY = _DEFAULTS.satiety_decay
AFFECTION_DECAY = _DEFAULTS.affection_decay
ENERGY_RATE = {"active": -1 / 60, "rest": -0.2 / 60, "sleep": 2 / 60}
FEED_AMOUNT = _DEFAULTS.feed_amount
PET_AMOUNT = _DEFAULTS.pet_amount
MAX_DT = 5.0
SICK_AFTER_S = 7200


class Mood(enum.IntEnum):
    NORMAL = 0
    SAD = 1
    SICK = 2


MOOD_TEXT = {Mood.NORMAL: "zufrieden", Mood.SAD: "traurig", Mood.SICK: "krank"}


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, float(v)))


def compute_mood(prev: Mood, s: float, a: float, low_s: float, low_a: float) -> Mood:
    if (s < 10 and a < 10) or low_s > SICK_AFTER_S or low_a > SICK_AFTER_S:
        raw = Mood.SICK
    elif s < 20 or a < 20:
        raw = Mood.SAD
    else:
        raw = Mood.NORMAL
    if prev != Mood.NORMAL and not (s >= 40 and a >= 40):
        return max(prev, raw)
    return raw


@dataclass
class Needs:
    satiety: float = 80
    affection: float = 80
    energy: float = 80
    low_satiety_s: float = 0
    low_affection_s: float = 0
    session_s: float = 0
    mood: Mood = Mood.NORMAL

    def tick(self, dt: float, activity: str, cfg: Config | None = None) -> None:
        cfg = cfg or _DEFAULTS
        dt = max(0.0, min(dt, MAX_DT))
        self.session_s += dt
        self.satiety = _clamp(self.satiety - cfg.satiety_decay * dt)
        self.affection = _clamp(self.affection - cfg.affection_decay * dt)
        self.energy = _clamp(self.energy + ENERGY_RATE[activity] * dt)
        self.low_satiety_s = self.low_satiety_s + dt if self.satiety < 10 else 0
        self.low_affection_s = self.low_affection_s + dt if self.affection < 10 else 0
        self.mood = compute_mood(self.mood, self.satiety, self.affection,
                                 self.low_satiety_s, self.low_affection_s)

    def feed(self, cfg: Config | None = None) -> bool:
        cfg = cfg or _DEFAULTS
        overfed = self.satiety > 100 - cfg.feed_amount
        self.satiety = _clamp(self.satiety + cfg.feed_amount)
        return overfed

    def pet(self, cfg: Config | None = None) -> None:
        self.affection = _clamp(self.affection + (cfg or _DEFAULTS).pet_amount)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["mood"] = int(self.mood)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Needs":
        n = cls()
        for f in fields(cls):
            if f.name not in d:
                continue
            try:
                if f.name == "mood":
                    n.mood = Mood(int(d["mood"]))
                elif f.name in ("satiety", "affection", "energy"):
                    setattr(n, f.name, _clamp(d[f.name]))
                else:
                    setattr(n, f.name, max(0.0, float(d[f.name])))
            except (TypeError, ValueError):
                pass
        return n
