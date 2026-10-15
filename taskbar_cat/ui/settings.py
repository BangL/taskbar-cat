"""Einstellungsdialog, aufgebaut aus config.SPECS (Grenzen stehen nur dort)."""
from PyQt6.QtWidgets import (QCheckBox, QColorDialog, QDialog, QDialogButtonBox, QDoubleSpinBox,
                             QFormLayout, QGroupBox, QHBoxLayout, QPushButton, QSpinBox,
                             QVBoxLayout, QWidget)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap

from ..config import FUR_PRESETS, SPECS, Config
from ..guard import guarded

GROUPS = (
    ("Darstellung", ("sprite_scale", "fur_color", "tabby", "debug_lines")),
    ("Verhalten", ("play_enabled", "shake_enabled", "walk_speed", "climb_speed", "jump_max_side",
                   "shake_limit", "p_jump", "p_climb", "p_hang", "p_groom", "p_yarn", "p_tree",
                   "p_bigtree")),
    ("Bedürfnisse", ("satiety_hours", "affection_hours", "feed_amount", "pet_amount")),
)


def _decimals(step: float) -> int:
    return 2 if step < 0.1 else 1 if step < 1 else 0


def screen_choices(app=None) -> list[tuple[str, str]]:
    """(KWin-Name, Beschriftung) je angeschlossenem Monitor."""
    from PyQt6.QtGui import QGuiApplication

    app = app or QGuiApplication.instance()
    out = []
    for s in app.screens() if app is not None else []:
        g = s.geometry()
        label = f"{s.name()} - {g.width()}x{g.height()} bei ({g.x()}, {g.y()})"
        model = (s.model() or "").strip().removeprefix(s.name()).strip(" -")
        if model:
            label += f", {model}"
        out.append((s.name(), label))
    return out


SWATCH = 16


def _swatch(value: str) -> QIcon:
    """Farbfleck mit dünnem Rand, damit auch Weiß auf dem Knopf zu sehen ist."""
    px = QPixmap(SWATCH, SWATCH)
    px.fill(QColor(value))
    painter = QPainter(px)
    painter.setPen(QColor(0, 0, 0, 120))
    painter.drawRect(0, 0, SWATCH - 1, SWATCH - 1)
    painter.end()
    return QIcon(px)


