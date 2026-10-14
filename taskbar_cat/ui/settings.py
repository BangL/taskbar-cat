"""Einstellungsdialog, aufgebaut aus config.SPECS (Grenzen stehen nur dort)."""
from PyQt6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                             QGroupBox, QSpinBox, QVBoxLayout, QWidget)
from PyQt6.QtCore import pyqtSignal

from ..config import SPECS, Config
from ..guard import guarded

GROUPS = (
    ("Darstellung", ("sprite_scale", "debug_lines")),
    ("Verhalten", ("play_enabled", "walk_speed", "climb_speed", "p_jump", "p_climb", "p_hang")),
    ("Bedürfnisse", ("satiety_hours", "affection_hours", "feed_amount", "pet_amount")),
)


def _decimals(step: float) -> int:
    return 2 if step < 0.1 else 1 if step < 1 else 0


class SettingsDialog(QDialog):
    changed = pyqtSignal(str)

    def __init__(self, cfg: Config, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Taskbar-Cat - Einstellungen")
        self._cfg = cfg
        self._widgets: dict[str, QWidget] = {}
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
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close
                                   | QDialogButtonBox.StandardButton.RestoreDefaults)
        buttons.rejected.connect(self.hide)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(
            guarded(self.restore_defaults))
        layout.addWidget(buttons)

    def _build(self, name: str) -> QWidget:
        spec = SPECS[name]
        value = getattr(self._cfg, name)
        if spec.kind == "bool":
            w = QCheckBox(spec.label)
            w.setChecked(bool(value))
            w.toggled.connect(guarded(lambda v, n=name: self._apply(n, v)))
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
