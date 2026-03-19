from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QWidget,
)

from core.packer import LAYOUT_GRID, LAYOUT_HORIZONTAL, LAYOUT_VERTICAL

PRESETS = [
    ("8",   8,   8),
    ("16",  16,  16),
    ("32",  32,  32),
    ("48",  48,  48),
    ("64",  64,  64),
    ("128", 128, 128),
]


class OutputToolbar(QWidget):
    """Horizontal bottom toolbar: layout mode, output settings, export."""

    settings_changed     = pyqtSignal()
    layout_changed       = pyqtSignal(str)   # "horizontal" | "vertical" | "grid"
    export_png_requested  = pyqtSignal()
    export_json_requested = pyqtSignal()
    export_both_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self._build_ui()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def layout_mode(self) -> str:
        if self.radio_horizontal.isChecked():
            return LAYOUT_HORIZONTAL
        if self.radio_vertical.isChecked():
            return LAYOUT_VERTICAL
        return LAYOUT_GRID

    @property
    def columns(self) -> int:
        return self.spin_cols.value()

    @property
    def cell_w(self) -> int:
        return self.spin_w.value()

    @property
    def cell_h(self) -> int:
        return self.spin_h.value()

    @property
    def padding(self) -> int:
        return self.spin_padding.value()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        # Layout mode radio buttons
        self.radio_horizontal = QRadioButton("Horizontal")
        self.radio_vertical   = QRadioButton("Vertical")
        self.radio_grid       = QRadioButton("Grid")
        self.radio_horizontal.setChecked(True)

        lg = QButtonGroup(self)
        for r in (self.radio_horizontal, self.radio_vertical, self.radio_grid):
            lg.addButton(r)
            layout.addWidget(r)

        self.radio_horizontal.toggled.connect(self._on_layout_toggled)
        self.radio_vertical.toggled.connect(self._on_layout_toggled)
        self.radio_grid.toggled.connect(self._on_layout_toggled)

        layout.addWidget(_sep())

        # Columns (only visible in Grid mode)
        self.lbl_cols = QLabel("Columns:")
        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(1, 64)
        self.spin_cols.setValue(4)
        self.spin_cols.setFixedWidth(55)
        layout.addWidget(self.lbl_cols)
        layout.addWidget(self.spin_cols)
        self._cols_widgets = (self.lbl_cols, self.spin_cols)

        layout.addWidget(_sep())

        # Cell size
        layout.addWidget(QLabel("Cell:"))
        self.spin_w = QSpinBox()
        self.spin_w.setRange(1, 2048)
        self.spin_w.setValue(32)
        self.spin_w.setFixedWidth(60)
        layout.addWidget(self.spin_w)
        layout.addWidget(QLabel("×"))
        self.spin_h = QSpinBox()
        self.spin_h.setRange(1, 2048)
        self.spin_h.setValue(32)
        self.spin_h.setFixedWidth(60)
        layout.addWidget(self.spin_h)

        for label, w, h in PRESETS:
            btn = QPushButton(label)
            btn.setFixedWidth(36)
            btn.clicked.connect(lambda _, w=w, h=h: self._apply_preset(w, h))
            layout.addWidget(btn)

        layout.addWidget(_sep())

        # Padding
        layout.addWidget(QLabel("Padding:"))
        self.spin_padding = QSpinBox()
        self.spin_padding.setRange(0, 64)
        self.spin_padding.setValue(0)
        self.spin_padding.setFixedWidth(55)
        layout.addWidget(self.spin_padding)

        layout.addStretch()

        # Action buttons
        self.btn_refresh      = QPushButton("Refresh")
        self.btn_export_png   = QPushButton("Export PNG")
        self.btn_export_json  = QPushButton("Export JSON")
        self.btn_export_both  = QPushButton("Export Both")

        for btn in (self.btn_refresh, self.btn_export_png,
                    self.btn_export_json, self.btn_export_both):
            layout.addWidget(btn)

        self.btn_refresh.clicked.connect(self.settings_changed.emit)
        self.btn_export_png.clicked.connect(self.export_png_requested.emit)
        self.btn_export_json.clicked.connect(self.export_json_requested.emit)
        self.btn_export_both.clicked.connect(self.export_both_requested.emit)

        # Set initial visibility
        self._update_cols_visibility()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def set_cell_size(self, w: int, h: int):
        self.spin_w.setValue(w)
        self.spin_h.setValue(h)

    def set_layout(self, mode: str):
        """Called by main_window to sync with source panel radio."""
        self.radio_horizontal.blockSignals(True)
        self.radio_vertical.blockSignals(True)
        self.radio_grid.blockSignals(True)
        if mode == LAYOUT_HORIZONTAL:
            self.radio_horizontal.setChecked(True)
        elif mode == LAYOUT_VERTICAL:
            self.radio_vertical.setChecked(True)
        else:
            self.radio_grid.setChecked(True)
        self.radio_horizontal.blockSignals(False)
        self.radio_vertical.blockSignals(False)
        self.radio_grid.blockSignals(False)
        self._update_cols_visibility()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_layout_toggled(self):
        self._update_cols_visibility()
        self.layout_changed.emit(self.layout_mode)
        self.settings_changed.emit()

    def _update_cols_visibility(self):
        visible = self.layout_mode == LAYOUT_GRID
        for w in self._cols_widgets:
            w.setVisible(visible)

    def _apply_preset(self, w: int, h: int):
        self.spin_w.setValue(w)
        self.spin_h.setValue(h)
        self.settings_changed.emit()


def _sep() -> QWidget:
    sep = QWidget()
    sep.setFixedWidth(1)
    sep.setStyleSheet("background: #555;")
    return sep