class ColorButton(QPushButton):
    """Knopf mit Farbfleck, öffnet den Farbwähler."""
    picked = pyqtSignal(str)

    def __init__(self, value: str, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._value = value
        self._title = title
        self._dialog: QColorDialog | None = None
        self.setIconSize(QSize(SWATCH, SWATCH))
        self.clicked.connect(guarded(self._choose))
        self._refresh()

    def value(self) -> str:
        return self._value

    def setValue(self, value: str) -> None:
        self._value = value
        self._refresh()

    def _refresh(self) -> None:
        self.setText(self._value.upper())
        self.setIcon(_swatch(self._value))

    def _choose(self, checked: bool = False) -> None:   # clicked liefert checked mit
        """Nicht modal: ein offener Farbwähler darf die Katze nicht blockieren."""
        dlg = self._dialog
        if dlg is None:
            for i, preset in enumerate(FUR_PRESETS):
                QColorDialog.setStandardColor(i, QColor(preset))
            dlg = self._dialog = QColorDialog(QColor(self._value), self)
            dlg.setWindowTitle(self._title)
            dlg.setWindowModality(Qt.WindowModality.NonModal)
            dlg.colorSelected.connect(guarded(self._chosen))
        dlg.setCurrentColor(QColor(self._value))
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _chosen(self, c: QColor) -> None:
        if c.isValid():
            self.setValue(c.name())
            self.picked.emit(self._value)


def _set_checked(box: QCheckBox, on: bool) -> None:
    box.blockSignals(True)
    box.setChecked(on)
    box.blockSignals(False)


class SettingsDialog(QDialog):
    changed = pyqtSignal(str)

    def __init__(self, cfg: Config, parent: QWidget | None = None,
                 screens: list[tuple[str, str]] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Taskbar-Cat - Einstellungen")
        self.setWindowModality(Qt.WindowModality.NonModal)   # darf die Katze nicht blockieren
        self._cfg = cfg
        self._widgets: dict[str, QWidget] = {}
        self._screens: dict[str, QCheckBox] = {}
        layout = QVBoxLayout(self)
        columns = QHBoxLayout()
        layout.addLayout(columns)
        self._columns = [QVBoxLayout(), QVBoxLayout()]
        self._heights = [0, 0]
        for col in self._columns:
            columns.addLayout(col)
        for title, names in GROUPS:
            box = QGroupBox(title)
            form = QFormLayout(box)
            for name in names:
                w = self._build(name)
                self._widgets[name] = w
                spec = SPECS[name]
                if spec.hint:
                    w.setToolTip(spec.hint)
                form.addRow("" if spec.kind == "bool" else f"{spec.label}:", w)
            self._place(box, len(names))
        self._build_screens(screen_choices() if screens is None else screens)
        for col in self._columns:
            col.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close
                                   | QDialogButtonBox.StandardButton.RestoreDefaults)
        buttons.rejected.connect(self.hide)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(
            guarded(self.restore_defaults))
        layout.addWidget(buttons)

    def _place(self, box: QGroupBox, rows: int) -> None:
        """Gruppe in die kürzere Spalte: der Dialog wird lieber breit als hoch."""
        i = self._heights.index(min(self._heights))
        self._columns[i].addWidget(box)
        self._heights[i] += rows + 1        # der Rahmen zählt wie eine Zeile

    def _build_screens(self, screens: list[tuple[str, str]]) -> None:
        """Ein Haken je Monitor. Gesperrte, aber abgezogene Monitore bleiben sichtbar,
        sonst könnte man sie nie wieder freigeben."""
        known = {n for n, _ in screens}
        screens = list(screens) + [(n, f"{n} - nicht verbunden")
                                   for n in self._cfg.blocked_outputs if n not in known]
        if len(screens) < 2:
            return
        box = QGroupBox("Monitore")
        form = QFormLayout(box)
        for name, label in screens:
            w = QCheckBox(label)
            w.setChecked(self._cfg.allows(name))
            w.setToolTip("Haken: die Katze darf auf diesem Monitor laufen")
            w.toggled.connect(guarded(lambda v, n=name: self._toggle_screen(n, v)))
            self._screens[name] = w
            form.addRow("", w)
        self._place(box, len(screens))

    def _toggle_screen(self, name: str, allowed: bool) -> None:
        if not allowed and not any(b.isChecked() for b in self._screens.values()):
            _set_checked(self._screens[name], True)   # irgendwo muss sie ja leben
            return
        self._apply("blocked_outputs", [n for n, b in self._screens.items() if not b.isChecked()])

    def _build(self, name: str) -> QWidget:
        spec = SPECS[name]
        value = getattr(self._cfg, name)
        if spec.kind == "bool":
            w = QCheckBox(spec.label)
            w.setChecked(bool(value))
            w.toggled.connect(guarded(lambda v, n=name: self._apply(n, v)))
            return w
        if spec.kind == "color":
            w = ColorButton(str(value), spec.label)
            w.picked.connect(guarded(lambda v, n=name: self._apply(n, v)))
            return w
        w = QSpinBox() if spec.kind == "int" else QDoubleSpinBox()
        if spec.kind == "float":
            w.setDecimals(_decimals(spec.step))
        w.setRange(spec.lo, spec.hi)
        w.setSingleStep(spec.step)
        w.setSuffix(f" {spec.unit}" if spec.unit else "")
        w.setValue(value)
        w.valueChanged.connect(guarded(lambda v, n=name: self._apply(n, v)))
        return w

    def show_value(self, name: str) -> None:
        """Von außen geänderten Wert anzeigen, ohne ihn erneut zu melden."""
        w = self._widgets[name]
        value = getattr(self._cfg, name)
        w.blockSignals(True)
        w.setChecked(bool(value)) if isinstance(w, QCheckBox) else w.setValue(value)
        w.blockSignals(False)

    def _apply(self, name: str, value) -> None:
        self._cfg.set(name, value)
        self.changed.emit(name)

    def restore_defaults(self, checked: bool = False) -> None:   # clicked liefert checked mit
        defaults = Config()
        for name in self._widgets:
            self._apply(name, getattr(defaults, name))
            self.show_value(name)
        for b in self._screens.values():
            _set_checked(b, True)
        self._apply("blocked_outputs", defaults.blocked_outputs)
