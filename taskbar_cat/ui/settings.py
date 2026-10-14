"""Einstellungsdialog, aufgebaut aus config.SPECS (Grenzen stehen nur dort)."""
from PyQt6.QtWidgets import (QCheckBox, QColorDialog, QDialog, QDialogButtonBox, QDoubleSpinBox,
                             QFormLayout, QGroupBox, QPushButton, QSpinBox, QVBoxLayout, QWidget)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor

from ..config import SPECS, Config
from ..guard import guarded

GROUPS = (
    ("Darstellung", ("sprite_scale", "fur_color", "debug_lines")),
    ("Verhalten", ("play_enabled", "walk_speed", "climb_speed", "p_jump", "p_climb", "p_hang")),
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


FUR_PRESETS = ("#e8913a", "#5c3a21", "#2e2e2e", "#d8d8d8", "#8899aa", "#f2ebdd", "#c44b3a", "#6b8e6b")


class ColorButton(QPushButton):
    """Knopf in der gewählten Farbe, öffnet den Farbwähler."""
    picked = pyqtSignal(str)

    def __init__(self, value: str, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._value = value
        self._title = title
        self.clicked.connect(guarded(self._choose))
        self._refresh()

    def value(self) -> str:
        return self._value

    def setValue(self, value: str) -> None:
        self._value = value
        self._refresh()

    def _refresh(self) -> None:
        c = QColor(self._value)
        self.setText(self._value.upper())
        self.setStyleSheet(f"background-color: {c.name()}; "
                           f"color: {'#000000' if c.lightness() > 128 else '#ffffff'};")

    def _choose(self, checked: bool = False) -> None:   # clicked liefert checked mit
        for i, preset in enumerate(FUR_PRESETS):
            QColorDialog.setStandardColor(i, QColor(preset))
        c = QColorDialog.getColor(QColor(self._value), self, self._title)
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
        self._cfg = cfg
        self._widgets: dict[str, QWidget] = {}
        self._screens: dict[str, QCheckBox] = {}
        layout = QVBoxLayout(self)
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
            layout.addWidget(box)
        self._build_screens(layout, screen_choices() if screens is None else screens)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close
                                   | QDialogButtonBox.StandardButton.RestoreDefaults)
        buttons.rejected.connect(self.hide)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(
            guarded(self.restore_defaults))
        layout.addWidget(buttons)

    def _build_screens(self, layout: QVBoxLayout, screens: list[tuple[str, str]]) -> None:
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
        layout.addWidget(box)

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

    def _apply(self, name: str, value) -> None:
        self._cfg.set(name, value)
        self.changed.emit(name)

    def restore_defaults(self) -> None:
        defaults = Config()
        for name, w in self._widgets.items():
            value = getattr(defaults, name)
            w.blockSignals(True)
            w.setChecked(bool(value)) if isinstance(w, QCheckBox) else w.setValue(value)
            w.blockSignals(False)
            self._apply(name, value)
        for b in self._screens.values():
            _set_checked(b, True)
        self._apply("blocked_outputs", defaults.blocked_outputs)
