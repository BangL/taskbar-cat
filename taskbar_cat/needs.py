"""Bedürfnisse und Stimmung der Katze (rein, ohne Qt)."""
import enum
from dataclasses import asdict, dataclass, fields

SATIETY_DECAY = 100 / (8 * 3600)
AFFECTION_DECAY = 100 / (4 * 3600)
ENERGY_RATE = {"active": -1 / 60, "rest": -0.2 / 60, "sleep": 2 / 60}
FEED_AMOUNT = 40
PET_AMOUNT = 2
MAX_DT = 5.0
SICK_AFTER_S = 7200


class Mood(enum.IntEnum):
    NORMAL = 0
    SAD = 1
    SICK = 2


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

    def tick(self, dt: float, activity: str) -> None:
        dt = max(0.0, min(dt, MAX_DT))
        self.session_s += dt
        self.satiety = _clamp(self.satiety - SATIETY_DECAY * dt)
        self.affection = _clamp(self.affection - AFFECTION_DECAY * dt)
        self.energy = _clamp(self.energy + ENERGY_RATE[activity] * dt)
        self.low_satiety_s = self.low_satiety_s + dt if self.satiety < 10 else 0
        self.low_affection_s = self.low_affection_s + dt if self.affection < 10 else 0
        self.mood = compute_mood(self.mood, self.satiety, self.affection,
                                 self.low_satiety_s, self.low_affection_s)

    def feed(self) -> bool:
        overfed = self.satiety > 60
        self.satiety = _clamp(self.satiety + FEED_AMOUNT)
        return overfed

    def pet(self) -> None:
        self.affection = _clamp(self.affection + PET_AMOUNT)

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
