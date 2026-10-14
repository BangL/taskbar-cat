"""Timer-Callbacks absichern: Fehler loggen statt die App zu beenden."""
import sys
import time
import traceback
from typing import Callable

REPEAT_LOG_S = 60.0


def _stderr(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


def guarded(fn: Callable, log: Callable[[str], None] = _stderr,
            clock: Callable[[], float] = time.monotonic) -> Callable:
    """Fängt Exceptions von fn ab. Gleiche Fehler werden höchstens einmal pro Minute geloggt."""
    last: dict[str, float] = {}

    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            text = traceback.format_exc()
            now = clock()
            if text not in last or now - last[text] >= REPEAT_LOG_S:
                last[text] = now
                log(f"taskbar-cat: Fehler abgefangen, läuft weiter:\n{text}")
            return None

    return wrapper
