"""Status der Katze als Text: Tray-Tooltip, Status-Dialog und Konsolenausgabe."""
import json

from .cat import Cat
from .needs import MOOD_TEXT, Mood, Needs

FIELDS = ("satiety", "affection", "energy")
LABELS = {"satiety": "Sättigung", "affection": "Zuneigung", "energy": "Energie"}


def snapshot(cat: Cat, sensor_ok: bool = True) -> dict:
    n = cat.needs
    return {"satiety": n.satiety, "affection": n.affection, "energy": n.energy,
            "mood": MOOD_TEXT[n.mood], "state": cat.state, "paused": cat.paused,
            "running": True, "sensor_ok": sensor_ok}


def from_needs(needs: Needs) -> dict:
    """Status aus einem gespeicherten Zustand (Katze läuft nicht)."""
    return {"satiety": needs.satiety, "affection": needs.affection, "energy": needs.energy,
            "mood": MOOD_TEXT[needs.mood], "state": "-", "paused": False,
            "running": False, "sensor_ok": True}


def _percent(d: dict, key: str) -> str:
    return f"{LABELS[key]} {d.get(key, 0):.0f} %"


def lines(d: dict) -> list[str]:
    out = [_percent(d, f) for f in FIELDS]
    out.append(f"Stimmung: {d.get('mood', MOOD_TEXT[Mood.NORMAL])}")
    if d.get("paused"):
        out.append("Pausiert")
    if not d.get("running", True):
        out.append("Nicht gestartet (gespeicherter Zustand)")
    if not d.get("sensor_ok", True):
        out.append("Warnung: Fenster-Sensor fehlt")
    return out


def one_line(d: dict) -> str:
    """Kurzform für die Konsole, z.B. Einbau in fastfetch."""
    parts = [f"{d.get(f, 0):.0f}%" for f in FIELDS]
    text = f"Sättigung {parts[0]} | Zuneigung {parts[1]} | Energie {parts[2]} | {d.get('mood', '?')}"
    if d.get("paused"):
        text += " (pausiert)"
    if not d.get("running", True):
        text += " (nicht gestartet)"
    return text


def as_json(d: dict) -> str:
    return json.dumps(d, ensure_ascii=False)
