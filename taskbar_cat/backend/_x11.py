"""Input-Region eines X11-Fensters über die XShape-Erweiterung setzen.

Qt kennt dafür nur QWindow.setMask(), und das beschneidet auf X11 auch das Bild:
Möbel würden auf ihren Mauskasten gestutzt und beim Ziehen unsichtbar. XShape
trennt beides - hier wird deshalb nur ShapeInput gesetzt, das Fenster bleibt
vollständig sichtbar.
"""
import ctypes
import ctypes.util
import sys

SHAPE_INPUT = 2    # ShapeKind: nur Mausereignisse, nicht das Bild
SHAPE_SET = 0      # ShapeOp
UNSORTED = 0       # Katze und Möbel kommen ungeordnet und dürfen sich überlappen


class XRectangle(ctypes.Structure):
    _fields_ = [("x", ctypes.c_short), ("y", ctypes.c_short),
                ("width", ctypes.c_ushort), ("height", ctypes.c_ushort)]


class _Shape:
    """Lädt libX11/libXext einmalig; ohne sie bleibt alles wirkungslos."""

    def __init__(self):
        self.display = None
        self._combine = None
        try:
            x11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
            xext = ctypes.CDLL(ctypes.util.find_library("Xext") or "libXext.so.6")
        except OSError as e:
            print(f"taskbar-cat: XShape nicht verfügbar: {e}", file=sys.stderr)
            return
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XFlush.argtypes = [ctypes.c_void_p]
        xext.XShapeCombineRectangles.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(XRectangle), ctypes.c_int, ctypes.c_int, ctypes.c_int]
        display = x11.XOpenDisplay(None)
        if not display:
            print("taskbar-cat: keine X11-Verbindung für die Input-Region", file=sys.stderr)
            return
        self.display = display
        self._x11 = x11
        self._combine = xext.XShapeCombineRectangles

    def set_input_region(self, window_id: int, rects) -> bool:
        """rects: Folge von (x, y, w, h) in Fensterkoordinaten; leer = alles durchlässig."""
        if self._combine is None or not window_id:
            return False
        items = [XRectangle(int(x), int(y), max(0, int(w)), max(0, int(h)))
                 for x, y, w, h in rects]
        array = (XRectangle * len(items))(*items) if items else None
        self._combine(self.display, window_id, SHAPE_INPUT, 0, 0,
                      array, len(items), SHAPE_SET, UNSORTED)
        self._x11.XFlush(self.display)
        return True


_shape: _Shape | None = None


def set_input_region(window_id: int, rects) -> bool:
    global _shape
    if _shape is None:
        _shape = _Shape()
    return _shape.set_input_region(window_id, rects)
